/**
 * Layer 7 — Social Signal Aggregator
 *
 * Combines all sub-analyses into a single NarrativeAssessment per cluster.
 */
import type { SocialCluster } from '../types/social.types.js';
import type { AccountProfile } from '../types/account.types.js';
import type { NarrativeAssessment } from '../types/narrative.types.js';
import { filterEcho } from './echo-filter.service.js';
import { detectOrigin } from './origin-detector.service.js';
import { buildPropagationGraph } from './propagation-graph.service.js';
import { evaluateInfluence } from './influence-engine.service.js';
import { computeSaturation } from './saturation-engine.service.js';
import { determineLifecycle } from './narrative-lifecycle.service.js';

export function aggregateCluster(cluster: SocialCluster, profiles: Map<string, AccountProfile>): NarrativeAssessment {
  const echo = filterEcho(cluster);
  const origin = detectOrigin(cluster, profiles);
  const propagation = buildPropagationGraph(cluster, origin);
  const influence = evaluateInfluence(cluster, profiles);
  const saturation = computeSaturation(cluster, echo, propagation);
  const lifecycle = determineLifecycle(cluster, origin, echo, saturation, propagation);

  // Social strength: combination of origin quality, influence, and freshness
  const socialStrength = Math.round(Math.min(1, (
    origin.trustScore * 0.3 +
    influence.weightedInfluence * 0.25 +
    (1 - echo.echoScore) * 0.2 +
    (1 - saturation.saturationScore) * 0.25
  )) * 100) / 100;

  // Social confidence: how much to trust this narrative signal
  const socialConfidence = Math.round(Math.min(1, (
    origin.confidence * 0.35 +
    (1 - echo.echoScore) * 0.25 +
    influence.weightedInfluence * 0.2 +
    saturation.freshInformationRatio * 0.2
  )) * 100) / 100;

  // Contradiction: check for bearish vs bullish split
  const contradictionScore = 0; // would need sentiment analysis per event

  return {
    clusterId: cluster.clusterId,
    origin: {
      eventId: origin.originEventId,
      authorId: origin.originAuthorId,
      authorName: origin.originAuthorName,
      trustScore: origin.trustScore,
    },
    velocity: propagation.spreadVelocity,
    echoScore: echo.echoScore,
    saturationScore: saturation.saturationScore,
    contradictionScore,
    lifecycle,
    highQualityAmplifiers: influence.highQualityAmplifiers,
    lowQualityAmplifiers: influence.lowQualityAmplifiers,
    socialStrength,
    socialConfidence,
  };
}
