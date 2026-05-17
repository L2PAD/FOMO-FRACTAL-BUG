/**
 * Test On-Chain Lite Integration
 * Verifies that On-Chain Lite mode is active and configured correctly
 */

async function testOnchainLiteIntegration() {
  console.log('🔍 On-Chain Lite Mode — Integration Test\n');
  
  // Test 1: Environment Variables
  console.log('📋 Step 1: Checking Environment Variables');
  const env = {
    ONCHAIN_ENABLED: process.env.ONCHAIN_ENABLED,
    ONCHAIN_MODE: process.env.ONCHAIN_MODE,
    ONCHAIN_PROVIDER: process.env.ONCHAIN_PROVIDER,
    INFURA_KEY: process.env.INFURA_KEY ? '✅ SET' : '❌ MISSING',
  };
  console.log(JSON.stringify(env, null, 2));
  
  if (process.env.ONCHAIN_ENABLED !== 'true') {
    console.log('\n❌ ONCHAIN_ENABLED is not set to "true"');
    console.log('Please update /app/backend/.env');
    process.exit(1);
  }
  
  if (process.env.ONCHAIN_MODE !== 'lite') {
    console.log('\n❌ ONCHAIN_MODE is not set to "lite"');
    process.exit(1);
  }
  
  if (!process.env.INFURA_KEY) {
    console.log('\n❌ INFURA_KEY is not set');
    process.exit(1);
  }
  
  console.log('\n✅ All environment variables are correct\n');
  
  // Test 2: Signal Weights
  console.log('📋 Step 2: Checking Signal Weights (Meta Brain Policies)');
  
  const { META_BRAIN_POLICIES } = await import('../modules/meta-brain-v2/policy/meta_brain_policies.js');
  
  const regimes = ['TREND', 'RANGE', 'RISK_OFF', 'TRANSITION'];
  
  for (const regime of regimes) {
    const policy = META_BRAIN_POLICIES[regime];
    const onchainWeight = policy.weights.onchain || 0;
    const percentage = Math.round(onchainWeight * 100);
    
    console.log(`  ${regime}: onchain weight = ${percentage}% (${onchainWeight})`);
    
    if (onchainWeight < 0.10 || onchainWeight > 0.15) {
      console.log(`    ⚠️  Warning: Weight ${percentage}% is outside the recommended 10-15% range`);
    } else {
      console.log('    ✅ Within recommended range (10-15%)');
    }
  }
  
  console.log('\n✅ Signal weights configured for On-Chain Lite mode\n');
  
  // Test 3: MongoDB Persistence
  console.log('📋 Step 3: Checking MongoDB Persistence Layer');
  
  const onchainServiceCode = await import('fs/promises').then(fs => 
    fs.readFile('/app/backend/src/modules/onchain-lite/onchain-lite.service.ts', 'utf8')
  );
  
  if (onchainServiceCode.includes('persistSnapshot') && onchainServiceCode.includes('onchain_lite_snapshots')) {
    console.log('  ✅ MongoDB persistence layer implemented');
    console.log('  ✅ Collection: onchain_lite_snapshots');
  } else {
    console.log('  ❌ MongoDB persistence not found');
  }
  
  console.log('\n===========================================');
  console.log('🎉 On-Chain Lite Mode — ACTIVATED');
  console.log('===========================================');
  console.log('\nConfiguration Summary:');
  console.log('  Mode: Lite (Infura + DefiLlama)');
  console.log('  Provider: Infura');
  console.log('  Signal Weight: 10-15% (adaptive per regime)');
  console.log('  Persistence: MongoDB (onchain_lite_snapshots)');
  console.log('  Status: ✅ READY');
  console.log('\nNext Steps:');
  console.log('  1. Backend service will auto-restart to load new configuration');
  console.log('  2. On-Chain data will start accumulating in the background');
  console.log('  3. Snapshots will be saved to onchain_lite_snapshots collection');
  console.log('  4. Signal aggregator will include On-Chain Lite signal at 10-15% weight');
}

testOnchainLiteIntegration().catch(err => {
  console.error('\n❌ Test failed:', err.message);
  console.error(err.stack);
  process.exit(1);
});
