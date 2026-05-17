/**
 * Source Attribution Service
 *
 * The second most important layer.
 *
 * Determines which information sources were helpful vs harmful.
 * Transforms "CoinTelegraph = 58%" into:
 *   "CoinTelegraph → late noise, poor origin"
 *   "SEC filing → early signal, high impact"
 */

import type { SourceAttribution, DecisionTrace, ResolvedMarket } from '../types/outcome-lab.types.js';
import { getDb } from '../../../db/mongodb.js';

class SourceAttributionService {
  /**
   * Attribute sources for a resolved market based on the event feed data.
   */
  async attribute(
    trace: DecisionTrace,
    resolved: ResolvedMarket,
  ): Promise<SourceAttribution[]> {
    const attributions: SourceAttribution[] = [];

    try {
      const db = getDb();

      // Find events that were about this market's entities/asset around trace time
      const entities = [trace.asset, ...trace.entities].map(e => e.toLowerCase());
      const lookbackMs = 72 * 3600 * 1000; // 72h before trace
      const since = new Date(new Date(trace.traceTimestamp).getTime() - lookbackMs);

      const events = await db.collection('notification_events')
        .find({
          $or: [
            { 'data.symbol': { $in: entities.map(e => e.toUpperCase()) } },
            { title: { $regex: entities.join('|'), $options: 'i' } },
          ],
          created_at: { $gte: since.toISOString() },
        }, { projection: { _id: 0 } })
        .sort({ created_at: 1 })
        .limit(50)
        .toArray();

      const outcomeYes = resolved.outcome === 'YES';
      const resolvedTime = new Date(resolved.resolvedAt).getTime();

      // Group by source
      const sourceEvents = new Map<string, any[]>();
      for (const e of events) {
        const src = e.source || 'unknown';
        if (!sourceEvents.has(src)) sourceEvents.set(src, []);
        sourceEvents.get(src)!.push(e);
      }

      for (const [source, srcEvents] of sourceEvents) {
        const earliest = srcEvents[0];
        const eventTime = new Date(earliest.created_at || earliest.timestamp).getTime();
        const traceTime = new Date(trace.traceTimestamp).getTime();

        // Timeliness
        const hoursBeforeTrace = (traceTime - eventTime) / 3600000;
        const hoursBeforeResolution = (resolvedTime - eventTime) / 3600000;
        const timeliness = hoursBeforeTrace > 24 ? 'early'
          : hoursBeforeTrace > 6 ? 'on_time'
          : hoursBeforeTrace > 0 ? 'late'
          : 'after_the_fact';

        // Was this source's signal in the correct direction?
        const title = (earliest.title || '').toLowerCase();
        const bullish = /bull|surge|rally|approval|breakout|growth|positive|launch/.test(title);
        const bearish = /bear|crash|hack|dump|ban|lawsuit|fraud|reject/.test(title);
        const signalCorrect = (bullish && outcomeYes) || (bearish && !outcomeYes);

        // Lead quality
        const leadQuality = timeliness === 'early' && signalCorrect ? 'HIGH' as const
          : timeliness === 'on_time' && signalCorrect ? 'MEDIUM' as const
          : timeliness === 'late' || !signalCorrect ? 'LOW' as const
          : 'NOISE' as const;

        // Impact score
        let impactScore = 0.3;
        if (leadQuality === 'HIGH') impactScore = 0.85;
        else if (leadQuality === 'MEDIUM') impactScore = 0.60;
        else if (leadQuality === 'LOW') impactScore = 0.25;
        else impactScore = 0.10;

        // Lesson
        let lesson = '';
        if (leadQuality === 'HIGH') {
          lesson = `Early signal (${Math.round(hoursBeforeResolution)}h before resolution) — reliable lead`;
        } else if (leadQuality === 'MEDIUM') {
          lesson = 'Confirmatory signal — useful but not first mover';
        } else if (timeliness === 'late' && signalCorrect) {
          lesson = 'Late but correct — confirmation only, no trading edge';
        } else if (!signalCorrect) {
          lesson = 'Misleading signal — direction was wrong';
        } else {
          lesson = 'Noise — no actionable value';
        }

        attributions.push({
          source,
          sourceType: earliest.type || 'news',
          helpful: signalCorrect && timeliness !== 'after_the_fact',
          leadQuality,
          impactScore: Math.round(impactScore * 100) / 100,
          timeliness,
          lesson,
        });
      }
    } catch (err: any) {
      console.error(`[SourceAttribution] Error: ${err.message}`);
    }

    // Sort by impact descending
    attributions.sort((a, b) => b.impactScore - a.impactScore);

    // If no real attributions, add a synthetic one based on trace
    if (attributions.length === 0) {
      attributions.push({
        source: 'system_model',
        sourceType: 'internal',
        helpful: trace.edge > 0 === (resolved.outcome === 'YES'),
        leadQuality: 'MEDIUM',
        impactScore: 0.5,
        timeliness: 'on_time',
        lesson: 'No external source data — relied on internal model signals only',
      });
    }

    return attributions.slice(0, 10);
  }
}

export const sourceAttributionService = new SourceAttributionService();
