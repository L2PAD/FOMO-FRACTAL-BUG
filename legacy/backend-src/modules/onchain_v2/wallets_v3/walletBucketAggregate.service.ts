/**
 * Wallet Bucket Aggregate Service — Phase C2
 * =============================================
 * Reads ERC20 logs for tracked wallets and upserts daily flow buckets.
 * Pattern follows CexBucketAggregateService.
 */

import mongoose from 'mongoose';
import { WalletFlowBucketModel } from './walletFlowBucket.model';
import { WalletTokenFlowBucketModel } from './walletTokenFlowBucket.model';
import { WalletCounterpartyFlowBucketModel } from './walletCounterpartyFlowBucket.model';

const STABLECOINS = new Set([
  '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
  '0xdac17f958d2ee523a2206206994597c13d831ec7',
  '0x6b175474e89094c44da98b954eedeac495271d0f',
  '0x4fabb145d64652a948d72533023f6e7a623c7c53',
]);

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

function parseValue(raw: string | number, decimals: number): number {
  if (!raw) return 0;
  const s = String(raw);
  if (s.length <= 15) return Number(s) / (10 ** decimals);
  if (s.length <= decimals) return Number('0.' + s.padStart(decimals, '0'));
  const intPart = s.slice(0, s.length - decimals);
  const fracPart = s.slice(s.length - decimals);
  return Number(intPart + '.' + fracPart);
}

function dayKey(ts: number): string {
  const d = new Date(ts);
  return d.toISOString().slice(0, 10);
}

function dayStart(dateStr: string): Date {
  return new Date(dateStr + 'T00:00:00.000Z');
}

interface DayAcc {
  inflowUsd: number;
  outflowUsd: number;
  netUsd: number;
  transfers: number;
  counterparties: Set<string>;
  stableUsd: number;
  topTokenUsd: number;
  topTokenSymbol: string;
}

function newDayAcc(): DayAcc {
  return {
    inflowUsd: 0, outflowUsd: 0, netUsd: 0, transfers: 0,
    counterparties: new Set(), stableUsd: 0,
    topTokenUsd: 0, topTokenSymbol: '',
  };
}

// C3: Per-token per-day accumulator
interface TokenDayAcc {
  inUsd: number;
  outUsd: number;
  netUsd: number;
  transfers: number;
  symbol: string;
}

// C3: Per-counterparty per-day accumulator
interface CpDayAcc {
  inUsd: number;
  outUsd: number;
  netUsd: number;
  transfers: number;
}

/**
 * Aggregate daily buckets for a specific wallet address.
 * Covers the last `days` days.
 * C3: Also populates per-token and per-counterparty buckets.
 */
