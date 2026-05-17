import { MongoClient } from 'mongodb';

async function listCollections() {
  const client = new MongoClient(process.env.MONGO_URL || 'mongodb://localhost:27017');
  await client.connect();
  const db = client.db('intelligence_engine');
  
  const collections = await db.listCollections().toArray();
  console.log('📋 All MongoDB Collections:');
  collections.forEach(c => console.log('  -', c.name));
  
  console.log('\n🔍 Searching for API keys-related collections:');
  const apiKeysRelated = collections.filter(c => 
    c.name.includes('key') || 
    c.name.includes('api') || 
    c.name.includes('intel') || 
    c.name.includes('setting') ||
    c.name.includes('config')
  );
  apiKeysRelated.forEach(c => console.log('  ✓', c.name));
  
  // Try to find any document with "infura"
  console.log('\n🔎 Checking admin_settings for infura:');
  const adminSettings = await db.collection('admin_settings').find({}).toArray();
  console.log('admin_settings count:', adminSettings.length);
  adminSettings.forEach(doc => {
    console.log('  Category:', doc.category);
    if (JSON.stringify(doc).toLowerCase().includes('infura')) {
      console.log('  ✅ FOUND INFURA in this doc:', JSON.stringify(doc, null, 2));
    }
  });
  
  // Check system_api_keys
  console.log('\n🔎 Checking system_api_keys:');
  const apiKeys = await db.collection('system_api_keys').find({}).toArray();
  console.log('system_api_keys count:', apiKeys.length);
  apiKeys.forEach(doc => {
    console.log('  Doc:', JSON.stringify(doc, null, 2));
  });
  
  await client.close();
}

listCollections().catch(console.error);
