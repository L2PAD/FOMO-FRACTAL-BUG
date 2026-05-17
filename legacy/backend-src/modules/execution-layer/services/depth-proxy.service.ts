/**
 * Depth Proxy Service
 *
 * Without full orderbook data, estimates depth quality from:
 *   liquidity, spread, volume, probability movement speed
 */

import type { DepthAssessment, DepthQuality } from '../types/microstructure.types.js';

class DepthProxyService {
  assess(liquidity: number, spread: number, volume24h: number, probVolatility?: number): DepthAssessment {
    const notes: string[] = [];

    // Component scores (0–1, higher = worse/more fragile)
    let fragilityScore = 0;

    // Liquidity component
    if (liquidity >= 100000) {
      notes.push(`Deep liquidity ($${(liquidity / 1000).toFixed(0)}K)`);
    } else if (liquidity >= 30000) {
      fragilityScore += 0.15;
    } else if (liquidity >= 10000) {
      fragilityScore += 0.30;
      notes.push(`Moderate liquidity ($${(liquidity / 1000).toFixed(0)}K)`);
    } else if (liquidity >= 3000) {
      fragilityScore += 0.45;
      notes.push(`Low liquidity ($${(liquidity / 1000).toFixed(0)}K) — larger orders will move price`);
    } else {
      fragilityScore += 0.60;
      notes.push(`Very low liquidity ($${liquidity.toFixed(0)}) — fragile market`);
    }

    // Spread component
    if (spread >= 0.08) {
      fragilityScore += 0.25;
    } else if (spread >= 0.05) {
      fragilityScore += 0.15;
    } else if (spread >= 0.03) {
      fragilityScore += 0.05;
    }

    // Volume component
    if (volume24h < 500) {
      fragilityScore += 0.20;
      notes.push('Extremely low volume — market may be abandoned');
    } else if (volume24h < 3000) {
      fragilityScore += 0.10;
    }

    // Probability volatility (if available)
    if (probVolatility && probVolatility > 0.15) {
      fragilityScore += 0.10;
      notes.push('High probability volatility — price discovery unstable');
    }

    fragilityScore = Math.min(1, Math.round(fragilityScore * 100) / 100);

    // Determine quality
    let depthQuality: DepthQuality;
    if (fragilityScore <= 0.15) {
      depthQuality = 'DEEP';
    } else if (fragilityScore <= 0.35) {
      depthQuality = 'OK';
    } else if (fragilityScore <= 0.60) {
      depthQuality = 'THIN';
    } else {
      depthQuality = 'FRAGILE';
    }

    return { depthQuality, fragilityScore, notes };
  }
}

export const depthProxyService = new DepthProxyService();
