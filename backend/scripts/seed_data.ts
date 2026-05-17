/**
 * Data Seeding Script for P0 - Populate actors collection
 * 
 * This script:
 * 1. Seeds entities from entities_seed.json
 * 2. Creates synthetic transfers between entity addresses
 * 3. Triggers the buildActorsGraph job to compute the graph
 */
import mongoose from 'mongoose';
import { config } from 'dotenv';

// Load environment
config({ path: '.env' });

// Models
import { EntityModel } from '../src/core/entities/entities.model.js';
import { EntityAddressModel } from '../src/core/entities/entity_address.model.js';
import { TransferModel } from '../src/core/transfers/transfers.model.js';
import { ComputedGraphModel } from '../src/core/actors/computed_graph.model.js';

// Seed data
import seedData from '../src/core/entities/entities_seed.json' with { type: 'json' };
import { ACTORS_SEED } from '../src/core/actors/actors_seed.data.js';

const MONGO_URL = process.env.MONGODB_URI || 'mongodb://localhost:27017/blockview';

/**
 * Connect to MongoDB
 */
async function connectDB() {
  console.log('[Seed] Connecting to MongoDB...');
  await mongoose.connect(MONGO_URL);
  console.log('[Seed] Connected to MongoDB');
}

/**
 * Seed entities from JSON
 */
async function seedEntities() {
  console.log('[Seed] Seeding entities...');
  
  // Clear existing
  await EntityModel.deleteMany({});
  await EntityAddressModel.deleteMany({});
  
  let entityCount = 0;
  let addressCount = 0;
  
  // Merge entities_seed.json and actors_seed.data.ts
  const allSeeds = [...seedData];
  
  // Add actors from actors_seed.data.ts that aren't in entities_seed.json
  const existingSlugs = new Set(seedData.map((e: any) => e.slug));
  
  for (const actor of ACTORS_SEED) {
    const slug = actor.name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
    if (!existingSlugs.has(slug)) {
      allSeeds.push({
        name: actor.name,
        slug: slug,
        logo: `https://via.placeholder.com/48/6366f1/ffffff?text=${actor.name.substring(0, 2)}`,
        description: `${actor.name} - ${actor.type}`,
        category: actor.type === 'exchange' ? 'exchange' : 
                  actor.type === 'market_maker' ? 'market_maker' :
                  actor.type === 'fund' ? 'fund' :
                  actor.type === 'protocol' ? 'protocol' : 'unknown',
        tags: actor.tags,
        primaryAddresses: actor.addresses.filter(a => !a.startsWith('0x00000000')),
        source: 'seed',
        attribution: {
          method: 'seed_dataset',
          confidence: actor.source === 'verified' ? 95 : 80,
          evidence: ['seed_data']
        }
      });
    }
  }
  
  for (const entityData of allSeeds) {
    const data = entityData as any;
    
    // Skip if no valid addresses
    const validAddresses = (data.primaryAddresses || []).filter(
      (a: string) => a && !a.startsWith('0x00000000') && a.length === 42
    );
    
    if (validAddresses.length === 0) {
      console.log(`[Seed] Skipping ${data.name} - no valid addresses`);
      continue;
    }
    
    // Create entity
    const entity = await EntityModel.create({
      name: data.name,
      slug: data.slug,
      logo: data.logo,
      description: data.description,
      category: data.category || 'unknown',
      tags: data.tags || [],
      addressesCount: validAddresses.length,
      primaryAddresses: validAddresses,
      coverage: 75,
      status: 'live',
      source: 'seed',
      attribution: data.attribution,
      firstSeen: new Date(),
      lastSeen: new Date(),
    });
    
    entityCount++;
    
    // Create entity addresses
    for (const address of validAddresses) {
      await EntityAddressModel.create({
        entityId: entity._id.toString(),
        chain: 'ethereum',
        address: address.toLowerCase(),
        role: 'hot',
        labelConfidence: data.attribution?.confidence || 80,
        firstSeen: new Date(),
        lastSeen: new Date(),
      });
      addressCount++;
    }
  }
  
  console.log(`[Seed] ✅ Seeded ${entityCount} entities with ${addressCount} addresses`);
  return { entityCount, addressCount };
}

/**
 * Generate synthetic transfers between entities
 */
