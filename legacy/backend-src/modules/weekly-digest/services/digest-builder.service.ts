/**
 * Digest Builder — Orchestrator
 *
 * Assembles all analysis layers into a single WeeklyDigest.
 * Reads from MongoDB (outcome lab traces + reviews).
 */

import { MongoClient } from 'mongodb';
import { performanceAggregatorService } from './performance-aggregator.service.js';
import { timingAnalysisService } from './timing-analysis.service.js';
import { edgeAttributionService } from './edge-attribution.service.js';
import { decisionQualityService } from './decision-quality.service.js';
import { sourcePerformanceService } from './source-performance.service.js';
import { marketPatternService } from './market-pattern.service.js';
import { missedOpportunityService } from './missed-opportunity.service.js';
import { calibrationAnalysisService } from './calibration-analysis.service.js';
import { alertPerformanceService } from './alert-performance.service.js';
import { learningExtractorService } from './learning-extractor.service.js';
import { executionQualityService } from './execution-quality.service.js';
import { digestComparisonService } from './digest-comparison.service.js';
import type { WeeklyDigest } from '../types/digest.types.js';

const MONGO_URL = process.env.MONGO_URL || 'mongodb://localhost:27017';
const DB_NAME = process.env.DB_NAME || 'intelligence_engine';

class DigestBuilderService {
  /**
   * Generate a weekly digest for a given time range.
   * If no range specified, uses last 7 days.
   */
  async generate(fromDate?: string, toDate?: string): Promise<WeeklyDigest> {
    const now = new Date();
    const to = toDate ? new Date(toDate) : now;
    const from = fromDate ? new Date(fromDate) : new Date(to.getTime() - 7 * 24 * 60 * 60 * 1000);

    // Previous period for comparison
    const prevFrom = new Date(from.getTime() - 7 * 24 * 60 * 60 * 1000);
    const prevTo = from;

    const client = new MongoClient(MONGO_URL);
    try {
      await client.connect();
      const db = client.db(DB_NAME);

      // Fetch reviews for current period
      const reviews = await db.collection('outcome_reviews').find({
        $or: [
          { createdAt: { $gte: from.toISOString(), $lte: to.toISOString() } },
          { createdAt: { $exists: false } },
          { createdAt: null },
        ],
      }).toArray();

      // Fetch reviews for previous period (for comparison)
      const prevReviews = await db.collection('outcome_reviews').find({
        createdAt: { $gte: prevFrom.toISOString(), $lte: prevTo.toISOString() },
      }).toArray();

      // Fetch traces for reviewed markets
      const marketIds = reviews.map(r => r.marketId);
      const traces = await db.collection('outcome_traces').find({
        marketId: { $in: marketIds },
      }).toArray();

      // Fetch alert history (from in-memory — use the alert-engine API)
      const alerts = await this.fetchAlertHistory();

      // Build trace map
      const traceMap = new Map<string, any[]>();
      for (const t of traces) {
        if (!traceMap.has(t.marketId)) traceMap.set(t.marketId, []);
        traceMap.get(t.marketId)!.push(t);
      }

      // Enrich reviews with traces
      const enrichedReviews = reviews.map(r => ({
        ...r,
        traces: traceMap.get(r.marketId) || [],
      }));

      const enrichedPrevReviews = prevReviews.map(r => ({ ...r, traces: [] }));

      // --- Run all analysis layers ---
      const periodFrom = from.toISOString();
      const periodTo = to.toISOString();

      const performance = performanceAggregatorService.aggregate(enrichedReviews, periodFrom, periodTo);
      const timing = timingAnalysisService.analyze(enrichedReviews);
      const edgeAttribution = edgeAttributionService.analyze(enrichedReviews);
      const decisionQuality = decisionQualityService.analyze(enrichedReviews);
      const sources = sourcePerformanceService.analyze(enrichedReviews);
      const patterns = marketPatternService.analyze(enrichedReviews);
      const missed = missedOpportunityService.analyze(enrichedReviews);
      const calibration = calibrationAnalysisService.analyze(enrichedReviews);
      const alertPerf = alertPerformanceService.analyze(alerts, enrichedReviews);
      const executionQuality = executionQualityService.analyze(enrichedReviews);

      // Previous period performance for comparison
      let prevPerf = null;
      let prevTiming = null;
      if (enrichedPrevReviews.length > 0) {
        prevPerf = performanceAggregatorService.aggregate(enrichedPrevReviews, prevFrom.toISOString(), prevTo.toISOString());
        prevTiming = timingAnalysisService.analyze(enrichedPrevReviews);
      }

      // Learning extractor (produces human-readable insights)
      const learning = learningExtractorService.extract({
        performance, timing, edgeAttribution, decisionQuality, calibration,
        bestPatterns: patterns.best, worstPatterns: patterns.worst,
        missedOpportunities: missed.topMissed,
        prevPerformance: prevPerf,
        prevTiming: prevTiming,
        executionQuality,
      });

      // --- Digest Comparison (vs previous digest from DB) ---
      let comparison = undefined;
      try {
        const prevDigest = await db.collection('weekly_digests')
          .find({}, { projection: { _id: 0 } })
          .sort({ generatedAt: -1 })
          .limit(1)
          .next() as WeeklyDigest | null;

        if (prevDigest) {
          const currentDigest: WeeklyDigest = {
            period: { from: periodFrom, to: periodTo },
            generatedAt: new Date().toISOString(),
            performance, timing, sources, patterns,
            edgeAttribution, decisionQuality, calibration,
            alertPerformance: alertPerf,
            executionQuality: executionQuality.totalEvaluated > 0 ? executionQuality : undefined,
            missedOpportunities: missed.topMissed,
            changes: learning.changes, lessons: learning.lessons,
            mistakes: learning.mistakes, improvements: learning.improvements,
          };
          comparison = digestComparisonService.compare(currentDigest, prevDigest);
        }
      } catch {
        // Comparison is optional — don't fail the digest
      }

      const digest: WeeklyDigest = {
        period: { from: periodFrom, to: periodTo },
        generatedAt: new Date().toISOString(),
        performance,
        timing,
        sources,
        patterns,
        edgeAttribution,
        decisionQuality,
        calibration,
        alertPerformance: alertPerf,
        executionQuality: executionQuality.totalEvaluated > 0 ? executionQuality : undefined,
        comparison,
        missedOpportunities: missed.topMissed,
        changes: learning.changes,
        lessons: learning.lessons,
        mistakes: learning.mistakes,
        improvements: learning.improvements,
      };

      // Save to MongoDB
      await db.collection('weekly_digests').insertOne({
        ...digest,
        _id: undefined,
        createdAt: new Date().toISOString(),
      });

      return digest;
    } finally {
      await client.close();
    }
  }

