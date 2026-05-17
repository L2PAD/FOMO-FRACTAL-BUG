/**
 * On-Chain Lite Service
 * =====================
 * 
 * Unified service with provider switching and MongoDB persistence.
 * 
 * ONCHAIN_MODE=lite → LiteProvider (Infura + DefiLlama)
 * ONCHAIN_MODE=production → EngineProvider (full indexer)
 * 
 * Cache TTL: 60 sec for all endpoints.
 * Total load: ~4 req/min (negligible).
 * 
 * ✅ MongoDB Persistence: All snapshots are saved to `onchain_lite_snapshots` collection
 */

import type {
  IOnchainProvider,
  OnchainSummary,
  OnchainFlows,
  OnchainWhales,
  OnchainActivity,
} from './providers/provider.types.js';
import { LiteProvider } from './providers/lite.provider.js';
import { EngineProvider } from './providers/engine.provider.js';
import mongoose from 'mongoose';

const CACHE_TTL_MS = 60_000;

// MongoDB Schema for Onchain Lite Snapshots
const OnchainLiteSnapshotSchema = {
  type: String,  // 'summary' | 'flows' | 'whales' | 'activity'
  data: Object,
  timestamp: Date,
  provider: String,
};

// Collection name
const COLLECTION_NAME = 'onchain_lite_snapshots';

interface CacheEntry<T> {
  data: T;
  cachedAt: number;
}

class OnchainLiteService {
  private provider: IOnchainProvider;
  private mode: string;
  
  private cache: {
    summary?: CacheEntry<OnchainSummary>;
    flows?: CacheEntry<OnchainFlows>;
    whales?: CacheEntry<OnchainWhales>;
    activity?: CacheEntry<OnchainActivity>;
  } = {};

  constructor() {
    this.mode = process.env.ONCHAIN_MODE || 'preview';
    
    if (this.mode === 'production') {
      this.provider = new EngineProvider();
    } else {
      this.provider = new LiteProvider();
    }
    
    console.log(`[Onchain-Lite] Service initialized in ${this.mode} mode`);
  }

  getMode(): string {
    return this.mode;
  }

  private isFresh<T>(entry?: CacheEntry<T>): entry is CacheEntry<T> {
    return !!entry && (Date.now() - entry.cachedAt < CACHE_TTL_MS);
  }

  async getSummary(): Promise<OnchainSummary> {
    if (this.isFresh(this.cache.summary)) return this.cache.summary.data;
    
    const data = await this.provider.getSummary();
    this.cache.summary = { data, cachedAt: Date.now() };
    
    // ✅ Persist to MongoDB
    await this.persistSnapshot('summary', data);
    
    return data;
  }

  async getFlows(): Promise<OnchainFlows> {
    if (this.isFresh(this.cache.flows)) return this.cache.flows.data;
    
    const data = await this.provider.getFlows();
    this.cache.flows = { data, cachedAt: Date.now() };
    
    // ✅ Persist to MongoDB
    await this.persistSnapshot('flows', data);
    
    return data;
  }

  async getWhales(): Promise<OnchainWhales> {
    if (this.isFresh(this.cache.whales)) return this.cache.whales.data;
    
    const data = await this.provider.getWhales();
    this.cache.whales = { data, cachedAt: Date.now() };
    
    // ✅ Persist to MongoDB
    await this.persistSnapshot('whales', data);
    
    return data;
  }

  async getActivity(): Promise<OnchainActivity> {
    if (this.isFresh(this.cache.activity)) return this.cache.activity.data;
    
    const data = await this.provider.getActivity();
    this.cache.activity = { data, cachedAt: Date.now() };
    
    // ✅ Persist to MongoDB
    await this.persistSnapshot('activity', data);
    
    return data;
  }

  /**
   * Persist snapshot to MongoDB for historical tracking
   */
  private async persistSnapshot(type: string, data: any): Promise<void> {
    try {
      const db = mongoose.connection.db;
      if (!db) {
        console.warn('[Onchain-Lite] MongoDB not connected, skipping persistence');
        return;
      }
      
      const collection = db.collection(COLLECTION_NAME);
      await collection.insertOne({
        type,
        data,
        timestamp: new Date(),
        provider: data.provider || this.mode,
      });
    } catch (err: any) {
      console.warn(`[Onchain-Lite] Failed to persist ${type} snapshot:`, err.message);
    }
  }
}

export const onchainLiteService = new OnchainLiteService();

console.log('[Onchain-Lite] Service loaded');
