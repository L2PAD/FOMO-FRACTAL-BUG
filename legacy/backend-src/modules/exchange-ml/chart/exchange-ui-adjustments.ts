/**
 * Exchange UI Adjustments Helper
 * ================================
 * 
 * BLOCK E1: Single source of truth for confidence/target adjustments
 * Used by chart, performance, and top-alts endpoints
 * 
 * Symmetric with Sentiment UI adjustments
 */

import { ExchangeReliabilityService } from '../reliability/exchange-reliability.service.js';

export interface AdjustmentContext {
  uriMultiplier: number;
  calibrationMultiplier: number;
  capitalMultiplier: number;
  safeMode: boolean;
  safeModeReason?: string;
  uriLevel: string;
  trainingBlocked: boolean;
  promotionBlocked: boolean;
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
export async function getExchangeAdjustmentContext(): Promise<AdjustmentContext> {
  const now = Date.now();
  
  if (cachedContext && (now - cacheTime) < CACHE_TTL_MS) {
    return cachedContext;
  }

  const reliabilityService = new ExchangeReliabilityService();
  const uri = await reliabilityService.computeStatus();

  const uriMultiplier = uri.actions?.confidenceMultiplier ?? 1;
  const capitalMultiplier = uri.actions?.sizeMultiplier ?? 1;
  const safeMode = uri.actions?.safeMode ?? false;
  const uriLevel = uri.level;
  const trainingBlocked = uri.actions?.trainingBlocked ?? false;
  const promotionBlocked = uri.actions?.promotionBlocked ?? false;

  // Calibration multiplier (use 1.0 for now, can integrate calibration service later)
  const calibrationMultiplier = 1.0;

  cachedContext = {
    uriMultiplier,
    calibrationMultiplier,
    capitalMultiplier,
    safeMode,
    safeModeReason: safeMode ? `URI level: ${uriLevel}` : undefined,
    uriLevel,
    trainingBlocked,
    promotionBlocked,
  };
  cacheTime = now;

  return cachedContext;
}

/**
 * Apply adjustments to raw values
 */
export function applyExchangeAdjustments(
  rawConfidence: number,
  rawExpectedMovePct: number,
  entry: number,
  context: AdjustmentContext
): AdjustedValues {
  const notes: string[] = [];

  // Apply multipliers to confidence
  let finalConfidence = rawConfidence * context.uriMultiplier * context.calibrationMultiplier * context.capitalMultiplier;

  if (context.uriMultiplier !== 1) {
    notes.push('URI_ADJ');
  }

  if (context.calibrationMultiplier !== 1) {
    notes.push('CALIBRATED');
  }

  if (context.capitalMultiplier !== 1) {
    notes.push('CAPITAL_GATE');
  }

  // SafeMode override
  if (context.safeMode) {
    finalConfidence = 0;
    notes.push('SAFE_MODE');
  }

  // Clamp confidence
  finalConfidence = Math.max(0, Math.min(1, finalConfidence));

  // Target calculation - scale by confidence ratio
  const rawTarget = entry * (1 + rawExpectedMovePct);
  const confRatio = rawConfidence > 0 ? finalConfidence / rawConfidence : 0;
  const finalTarget = context.safeMode 
    ? entry  // Neutralize target in safe mode
    : entry + (rawTarget - entry) * confRatio;

  return {
    finalConfidence,
    finalTarget,
    notes,
  };
}

/**
 * Calculate expected move percentage from signal score
 */
export function calculateExchangeExpectedMove(signalScore: number, confidence: number): number {
  // Simple model: signal strength * confidence * base move
  const baseMove = 0.03; // 3% base expectation for exchange
  return signalScore * confidence * baseMove;
}

/**
 * Determine direction from signal score
 */
export function signalToDirection(signalScore: number): 'LONG' | 'SHORT' | 'NEUTRAL' {
  if (signalScore > 0.1) return 'LONG';
  if (signalScore < -0.1) return 'SHORT';
  return 'NEUTRAL';
}
