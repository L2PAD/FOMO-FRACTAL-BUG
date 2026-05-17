/**
 * Simulation Price Provider
 * ==========================
 * 
 * BLOCK 7.3+8: Provides historical price data for regime/CHOP calculation.
 * 
 * For simulation, we need price history BEFORE the trade entry.
 * This provider fetches from our price data stores.
 */

import mongoose from 'mongoose';

export interface PriceBar {
  timestamp: Date;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface PriceHistory {
  symbol: string;
  asOf: Date;
  bars: PriceBar[];
  closes: number[];
  highs: number[];
  lows: number[];
}

/**
 * Get historical price bars for a symbol
 */
export async function getHistoricalPrices(
  symbol: string,
  asOf: Date,
  lookbackDays: number = 200
): Promise<PriceHistory | null> {
  try {
    const db = mongoose.connection.db;
    if (!db) return null;

    const startDate = new Date(asOf.getTime() - lookbackDays * 24 * 60 * 60 * 1000);
    const asOfStr = asOf.toISOString().slice(0, 10);
    const startStr = startDate.toISOString().slice(0, 10);
    
    // Normalize symbol (might be BTC or BTCUSDT)
    const symbolVariants = [symbol, symbol + 'USDT', symbol.replace('USDT', '')];
    
    // Try sim_price_cache first (has real daily data)
    try {
      const simDb = db.client.db('intelligence_engine_sim');
      const simColl = simDb.collection('sim_price_cache');
      
      // First try: query with date range up to asOf
      let docs = await simColl.find({
        symbol: { $in: symbolVariants },
        date: { $gte: startStr, $lt: asOfStr },
      })
      .sort({ date: 1 })
      .limit(lookbackDays)
      .toArray();

      // Fallback: if not enough data, get ALL available data for symbol
      if (docs.length < 50) {
        docs = await simColl.find({
          symbol: { $in: symbolVariants },
        })
        .sort({ date: 1 })
        .toArray();
      }

      if (docs.length >= 50) {
        const bars: PriceBar[] = docs.map(d => ({
          timestamp: new Date(d.date),
          open: d.open || d.close,
          high: d.high || d.close,
          low: d.low || d.close,
          close: d.close,
        }));

        return {
          symbol,
          asOf,
          bars,
          closes: bars.map(b => b.close),
          highs: bars.map(b => b.high),
          lows: bars.map(b => b.low),
        };
      }
    } catch {
      // Fallback to other sources
    }

    // Try market_price_history (hourly data, aggregate to daily)
    try {
      const intDb = db.client.db('intelligence_engine');
      const priceColl = intDb.collection('market_price_history');
      
      // Get hourly data and aggregate
      const hourlyDocs = await priceColl.find({
        symbol: { $in: symbolVariants },
        ts: { $gte: startDate.getTime(), $lt: asOf.getTime() },
      })
      .sort({ ts: 1 })
      .toArray();

      if (hourlyDocs.length >= 24) {
        // Aggregate to daily bars
        const dailyBars = new Map<string, { open: number; high: number; low: number; close: number; timestamp: Date }>();
        
        for (const doc of hourlyDocs) {
          const dateKey = new Date(doc.ts).toISOString().slice(0, 10);
          const existing = dailyBars.get(dateKey);
          
          if (!existing) {
            dailyBars.set(dateKey, {
              timestamp: new Date(doc.ts),
              open: doc.o || doc.c,
              high: doc.h || doc.c,
              low: doc.l || doc.c,
              close: doc.c,
            });
          } else {
            existing.high = Math.max(existing.high, doc.h || doc.c);
            existing.low = Math.min(existing.low, doc.l || doc.c);
            existing.close = doc.c; // Last close of the day
          }
        }

        const bars: PriceBar[] = Array.from(dailyBars.values())
          .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());

        if (bars.length >= 20) {
          return {
            symbol,
            asOf,
            bars,
            closes: bars.map(b => b.close),
            highs: bars.map(b => b.high),
            lows: bars.map(b => b.low),
          };
        }
      }
    } catch {
      // Continue to fallback
    }

    return null;
  } catch (err) {
    console.error(`[SimPriceProvider] Error fetching prices for ${symbol}:`, err);
    return null;
  }
}

/**
 * Generate synthetic price history from available data
 * Used when real historical data is not available
 */
export function generateSyntheticPrices(
  basePrice: number,
  numBars: number = 200,
  volatility: number = 0.02
): PriceHistory {
  const bars: PriceBar[] = [];
  let price = basePrice;
  const now = new Date();

  for (let i = numBars - 1; i >= 0; i--) {
    const change = (Math.random() - 0.5) * 2 * volatility;
    price = price * (1 + change);
    
    const high = price * (1 + Math.random() * volatility);
    const low = price * (1 - Math.random() * volatility);
    
    bars.push({
      timestamp: new Date(now.getTime() - i * 24 * 60 * 60 * 1000),
      open: price * (1 + (Math.random() - 0.5) * volatility * 0.5),
      high,
      low,
      close: price,
    });
  }

  return {
    symbol: 'SYNTHETIC',
    asOf: now,
    bars,
    closes: bars.map(b => b.close),
    highs: bars.map(b => b.high),
    lows: bars.map(b => b.low),
  };
}

console.log('[Sentiment-ML] Simulation Price Provider loaded (BLOCK 7.3+8)');
