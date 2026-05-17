/**
 * Sentiment Simulation Runner
 * ============================
 * 
 * BLOCK 7+8: Walk-forward simulation with Production CHOP Gate.
 * 
 * Flow:
 * 1. Load finalized samples with prices
 * 2. For each sample with |bias| > threshold:
 *    - Apply CHOP gate (no lookahead)
 *    - Determine direction (LONG/SHORT)
 *    - Calculate return (adjusted for fees)
 *    - Track capital
 * 3. Compute metrics and generate report
 */

import { SentimentDirSampleModel } from '../dataset/sentiment-dir-sample.model.js';
import { SentimentSimCapital } from './sentiment_sim.capital.js';
import { 
  SentimentSimConfig, 
  SimReport, 
  SimTrade,
  SimMetrics,
  SimWindow,
  SIM_TARGETS,
} from './sentiment_sim.types.js';
import { ENTRY_THRESHOLD } from '../contracts/sentiment.risk.types.js';
import { computeRegimeBreakdown, classifyRegime } from './sentiment_sim.regime.js';
import { runMonteCarlo } from './sentiment_sim.montecarlo.js';
import { getRegimeScoreService, RegimeResult } from '../risk/services/regime-score.service.js';
import { getHistoricalPrices, generateSyntheticPrices } from './sentiment_sim.price_provider.js';
import { createChopGateService, SentimentChopGateService } from '../risk/sentiment-chop-gate.service.js';
import { ChopConfig, ChopTagResult } from '../risk/chop.types.js';

export class SentimentSimulationRunner {
  private regimeService = getRegimeScoreService();
  private priceCache: Map<string, { closes: number[]; highs: number[]; lows: number[] }> = new Map();

