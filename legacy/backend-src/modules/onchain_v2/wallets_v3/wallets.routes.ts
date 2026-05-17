/**
 * Wallets v3 Routes — Phase C (C1-C4)
 * ======================================
 * Fastify plugin for wallet deep profile endpoints.
 *
 * Endpoints:
 *   GET /wallets/health
 *   GET /wallets/profile?address=0x..&window=7d
 *   GET /wallets/tokens?address=0x..&window=7d
 *   GET /wallets/counterparties?address=0x..&window=7d
 *   GET /wallets/series?address=0x..&window=7d&metric=netUsd
 *   GET /wallets/job/status
 *   POST /wallets/job/force-tick
 *   POST /wallets/buckets/aggregate?address=0x..&days=30
 */

import { FastifyInstance } from 'fastify';
import { computeWalletProfile } from './walletProfileCompute.service';
import { readWalletSeries, aggregateWalletBuckets } from './walletBucketAggregate.service';
import { getWalletTokens } from './walletTokenAggregate.service';
import { getWalletCounterparties } from './walletCounterpartyAggregate.service';
import { WalletSnapshotModel } from './walletSnapshot.model';
import {
  getWalletSnapshotJobStatus,
  forceWalletSnapshotTick,
  trackWalletForSnapshots,
} from './walletSnapshot.job';
import type { WindowKey } from './contracts';

function normAddr(x: any): string {
  return String(x || '').toLowerCase().trim();
}

function normWindow(x: any): WindowKey {
  const v = String(x || '7d');
  return (v === '24h' || v === '7d' || v === '30d') ? v as WindowKey : '7d';
}

function windowToDays(w: WindowKey): number {
  if (w === '24h') return 1;
  if (w === '7d') return 7;
  return 30;
}

export async function walletsV3Routes(fastify: FastifyInstance) {

  // ── Health ──
  fastify.get('/health', async () => ({
    ok: true,
    module: 'wallets_v3',
    cache: { enabled: true, ttlMin: 30 },
    jobs: {
      enabled: true,
      status: getWalletSnapshotJobStatus(),
    },
  }));

  // ── Profile (main endpoint — cache-first, then compute) ──
  fastify.get('/profile', async (req, reply) => {
    const q = req.query as any;
    const address = normAddr(q.address);
    const chainId = Number(q.chainId ?? 1);
    const window = normWindow(q.window);

    if (!address || address.length < 10) {
      return reply.code(400).send({ ok: false, error: 'MISSING_ADDRESS' });
    }

    // C4: Check cache first
    try {
      const cached = await WalletSnapshotModel.findOne(
        { chainId, address, window },
        { _id: 0, snapshot: 1, computedAt: 1 }
      ).lean();

      if (cached && (cached as any).snapshot) {
        const snapshot = (cached as any).snapshot;
        // Mark as cached
        snapshot._cached = true;
        snapshot._cachedAt = (cached as any).computedAt;
        return snapshot;
      }
    } catch {}

    // On-demand compute
    const snapshot = await computeWalletProfile({ chainId, address, window });

    // Auto-track for future snapshot jobs
    trackWalletForSnapshots(chainId, address).catch(() => {});

    // Also aggregate buckets on-demand (C2) — fire and forget
    aggregateWalletBuckets({ chainId, address, days: windowToDays(window) }).catch(() => {});

    return snapshot;
  });

  // ── Tokens (C3.1 — bucket-based aggregation) ──
  fastify.get('/tokens', async (req, reply) => {
    const q = req.query as any;
    const address = normAddr(q.address);
    const chainId = Number(q.chainId ?? 1);
    const window = normWindow(q.window);

    if (!address || address.length < 10) {
      return reply.code(400).send({ ok: false, error: 'MISSING_ADDRESS' });
    }

    // Ensure buckets exist (fire aggregation if needed, non-blocking for subsequent calls)
    aggregateWalletBuckets({ chainId, address, days: windowToDays(window) }).catch(() => {});

    const result = await getWalletTokens({ chainId, address, window });
    return result;
  });

  // ── Counterparties (C3.2 — bucket-based aggregation) ──
  fastify.get('/counterparties', async (req, reply) => {
    const q = req.query as any;
    const address = normAddr(q.address);
    const chainId = Number(q.chainId ?? 1);
    const window = normWindow(q.window);

    if (!address || address.length < 10) {
      return reply.code(400).send({ ok: false, error: 'MISSING_ADDRESS' });
    }

    // Ensure buckets exist
    aggregateWalletBuckets({ chainId, address, days: windowToDays(window) }).catch(() => {});

    const result = await getWalletCounterparties({ chainId, address, window });
    return result;
  });

  // ── Series (C2 — reads from pre-computed daily buckets) ──
  fastify.get('/series', async (req, reply) => {
    const q = req.query as any;
    const address = normAddr(q.address);
    const chainId = Number(q.chainId ?? 1);
    const window = normWindow(q.window);
    const metric = String(q.metric || 'netUsd');

    if (!address || address.length < 10) {
      return reply.code(400).send({ ok: false, error: 'MISSING_ADDRESS' });
    }

    const days = windowToDays(window);
    const points = await readWalletSeries({ chainId, address, days, metric });

    return {
      ok: true,
      chainId, address, window, metric,
      points,
      bucketed: true,
    };
  });

  // ── Job Status (C4) ──
  fastify.get('/job/status', async () => {
    return {
      ok: true,
      ...getWalletSnapshotJobStatus(),
    };
  });

  // ── Force Tick (C4) ──
  fastify.post('/job/force-tick', async () => {
    const status = await forceWalletSnapshotTick();
    return { ok: true, ...status };
  });

  // ── Manual Bucket Aggregate (C2) ──
  fastify.post('/buckets/aggregate', async (req, reply) => {
    const q = req.query as any;
    const address = normAddr(q.address);
    const chainId = Number(q.chainId ?? 1);
    const days = Math.min(Number(q.days || 30), 90);

    if (!address || address.length < 10) {
      return reply.code(400).send({ ok: false, error: 'MISSING_ADDRESS' });
    }

    const result = await aggregateWalletBuckets({ chainId, address, days });
    return { ok: true, ...result };
  });

  console.log('[Wallets v3] Routes registered (C1-C4)');
}
