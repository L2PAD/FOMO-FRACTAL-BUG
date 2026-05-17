/**
 * Layer 4 — Evidence Weighting
 *
 * Gives each signal a role and multi-dimensional weight:
 * trust, novelty, relevance, resolutionImpact, narrativeImpact, pricedIn.
 */
import type { EvidenceItem, WeightedEvidence, EventUnderstanding, CaseInput } from '../types/case.types.js';

const TRUST_BY_TIER: Record<string, number> = {
  tier1: 0.95,
  tier2: 0.7,
  tier3: 0.35,
};

const TRUST_BY_TYPE: Record<string, number> = {
  official: 0.95,
  media: 0.65,
  onchain: 0.8,
  exchange: 0.85,
  social: 0.3,
  unknown: 0.2,
};

function computeNovelty(ev: EvidenceItem, allItems: EvidenceItem[]): number {
  const text = ev.text.toLowerCase().slice(0, 60);
  let similar = 0;
  for (const other of allItems) {
    if (other.id === ev.id) continue;
    const otherText = other.text.toLowerCase().slice(0, 60);
    if (text === otherText || (text.length > 10 && otherText.includes(text.slice(0, 30)))) {
      similar++;
    }
  }
  return similar === 0 ? 1.0 : Math.max(0.1, 1.0 / (1 + similar));
}

function computeRelevance(ev: EvidenceItem, eventUnderstanding: EventUnderstanding): number {
  let score = 0.3;
  const text = ev.text.toLowerCase();

  for (const actor of eventUnderstanding.actors) {
    if (text.includes(actor)) score += 0.2;
  }
  for (const obj of eventUnderstanding.objects) {
    if (text.includes(obj.toLowerCase())) score += 0.15;
  }
  if (text.includes(eventUnderstanding.action)) score += 0.15;

  return Math.min(1, score);
}

function computeResolutionImpact(ev: EvidenceItem, eventUnderstanding: EventUnderstanding): number {
  const text = ev.text.toLowerCase();

  // Check if evidence directly relates to resolution mechanism
  for (const proof of eventUnderstanding.resolution.requiredProofs) {
    if (text.includes(proof.toLowerCase().split(' ')[0])) return 0.9;
  }

  // Official sources get higher resolution impact
  if (ev.sourceType === 'official') return 0.8;
  if (ev.sourceType === 'onchain' && eventUnderstanding.eventClass === 'threshold') return 0.85;
  if (ev.sourceType === 'media') return 0.4;
  return 0.15;
}

function computePricedIn(ev: EvidenceItem, marketState: CaseInput['marketState']): number {
  const ageHours = (Date.now() - ev.timestamp) / (1000 * 3600);

  // If large move already happened, signals are likely priced in
  const move = Math.abs(marketState.move6h || 0);
  if (move > 15 && ageHours > 6) return 0.9;
  if (move > 10 && ageHours > 3) return 0.7;
  if (move > 5 && ageHours > 1)  return 0.5;
  if (ageHours > 24)              return 0.6;
  return 0.15;
}

function assignRole(ev: EvidenceItem, dims: WeightedEvidence['dimensions']): WeightedEvidence['role'] {
  if (dims.resolutionImpact > 0.7 && dims.trust > 0.7) return 'driver';
  if (dims.trust > 0.5 && dims.relevance > 0.5) return 'confirmation';
  if (dims.trust < 0.3 || dims.novelty < 0.2) return 'noise';
  // Check for contradiction: low trust + opposing sentiment
  if (dims.narrativeImpact < 0.3 && dims.relevance < 0.4) return 'noise';
  return 'confirmation';
}

export function weightEvidence(
  items: EvidenceItem[],
  eventUnderstanding: EventUnderstanding,
  input: CaseInput,
): WeightedEvidence[] {
  return items.map(ev => {
    const trust = Math.max(TRUST_BY_TIER[ev.sourceTier] || 0.3, TRUST_BY_TYPE[ev.sourceType] || 0.2);
    const novelty = computeNovelty(ev, items);
    const relevance = computeRelevance(ev, eventUnderstanding);
    const resolutionImpact = computeResolutionImpact(ev, eventUnderstanding);
    const narrativeImpact = ev.sourceType === 'social' ? 0.6 : 0.3;
    const pricedIn = computePricedIn(ev, input.marketState);

    const dimensions = { trust, novelty, relevance, resolutionImpact, narrativeImpact, pricedIn };
    const weight = (trust * 0.25 + novelty * 0.15 + relevance * 0.2 + resolutionImpact * 0.25 + (1 - pricedIn) * 0.15);
    const role = assignRole(ev, dimensions);

    return {
      ...ev,
      weight: Math.round(weight * 100) / 100,
      role,
      dimensions: {
        trust: Math.round(trust * 100) / 100,
        novelty: Math.round(novelty * 100) / 100,
        relevance: Math.round(relevance * 100) / 100,
        resolutionImpact: Math.round(resolutionImpact * 100) / 100,
        narrativeImpact: Math.round(narrativeImpact * 100) / 100,
        pricedIn: Math.round(pricedIn * 100) / 100,
      },
    };
  });
}
