/**
 * OnChain V2 — Stablecoin Mint/Burn Indexer
 * ==========================================
 * 
 * Indexes USDT/USDC mint/burn events across all chains.
 * Mint: Transfer from 0x0
 * Burn: Transfer to 0x0
 */

import { rpcPool } from '../rpc-pool/index.js';
import { SyncStateModel } from '../ingestion/erc20/models.js';
import { StableMintBurnModel } from './stable_mintburn.model.js';
import { getStablecoinsForChain, STABLE_MINTBURN_ENABLED } from './stable_registry.js';
import { decodeMintBurn, normalizeAmount, TRANSFER_TOPIC } from './stable_decoder.js';
import { chainRegistry, getActiveChainIds, MULTICHAIN_ENABLED } from '../chains/index.js';

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

const MAX_BLOCK_SPAN_ETH = 500;   // Reduced to avoid RPC limits
const MAX_BLOCK_SPAN_L2 = 2000;

// ═══════════════════════════════════════════════════════════════
// SYNC STATE HELPERS
// ═══════════════════════════════════════════════════════════════

function getSyncKey(chainId: number): string {
  return `stable_mintburn_${chainId}`;
}

async function getSyncState(chainId: number): Promise<{ lastBlock: number }> {
  const key = getSyncKey(chainId);
  const doc = await SyncStateModel.findOne({ key }).lean();
  return { lastBlock: doc?.lastBlock || 0 };
}

async function updateSyncState(chainId: number, lastBlock: number): Promise<void> {
  const key = getSyncKey(chainId);
  await SyncStateModel.updateOne(
    { key },
    {
      $set: {
        key,
        chainId,
        lastBlock,
        lastSyncAt: Date.now(),
        status: 'idle',
      },
    },
    { upsert: true }
  );
}

// ═══════════════════════════════════════════════════════════════
// INDEXER CLASS
// ═══════════════════════════════════════════════════════════════

export class StableMintBurnIndexer {
  private running = new Set<number>();

  /**
   * Check if chain can be indexed
   */
  private canIndex(chainId: number): boolean {
    if (!STABLE_MINTBURN_ENABLED) return false;
    if (chainId !== 1 && !MULTICHAIN_ENABLED) return false;
    return chainRegistry.isActive(chainId);
  }

  /**
   * Get block span for chain
   */
  private getBlockSpan(chainId: number): number {
    return chainId === 1 ? MAX_BLOCK_SPAN_ETH : MAX_BLOCK_SPAN_L2;
  }

