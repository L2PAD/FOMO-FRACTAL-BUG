/**
 * CEX Bucket Routes — Phase A3.4
 * ================================
 * Fast-read endpoints powered by pre-computed cex_flow_buckets collection.
 * Replaces the slow 26-sequential-query pattern.
 *
 * Fastify plugin pattern (same as other onchain_v2 routes).
 */

import { FastifyInstance } from 'fastify';
import { CexFlowBucketModel } from './cexFlowBucket.model';
import { getCexBucketJobStatus, forceCexBucketTick } from './cexBucket.job';

const ENTITY_NAMES: Record<string, string> = {
  binance: 'Binance', bybit: 'Bybit', coinbase: 'Coinbase',
  kraken: 'Kraken', okx: 'OKX', kucoin: 'KuCoin',
  gemini: 'Gemini', bitfinex: 'Bitfinex', gate: 'Gate.io',
  htx: 'HTX', hyperliquid: 'Hyperliquid', crypto_com: 'Crypto.com',
  bitstamp: 'Bitstamp', bittrex: 'Bittrex', poloniex: 'Poloniex',
  deribit: 'Deribit', bitmex: 'BitMEX', mexc: 'MEXC',
  upbit: 'Upbit', bingx: 'BingX', coinone: 'Coinone',
  hitbtc: 'HitBTC', whitebit: 'WhiteBIT', bitflyer: 'bitFlyer',
  korbit: 'Korbit', binance_us: 'Binance.US',
};

function prettifyName(id: string): string {
  return ENTITY_NAMES[id] || id.charAt(0).toUpperCase() + id.slice(1);
}

