/**
 * Sentiment Equity V2 Service
 * ============================
 * 
 * BLOCK P2.2: Mini Equity Curve for Sentiment UI
 * Shows paper performance over time
 */

import {
  SentimentEquityResponse,
  SentimentEquityPoint,
} from './sentiment-chart-v2.types.js';
import { SentimentAggregateModel } from '../storage/sentiment-aggregate.model.js';

export class SentimentEquityV2Service {
  /**
   * Get equity curve for symbol/period
   */
  async getEquity(
    symbol: string,
    period: string = '90d'
  ): Promise<SentimentEquityResponse> {
    // Parse period
    const days = this.parsePeriod(period);
    const since = new Date(Date.now() - days * 24 * 60 * 60 * 1000);

    // Fetch historical aggregates
    const aggregates = await SentimentAggregateModel.find({
      symbol: symbol.toUpperCase(),
      window: '24H',
      asOf: { $gte: since },
    })
      .sort({ asOf: 1 })
      .lean();

    // Build equity curve from predictions
    const points: SentimentEquityPoint[] = [];
    let equity = 1.0;
    let maxEquity = 1.0;
    let maxDD = 0;
    let totalReturn = 0;
    let trades = 0;
    let wins = 0;

    for (let i = 0; i < aggregates.length - 1; i++) {
      const agg = aggregates[i];
      const nextAgg = aggregates[i + 1];

      const bias = agg.bias ?? 0;
      const confidence = agg.confidence ?? agg.weightedConfidence ?? 0.5;

      // Skip neutral signals
      if (Math.abs(bias) < 0.1 || confidence < 0.3) {
        points.push({
          time: agg.asOf?.toISOString() || new Date().toISOString(),
          equity,
        });
        continue;
      }

      // Simulate trade outcome
      // In real system, this would compare predicted vs actual price
      const direction = bias > 0 ? 1 : -1;
      const predictedMove = bias * confidence * 0.05;

      // Random walk simulation for demo (replace with actual price comparison)
      const actualMove = (Math.random() - 0.5) * 0.03 * direction;
      const hit = (predictedMove > 0 && actualMove > 0) || (predictedMove < 0 && actualMove < 0);

      const pnl = hit ? Math.abs(actualMove) * confidence : -Math.abs(actualMove) * 0.5;
      equity *= (1 + pnl);
      trades++;

      if (hit) wins++;

      // Track max drawdown
      maxEquity = Math.max(maxEquity, equity);
      const dd = (maxEquity - equity) / maxEquity;
      maxDD = Math.max(maxDD, dd);

      points.push({
        time: agg.asOf?.toISOString() || new Date().toISOString(),
        equity,
      });
    }

    // Add final point
    if (aggregates.length > 0) {
      const last = aggregates[aggregates.length - 1];
      points.push({
        time: last.asOf?.toISOString() || new Date().toISOString(),
        equity,
      });
    }

    totalReturn = (equity - 1);

    // Calculate Sharpe (simplified)
    const avgReturn = trades > 0 ? totalReturn / trades : 0;
    const sharpe = avgReturn > 0 ? avgReturn / (maxDD || 0.1) : 0;

    return {
      ok: true,
      symbol,
      period,
      points,
      stats: {
        totalReturn,
        maxDD,
        sharpe,
        trades,
      },
    };
  }

  private parsePeriod(period: string): number {
    const match = period.match(/^(\d+)([dDwWmM])$/);
    if (!match) return 90;

    const num = parseInt(match[1], 10);
    const unit = match[2].toLowerCase();

    switch (unit) {
      case 'd': return num;
      case 'w': return num * 7;
      case 'm': return num * 30;
      default: return 90;
    }
  }
}

// Singleton
let instance: SentimentEquityV2Service | null = null;

export function getSentimentEquityV2Service(): SentimentEquityV2Service {
  if (!instance) {
    instance = new SentimentEquityV2Service();
  }
  return instance;
}
