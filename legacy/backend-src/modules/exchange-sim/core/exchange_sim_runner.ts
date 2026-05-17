/**
 * Exchange Simulation Runner
 * ==========================
 * 
 * FULL production-grade walk-forward simulation.
 * 
 * Walk-forward logic:
 * - Model on day D sees only data up to D
 * - For each day: inference → outcomes → retrain → shadow → promotion → rollback → bias
 * 
 * Horizons:
 * - 1D: cycle every day
 * - 7D: cycle every 7 days
 * - 30D: cycle every 30 days
 * 
 * This is a "time machine" for existing ML lifecycle logic.
 */

import { Db } from 'mongodb';
import { v4 as uuidv4 } from 'uuid';
import {
  SimConfig,
  SimHorizon,
  SimDayResult,
  SimEvent,
  SimAggregateMetrics,
  SimReport,
  SimIssue,
  SimPriceProvider,
} from '../exchange_sim.types.js';
import { getSimNowProvider } from './sim_now_provider.js';
import { createSimAuditLogger, SimAuditLoggerImpl } from './sim_audit_logger.js';
import { HORIZON_DAYS, SIM_THRESHOLDS } from './sim_config.js';
import { loadExchangeSimFlags, ExchangeSimGates, ExchangeSimFlags } from './exchange_sim_config.js';

// Trade Quality Layer imports (v4.7.0)
import { 
  TradeRecord, 
  Horizon, 
  TradeSide,
} from '../../exchange-ml/perf/exchange_trade_types.js';
import { tagRegime, tagRegimeAtIndex } from '../../exchange-ml/perf/regime_tagger.js';
import { getExchangeTradeQualityService } from '../../exchange-ml/quality/exchange_trade_quality.service.js';
import { getExchangeTradePerfService } from '../../exchange-ml/perf/exchange_trade_perf.service.js';
import { EXCHANGE_TRADE_FLAGS, Regime } from '../../exchange-ml/config/exchange_trade_flags.js';

// ═══════════════════════════════════════════════════════════════
// CONCURRENCY GUARD TYPES (v4.8.0 - BLOCK B)
// ═══════════════════════════════════════════════════════════════

interface ActiveTrade {
  symbol: string;
  horizon: SimHorizon;
  entryDay: number;
  exitDay: number;
}

// ═══════════════════════════════════════════════════════════════
// CONCURRENCY GUARD CONFIG
// ═══════════════════════════════════════════════════════════════

const CONCURRENCY_CONFIG = {
  // Maximum concurrent positions per horizon per symbol
  maxConcurrent: {
    '1D': 3,   // 1D is short, allow some overlap
    '7D': 2,   // 7D medium
    '30D': 1,  // 30D STRICT: only 1 position at a time
  } as Record<SimHorizon, number>,
  
  // Minimum days between entries for the same horizon/symbol
  cooldownDays: {
    '1D': 0,   // No cooldown for 1D
    '7D': 3,   // 3 day cooldown for 7D
    '30D': 7,  // 7 day cooldown for 30D (prevents rolling ladder)
  } as Record<SimHorizon, number>,
};

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

interface SimDependencies {
  db: Db;
  priceProvider: SimPriceProvider;
  
  // Kill switch checker
  checkKillSwitch: () => Promise<boolean>;
}

interface PredictionRecord {
  symbol: string;
  horizon: SimHorizon;
  direction: 'UP' | 'DOWN' | 'FLAT';
  confidence: number;
  entryPrice: number;
  targetPrice: number;
  expectedReturn: number;
  modelVersion: string;
  createdAt: Date;
}

interface OutcomeRecord {
  symbol: string;
  horizon: SimHorizon;
  result: 'WIN' | 'LOSS';
  actualReturn: number;
  expectedReturn: number;
  resolvedAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// SIMULATION RUNNER
// ═══════════════════════════════════════════════════════════════

export class ExchangeSimRunner {
  private runId: string;
  private audit: SimAuditLoggerImpl;
  private nowProvider = getSimNowProvider();
  private gates: ExchangeSimGates;
  private simFlags: ExchangeSimFlags;
  
  // Tracking
  private dayResults: SimDayResult[] = [];
  private predictions: Map<string, PredictionRecord[]> = new Map(); // symbol -> predictions
  private outcomes: OutcomeRecord[] = [];
  
  // Trade Quality Layer tracking (v4.7.0)
  private tradeRecords: TradeRecord[] = [];
  private qualityBlockedTrades = 0;
  private qualityAllowedTrades = 0;
  private qualitySvc = getExchangeTradeQualityService();
  private perfSvc = getExchangeTradePerfService();
  
  // Lifecycle counters
  private retrainCount = 0;
  private promotionCount = 0;
  private rollbackCount = 0;
  private throttledRetrains = 0;
  private guardrailTriggers = 0;
  private shadowWins = 0;
  private activeWins = 0;
  private driftWarnings = 0;
  private driftCriticals = 0;
  private biasUpdates = 0;
  
  // Consecutive tracking
  private consecutivePromotions = 0;
  private consecutiveRollbacks = 0;
  private maxConsecutivePromotions = 0;
  private maxConsecutiveRollbacks = 0;
  
  // Weekly tracking
  private weeklyRetrains: number[] = [];
  private weeklyPromotions: number[] = [];
  private weeklyRollbacks: number[] = [];
  
  // Confidence tracking
  private confidenceValues: number[] = [];
  
  // Bias tracking
  private biasInfluences1Dto7D: number[] = [];
  private biasInfluences7Dto30D: number[] = [];
  
  // Capital-centric: last rollback day per symbol (for cooldown)
  private lastRollbackDayBySymbol: Map<string, number> = new Map();
  
  // Capital-centric: consecutive losses per symbol
  private consecutiveLossesBySymbol: Map<string, number> = new Map();
  
  // Capital-centric: last promotion day per symbol (for cooldown)
  private lastPromotionDayBySymbol: Map<string, number> = new Map();
  
  // ═══════════════════════════════════════════════════════════════
  // CONCURRENCY GUARD STATE (v4.8.0 - BLOCK B)
  // ═══════════════════════════════════════════════════════════════
  
  private activeTrades: ActiveTrade[] = [];
  private lastEntryDay: Map<string, number> = new Map(); // key: `${symbol}_${horizon}`
  private concurrencyBlocks = 0;
  private cooldownBlocks = 0;
  private chopBlocks = 0;
  
  // Historical prices cache for proactive regime tagging
  private priceHistory: Map<string, number[]> = new Map();
  
  constructor(private deps: SimDependencies, private config: SimConfig) {
    this.runId = `sim_${uuidv4().substring(0, 8)}`;
    this.audit = createSimAuditLogger(deps.db, this.runId);
    
    // Load diagnostic flags and gates
    this.simFlags = loadExchangeSimFlags();
    this.gates = new ExchangeSimGates(this.simFlags);
  }
  
  // ═══════════════════════════════════════════════════════════════
  // PUBLIC ACCESSOR FOR TRADE RECORDS
  // ═══════════════════════════════════════════════════════════════
  
