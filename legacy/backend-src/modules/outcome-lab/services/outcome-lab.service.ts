/**
 * Outcome Lab Orchestrator
 *
 * Main entry point: review(resolvedMarket) → full learning report
 *
 * Pipeline:
 *   1. Load trace from MongoDB
 *   2. Run all review engines
 *   3. Generate grade + lessons
 *   4. Store review
 *   5. Accumulate for weight proposals
 */

import { getDb } from '../../../db/mongodb.js';
import type {
  OutcomeReview, ResolvedMarket, DecisionTrace,
  SignalHeatmapEntry, ExecutionQualitySummary,
} from '../types/outcome-lab.types.js';
import { traceBuilderService } from './trace-builder.service.js';
import { correctnessReviewService } from './correctness-review.service.js';
import { timingReviewService } from './timing-review.service.js';
import { calibrationReviewService } from './calibration-review.service.js';
import { sourceAttributionService } from './source-attribution.service.js';
import { narrativeReviewService } from './narrative-review.service.js';
import { missedOpportunityService } from './missed-opportunity.service.js';
import { weightProposalService } from './weight-proposal.service.js';

class OutcomeLabService {
  private reviewCollection = 'outcome_reviews';
  private heatmapCollection = 'signal_heatmap';

  /**
   * Full review of a resolved market.
   */
  async review(resolved: ResolvedMarket): Promise<OutcomeReview | null> {
    // 1. Load trace
    const trace = await traceBuilderService.getLatestTrace(resolved.marketId);
    if (!trace) {
      console.warn(`[OutcomeLab] No trace for market ${resolved.marketId}`);
      return null;
    }
    const traceHistory = await traceBuilderService.getTraceHistory(resolved.marketId);

    // 2. Run all review engines
    const correctness = correctnessReviewService.review(trace, resolved);
    const timing = timingReviewService.review(trace, traceHistory, resolved);
    const calibration = calibrationReviewService.review(trace, resolved);
    const sourceAttributions = await sourceAttributionService.attribute(trace, resolved);
    const narrative = narrativeReviewService.review(trace, resolved);
    const missedOpportunity = missedOpportunityService.review(trace, traceHistory, resolved);

    // 3. Grade
    const overallGrade = this.computeGrade(correctness, timing, calibration, missedOpportunity);

    // 3.5. Execution quality from trace
    const executionQuality: ExecutionQualitySummary | undefined = trace.executionQuality ? {
      score: trace.executionQuality.score,
      grade: trace.executionQuality.grade,
      direction: trace.executionQuality.direction,
      entryQuality: trace.executionQuality.entryQuality,
      timingQuality: trace.executionQuality.timingQuality,
      slippageLeakage: trace.executionQuality.slippageLeakage,
      missedMove: trace.executionQuality.missedMove,
      lessons: trace.executionQuality.lessons,
    } : undefined;

    // 4. Lessons learned
    const lessonsLearned = this.extractLessons(
      correctness, timing, calibration, sourceAttributions, narrative, missedOpportunity, executionQuality,
    );

    // 5. Weight proposals (from accumulated reviews — load previous reviews)
    const previousReviews = await this.getPreviousReviews(20);
    const proposals = weightProposalService.propose(previousReviews);

    const review: OutcomeReview = {
      marketId: resolved.marketId,
      question: trace.question,
      asset: trace.asset,
      outcome: resolved.outcome,
      resolvedAt: resolved.resolvedAt,
      trace,
      correctness,
      timing,
      calibration,
      sourceAttributions,
      narrative,
      missedOpportunity,
      executionQuality,
      proposals,
      overallGrade,
      lessonsLearned,
      reviewedAt: new Date(),
    };

    // 6. Store review
    await this.storeReview(review);

    // 7. Update heatmap
    await this.updateHeatmap(sourceAttributions);

    return review;
  }

  /**
   * Review a batch of resolved markets. Used for simulation/backtest.
   */
  async reviewBatch(
    resolvedMarkets: ResolvedMarket[],
  ): Promise<{ reviews: OutcomeReview[]; summary: Record<string, any> }> {
    const reviews: OutcomeReview[] = [];
    for (const rm of resolvedMarkets) {
      const review = await this.review(rm);
      if (review) reviews.push(review);
    }

    const summary = this.computeBatchSummary(reviews);
    return { reviews, summary };
  }

