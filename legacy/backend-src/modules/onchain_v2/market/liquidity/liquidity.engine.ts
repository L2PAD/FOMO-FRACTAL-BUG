/**
 * LiquidityScore Engine
 * ======================
 * 
 * 🔒 FROZEN v1.0.0 — 2026-02-23
 * 
 * LARE (Liquidity & Alt Rotation Engine)
 * Core computation logic for LiquidityScore (0-100)
 * 
 * ⚠️ DO NOT MODIFY formulas without version bump
 * 
 * Computes LiquidityScore (0-100) from 5 market series + flow data.
 * NO price forecasts. Only regime classification.
 */

import {
  LiquidityRegime,
  LiquidityFlag,
  LiquidityFeatures,
  LiquidityEngineResult,
  FlagSeverity,
  FLAG_CODES,
  LIQUIDITY_THRESHOLDS as T,
  LARE_VERSION,
  LARE_FROZEN,
} from './contracts';

// ═══════════════════════════════════════════════════════════════
// MATH HELPERS
// ═══════════════════════════════════════════════════════════════

/**
 * Clamp value to range
 */
function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

/**
 * Sigmoid function for soft normalization
 */
function sigmoid(x: number): number {
  return 1 / (1 + Math.exp(-x));
}

/**
 * Calculate percentage change
 */
function pctChange(now: number, prev: number): number {
  if (prev === 0 || !prev || !now) return 0;
  return ((now - prev) / Math.abs(prev)) * 100;
}

/**
 * Robust Z-score using median and IQR
 */
function robustZ(value: number, median: number, iqr: number): number {
  const eps = 0.0001;
  return (value - median) / Math.max(iqr, eps);
}

/**
 * Calculate median of array
 */
