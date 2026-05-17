/**
 * Chain Controller (Routes) — Phase G0.1
 * ========================================
 * GET  /api/system/chains         → all chains
 * GET  /api/system/chains/enabled → enabled only
 * PATCH /api/system/chains/:key   → update chain config
 */

import { FastifyInstance } from 'fastify';
import { ChainModel } from './chain.model';
import { ChainRegistry } from './chain.registry';
import { isValidChainKey } from './chain.contracts';

export async function chainRoutes(fastify: FastifyInstance) {

  // GET /chains — all chains
  fastify.get('/chains', async () => {
    const chains = await ChainRegistry.getAll();
    return { ok: true, chains };
  });

  // GET /chains/enabled — enabled only
  fastify.get('/chains/enabled', async () => {
    const chains = await ChainRegistry.getEnabled();
    return { ok: true, chains };
  });

  // PATCH /chains/:key — update chain config
  fastify.patch('/chains/:key', async (req, reply) => {
    const { key } = req.params as { key: string };
    if (!isValidChainKey(key)) {
      return reply.code(400).send({ ok: false, error: 'INVALID_CHAIN_KEY' });
    }

    const body = req.body as Record<string, any> || {};
    const update: Record<string, any> = {};

    if (typeof body.enabled === 'boolean') update.enabled = body.enabled;
    if (typeof body.rpcUrl === 'string') update.rpcUrl = body.rpcUrl;
    if (typeof body.explorerUrl === 'string') update.explorerUrl = body.explorerUrl;
    if (typeof body.priority === 'number') update.priority = body.priority;

    if (Object.keys(update).length === 0) {
      return reply.code(400).send({ ok: false, error: 'NO_FIELDS_TO_UPDATE' });
    }

    const result = await ChainModel.updateOne({ key }, { $set: update });
    if (result.matchedCount === 0) {
      return reply.code(404).send({ ok: false, error: 'CHAIN_NOT_FOUND' });
    }

    // Invalidate cache
    await ChainRegistry.invalidate();

    const chain = await ChainRegistry.getByKey(key as any);
    return { ok: true, chain };
  });

  console.log('[Chains] Routes registered');
}
