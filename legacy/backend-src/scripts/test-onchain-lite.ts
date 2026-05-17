import { onchainLiteService } from '../modules/onchain-lite/onchain-lite.service.js';
import { MongoClient } from 'mongodb';

async function testOnchainLite() {
  console.log('🔍 On-Chain Lite Service Test\n');
  console.log('Mode:', onchainLiteService.getMode());
  console.log('ONCHAIN_ENABLED:', process.env.ONCHAIN_ENABLED);
  console.log('ONCHAIN_MODE:', process.env.ONCHAIN_MODE);
  console.log('INFURA_KEY:', process.env.INFURA_KEY ? '✅ SET (' + process.env.INFURA_KEY.substring(0, 8) + '...)' : '❌ NOT SET');
  
  console.log('\n📊 Testing Summary endpoint...');
  try {
    const summary = await onchainLiteService.getSummary();
    console.log('✅ Summary fetched successfully:');
    console.log(JSON.stringify(summary, null, 2));
  } catch (err: any) {
    console.error('❌ Summary fetch error:', err.message);
    console.error('Stack:', err.stack);
  }
  
  console.log('\n💾 Checking MongoDB persistence...');
  const client = new MongoClient(process.env.MONGO_URL || 'mongodb://localhost:27017');
  await client.connect();
  const db = client.db('intelligence_engine');
  
  const snapshots = await db.collection('onchain_lite_snapshots').find({}).sort({ timestamp: -1 }).limit(5).toArray();
  console.log(`Total snapshots in DB: ${snapshots.length}`);
  
  if (snapshots.length > 0) {
    console.log('\n📋 Latest snapshot:');
    console.log(JSON.stringify(snapshots[0], null, 2));
  } else {
    console.log('⚠️ No snapshots found yet. They will be created on first API call.');
  }
  
  await client.close();
}

testOnchainLite().catch(console.error);