  /**
   * Simulate a review (without real trace data — uses case data directly).
   */
  async simulateReview(
    caseData: Record<string, any>,
    outcome: 'YES' | 'NO',
  ): Promise<OutcomeReview> {
    // Build trace from case
    const trace = traceBuilderService.buildTrace(caseData);

    const resolved: ResolvedMarket = {
      marketId: caseData.market_id || 'sim_' + Date.now(),
      question: caseData.question || '',
      asset: caseData.asset || 'BTC',
      outcome,
      resolvedAt: new Date(),
      finalPrice: outcome === 'YES' ? 1 : 0,
    };

    const correctness = correctnessReviewService.review(trace, resolved);
    const timing = timingReviewService.review(trace, [trace], resolved);
    const calibration = calibrationReviewService.review(trace, resolved);
    const sourceAttributions = await sourceAttributionService.attribute(trace, resolved);
    const narrative = narrativeReviewService.review(trace, resolved);
    const missedOpportunity = missedOpportunityService.review(trace, [trace], resolved);
    const overallGrade = this.computeGrade(correctness, timing, calibration, missedOpportunity);
    const executionQuality: ExecutionQualitySummary | undefined = trace.executionQuality ? {
      score: trace.executionQuality.score,
      grade: trace.executionQuality.grade,
      direction: trace.executionQuality.direction,
      entryQuality: trace.executionQuality.entryQuality,
      timingQuality: trace.executionQuality.timingQuality,
      slippageLeakage: trace.executionQuality.slippageLeakage,
      missedMove: trace.executionQuality.missedMove,
      lessons: trace.executionQuality.lessons,
    } : undefined;
    const lessonsLearned = this.extractLessons(
      correctness, timing, calibration, sourceAttributions, narrative, missedOpportunity, executionQuality,
    );

    return {
      marketId: resolved.marketId,
      question: trace.question,
      asset: trace.asset,
      outcome,
      resolvedAt: resolved.resolvedAt,
      trace,
      correctness,
      timing,
      calibration,
      sourceAttributions,
      narrative,
      missedOpportunity,
      executionQuality,
      proposals: { sourceAdjustments: [], timingAdjustments: [], calibrationAdjustments: [] },
      overallGrade,
      lessonsLearned,
      reviewedAt: new Date(),
    };
  }

  /**
   * Get signal confidence heatmap.
   */
  async getHeatmap(): Promise<SignalHeatmapEntry[]> {
    try {
      const db = getDb();
      const docs = await db.collection(this.heatmapCollection)
        .find({}, { projection: { _id: 0 } })
        .sort({ reliability: -1 })
        .limit(50)
        .toArray();
      return docs as SignalHeatmapEntry[];
    } catch {
      return [];
    }
  }

  /**
   * Get outcome stats for dashboard.
   */
  async getStats(): Promise<Record<string, any>> {
    try {
      const db = getDb();
      const col = db.collection(this.reviewCollection);
      const total = await col.countDocuments();
      const reviews = await col.find({}, { projection: { _id: 0 } })
        .sort({ reviewedAt: -1 }).limit(100).toArray();

      const correct = reviews.filter((r: any) => r.correctness?.correctness === 'CORRECT').length;
      const wrong = reviews.filter((r: any) => r.correctness?.correctness === 'WRONG').length;
      const mixed = reviews.filter((r: any) => r.correctness?.correctness === 'MIXED').length;

      const grades: Record<string, number> = { A: 0, B: 0, C: 0, D: 0, F: 0 };
      for (const r of reviews) {
        const g = (r as any).overallGrade;
        if (g in grades) grades[g]++;
      }

      const missed = reviews.filter((r: any) => r.missedOpportunity?.missed).length;
      const avgCalibrationError = reviews.length > 0
        ? reviews.reduce((s: number, r: any) => s + (r.calibration?.errorScore || 0), 0) / reviews.length
        : 0;

      const traceStats = await traceBuilderService.getStats();

      return {
        totalReviews: total,
        traceStats,
        correctness: { correct, wrong, mixed, total: reviews.length },
        accuracy: reviews.length > 0 ? Math.round((correct / reviews.length) * 100) : 0,
        grades,
        missedOpportunities: missed,
        avgCalibrationError: Math.round(avgCalibrationError * 1000) / 1000,
      };
    } catch {
      return { totalReviews: 0 };
    }
  }

  /**
   * Get recent reviews for UI.
   */
  async getRecentReviews(limit: number = 20): Promise<OutcomeReview[]> {
    try {
      const db = getDb();
      const docs = await db.collection(this.reviewCollection)
        .find({}, { projection: { _id: 0 } })
        .sort({ reviewedAt: -1 })
        .limit(limit)
        .toArray();
      return docs as OutcomeReview[];
    } catch {
      return [];
    }
  }

  // ── Private ──

