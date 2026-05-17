/**
 * Prediction Intel Orchestrator
 *
 * Full pipeline: events → enrichment → dedup → trust → interpret → normalize → route
 *
 * Called by the prediction pipeline to get signal intelligence for a market.
 */
import { getDb } from '../../db/mongodb.js';
import { enrichEvent } from './services/event-enrichment.service.js';
import { deduplicateEvents, clusterEvents } from './services/dedup.service.js';
import { getSourceProfile, computeTrustScore } from './services/source-trust.service.js';
import { interpretEvent } from './services/event-interpreter.service.js';
import { normalizeSignals } from './services/signal-normalizer.service.js';
import { aggregateSignals } from './services/signal-router.service.js';
import type { EnrichedEvent, InterpretedEvent } from './types/event.types.js';
import type { SignalBatch } from './types/signal.types.js';

/**
 * Get signal intelligence for a specific market.
 *
 * @param marketId - Polymarket market ID
 * @param asset - Primary asset (BTC, ETH, etc.)
 * @param entities - Entities related to this market
 * @param eventType - Market event type (price_threshold, etf_catalyst, etc.)
 * @param currentProb - Current market probability
 * @param move6h - Price move in last 6h
 * @param move24h - Price move in last 24h
 * @param volume - Market volume
 * @param repricingState - Current repricing state
 * @param hoursBack - How far back to look for events (default: 24h)
 */
export async function getMarketIntelligence(opts: {
  marketId: string;
  asset: string;
  entities: string[];
  eventType: string;
  currentProb: number;
  move6h: number;
  move24h: number;
  volume: number;
  repricingState?: string;
  hoursBack?: number;
}): Promise<SignalBatch> {
  const {
    marketId, asset, entities, eventType,
    currentProb, move6h, move24h, volume,
    repricingState, hoursBack = 48,
  } = opts;

  let db;
  try {
    db = getDb();
  } catch {
    return aggregateSignals(marketId, asset, []);
  }

  // 1. Fetch raw events from MongoDB
  const cutoff = new Date(Date.now() - hoursBack * 3600 * 1000);
  const cutoffIso = cutoff.toISOString();
  const rawDocs = await db
    .collection('notification_events')
    .find({
      $and: [
        {
          $or: [
            { asset: { $in: [asset, ...entities] } },
            { asset: { $regex: new RegExp(asset, 'i') } },
          ],
        },
        {
          $or: [
            { createdAt: { $gte: cutoff } },        // Date objects
            { createdAt: { $gte: cutoffIso } },      // ISO strings
          ],
        },
      ],
    })
    .sort({ createdAt: -1 })
    .limit(100)
    .toArray();

  if (!rawDocs.length) {
    return aggregateSignals(marketId, asset, []);
  }

  // 2. Enrich
  const enriched: EnrichedEvent[] = rawDocs.map(doc => enrichEvent(doc));

  // 3. Dedup
  const deduped = deduplicateEvents(enriched);

  // 4. Build market context
  const context = {
    marketId,
    asset,
    entities,
    eventType,
    currentProb,
    move6h,
    move24h,
    volume,
    repricingState,
  };

  // 5. Interpret each event
  const recentTexts = deduped.map(e => e.text);
  const interpreted: InterpretedEvent[] = [];

  for (const evt of deduped) {
    const source = getSourceProfile(evt.extractedSource);
    const interp = interpretEvent(evt, source, context, recentTexts);
    interpreted.push(interp);
  }

  // 6. Normalize
  const signals = normalizeSignals(interpreted);

  // 7. Aggregate into a batch
  return aggregateSignals(marketId, asset, signals);
}

/**
 * Get signal intelligence for multiple markets at once.
 */
export async function getBatchIntelligence(
  markets: Array<{
    marketId: string;
    asset: string;
    entities: string[];
    eventType: string;
    currentProb: number;
    move6h: number;
    move24h: number;
    volume: number;
    repricingState?: string;
  }>,
): Promise<Map<string, SignalBatch>> {
  const results = new Map<string, SignalBatch>();

  for (const m of markets) {
    const batch = await getMarketIntelligence(m);
    results.set(m.marketId, batch);
  }

  return results;
}

/**
 * Get recent enriched events for an asset (for debugging/UI).
 */
export async function getRecentEvents(
  asset: string,
  hoursBack: number = 24,
): Promise<EnrichedEvent[]> {
  let db;
  try {
    db = getDb();
  } catch {
    return [];
  }

  const cutoff = new Date(Date.now() - hoursBack * 3600 * 1000);
  const cutoffIso = cutoff.toISOString();
  const docs = await db
    .collection('notification_events')
    .find({
      asset,
      $or: [
        { createdAt: { $gte: cutoff } },
        { createdAt: { $gte: cutoffIso } },
      ],
    })
    .sort({ createdAt: -1 })
    .limit(50)
    .toArray();

  return docs.map(doc => enrichEvent(doc));
}
