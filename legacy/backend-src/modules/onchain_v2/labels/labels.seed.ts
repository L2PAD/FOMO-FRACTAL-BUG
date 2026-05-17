/**
 * Labels Seed Data
 * =================
 * 
 * P0 Labeling: Initial seed of known addresses (CEX, Bridges, etc.)
 * This is extensible - add more addresses as needed
 */

import { LabelType } from './addressLabel.model';

interface Seed {
  chainId: number;
  address: string;
  labelType: LabelType;
  entityId: string;
  name: string;
  tags?: string[];
  confidence?: number;
  source?: string;
}

export const LABEL_SEED_V1: Seed[] = [
  // ═══════════════════════════════════════════════════════════════
  // EXCHANGES (Ethereum Mainnet)
  // ═══════════════════════════════════════════════════════════════
  
  // Binance
  { chainId: 1, address: '0x28c6c06298d514db089934071355e5743bf21d60', labelType: 'EXCHANGE', entityId: 'binance', name: 'Binance Hot Wallet 14', tags: ['hot', 'deposit'], confidence: 0.95 },
  { chainId: 1, address: '0x21a31ee1afc51d94c2efccaa2092ad1028285549', labelType: 'EXCHANGE', entityId: 'binance', name: 'Binance Hot Wallet 6', tags: ['hot'], confidence: 0.95 },
  { chainId: 1, address: '0xdfd5293d8e347dfe59e90efd55b2956a1343963d', labelType: 'EXCHANGE', entityId: 'binance', name: 'Binance Hot Wallet 8', tags: ['hot'], confidence: 0.95 },
  { chainId: 1, address: '0x56eddb7aa87536c09ccc2793473599fd21a8b17f', labelType: 'EXCHANGE', entityId: 'binance', name: 'Binance Hot Wallet 2', tags: ['hot'], confidence: 0.95 },
  { chainId: 1, address: '0x9696f59e4d72e237be84ffd425dcad154bf96976', labelType: 'EXCHANGE', entityId: 'binance', name: 'Binance Hot Wallet 15', tags: ['hot'], confidence: 0.95 },
  
  // Coinbase
  { chainId: 1, address: '0x71660c4005ba85c37ccec55d0c4493e66fe775d3', labelType: 'EXCHANGE', entityId: 'coinbase', name: 'Coinbase Hot Wallet 1', tags: ['hot'], confidence: 0.95 },
  { chainId: 1, address: '0x503828976d22510aad0201ac7ec88293211d23da', labelType: 'EXCHANGE', entityId: 'coinbase', name: 'Coinbase Hot Wallet 2', tags: ['hot'], confidence: 0.95 },
  { chainId: 1, address: '0xddfabcdc4d8ffc6d5beaf154f18b778f892a0740', labelType: 'EXCHANGE', entityId: 'coinbase', name: 'Coinbase Hot Wallet 3', tags: ['hot'], confidence: 0.95 },
  { chainId: 1, address: '0x3cd751e6b0078be393132286c442345e5dc49699', labelType: 'EXCHANGE', entityId: 'coinbase', name: 'Coinbase Hot Wallet 4', tags: ['hot'], confidence: 0.95 },
  
  // Kraken
  { chainId: 1, address: '0x2910543af39aba0cd09dbb2d50200b3e800a63d2', labelType: 'EXCHANGE', entityId: 'kraken', name: 'Kraken Hot Wallet 1', tags: ['hot'], confidence: 0.95 },
  { chainId: 1, address: '0x0a869d79a7052c7f1b55a8ebabbea3420f0d1e13', labelType: 'EXCHANGE', entityId: 'kraken', name: 'Kraken Hot Wallet 2', tags: ['hot'], confidence: 0.95 },
  
  // OKX
  { chainId: 1, address: '0x6cc5f688a315f3dc28a7781717a9a798a59fda7b', labelType: 'EXCHANGE', entityId: 'okx', name: 'OKX Hot Wallet 1', tags: ['hot'], confidence: 0.95 },
  { chainId: 1, address: '0x236f9f97e0e62388479bf9e5ba4889e46b0273c3', labelType: 'EXCHANGE', entityId: 'okx', name: 'OKX Hot Wallet 2', tags: ['hot'], confidence: 0.95 },
  
  // Bybit
  { chainId: 1, address: '0xf89d7b9c864f589bbf53a82105107622b35eaa40', labelType: 'EXCHANGE', entityId: 'bybit', name: 'Bybit Hot Wallet', tags: ['hot'], confidence: 0.90 },
  { chainId: 1, address: '0x1db92e2eebc8e0c075a02bea49a2935bcd2dfcf4', labelType: 'EXCHANGE', entityId: 'bybit', name: 'Bybit Hot Wallet 2', tags: ['hot'], confidence: 0.90 },
  
  // KuCoin
  { chainId: 1, address: '0xd6216fc19db775df9774a6e33526131da7d19a2c', labelType: 'EXCHANGE', entityId: 'kucoin', name: 'KuCoin Hot Wallet 1', tags: ['hot'], confidence: 0.90 },
  { chainId: 1, address: '0xf16e9b0d03470827a95cdfd0cb8a8a3b46969b91', labelType: 'EXCHANGE', entityId: 'kucoin', name: 'KuCoin Hot Wallet 2', tags: ['hot'], confidence: 0.90 },
  { chainId: 1, address: '0x88bd4d3e2997371bceefe8d9386c6b5b4de60346', labelType: 'EXCHANGE', entityId: 'kucoin', name: 'KuCoin Hot Wallet 3', tags: ['hot'], confidence: 0.90 },
  
  // Gemini
  { chainId: 1, address: '0xd24400ae8bfebb18ca49be86258a3c749cf46853', labelType: 'EXCHANGE', entityId: 'gemini', name: 'Gemini Hot Wallet 1', tags: ['hot'], confidence: 0.95 },
  { chainId: 1, address: '0x6fc82a5fe25a5cdb58bc74600a40a69c065263f8', labelType: 'EXCHANGE', entityId: 'gemini', name: 'Gemini Hot Wallet 2', tags: ['hot'], confidence: 0.95 },

  // Bitfinex
  { chainId: 1, address: '0x1151314c646ce4e0efd76d1af4760ae66a9fe30f', labelType: 'EXCHANGE', entityId: 'bitfinex', name: 'Bitfinex Hot Wallet', tags: ['hot'], confidence: 0.95 },
  { chainId: 1, address: '0x742d35cc6634c0532925a3b844bc454e4438f44e', labelType: 'EXCHANGE', entityId: 'bitfinex', name: 'Bitfinex Cold Wallet', tags: ['cold'], confidence: 0.95 },

  // Gate.io
  { chainId: 1, address: '0x0d0707963952f2fba59dd06f2b425ace40b492fe', labelType: 'EXCHANGE', entityId: 'gate_io', name: 'Gate.io Hot Wallet 1', tags: ['hot'], confidence: 0.90 },
  { chainId: 1, address: '0x1c4b70a3968436b9a0a9cf5205c787eb81bb558c', labelType: 'EXCHANGE', entityId: 'gate_io', name: 'Gate.io Hot Wallet 2', tags: ['hot'], confidence: 0.90 },

  // Huobi (HTX)
  { chainId: 1, address: '0x46705dfff24256421a05d056c29e81bdc09723b8', labelType: 'EXCHANGE', entityId: 'htx', name: 'HTX Hot Wallet 1', tags: ['hot'], confidence: 0.90 },
  { chainId: 1, address: '0x5c985e89dde482efe97ea9f1950ad149eb73829b', labelType: 'EXCHANGE', entityId: 'htx', name: 'HTX Hot Wallet 2', tags: ['hot'], confidence: 0.90 },

  // Binance Cold Wallets
  { chainId: 1, address: '0xf977814e90da44bfa03b6295a0616a897441acec', labelType: 'EXCHANGE', entityId: 'binance', name: 'Binance Cold Wallet 1', tags: ['cold'], confidence: 0.95 },
  { chainId: 1, address: '0xbe0eb53f46cd790cd13851d5eff43d12404d33e8', labelType: 'EXCHANGE', entityId: 'binance', name: 'Binance Cold Wallet 2', tags: ['cold'], confidence: 0.95 },

  // Coinbase Cold Wallet
  { chainId: 1, address: '0x77134cbc06cb00b66f4c7e623d5fdbf6777635ec', labelType: 'EXCHANGE', entityId: 'coinbase', name: 'Coinbase Cold Wallet', tags: ['cold'], confidence: 0.95 },
  { chainId: 1, address: '0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43', labelType: 'EXCHANGE', entityId: 'coinbase', name: 'Coinbase Hot Wallet 5', tags: ['hot'], confidence: 0.95 },

  // Kraken Cold + Additional
  { chainId: 1, address: '0xe853c56864a2ebe4576a807d26fdc4a0ada51919', labelType: 'EXCHANGE', entityId: 'kraken', name: 'Kraken Hot Wallet 3', tags: ['hot'], confidence: 0.95 },
  { chainId: 1, address: '0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0', labelType: 'EXCHANGE', entityId: 'kraken', name: 'Kraken Cold Wallet', tags: ['cold'], confidence: 0.95 },

  // Hyperliquid
  { chainId: 1, address: '0x2df1c51e09aecf9cacb7bc98cb1742757f163df7', labelType: 'EXCHANGE', entityId: 'hyperliquid', name: 'Hyperliquid Bridge', tags: ['hot', 'bridge'], confidence: 0.85 },
  
  // ═══════════════════════════════════════════════════════════════
  // BRIDGES
  // ═══════════════════════════════════════════════════════════════
  
  // Optimism
  { chainId: 1, address: '0x99c9fc46f92e8a1c0dec1b1747d010903e884be1', labelType: 'BRIDGE', entityId: 'optimism-gateway', name: 'Optimism L1 Bridge', tags: ['l1', 'opstack'], confidence: 0.99 },
  { chainId: 1, address: '0x5fd7d0d6b91cc4787bcb86ca47e0bd4ea0346d34', labelType: 'BRIDGE', entityId: 'optimism-snx', name: 'Optimism SNX Bridge', tags: ['l1', 'snx'], confidence: 0.95 },
  
  // Arbitrum
  { chainId: 1, address: '0x8315177ab297ba92a06054ce80a67ed4dbd7ed3a', labelType: 'BRIDGE', entityId: 'arbitrum-bridge', name: 'Arbitrum Bridge', tags: ['l1', 'arb'], confidence: 0.99 },
  { chainId: 1, address: '0xa3a7b6f88361f48403514059f1f16c8e78d60eec', labelType: 'BRIDGE', entityId: 'arbitrum-outbox', name: 'Arbitrum Outbox', tags: ['l1', 'arb'], confidence: 0.99 },
  { chainId: 1, address: '0xcee284f754e854890e311e3280b767f80797180d', labelType: 'BRIDGE', entityId: 'arbitrum-gateway', name: 'Arbitrum L1 Gateway Router', tags: ['l1', 'arb', 'router'], confidence: 0.99 },
  
  // Base
  { chainId: 1, address: '0x3154cf16ccdb4c6d922629664174b904d80f2c35', labelType: 'BRIDGE', entityId: 'base-portal', name: 'Base Portal', tags: ['l1', 'base'], confidence: 0.99 },
  
  // Polygon
  { chainId: 1, address: '0x401f6c983ea34274ec46f84d70b31c151321188b', labelType: 'BRIDGE', entityId: 'polygon-pos', name: 'Polygon PoS Bridge', tags: ['l1', 'polygon'], confidence: 0.95 },
  { chainId: 1, address: '0x5a51e2ebf8d136926b9ca7b59b60464e7c44d2eb', labelType: 'BRIDGE', entityId: 'polygon-plasma', name: 'Polygon Plasma Bridge', tags: ['l1', 'polygon', 'plasma'], confidence: 0.95 },
  
  // ═══════════════════════════════════════════════════════════════
  // PROTOCOLS
  // ═══════════════════════════════════════════════════════════════
  
  // Uniswap
  { chainId: 1, address: '0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45', labelType: 'PROTOCOL', entityId: 'uniswap-router', name: 'Uniswap V3 Router 2', tags: ['dex', 'router'], confidence: 0.99 },
  { chainId: 1, address: '0xe592427a0aece92de3edee1f18e0157c05861564', labelType: 'PROTOCOL', entityId: 'uniswap-router-v3', name: 'Uniswap V3 Router', tags: ['dex', 'router'], confidence: 0.99 },
  
  // Aave
  { chainId: 1, address: '0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2', labelType: 'PROTOCOL', entityId: 'aave-v3', name: 'Aave V3 Pool', tags: ['lending', 'defi'], confidence: 0.99 },
  
  // ═══════════════════════════════════════════════════════════════
  // FUNDS / SMART MONEY
  // ═══════════════════════════════════════════════════════════════
  
  // Jump Trading (example - would need verification)
  { chainId: 1, address: '0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9', labelType: 'FUND', entityId: 'jump-crypto', name: 'Jump Crypto', tags: ['mm', 'trading'], confidence: 0.80 },
  
  // Wintermute (example - would need verification)
  { chainId: 1, address: '0x00000000ae347930bd1e7b0f35588b92280f9e75', labelType: 'FUND', entityId: 'wintermute', name: 'Wintermute', tags: ['mm', 'trading'], confidence: 0.80 },
];
