/**
 * Token Resolve Service — Phase D1
 * ==================================
 * Canonical token resolution: symbol/address → token metadata.
 * Single source of truth for token lookup + suggest.
 */

import mongoose from 'mongoose';
import { tokenMetaService, type TokenMeta } from '../flow/tokenMeta.service';
import {
  TOKENS_BY_CHAIN,
  getTokenFromUniverse,
  getUniverseAddresses,
} from '../flow/tokenUniverse';

export interface ResolvedToken {
  address: string;
  symbol: string;
  name: string;
  decimals: number;
  verified: boolean;
}

/**
 * Resolve a query (symbol OR address) to a canonical token.
 */
export async function resolveToken(chainId: number, query: string): Promise<ResolvedToken | null> {
  const q = query.trim();
  if (!q) return null;

  // If looks like address (0x...) → resolve by address
  if (q.startsWith('0x') && q.length >= 10) {
    const addr = q.toLowerCase();
    const meta = await tokenMetaService.get(chainId, addr);
    if (meta && meta.source !== 'unknown') {
      return {
        address: meta.address,
        symbol: meta.symbol,
        name: meta.name,
        decimals: meta.decimals,
        verified: meta.source === 'known',
      };
    }
    // Still return it even if unknown — it's an address
    return {
      address: addr,
      symbol: meta?.symbol || addr.slice(0, 10),
      name: meta?.name || 'Unknown',
      decimals: meta?.decimals ?? 18,
      verified: false,
    };
  }

  // Symbol lookup — search universe first
  const upperQ = q.toUpperCase();
  const chain = TOKENS_BY_CHAIN[chainId];
  if (chain) {
    for (const [addr, info] of Object.entries(chain)) {
      if (info.symbol.toUpperCase() === upperQ) {
        return {
          address: addr,
          symbol: info.symbol,
          name: info.name,
          decimals: info.decimals,
          verified: true,
        };
      }
    }
  }

  // Fallback: search token_registry collection
  try {
    const reg = mongoose.connection.collection('token_registry');
    const doc = await reg.findOne({
      chainId,
      symbol: { $regex: new RegExp(`^${escapeRegex(q)}$`, 'i') },
    });
    if (doc) {
      return {
        address: String(doc.address).toLowerCase(),
        symbol: doc.symbol || q,
        name: doc.name || doc.symbol || q,
        decimals: doc.decimals ?? 18,
        verified: !!doc.verified,
      };
    }
  } catch {}

  // Try TokenMetadataModel
  try {
    const { TokenMetadataModel } = await import('../../ingestion/erc20/models');
    const doc = await TokenMetadataModel.findOne({
      chainId,
      symbol: { $regex: new RegExp(`^${escapeRegex(q)}$`, 'i') },
    }).lean();
    if (doc) {
      return {
        address: String(doc.address).toLowerCase(),
        symbol: doc.symbol || q,
        name: doc.name || doc.symbol || q,
        decimals: doc.decimals ?? 18,
        verified: false,
      };
    }
  } catch {}

  return null;
}

/**
 * Suggest tokens matching a partial query (for autocomplete).
 */
export async function suggestTokens(chainId: number, query: string, limit = 10): Promise<ResolvedToken[]> {
  const q = query.trim().toLowerCase();
  if (!q) return [];

  const results: ResolvedToken[] = [];
  const seen = new Set<string>();

  // 1. Universe tokens (fast, in-memory)
  const chain = TOKENS_BY_CHAIN[chainId];
  if (chain) {
    for (const [addr, info] of Object.entries(chain)) {
      if (
        info.symbol.toLowerCase().includes(q) ||
        info.name.toLowerCase().includes(q) ||
        addr.includes(q)
      ) {
        if (!seen.has(addr)) {
          seen.add(addr);
          results.push({
            address: addr,
            symbol: info.symbol,
            name: info.name,
            decimals: info.decimals,
            verified: true,
          });
        }
      }
      if (results.length >= limit) break;
    }
  }

  if (results.length >= limit) return results.slice(0, limit);

  // 2. token_registry collection
  try {
    const reg = mongoose.connection.collection('token_registry');
    const docs = await reg.find({
      chainId,
      $or: [
        { symbol: { $regex: new RegExp(escapeRegex(q), 'i') } },
        { name: { $regex: new RegExp(escapeRegex(q), 'i') } },
      ],
    }).limit(limit - results.length).toArray();

    for (const doc of docs) {
      const addr = String(doc.address).toLowerCase();
      if (!seen.has(addr)) {
        seen.add(addr);
        results.push({
          address: addr,
          symbol: doc.symbol || '',
          name: doc.name || doc.symbol || '',
          decimals: doc.decimals ?? 18,
          verified: !!doc.verified,
        });
      }
    }
  } catch {}

  return results.slice(0, limit);
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
