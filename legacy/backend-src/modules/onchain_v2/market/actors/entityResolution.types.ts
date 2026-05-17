/**
 * Entity Resolution Types
 * ========================
 * 
 * P0.6.1: Unified Entity Resolution (v2 labels + v1 inference)
 * 
 * Single source of truth for entity attribution contract
 */

export type EntityAttributionSource =
  | 'LABEL_V2'          // Institutional seed (высокая точность)
  | 'ENTITY_V1'         // v1 entities.addresses lookup
  | 'ACTOR_CLUSTER_V1'  // v1 clustering/inference (гипотеза)
  | 'BEHAVIORAL_FALLBACK'; // Heuristic fallback

export type ResolvedEntity = {
  entityId: string;
  entityName: string;
  entityType: string; // cex | fund | market_maker | whale | bridge | protocol | dex | actor | unknown
  confidence: number; // 0..1
  source: EntityAttributionSource;
  labelType?: string; // hot_wallet, bridge, contract, etc.
  evidence?: Array<{ kind: string; value: any; weight?: number }>;
};

export type EntityResolutionContext = {
  source?: string;        // cex | dex | bridge | whale
  tokenAddress?: string;
  window?: string;
  bucketTs?: Date;
  netUsd?: number;
  isWhale?: boolean;
};
