/**
 * SENTIMENT SIGNAL PROVIDER
 * =========================
 * 
 * Fetches signal from Sentiment Intelligence (Twitter sentiment).
 * Maps bias/confidence → MetaSignal.
 * 
 * Source: GET /api/market/sentiment/intelligence-v1?asset={asset}&window={horizon}
 */

import { MetaSignalProvider, SignalProviderInput } from '../contracts/provider.contract.js';
import { RawMetaSignal, Direction } from '../contracts/signal.contract.js';

const API_BASE = 'http://127.0.0.1:8003';
const TTL_MS = 12 * 3_600_000; // 12h

export class SentimentProvider implements MetaSignalProvider {
  readonly key = 'sentiment';
  readonly version = 'v1.0';

  async getSignal(input: SignalProviderInput): Promise<RawMetaSignal> {
    const url = `${API_BASE}/api/market/sentiment/intelligence-v1?asset=${input.asset}&window=${input.horizon}`;
    const resp = await fetch(url);
    const data = await resp.json();

    if (!data.ok) {
      return this.failSignal(input, 'Sentiment intelligence API not-ok');
    }

    const reliab = data.data?.reliability || {};
    const agg = data.data?.aggregation || {};
    const action = data.data?.action || {};
    const regime = data.data?.regime || {};

    // Try to extract sentiment bias
    const bias = agg.bias ?? agg.sentimentBias ?? 0;
    const sentimentConfidence = agg.confidence ?? reliab.confidenceMultiplier ?? 0.5;
    const sentimentAction = action.direction || action.action || '';

    let direction: Direction = 'NEUTRAL';
    let score = 0;

    // Use bias as primary signal
    if (Math.abs(bias) > 0.15) {
      direction = bias > 0 ? 'LONG' : 'SHORT';
      score = Math.max(-1, Math.min(1, bias));
    }

    // Override with action if available
    if (sentimentAction === 'LONG' || sentimentAction === 'BUY') {
      direction = 'LONG';
      if (score <= 0) score = 0.3;
    } else if (sentimentAction === 'SHORT' || sentimentAction === 'SELL') {
      direction = 'SHORT';
      if (score >= 0) score = -0.3;
    }

    const confidence = Math.max(0, Math.min(1, sentimentConfidence));
    const uriScore = reliab.uriScore ?? 0.5;

    const reasons: string[] = [];
    if (bias !== 0) reasons.push(`bias=${bias.toFixed(2)}`);
    if (sentimentAction) reasons.push(`action=${sentimentAction}`);
    reasons.push(`uriScore=${(uriScore*100).toFixed(0)}%`);
    if (regime.marketRegime) reasons.push(`regime=${regime.marketRegime}`);

    return {
      module: this.key,
      asset: input.asset,
      horizon: input.horizon,
      direction,
      score,
      confidence,
      asOfTs: Date.now(), // computed on-demand
      ttlMs: TTL_MS,
      sourceId: `sentiment_${input.asset}_${input.horizon}_${new Date().toISOString().slice(0,13)}`,
      basis: 'close',
      health: uriScore > 0.5 && !reliab.safeMode ? 'OK' : 'WARN',
      drift: reliab.safeMode ? 0.4 : 0.1,
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
      sourceId: `sentiment_fail_${Date.now()}`,
      basis: 'close',
      health: 'FAIL',
      reasons: [detail],
    };
  }
}
