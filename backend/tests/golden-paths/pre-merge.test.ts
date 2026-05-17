/**
 * GOLDEN PATHS TESTS — P1.B
 * =========================
 * 
 * Эталонные сценарии для защиты от регрессии при P2 merge.
 * Каждый тест = критический путь, который НИКОГДА не должен сломаться.
 * 
 * @sealed v1.0
 */

import {
  enforceInvariants,
  buildInvariantContext,
  type VerdictSnapshot,
} from '../../src/modules/meta-brain/invariants/index';

import {
  crossValidateLabSignal,
  type LabSignal,
  type MacroContext,
} from '../../src/modules/meta-brain/services/labs-macro.crossvalidation';

// ═══════════════════════════════════════════════════════════════
// GOLDEN PATH 1: EXTREME_FEAR + Bullish Labs → AVOID
// ═══════════════════════════════════════════════════════════════

describe('Golden Path 1: EXTREME_FEAR + Bullish Labs → AVOID', () => {
  
  test('Bullish Lab signal IGNORED in EXTREME risk', () => {
    const lab: LabSignal = {
      labId: 'volume-lab',
      direction: 'BULLISH',
      strength: 0.8,
      confidence: 0.75,
    };
    
    const macro: MacroContext = {
      regime: 'PANIC_SELL_OFF',
      riskLevel: 'EXTREME',
      bias: 'DEFENSIVE',
      blockedActions: ['BUY'],
      flags: ['EXTREME_FEAR'],
    };
    
    const result = crossValidateLabSignal(lab, macro);
    
    expect(result.status).toBe('IGNORED');
    expect(result.finalDirection).toBe('NEUTRAL');
    expect(result.finalStrength).toBe(0);
    expect(result.reason).toContain('MACRO_CONFLICT');
  });
  
  test('High confidence verdict DOWNGRADED in EXTREME risk', () => {
    const snapshot: VerdictSnapshot = {
      baseAction: 'BUY',
      baseConfidence: 0.9,
      baseStrength: 'STRONG',
      finalAction: 'BUY',
      finalConfidence: 0.9,
      finalStrength: 'STRONG',
      macroRegime: 'PANIC_SELL_OFF',
      macroRisk: 'EXTREME',
      macroConfidenceMultiplier: 0.5,
      macroFlags: ['EXTREME_FEAR', 'MACRO_PANIC'],
      mlApplied: false,
      mlModifier: 1,
      hasConflict: false,
    };
    
    const ctx = buildInvariantContext(snapshot);
    const result = enforceInvariants(ctx);
    
    // Must have violations for STRONG in PANIC
    expect(result.violations.length).toBeGreaterThan(0);
    expect(result.hasHardViolation).toBe(true);
    expect(result.forceDecision).toBe('AVOID');
  });
});

// ═══════════════════════════════════════════════════════════════
// GOLDEN PATH 2: ALT_ROTATION + Neutral Labs → HOLD
// ═══════════════════════════════════════════════════════════════

describe('Golden Path 2: ALT_ROTATION + Neutral Labs → Normal Operation', () => {
  
  test('Neutral Lab signal KEPT in MEDIUM risk', () => {
    const lab: LabSignal = {
      labId: 'regime-lab',
      direction: 'NEUTRAL',
      strength: 0.5,
      confidence: 0.6,
    };
    
    const macro: MacroContext = {
      regime: 'ALT_ROTATION',
      riskLevel: 'MEDIUM',
      bias: 'NEUTRAL',
      blockedActions: [],
      flags: [],
    };
    
    const result = crossValidateLabSignal(lab, macro);
    
    expect(result.status).toBe('KEPT');
    expect(result.finalDirection).toBe('NEUTRAL');
    expect(result.finalStrength).toBe(0.5);
  });
  
  test('MODERATE verdict passes in ALT_ROTATION', () => {
    const snapshot: VerdictSnapshot = {
      baseAction: 'BUY',
      baseConfidence: 0.65,
      baseStrength: 'MODERATE',
      finalAction: 'BUY',
      finalConfidence: 0.65,
      finalStrength: 'MODERATE',
      macroRegime: 'ALT_ROTATION',
      macroRisk: 'MEDIUM',
      macroConfidenceMultiplier: 0.85,
      macroFlags: [],
      mlApplied: false,
      mlModifier: 1,
      hasConflict: false,
    };
    
    const ctx = buildInvariantContext(snapshot);
    const result = enforceInvariants(ctx);
    
    // Should pass with no violations (confidence within MEDIUM cap)
    const hardViolations = result.violations.filter(v => v.level === 'HARD');
    expect(hardViolations.length).toBe(0);
    expect(result.proceed).toBe(true);
  });
});

// ═══════════════════════════════════════════════════════════════
// GOLDEN PATH 3: PANIC + High Confidence → BLOCKED
// ═══════════════════════════════════════════════════════════════

