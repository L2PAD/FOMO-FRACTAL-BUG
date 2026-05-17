/**
 * Builder: POLY_OVERHEATED (overheated)
 * =====================================
 * Market is overheating — crowded positioning, risk of reversal.
 * Priority: HIGH. Counter-trend signal.
 *
 * Example:
 *   ⚠️ <b>Market overheating</b>
 *   Crowded positioning · risk of reversal
 *
 * CTA: → See downside risk
 */

import type { UnifiedEvent } from '../../../modules/push_engine/types.js';

export interface BuilderOutput { text: string; cta: string; priority: 'CRITICAL' | 'HIGH' | 'MEDIUM'; }

export function buildPolymarketOverheatedMessage({
  event,
}: { event: UnifiedEvent }): BuilderOutput {
  const m: any = event.meta || {};
  const marketTitle = (m.marketTitle || event.reason || 'crypto market').slice(0, 80);

  const text =
    `⚠️ <b>Market overheating</b>\n` +
    `${marketTitle}\n` +
    `→ crowded positioning · risk of reversal`;

  return { text, cta: '→ See downside risk', priority: 'HIGH' };
}
