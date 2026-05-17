/**
 * Layer 3 — Propagation Graph
 *
 * Models how a signal spread: origin → first wave → second wave → late echo.
 * Computes spreadVelocity and amplificationDepth.
 */
import type { SocialCluster } from '../types/social.types.js';
import type { OriginResult } from './origin-detector.service.js';

export type PropagationResult = {
  firstWaveCount: number;
  secondWaveCount: number;
  lateEchoCount: number;
  spreadVelocity: number;
  amplificationDepth: number;
};

export function buildPropagationGraph(cluster: SocialCluster, origin: OriginResult): PropagationResult {
  if (!cluster.events.length || !origin.originTimestamp) {
    return { firstWaveCount: 0, secondWaveCount: 0, lateEchoCount: 0, spreadVelocity: 0, amplificationDepth: 0 };
  }

  const originTs = origin.originTimestamp;
  const sorted = [...cluster.events].sort((a, b) => a.timestamp - b.timestamp);

  // Define waves by time windows
  const FIRST_WAVE_MS = 30 * 60 * 1000;   // 30 min
  const SECOND_WAVE_MS = 120 * 60 * 1000;  // 2 hours

  let firstWave = 0, secondWave = 0, lateEcho = 0;

  for (const ev of sorted) {
    const delta = ev.timestamp - originTs;
    if (delta <= 0) continue; // origin itself
    if (delta <= FIRST_WAVE_MS) firstWave++;
    else if (delta <= SECOND_WAVE_MS) secondWave++;
    else lateEcho++;
  }

  // Spread velocity: events per hour in first wave
  const firstWaveHours = FIRST_WAVE_MS / (3600 * 1000);
  const spreadVelocity = Math.round((firstWave / firstWaveHours) * 100) / 100;

  // Amplification depth: how many layers of spread
  const totalAfterOrigin = firstWave + secondWave + lateEcho;
  const amplificationDepth = totalAfterOrigin === 0 ? 0 :
    secondWave > 0 && lateEcho > 0 ? 3 :
    secondWave > 0 ? 2 :
    firstWave > 0 ? 1 : 0;

  return {
    firstWaveCount: firstWave,
    secondWaveCount: secondWave,
    lateEchoCount: lateEcho,
    spreadVelocity,
    amplificationDepth,
  };
}
