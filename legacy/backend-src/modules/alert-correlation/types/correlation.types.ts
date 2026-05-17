/**
 * Alert Correlation Types
 */

export interface RawAlertRef {
  alertId: string;
  marketId: string;
  type: 'ENTRY_SIGNAL' | 'EXIT_SIGNAL' | 'TRIM_SIGNAL' | 'STATE_CHANGE' | 'RISK_ALERT';
  action?: string;
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
  timestamp: number;
  asset?: string;
  question?: string;
  edge?: number;
  confidence?: number;
  conviction?: string;
  entryStyle?: string;
  reasoning?: string;
  reasons?: string[];
  risks?: string[];

  factors?: {
    assetFactors: string[];
    themeFactors: string[];
    catalystFactors: string[];
    entityFactors: string[];
    deadlineFactors?: string[];
    resolutionFactors?: string[];
  };

  social?: {
    lifecycle?: string;
    saturation?: number;
  };

  project?: {
    verdict?: string;
    unlockRisk?: string;
    valuation?: string;
  };
}

export interface AlertCluster {
  clusterId: string;
  alerts: RawAlertRef[];
  windowStart: number;
  windowEnd: number;
}

export interface FactorOverlapResult {
  overlapScore: number;
  dominantSharedFactors: string[];
  assetOverlap: number;
  themeOverlap: number;
  catalystOverlap: number;
  entityOverlap: number;
}

export type MetaAlertType =
  | 'SECTOR_ROTATION'
  | 'MULTI_MARKET_CONFIRMATION'
  | 'UNLOCK_RISK_CLUSTER'
  | 'RISK_ON_SHIFT'
  | 'RISK_OFF_SHIFT'
  | 'NARRATIVE_EXHAUSTION'
  | 'BROAD_OVERHEAT'
  | 'CLUSTER_WAKEUP'
  | 'MIXED_CLUSTER';

export interface MetaAlert {
  metaAlertId: string;
  type: MetaAlertType;
  title: string;
  summary: string;
  members: string[];
  marketIds: string[];
  assets: string[];
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
  confidence: number;
  sharedFactors: string[];
  keyDrivers: string[];
  risks: string[];
  contradictionScore: number;
  memberDiversityScore: number;
  metaInsightGain: number;
  suppressMemberAlerts: boolean;
  regimeShift?: {
    detected: boolean;
    direction: 'RISK_ON' | 'RISK_OFF' | 'NEUTRAL';
    confidence: number;
  };
  dedupKey: string;
  timestamp: number;
}
