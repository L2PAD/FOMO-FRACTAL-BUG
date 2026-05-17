/**
 * Sentiment Shadow Window Service
 * =================================
 * 
 * BLOCK 4/5: Provides shadow statistics for lookback windows.
 * 
 * Used by:
 * - Auto-promotion: Check sustained lift over 3 windows
 * - Auto-rollback: Check degradation in 14-day window
 */

import mongoose from 'mongoose';
import type { SentimentWindow } from '../contracts/sentiment-ml.types.js';

export interface ShadowWindowStats {
  finalized: number;
  hitRule: number;
  hitML: number;
  avgRetRule: number;
  avgRetML: number;
  edgeDelta: number;      // hitML - hitRule (as rate, not count)
  disagreement: number;   // rate of disagreements
}

export class SentimentShadowWindowService {
  private readonly collectionName = 'sentiment_shadow_decisions';

  /**
   * Get shadow stats for a specific lookback window
   */
  async getWindowStats(window: SentimentWindow, lookbackDays: number): Promise<ShadowWindowStats> {
    const db = mongoose.connection.db;
    if (!db) {
      return this.emptyStats();
    }

    const col = db.collection(this.collectionName);
    const since = new Date(Date.now() - lookbackDays * 24 * 60 * 60 * 1000);

    // Find finalized decisions in the window
    const docs = await col
      .find({ 
        window, 
        evaluated: true, 
        createdAt: { $gte: since } 
      })
      .project({
        ruleCorrect: 1,
        mlCorrect: 1,
        forwardReturn: 1,
        agreement: 1,
      })
      .toArray();

    const finalized = docs.length;
    if (finalized === 0) {
      return this.emptyStats();
    }

    let hitRule = 0;
    let hitML = 0;
    let sumRet = 0;
    let disag = 0;

    for (const d of docs) {
      if (d.ruleCorrect) hitRule += 1;
      if (d.mlCorrect) hitML += 1;
      sumRet += Number(d.forwardReturn ?? 0);
      if (!d.agreement) disag += 1;
    }

    const hrRule = hitRule / finalized;
    const hrML = hitML / finalized;
    const avgRet = sumRet / finalized;

    return {
      finalized,
      hitRule,
      hitML,
      avgRetRule: avgRet,  // Same underlying return for both
      avgRetML: avgRet,
      edgeDelta: hrML - hrRule,
      disagreement: disag / finalized,
    };
  }

  /**
   * Get stats for multiple windows (for sustained lift check)
   */
  async getMultiWindowStats(window: SentimentWindow, windowDays: number, windowCount: number): Promise<ShadowWindowStats[]> {
    const results: ShadowWindowStats[] = [];
    
    for (let i = 0; i < windowCount; i++) {
      const lookback = windowDays * (i + 1);
      const stats = await this.getWindowStats(window, lookback);
      results.push(stats);
    }
    
    return results;
  }

  private emptyStats(): ShadowWindowStats {
    return {
      finalized: 0,
      hitRule: 0,
      hitML: 0,
      avgRetRule: 0,
      avgRetML: 0,
      edgeDelta: 0,
      disagreement: 0,
    };
  }
}

// Singleton
let windowServiceInstance: SentimentShadowWindowService | null = null;

export function getSentimentShadowWindowService(): SentimentShadowWindowService {
  if (!windowServiceInstance) {
    windowServiceInstance = new SentimentShadowWindowService();
  }
  return windowServiceInstance;
}

console.log('[Sentiment-ML] Shadow Window Service loaded (BLOCK 4/5)');
