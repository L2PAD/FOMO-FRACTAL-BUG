/**
 * Sentiment Price Adapter
 * =======================
 * 
 * BLOCK 6: Adapts DirPriceAdapter for sentiment dataset builder.
 * 
 * Provides:
 * - getClosePriceAt(symbol, timestamp) → { price, ts }
 * 
 * Uses the same price provider as Exchange module (no external API calls).
 */

import { getDirPriceAdapter } from '../../exchange-ml/dir/ports/dir.price.adapter.js';

export interface PriceAtResult {
  price: number;
  ts: Date;
}

export interface SentimentPricePort {
  getClosePriceAt(symbol: string, at: Date): Promise<PriceAtResult | null>;
}

/**
 * Adapter implementation using Exchange's DirPriceAdapter
 */
export class SentimentPriceAdapter implements SentimentPricePort {
  /**
   * Get close price at or near the specified timestamp.
   * Returns the closest candle close price within a reasonable window.
   */
  async getClosePriceAt(symbol: string, at: Date): Promise<PriceAtResult | null> {
    const adapter = getDirPriceAdapter();
    const targetSec = Math.floor(at.getTime() / 1000);
    
    // Add USDT suffix if not present (price DB stores as BTCUSDT, ETHUSDT, etc.)
    let querySymbol = symbol.toUpperCase();
    if (!querySymbol.endsWith('USDT')) {
      querySymbol = `${querySymbol}USDT`;
    }
    
    // Fetch 48h window around target (24h before, 24h after)
    const windowSec = 24 * 60 * 60;
    const fromSec = targetSec - windowSec;
    const toSec = targetSec + windowSec;
    
    try {
      const bars = await adapter.getSeries({
        symbol: querySymbol,
        from: fromSec,
        to: toSec,
        tf: '1d',  // Daily candles for consistency
      });

      if (bars.length === 0) {
        // Try hourly for more granularity
        const hourlyBars = await adapter.getSeries({
          symbol: querySymbol,
          from: fromSec,
          to: toSec,
          tf: '1h',
        });
        
        if (hourlyBars.length === 0) return null;
        
        // Find closest bar to target
        const closest = this.findClosestBar(hourlyBars, targetSec);
        if (!closest) return null;
        
        return {
          price: closest.close,
          ts: new Date(closest.t * 1000),
        };
      }

      // Find closest bar to target
      const closest = this.findClosestBar(bars, targetSec);
      if (!closest) return null;
      
      return {
        price: closest.close,
        ts: new Date(closest.t * 1000),
      };
    } catch (err) {
      console.error(`[SentimentPriceAdapter] Error fetching price for ${symbol} at ${at}:`, err);
      return null;
    }
  }

  /**
   * Find the bar closest to target timestamp (prefer before or at target)
   */
  private findClosestBar(bars: Array<{ t: number; close: number }>, targetSec: number): { t: number; close: number } | null {
    if (bars.length === 0) return null;

    let closest = bars[0];
    let minDiff = Math.abs(bars[0].t - targetSec);

    for (const bar of bars) {
      const diff = Math.abs(bar.t - targetSec);
      
      // Prefer bars at or before target (no future data)
      if (bar.t <= targetSec && diff <= minDiff) {
        closest = bar;
        minDiff = diff;
      } else if (diff < minDiff) {
        closest = bar;
        minDiff = diff;
      }
    }

    return closest;
  }
}

// Singleton
let priceAdapterInstance: SentimentPriceAdapter | null = null;

export function getSentimentPriceAdapter(): SentimentPriceAdapter {
  if (!priceAdapterInstance) {
    priceAdapterInstance = new SentimentPriceAdapter();
  }
  return priceAdapterInstance;
}
