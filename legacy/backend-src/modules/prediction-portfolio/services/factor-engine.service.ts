/**
 * Factor Engine — Stage 7
 *
 * Builds 6-axis factor profiles from market case data.
 * Axes: asset, theme, catalyst, deadline, resolution, entity.
 *
 * Critical: if this engine is weak, the entire Portfolio Brain is useless.
 */
import type { FactorProfile, CandidateCase } from '../types/portfolio.types.js';

// ══════════════════════════════════════
// Asset Factor Mapping
// ══════════════════════════════════════

const ASSET_GROUPS: Record<string, string[]> = {
  BTC:    ['BTC', 'CRYPTO', 'DIGITAL_ASSET'],
  ETH:    ['ETH', 'CRYPTO', 'DIGITAL_ASSET', 'SMART_CONTRACT'],
  SOL:    ['SOL', 'CRYPTO', 'DIGITAL_ASSET', 'ALT_L1'],
  XRP:    ['XRP', 'CRYPTO', 'DIGITAL_ASSET', 'PAYMENTS'],
  DOGE:   ['DOGE', 'CRYPTO', 'DIGITAL_ASSET', 'MEME'],
  PEPE:   ['PEPE', 'CRYPTO', 'DIGITAL_ASSET', 'MEME'],
  ADA:    ['ADA', 'CRYPTO', 'DIGITAL_ASSET', 'ALT_L1'],
  AVAX:   ['AVAX', 'CRYPTO', 'DIGITAL_ASSET', 'ALT_L1'],
  LINK:   ['LINK', 'CRYPTO', 'DIGITAL_ASSET', 'ORACLE'],
  SUI:    ['SUI', 'CRYPTO', 'DIGITAL_ASSET', 'ALT_L1'],
  NEAR:   ['NEAR', 'CRYPTO', 'DIGITAL_ASSET', 'ALT_L1'],
  ARB:    ['ARB', 'CRYPTO', 'DIGITAL_ASSET', 'L2'],
  OP:     ['OP', 'CRYPTO', 'DIGITAL_ASSET', 'L2'],
};

// ══════════════════════════════════════
// Theme Factor Mapping
// ══════════════════════════════════════

const EVENT_TYPE_THEMES: Record<string, string[]> = {
  price_threshold:  ['PRICE_ACTION', 'BULL_MARKET'],
  direction_bet:    ['PRICE_ACTION', 'DIRECTION'],
  generic_crypto:   ['PRICE_ACTION'],
  etf_catalyst:     ['ETF_THEME', 'REGULATORY', 'INSTITUTIONAL'],
  listing_catalyst: ['EXCHANGE_THEME', 'LISTING'],
  launch_catalyst:  ['LAUNCH_THEME', 'NEW_TOKEN'],
  token_launch:     ['LAUNCH_THEME', 'NEW_TOKEN', 'TOKENOMICS'],
};

// ══════════════════════════════════════
// Catalyst Factor Mapping
// ══════════════════════════════════════

const EVENT_TYPE_CATALYSTS: Record<string, string[]> = {
  etf_catalyst:     ['OFFICIAL_FILING', 'SEC_DECISION', 'ETF_APPROVAL'],
  listing_catalyst: ['EXCHANGE_LISTING', 'MARKET_ACCESS'],
  launch_catalyst:  ['PROJECT_LAUNCH', 'MAINNET'],
  token_launch:     ['TOKEN_GENERATION', 'AIRDROP'],
  price_threshold:  ['TECHNICAL_LEVEL', 'PRICE_TARGET'],
  direction_bet:    ['SHORT_TERM_MOVE'],
  generic_crypto:   ['MARKET_EVENT'],
};

// ══════════════════════════════════════
// Deadline Factor Extraction
// ══════════════════════════════════════

