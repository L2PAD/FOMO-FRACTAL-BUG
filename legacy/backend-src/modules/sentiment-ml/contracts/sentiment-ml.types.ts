/**
 * Sentiment ML Contracts
 * =======================
 * 
 * BLOCK 8: Binary ML Layer types and interfaces.
 * 
 * Key contracts:
 * - SentimentDirFeatures — feature vector for ML
 * - BinaryModelMeta — model metadata
 * - BinaryInferenceResult — prediction output
 */

export type SentimentWindow = '24H' | '7D' | '30D';

export type DirLabel = 'UP' | 'DOWN' | 'NEUTRAL';

export interface SentimentDirSampleInput {
  _id?: any;
  symbol: string;
  window: SentimentWindow;
  asOf: Date;

  // What we knew at asOf (from aggregates):
  bias: number;              // -1..+1
  score: number;             // 0..1
  confidence?: number;       // 0..1 (aggregated confidence)
  weightedScore?: number;    // 0..1
  weightedConfidence?: number; // 0..1
  eventsCount?: number;
  eventCount?: number;       // alias

  // Optional enrich summary (PHASE 2 - Connections):
  authorScoreMean?: number;  // 0..1
  influenceMean?: number;    // 0..1
  botProbMean?: number;      // 0..1
  uniqueAuthors?: number;

  // Outcome (for training):
  returnPct?: number;        // forward return
  forwardReturn?: number;    // alias
  label?: DirLabel;

  createdAt?: Date;
}

export interface SentimentDirFeatures {
  // PHASE 1: Core features (no Connections dependency)
  bias: number;              // -1..+1 directional bias
  absBias: number;           // |bias| - strength magnitude
  score: number;             // 0..1 raw sentiment score
  confidence: number;        // 0..1 aggregated confidence
  eventCountLog: number;     // log(1 + eventCount)

  // Derived features
  crowdSkew: number;         // bias * confidence
  signalStrength: number;    // absBias * confidence
  biasStrengthBucket: number; // 0=weak, 1=medium, 2=strong
  weightedBias: number;      // bias * confidence (main signal)
}

export interface BinaryModelMeta {
  modelId: string;
  window: SentimentWindow;
  algo: 'logreg';
  createdAt: Date;
  trainSamples: number;
  testSamples: number;
  auc?: number;
  acc?: number;
  brier?: number;
  posRatio?: number;  // % of UP labels in training
}

export interface BinaryInferenceResult {
  window: SentimentWindow;
  symbol: string;
  asOf: Date;
  pUp: number;       // 0..1 probability of UP
  pDown: number;     // 0..1 probability of DOWN
  pNeutral: number;  // derived
  action: 'LONG' | 'SHORT' | 'NEUTRAL';
  confidence: number; // 0..1
  meta: { 
    modelId: string;
    edge?: number;
  };
}

// Decision thresholds per window
// PHASE 1: Lower thresholds for collapsed model variance
export const DECISION_THRESHOLDS: Record<SentimentWindow, {
  enter: number;      // pUp threshold to enter LONG
  neutralBand: number; // half-width of neutral zone
}> = {
  '24H': { enter: 0.52, neutralBand: 0.02 },  // Tighter for Phase 1
  '7D':  { enter: 0.52, neutralBand: 0.02 },
  '30D': { enter: 0.52, neutralBand: 0.02 },
};

// Label thresholds for training data
export const LABEL_THRESHOLDS: Record<SentimentWindow, {
  up: number;   // return > this = UP
  down: number; // return < this = DOWN
}> = {
  '24H': { up: 0.003, down: -0.003 },   // ±0.3%
  '7D':  { up: 0.015, down: -0.015 },   // ±1.5%
  '30D': { up: 0.04,  down: -0.04 },    // ±4%
};

console.log('[Sentiment-ML] Binary contracts loaded (BLOCK 8)');
