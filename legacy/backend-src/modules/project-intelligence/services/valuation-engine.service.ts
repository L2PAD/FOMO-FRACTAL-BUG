/**
 * Valuation Engine
 *
 * Determines if a project is CHEAP / FAIR / EXPENSIVE / INSANE
 * based on FDV vs traction, revenue, TVL, comparable projects.
 *
 * Expected range gives low/base/high probability-weighted price targets.
 */

import type { ValuationAssessment, ProjectProfile, ValuationLevel } from '../types/project-intelligence.types.js';

// Sector FDV/Revenue multiples (annual)
const SECTOR_REVENUE_MULTIPLES: Record<string, { cheap: number; fair: number; expensive: number }> = {
  defi:    { cheap: 15,  fair: 40,  expensive: 100 },
  l1:      { cheap: 30,  fair: 80,  expensive: 200 },
  l2:      { cheap: 25,  fair: 60,  expensive: 150 },
  gaming:  { cheap: 20,  fair: 50,  expensive: 120 },
  infra:   { cheap: 30,  fair: 70,  expensive: 180 },
  ai:      { cheap: 40,  fair: 100, expensive: 250 },
  meme:    { cheap: 0,   fair: 0,   expensive: 0  },  // No revenue metric for meme
  default: { cheap: 20,  fair: 50,  expensive: 130 },
};

// Sector FDV/TVL benchmarks
const SECTOR_TVL_MULTIPLES: Record<string, { cheap: number; fair: number; expensive: number }> = {
  defi:    { cheap: 0.5, fair: 2,   expensive: 5  },
  l1:      { cheap: 2,   fair: 8,   expensive: 20 },
  l2:      { cheap: 1,   fair: 5,   expensive: 15 },
  default: { cheap: 1,   fair: 4,   expensive: 12 },
};

class ValuationEngine {
  assess(profile: ProjectProfile): ValuationAssessment {
    const notes: string[] = [];
    const signals: { level: ValuationLevel; weight: number }[] = [];

    const sector = profile.sector || 'default';

    // 1. FDV/Revenue analysis
    const fdvRevenue = this.assessFdvRevenue(profile, sector, notes, signals);

    // 2. FDV/TVL analysis
    const fdvTvl = this.assessFdvTvl(profile, sector, notes, signals);

    // 3. FDV/MC ratio (float premium)
    this.assessFloatPremium(profile, notes, signals);

    // 4. Narrative premium
    const narrativePremium = this.assessNarrativePremium(profile, notes, signals);

    // 5. Sector-relative FDV
    this.assessSectorRelative(profile, sector, notes, signals);

    // Aggregate valuation
    const valuation = this.aggregateValuation(signals, notes);

    // Expected range
    const expectedRange = this.computeExpectedRange(profile, valuation);

    // Confidence (more data = more confidence)
    const dataPoints = [
      profile.revenue30d ? 1 : 0,
      profile.tvl ? 1 : 0,
      profile.dailyActiveUsers ? 1 : 0,
      profile.totalFundingUsd ? 1 : 0,
      profile.dailyVolume ? 1 : 0,
    ].reduce((a, b) => a + b, 0);
    const confidence = Math.min(0.95, 0.30 + dataPoints * 0.13);

    return {
      valuation,
      expectedRange,
      fdvToRevenue: fdvRevenue,
      fdvToTvl: fdvTvl,
      narrativePremium,
      confidence: Math.round(confidence * 100) / 100,
      notes,
    };
  }

  private assessFdvRevenue(
    p: ProjectProfile, sector: string,
    notes: string[], signals: { level: ValuationLevel; weight: number }[],
  ): number | null {
    if (!p.revenue30d || p.revenue30d <= 0 || p.fdv <= 0) return null;

    const annualRevenue = p.revenue30d * 12;
    const ratio = p.fdv / annualRevenue;
    const bench = SECTOR_REVENUE_MULTIPLES[sector] || SECTOR_REVENUE_MULTIPLES['default'];

    if (bench.cheap === 0) return ratio; // Meme — skip revenue analysis

    if (ratio <= bench.cheap) {
      notes.push(`FDV/Revenue ${ratio.toFixed(0)}x — CHEAP for ${sector} (fair: ${bench.fair}x)`);
      signals.push({ level: 'CHEAP', weight: 0.35 });
    } else if (ratio <= bench.fair) {
      notes.push(`FDV/Revenue ${ratio.toFixed(0)}x — FAIR for ${sector}`);
      signals.push({ level: 'FAIR', weight: 0.35 });
    } else if (ratio <= bench.expensive) {
      notes.push(`FDV/Revenue ${ratio.toFixed(0)}x — EXPENSIVE for ${sector}`);
      signals.push({ level: 'EXPENSIVE', weight: 0.35 });
    } else {
      notes.push(`FDV/Revenue ${ratio.toFixed(0)}x — INSANE for ${sector} (threshold: ${bench.expensive}x)`);
      signals.push({ level: 'INSANE', weight: 0.35 });
    }

    return Math.round(ratio * 10) / 10;
  }

