/**
 * Trace Builder Service
 *
 * THE FOUNDATION OF OUTCOME LAB.
 *
 * Captures a complete snapshot of the system's reasoning at decision time.
 * Without this, everything else is garbage — you can't learn from
 * what you don't remember.
 *
 * Stores traces in MongoDB for later review when markets resolve.
 */

import { getDb } from '../../../db/mongodb.js';
import type { DecisionTrace } from '../types/outcome-lab.types.js';

class TraceBuilderService {
  private collectionName = 'decision_traces';

  /**
   * Build a trace from a case object (as returned by /api/prediction/run).
   */
  buildTrace(caseData: Record<string, any>): DecisionTrace {
    const a = caseData.analysis || {};
    const r = caseData.recommendation || {};
    const repr = caseData.repricing || {};
    const entry = caseData.entry_timing || {};
    const si = caseData.socialIntel || {};
    const pi = caseData.projectIntel || {};
    const ci = caseData.intelligence || {};
    const memo = ci.memo || {};
    const gap = ci.gap || {};
    const evStats = ci.evidenceStats || {};
    const es = caseData.executionScore || {};

    return {
      marketId: caseData.market_id,
      question: caseData.question || '',
      asset: caseData.asset || 'BTC',
      eventType: caseData.event_type || 'unknown',
      entities: caseData.entities || [],

      traceTimestamp: new Date(),
      endDate: caseData.end_date,

      fairProb: a.fair_prob ?? 0.5,
      marketProb: a.market_prob ?? 0.5,
      edge: a.net_edge ?? 0,
      confidence: a.model_confidence ?? 0,
      alignment: a.alignment_score ?? 0,

      action: r.action || 'AVOID',
      conviction: r.conviction || 'LOW',
      size: r.size || 'NONE',

      repricingState: repr.repricing_state || 'unknown',
      entryAction: entry.entry_action || 'do_not_enter',
      marketStage: caseData.market_stage || 'unknown',

      social: {
        lifecycle: si.lifecycle || null,
        echoScore: si.echoScore ?? 0,
        saturationScore: si.saturationScore ?? 0,
        originQuality: si.originQuality ?? 0,
        topOrigin: si.topOrigin || null,
      },

      project: {
        verdict: pi.verdict || null,
        valuation: pi.valuation || null,
        unlockRisk: pi.unlockRisk || null,
        tokenomics: pi.tokenomics || null,
        overallScore: pi.overallScore ?? 0,
      },

      intelligence: {
        memoAction: memo.action || null,
        mispricingType: gap.mispricingType || null,
        pricedInLevel: gap.pricedInLevel ?? 0,
        evidenceDrivers: evStats.drivers ?? 0,
        evidenceNoise: evStats.noise ?? 0,
      },

      executionQuality: es.score ? {
        score: es.score ?? 0,
        grade: es.grade ?? '',
        direction: es.direction ?? '',
        entryQuality: es.entryQuality ?? '',
        entryPosition: es.entryPosition ?? '',
        timingQuality: es.timingQuality ?? '',
        missedWindow: es.missedWindow ?? false,
        slippageLeakage: es.slippageLeakage ?? 0,
        missedMove: es.missedMove ?? 0,
        opportunityReason: es.opportunityReason ?? 'NONE',
        regime: es.regime ?? '',
        narrativePhase: es.narrative ?? '',
        lessons: es.lessons ?? [],
      } : undefined,
    };
  }

  /**
   * Save a trace to MongoDB. Upserts by marketId + date bucket.
   */
  async saveTrace(trace: DecisionTrace): Promise<void> {
    try {
      const db = getDb();
      const dateBucket = trace.traceTimestamp.toISOString().slice(0, 13); // YYYY-MM-DDTHH
      await db.collection(this.collectionName).updateOne(
        { marketId: trace.marketId, dateBucket },
        { $set: { ...trace, dateBucket, updatedAt: new Date() } },
        { upsert: true },
      );
    } catch (err: any) {
      console.error(`[TraceBuilder] Failed to save trace: ${err.message}`);
    }
  }

  /**
   * Save traces for a batch of cases.
   */
  async saveBatchTraces(cases: Record<string, any>[]): Promise<number> {
    let saved = 0;
    for (const c of cases) {
      const trace = this.buildTrace(c);
      if (trace.marketId && trace.action !== 'AVOID') {
        await this.saveTrace(trace);
        saved++;
      }
    }
    return saved;
  }

  /**
   * Get the latest trace for a market.
   */
  async getLatestTrace(marketId: string): Promise<DecisionTrace | null> {
    try {
      const db = getDb();
      const doc = await db.collection(this.collectionName)
        .findOne({ marketId }, { sort: { traceTimestamp: -1 }, projection: { _id: 0 } });
      return doc as DecisionTrace | null;
    } catch {
      return null;
    }
  }

  /**
   * Get all traces for a market (history).
   */
  async getTraceHistory(marketId: string): Promise<DecisionTrace[]> {
    try {
      const db = getDb();
      const docs = await db.collection(this.collectionName)
        .find({ marketId }, { projection: { _id: 0 } })
        .sort({ traceTimestamp: 1 })
        .limit(100)
        .toArray();
      return docs as DecisionTrace[];
    } catch {
      return [];
    }
  }

  /**
   * Get trace stats.
   */
  async getStats(): Promise<{ totalTraces: number; uniqueMarkets: number; latestTrace: Date | null }> {
    try {
      const db = getDb();
      const col = db.collection(this.collectionName);
      const totalTraces = await col.countDocuments();
      const uniqueMarkets = (await col.distinct('marketId')).length;
      const latest = await col.findOne({}, { sort: { traceTimestamp: -1 }, projection: { _id: 0, traceTimestamp: 1 } });
      return {
        totalTraces,
        uniqueMarkets,
        latestTrace: latest?.traceTimestamp || null,
      };
    } catch {
      return { totalTraces: 0, uniqueMarkets: 0, latestTrace: null };
    }
  }
}

export const traceBuilderService = new TraceBuilderService();
