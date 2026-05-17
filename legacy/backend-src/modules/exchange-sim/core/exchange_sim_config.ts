/**
 * Exchange Simulation Configuration
 * ==================================
 * 
 * Three diagnostic modes:
 * - baseline: inference + outcomes only (pure model predictive power)
 * - retrain_only: + retrain (test if retrain breaks things)
 * - lifecycle: full pipeline (retrain + shadow + promo + rollback + bias)
 * 
 * This allows isolating WHERE the problem is:
 * - baseline bad → model/features problem
 * - baseline ok, retrain_only bad → retrain is breaking things
 * - retrain_only ok, lifecycle bad → thresholds/guards problem
 */

export type ExchangeSimMode = 'baseline' | 'retrain_only' | 'lifecycle';

export interface ExchangeSimFlags {
  enabled: boolean;
  days: number;
  dbSuffix: string;
  mode: ExchangeSimMode;
  startDate: Date | null;
  symbols: string[];
  
  // Granular feature flags
  enableRetrain: boolean;
  enableShadow: boolean;
  enablePromotion: boolean;
  enableRollback: boolean;
  enableBias: boolean;
  
  // Reporting
  writeReports: boolean;
  reportDir: string;
  
  // Safety
  maxRunMinutes: number;
  killSwitchKey: string;
}

function envBool(v: string | undefined, def: boolean): boolean {
  if (v === undefined || v === null) return def;
  const s = String(v).toLowerCase().trim();
  if (['1', 'true', 'yes', 'y', 'on'].includes(s)) return true;
  if (['0', 'false', 'no', 'n', 'off'].includes(s)) return false;
  return def;
}

function envNum(v: string | undefined, def: number): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : def;
}

// Default symbols
const DEFAULT_SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT'];

// Mode-based defaults
const MODE_DEFAULTS: Record<ExchangeSimMode, {
  enableRetrain: boolean;
  enableShadow: boolean;
  enablePromotion: boolean;
  enableRollback: boolean;
  enableBias: boolean;
}> = {
  baseline: {
    enableRetrain: false,
    enableShadow: true,  // Shadow for comparison, but doesn't affect active
    enablePromotion: false,
    enableRollback: false,
    enableBias: false,
  },
  retrain_only: {
    enableRetrain: true,
    enableShadow: true,
    enablePromotion: false,
    enableRollback: false,
    enableBias: false,
  },
  lifecycle: {
    enableRetrain: true,
    enableShadow: true,
    enablePromotion: true,
    enableRollback: true,
    enableBias: true,
  },
};

export function loadExchangeSimFlags(): ExchangeSimFlags {
  const enabled = envBool(process.env.EXCHANGE_SIM_ENABLED, false);
  const days = envNum(process.env.EXCHANGE_SIM_DAYS, 90);
  const dbSuffix = (process.env.EXCHANGE_SIM_DB_SUFFIX || '_sim').trim();
  
  // Parse mode
  const modeRaw = (process.env.EXCHANGE_SIM_MODE || 'baseline').trim().toLowerCase();
  const mode: ExchangeSimMode = 
    modeRaw === 'lifecycle' ? 'lifecycle' :
    modeRaw === 'retrain_only' ? 'retrain_only' :
    'baseline';
  
  // Parse symbols
  const symbolsStr = process.env.EXCHANGE_SIM_SYMBOLS;
  const symbols = symbolsStr 
    ? symbolsStr.split(',').map(s => s.trim().toUpperCase())
    : DEFAULT_SYMBOLS;
  
  // Parse start date
  const startStr = process.env.EXCHANGE_SIM_START;
  let startDate: Date | null = null;
  if (startStr) {
    startDate = new Date(startStr);
    if (isNaN(startDate.getTime())) {
      startDate = null;
    }
  }
  
  // Get mode defaults
  const modeDefaults = MODE_DEFAULTS[mode];
  
  // Granular overrides (can override mode defaults)
  const enableRetrain = process.env.EXCHANGE_SIM_ENABLE_RETRAIN !== undefined
    ? envBool(process.env.EXCHANGE_SIM_ENABLE_RETRAIN, modeDefaults.enableRetrain)
    : modeDefaults.enableRetrain;
  
  const enableShadow = process.env.EXCHANGE_SIM_ENABLE_SHADOW !== undefined
    ? envBool(process.env.EXCHANGE_SIM_ENABLE_SHADOW, modeDefaults.enableShadow)
    : modeDefaults.enableShadow;
  
  const enablePromotion = process.env.EXCHANGE_SIM_ENABLE_PROMOTION !== undefined
    ? envBool(process.env.EXCHANGE_SIM_ENABLE_PROMOTION, modeDefaults.enablePromotion)
    : modeDefaults.enablePromotion;
  
  const enableRollback = process.env.EXCHANGE_SIM_ENABLE_ROLLBACK !== undefined
    ? envBool(process.env.EXCHANGE_SIM_ENABLE_ROLLBACK, modeDefaults.enableRollback)
    : modeDefaults.enableRollback;
  
  const enableBias = process.env.EXCHANGE_SIM_ENABLE_BIAS !== undefined
    ? envBool(process.env.EXCHANGE_SIM_ENABLE_BIAS, modeDefaults.enableBias)
    : modeDefaults.enableBias;
  
  const writeReports = envBool(process.env.EXCHANGE_SIM_WRITE_REPORTS, true);
  const reportDir = (process.env.EXCHANGE_SIM_REPORT_DIR || '/tmp').trim();
  
  const maxRunMinutes = envNum(process.env.EXCHANGE_SIM_MAX_RUN_MINUTES, 30);
  const killSwitchKey = process.env.EXCHANGE_SIM_KILL_SWITCH_KEY || 'sim_kill_switch';
  
  return {
    enabled,
    days,
    dbSuffix,
    mode,
    startDate,
    symbols,
    enableRetrain,
    enableShadow,
    enablePromotion,
    enableRollback,
    enableBias,
    writeReports,
    reportDir,
    maxRunMinutes,
    killSwitchKey,
  };
}

/**
 * Gates class - central guard for feature flags
 */
export class ExchangeSimGates {
  constructor(public flags: ExchangeSimFlags) {}
  
  get retrainEnabled(): boolean { return this.flags.enableRetrain; }
  get shadowEnabled(): boolean { return this.flags.enableShadow; }
  get promotionEnabled(): boolean { return this.flags.enablePromotion; }
  get rollbackEnabled(): boolean { return this.flags.enableRollback; }
  get biasEnabled(): boolean { return this.flags.enableBias; }
  
  // Summary for logging
  getSummary(): string {
    return `mode=${this.flags.mode} | retrain=${this.retrainEnabled} shadow=${this.shadowEnabled} promo=${this.promotionEnabled} rollback=${this.rollbackEnabled} bias=${this.biasEnabled}`;
  }
}
