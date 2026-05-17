/**
 * OnChain V2 — Final Output Service
 * ====================================
 * 
 * O9.5 CORE: Governed Snapshot Output (Institutional Grade)
 * 
 * 🔒 FROZEN v1.0.0 — Service logic locked
 * 
 * Pipeline:
 *   Raw Observation → Rolling Stats → Drift PSI → Guardrails → EMA → Caps → Final Output
 * 
 * This is the ONLY service that should be consumed by MetaBrain/Prediction.
 */

import { OnchainObservationModel } from '../core/persistence/models.js';
import { rollingStatsService } from './rolling.service.js';
import { driftService } from './drift.service.js';
import { 
  type OnchainFinalOutput,
  type GuardrailState,
  type GuardrailAction,
  type FinalState,
  type FinalStateReason,
  type DataState,
  type FinalFlag,
  type GuardrailConfig,
  DEFAULT_GUARDRAIL_CONFIG,
  FLAG_DEFINITIONS,
} from './final.contracts.js';
import { ONCHAIN_ENGINE_VERSION } from './governance.constants.js';
import type { OnchainWindow } from '../core/contracts.js';

// ═══════════════════════════════════════════════════════════════
// EMA STATE (in-memory cache)
// ═══════════════════════════════════════════════════════════════

interface EmaState {
  symbol: string;
  score: number;
  confidence: number;
  sampleCount: number;
  lastUpdatedAt: number;
}

const emaCache = new Map<string, EmaState>();

// ═══════════════════════════════════════════════════════════════
// GUARDRAIL RESULT
// ═══════════════════════════════════════════════════════════════

interface GuardrailResult {
  state: GuardrailState;
  action: GuardrailAction;
  actionReasons: string[];
  modifier: number;
  forceSafe: boolean;
}

// ═══════════════════════════════════════════════════════════════
// FINAL SERVICE
// ═══════════════════════════════════════════════════════════════

export class FinalOutputService {
  private config: GuardrailConfig;
  
  constructor(config?: Partial<GuardrailConfig>) {
    this.config = { ...DEFAULT_GUARDRAIL_CONFIG, ...config };
  }
  
  /**
   * Get final governed output for a symbol
   * This is the canonical endpoint for consumers
   */
  async getFinalOutput(params: {
    symbol: string;
    window?: OnchainWindow;
    chainId?: number;
  }): Promise<OnchainFinalOutput> {
    const { symbol, window = '30d', chainId = 1 } = params;
    const now = Date.now();
    
    // Step 1: Get latest observation
    const latestObs = await this.getLatestObservation(symbol, chainId);
    
    // Step 2: Get rolling stats
    const rolling = await rollingStatsService.getRolling({ symbol, window: '30d', chainId });
    
    // Step 3: Get drift PSI
    const drift = await driftService.calculateDrift({ symbol, metric: 'score', window: '30d' });
    
    // Step 4: Determine data state
    const dataAgeMs = latestObs ? now - latestObs.t0 : Infinity;
    const dataState = this.determineDataState(latestObs, dataAgeMs);
    
    // Step 5: Compute guardrail result
    const guardrailResult = this.computeGuardrailResult({
      sampleCount: rolling?.sampleCount ?? 0,
      psi: drift.psi,
      hasBaseline: drift.hasBaseline,
      dataAgeMs,
      dataState,
      providerHealthy: true, // TODO: check RPC pool health
    });
    
    // Step 6: Extract raw values
    let rawScoreOriginal = latestObs?.metrics?.flowScore ?? 0;
    const rawConfidence = latestObs?.metrics?.confidence ?? 0;
    const rawState = latestObs?.state ?? 'NO_DATA';
    const drivers = latestObs?.metrics?.drivers ?? [];
    
    // Normalize score to 0-1 if it's in old 0-100 format
    let rawScore = rawScoreOriginal;
    if (rawScore > 1) {
      rawScore = Math.min(1, rawScore / 100);
    }
    rawScore = Math.round(rawScore * 100) / 100;
    
    // Step 7: Apply EMA smoothing
    const emaResult = this.applyEma(symbol, rawScore, rawConfidence);
    
    // Step 8: Apply guardrail modifier
    let finalConfidence = Math.round(emaResult.confidence * guardrailResult.modifier * 100) / 100;
    let confidenceCapped = false;
    
    // Step 9: Apply confidence caps based on data state
    const capResult = this.applyConfidenceCaps({
      confidence: finalConfidence,
      dataState,
      sampleCount: rolling?.sampleCount ?? 0,
    });
    finalConfidence = capResult.confidence;
    confidenceCapped = capResult.capped;
    
    // Step 10: Determine final state and reason
    const { finalState, finalStateReason } = this.determineFinalStateWithReason({
      rawState,
      score: emaResult.score,
      confidence: finalConfidence,
      guardrailResult,
      dataState,
    });
    
    // Step 11: Collect flags with severity
    const flags = this.collectFlags({
      guardrailResult,
      rolling,
      drift,
      emaApplied: emaResult.smoothed,
      confidenceCapped,
      dataState,
      finalConfidence,
    });
    
    return {
      symbol,
      t0: latestObs?.t0 ?? now,
      window,
      
      finalScore: emaResult.score,
      finalConfidence,
      finalState,
      finalStateReason,
      
      dataState,
      
      drivers,
      flags,
      
      governance: {
        policyVersion: ONCHAIN_ENGINE_VERSION,
        guardrailState: guardrailResult.state,
        guardrailAction: guardrailResult.action,
        guardrailActionReasons: guardrailResult.actionReasons,
        psi: drift.psi,
        sampleCount30d: rolling?.sampleCount ?? 0,
        emaWindow: this.config.emaWindow,
        emaApplied: emaResult.smoothed,
        confidenceModifier: guardrailResult.modifier,
        confidenceCapped,
      },
      
      raw: {
        score: rawScore,
        confidence: rawConfidence,
        state: rawState,
      },
      
      processedAt: now,
    };
  }
  
