/**
 * OnChain V2 — DEX Ingestion Service
 * ====================================
 * 
 * Service for ingesting DEX swap events from blockchain.
 * Currently supports Uniswap V3 on Ethereum.
 */

import { DexSwapModel, DexPoolModel, type IDexSwap, type DexProtocol } from './models.js';
import { SyncStateModel } from '../erc20/models.js';
import { rpcPool } from '../../rpc-pool/pool.service.js';
import { poolMetaResolver } from './poolMeta.resolver.js';
import { 
  UNISWAP_V3_SWAP_TOPIC, 
  decodeUniswapV3Swap, 
  determineSwapDirection,
  isWhaleSwap,
  MAINNET_POOLS,
  ARBITRUM_POOLS,
  OPTIMISM_POOLS,
  BASE_POOLS,
} from './uniswap_v3_decoder.js';
import type { RpcChainId } from '../../rpc-pool/models.js';

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

const DEX_ENABLED = process.env.ONCHAIN_DEX_ENABLED !== 'false';
const DEX_LOOKBACK_BLOCKS = parseInt(process.env.DEX_LOOKBACK_BLOCKS || '2000', 10);
const DEX_BATCH_SIZE = parseInt(process.env.DEX_BATCH_SIZE || '500', 10);

// STEP 4: Max pools to ingest per chain (limits RPC load)
const DEX_MAX_POOLS = parseInt(process.env.ONCHAIN_V2_DEX_MAX_POOLS || '100', 10);

// Default pools to index (from env or fallback to well-known pools)
function getDefaultPools(chainId: number = 1): string[] {
  if (chainId === 42161) {
    const envPools = process.env.DEX_UNISWAP_V3_POOLS_ARB;
    if (envPools) return envPools.split(',').map(p => p.trim().toLowerCase());
    return [
      ARBITRUM_POOLS.WETH_USDC_500,
      ARBITRUM_POOLS.WETH_USDC_3000,
      ARBITRUM_POOLS.ARB_USDC_500,
      ARBITRUM_POOLS.ARB_WETH_500,
    ];
  }

  if (chainId === 10) {
    const envPools = process.env.DEX_UNISWAP_V3_POOLS_OP;
    if (envPools) return envPools.split(',').map(p => p.trim().toLowerCase());
    return [
      OPTIMISM_POOLS.WETH_USDC_500,
      OPTIMISM_POOLS.WETH_USDC_3000,
      OPTIMISM_POOLS.OP_USDC_3000,
      OPTIMISM_POOLS.OP_WETH_3000,
    ];
  }

  if (chainId === 8453) {
    const envPools = process.env.DEX_UNISWAP_V3_POOLS_BASE;
    if (envPools) return envPools.split(',').map(p => p.trim().toLowerCase());
    return [
      BASE_POOLS.WETH_USDC_500,
      BASE_POOLS.WETH_USDC_3000,
      BASE_POOLS.CBETH_WETH_500,
      BASE_POOLS.DEGEN_WETH_3000,
    ];
  }
  
  const envPools = process.env.DEX_UNISWAP_V3_POOLS_ETH;
  if (envPools) {
    return envPools.split(',').map(p => p.trim().toLowerCase());
  }
  
  // Default: top 4 most liquid pools
  return [
    MAINNET_POOLS.WETH_USDC_500,
    MAINNET_POOLS.WETH_USDC_3000,
    MAINNET_POOLS.WETH_USDT_500,
    MAINNET_POOLS.WBTC_WETH_3000,
  ];
}

/**
 * STEP 4: Get pools from database registry
 * Reads pools with status ACTIVE or DEGRADED, ordered by priority/score
 */
async function getPoolsFromRegistry(chainId: number): Promise<string[]> {
  try {
    const pools = await DexPoolModel.find({
      chainId,
      enabled: true,
      status: { $in: ['ACTIVE', 'DEGRADED'] },
    })
      .sort({ priority: -1, score: -1 })
      .limit(DEX_MAX_POOLS)
      .select({ address: 1 })
      .lean();
    
    if (pools.length > 0) {
      console.log(`[DexIngestion] Found ${pools.length} pools in registry for chain ${chainId}`);
      return pools.map(p => p.address.toLowerCase());
    }
    
    // Fallback to defaults if no pools in registry
    console.log(`[DexIngestion] No pools in registry for chain ${chainId}, using defaults`);
    return getDefaultPools(chainId);
  } catch (err) {
    console.error(`[DexIngestion] Error fetching pools from registry:`, err);
    return getDefaultPools();
  }
}

