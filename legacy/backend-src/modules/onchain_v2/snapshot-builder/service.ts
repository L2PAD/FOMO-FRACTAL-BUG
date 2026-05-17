/**
 * OnChain V2 — Snapshot Builder Service
 * =======================================
 * 
 * Builds C2.1 snapshots from indexed ERC20 logs + DEX swaps.
 * Independent of external APIs - uses only indexed data.
 * 
 * METRICS COMPUTED:
 * - activeAddresses: unique (from ∪ to) in window
 * - txCount: unique txHash count
 * - transferCount: total transfer logs
 * - largeTransfersCount: top 1% by value (whale threshold)
 * - distributionSkew: top10 address concentration
 * - velocity: normalized transfer rate
 * 
 * DEX METRICS (O8.4):
 * - dexSwapCount: total swap events
 * - dexBuyCount: buy direction swaps
 * - dexSellCount: sell direction swaps
 * - dexBuySellRatio: buy/sell ratio
 * - dexWhaleSwapCount: whale swaps
 */

import { ERC20LogModel, AddressLabelModel } from '../ingestion/erc20/models.js';
import { DexSwapModel } from '../ingestion/dex/models.js';
import { OnchainObservationModel } from '../core/persistence/models.js';
import type { OnchainWindow, OnchainState } from '../core/contracts.js';
import { deriveOnchainState } from '../core/contracts.js';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

interface SnapshotMetrics {
  // Activity metrics
  activeAddresses: number;
  txCount: number;
  transferCount: number;
  
  // Whale metrics
  largeTransfersCount: number;
  largeTransfersVolumeRaw: string;  // BigInt as string
  whaleThreshold: string;
  
  // Distribution
  distributionSkew: number;  // 0-1, higher = more concentrated
  top10Share: number;        // Share of volume by top 10 addresses
  
  // Flow proxies (from exchange labels)
  exchangeInflows: number;
  exchangeOutflows: number;
  exchangeNetFlow: number;
  
  // DEX metrics (O8.4)
  dexSwapCount: number;
  dexBuyCount: number;
  dexSellCount: number;
  dexBuySellRatio: number;    // > 1 = buy pressure, < 1 = sell pressure
  dexWhaleSwapCount: number;
  dexActivity: number;         // Normalized 0-100
  dexImbalance: number;        // -1 to 1 (negative = sell pressure)
  
  // Metadata
  blockRange: { from: number; to: number };
  logCount: number;
  computedAt: number;
  completeness: number;  // 0-1, how many fields we could compute
  sourceQuality: number;
}

export interface SnapshotResult {
  symbol: string;
  chainId: number;
  window: OnchainWindow;
  t0: number;
  metrics: SnapshotMetrics;
  state: OnchainState;
  confidence: number;
  saved: boolean;
}

// ═══════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════

const WINDOW_MS: Record<OnchainWindow, number> = {
  '1h': 60 * 60 * 1000,
  '4h': 4 * 60 * 60 * 1000,
  '24h': 24 * 60 * 60 * 1000,
  '7d': 7 * 24 * 60 * 60 * 1000,
  '30d': 30 * 24 * 60 * 60 * 1000,
};

// Average blocks per window (ETH ~12s/block)
const AVG_BLOCKS_PER_MS = 1 / 12000;

// ═══════════════════════════════════════════════════════════════
// SNAPSHOT BUILDER SERVICE
// ═══════════════════════════════════════════════════════════════

export class SnapshotBuilderService {
  private exchangeAddresses: Set<string> = new Set();
  private labelsCacheTime = 0;
  
