/**
 * Microstructure Types
 */

export type SpreadRegime = 'NARROW' | 'NORMAL' | 'WIDE' | 'BROKEN';
export type DepthQuality = 'DEEP' | 'OK' | 'THIN' | 'FRAGILE';

export interface MicrostructureSnapshot {
  marketId: string;
  impliedProb: number;
  spread: number;
  liquidity: number;
  volume24h: number;
  timestamp: number;
}

export interface SpreadAssessment {
  regime: SpreadRegime;
  spreadPenalty: number;      // 0–1
  rawSpread: number;
  notes: string[];
}

export interface DepthAssessment {
  depthQuality: DepthQuality;
  fragilityScore: number;     // 0–1
  notes: string[];
}
