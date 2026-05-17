/**
 * Sentiment Historical Replay Service
 * =====================================
 * 
 * Walk-forward replay of historical tweets through sentiment pipeline.
 * 
 * RULES (NO LEAKAGE):
 * - Process tweets by date order (oldest first)
 * - Aggregates use only tweets up to asOf date
 * - Forward returns calculated AFTER window closes
 * - No access to future data at any point
 * 
 * ISOLATION:
 * - Does NOT affect live sentiment pipeline
 * - Uses separate replay collections if needed
 * - Can be run in background
 * 
 * V2 ENHANCEMENTS:
 * - Parallel batch processing (concurrency limit)
 * - Retry with exponential backoff
 * - Global rate limit guard
 * - Detailed logging (success/failed/skipped)
 */

import axios from 'axios';

// TOP 20 crypto symbols for sentiment
export const REPLAY_SYMBOLS = [
  'BTC', 'ETH', 'SOL', 'XRP', 'BNB',
  'ADA', 'AVAX', 'DOGE', 'LINK', 'MATIC',
  'DOT', 'LTC', 'TRX', 'UNI', 'ATOM',
  'APT', 'ARB', 'OP', 'INJ', 'SUI'
];

export interface ReplayConfig {
  daysBack: number;
  tweetsPerDayPerSymbol: number;
  delayBetweenRequests: number; // ms
  parserUrl: string;
  userId: string;
  concurrency?: number; // parallel batch size (default: 4)
  maxRetries?: number;
}

export interface ReplayProgress {
  totalDays: number;
  completedDays: number;
  currentDate: string;
  currentSymbol: string;
  tweetsCollected: number;
  errors: number;
  skipped: number;
  successRequests: number;
  failedRequests: number;
  status: 'IDLE' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  startedAt?: Date;
  completedAt?: Date;
  concurrency: number;
}

export class SentimentHistoricalReplayService {
  private progress: ReplayProgress = {
    totalDays: 0,
    completedDays: 0,
    currentDate: '',
    currentSymbol: '',
    tweetsCollected: 0,
    errors: 0,
    skipped: 0,
    successRequests: 0,
    failedRequests: 0,
    status: 'IDLE',
    concurrency: 4,
  };

  private aborted = false;

  /**
   * Format date as YYYY-MM-DD
   */
  private formatDate(d: Date): string {
    return d.toISOString().split('T')[0];
  }

  /**
   * Get replay progress
   */
  getProgress(): ReplayProgress {
    return { ...this.progress };
  }

  /**
   * Abort running replay
   */
  abort(): void {
    this.aborted = true;
    console.log('[Replay] Abort requested');
  }

