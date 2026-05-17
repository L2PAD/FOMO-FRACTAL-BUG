import { MongoClient } from 'mongodb';

const MONGO_URL = process.env.MONGO_URL || 'mongodb://localhost:27017';

async function clear() {
  const client = new MongoClient(MONGO_URL);
  await client.connect();
  const db = client.db('intelligence_engine');
  const result = await db.collection('exchange_observations').deleteMany({});
  console.log('🗑️  Deleted', result.deletedCount, 'observations');
  await client.close();
}

clear().catch(console.error);