export async function aggregateWalletBuckets(params: {
  chainId: number;
  address: string;
  days: number;
}): Promise<{ bucketsUpserted: number; tokenBuckets: number; cpBuckets: number; elapsed: number }> {
  const start = Date.now();
  const { chainId, days } = params;
  const address = params.address.toLowerCase();

  const cutoffMs = Date.now() - days * 24 * 3600_000;
  const prices = await loadPrices(chainId);

  const erc20 = mongoose.connection.collection('onchain_v2_erc20_logs');

  // Fetch in + out logs — CHAIN-FILTERED to prevent cross-chain contamination
  const [inLogs, outLogs] = await Promise.all([
    erc20.find({ to: address, chainId, indexedAt: { $gte: cutoffMs } }).limit(100_000).toArray(),
    erc20.find({ from: address, chainId, indexedAt: { $gte: cutoffMs } }).limit(100_000).toArray(),
  ]);

  // Aggregate by day (wallet-level)
  const dayMap = new Map<string, DayAcc>();

  // C3: Aggregate by day+token and day+counterparty
  const tokenDayMap = new Map<string, TokenDayAcc>(); // key: "day|tokenAddress"
  const cpDayMap = new Map<string, CpDayAcc>();       // key: "day|counterpartyAddress"

  const getDay = (ts: number) => {
    const dk = dayKey(ts);
    if (!dayMap.has(dk)) dayMap.set(dk, newDayAcc());
    return { dk, acc: dayMap.get(dk)! };
  };

  const getTokenDay = (dk: string, tokenAddr: string): TokenDayAcc => {
    const key = `${dk}|${tokenAddr}`;
    if (!tokenDayMap.has(key)) tokenDayMap.set(key, { inUsd: 0, outUsd: 0, netUsd: 0, transfers: 0, symbol: '' });
    return tokenDayMap.get(key)!;
  };

  const getCpDay = (dk: string, cpAddr: string): CpDayAcc => {
    const key = `${dk}|${cpAddr}`;
    if (!cpDayMap.has(key)) cpDayMap.set(key, { inUsd: 0, outUsd: 0, netUsd: 0, transfers: 0 });
    return cpDayMap.get(key)!;
  };

  for (const log of inLogs) {
    const tokenAddr = String(log.tokenAddress || '').toLowerCase();
    const fromAddr = String(log.from || '').toLowerCase();
    const price = prices.get(tokenAddr);
    const amount = parseValue(log.value || '0', price?.decimals ?? 18);
    if (amount <= 0 || !isFinite(amount)) continue;
    const usd = (price?.usd ?? 0) * amount;
    if (!isFinite(usd)) continue;

    const ts = Number(log.indexedAt || log.blockTimestamp || Date.now());
    const { dk, acc: day } = getDay(ts);
    day.inflowUsd += usd;
    day.netUsd += usd;
    day.transfers++;
    if (fromAddr && fromAddr !== address) day.counterparties.add(fromAddr);
    if (STABLECOINS.has(tokenAddr)) day.stableUsd += usd;
    if (usd > day.topTokenUsd) {
      day.topTokenUsd = usd;
      day.topTokenSymbol = price?.symbol || '';
    }

    // C3: Token bucket
    const ta = getTokenDay(dk, tokenAddr);
    ta.inUsd += usd;
    ta.netUsd += usd;
    ta.transfers++;
    if (!ta.symbol && price?.symbol) ta.symbol = price.symbol;

    // C3: Counterparty bucket
    if (fromAddr && fromAddr !== address) {
      const cp = getCpDay(dk, fromAddr);
      cp.inUsd += usd;
      cp.netUsd += usd;
      cp.transfers++;
    }
  }

  for (const log of outLogs) {
    const tokenAddr = String(log.tokenAddress || '').toLowerCase();
    const toAddr = String(log.to || '').toLowerCase();
    const price = prices.get(tokenAddr);
    const amount = parseValue(log.value || '0', price?.decimals ?? 18);
    if (amount <= 0 || !isFinite(amount)) continue;
    const usd = (price?.usd ?? 0) * amount;
    if (!isFinite(usd)) continue;

    const ts = Number(log.indexedAt || log.blockTimestamp || Date.now());
    const { dk, acc: day } = getDay(ts);
    day.outflowUsd += usd;
    day.netUsd -= usd;
    day.transfers++;
    if (toAddr && toAddr !== address) day.counterparties.add(toAddr);
    if (STABLECOINS.has(tokenAddr)) day.stableUsd += usd;

    // C3: Token bucket
    const ta = getTokenDay(dk, tokenAddr);
    ta.outUsd += usd;
    ta.netUsd -= usd;
    ta.transfers++;
    if (!ta.symbol && price?.symbol) ta.symbol = price.symbol;

    // C3: Counterparty bucket
    if (toAddr && toAddr !== address) {
      const cp = getCpDay(dk, toAddr);
      cp.outUsd += usd;
      cp.netUsd -= usd;
      cp.transfers++;
    }
  }

  // Upsert wallet-level day buckets
  let bucketsUpserted = 0;
  const ops = [];

  for (const [dk, acc] of dayMap.entries()) {
    ops.push({
      updateOne: {
        filter: { chainId, address, bucketDate: dk },
        update: {
          $set: {
            chainId,
            address,
            bucketDate: dk,
            bucketStart: dayStart(dk),
            inflowUsd: acc.inflowUsd,
            outflowUsd: acc.outflowUsd,
            netUsd: acc.netUsd,
            transfers: acc.transfers,
            uniqueCounterparties: acc.counterparties.size,
            stableUsd: acc.stableUsd,
            topToken: acc.topTokenSymbol,
            updatedAt: new Date(),
          },
        },
        upsert: true,
      },
    });
    bucketsUpserted++;
  }

  if (ops.length > 0) {
    await WalletFlowBucketModel.bulkWrite(ops);
  }

  // C3: Upsert per-token daily buckets
  let tokenBuckets = 0;
  const tokenOps = [];

  for (const [key, acc] of tokenDayMap.entries()) {
    const [dk, tokenAddr] = key.split('|');
    tokenOps.push({
      updateOne: {
        filter: { chainId, walletAddress: address, tokenAddress: tokenAddr, bucketDate: dk },
        update: {
          $set: {
            chainId,
            walletAddress: address,
            tokenAddress: tokenAddr,
            tokenSymbol: acc.symbol,
            bucketDate: dk,
            bucketTs: dayStart(dk),
            inUsd: acc.inUsd,
            outUsd: acc.outUsd,
            netUsd: acc.netUsd,
            transfers: acc.transfers,
            updatedAt: new Date(),
          },
        },
        upsert: true,
      },
    });
    tokenBuckets++;
  }

  if (tokenOps.length > 0) {
    // Chunk to avoid hitting 100k ops limit
    const chunkSize = 1000;
    for (let i = 0; i < tokenOps.length; i += chunkSize) {
      await WalletTokenFlowBucketModel.bulkWrite(tokenOps.slice(i, i + chunkSize));
    }
  }

  // C3: Upsert per-counterparty daily buckets
  let cpBuckets = 0;
  const cpOps = [];

  for (const [key, acc] of cpDayMap.entries()) {
    const [dk, cpAddr] = key.split('|');
    cpOps.push({
      updateOne: {
        filter: { chainId, walletAddress: address, counterpartyAddress: cpAddr, bucketDate: dk },
        update: {
          $set: {
            chainId,
            walletAddress: address,
            counterpartyAddress: cpAddr,
            bucketDate: dk,
            bucketTs: dayStart(dk),
            inUsd: acc.inUsd,
            outUsd: acc.outUsd,
            netUsd: acc.netUsd,
            transfers: acc.transfers,
            updatedAt: new Date(),
          },
        },
        upsert: true,
      },
    });
    cpBuckets++;
  }

  if (cpOps.length > 0) {
    const chunkSize = 1000;
    for (let i = 0; i < cpOps.length; i += chunkSize) {
      await WalletCounterpartyFlowBucketModel.bulkWrite(cpOps.slice(i, i + chunkSize));
    }
  }

  return { bucketsUpserted, tokenBuckets, cpBuckets, elapsed: Date.now() - start };
}

/**
 * Read pre-computed daily series for a wallet.
 */
export async function readWalletSeries(params: {
  chainId: number;
  address: string;
  days: number;
  metric: string;
}): Promise<{ ts: string; value: number }[]> {
  const { chainId, days, metric } = params;
  const address = params.address.toLowerCase();

  const cutoff = new Date(Date.now() - days * 24 * 3600_000);

  const buckets = await WalletFlowBucketModel.find(
    { chainId, address, bucketStart: { $gte: cutoff } },
    { _id: 0, bucketDate: 1, inflowUsd: 1, outflowUsd: 1, netUsd: 1, transfers: 1, uniqueCounterparties: 1, stableUsd: 1 }
  ).sort({ bucketStart: 1 }).lean();

  return buckets.map((b: any) => ({
    ts: b.bucketDate,
    value: metric === 'inflowUsd' ? b.inflowUsd
         : metric === 'outflowUsd' ? b.outflowUsd
         : metric === 'transfers' ? b.transfers
         : metric === 'counterparties' ? b.uniqueCounterparties
         : b.netUsd,
  }));
}
