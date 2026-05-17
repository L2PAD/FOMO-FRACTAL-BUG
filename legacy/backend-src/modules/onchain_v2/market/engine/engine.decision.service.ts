/**
 * Engine Decision Service — Token-first v1
 * ==========================================
 * 
 * PHASE 4, Block E1: Produces actionable decisions per token.
 * 
 * Collects from 4 layers:
 *   1. AltFlow (score, confidence, flows, flags)
 *   2. Pricing (source, reliability, stale)
 *   3. Pool (best pool score/status + tvl)
 *   4. LARE v2 Gate (riskCap + regime)
 * 
 * Output: BUY | REDUCE | NO_TRADE + evidence + reasons
 */

import { AltFlowPointModel } from '../altflow/altflow.model.js';
import { pricingService } from '../pricing/price.service.js';
import { poolScoringService } from '../pricing/pools/poolScoring.service.js';
import { LareV2Model } from '../liquidity_v2/liquidity_v2.model.js';

// ═══════════════════════════════════════════════════════════════
// TYPES (Contract)
// ═══════════════════════════════════════════════════════════════

export type EngineAction = 'BUY' | 'REDUCE' | 'NO_TRADE';

export interface EngineDecisionFlag {
  code: string;
  severity: 'INFO' | 'WARN' | 'CRITICAL';
  detail?: string;
}

export interface EngineDecision {
  ok: true;
  chainId: number;
  window: string;
  target: { symbol?: string; address?: string };

  action: EngineAction;
  confidence: number;
  score: number;
  riskCap: number;
  regime: string;

  reasons: string[];
  flags: EngineDecisionFlag[];

  evidence: {
    trades: number;
    spanHours: number;
    pricedShare: number;
    priceSource: string;
    poolScore: number | null;
    poolStatus: string | null;
    tvlUsd: number | null;
  };

  modelFeatures: {
    altflowScore: number;
    altflowConfidence: number;
    priceReliability: number | null;
    poolScore: number | null;
    poolStatus: string | null;
    riskCap: number;
    regime: string;
  };

  links: {
    signalsUrl: string;
    assetUrl: string;
  };

  updatedAt: string;
  dataHealth: { blocked: boolean; blockers: string[] };
}

export interface EngineBlockedDecision {
  ok: true;
  chainId: number;
  window: string;
  target: { symbol?: string; address?: string };
  action: 'NO_TRADE';
  confidence: 0;
  score: 0;
  riskCap: number;
  regime: string;
  reasons: string[];
  flags: EngineDecisionFlag[];
  evidence: null;
  modelFeatures: null;
  links: { signalsUrl: string; assetUrl: string };
  updatedAt: string;
  dataHealth: { blocked: true; blockers: string[] };
}

// ═══════════════════════════════════════════════════════════════
// THRESHOLDS
// ═══════════════════════════════════════════════════════════════

const BUY_THRESHOLD = 65;
const REDUCE_THRESHOLD = 35;
const MIN_CONFIDENCE = 0.55;

// ═══════════════════════════════════════════════════════════════
// SERVICE
// ═══════════════════════════════════════════════════════════════

