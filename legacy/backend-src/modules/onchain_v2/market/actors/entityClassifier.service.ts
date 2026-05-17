/**
 * Entity Classifier Service
 * ==========================
 * 
 * PHASE 5: Simple entity classification based on behavior
 */

export type EntityType =
  | 'EXCHANGE'
  | 'BRIDGE'
  | 'FUND'
  | 'SMART_MONEY'
  | 'WHALE'
  | 'PROTOCOL'
  | 'UNKNOWN';

export interface ClassifyParams {
  address: string;
  totalUsd: number;
  isExchange?: boolean;
  isBridge?: boolean;
  isProtocol?: boolean;
}

/**
 * Classify entity based on known flags or USD volume
 */
export function classifyEntity(params: ClassifyParams): EntityType {
  if (params.isExchange) return 'EXCHANGE';
  if (params.isBridge) return 'BRIDGE';
  if (params.isProtocol) return 'PROTOCOL';

  // Volume-based classification
  if (params.totalUsd > 10_000_000) return 'WHALE';
  if (params.totalUsd > 1_000_000) return 'SMART_MONEY';

  return 'UNKNOWN';
}

/**
 * Get entity type display info
 */
export function getEntityTypeInfo(type: EntityType) {
  const info: Record<EntityType, { color: string; label: string; priority: number }> = {
    EXCHANGE: { color: 'blue', label: 'Exchange', priority: 1 },
    BRIDGE: { color: 'purple', label: 'Bridge', priority: 2 },
    FUND: { color: 'amber', label: 'Fund', priority: 3 },
    SMART_MONEY: { color: 'green', label: 'Smart Money', priority: 4 },
    WHALE: { color: 'indigo', label: 'Whale', priority: 5 },
    PROTOCOL: { color: 'cyan', label: 'Protocol', priority: 6 },
    UNKNOWN: { color: 'gray', label: 'Unknown', priority: 99 },
  };
  return info[type] || info.UNKNOWN;
}
