/**
 * Layer 6 — Market Gap Analysis
 *
 * The most important layer: what market already priced vs what it missed.
 * Determines mispricing type: underreaction / overreaction / correct.
 */
import type { WeightedEvidence, MarketGap, CaseInput } from '../types/case.types.js';

export function analyzeMarketGap(weighted: WeightedEvidence[], input: CaseInput): MarketGap {
  const drivers = weighted.filter(w => w.role === 'driver');
  const confirmations = weighted.filter(w => w.role === 'confirmation');
  const noise = weighted.filter(w => w.role === 'noise');

  const move6h = Math.abs(input.marketState.move6h || 0);
  const move1h = Math.abs(input.marketState.move1h || 0);

  // Compute priced-in level
  const avgPricedIn = weighted.length
    ? weighted.reduce((s, w) => s + w.dimensions.pricedIn, 0) / weighted.length
    : 0;

  // Adjust for price movement
  let pricedInLevel = avgPricedIn;
  if (move6h > 15) pricedInLevel = Math.max(pricedInLevel, 0.85);
  else if (move6h > 10) pricedInLevel = Math.max(pricedInLevel, 0.7);
  else if (move6h > 5) pricedInLevel = Math.max(pricedInLevel, 0.5);

  pricedInLevel = Math.round(pricedInLevel * 100) / 100;

  // Market knows
  const marketKnows: string[] = [];
  if (move6h > 5)                  marketKnows.push(`Price moved ${move6h.toFixed(0)}% in 6h — market reacting`);
  if (noise.length > 5)            marketKnows.push('High social/narrative saturation — story is widely known');
  if (input.marketState.volume24h > 50000) marketKnows.push('High trading volume — active market participation');
  if (input.marketState.impliedProb > 0.75) marketKnows.push(`High implied probability (${(input.marketState.impliedProb * 100).toFixed(0)}%) — market confident`);

  for (const d of drivers.filter(d => d.dimensions.pricedIn > 0.6)) {
    marketKnows.push(`${d.source}: ${d.text.slice(0, 60)}`);
  }

  // Market misses
  const marketMisses: string[] = [];

  // Fresh drivers not yet reflected in price
  for (const d of drivers.filter(d => d.dimensions.pricedIn < 0.4)) {
    marketMisses.push(`${d.source}: ${d.text.slice(0, 60)}`);
  }

  // Strong signals with no price reaction
  if (drivers.length > 0 && move6h < 3) {
    marketMisses.push('Strong drivers detected but price has not moved — potential underreaction');
  }

  // Onchain divergence
  const onchainSignals = weighted.filter(w => w.sourceType === 'onchain' && w.role === 'driver');
  if (onchainSignals.length > 0 && move6h < 5) {
    marketMisses.push('On-chain activity diverging from price — smart money may be ahead');
  }

  // Confirm signals from different categories
  const confirmedFromMultiple = confirmations.filter(c => c.sourceType !== 'social').length;
  if (confirmedFromMultiple >= 2 && move6h < 5) {
    marketMisses.push('Multiple independent confirmations not reflected in current price');
  }

  // Determine mispricing type
  let mispricingType: MarketGap['mispricingType'];
  if (drivers.length > 0 && pricedInLevel < 0.5) {
    mispricingType = 'underreaction';
  } else if (noise.length > drivers.length * 3 && move6h > 10) {
    mispricingType = 'overreaction';
  } else {
    mispricingType = 'correct';
  }

  return {
    pricedInLevel,
    marketKnows: marketKnows.length ? marketKnows : ['No clear indicators of what market has absorbed'],
    marketMisses: marketMisses.length ? marketMisses : ['No obvious mispricing detected'],
    mispricingType,
  };
}
