/**
 * Layer 1 — Event Understanding
 *
 * Decomposes the market question into structured event understanding:
 * actors, objects, action, resolution path, dependencies, time sensitivity.
 */
import type { CaseInput, EventUnderstanding } from '../types/case.types.js';

const EVENT_CLASS_MAP: Record<string, EventUnderstanding['eventClass']> = {
  price_threshold:  'threshold',
  direction_bet:    'threshold',
  generic_crypto:   'threshold',
  etf_catalyst:     'catalyst',
  listing_catalyst: 'listing',
  launch_catalyst:  'launch',
  token_launch:     'launch',
};

const RESOLUTION_MAP: Record<string, EventUnderstanding['resolution']> = {
  catalyst: {
    sourceOfTruth: 'Official regulatory filing or announcement',
    requiredProofs: ['SEC filing', 'Official issuer confirmation', 'Regulatory record'],
    invalidProofs: ['Journalist speculation', 'Twitter rumor', 'Secondary commentary'],
  },
  threshold: {
    sourceOfTruth: 'Price feed from major exchanges',
    requiredProofs: ['Spot price crossing threshold', 'Sustained above/below level'],
    invalidProofs: ['Flash wick only', 'Single exchange anomaly'],
  },
  listing: {
    sourceOfTruth: 'Exchange official announcement',
    requiredProofs: ['Exchange blog post', 'Trading pair live', 'Official Twitter'],
    invalidProofs: ['Leak from insider', 'Community rumor', 'Fake screenshot'],
  },
  launch: {
    sourceOfTruth: 'Mainnet deployment or TGE confirmation',
    requiredProofs: ['On-chain deployment', 'Team official announcement', 'Token live on explorers'],
    invalidProofs: ['Testnet only', 'Delayed announcement', 'Whitepaper claim'],
  },
};

function extractActors(question: string, entities: string[]): string[] {
  const actors: string[] = [];
  const q = question.toLowerCase();

  const KNOWN_ACTORS = [
    'blackrock', 'fidelity', 'grayscale', 'sec', 'cftc', 'fed',
    'binance', 'coinbase', 'kraken', 'okx', 'bybit',
    'microstrategy', 'tesla', 'trump', 'gensler', 'vitalik', 'cz',
  ];

  for (const actor of KNOWN_ACTORS) {
    if (q.includes(actor)) actors.push(actor);
  }

  for (const e of entities) {
    const lower = e.toLowerCase();
    if (!actors.includes(lower) && lower.length > 2) actors.push(lower);
  }

  return actors.length ? actors : ['market'];
}

function extractAction(eventType: string, question: string): string {
  const q = question.toLowerCase();
  if (q.includes('file') || q.includes('filing'))   return 'filing';
  if (q.includes('approv'))                          return 'approval';
  if (q.includes('list'))                            return 'listing';
  if (q.includes('launch') || q.includes('mainnet'))  return 'launch';
  if (q.includes('reach') || q.includes('hit'))      return 'price_crossing';
  if (q.includes('above') || q.includes('below'))    return 'price_level';
  if (q.includes('drop') || q.includes('fall'))      return 'price_decline';
  return 'market_outcome';
}

function computeTimeSensitivity(deadline?: string): EventUnderstanding['timeSensitivity'] {
  if (!deadline) return 'low';
  const daysLeft = (new Date(deadline).getTime() - Date.now()) / (1000 * 3600 * 24);
  if (daysLeft <= 3) return 'high';
  if (daysLeft <= 14) return 'medium';
  return 'low';
}

export function analyzeEvent(input: CaseInput): EventUnderstanding {
  const eventClass = EVENT_CLASS_MAP[input.decoded.eventType] || 'threshold';
  const actors = extractActors(input.question, input.decoded.entities);
  const objects = [input.decoded.asset, ...input.decoded.entities.filter(e => e !== input.decoded.asset)];
  const action = extractAction(input.decoded.eventType, input.question);
  const resolution = RESOLUTION_MAP[eventClass] || RESOLUTION_MAP.threshold;
  const dependencies = actors.filter(a => a !== 'market');

  return {
    eventClass,
    actors,
    objects,
    action,
    resolution,
    dependencies,
    timeSensitivity: computeTimeSensitivity(input.decoded.deadline),
  };
}
