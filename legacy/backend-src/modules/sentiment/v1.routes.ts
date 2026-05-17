/**
 * Universal Sentiment API — v1
 * ============================
 * Clean, versioned, standalone internal API.
 * Prefix: /api/v1/sentiment
 *
 * Endpoints:
 *   POST /api/v1/sentiment/analyze    — single text analysis (with cache)
 *   POST /api/v1/sentiment/batch      — batch analysis (up to 100 items)
 *   POST /api/v1/sentiment/normalize  — text cleanup + tokenization + language detection
 *   GET  /api/v1/sentiment/health     — engine health / readiness
 *   GET  /api/v1/sentiment/capabilities — engine metadata
 */

import { createHash } from 'crypto';
import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import {
  analyze,
  analyzeBatch,
  normalize,
  getCapabilities,
  ENGINE_VERSION,
  type SentimentResult,
  type SentimentSource,
} from './sentiment.engine.js';
import {
  validateApiKey,
  generateApiKey,
  listApiKeys,
  revokeApiKey,
  deleteApiKey,
} from './api-keys.js';

const PREFIX = '/api/v1/sentiment';
const MAX_TEXT = 10000;
const MAX_BATCH = 100;
const startedAt = new Date().toISOString();

// ── Cache (in-memory, SHA256 → result, TTL 24h) ─────────

const CACHE_TTL_MS = 24 * 60 * 60 * 1000; // 24 hours
const CACHE_MAX_SIZE = 10000;

interface CacheEntry {
  result: SentimentResult;
  expiresAt: number;
}

const cache = new Map<string, CacheEntry>();

function cacheKey(text: string): string {
  return createHash('sha256').update(text).digest('hex');
}

function cacheGet(text: string): SentimentResult | null {
  const key = cacheKey(text);
  const entry = cache.get(key);
  if (!entry) return null;
  if (Date.now() > entry.expiresAt) {
    cache.delete(key);
    return null;
  }
  return entry.result;
}

function cacheSet(text: string, result: SentimentResult): void {
  if (cache.size >= CACHE_MAX_SIZE) {
    // Evict oldest 10%
    const keys = [...cache.keys()];
    for (let i = 0; i < keys.length * 0.1; i++) {
      cache.delete(keys[i]);
    }
  }
  cache.set(cacheKey(text), { result, expiresAt: Date.now() + CACHE_TTL_MS });
}

// Periodic cleanup every 10 minutes
setInterval(() => {
  const now = Date.now();
  for (const [key, entry] of cache) {
    if (now > entry.expiresAt) cache.delete(key);
  }
}, 10 * 60 * 1000);

// ── Rate Limiter (1000 req/min per service, sliding window) ──

const RATE_LIMIT = 1000;
const RATE_WINDOW_MS = 60 * 1000;

const rateBuckets = new Map<string, number[]>();

function checkRateLimit(clientId: string): { allowed: boolean; remaining: number } {
  const now = Date.now();
  const windowStart = now - RATE_WINDOW_MS;

  let timestamps = rateBuckets.get(clientId) || [];
  timestamps = timestamps.filter(t => t > windowStart);

  if (timestamps.length >= RATE_LIMIT) {
    rateBuckets.set(clientId, timestamps);
    return { allowed: false, remaining: 0 };
  }

  timestamps.push(now);
  rateBuckets.set(clientId, timestamps);
  return { allowed: true, remaining: RATE_LIMIT - timestamps.length };
}

// Cleanup buckets every 2 minutes
setInterval(() => {
  const cutoff = Date.now() - RATE_WINDOW_MS;
  for (const [key, timestamps] of rateBuckets) {
    const filtered = timestamps.filter(t => t > cutoff);
    if (filtered.length === 0) rateBuckets.delete(key);
    else rateBuckets.set(key, filtered);
  }
}, 2 * 60 * 1000);

// ── Metrics (internal observability) ─────────────────────

const metrics = {
  requests: { analyze: 0, batch: 0, normalize: 0, health: 0, capabilities: 0 },
  errors: 0,
  cacheHits: 0,
  cacheMisses: 0,
  totalLatencyMs: 0,
  labelCounts: { POSITIVE: 0, NEUTRAL: 0, NEGATIVE: 0 } as Record<string, number>,
  sourceCounts: {} as Record<string, number>,
  startedAt: Date.now(),
};

