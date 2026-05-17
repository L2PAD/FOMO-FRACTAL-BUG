import { MongoClient } from 'mongodb';

const MONGO_URL = process.env.MONGO_URL || 'mongodb://localhost:27017';
const DB_NAME = 'intelligence_engine';

async function checkLatestData() {
  const client = new MongoClient(MONGO_URL);
  await client.connect();
  const db = client.db(DB_NAME);

  const modules = {
    'Exchange (WS)': 'exchange_observations',
    'Sentiment': 'sentiment_aggregates',
    'Fractals': 'fractal_canonical_ohlcv',
    'Predictions': 'prediction_snapshots',
    'News': 'canonical_events',
    'On-Chain': 'onchain_v2_snapshots',
    'Funding': 'exchange_funding_context',
    'Signal Log': 'signal_log'
  };

  console.log('\n📊 LATEST DATA BY MODULE:\n');

  for (const [name, coll] of Object.entries(modules)) {
    const count = await db.collection(coll).countDocuments();
    const latest = await db.collection(coll).find({}).sort({ _id: -1 }).limit(1).toArray();
    
    if (count > 0 && latest[0]) {
      const ts = latest[0].timestamp || latest[0].createdAt || latest[0]._id;
      const date = ts instanceof Date ? ts : new Date(parseInt(ts.toString().substring(0,8), 16) * 1000);
      console.log(`✅ ${name.padEnd(18)} ${String(count).padStart(6)} docs | Last: ${date.toLocaleString()}`);
    } else {
      console.log(`⚠️  ${name.padEnd(18)} ${String(count).padStart(6)} docs | EMPTY`);
    }
  }

  await client.close();
}

checkLatestData().catch(console.error);
