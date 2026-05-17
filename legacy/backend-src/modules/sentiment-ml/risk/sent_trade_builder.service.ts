/**
 * Sentiment Trade Builder Service
 * =================================
 * 
 * BLOCK 6B: Builds paper trades from finalized samples.
 * 
 * Flow:
 * 1. Get finalized samples
 * 2. Check guards (CHOP, exposure, cooldown)
 * 3. Get entry/exit prices
 * 4. Create trade + position state
 */

import { SentTradeModel } from './sent_trade.model.js';
import { SentPositionStateModel } from './sent_position_state.model.js';
import { getSentRiskGuardService } from './sent_risk_guard.service.js';
import { SentimentDirSampleModel } from '../dataset/sentiment-dir-sample.model.js';
import { 
  SentWindow, 
  SentMode,
  ENTRY_THRESHOLD,
  HORIZON_DAYS,
} from '../contracts/sentiment.risk.types.js';

export interface BuildResult {
  processed: number;
  created: number;
  skipped: number;
  reasons: Record<string, number>;
}

export class SentTradeBuilderService {
  private guard = getSentRiskGuardService();

  /**
   * Build trades for a specific window/mode
   */
  async buildForWindow(window: SentWindow, mode: SentMode): Promise<BuildResult> {
    // Get finalized samples with prices
    const samples = await SentimentDirSampleModel.find({
      window,
      labelVersion: 1,
      priceAtAsOf: { $exists: true, $ne: null },
      priceAtHorizonClose: { $exists: true, $ne: null },
    }).lean();

    let processed = 0;
    let created = 0;
    let skipped = 0;
    const reasons: Record<string, number> = {};

    for (const s of samples) {
      processed++;

      // Check entry threshold
      if (Math.abs(s.bias) < ENTRY_THRESHOLD[window]) {
        skipped++;
        reasons['BELOW_THRESHOLD'] = (reasons['BELOW_THRESHOLD'] || 0) + 1;
        continue;
      }

      // Check if trade already exists
      const exists = await SentTradeModel.exists({
        symbol: s.symbol,
        window,
        asOf: s.asOf,
        mode,
      });

      if (exists) {
        skipped++;
        reasons['DUPLICATE'] = (reasons['DUPLICATE'] || 0) + 1;
        continue;
      }

      // Calculate exit date
      const exitDate = this.getExitDate(new Date(s.asOf), window);

      // Check guards (for backfill, we skip guards since these are historical)
      // In live mode, guards would be checked before opening
      // For backfill, we create all valid trades

      const entryPrice = s.priceAtAsOf;
      const exitPrice = s.priceAtHorizonClose;

      if (!entryPrice || !exitPrice || entryPrice <= 0 || exitPrice <= 0) {
        skipped++;
        reasons['NO_PRICE'] = (reasons['NO_PRICE'] || 0) + 1;
        continue;
      }

      const direction = s.bias > 0 ? 'LONG' : 'SHORT';

      const pnlPct = direction === 'LONG'
        ? (exitPrice - entryPrice) / entryPrice
        : (entryPrice - exitPrice) / entryPrice;

      try {
        await SentTradeModel.create({
          symbol: s.symbol,
          window,
          mode,
          direction,
          asOf: s.asOf,
          entryPrice,
          exitPrice,
          pnlPct,
          openedAt: s.asOf,
          closedAt: exitDate,
          bias: s.bias,
          confidence: s.confidence || 0,
        });

        created++;
      } catch (err: any) {
        if (err.code === 11000) {
          // Duplicate key error - already exists
          skipped++;
          reasons['DUPLICATE'] = (reasons['DUPLICATE'] || 0) + 1;
        } else {
          throw err;
        }
      }
    }

    return { processed, created, skipped, reasons };
  }

  /**
   * Build trades for all windows/modes
   */
  async buildAll(): Promise<Record<string, BuildResult>> {
    const results: Record<string, BuildResult> = {};

    for (const window of ['24H', '7D', '30D'] as SentWindow[]) {
      for (const mode of ['RULE', 'ML'] as SentMode[]) {
        const key = `${window}_${mode}`;
        results[key] = await this.buildForWindow(window, mode);
      }
    }

    return results;
  }

  /**
   * Get exit date based on window
   */
  private getExitDate(asOf: Date, window: SentWindow): Date {
    const d = new Date(asOf);
    d.setDate(d.getDate() + HORIZON_DAYS[window]);
    return d;
  }
}

// Singleton
let builderInstance: SentTradeBuilderService | null = null;

export function getSentTradeBuilderService(): SentTradeBuilderService {
  if (!builderInstance) {
    builderInstance = new SentTradeBuilderService();
  }
  return builderInstance;
}

console.log('[Sentiment-ML] Trade Builder Service loaded (BLOCK 6B)');
