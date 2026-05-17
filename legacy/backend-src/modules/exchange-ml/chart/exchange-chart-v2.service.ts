/**
 * Exchange Chart V2 Service
 * ==========================
 * 
 * BLOCK E1: Production-grade chart engine for Exchange UI
 * 
 * Pipeline:
 * 1. Binance candles (real OHLC)
 * 2. Forecast from exchange_forecasts (real model) with fallback
 * 3. Reliability adjustments (URI / Calibration / Capital)
 * 4. Future candles + projection artifacts
 * 5. Chart DTO
 */

import {
  ExchangeChartV2Query,
  ExchangeChartV2Response,
  ChartCandle,
  ProjectionPoint,
  BandPoint,
  ChartMarker,
  Horizon,
} from './exchange-chart-v2.types.js';
import {
  getExchangeAdjustmentContext,
  applyExchangeAdjustments,
  signalToDirection,
  calculateExchangeExpectedMove,
} from './exchange-ui-adjustments.js';

function horizonToDays(horizon: Horizon): number {
  if (horizon === '24H') return 1;
  if (horizon === '7D') return 7;
  return 30;
}

function horizonToSeconds(horizon: Horizon): number {
  return horizonToDays(horizon) * 24 * 60 * 60;
}

interface StoredForecast {
  direction: string;
  confidence: number;
  expectedMovePct: number;
  entryPrice: number;
  targetPrice: number;
  horizonDays: number;
  madeAtTs: number;
  regime?: string;
  forecastSource: 'db' | 'fallback';
  uncertainty?: {
    value: number;
    level: 'low' | 'mid' | 'high';
    dominantRegime: string;
    regimeEntropy: number;
    flags: string[];
  };
  executionStatus?: {
    mode: 'normal' | 'reduced' | 'minimal';
    sizeFactor: number;
    confidenceAdjusted: number;
    reason: string;
    uncertaintyLevel: 'low' | 'mid' | 'high';
  };
  scenarios?: {
    scenarios: Array<{
      type: 'bullish' | 'base' | 'bearish';
      probability: number;
      range: [number, number];
      expected_move: number;
      narrative: string;
    }>;
    dominant: 'bullish' | 'base' | 'bearish';
    spread: number;
    confidence_tag: string;
  };
}

