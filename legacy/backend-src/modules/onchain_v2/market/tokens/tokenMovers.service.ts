/**
 * Token Movers Service — Phase D4
 * =================================
 * Top entities + top wallets moving a given token.
 * Reads from EntityFlowModel + TokenFlowModel.
 */

import mongoose from 'mongoose';
import { EntityFlowModel } from '../actors/entityFlow.model';
import { TokenFlowModel } from '../flow/flow.model';
import { resolveToken } from './tokenResolve.service';

type WindowKey = '24h' | '7d' | '30d';

interface EntityMover {
  entityId: string;
  label: string;
  attributionSource: string;
  attributionConfidence: number;
  inflowUsd: number;
  outflowUsd: number;
  netUsd: number;
  transfers: number;
}

interface WalletMover {
  address: string;
  inflowUsd: number;
  outflowUsd: number;
  netUsd: number;
  transfers: number;
}

export interface TokenMoversDTO {
  ok: true;
  tokenAddress: string;
  symbol: string;
  window: string;
  topEntities: EntityMover[];
  topWallets: WalletMover[];
}

function windowToMs(w: WindowKey): number {
  if (w === '24h') return 24 * 3600_000;
  if (w === '7d') return 7 * 24 * 3600_000;
  return 30 * 24 * 3600_000;
}

export async function getTokenMovers(params: {
  chainId: number;
  token: string;
  window?: WindowKey;
}): Promise<TokenMoversDTO | { ok: false; reason: string }> {
  const { chainId } = params;
  const window: WindowKey = (params.window || '7d') as WindowKey;

  // Resolve token
  const resolved = await resolveToken(chainId, params.token);
  if (!resolved) {
    return { ok: false, reason: 'TOKEN_NOT_FOUND' };
  }
  const tokenAddress = resolved.address.toLowerCase();
  const symbol = resolved.symbol;

  // ── Top Entities ──
  // Query EntityFlowModel for entities with token breakdown matching this token
  const topEntities: EntityMover[] = [];
  try {
    const cutoff = new Date(Date.now() - windowToMs(window));
    const entityFlows = await EntityFlowModel.find({
      chainId,
      window,
      bucketTs: { $gte: cutoff },
      'tokenBreakdown.tokenAddress': tokenAddress,
    }, { _id: 0 }).sort({ 'tokenBreakdown.netUsd': -1 }).limit(100).lean() as any[];

    // Aggregate by entityId
    const entityMap = new Map<string, EntityMover>();
    for (const ef of entityFlows) {
      const id = ef.entityId;
      if (!entityMap.has(id)) {
        entityMap.set(id, {
          entityId: id,
          label: ef.entityName || 'Unknown',
          attributionSource: ef.attributionSource || 'UNKNOWN',
          attributionConfidence: ef.attributionConfidence || 0,
          inflowUsd: 0,
          outflowUsd: 0,
          netUsd: 0,
          transfers: 0,
        });
      }
      const m = entityMap.get(id)!;
      // Find this token in breakdown
      const tb = (ef.tokenBreakdown || []).find((t: any) =>
        String(t.tokenAddress).toLowerCase() === tokenAddress
      );
      if (tb) {
        const net = tb.netUsd || 0;
        if (net > 0) m.inflowUsd += net;
        else m.outflowUsd += Math.abs(net);
        m.netUsd += net;
        m.transfers += tb.trades || 0;
      }
    }

    // Sort by abs(netUsd), top 20
    const sorted = Array.from(entityMap.values())
      .sort((a, b) => Math.abs(b.netUsd) - Math.abs(a.netUsd))
      .slice(0, 20);
    topEntities.push(...sorted);
  } catch {}

  // ── Top Wallets ──
  const topWallets: WalletMover[] = [];
  try {
    const cutoff = Date.now() - windowToMs(window);
    const flows = await TokenFlowModel.find({
      chainId,
      tokenAddress,
      blockTime: { $gte: cutoff },
    }).limit(50_000).lean() as any[];

    const walletMap = new Map<string, WalletMover>();
    for (const f of flows) {
      const addr = (f.counterparty || '').toLowerCase();
      if (!addr || addr.length < 10) continue;

      if (!walletMap.has(addr)) {
        walletMap.set(addr, { address: addr, inflowUsd: 0, outflowUsd: 0, netUsd: 0, transfers: 0 });
      }
      const w = walletMap.get(addr)!;
      const usd = Math.abs(f.usdVolume || 0);

      if (f.side === 'BUY') {
        w.inflowUsd += usd;
        w.netUsd += usd;
      } else {
        w.outflowUsd += usd;
        w.netUsd -= usd;
      }
      w.transfers++;
    }

    const sorted = Array.from(walletMap.values())
      .sort((a, b) => Math.abs(b.netUsd) - Math.abs(a.netUsd))
      .slice(0, 20);
    topWallets.push(...sorted);
  } catch {}

  return {
    ok: true,
    tokenAddress,
    symbol,
    window,
    topEntities,
    topWallets,
  };
}