  /**
   * Build a snapshot from indexed logs + DEX swaps
   */
  async buildSnapshot(
    chainId: number,
    symbol: string,
    window: OnchainWindow,
    t0?: number
  ): Promise<SnapshotResult> {
    const now = Date.now();
    t0 = t0 || now;
    
    const windowMs = WINDOW_MS[window];
    const fromTime = t0 - windowMs;
    
    // Estimate block range (rough, since we might not have timestamps)
    const estimatedBlockRange = Math.floor(windowMs * AVG_BLOCKS_PER_MS);
    
    // Get ERC20 logs from DB
    const logs = await ERC20LogModel.find({
      chainId,
      indexedAt: { $gte: fromTime, $lte: t0 },
    }).lean();
    
    // Get DEX swaps from DB
    const dexSwaps = await DexSwapModel.find({
      chainId,
      indexedAt: { $gte: fromTime, $lte: t0 },
    }).lean();
    
    if (logs.length === 0 && dexSwaps.length === 0) {
      return this.emptySnapshot(chainId, symbol, window, t0);
    }
    
    // Load exchange labels
    await this.loadExchangeLabels(chainId);
    
    // Compute ERC20 metrics
    const erc20Metrics = await this.computeERC20Metrics(logs, chainId);
    
    // Compute DEX metrics
    const dexMetrics = this.computeDexMetrics(dexSwaps);
    
    // Merge metrics
    const metrics: SnapshotMetrics = {
      ...erc20Metrics,
      ...dexMetrics,
    };
    
    // Derive state with DEX-aware scoring
    const score = this.computeScore(metrics);
    const confidence = this.computeConfidence(metrics, dexSwaps.length);
    const state = deriveOnchainState(score, confidence);
    
    // Build drivers
    const drivers = this.computeDrivers(metrics);
    
    // Build full observation document matching schema
    const observationId = `${symbol}_${chainId}_${window}_${t0}`;
    const observation = {
      id: observationId,
      symbol,
      t0,
      window,
      
      // Snapshot (full raw data)
      snapshot: {
        symbol,
        chain: chainId === 1 ? 'ethereum' : chainId === 42161 ? 'arbitrum' : chainId === 10 ? 'optimism' : chainId === 8453 ? 'base' : chainId === 137 ? 'polygon' : 'ethereum',
        t0,
        snapshotTimestamp: now,
        window,
        activeAddresses: metrics.activeAddresses,
        txCount: metrics.txCount,
        source: 'indexed' as const,
        sourceQuality: metrics.sourceQuality,
        exchangeNetUsd: metrics.exchangeNetFlow,
        largeTransfersCount: metrics.largeTransfersCount,
        // DEX data
        dexSwapCount: metrics.dexSwapCount,
        dexBuyCount: metrics.dexBuyCount,
        dexSellCount: metrics.dexSellCount,
      },
      
      // Computed metrics
      metrics: {
        symbol,
        t0,
        window,
        flowScore: score,
        exchangePressure: metrics.exchangeNetFlow,
        whaleActivity: metrics.largeTransfersCount,
        networkHeat: metrics.activeAddresses,
        velocity: metrics.transferCount,
        distributionSkew: metrics.distributionSkew,
        dataCompleteness: metrics.completeness,
        confidence,
        drivers,
        missing: [],
        // DEX metrics
        dexActivity: metrics.dexActivity,
        dexImbalance: metrics.dexImbalance,
        dexWhaleSwaps: metrics.dexWhaleSwapCount,
      },
      
      state,
      
      diagnostics: {
        source: 'indexed',
        sourceQuality: metrics.sourceQuality,
        blockRange: metrics.blockRange,
        logCount: metrics.logCount,
        computedAt: now,
        // DEX diagnostics
        dex: {
          swaps: metrics.dexSwapCount,
          buyCount: metrics.dexBuyCount,
          sellCount: metrics.dexSellCount,
          whaleCount: metrics.dexWhaleSwapCount,
          buySellRatio: metrics.dexBuySellRatio,
        },
      },
      
      createdAt: now,
      updatedAt: now,
    };
    
    await OnchainObservationModel.findOneAndUpdate(
      { id: observationId },
      observation,
      { upsert: true }
    );
    
    return {
      symbol,
      chainId,
      window,
      t0,
      metrics,
      state,
      confidence,
      saved: true,
    };
  }
  
