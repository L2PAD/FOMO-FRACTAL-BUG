/**
 * ActorScore Aggregate Service — Edge Score from EntityFlowModel
 * ===============================================================
 * 
 * P0.9: Computes structural Edge Score (0-100) per entity.
 * 
 * Formula:
 *   edgeScore = 100 * (0.45*coverage + 0.35*centrality + 0.20*activity)
 * 
 * Where:
 *   coverage   = entity's abs USD volume / total market abs USD volume
 *   centrality = tanh(tokensTouched / 20) — proxy for graph centrality
 *   activity   = tanh(trades/500 + tokensTouched/25)
 */

import { EntityFlowModel } from "./entityFlow.model";
import { ActorScoreModel } from "./actorScore.model";

type WindowKey = "24h" | "7d" | "30d";

export class ActorScoreAggregateService {
  async computeLatest(params: { chainId: number; window: WindowKey }) {
    const { chainId, window } = params;

    const last = await EntityFlowModel.findOne({ chainId, window })
      .sort({ bucketTs: -1 })
      .select("bucketTs")
      .lean();

    const bucketTs = last?.bucketTs;
    if (!bucketTs) return { ok: true, reason: "NO_ENTITYFLOW", n: 0 };

    // Market totals for coverage normalization
    const totals = await EntityFlowModel.aggregate([
      { $match: { chainId, window, bucketTs } },
      {
        $group: {
          _id: null,
          totalAbsUsd: { $sum: { $abs: "$netUsd" } },
          totalTrades: { $sum: "$trades" },
        },
      },
    ]);
    const totalAbsUsd = totals?.[0]?.totalAbsUsd || 1;

    // Per-entity aggregation
    const rows = await EntityFlowModel.aggregate([
      { $match: { chainId, window, bucketTs } },
      {
        $group: {
          _id: "$entityId",
          entityName: { $first: "$entityName" },
          entityType: { $first: "$entityType" },
          attributionSource: { $first: "$attributionSource" },
          attributionConfidence: { $first: "$attributionConfidence" },
          tokensTouchedSet: { $addToSet: "$tokenAddress" },
          trades: { $sum: "$trades" },
          netAbsUsd: { $sum: { $abs: "$netUsd" } },
        },
      },
      {
        $project: {
          entityId: "$_id",
          entityName: 1,
          entityType: 1,
          attributionSource: 1,
          attributionConfidence: 1,
          tokensTouched: { $size: "$tokensTouchedSet" },
          trades: 1,
          netAbsUsd: 1,
        },
      },
    ]);

    // Compute Edge Scores
    const scored = rows.map((r: any) => {
      const coverage = clamp01((r.netAbsUsd || 0) / totalAbsUsd);
      const activity = clamp01(Math.tanh(((r.trades || 0) / 500) + ((r.tokensTouched || 0) / 25)));
      const centrality = clamp01(Math.tanh((r.tokensTouched || 0) / 20));

      const edgeScore = Math.round(
        100 * (0.45 * coverage + 0.35 * centrality + 0.20 * activity)
      );

      return {
        chainId,
        window,
        bucketTs,
        entityId: r.entityId,
        entityName: r.entityName ?? null,
        entityType: r.entityType ?? null,
        attributionSource: r.attributionSource ?? "BEHAVIORAL_FALLBACK",
        attributionConfidence: Number(r.attributionConfidence ?? 0),
        edgeScore,
        coverage,
        activityScore: activity,
        centralityScore: centrality,
        tokensTouched: r.tokensTouched ?? 0,
        trades: r.trades ?? 0,
        netAbsUsd: r.netAbsUsd ?? 0,
      };
    });

    // Bulk upsert
    if (scored.length > 0) {
      await Promise.all(
        scored.map((s: any) =>
          ActorScoreModel.updateOne(
            { chainId, window, bucketTs, entityId: s.entityId },
            { $set: s },
            { upsert: true }
          )
        )
      );
    }

    console.log(`[ActorScore] Computed ${scored.length} scores for chainId=${chainId} window=${window}`);
    return { ok: true, chainId, window, bucketTs, n: scored.length };
  }
}

function clamp01(x: number) {
  return Math.max(0, Math.min(1, x || 0));
}
