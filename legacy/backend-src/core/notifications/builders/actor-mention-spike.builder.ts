/**
 * Builder: ACTOR_MENTION_SPIKE
 * =============================
 * Fires when an influential account (score >= 0.75) mentions an asset
 * >= 3 times within a 15-minute window.
 *
 * Product spec copy:
 *   🐦 <b>CZ mentioning ARB</b>
 *   3+ mentions detected · narrative forming
 *   → attention increasing rapidly
 *   ● market reacting to this
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

export function buildActorMentionSpikeMessage({ event, watchersCount }: BuilderInput): BuilderOutput {
  const asset = event.asset || 'Token';
  const m: any = event.meta || {};
  const actor = m.actorName || m.handle || 'Major account';
  const mentions = Number(m.mentionCount || m.count || 3);
  const influence = Number(m.influenceScore || 0);
  const reaction = influence >= 0.9 ? '● market reacting to this' : '● attention gathering';

  const watchLine = watchersCount && watchersCount > 0
    ? `\n● ${watchersCount} people tracking this`
    : '';

  const text = `🐦 <b>${actor} mentioning ${asset}</b>\n${mentions}+ mentions detected · narrative forming\n→ attention increasing rapidly\n${reaction}${watchLine}`;

  // CRITICAL only when influence is extreme (> 0.9). Otherwise HIGH.
  const priority: 'CRITICAL' | 'HIGH' = influence > 0.9 ? 'CRITICAL' : 'HIGH';

  return {
    text,
    cta: `→ Track ${asset} setup`,
    priority,
  };
}
