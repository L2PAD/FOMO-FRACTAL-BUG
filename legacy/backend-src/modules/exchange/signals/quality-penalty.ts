/**
 * Signal Quality Penalties - Confidence adjustments based on data quality
 */

/**
 * Apply quality-based confidence penalty
 */
export function applyObservationQualityPenalty(
  baseConfidence: number,
  quality: 'HIGH' | 'MEDIUM' | 'LOW'
): number {
  if (quality === 'HIGH') return baseConfidence;
  if (quality === 'MEDIUM') return baseConfidence * 0.75;
  return baseConfidence * 0.4; // Жёсткий штраф для LOW
}

/**
 * Apply spread-based penalty
 */
export function applySpreadPenalty(
  baseConfidence: number,
  spreadBps: number | null | undefined
): number {
  if (spreadBps == null) return baseConfidence;
  if (spreadBps < 15) return baseConfidence;
  if (spreadBps < 30) return baseConfidence * 0.85;
  return baseConfidence * 0.6; // Широкий spread = низкое доверие
}

/**
 * Combined penalty application
 */
export function applyAllPenalties(
  baseConfidence: number,
  quality: 'HIGH' | 'MEDIUM' | 'LOW',
  spreadBps: number | null | undefined
): number {
  let adjusted = applyObservationQualityPenalty(baseConfidence, quality);
  adjusted = applySpreadPenalty(adjusted, spreadBps);
  return adjusted;
}
