/**
 * Unlock Pressure Service
 *
 * Dedicated unlock risk analysis — direct edge on price markets.
 *
 * Rules:
 *   unlock > 5% supply → HIGH RISK
 *   unlock < 7 days → IMMEDIATE RISK
 *   insider heavy → DUMP RISK
 *   vesting almost done → supply flood incoming
 */

import type { UnlockPressure, ProjectProfile } from '../types/project-intelligence.types.js';

class UnlockPressureService {
  assess(profile: ProjectProfile): UnlockPressure {
    const notes: string[] = [];

    // Days until next unlock
    const nextUnlockDays = profile.nextUnlockDate
      ? Math.max(0, Math.round((new Date(profile.nextUnlockDate).getTime() - Date.now()) / 86400000))
      : null;

    // Unlock percent of total supply
    const unlockPercent = profile.nextUnlockPercent ?? 0;

    // Insider share
    const insiderShare = profile.insiderAllocation ?? 0;

    // Vesting months left
    const vestingMonthsLeft = profile.vestingEndDate
      ? Math.max(0, Math.round((new Date(profile.vestingEndDate).getTime() - Date.now()) / (30 * 86400000)))
      : 0;

    // ── Impact Score Calculation ──
    let impactScore = 0;

    // Unlock size impact
    if (unlockPercent >= 10) {
      impactScore += 0.40;
      notes.push(`Massive unlock: ${unlockPercent}% of total supply`);
    } else if (unlockPercent >= 5) {
      impactScore += 0.30;
      notes.push(`Large unlock: ${unlockPercent}% of total supply`);
    } else if (unlockPercent >= 2) {
      impactScore += 0.15;
      notes.push(`Moderate unlock: ${unlockPercent}% of total supply`);
    } else if (unlockPercent > 0) {
      impactScore += 0.05;
    }

    // Timing urgency
    if (nextUnlockDays !== null) {
      if (nextUnlockDays <= 3) {
        impactScore += 0.30;
        notes.push(`IMMINENT: unlock in ${nextUnlockDays} days`);
      } else if (nextUnlockDays <= 7) {
        impactScore += 0.20;
        notes.push(`NEAR: unlock in ${nextUnlockDays} days`);
      } else if (nextUnlockDays <= 14) {
        impactScore += 0.10;
        notes.push(`Upcoming unlock in ${nextUnlockDays} days`);
      } else if (nextUnlockDays <= 30) {
        impactScore += 0.05;
      }
    }

    // Insider concentration
    if (insiderShare >= 0.50) {
      impactScore += 0.20;
      notes.push(`Insider allocation ${(insiderShare * 100).toFixed(0)}% — heavy concentration, dump risk HIGH`);
    } else if (insiderShare >= 0.35) {
      impactScore += 0.10;
      notes.push(`Insider allocation ${(insiderShare * 100).toFixed(0)}% — moderate concentration`);
    }

    // Vesting ending soon = supply flood
    if (vestingMonthsLeft > 0 && vestingMonthsLeft <= 3) {
      impactScore += 0.10;
      notes.push(`Vesting ends in ${vestingMonthsLeft} months — full supply unlocking soon`);
    }

    // Float ratio check (circulating vs total)
    if (profile.totalSupply > 0 && profile.circulatingSupply > 0) {
      const floatRatio = profile.circulatingSupply / profile.totalSupply;
      if (floatRatio < 0.15) {
        impactScore += 0.10;
        notes.push(`Only ${(floatRatio * 100).toFixed(1)}% circulating — unlocks will dramatically increase supply`);
      }
    }

    impactScore = Math.min(1, Math.round(impactScore * 100) / 100);

    // Risk level
    const riskLevel = impactScore >= 0.60 ? 'HIGH' as const
      : impactScore >= 0.30 ? 'MEDIUM' as const
      : 'LOW' as const;

    if (impactScore < 0.1 && !profile.nextUnlockDate) {
      notes.push('No upcoming unlock data available');
    }

    return {
      nextUnlockDays,
      unlockPercent,
      unlockImpactScore: impactScore,
      insiderShare,
      vestingMonthsLeft,
      riskLevel,
      notes,
    };
  }
}

export const unlockPressureService = new UnlockPressureService();