async function generateTransfers() {
  console.log('[Seed] Generating synthetic transfers...');
  
  // Clear existing transfers
  await TransferModel.deleteMany({});
  
  // Get all entity addresses
  const entityAddresses = await EntityAddressModel.find({}).lean();
  const addresses = entityAddresses.map((ea: any) => ea.address.toLowerCase());
  
  if (addresses.length < 2) {
    console.log('[Seed] Not enough addresses to generate transfers');
    return 0;
  }
  
  // Common tokens
  const tokens = [
    { address: '0xdac17f958d2ee523a2206206994597c13d831ec7', symbol: 'USDT', decimals: 6 },
    { address: '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48', symbol: 'USDC', decimals: 6 },
    { address: '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2', symbol: 'WETH', decimals: 18 },
  ];
  
  const transfers = [];
  const now = Date.now();
  const day = 24 * 60 * 60 * 1000;
  
  // Generate transfers for the last 30 days
  for (let i = 0; i < 500; i++) {
    const fromIdx = Math.floor(Math.random() * addresses.length);
    let toIdx = Math.floor(Math.random() * addresses.length);
    
    // Ensure different addresses
    while (toIdx === fromIdx) {
      toIdx = Math.floor(Math.random() * addresses.length);
    }
    
    const token = tokens[Math.floor(Math.random() * tokens.length)];
    const amount = Math.floor(Math.random() * 1000000) + 10000; // 10k-1M
    const amountRaw = (BigInt(amount) * BigInt(10 ** token.decimals)).toString();
    
    // Random timestamp in last 30 days
    const timestamp = new Date(now - Math.floor(Math.random() * 30 * day));
    const blockNumber = 18000000 + Math.floor(Math.random() * 1000000);
    
    transfers.push({
      txHash: `0x${Buffer.from(crypto.getRandomValues(new Uint8Array(32))).toString('hex')}`,
      logIndex: Math.floor(Math.random() * 100),
      blockNumber,
      timestamp,
      from: addresses[fromIdx],
      to: addresses[toIdx],
      assetType: 'erc20',
      assetAddress: token.address,
      amountRaw,
      amountNormalized: amount,
      chain: 'ethereum',
      source: 'erc20_log',
      sourceId: `seed-${i}`,
      processed: false,
    });
  }
  
  // Bulk insert
  await TransferModel.insertMany(transfers);
  
  console.log(`[Seed] ✅ Generated ${transfers.length} transfers`);
  return transfers.length;
}

/**
 * Build the actors graph cache
 */
async function buildGraphCache() {
  console.log('[Seed] Building actors graph cache...');
  
  // Clear existing cache
  await ComputedGraphModel.deleteMany({});
  
  // Import and run the job
  const { buildActorsGraph } = await import('../src/jobs/build_actors_graph.job.js');
  const result = await buildActorsGraph();
  
  console.log(`[Seed] ✅ Built graph cache: ${result.windowsBuilt} windows, ${result.duration}ms`);
  if (result.errors.length > 0) {
    console.log('[Seed] ⚠️ Errors:', result.errors);
  }
  
  return result;
}

/**
 * Verify the data
 */
async function verifyData() {
  console.log('\n[Seed] Verifying data...');
  
  const entities = await EntityModel.countDocuments();
  const addresses = await EntityAddressModel.countDocuments();
  const transfers = await TransferModel.countDocuments();
  const graphs = await ComputedGraphModel.countDocuments();
  
  // Get graph details
  const graph7d = await ComputedGraphModel.findOne({ window: '7d' }).lean();
  const graph30d = await ComputedGraphModel.findOne({ window: '30d' }).lean();
  
  console.log('\n========== DATABASE STATUS ==========');
  console.log(`Entities:        ${entities}`);
  console.log(`Entity Addresses: ${addresses}`);
  console.log(`Transfers:       ${transfers}`);
  console.log(`Computed Graphs: ${graphs}`);
  
  if (graph7d) {
    const g = graph7d as any;
    console.log(`\n7d Graph:        ${g.nodes?.length || 0} nodes, ${g.edges?.length || 0} edges`);
  }
  if (graph30d) {
    const g = graph30d as any;
    console.log(`30d Graph:       ${g.nodes?.length || 0} nodes, ${g.edges?.length || 0} edges`);
  }
  
  console.log('=====================================\n');
  
  return { entities, addresses, transfers, graphs };
}

/**
 * Main function
 */
async function main() {
  console.log('\n🚀 Starting P0 Data Seeding...\n');
  
  try {
    await connectDB();
    
    // Step 1: Seed entities
    await seedEntities();
    
    // Step 2: Generate transfers
    await generateTransfers();
    
    // Step 3: Build graph cache
    await buildGraphCache();
    
    // Step 4: Verify
    await verifyData();
    
    console.log('✅ P0 Data Seeding Complete!\n');
    
  } catch (error) {
    console.error('❌ Error:', error);
    process.exit(1);
  } finally {
    await mongoose.disconnect();
    process.exit(0);
  }
}

main();