// ═══════════════════════════════════════════════════════════════
// SERVICE CLASS
// ═══════════════════════════════════════════════════════════════

export class DexIngestionService {
  private chainId: RpcChainId;
  private protocol: DexProtocol = 'uniswap_v3';

  constructor(chainId: RpcChainId = 1) {
    this.chainId = chainId;
  }

  /**
   * Check if DEX ingestion is enabled
   */
  isEnabled(): boolean {
    return DEX_ENABLED;
  }

  /**
   * Get sync state key
   */
  private getSyncKey(): string {
    return `dex_${this.protocol}_${this.chainId}`;
  }

  /**
   * Get or create sync state
   */
  async getSyncState() {
    const key = this.getSyncKey();
    let state = await SyncStateModel.findOne({ key });
    
    if (!state) {
      state = await SyncStateModel.create({
        key,
        chainId: this.chainId,
        lastBlock: 0,
        lastSyncAt: Date.now(),
        totalLogsIndexed: 0,
        status: 'idle',
      });
    }
    
    return state;
  }

  /**
   * Ingest swaps from a specific block range
   */
  async ingestRange(params: {
    fromBlock: number;
    toBlock: number;
    pools?: string[];
  }): Promise<{ swapsInserted: number; errors: number }> {
    const { fromBlock, toBlock, pools = getDefaultPools() } = params;
    
    let swapsInserted = 0;
    let errors = 0;
    
    // Batch blocks to avoid RPC limits
    const batchSize = Math.min(DEX_BATCH_SIZE, toBlock - fromBlock + 1);
    
    for (let start = fromBlock; start <= toBlock; start += batchSize) {
      const end = Math.min(start + batchSize - 1, toBlock);
      
      try {
        // Get logs for all pools in this batch
        const logs = await rpcPool.getLogs(this.chainId, {
          fromBlock: start,
          toBlock: end,
          address: pools,
          topics: [UNISWAP_V3_SWAP_TOPIC],
        });

        if (logs.length === 0) continue;

        // Decode and prepare swap documents
        const swapDocs: Partial<IDexSwap>[] = [];
        
        // Pre-resolve pool metadata for all unique pools in batch
        const uniquePools = [...new Set(logs.map(l => l.address.toLowerCase()))];
        const poolMetaMap = await poolMetaResolver.getBatch(this.chainId, uniquePools);
        
        for (const log of logs) {
          // Convert hex blockNumber/logIndex to numbers
          const normalizedLog = {
            ...log,
            blockNumber: typeof log.blockNumber === 'string' ? parseInt(log.blockNumber, 16) : log.blockNumber,
            logIndex: typeof log.logIndex === 'string' ? parseInt(log.logIndex, 16) : log.logIndex,
            transactionIndex: typeof log.transactionIndex === 'string' ? parseInt(log.transactionIndex, 16) : log.transactionIndex,
          };
          
          const decoded = decodeUniswapV3Swap(normalizedLog);
          if (!decoded) continue;

          // Get pool metadata - SKIP swap if no metadata
          const poolAddr = log.address.toLowerCase();
          const poolMeta = poolMetaMap.get(poolAddr);
          
          if (!poolMeta || !poolMeta.token0 || !poolMeta.token1) {
            console.warn(`[DexIngestion] Skipping swap - no pool meta for ${poolAddr}`);
            continue;
          }

          const direction = determineSwapDirection(decoded.amount0);
          const whale = isWhaleSwap(decoded.amount0, decoded.amount1);

          swapDocs.push({
            chainId: this.chainId,
            protocol: this.protocol,
            pool: poolAddr,
            token0: poolMeta.token0,
            token1: poolMeta.token1,
            amount0: decoded.amount0,
            amount1: decoded.amount1,
            blockNumber: normalizedLog.blockNumber,
            blockTimestamp: Date.now(), // Add timestamp for flow processing
            transactionHash: log.transactionHash,
            transactionIndex: normalizedLog.transactionIndex,
            logIndex: normalizedLog.logIndex,
            sender: decoded.sender,
            recipient: decoded.recipient,
            sqrtPriceX96: decoded.sqrtPriceX96,
            liquidity: decoded.liquidity,
            tick: decoded.tick,
            direction,
            isWhaleSwap: whale,
            indexedAt: Date.now(),
          });
        }

        // Bulk upsert with idempotency
        if (swapDocs.length > 0) {
          const ops = swapDocs.map(doc => ({
            updateOne: {
              filter: { 
                chainId: doc.chainId, 
                transactionHash: doc.transactionHash, 
                logIndex: doc.logIndex,
              },
              update: { $setOnInsert: doc },
              upsert: true,
            },
          }));

          const result = await DexSwapModel.bulkWrite(ops, { ordered: false });
          swapsInserted += result.upsertedCount || 0;
        }
      } catch (err) {
        console.error(`[DexIngestion] Error in blocks ${start}-${end}:`, err);
        errors++;
      }
    }

    return { swapsInserted, errors };
  }

