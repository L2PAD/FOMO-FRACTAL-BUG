/**
 * Sentiment Aggregate Model
 * =========================
 * 
 * BLOCK 4: Хранение агрегированных данных sentiment по символам
 * 
 * Структура:
 * - symbol: BTC, ETH, etc.
 * - window: 24H, 7D, 30D
 * - asOf: момент расчёта
 * - score, bias, confidence: основные метрики
 * - stats: детальная статистика
 */

import mongoose, { Schema, Document } from 'mongoose';

export interface ITopAuthor {
  handle: string;
  weight: number;
  avgScore: number;
  influence: number;
  authorScore: number;
}

export interface ISentimentAggregate extends Document {
  symbol: string;
  window: '24H' | '7D' | '30D';
  asOf: Date;
  
  // Main metrics
  score: number;          // 0..1 (sentiment score)
  bias: number;           // -1..+1 (directional bias)
  confidence: number;     // 0..1 (aggregated confidence)
  
  // Stats
  eventsCount: number;
  uniqueAuthors: number;
  posCount: number;
  negCount: number;
  neuCount: number;
  
  // ML Features (BLOCK 3: for training)
  authorScoreMean?: number;      // Mean author credibility score
  influenceMean?: number;        // Mean author influence
  botProbMean?: number;          // Mean bot probability
  weightedScore?: number;        // Weighted sentiment score
  weightedConfidence?: number;   // Weighted confidence
  
  // Top contributors
  topAuthors: ITopAuthor[];
  
  // Forecast mapping (computed from bias)
  direction: 'LONG' | 'SHORT' | 'NEUTRAL';
  expectedReturnPct: number;
  
  createdAt: Date;
  updatedAt: Date;
}

const TopAuthorSchema = new Schema<ITopAuthor>({
  handle: { type: String, required: true },
  weight: { type: Number, required: true },
  avgScore: { type: Number, required: true },
  influence: { type: Number, required: true },
  authorScore: { type: Number, required: true },
}, { _id: false });

const SentimentAggregateSchema = new Schema<ISentimentAggregate>(
  {
    symbol: { type: String, required: true, index: true },
    window: { type: String, required: true, enum: ['24H', '7D', '30D'], index: true },
    asOf: { type: Date, required: true, index: true },
    
    // Main metrics
    score: { type: Number, required: true },
    bias: { type: Number, required: true },
    confidence: { type: Number, required: true },
    
    // Stats
    eventsCount: { type: Number, required: true },
    uniqueAuthors: { type: Number, required: true },
    posCount: { type: Number, required: true },
    negCount: { type: Number, required: true },
    neuCount: { type: Number, required: true },
    
    // ML Features (BLOCK 3)
    authorScoreMean: { type: Number },
    influenceMean: { type: Number },
    botProbMean: { type: Number },
    weightedScore: { type: Number },
    weightedConfidence: { type: Number },
    
    // Top contributors
    topAuthors: [TopAuthorSchema],
    
    // Forecast mapping
    direction: { type: String, enum: ['LONG', 'SHORT', 'NEUTRAL'], required: true },
    expectedReturnPct: { type: Number, required: true },
  },
  { 
    timestamps: true,
    collection: 'sentiment_aggregates',
  }
);

// Compound index for efficient queries
SentimentAggregateSchema.index({ symbol: 1, window: 1, asOf: -1 });

// UNIQUE anti-duplicate key (one aggregate per symbol+window+asOf)
SentimentAggregateSchema.index({ symbol: 1, window: 1, asOf: 1 }, { unique: true });

export const SentimentAggregateModel = mongoose.model<ISentimentAggregate>(
  'SentimentAggregate',
  SentimentAggregateSchema
);
