/**
 * Sentiment Processing Tracker Model
 * ===================================
 * 
 * BLOCK 2A: Tracking обработки твитов
 * 
 * ВАЖНО: Не изменяем frozen tweet.model.ts
 * Вместо этого храним processing state отдельно.
 * 
 * Один документ на tweetId — отслеживает processed/lock состояние
 */

import mongoose, { Schema, Document } from 'mongoose';

export interface ISentimentProcessing extends Document {
  tweetId: string;
  
  // Processing state
  processed: boolean;
  processedAt?: Date;
  
  // Lock for concurrent workers
  lockId?: string;
  lockedAt?: Date;
  
  // Symbols extracted
  symbols: string[];
  
  // Error tracking
  lastError?: string;
  errorCount: number;
  
  createdAt: Date;
  updatedAt: Date;
}

const SentimentProcessingSchema = new Schema<ISentimentProcessing>(
  {
    tweetId: { type: String, required: true, unique: true, index: true },
    
    // Processing state
    processed: { type: Boolean, default: false, index: true },
    processedAt: { type: Date },
    
    // Lock
    lockId: { type: String, index: true },
    lockedAt: { type: Date, index: true },
    
    // Extracted symbols
    symbols: [{ type: String }],
    
    // Errors
    lastError: { type: String },
    errorCount: { type: Number, default: 0 },
  },
  { 
    timestamps: true,
    collection: 'sentiment_processing',
  }
);

// Index for worker queries
SentimentProcessingSchema.index({ processed: 1, lockedAt: 1 });
SentimentProcessingSchema.index({ processed: 1, createdAt: 1 });

export const SentimentProcessingModel = mongoose.model<ISentimentProcessing>(
  'SentimentProcessing',
  SentimentProcessingSchema
);
