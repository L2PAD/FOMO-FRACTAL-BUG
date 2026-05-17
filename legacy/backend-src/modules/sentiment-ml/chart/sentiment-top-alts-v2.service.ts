/**
 * Sentiment Top Alts V2 Service
 * ==============================
 * 
 * BLOCK P1.2: Top altcoins with reliability-adjusted values
 * Shows RAW vs FINAL expected moves and confidence
 */

import {
  SentimentTopAltsResponse,
  SentimentTopAltRow,
  Horizon,
} from './sentiment-chart-v2.types.js';
import {
  getAdjustmentContext,
  applyAdjustments,
  biasToDirection,
  calculateExpectedMove,
} from './sentiment-ui-adjustments.js';
import { SentimentAggregateModel } from '../storage/sentiment-aggregate.model.js';
import { SENTIMENT_TOP20 } from '../config/top20-symbols.js';

function horizonToWindow(horizon: Horizon): '24H' | '7D' | '30D' {
  return horizon;
}

export class SentimentTopAltsV2Service {
  /**
   * Get top alts with reliability adjustments
   */
  async getTopAlts(
    horizon: Horizon,
    limit: number = 20
  ): Promise<SentimentTopAltsResponse> {
    const window = horizonToWindow(horizon);
    const context = await getAdjustmentContext();

    // Fetch latest aggregates for all symbols
    const symbols = SENTIMENT_TOP20;
    const rows: SentimentTopAltRow[] = [];

    for (const symbol of symbols) {
      try {
        const agg = await SentimentAggregateModel.findOne({
          symbol: symbol.toUpperCase(),
          window,
        })
          .sort({ asOf: -1 })
          .lean();

        if (!agg) continue;

        // Raw values
        const score = agg.score ?? 0.5;
        const bias = agg.bias ?? 0;
        const rawConfidence = agg.confidence ?? agg.weightedConfidence ?? 0.5;
        const rawExpectedMovePct = calculateExpectedMove(bias, rawConfidence);

        // Entry price (estimate or use stored)
        const entry = 1; // Normalized for percentage calculation

        // Apply adjustments
        const adjusted = applyAdjustments(rawConfidence, rawExpectedMovePct, entry, context);

        // In SafeMode, neutralize direction
        const direction = context.safeMode ? 'NEUTRAL' : biasToDirection(bias);

        // Build flags
        const flags: string[] = [...adjusted.notes];

        // Add low data flag if applicable
        const eventsCount = (agg as any).eventsCount ?? 0;
        if (eventsCount < 10) {
          flags.push('LOW_DATA');
        }

        // P2.3: Build explain block per row
        const explain = {
          bias,
          rawConfidence,
          uriMultiplier: context.uriMultiplier,
          calibrationMultiplier: context.calibrationMultiplier,
          finalConfidence: adjusted.finalConfidence,
          flags: {
            safeMode: context.safeMode,
            uriAdjustment: context.uriMultiplier !== 1,
            lowData: eventsCount < 10,
          },
        };

        rows.push({
          symbol,
          score,
          bias,
          direction,
          expectedMovePctRaw: rawExpectedMovePct * 100, // Convert to percentage
          expectedMovePctFinal: (rawExpectedMovePct * context.capitalMultiplier) * 100,
          confidenceRaw: rawConfidence,
          confidenceFinal: adjusted.finalConfidence,
          flags,
          explain,
        });
      } catch (err) {
        console.warn(`[TopAltsV2] Error processing ${symbol}:`, err);
      }
    }

    // Sort by adjusted expected move (absolute value)
    rows.sort((a, b) => Math.abs(b.expectedMovePctFinal) - Math.abs(a.expectedMovePctFinal));

    // Limit results
    const limited = rows.slice(0, limit);

    // Count active (non-neutral, non-safemode)
    const activeCount = context.safeMode
      ? 0
      : limited.filter(r => r.direction !== 'NEUTRAL').length;

    return {
      ok: true,
      horizon,
      safeMode: context.safeMode,
      uriLevel: context.uriLevel,
      rows: limited,
      activeCount,
    };
  }
}

// Singleton
let instance: SentimentTopAltsV2Service | null = null;

export function getSentimentTopAltsV2Service(): SentimentTopAltsV2Service {
  if (!instance) {
    instance = new SentimentTopAltsV2Service();
  }
  return instance;
}
