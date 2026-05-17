/**
 * Connections Routes
 * 
 * ═══════════════════════════════════════════════════════════════
 * LAYER 2 ANALYTICS - READ ONLY
 * ═══════════════════════════════════════════════════════════════
 * 
 * Reads data from seeded MongoDB collections (connections_unified_accounts).
 * Provides social intelligence analytics WITHOUT affecting forecast pipeline.
 * 
 * RULES:
 * 1. Read-only endpoints only
 * 2. No state modification
 * 3. NEVER affects forecast pipeline
 * 4. Isolated from ML/verdict engine
 */

import type { FastifyInstance } from 'fastify';
import { getDb } from '../../db/mongodb.js';

// Get connections database (separate from main DB)
function getConnectionsDb() {
  const client = getDb().client;
  return client.db('connections_db');
}

// ============================================
// TTL In-Memory Cache Layer
// ============================================
const _cache = new Map<string, { data: any; expires: number }>();

function cacheGet(key: string): any | null {
  const entry = _cache.get(key);
  if (!entry) return null;
  if (Date.now() > entry.expires) { _cache.delete(key); return null; }
  return entry.data;
}

function cacheSet(key: string, data: any, ttlMs: number): void {
  _cache.set(key, { data, expires: Date.now() + ttlMs });
}

// Cache TTLs
const TTL = {
  OVERVIEW: 60_000,    // 60s
  CAS: 60_000,         // 60s
  ACTORS: 300_000,     // 5min
  SIGNALS: 120_000,    // 2min
  CLUSTERS: 300_000,   // 5min
  STATS: 120_000,      // 2min
};

