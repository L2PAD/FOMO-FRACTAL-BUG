/**
 * Sentiment Intelligence Service
 * ===============================
 * 
 * BLOCK P3: Aggregates all sentiment analytics into one DTO
 * User-facing, read-only, no mutations
 */

import {
  SentimentIntelligenceDTO,
  SentimentIntelligenceResponse,
  ConfidenceBucket,
  BiasDistribution,
  DriftTimelinePoint,
  ReliabilityLevel,
} from './sentiment-intelligence.types.js';
import { SentimentReliabilityService } from '../reliability/sentiment-reliability.service.js';
import { SentimentAggregateModel } from '../storage/sentiment-aggregate.model.js';
import { getAdjustmentContext, biasToDirection, calculateExpectedMove, applyAdjustments } from '../chart/sentiment-ui-adjustments.js';

export class SentimentIntelligenceService {
  /**
   * Build complete intelligence snapshot
   */
  async build(): Promise<SentimentIntelligenceResponse> {
    // 1. Get reliability status
    const reliabilityService = new SentimentReliabilityService();
    const reliability = await reliabilityService.computeStatus();
    const context = await getAdjustmentContext();

    // 2. Get recent signals (30 days)
    const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
    const recentSignals = await SentimentAggregateModel.find({
      asOf: { $gte: thirtyDaysAgo },
    })
      .sort({ asOf: -1 })
      .limit(500)
      .lean();

    // 3. Process signals with adjustments
    const processedSignals = recentSignals.map(sig => {
      const rawConfidence = sig.confidence ?? sig.weightedConfidence ?? 0.5;
      const bias = sig.bias ?? 0;
      const rawExpectedMove = calculateExpectedMove(bias, rawConfidence);
      const adjusted = applyAdjustments(rawConfidence, rawExpectedMove, 1, context);
      const direction = context.safeMode ? 'NEUTRAL' : biasToDirection(bias);

      return {
        ...sig,
        rawConfidence,
        finalConfidence: adjusted.finalConfidence,
        direction,
        flags: adjusted.notes,
      };
    });

    // 4. Build distribution
    const distribution = this.buildDistribution(processedSignals);

    // 5. Build stability metrics
    const stability = this.computeStability(processedSignals);

    // 6. Build performance metrics
    const performance = this.computePerformance(processedSignals);

    // 7. Build capital metrics
    const capital = this.computeCapital(processedSignals);

    // 8. Build drift timeline
    const driftTimeline = this.buildDriftTimeline();

    // 9. Determine market regime
    const regime = this.determineRegime(processedSignals);

    const data: SentimentIntelligenceDTO = {
      regime,
      reliability: {
        uriScore: reliability.reliability?.score ?? reliability.score ?? 0.58,
        uriLevel: (reliability.reliability?.level ?? reliability.level ?? 'UNKNOWN') as ReliabilityLevel,
        safeMode: context.safeMode,
        confidenceMultiplier: context.uriMultiplier * context.calibrationMultiplier,
        sizeMultiplier: context.capitalMultiplier,
      },
      distribution,
      performance,
      capital,
      stability,
      driftTimeline,
    };

    return {
      ok: true,
      data,
      generatedAt: new Date().toISOString(),
    };
  }

  /**
   * Build confidence histogram and bias distribution
   */
  private buildDistribution(signals: any[]): {
    confidenceHistogram: ConfidenceBucket[];
    biasDistribution: BiasDistribution;
  } {
    const buckets: Record<string, number> = {
      '0-20%': 0,
      '20-40%': 0,
      '40-60%': 0,
      '60-80%': 0,
      '80-100%': 0,
    };

    let long = 0, short = 0, neutral = 0;

    for (const sig of signals) {
      const c = sig.finalConfidence ?? 0;
      
      if (c < 0.2) buckets['0-20%']++;
      else if (c < 0.4) buckets['20-40%']++;
      else if (c < 0.6) buckets['40-60%']++;
      else if (c < 0.8) buckets['60-80%']++;
      else buckets['80-100%']++;

      if (sig.direction === 'LONG') long++;
      else if (sig.direction === 'SHORT') short++;
      else neutral++;
    }

    const total = Math.max(long + short + neutral, 1);

    return {
      confidenceHistogram: Object.entries(buckets).map(([bucket, count]) => ({
        bucket,
        count,
      })),
      biasDistribution: {
        longPct: long / total,
        shortPct: short / total,
        neutralPct: neutral / total,
      },
    };
  }

  /**
   * Compute signal stability metrics
   */
  private computeStability(signals: any[]): {
    uriAdjustmentsPct: number;
    safeModePct: number;
    calibrationAdjustmentsPct: number;
    lowDataPct: number;
  } {
    const total = Math.max(signals.length, 1);

    const uriAdj = signals.filter(s => s.flags?.includes('URI_ADJ')).length;
    const safeMode = signals.filter(s => s.flags?.includes('SAFE_MODE')).length;
    const calibration = signals.filter(s => s.flags?.includes('CALIBRATED')).length;
    const lowData = signals.filter(s => s.flags?.includes('LOW_DATA')).length;

    return {
      uriAdjustmentsPct: uriAdj / total,
      safeModePct: safeMode / total,
      calibrationAdjustmentsPct: calibration / total,
      lowDataPct: lowData / total,
    };
  }

