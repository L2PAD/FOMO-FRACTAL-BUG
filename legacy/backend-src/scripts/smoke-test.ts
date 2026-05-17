/**
 * SMOKE TEST — Data Accumulation Monitor
 * 
 * Проверяет ЖИВЫ ЛИ data pipelines после перезапуска
 */
import { MongoClient } from 'mongodb';
import { writeFileSync } from 'fs';

const MONGO_URL = process.env.MONGO_URL || 'mongodb://localhost:27017';
const DB_NAME = 'intelligence_engine';

interface ModuleSnapshot {
  module: string;
  collections: {
    name: string;
    count: number;
    lastCreatedAt: string | null;
    lastUpdatedAt: string | null;
    last3Docs: any[];
  }[];
  timestamp: string;
  timestampMs: number;
}

async function takeSnapshot(): Promise<ModuleSnapshot[]> {
  const client = new MongoClient(MONGO_URL);
  await client.connect();
  const db = client.db(DB_NAME);

  const snapshots: ModuleSnapshot[] = [];
  const now = new Date().toISOString();
  const nowMs = Date.now();

  // 1. EXCHANGE MODULE
  const exchangeCollections = [
    'exchange_observations',
    'exchange_funding_context',
    'exchange_forecasts',
    'exchange_forecast_runs'
  ];

  const exchangeData = await Promise.all(
    exchangeCollections.map(async (coll) => {
      const count = await db.collection(coll).countDocuments();
      const last3 = await db.collection(coll).find({}).sort({ _id: -1 }).limit(3).toArray();
      
      let lastCreatedAt = null;
      let lastUpdatedAt = null;

      if (last3.length > 0) {
        const doc = last3[0];
        
        // Try different timestamp fields
        const createdField = doc.createdAt || doc.timestamp;
        const updatedField = doc.updatedAt || doc.timestamp;
        
        if (createdField) {
          if (createdField instanceof Date) {
            lastCreatedAt = createdField.toISOString();
          } else if (typeof createdField === 'number') {
            lastCreatedAt = new Date(createdField).toISOString();
          } else {
            // ObjectId timestamp
            lastCreatedAt = new Date(parseInt(createdField.toString().substring(0,8), 16) * 1000).toISOString();
          }
        }
        
        if (updatedField) {
          if (updatedField instanceof Date) {
            lastUpdatedAt = updatedField.toISOString();
          } else if (typeof updatedField === 'number') {
            lastUpdatedAt = new Date(updatedField).toISOString();
          } else {
            // ObjectId timestamp
            lastUpdatedAt = new Date(parseInt(updatedField.toString().substring(0,8), 16) * 1000).toISOString();
          }
        }
      }

      return {
        name: coll,
        count,
        lastCreatedAt,
        lastUpdatedAt,
        last3Docs: last3.map(d => ({
          _id: d._id.toString(),
          symbol: d.symbol,
          asset: d.asset,
          timestamp: d.timestamp,
          createdAt: d.createdAt
        }))
      };
    })
  );

  snapshots.push({
    module: 'EXCHANGE',
    collections: exchangeData,
    timestamp: now,
    timestampMs: nowMs
  });

  // 2. SENTIMENT MODULE
  const sentimentCollections = [
    'sentiment_aggregates',
    'sentiment_events',
    'canonical_events'
  ];

  const sentimentData = await Promise.all(
    sentimentCollections.map(async (coll) => {
      const count = await db.collection(coll).countDocuments();
      const last3 = await db.collection(coll).find({}).sort({ _id: -1 }).limit(3).toArray();
      
      let lastCreatedAt = null;
      let lastUpdatedAt = null;

      if (last3.length > 0) {
        const doc = last3[0];
        
        // Try different timestamp fields
        const createdField = doc.createdAt || doc.timestamp;
        const updatedField = doc.updatedAt || doc.timestamp;
        
        if (createdField) {
          if (createdField instanceof Date) {
            lastCreatedAt = createdField.toISOString();
          } else if (typeof createdField === 'number') {
            lastCreatedAt = new Date(createdField).toISOString();
          } else {
            // ObjectId timestamp
            lastCreatedAt = new Date(parseInt(createdField.toString().substring(0,8), 16) * 1000).toISOString();
          }
        }
        
        if (updatedField) {
          if (updatedField instanceof Date) {
            lastUpdatedAt = updatedField.toISOString();
          } else if (typeof updatedField === 'number') {
            lastUpdatedAt = new Date(updatedField).toISOString();
          } else {
            // ObjectId timestamp
            lastUpdatedAt = new Date(parseInt(updatedField.toString().substring(0,8), 16) * 1000).toISOString();
          }
        }
      }

      return {
        name: coll,
        count,
        lastCreatedAt,
        lastUpdatedAt,
        last3Docs: last3.slice(0, 1).map(d => ({ _id: d._id.toString() }))
      };
    })
  );

  snapshots.push({
    module: 'SENTIMENT',
    collections: sentimentData,
    timestamp: now,
    timestampMs: nowMs
  });

  // 3. PREDICTION MODULE
  const predictionCollections = [
    'prediction_snapshots',
    'prediction_markets',
    'meta_brain_forecasts',
    'signal_snapshots'
  ];

  const predictionData = await Promise.all(
    predictionCollections.map(async (coll) => {
      const count = await db.collection(coll).countDocuments();
      const last3 = await db.collection(coll).find({}).sort({ _id: -1 }).limit(3).toArray();
      
      let lastCreatedAt = null;
      let lastUpdatedAt = null;

      if (last3.length > 0) {
        const doc = last3[0];
        
        // Try different timestamp fields
        const createdField = doc.createdAt || doc.timestamp;
        const updatedField = doc.updatedAt || doc.timestamp;
        
        if (createdField) {
          if (createdField instanceof Date) {
            lastCreatedAt = createdField.toISOString();
          } else if (typeof createdField === 'number') {
            lastCreatedAt = new Date(createdField).toISOString();
          } else {
            // ObjectId timestamp
            lastCreatedAt = new Date(parseInt(createdField.toString().substring(0,8), 16) * 1000).toISOString();
          }
        }
        
        if (updatedField) {
          if (updatedField instanceof Date) {
            lastUpdatedAt = updatedField.toISOString();
          } else if (typeof updatedField === 'number') {
            lastUpdatedAt = new Date(updatedField).toISOString();
          } else {
            // ObjectId timestamp
            lastUpdatedAt = new Date(parseInt(updatedField.toString().substring(0,8), 16) * 1000).toISOString();
          }
        }
      }

      return {
        name: coll,
        count,
        lastCreatedAt,
        lastUpdatedAt,
        last3Docs: last3.slice(0, 1).map(d => ({ _id: d._id.toString() }))
      };
    })
  );

  snapshots.push({
    module: 'PREDICTION',
    collections: predictionData,
    timestamp: now,
    timestampMs: nowMs
  });

  // 4. FRACTALS MODULE
  const fractalsCollections = [
    'fractal_canonical_ohlcv',
    'btc_fractal_forecasts',
    'fractal_projection_snapshots'
  ];

  const fractalsData = await Promise.all(
    fractalsCollections.map(async (coll) => {
      const count = await db.collection(coll).countDocuments();
      const last3 = await db.collection(coll).find({}).sort({ _id: -1 }).limit(3).toArray();
      
      let lastCreatedAt = null;
      let lastUpdatedAt = null;

      if (last3.length > 0) {
        const doc = last3[0];
        
        // Try different timestamp fields
        const createdField = doc.createdAt || doc.timestamp;
        const updatedField = doc.updatedAt || doc.timestamp;
        
        if (createdField) {
          if (createdField instanceof Date) {
            lastCreatedAt = createdField.toISOString();
          } else if (typeof createdField === 'number') {
            lastCreatedAt = new Date(createdField).toISOString();
          } else {
            // ObjectId timestamp
            lastCreatedAt = new Date(parseInt(createdField.toString().substring(0,8), 16) * 1000).toISOString();
          }
        }
        
        if (updatedField) {
          if (updatedField instanceof Date) {
            lastUpdatedAt = updatedField.toISOString();
          } else if (typeof updatedField === 'number') {
            lastUpdatedAt = new Date(updatedField).toISOString();
          } else {
            // ObjectId timestamp
            lastUpdatedAt = new Date(parseInt(updatedField.toString().substring(0,8), 16) * 1000).toISOString();
          }
        }
      }

      return {
        name: coll,
        count,
        lastCreatedAt,
        lastUpdatedAt,
        last3Docs: last3.slice(0, 1).map(d => ({ _id: d._id.toString() }))
      };
    })
  );

  snapshots.push({
    module: 'FRACTALS',
    collections: fractalsData,
    timestamp: now,
    timestampMs: nowMs
  });

  // 5. ON-CHAIN MODULE
  const onchainCollections = [
    'onchain_v2_snapshots',
    'onchain_v2_observations'
  ];

  const onchainData = await Promise.all(
    onchainCollections.map(async (coll) => {
      const count = await db.collection(coll).countDocuments();
      const last3 = await db.collection(coll).find({}).sort({ _id: -1 }).limit(3).toArray();
      
      let lastCreatedAt = null;
      let lastUpdatedAt = null;

      if (last3.length > 0) {
        const doc = last3[0];
        
        // Try different timestamp fields
        const createdField = doc.createdAt || doc.timestamp;
        const updatedField = doc.updatedAt || doc.timestamp;
        
        if (createdField) {
          if (createdField instanceof Date) {
            lastCreatedAt = createdField.toISOString();
          } else if (typeof createdField === 'number') {
            lastCreatedAt = new Date(createdField).toISOString();
          } else {
            // ObjectId timestamp
            lastCreatedAt = new Date(parseInt(createdField.toString().substring(0,8), 16) * 1000).toISOString();
          }
        }
        
        if (updatedField) {
          if (updatedField instanceof Date) {
            lastUpdatedAt = updatedField.toISOString();
          } else if (typeof updatedField === 'number') {
            lastUpdatedAt = new Date(updatedField).toISOString();
          } else {
            // ObjectId timestamp
            lastUpdatedAt = new Date(parseInt(updatedField.toString().substring(0,8), 16) * 1000).toISOString();
          }
        }
      }

      return {
        name: coll,
        count,
        lastCreatedAt,
        lastUpdatedAt,
        last3Docs: []
      };
    })
  );

  snapshots.push({
    module: 'ON-CHAIN',
    collections: onchainData,
    timestamp: now,
    timestampMs: nowMs
  });

  await client.close();
  return snapshots;
}