  /**
   * Get latest observation for a symbol
   */
  private async getLatestObservation(symbol: string, chainId: number): Promise<any | null> {
    const obs = await OnchainObservationModel.findOne({ symbol })
      .sort({ t0: -1 })
      .lean();
    return obs;
  }
  
  /**
   * Determine data state
   */
  private determineDataState(latestObs: any, dataAgeMs: number): DataState {
    if (!latestObs || latestObs.state === 'NO_DATA') {
      return 'NO_DATA';
    }
    if (dataAgeMs > this.config.maxDataAgeMs) {
      return 'STALE';
    }
    return 'OK';
  }
  
  /**
   * Compute guardrail result with action and reasons
   */
  private computeGuardrailResult(inputs: {
    sampleCount: number;
    psi: number;
    hasBaseline: boolean;
    dataAgeMs: number;
    dataState: DataState;
    providerHealthy: boolean;
  }): GuardrailResult {
    const actionReasons: string[] = [];
    let state: GuardrailState = 'HEALTHY';
    let action: GuardrailAction = 'NONE';
    let modifier = this.config.modifierHealthy;
    let forceSafe = false;
    
    // NO_DATA = CRITICAL + BLOCK_OUTPUT
    if (inputs.dataState === 'NO_DATA' || inputs.sampleCount === 0) {
      state = 'CRITICAL';
      action = 'BLOCK_OUTPUT';
      modifier = this.config.modifierCritical;
      forceSafe = true;
      actionReasons.push('NO_DATA');
    }
    // LOW_SAMPLES (but > 0)
    else if (inputs.sampleCount < this.config.minSamples30d) {
      state = 'CRITICAL';
      action = 'FORCE_SAFE';
      modifier = this.config.modifierCritical;
      forceSafe = true;
      actionReasons.push(`LOW_SAMPLES(${inputs.sampleCount}<${this.config.minSamples30d})`);
    }
    // WARN_SAMPLES
    else if (inputs.sampleCount < this.config.warnSamples30d) {
      if (state === 'HEALTHY') {
        state = 'WARN';
        action = 'DOWNWEIGHT';
      }
      modifier = Math.min(modifier, this.config.modifierWarn);
      actionReasons.push(`WARN_SAMPLES(${inputs.sampleCount}<${this.config.warnSamples30d})`);
    }
    
    // Check PSI drift (only if baseline exists and not already critical)
    if (inputs.hasBaseline && !forceSafe) {
      if (inputs.psi >= this.config.psiCritical) {
        state = 'CRITICAL';
        action = 'FORCE_SAFE';
        modifier = Math.min(modifier, this.config.modifierCritical);
        forceSafe = true;
        actionReasons.push(`PSI_CRITICAL(${inputs.psi}>=${this.config.psiCritical})`);
      } else if (inputs.psi >= this.config.psiDegraded) {
        if (state !== 'CRITICAL') {
          state = 'DEGRADED';
          action = 'DOWNWEIGHT';
        }
        modifier = Math.min(modifier, this.config.modifierDegraded);
        actionReasons.push(`PSI_DEGRADED(${inputs.psi}>=${this.config.psiDegraded})`);
      } else if (inputs.psi >= this.config.psiWarn) {
        if (state === 'HEALTHY') {
          state = 'WARN';
          action = 'DOWNWEIGHT';
        }
        modifier = Math.min(modifier, this.config.modifierWarn);
        actionReasons.push(`PSI_WARN(${inputs.psi}>=${this.config.psiWarn})`);
      }
    }
    
    // Check data freshness (only if not already critical)
    if (inputs.dataState === 'STALE' && !forceSafe) {
      if (state !== 'CRITICAL') {
        state = 'DEGRADED';
        action = 'DOWNWEIGHT';
      }
      modifier = Math.min(modifier, this.config.modifierDegraded);
      actionReasons.push(`DATA_STALE(age=${Math.round(inputs.dataAgeMs / 3600000)}h)`);
    }
    
    // Check provider health (only if not already critical)
    if (this.config.providerHealthRequired && !inputs.providerHealthy && !forceSafe) {
      if (state !== 'CRITICAL') {
        state = 'DEGRADED';
        action = 'DOWNWEIGHT';
      }
      modifier = Math.min(modifier, this.config.modifierDegraded);
      actionReasons.push('PROVIDER_UNHEALTHY');
    }
    
    return { state, action, actionReasons, modifier, forceSafe };
  }
  
