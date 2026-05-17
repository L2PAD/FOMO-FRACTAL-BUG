/**
 * Sentiment Binary Trainer
 * =========================
 * 
 * BLOCK 8: Logistic Regression trainer for UP vs REST classification.
 * 
 * Features:
 * - Pure TypeScript implementation (no external ML libs)
 * - Class weighting for imbalanced data
 * - L2 regularization
 * - Train/test split for validation
 * 
 * Can be replaced with XGBoost/LightGBM later without interface changes.
 */

import { 
  SentimentDirSampleInput, 
  SentimentWindow, 
  BinaryModelMeta,
  LABEL_THRESHOLDS,
} from '../contracts/sentiment-ml.types.js';
import { SentimentBinaryFeatureExtractor } from './sentiment.binary.feature-extractor.js';
import { SentimentBinModel } from './models/sentiment_bin_model.model.js';
import { SentimentBinRegistry } from './models/sentiment_bin_registry.model.js';

// Math utilities
const sigmoid = (z: number): number => 1 / (1 + Math.exp(-Math.max(-500, Math.min(500, z))));
const dot = (a: number[], b: number[]): number => a.reduce((s, v, i) => s + v * b[i], 0);

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export interface TrainResult {
  modelId: string;
  meta: BinaryModelMeta;
  weights: number[];
  bias: number;
}

