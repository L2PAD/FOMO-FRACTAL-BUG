/**
 * P1.5 — Regression & Lockdown Tests
 * ===================================
 * 
 * Tests that MUST pass before P2 (Connections merge).
 * These lock the current behavior as baseline.
 */

import {
  validateInvariants,
  assertMacroPrecedence,
  assertMLNeverOverridesRules,
  assertNoStrongActionDuringPanic,
  INVARIANT_CONSTANTS,
} from '../../src/modules/meta-brain/meta-brain.guard';

describe('P1.5 — Regression & Lockdown Tests', () => {
  
  // ═══════════════════════════════════════════════════════════════
  // REGRESSION: MACRO BEHAVIOR
  // ═══════════════════════════════════════════════════════════════
  
  describe('Macro Regression', () => {
    
    test('PANIC_SELL_OFF always blocks STRONG', () => {
      const ctx = {
        regime: 'PANIC_SELL_OFF',
        riskLevel: 'EXTREME' as const,
        macroFlags: [],
        baseAction: 'BUY' as const,
        baseStrength: 'STRONG' as const,
        baseConfidence: 0.9,
      };
      
      const result = validateInvariants(ctx);
      
      expect(result.finalStrength).not.toBe('STRONG');
      expect(result.blocked).toBe(true);
    });
    
    test('FULL_RISK_OFF forces AVOID', () => {
      const ctx = {
        regime: 'FULL_RISK_OFF',
        riskLevel: 'HIGH' as const,
        macroFlags: [],
        baseAction: 'BUY' as const,
        baseStrength: 'MODERATE' as const,
        baseConfidence: 0.7,
      };
      
      const result = validateInvariants(ctx);
      
      expect(result.finalAction).toBe('AVOID');
      expect(result.blocked).toBe(true);
    });
    
    test('EXTREME risk caps confidence at 0.45', () => {
      const ctx = {
        regime: 'CAPITAL_EXIT',
        riskLevel: 'EXTREME' as const,
        macroFlags: [],
        baseAction: 'SELL' as const,
        baseStrength: 'MODERATE' as const,
        baseConfidence: 0.8,
      };
      
      const result = validateInvariants(ctx);
      
      expect(result.finalConfidence).toBeLessThanOrEqual(0.45);
    });
    
    test('LOW risk allows high confidence', () => {
      const ctx = {
        regime: 'ALT_SEASON',
        riskLevel: 'LOW' as const,
        macroFlags: [],
        baseAction: 'BUY' as const,
        baseStrength: 'STRONG' as const,
        baseConfidence: 0.82,
      };
      
      const result = validateInvariants(ctx);
      
      expect(result.finalConfidence).toBe(0.82);
      expect(result.blocked).toBe(false);
    });
  });
  
  // ═══════════════════════════════════════════════════════════════
  // REGRESSION: ML BEHAVIOR
  // ═══════════════════════════════════════════════════════════════
  
  describe('ML Regression', () => {
    
    test('ML never changes direction', () => {
      const ctx = {
        regime: 'NEUTRAL',
        riskLevel: 'LOW' as const,
        macroFlags: [],
        baseAction: 'BUY' as const,
        baseStrength: 'MODERATE' as const,
        baseConfidence: 0.6,
        mlWantsAction: 'SELL' as const,
      };
      
      const result = assertMLNeverOverridesRules(ctx);
      
      expect(result.passed).toBe(false);
      expect(result.violation).toContain('change action');
    });
    
    test('ML never increases confidence', () => {
      const ctx = {
        regime: 'NEUTRAL',
        riskLevel: 'LOW' as const,
        macroFlags: [],
        baseAction: 'BUY' as const,
        baseStrength: 'MODERATE' as const,
        baseConfidence: 0.5,
        mlWantsConfidence: 0.8,
      };
      
      const result = assertMLNeverOverridesRules(ctx);
      
      expect(result.passed).toBe(false);
      expect(result.violation).toContain('increase confidence');
    });
    
    test('ML can lower confidence', () => {
      const ctx = {
        regime: 'NEUTRAL',
        riskLevel: 'LOW' as const,
        macroFlags: [],
        baseAction: 'BUY' as const,
        baseStrength: 'MODERATE' as const,
        baseConfidence: 0.7,
        mlWantsConfidence: 0.5,
      };
      
      const result = assertMLNeverOverridesRules(ctx);
      
      expect(result.passed).toBe(true);
    });
  });
  
  // ═══════════════════════════════════════════════════════════════
  // REGRESSION: PANIC HANDLING
  // ═══════════════════════════════════════════════════════════════
  
  describe('Panic Handling Regression', () => {
    
    test('MACRO_PANIC flag blocks STRONG', () => {
      const ctx = {
        regime: 'BTC_FLIGHT_TO_SAFETY',
        riskLevel: 'MEDIUM' as const,
        macroFlags: ['MACRO_PANIC'],
        baseAction: 'BUY' as const,
        baseStrength: 'STRONG' as const,
        baseConfidence: 0.7,
      };
      
      const result = assertNoStrongActionDuringPanic(ctx);
      
      expect(result.passed).toBe(false);
    });
    
    test('EXTREME_FEAR flag blocks STRONG', () => {
      const ctx = {
        regime: 'ALT_ROTATION',
        riskLevel: 'MEDIUM' as const,
        macroFlags: ['EXTREME_FEAR'],
        baseAction: 'SELL' as const,
        baseStrength: 'STRONG' as const,
        baseConfidence: 0.65,
      };
      
      const result = assertNoStrongActionDuringPanic(ctx);
      
      expect(result.passed).toBe(false);
    });
    
    test('MODERATE strength allowed during panic', () => {
      const ctx = {
        regime: 'PANIC_SELL_OFF',
        riskLevel: 'EXTREME' as const,
        macroFlags: ['MACRO_PANIC', 'EXTREME_FEAR'],
        baseAction: 'SELL' as const,
        baseStrength: 'MODERATE' as const,
        baseConfidence: 0.4,
      };
      
      const result = assertNoStrongActionDuringPanic(ctx);
      
      expect(result.passed).toBe(true);
    });
  });
  
  // ═══════════════════════════════════════════════════════════════
  // LOCKDOWN: CONSTANTS IMMUTABILITY
  // ═══════════════════════════════════════════════════════════════
  
  describe('Lockdown Constants', () => {
    
    test('STRONG_BLOCKED_REGIMES is immutable', () => {
      expect(INVARIANT_CONSTANTS.STRONG_BLOCKED_REGIMES).toEqual([
        'PANIC_SELL_OFF',
        'CAPITAL_EXIT',
        'FULL_RISK_OFF',
      ]);
    });
    
    test('MAX_CONFIDENCE_BY_RISK is immutable', () => {
      expect(INVARIANT_CONSTANTS.MAX_CONFIDENCE_BY_RISK).toEqual({
        LOW: 0.85,
        MEDIUM: 0.70,
        HIGH: 0.55,
        EXTREME: 0.45,
      });
    });
    
    test('STRONG_BLOCKED_FLAGS is immutable', () => {
      expect(INVARIANT_CONSTANTS.STRONG_BLOCKED_FLAGS).toContain('MACRO_PANIC');
      expect(INVARIANT_CONSTANTS.STRONG_BLOCKED_FLAGS).toContain('EXTREME_FEAR');
      expect(INVARIANT_CONSTANTS.STRONG_BLOCKED_FLAGS).toContain('STRONG_BLOCK');
    });
  });
  
  // ═══════════════════════════════════════════════════════════════
  // SNAPSHOT: DETERMINISTIC OUTPUT
  // ═══════════════════════════════════════════════════════════════
  
  describe('Deterministic Output Snapshots', () => {
    
    test('Same input produces same output', () => {
      const ctx = {
        regime: 'BTC_FLIGHT_TO_SAFETY',
        riskLevel: 'MEDIUM' as const,
        macroFlags: ['RISK_REVERSAL'],
        baseAction: 'BUY' as const,
        baseStrength: 'STRONG' as const,
        baseConfidence: 0.85,
      };
      
      const result1 = validateInvariants(ctx);
      const result2 = validateInvariants(ctx);
      
      expect(result1.finalAction).toBe(result2.finalAction);
      expect(result1.finalStrength).toBe(result2.finalStrength);
      expect(result1.finalConfidence).toBe(result2.finalConfidence);
      expect(result1.blocked).toBe(result2.blocked);
    });
  });
});
