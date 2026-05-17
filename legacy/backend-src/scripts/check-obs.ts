import { MongoClient } from 'mongodb';

async function checkObs() {
  const client = new MongoClient(process.env.MONGO_URL || 'mongodb://localhost:27017');
  await client.connect();
  const db = client.db('intelligence_engine');
  const obs = await db.collection('exchange_observations').findOne({ asset: 'BTC' });
  console.log(JSON.stringify(obs, null, 2));
  await client.close();
}

checkObs();
