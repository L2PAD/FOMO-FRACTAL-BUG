/**
 * Tokenomics Engine
 *
 * Evaluates token supply dynamics, FDV sanity, float quality, emission risk.
 *
 * Key rules:
 *   FDV too high → negative
 *   float < 10–15% → dangerous
 *   high emission → dilution risk
 *   no real utility → long-term weakness
 */

import type { TokenomicsAssessment, ProjectProfile, FdvLevel, FloatQuality } from '../types/project-intelligence.types.js';

// FDV benchmarks by sector (in USD)
const SECTOR_FDV_BENCHMARKS: Record<string, { fair: number; high: number; extreme: number }> = {
  l1:      { fair: 5e9,  high: 20e9,  extreme: 50e9 },
  l2:      { fair: 2e9,  high: 8e9,   extreme: 20e9 },
  defi:    { fair: 500e6, high: 3e9,  extreme: 10e9 },
  gaming:  { fair: 300e6, high: 2e9,  extreme: 8e9 },
  meme:    { fair: 100e6, high: 1e9,  extreme: 5e9 },
  ai:      { fair: 1e9,  high: 5e9,   extreme: 15e9 },
  rwa:     { fair: 500e6, high: 3e9,  extreme: 10e9 },
  infra:   { fair: 1e9,  high: 5e9,   extreme: 15e9 },
  default: { fair: 1e9,  high: 5e9,   extreme: 15e9 },
};

class TokenomicsEngine {
  assess(profile: ProjectProfile): TokenomicsAssessment {
    const notes: string[] = [];

    // 1. FDV Level
    const fdvLevel = this.assessFdv(profile, notes);

    // 2. Float Quality
    const floatQuality = this.assessFloat(profile, notes);

    // 3. Emission Risk
    const emissionRisk = this.assessEmission(profile, notes);

    // 4. Utility Score
    const utilityScore = this.assessUtility(profile, notes);

    // 5. Unlock risk (basic — detailed in unlock-pressure service)
    const unlockRisk = this.assessUnlockBasic(profile, notes);

    // 6. Verdict
    const negatives = [
      fdvLevel === 'EXTREME' ? 2 : fdvLevel === 'HIGH' ? 1 : 0,
      floatQuality === 'DANGEROUS' ? 2 : floatQuality === 'LOW' ? 1 : 0,
      emissionRisk > 0.7 ? 1 : 0,
      utilityScore < 0.3 ? 1 : 0,
      unlockRisk === 'HIGH' ? 1 : 0,
    ].reduce((a, b) => a + b, 0);

    const verdict = negatives >= 3 ? 'WEAK' as const
      : negatives >= 1 ? 'MID' as const
      : 'STRONG' as const;

    return {
      fdvLevel,
      floatQuality,
      unlockRisk,
      unlockInDays: profile.nextUnlockDate
        ? Math.max(0, Math.round((new Date(profile.nextUnlockDate).getTime() - Date.now()) / 86400000))
        : undefined,
      unlockPercent: profile.nextUnlockPercent,
      emissionRisk,
      utilityScore,
      verdict,
      notes,
    };
  }

  private assessFdv(p: ProjectProfile, notes: string[]): FdvLevel {
    const sector = p.sector || 'default';
    const bench = SECTOR_FDV_BENCHMARKS[sector] || SECTOR_FDV_BENCHMARKS['default'];

    if (p.fdv <= 0) {
      notes.push('FDV data unavailable');
      return 'FAIR';
    }

    if (p.fdv >= bench.extreme) {
      notes.push(`FDV $${(p.fdv / 1e9).toFixed(1)}B is EXTREME for ${sector} (threshold: $${(bench.extreme / 1e9).toFixed(0)}B)`);
      return 'EXTREME';
    }
    if (p.fdv >= bench.high) {
      notes.push(`FDV $${(p.fdv / 1e9).toFixed(1)}B is HIGH for ${sector}`);
      return 'HIGH';
    }
    if (p.fdv >= bench.fair) {
      notes.push(`FDV $${(p.fdv / 1e9).toFixed(1)}B is FAIR for ${sector}`);
      return 'FAIR';
    }
    notes.push(`FDV $${(p.fdv / 1e6).toFixed(0)}M is LOW for ${sector} — potential upside`);
    return 'LOW';
  }

