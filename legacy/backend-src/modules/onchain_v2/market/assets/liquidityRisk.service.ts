/**
 * OnChain V2 — Liquidity Risk Service
 * =====================================
 * 
 * PHASE 4: Assets Tab
 * Calculates liquidity risk score based on TVL, pool concentration, and depth.
 */

export interface LiquidityRiskInput {
  totalTvlUsd: number;
  activePools: number;
  concentrationTop1: number; // 0..1 share of TVL in top pool
  concentrationTop3: number; // 0..1 share of TVL in top 3 pools
}

export interface LiquidityRiskOutput {
  score: number;      // 0-100, higher = more risk
  label: 'VERY_LOW' | 'LOW' | 'MEDIUM' | 'HIGH';
  factors: {
    tvlRisk: number;
    poolRisk: number;
    concRisk: number;
  };
}

/**
 * Calculate liquidity risk score
 * 0 = low risk, 100 = high risk
 */
export function computeLiquidityRiskScore(input: LiquidityRiskInput): LiquidityRiskOutput {
  const tvl = Math.max(0, input.totalTvlUsd || 0);
  const pools = Math.max(0, input.activePools || 0);
  
  // TVL factor: lower TVL = higher risk
  // $100M+ = very low risk, $10M = low, $1M = medium, <$1M = high
  const tvlRisk =
    tvl <= 1_000_000 ? 0.85 :
    tvl <= 10_000_000 ? 0.55 :
    tvl <= 100_000_000 ? 0.25 : 0.12;
  
  // Pool count factor: fewer pools = higher risk
  const poolRisk =
    pools <= 1 ? 0.9 :
    pools === 2 ? 0.65 :
    pools <= 4 ? 0.45 : 0.25;
  
  // Concentration factor: higher concentration = higher risk
  const c1 = clamp01(input.concentrationTop1 ?? 1);
  const c3 = clamp01(input.concentrationTop3 ?? 1);
  const concRisk = clamp01((0.65 * c1) + (0.35 * c3));
  
  // Weighted final score
  const raw = (0.45 * tvlRisk) + (0.25 * poolRisk) + (0.30 * concRisk);
  const score = Math.round(clamp01(raw) * 100);
  
  const label: LiquidityRiskOutput['label'] =
    score >= 75 ? 'HIGH' :
    score >= 50 ? 'MEDIUM' :
    score >= 25 ? 'LOW' : 'VERY_LOW';
  
  return {
    score,
    label,
    factors: { tvlRisk, poolRisk, concRisk },
  };
}

function clamp01(n: number): number {
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(1, n));
}

console.log('[OnChain V2] Liquidity Risk Service loaded');