  /**
   * Compute ERC20 metrics from logs
   */
  private async computeERC20Metrics(logs: any[], chainId: number): Promise<Omit<SnapshotMetrics, 'dexSwapCount' | 'dexBuyCount' | 'dexSellCount' | 'dexBuySellRatio' | 'dexWhaleSwapCount' | 'dexActivity' | 'dexImbalance'>> {
    const addresses = new Set<string>();
    const txHashes = new Set<string>();
    const addressVolumes = new Map<string, bigint>();
    const values: bigint[] = [];
    
    let exchangeInflows = 0;
    let exchangeOutflows = 0;
    let totalVolume = 0n;
    
    let blockMin = Infinity;
    let blockMax = -Infinity;
    
    for (const log of logs) {
      // Track unique addresses
      addresses.add(log.from);
      addresses.add(log.to);
      
      // Track unique transactions
      txHashes.add(log.transactionHash);
      
      // Track volumes
      const value = BigInt(log.value || '0');
      values.push(value);
      totalVolume += value;
      
      // Track per-address volumes
      const fromVol = addressVolumes.get(log.from) || 0n;
      const toVol = addressVolumes.get(log.to) || 0n;
      addressVolumes.set(log.from, fromVol + value);
      addressVolumes.set(log.to, toVol + value);
      
      // Track exchange flows
      if (this.exchangeAddresses.has(log.from)) {
        exchangeOutflows++;
      }
      if (this.exchangeAddresses.has(log.to)) {
        exchangeInflows++;
      }
      
      // Track block range
      if (log.blockNumber < blockMin) blockMin = log.blockNumber;
      if (log.blockNumber > blockMax) blockMax = log.blockNumber;
    }
    
    // Compute whale threshold (top 1% by value)
    values.sort((a, b) => (a > b ? -1 : a < b ? 1 : 0));
    const percentile99Index = Math.floor(values.length * 0.01);
    const whaleThreshold = values[percentile99Index] || 0n;
    
    const largeTransfers = values.filter(v => v >= whaleThreshold);
    
    // Compute distribution skew (top 10 concentration)
    const sortedVolumes = Array.from(addressVolumes.values())
      .sort((a, b) => (a > b ? -1 : a < b ? 1 : 0));
    const top10Volume = sortedVolumes.slice(0, 10).reduce((a, b) => a + b, 0n);
    const top10Share = totalVolume > 0n 
      ? Number(top10Volume * 10000n / totalVolume) / 10000 
      : 0;
    
    // Distribution skew: 0 = even, 1 = highly concentrated
    const distributionSkew = Math.min(1, top10Share * 2); // Scale to 0-1
    
    // Completeness score
    const completeness = this.computeCompleteness(logs.length, addresses.size);
    
    return {
      activeAddresses: addresses.size,
      txCount: txHashes.size,
      transferCount: logs.length,
      
      largeTransfersCount: largeTransfers.length,
      largeTransfersVolumeRaw: largeTransfers.reduce((a, b) => a + b, 0n).toString(),
      whaleThreshold: whaleThreshold.toString(),
      
      distributionSkew,
      top10Share,
      
      exchangeInflows,
      exchangeOutflows,
      exchangeNetFlow: exchangeInflows - exchangeOutflows,
      
      blockRange: { 
        from: blockMin === Infinity ? 0 : blockMin, 
        to: blockMax === -Infinity ? 0 : blockMax 
      },
      logCount: logs.length,
      computedAt: Date.now(),
      completeness,
      sourceQuality: 1.0, // Indexed data = high quality
    };
  }
  