function printSnapshot(snapshots: ModuleSnapshot[]) {
  console.log('\n═══════════════════════════════════════════════════════════');
  console.log('          📸 DATA ACCUMULATION SNAPSHOT');
  console.log(`          Timestamp: ${snapshots[0].timestamp}`);
  console.log('═══════════════════════════════════════════════════════════\n');

  for (const snap of snapshots) {
    console.log(`\n🔥 ${snap.module}`);
    console.log('─'.repeat(65));

    for (const coll of snap.collections) {
      const status = coll.count > 0 ? '✅' : '⚠️ ';
      console.log(`${status} ${coll.name.padEnd(35)} ${String(coll.count).padStart(6)} docs`);
      
      if (coll.lastCreatedAt) {
        console.log(`   └─ Last created: ${coll.lastCreatedAt}`);
      }
      if (coll.lastUpdatedAt && coll.lastUpdatedAt !== coll.lastCreatedAt) {
        console.log(`   └─ Last updated: ${coll.lastUpdatedAt}`);
      }
    }
  }
}

function compareSnapshots(t0: ModuleSnapshot[], t1: ModuleSnapshot[]) {
  console.log('\n═══════════════════════════════════════════════════════════');
  console.log('          🔍 T0 → T1 COMPARISON');
  console.log(`          Duration: ${Math.round((t1[0].timestampMs - t0[0].timestampMs) / 60000)} minutes`);
  console.log('═══════════════════════════════════════════════════════════\n');

  for (let i = 0; i < t0.length; i++) {
    const m0 = t0[i];
    const m1 = t1[i];

    console.log(`\n🔥 ${m0.module}`);
    console.log('─'.repeat(65));

    for (let j = 0; j < m0.collections.length; j++) {
      const c0 = m0.collections[j];
      const c1 = m1.collections[j];

      const growth = c1.count - c0.count;
      const growthPct = c0.count > 0 ? ((growth / c0.count) * 100).toFixed(1) : 'N/A';

      const timestampChanged = c0.lastCreatedAt !== c1.lastCreatedAt || c0.lastUpdatedAt !== c1.lastUpdatedAt;

      let status = '';
      if (growth > 0) {
        status = '✅ HEALTHY';
      } else if (growth === 0 && timestampChanged) {
        status = '⚠️  DEGRADED';
      } else if (growth === 0 && !timestampChanged && c0.count > 0) {
        status = '❌ STALE';
      } else if (c0.count === 0 && c1.count === 0) {
        status = '⚪ EMPTY';
      } else {
        status = '❓ UNKNOWN';
      }

      console.log(`${status} ${c0.name.padEnd(35)}`);
      console.log(`   T0: ${String(c0.count).padStart(6)} → T1: ${String(c1.count).padStart(6)} | Δ${growth >= 0 ? '+' : ''}${growth} (${growthPct}%)`);
      
      if (timestampChanged) {
        console.log(`   📅 Timestamp updated`);
      }
    }
  }

  console.log('\n═══════════════════════════════════════════════════════════');
  console.log('                    SUMMARY');
  console.log('═══════════════════════════════════════════════════════════\n');

  const totalGrowth = t0.flatMap(m => m.collections).reduce((sum, c, i) => {
    const c1 = t1.flatMap(m => m.collections)[i];
    return sum + (c1.count - c.count);
  }, 0);

  console.log(`Total new documents: ${totalGrowth >= 0 ? '+' : ''}${totalGrowth}`);

  // Module-wise summary
  for (let i = 0; i < t0.length; i++) {
    const m0 = t0[i];
    const m1 = t1[i];
    
    const moduleGrowth = m0.collections.reduce((sum, c, j) => {
      return sum + (m1.collections[j].count - c.count);
    }, 0);

    const allStale = m0.collections.every((c, j) => {
      const c1 = m1.collections[j];
      return c.count === c1.count && c.lastCreatedAt === c1.lastCreatedAt;
    });

    const moduleStatus = moduleGrowth > 0 ? '✅ HEALTHY' 
      : (allStale && m0.collections.some(c => c.count > 0)) ? '❌ DEAD'
      : '⚠️  DEGRADED';

    console.log(`${moduleStatus} ${m0.module.padEnd(15)} Δ${moduleGrowth >= 0 ? '+' : ''}${moduleGrowth} docs`);
  }
}

