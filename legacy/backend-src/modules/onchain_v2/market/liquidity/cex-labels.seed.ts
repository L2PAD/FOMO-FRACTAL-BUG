/**
 * CEX Labels Seed
 * ================
 * 
 * PHASE 2.3: Exchange Address Labels for Exchange Pressure Feature
 * 
 * These are well-known CEX hot wallet addresses from public sources.
 * Sources: Etherscan labels, Arkham Intelligence, Nansen
 */

export interface CexLabelSeed {
  address: string;
  name: string;
  subtype: 'hot_wallet' | 'cold_wallet' | 'deposit';
  source: string;
}

export const CEX_LABELS: CexLabelSeed[] = [
  // ═══════════════════════════════════════════════════════════════
  // BINANCE
  // ═══════════════════════════════════════════════════════════════
  {
    address: '0x28c6c06298d514db089934071355e5743bf21d60',
    name: 'binance',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },
  {
    address: '0x21a31ee1afc51d94c2efccaa2092ad1028285549',
    name: 'binance',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },
  {
    address: '0xdfd5293d8e347dfe59e90efd55b2956a1343963d',
    name: 'binance',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },
  {
    address: '0x56eddb7aa87536c09ccc2793473599fd21a8b17f',
    name: 'binance',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },
  {
    address: '0x9696f59e4d72e237be84ffd425dcad154bf96976',
    name: 'binance',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },
  {
    address: '0xf977814e90da44bfa03b6295a0616a897441acec',
    name: 'binance',
    subtype: 'cold_wallet',
    source: 'etherscan',
  },
  {
    address: '0xbe0eb53f46cd790cd13851d5eff43d12404d33e8',
    name: 'binance',
    subtype: 'cold_wallet',
    source: 'etherscan',
  },

  // ═══════════════════════════════════════════════════════════════
  // COINBASE
  // ═══════════════════════════════════════════════════════════════
  {
    address: '0x503828976d22510aad0201ac7ec88293211d23da',
    name: 'coinbase',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },
  {
    address: '0x71660c4005ba85c37ccec55d0c4493e66fe775d3',
    name: 'coinbase',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },
  {
    address: '0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43',
    name: 'coinbase',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },
  {
    address: '0x77134cbc06cb00b66f4c7e623d5fdbf6777635ec',
    name: 'coinbase',
    subtype: 'cold_wallet',
    source: 'etherscan',
  },

  // ═══════════════════════════════════════════════════════════════
  // KRAKEN
  // ═══════════════════════════════════════════════════════════════
  {
    address: '0x2910543af39aba0cd09dbb2d50200b3e800a63d2',
    name: 'kraken',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },
  {
    address: '0x0a869d79a7052c7f1b55a8ebabbea3420f0d1e13',
    name: 'kraken',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },
  {
    address: '0xe853c56864a2ebe4576a807d26fdc4a0ada51919',
    name: 'kraken',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },
  {
    address: '0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0',
    name: 'kraken',
    subtype: 'cold_wallet',
    source: 'etherscan',
  },

  // ═══════════════════════════════════════════════════════════════
  // OKX
  // ═══════════════════════════════════════════════════════════════
  {
    address: '0x6cc5f688a315f3dc28a7781717a9a798a59fda7b',
    name: 'okx',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },
  {
    address: '0x236f9f97e0e62388479bf9e5ba4889e46b0273c3',
    name: 'okx',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },

  // ═══════════════════════════════════════════════════════════════
  // BYBIT
  // ═══════════════════════════════════════════════════════════════
  {
    address: '0xf89d7b9c864f589bbf53a82105107622b35eaa40',
    name: 'bybit',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },

  // ═══════════════════════════════════════════════════════════════
  // KUCOIN
  // ═══════════════════════════════════════════════════════════════
  {
    address: '0xf16e9b0d03470827a95cdfd0cb8a8a3b46969b91',
    name: 'kucoin',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },
  {
    address: '0x88bd4d3e2997371bceefe8d9386c6b5b4de60346',
    name: 'kucoin',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },

  // ═══════════════════════════════════════════════════════════════
  // GATE.IO
  // ═══════════════════════════════════════════════════════════════
  {
    address: '0x0d0707963952f2fba59dd06f2b425ace40b492fe',
    name: 'gate_io',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },
  {
    address: '0x1c4b70a3968436b9a0a9cf5205c787eb81bb558c',
    name: 'gate_io',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },

  // ═══════════════════════════════════════════════════════════════
  // HUOBI (HTX)
  // ═══════════════════════════════════════════════════════════════
  {
    address: '0x46705dfff24256421a05d056c29e81bdc09723b8',
    name: 'huobi',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },
  {
    address: '0x5c985e89dde482efe97ea9f1950ad149eb73829b',
    name: 'huobi',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },

  // ═══════════════════════════════════════════════════════════════
  // GEMINI
  // ═══════════════════════════════════════════════════════════════
  {
    address: '0xd24400ae8bfebb18ca49be86258a3c749cf46853',
    name: 'gemini',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },
  {
    address: '0x6fc82a5fe25a5cdb58bc74600a40a69c065263f8',
    name: 'gemini',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },

  // ═══════════════════════════════════════════════════════════════
  // BITFINEX
  // ═══════════════════════════════════════════════════════════════
  {
    address: '0x1151314c646ce4e0efd76d1af4760ae66a9fe30f',
    name: 'bitfinex',
    subtype: 'hot_wallet',
    source: 'etherscan',
  },
  {
    address: '0x742d35cc6634c0532925a3b844bc454e4438f44e',
    name: 'bitfinex',
    subtype: 'cold_wallet',
    source: 'etherscan',
  },
];

console.log(`[CEX Labels] Seed data loaded: ${CEX_LABELS.length} addresses`);