  private assessFloat(p: ProjectProfile, notes: string[]): FloatQuality {
    if (p.totalSupply <= 0 || p.circulatingSupply <= 0) {
      notes.push('Supply data incomplete');
      return 'HEALTHY';
    }

    const floatRatio = p.circulatingSupply / p.totalSupply;

    if (floatRatio < 0.10) {
      notes.push(`Float ${(floatRatio * 100).toFixed(1)}% — DANGEROUS: extreme dilution ahead`);
      return 'DANGEROUS';
    }
    if (floatRatio < 0.25) {
      notes.push(`Float ${(floatRatio * 100).toFixed(1)}% — LOW: significant supply overhang`);
      return 'LOW';
    }
    notes.push(`Float ${(floatRatio * 100).toFixed(1)}% — healthy circulation`);
    return 'HEALTHY';
  }

  private assessEmission(p: ProjectProfile, notes: string[]): number {
    if (p.totalSupply <= 0 || p.circulatingSupply <= 0) return 0.3;

    const floatRatio = p.circulatingSupply / p.totalSupply;
    const remainingToEmit = 1 - floatRatio;

    // If max supply exists, check if total supply == max supply
    const hasMaxCap = p.maxSupply && p.maxSupply > 0;
    const isInflationary = !hasMaxCap || (p.maxSupply! > p.totalSupply * 1.01);

    let risk = 0;

    // High remaining emission
    if (remainingToEmit > 0.7) {
      risk += 0.4;
      notes.push(`${(remainingToEmit * 100).toFixed(0)}% of supply still locked — heavy emission ahead`);
    } else if (remainingToEmit > 0.4) {
      risk += 0.2;
    }

    // Inflationary token
    if (isInflationary) {
      risk += 0.2;
      notes.push('Token is inflationary (no hard cap or max > total)');
    }

    // If insiders hold a lot
    if (p.insiderAllocation && p.insiderAllocation > 0.40) {
      risk += 0.2;
      notes.push(`Insider allocation ${(p.insiderAllocation * 100).toFixed(0)}% — concentrated ownership`);
    }

    return Math.min(1, Math.round(risk * 100) / 100);
  }

  private assessUtility(p: ProjectProfile, notes: string[]): number {
    let score = 0.3; // Base

    // Real usage indicators
    if (p.dailyActiveUsers && p.dailyActiveUsers > 10000) {
      score += 0.2;
      notes.push(`${(p.dailyActiveUsers / 1000).toFixed(0)}K DAU — meaningful usage`);
    }

    if (p.tvl && p.tvl > 100e6) {
      score += 0.2;
      notes.push(`TVL $${(p.tvl / 1e6).toFixed(0)}M — capital locked`);
    } else if (p.tvl && p.tvl > 10e6) {
      score += 0.1;
    }

    if (p.revenue30d && p.revenue30d > 1e6) {
      score += 0.2;
      notes.push(`Revenue $${(p.revenue30d / 1e6).toFixed(1)}M/30d — real cashflow`);
    } else if (p.revenue30d && p.revenue30d > 100000) {
      score += 0.1;
    }

    if (p.transactionCount30d && p.transactionCount30d > 1e6) {
      score += 0.1;
    }

    return Math.min(1, Math.round(score * 100) / 100);
  }

  private assessUnlockBasic(p: ProjectProfile, notes: string[]): 'LOW' | 'MEDIUM' | 'HIGH' {
    if (!p.nextUnlockDate || !p.nextUnlockPercent) return 'LOW';

    const daysUntil = (new Date(p.nextUnlockDate).getTime() - Date.now()) / 86400000;
    const pct = p.nextUnlockPercent;

    if (pct > 5 && daysUntil < 7) {
      notes.push(`URGENT: ${pct}% unlock in ${Math.round(daysUntil)} days`);
      return 'HIGH';
    }
    if (pct > 3 && daysUntil < 14) {
      notes.push(`Upcoming unlock: ${pct}% in ${Math.round(daysUntil)} days`);
      return 'MEDIUM';
    }
    if (pct > 5 && daysUntil < 30) {
      notes.push(`Large unlock: ${pct}% in ${Math.round(daysUntil)} days`);
      return 'MEDIUM';
    }
    return 'LOW';
  }
}

export const tokenomicsEngine = new TokenomicsEngine();