export class ExchangeChartV2Service {
  /**
   * Get full chart data with real forecast
   */
  async getChart(query: ExchangeChartV2Query): Promise<ExchangeChartV2Response> {
    const { symbol, horizon } = query;
    const hDays = horizonToDays(horizon);
    const now = Math.floor(Date.now() / 1000);

    // 1. Real Binance candles
    const candles = await this.getCandles(symbol);
    const entry = candles.length > 0 ? candles[candles.length - 1].close : 0;

    // 2. Get forecast from store (exchange_forecasts) or fallback
    const forecast = await this.getForecastFromStore(symbol, hDays, entry);

    // 3. Adjustment context (URI, calibration, capital)
    const context = await getExchangeAdjustmentContext();

    // 4. Apply reliability adjustments
    const rawConfidence = forecast.confidence;
    const rawExpectedMovePct = forecast.expectedMovePct / 100; // stored as % e.g. 4.8 → 0.048
    const adjusted = applyExchangeAdjustments(rawConfidence, rawExpectedMovePct, entry, context);
    const direction = context.safeMode ? 'NEUTRAL' : (forecast.direction as any);

    // 5. Target and band from real forecast
    const rawTarget = forecast.targetPrice;
    const finalTarget = adjusted.finalTarget;
    const bandWidth = Math.abs(rawExpectedMovePct) * (1 - adjusted.finalConfidence) * 1.5;
    const bandLow = finalTarget * (1 - Math.max(bandWidth, 0.01));
    const bandHigh = finalTarget * (1 + Math.max(bandWidth, 0.01));

    // 6. Build projection line
    const expiryTime = now + horizonToSeconds(horizon);
    const projectionLine: ProjectionPoint[] = [
      { time: now, value: entry },
      { time: expiryTime, value: finalTarget },
    ];

    // 7. Band area
    const bandArea: BandPoint[] = [
      { time: now, low: entry, high: entry },
      { time: expiryTime, low: bandLow, high: bandHigh },
    ];

    // 8. Generate daily forecast candles from real model data + historical vol
    const futureCandles = this.buildFutureCandles(entry, finalTarget, hDays, adjusted.finalConfidence, now, candles);

    // 9. Markers
    const markers: ChartMarker[] = [];
    if (context.safeMode) {
      markers.push({ type: 'SAFE_MODE', time: now, text: 'SAFE MODE' });
    }
    if (context.uriMultiplier !== 1) {
      markers.push({ type: 'URI_ADJUSTMENT', time: now, text: `URI ${context.uriLevel}` });
    }

    // 10. Explain
    const regime = forecast.regime || 'UNKNOWN';
    const explain = {
      core: {
        signalScore: rawExpectedMovePct * 10,
        regime,
        rawConfidence,
        notes: [`Source: ${forecast.forecastSource}`, `Regime: ${regime}`],
      },
      adjustments: {
        uriMultiplier: context.uriMultiplier,
        calibrationMultiplier: context.calibrationMultiplier,
        capitalMultiplier: context.capitalMultiplier,
        finalConfidence: adjusted.finalConfidence,
      },
      safety: {
        safeMode: context.safeMode,
        safeModeReason: context.safeModeReason,
        uriLevel: context.uriLevel,
        trainingBlocked: context.trainingBlocked,
        promotionBlocked: context.promotionBlocked,
      },
    };

    // 11. Module manifest
    const manifest = await this.getModuleManifest();
    const evaluateAt = new Date(Date.now() + horizonToSeconds(horizon) * 1000).toISOString();

    return {
      ok: true,
      meta: {
        symbol,
        horizon,
        generatedAt: new Date().toISOString(),
        safeMode: context.safeMode,
        uriLevel: context.uriLevel,
        moduleVersion: manifest.version,
        frozen: manifest.frozen,
        source: forecast.forecastSource,
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
        targetRaw: rawTarget,
        targetFinal: finalTarget,
        bandLow,
        bandHigh,
        expectedMovePct: rawExpectedMovePct,
        direction: direction as 'LONG' | 'SHORT' | 'NEUTRAL',
        evaluateAt,
      },
      chart: {
        candles: [...candles, ...futureCandles],
        projectionLine,
        bandArea,
        markers,
      },
      explain,
      uncertainty: forecast.uncertainty || null,
      executionStatus: forecast.executionStatus || null,
      scenarios: forecast.scenarios || null,
    } as any;
  }

