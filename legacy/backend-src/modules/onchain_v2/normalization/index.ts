/**
 * OnChain V2 — Normalization Module Index
 * =========================================
 * 
 * BLOCK 6: Normalization Engine
 * 
 * Converts all module signals to unified format:
 * - score: 0-100 (50 = neutral)
 * - direction: -1/0/+1
 * - strength: 0-1
 * - confidence: 0-1
 */

// Types
export {
  type SignalDirection,
  type NormalizedSignal,
  type NormalizeOptions,
  type NormalizationConfig,
  DEFAULT_SCALES,
} from './normalizer.types.js';

// Math utilities
export {
  clamp01,
  clampScore,
  tanhNorm,
  toScore,
  toDirection,
  toStrength,
  weightedAvg,
} from './normalizer.math.js';

// Service
export {
  NormalizerService,
  normalizerService,
} from './normalizer.service.js';

// Routes
export {
  buildNormalizationRoutes,
  type NormalizationDeps,
} from './normalization.routes.js';

console.log('[OnChain V2] Normalization module index loaded');
