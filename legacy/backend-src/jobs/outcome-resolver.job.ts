/**
 * OUTCOME RESOLVER JOB
 * ====================
 * 
 * Resolves predictions by comparing against actual market outcomes.
 * 
 * Runs periodically to:
 * 1. Find unresolved outcomes where horizon has passed
 * 2. Fetch actual price at horizon end
 * 3. Calculate accuracy metrics
 * 4. Mark outcome as resolved
 * 
 * This is the PROOF layer - shows if Meta Brain has alpha.
 */

import mongoose from 'mongoose';
import { findUnresolvedOutcomes, resolveOutcome } from '../modules/meta-brain-v2/outcomes/meta_brain_outcomes.repo.js';

/**
 * Fetch actual price for asset at specific timestamp
 * Uses exchange_observations collection
 */
async function getActualPrice(asset: string, targetTimestamp: Date): Promise<number | null> {
  const db = mongoose.connection.db;
  if (!db) throw new Error('MongoDB not connected');
  
  // Find closest observation within ±15 minutes window
  const window = 15 * 60 * 1000; // 15 minutes
  const startTs = targetTimestamp.getTime() - window;
  const endTs = targetTimestamp.getTime() + window;
  
  const observation = await db.collection('exchange_observations').findOne(
    {
      asset,
      timestamp: { $gte: startTs, $lte: endTs },
      'market.price': { $exists: true, $ne: null },
    },
    {
      sort: { timestamp: -1 },
      projection: { 'market.price': 1 },
    }
  );
  
  if (!observation?.market?.price) {
    console.warn(`[OutcomeResolver] No price found for ${asset} around ${targetTimestamp.toISOString()}`);
    return null;
  }
  
  return observation.market.price;
}

/**
 * Main resolver job
 */
export async function runOutcomeResolverJob(): Promise<void> {
  console.log('[OutcomeResolver] 🚀 Starting...');
  
  const t0 = Date.now();
  
  try {
    // Find unresolved outcomes
    const outcomes = await findUnresolvedOutcomes(100);
    
    if (outcomes.length === 0) {
      console.log('[OutcomeResolver] ✅ No outcomes ready to resolve');
      return;
    }
    
    console.log(`[OutcomeResolver] Found ${outcomes.length} outcomes to resolve`);
    
    let resolved = 0;
    let failed = 0;
    
    for (const outcome of outcomes) {
      try {
        // Calculate target timestamp (predictedAt + horizon)
        const horizonMs = outcome.horizon === '24H' ? 24 * 60 * 60 * 1000
          : outcome.horizon === '7D' ? 7 * 24 * 60 * 60 * 1000
          : 30 * 24 * 60 * 60 * 1000;
        
        const targetTimestamp = new Date(outcome.predictedAt.getTime() + horizonMs);
        
        // Fetch actual price
        const actualPrice = await getActualPrice(outcome.asset, targetTimestamp);
        
        if (!actualPrice) {
          failed++;
          console.warn(`[OutcomeResolver] ⚠️  ${outcome.asset} ${outcome.horizon}: no price data`);
          continue;
        }
        
        // Resolve outcome
        await resolveOutcome(outcome._id!, actualPrice, outcome.entryPrice);
        
        resolved++;
        
        const actualReturn = ((actualPrice - outcome.entryPrice) / outcome.entryPrice * 100).toFixed(2);
        console.log(`[OutcomeResolver] ✅ ${outcome.asset} ${outcome.horizon}: ${outcome.direction} → ${actualReturn}% return`);
        
      } catch (err: any) {
        failed++;
        console.error(`[OutcomeResolver] ❌ ${outcome.asset} ${outcome.horizon}:`, err.message);
      }
    }
    
    const durationMs = Date.now() - t0;
    console.log(`[OutcomeResolver] ✅ Complete: ${resolved} resolved, ${failed} failed, ${durationMs}ms`);
    
  } catch (err: any) {
    console.error('[OutcomeResolver] Job failed:', err.message);
  }
}

/**
 * Scheduler - run every 1 hour
 */
let intervalId: NodeJS.Timeout | null = null;
const INTERVAL_MS = 60 * 60 * 1000; // 1 hour

export function startOutcomeResolverScheduler(): void {
  if (intervalId) {
    console.log('[OutcomeResolverScheduler] Already running');
    return;
  }
  
  console.log('[OutcomeResolverScheduler] ✅ Starting (every 1 hour)');
  
  // Run immediately on startup
  runOutcomeResolverJob().catch(err => {
    console.error('[OutcomeResolverScheduler] Initial run failed:', err.message);
  });
  
  // Then every hour
  intervalId = setInterval(() => {
    runOutcomeResolverJob().catch(err => {
      console.error('[OutcomeResolverScheduler] Scheduled run failed:', err.message);
    });
  }, INTERVAL_MS);
}

export function stopOutcomeResolverScheduler(): void {
  if (intervalId) {
    clearInterval(intervalId);
    intervalId = null;
    console.log('[OutcomeResolverScheduler] ✅ Stopped');
  }
}

console.log('[OutcomeResolver] Job loaded');