  /**
   * Run walk-forward simulation
   */
  async run(config: SentimentSimConfig): Promise<SimReport> {
    // Clear price cache for fresh run
    this.priceCache.clear();
    
    const capitalEngine = new SentimentSimCapital(config.startCapital);
    const trades: SimTrade[] = [];
    const returns: number[] = [];
    let skippedChopLegacy = 0;
    let skippedBias = 0;
    let skippedRegime = 0;
    let skippedChopV1 = 0;
    let transitionTrades = 0;
    let trendTrades = 0;

    // Load samples
    const samples = await this.loadSamples(config);
    console.log(`[Sim] Loaded ${samples.length} samples for ${config.days}D ${config.window} ${config.mode}`);
    console.log(`[Sim] Config: chopGate=${config.chopGate}, chopV1=${config.chopV1}, minBias=${config.minBias}, regimeFilter=${config.regimeFilter}`);

    // Pre-load price history for filters if enabled
    if (config.regimeFilter || config.chopV1) {
      await this.preloadPriceHistory(samples);
    }

    // Create CHOP Gate service if enabled
    const chopGateService = config.chopV1 
      ? createChopGateService(config.chopConfig || {})
      : null;

    // CHOP stats tracking
    const chopTags: ChopTagResult[] = [];

    // Process each sample
    for (const s of samples) {
      // Check entry threshold
      const threshold = ENTRY_THRESHOLD[config.window];
      if (Math.abs(s.bias) < threshold) continue;

      // Extra minBias filter
      if (config.minBias && Math.abs(s.bias) < config.minBias) {
        skippedBias++;
        continue;
      }

      // Skip if no prices
      if (!s.priceAtAsOf || !s.priceAtHorizonClose) continue;
      if (s.priceAtAsOf <= 0 || s.priceAtHorizonClose <= 0) continue;

      // Variables for regime info
      let regimeResult: RegimeResult | null = null;
      let chopTag: ChopTagResult | null = null;
      let sizeMultiplier = 1.0;

      // BLOCK 8: Production CHOP Gate v1 (no lookahead)
      if (config.chopV1 && chopGateService) {
        const priceData = this.priceCache.get(s.symbol);
        if (priceData && priceData.closes.length > 100) {
          // Find index closest to asOf (use last bar as current)
          const index = priceData.closes.length - 1;
          chopTag = chopGateService.tagChopAtIndex(
            priceData.closes,
            priceData.highs,
            priceData.lows,
            index
          );
          chopTags.push(chopTag);
          
          // Skip if hard CHOP
          if (chopTag.isChop) {
            skippedChopV1++;
            continue;
          }
          
          // Apply severity-based position scaling
          // severityScore 0-0.4 = full size (1.0)
          // severityScore 0.4-0.6 = reduced size (0.7)
          // severityScore 0.6-0.8 = half size (0.5)
          // severityScore > 0.8 = quarter size (0.25)
          if (config.transitionScaling && chopTag.severityScore > 0.4) {
            if (chopTag.severityScore > 0.8) {
              sizeMultiplier = 0.25;
            } else if (chopTag.severityScore > 0.6) {
              sizeMultiplier = 0.5;
            } else {
              sizeMultiplier = 0.7;
            }
          }
        }
      }

      // Proactive Regime Filter v1.1 (alternative to chopV1)
      if (config.regimeFilter && !config.chopV1) {
        regimeResult = await this.evaluateRegimeAtEntry(s.symbol, new Date(s.asOf), s.priceAtAsOf);
        
        if (regimeResult.regime === 'CHOP') {
          skippedRegime++;
          continue;
        }
        
        if (config.transitionScaling && regimeResult.regime === 'TRANSITION') {
          sizeMultiplier = 0.5;
          transitionTrades++;
        } else if (regimeResult.regime === 'TREND') {
          trendTrades++;
        }
      }

      // Legacy CHOP gate (hindsight, for comparison only)
      if (config.chopGate && !config.regimeFilter && !config.chopV1) {
        const predictedRegime = classifyRegime(s.priceAtAsOf, s.priceAtHorizonClose, s.symbol);
        if (predictedRegime === 'CHOP') {
          skippedChopLegacy++;
          continue;
        }
      }

      // Determine direction based on bias
      const direction = s.bias > 0 ? 'LONG' : 'SHORT';

      // Calculate raw return
      const rawReturn = direction === 'LONG'
        ? (s.priceAtHorizonClose - s.priceAtAsOf) / s.priceAtAsOf
        : (s.priceAtAsOf - s.priceAtHorizonClose) / s.priceAtAsOf;

      // Apply fees
      const feePct = (config.feeBps + config.slippageBps) / 10000;
      
      // Apply position sizing - scaled return based on position size
      const scaledReturn = (rawReturn - feePct) * sizeMultiplier;

      // Track
      returns.push(scaledReturn);
      capitalEngine.applyReturn(scaledReturn, new Date(s.asOf));

      trades.push({
        date: new Date(s.asOf),
        symbol: s.symbol,
        direction,
        bias: s.bias,
        entryPrice: s.priceAtAsOf,
        exitPrice: s.priceAtHorizonClose,
        returnPct: scaledReturn,
        capitalAfter: capitalEngine.getCapital(),
        regime: regimeResult?.regime,
        regimeScore: regimeResult?.regimeScore,
        sizeMultiplier,
        chopTag: chopTag ? {
          isChop: chopTag.isChop,
          atrPercentile: chopTag.atrPercentile,
          rangeN: chopTag.rangeN,
          slope: chopTag.slope,
          severityScore: chopTag.severityScore,
        } : undefined,
      });
    }

    console.log(`[Sim] Processed: ${trades.length} trades`);
    console.log(`[Sim] Skipped: chopLegacy=${skippedChopLegacy}, chopV1=${skippedChopV1}, bias=${skippedBias}, regime=${skippedRegime}`);
    if (config.regimeFilter) {
      console.log(`[Sim] Regime breakdown: TRANSITION=${transitionTrades}, TREND=${trendTrades}`);
    }

    // Compute metrics
    const metrics = this.computeMetrics(returns, capitalEngine);

    // Evaluate pass/fail
    const { status, failReasons } = this.evaluateTargets(metrics);

    // Compute regime breakdown (post-hoc analysis)
    const regime = computeRegimeBreakdown(trades);

    // Run Monte Carlo (1000 iterations)
    const monteCarlo = runMonteCarlo(trades, {
      iterations: 1000,
      startCapital: config.startCapital,
    });

    // Compute CHOP stats
    const chopStats = chopTags.length > 0 ? {
      skipped: skippedChopV1,
      avgAtrPctl: chopTags.reduce((s, t) => s + t.atrPercentile, 0) / chopTags.length,
      avgRangeN: chopTags.reduce((s, t) => s + t.rangeN, 0) / chopTags.length,
      avgSlope: chopTags.reduce((s, t) => s + Math.abs(t.slope), 0) / chopTags.length,
    } : undefined;

    return {
      config,
      metrics,
      equityCurve: capitalEngine.getEquityCurve(),
      trades,
      status,
      failReasons,
      regime,
      monteCarlo,
      chopStats,
    };
  }

  /**
   * Pre-load price history for unique symbols
   */
  private async preloadPriceHistory(samples: any[]): Promise<void> {
    const uniqueSymbols = [...new Set(samples.map(s => s.symbol))];
    console.log(`[Sim] Pre-loading price history for ${uniqueSymbols.length} symbols`);
    
    for (const symbol of uniqueSymbols) {
      const sample = samples.find(s => s.symbol === symbol);
      if (!sample) continue;

      const priceHistory = await getHistoricalPrices(symbol, new Date(sample.asOf), 200);
      if (priceHistory && priceHistory.closes.length >= 50) {
        this.priceCache.set(symbol, {
          closes: priceHistory.closes,
          highs: priceHistory.highs,
          lows: priceHistory.lows,
        });
      }
    }
    console.log(`[Sim] Loaded price history for ${this.priceCache.size} symbols`);
  }

