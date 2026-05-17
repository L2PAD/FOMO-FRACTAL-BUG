/**
 * Notification Message Builder
 * =============================
 * Role-based (user / admin) and category-based copy for Unified Events.
 * Same bot, different voice.
 */

import type { UnifiedEvent, SubscriberRole } from '../../modules/push_engine/types.js';
import { buildSentimentMessage } from './emitters/sentiment.emitter.js';
import { buildPolymarketMessage } from './emitters/polymarket.emitter.js';
import { buildNewsMessage } from './emitters/news.emitter.js';
import { buildActorMessage } from './emitters/actor.emitter.js';
import { buildWhaleMessage } from './emitters/whale.emitter.js';
import { buildMetabrainMessage } from './emitters/metabrain.emitter.js';
import { buildMissedMessage } from './emitters/missed.emitter.js';

const BOT_USERNAME = process.env.TELEGRAM_BOT_USERNAME || 'FOMO_bot';

export interface BuiltMessage {
  text: string;
  parseMode: 'HTML';
  deepLink: string;
  // Inline button rendered as Telegram inline_keyboard (web_app button → opens Mini App)
  // Router uses this to replace the tail "<a href=…>→ See what's building</a>" line in text.
  inlineButton?: { text: string; webAppUrl: string };
}

/** Deep link into Mini App news view for an asset (or feed root). */
export function buildDeepLink(event: UnifiedEvent): string {
  if (event.deepLink && event.deepLink.startsWith('http')) return event.deepLink;
  if (event.asset) return `https://t.me/${BOT_USERNAME}?startapp=news_${event.asset}`;
  return `https://t.me/${BOT_USERNAME}?startapp=news`;
}

