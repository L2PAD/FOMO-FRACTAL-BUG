/**
 * FRACTAL SIGNAL PROVIDER
 * =======================
 * 
 * Fetches signal from Fractal Engine via focus-pack API.
 * Maps scenario probabilities + diagnostics → MetaSignal.
 * 
 * Source: GET /api/fractal/v2.1/focus-pack?symbol={asset}&focus={horizon}&mode=crossAsset
 */

import { MetaSignalProvider, SignalProviderInput } from '../contracts/provider.contract.js';
import { RawMetaSignal, Direction } from '../contracts/signal.contract.js';

const API_BASE = 'http://127.0.0.1:8003';
const TTL_MS = 48 * 3_600_000; // 48h

const HORIZON_MAP: Record<number, string> = {
  1: '1d',
  7: '7d',
  30: '30d',
};

export class FractalProvider implements MetaSignalProvider {
  readonly key = 'fractal';
  readonly version = 'v2.1';

  async getSignal(input: SignalProviderInput): Promise<RawMetaSignal> {
    const focus = HORIZON_MAP[input.horizonDays] || '7d';

    const url = `${API_BASE}/api/fractal/v2.1/focus-pack?symbol=${input.asset}&focus=${focus}&mode=crossAsset`;
    const resp = await fetch(url);
    const data = await resp.json();

    if (!data.ok || !data.focusPack) {
      return this.failSignal(input, 'Fractal API returned not-ok');
    }

    const fp = data.focusPack;
    const scenario = fp.scenario || {};
    const diag = fp.diagnostics || {};
    const meta = fp.meta || {};

    // Extract direction from scenario
    const probUp = scenario.probUp ?? 0.5;
    const probDown = scenario.probDown ?? 0.5;
    const p50 = scenario.returns?.p50 ?? 0;

    let direction: Direction = 'NEUTRAL';
    if (probUp > 0.55 && p50 > 0.01) direction = 'LONG';
    else if (probDown > 0.55 && p50 < -0.01) direction = 'SHORT';

    // Score: map p50 return to [-1..+1], clamped
    const score = Math.max(-1, Math.min(1, p50 * 5));

    // Confidence from diagnostics reliability
    const confidence = Math.max(0, Math.min(1, diag.reliability ?? 0.5));

    // asOfTs from meta
    const asOfTs = meta.asOf ? new Date(meta.asOf).getTime() : Date.now();

    const reasons: string[] = [];
    if (direction === 'LONG') reasons.push(`probUp=${(probUp*100).toFixed(0)}% p50=+${(p50*100).toFixed(1)}%`);
    else if (direction === 'SHORT') reasons.push(`probDown=${(probDown*100).toFixed(0)}% p50=${(p50*100).toFixed(1)}%`);
    else reasons.push(`neutral: probUp=${(probUp*100).toFixed(0)}% p50=${(p50*100).toFixed(1)}%`);
    if (diag.qualityScore) reasons.push(`quality=${(diag.qualityScore*100).toFixed(0)}%`);
    reasons.push(`sampleSize=${scenario.sampleSize ?? 'N/A'}`);

    return {
      module: this.key,
      asset: input.asset,
      horizon: input.horizon,
      direction,
      score,
      confidence,
      expectedMovePct: p50,
      band: scenario.returns ? {
        p25: scenario.returns.p25 ?? 0,
        p50: scenario.returns.p50 ?? 0,
        p75: scenario.returns.p75 ?? 0,
      } : undefined,
      asOfTs,
      ttlMs: TTL_MS,
      sourceId: `focuspack_${input.asset}_${focus}_${new Date(asOfTs).toISOString().slice(0,10)}`,
      basis: 'close',
      health: diag.reliability > 0.5 ? 'OK' : 'WARN',
      drift: diag.entropy ? Math.min(1, diag.entropy) : undefined,
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
      sourceId: `fractal_fail_${Date.now()}`,
      basis: 'close',
      health: 'FAIL',
      reasons: [detail],
    };
  }
}
