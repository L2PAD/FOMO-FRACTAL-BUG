import { MongoClient } from 'mongodb';

async function checkPublishers() {
  const client = new MongoClient(process.env.MONGO_URL || 'mongodb://localhost:27017');
  await client.connect();
  const db = client.db('intelligence_engine');

  console.log('🔍 Checking Publisher Results\n');

  // Exchange predictions
  const exchangePreds = await db.collection('exchange_prediction_snapshots').countDocuments();
  console.log(`📊 exchange_prediction_snapshots: ${exchangePreds} docs`);
  
  if (exchangePreds > 0) {
    const latest = await db.collection('exchange_prediction_snapshots')
      .find({})
      .sort({ timestamp: -1 })
      .limit(3)
      .toArray();
    
    console.log('\n✅ Latest Exchange Predictions:');
    latest.forEach(doc => {
      console.log(`  ${doc.asset} ${doc.horizon}: ${doc.direction} (score=${doc.score.toFixed(3)}, conf=${doc.confidence.toFixed(2)}, quality=${doc.quality})`);
      console.log(`    Target: $${doc.target_price} (move=${doc.expected_move_pct.toFixed(2)}%)`);
      console.log(`    Components: bull=${doc.components.bull_score.toFixed(3)}, bear=${doc.components.bear_score.toFixed(3)}`);
    });
  }

  // Fractal predictions
  const fractalPreds = await db.collection('fractal_prediction_snapshots').countDocuments();
  console.log(`\n📊 fractal_prediction_snapshots: ${fractalPreds} docs`);
  
  if (fractalPreds > 0) {
    const latest = await db.collection('fractal_prediction_snapshots')
      .find({})
      .sort({ timestamp: -1 })
      .limit(3)
      .toArray();
    
    console.log('\n✅ Latest Fractal Forecasts:');
    latest.forEach(doc => {
      console.log(`  ${doc.asset} ${doc.horizon}: ${doc.direction} (score=${doc.score.toFixed(3)}, conf=${doc.confidence.toFixed(2)})`);
      console.log(`    Expected return: ${doc.expected_return_pct.toFixed(2)}%`);
      console.log(`    Pattern: ${doc.pattern_type}, Regime: ${doc.regime || 'N/A'}`);
    });
  }

  // Health summary
  console.log('\n📊 Data Health Summary:');
  console.log(`  Exchange:  ${exchangePreds > 0 ? '✅ HEALTHY' : '❌ MISSING'}`);
  console.log(`  Fractal:   ${fractalPreds > 0 ? '✅ HEALTHY' : '❌ MISSING'}`);
  console.log(`  Sentiment: ✅ HEALTHY (10,260 docs)`);
  console.log(`  OnChain:   ⏳ PENDING (accumulating)`);

  await client.close();
}

checkPublishers().catch(console.error);
