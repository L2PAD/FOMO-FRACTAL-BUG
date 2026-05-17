/**
 * Builder: WHALE_EXCHANGE_OUTFLOW
 * ================================
 * Large exchange outflow ($5M+, zScore spike). Accumulation / supply tightening.
 *
 *   🐋 <b>Large outflow from exchange</b>
 *   $9.8M ETH withdrawn
 *   → accumulation signal
 *   ● supply tightening
 *
 * CTA: → See <ASSET> setup
 */

import type { UnifiedEvent } from '../../../modules/push_engine/types.js';

interface BuilderInput { event: UnifiedEvent; watchersCount?: number; }
export interface BuilderOutput {
  text: string;
  cta: string;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM';
}

function formatUsd(v: number): string {
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${Math.round(v / 1000)}K`;
  return `$${v.toFixed(0)}`;
}

export function buildWhaleOutflowMessage({ event, watchersCount }: BuilderInput): BuilderOutput {
  const asset = event.asset || 'Token';
  const m: any = event.meta || {};
  const usd = Number(m.usdValue || m.notionalUsd || 0);
  const amountLine = `${formatUsd(usd)} ${asset} withdrawn`;

  const watchLine = watchersCount && watchersCount > 0
    ? `\n● ${watchersCount} tracking this flow`
    : '';

  // Extreme outflow = CRITICAL (supply shock).
  const zScore = Number(m.zScore || 0);
  const priority: 'CRITICAL' | 'HIGH' = (usd >= 25_000_000 || zScore >= 4) ? 'CRITICAL' : 'HIGH';

  const text = `🐋 <b>Large outflow from exchange</b>\n${amountLine}\n→ accumulation signal\n● supply tightening${watchLine}`;

  return {
    text,
    cta: `→ See ${asset} setup`,
    priority,
  };
}