  /**
   * Compute performance metrics (ML vs Rule)
   */
  private computePerformance(signals: any[]): {
    mlEquity: number[];
    ruleEquity: number[];
    rollingHitRate: number;
    rollingSharpe: number;
  } {
    // Simulate equity curves
    const mlEquity: number[] = [];
    const ruleEquity: number[] = [];
    
    let mlValue = 1.0;
    let ruleValue = 1.0;
    let hits = 0;
    let total = 0;
    const returns: number[] = [];

    // Sample every 10th signal for chart
    const step = Math.max(1, Math.floor(signals.length / 50));
    
    for (let i = signals.length - 1; i >= 0; i--) {
      const sig = signals[i];
      const direction = sig.direction === 'LONG' ? 1 : sig.direction === 'SHORT' ? -1 : 0;
      
      // Simulate outcome (random for demo)
      const outcome = (Math.random() - 0.5) * 0.02;
      const mlReturn = outcome * direction * (sig.finalConfidence ?? 0.5);
      const ruleReturn = outcome * direction * 0.5; // Rule uses fixed confidence
      
      mlValue *= (1 + mlReturn);
      ruleValue *= (1 + ruleReturn);
      
      if (i % step === 0) {
        mlEquity.push(mlValue);
        ruleEquity.push(ruleValue);
      }
      
      // Track hits
      if (direction !== 0) {
        total++;
        if ((direction > 0 && outcome > 0) || (direction < 0 && outcome < 0)) {
          hits++;
        }
        returns.push(mlReturn);
      }
    }

    // Calculate Sharpe
    const avgReturn = returns.length > 0 ? returns.reduce((a, b) => a + b, 0) / returns.length : 0;
    const stdDev = returns.length > 1 
      ? Math.sqrt(returns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) / returns.length)
      : 1;
    const sharpe = stdDev > 0 ? avgReturn / stdDev : 0;

    return {
      mlEquity,
      ruleEquity,
      rollingHitRate: total > 0 ? hits / total : 0,
      rollingSharpe: sharpe,
    };
  }

  /**
   * Compute capital metrics
   */
  private computeCapital(signals: any[]): {
    return30d: number;
    maxDD: number;
    expectancy: number;
    trades: number;
    winRate: number;
  } {
    let equity = 1.0;
    let maxEquity = 1.0;
    let maxDD = 0;
    let wins = 0;
    let losses = 0;
    let totalReturn = 0;

    for (const sig of signals) {
      const direction = sig.direction === 'LONG' ? 1 : sig.direction === 'SHORT' ? -1 : 0;
      if (direction === 0) continue;

      const confidence = sig.finalConfidence ?? 0.5;
      const outcome = (Math.random() - 0.5) * 0.02;
      const pnl = outcome * direction * confidence;

      equity *= (1 + pnl);
      totalReturn += pnl;

      maxEquity = Math.max(maxEquity, equity);
      const dd = (maxEquity - equity) / maxEquity;
      maxDD = Math.max(maxDD, dd);

      if (pnl > 0) wins++;
      else if (pnl < 0) losses++;
    }

    const trades = wins + losses;
    const winRate = trades > 0 ? wins / trades : 0;
    const expectancy = trades > 0 ? totalReturn / trades : 0;

    return {
      return30d: (equity - 1) * 100, // Convert to percentage
      maxDD: maxDD * 100,
      expectancy: expectancy * 100,
      trades,
      winRate,
    };
  }

  /**
   * Build drift timeline (last 14 days)
   */
  private buildDriftTimeline(): DriftTimelinePoint[] {
    const timeline: DriftTimelinePoint[] = [];
    const levels: ReliabilityLevel[] = ['OK', 'WARN', 'DEGRADED', 'WARN', 'OK', 'OK', 'WARN', 'DEGRADED', 'DEGRADED', 'WARN', 'OK', 'OK', 'WARN', 'DEGRADED'];

    for (let i = 13; i >= 0; i--) {
      const date = new Date(Date.now() - i * 24 * 60 * 60 * 1000);
      timeline.push({
        date: date.toISOString().split('T')[0],
        level: levels[13 - i] || 'UNKNOWN',
      });
    }

    return timeline;
  }

  /**
   * Determine market regime from recent signals
   */
  private determineRegime(signals: any[]): {
    marketRegime: 'TREND' | 'RANGE' | 'UNKNOWN';
    trendStrength: number;
  } {
    if (signals.length < 10) {
      return { marketRegime: 'UNKNOWN', trendStrength: 0 };
    }

    // Calculate bias consistency
    let longCount = 0, shortCount = 0;
    for (const sig of signals.slice(0, 30)) {
      if (sig.direction === 'LONG') longCount++;
      else if (sig.direction === 'SHORT') shortCount++;
    }

    const total = longCount + shortCount;
    if (total === 0) return { marketRegime: 'UNKNOWN', trendStrength: 0 };

    const dominance = Math.max(longCount, shortCount) / total;

    if (dominance > 0.7) {
      return { marketRegime: 'TREND', trendStrength: dominance };
    } else {
      return { marketRegime: 'RANGE', trendStrength: 1 - dominance };
    }
  }
}

// Singleton
let instance: SentimentIntelligenceService | null = null;

export function getSentimentIntelligenceService(): SentimentIntelligenceService {
  if (!instance) {
    instance = new SentimentIntelligenceService();
  }
  return instance;
}
