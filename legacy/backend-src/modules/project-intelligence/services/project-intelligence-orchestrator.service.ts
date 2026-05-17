/**
 * Project Intelligence Orchestrator
 *
 * Runs all 6 engines and produces a complete ProjectIntel assessment.
 * Can pull price data from Polymarket/market data or accept it directly.
 */

import type { ProjectIntel, ProjectProfile } from '../types/project-intelligence.types.js';
import { tokenomicsEngine } from './tokenomics-engine.service.js';
import { unlockPressureService } from './unlock-pressure.service.js';
import { valuationEngine } from './valuation-engine.service.js';
import { teamFundQualityService } from './team-fund-quality.service.js';
import { launchStructureService } from './launch-structure.service.js';
import { projectThesisEngine } from './project-thesis-engine.service.js';
import { getProjectProfile } from './known-profiles.js';

class ProjectIntelligenceOrchestrator {
  /**
   * Full project intelligence assessment.
   */
  analyze(asset: string, dynamicData?: Partial<ProjectProfile>): ProjectIntel {
    const profile = getProjectProfile(asset, dynamicData);

    const tokenomics = tokenomicsEngine.assess(profile);
    const unlockPressure = unlockPressureService.assess(profile);
    const valuation = valuationEngine.assess(profile);
    const teamFund = teamFundQualityService.assess(profile);
    const launch = launchStructureService.assess(profile);
    const thesis = projectThesisEngine.synthesize({
      profile,
      tokenomics,
      unlock: unlockPressure,
      valuation,
      teamFund,
      launch,
    });

    return {
      asset: asset.toUpperCase(),
      tokenomics,
      unlockPressure,
      valuation,
      teamFund,
      launch,
      thesis,
      generatedAt: new Date(),
    };
  }

  /**
   * Batch analysis for multiple assets.
   */
  analyzeBatch(
    assets: string[],
    dynamicDataMap?: Record<string, Partial<ProjectProfile>>,
  ): Record<string, ProjectIntel> {
    const results: Record<string, ProjectIntel> = {};
    for (const asset of assets) {
      results[asset.toUpperCase()] = this.analyze(
        asset,
        dynamicDataMap?.[asset.toUpperCase()],
      );
    }
    return results;
  }

  /**
   * Quick assessment: only tokenomics + unlock + valuation (for the prediction pipeline).
   */
  quickAssess(asset: string, dynamicData?: Partial<ProjectProfile>): {
    asset: string;
    verdict: string;
    valuation: string;
    unlockRisk: string;
    tokenomicsVerdict: string;
    overallScore: number;
    keyRisks: string[];
    notes: string[];
  } {
    const intel = this.analyze(asset, dynamicData);
    return {
      asset: intel.asset,
      verdict: intel.thesis.projectVerdict,
      valuation: intel.valuation.valuation,
      unlockRisk: intel.unlockPressure.riskLevel,
      tokenomicsVerdict: intel.tokenomics.verdict,
      overallScore: intel.thesis.overallScore,
      keyRisks: intel.thesis.keyRisks,
      notes: [
        ...intel.tokenomics.notes.slice(0, 2),
        ...intel.valuation.notes.slice(0, 2),
        ...intel.unlockPressure.notes.slice(0, 1),
      ],
    };
  }
}

export const projectIntelligenceOrchestrator = new ProjectIntelligenceOrchestrator();
