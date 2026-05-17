/**
 * OnChain V2 — Normalization Routes
 * ===================================
 * 
 * BLOCK 6: Debug endpoints to inspect normalized signals.
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { normalizerService } from './normalizer.service.js';

// ═══════════════════════════════════════════════════════════════
// DEPENDENCIES INTERFACE
// ═══════════════════════════════════════════════════════════════

export interface NormalizationDeps {
  marketLiquidity: {
    getLatest: (window: string) => Promise<any>;
  };
  bridgeAgg: {
    getLatest: (window: string) => Promise<any>;
  };
  stablesAgg: {
    getLatest: (window: string) => Promise<any>;
  };
}

// ═══════════════════════════════════════════════════════════════
// ROUTE BUILDER
// ═══════════════════════════════════════════════════════════════

export function buildNormalizationRoutes(deps: NormalizationDeps) {
  return async function normalizationRoutes(fastify: FastifyInstance): Promise<void> {
    
    // Debug: Get all normalized signals
    fastify.get('/debug/latest', async (
      request: FastifyRequest<{ Querystring: { window?: string } }>,
      reply: FastifyReply
    ) => {
      const window = request.query.window || '24h';
      
      try {
        // Fetch latest from each module
        const [marketLatest, bridgeLatest, stablesLatest] = await Promise.all([
          deps.marketLiquidity.getLatest(window).catch(() => null),
          deps.bridgeAgg.getLatest(window).catch(() => null),
          deps.stablesAgg.getLatest(window).catch(() => null),
        ]);

        // Normalize each signal
        const marketSig = normalizerService.normalizeMarket(
          marketLatest?.score?.value ?? marketLatest?.score ?? 50,
          marketLatest?.score?.confidence ?? marketLatest?.confidence ?? 0,
          marketLatest?.drivers ?? [],
          marketLatest?.flags ?? [],
          { bucketTs: marketLatest?.bucketTs }
        );

        // Flow: currently extracted from market or separate
        const flowSig = normalizerService.normalizeFlow(
          marketLatest?.dexImbalancePct ?? 0,
          marketLatest?.flowConfidence ?? 0.3,
          ['Flow from DEX activity'],
          marketLatest?.dexImbalancePct === undefined ? ['FLOW_NO_DATA'] : [],
          { source: 'market' }
        );

        const bridgeSig = normalizerService.normalizeBridge(
          bridgeLatest?.metrics?.netUsd ?? 0,
          bridgeLatest?.score?.confidence ?? 0,
          bridgeLatest?.drivers ?? [],
          bridgeLatest?.flags ?? [],
          { bucketTs: bridgeLatest?.bucketTs }
        );

        const stablesSig = normalizerService.normalizeStables(
          stablesLatest?.metrics?.netUsd ?? 0,
          stablesLatest?.score?.confidence ?? 0,
          stablesLatest?.drivers ?? [],
          stablesLatest?.flags ?? [],
          { bucketTs: stablesLatest?.bucketTs }
        );

        return {
          ok: true,
          window,
          ts: Date.now(),
          signals: [marketSig, flowSig, bridgeSig, stablesSig],
          summary: {
            avgScore: (marketSig.score + flowSig.score + bridgeSig.score + stablesSig.score) / 4,
            avgConfidence: (marketSig.confidence + flowSig.confidence + bridgeSig.confidence + stablesSig.confidence) / 4,
          },
        };
      } catch (error) {
        return {
          ok: false,
          error: error instanceof Error ? error.message : 'Unknown error',
        };
      }
    });

    // Health check
    fastify.get('/health', async (request, reply) => {
      return {
        ok: true,
        module: 'normalization',
        version: 'v1.0.0',
        ts: Date.now(),
      };
    });

    console.log('[OnChain V2] Normalization routes registered');
  };
}

console.log('[OnChain V2] Normalization routes module loaded');
