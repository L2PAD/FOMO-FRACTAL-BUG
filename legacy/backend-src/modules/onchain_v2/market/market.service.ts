/**
 * Market Series Service
 * ======================
 * 
 * PHASE 1: Liquidity & Alt Rotation Engine
 * 
 * Collects and stores market-level time series:
 * - Uses existing dominance.provider for CoinGecko data
 * - Fetches USDT/USDC totalSupply via RPC Pool
 * - Calculates derived metrics
 * - Persists to MongoDB
 */

import { MarketSeriesModel, MARKET_SERIES_KEYS, MarketSeriesKey } from './market.model';
import { fetchDominanceData } from '../../macro/providers/dominance.provider';
import { rpcPool } from '../rpc-pool';

// Stablecoin addresses (Ethereum mainnet)
const STABLECOIN_ADDRESSES = {
  USDT: '0xdAC17F958D2ee523a2206206994597C13D831ec7',
  USDC: '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
};

// Decimals
const STABLECOIN_DECIMALS = {
  USDT: 6,
  USDC: 6,
};

// ERC20 totalSupply function selector
const TOTAL_SUPPLY_SELECTOR = '0x18160ddd';

interface MarketSnapshot {
  timestamp: number;
  pureAltCap: number | null;
  stableSupplyTotal: number | null;
  stableDominance: number | null;
  ethBtcRatio: number | null;
  btcDominanceRaw: number | null;
  sources: {
    dominance: 'LIVE' | 'CACHED' | 'NO_DATA';
    supply: 'LIVE' | 'ERROR';
  };
}

/**
 * Fetch stablecoin total supply via RPC Pool
 */
async function fetchStablecoinSupply(): Promise<{ usdt: number; usdc: number } | null> {
  try {
    // Use eth_call to get totalSupply
    const [usdtRaw, usdcRaw] = await Promise.all([
      rpcPool.call<string>(1, 'eth_call', [
        { to: STABLECOIN_ADDRESSES.USDT, data: TOTAL_SUPPLY_SELECTOR },
        'latest'
      ]),
      rpcPool.call<string>(1, 'eth_call', [
        { to: STABLECOIN_ADDRESSES.USDC, data: TOTAL_SUPPLY_SELECTOR },
        'latest'
      ]),
    ]);

    // Parse hex to number
    const usdt = parseInt(usdtRaw, 16) / Math.pow(10, STABLECOIN_DECIMALS.USDT);
    const usdc = parseInt(usdcRaw, 16) / Math.pow(10, STABLECOIN_DECIMALS.USDC);

    console.log(`[Market] Stablecoin supply: USDT=${(usdt / 1e9).toFixed(2)}B, USDC=${(usdc / 1e9).toFixed(2)}B`);

    return { usdt, usdc };
  } catch (error) {
    console.error('[Market] Failed to fetch stablecoin supply:', error);
    return null;
  }
}

/**
 * Collect all market data and calculate derived metrics
 */
export async function collectMarketSnapshot(): Promise<MarketSnapshot> {
  const timestamp = Date.now();

  // 1. Get dominance data (from existing provider - no duplicate API calls)
  const { dominance, quality } = await fetchDominanceData();

  // 2. Get stablecoin supply via RPC
  const supplyData = await fetchStablecoinSupply();

  // 3. Calculate derived metrics
  let pureAltCap: number | null = null;
  let stableDominance: number | null = null;
  let ethBtcRatio: number | null = null;
  let btcDominanceRaw: number | null = null;
  let stableSupplyTotal: number | null = null;

  if (dominance) {
    btcDominanceRaw = dominance.btcPct;

    // Pure Alt Cap as percentage (will be converted to USD in Phase 2)
    pureAltCap = dominance.altPct;

    // ETH/BTC ratio approximation from dominance
    // Note: This is alt/btc ratio, not exact eth/btc
    // Will be refined when we add explicit ETH tracking
    ethBtcRatio = dominance.altPct / dominance.btcPct;
  }

  if (supplyData) {
    stableSupplyTotal = supplyData.usdt + supplyData.usdc;
    
    // Stable dominance calculated from supply and dominance percentage
    if (dominance && dominance.stablePct > 0) {
      // More accurate: use actual supply / dominance percentage to estimate total cap
      const estimatedTotalCap = stableSupplyTotal / (dominance.stablePct / 100);
      stableDominance = (stableSupplyTotal / estimatedTotalCap) * 100;
      
      // Now we can calculate proper Pure Alt Cap in USD
      pureAltCap = estimatedTotalCap * (dominance.altPct / 100);
    }
  }

  return {
    timestamp,
    pureAltCap,
    stableSupplyTotal,
    stableDominance,
    ethBtcRatio,
    btcDominanceRaw,
    sources: {
      dominance: quality.mode as 'LIVE' | 'CACHED' | 'NO_DATA',
      supply: supplyData ? 'LIVE' : 'ERROR',
    },
  };
}

