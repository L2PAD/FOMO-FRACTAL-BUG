/**
 * Portfolio Adjustment — Stage 7
 *
 * Converts raw portfolio brain numbers into user-facing output:
 *   allowed, capped, blocked, adjustedSize, adjustedSizeFraction, reasons
 *
 * Rounding: 1.0→FULL, 0.5→MEDIUM, 0.25→SMALL, 0.1→TINY, <0.1→NONE
 */
import type { PortfolioAssessment } from '../types/portfolio.types.js';

type SizeLabel = 'FULL' | 'MEDIUM' | 'SMALL' | 'TINY' | 'NONE';

function fractionToSize(fraction: number): SizeLabel {
  if (fraction >= 0.75)  return 'FULL';
  if (fraction >= 0.40)  return 'MEDIUM';
  if (fraction >= 0.20)  return 'SMALL';
  if (fraction >= 0.10)  return 'TINY';
  return 'NONE';
}

export function buildPortfolioAssessment(opts: {
  baseSizeFraction: number;
  correlationPenalty: number;
  correlationBlocked: boolean;
  correlationReason?: string;
  budgetPenalty: number;
  budgetBlocked: boolean;
  budgetReasons: string[];
  maxOverlap: number;
}): PortfolioAssessment {
  const blocked = opts.correlationBlocked || opts.budgetBlocked;
  const reasons: string[] = [];

  if (opts.correlationReason) reasons.push(opts.correlationReason);
  reasons.push(...opts.budgetReasons);

  let adjustedFraction: number;

  if (blocked) {
    adjustedFraction = 0;
  } else {
    adjustedFraction = opts.baseSizeFraction
      * (1 - opts.correlationPenalty)
      * (1 - opts.budgetPenalty);

    adjustedFraction = Math.round(adjustedFraction * 100) / 100;
  }

  const capped = !blocked && adjustedFraction < opts.baseSizeFraction;

  return {
    allowed: !blocked && adjustedFraction >= 0.1,
    capped,
    blocked,
    overlapScore: opts.maxOverlap,
    correlationPenalty: opts.correlationPenalty,
    budgetPenalty: opts.budgetPenalty,
    adjustedSizeFraction: adjustedFraction,
    adjustedSize: fractionToSize(adjustedFraction),
    reasons,
  };
}