  /**
   * Sleep helper
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(r => setTimeout(r, ms));
  }

  /**
   * Fetch tweets for a symbol/date with retry logic
   */
  private async fetchWithRetry(args: {
    parserUrl: string;
    userId: string;
    symbol: string;
    sinceStr: string;
    untilStr: string;
    limit: number;
    maxRetries: number;
    delayMs: number;
  }): Promise<{ ok: boolean; fetched: number }> {
    const { parserUrl, userId, symbol, sinceStr, untilStr, limit, maxRetries, delayMs } = args;

    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        const response = await axios.post(
          `${parserUrl}/api/v4/twitter/parse/search`,
          {
            query: symbol,
            limit,
            dateRange: { since: sinceStr, until: untilStr },
          },
          {
            headers: {
              'Content-Type': 'application/json',
              'x-user-id': userId,
            },
            timeout: 120000,
          }
        );

        if (response.data?.ok) {
          return { ok: true, fetched: response.data.data?.fetched || 0 };
        }
        return { ok: false, fetched: 0 };
      } catch (err: any) {
        const isRateLimit = err.response?.status === 429;
        const waitMs = isRateLimit 
          ? delayMs * Math.pow(2, attempt + 1) 
          : delayMs * (attempt + 1);
        
        if (attempt < maxRetries - 1) {
          console.warn(`[Replay] Retry ${attempt + 1}/${maxRetries} for ${symbol} ${sinceStr}: ${err.message}`);
          await this.sleep(waitMs);
        }
      }
    }
    return { ok: false, fetched: 0 };
  }

  /**
   * Process symbols in batches (parallel)
   */
  private async processBatch(args: {
    symbols: string[];
    sinceStr: string;
    untilStr: string;
    config: ReplayConfig;
  }): Promise<void> {
    const { symbols, sinceStr, untilStr, config } = args;

    const promises = symbols.map(async (symbol) => {
      if (this.aborted) return;

      const result = await this.fetchWithRetry({
        parserUrl: config.parserUrl,
        userId: config.userId,
        symbol,
        sinceStr,
        untilStr,
        limit: config.tweetsPerDayPerSymbol,
        maxRetries: config.maxRetries || 3,
        delayMs: config.delayBetweenRequests,
      });

      if (result.ok) {
        this.progress.successRequests++;
        this.progress.tweetsCollected += result.fetched;
        if (result.fetched > 0) {
          console.log(`[Replay] ✓ ${symbol} ${sinceStr}: ${result.fetched} tweets`);
        }
      } else {
        this.progress.failedRequests++;
        this.progress.errors++;
        console.log(`[Replay] ✗ ${symbol} ${sinceStr}: failed`);
      }
    });

    await Promise.all(promises);
  }

  /**
   * Run historical replay with parallel batches
   */
  async runReplay(config: ReplayConfig): Promise<ReplayProgress> {
    const { daysBack, delayBetweenRequests, concurrency = 4 } = config;

    this.aborted = false;
    this.progress = {
      totalDays: daysBack,
      completedDays: 0,
      currentDate: '',
      currentSymbol: '',
      tweetsCollected: 0,
      errors: 0,
      skipped: 0,
      successRequests: 0,
      failedRequests: 0,
      status: 'RUNNING',
      startedAt: new Date(),
      concurrency,
    };

    const totalRequests = daysBack * REPLAY_SYMBOLS.length;
    console.log(`[Replay] Starting | ${daysBack} days | ${REPLAY_SYMBOLS.length} symbols | concurrency=${concurrency}`);
    console.log(`[Replay] Total requests: ${totalRequests} | Est. time: ${this.estimateDuration(config).estimatedMinutes} min`);

    const today = new Date();

    try {
      // Process days from oldest to newest (walk-forward)
      for (let i = daysBack; i >= 1 && !this.aborted; i--) {
        const since = new Date(today);
        since.setDate(today.getDate() - i);

        const until = new Date(since);
        until.setDate(since.getDate() + 1);

        const sinceStr = this.formatDate(since);
        const untilStr = this.formatDate(until);

        this.progress.currentDate = sinceStr;
        console.log(`[Replay] Day ${daysBack - i + 1}/${daysBack}: ${sinceStr}`);

        // Split symbols into batches
        for (let j = 0; j < REPLAY_SYMBOLS.length && !this.aborted; j += concurrency) {
          const batch = REPLAY_SYMBOLS.slice(j, j + concurrency);
          this.progress.currentSymbol = batch.join(',');

          await this.processBatch({
            symbols: batch,
            sinceStr,
            untilStr,
            config,
          });

          // Rate limit guard between batches
          if (j + concurrency < REPLAY_SYMBOLS.length) {
            await this.sleep(delayBetweenRequests);
          }
        }

        this.progress.completedDays++;
      }

      this.progress.status = this.aborted ? 'FAILED' : 'COMPLETED';
      this.progress.completedAt = new Date();

      const duration = this.progress.completedAt.getTime() - (this.progress.startedAt?.getTime() || 0);
      console.log(`[Replay] DONE | ${this.progress.tweetsCollected} tweets | ${this.progress.successRequests} ok | ${this.progress.failedRequests} failed | ${Math.round(duration / 60000)} min`);

    } catch (err: any) {
      this.progress.status = 'FAILED';
      console.error('[Replay] Fatal error:', err.message);
    }

    return this.progress;
  }

  /**
   * Estimate replay duration (accounting for parallelism)
   */
  estimateDuration(config: ReplayConfig): { 
    totalRequests: number; 
    estimatedMinutes: number;
  } {
    const concurrency = config.concurrency || 4;
    const totalRequests = config.daysBack * REPLAY_SYMBOLS.length;
    const batchesPerDay = Math.ceil(REPLAY_SYMBOLS.length / concurrency);
    const totalBatches = config.daysBack * batchesPerDay;
    // Each batch takes ~2s avg request + delay between batches
    const estimatedMs = totalBatches * (2000 + config.delayBetweenRequests);
    const estimatedMinutes = Math.ceil(estimatedMs / 60000);

    return { totalRequests, estimatedMinutes };
  }
}

// Singleton
let replayServiceInstance: SentimentHistoricalReplayService | null = null;

export function getSentimentReplayService(): SentimentHistoricalReplayService {
  if (!replayServiceInstance) {
    replayServiceInstance = new SentimentHistoricalReplayService();
  }
  return replayServiceInstance;
}

console.log('[Sentiment-ML] Historical Replay Service loaded');
