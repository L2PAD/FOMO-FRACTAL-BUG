import { MongoClient } from 'mongodb';

async function findInfura() {
  const client = new MongoClient(process.env.MONGO_URL || 'mongodb://localhost:27017');
  await client.connect();
  const db = client.db('intelligence_engine');
  
  // Check api_keys collection
  console.log('🔎 Checking api_keys collection:');
  const apiKeys = await db.collection('api_keys').find({}).toArray();
  console.log('Total documents:', apiKeys.length);
  
  if (apiKeys.length > 0) {
    console.log('\n📋 All documents in api_keys:');
    apiKeys.forEach((doc, idx) => {
      console.log(`\n[${idx + 1}]`, JSON.stringify(doc, null, 2));
    });
    
    const infuraKey = apiKeys.find(k => 
      JSON.stringify(k).toLowerCase().includes('infura')
    );
    
    if (infuraKey) {
      console.log('\n✅ FOUND INFURA KEY:');
      console.log(JSON.stringify(infuraKey, null, 2));
    } else {
      console.log('\n❌ No Infura key found');
    }
  } else {
    console.log('❌ Collection is empty');
  }
  
  // Also check system_config
  console.log('\n\n🔎 Checking system_config collection:');
  const systemConfig = await db.collection('system_config').find({}).toArray();
  console.log('Total documents:', systemConfig.length);
  systemConfig.forEach((doc, idx) => {
    console.log(`\n[${idx + 1}]`, JSON.stringify(doc, null, 2));
    if (JSON.stringify(doc).toLowerCase().includes('infura')) {
      console.log('  ⚡ Contains "infura"!');
    }
  });
  
  // Check onchain_v2_rpc_config
  console.log('\n\n🔎 Checking onchain_v2_rpc_config collection:');
  const rpcConfig = await db.collection('onchain_v2_rpc_config').find({}).toArray();
  console.log('Total documents:', rpcConfig.length);
  rpcConfig.forEach((doc, idx) => {
    console.log(`\n[${idx + 1}]`, JSON.stringify(doc, null, 2));
  });
  
  await client.close();
}

findInfura().catch(console.error);
