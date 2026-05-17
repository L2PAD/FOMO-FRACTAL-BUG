/**
 * CEX Flow Service — Phase A, Block A2
 * ======================================
 *
 * Aggregates IN/OUT flows for CEX entities from raw ERC20 transfer logs.
 * Uses onchain_v2_erc20_logs + onchain_v2_address_labels + pricing.
 *
 * IN  = ERC20 Transfer where `to` is a CEX address (deposits)
 * OUT = ERC20 Transfer where `from` is a CEX address (withdrawals)
 *
 * Internal transfers (from.entityId == to.entityId) are filtered out.
 */

import mongoose from 'mongoose';
import { AddressLabelModel } from '../../labels/addressLabel.model';

// ── ERC20 Log Collection (direct access) ──

function getErc20Collection() {
  return mongoose.connection.collection('onchain_v2_erc20_logs');
}

// ── Types ──

export interface CexExchange {
  entityId: string;
  entityName: string;
  addressCount: number;
}

export interface CexTokenFlow {
  tokenAddress: string;
  tokenSymbol: string;
  inUsd: number;
  outUsd: number;
  netUsd: number;
  txCount: number;
}

export interface CexFlowSummary {
  entityId: string;
  entityName: string;
  window: string;
  totals: {
    inUsd: number;
    outUsd: number;
    netUsd: number;
    txCount: number;
    uniqueCounterparties: number;
  };
  topTokensIn: CexTokenFlow[];
  topTokensOut: CexTokenFlow[];
  topNetTokens: CexTokenFlow[];
  updatedAt: string | null;
  quality: {
    totalLogs: number;
    pricedLogs: number;
    pricedShare: number;
  };
}

// ── Price cache (simple) ──

interface PriceEntry { usd: number; decimals: number; symbol: string }

async function loadPrices(chainId: number): Promise<Map<string, PriceEntry>> {
  const prices = new Map<string, PriceEntry>();

  // 1. Load from token_prices (field: "token")
  const priceColl = mongoose.connection.collection('onchain_v2_token_prices');
  const priceDocs = await priceColl.find({ chainId }).toArray();
  for (const d of priceDocs) {
    const addr = String(d.token || d.address || '').toLowerCase();
    if (addr) {
      prices.set(addr, {
        usd: d.priceUsd ?? 0,
        decimals: d.decimals ?? 18,
        symbol: d.symbol || '',
      });
    }
  }

  // 2. Enrich with decimals/symbol from token_registry
  const reg = mongoose.connection.collection('token_registry');
  const regDocs = await reg.find({ chainId }).toArray();
  for (const d of regDocs) {
    const addr = String(d.address || '').toLowerCase();
    if (!addr) continue;
    if (prices.has(addr)) {
      const p = prices.get(addr)!;
      if (!p.symbol && d.symbol) p.symbol = d.symbol;
      if (d.decimals != null) p.decimals = d.decimals;
    } else {
      prices.set(addr, {
        usd: d.priceUsd ?? 0,
        decimals: d.decimals ?? 18,
        symbol: d.symbol || 'UNKNOWN',
      });
    }
  }

  // 3. Known stablecoins fallback
  const stables: Record<string, { usd: number; decimals: number; symbol: string }> = {
    '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48': { usd: 1, decimals: 6, symbol: 'USDC' },
    '0xdac17f958d2ee523a2206206994597c13d831ec7': { usd: 1, decimals: 6, symbol: 'USDT' },
    '0x6b175474e89094c44da98b954eedeac495271d0f': { usd: 1, decimals: 18, symbol: 'DAI' },
  };
  for (const [addr, p] of Object.entries(stables)) {
    if (!prices.has(addr)) prices.set(addr, p);
    else if (!prices.get(addr)!.usd) prices.get(addr)!.usd = p.usd;
  }

  return prices;
}

// ── Helpers ──

function windowToMs(w: string): number {
  if (w === '24h') return 24 * 3600_000;
  if (w === '7d') return 7 * 24 * 3600_000;
  if (w === '30d') return 30 * 24 * 3600_000;
  return 7 * 24 * 3600_000;
}

function parseValue(raw: string | number, decimals: number): number {
  if (!raw) return 0;
  const s = String(raw);
  // Handle big integers - convert to float with decimals
  if (s.length <= 15) {
    return Number(s) / (10 ** decimals);
  }
  // For very large numbers, shift decimal point manually
  if (s.length <= decimals) {
    return Number('0.' + s.padStart(decimals, '0'));
  }
  const intPart = s.slice(0, s.length - decimals);
  const fracPart = s.slice(s.length - decimals);
  return Number(intPart + '.' + fracPart);
}

