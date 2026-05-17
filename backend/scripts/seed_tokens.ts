import 'dotenv/config';
import { connectMongo, disconnectMongo } from '../src/db/mongoose.js';
import { TokenRankingModel } from '../src/core/ranking/ranking.model.js';

async function run() {
  console.log('[Seed] Connecting to MongoDB...');
  await connectMongo();

  console.log('[Seed] Clearing existing tokens...');
  await TokenRankingModel.deleteMany({});

  console.log('[Seed] Inserting test tokens...');
  await TokenRankingModel.insertMany([
    {
      symbol: 'ETH',
      name: 'Ethereum',
      contractAddress: '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
      chainId: 1,
      compositeScore: 82,
      marketCapScore: 95,
      volumeScore: 88,
      momentumScore: 75,
      globalRank: 1,
      bucketRank: 1,
      bucket: 'BUY',
      engineConfidence: 78,
      actorSignalScore: 71,
      engineRisk: 42,
      priceUsd: 2200,
      priceChange24h: 3.5,
      volume24h: 15000000,
      marketCap: 264000000000,
      driftLevel: 'LOW',
      mlAdjusted: false,
      computedAt: new Date(),
    },
    {
      symbol: 'SOL',
      name: 'Solana',
      contractAddress: '0x7dFf46370e9eA5f0Bad3C4E29711aD50062EA7A4',
      chainId: 1,
      compositeScore: 61,
      marketCapScore: 82,
      volumeScore: 65,
      momentumScore: 58,
      globalRank: 2,
      bucketRank: 1,
      bucket: 'WATCH',
      engineConfidence: 55,
      actorSignalScore: 48,
      engineRisk: 63,
      priceUsd: 98,
      priceChange24h: -1.2,
      volume24h: 3500000,
      marketCap: 44000000000,
      driftLevel: 'LOW',
      mlAdjusted: false,
      computedAt: new Date(),
    },
    {
      symbol: 'USDT',
      name: 'Tether',
      contractAddress: '0xdAC17F958D2ee523a2206206994597C13D831ec7',
      chainId: 1,
      compositeScore: 45,
      marketCapScore: 98,
      volumeScore: 92,
      momentumScore: 5,
      globalRank: 3,
      bucketRank: 1,
      bucket: 'SELL',
      engineConfidence: 72,
      actorSignalScore: 12,
      engineRisk: 28,
      priceUsd: 1,
      priceChange24h: 0.01,
      volume24h: 50000000,
      marketCap: 95000000000,
      driftLevel: 'LOW',
      mlAdjusted: false,
      computedAt: new Date(),
    },
  ]);

  console.log('[Seed] ✅ Done. 3 tokens inserted.');
  await disconnectMongo();
  process.exit(0);
}

run().catch((err) => {
  console.error('[Seed] Error:', err);
  process.exit(1);
});
