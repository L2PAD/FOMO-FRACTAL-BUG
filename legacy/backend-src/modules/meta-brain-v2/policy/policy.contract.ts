/**
 * META BRAIN V2 — REGIME POLICY CONTRACT
 * ========================================
 *
 * Each market regime gets a full policy profile:
 *   - weights per module
 *   - verdict thresholds (enter/exit hysteresis)
 *   - cooldown per horizon
 *   - gate rules
 *   - confidence penalties (entropy, disagreement, coverage)
 */

export type MetaRegime = 'TREND' | 'RANGE' | 'RISK_OFF' | 'TRANSITION';

export interface RegimePolicy {
  regime: MetaRegime;

  /** Hysteresis thresholds for verdict */
  thresholds: {
    enter: number;   // score to ENTER directional state
    exit: number;    // score to EXIT directional state
  };

  /** Cooldown after verdict flip (ms) */
  cooldown: Record<string, number>;

  /** Base weights per module (renormalized at runtime) */
  weights: Record<string, number>;

  /** Gate rules */
  gates: {
    minCoverage: number;
    blockIfConflicted: boolean;
  };

  /** Meta confidence penalty coefficients */
  confidence: {
    entropyPenaltyK: number;
    disagreementPenaltyK: number;
    coveragePenaltyK: number;
  };
}
