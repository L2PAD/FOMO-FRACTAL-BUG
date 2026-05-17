/**
 * Wallet Profile Compute Service — Phase C1 + C1.3
 * ===================================================
 * Deterministic compute: ERC20 logs → profile snapshot.
 * No cache. No jobs. Pure computation.
 *
 * C1.3: Counterparty USD breakdown done in single pass.
 */

import mongoose from 'mongoose';
import type {
  WindowKey, WalletProfileSnapshot, WalletTokenRow,
  WalletCounterpartyRow, WalletAttribution,
} from './contracts';
import { AddressLabelModel } from '../labels/addressLabel.model';

// ── Direct collection access ──

function getErc20Collection() {
  return mongoose.connection.collection('onchain_v2_erc20_logs');
}

// ── Price loading (same pattern as CexBucketAggregate) ──

interface PriceEntry { usd: number; decimals: number; symbol: string }

async function loadPrices(chainId: number): Promise<Map<string, PriceEntry>> {
  const prices = new Map<string, PriceEntry>();

  const priceColl = mongoose.connection.collection('onchain_v2_token_prices');
  const priceDocs = await priceColl.find({ chainId }).toArray();
  for (const d of priceDocs) {
    const addr = String(d.token || d.address || '').toLowerCase();
    if (addr) prices.set(addr, { usd: d.priceUsd ?? 0, decimals: d.decimals ?? 18, symbol: d.symbol || '' });
  }

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
      prices.set(addr, { usd: d.priceUsd ?? 0, decimals: d.decimals ?? 18, symbol: d.symbol || '' });
    }
  }

  // Stablecoins fallback
  const stables: Record<string, PriceEntry> = {
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

const STABLECOINS = new Set([
  '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
  '0xdac17f958d2ee523a2206206994597c13d831ec7',
  '0x6b175474e89094c44da98b954eedeac495271d0f',
  '0x4fabb145d64652a948d72533023f6e7a623c7c53',
]);

function parseValue(raw: string | number, decimals: number): number {
  if (!raw) return 0;
  const s = String(raw);
  if (s.length <= 15) return Number(s) / (10 ** decimals);
  if (s.length <= decimals) return Number('0.' + s.padStart(decimals, '0'));
  const intPart = s.slice(0, s.length - decimals);
  const fracPart = s.slice(s.length - decimals);
  return Number(intPart + '.' + fracPart);
}

function windowToMs(w: WindowKey): number {
  if (w === '24h') return 24 * 3600_000;
  if (w === '7d') return 7 * 24 * 3600_000;
  return 30 * 24 * 3600_000;
}

// ── Entity Resolution (lightweight, inline) ──

async function resolveAddress(chainId: number, address: string): Promise<WalletAttribution> {
  const addr = String(address).toLowerCase();
  try {
    const label = await AddressLabelModel.findOne({ chainId, address: addr }).lean();
    if (label) {
      const l = label as any;
      return {
        entityId: l.entityId,
        entityName: l.name || l.entityId,
        entityType: l.labelType?.toLowerCase() || 'unknown',
        source: 'LABEL_V2',
        confidence: l.confidence ?? 0.90,
        evidence: [{ kind: 'label_v2', labelType: l.labelType, source: l.source }],
      };
    }
  } catch {}

  return {
    entityId: null,
    entityName: null,
    entityType: 'unknown',
    source: 'NONE',
    confidence: 0,
    evidence: [],
  };
}

async function batchResolve(chainId: number, addresses: string[]): Promise<Map<string, WalletAttribution>> {
  const map = new Map<string, WalletAttribution>();
  if (!addresses.length) return map;

  const addrs = addresses.map(a => a.toLowerCase());
  const labels = await AddressLabelModel.find({ chainId, address: { $in: addrs } }).lean();

  for (const l of labels) {
    const la = l as any;
    const addr = String(la.address).toLowerCase();
    map.set(addr, {
      entityId: la.entityId,
      entityName: la.name || la.entityId,
      entityType: la.labelType?.toLowerCase() || 'unknown',
      source: 'LABEL_V2',
      confidence: la.confidence ?? 0.90,
      evidence: [{ kind: 'label_v2', labelType: la.labelType }],
    });
  }

  for (const addr of addrs) {
    if (!map.has(addr)) {
      map.set(addr, {
        entityId: null, entityName: null, entityType: 'unknown',
        source: 'NONE', confidence: 0, evidence: [],
      });
    }
  }

  return map;
}

// ── Main Compute ──

const MAX_TRANSFERS = 50_000;

export async function computeWalletProfile(params: {
  chainId: number;
  address: string;
  window: WindowKey;
}): Promise<WalletProfileSnapshot> {
  const { chainId, window: win } = params;
  const address = String(params.address).toLowerCase();
  const tag = `[WalletV3:${address.slice(0, 8)}]`;
  const start = Date.now();

  const cutoffMs = Date.now() - windowToMs(win);
  const fromTs = new Date(cutoffMs).toISOString();
  const toTs = new Date().toISOString();

  // 1. Load prices once
  const prices = await loadPrices(chainId);

  // 2. Query ERC20 transfers involving this address
  const erc20 = getErc20Collection();
  const [inLogs, outLogs] = await Promise.all([
    erc20.find({ to: address, indexedAt: { $gte: cutoffMs } }).limit(MAX_TRANSFERS).toArray(),
    erc20.find({ from: address, indexedAt: { $gte: cutoffMs } }).limit(MAX_TRANSFERS).toArray(),
  ]);

  const truncated = inLogs.length >= MAX_TRANSFERS || outLogs.length >= MAX_TRANSFERS;
  const totalLogs = inLogs.length + outLogs.length;
  console.log(`${tag} Loaded ${inLogs.length} in + ${outLogs.length} out logs`);

  // 3. Single-pass aggregation (C1.3: token + counterparty USD in one pass)
  interface TokenAcc { inUsd: number; outUsd: number; transfers: number; symbol: string }
  interface CpAcc { inUsd: number; outUsd: number; transfers: number }

  const tokenAgg = new Map<string, TokenAcc>();
  const cpAgg = new Map<string, CpAcc>();

  let inflowUsd = 0, outflowUsd = 0, stableUsd = 0;
  const usdAmounts: number[] = [];

  const getOrCreateToken = (tok: string): TokenAcc => {
    if (!tokenAgg.has(tok)) tokenAgg.set(tok, { inUsd: 0, outUsd: 0, transfers: 0, symbol: '' });
    return tokenAgg.get(tok)!;
  };
  const getOrCreateCp = (cp: string): CpAcc => {
    if (!cpAgg.has(cp)) cpAgg.set(cp, { inUsd: 0, outUsd: 0, transfers: 0 });
    return cpAgg.get(cp)!;
  };

  // IN logs: to == address (inflow)
  for (const log of inLogs) {
    const tokenAddr = String(log.tokenAddress || '').toLowerCase();
    const fromAddr = String(log.from || '').toLowerCase();
    const price = prices.get(tokenAddr);
    const amount = parseValue(log.value || '0', price?.decimals ?? 18);
    if (amount <= 0 || !isFinite(amount)) continue;

    const usd = (price?.usd ?? 0) * amount;
    if (!isFinite(usd)) continue;

    const ta = getOrCreateToken(tokenAddr);
    ta.inUsd += usd;
    ta.transfers++;
    if (!ta.symbol && price?.symbol) ta.symbol = price.symbol;

    inflowUsd += usd;
    if (STABLECOINS.has(tokenAddr)) stableUsd += usd;
    if (usd > 0) usdAmounts.push(usd);

    if (fromAddr && fromAddr !== address) {
      const cp = getOrCreateCp(fromAddr);
      cp.inUsd += usd;
      cp.transfers++;
    }
  }

  // OUT logs: from == address (outflow)
  for (const log of outLogs) {
    const tokenAddr = String(log.tokenAddress || '').toLowerCase();
    const toAddr = String(log.to || '').toLowerCase();
    const price = prices.get(tokenAddr);
    const amount = parseValue(log.value || '0', price?.decimals ?? 18);
    if (amount <= 0 || !isFinite(amount)) continue;

    const usd = (price?.usd ?? 0) * amount;
    if (!isFinite(usd)) continue;

    const ta = getOrCreateToken(tokenAddr);
    ta.outUsd += usd;
    ta.transfers++;
    if (!ta.symbol && price?.symbol) ta.symbol = price.symbol;

    outflowUsd += usd;
    if (STABLECOINS.has(tokenAddr)) stableUsd += usd;
    if (usd > 0) usdAmounts.push(usd);

    if (toAddr && toAddr !== address) {
      const cp = getOrCreateCp(toAddr);
      cp.outUsd += usd;
      cp.transfers++;
    }
  }

  // 4. Build top tokens
  const topTokens: WalletTokenRow[] = Array.from(tokenAgg.entries())
    .map(([addr, t]) => ({
      tokenAddress: addr,
      symbol: t.symbol || addr.slice(0, 10) + '...',
      inUsd: t.inUsd,
      outUsd: t.outUsd,
      netUsd: t.inUsd - t.outUsd,
      transfers: t.transfers,
      priceUsd: prices.get(addr)?.usd ?? null,
    }))
    .filter(t => t.inUsd > 0 || t.outUsd > 0)
    .sort((a, b) => Math.abs(b.netUsd) - Math.abs(a.netUsd))
    .slice(0, 15);

  // 5. Build top counterparties with USD (C1.3)
  const cpEntries = Array.from(cpAgg.entries())
    .map(([addr, c]) => ({
      address: addr,
      inUsd: c.inUsd,
      outUsd: c.outUsd,
      netUsd: c.inUsd - c.outUsd,
      transfers: c.transfers,
    }))
    .sort((a, b) => Math.abs(b.netUsd) - Math.abs(a.netUsd))
    .slice(0, 20);

  // 6. Batch resolve attribution for top counterparties
  const cpAddresses = cpEntries.map(c => c.address);
  const cpAttrs = await batchResolve(chainId, cpAddresses);

  const topCounterparties: WalletCounterpartyRow[] = cpEntries.map(c => ({
    ...c,
    attribution: cpAttrs.get(c.address) || undefined,
  }));

  // 7. Self-attribution
  const attribution = await resolveAddress(chainId, address);

  // 8. Stats
  const totalVolume = inflowUsd + outflowUsd;
  const avgTransferUsd = usdAmounts.length > 0
    ? usdAmounts.reduce((s, v) => s + v, 0) / usdAmounts.length
    : 0;
  const stableShare = totalVolume > 0 ? stableUsd / totalVolume : 0;

  const elapsed = Date.now() - start;
  console.log(`${tag} Done: ${totalLogs} logs, ${tokenAgg.size} tokens, ${cpAgg.size} counterparties (${elapsed}ms)`);

  return {
    ok: true,
    chainId,
    address,
    window: win,
    totals: {
      inflowUsd,
      outflowUsd,
      netUsd: inflowUsd - outflowUsd,
      transfers: totalLogs,
      uniqueCounterparties: cpAgg.size,
      stableShare: Math.round(stableShare * 100) / 100,
      avgTransferUsd: Math.round(avgTransferUsd * 100) / 100,
    },
    attribution,
    topTokens,
    topCounterparties,
    meta: {
      fromTs,
      toTs,
      computedAt: new Date().toISOString(),
      pricedTokens: topTokens.filter(t => t.priceUsd != null && t.priceUsd > 0).length,
      totalTokens: tokenAgg.size,
      truncated,
    },
  };
}
