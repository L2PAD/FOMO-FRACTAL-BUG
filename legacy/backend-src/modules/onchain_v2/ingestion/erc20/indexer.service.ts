/**
 * OnChain V2 — ERC20 Indexer Service
 * ====================================
 * 
 * Syncs ERC20 Transfer logs from blockchain.
 * 
 * FEATURES:
 * - Adaptive batch sizing (reduces on "too many results")
 * - Idempotent (txHash + logIndex unique)
 * - Automatic timestamp batching
 * - Exchange wallet labeling
 * - Chunked backfill with progress tracking
 * - Rate-limit safety with pause
 */

import { rpcPool } from '../../rpc-pool/index.js';
import type { RpcChainId } from '../../rpc-pool/models.js';
import { 
  ERC20LogModel, 
  SyncStateModel, 
  TokenMetadataModel,
  AddressLabelModel,
} from './models.js';
import type { IERC20Log, ISyncState } from './models.js';

// ═══════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════

// ERC20 Transfer topic: Transfer(address,address,uint256)
const TRANSFER_TOPIC = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef';

// Default block ranges
const DEFAULT_MAX_BLOCKS = 100;
const MIN_BLOCKS_PER_BATCH = 5;
const DEFAULT_START_OFFSET = 10;

// Backfill settings
const BACKFILL_CHUNK_BLOCKS = 500;
const BACKFILL_SLEEP_MS = 300;
const BACKFILL_MAX_MINUTES = 20;
const RATE_LIMIT_PAUSE_MS = 60000;

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

interface SyncOptions {
  chainId: number;
  fromBlock?: number;
  toBlock?: number;
  maxBlocksPerBatch?: number;
  tokenAddresses?: string[];
  sleepMs?: number;
}

interface SyncResult {
  chainId: RpcChainId;
  logsProcessed: number;
  blocksProcessed: number;
  lastBlock: number;
  duration: number;
  errors: string[];
}

interface RawLog {
  address: string;
  topics: string[];
  data: string;
  blockNumber: string;
  transactionHash: string;
  logIndex: string;
  blockHash: string;
  transactionIndex: string;
}

// ═══════════════════════════════════════════════════════════════
// ERC20 INDEXER SERVICE
// ═══════════════════════════════════════════════════════════════

export class ERC20IndexerService {
  private syncLocks: Map<RpcChainId, boolean> = new Map();
  private addressLabelCache: Map<string, string | null> = new Map();
  
  /**
   * Run sync for a chain
   */
  async sync(options: SyncOptions): Promise<SyncResult> {
    const { chainId, maxBlocksPerBatch = DEFAULT_MAX_BLOCKS } = options;
    const startTime = Date.now();
    const errors: string[] = [];
    
    // Prevent concurrent syncs
    if (this.syncLocks.get(chainId)) {
      return {
        chainId,
        logsProcessed: 0,
        blocksProcessed: 0,
        lastBlock: 0,
        duration: 0,
        errors: ['Sync already in progress'],
      };
    }
    
    this.syncLocks.set(chainId, true);
    
    try {
      // Get or create sync state
      const stateKey = `erc20_${chainId}`;
      let state = await SyncStateModel.findOne({ key: stateKey });
      
      if (!state) {
        state = new SyncStateModel({
          key: stateKey,
          chainId,
          lastBlock: 0,
          totalLogsIndexed: 0,
          status: 'idle',
        });
      }
      
      // Update status
      state.status = 'syncing';
      state.lastSyncAt = Date.now();
      await state.save();
      
      // Get latest block
      const latestBlock = await rpcPool.getBlockNumber(chainId);
      
      // Determine range
      let fromBlock = options.fromBlock ?? (state.lastBlock + 1);
      const toBlock = options.toBlock ?? (latestBlock - DEFAULT_START_OFFSET);
      
      if (fromBlock === 0) {
        // Start from recent blocks if no previous state
        fromBlock = Math.max(1, toBlock - 10000);
      }
      
      if (fromBlock > toBlock) {
        state.status = 'idle';
        await state.save();
        
        return {
          chainId,
          logsProcessed: 0,
          blocksProcessed: 0,
          lastBlock: state.lastBlock,
          duration: Date.now() - startTime,
          errors: [],
        };
      }
      
      console.log(`[ERC20Indexer] Syncing chain ${chainId}: blocks ${fromBlock} → ${toBlock}`);
      
      let totalLogs = 0;
      let currentBlock = fromBlock;
      let batchSize = maxBlocksPerBatch;
      
      while (currentBlock <= toBlock) {
        const batchEnd = Math.min(currentBlock + batchSize - 1, toBlock);
        
        try {
          const logs = await this.fetchAndStoreLogs(chainId, currentBlock, batchEnd, options.tokenAddresses);
          totalLogs += logs;
          currentBlock = batchEnd + 1;
          
          // Update state after each batch
          state.lastBlock = batchEnd;
          state.totalLogsIndexed += logs;
          await state.save();
          
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          console.error(`[ERC20Backfill] Error at blocks ${currentBlock}-${batchEnd}:`, message);
          
          // Handle "too many results" by reducing batch size
          if (message.includes('too many') || message.includes('query returned more')) {
            batchSize = Math.max(MIN_BLOCKS_PER_BATCH, Math.floor(batchSize / 2));
            console.log(`[ERC20Backfill] Reducing batch size to ${batchSize}`);
            continue;
          }
          
          errors.push(`Block ${currentBlock}-${batchEnd}: ${message}`);
          
          // Skip this batch and continue
          currentBlock = batchEnd + 1;
          
          if (errors.length > 10) {
            state.status = 'error';
            state.lastError = 'Too many errors';
            state.lastErrorAt = Date.now();
            await state.save();
            break;
          }
        }
      }
      
      // Update final state
      state.status = errors.length > 0 ? 'error' : 'idle';
      if (errors.length > 0) {
        state.lastError = errors[errors.length - 1];
        state.lastErrorAt = Date.now();
      }
      await state.save();
      
      const result = {
        chainId,
        logsProcessed: totalLogs,
        blocksProcessed: toBlock - fromBlock + 1,
        lastBlock: toBlock,
        duration: Date.now() - startTime,
        errors,
      };
      
      console.log(`[ERC20Indexer] Sync complete: ${totalLogs} logs in ${result.duration}ms`);
      
      return result;
      
    } finally {
      this.syncLocks.set(chainId, false);
    }
  }
  
