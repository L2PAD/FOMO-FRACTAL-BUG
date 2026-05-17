/**
 * Sentiment Shadow Admin Routes
 * ==============================
 * 
 * BLOCK 9: Admin API for shadow mode monitoring.
 * 
 * Endpoints:
 * - GET /summary — Full shadow performance summary
 * - GET /latest — Recent shadow decisions
 * - GET /disagreements — Disagreement analysis
 * - GET /symbols — Per-symbol breakdown
 * - POST /finalize — Trigger finalization of pending decisions
 * - POST /record-test — Test shadow recording (debug)
 */

import fp from 'fastify-plugin';
import type { FastifyInstance } from 'fastify';
import { getSentimentShadowService } from './sentiment.shadow.service.js';
import { getSentimentShadowAnalyticsService } from './sentiment.shadow.analytics.service.js';
import { getSentimentShadowDecisionModel } from './sentiment.shadow.model.js';
import { getShadowRoutingEngine } from './sentiment.shadow.routing.js';

async function sentimentShadowRoutes(app: FastifyInstance): Promise<void> {
  const shadowService = getSentimentShadowService();
  const analyticsService = getSentimentShadowAnalyticsService();

  /**
   * GET /summary — Full shadow performance summary
   */
  app.get('/summary', async () => {
    const summary = await analyticsService.getSummary();
    
    return {
      ok: true,
      window: '24H',
      ...summary,
      
      // Formatted for UI
      formatted: {
        ruleHitRate: `${(summary.ruleHitRate * 100).toFixed(1)}%`,
        mlHitRate: `${(summary.mlHitRate * 100).toFixed(1)}%`,
        delta: `${summary.delta >= 0 ? '+' : ''}${(summary.delta * 100).toFixed(1)}%`,
        agreementRate: `${(summary.agreementRate * 100).toFixed(1)}%`,
      },
    };
  });

  /**
   * GET /latest — Recent shadow decisions
   */
  app.get('/latest', async () => {
    const decisions = await shadowService.getRecentDecisions(50);
    
    return {
      ok: true,
      count: decisions.length,
      decisions: decisions.map(d => ({
        symbol: d.symbol,
        asOf: d.asOf,
        ruleAction: d.ruleAction,
        mlAction: d.mlAction,
        agreement: d.agreement,
        evaluated: d.evaluated,
        forwardReturn: d.forwardReturn,
        forwardLabel: d.forwardLabel,
        ruleCorrect: d.ruleCorrect,
        mlCorrect: d.mlCorrect,
        newsContext: d.newsContext || null,
      })),
    };
  });

  /**
   * GET /disagreements — Disagreement analysis
   */
  app.get('/disagreements', async () => {
    const disagreements = await analyticsService.getDisagreements(100);
    
    const summary = {
      total: disagreements.length,
      mlWins: disagreements.filter(d => d.winner === 'ML').length,
      ruleWins: disagreements.filter(d => d.winner === 'RULE').length,
      ties: disagreements.filter(d => d.winner === 'TIE').length,
    };

    return {
      ok: true,
      summary,
      details: disagreements,
    };
  });

  /**
   * GET /symbols — Per-symbol breakdown
   */
  app.get('/symbols', async () => {
    const breakdown = await analyticsService.getSymbolBreakdown();
    
    return {
      ok: true,
      count: breakdown.length,
      symbols: breakdown.map(s => ({
        ...s,
        ruleHitRate: `${(s.ruleHitRate * 100).toFixed(1)}%`,
        mlHitRate: `${(s.mlHitRate * 100).toFixed(1)}%`,
        delta: `${s.delta >= 0 ? '+' : ''}${(s.delta * 100).toFixed(1)}%`,
      })),
    };
  });

  /**
   * GET /slice/:dimension — TASK 2.0: Slice by news context
   * Dimensions: eventType, importanceBand, assetClass, recencyBucket
   */
  app.get('/slice/:dimension', async (req: any) => {
    const { dimension } = req.params;
    const validDimensions = ['eventType', 'importanceBand', 'assetClass', 'recencyBucket'];
    
    if (!validDimensions.includes(dimension)) {
      return { ok: false, error: `Invalid dimension. Valid: ${validDimensions.join(', ')}` };
    }

    const breakdown = await analyticsService.getSliceBreakdown(dimension as any);
    
    return {
      ok: true,
      dimension,
      count: breakdown.length,
      slices: breakdown.map(s => ({
        ...s,
        ruleHitRate: `${(s.ruleHitRate * 100).toFixed(1)}%`,
        mlHitRate: `${(s.mlHitRate * 100).toFixed(1)}%`,
        delta: `${s.delta >= 0 ? '+' : ''}${(s.delta * 100).toFixed(1)}%`,
      })),
    };
  });

  /**
   * GET /confidence — TASK 2.0: Confidence calibration
   */
  app.get('/confidence', async () => {
    const calibration = await analyticsService.getConfidenceCalibration();
    
    return {
      ok: true,
      buckets: calibration.map(b => ({
        ...b,
        mlAccuracy: `${(b.mlAccuracy * 100).toFixed(1)}%`,
      })),
    };
  });

  /**
   * GET /stats — Enhanced stats with context coverage
   */
  app.get('/stats', async () => {
    const stats = await shadowService.getStats();
    
    return {
      ok: true,
      ...stats,
      formatted: {
        agreementRate: `${(stats.agreementRate * 100).toFixed(1)}%`,
        contextCoverage: `${(stats.contextCoverage * 100).toFixed(1)}%`,
      },
    };
  });

  /**
   * POST /backfill — Backfill newsContext for decisions missing it
   */
  app.post('/backfill', async () => {
    const result = await shadowService.backfillNewsContext();
    return { ok: true, ...result };
  });

  /**
   * GET /report — Full ML validation report (TASK 2.2)
   * Returns comprehensive analysis when enough data accumulated
   */
  app.get('/report', async () => {
    const summary = await analyticsService.getSummary();
    
    const [
      sliceEventType,
      sliceImportance,
      sliceAssetClass,
      sliceRecency,
      confidence,
      symbolBreakdown,
    ] = await Promise.all([
      analyticsService.getSliceBreakdown('eventType'),
      analyticsService.getSliceBreakdown('importanceBand'),
      analyticsService.getSliceBreakdown('assetClass'),
      analyticsService.getSliceBreakdown('recencyBucket'),
      analyticsService.getConfidenceCalibration(),
      analyticsService.getSymbolBreakdown(),
    ]);

    const formatSlice = (s: any) => ({
      ...s,
      ruleHitRate: `${(s.ruleHitRate * 100).toFixed(1)}%`,
      mlHitRate: `${(s.mlHitRate * 100).toFixed(1)}%`,
      delta: `${s.delta >= 0 ? '+' : ''}${(s.delta * 100).toFixed(1)}%`,
    });

    // Determine scenario
    let scenario = 'INSUFFICIENT_DATA';
    if (summary.evaluated >= 50) {
      if (summary.delta > 0.03) scenario = 'A_ML_HAS_EDGE';
      else if (summary.delta > -0.03) scenario = 'B_ML_EQUALS_RULE';
      else scenario = 'C_ML_WORSE';
    }

    return {
      ok: true,
      scenario,
      dataReady: summary.evaluated >= 150,
      global: {
        total: summary.total,
        evaluated: summary.evaluated,
        pending: summary.pending,
        mlAccuracy: `${(summary.mlHitRate * 100).toFixed(1)}%`,
        ruleAccuracy: `${(summary.ruleHitRate * 100).toFixed(1)}%`,
        delta: `${summary.delta >= 0 ? '+' : ''}${(summary.delta * 100).toFixed(1)}%`,
        agreementRate: `${(summary.agreementRate * 100).toFixed(1)}%`,
        promotionReady: summary.readyForPromotion,
        blockers: summary.promotionBlockers,
      },
      byImportance: sliceImportance.map(formatSlice),
      byEventType: sliceEventType.map(formatSlice),
      byAssetClass: sliceAssetClass.map(formatSlice),
      byRecency: sliceRecency.map(formatSlice),
      bySymbol: symbolBreakdown.map(s => ({
        ...s,
        ruleHitRate: `${(s.ruleHitRate * 100).toFixed(1)}%`,
        mlHitRate: `${(s.mlHitRate * 100).toFixed(1)}%`,
        delta: `${s.delta >= 0 ? '+' : ''}${(s.delta * 100).toFixed(1)}%`,
      })),
      confidenceCalibration: confidence.map(b => ({
        ...b,
        mlAccuracy: `${(b.mlAccuracy * 100).toFixed(1)}%`,
      })),
    };
  });

  /**
   * POST /finalize — Trigger finalization of pending decisions
   */
  app.post('/finalize', async () => {
    const result = await analyticsService.finalizeAllPending();
    
    return {
      ok: true,
      message: 'Finalization complete',
      ...result,
    };
  });

  /**
   * GET /label-distribution — Check outcome label quality (TASK 2.1+)
   * Ensures no skew toward NEUTRAL and balanced UP/DOWN
   */
  app.get('/label-distribution', async () => {
    const ShadowModel = getSentimentShadowDecisionModel();
    
    const [totalEvaluated, labels, volBuckets] = await Promise.all([
      ShadowModel.countDocuments({ evaluated: true }),
      ShadowModel.aggregate([
        { $match: { evaluated: true } },
        { $group: { _id: '$forwardLabel', count: { $sum: 1 } } },
      ]),
      ShadowModel.aggregate([
        { $match: { evaluated: true, volatilityBucket: { $exists: true } } },
        { $group: {
          _id: '$volatilityBucket',
          count: { $sum: 1 },
          avgThreshold: { $avg: '$adaptiveThreshold' },
          avgReturnPct: { $avg: '$forwardReturnPct' },
        }},
        { $sort: { _id: 1 } },
      ]),
    ]);
    
    const distribution: Record<string, number> = {};
    for (const l of labels) distribution[l._id || 'UNKNOWN'] = l.count;
    
    const total = totalEvaluated || 1;
    const neutralPct = ((distribution['FLAT'] || 0) / total) * 100;
    
    // Quality check
    const qualityOk = neutralPct >= 30 && neutralPct <= 65;
    const upDownBalance = Math.abs(
      ((distribution['UP'] || 0) - (distribution['DOWN'] || 0)) / total
    );

    return {
      ok: true,
      totalEvaluated,
      distribution,
      percentages: {
        UP: `${(((distribution['UP'] || 0) / total) * 100).toFixed(1)}%`,
        DOWN: `${(((distribution['DOWN'] || 0) / total) * 100).toFixed(1)}%`,
        FLAT: `${neutralPct.toFixed(1)}%`,
      },
      volatilityBuckets: volBuckets.map(v => ({
        bucket: v._id,
        count: v.count,
        avgThresholdPct: `±${(v.avgThreshold * 100).toFixed(2)}%`,
        avgReturnPct: `${v.avgReturnPct.toFixed(2)}%`,
      })),
      quality: {
        neutralInRange: qualityOk,
        upDownBalanced: upDownBalance < 0.3,
        verdict: qualityOk && upDownBalance < 0.3 ? 'GOOD' : 'NEEDS_REVIEW',
      },
    };
  });

  /**
   * POST /record-test — Test shadow recording (debug only)
   */
  app.post('/record-test', async (req: any) => {
    const { symbol = 'BTC', bias = 0.15 } = req.body || {};
    
    const result = await shadowService.recordShadowDecision({
      symbol,
      asOf: new Date(),
      ruleAction: bias > 0.1 ? 'LONG' : bias < -0.1 ? 'SHORT' : 'NEUTRAL',
      ruleConfidence: Math.abs(bias),
      ruleBias: bias,
      score: 0.6,
      weightedScore: 0.55,
      weightedConfidence: 0.7,
      eventsCount: 20,
    });
    
    return {
      ok: result.recorded,
      ...result,
    };
  });

  // ══════════════════════════════════════════════════════════════
  // ANALYSIS ENDPOINT — Decision-making tool for First Read
  // ══════════════════════════════════════════════════════════════

  /**
   * GET /analysis — Full shadow analysis for First Read
   * 
   * Returns:
   * - Global ML vs Rule (delta + count)
   * - Slice breakdowns (importance, eventType, recency, volatility)
   * - Cross-slice combinations (importance + eventType + recency)
   * - Top winning/losing slices (sorted by delta, filtered by count)
   * - Confidence calibration (0-0.4, 0.4-0.6, 0.6-0.8, 0.8+)
   */
  app.get('/analysis', async () => {
    const analyticsService = getSentimentShadowAnalyticsService();
    
    const [
      summary,
      byImportance,
      byEventType,
      byRecency,
      byAssetClass,
      byVolatility,
      confidence,
      crossSlice,
    ] = await Promise.all([
      analyticsService.getSummary(),
      analyticsService.getSliceBreakdown('importanceBand'),
      analyticsService.getSliceBreakdown('eventType'),
      analyticsService.getSliceBreakdown('recencyBucket'),
      analyticsService.getSliceBreakdown('assetClass'),
      analyticsService.getSliceBreakdown('volatilityBucket' as any),
      analyticsService.getConfidenceCalibration(),
      analyticsService.getCrossSliceAnalysis(3),
    ]);

    // Format slice with delta emphasis
    const fmtSlice = (s: any) => ({
      value: s.value,
      samples: s.samples,
      mlAccuracy: `${(s.mlHitRate * 100).toFixed(1)}%`,
      ruleAccuracy: `${(s.ruleHitRate * 100).toFixed(1)}%`,
      delta: `${s.delta >= 0 ? '+' : ''}${(s.delta * 100).toFixed(1)}%`,
      deltaRaw: s.delta,
      mlWins: s.delta > 0,
    });

    const fmtCross = (s: any) => ({
      slice: s.slice,
      importance: s.importance,
      eventType: s.eventType,
      recency: s.recency,
      samples: s.samples,
      mlAccuracy: `${(s.mlHitRate * 100).toFixed(1)}%`,
      ruleAccuracy: `${(s.ruleHitRate * 100).toFixed(1)}%`,
      delta: `${s.delta >= 0 ? '+' : ''}${(s.delta * 100).toFixed(1)}%`,
      deltaRaw: s.delta,
      avgConfidence: s.avgConfidence,
    });

    // Determine scenario
    let scenario = 'INSUFFICIENT_DATA';
    let recommendation = 'Ждём данные. Не трогай ML.';
    
    if (summary.evaluated >= 50) {
      if (summary.delta > 0.03) {
        scenario = 'A_ML_HAS_EDGE';
        recommendation = 'ML показывает edge. Проверь winning slices и включи routing.';
      } else if (summary.delta > -0.03) {
        scenario = 'B_ML_EQUALS_RULE';
        recommendation = 'ML ≈ Rule. Ищи edge в конкретных слайсах (HIGH + regulation + fresh).';
      } else {
        scenario = 'C_ML_WORSE';
        recommendation = 'ML хуже Rule. Не включай ML. Усиливай features.';
      }
    }

    return {
      ok: true,
      scenario,
      recommendation,
      
      global: {
        total: summary.total,
        evaluated: summary.evaluated,
        pending: summary.pending,
        mlAccuracy: `${(summary.mlHitRate * 100).toFixed(1)}%`,
        ruleAccuracy: `${(summary.ruleHitRate * 100).toFixed(1)}%`,
        delta: `${summary.delta >= 0 ? '+' : ''}${(summary.delta * 100).toFixed(1)}%`,
        deltaRaw: summary.delta,
        agreementRate: `${(summary.agreementRate * 100).toFixed(1)}%`,
        disagreements: summary.disagreements,
        mlWinsOnDisagreement: summary.mlWinsOnDisagreement,
        ruleWinsOnDisagreement: summary.ruleWinsOnDisagreement,
        promotionReady: summary.readyForPromotion,
        blockers: summary.promotionBlockers,
      },

      slices: {
        byImportance: byImportance.map(fmtSlice),
        byEventType: byEventType.map(fmtSlice),
        byRecency: byRecency.map(fmtSlice),
        byAssetClass: byAssetClass.map(fmtSlice),
        byVolatility: byVolatility.map(fmtSlice),
      },

      crossSlice: {
        topWinning: crossSlice.topWinning.map(fmtCross),
        topLosing: crossSlice.topLosing.map(fmtCross),
        allSlices: crossSlice.allSlices.map(fmtCross),
      },

      confidenceCalibration: confidence.map(b => ({
        range: b.confidenceRange,
        samples: b.samples,
        mlAccuracy: `${(b.mlAccuracy * 100).toFixed(1)}%`,
        calibrated: Math.abs(b.mlAccuracy - parseFloat(b.confidenceRange.split('-')[0])) < 0.2,
      })),

      dataReady: summary.evaluated >= 50,
      nextMilestone: summary.evaluated < 50
        ? `${50 - summary.evaluated} more evaluated decisions needed`
        : summary.evaluated < 150
          ? `${150 - summary.evaluated} more for full confidence`
          : 'Full confidence reached',
    };
  });

  // ══════════════════════════════════════════════════════════════
  // ROUTING ENGINE — Context-aware ML/Rule routing
  // ══════════════════════════════════════════════════════════════

  /**
   * GET /routing/rules — Get all routing rules
   */
  app.get('/routing/rules', async () => {
    const engine = getShadowRoutingEngine();
    const rules = await engine.getRules();
    
    return {
      ok: true,
      rules: rules.map(r => ({
        name: r.name,
        conditions: r.conditions,
        action: r.action,
        priority: r.priority,
        enabled: r.enabled,
        minSampleSize: r.minSampleSize,
        minDelta: r.minDelta,
        evidence: r.evidence,
        validation: engine.validateEvidence(r),
      })),
    };
  });

  /**
   * POST /routing/seed — Initialize default rules
   */
  app.post('/routing/seed', async () => {
    const engine = getShadowRoutingEngine();
    const result = await engine.seedDefaults();
    return { ok: true, ...result };
  });

  /**
   * PUT /routing/rules/:name — Update a routing rule
   */
  app.put<{ Params: { name: string }; Body: any }>('/routing/rules/:name', async (req) => {
    const engine = getShadowRoutingEngine();
    const updated = await engine.updateRule(req.params.name, req.body);
    
    if (!updated) return { ok: false, error: 'Rule not found' };
    
    return {
      ok: true,
      rule: updated,
      validation: engine.validateEvidence(updated),
    };
  });

  /**
   * POST /routing/match — Test context against routing rules
   */
  app.post<{ Body: any }>('/routing/match', async (req) => {
    const engine = getShadowRoutingEngine();
    const result = await engine.matchAction(req.body);
    return { ok: true, ...result };
  });

  console.log('[Sentiment-ML] Shadow admin routes registered (BLOCK 9)');
}

// Export wrapped in fastify-plugin
export default fp(sentimentShadowRoutes, {
  name: 'sentiment-shadow-routes',
  fastify: '4.x',
});

export { sentimentShadowRoutes };
