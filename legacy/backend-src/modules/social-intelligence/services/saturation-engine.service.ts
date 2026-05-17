/**
 * Layer 5 — Saturation Engine
 *
 * Determines how "known" a narrative already is.
 * High saturation = narrative exhausted as early edge.
 */
import type { SocialCluster } from '../types/social.types.js';
import type { EchoResult } from './echo-filter.service.js';
import type { PropagationResult } from './propagation-graph.service.js';

export type SaturationResult = {
  saturationScore: number;
  freshInformationRatio: number;
  crowdingLevel: 'LOW' | 'MEDIUM' | 'HIGH';
};

export function computeSaturation(cluster: SocialCluster, echo: EchoResult, propagation: PropagationResult): SaturationResult {
  const total = cluster.events.length;
  if (total === 0) return { saturationScore: 0, freshInformationRatio: 1, crowdingLevel: 'LOW' };

  // Factors contributing to saturation
  const echoFactor = echo.echoScore;
  const spreadFactor = Math.min(1, total / 20); // normalized by 20 events
  const depthFactor = Math.min(1, propagation.amplificationDepth / 3);
  const velocityFactor = Math.min(1, propagation.spreadVelocity / 10);

  // Unique authors
  const uniqueAuthors = new Set(cluster.events.map(e => e.authorId)).size;
  const authorDensity = Math.min(1, uniqueAuthors / 15);

  const saturationScore = (
    echoFactor * 0.30 +
    spreadFactor * 0.25 +
    depthFactor * 0.15 +
    velocityFactor * 0.15 +
    authorDensity * 0.15
  );

  const freshInformationRatio = echo.rawCount > 0 ? echo.originals / echo.rawCount : 1;

  const crowdingLevel: SaturationResult['crowdingLevel'] =
    saturationScore > 0.65 ? 'HIGH' :
    saturationScore > 0.35 ? 'MEDIUM' :
    'LOW';

  return {
    saturationScore: Math.round(Math.min(1, saturationScore) * 100) / 100,
    freshInformationRatio: Math.round(freshInformationRatio * 100) / 100,
    crowdingLevel,
  };
}
