/**
 * Missed Opportunity Analysis
 *
 * Identifies the most costly missed opportunities.
 */

import type { MissedOpportunity } from '../types/digest.types.js';

interface ReviewData {
  asset: string;
  missedOpportunity: { missed: boolean; reason: string; edgeAtBest: number; whyMissed: string[] };
  traces: { edge: number; action: string }[];
  question?: string;
}

class MissedOpportunityService {
  analyze(reviews: ReviewData[]): { totalMissed: number; topMissed: MissedOpportunity[] } {
    const missed: MissedOpportunity[] = [];

    for (const r of reviews) {
      if (r.missedOpportunity?.missed) {
        missed.push({
          market: (r.question || r.asset || '').slice(0, 80),
          asset: r.asset || '',
          missedEdge: r.missedOpportunity.edgeAtBest || 0,
          reason: r.missedOpportunity.reason || r.missedOpportunity.whyMissed?.[0] || 'Unknown',
        });
      }
    }

    missed.sort((a, b) => b.missedEdge - a.missedEdge);

    return {
      totalMissed: missed.length,
      topMissed: missed.slice(0, 5),
    };
  }
}

export const missedOpportunityService = new MissedOpportunityService();
