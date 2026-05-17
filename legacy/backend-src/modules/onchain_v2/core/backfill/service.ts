/**
 * OnChain V2 — Backfill Service
 * ===============================
 * 
 * Generate historical observations for 30d window.
 * Used to populate initial data for guardrails validation.
 */

import { randomUUID } from 'crypto';
import {
  OnchainObservation,
  OnchainSnapshot,
  OnchainMetrics,
  OnchainState,
  OnchainWindow,
  deriveOnchainState,
} from '../contracts.js';
import { OnchainObservationModel } from '../persistence/models.js';
import { getOnchainProvider, getActiveProviderConfig } from '../../providers/index.js';
import { metricsEngine } from '../metrics/index.js';
import { snapshotService } from '../snapshot/index.js';

// ═══════════════════════════════════════════════════════════════
// BACKFILL SERVICE
// ═══════════════════════════════════════════════════════════════

export interface BackfillOptions {
  symbol: string;
  windowDays: number;
  granularityHours: number;
}

export interface BackfillResult {
  ok: boolean;
  symbol: string;
  window: string;
  granularity: string;
  created: number;
  skipped: number;
  errors: number;
  startTime: number;
  endTime: number;
  durationMs: number;
}

export class OnchainBackfillService {
  /**
   * Run backfill for a symbol
   */
  async runBackfill(options: BackfillOptions): Promise<BackfillResult> {
    const startTime = Date.now();
    const { symbol, windowDays, granularityHours } = options;
    const normalizedSymbol = symbol.toUpperCase().replace('USDT', '').replace('USD', '');
    
    const config = getActiveProviderConfig();
    const now = Date.now();
    const fromTime = now - (windowDays * 24 * 60 * 60 * 1000);
    const stepMs = granularityHours * 60 * 60 * 1000;
    
    let created = 0;
    let skipped = 0;
    let errors = 0;
    
    // Generate timestamps
    const timestamps: number[] = [];
    for (let t = fromTime; t <= now; t += stepMs) {
      timestamps.push(t);
    }
    
    console.log(`[Backfill] Starting for ${normalizedSymbol}: ${timestamps.length} points`);
    
    for (const t0 of timestamps) {
      try {
        // Check if observation already exists
        const existing = await OnchainObservationModel.findOne({
          symbol: normalizedSymbol,
          t0: { $gte: t0 - stepMs / 2, $lte: t0 + stepMs / 2 },
        });
        
        if (existing) {
          skipped++;
          continue;
        }
        
        // Get snapshot for this timestamp
        const snapshotRes = await snapshotService.getSnapshot(normalizedSymbol, t0, '1h');
        
        if (!snapshotRes.ok || !snapshotRes.snapshot) {
          errors++;
          continue;
        }
        
        // Calculate metrics
        const metrics = metricsEngine.calculate(snapshotRes.snapshot);
        const state = deriveOnchainState(metrics, true);
        
        // Create observation
        const observation: Omit<OnchainObservation, 'createdAt' | 'updatedAt'> = {
          id: `obs_${randomUUID().split('-')[0]}`,
          symbol: normalizedSymbol,
          t0,
          window: '1h',
          snapshot: snapshotRes.snapshot,
          metrics,
          state,
          diagnostics: {
            calculatedAt: Date.now(),
            processingTimeMs: 0,
            provider: config.mode,
            providerMode: config.mode,
            warnings: [],
          },
        };
        
        await OnchainObservationModel.create({
          ...observation,
          createdAt: t0,
          updatedAt: Date.now(),
        });
        
        created++;
      } catch (error) {
        console.error(`[Backfill] Error at t0=${t0}:`, error);
        errors++;
      }
    }
    
    const endTime = Date.now();
    
    console.log(`[Backfill] Complete: created=${created}, skipped=${skipped}, errors=${errors}`);
    
    return {
      ok: errors === 0 || created > 0,
      symbol: normalizedSymbol,
      window: `${windowDays}d`,
      granularity: `${granularityHours}h`,
      created,
      skipped,
      errors,
      startTime: fromTime,
      endTime: now,
      durationMs: endTime - startTime,
    };
  }
  
  /**
   * Get observation count for a symbol in time range
   */
  async getObservationCount(symbol: string, windowDays: number): Promise<number> {
    const normalizedSymbol = symbol.toUpperCase().replace('USDT', '').replace('USD', '');
    const fromTime = Date.now() - (windowDays * 24 * 60 * 60 * 1000);
    
    return OnchainObservationModel.countDocuments({
      symbol: normalizedSymbol,
      t0: { $gte: fromTime },
    });
  }
  
  /**
   * Get observation history
   */
  async getHistory(
    symbol: string, 
    windowDays: number,
    limit = 720
  ): Promise<OnchainObservation[]> {
    const normalizedSymbol = symbol.toUpperCase().replace('USDT', '').replace('USD', '');
    const fromTime = Date.now() - (windowDays * 24 * 60 * 60 * 1000);
    
    const docs = await OnchainObservationModel.find({
      symbol: normalizedSymbol,
      t0: { $gte: fromTime },
    })
    .sort({ t0: 1 })
    .limit(limit);
    
    return docs.map(doc => ({
      id: doc.id,
      symbol: doc.symbol,
      t0: doc.t0,
      window: doc.window as OnchainWindow,
      snapshot: doc.snapshot as OnchainSnapshot,
      metrics: doc.metrics as OnchainMetrics,
      state: doc.state as OnchainState,
      diagnostics: doc.diagnostics as OnchainObservation['diagnostics'],
      createdAt: doc.createdAt,
      updatedAt: doc.updatedAt,
    }));
  }
}

// Singleton
export const backfillService = new OnchainBackfillService();

console.log('[OnChain V2] Backfill Service loaded');
