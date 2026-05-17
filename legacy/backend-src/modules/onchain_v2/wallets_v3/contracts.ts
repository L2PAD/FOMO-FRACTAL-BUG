/**
 * Wallet Profile v3 — Contracts
 * ==============================
 * Phase C: Typed interfaces for wallet deep profile.
 */

export type WindowKey = '24h' | '7d' | '30d';

export type AttributionSource =
  | 'LABEL_V2'
  | 'ENTITY_V1'
  | 'ACTOR_CLUSTER_V1'
  | 'BEHAVIORAL_FALLBACK'
  | 'NONE';

export interface WalletAttribution {
  entityId: string | null;
  entityName: string | null;
  entityType: string | null;
  source: AttributionSource;
  confidence: number;
  evidence: any[];
}

export interface WalletTokenRow {
  tokenAddress: string;
  symbol: string;
  inUsd: number;
  outUsd: number;
  netUsd: number;
  transfers: number;
  priceUsd: number | null;
}

export interface WalletCounterpartyRow {
  address: string;
  inUsd: number;
  outUsd: number;
  netUsd: number;
  transfers: number;
  attribution?: WalletAttribution;
}

export interface WalletProfileSnapshot {
  ok: true;
  chainId: number;
  address: string;
  window: WindowKey;

  totals: {
    inflowUsd: number;
    outflowUsd: number;
    netUsd: number;
    transfers: number;
    uniqueCounterparties: number;
    stableShare: number;
    avgTransferUsd: number;
  };

  attribution: WalletAttribution;
  topTokens: WalletTokenRow[];
  topCounterparties: WalletCounterpartyRow[];

  meta: {
    fromTs: string;
    toTs: string;
    computedAt: string;
    pricedTokens: number;
    totalTokens: number;
    truncated: boolean;
  };
}

export interface WalletSeriesPoint {
  ts: string;
  value: number;
}

export interface WalletSeriesResponse {
  ok: true;
  chainId: number;
  address: string;
  window: WindowKey;
  metric: string;
  points: WalletSeriesPoint[];
}
