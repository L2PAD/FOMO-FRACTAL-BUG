/**
 * Exchange Simulation CLI Script
 * ==============================
 * 
 * Run: npm run sim:exchange
 * 
 * CLI arguments (override .env):
 *   --mode baseline|retrain_only|lifecycle
 *   --days 90|365|etc
 * 
 * Environment variables:
 *   EXCHANGE_SIM_ENABLED=true     # Enable simulation
 *   EXCHANGE_SIM_MODE=baseline    # baseline, retrain_only, lifecycle
 *   EXCHANGE_SIM_SYMBOLS=BTC,ETH  # Comma-separated symbols
 *   EXCHANGE_SIM_DAYS=365         # Days to simulate
 *   EXCHANGE_SIM_START=2024-01-01 # Start date (optional)
 * 
 * Diagnostic modes:
 *   baseline     - only inference + outcomes (pure model power)
 *   retrain_only - + retrain (check if retrain breaks things)
 *   lifecycle    - full pipeline (retrain + shadow + promo + rollback + bias)
 */

import 'dotenv/config';
import { runExchangeSimulation } from '../modules/exchange-sim/index.js';

// Parse CLI arguments
function parseArg(name: string): string | null {
  const idx = process.argv.indexOf(`--${name}`);
  if (idx === -1 || idx + 1 >= process.argv.length) return null;
  return process.argv[idx + 1];
}

async function main() {
  console.log('════════════════════════════════════════════════════════════');
  console.log('   EXCHANGE ML DIAGNOSTIC SIMULATION');
  console.log('════════════════════════════════════════════════════════════');
  console.log('');
  
  // CLI overrides
  const modeArg = parseArg('mode');
  const daysArg = parseArg('days');
  
  if (modeArg) {
    process.env.EXCHANGE_SIM_MODE = modeArg;
    console.log(`[CLI] Mode override: ${modeArg}`);
  }
  if (daysArg) {
    process.env.EXCHANGE_SIM_DAYS = daysArg;
    console.log(`[CLI] Days override: ${daysArg}`);
  }
  
  if (process.env.EXCHANGE_SIM_ENABLED !== 'true') {
    console.log('Simulation is disabled.');
    console.log('Set EXCHANGE_SIM_ENABLED=true in .env to enable.');
    process.exit(0);
  }
  
  const result = await runExchangeSimulation();
  
  if (result.success) {
    console.log('');
    console.log('✅ Simulation completed successfully!');
    
    if (result.report) {
      // Show diagnostic summary
      const r = result.report;
      console.log('');
      console.log('╔══════════════════════════════════════════════════════════╗');
      console.log(`║  MODE: ${(r.diagnosticMode || 'unknown').toUpperCase().padEnd(50)}║`);
      if (r.gates) {
        console.log(`║  Gates: retrain=${r.gates.retrain} shadow=${r.gates.shadow} promo=${r.gates.promotion} rollback=${r.gates.rollback} bias=${r.gates.bias}`.padEnd(62) + '║');
      }
      console.log('╠══════════════════════════════════════════════════════════╣');
      console.log(`║  Accuracy 1D:  ${(r.metrics.accuracy['1D'].rate * 100).toFixed(1)}%`.padEnd(62) + '║');
      console.log(`║  Accuracy 7D:  ${(r.metrics.accuracy['7D'].rate * 100).toFixed(1)}%`.padEnd(62) + '║');
      console.log(`║  Accuracy 30D: ${(r.metrics.accuracy['30D'].rate * 100).toFixed(1)}%`.padEnd(62) + '║');
      console.log('╠══════════════════════════════════════════════════════════╣');
      console.log(`║  Retrains:   ${r.metrics.lifecycle.retrainCount}`.padEnd(62) + '║');
      console.log(`║  Promotions: ${r.metrics.lifecycle.promotionCount}`.padEnd(62) + '║');
      console.log(`║  Rollbacks:  ${r.metrics.lifecycle.rollbackCount}`.padEnd(62) + '║');
      console.log('╚══════════════════════════════════════════════════════════╝');
      
      const issues = r.issues;
      if (issues.length > 0) {
        console.log(`⚠️  ${issues.length} issue(s) detected. Review report for details.`);
      } else {
        console.log('✅ No critical issues detected.');
      }
    }
    
    process.exit(0);
  } else {
    console.error('');
    console.error('❌ Simulation failed:', result.error);
    process.exit(1);
  }
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
