/**
 * Seed Symbol Universe - Bootstrap trading symbols for Exchange Observation
 */
import { MongoClient } from 'mongodb';

const MONGO_URL = process.env.MONGO_URL || 'mongodb://localhost:27017';
const DB_NAME = process.env.DB_NAME || 'intelligence_engine';

const TOP_SYMBOLS = [
  'BTCUSDT',
  'ETHUSDT',
  'SOLUSDT',
  'BNBUSDT',
  'XRPUSDT',
  'ADAUSDT',
  'DOGEUSDT',
  'MATICUSDT',
  'DOTUSDT',
  'AVAXUSDT',
  'LINKUSDT',
  'UNIUSDT',
  'LTCUSDT',
  'ATOMUSDT',
  'ETCUSDT',
];

async function seed() {
  console.log('[Seed] Connecting to MongoDB...');
  const client = new MongoClient(MONGO_URL);
  await client.connect();
  const db = client.db(DB_NAME);

  console.log('[Seed] Clearing existing universe...');
  await db.collection('exchange_symbol_universe').deleteMany({});
  await db.collection('exchange_symbol_universe_alpha').deleteMany({});

  console.log('[Seed] Inserting symbols into exchange_symbol_universe...');
  const universeRecords = TOP_SYMBOLS.map((symbol) => ({
    symbol,
    source: 'manual_seed',
    createdAt: new Date(),
  }));
  await db.collection('exchange_symbol_universe').insertMany(universeRecords);

  console.log('[Seed] Inserting alpha symbols (top 5)...');
  const alphaSymbols = TOP_SYMBOLS.slice(0, 5);
  const alphaRecords = alphaSymbols.map((symbol, idx) => ({
    symbol,
    alphaScore: 100 - idx * 10, // 100, 90, 80, 70, 60
    source: 'manual_seed',
    createdAt: new Date(),
  }));
  await db.collection('exchange_symbol_universe_alpha').insertMany(alphaRecords);
  await db
    .collection('exchange_symbol_universe_alpha_dynamic')
    .insertMany(alphaRecords);

  console.log(`[Seed] ✅ Seeded ${universeRecords.length} universe symbols`);
  console.log(`[Seed] ✅ Seeded ${alphaRecords.length} alpha symbols`);

  await client.close();
  console.log('[Seed] Done!');
}

seed().catch(console.error);
