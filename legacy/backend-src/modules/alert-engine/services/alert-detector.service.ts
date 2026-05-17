/**
 * Alert Detector
 *
 * Determines WHEN to alert based on case data and state transitions.
 * Tier 1 = immediate, Tier 2 = soon, Tier 3 = batch only.
 */

import type { AlertTier, AlertType, AlertUrgency, AlertTrigger } from '../types/alert.types.js';

interface DetectorInput {
  marketId: string;
  question: string;
  asset: string;
  action: string;
  edge: number;
  confidence: number;
  alignment: number;
  repricing: string;
  entryStyle: string;
  exitAction: string;
  entryQualityScore: number;
  socialSaturation: number;
  transitions: string[];
  transitionSignificance: number;
}

class AlertDetectorService {
  detect(input: DetectorInput): AlertTrigger | null {
    const triggers: { type: AlertType; tier: AlertTier; urgency: AlertUrgency; reason: string }[] = [];

    // ─── Tier 1: IMMEDIATE ───
    // Fresh mispricing + actionable
    if (input.repricing === 'fresh_mispricing' && ['YES_NOW', 'NO_NOW'].includes(input.action)) {
      triggers.push({ type: 'ENTRY_SIGNAL', tier: 'HIGH', urgency: 'IMMEDIATE', reason: 'Fresh mispricing + high conviction' });
    }

    // High conviction + strong edge + good entry window
    if (['YES_NOW', 'NO_NOW'].includes(input.action) && Math.abs(input.edge) >= 0.10 && input.confidence >= 0.65) {
      triggers.push({ type: 'ENTRY_SIGNAL', tier: 'HIGH', urgency: 'IMMEDIATE', reason: 'Strong edge + high confidence' });
    }

    // Entry window open with ENTER_MARKET
    if (input.entryStyle === 'ENTER_MARKET' && input.entryQualityScore >= 0.70) {
      triggers.push({ type: 'ENTRY_SIGNAL', tier: 'HIGH', urgency: 'IMMEDIATE', reason: 'Market order entry — high quality window' });
    }

    // EXIT signal (always immediate)
    if (input.exitAction === 'EXIT') {
      triggers.push({ type: 'EXIT_SIGNAL', tier: 'HIGH', urgency: 'IMMEDIATE', reason: 'EXIT — thesis broken or fully compressed' });
    }

    // ─── Tier 2: SOON ───
    // Repricing started
    if (['active_repricing', 'early_repricing'].includes(input.repricing) && ['YES_SMALL', 'NO_SMALL', 'YES_NOW', 'NO_NOW'].includes(input.action)) {
      triggers.push({ type: 'ENTRY_SIGNAL', tier: 'MEDIUM', urgency: 'SOON', reason: 'Repricing started + actionable' });
    }

    // Strong alignment appeared
    if (input.alignment >= 0.70 && Math.abs(input.edge) >= 0.07) {
      triggers.push({ type: 'ENTRY_SIGNAL', tier: 'MEDIUM', urgency: 'SOON', reason: 'Strong alignment + good edge' });
    }

    // REDUCE/TRIM signal
    if (input.exitAction === 'REDUCE') {
      triggers.push({ type: 'EXIT_SIGNAL', tier: 'MEDIUM', urgency: 'SOON', reason: 'REDUCE — edge compressed or conditions deteriorated' });
    }
    if (input.exitAction === 'TRIM') {
      triggers.push({ type: 'TRIM_SIGNAL', tier: 'MEDIUM', urgency: 'SOON', reason: 'TRIM — partial profit recommended' });
    }

    // Significant state transition
    if (input.transitionSignificance >= 0.30 && input.transitions.length > 0) {
      triggers.push({ type: 'STATE_CHANGE', tier: 'MEDIUM', urgency: 'SOON', reason: `State changed: ${input.transitions[0]}` });
    }

    // ─── Tier 3: BATCH ───
    // Watchlist changes
    if (['WATCH', 'WAIT', 'GOOD_IDEA_BAD_PRICE'].includes(input.action) && input.transitionSignificance > 0) {
      triggers.push({ type: 'STATE_CHANGE', tier: 'LOW', urgency: 'BATCH', reason: 'Watchlist state changed' });
    }

    // Risk alert (high saturation + actionable position)
    if (input.socialSaturation > 0.75 && ['YES_NOW', 'NO_NOW', 'YES_SMALL', 'NO_SMALL'].includes(input.action)) {
      triggers.push({ type: 'RISK_ALERT', tier: 'LOW', urgency: 'BATCH', reason: 'High narrative saturation on active position' });
    }

    // Pick the highest-priority trigger (EXIT > TRIM > others, then by tier)
    if (triggers.length === 0) return null;

    const typeOrder: Record<string, number> = { EXIT_SIGNAL: 5, TRIM_SIGNAL: 4, RISK_ALERT: 3, ENTRY_SIGNAL: 2, STATE_CHANGE: 1 };
    const tierOrder: Record<AlertTier, number> = { HIGH: 3, MEDIUM: 2, LOW: 1 };
    triggers.sort((a, b) => {
      const typeDiff = (typeOrder[b.type] || 0) - (typeOrder[a.type] || 0);
      if (typeDiff !== 0) return typeDiff;
      return tierOrder[b.tier] - tierOrder[a.tier];
    });
    const best = triggers[0];

    return {
      type: best.type,
      marketId: input.marketId,
      question: input.question,
      asset: input.asset,
      action: input.action,
      urgency: best.urgency,
      tier: best.tier,
      timestamp: Date.now(),
    };
  }
}

export const alertDetectorService = new AlertDetectorService();
