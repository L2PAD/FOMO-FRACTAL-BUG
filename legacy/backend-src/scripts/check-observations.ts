import { MongoClient } from 'mongodb';

const MONGO_URL = process.env.MONGO_URL || 'mongodb://localhost:27017';
const DB_NAME = 'intelligence_engine';

async function checkDB() {
  const client = new MongoClient(MONGO_URL);
  await client.connect();
  const db = client.db(DB_NAME);
  
  const count = await db.collection('exchange_observations').countDocuments();
  console.log('📊 exchange_observations count:', count);

  const recent = await db.collection('exchange_observations')
    .find({})
    .sort({ timestamp: -1 })
    .limit(1)
    .toArray();

  console.log('\n🔥 Sample record:');
  console.log(JSON.stringify(recent[0], null, 2));

  await client.close();
}

checkDB().catch(console.error);
