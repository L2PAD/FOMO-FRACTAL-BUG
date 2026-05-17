/**
 * Static Historical Price Provider
 * =================================
 * 
 * Loads historical OHLCV data from CSV files (Binance format).
 * Used for deterministic, reproducible simulation.
 * 
 * NO API calls. NO live data. Pure offline historical data.
 */

import * as fs from 'fs';
import * as path from 'path';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface HistoricalCandle {
  timestamp: number;      // Unix ms
  date: string;           // YYYY-MM-DD
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface OHLCData {
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

// ═══════════════════════════════════════════════════════════════
// PROVIDER CLASS
// ═══════════════════════════════════════════════════════════════

export class StaticHistoricalPriceProvider {
  private data: Map<string, HistoricalCandle[]> = new Map();
  private dataDir: string;
  
  constructor(dataDir: string = '/app/backend/data/historical') {
    this.dataDir = dataDir;
  }
  
  // ═══════════════════════════════════════════════════════════════
  // LOAD DATA
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * Load historical data for a symbol from CSV file.
   */
  loadSymbol(symbol: string): boolean {
    const filePath = path.join(this.dataDir, `${symbol}_1d.csv`);
    
    if (!fs.existsSync(filePath)) {
      console.warn(`[StaticPriceProvider] File not found: ${filePath}`);
      return false;
    }
    
    const content = fs.readFileSync(filePath, 'utf-8');
    const lines = content.trim().split('\n');
    
    const candles: HistoricalCandle[] = [];
    
    for (const line of lines) {
      const parts = line.split(',');
      
      // Binance format: open_time, open, high, low, close, volume, ...
      if (parts.length < 6) continue;
      
      const timestamp = parseInt(parts[0], 10);
      const open = parseFloat(parts[1]);
      const high = parseFloat(parts[2]);
      const low = parseFloat(parts[3]);
      const close = parseFloat(parts[4]);
      const volume = parseFloat(parts[5]);
      
      // Skip invalid data
      if (isNaN(timestamp) || isNaN(close)) continue;
      
      // Convert timestamp to date string
      const date = new Date(timestamp).toISOString().split('T')[0];
      
      candles.push({
        timestamp,
        date,
        open,
        high,
        low,
        close,
        volume,
      });
    }
    
    // Sort by timestamp ascending
    candles.sort((a, b) => a.timestamp - b.timestamp);
    
    this.data.set(symbol, candles);
    
    console.log(`[StaticPriceProvider] Loaded ${symbol}: ${candles.length} candles (${candles[0]?.date} → ${candles[candles.length - 1]?.date})`);
    
    return true;
  }
  
  /**
   * Load multiple symbols.
   */
  loadSymbols(symbols: string[]): void {
    for (const symbol of symbols) {
      this.loadSymbol(symbol);
    }
  }
  
  /**
   * Auto-detect and load all available symbols.
   */
  loadAllAvailable(): string[] {
    const loaded: string[] = [];
    
    if (!fs.existsSync(this.dataDir)) {
      console.warn(`[StaticPriceProvider] Data directory not found: ${this.dataDir}`);
      return loaded;
    }
    
    const files = fs.readdirSync(this.dataDir);
    
    for (const file of files) {
      if (file.endsWith('_1d.csv')) {
        const symbol = file.replace('_1d.csv', '');
        if (this.loadSymbol(symbol)) {
          loaded.push(symbol);
        }
      }
    }
    
    return loaded;
  }
  
  // ═══════════════════════════════════════════════════════════════
  // QUERY METHODS
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * Get candle for a specific date.
   */
  getCandleOnDate(symbol: string, date: string): HistoricalCandle | null {
    const candles = this.data.get(symbol);
    if (!candles) return null;
    
    return candles.find(c => c.date === date) || null;
  }
  
  /**
   * Get candle for a specific Date object.
   */
  getCandleOnDay(symbol: string, day: Date): HistoricalCandle | null {
    const date = day.toISOString().split('T')[0];
    return this.getCandleOnDate(symbol, date);
  }
  
  /**
   * Get close price on a specific date.
   */
  getCloseOnDay(symbol: string, day: Date): number | null {
    const candle = this.getCandleOnDay(symbol, day);
    return candle?.close ?? null;
  }
  
  /**
   * Get OHLC on a specific date.
   */
  getOHLC(symbol: string, day: Date): OHLCData | null {
    const candle = this.getCandleOnDay(symbol, day);
    if (!candle) return null;
    
    return {
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
      volume: candle.volume,
    };
  }
  
  /**
   * Get candles in a date range.
   */
  getRange(symbol: string, from: Date, to: Date): HistoricalCandle[] {
    const candles = this.data.get(symbol);
    if (!candles) return [];
    
    const fromTime = from.getTime();
    const toTime = to.getTime();
    
    return candles.filter(c => c.timestamp >= fromTime && c.timestamp <= toTime);
  }
  
  /**
   * Get last N candles before a date.
   */
  getLastNCandles(symbol: string, beforeDate: Date, n: number): HistoricalCandle[] {
    const candles = this.data.get(symbol);
    if (!candles) return [];
    
    const beforeTime = beforeDate.getTime();
    const filtered = candles.filter(c => c.timestamp < beforeTime);
    
    return filtered.slice(-n);
  }
  
  /**
   * Calculate return from date A to date B.
   */
  calculateReturn(symbol: string, fromDate: Date, toDate: Date): number | null {
    const fromCandle = this.getCandleOnDay(symbol, fromDate);
    const toCandle = this.getCandleOnDay(symbol, toDate);
    
    if (!fromCandle || !toCandle) return null;
    
    return (toCandle.close - fromCandle.close) / fromCandle.close;
  }
  
  // ═══════════════════════════════════════════════════════════════
  // FEATURE CALCULATION
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * Calculate momentum features for Direction Model.
   * Returns features needed for prediction.
   */
  calculateDirectionFeatures(symbol: string, date: Date): {
    momentum1d: number;
    momentum3d: number;
    momentum7d: number;
    rsi14: number;
    volatility7d: number;
    trendStrength: number;
  } | null {
    const candles = this.getLastNCandles(symbol, date, 20);
    
    if (candles.length < 14) {
      return null;
    }
    
    const closes = candles.map(c => c.close);
    const latest = closes[closes.length - 1];
    
    // Momentum calculations
    const momentum1d = candles.length >= 2 
      ? (latest - closes[closes.length - 2]) / closes[closes.length - 2]
      : 0;
      
    const momentum3d = candles.length >= 4
      ? (latest - closes[closes.length - 4]) / closes[closes.length - 4]
      : 0;
      
    const momentum7d = candles.length >= 8
      ? (latest - closes[closes.length - 8]) / closes[closes.length - 8]
      : 0;
    
    // RSI-14
    const rsi14 = this.calculateRSI(closes.slice(-15), 14);
    
    // 7-day volatility (std dev of returns)
    const returns7d = [];
    for (let i = closes.length - 7; i < closes.length; i++) {
      if (i > 0) {
        returns7d.push((closes[i] - closes[i - 1]) / closes[i - 1]);
      }
    }
    const volatility7d = this.stdDev(returns7d);
    
    // Trend strength: (close - SMA7) / SMA7
    const sma7 = closes.slice(-7).reduce((a, b) => a + b, 0) / 7;
    const trendStrength = (latest - sma7) / sma7;
    
    return {
      momentum1d,
      momentum3d,
      momentum7d,
      rsi14,
      volatility7d,
      trendStrength,
    };
  }
  
  private calculateRSI(prices: number[], period: number): number {
    if (prices.length < period + 1) return 50;
    
    let gains = 0;
    let losses = 0;
    
    for (let i = prices.length - period; i < prices.length; i++) {
      const change = prices[i] - prices[i - 1];
      if (change > 0) gains += change;
      else losses += Math.abs(change);
    }
    
    const avgGain = gains / period;
    const avgLoss = losses / period;
    
    if (avgLoss === 0) return 100;
    
    const rs = avgGain / avgLoss;
    return 100 - (100 / (1 + rs));
  }
  
  private stdDev(values: number[]): number {
    if (values.length < 2) return 0;
    const mean = values.reduce((a, b) => a + b, 0) / values.length;
    const variance = values.reduce((a, b) => a + (b - mean) ** 2, 0) / (values.length - 1);
    return Math.sqrt(variance);
  }
  
  // ═══════════════════════════════════════════════════════════════
  // METADATA
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * Get available symbols.
   */
  getLoadedSymbols(): string[] {
    return Array.from(this.data.keys());
  }
  
  /**
   * Get date range for a symbol.
   */
  getDateRange(symbol: string): { start: string; end: string } | null {
    const candles = this.data.get(symbol);
    if (!candles || candles.length === 0) return null;
    
    return {
      start: candles[0].date,
      end: candles[candles.length - 1].date,
    };
  }
  
  /**
   * Get total candle count for a symbol.
   */
  getCandleCount(symbol: string): number {
    return this.data.get(symbol)?.length ?? 0;
  }
  
  /**
   * Check if data is available for a date.
   */
  hasDataForDate(symbol: string, date: Date): boolean {
    return this.getCandleOnDay(symbol, date) !== null;
  }
}

// ═══════════════════════════════════════════════════════════════
// SINGLETON FACTORY
// ═══════════════════════════════════════════════════════════════

let providerInstance: StaticHistoricalPriceProvider | null = null;

export function getStaticHistoricalPriceProvider(dataDir?: string): StaticHistoricalPriceProvider {
  if (!providerInstance) {
    providerInstance = new StaticHistoricalPriceProvider(dataDir);
  }
  return providerInstance;
}

export function resetStaticHistoricalPriceProvider(): void {
  providerInstance = null;
}

console.log('[Exchange Sim] Static historical price provider loaded');