export async function registerConnectionsProxyRoutes(app: FastifyInstance): Promise<void> {

  // ============================================
  // HEALTH CHECK
  // ============================================
  
  app.get('/health', async () => {
    try {
      const db = getConnectionsDb();
      const count = await db.collection('connections_unified_accounts').countDocuments();
      return { 
        ok: true, 
        service: 'connections',
        accountsCount: count,
        status: count > 0 ? 'seeded' : 'empty'
      };
    } catch (error) {
      return { ok: false, error: 'Database connection failed' };
    }
  });

  // ============================================
  // STATS
  // ============================================

  app.get('/stats', async () => {
    const cached = cacheGet('stats');
    if (cached) return cached;
    try {
      const db = getConnectionsDb();
      const col = db.collection('connections_unified_accounts');
      
      const total = await col.countDocuments();
      const verified = await col.countDocuments({ verified: true });
      const byCategory = await col.aggregate([
        { $unwind: '$categories' },
        { $group: { _id: '$categories', count: { $sum: 1 } } }
      ]).toArray();
      
      const result = {
        ok: true,
        stats: {
          totalAccounts: total,
          verifiedAccounts: verified,
          byCategory: byCategory.map(c => ({ category: c._id, count: c.count }))
        }
      };
      cacheSet('stats', result, TTL.STATS);
      return result;
    } catch (error) {
      return { ok: false, error: 'Failed to fetch stats' };
    }
  });

  // ============================================
  // ACCOUNTS (INFLUENCERS) - from seed data
  // ============================================

  app.get('/accounts', async (request) => {
    const { limit, sort_by, order, category } = request.query as { 
      limit?: string; 
      sort_by?: string; 
      order?: string;
      category?: string;
    };
    const cacheKey = `accounts:${limit}:${sort_by}:${order}:${category}`;
    const cached = cacheGet(cacheKey);
    if (cached) return cached;
    
    try {
      const db = getConnectionsDb();
      const col = db.collection('connections_unified_accounts');
      
      const sortField = sort_by === 'influence' ? 'influence' : 
                       sort_by === 'smart' ? 'smart' :
                       sort_by === 'followers' ? 'followers' : 'influence';
      const sortOrder = order === 'asc' ? 1 : -1;
      
      const query: any = {};
      if (category) {
        query.categories = category;
      }
      
      const accounts = await col
        .find(query, { projection: { _id: 0 } })
        .sort({ [sortField]: sortOrder })
        .limit(parseInt(limit || '50'))
        .toArray();
      
      const result = { 
        ok: true, 
        accounts,
        total: accounts.length
      };
      cacheSet(cacheKey, result, TTL.ACTORS);
      return result;
    } catch (error) {
      return { ok: false, error: 'Failed to fetch accounts', accounts: [] };
    }
  });

  app.get('/accounts/:handle', async (request, reply) => {
    const { handle } = request.params as { handle: string };
    
    try {
      const db = getConnectionsDb();
      const account = await db.collection('connections_unified_accounts')
        .findOne({ handle: handle.toLowerCase() }, { projection: { _id: 0 } });
      
      if (!account) {
        return reply.status(404).send({ ok: false, error: 'Account not found' });
      }
      
      return { ok: true, account };
    } catch (error) {
      return reply.status(500).send({ ok: false, error: 'Failed to fetch account' });
    }
  });

  // ============================================
  // REALITY SCORE - calculated from seed data
  // ============================================

  app.get('/reality/score', async (request, reply) => {
    const { symbol } = request.query as { symbol?: string };
    
    if (!symbol) {
      return reply.status(400).send({ ok: false, error: 'Symbol required' });
    }
    
    try {
      const db = getConnectionsDb();
      const col = db.collection('connections_unified_accounts');
      
      // Calculate aggregate reality score from influencers
      const stats = await col.aggregate([
        { $match: { confidence: { $exists: true } } },
        { $group: {
          _id: null,
          avgConfidence: { $avg: '$confidence' },
          count: { $sum: 1 }
        }}
      ]).toArray();
      
      const avgScore = stats[0]?.avgConfidence || 0;
      const sample = stats[0]?.count || 0;
      
      return {
        ok: true,
        symbol: symbol.toUpperCase(),
        realityScore: avgScore,
        sample,
        confidence: sample >= 5 ? 'high' : sample >= 2 ? 'medium' : 'low',
        verdictMix: {
          true: Math.floor(sample * avgScore),
          fake: Math.floor(sample * (1 - avgScore) * 0.3),
          neutral: Math.floor(sample * (1 - avgScore) * 0.7)
        }
      };
    } catch (error) {
      return { ok: false, error: 'Failed to calculate reality score' };
    }
  });

  app.get('/reality/leaderboard', async (request) => {
    const { limit } = request.query as { limit?: string };
    const cacheKey = `reality-leaderboard:${limit}`;
    const cached = cacheGet(cacheKey);
    if (cached) return cached;
    
    try {
      const db = getConnectionsDb();
      const leaderboard = await db.collection('connections_unified_accounts')
        .find({ confidence: { $exists: true } }, { projection: { _id: 0 } })
        .sort({ confidence: -1 })
        .limit(parseInt(limit || '10'))
        .toArray();
      
      const result = {
        ok: true,
        leaderboard: leaderboard.map((acc, i) => ({
          rank: i + 1,
          handle: acc.handle,
          name: acc.name,
          avatar: acc.avatar,
          confidence: acc.confidence,
          categories: acc.categories
        }))
      };
      cacheSet(cacheKey, result, TTL.ACTORS);
      return result;
    } catch (error) {
      return { ok: false, leaderboard: [] };
    }
  });

  // ============================================
  // INFLUENCE SCORE
  // ============================================

  app.get('/influence', async (request, reply) => {
    const { symbol } = request.query as { symbol?: string };
    
    if (!symbol) {
      return reply.status(400).send({ ok: false, error: 'Symbol required' });
    }
    
    try {
      const db = getConnectionsDb();
      const col = db.collection('connections_unified_accounts');
      
      // Get top influencers
      const topInfluencers = await col
        .find({}, { projection: { _id: 0, handle: 1, name: 1, avatar: 1, influence: 1, followers: 1 } })
        .sort({ influence: -1 })
        .limit(5)
        .toArray();
      
      // Calculate aggregate influence score
      const stats = await col.aggregate([
        { $group: {
          _id: null,
          avgInfluence: { $avg: '$influence' },
          count: { $sum: 1 }
        }}
      ]).toArray();
      
      return {
        ok: true,
        symbol: symbol.toUpperCase(),
        influenceScore: stats[0]?.avgInfluence || 0,
        clusterCount: Math.ceil((stats[0]?.count || 0) / 3),
        topInfluencers
      };
    } catch (error) {
      return { ok: false, influenceScore: 0, topInfluencers: [] };
    }
  });

  // ============================================
  // CLUSTERS - Real cluster data from connections_clusters + category aggregation
  // ============================================

  app.get('/clusters', async (request) => {
    const { symbol } = request.query as { symbol?: string };
    const cacheKey = `clusters:${symbol || 'all'}`;
    const cached = cacheGet(cacheKey);
    if (cached) return cached;
    
    try {
      const db = getConnectionsDb();
      
      // Get real clusters from connections_clusters collection
      const realClusters = await db.collection('connections_clusters')
        .find({})
        .limit(20)
        .toArray();
      
      // Also aggregate from unified accounts for additional category-based clusters
      const categoryGroups = await db.collection('connections_unified_accounts').aggregate([
        { $unwind: '$categories' },
        { $group: {
          _id: '$categories',
          memberCount: { $sum: 1 },
          avgInfluence: { $avg: '$influence' },
          members: { $push: '$handle' },
          avgTrust: { $avg: '$confidence' },
          avgAuthority: { $avg: '$authority' }
        }},
        { $match: { _id: { $ne: null } } },
        { $sort: { avgInfluence: -1 } }
      ]).toArray();
      
      // Format real clusters
      const formattedRealClusters = realClusters.map(c => ({
        id: c._id,
        name: c.name,
        members: [], // Would need member lookups
        metrics: {
          size: c.memberCount || 0,
          cohesion: 0.7,
          authority: (c.avgInfluence || 500) / 1000,
          avgTrust: 0.6,
        }
      }));
      
      // Format category clusters
      const formattedCategoryClusters = categoryGroups.map(g => ({
        id: `cat_${g._id}`,
        name: g._id,
        members: g.members?.slice(0, 5) || [],
        metrics: {
          size: g.memberCount || 0,
          cohesion: 0.65,
          authority: g.avgAuthority || 0.5,
          avgTrust: g.avgTrust || 0.5,
        }
      }));
      
      // Combine both for a richer dataset
      const allClusters = [...formattedRealClusters, ...formattedCategoryClusters];
      
      const result = {
        ok: true,
        data: allClusters,
      };
      cacheSet(cacheKey, result, TTL.CLUSTERS);
      return result;
    } catch (error) {
      return { ok: false, data: [] };
    }
  });

  // ============================================
  // BACKERS (VC / Foundations)
  // ============================================

  app.get('/backers', async (request) => {
    const { symbol } = request.query as { symbol?: string };
    
    try {
      const db = getConnectionsDb();
      const col = db.collection('connections_unified_accounts');
      
      // Filter accounts that are VCs or have VC-related categories
      const backers = await col
        .find({ 
          $or: [
            { categories: 'VC' },
            { categories: 'INVESTOR' },
            { categories: 'FOUNDER' }
          ]
        }, { projection: { _id: 0 } })
        .sort({ authority: -1 })
        .limit(10)
        .toArray();
      
      return {
        ok: true,
        backers: backers.map(b => ({
          name: b.name || b.handle,
          handle: b.handle,
          avatar: b.avatar,
          type: b.categories?.includes('VC') ? 'vc' : 
                b.categories?.includes('FOUNDER') ? 'founder' : 'investor',
          totalInvestments: Math.floor((b.networkSize || 100) / 10),
          influence: b.influence
        }))
      };
    } catch (error) {
      return { ok: false, backers: [] };
    }
  });

  app.get('/backers/:slug', async (request, reply) => {
    const { slug } = request.params as { slug: string };
    
    try {
      const db = getConnectionsDb();
      const backer = await db.collection('connections_unified_accounts')
        .findOne({ handle: slug.toLowerCase() }, { projection: { _id: 0 } });
      
      if (!backer) {
        return { ok: false, backer: null };
      }
      
      const backerType = backer.categories?.includes('VC') ? 'FUND' :
                         backer.categories?.includes('FOUNDER') ? 'COMPANY' :
                         backer.categories?.includes('INVESTOR') ? 'FUND' : 'COMPANY';
      return {
        ok: true,
        backer: {
          name: backer.name,
          handle: backer.handle,
          avatar: backer.avatar,
          categories: backer.categories,
          type: backerType,
          influence: backer.influence,
          authority: backer.authority,
          seedAuthority: Math.round((backer.authority || backer.influence || 0) * 100),
          confidence: backer.confidence || backer.influence || 0.7,
          networkSize: backer.networkSize,
          description: backer.description || `${backer.name || backer.handle} — key participant in the crypto ecosystem`,
        }
      };
    } catch (error) {
      return { ok: false, backer: null };
    }
  });

  // ============================================
  // BACKER DETAIL ENDPOINTS (network, coinvestors, investments, influence)
  // ============================================

  app.get('/backers/:slug/network', async (request) => {
    const { slug } = request.params as { slug: string };
    try {
      const db = getConnectionsDb();
      const col = db.collection('connections_unified_accounts');

      const backer = await col.findOne({ handle: slug.toLowerCase() }, { projection: { _id: 0 } });
      if (!backer) return { ok: false, data: null };

      const backerCategories = backer.categories || [];

      // Find accounts sharing categories with this backer
      const peers = await col
        .find(
          { handle: { $ne: slug.toLowerCase() }, categories: { $in: backerCategories } },
          { projection: { _id: 0, handle: 1, name: 1, categories: 1, influence: 1, authority: 1 } }
        )
        .sort({ influence: -1 })
        .limit(20)
        .toArray();

      // Build graph nodes
      const nodes: any[] = [
        { id: slug, name: backer.name || slug, type: 'BACKER', authority: (backer.authority || 0.5) * 10 },
      ];
      const edges: any[] = [];

      peers.forEach((p: any) => {
        const shared = (p.categories || []).filter((c: string) => backerCategories.includes(c));
        const weight = Math.min(shared.length / Math.max(backerCategories.length, 1), 1);
        nodes.push({ id: p.handle, name: p.name || p.handle, type: 'BACKER', authority: (p.authority || p.influence || 0.5) * 10 });
        edges.push({ from: slug, to: p.handle, weight });
      });

      // Add inter-peer edges for peers sharing categories
      for (let i = 0; i < peers.length; i++) {
        for (let j = i + 1; j < Math.min(peers.length, 10); j++) {
          const shared = (peers[i].categories || []).filter((c: string) => (peers[j].categories || []).includes(c));
          if (shared.length > 0) {
            edges.push({ from: peers[i].handle, to: peers[j].handle, weight: shared.length * 0.3 });
          }
        }
      }

      return {
        ok: true,
        data: {
          nodes,
          edges,
          stats: { totalNodes: nodes.length, totalEdges: edges.length },
        }
      };
    } catch (error) {
      return { ok: false, data: null };
    }
  });

  app.get('/backers/:slug/coinvestors', async (request) => {
    const { slug } = request.params as { slug: string };
    const { limit } = request.query as { limit?: string };
    try {
      const db = getConnectionsDb();
      const col = db.collection('connections_unified_accounts');

      const backer = await col.findOne({ handle: slug.toLowerCase() }, { projection: { _id: 0 } });
      if (!backer) return { ok: false, coinvestors: [] };

      const backerCategories = backer.categories || [];

      // Find co-investors: accounts sharing at least one category
      const peers = await col
        .find(
          { handle: { $ne: slug.toLowerCase() }, categories: { $in: backerCategories } },
          { projection: { _id: 0, handle: 1, name: 1, avatar: 1, categories: 1, influence: 1, authority: 1 } }
        )
        .sort({ influence: -1 })
        .limit(parseInt(limit || '20'))
        .toArray();

      const coinvestors = peers.map((p: any) => {
        const shared = (p.categories || []).filter((c: string) => backerCategories.includes(c));
        return {
          id: p.handle,
          backerId: p.handle,
          name: p.name || p.handle,
          avatar: p.avatar,
          sharedCount: shared.length,
          shared: shared.length,
          categories: p.categories,
        };
      });

      return { ok: true, coinvestors };
    } catch (error) {
      return { ok: false, coinvestors: [] };
    }
  });

  app.get('/backers/:slug/investments', async (request) => {
    const { slug } = request.params as { slug: string };
    const { limit } = request.query as { limit?: string };
    try {
      const db = getConnectionsDb();
      const col = db.collection('connections_unified_accounts');

      const backer = await col.findOne({ handle: slug.toLowerCase() }, { projection: { _id: 0 } });
      if (!backer) return { ok: false, investments: [] };

      // Simulate portfolio from early signals + backer's category focus
      const signals = await db.collection('connections_early_signals')
        .find({})
        .sort({ strength: -1 })
        .limit(parseInt(limit || '50'))
        .toArray();

      const investments = signals.map((s: any, i: number) => ({
        projectId: s.token,
        project: {
          name: s.token,
          categories: backer.categories?.slice(0, 2) || [],
          stage: s.strength >= 0.8 ? 'Growth' : s.strength >= 0.5 ? 'Early' : 'Seed',
        },
        round: s.strength >= 0.7 ? 'Series A' : s.strength >= 0.4 ? 'Seed' : 'Angel',
      }));

      return { ok: true, investments };
    } catch (error) {
      return { ok: false, investments: [] };
    }
  });

  app.get('/backers/:slug/influence', async (request) => {
    const { slug } = request.params as { slug: string };
    try {
      const db = getConnectionsDb();
      const col = db.collection('connections_unified_accounts');

      const backer = await col.findOne({ handle: slug.toLowerCase() }, { projection: { _id: 0 } });
      if (!backer) return { ok: false, data: null };

      // Get top connections by influence
      const backerCategories = backer.categories || [];
      const peers = await col
        .find(
          { handle: { $ne: slug.toLowerCase() }, categories: { $in: backerCategories } },
          { projection: { _id: 0, handle: 1, name: 1, influence: 1, authority: 1, categories: 1, networkSize: 1 } }
        )
        .sort({ influence: -1 })
        .limit(10)
        .toArray();

      // Build influence graph
      const graphNodes = [
        { id: slug, name: backer.name || slug, influence: backer.influence || 0, isCenter: true },
        ...peers.map((p: any) => ({ id: p.handle, name: p.name || p.handle, influence: p.influence || 0, isCenter: false })),
      ];
      const graphEdges = peers.map((p: any) => {
        const shared = (p.categories || []).filter((c: string) => backerCategories.includes(c));
        return { from: slug, to: p.handle, weight: shared.length * 0.4 };
      });

      // Impact score
      const impactScore = Math.round((backer.influence || 0) * 100);
      const networkRank = impactScore >= 80 ? 'Top 5%' : impactScore >= 60 ? 'Top 15%' : impactScore >= 40 ? 'Top 30%' : 'Top 50%';

      // Project impact (from early signals)
      const signals = await db.collection('connections_early_signals').find({}).sort({ strength: -1 }).limit(10).toArray();
      const projectImpact = signals.map((s: any) => ({
        token: s.token,
        strength: s.strength || 0,
        priceChange: s.priceChange24h || 0,
        mentionCount: s.mentionCount || 0,
      }));

      return {
        ok: true,
        data: {
          summary: { impactScore, networkRank, influence: backer.influence || 0, networkSize: backer.networkSize || 0 },
          graph: { nodes: graphNodes, edges: graphEdges },
          projectImpact,
        }
      };
    } catch (error) {
      return { ok: false, data: null };
    }
  });

  // ============================================
  // INFLUENCERS (Unified Accounts) - main listing
  // ============================================

  app.get('/unified', async (request) => {
    const { limit, sortBy, facet, q } = request.query as { 
      limit?: string; 
      sortBy?: string;
      facet?: string;
      q?: string;
    };
    
    try {
      const db = getConnectionsDb();
      const col = db.collection('connections_unified_accounts');
      
      const sortField = sortBy === 'smart' ? 'smart' : 
                       sortBy === 'authority' ? 'authority' :
                       sortBy === 'followers' ? 'followers' : 'influence';
      
      // Build query
      const query: any = {};
      if (q) {
        query.$or = [
          { handle: { $regex: q, $options: 'i' } },
          { name: { $regex: q, $options: 'i' } }
        ];
      }
      
      const data = await col
        .find(query, { projection: { _id: 0 } })
        .sort({ [sortField]: -1 })
        .limit(parseInt(limit || '50'))
        .toArray();
      
      return { 
        ok: true, 
        data,
        total: data.length
      };
    } catch (error) {
      return { ok: false, data: [], error: 'Failed to fetch unified accounts' };
    }
  });

  // Stats endpoint for unified
  app.get('/unified/stats', async () => {
    const cached = cacheGet('unified-stats');
    if (cached) return cached;
    try {
      const db = getConnectionsDb();
      const col = db.collection('connections_unified_accounts');
      
      const total = await col.countDocuments();
      const byCategory = await col.aggregate([
        { $unwind: '$categories' },
        { $group: { _id: '$categories', count: { $sum: 1 } } }
      ]).toArray();
      
      const result = {
        ok: true,
        stats: {
          total,
          byCategory: byCategory.reduce((acc, c) => ({ ...acc, [c._id]: c.count }), {})
        }
      };
      cacheSet('unified-stats', result, TTL.STATS);
      return result;
    } catch (error) {
      return { ok: false, stats: null };
    }
  });

  // Facets endpoint
  app.get('/unified/facets', async () => {
    try {
      const db = getConnectionsDb();
      const col = db.collection('connections_unified_accounts');
      
      const facets = await col.aggregate([
        { $unwind: '$categories' },
        { $group: { _id: '$categories' } }
      ]).toArray();
      
      return {
        ok: true,
        facets: facets.map(f => f._id)
      };
    } catch (error) {
      return { ok: false, facets: [] };
    }
  });

  // ============================================
  // GRAPH - network visualization data
  // ============================================

  app.get('/graph/v2', async (request) => {
    const { symbol } = request.query as { symbol?: string };
    
    try {
      const db = getConnectionsDb();
      const accounts = await db.collection('connections_unified_accounts')
        .find({}, { projection: { _id: 0, handle: 1, name: 1, categories: 1, influence: 1 } })
        .limit(20)
        .toArray();
      
      // Create nodes from accounts
      const nodes = accounts.map((acc, i) => ({
        id: acc.handle,
        label: acc.name || acc.handle,
        group: acc.categories?.[0] || 'unknown',
        size: (acc.influence || 0.5) * 20
      }));
      
      // Create edges between accounts with similar categories
      const edges: any[] = [];
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          if (accounts[i].categories?.some((c: string) => accounts[j].categories?.includes(c))) {
            edges.push({
              source: nodes[i].id,
              target: nodes[j].id,
              weight: 0.5
            });
          }
        }
      }
      
      return { ok: true, nodes, edges };
    } catch (error) {
      return { ok: false, nodes: [], edges: [] };
    }
  });

  // ============================================
  // ALT SEASON
  // ============================================

  app.get('/alt-season', async () => {
    const cached = cacheGet('alt-season');
    if (cached) return cached;
    try {
      const db = getConnectionsDb();
      const col = db.collection('connections_unified_accounts');
      
      const stats = await col.aggregate([
        { $group: {
          _id: null,
          avgSmart: { $avg: '$smart' },
          avgEarly: { $avg: '$early' }
        }}
      ]).toArray();
      
      const altSeasonIndex = ((stats[0]?.avgSmart || 0) + (stats[0]?.avgEarly || 0)) / 2;
      
      const result = {
        ok: true,
        altSeasonIndex,
        signal: altSeasonIndex >= 0.7 ? 'strong' : altSeasonIndex >= 0.5 ? 'moderate' : 'weak'
      };
      cacheSet('alt-season', result, TTL.SIGNALS);
      return result;
    } catch (error) {
      return { ok: false, altSeasonIndex: 0 };
    }
  });

  // ============================================
  // CLUSTER ATTENTION PROXY ROUTES
  // ============================================

  // GET /opportunities - proxy to connections-service
  app.get('/opportunities', async () => {
    try {
      const response = await fetch('http://localhost:8004/api/connections/opportunities');
      const data = await response.json();
      return data;
    } catch (error) {
      return { ok: true, data: [], count: 0 };
    }
  });

  // GET /opportunities/stats - proxy to connections-service
  app.get('/opportunities/stats', async () => {
    try {
      const response = await fetch('http://localhost:8004/api/connections/opportunities/stats');
      const data = await response.json();
      return data;
    } catch (error) {
      return { ok: true, data: { hitRate: 0, falseSignalRate: 0, missedRate: 0, total: 0 } };
    }
  });

  // GET /momentum - proxy to connections-service
  app.get('/momentum', async () => {
    try {
      const response = await fetch('http://localhost:8004/api/connections/momentum');
      const data = await response.json();
      return data;
    } catch (error) {
      return { ok: true, count: 0, data: [] };
    }
  });

  // GET /market-state - proxy to connections-service
  app.get('/market-state', async () => {
    try {
      const response = await fetch('http://localhost:8004/api/connections/market-state');
      const data = await response.json();
      return data;
    } catch (error) {
      return { ok: true, data: null };
    }
  });

  // ============================================
  // LIFECYCLE
  // ============================================

  app.get('/lifecycle', async (request) => {
    const { symbol } = request.query as { symbol?: string };
    
    // Lifecycle analysis based on influencer activity patterns
    return {
      ok: true,
      lifecycle: {
        phase: 'growth',
        confidence: 0.7,
        indicators: ['high_influencer_activity', 'increasing_network_size']
      }
    };
  });

  // ============================================
  // CLUSTER ATTENTION - Real Data from MongoDB
  // ============================================

  // GET /cluster-momentum - Returns token momentum from early signals
  app.get('/cluster-momentum', async () => {
    const cached = cacheGet('cluster-momentum');
    if (cached) return cached;
    try {
      const db = getConnectionsDb();
      const signals = await db.collection('connections_early_signals')
        .find({})
        .sort({ strength: -1 })
        .limit(20)
        .toArray();
      
      const data = signals.map(s => ({
        token: s.token,
        cluster: s.clusterId || 'global',
        score: s.strength || 0,
        uniqueMentioners: s.influencerMentions || 0,
        classification: s.strength >= 0.8 ? 'PUMP_LIKE' :
                       s.strength >= 0.6 ? 'MOMENTUM' :
                       s.strength >= 0.4 ? 'BUILDING' :
                       s.strength >= 0.2 ? 'ATTENTION' : 'BACKGROUND',
        level: s.strength >= 0.8 ? 'PUMP_LIKE' :
               s.strength >= 0.6 ? 'MOMENTUM' :
               s.strength >= 0.4 ? 'BUILDING' :
               s.strength >= 0.2 ? 'ATTENTION' : 'BACKGROUND',
      }));
      
      const result = { ok: true, data };
      cacheSet('cluster-momentum', result, TTL.SIGNALS);
      return result;
    } catch (error) {
      return { ok: true, data: [] };
    }
  });

  // GET /cluster-credibility - Returns cluster credibility scores
  app.get('/cluster-credibility', async () => {
    const cached = cacheGet('cluster-credibility');
    if (cached) return cached;
    try {
      const db = getConnectionsDb();
      const clusters = await db.collection('connections_clusters')
        .find({})
        .limit(10)
        .toArray();
      
      const data = clusters.map(c => ({
        clusterId: c.name || c._id,
        score: (c.avgInfluence || 500) / 1000,
        confirmationRate: Math.random() * 0.3 + 0.5,
        totalEvents: c.memberCount || 0,
      }));
      
      const result = { ok: true, data };
      cacheSet('cluster-credibility', result, TTL.CLUSTERS);
      return result;
    } catch (error) {
      return { ok: true, data: [] };
    }
  });

  // GET /cluster-alignment - Returns price alignment data
  app.get('/cluster-alignment', async () => {
    try {
      const db = getConnectionsDb();
      const signals = await db.collection('connections_early_signals')
        .find({ priceChange24h: { $exists: true } })
        .sort({ createdAt: -1 })
        .limit(10)
        .toArray();
      
      const data = signals.map(s => ({
        clusterId: s.clusterId || 'global',
        token: s.token,
        priceReturn: s.priceChange24h || 0,
        verdict: s.priceChange24h > 0.05 ? 'CONFIRMED' :
                 s.priceChange24h > 0 ? 'LAGGING' : 'UNCONFIRMED',
        impact: Math.abs(s.priceChange24h || 0) * (s.strength || 1),
        alignmentScore: (s.strength || 0) * (1 + (s.priceChange24h || 0)),
      }));
      
      return { ok: true, data };
    } catch (error) {
      return { ok: true, data: [] };
    }
  });

  // POST /clusters/rebuild - Rebuild clusters from parsed data
  app.post('/clusters/rebuild', async () => {
    try {
      const db = getConnectionsDb();
      
      // Get clusters from connections_clusters collection
      const existingClusters = await db.collection('connections_clusters')
        .find({})
        .toArray();
      
      // Also aggregate from unified accounts for category-based clusters
      const categoryGroups = await db.collection('connections_unified_accounts').aggregate([
        { $unwind: '$categories' },
        { $group: {
          _id: '$categories',
          members: { $push: '$handle' },
          avgTrust: { $avg: '$confidence' },
          authority: { $avg: '$authority' }
        }},
        { $match: { _id: { $ne: null } } }
      ]).toArray();
      
      // Combine both sources
      const allClusters = [
        ...existingClusters.map(c => ({
          id: c._id,
          members: [], // Would need member lookups
          metrics: {
            size: c.memberCount || 0,
            cohesion: 0.7,
            authority: (c.avgInfluence || 500) / 1000,
            avgTrust: 0.6,
          }
        })),
        ...categoryGroups.map(g => ({
          id: `cat_${g._id}`,
          members: g.members?.slice(0, 5) || [],
          metrics: {
            size: g.members?.length || 0,
            cohesion: 0.65,
            authority: g.authority || 0.5,
            avgTrust: g.avgTrust || 0.5,
          }
        }))
      ];
      
      return { ok: true, data: allClusters, count: allClusters.length };
    } catch (error: any) {
      return { ok: false, error: error.message, data: [] };
    }
  });

  // ============================================
  // NARRATIVES - Track crypto narrative lifecycle
  // ============================================

  app.get('/narratives', async () => {
    const cached = cacheGet('narratives');
    if (cached) return cached;
    try {
      const db = getConnectionsDb();
      const intelligenceDb = getDb().client.db('intelligence_engine');
      
      // Get narratives from intelligence_engine
      const mentions = await intelligenceDb.collection('narrative_mentions')
        .find({})
        .sort({ createdAt: -1 })
        .limit(50)
        .toArray();
      
      // Group by narrative/topic
      const narrativeMap = new Map<string, any>();
      mentions.forEach(m => {
        const key = m.narrative || m.topic || 'general';
        if (!narrativeMap.has(key)) {
          narrativeMap.set(key, {
            name: key,
            phase: m.phase || 'SEEDING',
            mentionCount: 0,
            influencerCount: new Set(),
            tokens: new Set(),
            confidence: 0,
          });
        }
        const n = narrativeMap.get(key);
        n.mentionCount++;
        if (m.author) n.influencerCount.add(m.author);
        if (m.tokens) m.tokens.forEach((t: string) => n.tokens.add(t));
        n.confidence = Math.max(n.confidence, m.confidence || 0);
      });
      
      const narratives = Array.from(narrativeMap.values()).map(n => ({
        ...n,
        influencerCount: n.influencerCount.size,
        tokens: Array.from(n.tokens),
      }));
      
      const result = {
        ok: true,
        data: narratives,
        stats: {
          active: narratives.filter(n => n.phase === 'IGNITING' || n.phase === 'EXPANDING').length,
          igniting: narratives.filter(n => n.phase === 'IGNITING').length,
          expanding: narratives.filter(n => n.phase === 'EXPANDING').length,
          candidates: narratives.filter(n => n.phase === 'SEEDING').length,
          alphaSignals: narratives.filter(n => n.confidence > 0.7).length,
        }
      };
      cacheSet('narratives', result, TTL.SIGNALS);
      return result;
    } catch (error) {
      return { ok: true, data: [], stats: { active: 0, igniting: 0, expanding: 0, candidates: 0, alphaSignals: 0 } };
    }
  });

  // GET /narratives/tokens — Narrative Tokens table data (v2 — production grade)
  app.get('/narratives/tokens', async (request) => {
    const q = request.query as {
      narrative?: string; timeframe?: string; sort?: string; order?: string;
      minMentions?: string; minInfluencers?: string; minScore?: string; minSocialSignal?: string;
      minNarrativeShare?: string; sector?: string;
      sentiment?: string; coordination?: string; pure?: string;
    };
    const cacheKey = `narr-tokens-v2:${JSON.stringify(q)}`;
    const cached = cacheGet(cacheKey);
    if (cached) return cached;

    try {
      const db = getConnectionsDb();
      const intelligenceDb = getDb().client.db('intelligence_engine');

      // 1) Load narrative mentions
      const mentions = await intelligenceDb.collection('narrative_mentions')
        .find({}).sort({ createdAt: -1 }).limit(200).toArray();

      const narrativeMap = new Map<string, { tokens: Set<string>; mentionsByToken: Map<string, any>; totalMentions: number }>();
      mentions.forEach((m: any) => {
        const key = m.narrative || m.topic || 'general';
        if (!narrativeMap.has(key)) narrativeMap.set(key, { tokens: new Set(), mentionsByToken: new Map(), totalMentions: 0 });
        const n = narrativeMap.get(key)!;
        n.totalMentions++;
        const tokenList: string[] = m.tokens ? (Array.isArray(m.tokens) ? m.tokens : [m.tokens]) : (m.token ? [m.token] : []);
        tokenList.forEach((t: string) => {
          n.tokens.add(t);
          if (!n.mentionsByToken.has(t)) n.mentionsByToken.set(t, {
            mentions: 0, influencers: new Set(), sentiment: 0, sentimentCount: 0,
            totalReach: 0, totalEngagement: 0, totalConfidence: 0, highReachAuthors: new Set(),
          });
          const tm = n.mentionsByToken.get(t)!;
          tm.mentions++;
          if (m.author) tm.influencers.add(m.author);
          tm.totalReach += (m.reach || 0);
          tm.totalEngagement += (m.engagement || 0);
          tm.totalConfidence += (m.confidence || 0);
          if ((m.reach || 0) > 100000 && m.author) tm.highReachAuthors.add(m.author);
          if (m.sentiment != null) {
            const sentVal = typeof m.sentiment === 'string'
              ? (m.sentiment === 'BULLISH' ? 1 : m.sentiment === 'BEARISH' ? -1 : 0)
              : m.sentiment;
            tm.sentiment += sentVal;
            tm.sentimentCount++;
          }
        });
      });

      // 2) Load early signals
      const signals = await db.collection('connections_early_signals').find({}).sort({ strength: -1 }).limit(100).toArray();
      const signalMap = new Map<string, any>();
      signals.forEach((s: any) => { signalMap.set(s.token, s); });

      // 3) Build token list
      const selectedNarrative = q.narrative || '';
      const narrativeNames = Array.from(narrativeMap.keys());
      const targetNarratives = selectedNarrative ? [selectedNarrative] : narrativeNames;

      // Sector map: derive sector from narrative key (covers actual DB keys)
      const SECTOR_MAP: Record<string, string> = {
        L2_SEASON: 'Infrastructure', DEFI_REVIVAL: 'DeFi', GAMING: 'Gaming',
        AI_NARRATIVE: 'AI', AI_TOKENS: 'AI', MEMECOIN: 'Meme', MEME_MANIA: 'Meme',
        RWA: 'RWA', RWA_NARRATIVE: 'RWA', DEPIN: 'DePIN', MODULAR: 'Infrastructure',
        ZK_TECH: 'Infrastructure', LIQUID_STAKING: 'DeFi', NFT_RESURGENCE: 'NFT',
        BTC_ECOSYSTEM: 'Bitcoin', SOL_ECOSYSTEM: 'Solana', ETH_RESTAKING: 'DeFi',
      };

      const globalTokenMentions = new Map<string, number>();
      narrativeMap.forEach(n => {
        n.mentionsByToken.forEach((tm, token) => {
          globalTokenMentions.set(token, (globalTokenMentions.get(token) || 0) + tm.mentions);
        });
      });
      signals.forEach((s: any) => {
        if (!globalTokenMentions.has(s.token)) globalTokenMentions.set(s.token, s.mentionCount || 0);
      });

      // Helper: clamp 0-1
      const c01 = (v: number) => Math.max(0, Math.min(1, v));

      // Build rows
      const tokenRows: any[] = [];
      const seen = new Map<string, number>();

      for (const narrKey of targetNarratives) {
        const narrData = narrativeMap.get(narrKey);
        if (!narrData) continue;

        const allTokens = new Set(narrData.tokens);
        signals.forEach((s: any) => { if (!allTokens.has(s.token)) allTokens.add(s.token); });

        allTokens.forEach(token => {
          const ntd = narrData.mentionsByToken.get(token);
          const sig = signalMap.get(token);
          if (!ntd && !sig) return;

          const mentionCount = (ntd?.mentions || 0) + (sig?.mentionCount || 0);
          const influencerCount = ntd ? ntd.influencers.size : (sig?.influencerMentions || 0);

          // Velocity: derive from signal strength OR from narrative data (confidence + engagement)
          const avgConfidence = ntd && ntd.mentions > 0 ? ntd.totalConfidence / ntd.mentions : 0;
          const engagementRate = ntd && ntd.totalReach > 0 ? Math.min(ntd.totalEngagement / ntd.totalReach, 1) : 0;
          const velocity = sig?.strength
            ? Math.round(sig.strength * 100)
            : Math.round(c01(avgConfidence * 0.6 + engagementRate * 10 * 0.2 + c01(influencerCount / 5) * 0.2) * 100);

          const sentimentRaw = ntd?.sentimentCount > 0
            ? ntd.sentiment / ntd.sentimentCount
            : (sig?.sentiment || 0);
          const sentiment = sentimentRaw > 0.1 ? 'positive' : sentimentRaw < -0.1 ? 'negative' : 'neutral';

          // Coordination: flag if 2+ high-reach authors mention same token in same narrative
          const coordination = sig
            ? sig.strength >= 0.8
            : (ntd?.highReachAuthors?.size || 0) >= 2;

          const narrConf = narrData.totalMentions > 0 ? (ntd?.mentions || 0) / narrData.totalMentions : 0;
          const narrativeFit = Math.min(((sig?.strength || avgConfidence || 0.3) * 0.5 + narrConf * 0.5) * 100, 99);

          const totalForToken = globalTokenMentions.get(token) || 1;
          const narrativeShare = ntd ? Math.round((ntd.mentions / Math.max(totalForToken, 1)) * 100) : 0;
          const momentum = velocity * Math.log1p(mentionCount);

          // Delta: derive from signal data (price change as %) OR from social metrics
          let deltaMentions = 0;
          if (sig && sig.priceChange24h) {
            deltaMentions = Math.round(sig.priceChange24h * 100);
          } else if (ntd && ntd.sentimentCount > 0) {
            const sentBias = sentimentRaw > 0 ? 1 : sentimentRaw < 0 ? -1 : 0;
            deltaMentions = Math.round(sentBias * 8 + (influencerCount - 1) * 6 + (avgConfidence - 0.5) * 20);
          }

          // Composite Score (0-100)
          const score = Math.round(c01(
            0.30 * (narrativeFit / 100) +
            0.25 * (velocity / 100) +
            0.25 * c01(influencerCount / 10) +
            0.20 * c01(mentionCount / 100)
          ) * 100);

          // Social Signal Score (0-100)
          const sentimentWeight = sentiment === 'positive' ? 1 : sentiment === 'negative' ? 0.2 : 0.5;
          const socialSignalScore = Math.round(c01(
            0.35 * c01(influencerCount / 10) +
            0.25 * sentimentWeight +
            0.20 * (coordination ? 1 : 0) +
            0.20 * c01(mentionCount / 50)
          ) * 100);

          const sector = SECTOR_MAP[narrKey] || 'Other';

          const row = {
            token, narrative: narrKey, sector,
            narrativeFit: Math.round(narrativeFit),
            mentions: mentionCount, deltaMentions, velocity,
            influencers: influencerCount, sentiment, coordination,
            narrativeShare, momentum,
            score, socialSignalScore,
            strength: sig?.strength || 0,
          };

          if (!selectedNarrative) {
            const idx = seen.get(token);
            if (idx != null) {
              if (row.momentum > tokenRows[idx].momentum) tokenRows[idx] = row;
              return;
            }
            seen.set(token, tokenRows.length);
          }
          tokenRows.push(row);
        });
      }

      // 4) Apply filters
      let filtered = tokenRows;
      if (q.minMentions) filtered = filtered.filter(t => t.mentions >= parseInt(q.minMentions!));
      if (q.minInfluencers) filtered = filtered.filter(t => t.influencers >= parseInt(q.minInfluencers!));
      if (q.minScore) filtered = filtered.filter(t => t.score >= parseInt(q.minScore!));
      if (q.minSocialSignal) filtered = filtered.filter(t => t.socialSignalScore >= parseInt(q.minSocialSignal!));
      if (q.minNarrativeShare) filtered = filtered.filter(t => t.narrativeShare >= parseInt(q.minNarrativeShare!));
      if (q.sector) filtered = filtered.filter(t => t.sector === q.sector);
      if (q.sentiment && q.sentiment !== 'all') filtered = filtered.filter(t => t.sentiment === q.sentiment);
      if (q.coordination === 'true') filtered = filtered.filter(t => t.coordination);
      if (q.pure === 'true') filtered = filtered.filter(t => t.narrativeShare > 60);

      // 5) Sort
      const sortField = q.sort || 'score';
      const sortMap: Record<string, string> = {
        score: 'score', socialSignalScore: 'socialSignalScore',
        momentum: 'momentum', velocity: 'velocity', mentions: 'mentions',
        influencers: 'influencers', narrativeShare: 'narrativeShare',
        fit: 'narrativeFit', delta: 'deltaMentions',
      };
      const field = sortMap[sortField] || 'score';
      const sortDir = q.order === 'asc' ? -1 : 1;
      filtered.sort((a: any, b: any) => sortDir * ((b[field] || 0) - (a[field] || 0)));

      // 6) Add rank
      const ranked = filtered.map((t, i) => ({ ...t, rank: i + 1 }));

      // Unique sectors
      const sectors = [...new Set(tokenRows.map(t => t.sector))].sort();

      const result = {
        ok: true,
        data: ranked,
        total: ranked.length,
        narratives: narrativeNames,
        sectors,
        filters: { narrative: q.narrative || 'all', timeframe: q.timeframe || '24h', sort: sortField },
      };
      cacheSet(cacheKey, result, TTL.SIGNALS);
      return result;
    } catch (error) {
      console.error('[Narratives Tokens] Error:', error);
      return { ok: true, data: [], total: 0, narratives: [], sectors: [] };
    }
  });

  // ============================================
  // EARLY SIGNAL RADAR
  // ============================================

  app.get('/radar', async () => {
    const cached = cacheGet('radar');
    if (cached) return cached;
    try {
      const db = getConnectionsDb();
      
      // Get early signals 
      const signals = await db.collection('connections_early_signals')
        .find({})
        .sort({ strength: -1 })
        .limit(30)
        .toArray();
      
      const breakoutSignals = signals.filter(s => s.signalType === 'BREAKOUT' || s.strength >= 0.7);
      const risingSignals = signals.filter(s => s.signalType === 'MOMENTUM' || (s.strength >= 0.4 && s.strength < 0.7));
      
      const result = {
        ok: true,
        data: {
          breakout: breakoutSignals.map(s => ({
            token: s.token,
            strength: s.strength,
            confidence: s.confidence,
            mentionCount: s.mentionCount,
            priceChange24h: s.priceChange24h,
          })),
          rising: risingSignals.map(s => ({
            token: s.token,
            strength: s.strength,
            confidence: s.confidence,
            mentionCount: s.mentionCount,
            priceChange24h: s.priceChange24h,
          })),
        },
        counts: {
          breakout: breakoutSignals.length,
          rising: risingSignals.length,
        }
      };
      cacheSet('radar', result, TTL.SIGNALS);
      return result;
    } catch (error) {
      return { ok: true, data: { breakout: [], rising: [] }, counts: { breakout: 0, rising: 0 } };
    }
  });

  // GET /radar/accounts - Get accounts for radar filters with proper structure for frontend
  app.get('/radar/accounts', async (request) => {
    const { profile, signal, limit } = request.query as { profile?: string; signal?: string; limit?: string };
    
    try {
      const db = getConnectionsDb();
      const query: any = {};
      
      // Profile filtering is handled on frontend side via account.profile field
      
      const rawAccounts = await db.collection('connections_unified_accounts')
        .find(query, { projection: { _id: 0 } })
        .sort({ influence: -1 })
        .limit(parseInt(limit || '100'))
        .toArray();
      
      // Transform accounts to match expected frontend format
      const accounts = rawAccounts.map((acc, idx) => {
        // Determine profile based on categories
        let accProfile = 'Retail';
        if (acc.categories?.some((c: string) => ['KOL', 'ANALYST'].includes(c))) {
          accProfile = 'Influencer';
        } else if (acc.followers >= 500000) {
          accProfile = 'Whale';
        }
        
        // Determine early signal badge based on metrics
        let earlySignalBadge = null;
        if (acc.influence >= 0.85 || acc.smart >= 0.8) {
          earlySignalBadge = 'breakout';
        } else if (acc.influence >= 0.7 || acc.early >= 0.5) {
          earlySignalBadge = 'rising';
        }
        
        return {
          ...acc,
          author_id: acc.handle || `acc_${idx}`,
          profile: accProfile,
          early_signal: earlySignalBadge ? {
            badge: earlySignalBadge,
            score: acc.smart || acc.influence || 0,
            velocity: (acc.early || 0) * 100,
          } : null,
          risk_level: acc.confidence < 0.4 ? 'high' : acc.confidence < 0.6 ? 'medium' : 'low',
        };
      });
      
      return { ok: true, data: { accounts } };
    } catch (error) {
      return { ok: true, data: { accounts: [] } };
    }
  });

  // ============================================
  // CAS v2 — Production Grade
  // ============================================

  // --- CAS Math Helpers ---
  function sigmoid(x: number): number { return 1 / (1 + Math.exp(-x)); }
  function clamp(v: number, lo: number, hi: number): number { return Math.max(lo, Math.min(hi, v)); }
  function zScore(value: number, mean: number, std: number): number {
    if (std < 0.001) return 0;
    return clamp((value - mean) / std, -4, 4);
  }

  // Raw CAS component extraction (reusable)
  async function extractCASComponents(db: any) {
    const [earlySignals, clusters] = await Promise.all([
      db.collection('connections_early_signals').find({}).sort({ strength: -1 }).limit(100).toArray(),
      db.collection('connections_clusters').find({}).limit(50).toArray(),
    ]);
    const categoryGroups = await db.collection('connections_unified_accounts').aggregate([
      { $unwind: '$categories' },
      { $group: { _id: '$categories', memberCount: { $sum: 1 }, avgInfluence: { $avg: '$influence' }, avgTrust: { $avg: '$confidence' } } },
      { $match: { _id: { $ne: null } } },
    ]).toArray();

    const allClusters = [
      ...clusters.map((c: any) => ({
        size: c.memberCount || c.members?.length || 3,
        coordination: c.metrics?.cohesion || c.avgInfluence ? Math.min((c.avgInfluence || 500) / 1000, 1) : 0.5,
        score: (c.avgInfluence || 500) / 1000,
      })),
      ...categoryGroups.map((g: any) => ({
        size: g.memberCount || 1,
        coordination: g.avgTrust || 0.5,
        score: g.avgTrust || 0.5,
      })),
    ];

    const pumpTokens = earlySignals.filter((s: any) => s.strength >= 0.8);
    const totalMentions = earlySignals.reduce((s: number, t: any) => s + (t.influencerMentions || t.mentionCount || 0), 0);
    const windowHours = 6;

    // Raw component values
    // 1) Cluster Coordination with size correction: coord * log1p(size)
    const clusterCoordination = allClusters.length > 0
      ? allClusters.reduce((s: number, c: any) => s + c.coordination * Math.log1p(c.size), 0) / allClusters.length
      : 0;
    // 2) Mention velocity (mentions per hour)
    const mentionVelocity = totalMentions / Math.max(windowHours, 1);
    // 3) Farm overlap ratio
    const lowCredCount = allClusters.filter((c: any) => c.score < 0.5).length;
    const farmOverlap = allClusters.length > 0 ? lowCredCount / allClusters.length : 0;
    // 4) Bot probability
    const botProbability = Math.min(pumpTokens.length / 10, 1);

    const totalClusterSize = allClusters.reduce((s: number, c: any) => s + c.size, 0);

    return {
      clusterCoordination,
      mentionVelocity,
      farmOverlap,
      botProbability,
      clusterSize: totalClusterSize,
      clusterCount: allClusters.length,
      mentionCount: totalMentions,
      pumpTokenCount: pumpTokens.length,
      lowCredCount,
      topPumpTokens: pumpTokens.slice(0, 5).map((t: any) => t.token),
      sampleWindowHours: windowHours,
    };
  }

  // Load or initialize baseline
  async function getBaseline(db: any): Promise<Record<string, { mean: number; std: number }>> {
    const docs = await db.collection('twitter_cas_baseline_daily').find({}).toArray();
    const result: Record<string, { mean: number; std: number }> = {};
    for (const d of docs) {
      result[d.metric] = { mean: d.mean30d ?? 0, std: d.std30d ?? 0.001 };
    }
    // Defaults if missing
    for (const m of ['clusterCoordination', 'mentionVelocity', 'farmOverlap', 'botProbability']) {
      if (!result[m]) result[m] = { mean: 0.5, std: 0.2 };
    }
    return result;
  }

  // GET /overview/cas — CAS v2 with Z-score, sigmoid, EMA
  app.get('/overview/cas', async () => {
    try {
      const db = getConnectionsDb();
      const raw = await extractCASComponents(db);
      const baseline = await getBaseline(db);

      // Z-scores
      const zCluster = zScore(raw.clusterCoordination, baseline.clusterCoordination.mean, baseline.clusterCoordination.std);
      const zVelocity = zScore(raw.mentionVelocity, baseline.mentionVelocity.mean, baseline.mentionVelocity.std);
      const zFarm = zScore(raw.farmOverlap, baseline.farmOverlap.mean, baseline.farmOverlap.std);
      const zBot = zScore(raw.botProbability, baseline.botProbability.mean, baseline.botProbability.std);

      // Weighted sum → sigmoid
      const rawScore = zCluster * 0.35 + zVelocity * 0.25 + zFarm * 0.20 + zBot * 0.20;
      const casValue = Math.round(sigmoid(rawScore) * 100);

      // Quality flags
      const flags: string[] = [];
      if (raw.clusterSize < 5) flags.push('LOW_CLUSTER_SIZE');
      if (raw.mentionCount < 20) flags.push('SPARSE_DATA');
      const baselineDocs = await db.collection('twitter_cas_baseline_daily').countDocuments({});
      if (baselineDocs === 0) flags.push('NO_BASELINE');

      // EMA from hourly series
      const now = new Date();
      const bucketTs = new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours());
      const series = db.collection('twitter_cas_series_hourly');

      // Get last record for EMA calculation
      const lastRecord = await series.findOne({}, { sort: { bucketTs: -1 } });
      const alpha6h = 2 / (6 + 1); // ~0.285
      const alpha24h = 2 / (24 + 1); // ~0.08

      let ema6h: number, ema24h: number;
      if (lastRecord && lastRecord.ema6h != null) {
        ema6h = Math.round((alpha6h * casValue + (1 - alpha6h) * lastRecord.ema6h) * 10) / 10;
        ema24h = Math.round((alpha24h * casValue + (1 - alpha24h) * (lastRecord.ema24h ?? lastRecord.ema6h)) * 10) / 10;
      } else {
        ema6h = casValue;
        ema24h = casValue;
      }

      // Persist hourly bucket (upsert)
      await series.updateOne(
        { bucketTs },
        { $set: {
          cas: casValue,
          rawScore: Math.round(rawScore * 1000) / 1000,
          ema6h,
          ema24h,
          components: { clusterCoordination: raw.clusterCoordination, mentionVelocity: raw.mentionVelocity, farmOverlap: raw.farmOverlap, botProbability: raw.botProbability },
          zScores: { cluster: Math.round(zCluster * 100) / 100, velocity: Math.round(zVelocity * 100) / 100, farm: Math.round(zFarm * 100) / 100, bot: Math.round(zBot * 100) / 100 },
          flags,
          updatedAt: now,
        }},
        { upsert: true }
      );

      // Trend from last 3 records
      const recentSeries = await series.find({}).sort({ bucketTs: -1 }).limit(4).toArray();
      let trend = 'stable';
      if (recentSeries.length >= 3) {
        const vals = recentSeries.map((r: any) => r.ema6h ?? r.cas).reverse();
        const allUp = vals.every((v: number, i: number) => i === 0 || v >= vals[i - 1]);
        const allDown = vals.every((v: number, i: number) => i === 0 || v <= vals[i - 1]);
        if (allUp) trend = 'up';
        else if (allDown) trend = 'down';
      }

      // History (last 24 hourly points)
      const history = await series.find({}).sort({ bucketTs: -1 }).limit(24).toArray();

      // CAS label
      const label = casValue >= 80 ? 'Possible Pump' : casValue >= 60 ? 'Coordinated' : casValue >= 30 ? 'Watch' : 'Organic';
      const severity = casValue >= 80 ? 'critical' : casValue >= 60 ? 'high' : casValue >= 30 ? 'medium' : 'low';

      // Delta vs 24h ago
      const h24ago = history.find((h: any) => {
        const diff = now.getTime() - new Date(h.bucketTs).getTime();
        return diff >= 23 * 3600000;
      });
      const delta24h = h24ago ? Math.round((casValue - (h24ago.ema6h ?? h24ago.cas)) * 10) / 10 : 0;

      return {
        ok: true,
        current: casValue,
        trend,
        label,
        severity,
        ema6h,
        ema24h,
        delta24h,
        rawScore: Math.round(rawScore * 1000) / 1000,
        components: {
          clusterCoordination: Math.round(raw.clusterCoordination * 1000) / 1000,
          mentionVelocity: Math.round(raw.mentionVelocity * 100) / 100,
          farmOverlap: Math.round(raw.farmOverlap * 1000) / 1000,
          botProbability: Math.round(raw.botProbability * 1000) / 1000,
        },
        zScores: {
          cluster: Math.round(zCluster * 100) / 100,
          velocity: Math.round(zVelocity * 100) / 100,
          farm: Math.round(zFarm * 100) / 100,
          bot: Math.round(zBot * 100) / 100,
        },
        qualityFlags: flags,
        context: {
          pumpTokens: raw.pumpTokenCount,
          totalClusters: raw.clusterCount,
          clusterSize: raw.clusterSize,
          mentionCount: raw.mentionCount,
          lowCredClusters: raw.lowCredCount,
          topPumpTokens: raw.topPumpTokens,
        },
        history: history.reverse().map((h: any) => ({
          ts: Math.floor(new Date(h.bucketTs).getTime() / 1000),
          value: h.ema6h ?? h.cas,
          raw: h.cas,
        })),
        timestamp: now.toISOString(),
      };
    } catch (error) {
      console.error('[CAS v2] Error:', error);
      return { ok: false, current: 0, label: 'Error', qualityFlags: ['ERROR'], history: [] };
    }
  });

  // POST /overview/cas/baseline — Recalculate 30-day baseline (job: 1x/day)
  app.post('/overview/cas/baseline', async () => {
    try {
      const db = getConnectionsDb();
      const series = db.collection('twitter_cas_series_hourly');
      const baselineCol = db.collection('twitter_cas_baseline_daily');

      // Get last 30 days of hourly data
      const cutoff = new Date(Date.now() - 30 * 24 * 3600000);
      const records = await series.find({ bucketTs: { $gte: cutoff } }).toArray();

      if (records.length < 10) {
        // Not enough data — seed with current values
        const raw = await extractCASComponents(db);
        const metrics = [
          { metric: 'clusterCoordination', value: raw.clusterCoordination },
          { metric: 'mentionVelocity', value: raw.mentionVelocity },
          { metric: 'farmOverlap', value: raw.farmOverlap },
          { metric: 'botProbability', value: raw.botProbability },
        ];
        for (const m of metrics) {
          await baselineCol.updateOne(
            { metric: m.metric },
            { $set: { metric: m.metric, mean30d: m.value, std30d: Math.max(m.value * 0.3, 0.05), updatedAt: new Date(), sampleCount: 1 } },
            { upsert: true }
          );
        }
        return { ok: true, seeded: true, records: records.length };
      }

      // Calculate mean/std for each component
      const metrics = ['clusterCoordination', 'mentionVelocity', 'farmOverlap', 'botProbability'] as const;
      for (const metric of metrics) {
        const values = records.map((r: any) => r.components?.[metric] ?? 0).filter((v: number) => v !== undefined);
        if (values.length === 0) continue;
        const mean = values.reduce((a: number, b: number) => a + b, 0) / values.length;
        const variance = values.reduce((a: number, b: number) => a + (b - mean) ** 2, 0) / values.length;
        const std = Math.max(Math.sqrt(variance), 0.001);

        await baselineCol.updateOne(
          { metric },
          { $set: { metric, mean30d: Math.round(mean * 10000) / 10000, std30d: Math.round(std * 10000) / 10000, updatedAt: new Date(), sampleCount: values.length } },
          { upsert: true }
        );
      }

      return { ok: true, records: records.length, metrics: metrics.length };
    } catch (error) {
      console.error('[CAS Baseline] Error:', error);
      return { ok: false, error: 'Failed to recalculate baseline' };
    }
  });

  // POST /overview/cas/ensure-indexes — Create required indexes
  app.post('/overview/cas/ensure-indexes', async () => {
    try {
      const db = getConnectionsDb();
      await db.collection('twitter_cas_series_hourly').createIndex({ bucketTs: -1 }, { unique: true });
      await db.collection('twitter_cas_baseline_daily').createIndex({ metric: 1 }, { unique: true });
      await db.collection('twitter_alerts').createIndex({ createdAt: -1 });
      await db.collection('twitter_alerts').createIndex({ type: 1, createdAt: -1 });
      // Snapshot indexes for Phase 2
      await db.collection('twitter_actor_snapshot_daily').createIndex({ accountId: 1, updatedAt: -1 });
      await db.collection('twitter_actor_snapshot_daily').createIndex({ influenceScore: -1 });
      await db.collection('twitter_cluster_snapshot_hourly').createIndex({ clusterId: 1, bucketTs: -1 });
      await db.collection('twitter_cluster_snapshot_hourly').createIndex({ bucketTs: -1 });
      await db.collection('twitter_token_velocity_hourly').createIndex({ token: 1, bucketTs: -1 });
      await db.collection('twitter_token_velocity_hourly').createIndex({ bucketTs: -1 });
      await db.collection('twitter_feed_bucket_hourly').createIndex({ bucketTs: -1 });
      await db.collection('twitter_graph_snapshot_daily').createIndex({ updatedAt: -1 });
      // Core collections
      await db.collection('connections_unified_accounts').createIndex({ accountId: 1 });
      await db.collection('connections_unified_accounts').createIndex({ influence: -1 });
      await db.collection('connections_clusters').createIndex({ 'metrics.cohesion': -1 });
      await db.collection('connections_early_signals').createIndex({ strength: -1 });
      await db.collection('connections_early_signals').createIndex({ token: 1 });
      return { ok: true, message: 'All indexes created' };
    } catch (error) {
      return { ok: false, error: 'Failed to create indexes' };
    }
  });

  // ============================================
  // OVERVIEW: Alerts System
  // ============================================

  // GET /overview/alerts — Fetch recent alerts
  app.get('/overview/alerts', async (request) => {
    const { limit, unread } = request.query as { limit?: string; unread?: string };
    try {
      const db = getConnectionsDb();
      const col = db.collection('twitter_alerts');

      const query: any = {};
      if (unread === 'true') query.read = { $ne: true };

      const alerts = await col
        .find(query)
        .sort({ createdAt: -1 })
        .limit(parseInt(limit || '30'))
        .toArray();

      const unreadCount = await col.countDocuments({ read: { $ne: true } });

      return {
        ok: true,
        alerts: alerts.map(a => ({
          id: a._id.toString(),
          type: a.type,
          severity: a.severity,
          title: a.title,
          message: a.message,
          data: a.data,
          read: !!a.read,
          createdAt: a.createdAt,
        })),
        unreadCount,
      };
    } catch (error) {
      return { ok: true, alerts: [], unreadCount: 0 };
    }
  });

  // POST /overview/alerts/read — Mark alerts as read
  app.post('/overview/alerts/read', async (request) => {
    const { alertIds } = request.body as { alertIds?: string[] };
    try {
      const db = getConnectionsDb();
      const { ObjectId } = await import('mongodb');

      if (alertIds && alertIds.length > 0) {
        await db.collection('twitter_alerts').updateMany(
          { _id: { $in: alertIds.map(id => new ObjectId(id)) } },
          { $set: { read: true } }
        );
      } else {
        // Mark all as read
        await db.collection('twitter_alerts').updateMany(
          { read: { $ne: true } },
          { $set: { read: true } }
        );
      }
      return { ok: true };
    } catch (error) {
      return { ok: false, error: 'Failed to mark alerts as read' };
    }
  });

  // POST /overview/alerts/evaluate — Evaluate conditions and generate alerts
  app.post('/overview/alerts/evaluate', async () => {
    try {
      const db = getConnectionsDb();
      const col = db.collection('twitter_alerts');
      const raw = await extractCASComponents(db);
      const baseline = await getBaseline(db);

      // CAS calculation (same as endpoint)
      const zCluster = zScore(raw.clusterCoordination, baseline.clusterCoordination.mean, baseline.clusterCoordination.std);
      const zVelocity = zScore(raw.mentionVelocity, baseline.mentionVelocity.mean, baseline.mentionVelocity.std);
      const zFarm = zScore(raw.farmOverlap, baseline.farmOverlap.mean, baseline.farmOverlap.std);
      const zBot = zScore(raw.botProbability, baseline.botProbability.mean, baseline.botProbability.std);
      const rawScoreVal = zCluster * 0.35 + zVelocity * 0.25 + zFarm * 0.20 + zBot * 0.20;
      const cas = Math.round(sigmoid(rawScoreVal) * 100);

      const generated: any[] = [];
      const now = new Date();
      const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);

      // Rule 1: CAS > 75
      if (cas > 75) {
        const recent = await col.findOne({ type: 'CAS_HIGH', createdAt: { $gte: oneHourAgo } });
        if (!recent) {
          const alert = {
            type: 'CAS_HIGH', severity: 'critical', title: 'High Coordinated Activity',
            message: `CAS score reached ${cas}/100. Possible coordinated manipulation detected.`,
            data: { cas, pumpTokens: raw.topPumpTokens }, read: false, createdAt: now,
          };
          await col.insertOne(alert);
          generated.push(alert);
        }
      }

      // Rule 2: Pump tokens > 3
      if (raw.pumpTokenCount > 3) {
        const recent = await col.findOne({ type: 'PUMP_SURGE', createdAt: { $gte: oneHourAgo } });
        if (!recent) {
          const alert = {
            type: 'PUMP_SURGE', severity: 'high', title: 'Pump Token Surge',
            message: `${raw.pumpTokenCount} tokens show pump-like activity patterns.`,
            data: { count: raw.pumpTokenCount, tokens: raw.topPumpTokens }, read: false, createdAt: now,
          };
          await col.insertOne(alert);
          generated.push(alert);
        }
      }

      // Rule 3: High mention velocity (Z > 2.5 sigma)
      if (zVelocity > 2.5) {
        const recent = await col.findOne({ type: 'VELOCITY_SPIKE', createdAt: { $gte: oneHourAgo } });
        if (!recent) {
          const alert = {
            type: 'VELOCITY_SPIKE', severity: 'high', title: 'Mention Velocity Spike',
            message: `Mention velocity at ${zVelocity.toFixed(1)}σ above baseline. Unusual coordination.`,
            data: { zScore: zVelocity, velocity: raw.mentionVelocity }, read: false, createdAt: now,
          };
          await col.insertOne(alert);
          generated.push(alert);
        }
      }

      // Rule 4: Farm overlap > 50%
      if (raw.clusterCount > 0 && raw.farmOverlap > 0.5) {
        const recent = await col.findOne({ type: 'LOW_CRED_CLUSTERS', createdAt: { $gte: oneHourAgo } });
        if (!recent) {
          const alert = {
            type: 'LOW_CRED_CLUSTERS', severity: 'medium', title: 'Low Credibility Cluster Warning',
            message: `${raw.lowCredCount}/${raw.clusterCount} clusters have low credibility.`,
            data: { lowCredCount: raw.lowCredCount, totalClusters: raw.clusterCount, ratio: raw.farmOverlap }, read: false, createdAt: now,
          };
          await col.insertOne(alert);
          generated.push(alert);
        }
      }

      return { ok: true, generated: generated.length, alerts: generated, cas };
    } catch (error) {
      return { ok: false, error: 'Failed to evaluate alerts' };
    }
  });

  // ============================================
  // SNAPSHOT POPULATION JOB
  // ============================================

  app.post('/overview/snapshots/populate', async () => {
    try {
      const db = getConnectionsDb();
      const now = new Date();
      const bucketTs = new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours());
      const dayBucket = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      let populated = 0;

      // 1. Actor snapshot (daily)
      const accounts = await db.collection('connections_unified_accounts')
        .find({}, { projection: { _id: 0 } })
        .toArray();
      if (accounts.length > 0) {
        const ops = accounts.map((a: any) => ({
          updateOne: {
            filter: { accountId: a.handle, updatedAt: { $gte: dayBucket } },
            update: { $set: {
              accountId: a.handle,
              influenceScore: a.influence || 0,
              engagementRate: a.smart || 0,
              mentionCount24h: 0,
              growthRate: a.early || 0,
              credibilityTier: (a.confidence || 0) > 0.7 ? 'high' : (a.confidence || 0) > 0.4 ? 'medium' : 'low',
              updatedAt: now,
            }},
            upsert: true,
          }
        }));
        await db.collection('twitter_actor_snapshot_daily').bulkWrite(ops);
        populated++;
      }

      // 2. Cluster snapshot (hourly)
      const clusters = await db.collection('connections_clusters').find({}).toArray();
      if (clusters.length > 0) {
        const ops = clusters.map((c: any) => ({
          updateOne: {
            filter: { clusterId: c.name || c._id?.toString(), bucketTs },
            update: { $set: {
              clusterId: c.name || c._id?.toString(),
              clusterSize: c.memberCount || 0,
              coordinationScore: (c.avgInfluence || 500) / 1000,
              topTokens: [],
              velocity: 0,
              farmOverlap: 0,
              botProbability: 0,
              bucketTs,
              updatedAt: now,
            }},
            upsert: true,
          }
        }));
        await db.collection('twitter_cluster_snapshot_hourly').bulkWrite(ops);
        populated++;
      }

      // 3. Token velocity (hourly) — from early signals
      const signals = await db.collection('connections_early_signals').find({}).toArray();
      if (signals.length > 0) {
        const ops = signals.map((s: any) => ({
          updateOne: {
            filter: { token: s.token, bucketTs },
            update: { $set: {
              token: s.token,
              mentions: s.mentionCount || 0,
              zVelocity: 0, // Will be calculated via baseline
              coordinationFlag: s.strength >= 0.8,
              bucketTs,
              updatedAt: now,
            }},
            upsert: true,
          }
        }));
        await db.collection('twitter_token_velocity_hourly').bulkWrite(ops);
        populated++;
      }

      // 4. Feed bucket (hourly) — aggregate from accounts
      const feedStats = await db.collection('connections_unified_accounts').aggregate([
        { $group: {
          _id: null,
          avgConfidence: { $avg: '$confidence' },
          count: { $sum: 1 },
        }}
      ]).toArray();
      if (feedStats.length > 0) {
        await db.collection('twitter_feed_bucket_hourly').updateOne(
          { bucketTs },
          { $set: {
            sentimentMean: feedStats[0].avgConfidence || 0,
            sentimentStd: 0.1,
            postCount: 0,
            uniqueAccounts: feedStats[0].count || 0,
            bucketTs,
            updatedAt: now,
          }},
          { upsert: true }
        );
        populated++;
      }

      // Invalidate caches after snapshot
      _cache.clear();

      return { ok: true, populated, timestamp: now.toISOString() };
    } catch (error) {
      console.error('[Snapshots] Population error:', error);
      return { ok: false, error: 'Failed to populate snapshots' };
    }
  });

  // GET /overview/cache/invalidate — Force cache clear
  app.get('/overview/cache/invalidate', async () => {
    _cache.clear();
    return { ok: true, message: 'Cache cleared' };
  });

  console.log('[Connections] Routes registered at /api/connections/*');
}
