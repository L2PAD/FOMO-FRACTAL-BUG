/**
 * Sentiment Binary Inference Service
 * ====================================
 * 
 * BLOCK 8 / PHASE 2: Runtime inference for sentiment signals.
 * 
 * PHASE 2 (Full ML — Active):
 * - Uses trained logistic regression model weights
 * - Feature vector → sigmoid(dot(w, x) + b) → pUp
 * - Cached model loading for performance
 * 
 * Fallback: If no trained model exists, falls back to bias-based rule.
 */

import { SentimentBinModel } from './models/sentiment_bin_model.model.js';
import { SentimentBinRegistry } from './models/sentiment_bin_registry.model.js';
import { SentimentBinaryFeatureExtractor } from './sentiment.binary.feature-extractor.js';
import { 
  BinaryInferenceResult, 
  SentimentWindow, 
  SentimentDirSampleInput,
  DECISION_THRESHOLDS,
} from '../contracts/sentiment-ml.types.js';

// Math utilities
const sigmoid = (z: number): number => 1 / (1 + Math.exp(-Math.max(-500, Math.min(500, z))));
const dot = (a: number[], b: number[]): number => a.reduce((s, v, i) => s + v * b[i], 0);

// ML decision thresholds (pUp-based)
const ML_UP_THRESHOLD = 0.55;    // pUp > 0.55 → LONG
const ML_DOWN_THRESHOLD = 0.45;  // pUp < 0.45 → SHORT

// Model cache (avoid DB lookup on every inference)
const modelCache = new Map<string, { weights: number[]; bias: number; modelId: string; loadedAt: number }>();
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 min

async function loadModel(window: SentimentWindow): Promise<{ weights: number[]; bias: number; modelId: string } | null> {
  const cached = modelCache.get(window);
  if (cached && Date.now() - cached.loadedAt < CACHE_TTL_MS) {
    return cached;
  }

  const reg = await SentimentBinRegistry.findOne({ window }).lean();
  if (!reg?.activeModelId) return null;

  const model = await SentimentBinModel.findOne({ modelId: reg.activeModelId }).lean();
  if (!model?.weights || !Array.isArray(model.weights) || model.weights.length === 0) return null;

  const entry = { weights: model.weights as number[], bias: (model.bias as number) ?? 0, modelId: reg.activeModelId, loadedAt: Date.now() };
  modelCache.set(window, entry);
  return entry;
}

export class SentimentBinaryInferenceService {
  /**
   * Run inference for a single sample/aggregate
   * PHASE 2: Uses trained model weights, fallback to bias rule
   */
  static async infer(args: {
    window: SentimentWindow;
    sampleLike: Pick<SentimentDirSampleInput, 
      'symbol' | 'asOf' | 'bias' | 'score' | 'confidence' |
      'eventsCount' | 'eventCount' |
      'authorScoreMean' | 'influenceMean' | 'botProbMean'
    >;
  }): Promise<BinaryInferenceResult> {
    const { window, sampleLike } = args;

    // Try to load trained model
    const model = await loadModel(window);

    if (model) {
      // PHASE 2: Trained model inference
      const features = SentimentBinaryFeatureExtractor.fromSample(sampleLike as any);
      const vec = SentimentBinaryFeatureExtractor.toVector(features);
      const z = dot(model.weights, vec) + model.bias;
      const pUp = sigmoid(z);
      const pDown = 1 - pUp;

      let action: 'LONG' | 'SHORT' | 'NEUTRAL' = 'NEUTRAL';
      let confidence = 0;

      if (pUp > ML_UP_THRESHOLD) {
        action = 'LONG';
        confidence = Math.min(1, (pUp - ML_UP_THRESHOLD) / (1 - ML_UP_THRESHOLD));
      } else if (pUp < ML_DOWN_THRESHOLD) {
        action = 'SHORT';
        confidence = Math.min(1, (ML_DOWN_THRESHOLD - pUp) / ML_DOWN_THRESHOLD);
      }

      return {
        window,
        symbol: sampleLike.symbol,
        asOf: sampleLike.asOf,
        pUp,
        pDown,
        pNeutral: 0,
        action,
        confidence,
        meta: {
          modelId: model.modelId,
          edge: Math.abs(pUp - 0.5),
          phase: 'ML_LOGREG',
        },
      };
    }

    // Fallback: Bias-based rule (no trained model)
    const bias = sampleLike.bias ?? 0;
    const absBias = Math.abs(bias);
    const biasThreshold = 0.15;

    let action: 'LONG' | 'SHORT' | 'NEUTRAL' = 'NEUTRAL';
    let confidence = 0;

    if (absBias > biasThreshold) {
      action = bias > 0 ? 'LONG' : 'SHORT';
      confidence = Math.min(1, (absBias - biasThreshold) / (1 - biasThreshold));
    }

    const pUp = 0.5 + bias * 0.4;
    const pDown = 1 - pUp;

    return {
      window,
      symbol: sampleLike.symbol,
      asOf: sampleLike.asOf,
      pUp,
      pDown,
      pNeutral: 0,
      action,
      confidence,
      meta: {
        modelId: 'BIAS_FALLBACK',
        edge: absBias,
        phase: 'BIAS_FALLBACK',
      },
    };
  }

  /**
   * Batch inference for multiple symbols
   */
  static async inferBatch(args: {
    window: SentimentWindow;
    samples: Array<Pick<SentimentDirSampleInput, 
      'symbol' | 'asOf' | 'bias' | 'score' | 'confidence' |
      'eventsCount' | 'eventCount' |
      'authorScoreMean' | 'influenceMean' | 'botProbMean'
    >>;
  }): Promise<BinaryInferenceResult[]> {
    const results: BinaryInferenceResult[] = [];

    for (const sample of args.samples) {
      const result = await this.infer({
        window: args.window,
        sampleLike: sample,
      });
      results.push(result);
    }

    return results;
  }

  /**
   * Get current active model info
   */
  static async getActiveModel(window: SentimentWindow): Promise<{
    modelId: string | null;
    meta?: any;
  }> {
    const reg = await SentimentBinRegistry.findOne({ window }).lean();
    if (!reg?.activeModelId) {
      return { modelId: null };
    }

    const model = await SentimentBinModel.findOne({ modelId: reg.activeModelId }).lean();
    return {
      modelId: reg.activeModelId,
      meta: model?.meta,
    };
  }
}

// Singleton getter
let inferenceInstance: typeof SentimentBinaryInferenceService | null = null;

export function getSentimentBinaryInferenceService(): typeof SentimentBinaryInferenceService {
  if (!inferenceInstance) {
    inferenceInstance = SentimentBinaryInferenceService;
  }
  return inferenceInstance;
}

console.log('[Sentiment-ML] Binary Inference Service loaded (PHASE 2 - ML LogReg + Bias Fallback)');
