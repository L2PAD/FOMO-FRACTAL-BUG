/**
 * Event Enrichment Service
 *
 * Takes raw notification_events from MongoDB and enriches them with:
 * - Extracted source name and type
 * - Extracted entities (assets, companies)
 * - Extracted tags
 */
import type { RawEvent, EnrichedEvent } from '../types/event.types.js';

const ENTITY_KEYWORDS: Record<string, string[]> = {
  BTC: ['bitcoin', 'btc'],
  ETH: ['ethereum', 'eth'],
  SOL: ['solana', 'sol'],
  XRP: ['xrp', 'ripple'],
  BNB: ['bnb', 'binance'],
  DOGE: ['doge', 'dogecoin'],
  BLACKROCK: ['blackrock'],
  SEC: ['sec ', ' sec'],
  COINBASE: ['coinbase'],
  GRAYSCALE: ['grayscale'],
  FIDELITY: ['fidelity'],
};

const TAG_KEYWORDS: Record<string, string[]> = {
  etf: ['etf'],
  listing: ['listing', 'list on'],
  launch: ['launch', 'mainnet'],
  whale: ['whale', 'large transfer'],
  divergence: ['divergence'],
  drift: ['drift'],
  risk: ['risk', 'warning'],
  bullish: ['bullish', 'inflow', 'buy', 'accumul'],
  bearish: ['bearish', 'outflow', 'sell', 'distribut'],
};

/**
 * Enrich a raw event from notification_events
 */
export function enrichEvent(raw: Record<string, any>): EnrichedEvent {
  const text = [raw.title || '', raw.text || '', JSON.stringify(raw.payload || {})].join(' ');
  const lower = text.toLowerCase();

  const entities = extractEntities(lower);
  const tags = extractTags(lower);
  const sourceType = mapSourceType(raw.source || '', raw.type || '');

  return {
    id: raw.id || raw._id?.toString() || '',
    text: raw.title || raw.text || '',
    sourceId: raw.source || 'unknown',
    sourceType,
    asset: raw.asset || null,
    timestamp: raw.timestamp ? new Date(raw.timestamp).getTime() : Date.now(),
    entities: entities.length > 0 ? entities : (raw.asset ? [raw.asset] : []),
    tags,
    severity: raw.severity || 'low',
    payload: raw.payload || {},
    // enrichment fields
    extractedSource: raw.source || 'unknown',
    extractedSourceType: sourceType,
    extractedEntities: entities,
    extractedTags: tags,
  };
}

function extractEntities(text: string): string[] {
  const found: string[] = [];
  for (const [entity, keywords] of Object.entries(ENTITY_KEYWORDS)) {
    if (keywords.some(kw => text.includes(kw))) {
      found.push(entity);
    }
  }
  return [...new Set(found)];
}

function extractTags(text: string): string[] {
  const found: string[] = [];
  for (const [tag, keywords] of Object.entries(TAG_KEYWORDS)) {
    if (keywords.some(kw => text.includes(kw))) {
      found.push(tag);
    }
  }
  return [...new Set(found)];
}

function mapSourceType(source: string, eventType: string): string {
  const s = source.toLowerCase();
  if (s === 'exchange') return 'exchange';
  if (s === 'onchain') return 'onchain';
  if (s === 'sentiment') return 'sentiment';
  if (s === 'system') return 'system';
  if (eventType.includes('official') || eventType.includes('filing')) return 'official';
  return 'noise';
}