  /**
   * Fetch logs and store in DB
   */
  private async fetchAndStoreLogs(
    chainId: RpcChainId,
    fromBlock: number,
    toBlock: number,
    tokenAddresses?: string[]
  ): Promise<number> {
    const logs = await rpcPool.getLogs(chainId, {
      fromBlock,
      toBlock,
      topics: [TRANSFER_TOPIC],
      address: tokenAddresses,
    });
    
    if (logs.length === 0) return 0;
    
    // Parse and deduplicate
    const parsedLogs = await this.parseLogs(chainId, logs);
    
    // Bulk upsert
    const bulkOps = parsedLogs.map(log => ({
      updateOne: {
        filter: {
          chainId: log.chainId,
          transactionHash: log.transactionHash,
          logIndex: log.logIndex,
        },
        update: { $setOnInsert: log },
        upsert: true,
      },
    }));
    
    if (bulkOps.length > 0) {
      await ERC20LogModel.bulkWrite(bulkOps, { ordered: false });
    }
    
    return parsedLogs.length;
  }
  
  /**
   * Parse raw logs to model format
   */
  private async parseLogs(chainId: RpcChainId, rawLogs: RawLog[]): Promise<Partial<IERC20Log>[]> {
    const parsed: Partial<IERC20Log>[] = [];
    
    for (const log of rawLogs) {
      if (log.topics.length < 3) continue;
      
      const from = '0x' + log.topics[1].slice(26).toLowerCase();
      const to = '0x' + log.topics[2].slice(26).toLowerCase();
      const value = log.data === '0x' ? '0' : BigInt(log.data).toString();
      
      // Get labels from cache
      const fromLabel = await this.getAddressLabel(chainId, from);
      const toLabel = await this.getAddressLabel(chainId, to);
      
      parsed.push({
        chainId,
        blockNumber: parseInt(log.blockNumber, 16),
        blockHash: log.blockHash,
        transactionHash: log.transactionHash.toLowerCase(),
        transactionIndex: parseInt(log.transactionIndex, 16),
        logIndex: parseInt(log.logIndex, 16),
        tokenAddress: log.address.toLowerCase(),
        from,
        to,
        value,
        fromLabel: fromLabel || undefined,
        toLabel: toLabel || undefined,
        indexedAt: Date.now(),
      });
    }
    
    return parsed;
  }
  
  /**
   * Get address label (cached)
   */
  private async getAddressLabel(chainId: RpcChainId, address: string): Promise<string | null> {
    const cacheKey = `${chainId}:${address}`;
    
    if (this.addressLabelCache.has(cacheKey)) {
      return this.addressLabelCache.get(cacheKey) || null;
    }
    
    const label = await AddressLabelModel.findOne({ chainId, address });
    const labelStr = label ? `${label.type}:${label.name}` : null;
    
    this.addressLabelCache.set(cacheKey, labelStr);
    return labelStr;
  }
  
