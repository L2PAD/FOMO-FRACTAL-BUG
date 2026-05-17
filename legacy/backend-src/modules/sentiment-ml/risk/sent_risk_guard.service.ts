/**
 * Sentiment Risk Guard Service
 * ==============================
 * 
 * BLOCK 6C: Exposure + Concurrency + Cooldown guards.
 * 
 * Rules:
 * - CHOP gate: |bias| must exceed threshold
 * - Symbol cap: max 1 active per symbol (all windows)
 * - Window cap: max N active per window
 * - Concurrency: only 1 active per (symbol, window, mode)
 * - Cooldown: wait period after closing
 */

import { SentPositionStateModel } from './sent_position_state.model.js';
import { 
  SentWindow, 
  SentMode,
  CHOP_FLOOR,
  COOLDOWN_MS,
  MAX_ACTIVE_BY_WINDOW,
} from '../contracts/sentiment.risk.types.js';

export interface CanOpenResult {
  ok: boolean;
  reason?: string;
}

export class SentRiskGuardService {
  /**
   * Check if a new position can be opened
   */
  async canOpen(params: {
    symbol: string;
    window: SentWindow;
    mode: SentMode;
    asOf: Date;
    closesAt: Date;
    bias: number;
  }): Promise<CanOpenResult> {
    const { symbol, window, mode, asOf, bias } = params;

    // 0) CHOP gate (signal too weak)
    if (Math.abs(bias) < CHOP_FLOOR[window]) {
      return { ok: false, reason: 'CHOP_GATE' };
    }

    // 1) Per-symbol cap (all windows combined) - max 1
    const activeForSymbol = await SentPositionStateModel.countDocuments({
      symbol,
      status: 'ACTIVE',
    });
    if (activeForSymbol >= 1) {
      return { ok: false, reason: 'SYMBOL_CAP' };
    }

    // 2) Window exposure cap
    const activeByWindow = await SentPositionStateModel.countDocuments({
      window,
      status: 'ACTIVE',
    });
    if (activeByWindow >= MAX_ACTIVE_BY_WINDOW[window]) {
      return { ok: false, reason: 'WINDOW_EXPOSURE_CAP' };
    }

    // 3) Concurrency: only one active per (symbol, window, mode)
    const activeSame = await SentPositionStateModel.findOne({
      symbol,
      window,
      mode,
      status: 'ACTIVE',
    }).lean();

    if (activeSame) {
      return { ok: false, reason: 'CONCURRENCY_ACTIVE' };
    }

    // 4) Cooldown (based on lastClosedAt for same symbol+window+mode)
    const lastClosed = await SentPositionStateModel.findOne({
      symbol,
      window,
      mode,
      status: 'CLOSED',
    }).sort({ lastClosedAt: -1 }).lean();

    if (lastClosed?.lastClosedAt) {
      const dt = asOf.getTime() - new Date(lastClosed.lastClosedAt).getTime();
      if (dt < COOLDOWN_MS[window]) {
        return { ok: false, reason: 'COOLDOWN' };
      }
    }

    return { ok: true };
  }

  /**
   * Get current exposure stats
   */
  async getExposureStats(): Promise<{
    byWindow: Record<SentWindow, number>;
    bySymbol: Record<string, number>;
    total: number;
  }> {
    const active = await SentPositionStateModel.find({ status: 'ACTIVE' }).lean();

    const byWindow: Record<SentWindow, number> = { '24H': 0, '7D': 0, '30D': 0 };
    const bySymbol: Record<string, number> = {};

    for (const p of active) {
      byWindow[p.window as SentWindow]++;
      bySymbol[p.symbol] = (bySymbol[p.symbol] || 0) + 1;
    }

    return {
      byWindow,
      bySymbol,
      total: active.length,
    };
  }
}

// Singleton
let guardInstance: SentRiskGuardService | null = null;

export function getSentRiskGuardService(): SentRiskGuardService {
  if (!guardInstance) {
    guardInstance = new SentRiskGuardService();
  }
  return guardInstance;
}

console.log('[Sentiment-ML] Risk Guard Service loaded (BLOCK 6C)');