  /**
   * Ingest recent swaps (from last synced block to latest)
   * STEP 4: Now reads pools from DB registry (ACTIVE/DEGRADED status)
   */
  async ingestRecent(params?: {
    lookbackBlocks?: number;
    pools?: string[];
  }): Promise<{
    fromBlock: number;
    toBlock: number;
    swapsInserted: number;
    errors: number;
  }> {
    // STEP 4: Get pools from registry if not explicitly provided
    const registryPools = params?.pools || await getPoolsFromRegistry(this.chainId);
    const { lookbackBlocks = DEX_LOOKBACK_BLOCKS, pools = registryPools } = params || {};
    
    const pool = rpcPool;
    const syncState = await this.getSyncState();
    
    // Get latest block
    const latestBlock = await rpcPool.getBlockNumber(this.chainId);
    
    // Calculate range
    let fromBlock = syncState.lastBlock > 0 
      ? syncState.lastBlock + 1 
      : latestBlock - lookbackBlocks;
    
    const toBlock = latestBlock;
    
    if (fromBlock > toBlock) {
      return { fromBlock, toBlock, swapsInserted: 0, errors: 0 };
    }

    // Update sync state to 'syncing'
    await SyncStateModel.updateOne(
      { key: this.getSyncKey() },
      { $set: { status: 'syncing' } }
    );

    try {
      const result = await this.ingestRange({ fromBlock, toBlock, pools });

      // Update sync state
      await SyncStateModel.updateOne(
        { key: this.getSyncKey() },
        {
          $set: {
            lastBlock: toBlock,
            lastSyncAt: Date.now(),
            status: 'idle',
          },
          $inc: {
            totalLogsIndexed: result.swapsInserted,
          },
        }
      );

      return { fromBlock, toBlock, ...result };
    } catch (err) {
      // Update sync state with error
      await SyncStateModel.updateOne(
        { key: this.getSyncKey() },
        {
          $set: {
            status: 'error',
            lastError: err instanceof Error ? err.message : 'Unknown error',
            lastErrorAt: Date.now(),
          },
        }
      );
      throw err;
    }
  }

  /**
   * Get current status
   * STEP 4: Now shows pools from registry
   */
  async getStatus(): Promise<{
    enabled: boolean;
    chainId: RpcChainId;
    protocol: DexProtocol;
    lastBlock: number;
    latestBlock: number;
    blocksBehind: number;
    totalSwapsIndexed: number;
    status: string;
    lastSyncAt: number;
    pools: string[];
    activePools: number;
    lastError?: string;
  }> {
    const syncState = await this.getSyncState();
    const pool = rpcPool;
    
    let latestBlock = 0;
    try {
      latestBlock = await rpcPool.getBlockNumber(this.chainId);
    } catch {
      // RPC may be down
    }

    // STEP 4: Get pools from registry
    const pools = await getPoolsFromRegistry(this.chainId);

    return {
      enabled: this.isEnabled(),
      chainId: this.chainId,
      protocol: this.protocol,
      lastBlock: syncState.lastBlock,
      latestBlock,
      blocksBehind: Math.max(0, latestBlock - syncState.lastBlock),
      totalSwapsIndexed: syncState.totalLogsIndexed,
      status: syncState.status,
      lastSyncAt: syncState.lastSyncAt,
      pools,
      activePools: pools.length,
      lastError: syncState.lastError,
    };
  }

