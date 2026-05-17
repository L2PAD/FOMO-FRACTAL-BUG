/**
 * Sentiment Shadow Decision Model
 * ================================
 * 
 * BLOCK 9: Shadow Mode - 24H only (first)
 * 
 * Stores parallel Rule vs ML decisions for comparison.
 * Production verdict = Rule-based (unchanged)
 * ML verdict = Shadow only (no user impact)
 * 
 * After accumulating 150+ samples:
 * - If ML ≥ Rule +5% → lifecycle promotion
 */

import mongoose, { Schema, Document } from 'mongoose';

export interface SentimentShadowDecision extends Document {
  symbol: string;
  asOf: Date;
  window: '24H';

  // Rule-based decision (current production)
  ruleAction: 'LONG' | 'SHORT' | 'NEUTRAL';
  ruleConfidence: number;
  ruleBias: number;

  // ML-based decision (shadow)
  mlAction: 'LONG' | 'SHORT' | 'NEUTRAL';
  mlConfidence: number;
  mlProbabilityUp: number;
  mlModelId: string;

  // Agreement
  agreement: boolean;

  // Outcome (filled after 24H window closes)
  forwardReturn?: number;
  forwardReturnPct?: number;    // raw % (e.g. 1.5 means +1.5%)
  forwardLabel?: 'UP' | 'DOWN' | 'FLAT';
  evaluated: boolean;

  // Adaptive labeling context (TASK 2.1+)
  volatility?: number;          // stdDev of recent returns (as fraction)
  volatilityBucket?: 'LOW' | 'MED' | 'HIGH';
  adaptiveThreshold?: number;   // threshold used for labeling (as fraction)

  // Correctness (filled after evaluation)
  ruleCorrect?: boolean;
  mlCorrect?: boolean;

  // ── News Context (TASK 2.0) ──
  newsContext?: {
    eventType?: string;
    importanceBand?: string;
    sourcesCount?: number;
    isBreaking?: boolean;
    clusterSize?: number;
    recencyBucket?: string;
    assetClass?: string;
    topClusterTitle?: string;
  };

  createdAt: Date;
  updatedAt: Date;
}

const schema = new Schema<SentimentShadowDecision>(
  {
    symbol: { type: String, required: true },
    asOf: { type: Date, required: true },
    window: { type: String, enum: ['24H'], required: true, default: '24H' },

    // Rule decision
    ruleAction: { type: String, enum: ['LONG', 'SHORT', 'NEUTRAL'], required: true },
    ruleConfidence: { type: Number, required: true },
    ruleBias: { type: Number, required: true },

    // ML decision
    mlAction: { type: String, enum: ['LONG', 'SHORT', 'NEUTRAL'], required: true },
    mlConfidence: { type: Number, required: true },
    mlProbabilityUp: { type: Number, required: true },
    mlModelId: { type: String, required: true },

    // Agreement
    agreement: { type: Boolean, required: true },

    // Outcome
    forwardReturn: { type: Number },
    forwardReturnPct: { type: Number },
    forwardLabel: { type: String, enum: ['UP', 'DOWN', 'FLAT'] },
    evaluated: { type: Boolean, default: false },

    // Adaptive labeling (TASK 2.1+)
    volatility: { type: Number },
    volatilityBucket: { type: String, enum: ['LOW', 'MED', 'HIGH'] },
    adaptiveThreshold: { type: Number },

    // Correctness
    ruleCorrect: { type: Boolean },
    mlCorrect: { type: Boolean },

    // News Context (TASK 2.0 - ML Validation)
    newsContext: {
      eventType: { type: String },
      importanceBand: { type: String },
      sourcesCount: { type: Number },
      isBreaking: { type: Boolean },
      clusterSize: { type: Number },
      recencyBucket: { type: String },
      assetClass: { type: String },
      topClusterTitle: { type: String },
    },
  },
  { 
    timestamps: true,
    collection: 'sentiment_shadow_decisions',
  }
);

// Unique index: one decision per symbol per asOf date
schema.index({ symbol: 1, window: 1, asOf: 1 }, { unique: true });

// Index for finding unevaluated decisions
schema.index({ evaluated: 1, asOf: 1 });

// Index for analytics queries
schema.index({ window: 1, evaluated: 1, createdAt: -1 });

// Safe model getter (prevents mongoose overwrite error during hot reload)
export function getSentimentShadowDecisionModel() {
  if (mongoose.models.SentimentShadowDecision) {
    return mongoose.models.SentimentShadowDecision as mongoose.Model<SentimentShadowDecision>;
  }
  return mongoose.model<SentimentShadowDecision>('SentimentShadowDecision', schema);
}

export const SentimentShadowDecisionModel = getSentimentShadowDecisionModel();

console.log('[Sentiment-ML] Shadow Decision Model loaded (BLOCK 9)');
