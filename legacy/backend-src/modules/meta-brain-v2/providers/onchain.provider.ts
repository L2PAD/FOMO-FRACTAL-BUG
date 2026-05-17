/**
 * ONCHAIN SIGNAL PROVIDER
 * =======================
 * 
 * Fetches signal from Sentiment Intelligence service (which aggregates
 * on-chain flow data). Maps flow state → MetaSignal.
 * 
 * On-chain V1 is active; V2 requires ONCHAIN_V2_ENABLED=true.
 * Uses /api/market/sentiment/intelligence-v1 as source (contains on-chain state).
 * 
 * Mapping:
 *   ACCUMULATION → LONG
 *   DISTRIBUTION → SHORT
 *   NEUTRAL      → NEUTRAL
 */

import { MetaSignalProvider, SignalProviderInput } from '../contracts/provider.contract.js';
import { RawMetaSignal, Direction } from '../contracts/signal.contract.js';

const API_BASE = 'http://127.0.0.1:8003';
const TTL_MS = 24 * 3_600_000; // 24h

export class OnChainProvider implements MetaSignalProvider {
  readonly key = 'onchain';
  readonly version = 'v1.0';

  async getSignal(input: SignalProviderInput): Promise<RawMetaSignal> {
    // Use sentiment intelligence which includes on-chain data
    const url = `${API_BASE}/api/market/sentiment/intelligence-v1?asset=${input.asset}&window=${input.horizon}`;
    const resp = await fetch(url);
    const data = await resp.json();

    if (!data.ok) {
      return this.failSignal(input, 'OnChain/Sentiment intelligence API not-ok');
    }

    const reliab = data.data?.reliability || {};
    const uriScore = reliab.uriScore ?? 0.5;
    const safeMode = reliab.safeMode ?? true;
    const confMultiplier = reliab.confidenceMultiplier ?? 0.5;

    // Try to extract on-chain specific data
    const onchainData = data.data?.onchain || data.data?.flow || {};
    const flowScore = onchainData.flowScore ?? onchainData.score ?? 0;
    const flowState = onchainData.state || onchainData.finalState || 'NEUTRAL';

    let direction: Direction = 'NEUTRAL';
    let score = 0;

    if (flowState === 'ACCUMULATION' || flowScore > 0.2) {
      direction = 'LONG';
      score = Math.min(1, Math.abs(flowScore) || 0.4);
    } else if (flowState === 'DISTRIBUTION' || flowScore < -0.2) {
      direction = 'SHORT';
      score = -Math.min(1, Math.abs(flowScore) || 0.4);
    }

    // If no on-chain specific data, use reliability score as a weak signal
    if (score === 0 && uriScore > 0) {
      // URI > 0.7 = market healthy → slight long bias
      // URI < 0.4 = degraded → slight short bias
      if (uriScore > 0.7 && !safeMode) {
        direction = 'LONG';
        score = 0.2;
      } else if (uriScore < 0.4) {
        direction = 'SHORT';
        score = -0.2;
      }
    }

    const confidence = Math.max(0, Math.min(1, confMultiplier));

    const reasons: string[] = [
      `uriScore=${(uriScore*100).toFixed(0)}%`,
      `safeMode=${safeMode}`,
    ];
    if (flowState !== 'NEUTRAL') reasons.push(`flowState=${flowState}`);
    if (flowScore !== 0) reasons.push(`flowScore=${flowScore.toFixed(2)}`);

    return {
      module: this.key,
      asset: input.asset,
      horizon: input.horizon,
      direction,
      score,
      confidence,
      asOfTs: Date.now(), // intelligence is computed on-demand
      ttlMs: TTL_MS,
      sourceId: `onchain_${input.asset}_${new Date().toISOString().slice(0,13)}`,
      basis: 'close',
      health: uriScore > 0.5 ? 'OK' : 'WARN',
      drift: safeMode ? 0.5 : 0.1,
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
      sourceId: `onchain_fail_${Date.now()}`,
      basis: 'close',
      health: 'FAIL',
      reasons: [detail],
    };
  }
}
