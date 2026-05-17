/**
 * Exposure Engine — Stage 7
 *
 * Aggregates current portfolio exposure across all dimensions:
 *   byAsset, byTheme, byEntity, byResolution, byCatalyst
 *
 * Mandatory service — needed for UI explanations and debugging.
 */
import type { ActivePosition, ExposureSummary } from '../types/portfolio.types.js';

export function computeExposureSummary(positions: ActivePosition[]): ExposureSummary {
  const byAsset:      Record<string, number> = {};
  const byTheme:      Record<string, number> = {};
  const byEntity:     Record<string, number> = {};
  const byResolution: Record<string, number> = {};
  const byCatalyst:   Record<string, number> = {};
  let totalExposure = 0;

  for (const pos of positions) {
    const size = pos.sizeFraction;
    totalExposure += size;

    // Asset
    byAsset[pos.asset] = (byAsset[pos.asset] || 0) + size;

    // Theme
    for (const t of pos.factorProfile.themeFactors) {
      byTheme[t] = (byTheme[t] || 0) + size;
    }

    // Entity
    for (const e of pos.factorProfile.entityFactors) {
      byEntity[e] = (byEntity[e] || 0) + size;
    }

    // Resolution
    for (const r of pos.factorProfile.resolutionFactors) {
      byResolution[r] = (byResolution[r] || 0) + size;
    }

    // Catalyst
    for (const c of pos.factorProfile.catalystFactors) {
      byCatalyst[c] = (byCatalyst[c] || 0) + size;
    }
  }

  return {
    totalExposure: Math.round(totalExposure * 100) / 100,
    byAsset,
    byTheme,
    byEntity,
    byResolution,
    byCatalyst,
    positionCount: positions.length,
  };
}
