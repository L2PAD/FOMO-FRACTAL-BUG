/**
 * Memory Tick Cache - In-memory реализация (можно заменить на Redis)
 */
import { ITickCache } from './tick-cache.interface.js';
import { RawTick } from '../types/market-data.js';

export class MemoryTickCache implements ITickCache {
  private ticks = new Map<string, RawTick[]>();

  push(symbol: string, tick: RawTick, maxPerSymbol = 50): void {
    const current = this.ticks.get(symbol) ?? [];
    current.push(tick);

    if (current.length > maxPerSymbol) {
      current.splice(0, current.length - maxPerSymbol);
    }

    this.ticks.set(symbol, current);
  }

  getLatest(symbol: string): RawTick[] {
    return [...(this.ticks.get(symbol) ?? [])];
  }

  getFresh(symbol: string, maxAgeMs = 15_000): RawTick[] {
    const now = Date.now();
    return this.getLatest(symbol).filter((tick) => now - tick.timestamp <= maxAgeMs);
  }

  clear(symbol?: string): void {
    if (symbol) {
      this.ticks.delete(symbol);
      return;
    }
    this.ticks.clear();
  }
}

// Singleton instance
export const memoryTickCache = new MemoryTickCache();
