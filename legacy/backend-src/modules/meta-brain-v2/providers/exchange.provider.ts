/**
 * EXCHANGE SIGNAL PROVIDER
 * ========================
 * 
 * Fetches signal from Exchange ML active snapshots.
 * Maps prediction/confidence/horizon → MetaSignal.
 * 
 * Source: GET /api/market/exchange/snapshots/active?symbol={asset}USDT
 */

import { MetaSignalProvider, SignalProviderInput } from '../contracts/provider.contract.js';
import { RawMetaSignal, Direction, Horizon } from '../contracts/signal.contract.js';

const API_BASE = 'http://127.0.0.1:8003';
const TTL_MS = 6 * 3_600_000; // 6h

const HORIZON_KEY_MAP: Record<number, string> = {
  1: '1D',
  7: '7D',
  30: '30D',
};

export class ExchangeProvider implements MetaSignalProvider {
  readonly key = 'exchange';
  readonly version = 'v1.0';

  async getSignal(input: SignalProviderInput): Promise<RawMetaSignal> {
    const symbol = `${input.asset}USDT`;
    const url = `${API_BASE}/api/market/exchange/snapshots/active?symbol=${symbol}`;
    const resp = await fetch(url);
    const data = await resp.json();

    if (!data.ok || !data.data) {
      return this.failSignal(input, 'Exchange snapshots API returned not-ok');
    }

    const horizonKey = HORIZON_KEY_MAP[input.horizonDays] || '7D';
    const snapshots: any[] = data.data[horizonKey] || [];

    // Find snapshot for this asset
    const snap = snapshots.find((s: any) => s.symbol === symbol) || snapshots[0];

    if (!snap) {
      return this.failSignal(input, `No active snapshot for ${symbol} ${horizonKey}`);
    }

    // prediction: probability of WIN (up move)
    const prediction = snap.prediction ?? 0.5;
    const confidence = snap.confidence ?? 0;

    let direction: Direction = 'NEUTRAL';
    if (prediction > 0.55) direction = 'LONG';
    else if (prediction < 0.45) direction = 'SHORT';

    // Score: map prediction (0..1) → (-1..+1)
    const score = Math.max(-1, Math.min(1, (prediction - 0.5) * 2));

    const createdAt = snap.createdAt ? new Date(snap.createdAt).getTime() : Date.now();

    const reasons: string[] = [
      `prediction=${(prediction*100).toFixed(0)}%`,
      `class=${snap.predictedClass ?? 'N/A'}`,
      `entry=$${snap.entryPrice ?? 'N/A'}`,
    ];
    if (snap.biasModifier) reasons.push(`bias=${snap.biasModifier}`);

    return {
      module: this.key,
      asset: input.asset,
      horizon: input.horizon,
      direction,
      score,
      confidence: Math.max(0, Math.min(1, confidence)),
      targetPrice: snap.entryPrice,
      asOfTs: createdAt,
      ttlMs: TTL_MS,
      sourceId: snap.snapshotId || `exch_${symbol}_${horizonKey}_${Date.now()}`,
      basis: 'close',
      health: confidence > 0.4 ? 'OK' : 'WARN',
      reasons,
    };
  }

  private failSignal(input: SignalProviderInput, detail: string): RawMetaSignal {
    return {
      module: this.key,
      asset: input.asset,
      horizon: input.horizon,
      direction: 'NEUTRAL',
      score: 0,
      confidence: 0,
      asOfTs: Date.now(),
      ttlMs: TTL_MS,
      sourceId: `exchange_fail_${Date.now()}`,
      basis: 'close',
      health: 'FAIL',
      reasons: [detail],
    };
  }
}
