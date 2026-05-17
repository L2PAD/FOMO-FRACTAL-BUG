/**
 * ACCURACY SERVICE
 * ================
 * 
 * Truth calculator: How accurate is Meta Brain really?
 * 
 * This service answers THE critical question:
 * "Does Meta Brain have alpha, or is it random?"
 */

import { getResolvedOutcomes } from '../outcomes/meta_brain_outcomes.repo.js';

export interface AccuracyReport {
  overall: number;
  totalOutcomes: number;
  
  byHorizon: {
    '24H': number;
    '7D': number;
    '30D': number;
  };
  
  confidenceBuckets: {
    '0.8+': number;
    '0.6-0.8': number;
    '<0.6': number;
  };
  
  byDirection: {
    LONG: number;
    SHORT: number;
    NEUTRAL: number;
  };
  
  avgConfidence: number;
  avgError?: number;
}

/**
 * Calculate overall accuracy
 */
export async function calculateAccuracy(filters?: {
  asset?: string;
  horizon?: '24H' | '7D' | '30D';
  minConfidence?: number;
}): Promise<AccuracyReport> {
  const outcomes = await getResolvedOutcomes(filters);
  
  if (outcomes.length === 0) {
    return {
      overall: 0,
      totalOutcomes: 0,
      byHorizon: { '24H': 0, '7D': 0, '30D': 0 },
      confidenceBuckets: { '0.8+': 0, '0.6-0.8': 0, '<0.6': 0 },
      byDirection: { LONG: 0, SHORT: 0, NEUTRAL: 0 },
      avgConfidence: 0,
    };
  }
  
  // Overall accuracy
  const correctCount = outcomes.filter(o => o.directionCorrect).length;
  const overall = correctCount / outcomes.length;
  
  // By horizon
  const byHorizon = {
    '24H': calculateAccuracyForSubset(outcomes.filter(o => o.horizon === '24H')),
    '7D': calculateAccuracyForSubset(outcomes.filter(o => o.horizon === '7D')),
    '30D': calculateAccuracyForSubset(outcomes.filter(o => o.horizon === '30D')),
  };
  
  // By confidence buckets
  const highConf = outcomes.filter(o => o.confidence >= 0.8);
  const midConf = outcomes.filter(o => o.confidence >= 0.6 && o.confidence < 0.8);
  const lowConf = outcomes.filter(o => o.confidence < 0.6);
  
  const confidenceBuckets = {
    '0.8+': calculateAccuracyForSubset(highConf),
    '0.6-0.8': calculateAccuracyForSubset(midConf),
    '<0.6': calculateAccuracyForSubset(lowConf),
  };
  
  // By direction
  const byDirection = {
    LONG: calculateAccuracyForSubset(outcomes.filter(o => o.direction === 'LONG')),
    SHORT: calculateAccuracyForSubset(outcomes.filter(o => o.direction === 'SHORT')),
    NEUTRAL: calculateAccuracyForSubset(outcomes.filter(o => o.direction === 'NEUTRAL')),
  };
  
  // Avg confidence
  const avgConfidence = outcomes.reduce((sum, o) => sum + o.confidence, 0) / outcomes.length;
  
  // Avg error
  const errorsWithData = outcomes.filter(o => o.errorPct !== undefined);
  const avgError = errorsWithData.length > 0
    ? errorsWithData.reduce((sum, o) => sum + (o.errorPct ?? 0), 0) / errorsWithData.length
    : undefined;
  
  return {
    overall,
    totalOutcomes: outcomes.length,
    byHorizon,
    confidenceBuckets,
    byDirection,
    avgConfidence,
    avgError,
  };
}

/**
 * Helper: Calculate accuracy for a subset
 */
function calculateAccuracyForSubset(subset: any[]): number {
  if (subset.length === 0) return 0;
  const correct = subset.filter(o => o.directionCorrect).length;
  return correct / subset.length;
}

console.log('[AccuracyService] Loaded');