  /**
   * Get sync status for all chains
   */
  async getStatus(): Promise<{
    chains: Array<{
      chainId: RpcChainId;
      lastBlock: number;
      latestBlock: number;
      behind: number;
      totalLogs: number;
      status: string;
      lastSyncAt: number;
    }>;
    totalLogs: number;
  }> {
    const states = await SyncStateModel.find({});
    const chains: Array<{
      chainId: RpcChainId;
      lastBlock: number;
      latestBlock: number;
      behind: number;
      totalLogs: number;
      status: string;
      lastSyncAt: number;
    }> = [];
    
    let totalLogs = 0;
    
    for (const state of states) {
      let latestBlock = 0;
      try {
        latestBlock = await rpcPool.getBlockNumber(state.chainId);
      } catch {
        // Ignore
      }
      
      const behind = Math.max(0, latestBlock - state.lastBlock);
      totalLogs += state.totalLogsIndexed;
      
      chains.push({
        chainId: state.chainId,
        lastBlock: state.lastBlock,
        latestBlock,
        behind,
        totalLogs: state.totalLogsIndexed,
        status: state.status,
        lastSyncAt: state.lastSyncAt,
      });
    }
    
    return { chains, totalLogs };
  }
  
  /**
   * Run backfill for a specific range (chunked with progress tracking)
   */
  async backfill(options: {
    chainId: number;
    fromBlock: number;
    toBlock: number;
    tokenAddresses?: string[];
    chunkBlocks?: number;
    sleepMs?: number;
    maxMinutes?: number;
  }): Promise<BackfillResult> {
    const {
      chainId,
      fromBlock,
      toBlock,
      tokenAddresses,
      chunkBlocks = BACKFILL_CHUNK_BLOCKS,
      sleepMs = BACKFILL_SLEEP_MS,
      maxMinutes = BACKFILL_MAX_MINUTES,
    } = options;
    
    const stateKey = `erc20_backfill_${chainId}`;
    const startTime = Date.now();
    const deadline = startTime + maxMinutes * 60 * 1000;
    
    // Initialize or get backfill state
    let state = await SyncStateModel.findOne({ key: stateKey });
    if (!state) {
      state = new SyncStateModel({
        key: stateKey,
        chainId,
        lastBlock: fromBlock - 1,
        totalLogsIndexed: 0,
        status: 'backfilling',
      });
    }
    
    state.status = 'backfilling';
    state.lastSyncAt = Date.now();
    await state.save();
    
    let currentBlock = Math.max(fromBlock, state.lastBlock + 1);
    let totalLogs = 0;
    let batchSize = chunkBlocks;
    let consecutiveErrors = 0;
    let pausedReason: string | null = null;
    const errors: string[] = [];
    
    console.log(`[ERC20Backfill] Starting: blocks ${currentBlock} → ${toBlock} (chain ${chainId})`);
    
    while (currentBlock <= toBlock) {
      // Check deadline
      if (Date.now() > deadline) {
        console.log(`[ERC20Backfill] Deadline reached after ${maxMinutes} minutes`);
        break;
      }
      
      const batchEnd = Math.min(currentBlock + batchSize - 1, toBlock);
      
      try {
        const logs = await this.fetchAndStoreLogs(chainId, currentBlock, batchEnd, tokenAddresses);
        totalLogs += logs;
        consecutiveErrors = 0;
        pausedReason = null;
        
        // Update state
        state.lastBlock = batchEnd;
        state.totalLogsIndexed += logs;
        state.lastSyncAt = Date.now();
        await state.save();
        
        currentBlock = batchEnd + 1;
        
        // Progress log every 10k blocks
        if ((batchEnd - fromBlock) % 10000 < batchSize) {
          const progress = ((batchEnd - fromBlock) / (toBlock - fromBlock) * 100).toFixed(1);
          console.log(`[ERC20Backfill] Progress: ${progress}% (block ${batchEnd}, ${totalLogs} logs)`);
        }
        
        // Sleep between batches
        if (sleepMs > 0 && currentBlock <= toBlock) {
          await this.sleep(sleepMs);
        }
        
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        consecutiveErrors++;
        
        // Handle "too many results" by reducing batch size
        if (message.includes('too many') || message.includes('query returned more')) {
          batchSize = Math.max(MIN_BLOCKS_PER_BATCH, Math.floor(batchSize / 2));
          console.log(`[ERC20Backfill] Reducing batch size to ${batchSize}`);
          continue;
        }
        
        // Rate limit detection
        if (message.includes('429') || message.includes('rate limit')) {
          pausedReason = 'Rate limited - pausing 60s';
          console.warn(`[ERC20Backfill] ${pausedReason}`);
          await this.sleep(RATE_LIMIT_PAUSE_MS);
          continue;
        }
        
        errors.push(`Block ${currentBlock}-${batchEnd}: ${message}`);
        
        // Too many consecutive errors - pause
        if (consecutiveErrors >= 5) {
          pausedReason = 'Too many consecutive errors';
          state.status = 'error';
          state.lastError = pausedReason;
          state.lastErrorAt = Date.now();
          await state.save();
          break;
        }
        
        // Skip this batch
        currentBlock = batchEnd + 1;
      }
    }
    
    // Finalize
    const isComplete = currentBlock > toBlock;
    state.status = isComplete ? 'idle' : (pausedReason ? 'error' : 'idle');
    if (pausedReason) {
      state.lastError = pausedReason;
      state.lastErrorAt = Date.now();
    }
    await state.save();
    
    const result: BackfillResult = {
      chainId,
      fromBlock,
      toBlock,
      processedBlocks: currentBlock - fromBlock,
      remainingBlocks: Math.max(0, toBlock - currentBlock + 1),
      logsInserted: totalLogs,
      duration: Date.now() - startTime,
      isComplete,
      pausedReason,
      errors,
    };
    
    console.log(`[ERC20Backfill] Done: ${result.processedBlocks} blocks, ${totalLogs} logs, ${result.duration}ms`);
    
    return result;
  }
  
