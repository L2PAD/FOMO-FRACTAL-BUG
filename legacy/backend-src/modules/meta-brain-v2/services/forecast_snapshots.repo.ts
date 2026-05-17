/**
 * META BRAIN V2 — FORECAST SNAPSHOTS REPOSITORY
 * ================================================
 *
 * Stores daily forecast snapshots for rolling forecast curve.
 * Each snapshot captures the Meta Brain's 1d/7d/30d targets at a point in time.
 *
 * Collection: meta_brain_forecasts
 *
 * The forecast-curve endpoint reads these snapshots and builds
 * a natural curve from real prediction points (not interpolation).
 */

import { getMongoDb } from '../../../db/mongoose.js';

const COLLECTION = 'meta_brain_forecasts';
const THROTTLE_MS = 60 * 60 * 1000; // 1 hour — don't save more often

export interface ForecastSnapshot {
  ts: number;
  date: string;
  asset: string;
  priceNow: number;
  verdict: string;
  metaConfidence: number;
  regime: string;
  forecast: {
    '1d': { target: number; expReturn: number };
    '7d': { target: number; expReturn: number };
    '30d': { target: number; expReturn: number };
  };
}

/**
 * Save a forecast snapshot (throttled — max 1 per hour per asset).
 */
export async function saveForecastSnapshot(snap: ForecastSnapshot): Promise<boolean> {
  const db = getMongoDb();
  if (!db) return false;

  const col = db.collection(COLLECTION);

  // Check last snapshot time
  const last = await col
    .find({ asset: snap.asset }, { projection: { _id: 0, ts: 1 } })
    .sort({ ts: -1 })
    .limit(1)
    .toArray();

  if (last.length > 0 && (snap.ts - last[0].ts) < THROTTLE_MS) {
    return false; // Too soon
  }

  await col.insertOne(snap);
  return true;
}

/**
 * Get recent forecast snapshots for building the rolling curve.
 */
export async function getRecentSnapshots(
  asset: string,
  limit: number = 40
): Promise<ForecastSnapshot[]> {
  const db = getMongoDb();
  if (!db) return [];

  const docs = await db.collection(COLLECTION)
    .find({ asset }, { projection: { _id: 0 } })
    .sort({ ts: -1 })
    .limit(limit)
    .toArray();

  return docs.reverse() as ForecastSnapshot[];
}

/**
 * Build the rolling forecast curve from stored snapshots.
 *
 * For each snapshot at time t0:
 *   - t0 + 1d  → forecast.1d.target
 *   - t0 + 7d  → forecast.7d.target
 *   - t0 + 30d → forecast.30d.target
 *
 * All points are merged, deduplicated by date, and sorted.
 * The result is a natural curve based on real forecasts.
 */
export function buildForecastCurve(
  snapshots: ForecastSnapshot[],
  priceNow: number
): {
  curve: Array<{ t: string; v: number; type: 'anchor' | '1d' | '7d' | '30d' }>;
  markers: Array<{ t: string; v: number; label: string }>;
} {
  if (snapshots.length === 0) {
    return { curve: [], markers: [] };
  }

  // Map: date → { value, type, ts } (keep best per date)
  const pointMap = new Map<string, { v: number; type: string; ts: number }>();

  for (const snap of snapshots) {
    const baseDate = new Date(snap.ts);

    // Anchor point (the price at time of forecast)
    const anchorKey = baseDate.toISOString().split('T')[0];
    pointMap.set(anchorKey, { v: snap.priceNow, type: 'anchor', ts: snap.ts });

    // 1D point
    const d1 = new Date(baseDate);
    d1.setDate(d1.getDate() + 1);
    const k1 = d1.toISOString().split('T')[0];
    if (!pointMap.has(k1) || pointMap.get(k1)!.ts < snap.ts) {
      pointMap.set(k1, { v: snap.forecast['1d'].target, type: '1d', ts: snap.ts });
    }

    // 7D point
    const d7 = new Date(baseDate);
    d7.setDate(d7.getDate() + 7);
    const k7 = d7.toISOString().split('T')[0];
    if (!pointMap.has(k7) || pointMap.get(k7)!.ts < snap.ts) {
      pointMap.set(k7, { v: snap.forecast['7d'].target, type: '7d', ts: snap.ts });
    }

    // 30D point
    const d30 = new Date(baseDate);
    d30.setDate(d30.getDate() + 30);
    const k30 = d30.toISOString().split('T')[0];
    if (!pointMap.has(k30) || pointMap.get(k30)!.ts < snap.ts) {
      pointMap.set(k30, { v: snap.forecast['30d'].target, type: '30d', ts: snap.ts });
    }
  }

  // Sort by date
  const sorted = Array.from(pointMap.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([t, data]) => ({
      t,
      v: Math.round(data.v * 100) / 100,
      type: data.type as 'anchor' | '1d' | '7d' | '30d',
    }));

  // Build markers from the LATEST snapshot only
  const latest = snapshots[snapshots.length - 1];
  const markers: Array<{ t: string; v: number; label: string }> = [];
  if (latest) {
    const base = new Date(latest.ts);

    const m1 = new Date(base); m1.setDate(m1.getDate() + 1);
    markers.push({ t: m1.toISOString().split('T')[0], v: latest.forecast['1d'].target, label: '1D' });

    const m7 = new Date(base); m7.setDate(m7.getDate() + 7);
    markers.push({ t: m7.toISOString().split('T')[0], v: latest.forecast['7d'].target, label: '7D' });

    const m30 = new Date(base); m30.setDate(m30.getDate() + 30);
    markers.push({ t: m30.toISOString().split('T')[0], v: latest.forecast['30d'].target, label: '30D' });
  }

  return { curve: sorted, markers };
}
