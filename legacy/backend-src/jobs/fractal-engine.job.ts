/**
 * FRACTAL ENGINE JOB
 * ==================
 * 
 * Generates fractal forecasts and writes to fractal_state.
 * Runs BEFORE fractal publisher in snapshot pipeline.
 * 
 * Pipeline: Exchange Observations → Fractal Engine → fractal_state → Publisher → Snapshots → Meta Brain
 */

import mongoose from 'mongoose';
import { buildFractalForecast } from '../modules/fractal/fractal-engine.js';

const ASSETS = ['BTC', 'ETH', 'SOL', 'ARB', 'OP', 'AVAX', 'MATIC'];

export async function runFractalEngineJob(): Promise<void> {
  console.log('[FractalEngineJob] 🚀 Starting...');

  const db = mongoose.connection.db;
  if (!db) {
    console.error('[FractalEngineJob] ❌ MongoDB not connected');
    return;
  }

  const results = { success: 0, failed: 0, skipped: 0 };

  for (const asset of ASSETS) {
    try {
      // Fetch recent price data from exchange observations
      const observations = await db
        .collection('exchange_observations')
        .find({ asset })
        .sort({ timestamp: -1 })
        .limit(50)
        .toArray();

      if (observations.length < 20) {
        results.skipped++;
        console.log(`[FractalEngineJob] ⚠️  ${asset}: Not enough data (${observations.length}/20)`);
        continue;
      }

      // Extract prices (reverse to get oldest→newest)
      const prices = observations
        .map(o => Number(o.market?.price ?? 0))
        .filter(p => p > 0)
        .reverse();

      if (prices.length < 20) {
        results.skipped++;
        console.log(`[FractalEngineJob] ⚠️  ${asset}: Not enough valid prices (${prices.length}/20)`);
        continue;
      }

      // Generate forecast
      const forecast = buildFractalForecast(prices);
      const currentPrice = prices[prices.length - 1];

      // Prepare fractal_state document
      const doc = {
        asset,
        timestamp: Date.now(),
        currentPrice,
        
        forecast: {
          direction: forecast.direction,
          expectedReturn: forecast.expectedReturn,
          low: forecast.low,
          high: forecast.high,
          confidence: forecast.confidence,
          horizon: '7D',
        },
        
        scenario: {
          direction: forecast.direction,
          expectedReturn: forecast.expectedReturn,
          horizon: '7D',
          returns: {
            p25: forecast.expectedReturn - forecast.volatility,
            p50: forecast.expectedReturn,
            p75: forecast.expectedReturn + forecast.volatility,
          },
        },
        
        regime: forecast.regime,
        volatility: forecast.volatility,
        
        diagnostics: {
          reliability: forecast.confidence,
          sampleSize: prices.length,
        },
        
        updatedAt: new Date(),
      };

      // Upsert to fractal_state
      await db.collection('fractal_state').updateOne(
        { asset },
        { $set: doc },
        { upsert: true }
      );

      results.success++;
      console.log(`[FractalEngineJob] ✅ ${asset}: ${forecast.direction} (ret=${(forecast.expectedReturn * 100).toFixed(2)}%, conf=${forecast.confidence.toFixed(2)}, regime=${forecast.regime})`);

    } catch (err: any) {
      results.failed++;
      console.error(`[FractalEngineJob] ❌ ${asset}:`, err.message);
    }
  }

  console.log(`[FractalEngineJob] ✅ Complete: ${results.success} success, ${results.skipped} skipped, ${results.failed} failed`);
}

export default runFractalEngineJob;
