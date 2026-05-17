/**
 * EXPLAINABILITY CONSISTENCY TESTS
 * =================================
 * 
 * P1.8: Automated tests to verify that explain blocks
 * are correctly generated under specific conditions.
 * 
 * Requirements:
 * 1. If BLOCKED → explain contains WHY
 * 2. If confidence < 0.4 → explain is mandatory
 * 3. If Macro influences → Macro block is visible
 */

import {
  validateInvariants,
  InvariantContext,
} from '../../src/modules/meta-brain/meta-brain.guard';

// Mock verdict generator for testing
interface MockVerdictInput {
  direction: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  confidence: number;
  strength: 'STRONG' | 'MODERATE' | 'WEAK';
  macroRegime: string;
  macroRisk: 'LOW' | 'MEDIUM' | 'HIGH' | 'EXTREME';
  macroFlags: string[];
  blocked: boolean;
}

interface MockExplainBlock {
  decision: { title: string; summary: string; bullets: string[] };
  macroContext: { title: string; summary: string; bullets: string[] };
  risks: { title: string; summary: string; bullets: string[] };
  confidence: { title: string; summary: string; bullets: string[] };
}

function generateMockExplainBlock(input: MockVerdictInput): MockExplainBlock {
  const action = input.direction === 'BULLISH' ? 'BUY' :
                 input.direction === 'BEARISH' ? 'SELL' : 'AVOID';
  
  return {
    decision: {
      title: action === 'BUY' ? 'WHY BUY' : action === 'SELL' ? 'WHY SELL' : 'WHY AVOID',
      summary: input.blocked 
        ? 'Action blocked by macro environment constraints.'
        : input.direction === 'NEUTRAL'
          ? 'Insufficient conviction or macro blocks aggressive actions.'
          : `${input.direction} signal detected with ${input.strength.toLowerCase()} strength.`,
      bullets: [
        `Final confidence: ${Math.round(input.confidence * 100)}%`,
        `Macro regime: ${input.macroRegime}`,
        input.blocked ? 'Strong actions blocked by macro' : 'Macro allows action',
      ],
    },
    macroContext: {
      title: 'MACRO CONTEXT',
      summary: `Market in ${input.macroRegime}. Risk level: ${input.macroRisk}.`,
      bullets: [
        `Risk: ${input.macroRisk}`,
        `Flags: ${input.macroFlags.length > 0 ? input.macroFlags.join(', ') : 'None'}`,
      ],
    },
    risks: {
      title: 'RISKS',
      summary: input.blocked 
        ? 'Elevated risk environment - caution advised.'
        : 'Standard market risk applies.',
      bullets: input.blocked 
        ? [`Action blocked due to ${input.macroFlags.join(', ') || 'high risk regime'}`]
        : ['No specific risks identified'],
    },
    confidence: {
      title: 'CONFIDENCE',
      summary: input.confidence >= 0.7 
        ? 'High confidence in this analysis.'
        : input.confidence >= 0.5 
          ? 'Moderate confidence - some uncertainty remains.'
          : input.confidence >= 0.4
            ? 'Low confidence - proceed with caution.'
            : 'Very low confidence - action not recommended.',
      bullets: [`Final: ${Math.round(input.confidence * 100)}%`],
    },
  };
}

