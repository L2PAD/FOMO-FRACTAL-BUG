/**
 * Simulation Audit Logger
 * =======================
 * 
 * Logs all simulation events to isolated collection.
 * Used for post-sim analysis and debugging.
 */

import { Db, Collection } from 'mongodb';
import { SimAuditLogger, SimEvent, SimHorizon } from '../exchange_sim.types.js';

const COLLECTION = 'sim_audit_log';

interface AuditLogEntry {
  runId: string;
  type: string;
  simDay: Date;
  realTime: Date;
  symbol?: string;
  horizon?: SimHorizon;
  details?: Record<string, any>;
}

export class SimAuditLoggerImpl implements SimAuditLogger {
  private collection: Collection<AuditLogEntry>;
  private runId: string;
  private events: SimEvent[] = [];
  
  constructor(db: Db, runId: string) {
    this.collection = db.collection<AuditLogEntry>(COLLECTION);
    this.runId = runId;
  }
  
  async log(event: {
    type: string;
    simDay: Date;
    symbol?: string;
    horizon?: SimHorizon;
    details?: Record<string, any>;
  }): Promise<void> {
    const entry: AuditLogEntry = {
      runId: this.runId,
      type: event.type,
      simDay: event.simDay,
      realTime: new Date(),
      symbol: event.symbol,
      horizon: event.horizon,
      details: event.details,
    };
    
    // Store in memory for quick access
    this.events.push({
      type: event.type as any,
      horizon: event.horizon,
      details: event.details || {},
      timestamp: event.simDay,
    });
    
    // Persist to DB
    try {
      await this.collection.insertOne(entry);
    } catch (error: any) {
      console.error('[SimAudit] Log error:', error.message);
    }
  }
  
  async getEvents(): Promise<SimEvent[]> {
    return [...this.events];
  }
  
  async getEventsByType(type: string): Promise<SimEvent[]> {
    return this.events.filter(e => e.type === type);
  }
  
  async getEventCount(): Promise<Record<string, number>> {
    const counts: Record<string, number> = {};
    for (const e of this.events) {
      counts[e.type] = (counts[e.type] || 0) + 1;
    }
    return counts;
  }
  
  // Ensure indexes
  static async ensureIndexes(db: Db): Promise<void> {
    await db.collection(COLLECTION).createIndex({ runId: 1 });
    await db.collection(COLLECTION).createIndex({ runId: 1, type: 1 });
    await db.collection(COLLECTION).createIndex({ runId: 1, simDay: 1 });
  }
}

export function createSimAuditLogger(db: Db, runId: string): SimAuditLoggerImpl {
  return new SimAuditLoggerImpl(db, runId);
}