async function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  if (command === 'snapshot' || !command) {
    // Take T0 snapshot
    console.log('📸 Taking snapshot...\n');
    const t0 = await takeSnapshot();
    printSnapshot(t0);
    
    // Save to file
    writeFileSync('/tmp/smoke_test_t0.json', JSON.stringify(t0, null, 2));
    console.log('\n✅ Snapshot saved to /tmp/smoke_test_t0.json');
    console.log('\n⏳ Wait 30-60 minutes, then run:');
    console.log('   npx tsx src/scripts/smoke-test.ts compare\n');
  } else if (command === 'compare') {
    // Load T0 and take T1
    const { readFileSync } = await import('fs');
    const t0 = JSON.parse(readFileSync('/tmp/smoke_test_t0.json', 'utf8'));
    
    console.log('📸 Taking T1 snapshot...\n');
    const t1 = await takeSnapshot();
    
    // Compare
    compareSnapshots(t0, t1);
    
    // Save T1
    writeFileSync('/tmp/smoke_test_t1.json', JSON.stringify(t1, null, 2));
    console.log('\n✅ T1 snapshot saved to /tmp/smoke_test_t1.json\n');
  } else {
    console.log('Usage:');
    console.log('  npx tsx src/scripts/smoke-test.ts snapshot  # Take T0');
    console.log('  npx tsx src/scripts/smoke-test.ts compare   # Take T1 and compare');
  }
}

main().catch(console.error);