  getTradeRecords(): TradeRecord[] {
    return [...this.tradeRecords];
  }
  
  // ═══════════════════════════════════════════════════════════════
  // MAIN RUN LOOP
  // ═══════════════════════════════════════════════════════════════
  
  async run(): Promise<SimReport> {
    const startedAt = new Date();
    let status: SimReport['status'] = 'COMPLETED';
    
    await this.audit.log({
      type: 'SIM_START',
      simDay: this.config.startDate,
      details: {
        runId: this.runId,
        symbols: this.config.symbols,
        days: this.config.days,
        mode: this.simFlags.mode,
        gates: {
          retrain: this.gates.retrainEnabled,
          shadow: this.gates.shadowEnabled,
          promotion: this.gates.promotionEnabled,
          rollback: this.gates.rollbackEnabled,
          bias: this.gates.biasEnabled,
        },
      },
    });
    
    console.log(`[SimRunner] Starting simulation ${this.runId}`);
    console.log(`[SimRunner] MODE: ${this.simFlags.mode.toUpperCase()}`);
    console.log(`[SimRunner] Gates: ${this.gates.getSummary()}`);
    console.log(`[SimRunner] Symbols: ${this.config.symbols.join(', ')}`);
    console.log(`[SimRunner] Date range: ${this.config.startDate.toISOString()} + ${this.config.days} days`);
    
    // v4.8.0: Log Concurrency Guard config
    console.log(`[SimRunner] v4.8.0 CONCURRENCY GUARD:`);
    console.log(`  - Max concurrent: 1D=${CONCURRENCY_CONFIG.maxConcurrent['1D']}, 7D=${CONCURRENCY_CONFIG.maxConcurrent['7D']}, 30D=${CONCURRENCY_CONFIG.maxConcurrent['30D']}`);
    console.log(`  - Cooldown days: 1D=${CONCURRENCY_CONFIG.cooldownDays['1D']}, 7D=${CONCURRENCY_CONFIG.cooldownDays['7D']}, 30D=${CONCURRENCY_CONFIG.cooldownDays['30D']}`);
    console.log(`  - CHOP hard disable: ${EXCHANGE_TRADE_FLAGS.chopHardDisable}`);
    console.log(`  - Enabled horizons: 1D=${EXCHANGE_TRADE_FLAGS.enabledByHorizon['1D']}, 7D=${EXCHANGE_TRADE_FLAGS.enabledByHorizon['7D']}, 30D=${EXCHANGE_TRADE_FLAGS.enabledByHorizon['30D']}`);
    
    let currentDay = new Date(this.config.startDate);
    const endDate = new Date(this.config.startDate);
    endDate.setDate(endDate.getDate() + this.config.days);
    
    const horizons: SimHorizon[] = ['1D', '7D', '30D'];
    let dayIndex = 0;
    const startTimeMs = Date.now();
    const maxMs = this.config.maxRunMinutes * 60 * 1000;
    
    // Initialize weekly counters
    this.initWeeklyCounters();
    
    try {
      while (currentDay < endDate) {
        // Check kill switch
        if (await this.deps.checkKillSwitch()) {
          await this.audit.log({ type: 'SIM_KILLED', simDay: currentDay });
          console.log('[SimRunner] Kill switch triggered');
          status = 'KILLED';
          break;
        }
        
        // Check timeout
        if ((Date.now() - startTimeMs) > maxMs) {
          await this.audit.log({ type: 'SIM_TIMEOUT', simDay: currentDay });
          console.log('[SimRunner] Timeout reached');
          status = 'TIMEOUT';
          break;
        }
        
        // Set simulated time
        this.nowProvider.set(currentDay);
        
        // Process each symbol
        for (const symbol of this.config.symbols) {
          const dayResult: SimDayResult = {
            day: new Date(currentDay),
            symbol,
            predictions: [],
            outcomes: [],
            events: [],
          };
          
          // Get current price
          const currentPrice = await this.deps.priceProvider.getCloseOnDay(symbol, currentDay);
          if (!currentPrice) {
            console.warn(`[SimRunner] No price for ${symbol} on ${currentDay.toISOString().split('T')[0]}`);
            continue;
          }
          
          // ═══════════════════════════════════════════════════════════════
          // v4.8.0: Update price history FIRST (for proactive regime)
          // ═══════════════════════════════════════════════════════════════
          this.updatePriceHistory(symbol, currentPrice);
          
          // ═══════════════════════════════════════════════════════════════
          // v4.8.0: Get PROACTIVE regime (BEFORE trade decision)
          // ═══════════════════════════════════════════════════════════════
          const proactiveRegime = this.getProactiveRegime(symbol, dayIndex);
          
          // 1. Run inference for each horizon (with pre-trade gates)
          for (const horizon of horizons) {
            // ═══════════════════════════════════════════════════════════════
            // v4.8.0: PRE-TRADE GATES (BLOCK B + BLOCK C)
            // ═══════════════════════════════════════════════════════════════
            
            // GATE 1: Horizon enable check
            if (!EXCHANGE_TRADE_FLAGS.enabledByHorizon[horizon as Horizon]) {
              continue; // Skip disabled horizons
            }
            
            // GATE 2: CONCURRENCY GUARD (BLOCK B) - Critical for 30D
            if (this.hasActiveTrade(symbol, horizon, dayIndex)) {
              this.concurrencyBlocks++;
              dayResult.events.push({
                type: 'GUARDRAIL_TRIGGER',
                details: { 
                  reason: `CONCURRENCY_BLOCK_${horizon}`, 
                  regime: proactiveRegime,
                  activeTrades: this.activeTrades.filter(t => t.symbol === symbol && t.horizon === horizon).length
                },
                timestamp: currentDay,
              });
              continue; // Skip this trade
            }
            
            // GATE 3: COOLDOWN check (prevents rolling ladder)
            if (this.isInCooldown(symbol, horizon, dayIndex)) {
              this.cooldownBlocks++;
              continue; // Skip this trade
            }
            
            // GATE 4: PROACTIVE CHOP GATE (BLOCK C)
            if (proactiveRegime === 'CHOP' && EXCHANGE_TRADE_FLAGS.chopHardDisable) {
              this.chopBlocks++;
              dayResult.events.push({
                type: 'GUARDRAIL_TRIGGER',
                details: { 
                  reason: `REGIME_CHOP_BLOCK_${horizon}`, 
                  regime: proactiveRegime 
                },
                timestamp: currentDay,
              });
              continue; // Skip trade in CHOP
            }
            
            // ═══════════════════════════════════════════════════════════════
            // All gates passed - proceed with inference
            // ═══════════════════════════════════════════════════════════════
            
            const prediction = await this.simulateInference({
              symbol,
              horizon,
              day: currentDay,
              currentPrice,
            });
            
            if (prediction) {
              // Store regime with prediction for later use
              (prediction as any).regime = proactiveRegime;
              
              dayResult.predictions.push({
                horizon,
                direction: prediction.direction,
                confidence: prediction.confidence,
                targetPrice: prediction.targetPrice,
                modelVersion: prediction.modelVersion,
              });
              
              // ═══════════════════════════════════════════════════════════════
              // v4.8.0: REGISTER ACTIVE TRADE (for concurrency tracking)
              // ═══════════════════════════════════════════════════════════════
              this.registerActiveTrade(symbol, horizon, dayIndex);
              
              // Store for outcome tracking
              this.storePrediction(symbol, prediction);
              this.confidenceValues.push(prediction.confidence);
            }
          }
          
          // 2. Resolve outcomes for matured predictions
          const resolvedOutcomes = await this.resolveOutcomes(symbol, currentDay);
          dayResult.outcomes = resolvedOutcomes;
          this.outcomes.push(...resolvedOutcomes.map(o => ({
            symbol,
            horizon: o.horizon,
            result: o.result,
            actualReturn: o.actualReturn,
            expectedReturn: o.expectedReturn,
            resolvedAt: currentDay,
          })));
          
          // ══════════════════════════════════════════════════════════════
          // GATED LIFECYCLE STEPS (controlled by diagnostic mode)
          // ══════════════════════════════════════════════════════════════
          
          // 3. Maybe retrain (GATED)
          if (this.gates.retrainEnabled) {
            const retrainResult = await this.simulateRetrain(symbol, dayIndex);
            if (retrainResult.retrained) {
              dayResult.events.push({
                type: 'RETRAIN',
                details: retrainResult,
                timestamp: currentDay,
              });
            }
            if (retrainResult.throttled) {
              this.throttledRetrains++;
            }
          }
          
          // 4. Evaluate shadow model (GATED)
          if (this.gates.shadowEnabled) {
            const shadowResult = await this.simulateShadowEval(symbol);
            if (shadowResult.evaluated) {
              dayResult.events.push({
                type: 'SHADOW_EVAL',
                details: shadowResult,
                timestamp: currentDay,
              });
              if (shadowResult.shadowBetter) this.shadowWins++;
              else this.activeWins++;
            }
          }
          
          // 5. Maybe promote (GATED)
          if (this.gates.promotionEnabled) {
            const promoteResult = await this.simulatePromotion(symbol, dayIndex);
            if (promoteResult.promoted) {
              this.promotionCount++;
              this.consecutivePromotions++;
              this.consecutiveRollbacks = 0;
              this.maxConsecutivePromotions = Math.max(this.maxConsecutivePromotions, this.consecutivePromotions);
              this.weeklyPromotions[this.weeklyPromotions.length - 1]++;
              
              dayResult.events.push({
                type: 'PROMOTE',
                details: promoteResult,
                timestamp: currentDay,
              });
            }
          }
          
          // 6. Maybe rollback (GATED)
          if (this.gates.rollbackEnabled) {
            const rollbackResult = await this.simulateRollback(symbol, dayIndex);
            if (rollbackResult.rolledBack) {
              this.rollbackCount++;
              this.consecutiveRollbacks++;
              this.consecutivePromotions = 0;
              this.maxConsecutiveRollbacks = Math.max(this.maxConsecutiveRollbacks, this.consecutiveRollbacks);
              this.weeklyRollbacks[this.weeklyRollbacks.length - 1]++;
              
              dayResult.events.push({
                type: 'ROLLBACK',
                details: rollbackResult,
                timestamp: currentDay,
              });
            }
          }
          
          // 7. Update cross-horizon bias (GATED)
          if (this.gates.biasEnabled) {
            const biasResult = await this.simulateBiasUpdate(symbol);
            if (biasResult.updated) {
              this.biasUpdates++;
              if (biasResult.influence1Dto7D) this.biasInfluences1Dto7D.push(biasResult.influence1Dto7D);
              if (biasResult.influence7Dto30D) this.biasInfluences7Dto30D.push(biasResult.influence7Dto30D);
              
              dayResult.events.push({
                type: 'BIAS_UPDATE',
                details: biasResult,
                timestamp: currentDay,
              });
            }
          }
          
          // ══════════════════════════════════════════════════════════════
          // NON-GATED MONITORING (always runs for diagnostic data)
          // ══════════════════════════════════════════════════════════════
          
          // 8. Check guardrails
          const guardrailResult = await this.checkGuardrails(symbol);
          if (guardrailResult.triggered) {
            this.guardrailTriggers++;
            dayResult.events.push({
              type: 'GUARDRAIL_TRIGGER',
              details: guardrailResult,
              timestamp: currentDay,
            });
          }
          
          // 9. Check drift
          const driftResult = await this.checkDrift(symbol);
          if (driftResult.state === 'WARNING') {
            this.driftWarnings++;
            dayResult.events.push({
              type: 'DRIFT_WARNING',
              details: driftResult,
              timestamp: currentDay,
            });
          } else if (driftResult.state === 'CRITICAL') {
            this.driftCriticals++;
            dayResult.events.push({
              type: 'DRIFT_WARNING',
              details: { ...driftResult, critical: true },
              timestamp: currentDay,
            });
          }
          
          this.dayResults.push(dayResult);
        }
        
        // Update weekly counters on week boundary
        if (dayIndex > 0 && dayIndex % 7 === 0) {
          this.weeklyRetrains.push(0);
          this.weeklyPromotions.push(0);
          this.weeklyRollbacks.push(0);
        }
        
        // Progress logging
        if (dayIndex % 30 === 0) {
          const pct = ((dayIndex / this.config.days) * 100).toFixed(1);
          console.log(`[SimRunner] Progress: ${pct}% (day ${dayIndex}/${this.config.days})`);
        }
        
        // Move to next day
        currentDay.setDate(currentDay.getDate() + 1);
        dayIndex++;
      }
    } catch (error: any) {
      console.error('[SimRunner] Error:', error);
      await this.audit.log({
        type: 'SIM_ERROR',
        simDay: currentDay,
        details: { error: error.message },
      });
      status = 'ERROR';
    }
    
    // Generate report
    const completedAt = new Date();
    await this.audit.log({ type: 'SIM_END', simDay: currentDay });
    
    console.log(`[SimRunner] Simulation completed: ${status}`);
    console.log(`[SimRunner] Duration: ${((completedAt.getTime() - startedAt.getTime()) / 1000).toFixed(1)}s`);
    
    return this.generateReport(status, startedAt, completedAt);
  }
  
