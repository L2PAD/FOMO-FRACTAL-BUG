/**
 * System Locks Service
 * ====================
 * 
 * Provides distributed locking for background jobs.
 * Ensures only one instance of a job runs at a time.
 * 
 * Usage:
 *   const locks = new SystemLocksService();
 *   const handle = await locks.acquire('my_job', 5 * 60 * 1000);
 *   if (!handle) return; // someone else has the lock
 *   try {
 *     // do work
 *   } finally {
 *     await locks.release(handle);
 *   }
 */

import crypto from 'crypto';
import { SystemLockModel } from './system-lock.model.js';

export type LockHandle = { key: string; owner: string };

export class SystemLocksService {
  private readonly owner: string;

  constructor(owner?: string) {
    this.owner = owner ?? `pid:${process.pid}:${crypto.randomUUID()}`;
  }

  /**
   * Attempt to acquire a lock.
   * Returns LockHandle if successful, null if lock is held by someone else.
   */
  async acquire(key: string, ttlMs: number): Promise<LockHandle | null> {
    const now = new Date();
    const lockedUntil = new Date(now.getTime() + ttlMs);

    try {
      // Acquire if expired OR absent
      const res = await SystemLockModel.findOneAndUpdate(
        {
          key,
          $or: [
            { lockedUntil: { $lte: now } },
            { lockedUntil: { $exists: false } },
          ],
        },
        { $set: { lockedUntil, owner: this.owner } },
        { upsert: true, new: true }
      ).lean();

      // Check if we actually got the lock
      if (!res || res.owner !== this.owner) {
        return null;
      }

      return { key, owner: this.owner };
    } catch (err: any) {
      // Duplicate key error means someone else got it
      if (err?.code === 11000) {
        return null;
      }
      throw err;
    }
  }

  /**
   * Release a lock (set lockedUntil to now, allowing immediate reacquisition)
   */
  async release(handle: LockHandle): Promise<boolean> {
    const now = new Date();
    const res = await SystemLockModel.updateOne(
      { key: handle.key, owner: handle.owner },
      { $set: { lockedUntil: now } }
    );
    return res.modifiedCount > 0;
  }

  /**
   * Force release a lock (admin use only)
   */
  async forceRelease(key: string): Promise<boolean> {
    const now = new Date();
    const res = await SystemLockModel.updateOne(
      { key },
      { $set: { lockedUntil: now } }
    );
    return res.modifiedCount > 0;
  }

  /**
   * Get lock status
   */
  async getStatus(key: string): Promise<{ locked: boolean; owner?: string; lockedUntil?: Date } | null> {
    const lock = await SystemLockModel.findOne({ key }).lean();
    if (!lock) return null;
    
    const now = new Date();
    return {
      locked: lock.lockedUntil > now,
      owner: lock.owner,
      lockedUntil: lock.lockedUntil,
    };
  }
}

// Singleton instance
let locksInstance: SystemLocksService | null = null;

export function getSystemLocksService(): SystemLocksService {
  if (!locksInstance) {
    locksInstance = new SystemLocksService();
  }
  return locksInstance;
}
