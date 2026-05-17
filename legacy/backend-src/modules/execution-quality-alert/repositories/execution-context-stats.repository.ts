/**
 * Execution Context Stats Repository
 *
 * Stores per-context execution score entries with time windowing.
 * Uses contextKey as the primary lookup key.
 */

import { MongoClient } from 'mongodb';
import type { ContextStats, ExecutionScoreEntry, ExecutionContext } from '../types/execution-context.types.js';

const MONGO_URL = process.env.MONGO_URL || 'mongodb://localhost:27017';
const DB_NAME = process.env.DB_NAME || 'intelligence_engine';
const COLLECTION = 'execution_context_stats';
const TIME_WINDOW_DAYS = 7;
const MAX_ENTRIES_PER_CONTEXT = 50;

class ExecutionContextStatsRepository {
  private async col() {
    const client = new MongoClient(MONGO_URL);
    await client.connect();
    return client.db(DB_NAME).collection(COLLECTION);
  }

  /**
   * Add a score entry to a context. Auto-prunes entries outside time window.
   */
  async addEntry(contextKey: string, context: ExecutionContext, entry: ExecutionScoreEntry): Promise<ContextStats> {
    const col = await this.col();
    const cutoff = new Date(Date.now() - TIME_WINDOW_DAYS * 24 * 60 * 60 * 1000).toISOString();

    // Upsert context stats
    await col.updateOne(
      { contextKey },
      {
        $push: {
          entries: {
            $each: [entry],
            $slice: -MAX_ENTRIES_PER_CONTEXT,
          },
        },
        $set: { context, updatedAt: new Date().toISOString() },
        $inc: { totalCount: 1 },
        $setOnInsert: { contextKey },
      },
      { upsert: true },
    );

    // Pull expired entries (outside time window)
    await col.updateOne(
      { contextKey },
      { $pull: { entries: { timestamp: { $lt: cutoff } } } as any },
    );

    // Return fresh state
    const doc = await col.findOne({ contextKey }, { projection: { _id: 0 } });
    return (doc as unknown as ContextStats) || { contextKey, context, entries: [], totalCount: 0, updatedAt: new Date().toISOString() };
  }

  /**
   * Get stats for a specific context.
   */
  async getStats(contextKey: string): Promise<ContextStats | null> {
    const col = await this.col();
    const doc = await col.findOne({ contextKey }, { projection: { _id: 0 } });
    return doc as unknown as ContextStats | null;
  }

  /**
   * Get all contexts with at least minEntries entries.
   */
  async getActiveContexts(minEntries = 1): Promise<ContextStats[]> {
    const col = await this.col();
    return col
      .find({ totalCount: { $gte: minEntries } }, { projection: { _id: 0 } })
      .sort({ updatedAt: -1 })
      .limit(100)
      .toArray() as unknown as ContextStats[];
  }

  /**
   * Get entries across ALL contexts for a given asset (for style comparison).
   */
  async getEntriesByAsset(asset: string, limit = 200): Promise<ExecutionScoreEntry[]> {
    const col = await this.col();
    const docs = await col
      .find({}, { projection: { _id: 0, entries: 1 } })
      .toArray();

    const allEntries: ExecutionScoreEntry[] = [];
    for (const doc of docs) {
      for (const entry of (doc as any).entries || []) {
        if (entry.asset === asset) allEntries.push(entry);
      }
    }
    return allEntries.sort((a, b) => b.timestamp.localeCompare(a.timestamp)).slice(0, limit);
  }
}

export const contextStatsRepo = new ExecutionContextStatsRepository();
