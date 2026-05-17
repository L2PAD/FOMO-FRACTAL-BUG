import { MongoClient } from 'mongodb';

async function checkRawData() {
  const client = new MongoClient(process.env.MONGO_URL || 'mongodb://localhost:27017');
  await client.connect();
  const db = client.db('intelligence_engine');

  console.log('🔍 Checking RAW data sources\n');

  // Exchange observations
  const exchangeObs = await db.collection('exchange_observations').countDocuments();
  console.log(`📊 exchange_observations: ${exchangeObs} docs`);
  
  if (exchangeObs > 0) {
    const latest = await db.collection('exchange_observations').find({}).sort({ timestamp: -1 }).limit(1).toArray();
    console.log('   Latest:', JSON.stringify(latest[0], null, 2).substring(0, 500));
  }

  // Fractal state
  const fractalState = await db.collection('fractal_state').countDocuments();
  console.log(`\n📊 fractal_state: ${fractalState} docs`);
  
  if (fractalState > 0) {
    const latest = await db.collection('fractal_state').find({}).sort({ updatedAt: -1 }).limit(1).toArray();
    console.log('   Latest:', JSON.stringify(latest[0], null, 2).substring(0, 500));
  }

  // Check active ML predictions
  const mlPredictions = await db.collection('ml_prediction_snapshots').countDocuments();
  console.log(`\n📊 ml_prediction_snapshots: ${mlPredictions} docs`);

  // Check exchange predictions (alternative collection)
  const exchangePred = await db.collection('exchange_predictions').countDocuments();
  console.log(`\n📊 exchange_predictions: ${exchangePred} docs`);

  await client.close();
}

checkRawData().catch(console.error);