  // ═══════════════════════════════════════════════════════════════
  // SIMULATION METHODS
  // ═══════════════════════════════════════════════════════════════
  
  private async simulateInference(params: {
    symbol: string;
    horizon: SimHorizon;
    day: Date;
    currentPrice: number;
  }): Promise<PredictionRecord | null> {
    // Simulate model inference
    // In FULL mode, this would call the real inference service
    // For now, we generate realistic predictions based on price momentum
    
    const { symbol, horizon, day, currentPrice } = params;
    
    // Get previous day price for momentum
    const prevDay = new Date(day);
    prevDay.setDate(prevDay.getDate() - 1);
    const prevPrice = await this.deps.priceProvider.getCloseOnDay(symbol, prevDay);
    
    if (!prevPrice) return null;
    
    const momentum = (currentPrice - prevPrice) / prevPrice;
    
    // Simulate prediction based on momentum with noise
    const noise = (Math.random() - 0.5) * 0.02;
    const expectedReturn = momentum * 0.5 + noise; // Mean reversion with trend following
    
    // Confidence based on momentum strength
    const confidence = 0.4 + Math.abs(momentum) * 5 + Math.random() * 0.2;
    const clampedConfidence = Math.min(0.85, Math.max(0.3, confidence));
    
    const direction: 'UP' | 'DOWN' | 'FLAT' = 
      expectedReturn > 0.005 ? 'UP' : 
      expectedReturn < -0.005 ? 'DOWN' : 'FLAT';
    
    return {
      symbol,
      horizon,
      direction,
      confidence: clampedConfidence,
      entryPrice: currentPrice,
      targetPrice: currentPrice * (1 + expectedReturn),
      expectedReturn,
      modelVersion: `sim_v1.${Math.floor(this.retrainCount / 10)}`,
      createdAt: new Date(day), // Create copy to prevent mutation
    };
  }
  