function trackSource(source: string) {
  metrics.sourceCounts[source] = (metrics.sourceCounts[source] || 0) + 1;
}

// ── Helpers ──────────────────────────────────────────────

function getClientId(req: FastifyRequest): string {
  return (req.headers['x-service-id'] as string) || req.ip || 'default';
}

const VALID_SOURCES: SentimentSource[] = ['twitter', 'news', 'telegram', 'article', 'headline', 'user'];

function parseSource(raw?: string): SentimentSource {
  if (!raw) return 'unknown';
  return VALID_SOURCES.includes(raw as SentimentSource) ? (raw as SentimentSource) : 'unknown';
}

// ── Routes ───────────────────────────────────────────────

// Endpoints that don't require API key auth
const PUBLIC_SUFFIXES = ['/health', '/capabilities', '/keys', '/metrics', '/sdk/typescript', '/sdk/python', '/sdk/docs', '/sdk/zip', '/config'];

function extractApiKey(req: FastifyRequest): string | null {
  const auth = req.headers['authorization'];
  if (auth?.startsWith('Bearer ')) return auth.slice(7);
  const xKey = req.headers['x-api-key'] as string;
  if (xKey) return xKey;
  return null;
}

export async function registerSentimentV1Routes(app: FastifyInstance) {

  // Rate limit hook for all sentiment v1 routes
  app.addHook('onRequest', async (req: FastifyRequest, reply: FastifyReply) => {
    if (!req.url.startsWith(PREFIX)) return;

    const clientId = getClientId(req);
    const { allowed, remaining } = checkRateLimit(clientId);

    reply.header('X-RateLimit-Limit', RATE_LIMIT);
    reply.header('X-RateLimit-Remaining', remaining);

    if (!allowed) {
      return reply.status(429).send({
        ok: false,
        error: 'RATE_LIMIT_EXCEEDED',
        message: `Rate limit of ${RATE_LIMIT} requests per minute exceeded`,
      });
    }
  });

  // API key auth hook — protects analyze/batch/normalize, allows health/capabilities/keys
  app.addHook('onRequest', async (req: FastifyRequest, reply: FastifyReply) => {
    if (!req.url.startsWith(PREFIX)) return;

    // Public endpoints — no key needed
    const path = req.url.split('?')[0];
    if (PUBLIC_SUFFIXES.some(s => path.endsWith(s))) return;

    // Internal requests (from same server) — no key needed
    const isInternal = req.headers['x-internal-service'];
    if (isInternal) return;

    const apiKey = extractApiKey(req);
    if (!apiKey) {
      return reply.status(401).send({
        ok: false,
        error: 'UNAUTHORIZED',
        message: 'API key required. Use header: Authorization: Bearer <key> or X-API-Key: <key>',
      });
    }

    const valid = await validateApiKey(apiKey);
    if (!valid) {
      return reply.status(403).send({
        ok: false,
        error: 'FORBIDDEN',
        message: 'Invalid or revoked API key',
      });
    }
  });

  // ── Health ──────────────────────────────────────────────
  app.get(`${PREFIX}/health`, async (_req: FastifyRequest, reply: FastifyReply) => {
    metrics.requests.health++;
    return reply.send({
      ok: true,
      data: {
        status: 'READY',
        engineVersion: ENGINE_VERSION,
        uptime: process.uptime(),
        startedAt,
        cache: {
          size: cache.size,
          maxSize: CACHE_MAX_SIZE,
          ttlHours: CACHE_TTL_MS / 3600000,
        },
      },
    });
  });

  // ── Capabilities ────────────────────────────────────────
  app.get(`${PREFIX}/capabilities`, async (_req: FastifyRequest, reply: FastifyReply) => {
    metrics.requests.capabilities++;
    return reply.send({
      ok: true,
      data: getCapabilities(),
    });
  });

  // ── Single Analyze (with cache) ─────────────────────────
  app.post(
    `${PREFIX}/analyze`,
    async (req: FastifyRequest<{ Body: { text: string; source?: string } }>, reply: FastifyReply) => {
      const { text, source: rawSource } = req.body ?? {};

      if (!text || typeof text !== 'string') {
        return reply.status(400).send({
          ok: false,
          error: 'INVALID_INPUT',
          message: 'Field "text" is required and must be a string',
        });
      }

      if (text.length > MAX_TEXT) {
        return reply.status(400).send({
          ok: false,
          error: 'TEXT_TOO_LONG',
          message: `Text must be under ${MAX_TEXT} characters`,
        });
      }

      const source = parseSource(rawSource);

      // Cache lookup
      const cached = cacheGet(text);
      if (cached) {
        metrics.requests.analyze++;
        metrics.cacheHits++;
        metrics.labelCounts[cached.label] = (metrics.labelCounts[cached.label] || 0) + 1;
        trackSource(source);
        return reply.send({
          ok: true,
          data: { ...cached, source, meta: { ...cached.meta, cached: true } },
        });
      }

      const result = analyze(text, source);
      cacheSet(text, result);
      metrics.requests.analyze++;
      metrics.cacheMisses++;
      metrics.totalLatencyMs += result.meta.processingTimeMs;
      metrics.labelCounts[result.label] = (metrics.labelCounts[result.label] || 0) + 1;
      trackSource(source);
      return reply.send({ ok: true, data: result });
    },
  );

  // ── Batch ───────────────────────────────────────────────
  app.post(
    `${PREFIX}/batch`,
    async (
      req: FastifyRequest<{ Body: { items: Array<{ id: string; text: string; source?: string }>; source?: string } }>,
      reply: FastifyReply,
    ) => {
      const { items, source: batchSource } = req.body ?? {};

      if (!items || !Array.isArray(items)) {
        return reply.status(400).send({
          ok: false,
          error: 'INVALID_INPUT',
          message: 'Field "items" is required and must be an array',
        });
      }

      if (items.length === 0) {
        return reply.status(400).send({
          ok: false,
          error: 'EMPTY_BATCH',
          message: 'Items array must not be empty',
        });
      }

      if (items.length > MAX_BATCH) {
        return reply.status(400).send({
          ok: false,
          error: 'BATCH_TOO_LARGE',
          message: `Maximum ${MAX_BATCH} items per batch`,
        });
      }

      for (let i = 0; i < items.length; i++) {
        if (!items[i].id) {
          return reply.status(400).send({
            ok: false,
            error: 'INVALID_ITEM',
            message: `Item at index ${i} is missing "id"`,
          });
        }
      }

      const defaultSource = parseSource(batchSource);
      const result = analyzeBatch(
        items.map(it => ({ ...it, source: it.source ? parseSource(it.source) : defaultSource })),
        defaultSource,
      );
      metrics.requests.batch++;
      metrics.totalLatencyMs += result.meta.processingTimeMs;
      for (const r of result.results) {
        if (r.result) {
          metrics.labelCounts[r.result.label] = (metrics.labelCounts[r.result.label] || 0) + 1;
          trackSource(r.result.source);
        }
      }
      return reply.send({ ok: true, data: result });
    },
  );

  // ── Normalize ───────────────────────────────────────────
  app.post(
    `${PREFIX}/normalize`,
    async (req: FastifyRequest<{ Body: { text: string } }>, reply: FastifyReply) => {
      const { text } = req.body ?? {};

      if (!text || typeof text !== 'string') {
        return reply.status(400).send({
          ok: false,
          error: 'INVALID_INPUT',
          message: 'Field "text" is required and must be a string',
        });
      }

      if (text.length > MAX_TEXT) {
        return reply.status(400).send({
          ok: false,
          error: 'TEXT_TOO_LONG',
          message: `Text must be under ${MAX_TEXT} characters`,
        });
      }

      const result = normalize(text);
      metrics.requests.normalize++;
      return reply.send({ ok: true, data: result });
    },
  );

  // ── Metrics (admin observability) ─────────────────────────
  app.get(`${PREFIX}/metrics`, async (_req: FastifyRequest, reply: FastifyReply) => {
    const totalRequests = Object.values(metrics.requests).reduce((a, b) => a + b, 0);
    const totalAnalyzed = metrics.cacheHits + metrics.cacheMisses;
    const cacheHitRate = totalAnalyzed > 0 ? Math.round((metrics.cacheHits / totalAnalyzed) * 1000) / 10 : 0;
    const avgLatency = totalAnalyzed > 0 ? Math.round((metrics.totalLatencyMs / metrics.cacheMisses) * 100) / 100 : 0;

    return reply.send({
      ok: true,
      data: {
        uptime: process.uptime(),
        startedAt: new Date(metrics.startedAt).toISOString(),
        requests: {
          total: totalRequests,
          ...metrics.requests,
        },
        cache: {
          size: cache.size,
          maxSize: CACHE_MAX_SIZE,
          ttlHours: CACHE_TTL_MS / 3600000,
          hits: metrics.cacheHits,
          misses: metrics.cacheMisses,
          hitRate: cacheHitRate,
        },
        latency: {
          avgMs: avgLatency,
          totalMs: Math.round(metrics.totalLatencyMs * 100) / 100,
        },
        labels: metrics.labelCounts,
        sources: metrics.sourceCounts,
        errors: metrics.errors,
      },
    });
  });

  // ── API Key Management (admin) ───────────────────────────

  app.post(
    `${PREFIX}/keys`,
    async (req: FastifyRequest<{ Body: { name: string } }>, reply: FastifyReply) => {
      const { name } = req.body ?? {};
      if (!name || typeof name !== 'string' || name.length < 2) {
        return reply.status(400).send({
          ok: false,
          error: 'INVALID_INPUT',
          message: 'Field "name" is required (min 2 chars)',
        });
      }
      try {
        const result = await generateApiKey(name);
        return reply.send({ ok: true, data: result });
      } catch (err: any) {
        return reply.status(500).send({ ok: false, error: 'KEY_GENERATION_FAILED', message: err.message });
      }
    },
  );

  app.get(`${PREFIX}/keys`, async (_req: FastifyRequest, reply: FastifyReply) => {
    try {
      const keys = await listApiKeys();
      return reply.send({ ok: true, data: keys });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: 'LIST_FAILED', message: err.message });
    }
  });

  app.delete(
    `${PREFIX}/keys`,
    async (req: FastifyRequest<{ Body: { prefix: string; permanent?: boolean } }>, reply: FastifyReply) => {
      const { prefix, permanent } = req.body ?? {};
      if (!prefix) {
        return reply.status(400).send({ ok: false, error: 'INVALID_INPUT', message: 'Field "prefix" is required' });
      }
      try {
        if (permanent) {
          const deleted = await deleteApiKey(prefix);
          return reply.send({ ok: true, data: { deleted } });
        } else {
          const revoked = await revokeApiKey(prefix);
          return reply.send({ ok: true, data: { revoked } });
        }
      } catch (err: any) {
        return reply.status(500).send({ ok: false, error: 'DELETE_FAILED', message: err.message });
      }
    },
  );

  // ── Server Config (persisted in MongoDB) ─────────────────

  app.get(`${PREFIX}/config`, async (_req: FastifyRequest, reply: FastifyReply) => {
    try {
      const { getDb } = await import('../../db/mongodb.js');
      const db = getDb();
      const config = await db.collection('sentiment_config').findOne(
        { key: 'server' },
        { projection: { _id: 0 } },
      );
      const data = config || { mode: 'local', url: 'http://localhost:8005' };

      // Server-side health check of the configured URL
      let live = false;
      let version = null;
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 3000);
        const res = await fetch(`${data.url}/api/v1/sentiment/health`, { signal: controller.signal });
        clearTimeout(timeout);
        const json = await res.json() as any;
        if (json.ok) {
          live = true;
          version = json.data?.engineVersion || null;
        }
      } catch {}

      return reply.send({
        ok: true,
        data: { ...data, live, version },
      });
    } catch (err: any) {
      return reply.send({
        ok: true,
        data: { mode: 'local', url: 'http://localhost:8005', live: false, version: null },
      });
    }
  });

  app.post(
    `${PREFIX}/config`,
    async (req: FastifyRequest<{ Body: { mode: string; url: string } }>, reply: FastifyReply) => {
      const { mode, url } = req.body ?? {};
      if (!mode || !url) {
        return reply.status(400).send({ ok: false, error: 'INVALID_INPUT', message: 'Fields "mode" and "url" are required' });
      }

      const cleanUrl = url.replace(/\/$/, '');

      // Server-side verification
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 5000);
        const res = await fetch(`${cleanUrl}/api/v1/sentiment/health`, { signal: controller.signal });
        clearTimeout(timeout);
        const json = await res.json() as any;
        if (!json.ok) {
          return reply.status(400).send({ ok: false, error: 'SERVER_NOT_RESPONDING', message: `Сервер ${cleanUrl} не отвечает корректно` });
        }
      } catch {
        return reply.status(400).send({ ok: false, error: 'SERVER_UNREACHABLE', message: `Не удалось подключиться к ${cleanUrl}` });
      }

      try {
        const { getDb } = await import('../../db/mongodb.js');
        const db = getDb();
        await db.collection('sentiment_config').updateOne(
          { key: 'server' },
          { $set: { key: 'server', mode, url: cleanUrl, updated_at: new Date().toISOString() } },
          { upsert: true },
        );
        return reply.send({ ok: true, data: { mode, url: cleanUrl } });
      } catch (err: any) {
        return reply.status(500).send({ ok: false, error: 'CONFIG_SAVE_FAILED', message: err.message });
      }
    },
  );

  // ── SDK Download ─────────────────────────────────────────

  app.get(`${PREFIX}/sdk/typescript`, async (_req: FastifyRequest, reply: FastifyReply) => {
    try {
      const { readFileSync } = await import('fs');
      const { resolve } = await import('path');
      const content = readFileSync(resolve(process.cwd(), 'public/sentiment-sdk.ts'), 'utf-8');
      reply.header('Content-Type', 'text/plain');
      reply.header('Content-Disposition', 'attachment; filename="sentiment-sdk.ts"');
      return reply.send(content);
    } catch {
      return reply.status(404).send({ ok: false, error: 'SDK file not found' });
    }
  });

  app.get(`${PREFIX}/sdk/python`, async (_req: FastifyRequest, reply: FastifyReply) => {
    try {
      const { readFileSync } = await import('fs');
      const { resolve } = await import('path');
      const content = readFileSync(resolve(process.cwd(), 'public/sentiment_sdk.py'), 'utf-8');
      reply.header('Content-Type', 'text/plain');
      reply.header('Content-Disposition', 'attachment; filename="sentiment_sdk.py"');
      return reply.send(content);
    } catch {
      return reply.status(404).send({ ok: false, error: 'SDK file not found' });
    }
  });

  app.get(`${PREFIX}/sdk/docs`, async (_req: FastifyRequest, reply: FastifyReply) => {
    try {
      const { readFileSync } = await import('fs');
      const { resolve } = await import('path');
      const content = readFileSync(resolve(process.cwd(), 'public/SENTIMENT_API_DOCS.md'), 'utf-8');
      reply.header('Content-Type', 'text/plain');
      reply.header('Content-Disposition', 'attachment; filename="SENTIMENT_API_DOCS.md"');
      return reply.send(content);
    } catch {
      return reply.status(404).send({ ok: false, error: 'Docs file not found' });
    }
  });

  app.get(`${PREFIX}/sdk/zip`, async (_req: FastifyRequest, reply: FastifyReply) => {
    try {
      const { default: AdmZip } = await import('adm-zip');
      const { readFileSync } = await import('fs');
      const { resolve } = await import('path');
      const { getDb } = await import('../../db/mongodb.js');
      const base = resolve(process.cwd(), 'public');

      // Get configured server URL
      let serverUrl = '<YOUR_SERVER_URL>';
      try {
        const db = getDb();
        const config = await db.collection('sentiment_config').findOne({ key: 'server' });
        if (config?.url) serverUrl = config.url;
      } catch {}

      const inject = (content: string) => content.replace(/<YOUR_SERVER_URL>/g, serverUrl);

      const zip = new AdmZip();
      zip.addFile('sentiment_sdk.py', Buffer.from(inject(readFileSync(resolve(base, 'sentiment_sdk.py'), 'utf-8'))));
      zip.addFile('sentiment-sdk.ts', Buffer.from(inject(readFileSync(resolve(base, 'sentiment-sdk.ts'), 'utf-8'))));
      zip.addFile('SENTIMENT_API_DOCS.md', Buffer.from(inject(readFileSync(resolve(base, 'SENTIMENT_API_DOCS.md'), 'utf-8'))));

      const buf = zip.toBuffer();
      reply.header('Content-Type', 'application/zip');
      reply.header('Content-Disposition', 'attachment; filename="sentiment-sdk.zip"');
      return reply.send(buf);
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: 'ZIP_FAILED', message: err.message });
    }
  });

  console.log(`[Sentiment-V1] Universal API registered: ${PREFIX}/* (auth=api-key, cache=24h, rateLimit=${RATE_LIMIT}/min)`);
}
