/**
 * Exchange Top Alts V2 Service
 * ==============================
 * 
 * BLOCK E5: Top altcoins with reliability-adjusted values
 * Symmetric with Sentiment Top Alts V2
 */

import {
  ExchangeTopAltsResponse,
  ExchangeTopAltRow,
  Horizon,
} from './exchange-chart-v2.types.js';
import { 
  getExchangeAdjustmentContext, 
  applyExchangeAdjustments,
  signalToDirection,
  calculateExchangeExpectedMove,
} from './exchange-ui-adjustments.js';

// Common altcoins
const ALT_SYMBOLS = [
  'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'AVAX', 'DOGE', 'DOT', 
  'LINK', 'MATIC', 'UNI', 'ATOM', 'LTC', 'FIL', 'APT',
  'ARB', 'OP', 'INJ', 'TIA', 'SUI'
];

export class ExchangeTopAltsV2Service {
  /**
   * Get top altcoins with reliability-adjusted values
   */
  async getTopAlts(
    horizon: Horizon,
    limit: number = 20
  ): Promise<ExchangeTopAltsResponse> {
    const context = await getExchangeAdjustmentContext();

    // Generate alt signals (in production, this would use actual ML predictions)
    const rows: ExchangeTopAltRow[] = [];

    for (const symbol of ALT_SYMBOLS.slice(0, limit)) {
      const signal = await this.generateAltSignal(symbol, horizon, context);
      rows.push(signal);
    }

    // Sort by final confidence (descending)
    rows.sort((a, b) => b.confidenceFinal - a.confidenceFinal);

    const activeCount = rows.filter(r => r.confidenceFinal > 0.3 && r.direction !== 'NEUTRAL').length;

    return {
      ok: true,
      horizon,
      safeMode: context.safeMode,
      uriLevel: context.uriLevel,
      rows,
      activeCount,
    };
  }

  /**
   * Generate signal for single alt
   */
  private async generateAltSignal(
    symbol: string,
    horizon: Horizon,
    context: any
  ): Promise<ExchangeTopAltRow> {
    // Generate mock signal (in production, use actual ML)
    const signalScore = (Math.random() - 0.5) * 2; // -1 to 1
    const rawConfidence = 0.3 + Math.random() * 0.5;
    const rawExpectedMovePct = calculateExchangeExpectedMove(signalScore, rawConfidence);

    // Mock entry price
    const mockPrices: Record<string, number> = {
      ETH: 3200, SOL: 180, BNB: 600, XRP: 0.6, ADA: 0.45,
      AVAX: 35, DOGE: 0.12, DOT: 7, LINK: 18, MATIC: 0.8,
      UNI: 12, ATOM: 9, LTC: 85, FIL: 5, APT: 8,
      ARB: 1.2, OP: 2.5, INJ: 25, TIA: 8, SUI: 1.5,
    };
    const entry = mockPrices[symbol] || 100;

    // Apply adjustments
    const adjusted = applyExchangeAdjustments(rawConfidence, rawExpectedMovePct, entry, context);
    const direction = context.safeMode ? 'NEUTRAL' : signalToDirection(signalScore);

    // Final expected move scaled by confidence
    const finalExpectedMovePct = context.safeMode ? 0 : rawExpectedMovePct * (adjusted.finalConfidence / rawConfidence);

    return {
      symbol,
      score: signalScore,
      direction,
      expectedMovePctRaw: rawExpectedMovePct,
      expectedMovePctFinal: finalExpectedMovePct,
      confidenceRaw: rawConfidence,
      confidenceFinal: adjusted.finalConfidence,
      flags: adjusted.notes,
      explain: {
        signalScore,
        rawConfidence,
        uriMultiplier: context.uriMultiplier,
        calibrationMultiplier: context.calibrationMultiplier,
        capitalMultiplier: context.capitalMultiplier,
        finalConfidence: adjusted.finalConfidence,
        flags: {
          safeMode: context.safeMode,
          uriAdjustment: context.uriMultiplier !== 1,
          capitalGate: context.capitalMultiplier !== 1,
        },
      },
    };
  }
}

// Singleton
let instance: ExchangeTopAltsV2Service | null = null;

export function getExchangeTopAltsV2Service(): ExchangeTopAltsV2Service {
  if (!instance) {
    instance = new ExchangeTopAltsV2Service();
  }
  return instance;
}