  /**
   * Evaluate regime at entry using ONLY data available at that time
   */
  private async evaluateRegimeAtEntry(
    symbol: string, 
    asOf: Date, 
    currentPrice: number
  ): Promise<RegimeResult> {
    // Try to get cached price history
    let priceData = this.priceCache.get(symbol);
    
    if (!priceData || priceData.closes.length < 50) {
      // Try to fetch from DB
      const history = await getHistoricalPrices(symbol, asOf, 200);
      if (history && history.closes.length >= 50) {
        priceData = {
          closes: history.closes,
          highs: history.highs,
          lows: history.lows,
        };
        this.priceCache.set(symbol, priceData);
      } else {
        // Generate synthetic data based on current price
        // This is conservative - will likely classify as CHOP
        const synthetic = generateSyntheticPrices(currentPrice, 200, 0.015);
        priceData = {
          closes: synthetic.closes,
          highs: synthetic.highs,
          lows: synthetic.lows,
        };
      }
    }

    return this.regimeService.evaluate(
      priceData.closes,
      priceData.highs,
      priceData.lows
    );
  }

  /**
   * Load finalized samples for simulation period
   */
  private async loadSamples(config: SentimentSimConfig) {
    const since = new Date(Date.now() - config.days * 24 * 60 * 60 * 1000);

    return SentimentDirSampleModel.find({
      window: config.window,
      labelVersion: 1,
      priceAtAsOf: { $exists: true, $ne: null },
      priceAtHorizonClose: { $exists: true, $ne: null },
      asOf: { $gte: since },
    })
      .sort({ asOf: 1 })
      .lean();
  }

  /**
   * Compute simulation metrics
   */
  private computeMetrics(returns: number[], capital: SentimentSimCapital): SimMetrics {
    const trades = returns.length;
    const wins = returns.filter(r => r > 0).length;
    const losses = returns.filter(r => r < 0).length;

    const winRate = trades > 0 ? wins / trades : 0;
    const expectancy = trades > 0 
      ? returns.reduce((a, b) => a + b, 0) / trades 
      : 0;

    // Sharpe-like (mean / std)
    const mean = trades > 0 
      ? returns.reduce((a, b) => a + b, 0) / trades 
      : 0;
    const variance = trades > 0
      ? returns.reduce((a, x) => a + (x - mean) ** 2, 0) / trades
      : 0;
    const std = Math.sqrt(variance);
    const sharpeLike = std > 1e-9 ? mean / std : 0;

    return {
      trades,
      wins,
      losses,
      winRate,
      expectancy,
      maxDD: capital.getMaxDD(),
      sharpeLike,
      equityFinal: capital.getCapital(),
      totalReturnPct: capital.getTotalReturnPct(),
    };
  }

  /**
   * Evaluate against targets
   */
  private evaluateTargets(metrics: SimMetrics): { status: 'PASS' | 'FAIL' | 'WARN'; failReasons: string[] } {
    const failReasons: string[] = [];

    if (metrics.winRate < SIM_TARGETS.minWinRate) {
      failReasons.push(`WinRate ${(metrics.winRate * 100).toFixed(1)}% < ${SIM_TARGETS.minWinRate * 100}%`);
    }

    if (metrics.expectancy < SIM_TARGETS.minExpectancy) {
      failReasons.push(`Expectancy ${(metrics.expectancy * 100).toFixed(2)}% < ${SIM_TARGETS.minExpectancy * 100}%`);
    }

    if (metrics.sharpeLike < SIM_TARGETS.minSharpe) {
      failReasons.push(`Sharpe ${metrics.sharpeLike.toFixed(3)} < ${SIM_TARGETS.minSharpe}`);
    }

    if (metrics.maxDD > SIM_TARGETS.maxDD) {
      failReasons.push(`MaxDD ${(metrics.maxDD * 100).toFixed(1)}% > ${SIM_TARGETS.maxDD * 100}%`);
    }

    if (failReasons.length === 0) {
      return { status: 'PASS', failReasons: [] };
    }

    // Warn if only Sharpe is low but others pass
    if (failReasons.length === 1 && failReasons[0].includes('Sharpe')) {
      return { status: 'WARN', failReasons };
    }

    return { status: 'FAIL', failReasons };
  }
}

// Singleton
let runnerInstance: SentimentSimulationRunner | null = null;

export function getSentimentSimulationRunner(): SentimentSimulationRunner {
  if (!runnerInstance) {
    runnerInstance = new SentimentSimulationRunner();
  }
  return runnerInstance;
}

console.log('[Sentiment-ML] Simulation Runner loaded (BLOCK 7)');
