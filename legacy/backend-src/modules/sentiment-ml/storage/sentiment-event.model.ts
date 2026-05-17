/**
 * Sentiment Event Model
 * =====================
 * 
 * BLOCK 2C: Storage для событий sentiment analysis
 * 
 * Каждый твит × symbol = один event.
 * Это основа для:
 * - Dataset для обучения
 * - Capital feedback
 * - Статистика авторов
 * - Lifecycle/promotion
 */

import mongoose, { Schema, Document } from 'mongoose';

export interface ISentimentEvent extends Document {
  // Tweet reference
  tweetId: string;
  tweetCreatedAt: Date;
  
  // Author info
  authorHandle?: string;
  authorId?: string;
  
  // Symbol (one event per symbol)
  symbol: string;
  
  // Base engine output (MOCK for now, later CNN/LLM)
  baseLabel: 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE';
  baseScore: number;        // 0..1
  baseConfidence: 'LOW' | 'MEDIUM' | 'HIGH';
  
  // Enrichment from Connections (Block 1)
  connectionsAvailable: boolean;
  authorScore?: number;     // 0..1
  influence?: number;       // 0..1
  botProb?: number;         // 0..1
  clusterId?: string;
  clusterScore?: number;    // 0..1
  manipulationProb?: number; // 0..1
  narrativeId?: string;
  narrativePhase?: 'EARLY' | 'MID' | 'LATE' | 'DEAD';
  narrativeHeat?: number;   // 0..1
  
  // Weighted Engine output (Block 3 - reserved)
  weightedScore?: number;   // 0..1
  weightedConfidence?: number; // 0..1
  
  // Direction prediction (Block 4 - reserved)
  direction?: 'LONG' | 'SHORT' | 'NEUTRAL';
  horizon?: '7D' | '30D';
  expectedReturn?: number;
  
  // Processing metadata
  processedAt: Date;
  processingVersion: string;
  
  createdAt: Date;
  updatedAt: Date;
}

const SentimentEventSchema = new Schema<ISentimentEvent>(
  {
    // Tweet reference
    tweetId: { type: String, required: true, index: true },
    tweetCreatedAt: { type: Date, required: true, index: true },
    
    // Author info
    authorHandle: { type: String, index: true },
    authorId: { type: String, index: true },
    
    // Symbol
    symbol: { type: String, required: true, index: true },
    
    // Base engine output
    baseLabel: { 
      type: String, 
      enum: ['POSITIVE', 'NEUTRAL', 'NEGATIVE'], 
      required: true 
    },
    baseScore: { type: Number, required: true },
    baseConfidence: { 
      type: String, 
      enum: ['LOW', 'MEDIUM', 'HIGH'], 
      required: true 
    },
    
    // Enrichment from Connections
    connectionsAvailable: { type: Boolean, default: false },
    authorScore: { type: Number },
    influence: { type: Number },
    botProb: { type: Number },
    clusterId: { type: String },
    clusterScore: { type: Number },
    manipulationProb: { type: Number },
    narrativeId: { type: String },
    narrativePhase: { type: String, enum: ['EARLY', 'MID', 'LATE', 'DEAD'] },
    narrativeHeat: { type: Number },
    
    // Weighted Engine output (Block 3)
    weightedScore: { type: Number },
    weightedConfidence: { type: Number },

    // Event classification (Ingestion Layer)
    eventType: { type: String },
    eventImpactWeight: { type: Number },
    sourceType: { type: String },
    sourceWeight: { type: Number },
    
    // Direction prediction (Block 4)
    direction: { type: String, enum: ['LONG', 'SHORT', 'NEUTRAL'] },
    horizon: { type: String, enum: ['7D', '30D'] },
    expectedReturn: { type: Number },
    
    // Processing metadata
    processedAt: { type: Date, required: true },
    processingVersion: { type: String, required: true },
  },
  { 
    timestamps: true,
    collection: 'sentiment_events',
  }
);

// Indexes for queries
SentimentEventSchema.index({ symbol: 1, tweetCreatedAt: -1 });
SentimentEventSchema.index({ authorHandle: 1, tweetCreatedAt: -1 });
SentimentEventSchema.index({ tweetId: 1, symbol: 1 }, { unique: true }); // защита от дублей
SentimentEventSchema.index({ processedAt: -1 });
SentimentEventSchema.index({ baseLabel: 1, symbol: 1, tweetCreatedAt: -1 });

// Indexes for future weighted/direction queries
SentimentEventSchema.index({ symbol: 1, direction: 1, tweetCreatedAt: -1 });
SentimentEventSchema.index({ weightedScore: -1 });

export const SentimentEventModel = mongoose.model<ISentimentEvent>(
  'SentimentEvent',
  SentimentEventSchema
);
