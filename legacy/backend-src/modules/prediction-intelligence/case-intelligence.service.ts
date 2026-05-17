/**
 * Case Builder — Main Orchestrator for Case Intelligence Engine
 *
 * Pipeline: Event Understanding → Evidence Collection → Classification →
 * Weighting → Thesis → Market Gap → Risk Map → Decision Memo
 */
import { getDb } from '../../db/mongodb.js';
import { analyzeEvent } from './services/event-understanding.service.js';
import { collectEvidence } from './services/evidence-collector.service.js';
import { classifyEvidence } from './services/evidence-classifier.service.js';
import { weightEvidence } from './services/evidence-weighting.service.js';
import { buildThesis } from './services/thesis-engine.service.js';
import { analyzeMarketGap } from './services/market-gap.service.js';
import { mapRisks } from './services/risk-mapper.service.js';
import { composeMemo } from './services/decision-memo.service.js';
import type { CaseInput, DecisionMemo, EventUnderstanding, EvidencePack, ThesisResult, MarketGap, RiskMap } from './types/case.types.js';

export type CaseIntelligenceResult = {
  memo: DecisionMemo;
  event: EventUnderstanding;
  evidenceStats: {
    total: number;
    primary: number;
    secondary: number;
    narrative: number;
    echo: number;
    contradictory: number;
    onchain: number;
    drivers: number;
    confirmations: number;
    noise: number;
  };
  thesis: ThesisResult;
  gap: MarketGap;
  risks: RiskMap;
};

// Load signals from MongoDB for a given market/asset
async function loadSignals(marketId: string, asset: string): Promise<CaseInput['signals']> {
  const signals: CaseInput['signals'] = { sentiment: [], onchain: [], news: [], twitter: [] };

  try {
    const db = getDb();
    const since = new Date(Date.now() - 48 * 3600 * 1000); // last 48h

    // Notification events (news/twitter proxy)
    const events = await db.collection('notification_events')
      .find({
        $or: [
          { assets: asset },
          { entities: { $in: [asset] } },
          { text: { $regex: asset, $options: 'i' } },
        ],
        created_at: { $gte: since.toISOString() },
      })
      .sort({ created_at: -1 })
      .limit(30)
      .project({ _id: 0 })
      .toArray();

    for (const ev of events) {
      const src = (ev.source || '').toLowerCase();
      if (src.includes('twitter') || src.includes('x.com')) signals.twitter.push(ev);
      else signals.news.push(ev);
    }

    // Sentiment events
    const sentiments = await db.collection('sentiment_events')
      .find({ asset, timestamp: { $gte: since.toISOString() } })
      .sort({ timestamp: -1 })
      .limit(10)
      .project({ _id: 0 })
      .toArray();
    signals.sentiment = sentiments;

    // Onchain snapshots
    const onchain = await db.collection('onchain_v2_snapshots')
      .find({ asset, timestamp: { $gte: since.toISOString() } })
      .sort({ timestamp: -1 })
      .limit(5)
      .project({ _id: 0 })
      .toArray();
    signals.onchain = onchain;
  } catch {
    // silent — signals may not be available
  }

  return signals;
}

export async function buildCase(rawCase: any): Promise<CaseIntelligenceResult> {
  // Build CaseInput from raw Python case data
  const input: CaseInput = {
    marketId: rawCase.market_id || rawCase.marketId,
    question: rawCase.question || '',
    decoded: {
      eventType: rawCase.event_type || rawCase.eventType || 'generic_crypto',
      entities: rawCase.entities || [],
      deadline: rawCase.end_date || rawCase.endDate,
      asset: rawCase.asset || 'BTC',
      comparator: rawCase.comparator,
      threshold: rawCase.threshold,
    },
    marketState: {
      impliedProb: rawCase.current_prob ?? rawCase.implied_prob ?? 0.5,
      liquidity: rawCase.liquidity ?? 0,
      volume24h: rawCase.volume_24h ?? rawCase.volume ?? 0,
      spread: rawCase.spread ?? 2,
      move1h: rawCase.move_1h ?? rawCase.pricing_state?.move_1h,
      move6h: rawCase.move_6h ?? rawCase.pricing_state?.move_6h,
    },
    signals: rawCase._signals || { sentiment: [], onchain: [], news: [], twitter: [] },
    context: rawCase._context || {},
  };

  // If signals not pre-loaded, load from DB
  if (!rawCase._signals) {
    input.signals = await loadSignals(input.marketId, input.decoded.asset);
  }

  // 1. Event Understanding
  const event = analyzeEvent(input);

  // 2. Evidence Collection
  const evidence = collectEvidence(input);

  // 3. Classification
  const classified = classifyEvidence(evidence);

  // 4. Weighting
  const allItems = [...classified.highSignal, ...classified.mediumSignal, ...classified.lowSignal, ...classified.noise];
  const weighted = weightEvidence(allItems, event, input);

  // 5. Thesis Engine
  const thesis = buildThesis(weighted, event, input);

  // 6. Market Gap Analysis
  const gap = analyzeMarketGap(weighted, input);

  // 7. Risk Mapping
  const risks = mapRisks(weighted, event, input);

  // 8. Decision Memo
  const memo = composeMemo(event, thesis, gap, risks, weighted, input);

  // Evidence stats
  const evidenceStats = {
    total: allItems.length,
    primary: evidence.primary.length,
    secondary: evidence.secondary.length,
    narrative: evidence.narrative.length,
    echo: evidence.echo.length,
    contradictory: evidence.contradictory.length,
    onchain: evidence.onchain.length,
    drivers: weighted.filter(w => w.role === 'driver').length,
    confirmations: weighted.filter(w => w.role === 'confirmation').length,
    noise: weighted.filter(w => w.role === 'noise').length,
  };

  return { memo, event, evidenceStats, thesis, gap, risks };
}

export async function buildCaseBatch(rawCases: any[]): Promise<Record<string, CaseIntelligenceResult>> {
  const results: Record<string, CaseIntelligenceResult> = {};
  for (const raw of rawCases) {
    const id = raw.market_id || raw.marketId;
    try {
      results[id] = await buildCase(raw);
    } catch {
      // skip failed cases
    }
  }
  return results;
}
