/**
 * META BRAIN OUTCOMES REPOSITORY
 * ================================
 * 
 * Truth layer: Prediction → Outcome tracking
 * 
 * This is the single source of truth for proving if Meta Brain has alpha.
 * Every prediction MUST be saved here.
 * Every outcome MUST be resolved through horizon.
 */

import mongoose from 'mongoose';

export interface MetaBrainOutcome {
  _id?: mongoose.Types.ObjectId;
  
  // Prediction
  asset: string;
  horizon: '24H' | '7D' | '30D';
  predictedAt: Date;
  
  direction: 'LONG' | 'SHORT' | 'NEUTRAL';
  confidence: number;
  
  // Snapshot meta
  regime: 'TREND' | 'RANGE' | 'RISK_OFF' | 'TRANSITION';
  modulesUsed: string[];
  moduleScores: {
    exchange?: number;
    fractal?: number;
    sentiment?: number;
    onchain?: number;
  };
  
  // Target (for error calculation)
  entryPrice: number;
  targetPrice?: number;
  bandLow?: number;
  bandHigh?: number;
  
  // Outcome (initially empty, filled by resolver)
  resolved: boolean;
  resolvedAt?: Date;
  
  actualPrice?: number;
  actualReturn?: number;
  
  directionCorrect?: boolean;
  bandHit?: boolean;
  
  errorPct?: number;
  
  // Debug
  meta: {
    version: string;
    policy: string;
  };
}

/**
 * Save new prediction outcome (resolved=false)
 */
export async function saveOutcome(outcome: Omit<MetaBrainOutcome, '_id'>): Promise<void> {
  const db = mongoose.connection.db;
  if (!db) throw new Error('MongoDB not connected');
  
  await db.collection('meta_brain_outcomes').insertOne({
    ...outcome,
    createdAt: new Date(),
  });
}

/**
 * Find unresolved outcomes ready to be resolved
 */
export async function findUnresolvedOutcomes(limit: number = 100): Promise<MetaBrainOutcome[]> {
  const db = mongoose.connection.db;
  if (!db) throw new Error('MongoDB not connected');
  
  const now = new Date();
  
  const docs = await db.collection('meta_brain_outcomes')
    .find({
      resolved: false,
      // Check if horizon has passed
      $or: [
        { horizon: '24H', predictedAt: { $lte: new Date(now.getTime() - 24 * 60 * 60 * 1000) } },
        { horizon: '7D', predictedAt: { $lte: new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000) } },
        { horizon: '30D', predictedAt: { $lte: new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000) } },
      ],
    })
    .limit(limit)
    .toArray();
  
  return docs as unknown as MetaBrainOutcome[];
}

/**
 * Resolve outcome with actual results
 */
export async function resolveOutcome(
  outcomeId: mongoose.Types.ObjectId,
  actualPrice: number,
  entryPrice: number
): Promise<void> {
  const db = mongoose.connection.db;
  if (!db) throw new Error('MongoDB not connected');
  
  // Fetch outcome
  const outcome = await db.collection('meta_brain_outcomes').findOne({ _id: outcomeId }) as unknown as MetaBrainOutcome;
  if (!outcome) throw new Error('Outcome not found');
  
  // Calculate return
  const actualReturn = (actualPrice - entryPrice) / entryPrice;
  
  // Calculate direction correctness
  let directionCorrect = false;
  const NEUTRAL_THRESHOLD = 0.005; // 0.5%
  
  if (outcome.direction === 'LONG') {
    directionCorrect = actualReturn > 0;
  } else if (outcome.direction === 'SHORT') {
    directionCorrect = actualReturn < 0;
  } else if (outcome.direction === 'NEUTRAL') {
    directionCorrect = Math.abs(actualReturn) < NEUTRAL_THRESHOLD;
  }
  
  // Calculate band hit
  let bandHit: boolean | undefined;
  if (outcome.bandLow !== undefined && outcome.bandHigh !== undefined) {
    bandHit = actualPrice >= outcome.bandLow && actualPrice <= outcome.bandHigh;
  }
  
  // Calculate error %
  let errorPct: number | undefined;
  if (outcome.targetPrice !== undefined) {
    errorPct = Math.abs(actualPrice - outcome.targetPrice) / outcome.targetPrice;
  }
  
  // Update outcome
  await db.collection('meta_brain_outcomes').updateOne(
    { _id: outcomeId },
    {
      $set: {
        resolved: true,
        resolvedAt: new Date(),
        actualPrice,
        actualReturn,
        directionCorrect,
        bandHit,
        errorPct,
      },
    }
  );
}

/**
 * Get resolved outcomes for accuracy calculation
 */
export async function getResolvedOutcomes(filters?: {
  asset?: string;
  horizon?: '24H' | '7D' | '30D';
  minConfidence?: number;
  modulesUsed?: string[];
}): Promise<MetaBrainOutcome[]> {
  const db = mongoose.connection.db;
  if (!db) throw new Error('MongoDB not connected');
  
  const query: any = { resolved: true };
  
  if (filters?.asset) query.asset = filters.asset;
  if (filters?.horizon) query.horizon = filters.horizon;
  if (filters?.minConfidence) query.confidence = { $gte: filters.minConfidence };
  if (filters?.modulesUsed) query.modulesUsed = { $all: filters.modulesUsed };
  
  const docs = await db.collection('meta_brain_outcomes')
    .find(query)
    .sort({ predictedAt: -1 })
    .limit(1000)
    .toArray();
  
  return docs as unknown as MetaBrainOutcome[];
}

console.log('[MetaBrainOutcomes] Repository loaded');