  private storePrediction(symbol: string, prediction: PredictionRecord): void {
    if (!this.predictions.has(symbol)) {
      this.predictions.set(symbol, []);
    }
    this.predictions.get(symbol)!.push(prediction);
  }
  
  private async resolveOutcomes(symbol: string, currentDay: Date): Promise<SimDayResult['outcomes']> {
    const outcomes: SimDayResult['outcomes'] = [];
    const symbolPredictions = this.predictions.get(symbol) || [];
    
    for (const prediction of symbolPredictions) {
      const horizonDays = HORIZON_DAYS[prediction.horizon];
      const maturityDate = new Date(prediction.createdAt);
      maturityDate.setDate(maturityDate.getDate() + horizonDays);
      
      // Check if prediction has matured
      if (maturityDate <= currentDay) {
        const actualPrice = await this.deps.priceProvider.getCloseOnDay(symbol, maturityDate);
        if (!actualPrice) continue;
        
        const actualReturn = (actualPrice - prediction.entryPrice) / prediction.entryPrice;
        
        // Determine outcome
        const directionCorrect = 
          (prediction.direction === 'UP' && actualReturn > 0) ||
          (prediction.direction === 'DOWN' && actualReturn < 0) ||
          (prediction.direction === 'FLAT' && Math.abs(actualReturn) < 0.01);
        
        outcomes.push({
          horizon: prediction.horizon,
          result: directionCorrect ? 'WIN' : 'LOSS',
          actualReturn,
          expectedReturn: prediction.expectedReturn,
        });
        
        // ═══════════════════════════════════════════════════════════════
        // CREATE TradeRecord for Quality Layer (v4.8.0)
        // Uses PROACTIVE regime stored during prediction phase
        // ═══════════════════════════════════════════════════════════════
        
        // Determine trade side based on prediction direction
        const side: TradeSide = prediction.direction === 'UP' ? 'LONG' : 'SHORT';
        
        // Calculate direction-aware PnL
        // LONG: profit = positive actualReturn
        // SHORT: profit = negative actualReturn
        const pnlPct = side === 'LONG' ? actualReturn : -actualReturn;
        
        // v4.8.0: Use PROACTIVE regime stored with prediction (no future leak)
        const regimeTag = ((prediction as any).regime || 'UNKNOWN') as Regime;
        
        // Apply Quality Filter with proactive regime
        const qualityInput = {
          horizon: prediction.horizon as Horizon,
          envState: 'USE' as const, // Simulated env state
          dirProbUp: prediction.direction === 'UP' ? prediction.confidence : 0.3,
          dirProbDown: prediction.direction === 'DOWN' ? prediction.confidence : 0.3,
          confidence: prediction.confidence,
          atrPct: 0.02, // Default ATR for simulation
          regime: regimeTag, // v4.8.0: Use proactive regime
        };
        
        const qualityDecision = this.qualitySvc.decide(qualityInput);
        
        // v4.8.0: Trade was already gated at entry time, just record outcome
        this.qualityAllowedTrades++;
        
        // Create and store TradeRecord with sized position
        const tradeRecord: TradeRecord = {
          // Decision part
          ts: Math.floor(prediction.createdAt.getTime() / 1000),
          symbol,
          horizon: prediction.horizon as Horizon,
          side,
          entryPrice: prediction.entryPrice,
          expectedReturn: prediction.expectedReturn,
          confidence: prediction.confidence,
          sizePct: 0.1 * qualityDecision.sizeMultiplier, // Base 10% position
          tags: {
            regime: regimeTag,
            quality: qualityDecision.reasons,
            gatedAt: 'ENTRY', // v4.8.0: Mark that trade was gated at entry
          },
          // Outcome part
          tsResolved: Math.floor(maturityDate.getTime() / 1000),
          exitPrice: actualPrice,
          ret: actualReturn,
          pnlPct: pnlPct * 0.1 * qualityDecision.sizeMultiplier, // Sized PnL
          win: directionCorrect,
          rMultiple: actualReturn > 0 ? actualReturn / 0.02 : actualReturn / -0.02, // Simplified R
        };
        
        this.tradeRecords.push(tradeRecord);
        
        // Remove matured prediction
        const idx = symbolPredictions.indexOf(prediction);
        if (idx > -1) symbolPredictions.splice(idx, 1);
      }
    }
    
    return outcomes;
  }
  
  private async simulateRetrain(symbol: string, dayIndex: number): Promise<{ retrained: boolean; throttled: boolean }> {
    // Simulate retrain based on outcome accumulation
    const minOutcomesForRetrain = 20;
    const retrainInterval = 7; // days
    
    // Check throttle
    if (dayIndex % retrainInterval !== 0) {
      return { retrained: false, throttled: false };
    }
    
    // Check if enough outcomes
    const symbolOutcomes = this.outcomes.filter(o => o.symbol === symbol);
    if (symbolOutcomes.length < minOutcomesForRetrain) {
      return { retrained: false, throttled: true };
    }
    
    this.retrainCount++;
    this.weeklyRetrains[this.weeklyRetrains.length - 1]++;
    
    return { retrained: true, throttled: false };
  }
  
  private async simulateShadowEval(symbol: string): Promise<{ evaluated: boolean; shadowBetter: boolean }> {
    // Simulate shadow model comparison
    // Shadow wins ~40% of the time initially, improving with more data
    const shadowWinRate = 0.4 + (this.outcomes.length / 1000) * 0.1;
    const shadowBetter = Math.random() < shadowWinRate;
    
    return { evaluated: true, shadowBetter };
  }
  
