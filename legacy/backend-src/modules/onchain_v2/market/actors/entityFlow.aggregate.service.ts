/**
 * Entity Flow Aggregation Service
 * =================================
 * 
 * P0.5 + P0.6.1: Aggregates TokenFlow events into EntityFlowModel
 * Uses Unified Entity Resolution (v2 labels + v1 inference)
 * 
 * Layers:
 * 1. LABEL_V2 — Institutional seed (Binance, Coinbase, etc.)
 * 2. ENTITY_V1 — v1 entities address membership
 * 3. ACTOR_CLUSTER_V1 — v1 actor clustering (hypothesis)
 * 4. BEHAVIORAL_FALLBACK — Heuristic inference
 */

import { EntityFlowModel } from './entityFlow.model';
import { TokenFlowModel } from '../flow/flow.model';
import { LabelsService } from '../../labels/labels.service';
import { EntityResolverService } from './entityResolver.service';
import type { ResolvedEntity, EntityAttributionSource } from './entityResolution.types';

type WindowKey = '24h' | '7d' | '30d';

const WINDOWS: { window: WindowKey; seconds: number }[] = [
  { window: '24h', seconds: 24 * 60 * 60 },
  { window: '7d', seconds: 7 * 24 * 60 * 60 },
  { window: '30d', seconds: 30 * 24 * 60 * 60 },
];

// Bucket size: 1 hour
const BUCKET_SECONDS = 60 * 60;

interface TokenData {
  tokenAddress: string;
  tokenSymbol: string;
  netUsd: number;
  trades: number;
}

interface EntityBucket {
  chainId: number;
  window: WindowKey;
  bucketTs: Date;
  entityId: string;
  entityName: string;
  entityType: string;
  attributionSource: EntityAttributionSource;
  attributionConfidence: number;
  attributionEvidence: any[];
  dexUsd: number;
  cexUsd: number;
  bridgeUsd: number;
  trades: number;
  pricedCount: number;
  tokens: Map<string, TokenData>;
}

export class EntityFlowAggregateService {
  private readonly resolver: EntityResolverService;

  constructor(private readonly labels: LabelsService) {
    // Initialize unified resolver with v1 inference enabled
    this.resolver = new EntityResolverService(labels, { enableV1: true });
  }

