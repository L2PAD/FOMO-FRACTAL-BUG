/**
 * Simulation Price Provider
 * =========================
 * 
 * Priority:
 * 1. Static historical data (real Binance dumps)
 * 2. DB cache
 * 3. Synthetic generation (fallback)
 * 
 * For real-data simulation, USE_STATIC_HISTORICAL=true
 */

import { Db } from 'mongodb';
import { SimPriceProvider } from '../exchange_sim.types.js';
import { 
  StaticHistoricalPriceProvider, 
  getStaticHistoricalPriceProvider 
} from './static_historical_provider.js';

const CACHE_COLLECTION = 'sim_price_cache';

// Base prices for synthetic generation (approximate real prices)
const BASE_PRICES: Record<string, number> = {
  'BTCUSDT': 42000,
  'BTC': 42000,
  'ETHUSDT': 2200,
  'ETH': 2200,
  'SOLUSDT': 100,
  'SOL': 100,
  'BNBUSDT': 300,
  'BNB': 300,
  'XRPUSDT': 0.55,
  'XRP': 0.55,
  'ADAUSDT': 0.45,
  'ADA': 0.45,
  'DOGEUSDT': 0.08,
  'DOGE': 0.08,
  'AVAXUSDT': 35,
  'AVAX': 35,
  'LINKUSDT': 15,
  'LINK': 15,
  'MATICUSDT': 0.85,
  'MATIC': 0.85,
};

interface CachedCandle {
  symbol: string;
  date: string; // YYYY-MM-DD
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  fetchedAt: Date;
  synthetic: boolean;
}

export class SimPriceProviderImpl implements SimPriceProvider {
  private memoryCache: Map<string, CachedCandle> = new Map();
  private staticProvider: StaticHistoricalPriceProvider | null = null;
  private useStaticHistorical: boolean = false;
  
  constructor(private db: Db) {
    // Check if real historical data is available
    this.initStaticProvider();
  }
  
  /**
   * Initialize static historical provider if data available.
   */
  private initStaticProvider(): void {
    try {
      this.staticProvider = getStaticHistoricalPriceProvider();
      const loaded = this.staticProvider.loadAllAvailable();
      
      if (loaded.length > 0) {
        this.useStaticHistorical = true;
        console.log(`[SimPriceProvider] ✅ Using REAL historical data: ${loaded.join(', ')}`);
      } else {
        console.log('[SimPriceProvider] ⚠️ No historical data found, using synthetic');
      }
    } catch (error) {
      console.warn('[SimPriceProvider] Could not load static provider:', error);
    }
  }
  
  /**
   * Force use of static historical data (for real-data simulation).
   */
  setUseStaticHistorical(use: boolean): void {
    this.useStaticHistorical = use;
    console.log(`[SimPriceProvider] Static historical: ${use ? 'ENABLED' : 'DISABLED'}`);
  }
  
  /**
   * Check if using real data.
   */
  isUsingRealData(): boolean {
    return this.useStaticHistorical && this.staticProvider !== null;
  }
  
  private getCacheKey(symbol: string, day: Date): string {
    const dateStr = day.toISOString().split('T')[0];
    return `${symbol.toUpperCase()}_${dateStr}`;
  }
  
  async getCloseOnDay(symbol: string, day: Date): Promise<number | null> {
    const ohlc = await this.getOHLC(symbol, day);
    return ohlc?.close ?? null;
  }
  
  async getOHLC(symbol: string, day: Date): Promise<{ open: number; high: number; low: number; close: number } | null> {
    const cacheKey = this.getCacheKey(symbol, day);
    const upperSymbol = symbol.toUpperCase();
    
    // 0. PRIORITY: Static historical data (real data)
    if (this.useStaticHistorical && this.staticProvider) {
      const realData = this.staticProvider.getOHLC(upperSymbol, day);
      if (realData) {
        return realData;
      }
      // If date not in historical data, don't fall back to synthetic
      // This ensures deterministic real-data simulation
      console.warn(`[SimPriceProvider] No real data for ${upperSymbol} on ${day.toISOString().split('T')[0]}`);
      return null;
    }
    
    // 1. Check memory cache
    const memCached = this.memoryCache.get(cacheKey);
    if (memCached) {
      return {
        open: memCached.open,
        high: memCached.high,
        low: memCached.low,
        close: memCached.close,
      };
    }
    
    // 2. Check DB cache
    const dateStr = day.toISOString().split('T')[0];
    const dbCached = await this.db.collection<CachedCandle>(CACHE_COLLECTION).findOne({
      symbol: upperSymbol,
      date: dateStr,
    });
    
    if (dbCached) {
      this.memoryCache.set(cacheKey, dbCached);
      return {
        open: dbCached.open,
        high: dbCached.high,
        low: dbCached.low,
        close: dbCached.close,
      };
    }
    
    // 3. Generate synthetic price (for lifecycle testing)
    const synthetic = this.generateSyntheticCandle(upperSymbol, day);
    if (synthetic) {
      // Cache in DB
      await this.db.collection<CachedCandle>(CACHE_COLLECTION).updateOne(
        { symbol: upperSymbol, date: dateStr },
        { $set: synthetic },
        { upsert: true }
      );
      
      this.memoryCache.set(cacheKey, synthetic);
      
      return {
        open: synthetic.open,
        high: synthetic.high,
        low: synthetic.low,
        close: synthetic.close,
      };
    }
    
    return null;
  }
  
