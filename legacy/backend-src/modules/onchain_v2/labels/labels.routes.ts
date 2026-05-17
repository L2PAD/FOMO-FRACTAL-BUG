/**
 * Labels Routes
 * ==============
 * 
 * P0 Labeling: API endpoints for entity labels
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { LabelsService } from './labels.service';
import { LABEL_SEED_V1 } from './labels.seed';
import { LabelType } from './addressLabel.model';

const svc = new LabelsService();

/**
 * GET /labels - List labels with optional filters
 */
async function listHandler(
  request: FastifyRequest<{
    Querystring: {
      chainId?: string;
      q?: string;
      type?: string;
      limit?: string;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const chainId = Number(request.query.chainId ?? 1);
    const q = request.query.q ? String(request.query.q) : undefined;
    const type = request.query.type ? (String(request.query.type) as LabelType) : undefined;
    const limit = request.query.limit ? Number(request.query.limit) : 50;

    const out = await svc.list({ chainId, q, type, limit });
    return out;
  } catch (e: any) {
    return { ok: false, error: e.message };
  }
}

/**
 * GET /labels/resolve - Resolve single address
 */
async function resolveHandler(
  request: FastifyRequest<{
    Querystring: {
      chainId?: string;
      address?: string;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const chainId = Number(request.query.chainId ?? 1);
    const address = String(request.query.address ?? '');

    if (!address) {
      return { ok: false, error: 'MISSING_ADDRESS' };
    }

    const label = await svc.resolve(chainId, address);
    return { ok: true, label };
  } catch (e: any) {
    return { ok: false, error: e.message };
  }
}

/**
 * GET /labels/stats - Get label statistics
 */
async function statsHandler(
  request: FastifyRequest<{
    Querystring: {
      chainId?: string;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const chainId = Number(request.query.chainId ?? 1);
    const stats = await svc.stats(chainId);
    return stats;
  } catch (e: any) {
    return { ok: false, error: e.message };
  }
}

/**
 * POST /labels/seed - Seed initial labels
 */
async function seedHandler(
  request: FastifyRequest<{
    Body: {
      chainId?: number;
      only?: string;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const chainId = Number(request.body?.chainId ?? 1);
    const only = request.body?.only ? String(request.body.only) : null;

    const items = LABEL_SEED_V1.filter((x) => x.chainId === chainId).filter((x) =>
      only ? x.labelType === only : true
    );

    const out = await svc.upsertMany(items as any);
    return { ok: true, ...out, count: items.length };
  } catch (e: any) {
    return { ok: false, error: e.message };
  }
}

/**
 * POST /labels/upsert - Manually upsert labels
 */
async function upsertHandler(
  request: FastifyRequest<{
    Body: {
      items?: any[];
    };
  }>,
  reply: FastifyReply
) {
  try {
    const items = Array.isArray(request.body?.items) ? request.body.items : [];

    if (!items.length) {
      return { ok: false, error: 'EMPTY_ITEMS' };
    }

    const out = await svc.upsertMany(items);
    return out;
  } catch (e: any) {
    return { ok: false, error: e.message };
  }
}

/**
 * POST /labels/batch-resolve - Batch resolve addresses
 */
async function batchResolveHandler(
  request: FastifyRequest<{
    Body: {
      chainId?: number;
      addresses?: string[];
    };
  }>,
  reply: FastifyReply
) {
  try {
    const chainId = Number(request.body?.chainId ?? 1);
    const addresses = Array.isArray(request.body?.addresses) ? request.body.addresses : [];

    if (!addresses.length) {
      return { ok: true, labels: {} };
    }

    const labels = await svc.batchResolve(chainId, addresses);
    return { ok: true, labels };
  } catch (e: any) {
    return { ok: false, error: e.message };
  }
}

/**
 * Register labels routes
 */
export async function labelsRoutes(fastify: FastifyInstance): Promise<void> {
  fastify.get('/', listHandler);
  fastify.get('/resolve', resolveHandler);
  fastify.get('/stats', statsHandler);
  fastify.post('/seed', seedHandler);
  fastify.post('/upsert', upsertHandler);
  fastify.post('/batch-resolve', batchResolveHandler);

  console.log('[Labels Routes] Registered');
}

export default labelsRoutes;
