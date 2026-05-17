#!/usr/bin/env node

/**
 * GOLDEN PATHS RUNNER — P1.4
 * ==========================
 * 
 * Quick validation of critical paths before P2 merge.
 * Runs without Jest dependency.
 */

// Import as ES modules
import * as invariantRegistry from '../../src/modules/meta-brain/invariants/invariant.registry.js';
import * as invariantEnforcer from '../../src/modules/meta-brain/invariants/invariant.enforcer.js';
import * as labsMacroCross from '../../src/modules/meta-brain/services/labs-macro.crossvalidation.js';

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`✅ ${name}`);
    passed++;
  } catch (e) {
    console.log(`❌ ${name}`);
    console.log(`   Error: ${e.message}`);
    failed++;
  }
}

function expect(value) {
  return {
    toBe: (expected) => {
      if (value !== expected) {
        throw new Error(`Expected ${expected}, got ${value}`);
      }
    },
    toBeDefined: () => {
      if (value === undefined) {
        throw new Error('Expected value to be defined');
      }
    },
    toBeUndefined: () => {
      if (value !== undefined) {
        throw new Error(`Expected undefined, got ${value}`);
      }
    },
    toBeGreaterThan: (expected) => {
      if (value <= expected) {
        throw new Error(`Expected ${value} > ${expected}`);
      }
    },
    toContain: (expected) => {
      if (!value.includes(expected)) {
        throw new Error(`Expected "${value}" to contain "${expected}"`);
      }
    },
  };
}

console.log('');
console.log('═══════════════════════════════════════════════════════════════');
console.log('GOLDEN PATHS — FINAL RUN');
console.log('═══════════════════════════════════════════════════════════════');
console.log('');

// ═══════════════════════════════════════════════════════════════
// GP1: EXTREME_FEAR + Bullish Labs → IGNORED
// ═══════════════════════════════════════════════════════════════

console.log('GP1: EXTREME_FEAR + Bullish Labs → IGNORED');

test('Bullish Lab ignored in EXTREME risk', () => {
  const lab = { labId: 'test-lab', direction: 'BULLISH', strength: 0.8, confidence: 0.75 };
  const macro = {
    regime: 'PANIC_SELL_OFF',
    riskLevel: 'EXTREME',
    bias: 'DEFENSIVE',
    blockedActions: ['BUY'],
    flags: ['EXTREME_FEAR'],
  };
  
  const result = labsMacroCross.crossValidateLabSignal(lab, macro);
  expect(result.status).toBe('IGNORED');
  expect(result.finalStrength).toBe(0);
});

// ═══════════════════════════════════════════════════════════════
// GP2: ALT_ROTATION + Neutral Labs → NORMAL
// ═══════════════════════════════════════════════════════════════

console.log('');
console.log('GP2: ALT_ROTATION + Neutral Labs → NORMAL');

test('Neutral Lab kept in MEDIUM risk', () => {
  const lab = { labId: 'test-lab', direction: 'NEUTRAL', strength: 0.5, confidence: 0.6 };
  const macro = {
    regime: 'ALT_ROTATION',
    riskLevel: 'MEDIUM',
    bias: 'NEUTRAL',
    blockedActions: [],
    flags: [],
  };
  
  const result = labsMacroCross.crossValidateLabSignal(lab, macro);
  expect(result.status).toBe('KEPT');
  expect(result.finalStrength).toBe(0.5);
});

// ═══════════════════════════════════════════════════════════════
// GP3: PANIC + High Confidence → BLOCKED
// ═══════════════════════════════════════════════════════════════

console.log('');
console.log('GP3: PANIC + High Confidence → BLOCKED');

