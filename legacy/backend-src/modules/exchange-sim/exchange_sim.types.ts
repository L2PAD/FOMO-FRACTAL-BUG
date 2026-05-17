/**
 * Exchange Simulation Types
 * =========================
 * 
 * UPDATED for Capital-Centric simulation.
 * 
 * Key additions:
 * - TradeWinRate tracking
 * - Equity curve metrics
 * - ENV/DIR separation
 * - Combined verdict evaluation
 */

export type SimHorizon = '1D' | '7D' | '30D';

export interface SimConfig {
  // Symbols to simulate
  symbols: string[];
  
  // Time range
  startDate: Date;
  days: number;
  
  // Database isolation
  dbSuffix: string; // e.g., '_sim' -> DB_NAME_sim
  
  // Safety
  maxRunMinutes: number;
  killSwitchKey: string;
  
  // Mode
  mode: 'FULL' | 'DRY'; // FULL = real retrain, DRY = metrics only
}

// ═══════════════════════════════════════════════════════════════
// TRADE EVALUATION (Capital-Centric)
// ═══════════════════════════════════════════════════════════════

export interface TradeEvaluation {
  traded: boolean;              // true if env=USE && dir!=NEUTRAL
  win?: boolean;                // direction correct?
  envLabel: 'USE' | 'WARNING' | 'IGNORE';
  dirLabel: 'UP' | 'DOWN' | 'NEUTRAL';
  realizedReturn: number;
  skippedReason?: string;
}

export interface SimTradeStats {
  totalTrades: number;
  wins: number;
  losses: number;
  skippedTrades: number;        // env blocked or dir neutral
  tradeWinRate: number;         // wins / (wins + losses)
}

// ═══════════════════════════════════════════════════════════════
// EQUITY METRICS (Capital-Centric)
// ═══════════════════════════════════════════════════════════════

export interface SimEquityMetrics {
  equityFinal: number;          // starting from 1.0
  maxDrawdown: number;          // 0..1
  sharpeLike: number;           // mean return / std return
  stabilityScore: number;       // 0..1
  avgTradeReturn: number;
  stdTradeReturn: number;
  consecutiveLossMax: number;
}

// ═══════════════════════════════════════════════════════════════
// DAY RESULT (Enhanced)
// ═══════════════════════════════════════════════════════════════

export interface SimDayResult {
  day: Date;
  symbol: string;
  
  // Inference (now with ENV + DIR separation)
  predictions: {
    horizon: SimHorizon;
    
    // Environment model
    envLabel: 'USE' | 'WARNING' | 'IGNORE';
    envConfidence: number;
    
    // Direction model
    dirLabel: 'UP' | 'DOWN' | 'NEUTRAL';
    dirConfidence: number;
    
    // Combined verdict
    action: 'BUY' | 'SELL' | 'HOLD';
    confidence: number;
    
    targetPrice: number;
    modelVersion: string;
  }[];
  
  // Outcomes resolved (enhanced)
  outcomes: {
    horizon: SimHorizon;
    result: 'WIN' | 'LOSS' | 'SKIPPED';
    actualReturn: number;
    expectedReturn: number;
    traded: boolean;             // whether position was taken
    envLabel?: string;
    dirLabel?: string;
  }[];
  
  // Lifecycle events
  events: SimEvent[];
}

export interface SimEvent {
  type: 'RETRAIN' | 'SHADOW_EVAL' | 'PROMOTE' | 'ROLLBACK' | 'BIAS_UPDATE' | 'GUARDRAIL_TRIGGER' | 'DRIFT_WARNING';
  horizon?: SimHorizon;
  details: Record<string, any>;
  timestamp: Date;
}

// ═══════════════════════════════════════════════════════════════
// AGGREGATE METRICS (Enhanced)
// ═══════════════════════════════════════════════════════════════

export interface SimAggregateMetrics {
  // Basic counts
  totalDays: number;
  totalSymbols: number;
  totalPredictions: number;
  totalOutcomes: number;
  
  // Legacy accuracy by horizon (still track for comparison)
  accuracy: {
    '1D': { wins: number; losses: number; rate: number };
    '7D': { wins: number; losses: number; rate: number };
    '30D': { wins: number; losses: number; rate: number };
  };
  
  // NEW: Trade stats by horizon (Capital-Centric)
  tradeStats: {
    '1D': SimTradeStats;
    '7D': SimTradeStats;
    '30D': SimTradeStats;
  };
  
  // NEW: Equity metrics by horizon
  equityMetrics: {
    '1D': SimEquityMetrics;
    '7D': SimEquityMetrics;
    '30D': SimEquityMetrics;
  };
  
