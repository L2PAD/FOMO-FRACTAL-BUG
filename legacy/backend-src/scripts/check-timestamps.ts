import { MongoClient } from 'mongodb';

const MONGO_URL = process.env.MONGO_URL || 'mongodb://localhost:27017';

async function checkTimestamps() {
  const client = new MongoClient(MONGO_URL);
  await client.connect();
  const db = client.db('intelligence_engine');

  // Get sample observation
  const obs = await db.collection('exchange_observations').findOne({});
  
  console.log('\n🔍 Sample Exchange Observation:');
  console.log('_id:', obs?._id);
  console.log('timestamp:', obs?.timestamp);
  console.log('createdAt:', obs?.createdAt);
  console.log('updatedAt:', obs?.updatedAt);
  console.log('symbol:', obs?.symbol);
  console.log('price:', obs?.market?.price);

  // Check funding context
  const funding = await db.collection('exchange_funding_context').findOne({}, { sort: { _id: -1 } });
  console.log('\n🔍 Latest Funding Context:');
  console.log('_id:', funding?._id);
  console.log('timestamp:', funding?.timestamp);
  console.log('createdAt:', funding?.createdAt);
  console.log('updatedAt:', funding?.updatedAt);

  // Check sentiment
  const sentiment = await db.collection('sentiment_aggregates').findOne({}, { sort: { _id: -1 } });
  console.log('\n🔍 Latest Sentiment Aggregate:');
  console.log('_id:', sentiment?._id);
  console.log('timestamp:', sentiment?.timestamp);
  console.log('createdAt:', sentiment?.createdAt);
  console.log('updatedAt:', sentiment?.updatedAt);

  await client.close();
}

checkTimestamps().catch(console.error);
