/**
 * Execution Types
 */

import type { SpreadRegime, DepthQuality } from './microstructure.types.js';

export type EntryStyle =
  | 'ENTER_MARKET'
  | 'ENTER_LIMIT'
  | 'STAGGER_LIMIT'
  | 'WAIT_RETRACE'
  | 'WAIT_CONFIRMATION'
  | 'DO_NOT_CHASE';

export type ScalingBias = 'ADD' | 'HOLD' | 'NO_ADD';

export interface EntryQualityAssessment {
  entryQualityScore: number;  // 0–1
  entryWindow: 'OPEN' | 'OK' | 'WEAK' | 'CLOSED';
  reasons: string[];
}

export interface SlippageAssessment {
  slippageRisk: number;       // 0–1
  expectedLeakage: number;    // fraction of edge lost
  maxSlippageBps: number;
  notes: string[];
}

export interface EdgeCompressionAssessment {
  edgeCompression: number;    // 0–1 (how much edge has been eaten)
  compressed: boolean;
  originalEdge: number;
  currentEdge: number;
  notes: string[];
}

export interface ExecutionPlan {
  entryStyle: EntryStyle;
  entryQualityScore: number;
  slippageRisk: number;
  spreadRegime: SpreadRegime;
  depthQuality: DepthQuality;
  chaseRisk: number;
  missRisk: number;
  maxSlippageBps: number;
  note: string;
}

export interface ScalingPlan {
  scalingBias: ScalingBias;
  reason: string;
}

export interface FullExecutionResult {
  entry: ExecutionPlan;
  scaling: ScalingPlan;
  exit: { action: string; confidence: number; reasons: string[] };
  edgeCompression: EdgeCompressionAssessment;
  microstructure: {
    spreadRegime: SpreadRegime;
    depthQuality: DepthQuality;
    slippageRisk: number;
  };
}
