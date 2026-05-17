/**
 * Entity Buckets Service
 * =======================
 * 
 * P2.1: Compute aggregates by entity type from EntityFlowModel
 */

import { EntityFlowModel } from './entityFlow.model';
import { EntityBucketsModel } from './entityBuckets.model';

type WindowKey = '24h' | '7d' | '30d';

const ENTITY_TYPES = ['EXCHANGE', 'BRIDGE', 'PROTOCOL', 'FUND', 'WHALE', 'SMART_MONEY', 'OTHER'] as const;
type EntityType = typeof ENTITY_TYPES[number];

function normalizeType(t: any): EntityType {
  const s = String(t || 'OTHER').toUpperCase();
  if (ENTITY_TYPES.includes(s as EntityType)) return s as EntityType;
  if (s === 'CEX') return 'EXCHANGE';
  if (s === 'UNKNOWN') return 'OTHER';
  return 'OTHER';
}

export class EntityBucketsService {
  /**
   * Compute latest entity buckets from EntityFlowModel
   */
  async computeLatest(
    chainId: number,
    window: WindowKey
  ): Promise<{
    ok: boolean;
    chainId: number;
    window: WindowKey;
    bucketTs: Date | null;
    doc: any;
    reason?: string;
  }> {
    // Find latest bucket timestamp
    const latest = await EntityFlowModel.findOne({ chainId, window })
      .sort({ bucketTs: -1 })
      .select('bucketTs')
      .lean();

    const bucketTs = latest?.bucketTs;
    if (!bucketTs) {
      return { ok: true, chainId, window, bucketTs: null, doc: null, reason: 'NO_ENTITY_FLOW_DATA' };
    }

    // Get all flows for this bucket
    const flows = await EntityFlowModel.find({ chainId, window, bucketTs })
      .select('entityId entityType entityLabel netUsd dexUsd cexUsd bridgeUsd trades pricedShare')
      .lean();

    if (!flows.length) {
      return { ok: true, chainId, window, bucketTs, doc: null, reason: 'EMPTY_BUCKET' };
    }

    // Initialize buckets by type
    const byType: Record<EntityType, { netUsd: number; trades: number }> = {} as any;
    for (const t of ENTITY_TYPES) {
      byType[t] = { netUsd: 0, trades: 0 };
    }

    let totalNetUsd = 0;
    let totalTrades = 0;
    let pricedSum = 0;
    let pricedCount = 0;

    // Accumulate by entity, then group by type
    const entityAgg = new Map<string, { entityId: string; entityLabel: string | null; entityType: string; netUsd: number; trades: number }>();

    for (const f of flows) {
      const entityId = f.entityId || 'unknown';
      const type = normalizeType(f.entityType);
      const net = Number(f.netUsd || 0);
      const trades = Number(f.trades || 0);

      // Type aggregation
      byType[type].netUsd += net;
      byType[type].trades += trades;

      // Entity aggregation
      if (!entityAgg.has(entityId)) {
        entityAgg.set(entityId, {
          entityId,
          entityLabel: f.entityLabel || null,
          entityType: type,
          netUsd: 0,
          trades: 0,
        });
      }
      const entity = entityAgg.get(entityId)!;
      entity.netUsd += net;
      entity.trades += trades;

      // Totals
      totalNetUsd += net;
      totalTrades += trades;

      const ps = Number(f.pricedShare ?? NaN);
      if (!Number.isNaN(ps)) {
        pricedSum += ps;
        pricedCount += 1;
      }
    }

    // Top accumulators and distributors
    const entities = Array.from(entityAgg.values());

    const topAccumulating = entities
      .filter(e => e.netUsd > 0)
      .sort((a, b) => b.netUsd - a.netUsd)
      .slice(0, 12)
      .map(e => ({
        entityId: e.entityId,
        entityLabel: e.entityLabel,
        entityType: e.entityType,
        netUsd: e.netUsd,
        trades: e.trades,
      }));

    const topDistributing = entities
      .filter(e => e.netUsd < 0)
      .sort((a, b) => a.netUsd - b.netUsd)
      .slice(0, 12)
      .map(e => ({
        entityId: e.entityId,
        entityLabel: e.entityLabel,
        entityType: e.entityType,
        netUsd: e.netUsd,
        trades: e.trades,
      }));

    const doc = {
      chainId,
      window,
      bucketTs,
      totalNetUsd,
      totalTrades,
      pricedShareAvg: pricedCount > 0 ? pricedSum / pricedCount : 0,
      byType,
      topAccumulating,
      topDistributing,
    };

    // Upsert
    await EntityBucketsModel.updateOne(
      { chainId, window, bucketTs },
      { $set: doc },
      { upsert: true }
    );

    return { ok: true, chainId, window, bucketTs, doc };
  }

  /**
   * Get latest computed buckets (read-only)
   */
  async getLatest(chainId: number, window: WindowKey) {
    const doc = await EntityBucketsModel.findOne({ chainId, window })
      .sort({ bucketTs: -1 })
      .lean();

    if (!doc) {
      return { ok: true, chainId, window, data: null, reason: 'NO_DATA' };
    }

    return { ok: true, chainId, window, data: doc };
  }
}
