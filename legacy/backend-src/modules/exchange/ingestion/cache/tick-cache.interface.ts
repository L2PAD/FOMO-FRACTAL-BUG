/**
 * Tick Cache Interface - Abstraction для замены на Redis
 */
import { RawTick } from '../types/market-data.js';

export interface ITickCache {
  push(symbol: string, tick: RawTick, maxPerSymbol?: number): Promise<void> | void;
  getLatest(symbol: string): Promise<RawTick[]> | RawTick[];
  getFresh(symbol: string, maxAgeMs?: number): Promise<RawTick[]> | RawTick[];
  clear(symbol?: string): Promise<void> | void;
}