  /**
   * Apply confidence caps based on data state
   */
  private applyConfidenceCaps(inputs: {
    confidence: number;
    dataState: DataState;
    sampleCount: number;
  }): { confidence: number; capped: boolean } {
    let confidence = inputs.confidence;
    let capped = false;
    
    // NO_DATA = 0
    if (inputs.dataState === 'NO_DATA' || inputs.sampleCount === 0) {
      if (confidence > this.config.noDataConfidenceCap) {
        confidence = this.config.noDataConfidenceCap;
        capped = true;
      }
    }
    // LOW_SAMPLES cap
    else if (inputs.sampleCount < this.config.minSamples30d) {
      if (confidence > this.config.lowSamplesConfidenceCap) {
        confidence = this.config.lowSamplesConfidenceCap;
        capped = true;
      }
    }
    // STALE cap
    else if (inputs.dataState === 'STALE') {
      if (confidence > this.config.staleDataConfidenceCap) {
        confidence = this.config.staleDataConfidenceCap;
        capped = true;
      }
    }
    
    return { confidence: Math.round(confidence * 100) / 100, capped };
  }
  
  /**
   * Apply EMA smoothing to score and confidence
   */
  private applyEma(symbol: string, rawScore: number, rawConfidence: number): {
    score: number;
    confidence: number;
    smoothed: boolean;
  } {
    const cacheKey = symbol;
    const cached = emaCache.get(cacheKey);
    const alpha = this.config.emaAlpha;
    
    // First sample or warmup not met - no smoothing
    if (!cached || cached.sampleCount < this.config.emaWarmupMin) {
      const newCount = (cached?.sampleCount ?? 0) + 1;
      emaCache.set(cacheKey, {
        symbol,
        score: rawScore,
        confidence: rawConfidence,
        sampleCount: newCount,
        lastUpdatedAt: Date.now(),
      });
      return { score: rawScore, confidence: rawConfidence, smoothed: false };
    }
    
    // EMA formula: new = alpha * raw + (1 - alpha) * old
    const emaScore = Math.round((alpha * rawScore + (1 - alpha) * cached.score) * 100) / 100;
    const emaConfidence = Math.round((alpha * rawConfidence + (1 - alpha) * cached.confidence) * 100) / 100;
    
    // Update cache
    emaCache.set(cacheKey, {
      symbol,
      score: emaScore,
      confidence: emaConfidence,
      sampleCount: cached.sampleCount + 1,
      lastUpdatedAt: Date.now(),
    });
    
    return { score: emaScore, confidence: emaConfidence, smoothed: true };
  }
  