describe('Golden Path 3: PANIC + High Confidence → BLOCKED', () => {
  
  test('STRONG action blocked during MACRO_PANIC', () => {
    const snapshot: VerdictSnapshot = {
      baseAction: 'SELL',
      baseConfidence: 0.85,
      baseStrength: 'STRONG',
      finalAction: 'SELL',
      finalConfidence: 0.85,
      finalStrength: 'STRONG',
      macroRegime: 'CAPITAL_EXIT',
      macroRisk: 'EXTREME',
      macroConfidenceMultiplier: 0.4,
      macroFlags: ['MACRO_PANIC'],
      mlApplied: false,
      mlModifier: 1,
      hasConflict: false,
    };
    
    const ctx = buildInvariantContext(snapshot);
    const result = enforceInvariants(ctx);
    
    // MACRO_PANIC_BLOCKS_STRONG invariant should trigger
    const panicViolation = result.violations.find(v => 
      v.id === 'MACRO_PANIC_BLOCKS_STRONG'
    );
    expect(panicViolation).toBeDefined();
    expect(result.hasHardViolation).toBe(true);
  });
  
  test('Confidence capped in EXTREME risk', () => {
    const snapshot: VerdictSnapshot = {
      baseAction: 'BUY',
      baseConfidence: 0.8,
      baseStrength: 'MODERATE',
      finalAction: 'BUY',
      finalConfidence: 0.8, // Exceeds EXTREME cap of 0.45
      finalStrength: 'MODERATE',
      macroRegime: 'PANIC_SELL_OFF',
      macroRisk: 'EXTREME',
      macroConfidenceMultiplier: 0.5,
      macroFlags: [],
      mlApplied: false,
      mlModifier: 1,
      hasConflict: false,
    };
    
    const ctx = buildInvariantContext(snapshot);
    const result = enforceInvariants(ctx);
    
    // MACRO_EXTREME_CAPS_CONFIDENCE should trigger
    const capViolation = result.violations.find(v => 
      v.id === 'MACRO_EXTREME_CAPS_CONFIDENCE'
    );
    expect(capViolation).toBeDefined();
  });
});

// ═══════════════════════════════════════════════════════════════
// GOLDEN PATH 4: ML Tries to Override Macro → BLOCKED
// ═══════════════════════════════════════════════════════════════

describe('Golden Path 4: ML Cannot Override Macro', () => {
  
  test('ML cannot increase confidence', () => {
    const snapshot: VerdictSnapshot = {
      baseAction: 'BUY',
      baseConfidence: 0.6,
      baseStrength: 'MODERATE',
      finalAction: 'BUY',
      finalConfidence: 0.75, // Increased!
      finalStrength: 'MODERATE',
      macroRegime: 'BTC_LEADS_ALT_FOLLOW',
      macroRisk: 'LOW',
      macroConfidenceMultiplier: 1.0,
      macroFlags: [],
      mlApplied: true,
      mlModifier: 1.25, // > 1 = violation
      hasConflict: false,
    };
    
    const ctx = buildInvariantContext(snapshot);
    const result = enforceInvariants(ctx);
    
    const mlViolation = result.violations.find(v => 
      v.id === 'ML_CANNOT_INCREASE_CONFIDENCE'
    );
    expect(mlViolation).toBeDefined();
    expect(result.hasHardViolation).toBe(true);
  });
  
  test('ML cannot change direction', () => {
    const snapshot: VerdictSnapshot = {
      baseAction: 'BUY',
      baseConfidence: 0.7,
      baseStrength: 'MODERATE',
      finalAction: 'BUY',
      finalConfidence: 0.65,
      finalStrength: 'MODERATE',
      macroRegime: 'ALT_SEASON',
      macroRisk: 'LOW',
      macroConfidenceMultiplier: 1.0,
      macroFlags: [],
      mlApplied: true,
      mlModifier: 0.9,
      mlRequestedAction: 'SELL', // Different from base!
      hasConflict: false,
    };
    
    const ctx = buildInvariantContext(snapshot);
    const result = enforceInvariants(ctx);
    
    const dirViolation = result.violations.find(v => 
      v.id === 'ML_CANNOT_CHANGE_DIRECTION'
    );
    expect(dirViolation).toBeDefined();
  });
});

// ═══════════════════════════════════════════════════════════════
// GOLDEN PATH 5: Labs Influence = 0 (READ-ONLY)
// ═══════════════════════════════════════════════════════════════

describe('Golden Path 5: Labs Are READ-ONLY', () => {
  
  test('Labs influence must be 0', () => {
    const snapshot: VerdictSnapshot = {
      baseAction: 'BUY',
      baseConfidence: 0.7,
      baseStrength: 'MODERATE',
      finalAction: 'BUY',
      finalConfidence: 0.7,
      finalStrength: 'MODERATE',
      macroRegime: 'ALT_SEASON',
      macroRisk: 'LOW',
      macroConfidenceMultiplier: 1.0,
      macroFlags: [],
      mlApplied: false,
      mlModifier: 1,
      hasConflict: false,
    };
    
    // Build context with Labs influence = 0
    const ctx = buildInvariantContext(snapshot);
    expect(ctx.labsInfluence).toBe(0);
    
    const result = enforceInvariants(ctx);
    
    // Should not have LABS_READ_ONLY violation
    const labsViolation = result.violations.find(v => 
      v.id === 'LABS_READ_ONLY'
    );
    expect(labsViolation).toBeUndefined();
  });
});

