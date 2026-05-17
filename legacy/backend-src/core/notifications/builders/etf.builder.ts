/**
 * Builder: ETF
 * ============
 * Copy when ETF-related news hits (approval, filing, flow shift).
 * Priority: CRITICAL for approvals, HIGH for filings.
 *
 * Example output:
 *   🏛️ <b>BTC ETF development</b>
 *   Approval flow confirmed · institutional demand expanding
 *
 * CTA: → See BTC setup
 */

import type { UnifiedEvent } from '../../../modules/push_engine/types.js';

interface BuilderInput { event: UnifiedEvent; watchersCount?: number; }

export interface BuilderOutput {
  text: string;
  cta: string;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM';
}

export function buildETFMessage({ event, watchersCount }: BuilderInput): BuilderOutput {
  const asset = event.asset || 'Asset';
  const m: any = event.meta || {};
  const stage = m.stage || m.etfStage || 'development';  // approval | filing | flow
  const direction = String(m.direction || '').toLowerCase();

  let headline: string;
  if (direction.includes('bull') || m.weightedScore >= 0.7) {
    headline = 'Approval flow confirmed · institutional demand expanding';
  } else if (direction.includes('bear')) {
    headline = 'Outflow pressure detected · institutional pullback';
  } else {
    headline = `ETF ${stage} update · institutional narrative active`;
  }

  const socialLine = watchersCount && watchersCount > 0
    ? `\n● ${watchersCount} people watching this setup`
    : '';

  const text = `🏛️ <b>${asset} ETF development</b>\n${headline}${socialLine}`;

  return {
    text,
    cta: `→ See ${asset} setup`,
    priority: 'CRITICAL',
  };
}