const ENTITY_NAMES: Record<string, string> = {
  binance: 'Binance',
  bybit: 'Bybit',
  coinbase: 'Coinbase',
  kraken: 'Kraken',
  okx: 'OKX',
  kucoin: 'KuCoin',
  gemini: 'Gemini',
  bitfinex: 'Bitfinex',
  gate_io: 'Gate.io',
  gate: 'Gate.io',
  htx: 'HTX',
  hyperliquid: 'Hyperliquid',
  crypto_com: 'Crypto.com',
  bitstamp: 'Bitstamp',
  bittrex: 'Bittrex',
  poloniex: 'Poloniex',
  deribit: 'Deribit',
  bitmex: 'BitMEX',
  mexc: 'MEXC',
  upbit: 'Upbit',
  bingx: 'BingX',
  coinone: 'Coinone',
  hitbtc: 'HitBTC',
  whitebit: 'WhiteBIT',
  bitflyer: 'bitFlyer',
  korbit: 'Korbit',
  binance_us: 'Binance.US',
};

function prettifyName(entityId: string): string {
  return ENTITY_NAMES[entityId] || entityId.charAt(0).toUpperCase() + entityId.slice(1);
}

// ── Service ──

export class CexFlowService {
  /**
   * Get list of available CEX exchanges (from labels)
   */
  async getExchanges(chainId: number): Promise<{ ok: boolean; exchanges: CexExchange[] }> {
    const agg = await AddressLabelModel.aggregate([
      { $match: { chainId, labelType: 'EXCHANGE' } },
      {
        $group: {
          _id: '$entityId',
          addressCount: { $sum: 1 },
        },
      },
      { $sort: { addressCount: -1 } },
    ]);

    const exchanges = agg.map((r: any) => ({
      entityId: r._id,
      entityName: prettifyName(r._id),
      addressCount: r.addressCount,
    }));

    return { ok: true, exchanges };
  }

