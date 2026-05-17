/**
 * OnChain V2 — Bridge Indexer Service
 * =====================================
 * 
 * Indexes bridge events from L1↔L2 canonical bridges.
 * Per-track sync state, idempotent storage.
 */

import { rpcPool } from '../rpc-pool/index.js';
import { SyncStateModel } from '../ingestion/erc20/models.js';
import { BridgeEventModel } from './bridge.model.js';
import { getBridgeTracks, getTracksForChain } from './bridge.registry.js';
import { resolveContracts, STATIC_BRIDGE_ADDRESSES } from './bridge.resolver.js';
import { 
  decodeOpBridgeEvent, 
  decodeArbBridgeEvent, 
  getBridgeTopics,
  DecodedBridgeEvent,
} from './bridge.decoders.js';
import { BRIDGE_ENABLED } from './bridge.health.service.js';
import { MULTICHAIN_ENABLED } from '../chains/index.js';
import type { BridgeTrack, BridgeFamily } from './bridge.types.js';

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

const MAX_BLOCK_SPAN = 2000;
const MAX_LOGS_PER_BATCH = 10000;

// ═══════════════════════════════════════════════════════════════
// SYNC STATE HELPERS
// ═══════════════════════════════════════════════════════════════

function getSyncKey(trackId: string): string {
  return `bridge_${trackId}`;
}

async function getSyncState(trackId: string): Promise<{
  lastBlock: number;
  status: string;
}> {
  const key = getSyncKey(trackId);
  const doc = await SyncStateModel.findOne({ key }).lean();
  
  if (!doc) {
    return { lastBlock: 0, status: 'idle' };
  }
  
  return {
    lastBlock: doc.lastBlock || 0,
    status: doc.status || 'idle',
  };
}

async function updateSyncState(
  trackId: string, 
  lastBlock: number, 
  status: string,
  error?: string
): Promise<void> {
  const key = getSyncKey(trackId);
  
  await SyncStateModel.updateOne(
    { key },
    {
      $set: {
        lastBlock,
        status,
        lastSyncAt: Date.now(),
        lastError: error,
      },
      $inc: { totalLogsIndexed: 0 }, // Will be incremented separately
    },
    { upsert: true }
  );
}

async function incrementLogsIndexed(trackId: string, count: number): Promise<void> {
  const key = getSyncKey(trackId);
  await SyncStateModel.updateOne({ key }, { $inc: { totalLogsIndexed: count } });
}

// ═══════════════════════════════════════════════════════════════
// BRIDGE INDEXER CLASS
// ═══════════════════════════════════════════════════════════════

export class BridgeIndexer {
  private running = new Set<string>();

  /**
   * Check if track can be indexed
   */
  private canIndex(track: BridgeTrack): boolean {
    if (!BRIDGE_ENABLED) return false;
    if (track.watchSide === 'L2' && !MULTICHAIN_ENABLED) return false;
    return true;
  }

  /**
   * Index single track
   */
  async indexTrack(track: BridgeTrack): Promise<{
    trackId: string;
    ok: boolean;
    fromBlock?: number;
    toBlock?: number;
    eventsFound?: number;
    eventsInserted?: number;
    error?: string;
  }> {
    const { id: trackId, bridge, direction, watchChainId, contractRoles } = track;

    // Check if already running
    if (this.running.has(trackId)) {
      return { trackId, ok: false, error: 'Already running' };
    }

    // Check if can index
    if (!this.canIndex(track)) {
      return { trackId, ok: false, error: 'Track disabled' };
    }

    this.running.add(trackId);

    try {
      // Resolve contract addresses
      const contracts = await resolveContracts(contractRoles, {
        env: process.env,
        staticMap: STATIC_BRIDGE_ADDRESSES,
      });

      const addresses = contracts
        .filter(c => c.address)
        .map(c => c.address!);

      if (addresses.length === 0) {
        return { trackId, ok: false, error: 'No contract addresses resolved' };
      }

      // Get latest block
      const latestBlock = await rpcPool.getBlockNumber(watchChainId);
      
      // Get sync state
      const state = await getSyncState(trackId);
      const fromBlock = state.lastBlock + 1;

      if (fromBlock > latestBlock) {
        return { trackId, ok: true, fromBlock, toBlock: latestBlock, eventsFound: 0, eventsInserted: 0 };
      }

      const toBlock = Math.min(fromBlock + MAX_BLOCK_SPAN, latestBlock);

      // Update status
      await updateSyncState(trackId, state.lastBlock, 'syncing');

      // Get topics for this bridge
      const topics = getBridgeTopics(bridge);

      // Fetch logs
      const logs = await this.fetchLogs(watchChainId, addresses, fromBlock, toBlock, topics);

      // Decode and persist
      let eventsInserted = 0;
      if (logs.length > 0) {
        eventsInserted = await this.persistEvents(logs, track);
      }

      // Update sync state
      await updateSyncState(trackId, toBlock, 'idle');
      if (eventsInserted > 0) {
        await incrementLogsIndexed(trackId, eventsInserted);
      }

      return {
        trackId,
        ok: true,
        fromBlock,
        toBlock,
        eventsFound: logs.length,
        eventsInserted,
      };

    } catch (error) {
      const errMsg = error instanceof Error ? error.message : 'Unknown error';
      await updateSyncState(trackId, 0, 'error', errMsg);
      return { trackId, ok: false, error: errMsg };
    } finally {
      this.running.delete(trackId);
    }
  }