test('STRONG blocked during MACRO_PANIC', () => {
  const snapshot = {
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
  
  const ctx = invariantEnforcer.buildInvariantContext(snapshot);
  const result = invariantEnforcer.enforceInvariants(ctx);
  
  expect(result.hasHardViolation).toBe(true);
  const panicViolation = result.violations.find(v => v.id === 'MACRO_PANIC_BLOCKS_STRONG');
  expect(panicViolation).toBeDefined();
});

// ═══════════════════════════════════════════════════════════════
// GP4: ML Cannot Override Macro
// ═══════════════════════════════════════════════════════════════

console.log('');
console.log('GP4: ML Cannot Override Macro');

test('ML cannot increase confidence', () => {
  const snapshot = {
    baseAction: 'BUY',
    baseConfidence: 0.6,
    baseStrength: 'MODERATE',
    finalAction: 'BUY',
    finalConfidence: 0.75,
    finalStrength: 'MODERATE',
    macroRegime: 'BTC_LEADS_ALT_FOLLOW',
    macroRisk: 'LOW',
    macroConfidenceMultiplier: 1.0,
    macroFlags: [],
    mlApplied: true,
    mlModifier: 1.25,
    hasConflict: false,
  };
  
  const ctx = invariantEnforcer.buildInvariantContext(snapshot);
  const result = invariantEnforcer.enforceInvariants(ctx);
  
  const mlViolation = result.violations.find(v => v.id === 'ML_CANNOT_INCREASE_CONFIDENCE');
  expect(mlViolation).toBeDefined();
});

// ═══════════════════════════════════════════════════════════════
// GP5: Labs READ-ONLY
// ═══════════════════════════════════════════════════════════════

console.log('');
console.log('GP5: Labs Are READ-ONLY');

test('Labs influence is always 0', () => {
  const snapshot = {
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
  
  const ctx = invariantEnforcer.buildInvariantContext(snapshot);
  expect(ctx.labsInfluence).toBe(0);
});

// ═══════════════════════════════════════════════════════════════
// GP6: FULL_RISK_OFF → Only AVOID
// ═══════════════════════════════════════════════════════════════

console.log('');
console.log('GP6: FULL_RISK_OFF → Only AVOID');

test('BUY blocked in FULL_RISK_OFF', () => {
  const snapshot = {
    baseAction: 'BUY',
    baseConfidence: 0.5,
    baseStrength: 'WEAK',
    finalAction: 'BUY',
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
  
  const ctx = invariantEnforcer.buildInvariantContext(snapshot);
  const result = invariantEnforcer.enforceInvariants(ctx);
  
  const riskOffViolation = result.violations.find(v => v.id === 'MACRO_RISK_OFF_BLOCKS_ACTION');
  expect(riskOffViolation).toBeDefined();
});

// ═══════════════════════════════════════════════════════════════
// GP7: Confidence Never Inflated
// ═══════════════════════════════════════════════════════════════

console.log('');
console.log('GP7: Confidence Never Inflated');

test('Final confidence cannot exceed base', () => {
  const snapshot = {
    baseAction: 'BUY',
    baseConfidence: 0.6,
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
  
  const ctx = invariantEnforcer.buildInvariantContext(snapshot);
  const result = invariantEnforcer.enforceInvariants(ctx);
  
  const inflationViolation = result.violations.find(v => 
    v.id === 'FINAL_CONFIDENCE_NEVER_EXCEEDS_BASE'
  );
  expect(inflationViolation).toBeDefined();
});

// ═══════════════════════════════════════════════════════════════
// INVARIANT REGISTRY CHECK
// ═══════════════════════════════════════════════════════════════

console.log('');
console.log('INVARIANT REGISTRY');

test('13 invariants loaded', () => {
  const count = invariantRegistry.getInvariantCount();
  expect(count.total).toBe(13);
});

test('12 HARD invariants', () => {
  const count = invariantRegistry.getInvariantCount();
  expect(count.hard).toBe(12);
});

test('1 SOFT invariant', () => {
  const count = invariantRegistry.getInvariantCount();
  expect(count.soft).toBe(1);
});

// ═══════════════════════════════════════════════════════════════
// SUMMARY
// ═══════════════════════════════════════════════════════════════

console.log('');
console.log('═══════════════════════════════════════════════════════════════');
console.log(`RESULT: ${passed} passed, ${failed} failed`);
console.log('═══════════════════════════════════════════════════════════════');

if (failed > 0) {
  console.log('');
  console.log('❌ GOLDEN PATHS FAILED — DO NOT PROCEED WITH P2 MERGE');
  process.exit(1);
} else {
  console.log('');
  console.log('✅ ALL GOLDEN PATHS PASSED — SAFE TO PROCEED WITH P2 MERGE');
  process.exit(0);
}
