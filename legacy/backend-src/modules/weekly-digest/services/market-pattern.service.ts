/**
 * Market Pattern Analysis
 *
 * Identifies which market families perform best/worst:
 * ETF, macro, meme, launch, regulation, listing, direction_bet, etc.
 */

import type { MarketPattern } from '../types/digest.types.js';

interface ReviewData {
  correctness: { correctness: string };
  traces: { edge: number; eventType?: string }[];
  asset?: string;
  marketType?: string;
}

class MarketPatternService {
  analyze(reviews: ReviewData[]): { best: MarketPattern[]; worst: MarketPattern[] } {
    const patternMap = new Map<string, { correct: number; total: number; edgeSum: number }>();

    for (const r of reviews) {
      const pattern = this.inferPattern(r);
      if (!patternMap.has(pattern)) {
        patternMap.set(pattern, { correct: 0, total: 0, edgeSum: 0 });
      }
      const p = patternMap.get(pattern)!;
      p.total++;
      p.edgeSum += Math.abs(r.traces?.[0]?.edge || 0);
      if (r.correctness?.correctness === 'CORRECT') p.correct++;
    }

    const patterns: MarketPattern[] = [];
    for (const [pattern, data] of patternMap.entries()) {
      patterns.push({
        pattern,
        accuracy: data.total > 0 ? Math.round((data.correct / data.total) * 100) : 0,
        count: data.total,
        avgEdge: data.total > 0 ? Math.round((data.edgeSum / data.total) * 10000) / 10000 : 0,
      });
    }

    patterns.sort((a, b) => b.accuracy - a.accuracy);

    return {
      best: patterns.filter(p => p.accuracy >= 50).slice(0, 5),
      worst: patterns.filter(p => p.accuracy < 50).slice(0, 5),
    };
  }

  private inferPattern(r: ReviewData): string {
    const eventType = r.traces?.[0]?.eventType;
    if (eventType && eventType !== 'unknown') return eventType;

    const asset = (r.asset || '').toUpperCase();
    if (['BTC', 'ETH'].includes(asset)) return 'major_crypto';
    if (['SOL', 'AVAX', 'SUI', 'APT'].includes(asset)) return 'alt_l1';
    if (['DOGE', 'PEPE', 'WIF', 'BONK'].includes(asset)) return 'meme';
    if (['UNI', 'AAVE', 'LINK'].includes(asset)) return 'defi_blue_chip';
    if (['ARB', 'OP', 'MATIC'].includes(asset)) return 'l2';
    return r.marketType || 'general';
  }
}

export const marketPatternService = new MarketPatternService();
