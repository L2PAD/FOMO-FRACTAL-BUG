/**
 * Builder: POLY_REPRICING (repricing_started, repricing_change)
 * =============================================================
 * Prediction market is repricing — participants shifting positions.
 * Priority: HIGH for repricing_started, MEDIUM for repricing_change.
 *
 * Example (started):
 *   📊 <b>Market repricing started</b>
 *   Positioning shifting across participants
 *
 * CTA: → Track market move
 */

import type { UnifiedEvent } from '../../../modules/push_engine/types.js';

export interface BuilderOutput { text: string; cta: string; priority: 'CRITICAL' | 'HIGH' | 'MEDIUM'; }

export function buildPolymarketRepricingMessage({
  event,
}: { event: UnifiedEvent }): BuilderOutput {
  const m: any = event.meta || {};
  const alertType = String(m.alertType || 'repricing_started');
  const marketTitle = (m.marketTitle || event.reason || 'crypto market').slice(0, 80);
  const transitionFrom = m.transitionFrom || null;
  const transitionTo = m.transitionTo || null;

  const headline = alertType === 'repricing_change'
    ? 'Repricing phase shifted'
    : 'Market repricing started';

  const transitionLine = (transitionFrom && transitionTo)
    ? `\n${transitionFrom} → ${transitionTo}`
    : '';

  const text =
    `📊 <b>${headline}</b>\n` +
    `${marketTitle}${transitionLine}\n` +
    `→ positioning shifting across participants`;

  const priority: 'HIGH' | 'MEDIUM' = alertType === 'repricing_change' ? 'MEDIUM' : 'HIGH';
  return { text, cta: '→ Track market move', priority };
}