  /**
   * Read latest forecast from exchange_forecasts (real model output)
   * Falls back to momentum formula if DB empty
   */
  private async getForecastFromStore(symbol: string, horizonDays: number, currentPrice: number): Promise<StoredForecast> {
    try {
      const { getDb } = await import('../../../db/mongodb.js');
      const db = getDb();
      const col = db.collection('exchange_forecasts');

      // Get latest forecast for this horizon
      const doc = await col.findOne(
        { asset: symbol.toUpperCase(), horizonDays },
        { sort: { madeAtTs: -1 }, projection: { _id: 0 } }
      );

      if (doc && doc.entryPrice && doc.expectedMovePct !== undefined) {
        const dir = doc.direction || 'NEUTRAL';
        // Normalize direction: UP→LONG, DOWN→SHORT
        const normalizedDir = dir === 'UP' ? 'LONG' : dir === 'DOWN' ? 'SHORT' : dir;

        // Extract uncertainty from audit (v4.3.1 regime calibration)
        const audit = doc.audit || {};
        const regimeAdj = audit.regimeAdjustments || {};
        const regimeV2 = audit.regimeV2 || {};
        const du = regimeAdj.decision_uncertainty ?? null;
        let uncertainty: StoredForecast['uncertainty'] = undefined;
        if (du !== null) {
          const level: 'low' | 'mid' | 'high' = du < 0.45 ? 'low' : du > 0.65 ? 'high' : 'mid';
          uncertainty = {
            value: du,
            level,
            dominantRegime: regimeV2.dominant_regime || 'unknown',
            regimeEntropy: regimeV2.regime_entropy ?? 0.5,
            flags: regimeAdj.flags || [],
          };
        }

        // Compute execution_status from uncertainty (P1: soft modulation)
        let executionStatus: StoredForecast['executionStatus'] = undefined;
        if (uncertainty) {
          const du = uncertainty.value;
          let mode: 'normal' | 'reduced' | 'minimal';
          let sizeFactor: number;
          let reason: string;

          if (du < 0.3) {
            mode = 'normal';
            sizeFactor = 1.0;
            reason = `Confident environment (${uncertainty.dominantRegime} regime)`;
          } else if (du < 0.6) {
            mode = 'reduced';
            sizeFactor = 0.75;
            reason = `Reduced conviction due to ${uncertainty.dominantRegime} regime and elevated uncertainty`;
          } else {
            mode = 'minimal';
            sizeFactor = 0.5;
            reason = `${uncertainty.dominantRegime.charAt(0).toUpperCase() + uncertainty.dominantRegime.slice(1)} regime: historically low forecast reliability`;
          }

          // FIX 3.9: Catastrophic guard for 30D high uncertainty
          // Extra size reduction when scenarios spread is very wide
          if (doc.horizonDays === 30 && du >= 0.6 && doc.scenarios?.spread > 25) {
            sizeFactor = Math.round(sizeFactor * 0.7 * 100) / 100; // 0.5 → 0.35
            reason += ' (catastrophic guard active)';
          }

          // FIX 4.7: Phase Risk Flagging — unstable_transition penalty
          // Monitoring showed 8% accuracy in this phase → reduce exposure
          const adjFlags: string[] = regimeAdj.flags || [];
          if (adjFlags.includes('transition_caution') || adjFlags.includes('transition_hard_dampen')) {
            sizeFactor = Math.round(sizeFactor * 0.7 * 100) / 100;
            reason += ' (phase risk: unstable_transition)';
          }

          // BLOCK 5.A.6: Proto Overlay (rule-based risk filter)
          // Closes risk gap while ML data accumulates
          let protoRisk = 0;
          const protoFlags: string[] = [];

          // Already counted transition in FIX 4.7, track for logging
          if (adjFlags.includes('transition_caution') || adjFlags.includes('transition_hard_dampen')) {
            protoRisk += 0.4;
            protoFlags.push('unstable_transition');
          }
          const entropy = regimeV2.regime_entropy ?? 0.5;
          if (entropy > 0.7) {
            protoRisk += 0.3;
            protoFlags.push('high_entropy');
          }
          const scenarioSpread = doc.scenarios?.spread ?? 0;
          if (scenarioSpread > 20) {
            protoRisk += 0.2;
            protoFlags.push('wide_scenario_spread');
          }
          if (du > 0.7) {
            protoRisk += 0.15;
            protoFlags.push('high_uncertainty');
          }
          protoRisk = Math.min(protoRisk, 1.0);

          // Apply proto overlay size penalty (only the excess beyond FIX 4.7)
          if (protoRisk > 0.6 && !protoFlags.includes('unstable_transition')) {
            // Strong penalty from OTHER factors (entropy + spread + uncertainty)
            sizeFactor = Math.round(sizeFactor * 0.85 * 100) / 100;
            reason += ` (proto overlay: ${protoFlags.join(', ')})`;
          } else if (protoRisk > 0.3 && !adjFlags.includes('transition_caution')) {
            sizeFactor = Math.round(sizeFactor * 0.9 * 100) / 100;
            reason += ` (proto overlay mild: ${protoFlags.join(', ')})`;
          }

          // FIX 6.1: NEUTRAL Regime Correction
          // Drift analysis: NEUTRAL regime = 8.3% accuracy, 33.3% catastrophic
          // Two-level protection: base reduction + entropy amplifier
          const dominantRegime = (regimeV2.dominant_regime || '').toLowerCase();
          if (dominantRegime === 'neutral' || dominantRegime === 'range') {
            sizeFactor = Math.round(sizeFactor * 0.6 * 100) / 100;
            reason += ' (FIX 6.1: neutral regime risk reduction)';

            if (entropy > 0.7) {
              sizeFactor = Math.round(sizeFactor * 0.7 * 100) / 100;
              reason += ' (high entropy in neutral)';
            }
          }

          // FIX 6.2: Drift Execution Hook
          // Fetch cached drift score and apply auto-response
          try {
            const axios = require('axios');
            const driftRes = await axios.get('http://localhost:8001/api/drift/intelligence', {
              params: { horizon: doc.horizonDays, asset: doc.asset || 'BTC' },
              timeout: 3000,
            });
            const driftData = driftRes.data;
            if (driftData?.ok) {
              const dScore = driftData.drift_score ?? 0;
              const catRate = driftData.metrics?.global?.catastrophic_rate ?? 0;

              if (dScore > 0.7) {
                sizeFactor = Math.round(sizeFactor * 0.6 * 100) / 100;
                reason += ` (FIX 6.2: drift defensive, score=${dScore})`;
              } else if (dScore > 0.5) {
                sizeFactor = Math.round(sizeFactor * 0.8 * 100) / 100;
                reason += ` (FIX 6.2: drift cautious, score=${dScore})`;
              }
              if (catRate > 0.25) {
                sizeFactor = Math.round(sizeFactor * 0.7 * 100) / 100;
                reason += ` (high catastrophic rate=${catRate})`;
              }
            }
          } catch (_driftErr) {
            // Drift unavailable — continue without it (no hard dependency)
          }

          // FLOOR: Prevent multiplier stacking from killing execution
          // After ALL modifiers: neutral, entropy, drift, catastrophic, proto
          sizeFactor = Math.max(sizeFactor, 0.3);

          executionStatus = {
            mode,
            sizeFactor,
            confidenceAdjusted: Math.round((doc.confidence ?? 0.5) * sizeFactor * 100) / 100,
            reason,
            uncertaintyLevel: uncertainty.level,
          };
        }

        return {
          direction: normalizedDir,
          confidence: doc.confidence ?? 0.5,
          expectedMovePct: doc.expectedMovePct ?? 0,
          entryPrice: doc.entryPrice,
          targetPrice: doc.targetPrice ?? doc.entryPrice * (1 + (doc.expectedMovePct ?? 0) / 100),
          horizonDays: doc.horizonDays,
          madeAtTs: doc.madeAtTs ?? Date.now(),
          regime: doc.regime || doc.regimeAtCreation || 'UNKNOWN',
          forecastSource: 'db',
          uncertainty,
          executionStatus,
          scenarios: doc.scenarios || undefined,
        };
      }
    } catch (err: any) {
      console.warn('[ExchangeChartV2] DB read error, falling back:', err.message);
    }

    // Fallback: momentum-based (legacy)
    return this.getMomentumFallback(symbol, currentPrice, horizonDays);
  }

