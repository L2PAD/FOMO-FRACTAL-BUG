/**
 * Alert Engine Types
 */

export type AlertType =
  | 'ENTRY_SIGNAL'
  | 'EXIT_SIGNAL'
  | 'TRIM_SIGNAL'
  | 'STATE_CHANGE'
  | 'RISK_ALERT';

export type AlertTier = 'HIGH' | 'MEDIUM' | 'LOW';

export type AlertUrgency = 'IMMEDIATE' | 'SOON' | 'BATCH';

export interface AlertTrigger {
  type: AlertType;
  marketId: string;
  question: string;
  asset: string;
  action: string;
  urgency: AlertUrgency;
  tier: AlertTier;
  timestamp: number;
  transitionFrom?: string;
  transitionTo?: string;
}

export interface AlertPayload {
  id: string;
  type: AlertType;
  tier: AlertTier;
  urgency: AlertUrgency;

  market: string;
  marketId: string;
  asset: string;
  action: string;

  priority: number;

  edge: number;
  confidence: number;
  alignment: number;

  execution: {
    entryStyle: string;
    slippageRisk: number;
    entryQualityScore: number;
  };

  project: {
    verdict: string | null;
    unlockRisk: string | null;
  };

  why: string[];
  risks: string[];

  timestamp: string;
}

export interface DigestPayload {
  type: 'realtime' | 'batch';
  timestamp: string;
  alerts: AlertPayload[];
  summary: {
    total: number;
    high: number;
    medium: number;
    low: number;
    topAction: string | null;
  };
}

export interface AlertState {
  action: string;
  entryStyle: string;
  exitAction: string;
  repricing: string;
  edge: number;
  tier: AlertTier | null;
}

export interface CooldownKey {
  marketId: string;
  action: string;
  state: string;
}
