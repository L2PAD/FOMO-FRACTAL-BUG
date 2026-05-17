/**
 * Exchange Reliability Types
 * ===========================
 * 
 * EX-S1: Unified Reliability Index (URI) for Exchange.
 * Mirrors Sentiment architecture but adapted for price-driven model.
 */

export type ReliabilityLevel = 'OK' | 'WARN' | 'DEGRADED' | 'CRITICAL';

export interface ExchangeReliabilityActions {
  workersBlocked: boolean;
  trainingBlocked: boolean;
  promotionBlocked: boolean;
  confidenceMultiplier: number;
  sizeMultiplier: number;
}

export interface ExchangeReliabilityComponents {
  dataHealth: number;        // 0..1 (PriceProvider health)
  driftHealth: number;       // 0..1 (Feature distribution stability)
  capitalHealth: number;     // 0..1 (Rolling equity performance)
  calibrationHealth: number; // 0..1 (Model calibration quality)
}

export interface ExchangeReliabilityStatus {
  uriScore: number;          // 0..1
  level: ReliabilityLevel;
  components: ExchangeReliabilityComponents;
  reasons: string[];
  actions: ExchangeReliabilityActions;
  asOf: string;
  raw?: {
    data?: any;
    drift?: any;
    capital?: any;
    calibration?: any;
  };
}

// Thresholds for URI levels
export const EX_URI_THRESHOLDS = {
  OK: 0.75,
  WARN: 0.60,
  DEGRADED: 0.40,
  CRITICAL: 0,
};

// Weights for URI components
export const EX_URI_WEIGHTS = {
  dataHealth: 0.30,
  driftHealth: 0.30,
  capitalHealth: 0.25,
  calibrationHealth: 0.15,
};

console.log('[Exchange-ML] Reliability types loaded (EX-S1)');
