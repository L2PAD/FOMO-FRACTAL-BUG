import { MongoClient } from 'mongodb';

async function getInfuraKey() {
  const client = new MongoClient(process.env.MONGO_URL || 'mongodb://localhost:27017');
  await client.connect();
  const db = client.db('intelligence_engine');

  // Find Infura key from admin API keys
  const infuraKey = await db.collection('system_api_keys').findOne({ service: /infura/i });
  
  if (infuraKey) {
    console.log('✅ Infura Key Found:');
    console.log('Service:', infuraKey.service);
    console.log('Key:', infuraKey.key);
    console.log('URL:', infuraKey.url);
    console.log('\nFull URL:', `https://mainnet.infura.io/v3/${infuraKey.key}`);
  } else {
    console.log('❌ No Infura key found in database');
  }

  await client.close();
}

getInfuraKey().catch(console.error);
