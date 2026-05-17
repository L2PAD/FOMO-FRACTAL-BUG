/**
 * Exchange Simulation Main Entry
 * ==============================
 * 
 * Builds and runs the complete simulation.
 * 
 * Usage:
 *   EXCHANGE_SIM_ENABLED=true npm run sim:exchange
 */

import { loadSimConfigFromEnv, buildSimConfig } from './core/sim_config.js';
import { loadExchangeSimFlags, ExchangeSimGates } from './core/exchange_sim_config.js';
import { connectSimDb, disconnectSimDb, ensureSimIndexes, getSimDb } from './core/sim_db.js';
import { createSimPriceProvider } from './providers/sim_price_provider.js';
import { createSimRunner } from './core/exchange_sim_runner.js';
import { createSimReporter } from './reporters/sim_reporter.js';
import { resetSimNowProvider } from './core/sim_now_provider.js';
import { SimReport } from './exchange_sim.types.js';

export interface SimRunResult {
  success: boolean;
  report?: SimReport;
  error?: string;
}

/**
 * Build and run simulation with all dependencies
 */
export async function runExchangeSimulation(): Promise<SimRunResult> {
  // Load config from environment
  const envConfig = loadSimConfigFromEnv();
  
  if (!envConfig.enabled) {
    console.log('[ExchangeSim] Simulation disabled (EXCHANGE_SIM_ENABLED=false)');
    return { success: false, error: 'Simulation disabled' };
  }
  
  // Load diagnostic flags
  const diagFlags = loadExchangeSimFlags();
  const gates = new ExchangeSimGates(diagFlags);
  
  console.log('[ExchangeSim] Starting Exchange ML Diagnostic Simulation');
  console.log('[ExchangeSim] ═══════════════════════════════════════════════');
  console.log('[ExchangeSim] MODE:', diagFlags.mode.toUpperCase());
  console.log('[ExchangeSim] Gates:', gates.getSummary());
  console.log('[ExchangeSim] Symbols:', envConfig.symbols.join(', '));
  console.log('[ExchangeSim] Days:', envConfig.days);
  console.log('[ExchangeSim] ═══════════════════════════════════════════════');
  
  let simDb;
  
  try {
    // Connect to simulation database
    const mongoUri = process.env.MONGO_URL || 'mongodb://localhost:27017';
    const baseDbName = process.env.DB_NAME || 'fomo';
    
    simDb = await connectSimDb({
      mongoUri,
      baseDbName,
      dbSuffix: envConfig.dbSuffix,
    });
    
    // Ensure indexes
    await ensureSimIndexes(simDb);
    
    // Build config
    const config = buildSimConfig(envConfig);
    
    // Create price provider
    const priceProvider = createSimPriceProvider(simDb);
    await priceProvider.ensureIndexes();
    
    // Prefetch prices (optimization)
    console.log('[ExchangeSim] Prefetching price history...');
    for (const symbol of config.symbols.slice(0, 5)) { // First 5 symbols
      await priceProvider.prefetchRange(symbol, config.startDate, Math.min(30, config.days));
    }
    
    // Create kill switch checker
    const killSwitchKey = envConfig.killSwitchKey;
    const checkKillSwitch = async (): Promise<boolean> => {
      // Check environment variable
      if (process.env.EXCHANGE_SIM_KILL_SWITCH === 'true') {
        return true;
      }
      
      // Check database flag
      try {
        const flag = await simDb!.collection('sim_flags').findOne({ key: killSwitchKey });
        return flag?.value === true;
      } catch {
        return false;
      }
    };
    
    // Create and run simulation
    const runner = createSimRunner(
      {
        db: simDb,
        priceProvider,
        checkKillSwitch,
      },
      config
    );
    
    const report = await runner.run();
    
    // Generate reports
    const reporter = createSimReporter(simDb);
    
    // Save to database
    await reporter.saveToDb(report);
    
    // Print summary
    reporter.printSummary(report);
    
    // Export files (optional)
    const exportDir = process.env.EXCHANGE_SIM_EXPORT_DIR || '/tmp';
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    
    await reporter.exportJson(report, `${exportDir}/sim_report_${timestamp}.json`);
    await reporter.exportDailyCsv(report, `${exportDir}/sim_daily_${timestamp}.csv`);
    await reporter.exportSymbolCsv(report, `${exportDir}/sim_symbols_${timestamp}.csv`);
    
    return { success: true, report };
    
  } catch (error: any) {
    console.error('[ExchangeSim] Error:', error);
    return { success: false, error: error.message };
    
  } finally {
    // Cleanup
    resetSimNowProvider();
    await disconnectSimDb();
  }
}

/**
 * Get simulation status
 */
export async function getSimulationStatus(): Promise<{
  enabled: boolean;
  config: ReturnType<typeof loadSimConfigFromEnv>;
  lastRun?: Date;
}> {
  const config = loadSimConfigFromEnv();
  
  let lastRun: Date | undefined;
  
  if (config.enabled) {
    try {
      const mongoUri = process.env.MONGO_URL || 'mongodb://localhost:27017';
      const baseDbName = process.env.DB_NAME || 'fomo';
      
      const simDb = await connectSimDb({
        mongoUri,
        baseDbName,
        dbSuffix: config.dbSuffix,
      });
      
      const lastReport = await simDb.collection('sim_reports')
        .findOne({}, { sort: { startedAt: -1 } });
      
      if (lastReport) {
        lastRun = lastReport.startedAt;
      }
      
      await disconnectSimDb();
    } catch {
      // Ignore errors
    }
  }
  
  return { enabled: config.enabled, config, lastRun };
}

export default { runExchangeSimulation, getSimulationStatus };
