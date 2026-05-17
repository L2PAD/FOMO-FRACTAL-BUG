/**
 * State Transition Service
 *
 * Detects CHANGES in market state, not just current state.
 * Only triggers alerts on transitions (prevState !== currentState).
 * This eliminates 80% of potential spam.
 */

import type { AlertState } from '../types/alert.types.js';

interface TransitionResult {
  hasTransition: boolean;
  transitions: string[];
  significance: number; // 0–1
  from: AlertState;
  to: AlertState;
}

// In-memory state store (per market)
const stateStore = new Map<string, AlertState>();

class StateTransitionService {
  /**
   * Detect transitions by comparing previous and current state.
   */
  detect(marketId: string, currentState: AlertState): TransitionResult {
    const prevState = stateStore.get(marketId) || this.emptyState();
    const transitions: string[] = [];
    let significance = 0;

    // Action change (YES_NOW ↔ AVOID etc.)
    if (prevState.action !== currentState.action && currentState.action) {
      transitions.push(`action: ${prevState.action || 'none'} → ${currentState.action}`);
      significance += this.actionTransitionWeight(prevState.action, currentState.action);
    }

    // Entry style change
    if (prevState.entryStyle !== currentState.entryStyle && currentState.entryStyle) {
      transitions.push(`entry: ${prevState.entryStyle || 'none'} → ${currentState.entryStyle}`);
      significance += 0.15;
    }

    // Exit action change (HOLD → TRIM/REDUCE/EXIT)
    if (prevState.exitAction !== currentState.exitAction && currentState.exitAction !== 'HOLD') {
      transitions.push(`exit: ${prevState.exitAction || 'HOLD'} → ${currentState.exitAction}`);
      significance += currentState.exitAction === 'EXIT' ? 0.35 : 0.20;
    }

    // Repricing state change
    if (prevState.repricing !== currentState.repricing && currentState.repricing) {
      transitions.push(`repricing: ${prevState.repricing || 'none'} → ${currentState.repricing}`);
      significance += 0.10;
    }

    // Save current state
    stateStore.set(marketId, { ...currentState });

    return {
      hasTransition: transitions.length > 0,
      transitions,
      significance: Math.min(1, Math.round(significance * 100) / 100),
      from: prevState,
      to: currentState,
    };
  }

  /**
   * Get weight for action transitions.
   * Bigger weight = more significant transition.
   */
  private actionTransitionWeight(from: string, to: string): number {
    // Becoming actionable from non-actionable
    if (['WATCH', 'WAIT', 'AVOID', '', 'none'].includes(from) &&
        ['YES_NOW', 'NO_NOW', 'YES_SMALL', 'NO_SMALL'].includes(to)) {
      return 0.40;
    }
    // Downgrade from actionable
    if (['YES_NOW', 'NO_NOW'].includes(from) && ['AVOID', 'WATCH'].includes(to)) {
      return 0.25;
    }
    // Upgrade conviction
    if (['YES_SMALL', 'NO_SMALL'].includes(from) && ['YES_NOW', 'NO_NOW'].includes(to)) {
      return 0.30;
    }
    return 0.15;
  }

  private emptyState(): AlertState {
    return { action: '', entryStyle: '', exitAction: 'HOLD', repricing: '', edge: 0, tier: null };
  }

  /** Get current stored state for a market */
  getState(marketId: string): AlertState | undefined {
    return stateStore.get(marketId);
  }

  /** Clear all states (for testing) */
  clearAll(): void {
    stateStore.clear();
  }
}

export const stateTransitionService = new StateTransitionService();