  /**
   * Compute DEX metrics from swaps
   */
  private computeDexMetrics(swaps: any[]): {
    dexSwapCount: number;
    dexBuyCount: number;
    dexSellCount: number;
    dexBuySellRatio: number;
    dexWhaleSwapCount: number;
    dexActivity: number;
    dexImbalance: number;
  } {
    if (swaps.length === 0) {
      return {
        dexSwapCount: 0,
        dexBuyCount: 0,
        dexSellCount: 0,
        dexBuySellRatio: 1,
        dexWhaleSwapCount: 0,
        dexActivity: 0,
        dexImbalance: 0,
      };
    }
    
    let buyCount = 0;
    let sellCount = 0;
    let whaleCount = 0;
    
    for (const swap of swaps) {
      if (swap.direction === 'buy') buyCount++;
      if (swap.direction === 'sell') sellCount++;
      if (swap.isWhaleSwap) whaleCount++;
    }
    
    const totalSwaps = swaps.length;
    
    // Buy/sell ratio: > 1 = buy pressure, < 1 = sell pressure
    const buySellRatio = sellCount > 0 
      ? buyCount / sellCount 
      : buyCount > 0 ? 2 : 1;
    
    // Normalized activity (0-100 scale)
    // 100 swaps/hour = 100 activity
    const dexActivity = Math.min(100, totalSwaps);
    
    // Imbalance: -1 to 1
    // -1 = all sells, +1 = all buys, 0 = balanced
    const dexImbalance = totalSwaps > 0 
      ? (buyCount - sellCount) / totalSwaps 
      : 0;
    
    return {
      dexSwapCount: totalSwaps,
      dexBuyCount: buyCount,
      dexSellCount: sellCount,
      dexBuySellRatio: Math.round(buySellRatio * 100) / 100,
      dexWhaleSwapCount: whaleCount,
      dexActivity,
      dexImbalance: Math.round(dexImbalance * 100) / 100,
    };
  }
  
  /**
   * Compute overall score from metrics (DEX-aware)
   */
  private computeScore(metrics: SnapshotMetrics): number {
    // Weights (can be tuned via policy later)
    const WEIGHTS = {
      activity: 0.25,      // Network activity
      whale: 0.20,         // Whale transfers
      flow: 0.20,          // Exchange flows
      dexActivity: 0.20,   // DEX swap activity
      dexImbalance: 0.15,  // Buy/sell imbalance
    };
    
    // Activity score (0-100)
    const activityScore = Math.min(100, 
      Math.log10(metrics.activeAddresses + 1) * 25 +
      Math.log10(metrics.txCount + 1) * 15
    );
    
    // Whale activity score (0-100)
    const whaleScore = Math.min(100, metrics.largeTransfersCount * 5);
    
    // Flow score (0-100)
    const flowScore = Math.min(100, Math.abs(metrics.exchangeNetFlow) * 2);
    
    // DEX activity score (already 0-100)
    const dexActivityScore = metrics.dexActivity;
    
    // DEX imbalance score (convert -1..1 to 0..100)
    // Strong imbalance = high score
    const dexImbalanceScore = Math.abs(metrics.dexImbalance) * 100;
    
    // Weighted sum (0-100 scale)
    const rawScore = 
      WEIGHTS.activity * activityScore +
      WEIGHTS.whale * whaleScore +
      WEIGHTS.flow * flowScore +
      WEIGHTS.dexActivity * dexActivityScore +
      WEIGHTS.dexImbalance * dexImbalanceScore;
    
    // Normalize to 0-1 for PSI drift compatibility
    const normalizedScore = Math.round(rawScore) / 100;
    
    return Math.min(1, Math.max(0, normalizedScore));
  }
  
  /**
   * Compute confidence with DEX boost
   */
  private computeConfidence(metrics: SnapshotMetrics, dexSwapCount: number): number {
    // Base confidence from data completeness
    let confidence = metrics.completeness;
    
    // DEX data boost
    if (dexSwapCount >= 10) {
      confidence += 0.1; // More swaps = more confidence
    }
    if (dexSwapCount >= 50) {
      confidence += 0.05;
    }
    
    // Whale swap boost
    if (metrics.dexWhaleSwapCount > 0) {
      confidence += 0.05;
    }
    
    // Cap at 1.0
    return Math.min(1, confidence);
  }
  
