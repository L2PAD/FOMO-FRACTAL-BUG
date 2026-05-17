/**
 * EXCHANGE PREDICTION PUBLISHER
 * =============================
 * 
 * Transforms raw exchange_observations into decision-ready prediction snapshots.
 * 
 * This is NOT an ML model.
 * This is a rule-based verdict engine that aggregates market signals.
 * 
 * INPUT:  exchange_observations (raw market telemetry)
 * OUTPUT: exchange_prediction_snapshots (decision-ready artifacts)
 * 
 * Meta Brain consumes ONLY snapshots, never raw observations.
 */

import mongoose from 'mongoose';

type Horizon = '24H' | '7D' | '30D';
type Direction = 'LONG' | 'SHORT' | 'NEUTRAL';
type Quality = 'HIGH' | 'MEDIUM' | 'LOW';

interface ExchangePredictionSnapshot {
  asset: string;
  timestamp: number;
  horizon: Horizon;
  
  direction: Direction;
  score: number;           // -1..1
  confidence: number;      // 0..1
  strength: number;        // 0..1
  
  current_price: number;
  expected_move_pct: number;
  target_price: number;
  band_low: number;
  band_high: number;
  
  quality: Quality;
  
  components: {
    momentum: number;
    structure: number;
    participation: number;
    orderbook: number;
    positioning: number;
    stress: number;
    bull_score: number;
    bear_score: number;
    delta: number;
  };
  
  source: string;
  observation_count: number;
  createdAt: Date;
}

const HORIZON_MULTIPLIER: Record<Horizon, number> = {
  '24H': 1.0,
  '7D': 2.0,
  '30D': 3.5,
};

function clamp(x: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, x));
}

