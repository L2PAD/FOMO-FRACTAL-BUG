/**
 * Project Thesis Engine
 *
 * Synthesizes all project intel layers into:
 *   - bull case
 *   - bear case
 *   - what market misses
 *   - key risks
 *   - overall verdict
 *
 * This is the final reasoning layer that transforms numeric scores
 * into actionable investment intelligence.
 */

import type {
  ProjectThesis, ProjectProfile, ProjectVerdict,
  TokenomicsAssessment, UnlockPressure, ValuationAssessment,
  TeamFundAssessment, LaunchAssessment,
} from '../types/project-intelligence.types.js';

interface ThesisInput {
  profile: ProjectProfile;
  tokenomics: TokenomicsAssessment;
  unlock: UnlockPressure;
  valuation: ValuationAssessment;
  teamFund: TeamFundAssessment;
  launch: LaunchAssessment;
}

class ProjectThesisEngine {
  synthesize(input: ThesisInput): ProjectThesis {
    const { profile, tokenomics, unlock, valuation, teamFund, launch } = input;

    const bullCase = this.buildBullCase(input);
    const bearCase = this.buildBearCase(input);
    const whatMarketMisses = this.findMarketGaps(input);
    const keyRisks = this.extractKeyRisks(input);
    const overallScore = this.computeOverallScore(input);

    const projectVerdict: ProjectVerdict = overallScore >= 0.65 ? 'STRONG'
      : overallScore >= 0.40 ? 'MIXED'
      : 'WEAK';

    return {
      bullCase,
      bearCase,
      projectVerdict,
      whatMarketMisses,
      keyRisks,
      overallScore: Math.round(overallScore * 100) / 100,
    };
  }

  private buildBullCase(input: ThesisInput): string[] {
    const { profile, tokenomics, valuation, teamFund, launch } = input;
    const points: string[] = [];

    // Valuation
    if (valuation.valuation === 'CHEAP') {
      points.push(`Undervalued at current FDV — potential for significant re-rating`);
    }

    // Strong team
    if (teamFund.verdict === 'STRONG') {
      points.push(`Strong team with proven execution + top-tier fund backing`);
    }

    // Real traction
    if (tokenomics.utilityScore >= 0.6) {
      points.push(`Real product usage and traction — not just narrative`);
    }

    // Revenue
    if (profile.revenue30d && profile.revenue30d > 1e6) {
      points.push(`Generating real revenue ($${(profile.revenue30d / 1e6).toFixed(1)}M/month)`);
    }

    // TVL
    if (profile.tvl && profile.tvl > 100e6) {
      points.push(`Significant capital locked ($${(profile.tvl / 1e6).toFixed(0)}M TVL)`);
    }

    // Good distribution
    if (launch.distributionQuality >= 0.70) {
      points.push(`Healthy token distribution — low insider concentration`);
    }

    // Fair launch
    if (launch.fairLaunch) {
      points.push(`Fair launch / airdrop — community-first distribution`);
    }

    // Low FDV
    if (tokenomics.fdvLevel === 'LOW') {
      points.push(`Low FDV relative to sector — room for growth`);
    }

    // Narrative tailwind
    if (valuation.narrativePremium > 0 && valuation.valuation !== 'INSANE') {
      points.push(`Active narrative tailwind (${profile.sector || profile.narrative || 'crypto'})`);
    }

    if (points.length === 0) {
      points.push('Limited bullish factors identified');
    }

    return points.slice(0, 5);
  }

  private buildBearCase(input: ThesisInput): string[] {
    const { profile, tokenomics, unlock, valuation, teamFund, launch } = input;
    const points: string[] = [];

    // Overvalued
    if (valuation.valuation === 'INSANE') {
      points.push(`Extremely overvalued — FDV unsustainable at current metrics`);
    } else if (valuation.valuation === 'EXPENSIVE') {
      points.push(`Expensive valuation — limited upside, significant downside risk`);
    }

    // Unlock pressure
    if (unlock.riskLevel === 'HIGH') {
      points.push(`Major unlock pressure: ${unlock.unlockPercent}% in ${unlock.nextUnlockDays ?? '?'} days`);
    }

    // Weak team
    if (teamFund.verdict === 'WEAK') {
      points.push(`Weak/unproven team — execution risk is high`);
    }

    // High insider risk
    if (teamFund.insiderRisk >= 0.60) {
      points.push(`Heavy insider allocation — concentrated sell pressure ahead`);
    }

    // Bad tokenomics
    if (tokenomics.floatQuality === 'DANGEROUS') {
      points.push(`Dangerously low float — massive dilution coming`);
    }

    // No real usage
    if (tokenomics.utilityScore < 0.3) {
      points.push(`No real product usage — price driven purely by speculation`);
    }

    // High emission
    if (tokenomics.emissionRisk > 0.6) {
      points.push(`High token emission — continuous sell pressure from inflation`);
    }

    // Dump risk
    if (launch.dumpRisk >= 0.60) {
      points.push(`High dump risk from distribution structure`);
    }

    // MM manipulation
    if (launch.mmRisk >= 0.60) {
      points.push(`Market maker manipulation risk — artificial price support may collapse`);
    }

    if (points.length === 0) {
      points.push('Limited bearish factors identified');
    }

    return points.slice(0, 5);
  }