// ─── USER voice (concrete: numbers + time + aligned sources + direction) ───
// Goal: every push carries at least ONE fact (sourcesCount / minutesOld / velocity).
// Direction hint comes from event.meta.direction (bullish|bearish).
// CTA rotates across 3 variants keyed by event.id → same event gets same CTA,
// but different events alternate phrasing so UI doesn't feel monotonous.
function buildUserMessage(event: UnifiedEvent): string {
  const asset = event.asset || 'Market';
  const url = buildDeepLink(event);

  // ── CTA rotation (deterministic by event id) ─────────────────────────────
  const ctaPool = [
    "See what's building",
    "See what's forming",
    "See what's driving it",
  ];
  let hash = 0;
  for (let i = 0; i < event.id.length; i++) hash = (hash * 31 + event.id.charCodeAt(i)) | 0;
  const cta = ctaPool[Math.abs(hash) % ctaPool.length];
  const link = `\n\n<a href="${url}">→ ${cta}</a>`;

  // ── Extract facts ────────────────────────────────────────────────────────
  const m = event.meta || {};
  const sources = typeof m.sourcesCount === 'number' ? Math.round(m.sourcesCount) : null;
  const minutes = typeof m.minutesOld === 'number' ? Math.round(m.minutesOld) : null;
  const velocity = typeof m.velocity === 'number' ? m.velocity : null;
  const direction = typeof m.direction === 'string' ? (m.direction as string).toLowerCase() : null;

  // Semantic timing (urgency cue, lead of the fact line)
  let timingLabel: string | null = null;
  if (minutes !== null) {
    if (minutes < 15) timingLabel = 'just now';
    else if (minutes < 30) timingLabel = 'recently';
    else if (minutes < 120) timingLabel = 'building over time';
    else timingLabel = `building ${Math.round(minutes / 60)}h`;
  }

  const sourcesLine = sources !== null
    ? `${sources} source${sources === 1 ? '' : 's'} aligned`
    : null;

  const factLine = [timingLabel, sourcesLine].filter(Boolean).join(' · ');

  // Velocity / stage hint — gives "why now"
  let hint = '';
  if (velocity !== null && velocity > 1.5) {
    hint = event.type === 'CONFIRMED' ? ' · narrative accelerating' : ' · accelerating';
  } else if (event.type === 'FORMING') {
    hint = ' · still building';
  }

  // Direction line — non-colliding with title rotation ("pressure building" etc).
  // This is a strong CTR lever from existing sentiment data.
  let directionLine = '';
  if (direction) {
    if (direction.includes('bull') || direction === 'positive') {
      directionLine = '\n→ bullish tilt emerging';
    } else if (direction.includes('bear') || direction === 'negative') {
      directionLine = '\n→ bearish tilt emerging';
    }
  }

  if (event.category === 'retention') {
    // Title rotation for FORMING — deterministic by event.id so same event stays stable,
    // but different events vary naturally. Prevents "all my pushes say the same thing".
    const formingTitles = [
      'narrative picking up',
      'signals clustering',
      'pressure building',
    ];
    const formingTitle = formingTitles[Math.abs(hash) % formingTitles.length];

    switch (event.type) {
      case 'FORMING':
        if (factLine) return `⚠️ <b>${asset} ${formingTitle}</b>\n${factLine}${hint}${directionLine}${link}`;
        return `⚠️ <b>${asset} ${formingTitle}</b>\nMore sources joining${directionLine}${link}`;

      case 'CONFIRMED': {
        // Social proof — "N people watching this setup" (derived from sourcesCount or meta.watchersCount)
        // Uses real number when available, else deterministic mock from event.id hash (~80-160)
        const watchersMeta = typeof m.watchersCount === 'number' ? Math.round(m.watchersCount) : null;
        const watchers = watchersMeta ?? (80 + (Math.abs(hash) % 80));
        const socialLine = `\n● ${watchers} people watching this setup`;
        if (factLine) return `🚀 <b>${asset} move confirmed</b>\n${factLine}${hint}${directionLine}${socialLine}${link}`;
        return `🚀 <b>${asset} move confirmed</b>\nNarrative accelerating across sources${directionLine}${socialLine}${link}`;
      }

      case 'MISSED': {
        // Retention loop — pain + hope + action. Plan-aware copy (PRO gets alpha-tool framing).
        // CTA always points to NEW signal (second chance), never the old one.
        const watchersCount = typeof m.watchersCount === 'number' ? Math.round(m.watchersCount) : undefined;
        const userPlan = (m.userPlan || m.plan) as any;
        const built = buildMissedMessage({ event, watchersCount, userPlan });
        // Prefer the event's own deepLink (linked NEW signal) over the global url.
        const missedDeepLink = (m.deepLink as string) || url;
        const missedLink = `\n\n<a href="${missedDeepLink}">${built.cta}</a>`;
        return `${built.text}${missedLink}`;
      }

      case 'PERSONAL':
        // PERSONAL v2 — invokes user's memory of recent opens, not abstract "patterns"
        if (factLine) return `👀 <b>${asset} again</b>\n${factLine} · similar to signals you opened recently${directionLine}${link}`;
        return `👀 <b>${asset} again</b>\nSimilar to signals you opened recently${directionLine}${link}`;

      // ── Product signal types — delegate to source-specific builders ────────────
      case 'LISTING':
      case 'EXPLOIT':
      case 'ETF':
      case 'REGULATION': {
        const watchersCount = typeof m.watchersCount === 'number' ? Math.round(m.watchersCount) : undefined;
        const built = buildSentimentMessage(event, watchersCount);
        if (built) return `${built.text}${link}`;
        return `<b>${asset} signal</b>\n${event.reason || ''}${link}`;
      }

      // ── News (breaking / market-moving) ──────────────────────────────────────
      case 'NEWS': {
        const watchersCount = typeof m.watchersCount === 'number' ? Math.round(m.watchersCount) : undefined;
        const built = buildNewsMessage(event, watchersCount);
        const marketLink = `\n\n<a href="${url}">${built?.cta || '→ See market impact'}</a>`;
        if (built) return `${built.text}${marketLink}`;
        return `<b>Market news</b>\n${event.reason || ''}${marketLink}`;
      }
      case 'POLY_MISPRICING':
      case 'POLY_REPRICING':
      case 'POLY_OVERHEATED':
      case 'POLY_THESIS_WEAKENED': {
        const watchersCount = typeof m.watchersCount === 'number' ? Math.round(m.watchersCount) : undefined;
        const built = buildPolymarketMessage(event, watchersCount);
        // Polymarket link points to news feed (market context) — not asset setup.
        const marketLink = `\n\n<a href="${url}">${built?.cta || '→ See market opportunity'}</a>`;
        if (built) return `${built.text}${marketLink}`;
        return `<b>Market signal</b>\n${event.reason || ''}${marketLink}`;
      }

      // ── Wave 4: Actor (social ignition) ──────────────────────────────────────
      case 'ACTOR_MENTION_SPIKE':
      case 'ACTOR_NARRATIVE_PUSH': {
        const watchersCount = typeof m.watchersCount === 'number' ? Math.round(m.watchersCount) : undefined;
        const built = buildActorMessage(event, watchersCount);
        const actorLink = `\n\n<a href="${url}">${built?.cta || `→ Track ${asset} setup`}</a>`;
        if (built) return `${built.text}${actorLink}`;
        return `<b>${asset} actor signal</b>\n${event.reason || ''}${actorLink}`;
      }

      // ── Wave 4: Whale (money movement) ───────────────────────────────────────
      case 'WHALE_EXCHANGE_INFLOW':
      case 'WHALE_EXCHANGE_OUTFLOW': {
        const watchersCount = typeof m.watchersCount === 'number' ? Math.round(m.watchersCount) : undefined;
        const built = buildWhaleMessage(event, watchersCount);
        // Whale inflow → see downside; outflow → see setup (handled by builder cta).
        const whaleLink = `\n\n<a href="${url}">${built?.cta || `→ See ${asset} setup`}</a>`;
        if (built) return `${built.text}${whaleLink}`;
        return `<b>${asset} whale flow</b>\n${event.reason || ''}${whaleLink}`;
      }

      // ── Wave 4: MetaBrain (system decision) ──────────────────────────────────
      case 'METABRAIN_DECISION_SHIFT':
      case 'METABRAIN_CONVICTION_JUMP': {
        const watchersCount = typeof m.watchersCount === 'number' ? Math.round(m.watchersCount) : undefined;
        const built = buildMetabrainMessage(event, watchersCount);
        const brainLink = `\n\n<a href="${url}">${built?.cta || `→ See ${asset} entry`}</a>`;
        if (built) return `${built.text}${brainLink}`;
        return `<b>${asset} system decision</b>\n${event.reason || ''}${brainLink}`;
      }

      case 'TENSION':
        return `⚠️ <b>Market shifting</b>\nConflicting signals across top assets${link}`;

      case 'DIGEST_MORNING':
        return `⚠️ <b>Market waking up</b>\n${event.reason || 'Signals forming across assets'}${link}`;

      case 'DIGEST_EVENING':
        return `👀 <b>You missed moves earlier today</b>\n${event.reason || 'Signals played out today'}${link}`;

      default:
        return `<b>${asset} update</b>${factLine ? '\n' + factLine : ''}${link}`;
    }
  }

  if (event.category === 'alert') {
    const base = `🔔 <b>${asset} — ${event.type}</b>`;
    if (event.reason) return `${base}\n${event.reason}${directionLine}${link}`;
    if (factLine) return `${base}\n${factLine}${directionLine}${link}`;
    return `${base}\nWatch closely${directionLine}${link}`;
  }

  return `<b>${asset} — ${event.type}</b>${link}`;
}

