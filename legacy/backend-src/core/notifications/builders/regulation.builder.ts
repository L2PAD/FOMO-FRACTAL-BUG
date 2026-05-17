/**
 * Builder: REGULATION / LEGAL
 * ===========================
 * Copy when regulation / legal news hits an asset.
 * Priority: HIGH. May be bullish (clarity, approval) or bearish (enforcement).
 *
 * Example output:
 *   ⚖️ <b>BTC regulation update</b>
 *   Enforcement risk detected · short-term volatility expected
 *
 * CTA: → See BTC setup
 */

import type { UnifiedEvent } from '../../../modules/push_engine/types.js';

interface BuilderInput { event: UnifiedEvent; }

export interface BuilderOutput {
  text: string;
  cta: string;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM';
}

export function buildRegulationMessage({ event }: BuilderInput): BuilderOutput {
  const asset = event.asset || 'Market';
  const m: any = event.meta || {};
  const kind = String(m.kind || 'regulation').toLowerCase(); // regulation | legal
  const score = typeof m.weightedScore === 'number' ? m.weightedScore : 0.5;
  const direction = String(m.direction || '').toLowerCase();

  let headline: string;
  if (direction.includes('bull') || score >= 0.65) {
    headline = 'Regulatory clarity emerging · tailwind for price';
  } else if (direction.includes('bear') || score <= 0.4) {
    headline = 'Enforcement risk detected · short-term volatility expected';
  } else {
    headline = kind === 'legal'
      ? 'Legal development active · monitor closely'
      : 'Regulatory development active · monitor closely';
  }

  const label = kind === 'legal' ? 'legal' : 'regulation';
  const text = `⚖️ <b>${asset} ${label} update</b>\n${headline}`;

  return {
    text,
    cta: `→ See ${asset} setup`,
    priority: 'HIGH',
  };
}
