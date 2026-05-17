/**
 * Migration Script: Backfill chainId = 1 (Ethereum) for all existing documents
 * ==============================================================================
 * 
 * Phase G0.2: All models now require chainId. This script patches existing
 * documents that were created before the field was added.
 * 
 * Safe to run multiple times (idempotent).
 * 
 * Usage: npx ts-node scripts/migrate_chainid_backfill.ts
 */

import mongoose from 'mongoose';

const MONGO_URL = process.env.MONGO_URL || 'mongodb://localhost:27017/onchain_intel';

const COLLECTIONS_TO_BACKFILL = [
  // Models that previously lacked chainId
  'onchain_v2_market_series',
  'onchain_v2_altflow_points',
  'onchain_v2_liquidity_series',
  'onchain_v2_liquidity_v2',
  'onchain_v2_bridge_aggregates',
  'onchain_v2_stable_aggregates',
  'onchain_v2_baselines',
  // Models that had chainId but not required (backfill nulls)
  'onchain_v2_actor_scores',
  'onchain_v2_entity_flows',
];

async function run() {
  console.log('[Migration] Connecting to MongoDB...');
  await mongoose.connect(MONGO_URL);
  const db = mongoose.connection.db;

  console.log('[Migration] Starting chainId backfill (default: 1 = Ethereum)');

  for (const collName of COLLECTIONS_TO_BACKFILL) {
    try {
      const coll = db.collection(collName);
      const count = await coll.countDocuments({ chainId: { $exists: false } });
      
      if (count === 0) {
        console.log(`  [${collName}] No documents need backfill`);
        continue;
      }

      const result = await coll.updateMany(
        { chainId: { $exists: false } },
        { $set: { chainId: 1 } }
      );

      console.log(`  [${collName}] Backfilled ${result.modifiedCount} documents`);
    } catch (err: any) {
      console.error(`  [${collName}] Error: ${err.message}`);
    }
  }

  // Also backfill null chainId values
  for (const collName of COLLECTIONS_TO_BACKFILL) {
    try {
      const coll = db.collection(collName);
      const result = await coll.updateMany(
        { chainId: null },
        { $set: { chainId: 1 } }
      );
      
      if (result.modifiedCount > 0) {
        console.log(`  [${collName}] Fixed ${result.modifiedCount} null chainId values`);
      }
    } catch (err: any) {
      // Ignore
    }
  }

  console.log('[Migration] Backfill complete');
  await mongoose.disconnect();
}

run().catch(err => {
  console.error('[Migration] Fatal error:', err);
  process.exit(1);
});
