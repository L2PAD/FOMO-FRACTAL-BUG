/**
 * LiquidityScore Service
 * =======================
 * 
 * PHASE 2.1 + 2.2: Orchestration layer
 * 
 * Fetches market series + flow data → computes score → saves to DB
 */

import { LiquiditySeriesModel, bucket10m } from './liquidity.model';
import { 
  computeLiquidityScore, 
  MarketSeriesHistory, 
  MarketSeriesLatest,
  FlowDataInput,
  FlowHistories,
} from './liquidity.engine';
import { applyGovernance } from './liquidity.governance';
import { 
  LiquidityLatest, 
  LiquiditySeries, 
  LiquiditySeriesPoint,
  LiquidityRegime,
  LiquidityInputs,
  LiquidityGate,
} from './contracts';
import { getMarketSeries, getAllLatestMarketValues } from '../market.service';
import { MARKET_SERIES_KEYS } from '../market.model';
import { 
  getFlowAggregation, 
  getFlowHistories,
  type FlowAggregation,
} from './flow.service';

// Window mappings
const WINDOW_MS: Record<string, number> = {
  '24h': 24 * 60 * 60 * 1000,
  '7d': 7 * 24 * 60 * 60 * 1000,
  '30d': 30 * 24 * 60 * 60 * 1000,
};

/**
 * Get value at specific time offset from series
 */
function getValueAtOffset(
  series: Array<{ t: number; value: number }>,
  now: number,
  offsetMs: number
): number | null {
  const targetTime = now - offsetMs;
  const tolerance = 30 * 60 * 1000; // 30 min tolerance
  
  // Find closest point
  let closest: { t: number; value: number } | null = null;
  let minDiff = Infinity;
  
  for (const point of series) {
    const diff = Math.abs(point.t - targetTime);
    if (diff < minDiff && diff < tolerance) {
      minDiff = diff;
      closest = point;
    }
  }
  
  return closest?.value ?? null;
}

/**
 * Fetch market series and prepare for engine
 */
async function fetchMarketData(): Promise<{
  latest: MarketSeriesLatest;
  history: MarketSeriesHistory;
  metadata: { latestAge: number; sampleCount: number };
}> {
  const now = Date.now();
  const window30d = 30 * 24 * 60 * 60 * 1000;
  const window7d = 7 * 24 * 60 * 60 * 1000;
  const window24h = 24 * 60 * 60 * 1000;

  // Fetch all series
  const [pureAltCapSeries, stableSupplySeries, stableDomSeries, btcDomSeries, ethbtcSeries] = 
    await Promise.all([
      getMarketSeries(MARKET_SERIES_KEYS.PURE_ALT_CAP, window30d),
      getMarketSeries(MARKET_SERIES_KEYS.STABLE_SUPPLY_TOTAL, window30d),
      getMarketSeries(MARKET_SERIES_KEYS.STABLE_DOMINANCE, window30d),
      getMarketSeries(MARKET_SERIES_KEYS.BTC_DOMINANCE_RAW, window30d),
      getMarketSeries(MARKET_SERIES_KEYS.ETHBTC_RATIO, window30d),
    ]);

  // Get latest values
  const latestValues = await getAllLatestMarketValues();

  // Calculate metadata
  const allSeries = [pureAltCapSeries, stableSupplySeries, stableDomSeries, btcDomSeries, ethbtcSeries];
  const allPoints = allSeries.flatMap(s => s);
  const latestPoint = allPoints.length > 0 ? Math.max(...allPoints.map(p => p.t)) : 0;
  const latestAge = latestPoint > 0 ? now - latestPoint : Infinity;
  const sampleCount = Math.min(...allSeries.map(s => s.length));

  // Build latest with historical lookbacks
  const latest: MarketSeriesLatest = {
    pureAltCap: latestValues.PURE_ALT_CAP != null ? {
      now: latestValues.PURE_ALT_CAP,
      prev7d: getValueAtOffset(pureAltCapSeries, now, window7d),
      prev24h: getValueAtOffset(pureAltCapSeries, now, window24h),
    } : null,
    stableSupply: latestValues.STABLE_SUPPLY_TOTAL != null ? {
      now: latestValues.STABLE_SUPPLY_TOTAL,
      prev7d: getValueAtOffset(stableSupplySeries, now, window7d),
      prev24h: getValueAtOffset(stableSupplySeries, now, window24h),
    } : null,
    stableDom: latestValues.STABLE_DOMINANCE != null ? {
      now: latestValues.STABLE_DOMINANCE,
      prev7d: getValueAtOffset(stableDomSeries, now, window7d),
      prev24h: getValueAtOffset(stableDomSeries, now, window24h),
    } : null,
    btcDom: latestValues.BTC_DOMINANCE_RAW != null ? {
      now: latestValues.BTC_DOMINANCE_RAW,
      prev7d: getValueAtOffset(btcDomSeries, now, window7d),
      prev24h: getValueAtOffset(btcDomSeries, now, window24h),
    } : null,
    ethbtc: latestValues.ETHBTC_RATIO != null ? {
      now: latestValues.ETHBTC_RATIO,
      prev7d: getValueAtOffset(ethbtcSeries, now, window7d),
      prev24h: getValueAtOffset(ethbtcSeries, now, window24h),
    } : null,
  };

  // Build history arrays for robust normalization
  const history: MarketSeriesHistory = {
    pureAltCap: pureAltCapSeries.map(p => p.value),
    stableSupply: stableSupplySeries.map(p => p.value),
    stableDom: stableDomSeries.map(p => p.value),
    btcDom: btcDomSeries.map(p => p.value),
    ethbtc: ethbtcSeries.map(p => p.value),
  };

  return { latest, history, metadata: { latestAge, sampleCount } };
}

