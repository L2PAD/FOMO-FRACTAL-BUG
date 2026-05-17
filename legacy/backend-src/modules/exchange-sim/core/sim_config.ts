/**
 * Simulation Configuration
 * ========================
 * 
 * Reads config from environment and provides defaults.
 */

import { SimConfig, SimHorizon } from '../exchange_sim.types.js';

// Default symbols (TOP-20)
const DEFAULT_SYMBOLS = [
  'BTC', 'ETH', 'BNB', 'SOL', 'XRP',
  'ADA', 'AVAX', 'DOT', 'LINK', 'MATIC',
  'LTC', 'ATOM', 'NEAR', 'APT', 'ARB',
  'OP', 'TRX', 'DOGE', 'ETC', 'UNI'
];

// Horizons in days
export const HORIZON_DAYS: Record<SimHorizon, number> = {
  '1D': 1,
  '7D': 7,
  '30D': 30,
};

export interface SimEnvConfig {
  enabled: boolean;
  mode: 'FULL' | 'DRY';
  dbSuffix: string;
  symbols: string[];
  days: number;
  startDate: Date | null;
  maxRunMinutes: number;
  killSwitchKey: string;
}

export function loadSimConfigFromEnv(): SimEnvConfig {
  const enabled = process.env.EXCHANGE_SIM_ENABLED === 'true';
  const mode = (process.env.EXCHANGE_SIM_MODE || 'FULL') as 'FULL' | 'DRY';
  const dbSuffix = process.env.EXCHANGE_SIM_DB_SUFFIX || '_sim';
  
  // Parse symbols
  const symbolsStr = process.env.EXCHANGE_SIM_SYMBOLS;
  const symbols = symbolsStr 
    ? symbolsStr.split(',').map(s => s.trim().toUpperCase())
    : DEFAULT_SYMBOLS;
  
  // Parse days
  const days = parseInt(process.env.EXCHANGE_SIM_DAYS || '365', 10);
  
  // Parse start date
  const startStr = process.env.EXCHANGE_SIM_START;
  let startDate: Date | null = null;
  if (startStr) {
    startDate = new Date(startStr);
    if (isNaN(startDate.getTime())) {
      console.warn('[SimConfig] Invalid EXCHANGE_SIM_START, will use (today - days)');
      startDate = null;
    }
  }
  
  const maxRunMinutes = parseInt(process.env.EXCHANGE_SIM_MAX_RUN_MINUTES || '30', 10);
  const killSwitchKey = process.env.EXCHANGE_SIM_KILL_SWITCH_KEY || 'sim_kill_switch';
  
  return {
    enabled,
    mode,
    dbSuffix,
    symbols,
    days,
    startDate,
    maxRunMinutes,
    killSwitchKey,
  };
}

export function buildSimConfig(envConfig: SimEnvConfig): SimConfig {
  // Calculate start date if not provided
  let startDate: Date;
  if (envConfig.startDate) {
    startDate = envConfig.startDate;
  } else {
    // Default: start (days) ago from today
    startDate = new Date();
    startDate.setDate(startDate.getDate() - envConfig.days);
  }
  
  // Start at midnight UTC
  startDate.setUTCHours(0, 0, 0, 0);
  
  return {
    symbols: envConfig.symbols,
    startDate,
    days: envConfig.days,
    dbSuffix: envConfig.dbSuffix,
    maxRunMinutes: envConfig.maxRunMinutes,
    killSwitchKey: envConfig.killSwitchKey,
    mode: envConfig.mode,
  };
}

// Issue detection thresholds (UPDATED for Capital-Centric)
export const SIM_THRESHOLDS = {
  // Promotion storm: too many promotions in short time
  maxPromotionsPerWeek: 3,
  maxConsecutivePromotions: 5,
  
  // Rollback storm (should be almost impossible now with cooldown)
  maxRollbacksPerWeek: 1,
  maxConsecutiveRollbacks: 2,
  
  // Retrain frequency
  maxRetrainsPerWeek: 7,
  
  // Bias damage: 1D hurting 30D
  maxBias1DTo30DCorrelation: -0.3,
  
  // Legacy accuracy thresholds (still tracked)
  minAccuracy1D: 0.45,
  minAccuracy7D: 0.45,
  minAccuracy30D: 0.45,
  
  // NEW: Trade Win Rate thresholds (Capital-Centric)
  minTradeWinRate1D: 0.45,
  minTradeWinRate7D: 0.50,
  minTradeWinRate30D: 0.55,
  
  // NEW: Equity/drawdown thresholds
  maxDrawdown1D: 0.15,
  maxDrawdown7D: 0.15,
  maxDrawdown30D: 0.20,
  minStabilityScore: 0.50,
  
  // Confidence calibration
  maxConfidenceVolatility: 0.25,
  
  // Drift (no longer triggers rollback, just warning)
  maxDriftCriticalDays: 7,
  
  // Trade activity
  minTradesFor90Days: 50, // Minimum trades to be statistically valid
};

