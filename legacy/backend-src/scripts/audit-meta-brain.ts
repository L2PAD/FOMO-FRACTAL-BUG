/**
 * META BRAIN V2 — COMPREHENSIVE AUDIT
 * ====================================
 * 
 * Tests all 4 signal providers and their integration into Meta Brain.
 * Checks data accumulation, API health, and signal aggregation.
 */

import { MongoClient } from 'mongodb';
import { getProviders, getActiveProviders } from '../modules/meta-brain-v2/registry/providers.registry.js';

const API_BASE = 'http://127.0.0.1:8003';

interface TestResult {
  module: string;
  status: 'PASS' | 'FAIL' | 'WARN';
  message: string;
  data?: any;
}

const results: TestResult[] = [];

async function testModule(name: string, apiUrl: string): Promise<TestResult> {
  try {
    const resp = await fetch(apiUrl, { signal: AbortSignal.timeout(5000) });
    const data = await resp.json();
    
    if (!resp.ok || !data.ok) {
      return { module: name, status: 'FAIL', message: 'API returned not-ok', data };
    }
    
    return { module: name, status: 'PASS', message: 'API healthy', data };
  } catch (err: any) {
    return { module: name, status: 'FAIL', message: `Error: ${err.message}` };
  }
}

async function runAudit() {
  console.log('🔍 META BRAIN V2 — COMPREHENSIVE AUDIT\n');
  console.log('=' .repeat(70));
  
  // ============================================
  // PHASE 1: PROVIDER REGISTRY
  // ============================================
  console.log('\n📋 PHASE 1: Provider Registry\n');
  
  const allProviders = getProviders();
  console.log(`Total Registered Providers: ${allProviders.length}`);
  allProviders.forEach(p => {
    console.log(`  ✓ ${p.key} (${p.version})`);
  });
  
  const activeProviders = await getActiveProviders();
  console.log(`\nActive Providers (Module Controller): ${activeProviders.length}`);
  activeProviders.forEach(p => {
    console.log(`  ✓ ${p.key}`);
  });
  
  if (activeProviders.length < allProviders.length) {
    console.log(`\n⚠️  WARNING: ${allProviders.length - activeProviders.length} provider(s) disabled by Module Controller`);
  }
  
  // ============================================
  // PHASE 2: API ENDPOINTS TEST
  // ============================================
  console.log('\n' + '='.repeat(70));
  console.log('\n📋 PHASE 2: API Endpoints Test\n');
  
  // Fractal API
  results.push(await testModule(
    'Fractal',
    `${API_BASE}/api/fractal/v2.1/focus-pack?symbol=BTC&focus=7d&mode=crossAsset`
  ));
  
  // Exchange API
  results.push(await testModule(
    'Exchange',
    `${API_BASE}/api/market/exchange/snapshots/active?symbol=BTCUSDT`
  ));
  
  // Sentiment API (also used by OnChain)
  results.push(await testModule(
    'Sentiment',
    `${API_BASE}/api/market/sentiment/intelligence-v1?asset=BTC&window=7D`
  ));
  
  // OnChain uses same API as Sentiment
  results.push({
    module: 'OnChain',
    status: results.find(r => r.module === 'Sentiment')?.status || 'WARN',
    message: 'Uses Sentiment Intelligence API (same endpoint)',
  });
  
  // Print results
  results.forEach(r => {
    const icon = r.status === 'PASS' ? '✅' : r.status === 'FAIL' ? '❌' : '⚠️ ';
    console.log(`${icon} ${r.module}: ${r.message}`);
  });
  
  // ============================================
  // PHASE 3: META BRAIN AGGREGATION API
  // ============================================
  console.log('\n' + '='.repeat(70));
  console.log('\n📋 PHASE 3: Meta Brain Aggregation API\n');
  
  try {
    const aggUrl = `${API_BASE}/api/meta-brain-v2/aggregate?asset=BTC&horizonDays=7`;
    const aggResp = await fetch(aggUrl, { signal: AbortSignal.timeout(10000) });
    const aggData = await aggResp.json();
    
    if (!aggData.ok) {
      console.log('❌ Meta Brain Aggregation API: FAILED');
      console.log('   Error:', aggData.error || 'Unknown');
    } else {
      console.log('✅ Meta Brain Aggregation API: OPERATIONAL');
      console.log(`   Raw Score: ${aggData.data.rawScore?.toFixed(3)}`);
      console.log(`   Verdict: ${aggData.data.rawVerdict}`);
      console.log(`   Confidence: ${(aggData.data.rawConfidence * 100).toFixed(1)}%`);
      console.log(`   Meta Confidence: ${(aggData.data.metaConfidence.final * 100).toFixed(1)}%`);
      console.log(`   Regime: ${aggData.data.regime}`);
      console.log(`   Active Signals: ${aggData.data.signals?.length || 0}/${aggData.data.coverage?.total || 0}`);
      
      if (aggData.data.signals && aggData.data.signals.length > 0) {
        console.log('\n   📊 Signal Breakdown:');
        aggData.data.signals.forEach((sig: any) => {
          console.log(`      • ${sig.module}: weight=${(sig.weight * 100).toFixed(1)}%, score=${sig.normalizedScore?.toFixed(3)}`);
        });
      }
      
      if (aggData.data.gatedModules && aggData.data.gatedModules.length > 0) {
        console.log('\n   ⚠️  Gated Modules (excluded from aggregation):');
        aggData.data.gatedModules.forEach((g: any) => {
          console.log(`      • ${g.module}: ${g.reason}`);
        });
      }
    }
  } catch (err: any) {
    console.log('❌ Meta Brain Aggregation API: ERROR');
    console.log('   Message:', err.message);
  }
  
  // ============================================
  // PHASE 4: DATABASE SNAPSHOTS
  // ============================================
  console.log('\n' + '='.repeat(70));
  console.log('\n📋 PHASE 4: Database Data Accumulation\n');
  
  const client = new MongoClient(process.env.MONGO_URL || 'mongodb://localhost:27017');
  await client.connect();
  const db = client.db('intelligence_engine');
  
  // Check key collections
  const collections = [
    { name: 'fractal_prediction_snapshots', module: 'Fractal' },
    { name: 'exchange_prediction_snapshots', module: 'Exchange' },
    { name: 'sentiment_aggregates', module: 'Sentiment' },
    { name: 'onchain_lite_snapshots', module: 'OnChain Lite' },
    { name: 'onchain_v2_snapshots', module: 'OnChain V2' },
  ];
  
  for (const col of collections) {
    const count = await db.collection(col.name).countDocuments();
    const latest = await db.collection(col.name).find({}).sort({ timestamp: -1, createdAt: -1 }).limit(1).toArray();
    
    const icon = count > 0 ? '✅' : '❌';
    console.log(`${icon} ${col.module} (${col.name})`);
    console.log(`   Documents: ${count.toLocaleString()}`);
    
    if (latest.length > 0) {
      const ts = latest[0].timestamp || latest[0].createdAt || latest[0].asOf;
      if (ts) {
        const age = Date.now() - new Date(ts).getTime();
        const ageHours = Math.floor(age / 3600000);
        console.log(`   Latest: ${ageHours}h ago (${new Date(ts).toISOString()})`);
      }
    } else {
      console.log('   ⚠️  No data found');
    }
  }
  
  await client.close();
  
  // ============================================
  // PHASE 5: SUMMARY & RECOMMENDATIONS
  // ============================================
  console.log('\n' + '='.repeat(70));
  console.log('\n📊 AUDIT SUMMARY\n');
  
  const passCount = results.filter(r => r.status === 'PASS').length;
  const failCount = results.filter(r => r.status === 'FAIL').length;
  const warnCount = results.filter(r => r.status === 'WARN').length;
  
  console.log(`✅ Passed: ${passCount}/${results.length}`);
  console.log(`❌ Failed: ${failCount}/${results.length}`);
  console.log(`⚠️  Warnings: ${warnCount}/${results.length}`);
  
  console.log('\n🎯 KEY FINDINGS:\n');
  
  if (failCount === 0) {
    console.log('✅ All modules are operational and integrated into Meta Brain');
  } else {
    console.log('❌ Some modules are not working. Meta Brain may have incomplete signals.');
  }
  
  console.log('\n📌 RECOMMENDATIONS:\n');
  
  if (failCount > 0) {
    const failedModules = results.filter(r => r.status === 'FAIL').map(r => r.module);
    console.log(`1. Fix failing modules: ${failedModules.join(', ')}`);
    console.log('2. Check service logs for errors');
    console.log('3. Verify data accumulation for failed modules');
  } else {
    console.log('1. ✅ All modules healthy');
    console.log('2. Monitor data accumulation rates');
    console.log('3. Verify signal weights in production');
  }
  
  console.log('\n' + '='.repeat(70));
  console.log('\n✅ AUDIT COMPLETE\n');
}

runAudit().catch(err => {
  console.error('\n❌ AUDIT FAILED:', err.message);
  console.error(err.stack);
  process.exit(1);
});