  /**
   * Legacy momentum fallback (only used when DB is empty)
   */
  private async getMomentumFallback(symbol: string, currentPrice: number, horizonDays: number): Promise<StoredForecast> {
    const candles = await this.getCandles(symbol);
    if (candles.length < 10) {
      return {
        direction: 'NEUTRAL', confidence: 0.5, expectedMovePct: 0,
        entryPrice: currentPrice, targetPrice: currentPrice,
        horizonDays, madeAtTs: Date.now(), regime: 'UNKNOWN', forecastSource: 'fallback',
      };
    }
    const recent = candles.slice(-24);
    const oldP = recent[0].close, newP = recent[recent.length - 1].close;
    const momentum = (newP - oldP) / oldP;
    const signalScore = Math.max(-1, Math.min(1, momentum * 10));
    const changes = recent.map((c, i) => i > 0 ? (c.close - recent[i - 1].close) / recent[i - 1].close : 0);
    const avg = changes.reduce((a, b) => a + b, 0) / changes.length;
    const variance = changes.reduce((a, b) => a + Math.pow(b - avg, 2), 0) / changes.length;
    const confidence = Math.max(0.3, Math.min(0.9, 0.7 - variance * 100));
    const movePct = signalScore * confidence * 3; // legacy 3% base
    const volatility = Math.sqrt(variance) * 100;

    return {
      direction: signalScore > 0.1 ? 'LONG' : signalScore < -0.1 ? 'SHORT' : 'NEUTRAL',
      confidence,
      expectedMovePct: movePct,
      entryPrice: currentPrice,
      targetPrice: currentPrice * (1 + movePct / 100),
      horizonDays,
      madeAtTs: Date.now(),
      regime: volatility > 3 ? 'VOLATILE' : volatility < 1 ? 'RANGING' : 'TRENDING',
      forecastSource: 'fallback',
    };
  }

