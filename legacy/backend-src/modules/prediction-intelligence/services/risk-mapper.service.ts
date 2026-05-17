/**
 * Layer 7 — Risk Mapper
 *
 * Maps all risk dimensions and invalidators.
 */
import type { RiskMap, WeightedEvidence, EventUnderstanding, CaseInput } from '../types/case.types.js';

export function mapRisks(weighted: WeightedEvidence[], event: EventUnderstanding, input: CaseInput): RiskMap {
  const risks: RiskMap['risks'] = [];
  const invalidators: string[] = [];

  // Resolution risk
  if (event.eventClass === 'catalyst') {
    risks.push({
      type: 'resolution',
      severity: 0.6,
      description: 'Requires official confirmation — outcome depends on regulatory or institutional action',
    });
    invalidators.push('Official denial or rejection');
    invalidators.push('Regulatory postponement or delay');
  }

  if (event.eventClass === 'threshold') {
    const distanceToThreshold = Math.abs(
      (input.decoded.threshold || 0) - (input.decoded.threshold || 0) * (1 - input.marketState.impliedProb)
    );
    if (input.marketState.impliedProb > 0.4 && input.marketState.impliedProb < 0.6) {
      risks.push({
        type: 'resolution',
        severity: 0.5,
        description: 'Close to 50/50 — outcome highly uncertain',
      });
    }
    invalidators.push('Sudden market reversal or black swan event');
  }

  // Timing risk
  if (event.timeSensitivity === 'high') {
    risks.push({
      type: 'timing',
      severity: 0.7,
      description: 'Deadline approaching — reduced time to be right',
    });
  }

  const move6h = Math.abs(input.marketState.move6h || 0);
  if (move6h > 10) {
    risks.push({
      type: 'timing',
      severity: 0.6,
      description: `Large recent move (${move6h.toFixed(0)}%) — may be entering too late`,
    });
  }

  // False signal risk
  const contradictions = weighted.filter(w => w.role === 'contradiction');
  if (contradictions.length > 0) {
    risks.push({
      type: 'false_signal',
      severity: Math.min(0.8, 0.3 + contradictions.length * 0.15),
      description: `${contradictions.length} contradictory signal(s) — thesis may be wrong`,
    });
    invalidators.push('Contradicting evidence proves correct');
  }

  const noise = weighted.filter(w => w.role === 'noise');
  if (noise.length > 5) {
    risks.push({
      type: 'false_signal',
      severity: 0.4,
      description: 'High noise — narrative may be echo-driven',
    });
  }

  // Liquidity risk
  if (input.marketState.liquidity < 5000) {
    risks.push({
      type: 'liquidity',
      severity: 0.7,
      description: `Low liquidity ($${input.marketState.liquidity.toFixed(0)}) — difficult to enter/exit`,
    });
  }
  if (input.marketState.spread > 5) {
    risks.push({
      type: 'liquidity',
      severity: 0.5,
      description: `Wide spread (${input.marketState.spread.toFixed(1)}%) — poor execution`,
    });
  }

  // Wording risk
  if (event.eventClass === 'catalyst') {
    risks.push({
      type: 'wording',
      severity: 0.3,
      description: 'Market wording may have specific resolution criteria — verify exact conditions',
    });
    invalidators.push('Technicality in market resolution wording');
  }

  return {
    risks: risks.sort((a, b) => b.severity - a.severity),
    invalidators,
  };
}
