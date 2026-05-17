/**
 * OnChain V2 — Bridge Scheduler
 * ===============================
 * 
 * Scheduled ingestion for bridge events.
 * Respects feature flags and direction completeness.
 */

import pLimit from 'p-limit';
import { bridgeIndexer } from './bridge.indexer.js';
import { bridgeHealthService, BRIDGE_ENABLED, BridgeHealthDeps } from './bridge.health.service.js';
import { chainRegistry, MULTICHAIN_ENABLED, getActiveChainIds } from '../chains/index.js';
import { STATIC_BRIDGE_ADDRESSES } from './bridge.resolver.js';

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

const SCHEDULER_INTERVAL_MS = parseInt(process.env.BRIDGE_SCHEDULER_INTERVAL_MS || '30000', 10);
const MAX_CONCURRENCY = 2;

// ═══════════════════════════════════════════════════════════════
// BRIDGE SCHEDULER
// ═══════════════════════════════════════════════════════════════

class BridgeScheduler {
  private intervalId: ReturnType<typeof setInterval> | null = null;
  private running = false;
  private limit = pLimit(MAX_CONCURRENCY);
  private tickCount = 0;
  private lastTick = 0;
  private lastResults: any = null;

  /**
   * Get health deps
   */
  private getDeps(): BridgeHealthDeps {
    return {
      env: process.env,
      staticMap: STATIC_BRIDGE_ADDRESSES,
      chains: {
        getActiveChainIds: () => chainRegistry.getActiveIds(),
        isActive: (chainId: number) => chainRegistry.isActive(chainId),
      },
      flags: {
        bridgeEnabled: BRIDGE_ENABLED,
        multiChainEnabled: MULTICHAIN_ENABLED,
      },
    };
  }

  /**
   * Start scheduler
   */
  start(): void {
    if (this.intervalId) {
      console.log('[BridgeScheduler] Already running');
      return;
    }

    if (!BRIDGE_ENABLED) {
      console.log('[BridgeScheduler] Bridge disabled, not starting');
      return;
    }

    console.log(`[BridgeScheduler] Starting with interval=${SCHEDULER_INTERVAL_MS}ms`);
    
    // Initial tick after short delay
    setTimeout(() => this.tick(), 5000);
    
    this.intervalId = setInterval(() => this.tick(), SCHEDULER_INTERVAL_MS);
  }

  /**
   * Stop scheduler
   */
  stop(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
      console.log('[BridgeScheduler] Stopped');
    }
  }

  /**
   * Single tick
   */
  private async tick(): Promise<void> {
    if (this.running) {
      console.log('[BridgeScheduler] Previous tick still running');
      return;
    }

    this.running = true;
    this.lastTick = Date.now();
    this.tickCount++;

    try {
      // Check readiness
      const deps = this.getDeps();
      const readiness = await bridgeHealthService.isReadyForIngestion(deps);
      
      if (!readiness.ready) {
        console.log(`[BridgeScheduler] Not ready: ${readiness.reason}`);
        return;
      }

      // Run indexer for all tracks
      const result = await bridgeIndexer.indexAll();
      this.lastResults = result;

      if (result.eventsInserted > 0) {
        console.log(`[BridgeScheduler] Tick #${this.tickCount}: +${result.eventsInserted} events`);
      }

      if (result.errors.length > 0) {
        console.warn(`[BridgeScheduler] Errors:`, result.errors);
      }

    } catch (error) {
      console.error('[BridgeScheduler] Tick error:', error);
    } finally {
      this.running = false;
    }
  }

  /**
   * Force immediate tick
   */
  async forceTick(): Promise<any> {
    await this.tick();
    return this.lastResults;
  }

  /**
   * Get status
   */
  getStatus(): {
    running: boolean;
    enabled: boolean;
    intervalMs: number;
    tickCount: number;
    lastTick: number;
    lastResults: any;
  } {
    return {
      running: this.running,
      enabled: BRIDGE_ENABLED,
      intervalMs: SCHEDULER_INTERVAL_MS,
      tickCount: this.tickCount,
      lastTick: this.lastTick,
      lastResults: this.lastResults,
    };
  }
}

// Singleton
export const bridgeScheduler = new BridgeScheduler();

console.log('[OnChain V2] Bridge Scheduler loaded');
