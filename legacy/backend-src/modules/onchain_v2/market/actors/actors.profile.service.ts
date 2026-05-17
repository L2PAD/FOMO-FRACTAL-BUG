/**
 * Actors Profile Service
 * =======================
 * 
 * PHASE 5.2 + P0.6.1: Entity profile with series, token impact, and attribution
 */

import { LabelsService } from '../../labels/labels.service';
import { EntityFlowModel } from './entityFlow.model';
import type { EntityAttributionSource } from './entityResolution.types';

type WindowKey = '24h' | '7d' | '30d';

export interface ActorProfile {
  ok: boolean;
  chainId: number;
  window: WindowKey;
  entityId: string;
  entityName: string | null;
  entityType: string;
  // P0.6.1: Attribution
  attribution: {
    source: EntityAttributionSource;
    confidence: number;
    evidence: any[];
  } | null;
  // Label (if available)
  label: {
    name: string;
    labelType: string;
    entityId: string;
    tags: string[];
    confidence: number;
  } | null;
  summary: {
    netUsd: number;
    dexUsd: number;
    cexUsd: number;
    bridgeUsd: number;
    trades: number;
    pricedShare: number;
    buckets: number;
    lastBucketTs: string | null;
  };
  miniSeries: Array<{
    bucketTs: string;
    netUsd: number;
    trades: number;
    pricedShare: number;
  }>;
  tokenImpact: Array<{
    tokenAddress: string;
    tokenSymbol: string;
    netUsd: number;
    trades: number;
  }>;
}

export class ActorsProfileService {
  private readonly labels = new LabelsService();

  async profile(params: { chainId: number; window: WindowKey; entityId: string }): Promise<ActorProfile> {
    const { chainId, window, entityId } = params;

    // 1) Resolve label if address
    const isAddr = entityId.toLowerCase().startsWith('0x') && entityId.length === 42;
    const label = isAddr ? await this.labels.resolve(chainId, entityId) : null;

    // 2) Aggregate summary with attribution
    const agg = await EntityFlowModel.aggregate([
      { $match: { chainId, window, entityId } },
      {
        $group: {
          _id: '$entityId',
          entityName: { $first: '$entityName' },
          entityType: { $first: '$entityType' },
          attributionSource: { $first: '$attributionSource' },
          attributionConfidence: { $avg: '$attributionConfidence' },
          attributionEvidence: { $first: '$attributionEvidence' },
          netUsd: { $sum: '$netUsd' },
          dexUsd: { $sum: '$dexUsd' },
          cexUsd: { $sum: '$cexUsd' },
          bridgeUsd: { $sum: '$bridgeUsd' },
          trades: { $sum: '$trades' },
          pricedShare: { $avg: '$pricedShare' },
          buckets: { $sum: 1 },
          lastBucketTs: { $max: '$bucketTs' },
        },
      },
      { $limit: 1 },
    ]);

    const summary = agg?.[0] ?? {
      entityName: null,
      entityType: 'UNKNOWN',
      attributionSource: null,
      attributionConfidence: null,
      attributionEvidence: [],
      netUsd: 0,
      dexUsd: 0,
      cexUsd: 0,
      bridgeUsd: 0,
      trades: 0,
      pricedShare: 0,
      buckets: 0,
      lastBucketTs: null,
    };

    // 3) Mini series (last 120 buckets)
    const seriesRaw = await EntityFlowModel.find({ chainId, window, entityId })
      .select('bucketTs netUsd trades pricedShare')
      .sort({ bucketTs: -1 })
      .limit(120)
      .lean();

    const miniSeries = (seriesRaw || []).reverse().map((p: any) => ({
      bucketTs: p.bucketTs?.toISOString?.() ?? String(p.bucketTs),
      netUsd: p.netUsd ?? 0,
      trades: p.trades ?? 0,
      pricedShare: p.pricedShare ?? 0,
    }));

    // 4) Token impact from tokenBreakdown
    const tokenImpact = await this.computeTokenImpact(chainId, window, entityId);

    // Build attribution object
    const attribution = summary.attributionSource
      ? {
          source: summary.attributionSource as EntityAttributionSource,
          confidence: summary.attributionConfidence ?? 0,
          evidence: summary.attributionEvidence ?? [],
        }
      : null;

    return {
      ok: true,
      chainId,
      window,
      entityId,
      entityName: summary.entityName || label?.name || null,
      entityType: summary.entityType || label?.labelType || 'UNKNOWN',
      attribution,
      label: label
        ? {
            name: label.name,
            labelType: label.labelType,
            entityId: label.entityId,
            tags: label.tags,
            confidence: label.confidence,
          }
        : null,
      summary: {
        netUsd: summary.netUsd ?? 0,
        dexUsd: summary.dexUsd ?? 0,
        cexUsd: summary.cexUsd ?? 0,
        bridgeUsd: summary.bridgeUsd ?? 0,
        trades: summary.trades ?? 0,
        pricedShare: summary.pricedShare ?? 0,
        buckets: summary.buckets ?? 0,
        lastBucketTs: summary.lastBucketTs?.toISOString?.() ?? null,
      },
      miniSeries,
      tokenImpact,
    };
  }

  private async computeTokenImpact(chainId: number, window: WindowKey, entityId: string) {
    // Aggregate from tokenBreakdown field
    const agg = await EntityFlowModel.aggregate([
      { $match: { chainId, window, entityId } },
      { $unwind: { path: '$tokenBreakdown', preserveNullAndEmptyArrays: false } },
      {
        $group: {
          _id: {
            tokenAddress: '$tokenBreakdown.tokenAddress',
            tokenSymbol: '$tokenBreakdown.tokenSymbol',
          },
          netUsd: { $sum: '$tokenBreakdown.netUsd' },
          trades: { $sum: '$tokenBreakdown.trades' },
        },
      },
      {
        $project: {
          tokenAddress: '$_id.tokenAddress',
          tokenSymbol: '$_id.tokenSymbol',
          netUsd: 1,
          trades: 1,
          absNet: { $abs: '$netUsd' },
        },
      },
      { $sort: { absNet: -1 } },
      { $limit: 20 },
    ]);

    return (agg || []).map((t: any) => ({
      tokenAddress: t.tokenAddress || '',
      tokenSymbol: t.tokenSymbol || 'UNKNOWN',
      netUsd: t.netUsd ?? 0,
      trades: t.trades ?? 0,
    }));
  }
}
