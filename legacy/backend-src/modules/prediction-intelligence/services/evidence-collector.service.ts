/**
 * Layer 2 — Evidence Collector
 *
 * Gathers ALL signals into a structured evidence pack:
 * primary, secondary, narrative, echo, contradictory, onchain.
 */
import type { CaseInput, EvidenceItem, EvidencePack } from '../types/case.types.js';

const TIER1_SOURCES = new Set([
  'sec', 'cftc', 'official', 'sec.gov', 'federal_register',
  'binance', 'coinbase', 'kraken',
]);

const TIER2_SOURCES = new Set([
  'bloomberg', 'reuters', 'coindesk', 'theblock', 'decrypt',
  'cointelegraph', 'blockworks',
]);

function inferTier(source: string): EvidenceItem['sourceTier'] {
  const s = source.toLowerCase();
  if (TIER1_SOURCES.has(s)) return 'tier1';
  if (TIER2_SOURCES.has(s)) return 'tier2';
  return 'tier3';
}

function inferType(source: string, category?: string): EvidenceItem['sourceType'] {
  if (category === 'onchain') return 'onchain';
  if (category === 'exchange') return 'exchange';
  const s = source.toLowerCase();
  if (TIER1_SOURCES.has(s)) return 'official';
  if (TIER2_SOURCES.has(s)) return 'media';
  if (s.includes('twitter') || s.includes('x.com')) return 'social';
  return 'unknown';
}

function toEvidence(raw: any, category: string): EvidenceItem {
  return {
    id: raw.id || raw._id || `${category}_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    text: raw.text || raw.title || raw.content || raw.summary || '',
    source: raw.source || raw.source_id || 'unknown',
    sourceType: inferType(raw.source || '', category),
    sourceTier: inferTier(raw.source || ''),
    timestamp: raw.timestamp || (raw.created_at ? new Date(raw.created_at).getTime() : Date.now()),
    entities: raw.entities || raw.assets || [],
    eventTags: raw.tags || raw.event_tags || [],
  };
}

export function collectEvidence(input: CaseInput): EvidencePack {
  const pack: EvidencePack = {
    primary: [],
    secondary: [],
    narrative: [],
    echo: [],
    contradictory: [],
    onchain: [],
  };

  // News signals → primary or secondary based on tier
  for (const raw of (input.signals.news || [])) {
    const ev = toEvidence(raw, 'news');
    if (ev.sourceTier === 'tier1') pack.primary.push(ev);
    else if (ev.sourceTier === 'tier2') pack.secondary.push(ev);
    else pack.narrative.push(ev);
  }

  // Twitter signals → narrative or echo (dedup by text similarity)
  const seenTexts = new Set<string>();
  for (const raw of (input.signals.twitter || [])) {
    const ev = toEvidence(raw, 'social');
    const normalized = ev.text.toLowerCase().replace(/\s+/g, ' ').trim().slice(0, 80);
    if (seenTexts.has(normalized)) {
      pack.echo.push(ev);
    } else {
      seenTexts.add(normalized);
      pack.narrative.push(ev);
    }
  }

  // Sentiment signals → check for contradictions
  for (const raw of (input.signals.sentiment || [])) {
    const ev = toEvidence(raw, 'sentiment');
    const bias = raw.bias || raw.sentiment;
    if (bias === 'bearish' || bias === 'negative') {
      pack.contradictory.push(ev);
    } else {
      pack.secondary.push(ev);
    }
  }

  // Onchain signals → dedicated bucket
  for (const raw of (input.signals.onchain || [])) {
    const ev = toEvidence(raw, 'onchain');
    pack.onchain.push(ev);
  }

  return pack;
}