  /**
   * Get latest digest from MongoDB.
   */
  async getLatest(): Promise<WeeklyDigest | null> {
    const client = new MongoClient(MONGO_URL);
    try {
      await client.connect();
      const db = client.db(DB_NAME);
      const doc = await db.collection('weekly_digests')
        .find({}, { projection: { _id: 0 } })
        .sort({ generatedAt: -1 })
        .limit(1)
        .next();
      return doc as WeeklyDigest | null;
    } finally {
      await client.close();
    }
  }

  /**
   * Get digest history.
   */
  async getHistory(limit = 10): Promise<WeeklyDigest[]> {
    const client = new MongoClient(MONGO_URL);
    try {
      await client.connect();
      const db = client.db(DB_NAME);
      const docs = await db.collection('weekly_digests')
        .find({}, { projection: { _id: 0 } })
        .sort({ generatedAt: -1 })
        .limit(limit)
        .toArray();
      return docs as WeeklyDigest[];
    } finally {
      await client.close();
    }
  }

  private async fetchAlertHistory(): Promise<any[]> {
    try {
      const { alertEngineOrchestrator } = await import('../../alert-engine/services/alert-orchestrator.service.js');
      return alertEngineOrchestrator.getHistory(200);
    } catch {
      return [];
    }
  }
}

export const digestBuilderService = new DigestBuilderService();
