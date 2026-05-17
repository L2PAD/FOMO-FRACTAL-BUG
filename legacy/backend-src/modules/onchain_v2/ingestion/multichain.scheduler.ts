/**
 * OnChain V2 — Multi-Chain Scheduler
 * ====================================
 * 
 * Unified scheduler for ERC20 and DEX ingestion across all chains.
 * Features:
 * - Concurrency limiter (p-limit)
 * - Per-chain sync state
 * - Adaptive batch sizing
 * - Health monitoring
 */

import pLimit from 'p-limit';
import { chainRegistry, getActiveChainIds } from '../chains/index.js';
import { erc20Indexer } from './erc20/index.js';
import { dexIngestionService } from './dex/index.js';
import { SyncStateModel } from './erc20/models.js';
import { rpcPool } from '../rpc-pool/index.js';

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

const SCHEDULER_INTERVAL_MS = parseInt(process.env.INDEXER_INTERVAL_MS || '15000', 10);
const MAX_CONCURRENCY = parseInt(process.env.INDEXER_CONCURRENCY || '2', 10);

// Adaptive batch sizes per chain
const BATCH_SIZES: Record<number, { erc20: number; dex: number }> = {
  1:     { erc20: 2000, dex: 1500 },   // ETH - slower, larger blocks
  42161: { erc20: 5000, dex: 4000 },   // ARB - fast
  10:    { erc20: 5000, dex: 4000 },   // OP - fast
  8453:  { erc20: 4000, dex: 3000 },   // BASE - medium
};

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

interface SchedulerStatus {
  running: boolean;
  lastTick: number;
  tickCount: number;
  activeChains: number[];
  chainStats: Map<number, ChainSyncStats>;
}

interface ChainSyncStats {
  chainId: number;
  erc20LastBlock: number;
  erc20BlocksBehind: number;
  erc20LastSync: number;
  erc20Errors: number;
  dexLastBlock: number;
  dexBlocksBehind: number;
  dexLastSync: number;
  dexErrors: number;
}

// ═══════════════════════════════════════════════════════════════
// MULTI-CHAIN SCHEDULER
// ═══════════════════════════════════════════════════════════════

class MultiChainScheduler {
  private running = false;
  private intervalId: ReturnType<typeof setInterval> | null = null;
  private limit = pLimit(MAX_CONCURRENCY);
  private tickCount = 0;
  private lastTick = 0;
  private chainStats = new Map<number, ChainSyncStats>();
  private consecutiveErrors = new Map<number, number>();

  /**
   * Start the scheduler
   */
  start(): void {
    if (this.intervalId) {
      console.log('[MultiChainScheduler] Already running');
      return;
    }

    console.log(`[MultiChainScheduler] Starting with interval=${SCHEDULER_INTERVAL_MS}ms, concurrency=${MAX_CONCURRENCY}`);
    
    // Initial tick
    this.tick();
    
    this.intervalId = setInterval(() => this.tick(), SCHEDULER_INTERVAL_MS);
  }