  /**
   * CAPITAL-CENTRIC Promotion Logic (v3)
   * 
   * Implements SUSTAINED LIFT + extended cooldown to eliminate promotion storm.
   * 
   * COOLDOWN: 56 days between promotions per symbol
   * SUSTAINED LIFT: Shadow must outperform in 3 consecutive 14-day windows
   */
  private async simulatePromotion(symbol: string, dayIndex: number): Promise<{ promoted: boolean; reason?: string }> {
    // COOLDOWN CHECK: 56 days between promotions (was 21)
    const lastPromotionDay = this.lastPromotionDayBySymbol.get(symbol) ?? -Infinity;
    const daysSinceLastPromotion = dayIndex - lastPromotionDay;
    const PROMOTION_COOLDOWN_DAYS = 56;
    
    if (daysSinceLastPromotion < PROMOTION_COOLDOWN_DAYS) {
      return { promoted: false };
    }
    
    // Check only on evaluation days (every 14 days)
    const promotionCheckInterval = 14;
    if (dayIndex % promotionCheckInterval !== 0) {
      return { promoted: false };
    }
    
    // Need sufficient data for SUSTAINED LIFT check
    const SUSTAINED_WINDOWS = 3;
    const WINDOW_DAYS = 14;
    const MIN_TRADES_PER_WINDOW = 10;
    const MIN_WIN_LIFT = 0.02;
    
    // Get recent outcomes
    const recentOutcomes = this.outcomes.filter(o => o.symbol === symbol);
    
    // Check if we have enough data for 3 windows
    const minTotalTrades = SUSTAINED_WINDOWS * MIN_TRADES_PER_WINDOW;
    if (recentOutcomes.length < minTotalTrades) {
      return { promoted: false };
    }
    
    // SUSTAINED LIFT: Shadow must outperform in 3 consecutive windows
    let sustainedPassed = true;
    
    for (let w = 0; w < SUSTAINED_WINDOWS; w++) {
      // Calculate window bounds
      const windowStart = recentOutcomes.length - ((w + 1) * MIN_TRADES_PER_WINDOW);
      const windowEnd = recentOutcomes.length - (w * MIN_TRADES_PER_WINDOW);
      
      if (windowStart < 0) {
        sustainedPassed = false;
        break;
      }
      
      const windowOutcomes = recentOutcomes.slice(Math.max(0, windowStart), windowEnd);
      
      // Calculate win rate for this window
      const wins = windowOutcomes.filter(o => o.result === 'WIN').length;
      const total = windowOutcomes.length;
      const windowWinRate = total > 0 ? wins / total : 0.5;
      
      // Shadow needs to show improvement (simulated as >52% win rate)
      // In real implementation, this would compare shadow vs active in each window
      const SHADOW_WIN_THRESHOLD = 0.52;
      if (windowWinRate < SHADOW_WIN_THRESHOLD) {
        sustainedPassed = false;
        break;
      }
    }
    
    if (!sustainedPassed) {
      return { promoted: false };
    }
    
    // Overall shadow win rate check
    const recentShadowWinRate = this.shadowWins / Math.max(1, this.shadowWins + this.activeWins);
    
    if (recentShadowWinRate < 0.55) {
      return { promoted: false };
    }
    
    this.lastPromotionDayBySymbol.set(symbol, dayIndex);
    return { promoted: true, reason: 'sustained_lift_confirmed' };
  }
  
  /**
   * CAPITAL-CENTRIC Rollback Logic (v2)
   * 
   * Replaces the old accuracy-based rollback with multi-condition capital metrics.
   * 
   * Rollback triggers (must meet MULTIPLE conditions):
   * 1. STREAK_KILLER: consecutiveLosses >= 12 AND (drawdown > 12% OR winRate < 45%)
   * 2. CAPITAL_INSTABILITY: drawdown > 12% AND stability < 0.50 AND winRate < 45%
   * 
   * COOLDOWN: 14 days between rollbacks (prevents rollback storm)
   */
  private async simulateRollback(symbol: string, dayIndex: number): Promise<{ rolledBack: boolean; reason?: string }> {
    // COOLDOWN CHECK: 14 days between rollbacks
    const lastRollbackDay = this.lastRollbackDayBySymbol.get(symbol) ?? -Infinity;
    const daysSinceLastRollback = dayIndex - lastRollbackDay;
    const ROLLBACK_COOLDOWN_DAYS = 14;
    
    if (daysSinceLastRollback < ROLLBACK_COOLDOWN_DAYS) {
      return { rolledBack: false };
    }
    
    // Get recent outcomes for this symbol (last 30 days worth)
    const recentOutcomes = this.outcomes.slice(-60).filter(o => o.symbol === symbol);
    
    // GUARD: Need minimum samples
    const MIN_SAMPLES = 15;
    if (recentOutcomes.length < MIN_SAMPLES) {
      return { rolledBack: false };
    }
    
    // Calculate capital metrics
    const wins = recentOutcomes.filter(o => o.result === 'WIN').length;
    const losses = recentOutcomes.filter(o => o.result === 'LOSS').length;
    const winRate = (wins + losses) > 0 ? wins / (wins + losses) : 0.5;
    
    // Calculate equity curve and drawdown
    let equity = 1.0;
    let peak = 1.0;
    let maxDrawdown = 0;
    let consecutiveLosses = 0;
    let maxConsecutiveLosses = 0;
    
    for (const outcome of recentOutcomes) {
      const returnPct = outcome.actualReturn;
      equity *= (1 + returnPct);
      peak = Math.max(peak, equity);
      const dd = (peak - equity) / peak;
      maxDrawdown = Math.max(maxDrawdown, dd);
      
      if (outcome.result === 'LOSS') {
        consecutiveLosses++;
        maxConsecutiveLosses = Math.max(maxConsecutiveLosses, consecutiveLosses);
      } else {
        consecutiveLosses = 0;
      }
    }
    
    // Track consecutive losses for this symbol
    this.consecutiveLossesBySymbol.set(symbol, consecutiveLosses);
    
    // Calculate stability score
    const returns = recentOutcomes.map(o => o.actualReturn);
    const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
    let stdReturn = 0;
    if (returns.length >= 2) {
      const variance = returns.reduce((a, b) => a + (b - avgReturn) ** 2, 0) / (returns.length - 1);
      stdReturn = Math.sqrt(variance);
    }
    
    let stabilityScore = 0.5;
    if (stdReturn > 0 && Math.abs(avgReturn) > 0.0001) {
      const volRatio = stdReturn / Math.abs(avgReturn);
      const base = 1 / (1 + volRatio);
      stabilityScore = Math.max(0, Math.min(1, base * (1 - maxDrawdown)));
    }
    
    // THRESHOLDS (Capital-Centric)
    const WIN_RATE_FLOOR = 0.45;
    const MAX_DRAWDOWN_CEIL = 0.12;
    const MIN_STABILITY = 0.50;
    const MAX_CONSECUTIVE_LOSSES = 12;
    
    const winRateBad = winRate < WIN_RATE_FLOOR;
    const drawdownBad = maxDrawdown > MAX_DRAWDOWN_CEIL;
    const stabilityBad = stabilityScore < MIN_STABILITY;
    const streakBad = maxConsecutiveLosses >= MAX_CONSECUTIVE_LOSSES;
    
    // ROLLBACK CONDITION 1: STREAK_KILLER
    if (streakBad && (drawdownBad || winRateBad)) {
      this.lastRollbackDayBySymbol.set(symbol, dayIndex);
      return { 
        rolledBack: true, 
        reason: `STREAK_KILLER: ${maxConsecutiveLosses} consecutive losses, DD=${(maxDrawdown * 100).toFixed(1)}%` 
      };
    }
    
    // ROLLBACK CONDITION 2: CAPITAL_INSTABILITY
    if (drawdownBad && stabilityBad && winRateBad) {
      this.lastRollbackDayBySymbol.set(symbol, dayIndex);
      return { 
        rolledBack: true, 
        reason: `CAPITAL_INSTABILITY: WinRate=${(winRate * 100).toFixed(1)}%, DD=${(maxDrawdown * 100).toFixed(1)}%, Stability=${stabilityScore.toFixed(2)}` 
      };
    }
    
    return { rolledBack: false };
  }
  
