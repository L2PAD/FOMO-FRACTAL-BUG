/**
 * Layer 5 — Thesis Engine
 *
 * Builds structured bull/bear/neutral thesis from weighted evidence.
 * Always builds BOTH sides — never one-sided.
 */
import type { WeightedEvidence, ThesisResult, EventUnderstanding, CaseInput } from '../types/case.types.js';

function buildBullArguments(drivers: WeightedEvidence[], confirmations: WeightedEvidence[], event: EventUnderstanding, input: CaseInput): string[] {
  const args: string[] = [];

  if (drivers.length > 0) {
    args.push(`${drivers.length} high-impact driver${drivers.length > 1 ? 's' : ''} detected from trusted sources`);
  }
  if (confirmations.length > 0) {
    args.push(`${confirmations.length} confirming signal${confirmations.length > 1 ? 's' : ''} across independent sources`);
  }

  // Onchain support
  const onchainDrivers = drivers.filter(d => d.sourceType === 'onchain');
  if (onchainDrivers.length > 0) {
    args.push('On-chain activity supports directional thesis');
  }

  // Price underreaction
  const move = Math.abs(input.marketState.move6h || 0);
  if (drivers.length > 0 && move < 5) {
    args.push('Price has not yet reacted to strong signals — potential underreaction');
  }

  // Low probability = room to move
  if (input.marketState.impliedProb < 0.4 && drivers.length > 0) {
    args.push(`Market implies ${(input.marketState.impliedProb * 100).toFixed(0)}% — room for upside if thesis correct`);
  }

  // Time pressure
  if (event.timeSensitivity === 'high') {
    args.push('Deadline approaching — forced resolution creates urgency');
  }

  return args.length ? args : ['Insufficient evidence for strong bull case'];
}

function buildBearArguments(contradictions: WeightedEvidence[], noise: WeightedEvidence[], event: EventUnderstanding, input: CaseInput): string[] {
  const args: string[] = [];

  if (contradictions.length > 0) {
    args.push(`${contradictions.length} contradictory signal${contradictions.length > 1 ? 's' : ''} found`);
  }

  const move = Math.abs(input.marketState.move6h || 0);
  if (move > 10) {
    args.push(`Price already moved ${move.toFixed(0)}% in 6h — late entry risk`);
  }

  if (input.marketState.impliedProb > 0.8) {
    args.push(`Market at ${(input.marketState.impliedProb * 100).toFixed(0)}% — limited remaining upside`);
  }

  if (noise.length > 5) {
    args.push('High noise level — narrative may be echo-driven rather than fundamental');
  }

  if (input.marketState.spread > 5) {
    args.push(`Wide spread (${input.marketState.spread.toFixed(1)}%) — poor execution conditions`);
  }

  // Resolution risk
  if (event.resolution.invalidProofs.length > 0 && contradictions.length > 0) {
    args.push('Some evidence matches known invalid proof patterns');
  }

  return args.length ? args : ['No strong counter-arguments identified'];
}

function buildNeutralArguments(weighted: WeightedEvidence[], input: CaseInput): string[] {
  const args: string[] = [];
  const drivers = weighted.filter(w => w.role === 'driver');
  const contradictions = weighted.filter(w => w.role === 'contradiction');

  if (drivers.length > 0 && contradictions.length > 0) {
    args.push('Mixed signals — drivers and contradictions both present');
  }

  if (input.marketState.impliedProb > 0.45 && input.marketState.impliedProb < 0.55) {
    args.push('Market near 50/50 — no clear directional bias');
  }

  const avgPricedIn = weighted.length
    ? weighted.reduce((s, w) => s + w.dimensions.pricedIn, 0) / weighted.length
    : 0;
  if (avgPricedIn > 0.6) {
    args.push('Most available information appears already priced in');
  }

  return args;
}

export function buildThesis(weighted: WeightedEvidence[], event: EventUnderstanding, input: CaseInput): ThesisResult {
  const drivers = weighted.filter(w => w.role === 'driver');
  const confirmations = weighted.filter(w => w.role === 'confirmation');
  const contradictions = weighted.filter(w => w.role === 'contradiction');
  const noise = weighted.filter(w => w.role === 'noise');

  const bullArgs = buildBullArguments(drivers, confirmations, event, input);
  const bearArgs = buildBearArguments(contradictions, noise, event, input);
  const neutralArgs = buildNeutralArguments(weighted, input);

  // Strength calculation
  const bullStrength = Math.min(1, (drivers.length * 0.3 + confirmations.length * 0.15) / 1.0);
  const bearStrength = Math.min(1, (contradictions.length * 0.3 + noise.length * 0.05) / 1.0);

  return {
    bullCase: { arguments: bullArgs, strength: Math.round(bullStrength * 100) / 100 },
    bearCase: { arguments: bearArgs, strength: Math.round(bearStrength * 100) / 100 },
    neutralCase: { arguments: neutralArgs },
  };
}