  /**
   * Get backfill status
   */
  async getBackfillStatus(chainId: number): Promise<BackfillStatus | null> {
    const stateKey = `erc20_backfill_${chainId}`;
    const state = await SyncStateModel.findOne({ key: stateKey });
    
    if (!state) return null;
    
    let latestBlock = 0;
    try {
      latestBlock = await rpcPool.getBlockNumber(chainId);
    } catch {
      // Ignore
    }
    
    const totalLogs = await ERC20LogModel.countDocuments({ chainId });
    
    return {
      chainId,
      lastProcessedBlock: state.lastBlock,
      latestBlock,
      remainingBlocks: Math.max(0, latestBlock - state.lastBlock),
      totalLogsIndexed: state.totalLogsIndexed,
      totalLogsInDb: totalLogs,
      status: state.status,
      lastError: state.lastError,
      lastSyncAt: state.lastSyncAt,
      eta: this.estimateEta(state.lastBlock, latestBlock, state.lastSyncAt),
    };
  }
  
  /**
   * Estimate time remaining
   */
  private estimateEta(lastBlock: number, latestBlock: number, lastSyncAt: number): string | null {
    if (lastBlock === 0 || lastSyncAt === 0) return null;
    
    const remaining = latestBlock - lastBlock;
    if (remaining <= 0) return 'Complete';
    
    // Rough estimate: ~1000 blocks/minute with current settings
    const blocksPerMin = 1000;
    const minutes = Math.ceil(remaining / blocksPerMin);
    
    if (minutes > 60) {
      return `~${Math.ceil(minutes / 60)}h`;
    }
    return `~${minutes}m`;
  }
  
  /**
   * Reset sync state (admin only)
   */
  async reset(chainId: number): Promise<void> {
    const stateKey = `erc20_${chainId}`;
    const backfillKey = `erc20_backfill_${chainId}`;
    await SyncStateModel.deleteMany({ key: { $in: [stateKey, backfillKey] } });
    await ERC20LogModel.deleteMany({ chainId });
    console.log(`[ERC20Indexer] Reset chain ${chainId}`);
  }
  
  /**
   * Clear label cache
   */
  clearLabelCache(): void {
    this.addressLabelCache.clear();
  }
  
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// ═══════════════════════════════════════════════════════════════
// TYPES (exported)
// ═══════════════════════════════════════════════════════════════

export interface BackfillResult {
  chainId: number;
  fromBlock: number;
  toBlock: number;
  processedBlocks: number;
  remainingBlocks: number;
  logsInserted: number;
  duration: number;
  isComplete: boolean;
  pausedReason: string | null;
  errors: string[];
}

export interface BackfillStatus {
  chainId: number;
  lastProcessedBlock: number;
  latestBlock: number;
  remainingBlocks: number;
  totalLogsIndexed: number;
  totalLogsInDb: number;
  status: string;
  lastError?: string;
  lastSyncAt: number;
  eta: string | null;
}

// Singleton
export const erc20Indexer = new ERC20IndexerService();

console.log('[OnChain V2] ERC20 Indexer Service loaded');
