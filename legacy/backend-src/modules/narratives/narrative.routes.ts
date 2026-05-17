/**
 * БЛОК 16-18 — Narrative Routes
 * Narrative Intelligence - tracks crypto narratives lifecycle
 * SEEDING → IGNITION → EXPANSION → DECAY
 */

import { FastifyInstance } from 'fastify';
import { Db, ObjectId } from 'mongodb';

// Narrative types
interface Narrative {
  _id?: ObjectId;
  key: string;
  displayName: string;
  description?: string;
  state: 'SEEDING' | 'IGNITION' | 'EXPANSION' | 'SATURATION' | 'DECAY';
  nms: number; // Narrative Momentum Score
  velocity: number;
  influencerWeight: number;
  clusterSpread: number;
  noveltyFactor: number;
  mentionCount: number;
  uniqueInfluencers: number;
  tokens: string[];
  timestamp: Date;
  createdAt: Date;
}

interface NarrativeMention {
  _id?: ObjectId;
  narrativeKey: string;
  tweetId: string;
  authorId: string;
  authorUsername: string;
  text: string;
  tokens: string[];
  confidence: number;
  timestamp: Date;
}

// NMS Calculation
function calculateNMS(velocity: number, influencerWeight: number, clusterSpread: number, noveltyFactor: number): number {
  const v = Math.max(0, Math.min(1, velocity / 100));
  const i = Math.max(0, Math.min(1, influencerWeight));
  const c = Math.max(0, Math.min(1, clusterSpread));
  const n = Math.max(0, Math.min(1, noveltyFactor));
  return v * 0.3 + i * 0.3 + c * 0.2 + n * 0.2;
}

function classifyState(nms: number, ageHours: number): Narrative['state'] {
  if (nms < 0.2) return 'SEEDING';
  if (nms >= 0.8 && ageHours < 24) return 'IGNITION';
  if (nms >= 0.6 && ageHours < 72) return 'EXPANSION';
  if (nms >= 0.4 && ageHours >= 72) return 'SATURATION';
  return 'DECAY';
}

