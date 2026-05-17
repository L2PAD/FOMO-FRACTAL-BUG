/**
 * Edge Attribution
 *
 * Understands which intelligence layers contribute to edge (or destroy it).
 * Maps module presence in traces to outcomes.
 */

import type { EdgeAttribution } from '../types/digest.types.js';

interface ReviewData {
  correctness: { correctness: string; edgeRealized: boolean };
  traces: TraceData[];
}

interface TraceData {
  edge: number;
  intelligence?: {
    evidenceDrivers?: number;
    evidenceNoise?: number;
    memoAction?: string;
    pricedInLevel?: number;
  };
  social?: { saturation?: number; lifecycle?: string };
  projectIntel?: { verdict?: string };
  sentiment?: number;
  onchain?: number;
}

class EdgeAttributionService {
  analyze(reviews: ReviewData[]): EdgeAttribution {
    const contributions = { exchange: 0, onchain: 0, sentiment: 0, social: 0, project: 0, intelligence: 0 };
    let total = 0;

    for (const r of reviews) {
      const isCorrect = r.correctness?.correctness === 'CORRECT';
      const bestTrace = r.traces?.[0];
      if (!bestTrace) continue;

      total++;
      const sign = isCorrect ? 1 : -1;
      const edge = Math.abs(bestTrace.edge || 0);

      // Intelligence layer (case intel memo quality)
      const intel = bestTrace.intelligence;
      if (intel) {
        const drivers = intel.evidenceDrivers || 0;
        const noise = intel.evidenceNoise || 0;
        const intelQuality = drivers > noise ? 0.6 : drivers === noise ? 0.3 : 0.1;
        contributions.intelligence += sign * intelQuality * edge;
      }

      // Project layer
      if (bestTrace.projectIntel?.verdict) {
        const pv = bestTrace.projectIntel.verdict;
        const projectSignal = pv === 'STRONG' ? 0.5 : pv === 'WEAK' ? -0.3 : 0.1;
        contributions.project += sign * projectSignal * edge;
      }

      // Social layer
      if (bestTrace.social) {
        const sat = bestTrace.social.saturation || 0;
        const socialSignal = sat < 0.3 ? 0.4 : sat > 0.7 ? -0.2 : 0.1;
        contributions.social += sign * socialSignal * edge;
      }

      // Sentiment
      const sentVal = bestTrace.sentiment || 0;
      if (sentVal !== 0) {
        contributions.sentiment += sign * Math.abs(sentVal) * 0.3 * edge;
      }

      // Exchange / base (always contributes)
      contributions.exchange += sign * 0.3 * edge;

      // On-chain
      const onchainVal = bestTrace.onchain || 0;
      if (onchainVal !== 0) {
        contributions.onchain += sign * Math.abs(onchainVal) * 0.2 * edge;
      }
    }

    // Normalize to -1..1
    if (total > 0) {
      for (const key of Object.keys(contributions) as (keyof typeof contributions)[]) {
        contributions[key] = Math.round((contributions[key] / total) * 100) / 100;
      }
    }

    return contributions;
  }
}

export const edgeAttributionService = new EdgeAttributionService();