  /**
   * Compute entity flows for a given chain and window
   */
  async compute(params: {
    chainId: number;
    window: WindowKey;
    now?: Date;
    maxBuckets?: number;
  }): Promise<{
    ok: boolean;
    source: string;
    chainId: number;
    window: WindowKey;
    buckets: number;
    upserts: number;
    reason?: string;
    stats?: {
      labelV2: number;
      entityV1: number;
      actorClusterV1: number;
      behavioralFallback: number;
    };
  }> {
    const { chainId, window } = params;
    const now = params.now ?? new Date();
    const maxBuckets = Math.min(Math.max(params.maxBuckets ?? 24, 1), 168);

    const cfg = WINDOWS.find(w => w.window === window);
    if (!cfg) return { ok: false, source: 'NONE', chainId, window, buckets: 0, upserts: 0, reason: 'INVALID_WINDOW' };

    const nowTs = Math.floor(now.getTime() / 1000);
    const fromTs = nowTs - cfg.seconds;

    // Get recent flows from TokenFlowModel
    const flows = await TokenFlowModel.find({
      chainId,
      blockTime: { $gte: fromTs },
    })
      .select('tokenAddress tokenSymbol side usdVolume source counterparty isWhale blockTime')
      .sort({ blockTime: -1 })
      .limit(50000)
      .lean();

    if (!flows.length) {
      return { ok: true, source: 'TOKEN_FLOW', chainId, window, buckets: 0, upserts: 0, reason: 'NO_FLOWS' };
    }

    // Batch resolve all counterparties via unified resolver
    const counterparties = [...new Set(flows.map(f => f.counterparty).filter(Boolean))] as string[];
    const resolvedMap = await this.resolver.batchResolve({
      chainId,
      counterparties,
    });

    // Stats tracking
    const stats = {
      labelV2: 0,
      entityV1: 0,
      actorClusterV1: 0,
      behavioralFallback: 0,
    };

    // Group by bucket + entity (NOT per token - tokens go to breakdown)
    const accum = new Map<string, EntityBucket>();

    for (const flow of flows) {
      const bucketTs = Math.floor(flow.blockTime / BUCKET_SECONDS) * BUCKET_SECONDS;
      const bucketDate = new Date(bucketTs * 1000);

      const counterparty = flow.counterparty?.toLowerCase();
      
      // Use unified resolver result or fallback
      let resolved: ResolvedEntity;
      if (counterparty && resolvedMap.has(counterparty)) {
        resolved = resolvedMap.get(counterparty)!;
      } else {
        // Inline fallback for flows without counterparty
        resolved = this.inlineFallback(flow);
      }

      // Track stats
      switch (resolved.source) {
        case 'LABEL_V2': stats.labelV2++; break;
        case 'ENTITY_V1': stats.entityV1++; break;
        case 'ACTOR_CLUSTER_V1': stats.actorClusterV1++; break;
        case 'BEHAVIORAL_FALLBACK': stats.behavioralFallback++; break;
      }

      const tokenAddress = flow.tokenAddress.toLowerCase();
      const tokenSymbol = flow.tokenSymbol || 'UNKNOWN';
      
      // Key is entity+window+bucket (NOT per token)
      const key = `${window}:${bucketTs}:${resolved.entityId}`;

      if (!accum.has(key)) {
        accum.set(key, {
          chainId,
          window,
          bucketTs: bucketDate,
          entityId: resolved.entityId,
          entityName: resolved.entityName,
          entityType: resolved.entityType,
          attributionSource: resolved.source,
          attributionConfidence: resolved.confidence,
          attributionEvidence: resolved.evidence || [],
          dexUsd: 0,
          cexUsd: 0,
          bridgeUsd: 0,
          trades: 0,
          pricedCount: 0,
          tokens: new Map(),
        });
      }

      const bucket = accum.get(key)!;

      // Calculate signed USD based on side
      const signedUsd = flow.side === 'BUY' ? flow.usdVolume : -flow.usdVolume;

      // Accumulate by source
      if (flow.source === 'dex') {
        bucket.dexUsd += signedUsd;
      } else if (flow.source === 'cex') {
        bucket.cexUsd += signedUsd;
      } else if (flow.source === 'bridge') {
        bucket.bridgeUsd += signedUsd;
      }

      bucket.trades += 1;
      if (flow.usdVolume > 0) bucket.pricedCount += 1;

      // Token breakdown
      if (!bucket.tokens.has(tokenAddress)) {
        bucket.tokens.set(tokenAddress, {
          tokenAddress,
          tokenSymbol,
          netUsd: 0,
          trades: 0,
        });
      }
      const tokenData = bucket.tokens.get(tokenAddress)!;
      tokenData.netUsd += signedUsd;
      tokenData.trades += 1;
    }

    // Upsert all buckets
    let upserts = 0;
    for (const bucket of accum.values()) {
      const netUsd = bucket.dexUsd + bucket.cexUsd + bucket.bridgeUsd;
      const pricedShare = bucket.trades > 0 ? bucket.pricedCount / bucket.trades : 0;

      // Convert tokens map to array
      const tokenBreakdown = Array.from(bucket.tokens.values())
        .sort((a, b) => Math.abs(b.netUsd) - Math.abs(a.netUsd))
        .slice(0, 20); // Top 20 tokens

      const filter = {
        chainId: bucket.chainId,
        window: bucket.window,
        bucketTs: bucket.bucketTs,
        entityId: bucket.entityId,
      };

      const update = {
        $set: {
          entityName: bucket.entityName,
          entityType: bucket.entityType,
          attributionSource: bucket.attributionSource,
          attributionConfidence: bucket.attributionConfidence,
          attributionEvidence: bucket.attributionEvidence,
          netUsd,
          dexUsd: bucket.dexUsd,
          cexUsd: bucket.cexUsd,
          bridgeUsd: bucket.bridgeUsd,
          trades: bucket.trades,
          pricedShare,
          tokenBreakdown,
        },
      };

      await EntityFlowModel.updateOne(filter, update, { upsert: true });
      upserts += 1;
    }

    return {
      ok: true,
      source: 'TOKEN_FLOW',
      chainId,
      window,
      buckets: accum.size,
      upserts,
      stats,
    };
  }

  /**
   * Inline fallback for flows without counterparty
   */
  private inlineFallback(flow: any): ResolvedEntity {
    if (flow.isWhale) {
      return {
        entityId: 'whale:unknown',
        entityName: 'Whale (unknown)',
        entityType: 'whale',
        confidence: 0.35,
        source: 'BEHAVIORAL_FALLBACK',
        evidence: [{ kind: 'heuristic', value: 'isWhale=true' }],
      };
    }
    if (flow.source === 'cex') {
      return {
        entityId: 'cex:unknown',
        entityName: 'CEX (unknown)',
        entityType: 'exchange',
        confidence: 0.35,
        source: 'BEHAVIORAL_FALLBACK',
        evidence: [{ kind: 'heuristic', value: 'source=cex' }],
      };
    }
    if (flow.source === 'bridge') {
      return {
        entityId: 'bridge:unknown',
        entityName: 'Bridge (unknown)',
        entityType: 'bridge',
        confidence: 0.35,
        source: 'BEHAVIORAL_FALLBACK',
        evidence: [{ kind: 'heuristic', value: 'source=bridge' }],
      };
    }
    if (flow.source === 'dex') {
      return {
        entityId: 'dex:market',
        entityName: 'DEX market',
        entityType: 'dex',
        confidence: 0.25,
        source: 'BEHAVIORAL_FALLBACK',
        evidence: [{ kind: 'heuristic', value: 'source=dex' }],
      };
    }
    return {
      entityId: 'unknown:address',
      entityName: 'Unknown',
      entityType: 'unknown',
      confidence: 0.15,
      source: 'BEHAVIORAL_FALLBACK',
      evidence: [{ kind: 'heuristic', value: 'fallback' }],
    };
  }
}
