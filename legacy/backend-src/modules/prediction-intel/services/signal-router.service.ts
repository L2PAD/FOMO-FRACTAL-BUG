/**
 * Signal Router
 *
 * Aggregates normalized signals for a market and produces
 * a SignalBatch with net impacts ready for pipeline injection.
 *
 * Key rule: probability impact only flows from resolution-relevant signals.
 */
import type { NormalizedSignal, SignalBatch } from '../types/signal.types.js';

/**
 * Aggregate signals for a single market.
 */
export function aggregateSignals(
  marketId: string,
  asset: string,
  signals: NormalizedSignal[],
): SignalBatch {
  if (signals.length === 0) {
    return {
      marketId,
      asset,
      signals: [],
      aggregated: {
        netProbabilityImpact: 0,
        netConfidenceImpact: 0,
        netAlignmentImpact: 0,
        dominantBias: 'neutral',
        signalCount: 0,
        avgNovelty: 0,
        avgAlreadyPriced: 0,
        topDriver: 'No relevant signals',
      },
    };
  }

  // Weighted sum — stronger signals have more influence
  let netProb = 0;
  let netConf = 0;
  let netAlign = 0;
  let bullishWeight = 0;
  let bearishWeight = 0;
  let totalNovelty = 0;
  let totalPriced = 0;

  for (const sig of signals) {
    const w = sig.strength;
    netProb += sig.impact.probability * w;
    netConf += sig.impact.confidence * w;
    netAlign += sig.impact.alignment * w;

    if (sig.bias === 'bullish') bullishWeight += w;
    if (sig.bias === 'bearish') bearishWeight += w;

    totalNovelty += sig.novelty;
    totalPriced += sig.alreadyPriced;
  }

  // Normalize by total weight
  const totalWeight = signals.reduce((s, sig) => s + sig.strength, 0) || 1;
  netProb /= totalWeight;
  netConf /= totalWeight;
  netAlign /= totalWeight;

  // Diminishing returns: cap aggregated impact
  netProb = capImpact(netProb, 0.15);
  netConf = capImpact(netConf, 0.20);
  netAlign = capImpact(netAlign, 0.15);

  const dominantBias: 'bullish' | 'bearish' | 'neutral' =
    bullishWeight > bearishWeight * 1.2 ? 'bullish' :
    bearishWeight > bullishWeight * 1.2 ? 'bearish' :
    'neutral';

  const topSignal = signals[0]; // already sorted by strength

  return {
    marketId,
    asset,
    signals,
    aggregated: {
      netProbabilityImpact: round(netProb),
      netConfidenceImpact: round(netConf),
      netAlignmentImpact: round(netAlign),
      dominantBias,
      signalCount: signals.length,
      avgNovelty: round(totalNovelty / signals.length),
      avgAlreadyPriced: round(totalPriced / signals.length),
      topDriver: topSignal?.smartDriver || 'No signals',
    },
  };
}

function capImpact(val: number, maxAbs: number): number {
  return Math.max(-maxAbs, Math.min(maxAbs, val));
}

function round(n: number): number {
  return Math.round(n * 10000) / 10000;
}
