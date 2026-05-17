/**
 * Trigger Engine
 *
 * Converts raw case data into structured trigger events.
 * Does NOT decide whether to alert — just builds triggers.
 */

import type { AlertType, AlertTrigger, AlertTier, AlertUrgency } from '../types/alert.types.js';

interface TriggerInput {
  marketId: string;
  question: string;
  asset: string;
  action: string;
  edge: number;
  confidence: number;
  repricing: string;
  exitAction: string;
  transitions: string[];
  transitionSignificance: number;
}

class TriggerEngineService {
  /**
   * Build trigger(s) from case data and transitions.
   */
  buildTriggers(input: TriggerInput): AlertTrigger[] {
    const triggers: AlertTrigger[] = [];
    const side = ['YES_NOW', 'YES_SMALL', 'YES'].includes(input.action) ? 'YES' : 'NO';

    // Entry triggers
    if (['YES_NOW', 'NO_NOW', 'YES_SMALL', 'NO_SMALL'].includes(input.action)) {
      triggers.push({
        type: 'ENTRY_SIGNAL',
        marketId: input.marketId,
        question: input.question,
        asset: input.asset,
        action: `${side}_NOW`,
        urgency: this.inferUrgency(input),
        tier: this.inferEntryTier(input),
        timestamp: Date.now(),
      });
    }

    // Exit/Trim triggers
    if (input.exitAction === 'EXIT') {
      triggers.push({
        type: 'EXIT_SIGNAL',
        marketId: input.marketId,
        question: input.question,
        asset: input.asset,
        action: 'EXIT',
        urgency: 'IMMEDIATE',
        tier: 'HIGH',
        timestamp: Date.now(),
      });
    } else if (input.exitAction === 'REDUCE') {
      triggers.push({
        type: 'EXIT_SIGNAL',
        marketId: input.marketId,
        question: input.question,
        asset: input.asset,
        action: 'REDUCE',
        urgency: 'SOON',
        tier: 'MEDIUM',
        timestamp: Date.now(),
      });
    } else if (input.exitAction === 'TRIM') {
      triggers.push({
        type: 'TRIM_SIGNAL',
        marketId: input.marketId,
        question: input.question,
        asset: input.asset,
        action: 'TRIM',
        urgency: 'SOON',
        tier: 'MEDIUM',
        timestamp: Date.now(),
      });
    }

    // State change triggers (if significant)
    if (input.transitionSignificance >= 0.15 && input.transitions.length > 0) {
      triggers.push({
        type: 'STATE_CHANGE',
        marketId: input.marketId,
        question: input.question,
        asset: input.asset,
        action: input.action,
        urgency: input.transitionSignificance >= 0.30 ? 'SOON' : 'BATCH',
        tier: input.transitionSignificance >= 0.30 ? 'MEDIUM' : 'LOW',
        timestamp: Date.now(),
        transitionFrom: input.transitions[0]?.split('→')[0]?.trim(),
        transitionTo: input.transitions[0]?.split('→')[1]?.trim(),
      });
    }

    return triggers;
  }

  private inferUrgency(input: TriggerInput): AlertUrgency {
    if (input.repricing === 'fresh_mispricing' && Math.abs(input.edge) >= 0.10) return 'IMMEDIATE';
    if (['YES_NOW', 'NO_NOW'].includes(input.action) && input.confidence >= 0.65) return 'IMMEDIATE';
    if (['YES_SMALL', 'NO_SMALL'].includes(input.action)) return 'SOON';
    return 'BATCH';
  }

  private inferEntryTier(input: TriggerInput): AlertTier {
    if (['YES_NOW', 'NO_NOW'].includes(input.action) && Math.abs(input.edge) >= 0.10) return 'HIGH';
    if (['YES_NOW', 'NO_NOW'].includes(input.action)) return 'MEDIUM';
    return 'LOW';
  }
}

export const triggerEngineService = new TriggerEngineService();