  private computeGrade(
    correctness: any, timing: any, calibration: any, missed: any,
  ): 'A' | 'B' | 'C' | 'D' | 'F' {
    let score = 0;

    // Correctness (40%)
    if (correctness.correctness === 'CORRECT') score += 40;
    else if (correctness.correctness === 'MIXED') score += 20;

    // Timing (25%)
    const tq = timing.timingQuality;
    if (tq === 'EARLY') score += 25;
    else if (tq === 'GOOD') score += 20;
    else if (tq === 'OK') score += 12;
    else if (tq === 'LATE') score += 5;

    // Calibration (20%)
    const cq = calibration.calibrationQuality;
    if (cq === 'WELL_CALIBRATED') score += 20;
    else if (cq === 'OVERCONFIDENT' || cq === 'UNDERCONFIDENT') score += 8;

    // Opportunity capture (15%)
    if (!missed.missed) score += 15;
    else score += 3;

    if (score >= 85) return 'A';
    if (score >= 70) return 'B';
    if (score >= 50) return 'C';
    if (score >= 30) return 'D';
    return 'F';
  }

  private extractLessons(...layers: any[]): string[] {
    const lessons: string[] = [];
    for (const layer of layers) {
      if (!layer) continue;
      if (Array.isArray(layer)) {
        // Source attributions
        for (const sa of layer.slice(0, 2)) {
          if (sa.lesson) lessons.push(`[${sa.source}] ${sa.lesson}`);
        }
      } else if (layer.lessons && Array.isArray(layer.lessons)) {
        // ExecutionQualitySummary
        for (const l of layer.lessons.slice(0, 2)) {
          lessons.push(`[Execution] ${l}`);
        }
      } else if (layer?.notes?.length > 0) {
        lessons.push(layer.notes[0]);
      }
    }
    return lessons.slice(0, 8);
  }

  private async storeReview(review: OutcomeReview): Promise<void> {
    try {
      const db = getDb();
      await db.collection(this.reviewCollection).updateOne(
        { marketId: review.marketId },
        { $set: review },
        { upsert: true },
      );
    } catch (err: any) {
      console.error(`[OutcomeLab] Failed to store review: ${err.message}`);
    }
  }

  private async getPreviousReviews(limit: number): Promise<OutcomeReview[]> {
    try {
      const db = getDb();
      const docs = await db.collection(this.reviewCollection)
        .find({}, { projection: { _id: 0 } })
        .sort({ reviewedAt: -1 })
        .limit(limit)
        .toArray();
      return docs as OutcomeReview[];
    } catch {
      return [];
    }
  }

  private async updateHeatmap(attributions: any[]): Promise<void> {
    try {
      const db = getDb();
      for (const a of attributions) {
        const existing = await db.collection(this.heatmapCollection)
          .findOne({ source: a.source }, { projection: { _id: 0 } });

        const total = (existing?.totalOccurrences || 0) + 1;
        const earlyCount = (existing?.earlySignalRate || 0) * (total - 1) + (a.timeliness === 'early' ? 1 : 0);
        const confirmCount = (existing?.confirmationRate || 0) * (total - 1) + (a.timeliness === 'on_time' ? 1 : 0);
        const noiseCount = (existing?.noiseRate || 0) * (total - 1) + (!a.helpful ? 1 : 0);

        await db.collection(this.heatmapCollection).updateOne(
          { source: a.source },
          {
            $set: {
              source: a.source,
              sourceType: a.sourceType,
              totalOccurrences: total,
              earlySignalRate: Math.round((earlyCount / total) * 100) / 100,
              confirmationRate: Math.round((confirmCount / total) * 100) / 100,
              noiseRate: Math.round((noiseCount / total) * 100) / 100,
              avgImpactScore: existing
                ? Math.round(((existing.avgImpactScore * (total - 1) + a.impactScore) / total) * 100) / 100
                : a.impactScore,
              avgLeadTime: 0,
              reliability: a.helpful ? 1 : 0,
              updatedAt: new Date(),
            },
          },
          { upsert: true },
        );
      }
    } catch (err: any) {
      console.error(`[OutcomeLab] Heatmap update error: ${err.message}`);
    }
  }

  private computeBatchSummary(reviews: OutcomeReview[]): Record<string, any> {
    const total = reviews.length;
    if (total === 0) return { total: 0 };

    const correct = reviews.filter(r => r.correctness.correctness === 'CORRECT').length;
    const grades: Record<string, number> = { A: 0, B: 0, C: 0, D: 0, F: 0 };
    for (const r of reviews) grades[r.overallGrade]++;

    const missed = reviews.filter(r => r.missedOpportunity.missed).length;
    const avgError = reviews.reduce((s, r) => s + r.calibration.errorScore, 0) / total;

    return {
      total,
      accuracy: Math.round((correct / total) * 100),
      grades,
      missedOpportunities: missed,
      avgCalibrationError: Math.round(avgError * 1000) / 1000,
      proposals: reviews.length >= 5 ? weightProposalService.propose(reviews) : null,
    };
  }
}

export const outcomeLabService = new OutcomeLabService();
