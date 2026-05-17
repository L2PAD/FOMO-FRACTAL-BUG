/**
 * Sentiment UI Adjustments Helper
 * ================================
 * 
 * BLOCK P1.2: Single source of truth for confidence/target adjustments
 * Used by chart, performance, and top-alts endpoints
 */

import { SentimentReliabilityService } from '../reliability/sentiment-reliability.service.js';
import { getSentimentCalibrationGuard } from '../../shared/calibration-guard.service.js';

export interface AdjustmentContext {
  uriMultiplier: number;
  calibrationMultiplier: number;
  capitalMultiplier: number;
  safeMode: boolean;
  uriLevel: string;
}

export interface AdjustedValues {
  finalConfidence: number;
  finalTarget: number;
  notes: string[];
}

let cachedContext: AdjustmentContext | null = null;
let cacheTime = 0;
const CACHE_TTL_MS = 5000; // 5s cache

/**
 * Get current adjustment context from reliability services
 */
export async function getAdjustmentContext(): Promise<AdjustmentContext> {
  const now = Date.now();
  
  if (cachedContext && (now - cacheTime) < CACHE_TTL_MS) {
    return cachedContext;
  }

  const reliabilityService = new SentimentReliabilityService();
  const uri = await reliabilityService.computeStatus();

  const uriMultiplier = uri.actions?.confidenceMultiplier ?? 1;
  const capitalMultiplier = uri.actions?.sizeMultiplier ?? 1;
  const safeMode = uri.actions?.safeMode ?? false;
  const uriLevel = uri.level;

  // Calibration
  let calibrationMultiplier = 1;
  try {
    const calibrationService = getSentimentCalibrationGuard();
    const calibrationStatus = await calibrationService.getLatestStatus('7D');
    calibrationMultiplier = calibrationStatus?.confidenceMultiplier ?? 1;
  } catch {
    // Calibration service may not be available
  }

  cachedContext = {
    uriMultiplier,
    calibrationMultiplier,
    capitalMultiplier,
    safeMode,
    uriLevel,
  };
  cacheTime = now;

  return cachedContext;
}

/**
 * Apply adjustments to raw values
 */
export function applyAdjustments(
  rawConfidence: number,
  rawExpectedMovePct: number,
  entry: number,
  context: AdjustmentContext
): AdjustedValues {
  const notes: string[] = [];

  // Apply multipliers to confidence
  let finalConfidence = rawConfidence * context.uriMultiplier * context.calibrationMultiplier;

  if (context.uriMultiplier !== 1) {
    notes.push('URI_ADJ');
  }

  if (context.calibrationMultiplier !== 1) {
    notes.push('CALIBRATED');
  }

  // SafeMode override
  if (context.safeMode) {
    finalConfidence = 0;
    notes.push('SAFE_MODE');
  }

  // Clamp confidence
  finalConfidence = Math.max(0, Math.min(1, finalConfidence));

  // Target calculation (expectedMovePct stays raw, but we can optionally scale by capital)
  const finalTarget = entry * (1 + rawExpectedMovePct);

  return {
    finalConfidence,
    finalTarget,
    notes,
  };
}

/**
 * Determine direction from bias
 */
export function biasToDirection(bias: number): 'LONG' | 'SHORT' | 'NEUTRAL' {
  if (bias > 0.1) return 'LONG';
  if (bias < -0.1) return 'SHORT';
  return 'NEUTRAL';
}

/**
 * Calculate expected move percentage from bias and confidence
 */
export function calculateExpectedMove(bias: number, confidence: number): number {
  // Simple model: bias strength * confidence * base move
  const baseMove = 0.05; // 5% base expectation
  return bias * confidence * baseMove;
}
