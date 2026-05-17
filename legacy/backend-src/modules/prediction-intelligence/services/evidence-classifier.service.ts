/**
 * Layer 3 — Evidence Classifier
 *
 * Separates signal vs noise vs echo.
 * highSignal, mediumSignal, lowSignal, noise.
 */
import type { EvidencePack, EvidenceItem, ClassifiedEvidence } from '../types/case.types.js';

export function classifyEvidence(pack: EvidencePack): ClassifiedEvidence {
  const result: ClassifiedEvidence = {
    highSignal: [],
    mediumSignal: [],
    lowSignal: [],
    noise: [],
  };

  // Primary → always high signal
  for (const ev of pack.primary) {
    result.highSignal.push(ev);
  }

  // Secondary → medium signal
  for (const ev of pack.secondary) {
    result.mediumSignal.push(ev);
  }

  // Onchain → medium to high depending on type
  for (const ev of pack.onchain) {
    if (ev.sourceTier === 'tier1') result.highSignal.push(ev);
    else result.mediumSignal.push(ev);
  }

  // Narrative → low signal (twitter, blogs)
  for (const ev of pack.narrative) {
    result.lowSignal.push(ev);
  }

  // Contradictory → medium (important to track)
  for (const ev of pack.contradictory) {
    result.mediumSignal.push(ev);
  }

  // Echo → noise
  for (const ev of pack.echo) {
    result.noise.push(ev);
  }

  return result;
}
