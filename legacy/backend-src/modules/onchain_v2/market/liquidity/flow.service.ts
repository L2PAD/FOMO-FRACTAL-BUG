/**
 * Flow Data Service
 * ==================
 * 
 * PHASE 2.2: Micro Flow Integration
 * 
 * Aggregates DEX and ERC20 flow data for LiquidityScore.
 */

import { DexSwapModel } from '../../ingestion/dex/models';
import { ERC20LogModel, AddressLabelModel } from '../../ingestion/erc20/models';

// ═══════════════════════════════════════════════════════════════
// FLOW DATA OUTPUT
// ═══════════════════════════════════════════════════════════════

export interface DexFlowData {
  totalSwaps: number;
  buyCount: number;
  sellCount: number;
  whaleSwaps: number;
  imbalance: number;  // (buy - sell) / total, range [-1, 1]
  isStale: boolean;
  lastSwapAge: number;  // ms since last swap
}

export interface ExchangeFlowData {
  inflows: number;      // Count of transfers TO exchanges
  outflows: number;     // Count of transfers FROM exchanges
  netInflow: number;    // inflows - outflows
  inflowPressure: number; // Normalized [-1, 1], positive = more inflows
  hasLabels: boolean;
  isStale: boolean;
  lastTransferAge: number;
}

export interface FlowAggregation {
  dex: DexFlowData | null;
  exchange: ExchangeFlowData | null;
  timestamp: number;
  windowMs: number;
  completeness: number;  // 0-1, how much flow data is available
}

// ═══════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════

const STALE_THRESHOLD_MS = 60 * 60 * 1000;  // 1 hour
const DEFAULT_WINDOW_MS = 24 * 60 * 60 * 1000;  // 24 hours

// ═══════════════════════════════════════════════════════════════
// DEX FLOW
// ═══════════════════════════════════════════════════════════════

/**
 * Get DEX swap aggregation for a time window
 */
export async function getDexFlow(windowMs: number = DEFAULT_WINDOW_MS): Promise<DexFlowData | null> {
  const cutoff = Date.now() - windowMs;
  
  try {
    // Aggregate DEX swaps
    const [stats] = await DexSwapModel.aggregate([
      { $match: { indexedAt: { $gte: cutoff } } },
      {
        $group: {
          _id: null,
          totalSwaps: { $sum: 1 },
          buyCount: { $sum: { $cond: [{ $eq: ['$direction', 'buy'] }, 1, 0] } },
          sellCount: { $sum: { $cond: [{ $eq: ['$direction', 'sell'] }, 1, 0] } },
          whaleSwaps: { $sum: { $cond: ['$isWhaleSwap', 1, 0] } },
          maxIndexedAt: { $max: '$indexedAt' },
        },
      },
    ]);

    if (!stats || stats.totalSwaps === 0) {
      return null;
    }

    const { totalSwaps, buyCount, sellCount, whaleSwaps, maxIndexedAt } = stats;
    const lastSwapAge = Date.now() - (maxIndexedAt || 0);
    
    // Calculate imbalance: (buy - sell) / total, clamped to [-1, 1]
    const rawImbalance = (buyCount - sellCount) / Math.max(totalSwaps, 1);
    const imbalance = Math.max(-1, Math.min(1, rawImbalance));

    return {
      totalSwaps,
      buyCount,
      sellCount,
      whaleSwaps,
      imbalance,
      isStale: lastSwapAge > STALE_THRESHOLD_MS,
      lastSwapAge,
    };
  } catch (error) {
    console.error('[FlowService] Error getting DEX flow:', error);
    return null;
  }
}

/**
 * Get DEX flow history for normalization
 */
export async function getDexFlowHistory(days: number = 30): Promise<number[]> {
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  const bucketMs = 60 * 60 * 1000;  // 1 hour buckets
  
  try {
    const buckets = await DexSwapModel.aggregate([
      { $match: { indexedAt: { $gte: cutoff } } },
      {
        $group: {
          _id: { $floor: { $divide: ['$indexedAt', bucketMs] } },
          buyCount: { $sum: { $cond: [{ $eq: ['$direction', 'buy'] }, 1, 0] } },
          sellCount: { $sum: { $cond: [{ $eq: ['$direction', 'sell'] }, 1, 0] } },
          total: { $sum: 1 },
        },
      },
      { $sort: { _id: 1 } },
    ]);

    // Calculate imbalance for each bucket
    return buckets
      .filter(b => b.total > 0)
      .map(b => (b.buyCount - b.sellCount) / b.total);
  } catch (error) {
    console.error('[FlowService] Error getting DEX history:', error);
    return [];
  }
}

// ═══════════════════════════════════════════════════════════════
// EXCHANGE FLOW (CEX labels)
// ═══════════════════════════════════════════════════════════════

/**
 * Get exchange flow (inflows/outflows to CEX addresses)
 */