  /**
   * Stop the scheduler
   */
  stop(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
      console.log('[MultiChainScheduler] Stopped');
    }
  }

  /**
   * Single tick - process all active chains
   */
  private async tick(): Promise<void> {
    if (this.running) {
      console.log('[MultiChainScheduler] Previous tick still running, skipping');
      return;
    }

    this.running = true;
    this.lastTick = Date.now();
    this.tickCount++;

    try {
      const activeChains = getActiveChainIds();
      
      if (activeChains.length === 0) {
        console.log('[MultiChainScheduler] No active chains');
        return;
      }

      // Process chains with concurrency limit
      const tasks = activeChains.map(chainId => 
        this.limit(() => this.processChain(chainId))
      );

      await Promise.allSettled(tasks);

    } catch (error) {
      console.error('[MultiChainScheduler] Tick error:', error);
    } finally {
      this.running = false;
    }
  }

  /**
   * Process single chain (ERC20 + DEX)
   */
  private async processChain(chainId: number): Promise<void> {
    const chain = chainRegistry.getShort(chainId);
    
    try {
      // Get latest block
      let latestBlock = 0;
      try {
        latestBlock = await rpcPool.getBlockNumber(chainId);
      } catch (e) {
        console.error(`[MultiChainScheduler] ${chain}: Failed to get block number:`, e);
        this.incrementErrors(chainId);
        return;
      }

      // Initialize stats if needed
      if (!this.chainStats.has(chainId)) {
        this.chainStats.set(chainId, {
          chainId,
          erc20LastBlock: 0,
          erc20BlocksBehind: 0,
          erc20LastSync: 0,
          erc20Errors: 0,
          dexLastBlock: 0,
          dexBlocksBehind: 0,
          dexLastSync: 0,
          dexErrors: 0,
        });
      }

      const stats = this.chainStats.get(chainId)!;

      // Run ERC20 indexer
      try {
        const erc20Result = await erc20Indexer.sync({
          chainId,
          maxBlocksPerBatch: BATCH_SIZES[chainId]?.erc20 || 2000,
        });
        
        stats.erc20LastBlock = erc20Result.lastBlock;
        stats.erc20BlocksBehind = Math.max(0, latestBlock - erc20Result.lastBlock);
        stats.erc20LastSync = Date.now();
        
        if (erc20Result.errors.length > 0) {
          stats.erc20Errors++;
        }
        
        if (erc20Result.logsProcessed > 0) {
          console.log(`[MultiChainScheduler] ${chain} ERC20: +${erc20Result.logsProcessed} logs, block ${erc20Result.lastBlock}`);
        }
      } catch (e) {
        console.error(`[MultiChainScheduler] ${chain} ERC20 error:`, e);
        stats.erc20Errors++;
      }

      // Run DEX indexer
      try {
        const dexResult = await dexIngestionService.syncChain(chainId, {
          maxBlocks: BATCH_SIZES[chainId]?.dex || 1500,
        });
        
        if (dexResult.ok) {
          stats.dexLastBlock = dexResult.lastBlock || 0;
          stats.dexBlocksBehind = Math.max(0, latestBlock - (dexResult.lastBlock || 0));
          stats.dexLastSync = Date.now();
        }
        
        if (dexResult.swaps && dexResult.swaps > 0) {
          console.log(`[MultiChainScheduler] ${chain} DEX: +${dexResult.swaps} swaps, block ${dexResult.lastBlock}`);
        }
      } catch (e) {
        console.error(`[MultiChainScheduler] ${chain} DEX error:`, e);
        stats.dexErrors++;
      }

      // Reset consecutive errors on success
      this.consecutiveErrors.set(chainId, 0);

    } catch (error) {
      console.error(`[MultiChainScheduler] ${chain}: Process error:`, error);
      this.incrementErrors(chainId);
    }
  }

  /**
   * Increment error count for chain
   */
  private incrementErrors(chainId: number): void {
    const current = this.consecutiveErrors.get(chainId) || 0;
    this.consecutiveErrors.set(chainId, current + 1);
    
    // Log warning if too many consecutive errors
    if (current + 1 >= 5) {
      console.warn(`[MultiChainScheduler] Chain ${chainId} has ${current + 1} consecutive errors`);
    }
  }

  /**
   * Get scheduler status
   */
  getStatus(): {
    running: boolean;
    lastTick: number;
    tickCount: number;
    activeChains: number[];
    stats: Array<ChainSyncStats & { chain: string; latestBlock: number }>;
  } {
    const activeChains = getActiveChainIds();
    const stats: Array<ChainSyncStats & { chain: string; latestBlock: number }> = [];

    for (const chainId of activeChains) {
      const chainStat = this.chainStats.get(chainId);
      if (chainStat) {
        stats.push({
          ...chainStat,
          chain: chainRegistry.getShort(chainId),
          latestBlock: 0, // Will be filled by caller if needed
        });
      }
    }

    return {
      running: this.running,
      lastTick: this.lastTick,
      tickCount: this.tickCount,
      activeChains,
      stats,
    };
  }

  /**
   * Force immediate tick
   */
  async forceTick(): Promise<void> {
    await this.tick();
  }
}

// Singleton
export const multiChainScheduler = new MultiChainScheduler();

console.log('[OnChain V2] Multi-Chain Scheduler loaded');
