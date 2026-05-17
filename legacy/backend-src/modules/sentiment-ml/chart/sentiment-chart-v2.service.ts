/**
 * Sentiment Chart V2 Service
 * ==========================
 * 
 * BLOCK P1.1: Production-grade chart engine for Sentiment UI
 * Symmetric with Exchange v4 architecture
 * 
 * Pipeline:
 * Raw Aggregates → Reliability Layer → Calibration → SafeMode → Chart DTO
 */

import {
  SentimentChartQuery,
  SentimentChartResponse,
  ChartCandle,
  ProjectionPoint,
  BandPoint,
  ChartMarker,
  Horizon,
} from './sentiment-chart-v2.types.js';
import {
  getAdjustmentContext,
  applyAdjustments,
  biasToDirection,
  calculateExpectedMove,
} from './sentiment-ui-adjustments.js';
import { sentimentAggregationService } from '../services/sentiment-aggregation.service.js';
import { SentimentAggregateModel } from '../storage/sentiment-aggregate.model.js';
import mongoose from 'mongoose';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

function horizonToWindow(horizon: Horizon): '24H' | '7D' | '30D' {
  return horizon;
}

function horizonToDays(horizon: Horizon): number {
  if (horizon === '24H') return 1;
  if (horizon === '7D') return 7;
  return 30;
}

export class SentimentChartV2Service {
  /**
   * Get full chart data with reliability adjustments
   */
  async getChart(query: SentimentChartQuery): Promise<SentimentChartResponse> {
    const { symbol, horizon } = query;
    const window = horizonToWindow(horizon);

    // 1. Get raw aggregate
    const aggregate = await this.getLatestAggregate(symbol, window);

    if (!aggregate) {
      throw new Error(`No aggregate found for ${symbol}/${horizon}`);
    }

    // 2. Get adjustment context (URI, calibration, capital)
    const context = await getAdjustmentContext();

    // 3. Extract raw values
    const rawConfidence = aggregate.confidence ?? aggregate.weightedConfidence ?? 0.5;
    const bias = aggregate.bias ?? 0;
    const rawExpectedMovePct = calculateExpectedMove(bias, rawConfidence);

    // 4. Get current price as entry
    const candles = await this.getCandles(symbol);
    const entry = candles.length > 0 ? candles[candles.length - 1].close : 0;

    // 5. Apply adjustments
    const adjusted = applyAdjustments(rawConfidence, rawExpectedMovePct, entry, context);
    const direction = context.safeMode ? 'NEUTRAL' : biasToDirection(bias);

    // 6. Calculate target and band
    const rawTarget = entry * (1 + rawExpectedMovePct);
    const finalTarget = adjusted.finalTarget;

    // Band width scales inversely with confidence
    const bandWidth = Math.abs(rawExpectedMovePct) * (1 - adjusted.finalConfidence) * 2;
    const bandLow = finalTarget * (1 - bandWidth);
    const bandHigh = finalTarget * (1 + bandWidth);

    // 7. Build projection line
    const now = Math.floor(Date.now() / 1000);
    const expiryTime = now + horizonToDays(horizon) * 24 * 60 * 60;

    const projectionLine: ProjectionPoint[] = [
      { time: now, value: entry },
      { time: expiryTime, value: finalTarget },
    ];

    // 8. Build band area (for the forecast period)
    const bandArea: BandPoint[] = [
      { time: now, low: entry, high: entry },
      { time: expiryTime, low: bandLow, high: bandHigh },
    ];

    // 9. Build markers
    const markers: ChartMarker[] = [];

    if (context.safeMode) {
      markers.push({
        type: 'SAFE_MODE',
        time: now,
        text: 'SAFE MODE',
      });
    }

    if (context.calibrationMultiplier !== 1) {
      markers.push({
        type: 'CALIBRATION',
        time: now,
        text: `CALIBRATED (×${context.calibrationMultiplier.toFixed(2)})`,
      });
    }

    if (context.uriMultiplier !== 1) {
      markers.push({
        type: 'URI_ADJUSTMENT',
        time: now,
        text: `URI ${context.uriLevel} (×${context.uriMultiplier.toFixed(2)})`,
      });
    }

    // 10. Build explain block for P2
    const score = (aggregate as any).score ?? 0.5;
    const eventsCount = (aggregate as any).eventsCount ?? 0;

    const explain = {
      core: {
        bias,
        score,
        rawConfidence,
        eventsCount,
        quality: eventsCount < 10 ? 'LOW_VOLUME' as const : 'OK' as const,
      },
      adjustments: {
        uriMultiplier: context.uriMultiplier,
        calibrationMultiplier: context.calibrationMultiplier,
        sizeMultiplier: context.capitalMultiplier,
        finalConfidence: adjusted.finalConfidence,
      },
      safety: {
        safeMode: context.safeMode,
        safeModeReason: context.safeMode ? `URI level: ${context.uriLevel}` : undefined,
        uriLevel: context.uriLevel,
        calibrationStatus: context.calibrationMultiplier === 1 ? 'OK' : 'ADJUSTED',
      },
    };

    return {
      ok: true,
      meta: {
        symbol,
        horizon,
        generatedAt: new Date().toISOString(),
        safeMode: context.safeMode,
        uriLevel: context.uriLevel,
        moduleVersion: 'v1.0.0',
      },
      reliability: {
        rawConfidence,
        uriMultiplier: context.uriMultiplier,
        calibrationMultiplier: context.calibrationMultiplier,
        capitalMultiplier: context.capitalMultiplier,
        finalConfidence: adjusted.finalConfidence,
      },
      forecast: {
        entry,
        target: finalTarget,
        bandLow,
        bandHigh,
        expectedMovePct: rawExpectedMovePct,
        direction,
      },
      chart: {
        candles,
        projectionLine,
        bandArea,
        markers,
      },
      explain,
    };
  }