// ═══════════════════════════════════════════════════════════════
// GOLDEN PATH 6: FULL_RISK_OFF → Only AVOID
// ═══════════════════════════════════════════════════════════════

describe('Golden Path 6: FULL_RISK_OFF Forces AVOID', () => {
  
  test('BUY blocked in FULL_RISK_OFF', () => {
    const snapshot: VerdictSnapshot = {
      baseAction: 'BUY',
      baseConfidence: 0.5,
      baseStrength: 'WEAK',
      finalAction: 'BUY', // Should be AVOID
      finalConfidence: 0.5,
      finalStrength: 'WEAK',
      macroRegime: 'FULL_RISK_OFF',
      macroRisk: 'HIGH',
      macroConfidenceMultiplier: 0.6,
      macroFlags: [],
      mlApplied: false,
      mlModifier: 1,
      hasConflict: false,
    };
    
    const ctx = buildInvariantContext(snapshot);
    const result = enforceInvariants(ctx);
    
    const riskOffViolation = result.violations.find(v => 
      v.id === 'MACRO_RISK_OFF_BLOCKS_ACTION'
    );
    expect(riskOffViolation).toBeDefined();
  });
  
  test('AVOID allowed in FULL_RISK_OFF', () => {
    const snapshot: VerdictSnapshot = {
      baseAction: 'AVOID',
      baseConfidence: 0.3,
      baseStrength: 'WEAK',
      finalAction: 'AVOID',
      finalConfidence: 0.3,
      finalStrength: 'WEAK',
      macroRegime: 'FULL_RISK_OFF',
      macroRisk: 'HIGH',
      macroConfidenceMultiplier: 0.6,
      macroFlags: [],
      mlApplied: false,
      mlModifier: 1,
      hasConflict: false,
    };
    
    const ctx = buildInvariantContext(snapshot);
    const result = enforceInvariants(ctx);
    
    const riskOffViolation = result.violations.find(v => 
      v.id === 'MACRO_RISK_OFF_BLOCKS_ACTION'
    );
    expect(riskOffViolation).toBeUndefined();
  });
});

// ═══════════════════════════════════════════════════════════════
// GOLDEN PATH 7: Confidence Never Exceeds Base
// ═══════════════════════════════════════════════════════════════

describe('Golden Path 7: Confidence Never Inflated', () => {
  
  test('Final confidence cannot exceed base', () => {
    const snapshot: VerdictSnapshot = {
      baseAction: 'BUY',
      baseConfidence: 0.6,
      baseStrength: 'MODERATE',
      finalAction: 'BUY',
      finalConfidence: 0.7, // Exceeds base!
      finalStrength: 'MODERATE',
      macroRegime: 'ALT_SEASON',
      macroRisk: 'LOW',
      macroConfidenceMultiplier: 1.0,
      macroFlags: [],
      mlApplied: false,
      mlModifier: 1,
      hasConflict: false,
    };
    
    const ctx = buildInvariantContext(snapshot);
    const result = enforceInvariants(ctx);
    
    const inflationViolation = result.violations.find(v => 
      v.id === 'FINAL_CONFIDENCE_NEVER_EXCEEDS_BASE'
    );
    expect(inflationViolation).toBeDefined();
  });
  
  test('Reduced confidence allowed', () => {
    const snapshot: VerdictSnapshot = {
      baseAction: 'BUY',
      baseConfidence: 0.8,
      baseStrength: 'MODERATE',
      finalAction: 'BUY',
      finalConfidence: 0.6, // Reduced - OK
      finalStrength: 'MODERATE',
      macroRegime: 'BTC_FLIGHT_TO_SAFETY',
      macroRisk: 'MEDIUM',
      macroConfidenceMultiplier: 0.75,
      macroFlags: [],
      mlApplied: false,
      mlModifier: 1,
      hasConflict: false,
    };
    
    const ctx = buildInvariantContext(snapshot);
    const result = enforceInvariants(ctx);
    
    const inflationViolation = result.violations.find(v => 
      v.id === 'FINAL_CONFIDENCE_NEVER_EXCEEDS_BASE'
    );
    expect(inflationViolation).toBeUndefined();
  });
});

// ═══════════════════════════════════════════════════════════════
// SUMMARY: All 7 Golden Paths
// ═══════════════════════════════════════════════════════════════
/*
 * GP1: EXTREME_FEAR + Bullish Labs → AVOID
 * GP2: ALT_ROTATION + Neutral Labs → Normal Operation  
 * GP3: PANIC + High Confidence → BLOCKED
 * GP4: ML Cannot Override Macro
 * GP5: Labs Are READ-ONLY (influence = 0)
 * GP6: FULL_RISK_OFF → Only AVOID allowed
 * GP7: Confidence Never Inflated
 * 
 * All paths MUST pass before P2 merge.
 */