  /**
   * Index single chain
   */
  async indexChain(chainId: number): Promise<{
    chainId: number;
    ok: boolean;
    fromBlock?: number;
    toBlock?: number;
    eventsFound?: number;
    eventsInserted?: number;
    error?: string;
  }> {
    if (this.running.has(chainId)) {
      return { chainId, ok: false, error: 'Already running' };
    }

    if (!this.canIndex(chainId)) {
      return { chainId, ok: false, error: 'Chain disabled' };
    }

    const stablecoins = getStablecoinsForChain(chainId);
    if (stablecoins.length === 0) {
      return { chainId, ok: false, error: 'No stablecoins configured' };
    }

    this.running.add(chainId);

    try {
      // Get latest block
      const latestBlock = await rpcPool.getBlockNumber(chainId);
      
      // Get sync state
      const state = await getSyncState(chainId);
      // Start from recent blocks to avoid large historical queries
      const fromBlock = state.lastBlock > 0 ? state.lastBlock + 1 : Math.max(0, latestBlock - 100);

      if (fromBlock > latestBlock) {
        return { chainId, ok: true, fromBlock, toBlock: latestBlock, eventsFound: 0, eventsInserted: 0 };
      }

      const toBlock = Math.min(fromBlock + this.getBlockSpan(chainId), latestBlock);

      // Fetch logs for all stablecoins
      let totalEvents = 0;
      let totalInserted = 0;

      for (const stable of stablecoins) {
        try {
          const logs = await rpcPool.call<any[]>(chainId, 'eth_getLogs', [{
            address: stable.address,
            fromBlock: '0x' + fromBlock.toString(16),
            toBlock: '0x' + toBlock.toString(16),
            topics: [TRANSFER_TOPIC],
          }]);

          if (logs && logs.length > 0) {
            const inserted = await this.persistEvents(logs, chainId, stable);
            totalEvents += logs.length;
            totalInserted += inserted;
          }
        } catch (e) {
          console.warn(`[StableMintBurn] Error fetching ${stable.symbol} on chain ${chainId}:`, e);
        }
      }

      // Update sync state
      await updateSyncState(chainId, toBlock);

      return {
        chainId,
        ok: true,
        fromBlock,
        toBlock,
        eventsFound: totalEvents,
        eventsInserted: totalInserted,
      };

    } catch (error) {
      return {
        chainId,
        ok: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    } finally {
      this.running.delete(chainId);
    }
  }

  /**
   * Persist mint/burn events
   */
  private async persistEvents(
    logs: any[],
    chainId: number,
    stable: { symbol: string; address: string; decimals: number }
  ): Promise<number> {
    const bulkOps: any[] = [];

    for (const log of logs) {
      const decoded = decodeMintBurn(log);
      if (!decoded) continue; // Not a mint/burn

      const blockNumber = parseInt(log.blockNumber, 16);
      const logIndex = parseInt(log.logIndex, 16);
      const timestamp = Date.now();

      const amount = normalizeAmount(decoded.rawAmount, stable.decimals);
      const usdAmount = amount; // Stables are ~$1

      bulkOps.push({
        updateOne: {
          filter: {
            chainId,
            txHash: log.transactionHash,
            logIndex,
          },
          update: {
            $setOnInsert: {
              chainId,
              token: stable.symbol,
              tokenAddress: stable.address.toLowerCase(),
              blockNumber,
              timestamp,
              txHash: log.transactionHash,
              logIndex,
              direction: decoded.direction,
              rawAmount: decoded.rawAmount,
              amount,
              usdAmount,
              participant: decoded.participant,
              decimals: stable.decimals,
            },
          },
          upsert: true,
        },
      });
    }

    if (bulkOps.length === 0) return 0;

    try {
      const result = await StableMintBurnModel.bulkWrite(bulkOps, { ordered: false });
      return result.upsertedCount || 0;
    } catch (e: any) {
      if (e.code === 11000) {
        return bulkOps.length; // Duplicates skipped
      }
      throw e;
    }
  }

  /**
   * Index all active chains
   */
  async indexAll(): Promise<{
    ok: boolean;
    results: Array<{ chainId: number; ok: boolean; eventsInserted?: number; error?: string }>;
  }> {
    const activeChains = getActiveChainIds();
    const results = [];

    for (const chainId of activeChains) {
      const result = await this.indexChain(chainId);
      results.push({
        chainId: result.chainId,
        ok: result.ok,
        eventsInserted: result.eventsInserted,
        error: result.error,
      });
    }

    return { ok: results.every(r => r.ok), results };
  }

  /**
   * Get status
   */
  async getStatus(): Promise<{
    enabled: boolean;
    chains: Array<{
      chainId: number;
      chain: string;
      enabled: boolean;
      stablecoins: number;
      lastBlock: number;
    }>;
  }> {
    const activeChains = getActiveChainIds();
    const chains = [];

    for (const chainId of [1, 42161, 10, 8453]) {
      const stablecoins = getStablecoinsForChain(chainId);
      const state = await getSyncState(chainId);
      const enabled = this.canIndex(chainId);

      chains.push({
        chainId,
        chain: chainRegistry.getShort(chainId),
        enabled,
        stablecoins: stablecoins.length,
        lastBlock: state.lastBlock,
      });
    }

    return { enabled: STABLE_MINTBURN_ENABLED, chains };
  }
}

// Singleton
export const stableMintBurnIndexer = new StableMintBurnIndexer();

console.log('[OnChain V2] Stable Mint/Burn Indexer loaded');
