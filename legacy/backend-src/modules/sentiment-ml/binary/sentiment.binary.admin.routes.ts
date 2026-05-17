/**
 * Sentiment Binary Admin Routes
 * ==============================
 * 
 * BLOCK 8: Admin API for binary ML layer management.
 * 
 * Endpoints:
 * - GET /status — Current model registry
 * - POST /train — Train new model for window
 * - GET /stats — Training data statistics
 * - POST /predict — Manual inference test
 */

import fp from 'fastify-plugin';
import type { FastifyInstance, FastifyRequest } from 'fastify';
import { SentimentBinaryTrainer } from './sentiment.binary.trainer.js';
import { SentimentBinaryInferenceService } from './sentiment.binary.inference.service.js';
import { SentimentDirSampleModel } from '../dataset/sentiment-dir-sample.model.js';
import { SentimentBinRegistry } from './models/sentiment_bin_registry.model.js';
import { SentimentBinModel } from './models/sentiment_bin_model.model.js';
import { SentimentWindow } from '../contracts/sentiment-ml.types.js';

interface TrainBody {
  window?: SentimentWindow;
  epochs?: number;
  lr?: number;
  testRatio?: number;
}

interface PredictBody {
  window?: SentimentWindow;
  symbol: string;
  bias: number;
  score: number;
  confidence?: number;
  eventsCount?: number;
}

async function sentimentBinaryAdminRoutes(app: FastifyInstance): Promise<void> {
  /**
   * GET /status — Model registry status
   */
  app.get('/status', async () => {
    const registry = await SentimentBinRegistry.find({}).lean();
    const models = await SentimentBinModel.find({})
      .sort({ 'meta.createdAt': -1 })
      .limit(10)
      .lean();

    return {
      ok: true,
      registry,
      recentModels: models.map(m => ({
        modelId: m.modelId,
        window: m.window,
        createdAt: m.meta?.createdAt,
        trainSamples: m.meta?.trainSamples,
        testSamples: m.meta?.testSamples,
        acc: m.meta?.acc,
        posRatio: m.meta?.posRatio,
      })),
    };
  });

  /**
   * POST /train — Train new model
   */
  app.post('/train', async (req: FastifyRequest<{ Body: TrainBody }>) => {
    const body = req.body || {};
    const window = (body.window || '24H') as SentimentWindow;

    if (!['24H', '7D', '30D'].includes(window)) {
      return {
        ok: false,
        error: `Invalid window: ${window}. Use 24H, 7D, or 30D.`,
      };
    }

    try {
      // Load all samples for the window
      const samples = await SentimentDirSampleModel.find({ window }).lean();

      if (samples.length < 30) {
        return {
          ok: false,
          error: `Not enough samples: ${samples.length}. Need at least 30.`,
          window,
          sampleCount: samples.length,
        };
      }

      // Train model
      const result = await SentimentBinaryTrainer.trainUpModel({
        window,
        samples: samples as any[],
        epochs: body.epochs,
        lr: body.lr,
        testRatio: body.testRatio,
      });

      return {
        ok: true,
        modelId: result.modelId,
        meta: result.meta,
      };

    } catch (err: any) {
      console.error('[BinaryAdmin] Train error:', err);
      return {
        ok: false,
        error: err.message,
      };
    }
  });

  /**
   * GET /stats — Training data statistics
   */
  app.get('/stats', async (req: FastifyRequest<{ Querystring: { window?: string } }>) => {
    const window = (req.query.window?.toUpperCase() || '24H') as SentimentWindow;

    const samples = await SentimentDirSampleModel.find({ window }).lean();
    const stats = await SentimentBinaryTrainer.getTrainingStats({
      window,
      samples: samples as any[],
    });

    return {
      ok: true,
      window,
      stats,
    };
  });

  /**
   * POST /predict — Manual inference test
   */
  app.post('/predict', async (req: FastifyRequest<{ Body: PredictBody }>) => {
    const body = req.body || {};
    const window = (body.window || '24H') as SentimentWindow;

    if (!body.symbol) {
      return {
        ok: false,
        error: 'Missing symbol',
      };
    }

    try {
      const result = await SentimentBinaryInferenceService.infer({
        window,
        sampleLike: {
          symbol: body.symbol,
          asOf: new Date(),
          bias: body.bias ?? 0,
          score: body.score ?? 0.5,
          confidence: body.confidence ?? 0.5,
          eventsCount: body.eventsCount ?? 0,
        },
      });

      return {
        ok: true,
        result,
      };

    } catch (err: any) {
      return {
        ok: false,
        error: err.message,
      };
    }
  });

  /**
   * GET /models — List all models
   */
  app.get('/models', async () => {
    const models = await SentimentBinModel.find({})
      .sort({ 'meta.createdAt': -1 })
      .lean();

    return {
      ok: true,
      count: models.length,
      models: models.map(m => ({
        modelId: m.modelId,
        window: m.window,
        algo: m.algo,
        weightsCount: m.weights?.length,
        meta: m.meta,
      })),
    };
  });

  /**
   * POST /activate — Manually activate a specific model
   */
  app.post('/activate', async (req: FastifyRequest<{ Body: { modelId: string } }>) => {
    const { modelId } = req.body || {};

    if (!modelId) {
      return { ok: false, error: 'Missing modelId' };
    }

    const model = await SentimentBinModel.findOne({ modelId }).lean();
    if (!model) {
      return { ok: false, error: `Model not found: ${modelId}` };
    }

    await SentimentBinRegistry.updateOne(
      { window: model.window },
      { $set: { activeModelId: modelId, updatedAt: new Date() } },
      { upsert: true }
    );

    return {
      ok: true,
      message: `Activated ${modelId} for ${model.window}`,
    };
  });

  console.log('[Sentiment-ML] Binary Admin routes registered (BLOCK 8)');
}

// Export wrapped in fastify-plugin
export default fp(sentimentBinaryAdminRoutes, {
  name: 'sentiment-binary-admin-routes',
  fastify: '4.x',
});

export { sentimentBinaryAdminRoutes };
