/**
 * News Classifier — hard filter for breaking / market-moving news
 * ================================================================
 * Without this, every news_articles row would trigger a push — noise fast.
 * Rule: only news with tier=A + critical tags OR tier=A+B with Markets/Macro
 * emphasis make it through.
 *
 * Works with the real news_articles shape we have:
 *   { tier:'A'|'B'|'C', tags:string[], title, summary, source_name,
 *     entities_mentioned:string[], entity_count, published_at }
 */

export interface NewsClassification {
  isBreaking: boolean;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM';
  score: number;
  reason: string;
  sentiment: 'bullish' | 'bearish' | 'neutral';
  direction: -1 | 0 | 1;
}

// Tags that flip a news into CRITICAL regardless of tier (market-moving)
const CRITICAL_TAGS = new Set([
  'ETF', 'Regulation', 'Exchange', 'Exploit', 'Hack', 'Ban', 'SEC',
  'Approval', 'Enforcement', 'Breach', 'Security', 'Court'
]);

// Tags indicating market relevance (HIGH if tier=A, MEDIUM if tier=B)
const MARKET_TAGS = new Set([
  'Markets', 'Macro', 'Trading', 'Crypto Ecosystems', 'Public Equities',
  'Equities', 'Stablecoins', 'DeFi', 'Layer 1', 'Bitcoin', 'Ethereum'
]);

// Tier → source reputation
const TIER_REP: Record<string, number> = { A: 1.0, B: 0.6, C: 0.3 };

// Simple sentiment lexicon (last-resort, keyword match on title+summary)
const BULLISH_KW = /\b(approved|approval|breakthrough|surge|rally|record\s*high|all-time\s*high|bull(?:ish)?|jump|soar|adopt|partnership|inflow|gain|growth|expan(d|sion)|launch|unlock)\b/i;
const BEARISH_KW = /\b(hack(ed)?|exploit|breach|ban|block(ed)?|delist|reject(ed)?|denied|probe|investigation|crash|plunge|dump|sell-?off|losses?|exploit|lawsuit|sue(d)?|fine(d)?|enforcement|outflow|decline|bear(ish)?)\b/i;

function detectSentiment(article: any): { direction: -1 | 0 | 1; label: 'bullish' | 'bearish' | 'neutral' } {
  const haystack = `${article.title || ''} ${article.summary || ''}`;
  if (BEARISH_KW.test(haystack)) return { direction: -1, label: 'bearish' };
  if (BULLISH_KW.test(haystack)) return { direction: 1, label: 'bullish' };
  return { direction: 0, label: 'neutral' };
}

export function classifyBreakingNews(article: any): NewsClassification {
  const tags: string[] = Array.isArray(article.tags) ? article.tags : [];
  const tier = String(article.tier || 'C').toUpperCase();
  const sourceRep = TIER_REP[tier] ?? 0.3;
  const entityCount = Number(article.entity_count || (article.entities_mentioned?.length ?? 0));

  const hasCritical = tags.some(t => CRITICAL_TAGS.has(t));
  const hasMarket = tags.some(t => MARKET_TAGS.has(t));

  // Normalized score 0..1
  const tagScore = hasCritical ? 1.0 : hasMarket ? 0.7 : 0.3;
  const entityScore = Math.min(entityCount / 5, 1);
  const score =
    sourceRep * 0.4 +
    tagScore * 0.4 +
    entityScore * 0.2;

  const sent = detectSentiment(article);

  // Hard rules — 80% of the filter
  let isBreaking = false;
  let priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' = 'MEDIUM';
  let reason = 'low-signal';

  if (hasCritical && (tier === 'A' || tier === 'B')) {
    isBreaking = true;
    priority = 'CRITICAL';
    reason = `critical_tag+${tier}`;
  } else if (tier === 'A' && hasMarket && score >= 0.7) {
    isBreaking = true;
    priority = score >= 0.85 ? 'HIGH' : 'MEDIUM';
    reason = `tierA+market+score${score.toFixed(2)}`;
  } else if (score >= 0.85) {
    isBreaking = true;
    priority = 'HIGH';
    reason = `high_score_${score.toFixed(2)}`;
  }

  return { isBreaking, priority, score, reason, sentiment: sent.label, direction: sent.direction };
}
