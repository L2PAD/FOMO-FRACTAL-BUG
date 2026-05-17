/**
 * Builder: WHALE_EXCHANGE_INFLOW
 * ===============================
 * Large exchange inflow ($5M+, zScore spike). Distribution risk / sell pressure.
 *
 *   🐋 <b>Large inflow to exchange</b>
 *   $12.4M BTC moved to Binance
 *   → potential sell pressure
 *   ● distribution risk rising
 *
 * CTA: → See <ASSET> downside
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

export function buildWhaleInflowMessage({ event, watchersCount }: BuilderInput): BuilderOutput {
  const asset = event.asset || 'Token';
  const m: any = event.meta || {};
  const usd = Number(m.usdValue || m.notionalUsd || 0);
  const exchange = m.exchange || 'exchange';
  const amountLine = `${formatUsd(usd)} ${asset} moved to ${exchange}`;

  const watchLine = watchersCount && watchersCount > 0
    ? `\n● ${watchersCount} tracking this flow`
    : '';

  // Extreme inflow (>$25M or zScore > 4) = CRITICAL (systemic distribution).
  const zScore = Number(m.zScore || 0);
  const priority: 'CRITICAL' | 'HIGH' = (usd >= 25_000_000 || zScore >= 4) ? 'CRITICAL' : 'HIGH';

  const text = `🐋 <b>Large inflow to exchange</b>\n${amountLine}\n→ potential sell pressure\n● distribution risk rising${watchLine}`;

  return {
    text,
    cta: `→ See ${asset} downside`,
    priority,
  };
}
