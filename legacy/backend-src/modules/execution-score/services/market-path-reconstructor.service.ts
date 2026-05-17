/**
 * Market Path Reconstructor
 *
 * Reconstructs the market's probability path after a signal.
 * Computes edge windows (when edge was available and how long).
 */

import type { MarketPath, EdgeWindow } from '../types/execution-score.types.js';

class MarketPathReconstructorService {
  /**
   * Reconstruct market path from trace snapshots.
   * snapshots: array of { timestamp, marketProb, edge } ordered by time.
   * If no snapshots available, simulate from available data.
   */
  reconstruct(
    entryProb: number,
    fairProb: number,
    snapshots: { timestamp: string; marketProb: number }[],
  ): MarketPath {
    if (snapshots.length >= 2) {
      return this.fromSnapshots(entryProb, fairProb, snapshots);
    }
    return this.simulate(entryProb, fairProb);
  }

  private fromSnapshots(
    entryProb: number,
    fairProb: number,
    snaps: { timestamp: string; marketProb: number }[],
  ): MarketPath {
    const sorted = [...snaps].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
    const probs = sorted.map(s => s.marketProb);

    const t0 = probs[0] ?? entryProb;
    const pickAt = (idx: number) => idx < probs.length ? probs[idx] : probs[probs.length - 1];

    // Approximate time indices (assuming roughly even spacing)
    const step = Math.max(1, Math.floor(probs.length / 6));

    const path: MarketPath = {
      t0,
      t5m: pickAt(step),
      t15m: pickAt(step * 2),
      t1h: pickAt(step * 3),
      t4h: pickAt(step * 4),
      t24h: pickAt(step * 5),
      high: Math.max(...probs),
      low: Math.min(...probs),
      final: probs[probs.length - 1],
      edgeWindows: this.computeEdgeWindows(t0, fairProb, probs),
    };

    return path;
  }

  /**
   * Simulate a market path when no snapshots exist.
   * Uses entry prob and fair prob to model probable trajectory.
   */
  private simulate(entryProb: number, fairProb: number): MarketPath {
    const edge = fairProb - entryProb;
    const absEdge = Math.abs(edge);
    const dir = edge > 0 ? 1 : -1;

    // Simulate gradual repricing toward fair value
    const decay = (t: number) => entryProb + dir * absEdge * (1 - Math.exp(-t / 3));

    const path: MarketPath = {
      t0: entryProb,
      t5m: this.clamp(decay(0.08)),
      t15m: this.clamp(decay(0.25)),
      t1h: this.clamp(decay(1)),
      t4h: this.clamp(decay(4)),
      t24h: this.clamp(decay(24)),
      high: this.clamp(entryProb + dir * absEdge * 1.15),
      low: this.clamp(entryProb - dir * absEdge * 0.2),
      final: this.clamp(decay(48)),
      edgeWindows: this.simulateEdgeWindows(entryProb, fairProb),
    };

    return path;
  }

  private computeEdgeWindows(
    entryProb: number,
    fairProb: number,
    probs: number[],
  ): EdgeWindow[] {
    const windows: EdgeWindow[] = [];
    const totalEdge = Math.abs(fairProb - entryProb);
    if (totalEdge < 0.01) return windows;

    // Create 4 windows
    const windowSize = Math.max(1, Math.floor(probs.length / 4));
    for (let i = 0; i < 4; i++) {
      const start = i * windowSize;
      const end = Math.min(start + windowSize, probs.length);
      const slice = probs.slice(start, end);
      if (slice.length === 0) continue;

      const avgProb = slice.reduce((a, b) => a + b, 0) / slice.length;
      const remainingEdge = Math.abs(fairProb - avgProb);
      const pctEdge = remainingEdge / totalEdge;

      windows.push({
        startMin: i * 15,
        endMin: (i + 1) * 15,
        avgEdge: Math.round(remainingEdge * 10000) / 10000,
        available: pctEdge > 0.3,
      });
    }

    return windows;
  }

  private simulateEdgeWindows(entryProb: number, fairProb: number): EdgeWindow[] {
    const totalEdge = Math.abs(fairProb - entryProb);
    if (totalEdge < 0.01) return [];

    return [
      { startMin: 0, endMin: 5, avgEdge: Math.round(totalEdge * 0.95 * 10000) / 10000, available: true },
      { startMin: 5, endMin: 15, avgEdge: Math.round(totalEdge * 0.80 * 10000) / 10000, available: true },
      { startMin: 15, endMin: 60, avgEdge: Math.round(totalEdge * 0.55 * 10000) / 10000, available: true },
      { startMin: 60, endMin: 240, avgEdge: Math.round(totalEdge * 0.25 * 10000) / 10000, available: totalEdge > 0.05 },
    ];
  }

  private clamp(v: number): number {
    return Math.max(0.01, Math.min(0.99, Math.round(v * 10000) / 10000));
  }
}

export const marketPathReconstructorService = new MarketPathReconstructorService();