  /**
   * Compute drivers array from metrics (DEX-aware)
   */
  private computeDrivers(metrics: SnapshotMetrics): string[] {
    const drivers: string[] = [];
    
    // ERC20 / Exchange drivers
    if (metrics.exchangeNetFlow > 10) drivers.push('exchange_inflow');
    if (metrics.exchangeNetFlow < -10) drivers.push('exchange_outflow');
    if (metrics.largeTransfersCount > 5) drivers.push('whale_activity');
    if (metrics.activeAddresses > 100) drivers.push('high_activity');
    if (metrics.distributionSkew > 0.7) drivers.push('concentrated');
    
    // DEX drivers
    if (metrics.dexSwapCount > 0) {
      // Activity spike
      if (metrics.dexSwapCount >= 50) {
        drivers.push('dex_high_activity');
      } else if (metrics.dexSwapCount >= 20) {
        drivers.push('dex_activity_spike');
      }
      
      // Buy/sell pressure
      if (metrics.dexImbalance > 0.3) {
        drivers.push('dex_buy_pressure');
      } else if (metrics.dexImbalance < -0.3) {
        drivers.push('dex_sell_pressure');
      }
      
      // Strong imbalance
      if (Math.abs(metrics.dexImbalance) > 0.6) {
        drivers.push(metrics.dexImbalance > 0 ? 'dex_strong_buy' : 'dex_strong_sell');
      }
      
      // Whale swaps
      if (metrics.dexWhaleSwapCount > 0) {
        drivers.push('dex_whale_swaps');
      }
      
      // Ratio extremes
      if (metrics.dexBuySellRatio > 2) {
        drivers.push('dex_buy_dominant');
      } else if (metrics.dexBuySellRatio < 0.5) {
        drivers.push('dex_sell_dominant');
      }
    }
    
    return drivers;
  }
  
  /**
   * Compute data completeness
   */
  private computeCompleteness(logCount: number, addressCount: number): number {
    // Minimum thresholds for "complete" data
    const minLogs = 100;
    const minAddresses = 50;
    
    const logCompleteness = Math.min(1, logCount / minLogs);
    const addressCompleteness = Math.min(1, addressCount / minAddresses);
    
    return (logCompleteness + addressCompleteness) / 2;
  }
  
  /**
   * Load exchange addresses from labels
   */
  private async loadExchangeLabels(chainId: number): Promise<void> {
    // Cache for 5 minutes
    if (Date.now() - this.labelsCacheTime < 300000) return;
    
    const labels = await AddressLabelModel.find({
      chainId,
      type: 'exchange',
    }).lean();
    
    this.exchangeAddresses = new Set(labels.map(l => l.address));
    this.labelsCacheTime = Date.now();
  }
  
  /**
   * Empty snapshot when no data
   */
  private emptySnapshot(
    chainId: number,
    symbol: string,
    window: OnchainWindow,
    t0: number
  ): SnapshotResult {
    return {
      symbol,
      chainId,
      window,
      t0,
      metrics: {
        activeAddresses: 0,
        txCount: 0,
        transferCount: 0,
        largeTransfersCount: 0,
        largeTransfersVolumeRaw: '0',
        whaleThreshold: '0',
        distributionSkew: 0,
        top10Share: 0,
        exchangeInflows: 0,
        exchangeOutflows: 0,
        exchangeNetFlow: 0,
        // DEX metrics
        dexSwapCount: 0,
        dexBuyCount: 0,
        dexSellCount: 0,
        dexBuySellRatio: 1,
        dexWhaleSwapCount: 0,
        dexActivity: 0,
        dexImbalance: 0,
        // Metadata
        blockRange: { from: 0, to: 0 },
        logCount: 0,
        computedAt: Date.now(),
        completeness: 0,
        sourceQuality: 0,
      },
      state: 'NO_DATA',
      confidence: 0,
      saved: false,
    };
  }
  
  /**
   * Backfill observations for a window
   */
  async backfillObservations(
    chainId: number,
    symbol: string,
    window: OnchainWindow,
    days: number = 30
  ): Promise<{ created: number; errors: string[] }> {
    const windowMs = WINDOW_MS[window];
    const intervalMs = windowMs; // One observation per window
    const now = Date.now();
    const startTime = now - (days * 24 * 60 * 60 * 1000);
    
    let created = 0;
    const errors: string[] = [];
    
    for (let t = startTime; t <= now; t += intervalMs) {
      try {
        const result = await this.buildSnapshot(chainId, symbol, window, t);
        if (result.saved) created++;
      } catch (error) {
        const msg = error instanceof Error ? error.message : String(error);
        errors.push(`t=${t}: ${msg}`);
      }
    }
    
    return { created, errors };
  }
}

// Singleton
export const snapshotBuilder = new SnapshotBuilderService();

console.log('[OnChain V2] Snapshot Builder Service loaded');