  /**
   * Fetch logs from RPC
   */
  private async fetchLogs(
    chainId: number,
    addresses: string[],
    fromBlock: number,
    toBlock: number,
    topics: string[]
  ): Promise<any[]> {
    // Fetch per address to avoid huge payloads
    const allLogs: any[] = [];

    for (const address of addresses) {
      try {
        const logs = await rpcPool.call<any[]>(chainId, 'eth_getLogs', [{
          address,
          fromBlock: '0x' + fromBlock.toString(16),
          toBlock: '0x' + toBlock.toString(16),
          topics: [topics], // Filter by known topics
        }]);

        if (logs && logs.length > 0) {
          allLogs.push(...logs);
        }

        // Safety limit
        if (allLogs.length >= MAX_LOGS_PER_BATCH) {
          console.warn(`[BridgeIndexer] Hit max logs limit for chain ${chainId}`);
          break;
        }
      } catch (e) {
        console.warn(`[BridgeIndexer] Error fetching logs from ${address}:`, e);
      }
    }

    return allLogs;
  }

  /**
   * Persist decoded events
   */
  private async persistEvents(logs: any[], track: BridgeTrack): Promise<number> {
    const { id: trackId, bridge, direction, watchChainId } = track;
    
    const decoder = bridge === 'ARBITRUM' ? decodeArbBridgeEvent : decodeOpBridgeEvent;
    const bulkOps: any[] = [];

    for (const log of logs) {
      try {
        const decoded = decoder({
          topics: log.topics,
          data: log.data,
          address: log.address,
        });

        if (!decoded) continue;

        const blockNumber = parseInt(log.blockNumber, 16);
        const logIndex = parseInt(log.logIndex, 16);
        const timestamp = Date.now(); // Will be enriched with block timestamp later

        bulkOps.push({
          updateOne: {
            filter: {
              chainId: watchChainId,
              txHash: log.transactionHash,
              logIndex,
            },
            update: {
              $setOnInsert: {
                chainId: watchChainId,
                txHash: log.transactionHash,
                logIndex,
                blockNumber,
                bridge,
                trackId,
                direction,
                contractAddress: log.address.toLowerCase(),
                eventName: decoded.eventName,
                tokenAddress: decoded.tokenAddress,
                amountRaw: decoded.amountRaw,
                sender: decoded.sender,
                receiver: decoded.receiver,
                isStable: decoded.isStable,
                isWhale: decoded.isWhale,
                timestamp,
              },
            },
            upsert: true,
          },
        });
      } catch (e) {
        console.warn('[BridgeIndexer] Error processing log:', e);
      }
    }

    if (bulkOps.length === 0) return 0;

    try {
      const result = await BridgeEventModel.bulkWrite(bulkOps, { ordered: false });
      return result.upsertedCount || 0;
    } catch (e: any) {
      // Handle duplicate key errors gracefully
      if (e.code === 11000) {
        console.log('[BridgeIndexer] Some duplicates skipped (idempotent)');
        return bulkOps.length; // Approximate
      }
      throw e;
    }
  }

  /**
   * Index all active tracks for a chain
   */
  async indexChain(chainId: number): Promise<{
    chainId: number;
    results: Array<{
      trackId: string;
      ok: boolean;
      eventsInserted?: number;
      error?: string;
    }>;
  }> {
    const tracks = getTracksForChain(chainId).filter(t => this.canIndex(t));
    const results = [];

    for (const track of tracks) {
      const result = await this.indexTrack(track);
      results.push({
        trackId: result.trackId,
        ok: result.ok,
        eventsInserted: result.eventsInserted,
        error: result.error,
      });
    }

    return { chainId, results };
  }

  /**
   * Index all active tracks
   */
  async indexAll(): Promise<{
    ok: boolean;
    tracks: number;
    eventsInserted: number;
    errors: string[];
  }> {
    const tracks = getBridgeTracks().filter(t => this.canIndex(t));
    let totalEvents = 0;
    const errors: string[] = [];

    for (const track of tracks) {
      const result = await this.indexTrack(track);
      if (result.ok) {
        totalEvents += result.eventsInserted || 0;
      } else if (result.error) {
        errors.push(`${track.id}: ${result.error}`);
      }
    }

    return {
      ok: errors.length === 0,
      tracks: tracks.length,
      eventsInserted: totalEvents,
      errors,
    };
  }

  /**
   * Get status for all tracks
   */
  async getStatus(): Promise<Array<{
    trackId: string;
    bridge: string;
    direction: string;
    chainId: number;
    lastBlock: number;
    status: string;
    enabled: boolean;
  }>> {
    const tracks = getBridgeTracks();
    const results = [];

    for (const track of tracks) {
      const state = await getSyncState(track.id);
      results.push({
        trackId: track.id,
        bridge: track.bridge,
        direction: track.direction,
        chainId: track.watchChainId,
        lastBlock: state.lastBlock,
        status: state.status,
        enabled: this.canIndex(track),
      });
    }

    return results;
  }
}

// Singleton
export const bridgeIndexer = new BridgeIndexer();

console.log('[OnChain V2] Bridge Indexer loaded');
