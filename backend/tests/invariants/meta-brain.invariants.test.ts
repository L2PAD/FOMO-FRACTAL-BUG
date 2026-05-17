/**
 * META-BRAIN INVARIANTS — UNIT TESTS
 * ==================================
 * 
 * P0.2: Critical tests for invariant enforcement.
 * 
 * Test cases:
 * 1. Macro cannot increase confidence
 * 2. ML cannot override BLOCKED verdict  
 * 3. AVOID is terminal
 * 4. Confidence bounds [0, 1]
 * 5. PANIC blocks STRONG actions
 */

import { describe, it, expect } from 'vitest';
import { 
  enforceInvariants, 
  buildInvariantContext,
  canDoStrongAction,
  isActionAllowed,
  getConfidenceCap
} from '../../src/modules/meta-brain/invariants/invariant.enforcer';
import { InvariantCheckContext, InvariantLevel } from '../../src/modules/meta-brain/invariants/invariants.types';
import {
  validateConfidence,
  isConfidenceInflated,
  clampConfidence
} from '../../src/modules/meta-brain/invariants/rules/confidence.invariant';
import {
  isRegimeBlocking,
  getConfidenceCapForRisk,
  validateMacroPenalty
} from '../../src/modules/meta-brain/invariants/rules/macro.invariant';
import {
  validateMLModifier,
  isMLChangingDirection,
  isMLBoostingConfidence,
  CURRENT_ML_SCOPE
} from '../../src/modules/meta-brain/invariants/rules/ml-scope.invariant';
import {
  canOverrideAvoid,
  shouldConflictForceAvoid,
  getExpectedStrength
} from '../../src/modules/meta-brain/invariants/rules/decision.invariant';

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function createBaseContext(overrides: Partial<InvariantCheckContext> = {}): InvariantCheckContext {
  return {
    baseAction: 'BUY',
    baseConfidence: 0.7,
    baseStrength: 'MODERATE',
    finalAction: 'BUY',
    finalConfidence: 0.65,
    finalStrength: 'MODERATE',
    macroRegime: 'CAUTIOUS_OPTIMISM',
    macroRisk: 'MEDIUM',
    macroPenalty: 0.95,
    macroFlags: [],
    mlApplied: false,
    mlModifier: 1.0,
    labsInfluence: 0,
    labsConflict: false,
    hasConflict: false,
    decision: 'BUY',
    ...overrides,
  };
}

// ═══════════════════════════════════════════════════════════════
// TEST: MACRO CANNOT INCREASE CONFIDENCE
// ═══════════════════════════════════════════════════════════════

