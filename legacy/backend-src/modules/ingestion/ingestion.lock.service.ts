/**
 * Ingestion Lock Service
 * ======================
 * MongoDB-based distributed lock to prevent concurrent ingestion runs.
 * Uses TTL-based expiry for automatic cleanup.
 */

import mongoose from 'mongoose';

const LOCK_COLLECTION = 'ingestion_locks';

class IngestionLockService {
  /**
   * Try to acquire a lock. Returns true if acquired.
   */
  async acquire(key: string, ttlMs: number): Promise<boolean> {
    const db = mongoose.connection.db;
    if (!db) return false;

    const now = new Date();
    const expiresAt = new Date(now.getTime() + ttlMs);

    try {
      const result = await db.collection(LOCK_COLLECTION).findOneAndUpdate(
        {
          key,
          $or: [
            { expiresAt: { $lt: now } },
            { expiresAt: { $exists: false } },
          ],
        },
        {
          $set: { key, expiresAt, acquiredAt: now },
        },
        { upsert: true, returnDocument: 'after' }
      );

      return !!result;
    } catch (err: any) {
      // Duplicate key = someone else acquired
      if (err.code === 11000) return false;
      console.error('[IngestionLock] Acquire error:', err.message);
      return false;
    }
  }

  /**
   * Release a lock.
   */
  async release(key: string): Promise<void> {
    const db = mongoose.connection.db;
    if (!db) return;

    await db.collection(LOCK_COLLECTION).deleteOne({ key });
  }

  /**
   * Initialize indexes.
   */
  async ensureIndexes(): Promise<void> {
    const db = mongoose.connection.db;
    if (!db) return;

    await db.collection(LOCK_COLLECTION).createIndex({ key: 1 }, { unique: true });
    await db.collection(LOCK_COLLECTION).createIndex({ expiresAt: 1 }, { expireAfterSeconds: 0 });
  }
}

export const ingestionLockService = new IngestionLockService();