export class SentimentBinaryTrainer {
  /**
   * Train UP vs REST (DOWN+NEUTRAL) binary classifier
   */
  static async trainUpModel(args: {
    window: SentimentWindow;
    samples: SentimentDirSampleInput[];
    epochs?: number;
    lr?: number;
    l2?: number;
    testRatio?: number;
  }): Promise<TrainResult> {
    const epochs = args.epochs ?? 30;
    const lr = args.lr ?? 0.12;
    const l2 = args.l2 ?? 1e-3;
    const testRatio = args.testRatio ?? 0.2;

    console.log(`[BinaryTrainer] Training UP model for ${args.window}`);
    console.log(`[BinaryTrainer] Input samples: ${args.samples.length}`);

    // Filter to target window and samples with valid labels
    const usable = args.samples.filter(s => {
      const w = s.window;
      if (w !== args.window) return false;
      
      // Need either label or returnPct to determine label
      if (s.label) return true;
      const ret = s.returnPct ?? s.forwardReturn;
      return typeof ret === 'number';
    });

    console.log(`[BinaryTrainer] Usable samples for ${args.window}: ${usable.length}`);

    if (usable.length < 30) {
      throw new Error(`Not enough samples to train: ${usable.length} (need 30+)`);
    }

    // Shuffle and split
    const data = shuffle(usable);
    const testN = Math.max(1, Math.floor(data.length * testRatio));
    const test = data.slice(0, testN);
    const train = data.slice(testN);

    console.log(`[BinaryTrainer] Train: ${train.length}, Test: ${test.length}`);

    // Convert to feature vectors
    const thresholds = LABEL_THRESHOLDS[args.window];
    
    const getLabel = (s: SentimentDirSampleInput): 0 | 1 => {
      if (s.label === 'UP') return 1;
      if (s.label === 'DOWN' || s.label === 'NEUTRAL') return 0;
      
      // Compute from return
      const ret = s.returnPct ?? s.forwardReturn ?? 0;
      return ret > thresholds.up ? 1 : 0;
    };

    const X = train.map(s => 
      SentimentBinaryFeatureExtractor.toVector(
        SentimentBinaryFeatureExtractor.fromSample(s)
      )
    );
    const y = train.map(getLabel);

    // Class weights for imbalance
    const pos = y.reduce((s, v) => s + v, 0);
    const neg = y.length - pos;
    const wPos = neg / Math.max(1, pos);
    const wNeg = 1;

    console.log(`[BinaryTrainer] Positive: ${pos}, Negative: ${neg}, wPos: ${wPos.toFixed(2)}`);

    // Initialize weights
    const dim = X[0].length;
    let w = new Array(dim).fill(0);
    let b = 0;

    // Training loop (batch gradient descent)
    for (let ep = 0; ep < epochs; ep++) {
      let gw = new Array(dim).fill(0);
      let gb = 0;
      let loss = 0;

      for (let i = 0; i < X.length; i++) {
        const xi = X[i];
        const yi = y[i];
        const z = dot(w, xi) + b;
        const p = sigmoid(z);
        const err = p - yi;
        const cw = yi === 1 ? wPos : wNeg;

        // Gradients
        for (let k = 0; k < dim; k++) {
          gw[k] += cw * (err * xi[k] + l2 * w[k]);
        }
        gb += cw * err;

        // Log loss
        const pClip = Math.max(1e-7, Math.min(1 - 1e-7, p));
        loss += cw * (yi === 1 
          ? -Math.log(pClip) 
          : -Math.log(1 - pClip)
        );
      }

      // Update weights
      for (let k = 0; k < dim; k++) {
        w[k] -= lr * (gw[k] / X.length);
      }
      b -= lr * (gb / X.length);

      if (ep % 10 === 0) {
        console.log(`[BinaryTrainer] Epoch ${ep}: loss = ${(loss / X.length).toFixed(4)}`);
      }
    }

    // Evaluate on test set
    const evalMetrics = (samples: SentimentDirSampleInput[]) => {
      let correct = 0;
      let tp = 0, fp = 0, fn = 0, tn = 0;

      for (const s of samples) {
        const xi = SentimentBinaryFeatureExtractor.toVector(
          SentimentBinaryFeatureExtractor.fromSample(s)
        );
        const p = sigmoid(dot(w, xi) + b);
        const pred = p >= 0.5 ? 1 : 0;
        const gt = getLabel(s);

        if (pred === gt) correct++;
        if (pred === 1 && gt === 1) tp++;
        if (pred === 1 && gt === 0) fp++;
        if (pred === 0 && gt === 1) fn++;
        if (pred === 0 && gt === 0) tn++;
      }

      const acc = correct / Math.max(1, samples.length);
      const precision = tp / Math.max(1, tp + fp);
      const recall = tp / Math.max(1, tp + fn);

      return { acc, precision, recall, tp, fp, fn, tn };
    };

    const testMetrics = evalMetrics(test);
    const trainMetrics = evalMetrics(train);

    console.log(`[BinaryTrainer] Train Acc: ${(trainMetrics.acc * 100).toFixed(1)}%`);
    console.log(`[BinaryTrainer] Test Acc: ${(testMetrics.acc * 100).toFixed(1)}%`);
    console.log(`[BinaryTrainer] Test Precision: ${(testMetrics.precision * 100).toFixed(1)}%, Recall: ${(testMetrics.recall * 100).toFixed(1)}%`);

    // Create model ID
    const modelId = `sent_bin_up_${args.window}_${Date.now()}`;

    const meta: BinaryModelMeta = {
      modelId,
      window: args.window,
      algo: 'logreg',
      createdAt: new Date(),
      trainSamples: train.length,
      testSamples: test.length,
      acc: testMetrics.acc,
      posRatio: pos / y.length,
    };

    // Save model
    await SentimentBinModel.create({
      modelId,
      window: args.window,
      algo: 'logreg',
      weights: w,
      bias: b,
      meta,
    });

    // Update registry to point to new model
    await SentimentBinRegistry.updateOne(
      { window: args.window },
      { 
        $set: { 
          activeModelId: modelId, 
          updatedAt: new Date(),
        },
      },
      { upsert: true }
    );

    console.log(`[BinaryTrainer] Model saved: ${modelId}`);

    return { modelId, meta, weights: w, bias: b };
  }

  /**
   * Get training statistics without training
   */
  static async getTrainingStats(args: {
    window: SentimentWindow;
    samples: SentimentDirSampleInput[];
  }): Promise<{
    total: number;
    up: number;
    down: number;
    neutral: number;
    posRatio: number;
  }> {
    const thresholds = LABEL_THRESHOLDS[args.window];
    
    const usable = args.samples.filter(s => s.window === args.window);
    
    let up = 0, down = 0, neutral = 0;
    
    for (const s of usable) {
      if (s.label === 'UP') { up++; continue; }
      if (s.label === 'DOWN') { down++; continue; }
      if (s.label === 'NEUTRAL') { neutral++; continue; }
      
      const ret = s.returnPct ?? s.forwardReturn ?? 0;
      if (ret > thresholds.up) up++;
      else if (ret < thresholds.down) down++;
      else neutral++;
    }

    return {
      total: usable.length,
      up,
      down,
      neutral,
      posRatio: up / Math.max(1, usable.length),
    };
  }
}

console.log('[Sentiment-ML] Binary Trainer loaded (BLOCK 8)');
