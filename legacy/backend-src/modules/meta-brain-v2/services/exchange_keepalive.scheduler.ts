/**
 * META BRAIN V2 — EXCHANGE SNAPSHOT KEEPALIVE
 * =============================================
 *
 * Lightweight scheduler that checks exchange snapshots freshness.
 * If snapshots are older than STALE_THRESHOLD, refreshes them using
 * current market price from Bybit + last valid prediction values.
 *
 * This is a safety net for when the ML inference pipeline is down.
 * It does NOT replace the real ML pipeline — just keeps Meta Brain
 * from losing the exchange signal entirely.
 *
 * Runs every CHECK_INTERVAL (4h by default).
 */

const API_BASE = 'http://127.0.0.1:8003';
const BYBIT_BASE = 'https://api.bybit.com';
const CHECK_INTERVAL = 4 * 60 * 60 * 1000; // 4 hours
const STALE_THRESHOLD = 12 * 60 * 60 * 1000; // 12 hours

const HORIZONS = ['1D', '7D', '30D'] as const;

let handle: NodeJS.Timeout | null = null;

async function fetchBtcPrice(): Promise<number | null> {
  try {
    const resp = await fetch(`${BYBIT_BASE}/v5/market/tickers?category=linear&symbol=BTCUSDT`, {
      signal: AbortSignal.timeout(5000),
    });
    const data = await resp.json() as any;
    const ticker = data?.result?.list?.[0];
    return ticker ? parseFloat(ticker.lastPrice) : null;
  } catch {
    return null;
  }
}

async function getActiveSnapshot(horizon: string): Promise<any | null> {
  try {
    const resp = await fetch(`${API_BASE}/api/market/exchange/snapshots/active?symbol=BTCUSDT`, {
      signal: AbortSignal.timeout(5000),
    });
    const data = await resp.json() as any;
    if (!data.ok) return null;
    const snaps = data.data?.[horizon];
    return Array.isArray(snaps) && snaps.length > 0 ? snaps[0] : null;
  } catch {
    return null;
  }
}

async function createSnapshot(
  horizon: string,
  prediction: number,
  confidence: number,
  entryPrice: number
): Promise<boolean> {
  try {
    const resp = await fetch(`${API_BASE}/api/admin/exchange-ml/snapshots/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol: 'BTCUSDT',
        horizon,
        prediction,
        confidence,
        entryPrice,
        modelId: 'keepalive',
        modelVersion: 0,
      }),
      signal: AbortSignal.timeout(5000),
    });
    const data = await resp.json() as any;
    return data.ok === true;
  } catch {
    return false;
  }
}

async function checkAndRefresh(): Promise<void> {
  const now = Date.now();

  for (const horizon of HORIZONS) {
    const snap = await getActiveSnapshot(horizon);

    if (snap) {
      const age = now - new Date(snap.createdAt).getTime();
      if (age < STALE_THRESHOLD) continue; // Fresh enough
    }

    // Stale or missing — refresh
    const btcPrice = await fetchBtcPrice();
    if (!btcPrice) {
      console.warn(`[ExchangeKeepalive] Cannot fetch BTC price for ${horizon} refresh`);
      continue;
    }

    // Use last valid prediction values or conservative defaults
    const prediction = snap?.prediction ?? 0.5;
    const confidence = snap?.confidence ? Math.max(0.3, snap.confidence * 0.9) : 0.45;

    const ok = await createSnapshot(horizon, prediction, confidence, btcPrice);
    if (ok) {
      console.log(`[ExchangeKeepalive] Refreshed ${horizon} snapshot (price=$${btcPrice.toFixed(0)}, pred=${prediction})`);
    } else {
      console.warn(`[ExchangeKeepalive] Failed to refresh ${horizon} snapshot`);
    }
  }
}

export function startExchangeKeepalive(): void {
  if (handle) return;
  console.log(`[ExchangeKeepalive] Starting (check every ${CHECK_INTERVAL / 3600000}h, stale threshold ${STALE_THRESHOLD / 3600000}h)`);
  checkAndRefresh(); // Initial check
  handle = setInterval(checkAndRefresh, CHECK_INTERVAL);
}

export function stopExchangeKeepalive(): void {
  if (handle) {
    clearInterval(handle);
    handle = null;
  }
}

export async function manualRefresh(): Promise<{ refreshed: string[]; skipped: string[]; failed: string[] }> {
  const refreshed: string[] = [];
  const skipped: string[] = [];
  const failed: string[] = [];
  const now = Date.now();

  const btcPrice = await fetchBtcPrice();
  if (!btcPrice) return { refreshed: [], skipped: [], failed: HORIZONS.slice() };

  for (const horizon of HORIZONS) {
    const snap = await getActiveSnapshot(horizon);
    if (snap) {
      const age = now - new Date(snap.createdAt).getTime();
      if (age < STALE_THRESHOLD) {
        skipped.push(`${horizon} (age=${(age / 3600000).toFixed(1)}h)`);
        continue;
      }
    }

    const prediction = snap?.prediction ?? 0.5;
    const confidence = snap?.confidence ? Math.max(0.3, snap.confidence * 0.9) : 0.45;
    const ok = await createSnapshot(horizon, prediction, confidence, btcPrice);
    if (ok) refreshed.push(horizon);
    else failed.push(horizon);
  }

  return { refreshed, skipped, failed };
}
