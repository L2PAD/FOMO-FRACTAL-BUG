/**
 * Microstructure Orchestrator
 *
 * Combines all 8 execution services into a single analysis pipeline.
 * Input: case data from the prediction pipeline.
 * Output: full execution assessment (entry, scaling, exit, microstructure).
 */

import { spreadRegimeService } from './spread-regime.service.js';
import { depthProxyService } from './depth-proxy.service.js';
import { slippageEngineService } from './slippage-engine.service.js';
import { entryQualityService } from './entry-quality.service.js';
import { executionPlanService } from './execution-plan.service.js';
import { edgeCompressionService } from './edge-compression.service.js';
import { scalingPolicyService } from './scaling-policy.service.js';
import { exitPolicyService } from './exit-policy.service.js';
import type { FullExecutionResult } from '../types/execution.types.js';

interface OrchestratorInput {
  // Market microstructure
  spread: number;
  liquidity: number;
  volume24h: number;

  // Analysis
  edge: number;
  fairProb: number;
  marketProb: number;
  confidence: number;
  alignment: number;

  // Repricing / timing
  repricingState: string;
  marketStage: string;

  // Social
  socialSaturation: number;
  socialLifecycle: string | null;

  // Project
  projectVerdict: string | null;

  // Position
  positionOversized: boolean;

  // Optional: original edge for compression calc
  originalEdge?: number;

  // Probability volatility (optional)
  probVolatility?: number;
}

class MicrostructureOrchestratorService {
  analyze(input: OrchestratorInput): FullExecutionResult {
    const {
      spread, liquidity, volume24h,
      edge, fairProb, marketProb, confidence, alignment,
      repricingState, marketStage,
      socialSaturation, socialLifecycle,
      projectVerdict, positionOversized,
      originalEdge, probVolatility,
    } = input;

    // 1. Spread Regime
    const spreadAssessment = spreadRegimeService.assess(spread, liquidity, volume24h);

    // 2. Depth Proxy
    const depthAssessment = depthProxyService.assess(liquidity, spread, volume24h, probVolatility);

    // 3. Slippage Engine
    const slippageAssessment = slippageEngineService.assess(
      spread,
      spreadAssessment.regime,
      depthAssessment.depthQuality,
      repricingState,
      edge,
    );

    // 4. Edge Compression
    const edgeCompressionResult = edgeCompressionService.assess(edge, originalEdge, repricingState);

    // 5. Entry Quality
    const entryQuality = entryQualityService.assess(
      edge, confidence, repricingState,
      spreadAssessment.regime, depthAssessment.depthQuality,
      slippageAssessment.slippageRisk,
      socialSaturation, marketStage,
    );

    // 6. Execution Plan
    const executionPlan = executionPlanService.plan({
      entryQualityScore: entryQuality.entryQualityScore,
      entryWindow: entryQuality.entryWindow,
      chaseRisk: entryQuality.chaseRisk,
      missRisk: entryQuality.missRisk,
      spreadRegime: spreadAssessment.regime,
      depthQuality: depthAssessment.depthQuality,
      slippageRisk: slippageAssessment.slippageRisk,
      maxSlippageBps: slippageAssessment.maxSlippageBps,
      edge,
      repricingState,
      confidence,
    });

    // 7. Scaling Policy
    const scalingPlan = scalingPolicyService.assess(
      edge, repricingState,
      spreadAssessment.regime, depthAssessment.depthQuality,
      socialSaturation, confidence,
      edgeCompressionResult.compressed, positionOversized,
    );

    // 8. Exit Policy
    const exitPlan = exitPolicyService.assess({
      edge,
      edgeCompression: edgeCompressionResult.edgeCompression,
      confidence,
      repricingState,
      socialSaturation,
      socialLifecycle,
      projectVerdict,
      fairProb,
      marketProb,
      alignment,
    });

    return {
      entry: executionPlan,
      scaling: scalingPlan,
      exit: {
        action: exitPlan.action,
        confidence: exitPlan.confidence,
        reasons: exitPlan.reasons,
      },
      edgeCompression: edgeCompressionResult,
      microstructure: {
        spreadRegime: spreadAssessment.regime,
        depthQuality: depthAssessment.depthQuality,
        slippageRisk: slippageAssessment.slippageRisk,
      },
    };
  }
}

export const microstructureOrchestratorService = new MicrostructureOrchestratorService();