export async function cexBucketRoutes(fastify: FastifyInstance) {

  // ── Job control ──

  fastify.get('/job/status', async () => {
    return { ok: true, ...getCexBucketJobStatus() };
  });

  fastify.post('/job/force-tick', async () => {
    const result = await forceCexBucketTick();
    return { ok: true, ...result };
  });

  // ── Cross-exchange overview (replaces slow /cex-flow/cross) ──
  // GET /cex-flow/buckets/cross?chainId=1&window=24h

  fastify.get('/cross', async (req) => {
    const q = req.query as any;
    const chainId = Number(q.chainId ?? 1);
    const window = String(q.window ?? '24h');

    // Find the latest bucketStart for this window
    const latest = await CexFlowBucketModel.findOne(
      { chainId, window },
      { bucketStart: 1 },
      { sort: { bucketStart: -1 } }
    ).lean();

    if (!latest) {
      return { ok: true, items: [], window, bucketStart: null, stale: true, reason: 'NO_BUCKETS' };
    }

    const bucketStart = (latest as any).bucketStart;
    const stale = Date.now() - new Date(bucketStart).getTime() > 30 * 60_000;

    // Aggregate by exchange
    const rows = await CexFlowBucketModel.aggregate([
      { $match: { chainId, window, bucketStart } },
      {
        $group: {
          _id: '$exchangeId',
          inflowUsd:   { $sum: '$inflowUsd' },
          outflowUsd:  { $sum: '$outflowUsd' },
          netUsd:      { $sum: '$netUsd' },
          transferCount: { $sum: '$transferCount' },
        },
      },
      { $sort: { netUsd: -1 } },
    ]);

    const items = rows.map((r: any) => ({
      exchangeId: r._id,
      entityName: prettifyName(r._id),
      inflowUsd: r.inflowUsd,
      outflowUsd: r.outflowUsd,
      netUsd: r.netUsd,
      transferCount: r.transferCount,
    }));

    return { ok: true, window, bucketStart, stale, items };
  });

  // ── Exchange drilldown (top tokens) ──
  // GET /cex-flow/buckets/exchange/:exchangeId?window=24h&limit=20

  fastify.get('/exchange/:exchangeId', async (req) => {
    const { exchangeId } = req.params as any;
    const q = req.query as any;
    const chainId = Number(q.chainId ?? 1);
    const window = String(q.window ?? '24h');
    const limit = Math.min(Number(q.limit ?? 20), 50);

    // Find latest bucket
    const latest = await CexFlowBucketModel.findOne(
      { chainId, exchangeId, window },
      { bucketStart: 1 },
      { sort: { bucketStart: -1 } }
    ).lean();

    if (!latest) {
      return {
        ok: true, exchangeId, entityName: prettifyName(exchangeId),
        window, bucketStart: null, topIn: [], topOut: [], totals: null,
        stale: true, reason: 'NO_BUCKETS',
      };
    }

    const bucketStart = (latest as any).bucketStart;
    const stale = Date.now() - new Date(bucketStart).getTime() > 30 * 60_000;

    // Get all token buckets for this exchange
    const buckets = await CexFlowBucketModel.find(
      { chainId, exchangeId, window, bucketStart },
      { _id: 0, tokenAddress: 1, tokenSymbol: 1, inflowUsd: 1, outflowUsd: 1, netUsd: 1, transferCount: 1 }
    ).lean();

    // Compute totals
    let totalIn = 0, totalOut = 0, totalNet = 0, totalTx = 0;
    for (const b of buckets) {
      totalIn += (b as any).inflowUsd || 0;
      totalOut += (b as any).outflowUsd || 0;
      totalNet += (b as any).netUsd || 0;
      totalTx += (b as any).transferCount || 0;
    }

    const sorted = (buckets as any[]).map(b => ({
      tokenAddress: b.tokenAddress,
      tokenSymbol: b.tokenSymbol || b.tokenAddress.slice(0, 10) + '...',
      inflowUsd: b.inflowUsd,
      outflowUsd: b.outflowUsd,
      netUsd: b.netUsd,
      transferCount: b.transferCount,
    }));

    const topIn = [...sorted].sort((a, b) => b.inflowUsd - a.inflowUsd).slice(0, limit);
    const topOut = [...sorted].sort((a, b) => b.outflowUsd - a.outflowUsd).slice(0, limit);

    return {
      ok: true, exchangeId, entityName: prettifyName(exchangeId),
      window, bucketStart, stale,
      totals: { inflowUsd: totalIn, outflowUsd: totalOut, netUsd: totalNet, transferCount: totalTx },
      topIn, topOut,
    };
  });

  // ── Token across exchanges ──
  // GET /cex-flow/buckets/token/:tokenAddress?window=24h

  fastify.get('/token/:tokenAddress', async (req) => {
    const { tokenAddress } = req.params as any;
    const q = req.query as any;
    const chainId = Number(q.chainId ?? 1);
    const window = String(q.window ?? '24h');
    const addr = String(tokenAddress).toLowerCase();

    const latest = await CexFlowBucketModel.findOne(
      { chainId, tokenAddress: addr, window },
      { bucketStart: 1 },
      { sort: { bucketStart: -1 } }
    ).lean();

    if (!latest) {
      return { ok: true, tokenAddress: addr, window, items: [], reason: 'NO_BUCKETS' };
    }

    const bucketStart = (latest as any).bucketStart;

    const rows = await CexFlowBucketModel.find(
      { chainId, tokenAddress: addr, window, bucketStart },
      { _id: 0, exchangeId: 1, inflowUsd: 1, outflowUsd: 1, netUsd: 1, transferCount: 1, tokenSymbol: 1 }
    ).lean();

    const items = (rows as any[]).map(r => ({
      exchangeId: r.exchangeId,
      entityName: prettifyName(r.exchangeId),
      inflowUsd: r.inflowUsd,
      outflowUsd: r.outflowUsd,
      netUsd: r.netUsd,
      transferCount: r.transferCount,
    }));

    return {
      ok: true, tokenAddress: addr,
      tokenSymbol: (rows as any[])[0]?.tokenSymbol || '',
      window, bucketStart, items,
    };
  });

  console.log('[CEX Bucket Routes] Registered');
}
