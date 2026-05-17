/**
 * Layer 8 — Decision Memo Composer
 *
 * Final output: structured reasoning memo, not just a score.
 * thesis + counterThesis + market gap + action + conviction + reasons.
 */
import type { DecisionMemo, ThesisResult, MarketGap, RiskMap, EventUnderstanding, CaseInput, WeightedEvidence } from '../types/case.types.js';

function composeAction(thesis: ThesisResult, gap: MarketGap, risks: RiskMap, input: CaseInput): DecisionMemo['action'] {
  const bullStrong = thesis.bullCase.strength > 0.5;
  const bearStrong = thesis.bearCase.strength > 0.5;
  const highRisk = risks.risks.some(r => r.severity > 0.7);
  const isUnderreaction = gap.mispricingType === 'underreaction';
  const isOverreaction = gap.mispricingType === 'overreaction';

  if (bullStrong && isUnderreaction && !highRisk) return 'YES_NOW';
  if (bearStrong && !bullStrong) return 'NO_NOW';
  if (isOverreaction) return 'AVOID';
  if (bullStrong && gap.pricedInLevel > 0.7) return 'WAIT';
  if (thesis.bullCase.strength > 0.3 && !highRisk) return 'WAIT';
  return 'AVOID';
}

function composeConviction(thesis: ThesisResult, gap: MarketGap, weighted: WeightedEvidence[]): DecisionMemo['conviction'] {
  const drivers = weighted.filter(w => w.role === 'driver');
  const confirmations = weighted.filter(w => w.role === 'confirmation');

  if (drivers.length >= 2 && thesis.bullCase.strength > 0.6 && gap.pricedInLevel < 0.5) return 'HIGH';
  if (drivers.length >= 1 && confirmations.length >= 1 && gap.pricedInLevel < 0.7) return 'MEDIUM';
  return 'LOW';
}

function composeSummary(action: string, conviction: string, gap: MarketGap, event: EventUnderstanding): string {
  const mispricingLabel =
    gap.mispricingType === 'underreaction' ? 'Market appears to underreact' :
    gap.mispricingType === 'overreaction' ? 'Market appears to overreact' :
    'Market fairly priced';

  return `${event.eventClass} event on ${event.objects.join(', ')}. ${mispricingLabel}. ` +
    `Priced-in: ${(gap.pricedInLevel * 100).toFixed(0)}%. Action: ${action} (${conviction})`;
}

function composeWhyNow(thesis: ThesisResult, gap: MarketGap, event: EventUnderstanding): string[] {
  const reasons: string[] = [];
  if (gap.mispricingType === 'underreaction') reasons.push('Market has not fully absorbed available signals');
  if (event.timeSensitivity === 'high') reasons.push('Deadline approaching — urgency');
  if (thesis.bullCase.strength > 0.5) reasons.push('Strong evidence base supports thesis');
  if (gap.marketMisses.length > 1) reasons.push(`Market misses ${gap.marketMisses.length} signals`);
  return reasons.length ? reasons : ['No strong urgency for immediate action'];
}

function composeWhyNot(thesis: ThesisResult, gap: MarketGap, risks: RiskMap): string[] {
  const reasons: string[] = [];
  if (gap.pricedInLevel > 0.7) reasons.push('Most information already priced in');
  if (thesis.bearCase.strength > 0.4) reasons.push('Bear case has substance');
  for (const r of risks.risks.filter(r => r.severity > 0.5)) {
    reasons.push(r.description);
  }
  if (risks.invalidators.length > 0) reasons.push(`${risks.invalidators.length} known invalidator(s)`);
  return reasons.length ? reasons : ['No significant counter-arguments'];
}

export function composeMemo(
  event: EventUnderstanding,
  thesis: ThesisResult,
  gap: MarketGap,
  risks: RiskMap,
  weighted: WeightedEvidence[],
  input: CaseInput,
): DecisionMemo {
  const action = composeAction(thesis, gap, risks, input);
  const conviction = composeConviction(thesis, gap, weighted);

  return {
    summary: composeSummary(action, conviction, gap, event),
    thesis: thesis.bullCase.arguments.join('. '),
    counterThesis: thesis.bearCase.arguments.join('. '),
    keyDrivers: weighted.filter(w => w.role === 'driver').map(w => `[${w.source}] ${w.text.slice(0, 80)}`),
    keyRisks: risks.risks.slice(0, 4).map(r => r.description),
    whatMarketPricesIn: gap.marketKnows,
    whatMarketMisses: gap.marketMisses,
    action,
    conviction,
    whyNow: composeWhyNow(thesis, gap, event),
    whyNot: composeWhyNot(thesis, gap, risks),
  };
}