describe('MACRO_CAN_ONLY_PENALIZE', () => {
  it('should PASS when macroPenalty <= 1', () => {
    const ctx = createBaseContext({ macroPenalty: 0.8 });
    const result = enforceInvariants(ctx);
    
    const violation = result.violations.find(v => v.id === 'MACRO_CAN_ONLY_PENALIZE');
    expect(violation).toBeUndefined();
  });

  it('should FAIL when macroPenalty > 1 (would inflate)', () => {
    const ctx = createBaseContext({ macroPenalty: 1.2 });
    const result = enforceInvariants(ctx);
    
    const violation = result.violations.find(v => v.id === 'MACRO_CAN_ONLY_PENALIZE');
    expect(violation).toBeDefined();
    expect(violation?.level).toBe(InvariantLevel.HARD);
  });

  it('should force AVOID on violation', () => {
    const ctx = createBaseContext({ macroPenalty: 1.5 });
    const result = enforceInvariants(ctx);
    
    expect(result.hasHardViolation).toBe(true);
    expect(result.forceDecision).toBe('AVOID');
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST: ML CANNOT CHANGE DIRECTION
// ═══════════════════════════════════════════════════════════════

describe('ML_CANNOT_CHANGE_DIRECTION', () => {
  it('should PASS when ML doesn\'t change direction', () => {
    const ctx = createBaseContext({
      mlApplied: true,
      mlAction: 'BUY',
      baseAction: 'BUY',
    });
    const result = enforceInvariants(ctx);
    
    const violation = result.violations.find(v => v.id === 'ML_CANNOT_CHANGE_DIRECTION');
    expect(violation).toBeUndefined();
  });

  it('should FAIL when ML tries to change BUY to SELL', () => {
    const ctx = createBaseContext({
      mlApplied: true,
      mlAction: 'SELL',
      baseAction: 'BUY',
    });
    const result = enforceInvariants(ctx);
    
    const violation = result.violations.find(v => v.id === 'ML_CANNOT_CHANGE_DIRECTION');
    expect(violation).toBeDefined();
    expect(violation?.level).toBe(InvariantLevel.HARD);
  });

  it('should FAIL when ML tries to change AVOID to BUY', () => {
    const ctx = createBaseContext({
      mlApplied: true,
      mlAction: 'BUY',
      baseAction: 'AVOID',
    });
    const result = enforceInvariants(ctx);
    
    const violation = result.violations.find(v => v.id === 'ML_CANNOT_CHANGE_DIRECTION');
    expect(violation).toBeDefined();
  });

  it('should PASS when ML not applied', () => {
    const ctx = createBaseContext({
      mlApplied: false,
    });
    const result = enforceInvariants(ctx);
    
    const violation = result.violations.find(v => v.id === 'ML_CANNOT_CHANGE_DIRECTION');
    expect(violation).toBeUndefined();
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST: ML CANNOT INCREASE CONFIDENCE
// ═══════════════════════════════════════════════════════════════

describe('ML_CANNOT_INCREASE_CONFIDENCE', () => {
  it('should PASS when mlModifier <= 1', () => {
    const ctx = createBaseContext({
      mlApplied: true,
      mlModifier: 0.9,
    });
    const result = enforceInvariants(ctx);
    
    const violation = result.violations.find(v => v.id === 'ML_CANNOT_INCREASE_CONFIDENCE');
    expect(violation).toBeUndefined();
  });

  it('should FAIL when mlModifier > 1 (would boost)', () => {
    const ctx = createBaseContext({
      mlApplied: true,
      mlModifier: 1.1,
    });
    const result = enforceInvariants(ctx);
    
    const violation = result.violations.find(v => v.id === 'ML_CANNOT_INCREASE_CONFIDENCE');
    expect(violation).toBeDefined();
    expect(violation?.level).toBe(InvariantLevel.HARD);
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST: PANIC BLOCKS STRONG ACTIONS
// ═══════════════════════════════════════════════════════════════

describe('MACRO_PANIC_BLOCKS_STRONG', () => {
  it('should PASS when STRONG in non-panic regime', () => {
    const ctx = createBaseContext({
      finalStrength: 'STRONG',
      macroFlags: [],
      macroRegime: 'CAUTIOUS_OPTIMISM',
    });
    const result = enforceInvariants(ctx);
    
    const violation = result.violations.find(v => v.id === 'MACRO_PANIC_BLOCKS_STRONG');
    expect(violation).toBeUndefined();
  });

  it('should FAIL when STRONG during MACRO_PANIC', () => {
    const ctx = createBaseContext({
      finalStrength: 'STRONG',
      macroFlags: ['MACRO_PANIC'],
    });
    const result = enforceInvariants(ctx);
    
    const violation = result.violations.find(v => v.id === 'MACRO_PANIC_BLOCKS_STRONG');
    expect(violation).toBeDefined();
    expect(result.hasHardViolation).toBe(true);
  });

  it('should FAIL when STRONG during EXTREME_FEAR', () => {
    const ctx = createBaseContext({
      finalStrength: 'STRONG',
      macroFlags: ['EXTREME_FEAR'],
    });
    const result = enforceInvariants(ctx);
    
    const violation = result.violations.find(v => v.id === 'MACRO_PANIC_BLOCKS_STRONG');
    expect(violation).toBeDefined();
  });

  it('should FAIL when STRONG during PANIC_SELL_OFF regime', () => {
    const ctx = createBaseContext({
      finalStrength: 'STRONG',
      macroRegime: 'PANIC_SELL_OFF',
      macroFlags: [],
    });
    const result = enforceInvariants(ctx);
    
    const violation = result.violations.find(v => v.id === 'MACRO_PANIC_BLOCKS_STRONG');
    expect(violation).toBeDefined();
  });

  it('should PASS when MODERATE during panic', () => {
    const ctx = createBaseContext({
      finalStrength: 'MODERATE',
      macroFlags: ['MACRO_PANIC'],
    });
    const result = enforceInvariants(ctx);
    
    const violation = result.violations.find(v => v.id === 'MACRO_PANIC_BLOCKS_STRONG');
    expect(violation).toBeUndefined();
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST: CONFIDENCE BOUNDS
// ═══════════════════════════════════════════════════════════════

describe('CONFIDENCE_BOUNDS', () => {
  it('should PASS when confidence in [0, 1]', () => {
    expect(validateConfidence(0.5).valid).toBe(true);
    expect(validateConfidence(0).valid).toBe(true);
    expect(validateConfidence(1).valid).toBe(true);
  });

  it('should FAIL when confidence < 0', () => {
    expect(validateConfidence(-0.1).valid).toBe(false);
  });

  it('should FAIL when confidence > 1', () => {
    expect(validateConfidence(1.1).valid).toBe(false);
  });

  it('should FAIL when confidence is NaN', () => {
    expect(validateConfidence(NaN).valid).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST: FINAL CONFIDENCE NEVER EXCEEDS BASE
// ═══════════════════════════════════════════════════════════════

describe('FINAL_CONFIDENCE_NEVER_EXCEEDS_BASE', () => {
  it('should PASS when final <= base', () => {
    const ctx = createBaseContext({
      baseConfidence: 0.8,
      finalConfidence: 0.7,
    });
    const result = enforceInvariants(ctx);
    
    const violation = result.violations.find(v => v.id === 'FINAL_CONFIDENCE_NEVER_EXCEEDS_BASE');
    expect(violation).toBeUndefined();
  });

  it('should FAIL when final > base (inflation)', () => {
    const ctx = createBaseContext({
      baseConfidence: 0.6,
      finalConfidence: 0.8,
    });
    const result = enforceInvariants(ctx);
    
    const violation = result.violations.find(v => v.id === 'FINAL_CONFIDENCE_NEVER_EXCEEDS_BASE');
    expect(violation).toBeDefined();
    expect(violation?.level).toBe(InvariantLevel.HARD);
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST: FULL_RISK_OFF ONLY AVOID
// ═══════════════════════════════════════════════════════════════

describe('MACRO_RISK_OFF_BLOCKS_ACTION', () => {
  it('should PASS when AVOID in FULL_RISK_OFF', () => {
    const ctx = createBaseContext({
      macroRegime: 'FULL_RISK_OFF',
      finalAction: 'AVOID',
      decision: 'AVOID',
    });
    const result = enforceInvariants(ctx);
    
    const violation = result.violations.find(v => v.id === 'MACRO_RISK_OFF_BLOCKS_ACTION');
    expect(violation).toBeUndefined();
  });

  it('should FAIL when BUY in FULL_RISK_OFF', () => {
    const ctx = createBaseContext({
      macroRegime: 'FULL_RISK_OFF',
      finalAction: 'BUY',
      decision: 'BUY',
    });
    const result = enforceInvariants(ctx);
    
    const violation = result.violations.find(v => v.id === 'MACRO_RISK_OFF_BLOCKS_ACTION');
    expect(violation).toBeDefined();
    expect(result.forceDecision).toBe('AVOID');
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST: LABS READ-ONLY
// ═══════════════════════════════════════════════════════════════

describe('LABS_READ_ONLY', () => {
  it('should PASS when labsInfluence = 0', () => {
    const ctx = createBaseContext({
      labsInfluence: 0,
    });
    const result = enforceInvariants(ctx);
    
    const violation = result.violations.find(v => v.id === 'LABS_READ_ONLY');
    expect(violation).toBeUndefined();
  });

  it('should FAIL when labsInfluence > 0', () => {
    const ctx = createBaseContext({
      labsInfluence: 0.5,
    });
    const result = enforceInvariants(ctx);
    
    const violation = result.violations.find(v => v.id === 'LABS_READ_ONLY');
    expect(violation).toBeDefined();
    expect(violation?.level).toBe(InvariantLevel.HARD);
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST: HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

describe('Helper Functions', () => {
  describe('canDoStrongAction', () => {
    it('should return false for blocking regimes', () => {
      expect(canDoStrongAction('PANIC_SELL_OFF', 'HIGH', [])).toBe(false);
      expect(canDoStrongAction('CAPITAL_EXIT', 'HIGH', [])).toBe(false);
      expect(canDoStrongAction('FULL_RISK_OFF', 'HIGH', [])).toBe(false);
    });

    it('should return false for EXTREME risk', () => {
      expect(canDoStrongAction('NEUTRAL', 'EXTREME', [])).toBe(false);
    });

    it('should return false for panic flags', () => {
      expect(canDoStrongAction('NEUTRAL', 'MEDIUM', ['MACRO_PANIC'])).toBe(false);
      expect(canDoStrongAction('NEUTRAL', 'MEDIUM', ['EXTREME_FEAR'])).toBe(false);
    });

    it('should return true for normal conditions', () => {
      expect(canDoStrongAction('CAUTIOUS_OPTIMISM', 'MEDIUM', [])).toBe(true);
    });
  });

  describe('isActionAllowed', () => {
    it('should allow only AVOID in FULL_RISK_OFF', () => {
      expect(isActionAllowed('AVOID', 'FULL_RISK_OFF')).toBe(true);
      expect(isActionAllowed('BUY', 'FULL_RISK_OFF')).toBe(false);
      expect(isActionAllowed('SELL', 'FULL_RISK_OFF')).toBe(false);
    });

    it('should allow all actions in other regimes', () => {
      expect(isActionAllowed('BUY', 'NEUTRAL')).toBe(true);
      expect(isActionAllowed('SELL', 'NEUTRAL')).toBe(true);
      expect(isActionAllowed('AVOID', 'NEUTRAL')).toBe(true);
    });
  });

  describe('getConfidenceCap', () => {
    it('should return correct caps for risk levels', () => {
      expect(getConfidenceCap('LOW')).toBe(0.85);
      expect(getConfidenceCap('MEDIUM')).toBe(0.70);
      expect(getConfidenceCap('HIGH')).toBe(0.55);
      expect(getConfidenceCap('EXTREME')).toBe(0.45);
    });

    it('should return 1.0 for unknown risk', () => {
      expect(getConfidenceCap('UNKNOWN')).toBe(1.0);
    });
  });

  describe('validateMacroPenalty', () => {
    it('should validate correct penalties', () => {
      expect(validateMacroPenalty(0.8).valid).toBe(true);
      expect(validateMacroPenalty(1).valid).toBe(true);
      expect(validateMacroPenalty(0).valid).toBe(true);
    });

    it('should reject invalid penalties', () => {
      expect(validateMacroPenalty(1.1).valid).toBe(false);
      expect(validateMacroPenalty(-0.1).valid).toBe(false);
    });
  });

  describe('validateMLModifier', () => {
    it('should validate correct modifiers', () => {
      expect(validateMLModifier(0.9).valid).toBe(true);
      expect(validateMLModifier(1).valid).toBe(true);
    });

    it('should reject invalid modifiers', () => {
      expect(validateMLModifier(1.1).valid).toBe(false);
      expect(validateMLModifier(-0.1).valid).toBe(false);
      expect(validateMLModifier(NaN).valid).toBe(false);
    });
  });

  describe('isMLChangingDirection', () => {
    it('should detect direction changes', () => {
      expect(isMLChangingDirection('BUY', 'SELL')).toBe(true);
      expect(isMLChangingDirection('SELL', 'BUY')).toBe(true);
      expect(isMLChangingDirection('BUY', 'BUY')).toBe(false);
      expect(isMLChangingDirection('BUY', undefined)).toBe(false);
    });
  });

  describe('canOverrideAvoid', () => {
    it('should always return false (AVOID is terminal)', () => {
      expect(canOverrideAvoid()).toBe(false);
    });
  });

  describe('shouldConflictForceAvoid', () => {
    it('should force AVOID on conflict with low confidence', () => {
      expect(shouldConflictForceAvoid(true, 0.3)).toBe(true);
      expect(shouldConflictForceAvoid(true, 0.5)).toBe(false);
      expect(shouldConflictForceAvoid(false, 0.3)).toBe(false);
    });
  });

  describe('getExpectedStrength', () => {
    it('should return correct strength for confidence', () => {
      expect(getExpectedStrength(0.8)).toBe('STRONG');
      expect(getExpectedStrength(0.5)).toBe('MODERATE');
      expect(getExpectedStrength(0.2)).toBe('WEAK');
    });
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST: CURRENT ML SCOPE
// ═══════════════════════════════════════════════════════════════

describe('ML Scope', () => {
  it('should be CONFIDENCE_ONLY', () => {
    expect(CURRENT_ML_SCOPE).toBe('CONFIDENCE_ONLY');
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST: ENFORCER RESULT
// ═══════════════════════════════════════════════════════════════

describe('Enforcer Result Structure', () => {
  it('should return proper audit trail', () => {
    const ctx = createBaseContext();
    const result = enforceInvariants(ctx);
    
    expect(result.audit).toBeDefined();
    expect(result.audit.invariantsChecked).toBeGreaterThan(0);
    expect(result.audit.checkedAt).toBeGreaterThan(0);
  });

  it('should calculate confidencePenalty correctly', () => {
    const ctx = createBaseContext();
    const result = enforceInvariants(ctx);
    
    expect(result.confidencePenalty).toBeDefined();
    expect(result.confidencePenalty).toBeLessThanOrEqual(1);
    expect(result.confidencePenalty).toBeGreaterThan(0);
  });
});
