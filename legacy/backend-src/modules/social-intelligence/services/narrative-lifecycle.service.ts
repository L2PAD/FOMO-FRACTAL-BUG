/**
 * Layer 6 — Narrative Lifecycle
 *
 * Determines the phase: EARLY → EXPANDING → SATURATED → FADING → DORMANT
 */
import type { SocialCluster } from '../types/social.types.js';
import type { EchoResult } from './echo-filter.service.js';
import type { SaturationResult } from './saturation-engine.service.js';
import type { PropagationResult } from './propagation-graph.service.js';
import type { OriginResult } from './origin-detector.service.js';
import type { NarrativeState } from '../types/narrative.types.js';

export function determineLifecycle(
  cluster: SocialCluster,
  origin: OriginResult,
  echo: EchoResult,
  saturation: SaturationResult,
  propagation: PropagationResult,
): NarrativeState {
  const total = cluster.events.length;
  if (total === 0) return 'DORMANT';

  // Age of narrative (hours since origin)
  const now = Date.now();
  const ageHours = origin.originTimestamp
    ? (now - origin.originTimestamp) / (3600 * 1000)
    : 24;

  // DORMANT: very old, no recent activity
  const latestEvent = Math.max(...cluster.events.map(e => e.timestamp));
  const hoursSinceLatest = (now - latestEvent) / (3600 * 1000);
  if (hoursSinceLatest > 12) return 'DORMANT';

  // FADING: old narrative, slowing spread
  if (ageHours > 8 && propagation.spreadVelocity < 2 && echo.echoScore > 0.5) return 'FADING';

  // SATURATED: high echo, high saturation, many events
  if (saturation.saturationScore > 0.6 && echo.echoScore > 0.5) return 'SATURATED';
  if (total > 15 && echo.echoScore > 0.6) return 'SATURATED';

  // EXPANDING: spreading, moderate echo, moderate saturation
  if (total > 3 && propagation.firstWaveCount > 0 && saturation.saturationScore < 0.6) return 'EXPANDING';
  if (propagation.spreadVelocity > 3 && saturation.saturationScore < 0.5) return 'EXPANDING';

  // EARLY: few events, low echo, low saturation, fresh
  if (total <= 5 && echo.echoScore < 0.4 && saturation.saturationScore < 0.35) return 'EARLY';
  if (ageHours < 2 && saturation.saturationScore < 0.4) return 'EARLY';

  // Default: if moderate signals, call it EXPANDING
  return 'EXPANDING';
}