export async function getExchangeFlow(windowMs: number = DEFAULT_WINDOW_MS): Promise<ExchangeFlowData | null> {
  const cutoff = Date.now() - windowMs;
  
  try {
    // First check if we have any exchange labels
    const exchangeLabels = await AddressLabelModel.find(
      { type: 'exchange' },
      { address: 1 }
    ).lean();

    if (exchangeLabels.length === 0) {
      // No exchange labels configured
      return {
        inflows: 0,
        outflows: 0,
        netInflow: 0,
        inflowPressure: 0,
        hasLabels: false,
        isStale: true,
        lastTransferAge: Infinity,
      };
    }

    const exchangeAddresses = exchangeLabels.map(l => l.address.toLowerCase());

    // Get inflows (transfers TO exchanges)
    const [inflowStats] = await ERC20LogModel.aggregate([
      {
        $match: {
          indexedAt: { $gte: cutoff },
          to: { $in: exchangeAddresses },
        },
      },
      {
        $group: {
          _id: null,
          count: { $sum: 1 },
          maxIndexedAt: { $max: '$indexedAt' },
        },
      },
    ]);

    // Get outflows (transfers FROM exchanges)
    const [outflowStats] = await ERC20LogModel.aggregate([
      {
        $match: {
          indexedAt: { $gte: cutoff },
          from: { $in: exchangeAddresses },
        },
      },
      {
        $group: {
          _id: null,
          count: { $sum: 1 },
          maxIndexedAt: { $max: '$indexedAt' },
        },
      },
    ]);

    const inflows = inflowStats?.count || 0;
    const outflows = outflowStats?.count || 0;
    const netInflow = inflows - outflows;
    const total = inflows + outflows;

    // Calculate inflow pressure: (inflows - outflows) / total
    const inflowPressure = total > 0 
      ? Math.max(-1, Math.min(1, netInflow / total))
      : 0;

    const lastInflowAt = inflowStats?.maxIndexedAt || 0;
    const lastOutflowAt = outflowStats?.maxIndexedAt || 0;
    const lastTransferAge = Date.now() - Math.max(lastInflowAt, lastOutflowAt);

    return {
      inflows,
      outflows,
      netInflow,
      inflowPressure,
      hasLabels: true,
      isStale: lastTransferAge > STALE_THRESHOLD_MS,
      lastTransferAge,
    };
  } catch (error) {
    console.error('[FlowService] Error getting exchange flow:', error);
    return null;
  }
}

/**
 * Get exchange flow history for normalization
 */
export async function getExchangeFlowHistory(days: number = 30): Promise<number[]> {
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  const bucketMs = 60 * 60 * 1000;  // 1 hour buckets
  
  try {
    const exchangeLabels = await AddressLabelModel.find(
      { type: 'exchange' },
      { address: 1 }
    ).lean();

    if (exchangeLabels.length === 0) return [];

    const exchangeAddresses = exchangeLabels.map(l => l.address.toLowerCase());

    // Aggregate by hour bucket
    const inflowBuckets = await ERC20LogModel.aggregate([
      {
        $match: {
          indexedAt: { $gte: cutoff },
          to: { $in: exchangeAddresses },
        },
      },
      {
        $group: {
          _id: { $floor: { $divide: ['$indexedAt', bucketMs] } },
          count: { $sum: 1 },
        },
      },
    ]);

    const outflowBuckets = await ERC20LogModel.aggregate([
      {
        $match: {
          indexedAt: { $gte: cutoff },
          from: { $in: exchangeAddresses },
        },
      },
      {
        $group: {
          _id: { $floor: { $divide: ['$indexedAt', bucketMs] } },
          count: { $sum: 1 },
        },
      },
    ]);

    // Combine into net flow per bucket
    const inflowMap = new Map(inflowBuckets.map(b => [b._id, b.count]));
    const outflowMap = new Map(outflowBuckets.map(b => [b._id, b.count]));
    
    const allBuckets = new Set([...inflowMap.keys(), ...outflowMap.keys()]);
    const netFlows: number[] = [];
    
    for (const bucket of [...allBuckets].sort()) {
      const inflow = inflowMap.get(bucket) || 0;
      const outflow = outflowMap.get(bucket) || 0;
      const total = inflow + outflow;
      if (total > 0) {
        netFlows.push((inflow - outflow) / total);
      }
    }

    return netFlows;
  } catch (error) {
    console.error('[FlowService] Error getting exchange flow history:', error);
    return [];
  }
}

// ═══════════════════════════════════════════════════════════════
// AGGREGATED FLOW
// ═══════════════════════════════════════════════════════════════

/**
 * Get all flow data aggregated
 */
export async function getFlowAggregation(windowMs: number = DEFAULT_WINDOW_MS): Promise<FlowAggregation> {
  const [dex, exchange] = await Promise.all([
    getDexFlow(windowMs),
    getExchangeFlow(windowMs),
  ]);

  // Calculate completeness: how much flow data is available
  let featuresPresent = 0;
  let featuresExpected = 2;

  if (dex && !dex.isStale && dex.totalSwaps >= 10) {
    featuresPresent++;
  }
  
  if (exchange && exchange.hasLabels && !exchange.isStale && (exchange.inflows + exchange.outflows) >= 5) {
    featuresPresent++;
  }

  return {
    dex,
    exchange,
    timestamp: Date.now(),
    windowMs,
    completeness: featuresPresent / featuresExpected,
  };
}

/**
 * Get flow histories for normalization
 */
export async function getFlowHistories(): Promise<{
  dexImbalance: number[];
  exchangeFlow: number[];
}> {
  const [dexImbalance, exchangeFlow] = await Promise.all([
    getDexFlowHistory(30),
    getExchangeFlowHistory(30),
  ]);

  return { dexImbalance, exchangeFlow };
}

console.log('[Liquidity] Flow Service loaded');
