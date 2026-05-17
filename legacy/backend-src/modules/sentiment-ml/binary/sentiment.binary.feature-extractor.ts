/**
 * Sentiment Binary Feature Extractor
 * ====================================
 * 
 * BLOCK 8: Converts raw sample data into fixed-length feature vector.
 * 
 * PHASE 1 (Core ML - no Connections):
 * - bias, absBias
 * - score, confidence
 * - eventCountLog
 * - crowdSkew, signalStrength
 * 
 * PHASE 2 (Connections Booster - later):
 * - authorScoreMean, influenceMean, botProbMean
 * 
 * NO price features (would be leakage).
 * NO future data access.
 */

import { 
  SentimentDirSampleInput, 
  SentimentDirFeatures 
} from '../contracts/sentiment-ml.types.js';

const clamp01 = (x: number): number => Math.max(0, Math.min(1, x));
const safe = (x: any, d = 0): number => (Number.isFinite(Number(x)) ? Number(x) : d);

export class SentimentBinaryFeatureExtractor {
  /**
   * Extract features from a sample document
   * PHASE 1: Core features only (no Connections dependency)
   */
  static fromSample(s: SentimentDirSampleInput): SentimentDirFeatures {
    // Core sentiment
    const bias = safe(s.bias, 0);
    const absBias = Math.abs(bias);
    const score = clamp01(safe(s.score, 0.5));
    const confidence = clamp01(safe(s.weightedConfidence ?? s.confidence, 0.5));

    // Event count (logarithmic to reduce outlier impact)
    const eventCount = Math.max(0, safe(s.eventsCount ?? s.eventCount, 0));
    const eventCountLog = Math.log1p(eventCount);

    // Derived features (core - no Connections needed)
    const crowdSkew = bias * confidence;        // directional signal strength
    const signalStrength = absBias * confidence; // absolute signal strength
    
    // Bias strength bucket (categorical encoded as numeric)
    // 0: weak (|bias| < 0.2), 1: medium (0.2-0.5), 2: strong (>0.5)
    const biasStrengthBucket = absBias < 0.2 ? 0 : absBias < 0.5 ? 1 : 2;
    
    // Confidence-weighted bias (main predictive feature)
    const weightedBias = bias * confidence;

    return {
      bias,
      absBias,
      score,
      confidence,
      eventCountLog,
      crowdSkew,
      signalStrength,
      biasStrengthBucket,
      weightedBias,
    };
  }

  /**
   * Convert features to numeric vector (order matters!)
   * Keep this stable across model versions.
   * PHASE 1: 9 core features
   */
  static toVector(f: SentimentDirFeatures): number[] {
    return [
      f.bias,
      f.absBias,
      f.score,
      f.confidence,
      f.eventCountLog,
      f.crowdSkew,
      f.signalStrength,
      f.biasStrengthBucket,
      f.weightedBias,
    ];
  }

  /**
   * Feature names (for debugging/logging)
   */
  static featureNames(): string[] {
    return [
      'bias',
      'absBias',
      'score',
      'confidence',
      'eventCountLog',
      'crowdSkew',
      'signalStrength',
      'biasStrengthBucket',
      'weightedBias',
    ];
  }

  /**
   * Get feature dimension
   */
  static dim(): number {
    return 9;
  }
}

console.log('[Sentiment-ML] Binary Feature Extractor loaded (PHASE 1 - Core ML)');