  /**
   * Generate daily forecast candles from real model prediction.
   * 
   * - 7D → 7 candles, 30D → 30 candles (daily, not hourly)
   * - Volatility estimated from recent real candles
   * - Last candle close clamped to targetPrice
   * - Deterministic (seeded from entry + target + day)
   */
  private buildFutureCandles(
    entry: number, target: number, horizonDays: number,
    confidence: number, nowSec: number,
    realCandles: ChartCandle[]
  ): ChartCandle[] {
    if (horizonDays <= 1) return []; // 1D: no future candles

    const steps = horizonDays; // daily candles
    const totalMove = Math.log(target / entry);
    const drift = totalMove / steps; // daily log-return to reach target

    // Estimate daily volatility from last 7 days of real 1h candles
    const dailyVol = this.estimateDailyVol(realCandles);

    // Noise scaling: lower confidence → trajectory closer to straight line (less noise)
    // Higher confidence → allow more realistic volatility
    const noiseScale = 0.35 * Math.min(confidence + 0.3, 1.0);

    // Deterministic seed (consistent per day, won't jump on re-render)
    const dayKey = Math.floor(nowSec / 86400);
    const seed = Math.abs(dayKey * 31 + Math.round(entry) + horizonDays * 7) % 10000;

    // Align to next midnight UTC
    const startTime = (Math.floor(nowSec / 86400) + 1) * 86400;

    const candles: ChartCandle[] = [];
    let price = entry;

    for (let i = 0; i < steps; i++) {
      // Seeded deterministic noise (sin-based, stable across renders)
      const noise = Math.sin(seed + i * 13.7) * dailyVol * noiseScale;
      const ret = drift + noise;
      const nextPrice = price * Math.exp(ret);

      // Wick size from historical vol
      const wick = dailyVol * price * 0.5 * (0.5 + 0.5 * Math.abs(Math.sin(seed + i * 5.3)));

      const o = Math.round(price * 100) / 100;
      const c = Math.round(nextPrice * 100) / 100;
      const h = Math.round((Math.max(o, c) + wick) * 100) / 100;
      const l = Math.round((Math.min(o, c) - wick) * 100) / 100;

      candles.push({
        time: startTime + i * 86400,
        open: o,
        high: h,
        low: l,
        close: c,
      });
      price = nextPrice;
    }

    // Clamp last candle close to exact targetPrice
    if (candles.length > 0) {
      const last = candles[candles.length - 1];
      last.close = Math.round(target * 100) / 100;
      last.high = Math.max(last.high, last.close);
      last.low = Math.min(last.low, last.close);
    }

    return candles;
  }

  /**
   * Estimate daily volatility from hourly candles
   * Uses close-to-close returns over last ~7 days (168 candles)
   */
  private estimateDailyVol(candles: ChartCandle[]): number {
    if (candles.length < 48) return 0.02; // default 2% daily vol

    // Take last 168 hourly candles, compute hourly returns
    const recent = candles.slice(-168);
    const returns: number[] = [];
    for (let i = 1; i < recent.length; i++) {
      if (recent[i - 1].close > 0) {
        returns.push(Math.log(recent[i].close / recent[i - 1].close));
      }
    }
    if (returns.length < 10) return 0.02;

    const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
    const variance = returns.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / returns.length;
    const hourlyVol = Math.sqrt(variance);

    // Scale to daily: dailyVol = hourlyVol * sqrt(24)
    return hourlyVol * Math.sqrt(24);
  }

  /**
   * Get OHLC candles from Binance API
   */
  private async getCandles(symbol: string): Promise<ChartCandle[]> {
    try {
      const response = await fetch(
        `${process.env.BINANCE_API_URL || 'https://api.binance.com'}/api/v3/klines?symbol=${symbol.toUpperCase()}USDT&interval=1h&limit=168`
      );
      if (!response.ok) return this.generateMockCandles();
      const data = await response.json();
      return data.map((k: any) => ({
        time: Math.floor(k[0] / 1000),
        open: parseFloat(k[1]),
        high: parseFloat(k[2]),
        low: parseFloat(k[3]),
        close: parseFloat(k[4]),
      }));
    } catch (err) {
      console.warn('[ExchangeChartV2] Binance error, using mock:', err);
      return this.generateMockCandles();
    }
  }

  private generateMockCandles(): ChartCandle[] {
    const candles: ChartCandle[] = [];
    const now = Math.floor(Date.now() / 1000);
    let price = 68000;
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

  private async getModuleManifest(): Promise<{ version: string; frozen: boolean }> {
    try {
      const fs = await import('fs/promises');
      const path = await import('path');
      const manifestPath = path.join(process.cwd(), 'src/modules/exchange-ml/module_manifest.json');
      const content = await fs.readFile(manifestPath, 'utf-8');
      const manifest = JSON.parse(content);
      return { version: manifest.version || 'v1.0.0', frozen: manifest.frozen || false };
    } catch {
      return { version: 'v1.0.0', frozen: true };
    }
  }
}

let instance: ExchangeChartV2Service | null = null;
export function getExchangeChartV2Service(): ExchangeChartV2Service {
  if (!instance) instance = new ExchangeChartV2Service();
  return instance;
}