export async function registerNarrativeRoutes(app: FastifyInstance, db: Db): Promise<void> {
  const narrativesCol = db.collection<Narrative>('narratives');
  const mentionsCol = db.collection<NarrativeMention>('narrative_mentions');
  const bindingsCol = db.collection('narrative_bindings');
  const atomsCol = db.collection('narrative_atoms');

  // ═══════════════════════════════════════════════════════════════
  // PUBLIC API - /api/narratives (Block 16-18 Connections)
  // Different from /api/market/narratives (on-chain flow analysis)
  // ═══════════════════════════════════════════════════════════════

  // GET /api/narratives - all narratives with stats (for NarrativesPage)
  app.get('/api/narratives', async (_req, reply) => {
    try {
      const narratives = await narrativesCol.find({}).sort({ nms: -1 }).toArray();
      
      // Calculate stats
      const stats = {
        active: narratives.filter(n => n.state === 'IGNITION' || n.state === 'EXPANSION').length,
        igniting: narratives.filter(n => n.state === 'IGNITION').length,
        expanding: narratives.filter(n => n.state === 'EXPANSION').length,
        candidates: narratives.filter(n => n.state === 'SEEDING').length,
        alphaSignals: narratives.filter(n => n.nms > 0.7).length,
        totalSignals: narratives.length,
      };

      // Transform for frontend
      const data = {
        narratives: narratives.map(n => ({
          key: n.key,
          name: n.displayName,
          description: n.description,
          phase: n.state,
          nms: n.nms,
          velocity: n.velocity,
          mentionCount: n.mentionCount,
          uniqueInfluencers: n.uniqueInfluencers,
          tokens: n.tokens,
          confidence: n.nms,
          timestamp: n.timestamp,
        })),
        ...stats,
      };

      return reply.send({ ok: true, data });
    } catch (error: any) {
      console.error('[Narratives] Error fetching narratives:', error);
      return reply.send({ 
        ok: true, 
        data: { 
          narratives: [], 
          active: 0, igniting: 0, expanding: 0, candidates: 0, alphaSignals: 0, totalSignals: 0 
        } 
      });
    }
  });

  // GET /api/narratives/top - top emerging narratives
  app.get('/api/narratives/top', async (req, reply) => {
    const { limit = '10' } = req.query as { limit?: string };
    try {
      const narratives = await narrativesCol
        .find({ state: { $in: ['SEEDING', 'IGNITION'] } })
        .sort({ nms: -1 })
        .limit(Number(limit))
        .toArray();

      return reply.send({ ok: true, data: narratives });
    } catch (error) {
      return reply.send({ ok: true, data: [] });
    }
  });

  // GET /api/narratives/candidates - token candidates from narratives
  app.get('/api/narratives/candidates', async (req, reply) => {
    const { limit = '30' } = req.query as { limit?: string };
    try {
      // Get narratives in early stages
      const narratives = await narrativesCol
        .find({ state: { $in: ['SEEDING', 'IGNITION', 'EXPANSION'] } })
        .sort({ nms: -1 })
        .limit(20)
        .toArray();

      // Extract token candidates
      const tokenMap = new Map<string, { symbol: string; narratives: string[]; score: number }>();
      
      for (const n of narratives) {
        for (const token of n.tokens || []) {
          if (!tokenMap.has(token)) {
            tokenMap.set(token, { symbol: token, narratives: [], score: 0 });
          }
          const entry = tokenMap.get(token)!;
          entry.narratives.push(n.key);
          entry.score += n.nms;
        }
      }

      const candidates = Array.from(tokenMap.values())
        .sort((a, b) => b.score - a.score)
        .slice(0, Number(limit));

      return reply.send({ ok: true, data: candidates });
    } catch (error) {
      return reply.send({ ok: true, data: [] });
    }
  });

  // GET /api/narratives/:key - single narrative details
  app.get('/api/narratives/:key', async (req, reply) => {
    const { key } = req.params as { key: string };
    try {
      const narrative = await narrativesCol.findOne({ key: key.toUpperCase() });
      if (!narrative) {
        return reply.status(404).send({ ok: false, error: 'Narrative not found' });
      }
      return reply.send({ ok: true, data: narrative });
    } catch (error) {
      return reply.status(500).send({ ok: false, error: 'Internal error' });
    }
  });

  // GET /api/narratives/atoms/trending - trending keywords
  app.get('/api/narratives/atoms/trending', async (req, reply) => {
    const { limit = '20' } = req.query as { limit?: string };
    try {
      const atoms = await atomsCol
        .find({})
        .sort({ weightedAttention: -1 })
        .limit(Number(limit))
        .toArray();

      return reply.send({ ok: true, data: atoms });
    } catch (error) {
      return reply.send({ ok: true, data: [] });
    }
  });

  // ═══════════════════════════════════════════════════════════════
  // ALPHA SIGNALS API - /api/alpha
  // ═══════════════════════════════════════════════════════════════

  // GET /api/alpha/top - top alpha signals from narratives
  app.get('/api/alpha/top', async (req, reply) => {
    const { limit = '10' } = req.query as { limit?: string };
    try {
      const narratives = await narrativesCol
        .find({ nms: { $gte: 0.6 } })
        .sort({ nms: -1 })
        .limit(Number(limit))
        .toArray();

      const signals = narratives.map(n => ({
        key: n.key,
        name: n.displayName,
        score: n.nms,
        phase: n.state,
        tokens: n.tokens,
        confidence: n.nms,
      }));

      return reply.send({ ok: true, data: signals });
    } catch (error) {
      return reply.send({ ok: true, data: [] });
    }
  });

  // GET /api/alpha/health - alpha system health
  app.get('/api/alpha/health', async (_req, reply) => {
    try {
      const totalNarratives = await narrativesCol.countDocuments();
      const activeNarratives = await narrativesCol.countDocuments({ 
        state: { $in: ['IGNITION', 'EXPANSION'] } 
      });
      const recentMentions = await mentionsCol.countDocuments({
        timestamp: { $gte: new Date(Date.now() - 24 * 60 * 60 * 1000) }
      });

      return reply.send({
        ok: true,
        data: {
          status: 'healthy',
          totalNarratives,
          activeNarratives,
          recentMentions24h: recentMentions,
          lastUpdate: new Date(),
        }
      });
    } catch (error) {
      return reply.send({ ok: true, data: { status: 'degraded' } });
    }
  });

  // ═══════════════════════════════════════════════════════════════
  // ADMIN API - /api/admin/narratives
  // ═══════════════════════════════════════════════════════════════

  // POST /api/admin/narratives - create/update narrative
  app.post('/api/admin/narratives', async (req, reply) => {
    const data = req.body as any;
    if (!data.key || !data.displayName) {
      return reply.status(400).send({ ok: false, error: 'Missing key or displayName' });
    }

    try {
      const nms = calculateNMS(
        data.velocity || 0,
        data.influencerWeight || 0,
        data.clusterSpread || 0,
        data.noveltyFactor || 0
      );
      
      const ageHours = data.createdAt 
        ? (Date.now() - new Date(data.createdAt).getTime()) / (1000 * 60 * 60)
        : 0;
      
      const state = classifyState(nms, ageHours);

      const narrative: Omit<Narrative, '_id'> = {
        key: data.key.toUpperCase(),
        displayName: data.displayName,
        description: data.description,
        state,
        nms,
        velocity: data.velocity || 0,
        influencerWeight: data.influencerWeight || 0,
        clusterSpread: data.clusterSpread || 0,
        noveltyFactor: data.noveltyFactor || 0,
        mentionCount: data.mentionCount || 0,
        uniqueInfluencers: data.uniqueInfluencers || 0,
        tokens: data.tokens || [],
        timestamp: new Date(),
        createdAt: data.createdAt ? new Date(data.createdAt) : new Date(),
      };

      await narrativesCol.updateOne(
        { key: narrative.key },
        { $set: narrative, $setOnInsert: { createdAt: new Date() } },
        { upsert: true }
      );

      return reply.send({ ok: true, data: narrative });
    } catch (error: any) {
      return reply.status(500).send({ ok: false, error: error.message });
    }
  });

  // POST /api/admin/narratives/binding - add token binding
  app.post('/api/admin/narratives/binding', async (req, reply) => {
    const { narrativeKey, symbol, weight = 1.0, reason = 'manual' } = req.body as any;
    if (!narrativeKey || !symbol) {
      return reply.status(400).send({ ok: false, error: 'Missing narrativeKey or symbol' });
    }

    try {
      await bindingsCol.updateOne(
        { narrativeKey, symbol },
        { $set: { narrativeKey, symbol, weight, reason, updatedAt: new Date() } },
        { upsert: true }
      );
      return reply.send({ ok: true });
    } catch (error: any) {
      return reply.status(500).send({ ok: false, error: error.message });
    }
  });

  // GET /api/admin/narratives/mentions - get recent mentions
  app.get('/api/admin/narratives/mentions', async (req, reply) => {
    const { narrativeKey, limit = '50' } = req.query as any;
    try {
      const query: any = {};
      if (narrativeKey) query.narrativeKey = narrativeKey;

      const mentions = await mentionsCol
        .find(query)
        .sort({ timestamp: -1 })
        .limit(Number(limit))
        .toArray();

      return reply.send({ ok: true, data: mentions });
    } catch (error) {
      return reply.send({ ok: true, data: [] });
    }
  });

  console.log('[Narratives] Routes registered at /api/market/narratives/*, /api/alpha/*, /api/admin/narratives/*');
}