function median(arr: number[]): number {
  if (!arr.length) return 0;
  const sorted = [...arr].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

/**
 * Calculate IQR (interquartile range)
 */
function iqr(arr: number[]): number {
  if (arr.length < 4) return Math.max(...arr) - Math.min(...arr) || 1;
  const sorted = [...arr].sort((a, b) => a - b);
  const q1Idx = Math.floor(sorted.length * 0.25);
  const q3Idx = Math.floor(sorted.length * 0.75);
  return sorted[q3Idx] - sorted[q1Idx] || 1;
}

/**
 * Normalize delta to 0-1 using robust stats
 */
function normalizeRobust(
  delta: number,
  history: number[],
  k: number = T.SIGMOID_K
): number {
  if (!history.length) return 0.5;
  const med = median(history);
  const range = iqr(history);
  const z = robustZ(delta, med, range);
  return sigmoid(z / k);
}

// ═══════════════════════════════════════════════════════════════
// REGIME DETECTION
// ═══════════════════════════════════════════════════════════════

interface DeltaFlags {
  altUp: boolean;
  altDown: boolean;
  stableUp: boolean;
  btcDomUp: boolean;
  ethbtcUp: boolean;
  ethbtcDown: boolean;
}

function detectDeltaFlags(deltas: Record<string, number | null>): DeltaFlags {
  const altDelta = deltas.pureAltCap ?? 0;
  const stableDomDelta = deltas.stableDom ?? 0;
  const stableSupplyDelta = deltas.stableSupply ?? 0;
  const btcDomDelta = deltas.btcDom ?? 0;
  const ethbtcDelta = deltas.ethbtc ?? 0;

  return {
    altUp: altDelta > T.ALT_UP_PCT,
    altDown: altDelta < T.ALT_DOWN_PCT,
    stableUp: stableDomDelta > T.STABLE_DOM_UP || stableSupplyDelta > T.STABLE_SUPPLY_UP,
    btcDomUp: btcDomDelta > T.BTC_DOM_UP,
    ethbtcUp: ethbtcDelta > T.ETHBTC_UP,
    ethbtcDown: ethbtcDelta < T.ETHBTC_DOWN,
  };
}

function deriveRegime(flags: DeltaFlags): LiquidityRegime {
  // Priority order (most specific first)
  
  // 1. STABLE_INFLOW: stables rising + alts falling = risk parking
  if (flags.stableUp && flags.altDown) {
    return LiquidityRegime.STABLE_INFLOW;
  }
  
  // 2. BTC_FLIGHT: BTC dom rising + alts falling = flight to BTC
  if (flags.btcDomUp && flags.altDown) {
    return LiquidityRegime.BTC_FLIGHT;
  }
  
  // 3. RISK_ON_ALTS: alts rising + ETH strong + no stable/BTC pressure
  if (flags.altUp && !flags.stableUp && !flags.btcDomUp && flags.ethbtcUp) {
    return LiquidityRegime.RISK_ON_ALTS;
  }
  
  // 4. RISK_OFF: alts falling + any risk-off signal
  if (flags.altDown && (flags.stableUp || flags.btcDomUp || flags.ethbtcDown)) {
    return LiquidityRegime.RISK_OFF;
  }
  
  // 5. NEUTRAL: everything else
  return LiquidityRegime.NEUTRAL;
}

// ═══════════════════════════════════════════════════════════════
// DRIVERS GENERATION
// ═══════════════════════════════════════════════════════════════

function buildDrivers(
  deltas: Record<string, number | null>,
  regime: LiquidityRegime
): string[] {
  const drivers: string[] = [];
  
  const altDelta = deltas.pureAltCap ?? 0;
  const stableDomDelta = deltas.stableDom ?? 0;
  const stableSupplyDelta = deltas.stableSupply ?? 0;
  const btcDomDelta = deltas.btcDom ?? 0;
  const ethbtcDelta = deltas.ethbtc ?? 0;

  // Add relevant drivers based on regime
  if (altDelta > T.ALT_UP_PCT) {
    drivers.push(`Pure alt cap rising (7d +${altDelta.toFixed(1)}%)`);
  } else if (altDelta < T.ALT_DOWN_PCT) {
    drivers.push(`Alt cap contracting (7d ${altDelta.toFixed(1)}%)`);
  }

  if (ethbtcDelta > T.ETHBTC_UP) {
    drivers.push(`ETH/BTC strengthening (7d +${ethbtcDelta.toFixed(1)}%)`);
  } else if (ethbtcDelta < T.ETHBTC_DOWN) {
    drivers.push(`ETH/BTC weakening (7d ${ethbtcDelta.toFixed(1)}%)`);
  }

  if (stableDomDelta > T.STABLE_DOM_UP) {
    drivers.push(`Stable dominance rising (7d +${stableDomDelta.toFixed(2)}pp)`);
  }

  if (stableSupplyDelta > T.STABLE_SUPPLY_UP) {
    drivers.push(`Stablecoin supply growing (7d +${stableSupplyDelta.toFixed(1)}%)`);
  }

  if (btcDomDelta > T.BTC_DOM_UP) {
    drivers.push(`BTC dominance rising (7d +${btcDomDelta.toFixed(2)}pp)`);
  } else if (btcDomDelta < -T.BTC_DOM_UP) {
    drivers.push(`BTC dominance falling (7d ${btcDomDelta.toFixed(2)}pp)`);
  }

  // Add regime context if no specific drivers
  if (drivers.length === 0) {
    drivers.push(`Market in ${regime.toLowerCase().replace('_', ' ')} state`);
  }

  return drivers.slice(0, 6); // Max 6 drivers
}

// ═══════════════════════════════════════════════════════════════
// FLAGS GENERATION
// ═══════════════════════════════════════════════════════════════

function buildFlags(
  keysPresent: number,
  totalKeys: number,
  latestAge: number,
  sampleCount: number,
  outlierDetected: boolean
): LiquidityFlag[] {
  const flags: LiquidityFlag[] = [];

  // NO_DATA
  if (keysPresent === 0) {
    flags.push({
      code: FLAG_CODES.NO_DATA,
      severity: FlagSeverity.CRITICAL,
      message: 'No market series data available',
    });
    return flags; // Critical, skip other checks
  }

  // API_PARTIAL
  if (keysPresent < totalKeys) {
    flags.push({
      code: FLAG_CODES.API_PARTIAL,
      severity: FlagSeverity.WARN,
      message: `Only ${keysPresent}/${totalKeys} market series available`,
    });
  }

  // STALE_MARKET_SERIES
  if (latestAge > T.VERY_STALE_MS) {
    flags.push({
      code: FLAG_CODES.STALE_MARKET_SERIES,
      severity: FlagSeverity.DEGRADED,
      message: `Latest data is ${Math.round(latestAge / 60000)}m old`,
    });
  } else if (latestAge > T.STALE_THRESHOLD_MS) {
    flags.push({
      code: FLAG_CODES.STALE_MARKET_SERIES,
      severity: FlagSeverity.WARN,
      message: `Latest data is ${Math.round(latestAge / 60000)}m old`,
    });
  }

  // LOW_SAMPLES_30D
  if (sampleCount < T.SAMPLE_COUNT_TARGET * 0.5) {
    flags.push({
      code: FLAG_CODES.LOW_SAMPLES_30D,
      severity: FlagSeverity.DEGRADED,
      message: `Only ${sampleCount} samples (need ${T.SAMPLE_COUNT_TARGET})`,
    });
  } else if (sampleCount < T.SAMPLE_COUNT_TARGET) {
    flags.push({
      code: FLAG_CODES.LOW_SAMPLES_30D,
      severity: FlagSeverity.WARN,
      message: `${sampleCount} samples (target ${T.SAMPLE_COUNT_TARGET})`,
    });
  }

  // OUTLIER_SPIKE
  if (outlierDetected) {
    flags.push({
      code: FLAG_CODES.OUTLIER_SPIKE,
      severity: FlagSeverity.WARN,
      message: 'Unusual market movement detected',
    });
  }

  return flags;
}

// ═══════════════════════════════════════════════════════════════
// PHASE 2.2: FLOW HELPERS
// ═══════════════════════════════════════════════════════════════

/**
 * Add flow-related flags
 */
function addFlowFlags(flags: LiquidityFlag[], flowData?: FlowDataInput): void {
  if (!flowData) return;

  // DEX data flags
  if (flowData.dexSwapCount === 0) {
    flags.push({
      code: FLAG_CODES.NO_DEX_DATA,
      severity: FlagSeverity.WARN,
      message: 'No DEX swap data available',
    });
  } else if (flowData.dexStale) {
    flags.push({
      code: FLAG_CODES.DEX_DATA_STALE,
      severity: FlagSeverity.WARN,
      message: 'DEX data is stale (>1h old)',
    });
  } else if (flowData.dexSwapCount < T.DEX_MIN_SWAPS) {
    flags.push({
      code: FLAG_CODES.LOW_FLOW_SAMPLES,
      severity: FlagSeverity.INFO,
      message: `Low DEX samples (${flowData.dexSwapCount} swaps)`,
    });
  }

  // Exchange labels flag
  if (!flowData.hasExchangeLabels) {
    flags.push({
      code: FLAG_CODES.EXCHANGE_LABELS_MISSING,
      severity: FlagSeverity.INFO,
      message: 'Exchange address labels not configured',
    });
  } else if (flowData.exchangeStale && flowData.exchangeTransferCount > 0) {
    flags.push({
      code: FLAG_CODES.DEX_DATA_STALE,
      severity: FlagSeverity.WARN,
      message: 'Exchange flow data is stale',
    });
  }
}

/**
 * Compute DEX pressure feature (0-1)
 * Higher = more buy pressure = bullish for alts
 */
function computeDexPressureFeature(
  flowData?: FlowDataInput,
  flowHistories?: FlowHistories
): number {
  if (!flowData || flowData.dexImbalance === null || flowData.dexSwapCount < T.DEX_MIN_SWAPS) {
    return 0.5; // Neutral when no data
  }

  // DEX imbalance is already [-1, 1], convert to [0, 1]
  // +1 = all buys, -1 = all sells
  // We want: more buys = higher feature = bullish
  const baseValue = (flowData.dexImbalance + 1) / 2;

  // If we have history, normalize using robust stats
  if (flowHistories && flowHistories.dexImbalance.length > 10) {
    return normalizeRobust(flowData.dexImbalance, flowHistories.dexImbalance);
  }

  return clamp(baseValue, 0, 1);
}

/**
 * Compute exchange pressure feature (0-1)
 * Higher = more inflows = bearish for alts (risk-off)
 */
function computeExchangePressureFeature(
  flowData?: FlowDataInput,
  flowHistories?: FlowHistories
): number {
  if (!flowData || !flowData.hasExchangeLabels || flowData.exchangePressure === null) {
    return 0.5; // Neutral when no data
  }

  if (flowData.exchangeTransferCount < T.EXCHANGE_MIN_TRANSFERS) {
    return 0.5;
  }

  // Exchange pressure is already [-1, 1], convert to [0, 1]
  // +1 = all inflows (bearish), -1 = all outflows (bullish)
  // We want: more inflows = higher feature = bearish (inverted in score calc)
  const baseValue = (flowData.exchangePressure + 1) / 2;

  // If we have history, normalize using robust stats
  if (flowHistories && flowHistories.exchangeFlow.length > 10) {
    return normalizeRobust(flowData.exchangePressure, flowHistories.exchangeFlow);
  }

  return clamp(baseValue, 0, 1);
}

/**
 * Calculate weighted score with dynamic weight redistribution
 */
function calculateWeightedScore(
  features: LiquidityFeatures,
  flowData?: FlowDataInput
): { macroScore: number; flowScore: number; totalWeight: number } {
  // Macro features (always available)
  const macroScore =
    T.WEIGHT_ALT_MOM * features.altMom +
    T.WEIGHT_ETHBTC * features.ethbtcImpulse +
    T.WEIGHT_STABLE * (1 - features.stableInflow) +
    T.WEIGHT_BTC * (1 - features.btcFlight);

  let macroWeight = T.WEIGHT_ALT_MOM + T.WEIGHT_ETHBTC + T.WEIGHT_STABLE + T.WEIGHT_BTC;

  // Flow features (may be unavailable)
  let flowScore = 0;
  let flowWeight = 0;

  const hasDexData = flowData && 
    flowData.dexImbalance !== null && 
    flowData.dexSwapCount >= T.DEX_MIN_SWAPS &&
    !flowData.dexStale;

  const hasExchangeData = flowData && 
    flowData.hasExchangeLabels &&
    flowData.exchangePressure !== null &&
    flowData.exchangeTransferCount >= T.EXCHANGE_MIN_TRANSFERS &&
    !flowData.exchangeStale;

  if (hasDexData) {
    flowScore += T.WEIGHT_DEX_PRESSURE * features.dexPressure;
    flowWeight += T.WEIGHT_DEX_PRESSURE;
  }

  if (hasExchangeData) {
    // Exchange pressure is inverted (high inflow = bearish)
    flowScore += T.WEIGHT_EXCHANGE * (1 - features.exchangePressure);
    flowWeight += T.WEIGHT_EXCHANGE;
  }

  // Total weight should sum to 1, redistribute if flow missing
  const totalWeight = macroWeight + flowWeight;

  return { macroScore, flowScore, totalWeight };
}

/**
 * Derive regime with flow signals
 */
function deriveRegimeWithFlow(
  deltaFlags: DeltaFlags,
  flowData?: FlowDataInput
): LiquidityRegime {
  // Base regime from macro signals
  const baseRegime = deriveRegime(deltaFlags);

  // If no flow data, return base regime
  if (!flowData) return baseRegime;

  // Flow can strengthen or weaken regime classification
  const hasDexSellPressure = flowData.dexImbalance !== null && flowData.dexImbalance < -0.3;
  const hasDexBuyPressure = flowData.dexImbalance !== null && flowData.dexImbalance > 0.3;
  const hasExchangeInflow = flowData.exchangePressure !== null && flowData.exchangePressure > 0.3;
  const hasExchangeOutflow = flowData.exchangePressure !== null && flowData.exchangePressure < -0.3;

  // Flow can push NEUTRAL to directional
  if (baseRegime === LiquidityRegime.NEUTRAL) {
    // Strong sell pressure + exchange inflows → RISK_OFF
    if (hasDexSellPressure && hasExchangeInflow) {
      return LiquidityRegime.RISK_OFF;
    }
    // Strong buy pressure + exchange outflows → RISK_ON_ALTS
    if (hasDexBuyPressure && hasExchangeOutflow && deltaFlags.altUp) {
      return LiquidityRegime.RISK_ON_ALTS;
    }
  }

  // Flow can confirm existing regime
  if (baseRegime === LiquidityRegime.RISK_OFF && hasDexSellPressure) {
    return LiquidityRegime.RISK_OFF; // Confirmed
  }

  if (baseRegime === LiquidityRegime.RISK_ON_ALTS && hasDexBuyPressure) {
    return LiquidityRegime.RISK_ON_ALTS; // Confirmed
  }

  return baseRegime;
}

/**
 * Build drivers with flow context
 */
function buildDriversWithFlow(
  deltas: Record<string, number | null>,
  regime: LiquidityRegime,
  flowData?: FlowDataInput
): string[] {
  // Start with macro drivers
  const drivers = buildDrivers(deltas, regime);

  // Add flow-based drivers
  if (!flowData) return drivers;

  // DEX pressure drivers
  if (flowData.dexImbalance !== null && flowData.dexSwapCount >= T.DEX_MIN_SWAPS) {
    if (flowData.dexImbalance > 0.2) {
      drivers.push(`DEX buy pressure rising (+${(flowData.dexImbalance * 100).toFixed(0)}% imbalance)`);
    } else if (flowData.dexImbalance < -0.2) {
      drivers.push(`DEX sell pressure rising (${(flowData.dexImbalance * 100).toFixed(0)}% imbalance)`);
    }
  }

  // Exchange flow drivers
  if (flowData.hasExchangeLabels && flowData.exchangePressure !== null) {
    if (flowData.exchangePressure > 0.2) {
      drivers.push('Large inflows to exchanges detected');
    } else if (flowData.exchangePressure < -0.2) {
      drivers.push('Exchange outflows increasing');
    }
  }

  return drivers.slice(0, 6); // Max 6 drivers
}

/**
 * Calculate flow data completeness for confidence
 */
function calculateFlowCompleteness(flowData?: FlowDataInput): number {
  if (!flowData) return 0;

  let featuresPresent = 0;
  let featuresExpected = 2;

  // DEX feature present?
  if (flowData.dexImbalance !== null && 
      flowData.dexSwapCount >= T.DEX_MIN_SWAPS && 
      !flowData.dexStale) {
    featuresPresent++;
  }

  // Exchange feature present?
  if (flowData.hasExchangeLabels && 
      flowData.exchangePressure !== null &&
      flowData.exchangeTransferCount >= T.EXCHANGE_MIN_TRANSFERS &&
      !flowData.exchangeStale) {
    featuresPresent++;
  }

  return featuresPresent / featuresExpected;
}

// ═══════════════════════════════════════════════════════════════
// MAIN ENGINE
// ═══════════════════════════════════════════════════════════════

export interface MarketSeriesHistory {
  pureAltCap: number[];
  stableSupply: number[];
  stableDom: number[];
  btcDom: number[];
  ethbtc: number[];
}

export interface MarketSeriesLatest {
  pureAltCap: { now: number; prev7d: number | null; prev24h: number | null } | null;
  stableSupply: { now: number; prev7d: number | null; prev24h: number | null } | null;
  stableDom: { now: number; prev7d: number | null; prev24h: number | null } | null;
  btcDom: { now: number; prev7d: number | null; prev24h: number | null } | null;
  ethbtc: { now: number; prev7d: number | null; prev24h: number | null } | null;
}

// Phase 2.2: Flow data input
export interface FlowDataInput {
  dexImbalance: number | null;      // [-1, 1] buy/sell imbalance
  exchangePressure: number | null;  // [-1, 1] inflow/outflow pressure
  dexSwapCount: number;
  exchangeTransferCount: number;
  dexStale: boolean;
  exchangeStale: boolean;
  hasExchangeLabels: boolean;
}

export interface FlowHistories {
  dexImbalance: number[];
  exchangeFlow: number[];
}

export function computeLiquidityScore(
  latest: MarketSeriesLatest,
  history: MarketSeriesHistory,
  metadata: { latestAge: number; sampleCount: number },
  flowData?: FlowDataInput,
  flowHistories?: FlowHistories
): LiquidityEngineResult {
  // Count present keys
  const keys = ['pureAltCap', 'stableSupply', 'stableDom', 'btcDom', 'ethbtc'] as const;
  const keysPresent = keys.filter(k => latest[k] !== null).length;

  // Calculate deltas (7d)
  const rawDeltas: Record<string, number | null> = {
    pureAltCap: latest.pureAltCap?.prev7d != null 
      ? pctChange(latest.pureAltCap.now, latest.pureAltCap.prev7d) 
      : null,
    stableSupply: latest.stableSupply?.prev7d != null 
      ? pctChange(latest.stableSupply.now, latest.stableSupply.prev7d) 
      : null,
    stableDom: latest.stableDom?.prev7d != null 
      ? (latest.stableDom.now - latest.stableDom.prev7d) // pp change, not %
      : null,
    btcDom: latest.btcDom?.prev7d != null 
      ? (latest.btcDom.now - latest.btcDom.prev7d) // pp change
      : null,
    ethbtc: latest.ethbtc?.prev7d != null 
      ? pctChange(latest.ethbtc.now, latest.ethbtc.prev7d) 
      : null,
  };

  // Build flags first (may indicate NO_DATA)
  const flags = buildFlags(
    keysPresent,
    keys.length,
    metadata.latestAge,
    metadata.sampleCount,
    false // Outlier detection simplified
  );

  // Add flow-related flags (Phase 2.2)
  addFlowFlags(flags, flowData);

  // Check for critical NO_DATA
  const hasCritical = flags.some(f => f.severity === FlagSeverity.CRITICAL);
  if (hasCritical) {
    return {
      score: 50,
      confidenceBase: 0,
      regime: LiquidityRegime.NEUTRAL,
      drivers: ['No market data available'],
      flags,
      features: { altMom: 0.5, stableInflow: 0.5, btcFlight: 0.5, ethbtcImpulse: 0.5, dexPressure: 0.5, exchangePressure: 0.5 },
    };
  }

  // Calculate delta histories for normalization
  const deltaHistories = {
    pureAltCap: history.pureAltCap.slice(1).map((v, i) => pctChange(v, history.pureAltCap[i])),
    stableSupply: history.stableSupply.slice(1).map((v, i) => pctChange(v, history.stableSupply[i])),
    stableDom: history.stableDom.slice(1).map((v, i) => v - history.stableDom[i]),
    btcDom: history.btcDom.slice(1).map((v, i) => v - history.btcDom[i]),
    ethbtc: history.ethbtc.slice(1).map((v, i) => pctChange(v, history.ethbtc[i])),
  };

  // Normalize to 0-1 features (macro layer)
  const altMom = normalizeRobust(rawDeltas.pureAltCap ?? 0, deltaHistories.pureAltCap);
  const stableInflow = normalizeRobust(rawDeltas.stableDom ?? 0, deltaHistories.stableDom);
  const btcFlight = normalizeRobust(rawDeltas.btcDom ?? 0, deltaHistories.btcDom);
  const ethbtcImpulse = normalizeRobust(rawDeltas.ethbtc ?? 0, deltaHistories.ethbtc);

  // Phase 2.2: Flow features (micro layer)
  const dexPressure = computeDexPressureFeature(flowData, flowHistories);
  const exchangePressureFeature = computeExchangePressureFeature(flowData, flowHistories);

  const features: LiquidityFeatures = {
    altMom,
    stableInflow,
    btcFlight,
    ethbtcImpulse,
    dexPressure,
    exchangePressure: exchangePressureFeature,
  };

  // Calculate raw score with flow features
  // If flow data is unavailable, redistribute weights to macro features
  const { macroScore, flowScore, totalWeight } = calculateWeightedScore(features, flowData);
  const rawScore = (macroScore + flowScore) / totalWeight;

  const score = Math.round(100 * clamp(rawScore, 0, 1));

  // Determine regime from raw deltas + flow signals
  const deltaFlags = detectDeltaFlags(rawDeltas);
  const regime = deriveRegimeWithFlow(deltaFlags, flowData);

  // Build drivers with flow context
  const drivers = buildDriversWithFlow(rawDeltas, regime, flowData);

  // Calculate base confidence with flow completeness
  const flowCompleteness = calculateFlowCompleteness(flowData);
  const cComplete = keysPresent / keys.length;
  const cFresh = metadata.latestAge <= 15 * 60 * 1000 ? 1 
    : metadata.latestAge <= 60 * 60 * 1000 ? 0.6 
    : 0.2;
  const cSamples = clamp(metadata.sampleCount / T.SAMPLE_COUNT_TARGET, 0, 1);
  
  // Phase 2.2: Updated confidence formula
  const confidenceBase = clamp(
    0.30 * cComplete + 0.25 * cFresh + 0.25 * cSamples + 0.20 * flowCompleteness,
    0,
    1
  );

  return {
    score,
    confidenceBase,
    regime,
    drivers,
    flags,
    features,
    debug: {
      rawDeltas,
      normalizedFeatures: features,
    },
  };
}

console.log('[Liquidity] Engine loaded');