  /**
   * Get latest aggregate from database
   */
  private async getLatestAggregate(symbol: string, window: '24H' | '7D' | '30D') {
    try {
      const doc = await SentimentAggregateModel.findOne({
        symbol: symbol.toUpperCase(),
        window,
      }).sort({ asOf: -1 }).lean();

      return doc;
    } catch (err) {
      console.error(`[SentimentChartV2] Error fetching aggregate:`, err);
      return null;
    }
  }

  private static readonly KRAKEN_PAIR: Record<string, string> = {
    BTC: 'XBTUSD', ETH: 'XETHUSD', SOL: 'SOLUSD',
  };

  /**
   * Get OHLC candles — Kraken first, Binance fallback, then mock
   */
  private async getCandles(symbol: string): Promise<ChartCandle[]> {
    // Try Kraken first (works from this region)
    try {
      const pair = SentimentChartV2Service.KRAKEN_PAIR[symbol.toUpperCase()] || `${symbol.toUpperCase()}USD`;
      const since = Math.floor((Date.now() - 168 * 3600 * 1000) / 1000);
      const response = await fetch(
        `https://api.kraken.com/0/public/OHLC?pair=${pair}&interval=60&since=${since}`
      );
      if (response.ok) {
        const json = await response.json();
        const result = json?.result || {};
        const key = Object.keys(result).find(k => k !== 'last');
        if (key && Array.isArray(result[key]) && result[key].length > 10) {
          return result[key].map((c: any) => ({
            time: Number(c[0]),
            open: parseFloat(c[1]),
            high: parseFloat(c[2]),
            low: parseFloat(c[3]),
            close: parseFloat(c[4]),
          }));
        }
      }
    } catch (err) {
      console.warn('[SentimentChartV2] Kraken error:', err);
    }

    // Try Binance as fallback
    try {
      const response = await fetch(
        `${process.env.BINANCE_API_URL || 'https://api.binance.com'}/api/v3/klines?symbol=${symbol.toUpperCase()}USDT&interval=1h&limit=168`
      );
      if (response.ok) {
        const data = await response.json();
        if (Array.isArray(data) && data.length > 0) {
          return data.map((k: any) => ({
            time: Math.floor(k[0] / 1000),
            open: parseFloat(k[1]),
            high: parseFloat(k[2]),
            low: parseFloat(k[3]),
            close: parseFloat(k[4]),
          }));
        }
      }
    } catch {}

    // MongoDB fallback
    try {
      const db = mongoose.connection.db;
      if (db) {
        const docs = await db.collection('fractal_canonical_ohlcv')
          .find({ 'meta.symbol': symbol.toUpperCase() })
          .sort({ ts: -1 })
          .limit(168)
          .toArray();
        if (docs.length > 0) {
          return docs.reverse().map(d => ({
            time: Math.floor(new Date(d.ts).getTime() / 1000),
            open: d.ohlcv?.o ?? d.ohlcv?.c ?? 0,
            high: d.ohlcv?.h ?? d.ohlcv?.c ?? 0,
            low: d.ohlcv?.l ?? d.ohlcv?.c ?? 0,
            close: d.ohlcv?.c ?? 0,
          }));
        }
      }
    } catch {}

    console.warn('[SentimentChartV2] All price sources failed, using mock');
    return this.generateMockCandles();
  }

  /**
   * Generate mock candles (last resort fallback)
   */
  private generateMockCandles(): ChartCandle[] {
    const candles: ChartCandle[] = [];
    const now = Math.floor(Date.now() / 1000);
    let price = 65000;

    for (let i = 168; i >= 0; i--) {
      const time = now - i * 3600;
      const change = (Math.random() - 0.5) * 200;
      const open = price;
      const close = price + change;
      const high = Math.max(open, close) + Math.random() * 100;
      const low = Math.min(open, close) - Math.random() * 100;
      candles.push({ time, open, high, low, close });
      price = close;
    }
    return candles;
  }
}

// Singleton
let instance: SentimentChartV2Service | null = null;

export function getSentimentChartV2Service(): SentimentChartV2Service {
  if (!instance) {
    instance = new SentimentChartV2Service();
  }
  return instance;
}
