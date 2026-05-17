/**
 * Actors List Service
 * ====================
 * 
 * PHASE 5 + P0.6.1: List top accumulators/distributors with attribution
 */

import { EntityFlowModel } from './entityFlow.model';
import { LabelsService } from '../../labels/labels.service';
import type { EntityAttributionSource } from './entityResolution.types';

type WindowKey = '24h' | '7d' | '30d';
type Direction = 'accumulation' | 'distribution';

export interface ActorListItem {
  entityId: string;
  entityName: string | null;
  entityType: string;
  tags: string[];
  // P0.6.1: Attribution fields
  attributionSource: EntityAttributionSource | null;
  attributionConfidence: number | null;
  // Flow metrics
  netUsd: number;
  dexUsd: number;
  cexUsd: number;
  bridgeUsd: number;
  trades: number;
  pricedShare: number;
}

export class ActorsListService {
  private readonly labels = new LabelsService();

  async list(params: {
    chainId: number;
    window: WindowKey;
    direction: Direction;
    limit?: number;
  }): Promise<{ ok: boolean; direction: Direction; window: WindowKey; items: ActorListItem[] }> {
    const limit = Math.min(Math.max(params.limit ?? 20, 5), 50);

    const rows = await EntityFlowModel.aggregate([
      { $match: { chainId: params.chainId, window: params.window } },
      {
        $group: {
          _id: { entityId: '$entityId', entityType: '$entityType' },
          entityName: { $first: '$entityName' },
          attributionSource: { $first: '$attributionSource' },
          attributionConfidence: { $avg: '$attributionConfidence' },
          netUsd: { $sum: '$netUsd' },
          dexUsd: { $sum: '$dexUsd' },
          cexUsd: { $sum: '$cexUsd' },
          bridgeUsd: { $sum: '$bridgeUsd' },
          trades: { $sum: '$trades' },
          pricedShare: { $avg: '$pricedShare' },
        },
      },
      {
        $sort: {
          netUsd: params.direction === 'accumulation' ? -1 : 1,
        },
      },
      { $limit: limit },
    ]);

    // Resolve labels for addresses to get tags
    const addresses = rows
      .map((r: any) => String(r._id.entityId))
      .filter((x: string) => x.startsWith('0x') && x.length === 42)
      .map((x: string) => x.toLowerCase());

    const labelMap = await this.labels.batchResolve(params.chainId, addresses);

    const items: ActorListItem[] = rows.map((r: any) => {
      const id = String(r._id.entityId).toLowerCase();
      const lbl = labelMap[id];

      return {
        entityId: r._id.entityId,
        entityName: r.entityName || lbl?.name || null,
        entityType: r._id.entityType ?? lbl?.labelType ?? 'UNKNOWN',
        tags: lbl?.tags ?? [],
        // P0.6.1: Attribution
        attributionSource: r.attributionSource || null,
        attributionConfidence: r.attributionConfidence ?? lbl?.confidence ?? null,
        // Metrics
        netUsd: r.netUsd ?? 0,
        dexUsd: r.dexUsd ?? 0,
        cexUsd: r.cexUsd ?? 0,
        bridgeUsd: r.bridgeUsd ?? 0,
        trades: r.trades ?? 0,
        pricedShare: r.pricedShare ?? 0,
      };
    });

    return {
      ok: true,
      direction: params.direction,
      window: params.window,
      items,
    };
  }
}