  /**
   * Determine final state with explicit reason
   */
  private determineFinalStateWithReason(inputs: {
    rawState: string;
    score: number;
    confidence: number;
    guardrailResult: GuardrailResult;
    dataState: DataState;
  }): { finalState: FinalState; finalStateReason: FinalStateReason } {
    
    // NO_DATA cases
    if (inputs.dataState === 'NO_DATA') {
      return { finalState: 'SAFE', finalStateReason: 'NO_DATA_FORCED_SAFE' };
    }
    
    // CRITICAL/FROZEN guardrail = force SAFE
    if (inputs.guardrailResult.forceSafe) {
      if (inputs.dataState === 'STALE') {
        return { finalState: 'SAFE', finalStateReason: 'DATA_STALE_FORCED_SAFE' };
      }
      return { finalState: 'SAFE', finalStateReason: 'GUARDRAIL_FORCED_SAFE' };
    }
    
    // Raw state = NO_DATA
    if (inputs.rawState === 'NO_DATA') {
      return { finalState: 'NO_DATA', finalStateReason: 'NO_DATA' };
    }
    
    // Low confidence = NEUTRAL
    if (inputs.confidence < 0.4) {
      return { finalState: 'NEUTRAL', finalStateReason: 'LOW_CONFIDENCE' };
    }
    
    // Map raw state to final state with signal reasons
    if (inputs.rawState === 'ACCUMULATION') {
      return { finalState: 'ACCUMULATION', finalStateReason: 'SIGNAL_ACCUMULATION' };
    }
    if (inputs.rawState === 'DISTRIBUTION') {
      return { finalState: 'DISTRIBUTION', finalStateReason: 'SIGNAL_DISTRIBUTION' };
    }
    
    return { finalState: 'NEUTRAL', finalStateReason: 'SIGNAL_NEUTRAL' };
  }
  
  /**
   * Collect all applicable flags with severity
   */
  private collectFlags(inputs: {
    guardrailResult: GuardrailResult;
    rolling: any;
    drift: { psi: number; level: string };
    emaApplied: boolean;
    confidenceCapped: boolean;
    dataState: DataState;
    finalConfidence: number;
  }): FinalFlag[] {
    const flags: FinalFlag[] = [];
    
    const addFlag = (code: string) => {
      const def = FLAG_DEFINITIONS[code];
      if (def) {
        flags.push({ code, severity: def.severity, domain: def.domain });
      }
    };
    
    // Data flags
    if (inputs.dataState === 'NO_DATA') {
      addFlag('NO_DATA');
    }
    if ((inputs.rolling?.sampleCount ?? 0) < this.config.minSamples30d) {
      addFlag('LOW_SAMPLES');
    }
    if (inputs.dataState === 'STALE') {
      addFlag('DATA_STALE');
    }
    
    // Drift flags
    if (inputs.drift.level === 'WARN') addFlag('DRIFT_WARN');
    if (inputs.drift.level === 'DEGRADED') addFlag('DRIFT_DEGRADED');
    if (inputs.drift.level === 'CRITICAL') addFlag('DRIFT_CRITICAL');
    
    // Post-processing flags
    if (inputs.emaApplied) {
      addFlag('EMA_SMOOTHED');
    }
    if (inputs.guardrailResult.modifier < 1.0) {
      addFlag('CONFIDENCE_REDUCED');
    }
    if (inputs.confidenceCapped) {
      addFlag('CONFIDENCE_CAPPED');
    }
    
    // Governance flags
    if (inputs.guardrailResult.forceSafe) {
      addFlag('FORCED_SAFE');
    }
    
    // Sort by severity: CRITICAL first, then WARN, then INFO
    const severityOrder = { CRITICAL: 0, WARN: 1, INFO: 2 };
    flags.sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity]);
    
    return flags;
  }
  
  /**
   * Reset EMA state for a symbol (for testing)
   */
  resetEma(symbol: string): void {
    emaCache.delete(symbol);
  }
  
  /**
   * Get EMA state for debugging
   */
  getEmaState(symbol: string): EmaState | undefined {
    return emaCache.get(symbol);
  }
  
  /**
   * Update config
   */
  updateConfig(config: Partial<GuardrailConfig>): void {
    this.config = { ...this.config, ...config };
  }
  
  /**
   * Get current config
   */
  getConfig(): GuardrailConfig {
    return { ...this.config };
  }
}

// Singleton
export const finalOutputService = new FinalOutputService();

console.log('[OnChain V2] Final Output Service loaded');
