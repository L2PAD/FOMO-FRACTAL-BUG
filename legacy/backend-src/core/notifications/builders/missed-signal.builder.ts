/**
 * Builder: MISSED
 * =================
 * NOT information. Emotion: regret + second chance.
 *
 * 3 copy variants based on movePct + plan:
 *
 *   BASIC (movePct >= 3%):
 *     ⚠️ BTC moved +4.5% without you
 *     You were early, but didn’t act
 *     ● Next setup forming now
 *     [→ Don’t miss next one]
 *
 *   STRONG (movePct >= 5%):
 *     ⚠️ ETH ran +8.2% after your signal
 *     You saw this · didn’t act
 *     ● New setup already forming
 *     [→ Don’t miss next one]
 *
 *   PRO (user.plan === 'PRO'|'INSTITUTIONAL'):
 *     ⚠️ You missed a +6.1% move
 *     Full entry was available
 *     ● Next one forming now
 *     [→ Stay ahead]
 *
 * Priority: MEDIUM (never Hero). CTA always points to the NEW setup, never the old one.
 */

import type { UnifiedEvent } from '../../../modules/push_engine/types.js';

interface BuilderInput {
  event: UnifiedEvent;
  watchersCount?: number;
  userPlan?: 'FREE' | 'PRO' | 'INSTITUTIONAL' | string;
}

export interface BuilderOutput {
  text: string;
  cta: string;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM';
}

function fmtPct(v: number): string {
  const abs = Math.abs(v);
  const sign = v >= 0 ? '+' : '-';
  return `${sign}${abs.toFixed(1)}%`;
}

export function buildMissedMessage({ event, watchersCount, userPlan }: BuilderInput): BuilderOutput {
  const asset = event.asset || 'Token';
  const m: any = event.meta || {};
  const move = Number(m.movePct || m.move || 0);
  const isPro = userPlan === 'PRO' || userPlan === 'INSTITUTIONAL';
  const strong = Math.abs(move) >= 5;

  const pctStr = move ? fmtPct(move) : '+move';
  const watchLine = watchersCount && watchersCount > 0
    ? `\n● ${watchersCount} tracking next setup`
    : '\n● Next setup forming now';

  // PRO copy — positions the product as an alpha tool, not a generic feed.
  if (isPro) {
    const text = `⚠️ <b>You missed a ${pctStr} move</b>\nFull entry was available\n● Next one forming now${watchLine.includes('tracking') ? watchLine : ''}`;
    return {
      text,
      cta: '→ Stay ahead',
      priority: 'MEDIUM',
    };
  }

  if (strong) {
    const text = `⚠️ <b>${asset} ran ${pctStr} after your signal</b>\nYou saw this · didn’t act\n● New setup already forming${watchersCount ? `\n● ${watchersCount} tracking next setup` : ''}`;
    return {
      text,
      cta: '→ Don’t miss next one',
      priority: 'MEDIUM',
    };
  }

  // Basic — most common path.
  const text = `⚠️ <b>${asset} moved ${pctStr} without you</b>\nYou were early, but didn’t act${watchLine}`;
  return {
    text,
    cta: '→ Don’t miss next one',
    priority: 'MEDIUM',
  };
}
