/**
 * MODULE IMPACT SERVICE
 * =====================
 * 
 * THE MOST CRITICAL ANALYSIS:
 * Which modules help? Which hurt? Which are noise?
 * 
 * This determines:
 * - Whether to increase/decrease module weights
 * - Whether to drop a module entirely
 * - Where the real alpha comes from
 */

import { getResolvedOutcomes } from '../outcomes/meta_brain_outcomes.repo.js';

export interface ModuleImpact {
  helped: number;
  hurt: number;
  neutral: number;
  totalWithModule: number;
  totalWithoutModule: number;
  accuracyWith: number;
  accuracyWithout: number;
  lift: number; // positive = helps, negative = hurts
}

export interface ModuleImpactReport {
  exchange: ModuleImpact;
  fractal: ModuleImpact;
  sentiment: ModuleImpact;
  onchain: ModuleImpact;
}

/**
 * Calculate module impact (Ablation Test)
 * 
 * For each module:
 * - Compare accuracy WITH module vs WITHOUT module
 * - Positive lift = module helps
 * - Negative lift = module hurts
 */
export async function calculateModuleImpact(): Promise<ModuleImpactReport> {
  const allOutcomes = await getResolvedOutcomes();
  
  const modules = ['exchange', 'fractal', 'sentiment', 'onchain'] as const;
  
  const report: any = {};
  
  for (const module of modules) {
    const withModule = allOutcomes.filter(o => o.modulesUsed.includes(module));
    const withoutModule = allOutcomes.filter(o => !o.modulesUsed.includes(module));
    
    const accuracyWith = calculateAccuracy(withModule);
    const accuracyWithout = calculateAccuracy(withoutModule);
    
    const lift = accuracyWith - accuracyWithout;
    
    // Classify outcomes
    let helped = 0;
    let hurt = 0;
    let neutral = 0;
    
    for (const outcome of withModule) {
      const moduleScore = outcome.moduleScores[module];
      
      if (moduleScore === undefined) {
        neutral++;
        continue;
      }
      
      // Module helped if:
      // - It voted correctly (score direction matches actual outcome)
      const correctDirection = outcome.directionCorrect;
      
      // Simplified: if outcome was correct AND module had non-zero score, it helped
      if (correctDirection && Math.abs(moduleScore) > 0.01) {
        helped++;
      } else if (!correctDirection && Math.abs(moduleScore) > 0.01) {
        hurt++;
      } else {
        neutral++;
      }
    }
    
    report[module] = {
      helped,
      hurt,
      neutral,
      totalWithModule: withModule.length,
      totalWithoutModule: withoutModule.length,
      accuracyWith,
      accuracyWithout,
      lift,
    };
  }
  
  return report as ModuleImpactReport;
}

/**
 * Helper: Calculate accuracy for array
 */
function calculateAccuracy(outcomes: any[]): number {
  if (outcomes.length === 0) return 0;
  const correct = outcomes.filter(o => o.directionCorrect).length;
  return correct / outcomes.length;
}

console.log('[ModuleImpactService] Loaded');
