/**
 * Exit Policy Service
 *
 * Many systems know how to enter. Few know how to exit.
 *
 * HOLD / TRIM / REDUCE / EXIT
 */

import type { ExitPlan, ExitAction } from '../types/exit.types.js';

interface ExitInput {
  edge: number;
  edgeCompression: number;
  confidence: number;
  repricingState: string;
  socialSaturation: number;
  socialLifecycle: string | null;
  projectVerdict: string | null;
  fairProb: number;
  marketProb: number;
  alignment: number;
}

class ExitPolicyService {
  assess(input: ExitInput): ExitPlan {
    const reasons: string[] = [];
    let exitScore = 0; // Higher = more reasons to exit

    // 1. Edge compression
    if (input.edgeCompression > 0.85) {
      exitScore += 0.35;
      reasons.push('Edge almost fully compressed — thesis largely realized');
    } else if (input.edgeCompression > 0.60) {
      exitScore += 0.20;
      reasons.push('Significant edge compression — consider taking profits');
    }

    // 2. Fair value reached/exceeded
    const edgeSign = input.fairProb > input.marketProb ? 1 : -1;
    const marketPastFair = edgeSign > 0
      ? input.marketProb >= input.fairProb
      : input.marketProb <= input.fairProb;
    if (marketPastFair) {
      exitScore += 0.25;
      reasons.push('Market has reached or exceeded fair value — edge is gone');
    }

    // 3. Narrative overheated
    if (input.socialSaturation > 0.75) {
      exitScore += 0.15;
      reasons.push('Narrative fully saturated — crowd positioning creates reversal risk');
    }
    if (input.socialLifecycle === 'FADING' || input.socialLifecycle === 'DORMANT') {
      exitScore += 0.10;
      reasons.push(`Narrative ${input.socialLifecycle} — support fading`);
    }

    // 4. Repricing state
    if (input.repricingState === 'overheated') {
      exitScore += 0.15;
      reasons.push('Overheated repricing — risk of snap reversal');
    } else if (input.repricingState === 'crowded') {
      exitScore += 0.10;
      reasons.push('Crowded market — diminishing returns');
    }

    // 5. Confidence dropped
    if (input.confidence < 0.3) {
      exitScore += 0.10;
      reasons.push('Confidence dropped below threshold');
    }

    // 6. Project contradiction
    if (input.projectVerdict === 'WEAK' && input.edge > 0) {
      exitScore += 0.05;
      reasons.push('Weak project verdict contradicts bullish position');
    }

    // 7. Alignment dropped
    if (input.alignment < 0.3) {
      exitScore += 0.08;
      reasons.push('Module alignment low — signals contradicting');
    }

    exitScore = Math.min(1, exitScore);

    // Determine action
    let action: ExitAction;
    let exitConfidence: number;

    if (exitScore >= 0.65) {
      action = 'EXIT';
      exitConfidence = Math.min(0.95, exitScore);
    } else if (exitScore >= 0.45) {
      action = 'REDUCE';
      exitConfidence = 0.60 + exitScore * 0.2;
    } else if (exitScore >= 0.25) {
      action = 'TRIM';
      exitConfidence = 0.50 + exitScore * 0.3;
    } else {
      action = 'HOLD';
      exitConfidence = 0.70 - exitScore * 0.3;
      if (reasons.length === 0) {
        reasons.push('Thesis intact, edge alive — continue holding');
      }
    }

    return {
      action,
      confidence: Math.round(exitConfidence * 100) / 100,
      reasons,
    };
  }
}

export const exitPolicyService = new ExitPolicyService();
