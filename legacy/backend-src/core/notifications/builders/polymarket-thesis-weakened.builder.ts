/**
 * Builder: POLY_THESIS_WEAKENED (thesis_weakened, entry_window_closed)
 * ====================================================================
 * Market thesis is weakening or entry window closing — re-evaluate.
 * Priority: HIGH for thesis_weakened, MEDIUM for entry_window_closed.
 *
 * Example:
 *   📉 <b>Market thesis weakening</b>
 *   Conviction dropping across participants
 *
 * CTA: → Re-evaluate setup
 */

import type { UnifiedEvent } from '../../../modules/push_engine/types.js';

export interface BuilderOutput { text: string; cta: string; priority: 'CRITICAL' | 'HIGH' | 'MEDIUM'; }

export function buildPolymarketThesisWeakenedMessage({
  event,
}: { event: UnifiedEvent }): BuilderOutput {
  const m: any = event.meta || {};
  const alertType = String(m.alertType || 'thesis_weakened');
  const marketTitle = (m.marketTitle || event.reason || 'crypto narrative').slice(0, 80);

  if (alertType === 'entry_window_closed') {
    const text =
      `⏳ <b>Entry window closing</b>\n` +
      `${marketTitle}\n` +
      `→ late entries now risky`;
    return { text, cta: '→ Re-evaluate setup', priority: 'MEDIUM' };
  }

  const text =
    `📉 <b>Market thesis weakening</b>\n` +
    `${marketTitle}\n` +
    `→ conviction dropping across participants`;
  return { text, cta: '→ Re-evaluate setup', priority: 'HIGH' };
}
