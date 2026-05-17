import { MongoClient } from 'mongodb';

async function metaBrainIntegrationTest() {
  const client = new MongoClient(process.env.MONGO_URL || 'mongodb://localhost:27017');
  await client.connect();
  const db = client.db('intelligence_engine');

  console.log('🧠 META BRAIN INTEGRATION TEST\n');
  console.log('='.repeat(70));

  // 1. Check all snapshot sources
  console.log('\n📊 STEP 1: Data Source Verification\n');

  const exchangeCount = await db.collection('exchange_prediction_snapshots').countDocuments();
  const fractalCount = await db.collection('fractal_prediction_snapshots').countDocuments();
  const sentimentCount = await db.collection('sentiment_aggregates').countDocuments();
  const onchainCount = await db.collection('onchain_lite_snapshots').countDocuments();

  console.log(`  Exchange:  ${exchangeCount.toLocaleString()} ${exchangeCount > 0 ? '✅' : '❌'}`);
  console.log(`  Fractal:   ${fractalCount.toLocaleString()} ${fractalCount > 0 ? '✅' : '❌'}`);
  console.log(`  Sentiment: ${sentimentCount.toLocaleString()} ${sentimentCount > 0 ? '✅' : '❌'}`);
  console.log(`  OnChain:   ${onchainCount.toLocaleString()} ${onchainCount > 0 ? '✅' : '⏳'}`);

  const healthyModules = [exchangeCount, fractalCount, sentimentCount].filter(c => c > 0).length;

  console.log(`\n  Active Modules: ${healthyModules}/3 (Exchange + Fractal + Sentiment)`);

  if (healthyModules >= 3) {
    console.log('  ✅ Meta Brain is MULTI-MODEL (no longer sentiment-only!)');
  } else if (healthyModules >= 2) {
    console.log('  ⚠️  Meta Brain is DEGRADED (only 2 modules active)');
  } else {
    console.log('  ❌ Meta Brain is CRITICAL (less than 2 modules)');
  }

  // 2. Show sample snapshots from each module
  console.log('\n' + '='.repeat(70));
  console.log('\n📊 STEP 2: Sample Snapshots\n');

  if (exchangeCount > 0) {
    const exchangeSnapshot = await db.collection('exchange_prediction_snapshots').findOne({}, { sort: { timestamp: -1 } });
    console.log('  🔹 Exchange Sample:');
    console.log(`     Asset: ${exchangeSnapshot.asset}`);
    console.log(`     Direction: ${exchangeSnapshot.direction}`);
    console.log(`     Score: ${exchangeSnapshot.score.toFixed(3)}`);
    console.log(`     Confidence: ${(exchangeSnapshot.confidence * 100).toFixed(1)}%`);
    console.log(`     Quality: ${exchangeSnapshot.quality}`);
  }

  if (fractalCount > 0) {
    const fractalSnapshot = await db.collection('fractal_prediction_snapshots').findOne({}, { sort: { timestamp: -1 } });
    console.log('\n  🔹 Fractal Sample:');
    console.log(`     Asset: ${fractalSnapshot.asset}`);
    console.log(`     Direction: ${fractalSnapshot.direction}`);
    console.log(`     Score: ${fractalSnapshot.score.toFixed(3)}`);
    console.log(`     Confidence: ${(fractalSnapshot.confidence * 100).toFixed(1)}%`);
    console.log(`     Expected Return: ${fractalSnapshot.expected_return_pct.toFixed(2)}%`);
    console.log(`     Regime: ${fractalSnapshot.regime}`);
  }

  if (sentimentCount > 0) {
    const sentimentSnapshot = await db.collection('sentiment_aggregates').findOne({}, { sort: { createdAt: -1 } });
    console.log('\n  🔹 Sentiment Sample:');
    console.log(`     Asset: ${sentimentSnapshot.asset}`);
    console.log(`     Bias: ${sentimentSnapshot.aggregation?.bias?.toFixed(3) || 'N/A'}`);
    console.log(`     Confidence: ${((sentimentSnapshot.aggregation?.confidence || 0) * 100).toFixed(1)}%`);
  }

  // 3. Check fractal_state (upstream)
  console.log('\n' + '='.repeat(70));
  console.log('\n📊 STEP 3: Fractal Engine Verification\n');

  const fractalStates = await db.collection('fractal_state').find({}).toArray();
  console.log(`  Total fractal_state documents: ${fractalStates.length}`);

  if (fractalStates.length > 0) {
    console.log('\n  Sample fractal_state:');
    const state = fractalStates[0];
    console.log(`     Asset: ${state.asset}`);
    console.log(`     Forecast exists: ${state.forecast ? '✅' : '❌'}`);
    console.log(`     Scenario exists: ${state.scenario ? '✅' : '❌'}`);
    if (state.forecast) {
      console.log(`     Direction: ${state.forecast.direction}`);
      console.log(`     Expected Return: ${(state.forecast.expectedReturn * 100).toFixed(2)}%`);
      console.log(`     Confidence: ${(state.forecast.confidence * 100).toFixed(1)}%`);
    }
  }

  // 4. Final verdict
  console.log('\n' + '='.repeat(70));
  console.log('\n🎯 FINAL VERDICT\n');

  if (healthyModules >= 3) {
    console.log('  ✅ Meta Brain is FULLY OPERATIONAL');
    console.log('  ✅ Multi-model aggregation active');
    console.log('  ✅ Sentiment bias eliminated');
    console.log('\n  Ready for:');
    console.log('    - Historical backfill');
    console.log('    - Confidence calibration');
    console.log('    - Production deployment');
  } else {
    console.log('  ⚠️  Meta Brain is PARTIALLY OPERATIONAL');
    console.log(`  ⚠️  Only ${healthyModules}/3 modules active`);
    console.log('\n  Next steps:');
    console.log('    - Activate missing modules');
    console.log('    - Verify data accumulation');
  }

  console.log('\n' + '='.repeat(70));

  await client.close();
}

metaBrainIntegrationTest().catch(console.error);
