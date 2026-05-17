/**
 * Builder: ACTOR_NARRATIVE_PUSH
 * ==============================
 * Fires when influence >= 0.8, sentiment is strong (abs > 0.6) and
 * confidence >= 0.7 — i.e. a coordinated narrative is being pushed,
 * not just casual mentions.
 *
 * Bullish copy:
 *   🐦 <b>CZ pushing BNB</b>
 *   strong bullish narrative · audience reacting
 *   → sentiment shift detected
 *   ● narrative gaining traction
 *
 * Bearish copy:
 *   🐦 <b>CZ warning on BNB</b>
 *   bearish narrative emerging
 *   → downside pressure possible
 *   ● sentiment weakening
 *
 * CTA: bullish → See <ASSET> setup · bearish → See <ASSET> risk
 */

import type { UnifiedEvent } from '../../../modules/push_engine/types.js';

interface BuilderInput { event: UnifiedEvent; watchersCount?: number; }
export interface BuilderOutput {
  text: string;
  cta: string;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM';
}

export function buildActorNarrativeMessage({ event, watchersCount }: BuilderInput): BuilderOutput {
  const asset = event.asset || 'Token';
  const m: any = event.meta || {};
  const actor = m.actorName || m.handle || 'Major account';
  const direction = String(m.direction || m.sentimentHint || 'bullish').toLowerCase();
  const isBearish = direction === 'bearish' || direction === 'negative' || direction === 'down';

  const watchLine = watchersCount && watchersCount > 0
    ? `\n● ${watchersCount} people tracking this`
    : '';

  if (isBearish) {
    const text = `🐦 <b>${actor} warning on ${asset}</b>\nbearish narrative emerging\n→ downside pressure possible\n● sentiment weakening${watchLine}`;
    return { text, cta: `→ See ${asset} risk`, priority: 'HIGH' };
  }

  const text = `🐦 <b>${actor} pushing ${asset}</b>\nstrong bullish narrative · audience reacting\n→ sentiment shift detected\n● narrative gaining traction${watchLine}`;
  return { text, cta: `→ See ${asset} setup`, priority: 'HIGH' };
}
