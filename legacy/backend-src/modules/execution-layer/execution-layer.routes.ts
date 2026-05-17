/**
 * Execution Layer Routes
 *
 * POST /api/execution-layer/analyze       — Full execution analysis for a single case
 * POST /api/execution-layer/analyze/batch  — Batch execution analysis
 */

import type { FastifyInstance } from 'fastify';
import { microstructureOrchestratorService } from './services/microstructure-orchestrator.service.js';

interface AnalyzeBody {
  spread: number;
  liquidity: number;
  volume24h: number;
  edge: number;
  fairProb: number;
  marketProb: number;
  confidence: number;
  alignment: number;
  repricingState: string;
  marketStage: string;
  socialSaturation: number;
  socialLifecycle?: string | null;
  projectVerdict?: string | null;
  positionOversized?: boolean;
  originalEdge?: number;
  probVolatility?: number;
}

interface BatchBody {
  cases: (AnalyzeBody & { marketId: string })[];
}

export async function executionLayerRoutes(app: FastifyInstance): Promise<void> {
  /**
   * POST /api/execution-layer/analyze — Single case execution analysis
   */
  app.post<{ Body: AnalyzeBody }>('/analyze', async (request) => {
    const body = request.body;

    if (body.spread == null || body.edge == null) {
      return { ok: false, error: 'spread and edge are required' };
    }

    const result = microstructureOrchestratorService.analyze({
      spread: body.spread ?? 0,
      liquidity: body.liquidity ?? 0,
      volume24h: body.volume24h ?? 0,
      edge: body.edge ?? 0,
      fairProb: body.fairProb ?? 0.5,
      marketProb: body.marketProb ?? 0.5,
      confidence: body.confidence ?? 0.5,
      alignment: body.alignment ?? 0.5,
      repricingState: body.repricingState ?? 'stalled',
      marketStage: body.marketStage ?? 'unknown',
      socialSaturation: body.socialSaturation ?? 0,
      socialLifecycle: body.socialLifecycle ?? null,
      projectVerdict: body.projectVerdict ?? null,
      positionOversized: body.positionOversized ?? false,
      originalEdge: body.originalEdge,
      probVolatility: body.probVolatility,
    });

    return { ok: true, execution: result };
  });

  /**
   * POST /api/execution-layer/analyze/batch — Batch analysis
   */
  app.post<{ Body: BatchBody }>('/analyze/batch', async (request) => {
    const { cases } = request.body;
    if (!cases?.length) return { ok: false, error: 'cases array required' };

    const results: Record<string, any> = {};

    for (const c of cases) {
      try {
        results[c.marketId] = microstructureOrchestratorService.analyze({
          spread: c.spread ?? 0,
          liquidity: c.liquidity ?? 0,
          volume24h: c.volume24h ?? 0,
          edge: c.edge ?? 0,
          fairProb: c.fairProb ?? 0.5,
          marketProb: c.marketProb ?? 0.5,
          confidence: c.confidence ?? 0.5,
          alignment: c.alignment ?? 0.5,
          repricingState: c.repricingState ?? 'stalled',
          marketStage: c.marketStage ?? 'unknown',
          socialSaturation: c.socialSaturation ?? 0,
          socialLifecycle: c.socialLifecycle ?? null,
          projectVerdict: c.projectVerdict ?? null,
          positionOversized: c.positionOversized ?? false,
          originalEdge: c.originalEdge,
          probVolatility: c.probVolatility,
        });
      } catch {
        results[c.marketId] = null;
      }
    }

    return { ok: true, results, count: Object.keys(results).length };
  });
}
