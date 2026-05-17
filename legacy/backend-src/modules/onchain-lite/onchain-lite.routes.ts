/**
 * On-Chain Lite Routes
 * ====================
 * 
 * GET /api/onchain/summary   — Network health (block, gas, TPS)
 * GET /api/onchain/flows     — Exchange + Stablecoin flows
 * GET /api/onchain/whales    — Large transfers
 * GET /api/onchain/activity  — DEX, TVL, liquidity
 */

import { FastifyInstance } from 'fastify';
import { onchainLiteService } from './onchain-lite.service.js';

export async function onchainLiteRoutes(fastify: FastifyInstance): Promise<void> {

  fastify.get('/summary', async () => {
    try {
      const data = await onchainLiteService.getSummary();
      return { ok: true, data, mode: onchainLiteService.getMode() };
    } catch (err: any) {
      console.error('[Onchain-Lite] Summary error:', err?.message);
      return { ok: false, error: err?.message || 'Failed to fetch summary', mode: onchainLiteService.getMode() };
    }
  });

  fastify.get('/flows', async () => {
    try {
      const data = await onchainLiteService.getFlows();
      return { ok: true, data, mode: onchainLiteService.getMode() };
    } catch (err: any) {
      console.error('[Onchain-Lite] Flows error:', err?.message);
      return { ok: false, error: err?.message || 'Failed to fetch flows', mode: onchainLiteService.getMode() };
    }
  });

  fastify.get('/whales', async () => {
    try {
      const data = await onchainLiteService.getWhales();
      return { ok: true, data, mode: onchainLiteService.getMode() };
    } catch (err: any) {
      console.error('[Onchain-Lite] Whales error:', err?.message);
      return { ok: false, error: err?.message || 'Failed to fetch whales', mode: onchainLiteService.getMode() };
    }
  });

  fastify.get('/activity', async () => {
    try {
      const data = await onchainLiteService.getActivity();
      return { ok: true, data, mode: onchainLiteService.getMode() };
    } catch (err: any) {
      console.error('[Onchain-Lite] Activity error:', err?.message);
      return { ok: false, error: err?.message || 'Failed to fetch activity', mode: onchainLiteService.getMode() };
    }
  });

  console.log('[Onchain-Lite] Routes registered');
}