  private async simulateBiasUpdate(symbol: string): Promise<{ updated: boolean; influence1Dto7D?: number; influence7Dto30D?: number }> {
    // Simulate cross-horizon bias update
    const symbolOutcomes = this.outcomes.filter(o => o.symbol === symbol);
    
    if (symbolOutcomes.length < 20) {
      return { updated: false };
    }
    
    // Calculate bias influences
    const outcomes1D = symbolOutcomes.filter(o => o.horizon === '1D');
    const win1D = outcomes1D.filter(o => o.result === 'WIN').length / Math.max(1, outcomes1D.length);
    
    const influence1Dto7D = (win1D - 0.5) * 0.15; // Max ±15%
    const influence7Dto30D = (win1D - 0.5) * 0.25; // Max ±25%
    
    return {
      updated: true,
      influence1Dto7D,
      influence7Dto30D,
    };
  }
  
  // ═══════════════════════════════════════════════════════════════
  // CONCURRENCY GUARD METHODS (v4.8.0 - BLOCK B)
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * Check if we can open a new trade (concurrency limit not exceeded).
   */
  private hasActiveTrade(symbol: string, horizon: SimHorizon, dayIndex: number): boolean {
    // Clean up expired trades
    this.activeTrades = this.activeTrades.filter(t => t.exitDay > dayIndex);
    
    // Count active trades for this symbol/horizon
    const activeCount = this.activeTrades.filter(
      t => t.symbol === symbol && t.horizon === horizon
    ).length;
    
    return activeCount >= CONCURRENCY_CONFIG.maxConcurrent[horizon];
  }
  
  /**
   * Check if we're in cooldown period for this symbol/horizon.
   */
  private isInCooldown(symbol: string, horizon: SimHorizon, dayIndex: number): boolean {
    const key = `${symbol}_${horizon}`;
    const lastEntry = this.lastEntryDay.get(key);
    
    if (lastEntry === undefined) return false;
    
    const daysSinceEntry = dayIndex - lastEntry;
    return daysSinceEntry < CONCURRENCY_CONFIG.cooldownDays[horizon];
  }
  
  /**
   * Register a new active trade.
   */
  private registerActiveTrade(symbol: string, horizon: SimHorizon, dayIndex: number): void {
    const horizonDays = HORIZON_DAYS[horizon];
    
    this.activeTrades.push({
      symbol,
      horizon,
      entryDay: dayIndex,
      exitDay: dayIndex + horizonDays,
    });
    
    // Track last entry for cooldown
    const key = `${symbol}_${horizon}`;
    this.lastEntryDay.set(key, dayIndex);
  }
  
  /**
   * Get proactive regime tag using only historical data up to dayIndex.
   */
  private getProactiveRegime(symbol: string, dayIndex: number): Regime {
    const closes = this.priceHistory.get(symbol);
    if (!closes || closes.length < 50) return 'UNKNOWN';
    
    // Only use data up to current day
    const idx = Math.min(dayIndex, closes.length - 1);
    return tagRegimeAtIndex(closes, idx, 240) as Regime;
  }
  
  /**
   * Update price history for a symbol.
   */
  private updatePriceHistory(symbol: string, price: number): void {
    if (!this.priceHistory.has(symbol)) {
      this.priceHistory.set(symbol, []);
    }
    this.priceHistory.get(symbol)!.push(price);
  }
  
  private async checkGuardrails(symbol: string): Promise<{ triggered: boolean; reason?: string }> {
    // Check for guardrail triggers
    const maxRetrainsPerWeek = SIM_THRESHOLDS.maxRetrainsPerWeek;
    const currentWeekRetrains = this.weeklyRetrains[this.weeklyRetrains.length - 1] || 0;
    
    if (currentWeekRetrains > maxRetrainsPerWeek) {
      return { triggered: true, reason: 'excessive_retrains' };
    }
    
    return { triggered: false };
  }
  
  private async checkDrift(symbol: string): Promise<{ state: 'NORMAL' | 'WARNING' | 'CRITICAL' }> {
    // Simulate drift detection based on recent accuracy
    const recentOutcomes = this.outcomes.slice(-30);
    const symbolOutcomes = recentOutcomes.filter(o => o.symbol === symbol);
    
    if (symbolOutcomes.length < 5) {
      return { state: 'NORMAL' };
    }
    
    const recentWinRate = symbolOutcomes.filter(o => o.result === 'WIN').length / symbolOutcomes.length;
    
    if (recentWinRate < 0.3) {
      return { state: 'CRITICAL' };
    }
    if (recentWinRate < 0.4) {
      return { state: 'WARNING' };
    }
    
    return { state: 'NORMAL' };
  }
  
  private initWeeklyCounters(): void {
    this.weeklyRetrains = [0];
    this.weeklyPromotions = [0];
    this.weeklyRollbacks = [0];
    
    // Reset capital-centric tracking
    this.lastRollbackDayBySymbol.clear();
    this.consecutiveLossesBySymbol.clear();
    this.lastPromotionDayBySymbol.clear();
    
    // Reset Trade Quality Layer tracking (v4.7.0)
    this.tradeRecords = [];
    this.qualityBlockedTrades = 0;
    this.qualityAllowedTrades = 0;
    
    // Reset Concurrency Guard tracking (v4.8.0)
    this.activeTrades = [];
    this.lastEntryDay.clear();
    this.concurrencyBlocks = 0;
    this.cooldownBlocks = 0;
    this.chopBlocks = 0;
    this.priceHistory.clear();
  }
  
  // ═══════════════════════════════════════════════════════════════
  // REPORT GENERATION
  // ═══════════════════════════════════════════════════════════════
  
