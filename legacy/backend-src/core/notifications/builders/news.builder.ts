/**
 * Builder: NEWS (breaking / market-moving)
 * =========================================
 * Market-first copy — no asset-specific CTA. Direction-aware: bullish vs
 * bearish choose icon + impact line.
 *
 *   📰 <b>Market moving news</b>
 *   BlackRock expands crypto ETF exposure
 *   institutional demand increasing
 *   ● 124 people watching this setup
 *
 * CTA: → See market impact
 */

import type { UnifiedEvent } from '../../../modules/push_engine/types.js';

export interface BuilderOutput { text: string; cta: string; priority: 'CRITICAL' | 'HIGH' | 'MEDIUM'; }

export function buildBreakingNewsMessage({
  event, watchersCount,
}: { event: UnifiedEvent; watchersCount?: number }): BuilderOutput {
  const m: any = event.meta || {};
  const direction = String(m.sentiment || m.direction || 'neutral').toLowerCase();
  const priority = (m.priority || 'HIGH') as 'CRITICAL' | 'HIGH' | 'MEDIUM';

  const emoji = direction === 'bearish' ? '⚠️' : '📰';
  const header = direction === 'bearish' ? 'Market risk emerging' : 'Market moving news';

  const title = (m.title || event.reason || '').slice(0, 120);
  const summary = (m.summary || '').slice(0, 140);
  const sourceName = m.sourceName ? ` · via ${m.sourceName}` : '';

  const impact =
    direction === 'bullish' ? 'upside pressure building'
    : direction === 'bearish' ? 'downside risk increasing'
    : 'market reacting';

  const socialLine = watchersCount && watchersCount > 0
    ? `\n● ${watchersCount} people watching this setup`
    : '';

  const lines: string[] = [];
  lines.push(`${emoji} <b>${header}</b>`);
  if (title) lines.push(title);
  if (summary && summary !== title) lines.push(summary);
  lines.push(`→ ${impact}${sourceName}`);
  const text = lines.join('\n') + socialLine;

  return { text, cta: '→ See market impact', priority };
}
