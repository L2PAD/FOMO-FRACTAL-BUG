/**
 * Universe Loader Service V2 — Priority-based
 * 
 * Reads symbol lists from MongoDB with priority tiers:
 *   P1: Top 100 alpha by alphaScore
 *   P2: Top 100 main by volume
 *   P3: Remainder (round-robin)
 * 
 * Uses dynamic alpha universe (exchange_symbol_universe_alpha_dynamic).
 */

import { MongoClient, Db } from 'mongodb';

const MONGO_URL = process.env.MONGO_URL || 'mongodb://localhost:27017';
const DB_NAME = process.env.DB_NAME || 'intelligence_engine';

let db: Db | null = null;

async function getDb(): Promise<Db> {
  if (db) return db;
  const client = new MongoClient(MONGO_URL);
  await client.connect();
  db = client.db(DB_NAME);
  return db;
}

/**
 * Get prioritized spot symbols for observation collection.
 * Returns up to `limit` symbols, sorted by priority.
 */
export async function getSpotSymbols(limit: number = 200): Promise<string[]> {
  const db = await getDb();
  const seen = new Set<string>();
  const result: string[] = [];
  
  // P2: Main universe symbols sorted by volume (from snapshots)
  const snapshotDocs = await db.collection('exchange_symbol_snapshots')
    .find({}, { projection: { _id: 0, base: 1, features: 1 } })
    .sort({ 'features.volume_log': -1 })
    .toArray();
  
  for (const doc of snapshotDocs) {
    const sym = (doc.base as string) + 'USDT';
    if (!seen.has(sym)) {
      seen.add(sym);
      result.push(sym);
    }
  }
  
  // P3: From exchange_symbol_universe (remaining)
  const universeDocs = await db.collection('exchange_symbol_universe')
    .find({}, { projection: { _id: 0, symbol: 1 } })
    .toArray();
  
  for (const doc of universeDocs) {
    const sym = doc.symbol as string;
    if (!seen.has(sym)) {
      seen.add(sym);
      result.push(sym);
    }
  }
  
  return result.slice(0, limit);
}

/**
 * Get alpha symbols from dynamic universe, sorted by alphaScore.
 * Falls back to static whitelist if dynamic is empty.
 */
export async function getAlphaSymbols(limit: number = 200): Promise<string[]> {
  const db = await getDb();
  
  // Try dynamic alpha first (P1 priority)
  const dynamicDocs = await db.collection('exchange_symbol_universe_alpha_dynamic')
    .find({}, { projection: { _id: 0, symbol: 1, alphaScore: 1 } })
    .sort({ alphaScore: -1 })
    .limit(limit)
    .toArray();
  
  if (dynamicDocs.length >= 10) {
    return dynamicDocs.map(d => d.symbol as string);
  }
  
  // Fallback: static alpha
  const staticDocs = await db.collection('exchange_symbol_universe_alpha')
    .find({}, { projection: { _id: 0, symbol: 1 } })
    .limit(limit)
    .toArray();
  
  return staticDocs.map(d => d.symbol as string);
}

/**
 * Get last observation timestamp for a symbol
 */
export async function getLastObservationTs(symbol: string): Promise<number | null> {
  const db = await getDb();
  
  const doc = await db.collection('exchange_observations')
    .findOne(
      { symbol: symbol.toUpperCase() },
      { projection: { _id: 0, timestamp: 1 }, sort: { timestamp: -1 } }
    );
  
  return doc ? (doc.timestamp as number) : null;
}

console.log('[UniverseLoader] V2 Module loaded (priority-based)');
