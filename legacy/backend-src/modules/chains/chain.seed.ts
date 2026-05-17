/**
 * Chain Seed — Phase G0.1
 * =========================
 * Idempotent seed: upsert 4 chains on startup.
 */

import { ChainModel } from './chain.model';

const SEED_CHAINS = [
  {
    chainId: 1,
    key: 'eth',
    name: 'Ethereum',
    rpcUrl: process.env.ETH_RPC_URL || '',
    explorerUrl: 'https://etherscan.io',
    nativeSymbol: 'ETH',
    enabled: true,
    priority: 1,
  },
  {
    chainId: 42161,
    key: 'arb',
    name: 'Arbitrum',
    rpcUrl: process.env.ARB_RPC_URL || '',
    explorerUrl: 'https://arbiscan.io',
    nativeSymbol: 'ETH',
    enabled: false,
    priority: 2,
  },
  {
    chainId: 10,
    key: 'op',
    name: 'Optimism',
    rpcUrl: process.env.OP_RPC_URL || '',
    explorerUrl: 'https://optimistic.etherscan.io',
    nativeSymbol: 'ETH',
    enabled: false,
    priority: 3,
  },
  {
    chainId: 8453,
    key: 'base',
    name: 'Base',
    rpcUrl: process.env.BASE_RPC_URL || '',
    explorerUrl: 'https://basescan.org',
    nativeSymbol: 'ETH',
    enabled: false,
    priority: 4,
  },
];

export async function seedChains(): Promise<void> {
  for (const chain of SEED_CHAINS) {
    await ChainModel.updateOne(
      { chainId: chain.chainId },
      { $setOnInsert: chain },
      { upsert: true }
    );
  }
  console.log(`[ChainSeed] Seeded ${SEED_CHAINS.length} chains (idempotent)`);
}