export async function computeDecision(args: {
  chainId: number;
  window: string;
  symbol?: string;
  address?: string;
}): Promise<EngineDecision | EngineBlockedDecision> {
  const { chainId, window: win, symbol, address } = args;
  const now = new Date();
  const blockers: string[] = [];
  const reasons: string[] = [];
  const flags: EngineDecisionFlag[] = [];
  
  const target = { symbol, address };
  const baseLinks = {
    signalsUrl: `/intelligence/onchain-v3?tab=signals&token=${symbol || address || ''}`,
    assetUrl: `/intelligence/onchain-v3?tab=assets&token=${symbol || address || ''}`,
  };

  // ─── 1. Get LARE v2 Gate (regime + riskCap) ─────────────────
  let riskCap = 0.10; // default conservative
  let regime = 'UNKNOWN';
  
  try {
    const lare = await LareV2Model.findOne(
      { chainId: chainId || 1 },
      {},
      { sort: { bucketTs: -1 } }
    ).lean();
    
    if (lare) {
      riskCap = (lare as any).gate?.riskCap ?? 0.10;
      regime = (lare as any).regime ?? 'UNKNOWN';
      
      if ((lare as any).gate?.blockNewPositions) {
        blockers.push('LARE gate: new positions blocked');
        flags.push({ code: 'GATE_BLOCKED', severity: 'CRITICAL', detail: (lare as any).gate?.reason });
      }
    } else {
      flags.push({ code: 'NO_LARE', severity: 'WARN', detail: 'No LARE v2 snapshot found' });
    }
  } catch (err) {
    flags.push({ code: 'LARE_ERROR', severity: 'WARN', detail: String(err) });
  }

  // ─── 2. Get AltFlow signal ──────────────────────────────────
  const lookupKey = symbol || address;
  if (!lookupKey) {
    blockers.push('No symbol or address provided');
  }
  
  let altflow: any = null;
  if (lookupKey) {
    altflow = await AltFlowPointModel.findOne(
      { 
        chainId: chainId || 1,
        window: win,
        $or: [
          { symbol: { $regex: new RegExp(`^${lookupKey}$`, 'i') } },
          { symbol: lookupKey.toUpperCase() },
        ],
      },
      {},
      { sort: { t: -1 } }
    ).lean();
  }

  if (!altflow) {
    blockers.push(`No AltFlow data for ${lookupKey} (${win})`);
  }

  // ─── BLOCKED check ──────────────────────────────────────────
  if (blockers.length > 0) {
    return {
      ok: true,
      chainId,
      window: win,
      target,
      action: 'NO_TRADE',
      confidence: 0,
      score: 0,
      riskCap,
      regime,
      reasons: [`Blocked: ${blockers.join('; ')}`],
      flags: [...flags, { code: 'DATA_MISSING', severity: 'CRITICAL', detail: blockers.join('; ') }],
      evidence: null,
      modelFeatures: null,
      links: baseLinks,
      updatedAt: now.toISOString(),
      dataHealth: { blocked: true, blockers },
    };
  }

  // ─── 3. Extract AltFlow metrics ─────────────────────────────
  const altScore = Math.round(((altflow.score ?? 0) + 1) * 50); // -1..1 → 0..100
  const altConf = altflow.confidence ?? 0;
  const altFlags: any[] = altflow.flags ?? [];
  const quality = altflow.quality ?? {};
  const evidence = altflow.evidence ?? {};
  
  // Propagate AltFlow flags
  for (const f of altFlags) {
    if (typeof f === 'object' && f.code) {
      flags.push(f);
    } else if (typeof f === 'string') {
      flags.push({ code: f, severity: 'INFO' });
    }
  }

  // ─── 4. Pricing check ──────────────────────────────────────
  let priceSource = quality.priceSource || 'NONE';
  let priceReliability: number | null = quality.priceConfidence ?? null;
  const pricedShare = evidence.pricedShare ?? 0;
  
  if (priceSource === 'NONE' && pricedShare < 0.3) {
    flags.push({ code: 'NO_PRICE', severity: 'CRITICAL', detail: `pricedShare=${pricedShare.toFixed(2)}` });
    blockers.push('No reliable pricing');
  }

  // ─── 5. Pool check ─────────────────────────────────────────
  const poolScore = quality.poolScore ?? null;
  const poolStatus = quality.poolStatus ?? null;
  
  if (poolStatus === 'DISABLED') {
    flags.push({ code: 'POOL_DISABLED', severity: 'CRITICAL' });
    blockers.push('Best pool is DISABLED');
  } else if (poolStatus === 'DEGRADED') {
    flags.push({ code: 'POOL_DEGRADED', severity: 'WARN' });
    reasons.push('Pool quality degraded — reduced reliability');
  }

  // ─── RE-CHECK blockers after pricing/pool ───────────────────
  if (blockers.length > 0) {
    return {
      ok: true,
      chainId,
      window: win,
      target,
      action: 'NO_TRADE',
      confidence: 0,
      score: 0,
      riskCap,
      regime,
      reasons: [`Blocked: ${blockers.join('; ')}`],
      flags: [...flags, { code: 'DATA_MISSING', severity: 'CRITICAL' }],
      evidence: null,
      modelFeatures: null,
      links: baseLinks,
      updatedAt: now.toISOString(),
      dataHealth: { blocked: true, blockers },
    };
  }

  // ─── 6. Compute Decision ────────────────────────────────────
  const score = altScore;
  const confidence = altConf;
  
  let action: EngineAction = 'NO_TRADE';
  
  // Safety gates
  if (confidence < MIN_CONFIDENCE) {
    action = 'NO_TRADE';
    reasons.push(`Confidence ${(confidence * 100).toFixed(0)}% below threshold (${MIN_CONFIDENCE * 100}%)`);
    flags.push({ code: 'LOW_CONFIDENCE', severity: 'WARN', detail: `conf=${confidence.toFixed(2)}` });
  } else if (score >= BUY_THRESHOLD) {
    action = 'BUY';
    reasons.push(`Score ${score} above BUY threshold (${BUY_THRESHOLD})`);
  } else if (score <= REDUCE_THRESHOLD) {
    action = 'REDUCE';
    reasons.push(`Score ${score} below REDUCE threshold (${REDUCE_THRESHOLD})`);
  } else {
    action = 'NO_TRADE';
    reasons.push(`Score ${score} in neutral zone (${REDUCE_THRESHOLD}-${BUY_THRESHOLD})`);
  }

  // Risk cap annotation
  if (action === 'BUY' && riskCap <= 0.06) {
    reasons.push(`Risk constrained: riskCap=${(riskCap * 100).toFixed(0)}% (${regime})`);
    flags.push({ code: 'RISK_CONSTRAINED', severity: 'INFO', detail: `riskCap=${riskCap}` });
  }
  
  // Add flow drivers
  const drivers = altflow.drivers ?? [];
  for (const d of drivers.slice(0, 3)) {
    reasons.push(d);
  }

  // Regime context
  reasons.push(`Regime: ${regime}, RiskCap: ${(riskCap * 100).toFixed(0)}%`);

  return {
    ok: true,
    chainId,
    window: win,
    target,
    action,
    confidence,
    score,
    riskCap,
    regime,
    reasons: reasons.slice(0, 6),
    flags,
    evidence: {
      trades: evidence.trades ?? 0,
      spanHours: evidence.spanHours ?? 0,
      pricedShare: evidence.pricedShare ?? 0,
      priceSource,
      poolScore,
      poolStatus,
      tvlUsd: null,
    },
    modelFeatures: {
      altflowScore: altScore,
      altflowConfidence: altConf,
      priceReliability,
      poolScore,
      poolStatus,
      riskCap,
      regime,
    },
    links: baseLinks,
    updatedAt: now.toISOString(),
    dataHealth: { blocked: false, blockers: [] },
  };
}

console.log('[Engine] Decision Service v1 loaded');