  /**
   * Get swap counts for a time window
   */
  async getSwapStats(params: {
    fromBlock?: number;
    toBlock?: number;
    pool?: string;
    windowMs?: number;
  }): Promise<{
    totalSwaps: number;
    buyCount: number;
    sellCount: number;
    whaleSwaps: number;
    uniquePools: number;
  }> {
    const { pool, windowMs = 3600000 } = params;
    
    const query: any = { chainId: this.chainId };
    
    if (params.fromBlock && params.toBlock) {
      query.blockNumber = { $gte: params.fromBlock, $lte: params.toBlock };
    } else if (windowMs) {
      query.indexedAt = { $gte: Date.now() - windowMs };
    }
    
    if (pool) {
      query.pool = pool.toLowerCase();
    }

    const [stats] = await DexSwapModel.aggregate([
      { $match: query },
      {
        $group: {
          _id: null,
          totalSwaps: { $sum: 1 },
          buyCount: { $sum: { $cond: [{ $eq: ['$direction', 'buy'] }, 1, 0] } },
          sellCount: { $sum: { $cond: [{ $eq: ['$direction', 'sell'] }, 1, 0] } },
          whaleSwaps: { $sum: { $cond: ['$isWhaleSwap', 1, 0] } },
          uniquePools: { $addToSet: '$pool' },
        },
      },
      {
        $project: {
          _id: 0,
          totalSwaps: 1,
          buyCount: 1,
          sellCount: 1,
          whaleSwaps: 1,
          uniquePools: { $size: '$uniquePools' },
        },
      },
    ]);

    return stats || {
      totalSwaps: 0,
      buyCount: 0,
      sellCount: 0,
      whaleSwaps: 0,
      uniquePools: 0,
    };
  }

  /**
   * Initialize default pools in database
   */
  async initializePools(): Promise<void> {
    const pools = getDefaultPools();
    
    for (const address of pools) {
      await DexPoolModel.updateOne(
        { chainId: this.chainId, address },
        {
          $setOnInsert: {
            chainId: this.chainId,
            protocol: this.protocol,
            address,
            token0: '',
            token1: '',
            enabled: true,
            priority: 0,
            totalSwapsIndexed: 0,
            addedAt: Date.now(),
          },
          $set: {
            updatedAt: Date.now(),
          },
        },
        { upsert: true }
      );
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// MULTI-CHAIN DEX SERVICE WRAPPER
// ═══════════════════════════════════════════════════════════════

class MultiChainDexService {
  private services = new Map<number, DexIngestionService>();

  /**
   * Get or create service for chain
   */
  private getService(chainId: number): DexIngestionService {
    if (!this.services.has(chainId)) {
      this.services.set(chainId, new DexIngestionService(chainId));
    }
    return this.services.get(chainId)!;
  }

  /**
   * Sync DEX for specific chain
   */
  async syncChain(chainId: number, options?: { maxBlocks?: number }): Promise<{
    ok: boolean;
    chainId: number;
    swaps?: number;
    lastBlock?: number;
    error?: string;
  }> {
    try {
      const service = this.getService(chainId);
      
      if (!service.isEnabled()) {
        return { ok: true, chainId, swaps: 0 };
      }

      const result = await service.ingestRecent({
        lookbackBlocks: options?.maxBlocks || 2000,
      });

      return {
        ok: true,
        chainId,
        swaps: result.swapsInserted,
        lastBlock: result.toBlock,
      };
    } catch (error) {
      return {
        ok: false,
        chainId,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  /**
   * Get status for all chains
   */
  async getAllStatus(chainIds: number[]): Promise<{
    chains: Array<{
      chainId: number;
      enabled: boolean;
      lastBlock: number;
      blocksBehind: number;
      totalSwaps: number;
      status: string;
    }>;
  }> {
    const chains = [];

    for (const chainId of chainIds) {
      try {
        const service = this.getService(chainId);
        const status = await service.getStatus();
        chains.push({
          chainId,
          enabled: status.enabled,
          lastBlock: status.lastBlock,
          blocksBehind: status.blocksBehind,
          totalSwaps: status.totalSwapsIndexed,
          status: status.status,
        });
      } catch {
        chains.push({
          chainId,
          enabled: false,
          lastBlock: 0,
          blocksBehind: 0,
          totalSwaps: 0,
          status: 'error',
        });
      }
    }

    return { chains };
  }
}

// Singleton for multi-chain DEX service
export const dexIngestionService = new MultiChainDexService();

// Singleton instance for Ethereum mainnet
let ethDexService: DexIngestionService | null = null;

export function getDexIngestionService(chainId: RpcChainId = 1): DexIngestionService {
  if (chainId === 1) {
    if (!ethDexService) {
      ethDexService = new DexIngestionService(1);
    }
    return ethDexService;
  }
  return new DexIngestionService(chainId);
}

console.log('[OnChain V2] DEX Ingestion Service loaded');