/**
 * Fetch flow data for Phase 2.2
 */
async function fetchFlowData(): Promise<{
  flowData: FlowDataInput;
  flowHistories: FlowHistories;
}> {
  try {
    const [aggregation, histories] = await Promise.all([
      getFlowAggregation(24 * 60 * 60 * 1000), // 24h window
      getFlowHistories(),
    ]);

    const flowData: FlowDataInput = {
      dexImbalance: aggregation.dex?.imbalance ?? null,
      exchangePressure: aggregation.exchange?.inflowPressure ?? null,
      dexSwapCount: aggregation.dex?.totalSwaps ?? 0,
      exchangeTransferCount: (aggregation.exchange?.inflows ?? 0) + (aggregation.exchange?.outflows ?? 0),
      dexStale: aggregation.dex?.isStale ?? true,
      exchangeStale: aggregation.exchange?.isStale ?? true,
      hasExchangeLabels: aggregation.exchange?.hasLabels ?? false,
    };

    return { flowData, flowHistories: histories };
  } catch (error) {
    console.error('[Liquidity Service] Error fetching flow data:', error);
    // Return empty flow data on error (graceful degradation)
    return {
      flowData: {
        dexImbalance: null,
        exchangePressure: null,
        dexSwapCount: 0,
        exchangeTransferCount: 0,
        dexStale: true,
        exchangeStale: true,
        hasExchangeLabels: false,
      },
      flowHistories: {
        dexImbalance: [],
        exchangeFlow: [],
      },
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// GATE BUILDER (Context Layer Output)
// ═══════════════════════════════════════════════════════════════

/**
 * Build Risk Gate - Context Layer Output
 * 
 * OnChain does NOT provide direction (BUY/SELL).
 * It provides risk context and permission gates.
 */
function buildLiquidityGate(params: {
  regime: LiquidityRegime;
  score: number;
  confidence: number;
  guardrailState: string;
  guardrailAction: string;
}): LiquidityGate {
  const { regime, score, confidence, guardrailState, guardrailAction } = params;

  // Governance override - CRITICAL blocks everything
  if (guardrailState === 'CRITICAL' || guardrailAction === 'BLOCK_OUTPUT') {
    return {
      allowAggressiveRisk: false,
      riskCap: 0,
      blockNewPositions: true,
      reason: 'Governance block - insufficient data quality',
    };
  }

  let riskCap = 1;
  let allowAggressiveRisk = false;

  // DEGRADED state reduces risk cap
  if (guardrailState === 'DEGRADED') {
    riskCap *= 0.6;
  }
  
  // WARN state slightly reduces risk cap
  if (guardrailState === 'WARN') {
    riskCap *= 0.85;
  }

  // Regime-based logic
  switch (regime) {
    case LiquidityRegime.RISK_ON_ALTS:
      // Only allow aggressive risk if score is strong (>65) and confidence decent
      if (score >= 65 && confidence >= 0.4) {
        allowAggressiveRisk = true;
        riskCap *= 1.0;
      } else {
        riskCap *= 0.9;
      }
      break;

    case LiquidityRegime.RISK_OFF:
      // Strong risk reduction in risk-off
      riskCap *= 0.4;
      break;

    case LiquidityRegime.STABLE_INFLOW:
      // Moderate risk reduction - capital parking
      riskCap *= 0.5;
      break;

    case LiquidityRegime.BTC_FLIGHT:
      // Moderate risk reduction - flight to BTC
      riskCap *= 0.6;
      break;

    case LiquidityRegime.NEUTRAL:
    default:
      // Default cautious stance
      riskCap *= 0.8;
      break;
  }

  // Confidence dampening - low confidence reduces cap further
  riskCap *= Math.max(0.3, confidence);

  // Build reason string
  const reasons: string[] = [];
  if (regime === LiquidityRegime.RISK_ON_ALTS) reasons.push('Alt liquidity favorable');
  if (regime === LiquidityRegime.RISK_OFF) reasons.push('Risk-off regime active');
  if (regime === LiquidityRegime.STABLE_INFLOW) reasons.push('Capital parking in stables');
  if (regime === LiquidityRegime.BTC_FLIGHT) reasons.push('Flight to BTC detected');
  if (confidence < 0.4) reasons.push('Low confidence data');
  if (guardrailState === 'DEGRADED') reasons.push('Degraded data quality');

  return {
    allowAggressiveRisk,
    riskCap: Number(riskCap.toFixed(3)),
    blockNewPositions: false,
    reason: reasons.length > 0 ? reasons.join('; ') : 'Normal operation',
  };
}

/**
 * Get latest liquidity score (computed)
 */
export async function getLatestLiquidity(): Promise<LiquidityLatest> {
  // Fetch both market data and flow data in parallel
  const [marketDataResult, flowDataResult] = await Promise.all([
    fetchMarketData(),
    fetchFlowData(),
  ]);

  const { latest, history, metadata } = marketDataResult;
  const { flowData, flowHistories } = flowDataResult;
  
  // Compute score with flow data (Phase 2.2)
  const engineResult = computeLiquidityScore(
    latest, 
    history, 
    metadata,
    flowData,
    flowHistories
  );
  
  // Apply governance
  const keysPresent = Object.values(latest).filter(v => v !== null).length;
  const govResult = applyGovernance({
    confidenceBase: engineResult.confidenceBase,
    flags: engineResult.flags,
    latestAge: metadata.latestAge,
    sampleCount: metadata.sampleCount,
    keysPresent,
  });

  // Build inputs for output
  const inputs: LiquidityInputs = {
    pureAltCap: {
      now: latest.pureAltCap?.now ?? 0,
      delta24h: latest.pureAltCap?.prev24h != null 
        ? ((latest.pureAltCap.now - latest.pureAltCap.prev24h) / latest.pureAltCap.prev24h) * 100 
        : null,
      delta7d: latest.pureAltCap?.prev7d != null 
        ? ((latest.pureAltCap.now - latest.pureAltCap.prev7d) / latest.pureAltCap.prev7d) * 100 
        : null,
    },
    stableSupply: {
      now: latest.stableSupply?.now ?? 0,
      delta24h: latest.stableSupply?.prev24h != null 
        ? ((latest.stableSupply.now - latest.stableSupply.prev24h) / latest.stableSupply.prev24h) * 100 
        : null,
      delta7d: latest.stableSupply?.prev7d != null 
        ? ((latest.stableSupply.now - latest.stableSupply.prev7d) / latest.stableSupply.prev7d) * 100 
        : null,
    },
    stableDom: {
      now: latest.stableDom?.now ?? 0,
      delta24h: latest.stableDom?.prev24h != null 
        ? (latest.stableDom.now - latest.stableDom.prev24h) 
        : null,
      delta7d: latest.stableDom?.prev7d != null 
        ? (latest.stableDom.now - latest.stableDom.prev7d) 
        : null,
    },
    btcDom: {
      now: latest.btcDom?.now ?? 0,
      delta24h: latest.btcDom?.prev24h != null 
        ? (latest.btcDom.now - latest.btcDom.prev24h) 
        : null,
      delta7d: latest.btcDom?.prev7d != null 
        ? (latest.btcDom.now - latest.btcDom.prev7d) 
        : null,
    },
    ethbtc: {
      now: latest.ethbtc?.now ?? 0,
      delta24h: latest.ethbtc?.prev24h != null 
        ? ((latest.ethbtc.now - latest.ethbtc.prev24h) / latest.ethbtc.prev24h) * 100 
        : null,
      delta7d: latest.ethbtc?.prev7d != null 
        ? ((latest.ethbtc.now - latest.ethbtc.prev7d) / latest.ethbtc.prev7d) * 100 
        : null,
    },
  };

  // Build risk gate (Context Layer output)
  const gate = buildLiquidityGate({
    regime: govResult.shouldBlockOutput ? LiquidityRegime.NEUTRAL : engineResult.regime,
    score: govResult.shouldBlockOutput ? 50 : engineResult.score,
    confidence: govResult.finalConfidence,
    guardrailState: govResult.governance.guardrailState,
    guardrailAction: govResult.governance.guardrailAction,
  });

  return {
    ok: true,
    t: Date.now(),
    score: govResult.shouldBlockOutput ? 50 : engineResult.score,
    confidence: govResult.finalConfidence,
    regime: govResult.shouldBlockOutput ? LiquidityRegime.NEUTRAL : engineResult.regime,
    drivers: engineResult.drivers,
    flags: engineResult.flags,
    inputs,
    governance: govResult.governance,
    gate,
    version: 'v1.0.0',
  };
}

/**
 * Tick: compute and save liquidity point
 */
export async function tickLiquidity(chainId: number = 1): Promise<LiquiditySeriesPoint> {
  const now = Date.now();
  const bucketTime = bucket10m(now);

  const latest = await getLatestLiquidity();

  const point: LiquiditySeriesPoint = {
    t: bucketTime,
    score: latest.score,
    confidence: latest.confidence,
    regime: latest.regime,
    flags: latest.flags.map(f => f.code),
    drivers: latest.drivers,
  };

  // Upsert to DB
  await LiquiditySeriesModel.updateOne(
    { chainId, t: bucketTime },
    { $set: { ...point, chainId } },
    { upsert: true }
  );

  console.log(`[Liquidity] Tick saved: score=${point.score}, regime=${point.regime}, conf=${point.confidence.toFixed(2)}`);

  return point;
}

/**
 * Get liquidity series from DB
 */
export async function getLiquiditySeries(window: string = '30d', chainId: number = 1): Promise<LiquiditySeries> {
  const windowMs = WINDOW_MS[window] || WINDOW_MS['30d'];
  const cutoff = Date.now() - windowMs;

  const docs = await LiquiditySeriesModel.find(
    { chainId, t: { $gte: cutoff } },
    { _id: 0 }
  )
    .sort({ t: 1 })
    .lean();

  const series: LiquiditySeriesPoint[] = docs.map(d => ({
    t: d.t,
    score: d.score,
    confidence: d.confidence,
    regime: d.regime as LiquidityRegime,
    flags: d.flags,
    drivers: d.drivers,
  }));

  return {
    ok: true,
    key: 'ALT_LIQUIDITY',
    window,
    count: series.length,
    series,
  };
}

/**
 * Health check
 */
export async function getLiquidityHealth(chainId: number = 1): Promise<{
  ok: boolean;
  lastPointAge: number;
  sampleCount30d: number;
  latestScore: number | null;
  latestRegime: string | null;
}> {
  const latest = await LiquiditySeriesModel.findOne({ chainId })
    .sort({ t: -1 })
    .lean();

  const count = await LiquiditySeriesModel.countDocuments({
    chainId,
    t: { $gte: Date.now() - 30 * 24 * 60 * 60 * 1000 }
  });

  return {
    ok: latest !== null,
    lastPointAge: latest ? Date.now() - latest.t : Infinity,
    sampleCount30d: count,
    latestScore: latest?.score ?? null,
    latestRegime: latest?.regime ?? null,
  };
}

console.log('[Liquidity] Service loaded');