  private findMarketGaps(input: ThesisInput): string[] {
    const { tokenomics, unlock, valuation, teamFund, launch } = input;
    const gaps: string[] = [];

    // Unlock not priced in
    if (unlock.riskLevel === 'HIGH' && unlock.nextUnlockDays !== null && unlock.nextUnlockDays > 3) {
      gaps.push(`Upcoming ${unlock.unlockPercent}% unlock in ${unlock.nextUnlockDays} days — likely NOT priced in yet`);
    }

    // FDV/MC disconnect
    if (valuation.valuation === 'INSANE' && tokenomics.floatQuality === 'DANGEROUS') {
      gaps.push(`Market cap misleading — FDV reveals massive future dilution`);
    }

    // Hype vs fundamentals disconnect
    if (valuation.narrativePremium >= 0.30 && tokenomics.utilityScore < 0.3) {
      gaps.push(`Narrative premium (${ (valuation.narrativePremium * 100).toFixed(0) }%) with no real usage — correction likely`);
    }

    // Strong project undervalued
    if (valuation.valuation === 'CHEAP' && teamFund.verdict === 'STRONG') {
      gaps.push(`Quality project trading below fair value — market hasn't recognized fundamentals`);
    }

    // Insider sell pressure not visible
    if (teamFund.insiderRisk >= 0.50 && tokenomics.floatQuality !== 'HEALTHY') {
      gaps.push(`Insider sell pressure building but not yet visible in order flow`);
    }

    // Good distribution not rewarded
    if (launch.distributionQuality >= 0.80 && valuation.valuation !== 'EXPENSIVE') {
      gaps.push(`Healthy distribution often leads to more sustainable price appreciation`);
    }

    return gaps.slice(0, 4);
  }

  private extractKeyRisks(input: ThesisInput): string[] {
    const { tokenomics, unlock, valuation, teamFund, launch } = input;
    const risks: string[] = [];

    if (unlock.riskLevel === 'HIGH') risks.push('Imminent token unlock');
    if (valuation.valuation === 'INSANE') risks.push('Extreme overvaluation');
    if (tokenomics.floatQuality === 'DANGEROUS') risks.push('Dangerous float ratio');
    if (teamFund.insiderRisk >= 0.60) risks.push('Insider dump risk');
    if (launch.mmRisk >= 0.60) risks.push('Market maker dependency');
    if (tokenomics.emissionRisk > 0.6) risks.push('High inflation/emission');
    if (teamFund.verdict === 'WEAK') risks.push('Unproven team');
    if (launch.dumpRisk >= 0.60) risks.push('Structural dump risk');

    return risks.slice(0, 5);
  }

  private computeOverallScore(input: ThesisInput): number {
    const { tokenomics, unlock, valuation, teamFund, launch } = input;

    // Score components (higher = better project)
    const tokenScore = tokenomics.verdict === 'STRONG' ? 0.85 : tokenomics.verdict === 'MID' ? 0.50 : 0.20;
    const unlockSafe = 1 - unlock.unlockImpactScore;
    const valScore = valuation.valuation === 'CHEAP' ? 0.90
      : valuation.valuation === 'FAIR' ? 0.65
      : valuation.valuation === 'EXPENSIVE' ? 0.35
      : 0.10;
    const teamScore = teamFund.verdict === 'STRONG' ? 0.85 : teamFund.verdict === 'MID' ? 0.50 : 0.20;
    const launchScore = launch.verdict === 'STRONG' ? 0.85 : launch.verdict === 'MID' ? 0.50 : 0.20;

    return (
      tokenScore * 0.25 +
      unlockSafe * 0.20 +
      valScore * 0.25 +
      teamScore * 0.15 +
      launchScore * 0.15
    );
  }
}

export const projectThesisEngine = new ProjectThesisEngine();
