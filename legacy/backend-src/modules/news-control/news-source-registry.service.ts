/**
 * News Source Registry Service
 * ============================
 * Manages news feed sources: enable/disable, track stats, health monitoring.
 * Collection: news_sources
 *
 * CONTROL LAYER — no AI, no clustering, no ML impact.
 */

import mongoose from 'mongoose';
import { CRYPTO_RSS_FEEDS } from './crypto-rss-feeds.js';

const SOURCES_COLLECTION = 'news_sources';

export interface NewsSource {
  id: string;
  name: string;
  url: string;
  enabled: boolean;
  tier: 'A' | 'B' | 'C';
  lang: string;

  // Tracking
  lastFetchAt: Date | null;
  lastSuccessAt: Date | null;
  lastErrorAt: Date | null;
  lastError: string | null;
  consecutiveFailures: number;
  totalFetches: number;
  totalSuccess: number;
  totalErrors: number;
  totalArticles: number;
  avgLatencyMs: number;

  // Derived
  successRate: number;
  healthy: boolean;
  createdAt: Date;
  updatedAt: Date;
}

// Full 120+ RSS feed registry loaded from crypto-rss-feeds.ts
const DEFAULT_FEEDS: Pick<NewsSource, 'id' | 'name' | 'url' | 'tier' | 'lang'>[] = CRYPTO_RSS_FEEDS;

const MAX_CONSECUTIVE_FAILURES = 3;

class NewsSourceRegistryService {
  private initialized = false;

  /**
   * Ensure all default sources exist in the collection.
   */
  async ensureDefaults(): Promise<void> {
    if (this.initialized) return;
    const db = mongoose.connection.db;
    if (!db) return;

    const col = db.collection(SOURCES_COLLECTION);
    await col.createIndex({ id: 1 }, { unique: true });

    for (const feed of DEFAULT_FEEDS) {
      await col.updateOne(
        { id: feed.id },
        {
          $setOnInsert: {
            ...feed,
            enabled: true,
            lastFetchAt: null,
            lastSuccessAt: null,
            lastErrorAt: null,
            lastError: null,
            consecutiveFailures: 0,
            totalFetches: 0,
            totalSuccess: 0,
            totalErrors: 0,
            totalArticles: 0,
            avgLatencyMs: 0,
            successRate: 1,
            healthy: true,
            createdAt: new Date(),
            updatedAt: new Date(),
          },
        },
        { upsert: true }
      );
    }

    this.initialized = true;
    const count = await col.countDocuments();
    console.log(`[NewsSourceRegistry] ${count} sources in DB (${DEFAULT_FEEDS.length} feeds in registry)`);
  }

  /**
   * Get all sources (for admin UI).
   */
  async getAll(): Promise<NewsSource[]> {
    await this.ensureDefaults();
    const db = mongoose.connection.db;
    if (!db) return [];

    return db.collection<NewsSource>(SOURCES_COLLECTION)
      .find({}, { projection: { _id: 0 } })
      .sort({ tier: 1, name: 1 })
      .toArray() as unknown as NewsSource[];
  }

  /**
   * Get only enabled sources (for adapter).
   */
  async getEnabled(): Promise<NewsSource[]> {
    await this.ensureDefaults();
    const db = mongoose.connection.db;
    if (!db) return [];

    return db.collection<NewsSource>(SOURCES_COLLECTION)
      .find({ enabled: true }, { projection: { _id: 0 } })
      .sort({ tier: 1, name: 1 })
      .toArray() as unknown as NewsSource[];
  }

  /**
   * Toggle a source on/off.
   */
  async toggle(sourceId: string, enabled: boolean): Promise<NewsSource | null> {
    const db = mongoose.connection.db;
    if (!db) return null;

    const result = await db.collection(SOURCES_COLLECTION).findOneAndUpdate(
      { id: sourceId },
      { $set: { enabled, updatedAt: new Date() } },
      { returnDocument: 'after', projection: { _id: 0 } }
    );

    return result as unknown as NewsSource | null;
  }

  /**
   * Record a successful fetch for a source.
   */
  async recordSuccess(sourceId: string, articlesCount: number, latencyMs: number): Promise<void> {
    const db = mongoose.connection.db;
    if (!db) return;

    const col = db.collection(SOURCES_COLLECTION);
    const doc = await col.findOne({ id: sourceId });
    const totalFetches = (doc?.totalFetches || 0) + 1;
    const totalSuccess = (doc?.totalSuccess || 0) + 1;
    const totalArticles = (doc?.totalArticles || 0) + articlesCount;
    const oldAvg = doc?.avgLatencyMs || 0;
    const avgLatencyMs = Math.round((oldAvg * (totalFetches - 1) + latencyMs) / totalFetches);
    const successRate = Math.round((totalSuccess / totalFetches) * 100) / 100;

    await col.updateOne(
      { id: sourceId },
      {
        $set: {
          lastFetchAt: new Date(),
          lastSuccessAt: new Date(),
          consecutiveFailures: 0,
          totalFetches,
          totalSuccess,
          totalArticles,
          avgLatencyMs,
          successRate,
          healthy: true,
          updatedAt: new Date(),
        },
      }
    );
  }

  /**
   * Record a failed fetch for a source.
   */
  async recordFailure(sourceId: string, error: string): Promise<void> {
    const db = mongoose.connection.db;
    if (!db) return;

    const col = db.collection(SOURCES_COLLECTION);
    const doc = await col.findOne({ id: sourceId });
    const totalFetches = (doc?.totalFetches || 0) + 1;
    const totalErrors = (doc?.totalErrors || 0) + 1;
    const consecutiveFailures = (doc?.consecutiveFailures || 0) + 1;
    const totalSuccess = doc?.totalSuccess || 0;
    const successRate = totalFetches > 0 ? Math.round((totalSuccess / totalFetches) * 100) / 100 : 0;
    const healthy = consecutiveFailures < MAX_CONSECUTIVE_FAILURES;

    await col.updateOne(
      { id: sourceId },
      {
        $set: {
          lastFetchAt: new Date(),
          lastErrorAt: new Date(),
          lastError: error.slice(0, 500),
          consecutiveFailures,
          totalFetches,
          totalErrors,
          successRate,
          healthy,
          updatedAt: new Date(),
        },
      }
    );

    if (!healthy) {
      console.warn(`[NewsSourceRegistry] SOURCE UNHEALTHY: ${sourceId} (${consecutiveFailures} consecutive failures)`);
    }
  }
}

export const newsSourceRegistryService = new NewsSourceRegistryService();
