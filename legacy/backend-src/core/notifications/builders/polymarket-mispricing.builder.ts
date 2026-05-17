/**
 * Builder: POLY_MISPRICING (new_mispricing)
 * =========================================
 * Prediction-market mispricing detected — odds diverging from expected outcome.
 * Priority: CRITICAL. Polymarket signals are MARKET-FIRST, not asset-first —
 * CTA must point to "market opportunity", NOT "$ASSET setup".
 *
 * Example:
 *   🎯 <b>Market mispricing detected</b>
 *   Odds diverging from expected outcome
 *   ● 124 people watching this setup
 *
 * CTA: → See market opportunity
 */

import type { UnifiedEvent } from '../../../modules/push_engine/types.js';

export interface BuilderOutput { text: string; cta: string; priority: 'CRITICAL' | 'HIGH' | 'MEDIUM'; }

export function buildPolymarketMispricingMessage({
  event, watchersCount,
}: { event: UnifiedEvent; watchersCount?: number }): BuilderOutput {
  const m: any = event.meta || {};
  const marketTitle = (m.marketTitle || event.reason || 'crypto narrative').slice(0, 80);
  const edge = typeof m.edge === 'number' ? m.edge : null;
  const edgeLine = edge !== null && Math.abs(edge) > 0
    ? ` · edge ${edge > 0 ? '+' : ''}${(edge * 100).toFixed(0)}%`
    : '';

  const socialLine = watchersCount && watchersCount > 0
    ? `\n● ${watchersCount} people watching this setup`
    : '';

  const text =
    `🎯 <b>Market mispricing detected</b>\n` +
    `${marketTitle}${edgeLine}\n` +
    `→ odds diverging from expected outcome${socialLine}`;

  return { text, cta: '→ See market opportunity', priority: 'CRITICAL' };
}
