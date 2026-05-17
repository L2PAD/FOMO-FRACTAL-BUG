/**
 * Builder: METABRAIN_DECISION_SHIFT (CRITICAL)
 * =============================================
 * Fires when MetaBrain's consolidated decision for an asset flips
 * (BUY ↔ SELL ↔ NEUTRAL) with confidence >= 0.7.
 *
 * This is the single most important push in the product — system
 * bias is changing. It SHOULD be allowed to take Hero.
 *
 * BUY copy:
 *   🧠 <b>System flipped bullish on BTC</b>
 *   multi-signal alignment detected
 *   → high-probability setup
 *   ● decision confidence high
 *
 * SELL copy:
 *   🧠 <b>System flipped bearish on BTC</b>
 *   signals turning negative
 *   → downside risk increasing
 *   ● decision confidence high
 *
 * CTA: BUY → See <ASSET> entry · SELL → See <ASSET> risk
 */

import type { UnifiedEvent } from '../../../modules/push_engine/types.js';

interface BuilderInput { event: UnifiedEvent; watchersCount?: number; }
export interface BuilderOutput {
  text: string;
  cta: string;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM';
}

export function buildMetabrainDecisionMessage({ event, watchersCount }: BuilderInput): BuilderOutput {
  const asset = event.asset || 'Token';
  const m: any = event.meta || {};
  const to = String(m.to || m.toDecision || '').toUpperCase();
  const isBearish = to === 'SELL' || to === 'BEARISH' || to === 'DOWN';

  const watchLine = watchersCount && watchersCount > 0
    ? `\n● ${watchersCount} watching this decision`
    : '';

  if (isBearish) {
    const text = `🧠 <b>System flipped bearish on ${asset}</b>\nsignals turning negative\n→ downside risk increasing\n● decision confidence high${watchLine}`;
    return { text, cta: `→ See ${asset} risk`, priority: 'CRITICAL' };
  }

  const text = `🧠 <b>System flipped bullish on ${asset}</b>\nmulti-signal alignment detected\n→ high-probability setup\n● decision confidence high${watchLine}`;
  return { text, cta: `→ See ${asset} entry`, priority: 'CRITICAL' };
}