/**
 * Save market snapshot to MongoDB
 */
export async function saveMarketSnapshot(snapshot: MarketSnapshot, chainId: number = 1): Promise<number> {
  const { timestamp } = snapshot;
  const operations: Array<{ key: MarketSeriesKey; value: number | null }> = [
    { key: MARKET_SERIES_KEYS.PURE_ALT_CAP, value: snapshot.pureAltCap },
    { key: MARKET_SERIES_KEYS.STABLE_SUPPLY_TOTAL, value: snapshot.stableSupplyTotal },
    { key: MARKET_SERIES_KEYS.STABLE_DOMINANCE, value: snapshot.stableDominance },
    { key: MARKET_SERIES_KEYS.ETHBTC_RATIO, value: snapshot.ethBtcRatio },
    { key: MARKET_SERIES_KEYS.BTC_DOMINANCE_RAW, value: snapshot.btcDominanceRaw },
  ];

  let savedCount = 0;

  for (const op of operations) {
    if (op.value === null || op.value === undefined) continue;

    try {
      await MarketSeriesModel.updateOne(
        { chainId, key: op.key, t: timestamp },
        {
          $set: {
            chainId,
            key: op.key,
            t: timestamp,
            value: op.value,
            meta: { source: snapshot.sources.dominance },
          },
        },
        { upsert: true }
      );
      savedCount++;
    } catch (error: any) {
      // Ignore duplicate key errors (race condition)
      if (error.code !== 11000) {
        console.error(`[Market] Failed to save ${op.key}:`, error.message);
      }
    }
  }

  console.log(`[Market] Saved ${savedCount} series at t=${timestamp}`);
  return savedCount;
}

/**
 * Get series data from MongoDB
 */
export async function getMarketSeries(
  key: MarketSeriesKey,
  windowMs: number = 30 * 24 * 60 * 60 * 1000, // 30 days default
  chainId: number = 1
): Promise<Array<{ t: number; value: number }>> {
  const cutoff = Date.now() - windowMs;

  const docs = await MarketSeriesModel.find(
    { chainId, key, t: { $gte: cutoff } },
    { t: 1, value: 1, _id: 0 }
  )
    .sort({ t: 1 })
    .lean();

  return docs.map((d) => ({ t: d.t, value: d.value }));
}

/**
 * Get latest value for a series
 */
export async function getLatestMarketValue(key: MarketSeriesKey, chainId: number = 1): Promise<number | null> {
  const doc = await MarketSeriesModel.findOne({ chainId, key })
    .sort({ t: -1 })
    .lean();

  return doc?.value ?? null;
}

/**
 * Get all latest values
 */
export async function getAllLatestMarketValues(): Promise<Record<MarketSeriesKey, number | null>> {
  const result: Record<string, number | null> = {};

  for (const key of Object.values(MARKET_SERIES_KEYS)) {
    result[key] = await getLatestMarketValue(key);
  }

  return result as Record<MarketSeriesKey, number | null>;
}

console.log('[Market] Service loaded');
