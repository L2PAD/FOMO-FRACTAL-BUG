/**
 * Layer 1 — Echo Filter
 *
 * Separates real signal from echo in a cluster.
 * Echo types: retweet (100%), quote (60%), paraphrase (40%).
 *
 * echoScore = (retweets*1 + quotes*0.6 + paraphrases*0.4) / total
 */
import type { SocialEvent, SocialCluster } from '../types/social.types.js';

function normalize(text: string): string {
  return text.toLowerCase().replace(/https?:\/\/\S+/g, '').replace(/[@#]\w+/g, '').replace(/[^\w\s]/g, '').replace(/\s+/g, ' ').trim();
}

export type EchoResult = {
  rawCount: number;
  uniqueCount: number;
  echoCount: number;
  echoScore: number;
  retweets: number;
  quotes: number;
  paraphrases: number;
  originals: number;
};

function classifyEchoType(event: SocialEvent, canonical: string): 'retweet' | 'quote' | 'paraphrase' | 'original' {
  if (event.repostOfId) return 'retweet';
  if (event.quotedEventId) return 'quote';

  const normEvent = normalize(event.text);
  const normCanon = normalize(canonical);

  // Exact or near-exact match = retweet-like
  if (normEvent === normCanon) return 'retweet';

  // High overlap = paraphrase
  const eventWords = new Set(normEvent.split(' ').filter(w => w.length > 3));
  const canonWords = new Set(normCanon.split(' ').filter(w => w.length > 3));
  if (!eventWords.size || !canonWords.size) return 'original';

  let overlap = 0;
  for (const w of eventWords) {
    if (canonWords.has(w)) overlap++;
  }
  const ratio = overlap / Math.max(eventWords.size, canonWords.size);
  if (ratio > 0.6) return 'paraphrase';

  return 'original';
}

export function filterEcho(cluster: SocialCluster): EchoResult {
  const total = cluster.events.length;
  if (total === 0) return { rawCount: 0, uniqueCount: 0, echoCount: 0, echoScore: 0, retweets: 0, quotes: 0, paraphrases: 0, originals: 0 };
  if (total === 1) return { rawCount: 1, uniqueCount: 1, echoCount: 0, echoScore: 0, retweets: 0, quotes: 0, paraphrases: 0, originals: 1 };

  let retweets = 0, quotes = 0, paraphrases = 0, originals = 0;

  // First event in cluster is always treated as original
  originals = 1;

  for (let i = 1; i < cluster.events.length; i++) {
    const ev = cluster.events[i];
    const type = classifyEchoType(ev, cluster.canonicalText);
    if (type === 'retweet') retweets++;
    else if (type === 'quote') quotes++;
    else if (type === 'paraphrase') paraphrases++;
    else originals++;
  }

  const weightedEcho = retweets * 1.0 + quotes * 0.6 + paraphrases * 0.4;
  const echoScore = total > 0 ? Math.round((weightedEcho / total) * 100) / 100 : 0;

  return {
    rawCount: total,
    uniqueCount: originals + quotes,
    echoCount: retweets + quotes + paraphrases,
    echoScore: Math.min(1, echoScore),
    retweets,
    quotes,
    paraphrases,
    originals,
  };
}
