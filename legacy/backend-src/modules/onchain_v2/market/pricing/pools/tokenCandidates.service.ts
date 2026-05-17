/**
 * OnChain V2 — Token Candidates Service
 * =======================================
 * 
 * STEP 2.5.2: Extracts top tokens from DEX swaps
 * for pool discovery.
 */

import { DexSwapModel } from '../../../ingestion/dex/models';
import { DISCOVERY } from './poolScoring.constants';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface TokenCandidate {
  token: string;
  trades: number;
  volumeUsd: number;
}

// ═══════════════════════════════════════════════════════════════
// SERVICE
// ═══════════════════════════════════════════════════════════════

export class TokenCandidatesService {
  
  /**
   * Get top traded tokens from DEX swaps
   */
  async getTopTokensFromDex(args: { 
    chainId: number; 
    window: '24h' | '7d';
  }): Promise<TokenCandidate[]> {
    const { chainId, window } = args;
    const sinceMs = window === '24h' ? 24 * 60 * 60 * 1000 : 7 * 24 * 60 * 60 * 1000;
    const since = Date.now() - sinceMs;
    
    // Build aggregation pipeline
    const pipeline: any[] = [
      { 
        $match: { 
          chainId, 
          token0: { $ne: null, $exists: true },
          token1: { $ne: null, $exists: true },
          $or: [
            { blockTimestamp: { $gte: since } },
            { indexedAt: { $gte: since } },
          ],
        },
      },
      {
        $project: {
          tokens: ['$token0', '$token1'],
          volumeUsd: { $ifNull: ['$volumeUsd', 0] },
        },
      },
      { $unwind: '$tokens' },
      {
        $group: {
          _id: '$tokens',
          trades: { $sum: 1 },
          volumeUsd: { $sum: '$volumeUsd' },
        },
      },
      { 
        $match: { 
          trades: { $gte: DISCOVERY.MIN_TRADES_24H },
        },
      },
      { $sort: { trades: -1, volumeUsd: -1 } },
      { $limit: DISCOVERY.TOP_TOKENS_LIMIT },
    ];
    
    try {
      const rows = await DexSwapModel.aggregate(pipeline).allowDiskUse(true);
      
      return rows.map(r => ({
        token: String(r._id).toLowerCase(),
        trades: Number(r.trades || 0),
        volumeUsd: Number(r.volumeUsd || 0),
      }));
    } catch (error) {
      console.error('[TokenCandidatesService] Aggregation error:', error);
      return [];
    }
  }
  
  /**
   * Get token stats for a specific token
   */
  async getTokenStats(chainId: number, token: string, windowHours: number = 24): Promise<{
    trades: number;
    volumeUsd: number;
    uniquePools: number;
  }> {
    const since = Date.now() - windowHours * 60 * 60 * 1000;
    const tokenLower = token.toLowerCase();
    
    const stats = await DexSwapModel.aggregate([
      {
        $match: {
          chainId,
          $and: [
            { $or: [
              { token0: tokenLower },
              { token1: tokenLower },
            ]},
            { $or: [
              { blockTimestamp: { $gte: since } },
              { indexedAt: { $gte: since } },
            ]},
          ],
        },
      },
      {
        $group: {
          _id: null,
          trades: { $sum: 1 },
          volumeUsd: { $sum: { $ifNull: ['$volumeUsd', 0] } },
          pools: { $addToSet: '$pool' },
        },
      },
    ]);
    
    const s = stats[0] || { trades: 0, volumeUsd: 0, pools: [] };
    
    return {
      trades: s.trades,
      volumeUsd: s.volumeUsd,
      uniquePools: s.pools?.length || 0,
    };
  }
}

export const tokenCandidatesService = new TokenCandidatesService();

console.log('[OnChain V2] Token Candidates Service loaded');
