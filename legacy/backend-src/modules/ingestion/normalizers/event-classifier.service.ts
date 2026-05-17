/**
 * Event Classifier
 * ================
 * Rule-based classification of text events into market-relevant categories.
 * This improves sentiment quality by weighting events by type.
 */

export type EventType =
  | 'bullish_news'
  | 'bearish_news'
  | 'neutral_info'
  | 'hype'
  | 'fear'
  | 'listing'
  | 'unlock'
  | 'regulation'
  | 'exploit'
  | 'macro'
  | 'partnership'
  | 'funding'
  | 'legal'
  | 'etf';

const RULES: Array<{ keywords: string[]; type: EventType }> = [
  // High-impact events first (order matters — first match wins)
  { keywords: ['hack', 'exploit', 'drain', 'stolen', 'breach', 'vulnerability', 'attack'], type: 'exploit' },
  { keywords: ['etf approval', 'etf filing', 'etf reject', 'spot etf', 'bitcoin etf', 'ethereum etf'], type: 'etf' },
  { keywords: ['listing', 'listed on', 'binance listing', 'coinbase listing', 'new trading pair'], type: 'listing' },
  { keywords: ['unlock', 'vesting', 'cliff', 'token release', 'token unlock'], type: 'unlock' },
  { keywords: ['sec ', 'cftc', 'regulation', 'regulatory', 'ban crypto', 'framework', 'compliance'], type: 'regulation' },
  { keywords: ['lawsuit', 'subpoena', 'indictment', 'guilty', 'settlement', 'enforcement', 'fine'], type: 'legal' },
  { keywords: ['partnership', 'collab', 'integrate', 'adoption', 'mainnet', 'upgrade'], type: 'partnership' },
  { keywords: ['funding round', 'series a', 'series b', 'raised', 'investment', 'venture'], type: 'funding' },
  { keywords: ['rug', 'scam', 'dump', 'crash', 'collapse', 'insolvent', 'bankrupt'], type: 'bearish_news' },
  { keywords: ['launch', 'bullish', 'all-time high', 'ath', 'surge', 'rally', 'breakout'], type: 'bullish_news' },
  { keywords: ['fed ', 'fomc', 'cpi ', 'inflation', 'rate cut', 'rate hike', 'gdp', 'jobs report', 'unemployment'], type: 'macro' },
  { keywords: ['moon', 'pump', 'lfg', 'wagmi', 'bullish af', 'send it'], type: 'hype' },
  { keywords: ['rekt', 'liquidat', 'capitulat', 'blood', 'ngmi'], type: 'fear' },
];

const EVENT_IMPACT_WEIGHTS: Record<EventType, number> = {
  exploit: 1.4,
  etf: 1.5,
  listing: 1.3,
  legal: 1.2,
  regulation: 1.1,
  partnership: 1.1,
  funding: 1.0,
  bullish_news: 1.2,
  bearish_news: 1.2,
  macro: 1.0,
  unlock: 1.0,
  fear: 0.9,
  hype: 0.8,
  neutral_info: 0.5,
};

const SOURCE_WEIGHTS: Record<string, number> = {
  twitter: 0.7,
  news: 1.0,
  telegram: 0.6,
};

class EventClassifierService {
  classify(text: string): EventType {
    const t = text.toLowerCase();

    for (const rule of RULES) {
      if (rule.keywords.some((kw) => t.includes(kw))) {
        return rule.type;
      }
    }

    return 'neutral_info';
  }

  getEventImpactWeight(type: EventType): number {
    return EVENT_IMPACT_WEIGHTS[type] ?? 1.0;
  }

  getSourceWeight(sourceType: string): number {
    return SOURCE_WEIGHTS[sourceType] ?? 0.8;
  }
}

export const eventClassifierService = new EventClassifierService();
