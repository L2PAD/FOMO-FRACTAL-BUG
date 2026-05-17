/**
 * Builder: METABRAIN_CONVICTION_JUMP (HIGH)
 * ==========================================
 * Fires when conviction rises by >= +20% on the SAME decision.
 * Not a reversal — a strengthening of an existing setup.
 *
 *   🧠 <b>Conviction rising on BTC</b>
 *   confidence jumped +22%
 *   → strengthening setup
 *   ● alignment improving
 *
 * CTA: → Track <ASSET> setup
 */

import type { UnifiedEvent } from '../../../modules/push_engine/types.js';

interface BuilderInput { event: UnifiedEvent; watchersCount?: number; }
export interface BuilderOutput {
  text: string;
  cta: string;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM';
}

export function buildMetabrainConvictionMessage({ event, watchersCount }: BuilderInput): BuilderOutput {
  const asset = event.asset || 'Token';
  const m: any = event.meta || {};
  const delta = Number(m.delta || m.convictionDelta || 0);
  const deltaRounded = Math.round(delta * 100);
  const jumpLine = deltaRounded > 0
    ? `confidence jumped +${deltaRounded}%`
    : 'confidence strengthening';

  const watchLine = watchersCount && watchersCount > 0
    ? `\n● ${watchersCount} watching this setup`
    : '';

  const text = `🧠 <b>Conviction rising on ${asset}</b>\n${jumpLine}\n→ strengthening setup\n● alignment improving${watchLine}`;

  return {
    text,
    cta: `→ Track ${asset} setup`,
    priority: 'HIGH',
  };
}
