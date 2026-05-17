/**
 * EXCHANGE SNAPSHOT BUILDER
 * =========================
 * 
 * Transforms raw exchange_observations into decision-ready snapshots
 * for Meta Brain V2 consumption.
 * 
 * INPUT:  exchange_observations (raw ML predictions, funding, OI, volume)
 * OUTPUT: exchange_prediction_snapshots (standardized decision format)
 * 
 * Meta Brain reads ONLY from snapshots, never from raw observations.
 */

import mongoose from 'mongoose';

interface ExchangeSnapshot {
  asset: string;
  horizon: '1D' | '7D' | '30D';
  timestamp: Date;
  direction: 'LONG' | 'SHORT' | 'NEUTRAL';
  score: number;
  confidence: number;
  components: {
    bull: number;
    bear: number;
    sampleSize: number;
    avgPrediction: number;
    fundingBias: number;
  };
  source: string;
}

/**
 * Build Exchange snapshot for specific asset + horizon
 * Aggregates recent observations into a single decision signal
 */
export async function buildExchangeSnapshot(
  asset: string,
  horizon: '1D' | '7D' | '30D' = '7D'
): Promise<ExchangeSnapshot | null> {
  const db = mongoose.connection.db;
  if (!db) {
    console.warn('[ExchangeSnapshotBuilder] MongoDB not connected');
    return null;
  }

  // Fetch recent observations (last 50 for this asset + horizon)
  const observations = await db
    .collection('exchange_observations')
    .find({ 
      asset,
      // No horizon filtering - exchange_observations don't have horizon field
      timestamp: { $gte: Date.now() - 7 * 24 * 3600000 }, // last 7 days
    })
    .sort({ timestamp: -1 })
    .limit(50)
    .toArray();

  if (observations.length === 0) {
    console.warn(`[ExchangeSnapshotBuilder] No observations for ${asset} ${horizon}`);
    return null;
  }

  // Aggregate signals
  let bull = 0;
  let bear = 0;
  let totalConfidence = 0;
  let totalPrediction = 0;
  let fundingSum = 0;

  for (const obs of observations) {
    // prediction is probability of UP move (0..1)
    const prediction = obs.prediction ?? 0.5;
    const confidence = obs.confidence ?? 0;
    const weight = Math.max(0, confidence); // weight by confidence
    
    // Funding rate bias (if available)
    const funding = obs.fundingRate ?? 0;
    fundingSum += funding;

    // Accumulate bull/bear sentiment
    if (prediction > 0.5) {
      bull += (prediction - 0.5) * 2 * weight; // normalize to [0..1]
    } else if (prediction < 0.5) {
      bear += (0.5 - prediction) * 2 * weight;
    }

    totalConfidence += confidence;
    totalPrediction += prediction;
  }

  const total = bull + bear;
  
  // Calculate final direction and score
  let direction: 'LONG' | 'SHORT' | 'NEUTRAL' = 'NEUTRAL';
  let finalScore = 0;

  if (total > 0) {
    finalScore = (bull - bear) / total; // [-1..+1]
    
    if (finalScore >= 0.15) direction = 'LONG';
    else if (finalScore <= -0.15) direction = 'SHORT';
  }

  // Average confidence (clamped to 0.95 max for safety)
  const avgConfidence = Math.min(0.95, totalConfidence / observations.length);
  const avgPrediction = totalPrediction / observations.length;
  const avgFunding = fundingSum / observations.length;

  const snapshot: ExchangeSnapshot = {
    asset,
    horizon,
    timestamp: new Date(),
    direction,
    score: finalScore,
    confidence: avgConfidence,
    components: {
      bull: Math.round(bull * 1000) / 1000,
      bear: Math.round(bear * 1000) / 1000,
      sampleSize: observations.length,
      avgPrediction: Math.round(avgPrediction * 1000) / 1000,
      fundingBias: Math.round(avgFunding * 1000) / 1000,
    },
    source: 'exchange_v2',
  };

  // Save to snapshots collection
  await db.collection('exchange_prediction_snapshots').insertOne(snapshot);

  console.log(`[ExchangeSnapshotBuilder] ✅ ${asset} ${horizon}: ${direction} (score=${finalScore.toFixed(3)}, conf=${avgConfidence.toFixed(2)})`);

  return snapshot;
}

/**
 * Build snapshots for all horizons for a given asset
 */
export async function buildAllExchangeSnapshots(asset: string): Promise<void> {
  const horizons: Array<'1D' | '7D' | '30D'> = ['1D', '7D', '30D'];
  
  for (const horizon of horizons) {
    try {
      await buildExchangeSnapshot(asset, horizon);
    } catch (err: any) {
      console.error(`[ExchangeSnapshotBuilder] Error for ${asset} ${horizon}:`, err.message);
    }
  }
}

export default buildExchangeSnapshot;
