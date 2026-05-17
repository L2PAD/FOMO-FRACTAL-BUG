/**
 * Launch Structure Service
 *
 * Evaluates launch quality, distribution, market maker risk, dump risk.
 * Bad distribution → dump.
 * Low float → volatile.
 * MM risk → fake support.
 */

import type { LaunchAssessment, ProjectProfile, QualityLevel } from '../types/project-intelligence.types.js';

class LaunchStructureService {
  assess(profile: ProjectProfile): LaunchAssessment {
    const notes: string[] = [];

    // 1. Launch Quality
    const launchQuality = this.assessLaunchQuality(profile, notes);

    // 2. Distribution Quality
    const distributionQuality = this.assessDistribution(profile, notes);

    // 3. Market Maker Risk
    const mmRisk = this.assessMmRisk(profile, notes);

    // 4. Dump Risk
    const dumpRisk = this.assessDumpRisk(profile, notes);

    // Fair launch flag
    const fairLaunch = profile.launchType === 'fair_launch' || profile.launchType === 'airdrop';

    // Verdict
    const avgScore = (launchQuality + distributionQuality + (1 - mmRisk) + (1 - dumpRisk)) / 4;
    const verdict: QualityLevel = avgScore >= 0.65 ? 'STRONG'
      : avgScore >= 0.40 ? 'MID'
      : 'WEAK';

    return {
      launchQuality: Math.round(launchQuality * 100) / 100,
      distributionQuality: Math.round(distributionQuality * 100) / 100,
      mmRisk: Math.round(mmRisk * 100) / 100,
      dumpRisk: Math.round(dumpRisk * 100) / 100,
      fairLaunch,
      verdict,
      notes,
    };
  }

  private assessLaunchQuality(p: ProjectProfile, notes: string[]): number {
    let score = 0.5;

    switch (p.launchType) {
      case 'fair_launch':
        score = 0.85;
        notes.push('Fair launch — no insider advantage, community-first');
        break;
      case 'airdrop':
        score = 0.70;
        notes.push('Airdrop distribution — broad but may create sell pressure');
        break;
      case 'ido':
        score = 0.55;
        notes.push('IDO launch — public sale, moderate distribution');
        break;
      case 'ico':
        score = 0.45;
        notes.push('ICO — pre-sale heavy, insider allocation likely');
        break;
      case 'vc_backed':
        score = 0.40;
        notes.push('VC-backed launch — insider-heavy, unlock schedule critical');
        break;
      default:
        notes.push('Launch type unknown');
    }

    // Initial float adjustment
    if (p.initialFloat !== undefined) {
      if (p.initialFloat >= 0.50) {
        score = Math.min(1, score + 0.10);
        notes.push(`Initial float ${(p.initialFloat * 100).toFixed(0)}% — healthy circulation at launch`);
      } else if (p.initialFloat <= 0.10) {
        score = Math.max(0, score - 0.20);
        notes.push(`Initial float ${(p.initialFloat * 100).toFixed(0)}% — extremely low, heavy volatility risk`);
      } else if (p.initialFloat <= 0.20) {
        score = Math.max(0, score - 0.10);
        notes.push(`Initial float ${(p.initialFloat * 100).toFixed(0)}% — low float, manipulation risk`);
      }
    }

    return score;
  }

  private assessDistribution(p: ProjectProfile, notes: string[]): number {
    let score = 0.5;

    const insiderAlloc = p.insiderAllocation ?? 0;

    // Distribution based on insider allocation
    if (insiderAlloc <= 0.15) {
      score = 0.90;
      notes.push('Excellent distribution — low insider concentration');
    } else if (insiderAlloc <= 0.30) {
      score = 0.65;
    } else if (insiderAlloc <= 0.50) {
      score = 0.35;
      notes.push('Poor distribution — high insider concentration');
    } else {
      score = 0.15;
      notes.push('Terrible distribution — insiders control majority of supply');
    }

    // Fair launch boost
    if (p.launchType === 'fair_launch') {
      score = Math.min(1, score + 0.15);
    }

    return score;
  }

  private assessMmRisk(p: ProjectProfile, notes: string[]): number {
    let risk = 0.3; // Default (moderate unknown)

    if (p.mmPresent === true) {
      risk = 0.55;
      notes.push('Market maker present — potential for artificial price support');
    } else if (p.mmPresent === false) {
      risk = 0.15;
    }

    // Low float + VC = high MM risk
    const floatRatio = p.totalSupply > 0 ? p.circulatingSupply / p.totalSupply : 0.5;
    if (floatRatio < 0.15 && p.launchType === 'vc_backed') {
      risk = Math.min(1, risk + 0.25);
      notes.push('Low float + VC-backed → high probability of coordinated price management');
    }

    return risk;
  }

  private assessDumpRisk(p: ProjectProfile, notes: string[]): number {
    let risk = 0.2;

    // Insider allocation
    const insiderAlloc = p.insiderAllocation ?? 0;
    if (insiderAlloc >= 0.50) risk += 0.30;
    else if (insiderAlloc >= 0.35) risk += 0.15;

    // Float ratio
    const floatRatio = p.totalSupply > 0 ? p.circulatingSupply / p.totalSupply : 0.5;
    if (floatRatio < 0.10) {
      risk += 0.20;
      notes.push('Very low float → unlocks will create massive sell pressure');
    } else if (floatRatio < 0.20) {
      risk += 0.10;
    }

    // Upcoming unlock
    if (p.nextUnlockDate && p.nextUnlockPercent) {
      const days = (new Date(p.nextUnlockDate).getTime() - Date.now()) / 86400000;
      if (days < 14 && p.nextUnlockPercent > 5) {
        risk += 0.20;
        notes.push(`Imminent large unlock (${p.nextUnlockPercent}% in ${Math.round(days)}d) → high dump probability`);
      }
    }

    // Airdrop dump risk
    if (p.launchType === 'airdrop') {
      risk += 0.10;
      notes.push('Airdrop recipients tend to sell early — initial dump risk');
    }

    return Math.min(1, risk);
  }
}

export const launchStructureService = new LaunchStructureService();