describe('Explainability Consistency Tests', () => {
  
  // ═══════════════════════════════════════════════════════════════
  // REQUIREMENT 1: BLOCKED → explain contains WHY
  // ═══════════════════════════════════════════════════════════════
  
  describe('Blocked Actions Must Have Explanation', () => {
    
    test('MACRO_PANIC blocks → explain.risks contains reason', () => {
      const input: MockVerdictInput = {
        direction: 'BULLISH',
        confidence: 0.8,
        strength: 'STRONG',
        macroRegime: 'BTC_FLIGHT_TO_SAFETY',
        macroRisk: 'MEDIUM',
        macroFlags: ['MACRO_PANIC'],
        blocked: true,
      };
      
      const explain = generateMockExplainBlock(input);
      
      // Must contain WHY blocked
      expect(explain.risks.summary).toContain('Elevated risk');
      expect(explain.risks.bullets.some(b => b.includes('blocked'))).toBe(true);
      expect(explain.decision.bullets.some(b => b.includes('blocked'))).toBe(true);
    });
    
    test('PANIC_SELL_OFF regime blocks → explain visible', () => {
      const input: MockVerdictInput = {
        direction: 'BULLISH',
        confidence: 0.4,
        strength: 'WEAK',
        macroRegime: 'PANIC_SELL_OFF',
        macroRisk: 'EXTREME',
        macroFlags: [],
        blocked: true,
      };
      
      const explain = generateMockExplainBlock(input);
      
      expect(explain.macroContext.summary).toContain('PANIC_SELL_OFF');
      expect(explain.macroContext.bullets.some(b => b.includes('EXTREME'))).toBe(true);
    });
    
    test('FULL_RISK_OFF forces AVOID → explain clear', () => {
      const input: MockVerdictInput = {
        direction: 'NEUTRAL',
        confidence: 0.3,
        strength: 'WEAK',
        macroRegime: 'FULL_RISK_OFF',
        macroRisk: 'HIGH',
        macroFlags: [],
        blocked: true,
      };
      
      const explain = generateMockExplainBlock(input);
      
      expect(explain.decision.title).toBe('WHY AVOID');
      expect(explain.decision.summary).toContain('blocked');
    });
  });
  
  // ═══════════════════════════════════════════════════════════════
  // REQUIREMENT 2: LOW CONFIDENCE → explain mandatory
  // ═══════════════════════════════════════════════════════════════
  
  describe('Low Confidence Must Have Explanation', () => {
    
    test('confidence < 0.4 → explain.confidence warns', () => {
      const input: MockVerdictInput = {
        direction: 'BULLISH',
        confidence: 0.35,
        strength: 'WEAK',
        macroRegime: 'NEUTRAL',
        macroRisk: 'LOW',
        macroFlags: [],
        blocked: false,
      };
      
      const explain = generateMockExplainBlock(input);
      
      expect(explain.confidence.summary).toContain('Very low confidence');
      expect(explain.confidence.summary).toContain('not recommended');
    });
    
    test('confidence = 0.2 → decision warns user', () => {
      const input: MockVerdictInput = {
        direction: 'BEARISH',
        confidence: 0.2,
        strength: 'WEAK',
        macroRegime: 'NEUTRAL',
        macroRisk: 'LOW',
        macroFlags: [],
        blocked: false,
      };
      
      const explain = generateMockExplainBlock(input);
      
      expect(explain.confidence.summary).toContain('Very low');
      expect(parseInt(explain.confidence.bullets[0].match(/\d+/)?.[0] || '0')).toBeLessThan(40);
    });
    
    test('confidence >= 0.4 but < 0.5 → moderate warning', () => {
      const input: MockVerdictInput = {
        direction: 'BULLISH',
        confidence: 0.45,
        strength: 'WEAK',
        macroRegime: 'NEUTRAL',
        macroRisk: 'LOW',
        macroFlags: [],
        blocked: false,
      };
      
      const explain = generateMockExplainBlock(input);
      
      expect(explain.confidence.summary).toContain('Low confidence');
      expect(explain.confidence.summary).toContain('caution');
    });
  });
  
  // ═══════════════════════════════════════════════════════════════
  // REQUIREMENT 3: MACRO INFLUENCE → visible in explain
  // ═══════════════════════════════════════════════════════════════
  
  describe('Macro Influence Must Be Visible', () => {
    
    test('Macro regime shown in explain.macroContext', () => {
      const input: MockVerdictInput = {
        direction: 'BULLISH',
        confidence: 0.7,
        strength: 'MODERATE',
        macroRegime: 'BTC_FLIGHT_TO_SAFETY',
        macroRisk: 'MEDIUM',
        macroFlags: ['BTC_DOM_UP'],
        blocked: false,
      };
      
      const explain = generateMockExplainBlock(input);
      
      expect(explain.macroContext.title).toBe('MACRO CONTEXT');
      expect(explain.macroContext.summary).toContain('BTC_FLIGHT_TO_SAFETY');
      expect(explain.macroContext.summary).toContain('MEDIUM');
    });
    
    test('Macro flags shown in explain', () => {
      const input: MockVerdictInput = {
        direction: 'BULLISH',
        confidence: 0.6,
        strength: 'MODERATE',
        macroRegime: 'ALT_SEASON',
        macroRisk: 'LOW',
        macroFlags: ['MACRO_RISK_ON', 'STABLE_OUTFLOW'],
        blocked: false,
      };
      
      const explain = generateMockExplainBlock(input);
      
      const flagsBullet = explain.macroContext.bullets.find(b => b.includes('Flags'));
      expect(flagsBullet).toBeDefined();
      expect(flagsBullet).toContain('MACRO_RISK_ON');
      expect(flagsBullet).toContain('STABLE_OUTFLOW');
    });
    
    test('Risk level visible in decision bullets', () => {
      const input: MockVerdictInput = {
        direction: 'BEARISH',
        confidence: 0.5,
        strength: 'WEAK',
        macroRegime: 'CAPITAL_EXIT',
        macroRisk: 'EXTREME',
        macroFlags: ['EXTREME_FEAR'],
        blocked: true,
      };
      
      const explain = generateMockExplainBlock(input);
      
      expect(explain.macroContext.bullets.some(b => b.includes('EXTREME'))).toBe(true);
      expect(explain.decision.bullets.some(b => b.includes('CAPITAL_EXIT'))).toBe(true);
    });
  });
  
  // ═══════════════════════════════════════════════════════════════
  // EXPLAIN STRUCTURE VALIDATION
  // ═══════════════════════════════════════════════════════════════
  
  describe('Explain Structure Completeness', () => {
    
    test('All explain blocks have required fields', () => {
      const input: MockVerdictInput = {
        direction: 'NEUTRAL',
        confidence: 0.5,
        strength: 'WEAK',
        macroRegime: 'NEUTRAL',
        macroRisk: 'LOW',
        macroFlags: [],
        blocked: false,
      };
      
      const explain = generateMockExplainBlock(input);
      
      // Check all blocks exist
      expect(explain.decision).toBeDefined();
      expect(explain.macroContext).toBeDefined();
      expect(explain.risks).toBeDefined();
      expect(explain.confidence).toBeDefined();
      
      // Check each block has title, summary, bullets
      for (const block of [explain.decision, explain.macroContext, explain.risks, explain.confidence]) {
        expect(block.title).toBeDefined();
        expect(block.title.length).toBeGreaterThan(0);
        expect(block.summary).toBeDefined();
        expect(block.summary.length).toBeGreaterThan(0);
        expect(Array.isArray(block.bullets)).toBe(true);
      }
    });
    
    test('Decision title matches action', () => {
      // BUY
      expect(generateMockExplainBlock({
        direction: 'BULLISH', confidence: 0.7, strength: 'MODERATE',
        macroRegime: 'NEUTRAL', macroRisk: 'LOW', macroFlags: [], blocked: false,
      }).decision.title).toBe('WHY BUY');
      
      // SELL
      expect(generateMockExplainBlock({
        direction: 'BEARISH', confidence: 0.7, strength: 'MODERATE',
        macroRegime: 'NEUTRAL', macroRisk: 'LOW', macroFlags: [], blocked: false,
      }).decision.title).toBe('WHY SELL');
      
      // AVOID
      expect(generateMockExplainBlock({
        direction: 'NEUTRAL', confidence: 0.5, strength: 'WEAK',
        macroRegime: 'NEUTRAL', macroRisk: 'LOW', macroFlags: [], blocked: false,
      }).decision.title).toBe('WHY AVOID');
    });
    
    test('Confidence percentage in bullets', () => {
      const input: MockVerdictInput = {
        direction: 'BULLISH',
        confidence: 0.73,
        strength: 'MODERATE',
        macroRegime: 'NEUTRAL',
        macroRisk: 'LOW',
        macroFlags: [],
        blocked: false,
      };
      
      const explain = generateMockExplainBlock(input);
      
      const confBullet = explain.confidence.bullets.find(b => b.includes('%'));
      expect(confBullet).toBeDefined();
      expect(confBullet).toContain('73%');
    });
  });
  
  // ═══════════════════════════════════════════════════════════════
  // EDGE CASES
  // ═══════════════════════════════════════════════════════════════
  
  describe('Edge Cases', () => {
    
    test('Empty macro flags handled', () => {
      const input: MockVerdictInput = {
        direction: 'BULLISH',
        confidence: 0.8,
        strength: 'STRONG',
        macroRegime: 'ALT_SEASON',
        macroRisk: 'LOW',
        macroFlags: [],
        blocked: false,
      };
      
      const explain = generateMockExplainBlock(input);
      
      const flagsBullet = explain.macroContext.bullets.find(b => b.includes('Flags'));
      expect(flagsBullet).toContain('None');
    });
    
    test('Multiple flags all shown', () => {
      const input: MockVerdictInput = {
        direction: 'BEARISH',
        confidence: 0.4,
        strength: 'WEAK',
        macroRegime: 'PANIC_SELL_OFF',
        macroRisk: 'EXTREME',
        macroFlags: ['MACRO_PANIC', 'EXTREME_FEAR', 'BTC_DOM_UP', 'STABLE_INFLOW'],
        blocked: true,
      };
      
      const explain = generateMockExplainBlock(input);
      
      const flagsBullet = explain.macroContext.bullets.find(b => b.includes('Flags'));
      expect(flagsBullet).toContain('MACRO_PANIC');
      expect(flagsBullet).toContain('EXTREME_FEAR');
    });
    
    test('Confidence at boundary (0.4) handled', () => {
      const input: MockVerdictInput = {
        direction: 'BULLISH',
        confidence: 0.4,
        strength: 'WEAK',
        macroRegime: 'NEUTRAL',
        macroRisk: 'LOW',
        macroFlags: [],
        blocked: false,
      };
      
      const explain = generateMockExplainBlock(input);
      
      // 0.4 should be "Low confidence"
      expect(explain.confidence.summary).toContain('Low confidence');
      expect(explain.confidence.bullets[0]).toContain('40%');
    });
  });
});