  private assessFdvTvl(
    p: ProjectProfile, sector: string,
    notes: string[], signals: { level: ValuationLevel; weight: number }[],
  ): number | null {
    if (!p.tvl || p.tvl <= 0 || p.fdv <= 0) return null;

    const ratio = p.fdv / p.tvl;
    const bench = SECTOR_TVL_MULTIPLES[sector] || SECTOR_TVL_MULTIPLES['default'];

    if (ratio <= bench.cheap) {
      notes.push(`FDV/TVL ${ratio.toFixed(1)}x — CHEAP (capital efficiency high)`);
      signals.push({ level: 'CHEAP', weight: 0.25 });
    } else if (ratio <= bench.fair) {
      notes.push(`FDV/TVL ${ratio.toFixed(1)}x — FAIR`);
      signals.push({ level: 'FAIR', weight: 0.25 });
    } else if (ratio <= bench.expensive) {
      notes.push(`FDV/TVL ${ratio.toFixed(1)}x — EXPENSIVE`);
      signals.push({ level: 'EXPENSIVE', weight: 0.25 });
    } else {
      notes.push(`FDV/TVL ${ratio.toFixed(1)}x — INSANE (${sector} threshold: ${bench.expensive}x)`);
      signals.push({ level: 'INSANE', weight: 0.25 });
    }

    return Math.round(ratio * 10) / 10;
  }

  private assessFloatPremium(
    p: ProjectProfile,
    notes: string[], signals: { level: ValuationLevel; weight: number }[],
  ): void {
    if (p.fdv <= 0 || p.marketCap <= 0) return;

    const fdvMcRatio = p.fdv / p.marketCap;

    if (fdvMcRatio >= 10) {
      notes.push(`FDV/MC ratio ${fdvMcRatio.toFixed(1)}x — extreme dilution ahead, price overstated`);
      signals.push({ level: 'INSANE', weight: 0.20 });
    } else if (fdvMcRatio >= 5) {
      notes.push(`FDV/MC ratio ${fdvMcRatio.toFixed(1)}x — significant supply overhang`);
      signals.push({ level: 'EXPENSIVE', weight: 0.20 });
    } else if (fdvMcRatio >= 2) {
      notes.push(`FDV/MC ratio ${fdvMcRatio.toFixed(1)}x — moderate overhang`);
      signals.push({ level: 'FAIR', weight: 0.15 });
    }
  }

  private assessNarrativePremium(
    p: ProjectProfile,
    notes: string[], signals: { level: ValuationLevel; weight: number }[],
  ): number {
    const hotNarratives = new Set(['ai', 'rwa', 'modular', 'restaking', 'depin', 'meme']);
    const sector = p.sector || '';
    const narrative = p.narrative || '';

    let premium = 0;

    if (hotNarratives.has(sector) || hotNarratives.has(narrative.toLowerCase())) {
      premium = 0.30;
      notes.push(`Active narrative premium (${sector || narrative}) — price includes hype`);
    }

    // Meme premium
    if (sector === 'meme') {
      premium = 0.50;
      notes.push('Meme token — price is pure narrative, no fundamental floor');
      signals.push({ level: 'EXPENSIVE', weight: 0.15 });
    }

    return premium;
  }

  private assessSectorRelative(
    p: ProjectProfile, sector: string,
    notes: string[], signals: { level: ValuationLevel; weight: number }[],
  ): void {
    // Very rough sector FDV brackets
    const sectorMedians: Record<string, number> = {
      l1: 8e9, l2: 3e9, defi: 800e6, gaming: 400e6,
      ai: 2e9, meme: 200e6, infra: 1.5e9, rwa: 600e6,
    };

    const median = sectorMedians[sector];
    if (!median || p.fdv <= 0) return;

    const ratio = p.fdv / median;
    if (ratio >= 5) {
      signals.push({ level: 'EXPENSIVE', weight: 0.15 });
    } else if (ratio <= 0.2) {
      signals.push({ level: 'CHEAP', weight: 0.15 });
    }
  }

  private aggregateValuation(
    signals: { level: ValuationLevel; weight: number }[],
    notes: string[],
  ): ValuationLevel {
    if (signals.length === 0) {
      notes.push('Insufficient data for valuation — defaulting to FAIR');
      return 'FAIR';
    }

    const levelScores: Record<ValuationLevel, number> = {
      'CHEAP': 0, 'FAIR': 1, 'EXPENSIVE': 2, 'INSANE': 3,
    };

    let weighted = 0;
    let totalWeight = 0;

    for (const s of signals) {
      weighted += levelScores[s.level] * s.weight;
      totalWeight += s.weight;
    }

    const avg = totalWeight > 0 ? weighted / totalWeight : 1;

    if (avg >= 2.5) return 'INSANE';
    if (avg >= 1.5) return 'EXPENSIVE';
    if (avg >= 0.5) return 'FAIR';
    return 'CHEAP';
  }

  private computeExpectedRange(
    p: ProjectProfile,
    valuation: ValuationLevel,
  ): { low: number; base: number; high: number } {
    const price = p.currentPrice || 1;

    // Multipliers based on valuation
    const ranges: Record<ValuationLevel, { low: number; base: number; high: number }> = {
      'CHEAP':     { low: 0.85, base: 1.5, high: 3.0 },
      'FAIR':      { low: 0.70, base: 1.0, high: 1.8 },
      'EXPENSIVE': { low: 0.50, base: 0.8, high: 1.3 },
      'INSANE':    { low: 0.30, base: 0.5, high: 1.0 },
    };

    const r = ranges[valuation];
    return {
      low: Math.round(price * r.low * 100) / 100,
      base: Math.round(price * r.base * 100) / 100,
      high: Math.round(price * r.high * 100) / 100,
    };
  }
}

export const valuationEngine = new ValuationEngine();