  private generateReport(status: SimReport['status'], startedAt: Date, completedAt: Date): SimReport {
    // Calculate accuracy by horizon
    const accuracyByHorizon = this.calculateAccuracyByHorizon();
    
    // Calculate metrics
    const metrics: SimAggregateMetrics = {
      totalDays: this.dayResults.length / this.config.symbols.length,
      totalSymbols: this.config.symbols.length,
      totalPredictions: this.dayResults.reduce((sum, d) => sum + d.predictions.length, 0),
      totalOutcomes: this.outcomes.length,
      
      accuracy: accuracyByHorizon,
      
      lifecycle: {
        retrainCount: this.retrainCount,
        promotionCount: this.promotionCount,
        rollbackCount: this.rollbackCount,
        throttledRetrains: this.throttledRetrains,
        guardrailTriggers: this.guardrailTriggers,
        driftWarnings: this.driftWarnings,
        driftCriticals: this.driftCriticals,
      },
      
      shadow: {
        shadowWins: this.shadowWins,
        activeWins: this.activeWins,
        ties: 0,
        avgDelta: 0,
      },
      
      bias: {
        biasUpdates: this.biasUpdates,
        avg1Dto7DInfluence: this.average(this.biasInfluences1Dto7D),
        avg7Dto30DInfluence: this.average(this.biasInfluences7Dto30D),
        maxInfluenceApplied: Math.max(
          Math.max(...this.biasInfluences1Dto7D.map(Math.abs), 0),
          Math.max(...this.biasInfluences7Dto30D.map(Math.abs), 0)
        ),
      },
      
      stress: {
        maxConsecutivePromotions: this.maxConsecutivePromotions,
        maxConsecutiveRollbacks: this.maxConsecutiveRollbacks,
        maxRetrainsPerWeek: Math.max(...this.weeklyRetrains, 0),
        confidenceVolatility: this.stdDev(this.confidenceValues),
      },
      
      correlations: {
        bias1D_accuracy30D: this.calculateBiasAccuracyCorrelation(),
        confidence_accuracy: this.calculateConfidenceAccuracyCorrelation(),
      },
    };
    
    // Detect issues
    const issues = this.detectIssues(metrics);
    
    // Generate recommendations
    const recommendations = this.generateRecommendations(issues, metrics);
    
    // Daily metrics for charts
    const dailyMetrics = this.aggregateDailyMetrics();
    
    // Per-symbol metrics
    const symbolMetrics = this.aggregateSymbolMetrics();
    
    // ═══════════════════════════════════════════════════════════════
    // CAPITAL METRICS FROM TRADE QUALITY LAYER (v4.7.0)
    // ═══════════════════════════════════════════════════════════════
    
    const capitalMetrics = this.computeCapitalMetrics();
    
    return {
      config: this.config,
      startedAt,
      completedAt,
      status,
      // Diagnostic metadata
      diagnosticMode: this.simFlags.mode,
      gates: {
        retrain: this.gates.retrainEnabled,
        shadow: this.gates.shadowEnabled,
        promotion: this.gates.promotionEnabled,
        rollback: this.gates.rollbackEnabled,
        bias: this.gates.biasEnabled,
      },
      metrics,
      dailyMetrics,
      symbolMetrics,
      issues,
      recommendations,
      // Trade Quality Layer metrics (v4.7.0)
      capitalMetrics,
    };
  }
  
  /**
   * Compute capital-centric metrics from TradeRecords.
   * These are the key metrics for the Performance Dashboard.
   * v4.8.0: Added concurrency guard statistics.
   */
  private computeCapitalMetrics(): {
    totalTrades: number;
    qualityBlocked: number;
    qualityAllowed: number;
    blockRate: number;
    // v4.8.0: Concurrency Guard stats
    concurrencyBlocks: number;
    cooldownBlocks: number;
    chopBlocks: number;
    byHorizon: Record<Horizon, {
      trades: number;
      winRate: number;
      expectancy: number;
      sharpeLike: number;
      maxDD: number;
    }>;
    aggregate: {
      winRate: number;
      expectancy: number;
      sharpeLike: number;
      maxDD: number;
    };
  } {
    const horizons: Horizon[] = ['1D', '7D', '30D'];
    const byHorizon: any = {};
    
    for (const h of horizons) {
      const perfWindow = this.perfSvc.compute(this.tradeRecords, h, 365);
      byHorizon[h] = {
        trades: perfWindow.trades,
        winRate: perfWindow.winRate,
        expectancy: perfWindow.expectancy,
        sharpeLike: perfWindow.sharpeLike,
        maxDD: perfWindow.maxDD,
      };
    }
    
    // Aggregate across all horizons
    const allTrades = this.tradeRecords;
    const totalWins = allTrades.filter(t => t.win).length;
    const pnls = allTrades.map(t => t.pnlPct);
    
    let avgPnl = 0;
    let stdPnl = 0;
    let maxDD = 0;
    
    if (pnls.length > 0) {
      avgPnl = pnls.reduce((a, b) => a + b, 0) / pnls.length;
      
      if (pnls.length >= 2) {
        const variance = pnls.reduce((a, b) => a + (b - avgPnl) ** 2, 0) / (pnls.length - 1);
        stdPnl = Math.sqrt(variance);
      }
      
      // Calculate drawdown
      let eq = 1;
      let peak = 1;
      for (const p of pnls) {
        eq *= (1 + p);
        peak = Math.max(peak, eq);
        maxDD = Math.max(maxDD, (peak - eq) / peak);
      }
    }
    
    const sharpeLike = stdPnl > 0 ? (avgPnl / stdPnl) * Math.sqrt(allTrades.length) : 0;
    
    return {
      totalTrades: this.qualityAllowedTrades,
      qualityBlocked: this.qualityBlockedTrades,
      qualityAllowed: this.qualityAllowedTrades,
      blockRate: this.qualityBlockedTrades + this.qualityAllowedTrades > 0
        ? this.qualityBlockedTrades / (this.qualityBlockedTrades + this.qualityAllowedTrades)
        : 0,
      // v4.8.0: Concurrency Guard statistics
      concurrencyBlocks: this.concurrencyBlocks,
      cooldownBlocks: this.cooldownBlocks,
      chopBlocks: this.chopBlocks,
      byHorizon,
      aggregate: {
        winRate: allTrades.length > 0 ? totalWins / allTrades.length : 0,
        expectancy: avgPnl,
        sharpeLike,
        maxDD,
      },
    };
  }
  
  private calculateAccuracyByHorizon(): SimAggregateMetrics['accuracy'] {
    const horizons: SimHorizon[] = ['1D', '7D', '30D'];
    const result: any = {};
    
    for (const h of horizons) {
      const outcomes = this.outcomes.filter(o => o.horizon === h);
      const wins = outcomes.filter(o => o.result === 'WIN').length;
      const losses = outcomes.filter(o => o.result === 'LOSS').length;
      const total = wins + losses;
      
      result[h] = {
        wins,
        losses,
        rate: total > 0 ? wins / total : 0,
      };
    }
    
    return result;
  }
  
