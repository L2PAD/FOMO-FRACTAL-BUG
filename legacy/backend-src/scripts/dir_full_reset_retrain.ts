/**
 * Direction Model Full Reset + Retrain Script
 * ============================================
 * 
 * Complete cycle for production-grade Direction model:
 * 1. Reset collections (samples, models, registry)
 * 2. Backfill on REAL historical data (700 days)
 * 3. Train models per horizon with ATR-adjusted labels
 * 4. Activate models
 * 
 * Usage:
 *   npx tsx src/scripts/dir_full_reset_retrain.ts
 */

import { MongoClient, Db } from 'mongodb';
import { DirBackfillService } from '../modules/exchange-ml/dir/jobs/dir_backfill.job.js';
import { DirTrainService } from '../modules/exchange-ml/dir/dir.train.service.js';
import { 
  StaticHistoricalPriceProvider, 
  getStaticHistoricalPriceProvider 
} from '../modules/exchange-sim/providers/static_historical_provider.js';
import { DirFeatureDeps } from '../modules/exchange-ml/dir/dir.feature-extractor.js';
import { Horizon } from '../modules/exchange-ml/contracts/exchange.types.js';

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

const MONGO_URL = process.env.MONGO_URL || 'mongodb://localhost:27017';
const DB_NAME = process.env.DB_NAME || 'fomo_dev';

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT'];
const HORIZONS: Horizon[] = ['1D', '7D', '30D'];

// ═══════════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════════

