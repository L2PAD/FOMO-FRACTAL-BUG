/**
 * Sentiment Aggregate Worker
 * ==========================
 * 
 * BLOCK 4: Background worker для периодической агрегации
 * 
 * Принцип:
 * - Работает только по TOP20 символам
 * - Запускается каждые N секунд (env: SENTIMENT_AGG_INTERVAL_MS)
 * - Вычисляет агрегаты для всех окон
 * - Изолирован от других модулей
 */

import { sentimentAggregationService, WindowKey } from '../services/sentiment-aggregation.service.js';
import { SENTIMENT_TOP20 } from '../config/top20-symbols.js';
import { getSentimentShadowService } from '../shadow/sentiment.shadow.service.js';

// Track when last shadow decision was recorded per symbol (max 1/hour)
const lastShadowRecord: Map<string, number> = new Map();
const SHADOW_INTERVAL_MS = 60 * 60 * 1000; // 1 hour

export interface AggregateWorkerStats {
  isRunning: boolean;
  startedAt: Date | null;
  tickCount: number;
  lastTickAt: Date | null;
  symbolsProcessed: number;
  aggregatesCreated: number;
  errorsCount: number;
  lastError: string | null;
}

export class SentimentAggregateWorker {
  private running = false;
  private startedAt: Date | null = null;
  private timer: NodeJS.Timeout | null = null;
  
  private stats: AggregateWorkerStats = {
    isRunning: false,
    startedAt: null,
    tickCount: 0,
    lastTickAt: null,
    symbolsProcessed: 0,
    aggregatesCreated: 0,
    errorsCount: 0,
    lastError: null,
  };

  /**
   * Start the worker loop
   */
  async start(): Promise<void> {
    if (this.running) {
      console.log('[SentimentAgg] Worker already running');
      return;
    }

    this.running = true;
    this.startedAt = new Date();
    this.stats.isRunning = true;
    this.stats.startedAt = this.startedAt;

    const intervalMs = parseInt(process.env.SENTIMENT_AGG_INTERVAL_MS || '60000', 10);
    
    console.log(`[SentimentAgg] Worker started (interval ${intervalMs}ms)`);
    console.log(`[SentimentAgg] Processing ${SENTIMENT_TOP20.length} symbols: ${SENTIMENT_TOP20.slice(0, 5).join(', ')}...`);

    // Run immediately on start
    await this.tick();

    // Then schedule periodic runs
    this.timer = setInterval(async () => {
      await this.tick();
    }, intervalMs);
  }

  /**
   * Stop the worker
   */
  stop(): void {
    this.running = false;
    this.stats.isRunning = false;
    
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    
    console.log('[SentimentAgg] Worker stopped');
  }

  /**
   * Get current stats
   */
  getStats(): AggregateWorkerStats {
    return { ...this.stats };
  }

  /**
   * Single tick - process all TOP20 symbols
   */
  private async tick(): Promise<void> {
    this.stats.tickCount++;
    const tickStart = Date.now();
    
    try {
      const now = new Date();
      const windows: WindowKey[] = ['24H', '7D', '30D'];
      
      for (const symbol of SENTIMENT_TOP20) {
        try {
          const results = await sentimentAggregationService.computeForSymbol(symbol, now, windows);
          
          this.stats.symbolsProcessed++;
          this.stats.aggregatesCreated += results.length;
          
          // Log if there are events (for debugging)
          const total = results.reduce((sum, r) => sum + r.eventsCount, 0);
          if (total > 0) {
            console.log(`[SentimentAgg] ${symbol}: ${total} events → score=${results[1]?.score.toFixed(2)} bias=${results[1]?.bias.toFixed(2)}`);
          }
          
          // Record shadow decision for 24H window (for ML accuracy tracking, max 1/hour/symbol)
          const result24H = results.find(r => r.window === '24H');
          const lastRecord = lastShadowRecord.get(symbol) || 0;
          if (result24H && result24H.eventsCount >= 3 && Date.now() - lastRecord > SHADOW_INTERVAL_MS) {
            try {
              const ruleAction = result24H.score > 0.55 ? 'LONG' : result24H.score < 0.45 ? 'SHORT' : 'NEUTRAL';
              await getSentimentShadowService().recordShadowDecision({
                symbol,
                asOf: now,
                ruleAction: ruleAction as 'LONG' | 'SHORT' | 'NEUTRAL',
                ruleConfidence: Math.abs(result24H.score - 0.5) * 2,
                ruleBias: result24H.bias,
                score: result24H.score,
                weightedScore: result24H.score,
                weightedConfidence: Math.abs(result24H.score - 0.5) * 2,
                eventsCount: result24H.eventsCount,
              });
              lastShadowRecord.set(symbol, Date.now());
            } catch (shadowErr: any) {
              // Non-critical — don't break the main loop
            }
          }
        } catch (symbolErr: any) {
          this.stats.errorsCount++;
          this.stats.lastError = `${symbol}: ${symbolErr.message}`;
          console.error(`[SentimentAgg] Error processing ${symbol}:`, symbolErr.message);
        }
      }
      
      this.stats.lastTickAt = new Date();
      
      const duration = Date.now() - tickStart;
      console.log(`[SentimentAgg] Tick #${this.stats.tickCount} completed in ${duration}ms`);
      
    } catch (error: any) {
      this.stats.errorsCount++;
      this.stats.lastError = error.message;
      console.error('[SentimentAgg] Tick error:', error.message);
    }
  }
}

// Singleton instance
let workerInstance: SentimentAggregateWorker | null = null;

/**
 * Get or create worker instance
 */
export function getSentimentAggregateWorker(): SentimentAggregateWorker {
  if (!workerInstance) {
    workerInstance = new SentimentAggregateWorker();
  }
  return workerInstance;
}

/**
 * Start the aggregate worker (call from bootstrap)
 */
export async function startSentimentAggregateWorker(): Promise<void> {
  const enabled = process.env.SENTIMENT_AGG_ENABLED === 'true';
  
  if (!enabled) {
    console.log('[SentimentAgg] Worker disabled (SENTIMENT_AGG_ENABLED != true)');
    return;
  }

  const worker = getSentimentAggregateWorker();
  
  // Start in background
  worker.start().catch(err => {
    console.error('[SentimentAgg] Worker crashed:', err);
  });
}
