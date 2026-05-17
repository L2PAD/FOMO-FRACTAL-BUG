/**
 * Seed entities and build actors graph
 * Run with: npx tsx scripts/seed_and_build.ts
 */
import 'dotenv/config';
import { connectMongo, disconnectMongo } from '../src/db/mongoose.js';
import { seedEntities } from '../src/core/entities/entities.seed.js';
import { buildActorsGraph } from '../src/jobs/build_actors_graph.job.js';

async function main() {
  console.log('[Seed] Connecting to MongoDB...');
  await connectMongo();
  
  console.log('\n[Seed] Step 1: Seeding entities...');
  const seedResult = await seedEntities();
  console.log('[Seed] Entities result:', seedResult);
  
  console.log('\n[Seed] Step 2: Building actors graph...');
  const graphResult = await buildActorsGraph();
  console.log('[Seed] Actors graph result:', graphResult);
  
  console.log('\n[Seed] ✅ Complete!');
  await disconnectMongo();
  process.exit(0);
}

main().catch(err => {
  console.error('[Seed] Fatal error:', err);
  process.exit(1);
});