async function main() {
  console.log('═══════════════════════════════════════════════════════════════');
  console.log('   DIRECTION MODEL FULL RESET + RETRAIN');
  console.log('═══════════════════════════════════════════════════════════════');
  console.log();
  
  // Connect to MongoDB
  const client = new MongoClient(MONGO_URL);
  await client.connect();
  const db = client.db(DB_NAME);
  
  console.log(`Connected to MongoDB: ${DB_NAME}`);
  console.log();
  
  try {
    // ═════════════════════════════════════════════════════════════
    // STEP 1: RESET COLLECTIONS
    // ═════════════════════════════════════════════════════════════
    
    console.log('┌──────────────────────────────────────────────────────────────┐');
    console.log('│  STEP 1: RESET COLLECTIONS                                   │');
    console.log('└──────────────────────────────────────────────────────────────┘');
    
    const collections = ['exch_dir_samples', 'exch_dir_models', 'exch_dir_registry'];
    
    for (const collName of collections) {
      const count = await db.collection(collName).countDocuments();
      await db.collection(collName).deleteMany({});
      console.log(`  ✓ Cleared ${collName}: ${count} documents removed`);
    }
    
    console.log();
    
    // ═════════════════════════════════════════════════════════════
    // STEP 2: LOAD HISTORICAL DATA
    // ═════════════════════════════════════════════════════════════
    
    console.log('┌──────────────────────────────────────────────────────────────┐');
    console.log('│  STEP 2: LOAD REAL HISTORICAL DATA                           │');
    console.log('└──────────────────────────────────────────────────────────────┘');
    
    const staticProvider = getStaticHistoricalPriceProvider('/app/backend/data/historical');
    const loaded = staticProvider.loadAllAvailable();
    
    console.log(`  Loaded symbols: ${loaded.join(', ')}`);
    
    // Get date range
    const btcRange = staticProvider.getDateRange('BTCUSDT');
    console.log(`  Date range: ${btcRange?.start} → ${btcRange?.end}`);
    console.log(`  Total candles per symbol: ~${staticProvider.getCandleCount('BTCUSDT')}`);
    console.log();
    
    // ═════════════════════════════════════════════════════════════
    // STEP 3: BACKFILL SAMPLES (All symbols, 700 days)
    // ═════════════════════════════════════════════════════════════
    
    console.log('┌──────────────────────────────────────────────────────────────┐');
    console.log('│  STEP 3: BACKFILL SAMPLES (ATR-Adjusted Labels)              │');
    console.log('└──────────────────────────────────────────────────────────────┘');
    
    // Create feature deps using static provider
    const featureDeps = createFeatureDeps(staticProvider);
    const backfillService = new DirBackfillService(db, featureDeps);
    
    // Calculate date range (use available data, leave buffer for horizon resolution)
    const endDateStr = btcRange?.end || '2024-12-25';
    const endDate = new Date(endDateStr);
    const startDate = new Date(endDateStr);
    startDate.setDate(startDate.getDate() - 650); // 650 days of samples
    
    const fromTs = Math.floor(startDate.getTime() / 1000);
    const toTs = Math.floor(endDate.getTime() / 1000) - (30 * 86400); // Buffer for 30D resolution
    
    console.log(`  Backfill range: ${startDate.toISOString().split('T')[0]} → ${new Date(toTs * 1000).toISOString().split('T')[0]}`);
    console.log();
    
    let totalCreated = 0;
    
    for (const symbol of SYMBOLS) {
      if (!loaded.includes(symbol)) {
        console.log(`  ⚠️ Skipping ${symbol}: no data`);
        continue;
      }
      
      const result = await backfillService.backfill({
        symbol,
        fromTs,
        toTs,
        horizons: HORIZONS,
        onProgress: (p) => {
          if (p.processed % 300 === 0) {
            const pct = ((p.processed / p.total) * 100).toFixed(0);
            process.stdout.write(`\r  ${symbol}: ${pct}% (${p.created} created, ${p.errors} errors)    `);
          }
        },
      });
      
      console.log();
      console.log(`  ✓ ${symbol}: ${result.samples.created} samples created, ${result.samples.errors} errors`);
      totalCreated += result.samples.created;
    }
    
    console.log();
    console.log(`  TOTAL SAMPLES CREATED: ${totalCreated}`);
    console.log();
    
    // Get sample stats
    const stats = await backfillService.getStats();
    console.log('  Sample Distribution:');
    console.log(`    1D:  ${stats.byHorizon['1D']} samples`);
    console.log(`    7D:  ${stats.byHorizon['7D']} samples`);
    console.log(`    30D: ${stats.byHorizon['30D']} samples`);
    console.log(`    UP:  ${stats.byLabel.UP} | DOWN: ${stats.byLabel.DOWN} | NEUTRAL: ${stats.byLabel.NEUTRAL}`);
    console.log();
    
    // ═════════════════════════════════════════════════════════════
    // STEP 4: TRAIN MODELS PER HORIZON
    // ═════════════════════════════════════════════════════════════
    
    console.log('┌──────────────────────────────────────────────────────────────┐');
    console.log('│  STEP 4: TRAIN MODELS (Horizon-Specific Features)            │');
    console.log('└──────────────────────────────────────────────────────────────┘');
    
    const trainService = new DirTrainService(db);
    await trainService.ensureIndexes();
    
    const trainResults = [];
    
    for (const horizon of HORIZONS) {
      console.log();
      console.log(`  Training ${horizon}...`);
      
      const result = await trainService.trainForHorizon({ horizon });
      trainResults.push(result);
      
      if (result.success) {
        console.log(`    ✓ Model: ${result.model?.version}`);
        console.log(`    ✓ Train Accuracy: ${(result.trainMetrics?.trainAccuracy || 0) * 100}%`);
        console.log(`    ✓ Test Accuracy: ${(result.trainMetrics?.testAccuracy || 0) * 100}%`);
        console.log(`    ✓ Training Size: ${result.model?.trainingSize}`);
        
        // Activate model
        if (result.modelId) {
          await trainService.activateModel(horizon, result.modelId);
          console.log(`    ✓ Model ACTIVATED`);
        }
      } else {
        console.log(`    ✗ Training failed: ${result.error}`);
      }
    }
    
    console.log();
    
    // ═════════════════════════════════════════════════════════════
    // STEP 5: VERIFY REGISTRY
    // ═════════════════════════════════════════════════════════════
    
    console.log('┌──────────────────────────────────────────────────────────────┐');
    console.log('│  STEP 5: VERIFY MODEL REGISTRY                               │');
    console.log('└──────────────────────────────────────────────────────────────┘');
    
    const registry = await trainService.getRegistryState();
    
    console.log();
    for (const horizon of HORIZONS) {
      const entry = registry[horizon];
      console.log(`  ${horizon}:`);
      console.log(`    Active Model: ${entry.activeModelVersion || 'NONE'}`);
      console.log(`    Shadow Model: ${entry.shadowModelVersion || 'NONE'}`);
    }
    console.log();
    
    // ═════════════════════════════════════════════════════════════
    // SUMMARY
    // ═════════════════════════════════════════════════════════════
    
    console.log('═══════════════════════════════════════════════════════════════');
    console.log('   SUMMARY');
    console.log('═══════════════════════════════════════════════════════════════');
    console.log();
    console.log('  ✅ Collections reset');
    console.log(`  ✅ ${totalCreated} samples created with ATR-adjusted labels`);
    console.log('  ✅ Models trained per horizon with horizon-specific features');
    console.log('  ✅ Models activated');
    console.log();
    console.log('  TEST ACCURACY:');
    for (const r of trainResults) {
      if (r.success) {
        console.log(`    ${r.horizon}: ${((r.trainMetrics?.testAccuracy || 0) * 100).toFixed(1)}%`);
      }
    }
    console.log();
    console.log('  NEXT: Run 365-day lifecycle simulation');
    console.log('    npm run sim:exchange -- --mode lifecycle --days 365');
    console.log();
    
  } finally {
    await client.close();
  }
}

// ═══════════════════════════════════════════════════════════════
// HELPER: Create DirFeatureDeps from StaticHistoricalPriceProvider
// ═══════════════════════════════════════════════════════════════

function createFeatureDeps(staticProvider: StaticHistoricalPriceProvider): DirFeatureDeps {
  return {
    price: {
      getSeries: async (params: { symbol: string; from: number; to: number; tf: string }) => {
        const { symbol, from, to } = params;
        const fromDate = new Date(from * 1000);
        const toDate = new Date(to * 1000);
        
        const candles = staticProvider.getRange(symbol, fromDate, toDate);
        
        return candles.map(c => ({
          t: Math.floor(c.timestamp / 1000),
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
          volume: c.volume,
        }));
      },
    },
    getFlowBias: async (_symbol: string, _t: number) => {
      // No flow data in static provider, return neutral
      return 0;
    },
  };
}

// ═══════════════════════════════════════════════════════════════
// RUN
// ═══════════════════════════════════════════════════════════════

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
