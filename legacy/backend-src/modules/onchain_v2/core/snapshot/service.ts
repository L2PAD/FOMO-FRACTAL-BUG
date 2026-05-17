/**
 * OnChain V2 — Snapshot Service
 * ==============================
 * 
 * Service for creating and managing on-chain snapshots.
 * Uses provider abstraction for data source.
 */

import {
  OnchainSnapshot,
  OnchainWindow,
  OnchainSnapshotResponse,
  ONCHAIN_THRESHOLDS,
} from '../contracts.js';

import { getOnchainProvider } from '../../providers/index.js';
import { OnchainSnapshotModel, IOnchainSnapshotDoc } from '../persistence/models.js';

// ═══════════════════════════════════════════════════════════════
// SNAPSHOT SERVICE
// ═══════════════════════════════════════════════════════════════

export class OnchainSnapshotService {
  private initialized = false;
  
  async initialize(): Promise<void> {
    if (this.initialized) return;
    
    const provider = getOnchainProvider();
    await provider.initialize();
    
    this.initialized = true;
    console.log('[OnChain V2] SnapshotService initialized');
  }
  
  async getSnapshot(
    symbol: string,
    t0?: number,
    window: OnchainWindow = '1h'
  ): Promise<OnchainSnapshotResponse> {
    await this.initialize();
    
    const effectiveT0 = t0 || Date.now();
    const normalizedSymbol = symbol.toUpperCase().replace('-', '');
    
    // Check DB for existing snapshot
    const tolerance = 60_000;
    const existing = await OnchainSnapshotModel.findOne({
      symbol: normalizedSymbol,
      window,
      t0: { $gte: effectiveT0 - tolerance, $lte: effectiveT0 + tolerance },
    });
    
    if (existing) {
      return {
        ok: true,
        snapshot: this.docToSnapshot(existing),
        source: existing.source,
        confidence: existing.sourceQuality,
        dataAvailable: existing.sourceQuality >= ONCHAIN_THRESHOLDS.MIN_USABLE_CONFIDENCE,
      };
    }
    
    // Get from provider
    const provider = getOnchainProvider();
    const snapshot = await provider.getSnapshot(normalizedSymbol, effectiveT0, window);
    
    // Store in DB
    try {
      await OnchainSnapshotModel.findOneAndUpdate(
        { symbol: normalizedSymbol, t0: effectiveT0, window },
        snapshot,
        { upsert: true }
      );
    } catch (error) {
      if ((error as any).code !== 11000) {
        console.error('[OnChain V2] Store error:', error);
      }
    }
    
    return {
      ok: true,
      snapshot,
      source: snapshot.source,
      confidence: snapshot.sourceQuality,
      dataAvailable: snapshot.sourceQuality >= ONCHAIN_THRESHOLDS.MIN_USABLE_CONFIDENCE,
    };
  }
  
  async getLatest(
    symbol: string,
    window: OnchainWindow = '1h'
  ): Promise<OnchainSnapshotResponse> {
    await this.initialize();
    
    const normalizedSymbol = symbol.toUpperCase().replace('-', '');
    
    const latest = await OnchainSnapshotModel.findOne(
      { symbol: normalizedSymbol, window },
      {},
      { sort: { t0: -1 } }
    );
    
    if (latest) {
      return {
        ok: true,
        snapshot: this.docToSnapshot(latest),
        source: latest.source,
        confidence: latest.sourceQuality,
        dataAvailable: latest.sourceQuality >= ONCHAIN_THRESHOLDS.MIN_USABLE_CONFIDENCE,
      };
    }
    
    return this.getSnapshot(normalizedSymbol, Date.now(), window);
  }
  
  private docToSnapshot(doc: IOnchainSnapshotDoc): OnchainSnapshot {
    return {
      symbol: doc.symbol,
      chain: doc.chain,
      t0: doc.t0,
      snapshotTimestamp: doc.snapshotTimestamp,
      window: doc.window,
      exchangeInflowUsd: doc.exchangeInflowUsd,
      exchangeOutflowUsd: doc.exchangeOutflowUsd,
      exchangeNetUsd: doc.exchangeNetUsd,
      netInflowUsd: doc.netInflowUsd,
      netOutflowUsd: doc.netOutflowUsd,
      netFlowUsd: doc.netFlowUsd,
      activeAddresses: doc.activeAddresses,
      txCount: doc.txCount,
      feesUsd: doc.feesUsd,
      largeTransfersCount: doc.largeTransfersCount,
      largeTransfersVolumeUsd: doc.largeTransfersVolumeUsd,
      topHolderDeltaUsd: doc.topHolderDeltaUsd,
      source: doc.source,
      sourceProvider: doc.sourceProvider,
      sourceQuality: doc.sourceQuality,
      missingFields: doc.missingFields || [],
    };
  }
}

// Singleton instance
export const snapshotService = new OnchainSnapshotService();

console.log('[OnChain V2] Snapshot Service loaded');
