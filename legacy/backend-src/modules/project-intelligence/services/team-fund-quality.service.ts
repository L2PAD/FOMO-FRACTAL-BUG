/**
 * Team & Fund Quality Service
 *
 * Evaluates team reputation, fund quality, insider risk.
 * Strong team + top funds → higher conviction.
 * No-name team + insider heavy → dump risk.
 */

import type { TeamFundAssessment, ProjectProfile, QualityLevel } from '../types/project-intelligence.types.js';

// Known top-tier funds (increase confidence)
const TOP_FUNDS = new Set([
  'a16z', 'andreessen horowitz', 'paradigm', 'sequoia', 'polychain',
  'multicoin', 'dragonfly', 'pantera', 'galaxy digital', 'coinbase ventures',
  'binance labs', 'framework ventures', 'electric capital', 'placeholder',
  'variant', 'haun ventures', 'delphi ventures', 'jump crypto', 'alameda',
  'three arrows', '3ac', 'wintermute', 'dwd', 'kkr', 'blackrock',
  'fidelity', 'grayscale', 'vaneck', 'ark invest',
]);

// Funding amount benchmarks
const FUNDING_TIERS = {
  mega:   100e6,  // $100M+ → huge war chest
  large:  30e6,   // $30M+ → well funded
  medium: 10e6,   // $10M+ → adequate
  small:  3e6,    // $3M+ → lean
};

class TeamFundQualityService {
  assess(profile: ProjectProfile): TeamFundAssessment {
    const notes: string[] = [];

    // 1. Team Score
    const teamScore = this.assessTeam(profile, notes);

    // 2. Fund Score
    const fundScore = this.assessFunds(profile, notes);

    // 3. Insider Risk
    const insiderRisk = this.assessInsiderRisk(profile, notes);

    // 4. Execution History
    const executionHistory = profile.teamReputation || this.inferExecution(profile, notes);

    // 5. Verdict
    const combined = teamScore * 0.35 + fundScore * 0.30 + (1 - insiderRisk) * 0.20 +
      (executionHistory === 'STRONG' ? 0.15 : executionHistory === 'MID' ? 0.08 : 0);

    const verdict: QualityLevel = combined >= 0.65 ? 'STRONG'
      : combined >= 0.40 ? 'MID'
      : 'WEAK';

    return {
      teamScore: Math.round(teamScore * 100) / 100,
      fundScore: Math.round(fundScore * 100) / 100,
      insiderRisk: Math.round(insiderRisk * 100) / 100,
      executionHistory,
      verdict,
      notes,
    };
  }

  private assessTeam(p: ProjectProfile, notes: string[]): number {
    let score = 0.3; // Base (unknown team)

    if (p.teamReputation === 'STRONG') {
      score = 0.85;
      notes.push('Team has strong reputation and execution track record');
    } else if (p.teamReputation === 'MID') {
      score = 0.55;
      notes.push('Team has moderate reputation');
    } else if (p.teamReputation === 'WEAK') {
      score = 0.15;
      notes.push('Team is weak or unproven — execution risk HIGH');
    }

    // Boost for previous successful projects
    if (p.previousProjects && p.previousProjects.length > 0) {
      score = Math.min(1, score + 0.15);
      notes.push(`Team has prior projects: ${p.previousProjects.join(', ')}`);
    }

    return score;
  }

  private assessFunds(p: ProjectProfile, notes: string[]): number {
    let score = 0.2; // Base (no known funding)

    const funds = p.topFundsInvolved || [];
    const topFundCount = funds.filter(f => TOP_FUNDS.has(f.toLowerCase())).length;

    if (topFundCount >= 3) {
      score += 0.50;
      notes.push(`${topFundCount} top-tier funds invested — strong institutional backing`);
    } else if (topFundCount >= 1) {
      score += 0.30;
      notes.push(`Top fund(s): ${funds.filter(f => TOP_FUNDS.has(f.toLowerCase())).join(', ')}`);
    } else if (funds.length > 0) {
      score += 0.10;
      notes.push(`Funded by: ${funds.slice(0, 3).join(', ')} (no top-tier)`);
    }

    // Funding amount
    const funding = p.totalFundingUsd || 0;
    if (funding >= FUNDING_TIERS.mega) {
      score += 0.20;
      notes.push(`Total funding $${(funding / 1e6).toFixed(0)}M — massive war chest`);
    } else if (funding >= FUNDING_TIERS.large) {
      score += 0.15;
    } else if (funding >= FUNDING_TIERS.medium) {
      score += 0.10;
    } else if (funding >= FUNDING_TIERS.small) {
      score += 0.05;
    }

    return Math.min(1, score);
  }

  private assessInsiderRisk(p: ProjectProfile, notes: string[]): number {
    let risk = 0.2; // Default (moderate unknown)

    const insiderAlloc = p.insiderAllocation ?? 0;

    if (insiderAlloc >= 0.60) {
      risk = 0.90;
      notes.push(`${(insiderAlloc * 100).toFixed(0)}% insider allocation — extreme concentration, HIGH dump risk`);
    } else if (insiderAlloc >= 0.45) {
      risk = 0.70;
      notes.push(`${(insiderAlloc * 100).toFixed(0)}% insider allocation — significant concentration`);
    } else if (insiderAlloc >= 0.30) {
      risk = 0.45;
      notes.push(`${(insiderAlloc * 100).toFixed(0)}% insider allocation — moderate`);
    } else if (insiderAlloc >= 0.15) {
      risk = 0.25;
    } else if (insiderAlloc > 0) {
      risk = 0.10;
      notes.push(`${(insiderAlloc * 100).toFixed(0)}% insider allocation — low, healthy distribution`);
    }

    return risk;
  }

  private inferExecution(p: ProjectProfile, notes: string[]): QualityLevel {
    // Infer from traction
    if (p.dailyActiveUsers && p.dailyActiveUsers > 50000) return 'STRONG';
    if (p.tvl && p.tvl > 500e6) return 'STRONG';
    if (p.revenue30d && p.revenue30d > 5e6) return 'STRONG';
    if (p.dailyActiveUsers && p.dailyActiveUsers > 5000) return 'MID';
    if (p.tvl && p.tvl > 50e6) return 'MID';
    return 'WEAK';
  }
}

export const teamFundQualityService = new TeamFundQualityService();