  private detectIssues(metrics: SimAggregateMetrics): SimIssue[] {
    const issues: SimIssue[] = [];
    
    // Check promotion storm
    if (metrics.stress.maxConsecutivePromotions > SIM_THRESHOLDS.maxConsecutivePromotions) {
      issues.push({
        severity: 'HIGH',
        category: 'PROMOTION_STORM',
        description: 'Too many consecutive promotions detected',
        metric: 'maxConsecutivePromotions',
        value: metrics.stress.maxConsecutivePromotions,
        threshold: SIM_THRESHOLDS.maxConsecutivePromotions,
        recommendation: 'Increase promotion thresholds or add cooldown period',
      });
    }
    
    // Check rollback storm
    if (metrics.stress.maxConsecutiveRollbacks > SIM_THRESHOLDS.maxConsecutiveRollbacks) {
      issues.push({
        severity: 'HIGH',
        category: 'ROLLBACK_STORM',
        description: 'Too many consecutive rollbacks detected',
        metric: 'maxConsecutiveRollbacks',
        value: metrics.stress.maxConsecutiveRollbacks,
        threshold: SIM_THRESHOLDS.maxConsecutiveRollbacks,
        recommendation: 'Reduce rollback sensitivity or add stability period',
      });
    }
    
    // Check 1D accuracy
    if (metrics.accuracy['1D'].rate < SIM_THRESHOLDS.minAccuracy1D) {
      issues.push({
        severity: 'MEDIUM',
        category: 'ACCURACY_DEGRADATION',
        description: '1D accuracy below threshold',
        metric: 'accuracy1D',
        value: metrics.accuracy['1D'].rate,
        threshold: SIM_THRESHOLDS.minAccuracy1D,
        recommendation: 'Review 1D model features and training data',
      });
    }
    
    // Check bias damage
    if (metrics.correlations.bias1D_accuracy30D < SIM_THRESHOLDS.maxBias1DTo30DCorrelation) {
      issues.push({
        severity: 'CRITICAL',
        category: 'BIAS_DAMAGE',
        description: '1D bias is negatively affecting 30D accuracy',
        metric: 'bias1D_accuracy30D_correlation',
        value: metrics.correlations.bias1D_accuracy30D,
        threshold: SIM_THRESHOLDS.maxBias1DTo30DCorrelation,
        recommendation: 'Reduce 1D→7D→30D bias influence caps',
      });
    }
    
    // Check excessive retrains
    if (metrics.stress.maxRetrainsPerWeek > SIM_THRESHOLDS.maxRetrainsPerWeek) {
      issues.push({
        severity: 'MEDIUM',
        category: 'RETRAIN_EXCESSIVE',
        description: 'Too many retrains in a week',
        metric: 'maxRetrainsPerWeek',
        value: metrics.stress.maxRetrainsPerWeek,
        threshold: SIM_THRESHOLDS.maxRetrainsPerWeek,
        recommendation: 'Increase retrain cooldown or outcome threshold',
      });
    }
    
    return issues;
  }
  
  private generateRecommendations(issues: SimIssue[], metrics: SimAggregateMetrics): string[] {
    const recommendations: string[] = [];
    
    if (issues.length === 0) {
      recommendations.push('System appears stable. No immediate changes recommended.');
    }
    
    // Add issue-specific recommendations
    for (const issue of issues) {
      recommendations.push(issue.recommendation);
    }
    
    // Add general recommendations
    if (metrics.lifecycle.rollbackCount > metrics.lifecycle.promotionCount * 2) {
      recommendations.push('Consider making promotion criteria less strict');
    }
    
    if (metrics.shadow.shadowWins < metrics.shadow.activeWins * 0.3) {
      recommendations.push('Shadow model underperforming - review shadow training strategy');
    }
    
    if (metrics.stress.confidenceVolatility > SIM_THRESHOLDS.maxConfidenceVolatility) {
      recommendations.push('High confidence volatility - consider smoothing or ensemble approaches');
    }
    
    return recommendations;
  }
  
  private aggregateDailyMetrics(): SimReport['dailyMetrics'] {
    const dailyMap = new Map<string, SimReport['dailyMetrics'][0]>();
    
    for (const result of this.dayResults) {
      const dateStr = result.day.toISOString().split('T')[0];
      
      if (!dailyMap.has(dateStr)) {
        dailyMap.set(dateStr, {
          date: dateStr,
          wins: 0,
          losses: 0,
          retrains: 0,
          promotions: 0,
          rollbacks: 0,
          avgConfidence: 0,
        });
      }
      
      const daily = dailyMap.get(dateStr)!;
      daily.wins += result.outcomes.filter(o => o.result === 'WIN').length;
      daily.losses += result.outcomes.filter(o => o.result === 'LOSS').length;
      daily.retrains += result.events.filter(e => e.type === 'RETRAIN').length;
      daily.promotions += result.events.filter(e => e.type === 'PROMOTE').length;
      daily.rollbacks += result.events.filter(e => e.type === 'ROLLBACK').length;
      
      const dayConfidences = result.predictions.map(p => p.confidence);
      if (dayConfidences.length > 0) {
        daily.avgConfidence = this.average(dayConfidences);
      }
    }
    
    return Array.from(dailyMap.values()).sort((a, b) => a.date.localeCompare(b.date));
  }
  
  private aggregateSymbolMetrics(): SimReport['symbolMetrics'] {
    const symbolMap: SimReport['symbolMetrics'] = {};
    
    for (const symbol of this.config.symbols) {
      const symbolOutcomes = this.outcomes.filter(o => o.symbol === symbol);
      const symbolEvents = this.dayResults
        .filter(d => d.symbol === symbol)
        .flatMap(d => d.events);
      
      const outcomes1D = symbolOutcomes.filter(o => o.horizon === '1D');
      const outcomes7D = symbolOutcomes.filter(o => o.horizon === '7D');
      const outcomes30D = symbolOutcomes.filter(o => o.horizon === '30D');
      
      symbolMap[symbol] = {
        accuracy1D: outcomes1D.length > 0 
          ? outcomes1D.filter(o => o.result === 'WIN').length / outcomes1D.length 
          : 0,
        accuracy7D: outcomes7D.length > 0 
          ? outcomes7D.filter(o => o.result === 'WIN').length / outcomes7D.length 
          : 0,
        accuracy30D: outcomes30D.length > 0 
          ? outcomes30D.filter(o => o.result === 'WIN').length / outcomes30D.length 
          : 0,
        retrains: symbolEvents.filter(e => e.type === 'RETRAIN').length,
        promotions: symbolEvents.filter(e => e.type === 'PROMOTE').length,
        rollbacks: symbolEvents.filter(e => e.type === 'ROLLBACK').length,
      };
    }
    
    return symbolMap;
  }
  
  // ═══════════════════════════════════════════════════════════════
  // UTILITY METHODS
  // ═══════════════════════════════════════════════════════════════
  
  private average(values: number[]): number {
    if (values.length === 0) return 0;
    return values.reduce((a, b) => a + b, 0) / values.length;
  }
  
  private stdDev(values: number[]): number {
    if (values.length < 2) return 0;
    const avg = this.average(values);
    const squareDiffs = values.map(v => Math.pow(v - avg, 2));
    return Math.sqrt(this.average(squareDiffs));
  }
  
  private calculateBiasAccuracyCorrelation(): number {
    // Simplified correlation calculation
    // In production, would use proper time-series correlation
    if (this.biasInfluences1Dto7D.length < 10) return 0;
    
    // Placeholder - would need proper implementation with aligned time series
    return 0;
  }
  
  private calculateConfidenceAccuracyCorrelation(): number {
    // Simplified correlation between confidence and actual outcomes
    // Would need proper implementation with aligned data
    return 0;
  }
}

// Factory function
export function createSimRunner(deps: SimDependencies, config: SimConfig): ExchangeSimRunner {
  return new ExchangeSimRunner(deps, config);
}
