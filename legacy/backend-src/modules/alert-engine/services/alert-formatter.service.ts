/**
 * Alert Formatter
 *
 * Builds the final AlertPayload from case data.
 * Alerts = ACTION, not analysis.
 */

import { randomUUID } from 'crypto';
import type { AlertPayload, AlertType, AlertTier, AlertUrgency } from '../types/alert.types.js';

interface FormatInput {
  type: AlertType;
  tier: AlertTier;
  urgency: AlertUrgency;
  priority: number;
  case: Record<string, any>;
}

class AlertFormatterService {
  format(input: FormatInput): AlertPayload {
    const c = input.case;
    const analysis = c.analysis || {};
    const reco = c.recommendation || {};
    const el = c.executionLayer || {};
    const pi = c.projectIntel || {};

    // Build concise why/risks
    const why = this.buildWhy(c);
    const risks = this.buildRisks(c);

    return {
      id: randomUUID(),
      type: input.type,
      tier: input.tier,
      urgency: input.urgency,

      market: (c.question || '').slice(0, 100),
      marketId: c.market_id || '',
      asset: c.asset || '',
      action: reco.action || '',

      priority: input.priority,

      edge: analysis.net_edge || 0,
      confidence: analysis.model_confidence || 0,
      alignment: analysis.alignment_score || 0,

      execution: {
        entryStyle: el.entryStyle || '',
        slippageRisk: el.slippageRisk || 0,
        entryQualityScore: el.entryQualityScore || 0,
      },

      project: {
        verdict: pi.verdict || null,
        unlockRisk: pi.unlockRisk || null,
      },

      why,
      risks,

      timestamp: new Date().toISOString(),
    };
  }

  private buildWhy(c: Record<string, any>): string[] {
    const reasons: string[] = [];
    const repr = c.repricing || {};
    const el = c.executionLayer || {};
    const si = c.socialIntel || {};

    if (repr.repricing_state === 'fresh_mispricing') reasons.push('Fresh mispricing — early window');
    if (repr.repricing_state === 'early_repricing') reasons.push('Early repricing underway');
    if (el.entryStyle === 'ENTER_MARKET') reasons.push('Market order entry recommended');
    if (el.entryQualityScore > 0.75) reasons.push(`Strong entry quality (${(el.entryQualityScore * 100).toFixed(0)}%)`);
    if ((c.analysis || {}).alignment_score > 0.65) reasons.push('Strong module alignment');
    if (si?.saturationScore < 0.30) reasons.push('Low narrative saturation — early');
    if (c.why_now?.length) reasons.push(c.why_now[0]);

    return reasons.slice(0, 4);
  }

  private buildRisks(c: Record<string, any>): string[] {
    const risks: string[] = [];
    const el = c.executionLayer || {};
    const repr = c.repricing || {};
    const pi = c.projectIntel || {};

    if (el.slippageRisk > 0.5) risks.push(`High slippage risk (${(el.slippageRisk * 100).toFixed(0)}%)`);
    if (el.chaseRisk > 0.5) risks.push(`Chase risk elevated (${(el.chaseRisk * 100).toFixed(0)}%)`);
    if (repr.repricing_state === 'late_repricing') risks.push('Late repricing — may be too late');
    if (pi.unlockRisk === 'HIGH') risks.push('Token unlock risk HIGH');
    if (pi.verdict === 'WEAK') risks.push('Weak project fundamentals');
    if (c.why_not?.length) risks.push(c.why_not[0]);

    return risks.slice(0, 3);
  }
}

export const alertFormatterService = new AlertFormatterService();
