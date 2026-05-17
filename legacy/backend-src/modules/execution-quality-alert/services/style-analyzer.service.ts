/**
 * Style Analyzer
 *
 * Compares execution styles across all contexts for a given asset.
 * Output: bestStyle, worstStyle, delta — critical for future auto-tune.
 */

import type { ExecutionScoreEntry, StyleComparison } from '../types/execution-context.types.js';
import type { StyleAnalysisResult } from '../types/execution-anomaly.types.js';
import { contextStatsRepo } from '../repositories/execution-context-stats.repository.js';

const MIN_SAMPLES_PER_STYLE = 2;

class StyleAnalyzerService {
  /**
   * Compare execution styles from provided entries.
   */
  analyze(entries: ExecutionScoreEntry[], currentStyle: string): StyleAnalysisResult {
    // Group by execution style (derived from the context key or entry metadata)
    const styleMap = new Map<string, { scores: number[]; leakages: number[]; misses: number }>();

    for (const entry of entries) {
      // Try to extract style from entry context or use the score-based inference
      const style = this.inferStyleFromEntry(entry);
      if (!styleMap.has(style)) {
        styleMap.set(style, { scores: [], leakages: [], misses: 0 });
      }
      const s = styleMap.get(style)!;
      s.scores.push(entry.score);
      s.leakages.push(entry.slippageLeakage);
      if (entry.opportunityReason !== 'NONE' && entry.opportunityReason) s.misses++;
    }

    // Build comparisons
    const allStyles: { style: string; avgScore: number; count: number }[] = [];
    let bestStyle = currentStyle;
    let bestAvgScore = 0;
    let worstStyle = currentStyle;
    let worstAvgScore = 1;
    let currentAvgScore = 0;

    for (const [style, data] of styleMap) {
      if (data.scores.length < MIN_SAMPLES_PER_STYLE) continue;

      const avgScore = data.scores.reduce((a, b) => a + b, 0) / data.scores.length;
      const rounded = Math.round(avgScore * 100) / 100;

      allStyles.push({ style, avgScore: rounded, count: data.scores.length });

      if (rounded > bestAvgScore) { bestAvgScore = rounded; bestStyle = style; }
      if (rounded < worstAvgScore) { worstAvgScore = rounded; worstStyle = style; }

      if (style.toUpperCase() === currentStyle.toUpperCase()) {
        currentAvgScore = rounded;
      }
    }

    // If current style wasn't found, use overall worst
    if (currentAvgScore === 0 && allStyles.length > 0) {
      currentAvgScore = worstAvgScore;
    }

    return {
      currentStyle,
      currentAvgScore,
      bestStyle,
      bestAvgScore,
      worstStyle,
      worstAvgScore,
      delta: Math.round((bestAvgScore - currentAvgScore) * 100) / 100,
      allStyles: allStyles.sort((a, b) => b.avgScore - a.avgScore),
    };
  }

  /**
   * Load entries by asset and run full analysis.
   */
  async analyzeByAsset(asset: string, currentStyle: string): Promise<StyleAnalysisResult> {
    const entries = await contextStatsRepo.getEntriesByAsset(asset);
    return this.analyze(entries, currentStyle);
  }

  private inferStyleFromEntry(entry: ExecutionScoreEntry): string {
    // Entry doesn't store style directly — infer from opportunity reason and scores
    if (entry.opportunityReason === 'WAIT_TOO_LONG') return 'WAIT';
    if (entry.opportunityReason === 'LIMIT_NOT_FILLED') return 'LIMIT';
    if (entry.slippageLeakage > 0.03) return 'MARKET';
    if (entry.timingScore > 0.7 && entry.entryScore > 0.6) return 'MARKET';
    if (entry.timingScore < 0.4) return 'WAIT';
    return 'UNKNOWN';
  }
}

export const styleAnalyzerService = new StyleAnalyzerService();
