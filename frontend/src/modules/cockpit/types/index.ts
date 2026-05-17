// Cockpit Types

export interface SystemStatus {
  executionMode: 'PAPER' | 'APPROVAL' | 'LIVE';
  capitalMode: 'PILOT' | 'STANDARD';
  systemHealth: 'HEALTHY' | 'DEGRADED' | 'CRITICAL';
  killSwitchState: boolean;
  circuitBreakerState: boolean;
  connectedExchanges: string[];
  totalEquity: number;
  dailyPnL: number;
  alertsCount: number;
  latency: { avg: number; p95: number; p99: number };
}

export interface MarketRegime {
  regime: 'TRENDING_UP' | 'TRENDING_DOWN' | 'RANGING' | 'VOLATILE' | 'COMPRESSION';
  confidence: number;
  transitionProbability: number;
  nextLikelyRegime: string;
}

export interface CapitalFlow {
  flowBias: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  dominantRotation: string;
  flowStrength: number;
}

export interface FractalMatch {
  alignment: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  topMatch: string;
  similarityScore: number;
}

export interface Microstructure {
  pressureBias: 'BUY' | 'SELL' | 'NEUTRAL';
  vacuumState: boolean;
  cascadeRisk: number;
  impactState: 'LOW' | 'MEDIUM' | 'HIGH';
}

export interface Hypothesis {
  id: string;
  type: string;
  direction: 'LONG' | 'SHORT' | 'NEUTRAL';
  confidence: number;
  reliability: number;
  alphaFamily: string;
  decayStage: 'FRESH' | 'MATURE' | 'DECAYING' | 'EXPIRED';
  scenarioAlignment: number;
  capitalFlowAlignment: number;
  fractalAlignment: number;
  explanation: string;
  conflicts: string[];
  executionEligibility: boolean;
}

export interface Position {
  symbol: string;
  direction: 'LONG' | 'SHORT';
  size: number;
  entry: number;
  currentPrice: number;
  pnl: number;
  riskContribution: number;
  targetWeight: number;
  currentWeight: number;
}

export interface ApprovalItem {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  size: number;
  strategy: string;
  confidence: number;
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH';
  impactState: string;
  exchange: string;
  createdAt: string;
}

export interface ChartObject {
  type: 'trendline' | 'horizontal' | 'zone' | 'channel' | 'triangle' | 'wedge' | 'breakout' | 'invalidation' | 'target' | 'liquidity' | 'support_resistance' | 'fractal' | 'hypothesis_path' | 'confidence_corridor';
  points: { x: number; y: number }[];
  style: {
    color: string;
    lineWidth: number;
    lineDash?: number[];
    fill?: string;
  };
  label?: string;
  visible: boolean;
}

export interface Candle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ChartPayload {
  symbol: string;
  timeframe: string;
  candles: Candle[];
  indicators: Record<string, number[]>;
  objects: ChartObject[];
  hypothesisPaths: any[];
  fractalProjections: any[];
}

export interface Alert {
  id: string;
  type: 'RISK' | 'EXECUTION' | 'MARKET' | 'SYSTEM';
  severity: 'INFO' | 'WARNING' | 'CRITICAL';
  message: string;
  timestamp: string;
  read: boolean;
}

export interface PortfolioState {
  equity: number;
  realizedPnL: number;
  unrealizedPnL: number;
  dailyPnL: number;
  weeklyPnL: number;
  longExposure: number;
  shortExposure: number;
  netExposure: number;
  positions: Position[];
}

export interface RiskState {
  killSwitchState: boolean;
  circuitBreakerState: boolean;
  throttleState: boolean;
  drawdown: number;
  blockedTrades: number;
  var95: number;
  var99: number;
  riskBudget: Record<string, number>;
}

export type CockpitPage = 'overview' | 'chart' | 'hypotheses' | 'execution' | 'portfolio' | 'risk' | 'system';