  // NEW: ENV accuracy (USE/IGNORE/WARNING vs volatility regime)
  envAccuracy: {
    '1D': { correct: number; total: number; rate: number };
    '7D': { correct: number; total: number; rate: number };
    '30D': { correct: number; total: number; rate: number };
  };
  
  // NEW: DIR accuracy (UP/DOWN/NEUTRAL vs realized return)
  dirAccuracy: {
    '1D': { correct: number; total: number; rate: number };
    '7D': { correct: number; total: number; rate: number };
    '30D': { correct: number; total: number; rate: number };
  };
  
  // Lifecycle stability
  lifecycle: {
    retrainCount: number;
    promotionCount: number;
    rollbackCount: number;
    throttledRetrains: number;
    guardrailTriggers: number;
    driftWarnings: number;
    driftCriticals: number;
  };
  
  // Shadow comparison
  shadow: {
    shadowWins: number;
    activeWins: number;
    ties: number;
    avgDelta: number;
  };
  
  // Cross-horizon bias
  bias: {
    biasUpdates: number;
    avg1Dto7DInfluence: number;
    avg7Dto30DInfluence: number;
    maxInfluenceApplied: number;
  };
  
  // Stress metrics
  stress: {
    maxConsecutivePromotions: number;
    maxConsecutiveRollbacks: number;
    maxRetrainsPerWeek: number;
    confidenceVolatility: number;
  };
  
  // Correlation analysis
  correlations: {
    bias1D_accuracy30D: number;
    confidence_accuracy: number;
  };
}

export type DiagnosticMode = 'baseline' | 'retrain_only' | 'lifecycle';

export interface DiagnosticGates {
  retrain: boolean;
  shadow: boolean;
  promotion: boolean;
  rollback: boolean;
  bias: boolean;
}

// ═══════════════════════════════════════════════════════════════
// SIMULATION REPORT (Enhanced)
// ═══════════════════════════════════════════════════════════════

export interface SimReport {
  config: SimConfig;
  startedAt: Date;
  completedAt: Date;
  status: 'COMPLETED' | 'KILLED' | 'ERROR' | 'TIMEOUT';
  
  // Diagnostic metadata
  diagnosticMode?: DiagnosticMode;
  gates?: DiagnosticGates;
  
  metrics: SimAggregateMetrics;
  
  // Daily breakdown (for charts)
  dailyMetrics: {
    date: string;
    wins: number;
    losses: number;
    skipped: number;            // NEW: skipped trades
    tradeWinRate: number;       // NEW: daily trade win rate
    equity: number;             // NEW: running equity
    retrains: number;
    promotions: number;
    rollbacks: number;
    avgConfidence: number;
  }[];
  
  // Per-symbol breakdown
  symbolMetrics: Record<string, {
    accuracy1D: number;
    accuracy7D: number;
    accuracy30D: number;
    // NEW: Trade win rates
    tradeWinRate1D: number;
    tradeWinRate7D: number;
    tradeWinRate30D: number;
    // NEW: Equity
    equityFinal: number;
    maxDrawdown: number;
    retrains: number;
    promotions: number;
    rollbacks: number;
  }>;
  
  // Issues detected
  issues: SimIssue[];
  
  // Recommendations
  recommendations: string[];
}

export interface SimIssue {
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  category: 
    | 'PROMOTION_STORM' 
    | 'ROLLBACK_STORM' 
    | 'BIAS_DAMAGE' 
    | 'DRIFT_INSTABILITY' 
    | 'RETRAIN_EXCESSIVE' 
    | 'ACCURACY_DEGRADATION'
    | 'TRADE_WINRATE_LOW'       // NEW
    | 'DRAWDOWN_HIGH'          // NEW
    | 'STABILITY_LOW';         // NEW
  description: string;
  metric: string;
  value: number;
  threshold: number;
  recommendation: string;
}

// Price provider interface for simulation
export interface SimPriceProvider {
  getCloseOnDay(symbol: string, day: Date): Promise<number | null>;
  getOHLC(symbol: string, day: Date): Promise<{ open: number; high: number; low: number; close: number } | null>;
}

// Now provider for time simulation
export interface SimNowProvider {
  now(): Date;
  set(date: Date): void;
}

// Audit logger for simulation events
export interface SimAuditLogger {
  log(event: {
    type: string;
    simDay: Date;
    symbol?: string;
    horizon?: SimHorizon;
    details?: Record<string, any>;
  }): Promise<void>;
  
  getEvents(): Promise<SimEvent[]>;
}
