/**
 * Source Performance
 *
 * Tracks which sources give alpha vs noise.
 * Analyzes win rate, early signal score, noise score per source.
 */

import type { SourcePerformance, SourceStat } from '../types/digest.types.js';

interface ReviewData {
  correctness: { correctness: string };
  sourceAttribution?: { sources: string[]; primarySource?: string };
  traces: { edge: number }[];
}

class SourcePerformanceService {
  analyze(reviews: ReviewData[]): SourcePerformance {
    const sourceMap = new Map<string, { wins: number; losses: number; edges: number[]; earlySignals: number; total: number }>();

    for (const r of reviews) {
      const sources = r.sourceAttribution?.sources || [r.sourceAttribution?.primarySource].filter(Boolean) as string[];
      const isCorrect = r.correctness?.correctness === 'CORRECT';
      const edge = Math.abs(r.traces?.[0]?.edge || 0);

      for (const source of sources) {
        if (!source) continue;
        if (!sourceMap.has(source)) {
          sourceMap.set(source, { wins: 0, losses: 0, edges: [], earlySignals: 0, total: 0 });
        }
        const s = sourceMap.get(source)!;
        s.total++;
        s.edges.push(edge);
        if (isCorrect) s.wins++;
        else s.losses++;
      }
    }

    // If no source data, provide system-level defaults
    if (sourceMap.size === 0) {
      sourceMap.set('system_model', { wins: reviews.filter(r => r.correctness?.correctness === 'CORRECT').length, losses: reviews.filter(r => r.correctness?.correctness !== 'CORRECT').length, edges: reviews.map(r => Math.abs(r.traces?.[0]?.edge || 0)), earlySignals: 0, total: reviews.length });
    }

    const stats: SourceStat[] = [];
    for (const [source, data] of sourceMap.entries()) {
      const avgImpact = data.edges.length > 0 ? data.edges.reduce((a, b) => a + b, 0) / data.edges.length : 0;
      const winRate = data.total > 0 ? data.wins / data.total : 0;
      const noiseScore = data.total > 2 ? 1 - winRate : 0.5; // need enough data

      stats.push({
        source,
        winRate: Math.round(winRate * 100) / 100,
        avgImpact: Math.round(avgImpact * 10000) / 10000,
        signalCount: data.total,
        earlySignalScore: Math.round((data.earlySignals / Math.max(data.total, 1)) * 100) / 100,
        noiseScore: Math.round(noiseScore * 100) / 100,
      });
    }

    stats.sort((a, b) => b.winRate - a.winRate);

    return {
      topSources: stats.filter(s => s.winRate >= 0.6).slice(0, 5),
      decliningSources: stats.filter(s => s.winRate < 0.4 && s.signalCount >= 2).slice(0, 5),
      noisySources: stats.filter(s => s.noiseScore > 0.6).slice(0, 5),
    };
  }
}

export const sourcePerformanceService = new SourcePerformanceService();
