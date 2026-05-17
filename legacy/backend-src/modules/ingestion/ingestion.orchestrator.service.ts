/**
 * Ingestion Orchestrator Service
 * ==============================
 * Main service that coordinates ingestion from any adapter:
 * 1. Fetch from adapter
 * 2. Normalize + dedupe key
 * 3. Idempotent upsert to raw_events
 * 4. Record metrics
 *
 * Lock-protected to prevent concurrent runs.
 */

import { bridgeTwitterAdapter } from './adapters/bridge-twitter.adapter.js';
import { newsAdapter } from './adapters/news.adapter.js';
import { dedupeService } from './dedupe/dedupe.service.js';
import { newsDedupeService } from './dedupe/news-dedupe.service.js';
import { ingestionLockService } from './ingestion.lock.service.js';
import { ingestionMetricsService } from './ingestion.metrics.service.js';
import { RawEventModel } from './models/raw-event.model.js';
import type { IngestionRunResult, IngestionAdapter, UnifiedTextEvent } from './ingestion.types.js';

const LOCK_TTL_MS = 4 * 60 * 1000; // 4 minutes

class IngestionOrchestratorService {
  /**
   * Generic ingestion runner — works with any adapter.
   * Handles fetch → dedupe → upsert → metrics.
   */
  private async runAdapterIngestion(
    adapter: IngestionAdapter,
    lockKey: string,
    params?: { limit?: number; sinceMinutes?: number; seedAll?: boolean },
    dedupeOverride?: (event: UnifiedTextEvent) => string,
  ): Promise<IngestionRunResult> {
    const acquired = await ingestionLockService.acquire(lockKey, LOCK_TTL_MS);
    if (!acquired) {
      throw new Error(`LOCK_BUSY: ${lockKey} ingestion already running`);
    }

    const startedAt = new Date();
    let fetched = 0;
    let inserted = 0;
    let duplicated = 0;
    let errors = 0;

    try {
      const events = await adapter.fetch(params);
      fetched = events.length;

      for (const event of events) {
        try {
          // Use override dedupe (e.g., news cross-source) or standard
          event.dedupeKey = dedupeOverride
            ? dedupeOverride(event)
            : dedupeService.buildDedupeKey(event);

          const result = await RawEventModel.updateOne(
            { sourceType: event.sourceType, externalId: event.externalId },
            { $setOnInsert: event },
            { upsert: true }
          );

          if (result.upsertedCount > 0) {
            inserted++;
          } else {
            duplicated++;
          }
        } catch (err: any) {
          if (err.code === 11000) {
            duplicated++;
          } else {
            errors++;
            if (errors <= 3) {
              console.error(`[IngestionOrchestrator] ${adapter.sourceName} error:`, err.message);
            }
          }
        }
      }

      const finishedAt = new Date();
      const result: IngestionRunResult = {
        source: adapter.sourceName,
        fetched,
        inserted,
        duplicated,
        errors,
        durationMs: finishedAt.getTime() - startedAt.getTime(),
        startedAt,
        finishedAt,
      };

      await ingestionMetricsService.record(result);
      return result;
    } finally {
      await ingestionLockService.release(lockKey);
    }
  }

  /**
   * Run bridge ingestion: user_twitter_parsed_tweets -> raw_events
   */
  async runBridgeIngestion(params?: {
    limit?: number;
    sinceMinutes?: number;
    seedAll?: boolean;
  }): Promise<IngestionRunResult> {
    return this.runAdapterIngestion(bridgeTwitterAdapter, 'bridge-twitter', params);
  }

  /**
   * Run news ingestion: parsed_news -> raw_events
   * Uses cross-source headline dedupe for news.
   */
  async runNewsIngestion(params?: {
    limit?: number;
    sinceMinutes?: number;
    seedAll?: boolean;
  }): Promise<IngestionRunResult> {
    return this.runAdapterIngestion(
      newsAdapter,
      'news-parser',
      params,
      (event) => newsDedupeService.buildNewsDedupeKey(event),
    );
  }

  /**
   * Run all adapters sequentially.
   */
  async runAll(params?: {
    limit?: number;
    sinceMinutes?: number;
    seedAll?: boolean;
  }): Promise<IngestionRunResult[]> {
    const results: IngestionRunResult[] = [];

    try {
      results.push(await this.runBridgeIngestion(params));
    } catch (err: any) {
      console.warn('[IngestionOrchestrator] Bridge error:', err.message);
    }

    try {
      results.push(await this.runNewsIngestion(params));
    } catch (err: any) {
      console.warn('[IngestionOrchestrator] News error:', err.message);
    }

    return results;
  }
}

export const ingestionOrchestratorService = new IngestionOrchestratorService();