  /**
   * Get CEX flow summary for a specific exchange
   */
  async getSummary(params: {
    chainId: number;
    entityId: string;
    window: string;
  }): Promise<{ ok: boolean } & Partial<CexFlowSummary>> {
    const { chainId, entityId, window } = params;

    // 1. Get all addresses for this exchange
    const labels = await AddressLabelModel.find({
      chainId,
      labelType: 'EXCHANGE',
      entityId,
    }).lean();

    const addresses = labels.map((l: any) => String(l.address).toLowerCase());
    if (addresses.length === 0) {
      return {
        ok: true,
        entityId,
        entityName: prettifyName(entityId),
        window,
        totals: { inUsd: 0, outUsd: 0, netUsd: 0, txCount: 0, uniqueCounterparties: 0 },
        topTokensIn: [],
        topTokensOut: [],
        topNetTokens: [],
        updatedAt: null,
        quality: { totalLogs: 0, pricedLogs: 0, pricedShare: 0 },
      };
    }

    // 2. Get all CEX addresses (for internal transfer filter)
    const allCexLabels = await AddressLabelModel.find({
      chainId,
      labelType: 'EXCHANGE',
      entityId,
    }).lean();
    const entityAddressSet = new Set(allCexLabels.map((l: any) => String(l.address).toLowerCase()));

    // 3. Time window — use indexedAt (ms timestamp) since blockTimestamp is null
    const cutoffMs = Date.now() - windowToMs(window);

    // 4. Load prices
    const prices = await loadPrices(chainId);

    // 5. Query ERC20 logs: IN (to=exchange) + OUT (from=exchange)
    const erc20 = getErc20Collection();

    const [inLogs, outLogs] = await Promise.all([
      erc20.find({
        to: { $in: addresses },
        indexedAt: { $gte: cutoffMs },
      }).toArray(),
      erc20.find({
        from: { $in: addresses },
        indexedAt: { $gte: cutoffMs },
      }).toArray(),
    ]);

    // 6. Aggregate
    const tokenMap = new Map<string, CexTokenFlow>();
    const counterparties = new Set<string>();
    let pricedCount = 0;
    let totalLogs = 0;
    let latestTs: Date | null = null;

    const ensureToken = (addr: string, symbol: string): CexTokenFlow => {
      if (!tokenMap.has(addr)) {
        tokenMap.set(addr, {
          tokenAddress: addr,
          tokenSymbol: symbol,
          inUsd: 0,
          outUsd: 0,
          netUsd: 0,
          txCount: 0,
        });
      }
      return tokenMap.get(addr)!;
    };

    // IN logs (to = exchange)
    for (const log of inLogs) {
      const from = String(log.from || '').toLowerCase();
      if (entityAddressSet.has(from)) continue;

      const tokenAddr = String(log.tokenAddress || '').toLowerCase();
      const price = prices.get(tokenAddr);
      const decimals = price?.decimals ?? 18;
      const symbol = price?.symbol ?? 'UNKNOWN';
      const amount = parseValue(log.value || '0', decimals);
      const usd = price ? amount * price.usd : 0;

      if (usd > 0) pricedCount++;
      totalLogs++;

      const row = ensureToken(tokenAddr, symbol);
      row.inUsd += usd;
      row.netUsd += usd;
      row.txCount++;
      counterparties.add(from);

      const ts = log.indexedAt ? new Date(log.indexedAt) : null;
      if (ts && (!latestTs || ts > latestTs)) latestTs = ts;
    }

    // OUT logs (from = exchange)
    for (const log of outLogs) {
      const to = String(log.to || '').toLowerCase();
      if (entityAddressSet.has(to)) continue;

      const tokenAddr = String(log.tokenAddress || '').toLowerCase();
      const price = prices.get(tokenAddr);
      const decimals = price?.decimals ?? 18;
      const symbol = price?.symbol ?? 'UNKNOWN';
      const amount = parseValue(log.value || '0', decimals);
      const usd = price ? amount * price.usd : 0;

      if (usd > 0) pricedCount++;
      totalLogs++;

      const row = ensureToken(tokenAddr, symbol);
      row.outUsd += usd;
      row.netUsd -= usd;
      row.txCount++;
      counterparties.add(to);

      const ts = log.indexedAt ? new Date(log.indexedAt) : null;
      if (ts && (!latestTs || ts > latestTs)) latestTs = ts;
    }

    // 7. Compute totals
    const allTokens = Array.from(tokenMap.values());
    const totals = {
      inUsd: allTokens.reduce((s, t) => s + t.inUsd, 0),
      outUsd: allTokens.reduce((s, t) => s + t.outUsd, 0),
      netUsd: allTokens.reduce((s, t) => s + t.netUsd, 0),
      txCount: totalLogs,
      uniqueCounterparties: counterparties.size,
    };

    const topTokensIn = [...allTokens].filter(t => t.inUsd > 0).sort((a, b) => b.inUsd - a.inUsd).slice(0, 20);
    const topTokensOut = [...allTokens].filter(t => t.outUsd > 0).sort((a, b) => b.outUsd - a.outUsd).slice(0, 20);
    const topNetTokens = [...allTokens].sort((a, b) => Math.abs(b.netUsd) - Math.abs(a.netUsd)).slice(0, 20);

    return {
      ok: true,
      entityId,
      entityName: prettifyName(entityId),
      window,
      totals,
      topTokensIn,
      topTokensOut,
      topNetTokens,
      updatedAt: latestTs ? latestTs.toISOString() : null,
      quality: {
        totalLogs,
        pricedLogs: pricedCount,
        pricedShare: totalLogs > 0 ? pricedCount / totalLogs : 0,
      },
    };
  }

  /**
   * Get cross-exchange comparison (all exchanges for a window)
   */
  async getCrossExchange(params: {
    chainId: number;
    window: string;
  }): Promise<{
    ok: boolean;
    exchanges: Array<{
      entityId: string;
      entityName: string;
      inUsd: number;
      outUsd: number;
      netUsd: number;
      txCount: number;
    }>;
  }> {
    const { chainId, window } = params;

    // Get all exchange entities
    const { exchanges: exList } = await this.getExchanges(chainId);

    const results = [];
    for (const ex of exList) {
      const summary = await this.getSummary({ chainId, entityId: ex.entityId, window });
      const totals = summary.totals || { inUsd: 0, outUsd: 0, netUsd: 0, txCount: 0 };
      results.push({
        entityId: ex.entityId,
        entityName: ex.entityName,
        inUsd: totals.inUsd,
        outUsd: totals.outUsd,
        netUsd: totals.netUsd,
        txCount: totals.txCount,
      });
    }

    // Sort by total volume desc
    results.sort((a, b) => (b.inUsd + b.outUsd) - (a.inUsd + a.outUsd));

    return { ok: true, exchanges: results };
  }
}