function avg(values: number[]): number {
  if (!values.length) return 0;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function detectQuality(sampleSize: number, providers: Set<string>): Quality {
  if (sampleSize >= 20 && providers.size >= 2) return 'HIGH';
  if (sampleSize >= 8) return 'MEDIUM';
  return 'LOW';
}

function qualityMultiplier(q: Quality): number {
  if (q === 'HIGH') return 1.0;
  if (q === 'MEDIUM') return 0.75;
  return 0.4;
}

function directionFromDelta(delta: number): Direction {
  if (delta >= 0.10) return 'LONG';
  if (delta <= -0.10) return 'SHORT';
  return 'NEUTRAL';
}

/**
 * Publish prediction snapshots for a single asset
 * Generates snapshots for all 3 horizons (24H, 7D, 30D)
 */
export async function publishExchangePredictionSnapshots(
  asset: string
): Promise<{ ok: boolean; reason?: string; inserted?: number; direction?: Direction; score?: number }> {
  const db = mongoose.connection.db;
  if (!db) {
    console.warn('[ExchangePublisher] MongoDB not connected');
    return { ok: false, reason: 'db_not_connected' };
  }

  // Fetch recent observations
  const observations = await db
    .collection('exchange_observations')
    .find({ asset })
    .sort({ timestamp: -1 })
    .limit(50)
    .toArray();

  if (!observations.length) {
    return { ok: false, reason: 'no_observations' };
  }

  const providers = new Set<string>();
  const momentumVals: number[] = [];
  const structureVals: number[] = [];
  const participationVals: number[] = [];
  const orderbookVals: number[] = [];
  const positioningVals: number[] = [];
  const stressVals: number[] = [];
  const volVals: number[] = [];
  const prices: number[] = [];

  // Aggregate signals from observations
  for (const o of observations) {
    if (o.provider) providers.add(o.provider);
    
    // Extract normalized indicators (already -1..1 from observations)
    const inds = o.indicators || {};
    momentumVals.push(Number(inds.ema_distance_fast?.value ?? 0));
    structureVals.push(Number(inds.vwap_deviation?.value ?? 0));
    participationVals.push(Number(o.volume?.delta ?? 0));
    orderbookVals.push(Number(o.orderFlow?.dominance ?? 0.5) - 0.5); // center at 0
    positioningVals.push(Number(o.openInterest?.deltaPct ?? 0));
    stressVals.push(Number(o.liquidations?.cascadeActive ? 1 : 0));
    volVals.push(Number(o.market?.volatility ?? 0));
    
    const price = Number(o.market?.price ?? 0);
    if (price > 0) prices.push(price);
  }

  const currentPrice = prices[0] ?? 0;
  if (!currentPrice) {
    return { ok: false, reason: 'no_price' };
  }

  // Calculate component scores
  const momentum = avg(momentumVals);
  const structure = avg(structureVals);
  const participation = avg(participationVals);
  const orderbook = avg(orderbookVals);
  const positioning = avg(positioningVals);
  const stress = avg(stressVals);
  const volatility = Math.max(0.2, avg(volVals));

  // Bull/Bear scoring (weighted combination)
  const bullScore =
    Math.max(0, momentum) * 0.20 +
    Math.max(0, structure) * 0.20 +
    Math.max(0, participation) * 0.15 +
    Math.max(0, orderbook) * 0.15 +
    Math.max(0, positioning) * 0.15 +
    Math.max(0, -stress) * 0.15;

  const bearScore =
    Math.max(0, -momentum) * 0.20 +
    Math.max(0, -structure) * 0.20 +
    Math.max(0, -participation) * 0.15 +
    Math.max(0, -orderbook) * 0.15 +
    Math.max(0, -positioning) * 0.15 +
    Math.max(0, stress) * 0.15;

  const delta = bullScore - bearScore;
  const direction = directionFromDelta(delta);

  const quality = detectQuality(observations.length, providers);
  const qMult = qualityMultiplier(quality);

  const strength = clamp(Math.abs(delta), 0, 1);
  const baseConfidence = clamp(0.35 + strength * 0.55, 0.2, 0.95);
  const confidence = clamp(baseConfidence * qMult, 0.2, 0.95);

  const sourceScore = clamp(delta, -1, 1);

  // Generate snapshots for all horizons
  const docs: ExchangePredictionSnapshot[] = (['24H', '7D', '30D'] as Horizon[]).map((horizon) => {
    const horizonMult = HORIZON_MULTIPLIER[horizon];
    const expectedMovePct =
      direction === 'NEUTRAL'
        ? 0
        : volatility * (0.5 + strength * 1.5) * horizonMult;

    const sign = direction === 'LONG' ? 1 : direction === 'SHORT' ? -1 : 0;

    const targetPrice = currentPrice * (1 + (sign * expectedMovePct) / 100);
    const bandWidthPct = volatility * (1.2 - confidence * 0.4) * horizonMult;

    const bandLow = targetPrice * (1 - bandWidthPct / 100);
    const bandHigh = targetPrice * (1 + bandWidthPct / 100);

    return {
      asset,
      timestamp: Date.now(),
      horizon,
      direction,
      score: Number(sourceScore.toFixed(4)),
      confidence: Number(confidence.toFixed(4)),
      strength: Number(strength.toFixed(4)),

      current_price: Number(currentPrice.toFixed(2)),
      expected_move_pct: Number((sign * expectedMovePct).toFixed(4)),
      target_price: Number(targetPrice.toFixed(2)),
      band_low: Number(bandLow.toFixed(2)),
      band_high: Number(bandHigh.toFixed(2)),

      quality,
      components: {
        momentum: Number(momentum.toFixed(4)),
        structure: Number(structure.toFixed(4)),
        participation: Number(participation.toFixed(4)),
        orderbook: Number(orderbook.toFixed(4)),
        positioning: Number(positioning.toFixed(4)),
        stress: Number(stress.toFixed(4)),
        bull_score: Number(bullScore.toFixed(4)),
        bear_score: Number(bearScore.toFixed(4)),
        delta: Number(delta.toFixed(4)),
      },

      source: 'exchange_rule_engine_v1',
      observation_count: observations.length,
      createdAt: new Date(),
    };
  });

  if (docs.length) {
    await db.collection('exchange_prediction_snapshots').insertMany(docs);
    console.log(`[ExchangePublisher] ✅ ${asset}: ${direction} (score=${sourceScore.toFixed(3)}, conf=${confidence.toFixed(2)}, obs=${observations.length})`);
  }

  return {
    ok: true,
    inserted: docs.length,
    direction,
    score: sourceScore,
  };
}

export default publishExchangePredictionSnapshots;
