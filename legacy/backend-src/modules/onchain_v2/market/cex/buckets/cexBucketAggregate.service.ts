/**
 * CEX Bucket Aggregate Service — Phase A3.2
 * ==========================================
 * Reads raw ERC20 transfer logs + registry addresses,
 * computes IN/OUT/NET per (exchange, token, window),
 * upserts results into cex_flow_buckets.
 *
 * Reuses loadPrices() / parseValue() from CexFlowService.
 */

import mongoose from 'mongoose';
import { CexFlowBucketModel, type CexWindow } from './cexFlowBucket.model';
import { AddressLabelModel } from '../../../labels/addressLabel.model';

// ── Direct collection access (same pattern as CexFlowService) ──

function getErc20Collection() {
  return mongoose.connection.collection('onchain_v2_erc20_logs');
}

// ── Price loading (reuse from CexFlowService pattern) ──

interface PriceEntry { usd: number; decimals: number; symbol: string }

async function loadPrices(chainId: number): Promise<Map<string, PriceEntry>> {
  const prices = new Map<string, PriceEntry>();

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

// ── Helpers ──

function windowToMs(w: CexWindow): number {
  if (w === '24h') return 24 * 3600_000;
  if (w === '7d') return 7 * 24 * 3600_000;
  return 30 * 24 * 3600_000;
}

// ── Accumulator row ──

interface AccRow {
  chainId: number;
  exchangeId: string;
  tokenAddress: string;
  window: CexWindow;
  bucketStart: Date;
  inAmount: number;
  outAmount: number;
  transferCount: number;
  senders: Set<string>;
  receivers: Set<string>;
}

// ── Service ──

export class CexBucketAggregateService {
  /**
   * Aggregate a single window for a chainId.
   * Reads all ERC20 logs in the window, matches against registry, writes buckets.
   */
  async aggregateWindow(p: { chainId: number; window: CexWindow }) {
    const { chainId, window } = p;
    const tag = `[CexBucket:${window}]`;
    const start = Date.now();

    // 1. Get all exchange addresses from registry
    const labels = await AddressLabelModel.find({
      chainId,
      labelType: 'EXCHANGE',
    }).lean();

    if (!labels.length) {
      console.log(`${tag} No registry addresses, skipping`);
      return { ok: true, reason: 'NO_REGISTRY_ADDRESSES', bucketsUpserted: 0 };
    }

    // Build exchange->address sets for internal transfer filter
    const exchangeAddrSets = new Map<string, Set<string>>();
    const allAddrs: string[] = [];

    for (const l of labels) {
      const addr = String((l as any).address || '').toLowerCase();
      const exId = String((l as any).entityId || '');
      if (!addr || !exId) continue;
      if (!exchangeAddrSets.has(exId)) exchangeAddrSets.set(exId, new Set());
      exchangeAddrSets.get(exId)!.add(addr);
      allAddrs.push(addr);
    }

    const allAddrSet = new Set(allAddrs);

    // 2. Time boundaries
    const cutoffMs = Date.now() - windowToMs(window);
    const bucketStart = new Date(Math.floor(Date.now() / 3600_000) * 3600_000); // floor to hour

    // 3. Load prices once
    const prices = await loadPrices(chainId);

    // 4. Query ERC20 logs: transfers involving any CEX address
    const erc20 = getErc20Collection();
    const [inLogs, outLogs] = await Promise.all([
      erc20.find({ to: { $in: allAddrs }, indexedAt: { $gte: cutoffMs } }).toArray(),
      erc20.find({ from: { $in: allAddrs }, indexedAt: { $gte: cutoffMs } }).toArray(),
    ]);

    console.log(`${tag} Loaded ${inLogs.length} in-logs, ${outLogs.length} out-logs`);

    // 5. Aggregate in-memory: (exchangeId, token) -> metrics
    const acc = new Map<string, AccRow>();

    const getOrCreate = (exId: string, tokenAddr: string): AccRow => {
      const k = `${exId}|${tokenAddr}`;
      if (!acc.has(k)) {
        acc.set(k, {
          chainId, exchangeId: exId, tokenAddress: tokenAddr,
          window, bucketStart,
          inAmount: 0, outAmount: 0, transferCount: 0,
          senders: new Set(), receivers: new Set(),
        });
      }
      return acc.get(k)!;
    };

    const findExchange = (addr: string): string | null => {
      for (const [exId, set] of exchangeAddrSets.entries()) {
        if (set.has(addr)) return exId;
      }
      return null;
    };

    // IN logs: to is a CEX address (deposit)
    for (const log of inLogs) {
      const toAddr = String(log.to || '').toLowerCase();
      const fromAddr = String(log.from || '').toLowerCase();
      const exTo = findExchange(toAddr);
      if (!exTo) continue;

      // Internal filter: skip if sender is also same exchange
      if (exchangeAddrSets.get(exTo)?.has(fromAddr)) continue;

      const tokenAddr = String(log.tokenAddress || '').toLowerCase();
      const price = prices.get(tokenAddr);
      const amount = parseValue(log.value || '0', price?.decimals ?? 18);
      if (amount <= 0 || !isFinite(amount)) continue;

      const row = getOrCreate(exTo, tokenAddr);
      row.inAmount += amount;
      row.transferCount++;
      row.senders.add(fromAddr);
      row.receivers.add(toAddr);
    }

    // OUT logs: from is a CEX address (withdrawal)
    for (const log of outLogs) {
      const fromAddr = String(log.from || '').toLowerCase();
      const toAddr = String(log.to || '').toLowerCase();
      const exFrom = findExchange(fromAddr);
      if (!exFrom) continue;

      // Internal filter
      if (exchangeAddrSets.get(exFrom)?.has(toAddr)) continue;

      const tokenAddr = String(log.tokenAddress || '').toLowerCase();
      const price = prices.get(tokenAddr);
      const amount = parseValue(log.value || '0', price?.decimals ?? 18);
      if (amount <= 0 || !isFinite(amount)) continue;

      const row = getOrCreate(exFrom, tokenAddr);
      row.outAmount += amount;
      row.transferCount++;
      row.senders.add(fromAddr);
      row.receivers.add(toAddr);
    }

    // 6. Build bulkWrite ops with USD pricing
    const bulk: any[] = [];
    for (const row of acc.values()) {
      const price = prices.get(row.tokenAddress);
      const px = price?.usd ?? 0;
      const symbol = price?.symbol ?? '';
      const inflowUsd = row.inAmount * px;
      const outflowUsd = row.outAmount * px;
      const netUsd = inflowUsd - outflowUsd;

      // NaN/Inf guard
      if (![inflowUsd, outflowUsd, netUsd].every(n => isFinite(n))) continue;

      bulk.push({
        updateOne: {
          filter: {
            chainId: row.chainId,
            exchangeId: row.exchangeId,
            tokenAddress: row.tokenAddress,
            window: row.window,
            bucketStart: row.bucketStart,
          },
          update: {
            $set: {
              inflowUsd, outflowUsd, netUsd,
              transferCount: row.transferCount,
              uniqueSenders: row.senders.size,
              uniqueReceivers: row.receivers.size,
              tokenSymbol: symbol,
              updatedAt: new Date(),
            },
          },
          upsert: true,
        },
      });
    }

    if (bulk.length) {
      await CexFlowBucketModel.bulkWrite(bulk, { ordered: false });
    }

    const elapsed = Date.now() - start;
    console.log(`${tag} Done: ${bulk.length} buckets upserted (${elapsed}ms)`);

    return {
      ok: true,
      chainId, window, bucketStart,
      transfersSeen: inLogs.length + outLogs.length,
      bucketsUpserted: bulk.length,
      elapsed,
    };
  }
}
