/**
 * Execution Plan Engine
 *
 * The main output: HOW to enter. ENTER_MARKET / ENTER_LIMIT / STAGGER / WAIT / DO_NOT_CHASE
 */

import type { ExecutionPlan, EntryStyle, SpreadRegime, DepthQuality } from '../types/execution.types.js';

interface PlanInput {
  entryQualityScore: number;
  entryWindow: string;
  chaseRisk: number;
  missRisk: number;
  spreadRegime: SpreadRegime;
  depthQuality: DepthQuality;
  slippageRisk: number;
  maxSlippageBps: number;
  edge: number;
  repricingState: string;
  confidence: number;
}

class ExecutionPlanService {
  plan(input: PlanInput): ExecutionPlan {
    const {
      entryQualityScore, entryWindow, chaseRisk, missRisk,
      spreadRegime, depthQuality, slippageRisk, maxSlippageBps,
      edge, repricingState, confidence,
    } = input;

    let entryStyle: EntryStyle;
    let note: string;

    // ── Decision Tree ──

    // DO_NOT_CHASE: overcrowded, overheated, broken spread, high slippage
    if (entryWindow === 'CLOSED' || spreadRegime === 'BROKEN') {
      entryStyle = 'DO_NOT_CHASE';
      note = 'Market conditions too poor for entry — wait for reset';
    }
    // DO_NOT_CHASE: chase risk dominant
    else if (chaseRisk > 0.70 && missRisk < 0.40) {
      entryStyle = 'DO_NOT_CHASE';
      note = 'High chase risk with low miss risk — patience is correct';
    }
    // ENTER_MARKET: tight spread + deep depth + strong edge + early repricing + high miss risk
    else if (
      spreadRegime === 'NARROW' &&
      (depthQuality === 'DEEP' || depthQuality === 'OK') &&
      Math.abs(edge) >= 0.08 &&
      ['fresh_mispricing', 'early_signal', 'pre_event'].includes(repricingState) &&
      missRisk >= 0.50
    ) {
      entryStyle = 'ENTER_MARKET';
      note = 'Tight spread + strong edge + early stage — market order to capture before move';
    }
    // ENTER_MARKET: narrow spread + high miss risk + good confidence
    else if (spreadRegime === 'NARROW' && missRisk >= 0.60 && confidence >= 0.6) {
      entryStyle = 'ENTER_MARKET';
      note = 'High miss risk with good execution conditions — take it now';
    }
    // ENTER_LIMIT: good edge but spread normal or repricing active
    else if (
      Math.abs(edge) >= 0.05 &&
      (spreadRegime === 'NORMAL' || spreadRegime === 'NARROW') &&
      slippageRisk < 0.60
    ) {
      entryStyle = 'ENTER_LIMIT';
      note = 'Good edge with acceptable spread — use limit order to minimize leakage';
    }
    // STAGGER_LIMIT: strong thesis but uncomfortable market
    else if (
      Math.abs(edge) >= 0.06 &&
      confidence >= 0.5 &&
      (spreadRegime === 'WIDE' || depthQuality === 'THIN')
    ) {
      entryStyle = 'STAGGER_LIMIT';
      note = 'Strong thesis but poor microstructure — stagger entry to reduce impact';
    }
    // WAIT_RETRACE: thesis strong but late/stretched repricing
    else if (
      Math.abs(edge) >= 0.04 &&
      ['late_repricing', 'overheated'].includes(repricingState) &&
      chaseRisk > 0.40
    ) {
      entryStyle = 'WAIT_RETRACE';
      note = 'Thesis valid but repricing stretched — wait for pullback to enter';
    }
    // WAIT_CONFIRMATION: thesis present but weak signal
    else if (
      Math.abs(edge) >= 0.03 &&
      confidence < 0.45 &&
      ['stalled', 'pre_event'].includes(repricingState)
    ) {
      entryStyle = 'WAIT_CONFIRMATION';
      note = 'Edge exists but confidence low — wait for confirming signal';
    }
    // ENTER_LIMIT: default for any remaining tradeable scenario
    else if (entryWindow !== 'CLOSED' && Math.abs(edge) >= 0.03) {
      entryStyle = 'ENTER_LIMIT';
      note = 'Moderate conditions — use limit order for controlled entry';
    }
    // Default: don't chase
    else {
      entryStyle = 'DO_NOT_CHASE';
      note = 'Insufficient edge or poor conditions — no entry recommended';
    }

    return {
      entryStyle,
      entryQualityScore,
      slippageRisk,
      spreadRegime,
      depthQuality,
      chaseRisk,
      missRisk,
      maxSlippageBps,
      note,
    };
  }
}

export const executionPlanService = new ExecutionPlanService();