function extractDeadlineFactors(endDate?: string): string[] {
  if (!endDate) return ['NO_DEADLINE'];

  const now = Date.now();
  const end = new Date(endDate).getTime();
  const daysLeft = Math.max(0, (end - now) / (1000 * 3600 * 24));

  const factors: string[] = [];

  if (daysLeft <= 1)       factors.push('EXPIRES_TODAY', 'ULTRA_SHORT');
  else if (daysLeft <= 3)  factors.push('EXPIRES_3D', 'ULTRA_SHORT');
  else if (daysLeft <= 7)  factors.push('EXPIRES_7D', 'SHORT_TERM');
  else if (daysLeft <= 30) factors.push('EXPIRES_30D', 'MEDIUM_TERM');
  else                     factors.push('EXPIRES_LONG', 'LONG_TERM');

  // Add month bucket for clustering
  const endMonth = new Date(endDate).toISOString().slice(0, 7); // YYYY-MM
  factors.push(`MONTH_${endMonth}`);

  return factors;
}

// ══════════════════════════════════════
// Resolution Factor Extraction
// ══════════════════════════════════════

function extractResolutionFactors(eventType: string, question: string): string[] {
  const factors: string[] = [];
  const q = question.toLowerCase();

  // Resolution mechanism
  if (eventType.includes('etf'))     factors.push('SEC_RESOLUTION', 'OFFICIAL_RESOLUTION');
  if (eventType.includes('listing')) factors.push('EXCHANGE_RESOLUTION');
  if (eventType.includes('launch'))  factors.push('PROJECT_RESOLUTION');
  if (eventType.includes('price') || eventType.includes('direction'))
    factors.push('PRICE_RESOLUTION', 'MARKET_RESOLUTION');

  // Specific resolution dependencies
  if (q.includes('sec') || q.includes('approval'))  factors.push('SEC_DEPENDENT');
  if (q.includes('binance') || q.includes('coinbase')) factors.push('EXCHANGE_DEPENDENT');
  if (q.includes('launch') || q.includes('mainnet'))   factors.push('LAUNCH_DEPENDENT');

  return factors.length ? factors : ['GENERIC_RESOLUTION'];
}

// ══════════════════════════════════════
// Entity Factor Extraction
// ══════════════════════════════════════

function extractEntityFactors(entities: string[], question: string): string[] {
  const factors = entities.map(e => `ENTITY_${e.toUpperCase()}`);
  const q = question.toLowerCase();

  // Extract additional entities from question
  const knownEntities = [
    'sec', 'cftc', 'fed', 'binance', 'coinbase', 'kraken',
    'blackrock', 'fidelity', 'grayscale', 'microstrategy',
    'trump', 'gensler', 'elon', 'vitalik', 'cz',
  ];

  for (const ent of knownEntities) {
    if (q.includes(ent)) {
      const tag = `ENTITY_${ent.toUpperCase()}`;
      if (!factors.includes(tag)) factors.push(tag);
    }
  }

  return factors.length ? factors : ['ENTITY_UNKNOWN'];
}

// ══════════════════════════════════════
// Main: Build Factor Profile
// ══════════════════════════════════════

export function buildFactorProfile(c: {
  asset: string;
  eventType: string;
  entities?: string[];
  question: string;
  endDate?: string;
}): FactorProfile {
  const asset = (c.asset || 'BTC').toUpperCase();

  return {
    assetFactors:       ASSET_GROUPS[asset] || [asset, 'CRYPTO', 'DIGITAL_ASSET'],
    themeFactors:       EVENT_TYPE_THEMES[c.eventType] || ['GENERIC'],
    catalystFactors:    EVENT_TYPE_CATALYSTS[c.eventType] || ['GENERIC'],
    deadlineFactors:    extractDeadlineFactors(c.endDate),
    resolutionFactors:  extractResolutionFactors(c.eventType, c.question),
    entityFactors:      extractEntityFactors(c.entities || [], c.question),
  };
}

/**
 * Deduplicate factors within each axis (safety).
 */
export function deduplicateProfile(profile: FactorProfile): FactorProfile {
  return {
    assetFactors:       [...new Set(profile.assetFactors)],
    themeFactors:       [...new Set(profile.themeFactors)],
    catalystFactors:    [...new Set(profile.catalystFactors)],
    deadlineFactors:    [...new Set(profile.deadlineFactors)],
    resolutionFactors:  [...new Set(profile.resolutionFactors)],
    entityFactors:      [...new Set(profile.entityFactors)],
  };
}