  /**
   * Generate synthetic candle data for simulation.
   * Uses deterministic randomness based on symbol+date for reproducibility.
   * Simulates realistic market behavior: trends, volatility, mean reversion.
   */
  private generateSyntheticCandle(symbol: string, day: Date): CachedCandle | null {
    const basePrice = BASE_PRICES[symbol];
    if (!basePrice) {
      console.warn(`[SimPriceProvider] No base price for ${symbol}`);
      return null;
    }
    
    const dateStr = day.toISOString().split('T')[0];
    
    // Deterministic seed based on symbol + date
    const seed = this.hashCode(`${symbol}_${dateStr}`);
    const rand = this.seededRandom(seed);
    
    // Calculate days since reference date for trend simulation
    const refDate = new Date('2024-01-01');
    const daysSinceRef = Math.floor((day.getTime() - refDate.getTime()) / (24 * 60 * 60 * 1000));
    
    // Simulate market regimes (30-day cycles)
    const cyclePhase = (daysSinceRef % 60) / 60; // 0-1
    const regime = cyclePhase < 0.4 ? 'BULL' : (cyclePhase < 0.7 ? 'BEAR' : 'SIDEWAYS');
    
    // Base trend based on regime
    let trendBias = 0;
    switch (regime) {
      case 'BULL': trendBias = 0.002; break;  // +0.2%/day
      case 'BEAR': trendBias = -0.002; break; // -0.2%/day
      case 'SIDEWAYS': trendBias = 0; break;
    }
    
    // Calculate price with accumulated trend
    const trendFactor = 1 + (trendBias * daysSinceRef * 0.3); // Dampened trend
    const volatility = 0.02 + (rand() * 0.03); // 2-5% daily volatility
    
    // Generate OHLC
    const dailyReturn = trendBias + (rand() - 0.5) * 2 * volatility;
    const open = basePrice * trendFactor * (1 + (rand() - 0.5) * 0.01);
    const close = open * (1 + dailyReturn);
    const high = Math.max(open, close) * (1 + rand() * volatility * 0.5);
    const low = Math.min(open, close) * (1 - rand() * volatility * 0.5);
    
    return {
      symbol,
      date: dateStr,
      open: Math.round(open * 100) / 100,
      high: Math.round(high * 100) / 100,
      low: Math.round(low * 100) / 100,
      close: Math.round(close * 100) / 100,
      volume: Math.floor(1000000 + rand() * 5000000),
      fetchedAt: new Date(),
      synthetic: true,
    };
  }
  
  // Simple hash function for deterministic seeding
  private hashCode(str: string): number {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    return Math.abs(hash);
  }
  
  // Seeded random number generator (Linear Congruential Generator)
  private seededRandom(seed: number): () => number {
    let s = seed;
    return () => {
      s = (s * 1103515245 + 12345) & 0x7fffffff;
      return s / 0x7fffffff;
    };
  }
  
  // Pre-fetch prices for a date range (optimization)
  async prefetchRange(symbol: string, startDate: Date, days: number): Promise<number> {
    // If using static historical, no prefetch needed
    if (this.useStaticHistorical && this.staticProvider) {
      const count = this.staticProvider.getCandleCount(symbol);
      console.log(`[SimPriceProvider] Using ${count} real candles for ${symbol}`);
      return count;
    }
    
    let count = 0;
    const current = new Date(startDate);
    
    for (let i = 0; i < days; i++) {
      const ohlc = await this.getOHLC(symbol, current);
      if (ohlc) count++;
      current.setDate(current.getDate() + 1);
    }
    
    console.log(`[SimPriceProvider] Generated ${count}/${days} synthetic candles for ${symbol}`);
    return count;
  }
  
  /**
   * Get direction features from real historical data.
   */
  getDirectionFeatures(symbol: string, date: Date): {
    momentum1d: number;
    momentum3d: number;
    momentum7d: number;
    rsi14: number;
    volatility7d: number;
    trendStrength: number;
  } | null {
    if (!this.staticProvider) return null;
    return this.staticProvider.calculateDirectionFeatures(symbol, date);
  }
  
  // Ensure indexes
  async ensureIndexes(): Promise<void> {
    await this.db.collection(CACHE_COLLECTION).createIndex(
      { symbol: 1, date: 1 },
      { unique: true }
    );
  }
}

// Factory
export function createSimPriceProvider(db: Db): SimPriceProviderImpl {
  return new SimPriceProviderImpl(db);
}
