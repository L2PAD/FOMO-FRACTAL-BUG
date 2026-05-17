/**
 * META BRAIN V2 — FORECAST TABLE SERVICE
 * ========================================
 *
 * Generates the prediction table from REAL forecast snapshot data only.
 * If no snapshot exists for a date — shows a dash ("—"), not fabricated data.
 *
 * Each snapshot provides 3 real targets: 1D, 7D, 30D.
 * The table only shows rows where actual forecast data exists.
 *
 * For the selected horizon:
 * - 1D: Yesterday + Today + Tomorrow (3 rows). Only shows target if snapshot exists.
 * - 7D: Yesterday + Today + up to 7 future days. Only days with real targets.
 * - 30D: Yesterday + Today + up to 30 future days (scrollable). Only real targets.
 */

import { ForecastSnapshot, getRecentSnapshots } from './forecast_snapshots.repo.js';

export interface ForecastTableRow {
  dayLabel: string | null;
  date: string;
  direction: string | null;
  target: number | null;
  confidence: number | null;
  status: string;
  hasData: boolean;
}

export interface ForecastTableData {
  summary: {
    winRate: number;
    avgReturn: number;
    evaluated: string;
    totalRows: number;
  };
  rows: ForecastTableRow[];
}

function formatDateShort(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00Z');
  const month = d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
  return `${month} ${d.getUTCDate()}`;
}

function addDaysUTC(dateStr: string, days: number): string {
  const ms = Date.parse(dateStr + 'T00:00:00Z') + days * 86400000;
  const d = new Date(ms);
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/**
 * Build forecast table from REAL snapshot data only.
 */
export async function buildForecastTable(
  asset: string,
  horizonDays: number,
  candles: Array<{ t: string; c: number }>,
  currentPrice: number,
): Promise<ForecastTableData> {
  // Get all snapshots
  const snapshots = await getRecentSnapshots(asset, 60);

  // Index snapshots by date
  const snapByDate = new Map<string, ForecastSnapshot>();
  for (const s of snapshots) {
    snapByDate.set(s.date, s);
  }

  // Latest snapshot is the most recent forecast (regardless of candle date)
  const latestSnap = snapshots.length > 0 ? snapshots[snapshots.length - 1] : null;

  // Candle price map
  const priceMap = new Map<string, number>();
  for (const c of candles) {
    const d = c.t.includes('T') ? c.t.split('T')[0] : c.t;
    priceMap.set(d, c.c);
  }

  // "Today" = current date (from latest snapshot or server time)
  // Uses snapshot date instead of candle date to align with forecast anchor
  const todayDate = latestSnap ? latestSnap.date : new Date().toISOString().split('T')[0];

  // Horizon key for the selected horizon
  const hKey = horizonDays <= 1 ? '1d' : horizonDays <= 7 ? '7d' : '30d';

  // How many rows to generate
  const totalDays = horizonDays <= 1 ? 3 : horizonDays + 2;

  const rows: ForecastTableRow[] = [];
  let evaluated = 0;
  let hits = 0;

  for (let i = -1; i < totalDays - 1; i++) {
    const dateStr = addDaysUTC(todayDate, i);
    const dateLabel = formatDateShort(dateStr);

    let dayLabel: string | null = null;
    if (i === -1) dayLabel = 'Yesterday';
    else if (i === 0) dayLabel = 'Today';
    else if (i === 1) dayLabel = 'Tomorrow';

    // Find snapshot for this date
    // For past: exact date match
    // For today/tomorrow: use latest snapshot (most recent forecast)
    const snap = (i >= 0 && latestSnap) ? latestSnap : snapByDate.get(dateStr);

    if (!snap) {
      // No snapshot available — show dash
      rows.push({
        dayLabel,
        date: dateLabel,
        direction: null,
        target: null,
        confidence: null,
        status: '—',
        hasData: false,
      });
      continue;
    }

    if (i <= 0) {
      // Past/today WITH snapshot — show the snapshot's target for selected horizon
      const target = snap.forecast[hKey]?.target ?? null;
      const actualPrice = priceMap.get(dateStr);
      let status = 'Pending';

      if (i < 0 && actualPrice != null && target != null) {
        // Past — evaluate
        evaluated++;
        if (snap.verdict === 'NEUTRAL') {
          status = 'Missed opp';
        } else if (snap.verdict === 'LONG' && actualPrice >= snap.priceNow) {
          status = 'Hit';
          hits++;
        } else if (snap.verdict === 'SHORT' && actualPrice <= snap.priceNow) {
          status = 'Hit';
          hits++;
        } else {
          status = 'Miss';
        }
      } else if (i === 0) {
        evaluated++;
        if (snap.verdict === 'NEUTRAL') {
          status = 'Missed opp';
        } else if (snap.verdict === 'LONG' && currentPrice >= snap.priceNow) {
          status = 'Hit';
          hits++;
        } else if (snap.verdict === 'SHORT' && currentPrice <= snap.priceNow) {
          status = 'Hit';
          hits++;
        } else {
          status = 'Miss';
        }
      }

      rows.push({
        dayLabel,
        date: dateLabel,
        direction: snap.verdict,
        target: target ? Math.round(target) : null,
        confidence: Math.round(snap.metaConfidence * 100),
        status,
        hasData: true,
      });
      continue;
    }

    // Future days — only show target from the LATEST snapshot
    // Use only the most recent forecast to avoid showing stale predictions
    // from old snapshots that happen to land on this date.

    let futureTarget: number | null = null;
    let futureSnap: ForecastSnapshot | null = null;
    let futureLabel = '';

    if (latestSnap) {
      const snapMs = Date.parse(latestSnap.date + 'T00:00:00Z');
      const thisMs = Date.parse(dateStr + 'T00:00:00Z');
      const diffDays = Math.round((thisMs - snapMs) / 86400000);

      // Only match if this date falls within the selected horizon
      if (diffDays === 1 && horizonDays >= 1) {
        futureTarget = latestSnap.forecast['1d']?.target ?? null;
        futureSnap = latestSnap;
        futureLabel = '1D';
      } else if (diffDays === 7 && horizonDays >= 7) {
        futureTarget = latestSnap.forecast['7d']?.target ?? null;
        futureSnap = latestSnap;
        futureLabel = '7D';
      } else if (diffDays === 30 && horizonDays >= 30) {
        futureTarget = latestSnap.forecast['30d']?.target ?? null;
        futureSnap = latestSnap;
        futureLabel = '30D';
      }
    }

    if (futureTarget != null && futureSnap) {
      rows.push({
        dayLabel,
        date: `${dateLabel} (${futureLabel})`,
        direction: futureSnap.verdict,
        target: Math.round(futureTarget),
        confidence: Math.round(futureSnap.metaConfidence * 100),
        status: 'Pending',
        hasData: true,
      });
    } else {
      // No real forecast for this date — show dash
      rows.push({
        dayLabel,
        date: dateLabel,
        direction: null,
        target: null,
        confidence: null,
        status: '—',
        hasData: false,
      });
    }
  }

  const winRate = evaluated > 0 ? Math.round((hits / evaluated) * 100) : 0;

  return {
    summary: {
      winRate,
      avgReturn: 0,
      evaluated: `${evaluated}/${rows.filter(r => r.hasData).length}`,
      totalRows: rows.length,
    },
    rows,
  };
}
