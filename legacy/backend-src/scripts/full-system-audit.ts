import { MongoClient } from 'mongodb';

const MONGO_URL = process.env.MONGO_URL || 'mongodb://localhost:27017';
const DB_NAME = 'intelligence_engine';

async function auditSystem() {
  const client = new MongoClient(MONGO_URL);
  await client.connect();
  const db = client.db(DB_NAME);

  console.log('═══════════════════════════════════════════════════════════');
  console.log('          📊 FULL SYSTEM DATA AUDIT');
  console.log('═══════════════════════════════════════════════════════════\n');

  // Get all collections
  const collections = await db.listCollections().toArray();
  
  console.log(`📁 Total collections: ${collections.length}\n`);
  
  // Group by category
  const categories = {
    '🔗 Exchange / Market Data': [],
    '🧠 Sentiment / Social': [],
    '📐 Fractals / Patterns': [],
    '🔮 Predictions / ML': [],
    '⛓️  On-Chain / Blockchain': [],
    '👤 Users / Auth': [],
    '⚙️  System / Config': [],
    '📊 Other': []
  };

  for (const coll of collections) {
    const name = coll.name;
    const count = await db.collection(name).countDocuments();
    
    // Get recent document if exists
    let recent = null;
    if (count > 0) {
      const docs = await db.collection(name).find({}).sort({ _id: -1 }).limit(1).toArray();
      recent = docs[0];
    }

    const item = { name, count, recent };

    // Categorize
    if (name.includes('exchange') || name.includes('observation') || name.includes('symbol') || name.includes('market')) {
      categories['🔗 Exchange / Market Data'].push(item);
    } else if (name.includes('sentiment') || name.includes('twitter') || name.includes('news') || name.includes('social')) {
      categories['🧠 Sentiment / Social'].push(item);
    } else if (name.includes('fractal') || name.includes('pattern')) {
      categories['📐 Fractals / Patterns'].push(item);
    } else if (name.includes('prediction') || name.includes('ml') || name.includes('model') || name.includes('signal')) {
      categories['🔮 Predictions / ML'].push(item);
    } else if (name.includes('onchain') || name.includes('transaction') || name.includes('block') || name.includes('contract')) {
      categories['⛓️  On-Chain / Blockchain'].push(item);
    } else if (name.includes('user') || name.includes('auth') || name.includes('admin')) {
      categories['👤 Users / Auth'].push(item);
    } else if (name.includes('config') || name.includes('setting') || name.includes('runtime') || name.includes('policy')) {
      categories['⚙️  System / Config'].push(item);
    } else {
      categories['📊 Other'].push(item);
    }
  }

  // Print by category
  for (const [category, items] of Object.entries(categories)) {
    if (items.length === 0) continue;

    console.log(`\n${category}`);
    console.log('─'.repeat(65));

    for (const item of items) {
      const status = item.count > 0 ? '✅' : '⚠️ ';
      const recentDate = item.recent?._id ? new Date(parseInt(item.recent._id.toString().substring(0, 8), 16) * 1000).toLocaleString() : 'N/A';
      
      console.log(`${status} ${item.name.padEnd(45)} ${String(item.count).padStart(8)} docs`);
      
      if (item.count > 0) {
        console.log(`   └─ Last updated: ${recentDate}`);
      }
    }
  }

  console.log('\n═══════════════════════════════════════════════════════════');
  console.log('                  SUMMARY');
  console.log('═══════════════════════════════════════════════════════════\n');

  const totalDocs = await Promise.all(
    collections.map(c => db.collection(c.name).countDocuments())
  );
  
  const sum = totalDocs.reduce((a, b) => a + b, 0);
  
  console.log(`Total documents across all collections: ${sum.toLocaleString()}`);
  console.log(`Active collections (with data): ${collections.filter((_, i) => totalDocs[i] > 0).length}`);
  console.log(`Empty collections: ${collections.filter((_, i) => totalDocs[i] === 0).length}`);

  await client.close();
}

auditSystem().catch(console.error);
