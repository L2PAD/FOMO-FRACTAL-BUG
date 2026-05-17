/**
 * Actors Routes
 * ==============
 * 
 * PHASE 5: API endpoints for actors/entities
 * P0.8: Added job control and buckets endpoints
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { ActorsListService } from './actors.list.service';
import { ActorsProfileService } from './actors.profile.service';
import { EntityBucketsService } from './entityBuckets.service';
import { getEntityFlowJob } from './entityFlow.job';
import { LabelsService } from '../../labels/labels.service';
import { EntityFlowAggregateService } from './entityFlow.aggregate.service';
import { ActorScoreModel } from './actorScore.model';
import { getActorScoreJob } from './actorScore.job';

const listSvc = new ActorsListService();
const profileSvc = new ActorsProfileService();
const bucketsSvc = new EntityBucketsService();

/**
 * GET /actors/list - List top accumulators or distributors
 */
async function listHandler(
  request: FastifyRequest<{
    Querystring: {
      chainId?: string;
      window?: string;
      direction?: string;
      limit?: string;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const chainId = Number(request.query.chainId ?? 1);
    const window = (request.query.window as '24h' | '7d' | '30d') ?? '7d';
    const direction = (request.query.direction as 'accumulation' | 'distribution') ?? 'accumulation';
    const limit = Number(request.query.limit ?? 20);

    const out = await listSvc.list({ chainId, window, direction, limit });
    return out;
  } catch (e: any) {
    return { ok: false, error: e.message };
  }
}

/**
 * GET /actors/profile - Get detailed profile for an entity
 */
async function profileHandler(
  request: FastifyRequest<{
    Querystring: {
      chainId?: string;
      window?: string;
      entityId?: string;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const chainId = Number(request.query.chainId ?? 1);
    const window = (request.query.window as '24h' | '7d' | '30d') ?? '7d';
    const entityId = String(request.query.entityId ?? '');

    if (!entityId) {
      return { ok: false, error: 'MISSING_ENTITY_ID' };
    }

    const out = await profileSvc.profile({ chainId, window, entityId });
    return out;
  } catch (e: any) {
    return { ok: false, error: e.message };
  }
}

/**
 * GET /actors/stats - Get aggregate stats for actors
 */
async function statsHandler(
  request: FastifyRequest<{
    Querystring: {
      chainId?: string;
      window?: string;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const chainId = Number(request.query.chainId ?? 1);
    const window = (request.query.window as '24h' | '7d' | '30d') ?? '7d';

    const { EntityFlowModel } = await import('./entityFlow.model');

    const typeStats = await EntityFlowModel.aggregate([
      { $match: { chainId, window } },
      {
        $group: {
          _id: '$entityType',
          count: { $sum: 1 },
          totalNetUsd: { $sum: '$netUsd' },
          totalTrades: { $sum: '$trades' },
        },
      },
      { $sort: { totalNetUsd: -1 } },
    ]);

    const totalAccum = await EntityFlowModel.aggregate([
      { $match: { chainId, window, netUsd: { $gt: 0 } } },
      { $group: { _id: null, total: { $sum: '$netUsd' }, count: { $sum: 1 } } },
    ]);

    const totalDist = await EntityFlowModel.aggregate([
      { $match: { chainId, window, netUsd: { $lt: 0 } } },
      { $group: { _id: null, total: { $sum: '$netUsd' }, count: { $sum: 1 } } },
    ]);

    return {
      ok: true,
      chainId,
      window,
      byType: typeStats,
      accumulation: {
        totalUsd: totalAccum[0]?.total ?? 0,
        entities: totalAccum[0]?.count ?? 0,
      },
      distribution: {
        totalUsd: totalDist[0]?.total ?? 0,
        entities: totalDist[0]?.count ?? 0,
      },
    };
  } catch (e: any) {
    return { ok: false, error: e.message };
  }
}

/**
 * GET /actors/job/status - Get aggregation job status
 */
async function jobStatusHandler(request: FastifyRequest, reply: FastifyReply) {
  const job = getEntityFlowJob();
  if (!job) {
    return { ok: true, enabled: false, reason: 'JOB_NOT_INITIALIZED' };
  }
  return job.status();
}

/**
 * POST /actors/job/force-tick - Force run aggregation
 */
async function forceTickHandler(request: FastifyRequest, reply: FastifyReply) {
  const job = getEntityFlowJob();
  if (!job) {
    return { ok: false, error: 'JOB_NOT_INITIALIZED' };
  }

  try {
    const result = await job.tick();
    return { ok: true, ...result };
  } catch (e: any) {
    return { ok: false, error: e.message };
  }
}

/**
 * POST /actors/aggregate - Manual aggregation trigger
 */
async function aggregateHandler(
  request: FastifyRequest<{
    Body: {
      chainId?: number;
      window?: string;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const chainId = Number(request.body?.chainId ?? 1);
    const window = (request.body?.window as '24h' | '7d' | '30d') ?? '7d';

    const labels = new LabelsService();
    const svc = new EntityFlowAggregateService(labels);
    const result = await svc.compute({ chainId, window, maxBuckets: 72 });

    return result;
  } catch (e: any) {
    return { ok: false, error: e.message };
  }
}

/**
 * GET /actors/buckets/latest - Get latest entity buckets by type
 */
async function bucketsLatestHandler(
  request: FastifyRequest<{
    Querystring: {
      chainId?: string;
      window?: string;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const chainId = Number(request.query.chainId ?? 1);
    const window = (request.query.window as '24h' | '7d' | '30d') ?? '7d';

    // First compute fresh, then return
    const computed = await bucketsSvc.computeLatest(chainId, window);
    return computed;
  } catch (e: any) {
    return { ok: false, error: e.message };
  }
}

/**
 * GET /actors/buckets/read - Read cached entity buckets
 */
async function bucketsReadHandler(
  request: FastifyRequest<{
    Querystring: {
      chainId?: string;
      window?: string;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const chainId = Number(request.query.chainId ?? 1);
    const window = (request.query.window as '24h' | '7d' | '30d') ?? '7d';

    return bucketsSvc.getLatest(chainId, window);
  } catch (e: any) {
    return { ok: false, error: e.message };
  }
}

/**
 * P0.9: Structural Edge Score — list by edgeScore
 */
async function structuralListHandler(
  request: FastifyRequest<{
    Querystring: {
      chainId?: string;
      window?: string;
      q?: string;
      minScore?: string;
      type?: string;
      limit?: string;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const chainId = Number(request.query.chainId ?? 1);
    const window = String(request.query.window ?? '7d');
    const q = String(request.query.q ?? '').trim();
    const minScore = Number(request.query.minScore ?? 0);
    const type = String(request.query.type ?? '').trim();
    const limit = Math.min(Math.max(Number(request.query.limit ?? 80), 10), 200);

    const last = await ActorScoreModel.findOne({ chainId, window })
      .sort({ bucketTs: -1 })
      .select('bucketTs')
      .lean();
    const bucketTs = last?.bucketTs;
    if (!bucketTs) return { ok: true, items: [], reason: 'NO_SCORES' };

    const filter: any = { chainId, window, bucketTs, edgeScore: { $gte: minScore } };
    if (type) filter.entityType = type;
    if (q) {
      filter.$or = [
        { entityName: { $regex: q, $options: 'i' } },
        { entityId: { $regex: q, $options: 'i' } },
      ];
    }

    const items = await ActorScoreModel.find(filter, { _id: 0, __v: 0 })
      .sort({ edgeScore: -1 })
      .limit(limit)
      .lean();

    return { ok: true, chainId, window, bucketTs, items };
  } catch (e: any) {
    return { ok: false, error: e.message };
  }
}

async function structuralJobStatusHandler(request: FastifyRequest, reply: FastifyReply) {
  return getActorScoreJob().status();
}

async function structuralJobForceTickHandler(request: FastifyRequest, reply: FastifyReply) {
  try {
    return await getActorScoreJob().tick();
  } catch (e: any) {
    return { ok: false, error: e.message };
  }
}

/**
 * Register actors routes
 */
export async function actorsRoutes(fastify: FastifyInstance): Promise<void> {
  // Core endpoints
  fastify.get('/list', listHandler);
  fastify.get('/profile', profileHandler);
  fastify.get('/stats', statsHandler);

  // Job control (P0.8)
  fastify.get('/job/status', jobStatusHandler);
  fastify.post('/job/force-tick', forceTickHandler);
  fastify.post('/aggregate', aggregateHandler);

  // Entity Buckets (P2.1)
  fastify.get('/buckets/latest', bucketsLatestHandler);
  fastify.get('/buckets/read', bucketsReadHandler);

  // P0.9: Structural Edge Score endpoints
  fastify.get('/structural/list', structuralListHandler);
  fastify.get('/structural/job/status', structuralJobStatusHandler);
  fastify.post('/structural/job/force-tick', structuralJobForceTickHandler);

  console.log('[Actors Routes] Registered with job control + structural');
}

export default actorsRoutes;
