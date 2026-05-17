/**
 * Simulation Database Connector
 * =============================
 * 
 * Creates isolated database connection for simulation.
 * NEVER writes to production database.
 */

import { MongoClient, Db } from 'mongodb';

let simClient: MongoClient | null = null;
let simDb: Db | null = null;

export interface SimDbConfig {
  mongoUri: string;
  baseDbName: string;
  dbSuffix: string; // e.g., '_sim'
}

/**
 * Connect to simulation database
 * Creates a separate connection with suffix appended to DB name
 */
export async function connectSimDb(config: SimDbConfig): Promise<Db> {
  if (simDb) {
    return simDb;
  }
  
  const dbName = `${config.baseDbName}${config.dbSuffix}`;
  
  console.log(`[SimDb] Connecting to simulation database: ${dbName}`);
  
  simClient = new MongoClient(config.mongoUri);
  await simClient.connect();
  
  simDb = simClient.db(dbName);
  
  console.log(`[SimDb] Connected to ${dbName}`);
  
  return simDb;
}

/**
 * Get existing simulation database connection
 */
export function getSimDb(): Db {
  if (!simDb) {
    throw new Error('Simulation database not connected. Call connectSimDb first.');
  }
  return simDb;
}

/**
 * Disconnect from simulation database
 */
export async function disconnectSimDb(): Promise<void> {
  if (simClient) {
    await simClient.close();
    simClient = null;
    simDb = null;
    console.log('[SimDb] Disconnected from simulation database');
  }
}

/**
 * Clear all simulation data
 * USE WITH CAUTION - removes all data from sim database
 */
export async function clearSimDb(): Promise<void> {
  if (!simDb) {
    throw new Error('Simulation database not connected');
  }
  
  const collections = await simDb.listCollections().toArray();
  
  for (const col of collections) {
    // Only drop collections with sim_ prefix for safety
    if (col.name.startsWith('sim_')) {
      await simDb.collection(col.name).drop();
      console.log(`[SimDb] Dropped collection: ${col.name}`);
    }
  }
  
  console.log('[SimDb] Cleared all simulation collections');
}

/**
 * Ensure simulation indexes
 */
export async function ensureSimIndexes(db: Db): Promise<void> {
  // Price cache indexes
  await db.collection('sim_price_cache').createIndex(
    { symbol: 1, date: 1 },
    { unique: true }
  );
  
  // Audit log indexes
  await db.collection('sim_audit_log').createIndex({ runId: 1 });
  await db.collection('sim_audit_log').createIndex({ runId: 1, type: 1 });
  
  // Report indexes
  await db.collection('sim_reports').createIndex({ startedAt: -1 });
  
  console.log('[SimDb] Simulation indexes ensured');
}
