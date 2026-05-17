/**
 * ActorScore Model — Structural Edge Score v3
 * =============================================
 * 
 * P0.9: Computed from EntityFlowModel data.
 * Edge Score = f(coverage, centrality, activity)
 */

import { Schema, model } from "mongoose";

const ActorScoreSchema = new Schema(
  {
    chainId: { type: Number, required: true, default: 1, index: true },
    window: { type: String, index: true },
    bucketTs: { type: Date, index: true },

    entityId: { type: String, index: true },
    entityName: { type: String },
    entityType: { type: String },

    attributionSource: { type: String },
    attributionConfidence: { type: Number },

    edgeScore: { type: Number, index: true },
    coverage: { type: Number },

    activityScore: { type: Number },
    centralityScore: { type: Number },

    tokensTouched: { type: Number },
    trades: { type: Number },
    netAbsUsd: { type: Number },
  },
  { timestamps: true }
);

ActorScoreSchema.index({ chainId: 1, window: 1, bucketTs: -1, edgeScore: -1 });

export const ActorScoreModel = model("OnchainV2_ActorScore", ActorScoreSchema);

console.log('[OnChain V2] ActorScore Model loaded');