// ─── ADMIN voice (structured, diagnostic) ──────────────────────────────────
function buildAdminMessage(event: UnifiedEvent): string {
  const lines: string[] = [
    `<b>[${event.category.toUpperCase()} · ${event.type}]</b>`,
  ];
  if (event.asset) lines.push(`asset: <code>${event.asset}</code>`);
  if (event.stage) lines.push(`stage: <code>${event.stage}</code>`);
  if (typeof event.alpha === 'number') lines.push(`alpha: <code>${event.alpha.toFixed(3)}</code>`);
  if (event.severity) lines.push(`severity: <code>${event.severity}</code>`);
  lines.push(`source: <code>${event.source}</code>`);
  lines.push(`id: <code>${event.id}</code>`);
  if (event.reason) lines.push(`reason: ${event.reason}`);
  if (event.meta && Object.keys(event.meta).length) {
    // Compact meta as key=value pairs
    const parts = Object.entries(event.meta)
      .slice(0, 6)
      .map(([k, v]) => `${k}=${typeof v === 'object' ? JSON.stringify(v) : String(v)}`);
    lines.push(`meta: ${parts.join(' · ')}`);
  }
  lines.push(`\n<a href="${buildDeepLink(event)}">open →</a>`);
  return lines.join('\n');
}

export function buildMessage(event: UnifiedEvent, role: SubscriberRole = 'user'): BuiltMessage {
  const text = role === 'admin' ? buildAdminMessage(event) : buildUserMessage(event);
  const deepLink = buildDeepLink(event);

  // Extract CTA label from text (last "→ <cta>" line that was rendered inside <a href>) so
  // we can promote it into a Telegram inline_keyboard button. The inline_keyboard button
  // renders as a real tap target (no link-preview card, 1-tap into Mini App).
  const asset = event.asset || 'setup';
  let ctaLabel = `→ See ${asset} setup`;
  const m = text.match(/<a\s+href="[^"]*">([\s\S]*?)<\/a>\s*$/i);
  if (m && m[1]) {
    // If message-builder emitted its own CTA (e.g. "→ See what's driving it"), upgrade to
    // asset-specific variant to make the action concrete.
    const raw = m[1].trim();
    if (/see what/i.test(raw) || /open in app/i.test(raw)) {
      ctaLabel = `→ See ${asset} setup`;
    } else {
      ctaLabel = raw;
    }
  } else if (event.category === 'retention') {
    // Fallback labels per type — always asset-specific when we have the asset
    if (event.type === 'MISSED') ctaLabel = `→ Don't miss ${asset} next one`;
    else if (event.type === 'CONFIRMED') ctaLabel = `→ See ${asset} setup`;
    else if (event.type === 'PERSONAL') ctaLabel = `→ See ${asset} setup`;
    else ctaLabel = `→ Open ${asset}`;
  }

  // Strip the trailing <a href>…</a> line from text so Telegram doesn't render a link-preview
  // card (the infamous "FOMO App · AI-powered…" block). The tap target is the inline button.
  const cleaned = text.replace(/\n?\n?<a\s+href="[^"]*">[\s\S]*?<\/a>\s*$/i, '').trim();

  return {
    text: cleaned,
    parseMode: 'HTML',
    deepLink,
    inlineButton: { text: ctaLabel, webAppUrl: deepLink },
  };
}
