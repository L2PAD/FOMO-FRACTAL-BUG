/**
 * Builder: LISTING
 * =================
 * Copy when a new CEX/DEX listing is detected for an asset.
 * Priority: CRITICAL. Drives discovery + fast entry.
 *
 * Example output:
 *   🚀 <b>ARB listing detected</b>
 *   Binance listing confirmed · liquidity expansion expected
 *   ● 132 people watching this setup
 *
 * CTA (inline button): → See ARB setup
 */

import type { UnifiedEvent } from '../../../modules/push_engine/types.js';

interface BuilderInput {
  event: UnifiedEvent;
  watchersCount?: number;
}

export interface BuilderOutput {
  text: string;
  cta: string;                     // "→ See ARB setup"
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM';
}

export function buildListingMessage({ event, watchersCount }: BuilderInput): BuilderOutput {
  const asset = event.asset || 'Token';
  const m: any = event.meta || {};
  const exchange = m.exchange || m.source_exchange || null;
  const headline = exchange ? `${exchange} listing confirmed` : 'New listing confirmed';
  const impact = '· liquidity expansion expected';

  const socialLine = watchersCount && watchersCount > 0
    ? `\n● ${watchersCount} people watching this setup`
    : '';

  const text = `🚀 <b>${asset} listing detected</b>\n${headline} ${impact}${socialLine}`;

  return {
    text,
    cta: `→ See ${asset} setup`,
    priority: 'CRITICAL',
  };
}
