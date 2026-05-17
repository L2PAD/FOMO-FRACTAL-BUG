/**
 * Alert Quality Gate
 *
 * Rejects weak signals before they become alerts.
 * Better 3 strong alerts than 20 mediocre ones.
 */

interface QualityInput {
  edge: number;
  confidence: number;
  action: string;
  entryStyle: string;
  repricing: string;
  projectVerdict: string | null;
  exitAction: string;
  alignment: number;
  transitionSignificance: number;
}

interface GateResult {
  passed: boolean;
  reason: string;
}

class AlertQualityGateService {
  /**
   * Check if a signal is strong enough to become an alert.
   */
  check(input: QualityInput): GateResult {
    const { edge, confidence, action, entryStyle, repricing, projectVerdict, exitAction, alignment, transitionSignificance } = input;
    const absEdge = Math.abs(edge);

    // EXIT/TRIM signals always pass (critical operational signals)
    if (exitAction === 'EXIT') {
      return { passed: true, reason: 'EXIT signal — always alert' };
    }
    if (exitAction === 'REDUCE') {
      return { passed: true, reason: 'REDUCE signal — always alert' };
    }
    if (exitAction === 'TRIM' && absEdge < 0.03) {
      return { passed: true, reason: 'TRIM signal with compressed edge' };
    }

    // Significant state transitions pass with lower thresholds
    if (transitionSignificance >= 0.30) {
      if (absEdge >= 0.04 && confidence >= 0.40) {
        return { passed: true, reason: 'Significant state transition with minimum quality' };
      }
    }

    // Entry signals — strict quality gate
    if (absEdge < 0.06) {
      return { passed: false, reason: `Edge too small (${(absEdge * 100).toFixed(1)}% < 6%)` };
    }

    if (confidence < 0.55) {
      return { passed: false, reason: `Confidence too low (${(confidence * 100).toFixed(0)}% < 55%)` };
    }

    if (entryStyle === 'DO_NOT_CHASE') {
      return { passed: false, reason: 'DO_NOT_CHASE — not alertable as entry' };
    }

    if (repricing === 'overheated' && !['NO_NOW', 'NO_SMALL'].includes(action)) {
      return { passed: false, reason: 'Overheated repricing — only NO signals pass' };
    }

    if (projectVerdict === 'WEAK' && ['YES_NOW', 'YES_SMALL'].includes(action)) {
      return { passed: false, reason: 'Weak project contradicts bullish action' };
    }

    if (alignment < 0.35) {
      return { passed: false, reason: `Low alignment (${(alignment * 100).toFixed(0)}% < 35%)` };
    }

    // AVOID actions never alert as entry
    if (action === 'AVOID') {
      return { passed: false, reason: 'AVOID action — no entry alert' };
    }

    return { passed: true, reason: 'Quality gate passed' };
  }
}

export const alertQualityGateService = new AlertQualityGateService();
