/**
 * OnChain V2 — Final Output Routes
 * ==================================
 * 
 * The canonical endpoint for consumers.
 * 
 * GET /api/v10/onchain-v2/final/:symbol
 */

import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { finalOutputService } from './final.service.js';
import type { OnchainWindow } from '../core/contracts.js';

export async function finalRoutes(app: FastifyInstance) {
  
  /**
   * GET /api/v10/onchain-v2/final/:symbol
   * 
   * The OFFICIAL contract for MetaBrain/Prediction consumers.
   * Returns governed, EMA-smoothed, guardrail-protected output.
   */
  app.get('/final/:symbol', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const params = req.params as { symbol: string };
      const query = req.query as { window?: string; chainId?: string };
      
      const symbol = params.symbol.toUpperCase();
      const window = (query.window || '30d') as OnchainWindow;
      const chainId = query.chainId ? parseInt(query.chainId) : 1;
      
      const output = await finalOutputService.getFinalOutput({ symbol, window, chainId });
      
      return {
        ok: true,
        output,
      };
    } catch (err) {
      console.error('[FinalRoutes] final/:symbol error:', err);
      return reply.status(500).send({
        ok: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  });
  
  /**
   * GET /api/v10/onchain-v2/final/debug/:symbol
   * 
   * Debug endpoint showing all intermediate values.
   */
  app.get('/final/debug/:symbol', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const params = req.params as { symbol: string };
      const symbol = params.symbol.toUpperCase();
      
      const output = await finalOutputService.getFinalOutput({ symbol });
      const emaState = finalOutputService.getEmaState(symbol);
      const config = finalOutputService.getConfig();
      
      return {
        ok: true,
        output,
        debug: {
          emaState,
          config,
        },
      };
    } catch (err) {
      console.error('[FinalRoutes] final/debug error:', err);
      return reply.status(500).send({
        ok: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  });
  
  /**
   * POST /api/v10/onchain-v2/final/reset-ema
   * 
   * Reset EMA state for testing/recovery.
   */
  app.post('/final/reset-ema', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const body = req.body as { symbol?: string };
      const symbol = body.symbol?.toUpperCase() || 'ALL';
      
      if (symbol === 'ALL') {
        // Reset all - not implemented for safety
        return {
          ok: false,
          error: 'Use specific symbol to reset',
        };
      }
      
      finalOutputService.resetEma(symbol);
      
      return {
        ok: true,
        message: `EMA state reset for ${symbol}`,
      };
    } catch (err) {
      console.error('[FinalRoutes] reset-ema error:', err);
      return reply.status(500).send({
        ok: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  });
  
  /**
   * GET /api/v10/onchain-v2/final/config
   * 
   * Get current guardrail config.
   */
  app.get('/final/config', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const config = finalOutputService.getConfig();
      
      return {
        ok: true,
        config,
      };
    } catch (err) {
      console.error('[FinalRoutes] config error:', err);
      return reply.status(500).send({
        ok: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  });
  
  /**
   * PUT /api/v10/onchain-v2/final/config
   * 
   * Update guardrail config (admin only).
   */
  app.put('/final/config', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const body = req.body as Record<string, any>;
      
      // Validate known fields
      const allowedFields = [
        'minSamples30d', 'warnSamples30d',
        'psiWarn', 'psiDegraded', 'psiCritical',
        'modifierHealthy', 'modifierWarn', 'modifierDegraded', 'modifierCritical',
        'emaAlpha', 'emaWindow',
        'providerHealthRequired', 'maxDataAgeMs',
      ];
      
      const updates: Record<string, any> = {};
      for (const field of allowedFields) {
        if (field in body) {
          updates[field] = body[field];
        }
      }
      
      if (Object.keys(updates).length === 0) {
        return {
          ok: false,
          error: 'No valid fields to update',
        };
      }
      
      finalOutputService.updateConfig(updates);
      
      return {
        ok: true,
        message: 'Config updated',
        config: finalOutputService.getConfig(),
      };
    } catch (err) {
      console.error('[FinalRoutes] config update error:', err);
      return reply.status(500).send({
        ok: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  });
  
  console.log('[OnChain V2] Final routes registered');
}
