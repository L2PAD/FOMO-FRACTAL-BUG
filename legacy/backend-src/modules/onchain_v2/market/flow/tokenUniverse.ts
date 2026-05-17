/**
 * OnChain V2 — Token Universe
 * =============================
 * 
 * STEP 4: Expanded token list per chain for coverage expansion
 * 
 * Structure: TOKENS_BY_CHAIN[chainId][address.toLowerCase()] = TokenInfo
 */

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface TokenInfo {
  symbol: string;
  name: string;
  decimals: number;
  isStable?: boolean;
  isBase?: boolean;
  coingeckoId?: string;
}

export type TokenUniverseMap = Record<number, Record<string, TokenInfo>>;

// ═══════════════════════════════════════════════════════════════
// ETHEREUM MAINNET (chainId: 1)
// ═══════════════════════════════════════════════════════════════

const ETH_TOKENS: Record<string, TokenInfo> = {
  // === STABLES ===
  '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48': { symbol: 'USDC', name: 'USD Coin', decimals: 6, isStable: true },
  '0xdac17f958d2ee523a2206206994597c13d831ec7': { symbol: 'USDT', name: 'Tether USD', decimals: 6, isStable: true },
  '0x6b175474e89094c44da98b954eedeac495271d0f': { symbol: 'DAI', name: 'Dai Stablecoin', decimals: 18, isStable: true },
  '0x853d955acef822db058eb8505911ed77f175b99e': { symbol: 'FRAX', name: 'Frax', decimals: 18, isStable: true },
  '0x4fabb145d64652a948d72533023f6e7a623c7c53': { symbol: 'BUSD', name: 'Binance USD', decimals: 18, isStable: true },
  '0x0000000000085d4780b73119b644ae5ecd22b376': { symbol: 'TUSD', name: 'TrueUSD', decimals: 18, isStable: true },
  '0x8e870d67f660d95d5be530380d0ec0bd388289e1': { symbol: 'USDP', name: 'Pax Dollar', decimals: 18, isStable: true },
  
  // === BASE TOKENS ===
  '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2': { symbol: 'WETH', name: 'Wrapped Ether', decimals: 18, isBase: true },
  '0x2260fac5e5542a773aa44fbcfedf7c193bc2c599': { symbol: 'WBTC', name: 'Wrapped BTC', decimals: 8, isBase: true },
  
  // === DeFi MAJORS ===
  '0x514910771af9ca656af840dff83e8264ecf986ca': { symbol: 'LINK', name: 'Chainlink', decimals: 18, coingeckoId: 'chainlink' },
  '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984': { symbol: 'UNI', name: 'Uniswap', decimals: 18, coingeckoId: 'uniswap' },
  '0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9': { symbol: 'AAVE', name: 'Aave', decimals: 18, coingeckoId: 'aave' },
  '0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2': { symbol: 'MKR', name: 'Maker', decimals: 18, coingeckoId: 'maker' },
  '0xc011a73ee8576fb46f5e1c5751ca3b9fe0af2a6f': { symbol: 'SNX', name: 'Synthetix', decimals: 18, coingeckoId: 'synthetix-network-token' },
  '0xd533a949740bb3306d119cc777fa900ba034cd52': { symbol: 'CRV', name: 'Curve DAO', decimals: 18, coingeckoId: 'curve-dao-token' },
  '0xba100000625a3754423978a60c9317c58a424e3d': { symbol: 'BAL', name: 'Balancer', decimals: 18, coingeckoId: 'balancer' },
  '0x111111111117dc0aa78b770fa6a738034120c302': { symbol: '1INCH', name: '1inch', decimals: 18, coingeckoId: '1inch' },
  '0x6b3595068778dd592e39a122f4f5a5cf09c90fe2': { symbol: 'SUSHI', name: 'SushiSwap', decimals: 18, coingeckoId: 'sushi' },
  '0xc00e94cb662c3520282e6f5717214004a7f26888': { symbol: 'COMP', name: 'Compound', decimals: 18, coingeckoId: 'compound-governance-token' },
  
  // === LSD / Liquid Staking ===
  '0x5a98fcbea516cf06857215779fd812ca3bef1b32': { symbol: 'LDO', name: 'Lido DAO', decimals: 18, coingeckoId: 'lido-dao' },
  '0xae78736cd615f374d3085123a210448e74fc6393': { symbol: 'rETH', name: 'Rocket Pool ETH', decimals: 18, coingeckoId: 'rocket-pool-eth' },
  '0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0': { symbol: 'wstETH', name: 'Wrapped stETH', decimals: 18, coingeckoId: 'wrapped-steth' },
  '0xbe9895146f7af43049ca1c1ae358b0541ea49704': { symbol: 'cbETH', name: 'Coinbase ETH', decimals: 18, coingeckoId: 'coinbase-wrapped-staked-eth' },
  '0xac3e018457b222d93114458476f3e3416abbe38f': { symbol: 'sfrxETH', name: 'Staked Frax ETH', decimals: 18, coingeckoId: 'staked-frax-ether' },
  
  // === L2 TOKENS (ERC20 on mainnet) ===
  '0xb50721bcf8d664c30412cfbc6cf7a15145234ad1': { symbol: 'ARB', name: 'Arbitrum', decimals: 18, coingeckoId: 'arbitrum' },
  '0x4200000000000000000000000000000000000042': { symbol: 'OP', name: 'Optimism', decimals: 18, coingeckoId: 'optimism' },
  '0x7d1afa7b718fb893db30a3abc0cfc608aacfebb0': { symbol: 'MATIC', name: 'Polygon', decimals: 18, coingeckoId: 'matic-network' },
  
  // === MEMES ===
  '0x6982508145454ce325ddbe47a25d4ec3d2311933': { symbol: 'PEPE', name: 'Pepe', decimals: 18, coingeckoId: 'pepe' },
  '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce': { symbol: 'SHIB', name: 'Shiba Inu', decimals: 18, coingeckoId: 'shiba-inu' },
  '0x761d38e5ddf6ccf6cf7c55759d5210750b5d60f3': { symbol: 'ELON', name: 'Dogelon Mars', decimals: 18, coingeckoId: 'dogelon-mars' },
  '0x4d224452801aced8b2f0aebe155379bb5d594381': { symbol: 'APE', name: 'ApeCoin', decimals: 18, coingeckoId: 'apecoin' },
  '0xb131f4a55907b10d1f0a50d8ab8fa09ec342cd74': { symbol: 'MEME', name: 'Memecoin', decimals: 18, coingeckoId: 'memecoin-2' },
  '0x163f8c2467924be0ae7b5347228cabf260318753': { symbol: 'WLD', name: 'Worldcoin', decimals: 18, coingeckoId: 'worldcoin' },
  
  // === GAMING / METAVERSE ===
  '0x3845badade8e6dff049820680d1f14bd3903a5d0': { symbol: 'SAND', name: 'The Sandbox', decimals: 18, coingeckoId: 'the-sandbox' },
  '0x0f5d2fb29fb7d3cfee444a200298f468908cc942': { symbol: 'MANA', name: 'Decentraland', decimals: 18, coingeckoId: 'decentraland' },
  '0xbb0e17ef65f82ab018d8edd776e8dd940327b28b': { symbol: 'AXS', name: 'Axie Infinity', decimals: 18, coingeckoId: 'axie-infinity' },
  '0xf629cbd94d3791c9250152bd8dfbdf380e2a3b9c': { symbol: 'ENJ', name: 'Enjin Coin', decimals: 18, coingeckoId: 'enjincoin' },
  '0x15d4c048f83bd7e37d49ea4c83a07267ec4203da': { symbol: 'GALA', name: 'Gala', decimals: 8, coingeckoId: 'gala' },
  '0x4c19596f5aaff459fa38b0f7ed92f11ae6543784': { symbol: 'TRU', name: 'TrueFi', decimals: 8, coingeckoId: 'truefi' },
  
  // === AI / COMPUTE ===
  '0xd31a59c85ae9d8edefec411d448f90841571b89c': { symbol: 'SOL', name: 'Wrapped SOL', decimals: 9, coingeckoId: 'solana' },
  '0x6de037ef9ad2725eb40118bb1702ebb27e4aeb24': { symbol: 'RNDR', name: 'Render', decimals: 18, coingeckoId: 'render-token' },
  '0xb64ef51c888972c908cfacf59b47c1afbc0ab8ac': { symbol: 'STORJ', name: 'Storj', decimals: 8, coingeckoId: 'storj' },
  '0x0d8775f648430679a709e98d2b0cb6250d2887ef': { symbol: 'BAT', name: 'Basic Attention', decimals: 18, coingeckoId: 'basic-attention-token' },
  '0x0bc529c00c6401aef6d220be8c6ea1667f6ad93e': { symbol: 'YFI', name: 'yearn.finance', decimals: 18, coingeckoId: 'yearn-finance' },
  
  // === OTHER ALTS ===
  '0x2af5d2ad76741191d15dfe7bf6ac92d4bd912ca3': { symbol: 'LEO', name: 'UNUS SED LEO', decimals: 18, coingeckoId: 'leo-token' },
  '0x0d438f3b5175bebc262bf23753c1e53d03432bde': { symbol: 'wNXM', name: 'Wrapped NXM', decimals: 18, coingeckoId: 'wrapped-nxm' },
  '0x6810e776880c02933d47db1b9fc05908e5386b96': { symbol: 'GNO', name: 'Gnosis', decimals: 18, coingeckoId: 'gnosis' },
  '0x4e3fbd56cd56c3e72c1403e103b45db9da5b9d2b': { symbol: 'CVX', name: 'Convex Finance', decimals: 18, coingeckoId: 'convex-finance' },
  '0x57ab1ec28d129707052df4df418d58a2d46d5f51': { symbol: 'sUSD', name: 'Synth sUSD', decimals: 18, isStable: true },
  '0x5283d291dbcf85356a21ba090e6db59121208b44': { symbol: 'BLUR', name: 'Blur', decimals: 18, coingeckoId: 'blur' },
  '0x64aa3364f17a4d01c6f1751fd97c2bd3d7e7f1d5': { symbol: 'OHM', name: 'Olympus', decimals: 9, coingeckoId: 'olympus' },
  '0xc18360217d8f7ab5e7c516566761ea12ce7f9d72': { symbol: 'ENS', name: 'Ethereum Name Service', decimals: 18, coingeckoId: 'ethereum-name-service' },
  '0x62d0a8458ed7719fdaf978fe5929c6d342b0bfce': { symbol: 'BEAM', name: 'Beam', decimals: 18, coingeckoId: 'beam-3' },
};

// ═══════════════════════════════════════════════════════════════
// ARBITRUM (chainId: 42161)
// ═══════════════════════════════════════════════════════════════

const ARB_TOKENS: Record<string, TokenInfo> = {
  // Stables
  '0xaf88d065e77c8cc2239327c5edb3a432268e5831': { symbol: 'USDC', name: 'USD Coin', decimals: 6, isStable: true },
  '0xff970a61a04b1ca14834a43f5de4533ebddb5cc8': { symbol: 'USDC.e', name: 'Bridged USDC', decimals: 6, isStable: true },
  '0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9': { symbol: 'USDT', name: 'Tether USD', decimals: 6, isStable: true },
  '0xda10009cbd5d07dd0cecc66161fc93d7c9000da1': { symbol: 'DAI', name: 'Dai Stablecoin', decimals: 18, isStable: true },
  '0x17fc002b466eec40dae837fc4be5c67993ddbd6f': { symbol: 'FRAX', name: 'Frax', decimals: 18, isStable: true },
  
  // Base
  '0x82af49447d8a07e3bd95bd0d56f35241523fbab1': { symbol: 'WETH', name: 'Wrapped Ether', decimals: 18, isBase: true },
  '0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f': { symbol: 'WBTC', name: 'Wrapped BTC', decimals: 8, isBase: true },
  
  // Native
  '0x912ce59144191c1204e64559fe8253a0e49e6548': { symbol: 'ARB', name: 'Arbitrum', decimals: 18, coingeckoId: 'arbitrum' },
  
  // DeFi
  '0xfc5a1a6eb076a2c7ad06ed22c90d7e710e35ad0a': { symbol: 'GMX', name: 'GMX', decimals: 18, coingeckoId: 'gmx' },
  '0xf97f4df75117a78c1a5a0dbb814af92458539fb4': { symbol: 'LINK', name: 'Chainlink', decimals: 18, coingeckoId: 'chainlink' },
  '0xfa7f8980b0f1e64a2062791cc3b0871572f1f7f0': { symbol: 'UNI', name: 'Uniswap', decimals: 18, coingeckoId: 'uniswap' },
  '0xba5ddd1f9d7f570dc94a51479a000e3bce967196': { symbol: 'AAVE', name: 'Aave', decimals: 18, coingeckoId: 'aave' },
  '0x6c2c06790b3e3e3c38e12ee22f8183b37a13ee55': { symbol: 'DPX', name: 'Dopex', decimals: 18, coingeckoId: 'dopex' },
  '0x539bde0d7dbd336b79148aa742883198bbf60342': { symbol: 'MAGIC', name: 'Magic', decimals: 18, coingeckoId: 'magic' },
  '0x3d9907f9a368ad0a51be60f7da3b97cf940982d8': { symbol: 'GRAIL', name: 'Camelot', decimals: 18, coingeckoId: 'camelot-token' },
  '0x5979d7b546e38e414f7e9822514be443a4800529': { symbol: 'wstETH', name: 'Wrapped stETH', decimals: 18, coingeckoId: 'wrapped-steth' },
  '0x13ad51ed4f1b7e9dc168d8a00cb3f4ddd85efa60': { symbol: 'LDO', name: 'Lido DAO', decimals: 18, coingeckoId: 'lido-dao' },
  '0x6694340fc020c5e6b96567843da2df01b2ce1eb6': { symbol: 'STG', name: 'Stargate', decimals: 18, coingeckoId: 'stargate-finance' },
  '0xd4d42f0b6def4ce0383636770ef773390d85c61a': { symbol: 'SUSHI', name: 'SushiSwap', decimals: 18, coingeckoId: 'sushi' },
  '0x354a6da3fcde098f8389cad84b0182725c6c91de': { symbol: 'COMP', name: 'Compound', decimals: 18, coingeckoId: 'compound-governance-token' },
  '0xec70dcb4a1efa46b8f2d97c310c9c4790ba5ffa8': { symbol: 'rETH', name: 'Rocket Pool ETH', decimals: 18, coingeckoId: 'rocket-pool-eth' },
  '0x0c880f6761f1af8d9aa9c466984b80dab9a8c9e8': { symbol: 'PENDLE', name: 'Pendle', decimals: 18, coingeckoId: 'pendle' },
};

// ═══════════════════════════════════════════════════════════════
// OPTIMISM (chainId: 10)
// ═══════════════════════════════════════════════════════════════

const OP_TOKENS: Record<string, TokenInfo> = {
  // Stables
  '0x0b2c639c533813f4aa9d7837caf62653d097ff85': { symbol: 'USDC', name: 'USD Coin', decimals: 6, isStable: true },
  '0x7f5c764cbc14f9669b88837ca1490cca17c31607': { symbol: 'USDC.e', name: 'Bridged USDC', decimals: 6, isStable: true },
  '0x94b008aa00579c1307b0ef2c499ad98a8ce58e58': { symbol: 'USDT', name: 'Tether USD', decimals: 6, isStable: true },
  '0xda10009cbd5d07dd0cecc66161fc93d7c9000da1': { symbol: 'DAI', name: 'Dai Stablecoin', decimals: 18, isStable: true },
  
  // Base
  '0x4200000000000000000000000000000000000006': { symbol: 'WETH', name: 'Wrapped Ether', decimals: 18, isBase: true },
  '0x68f180fcce6836688e9084f035309e29bf0a2095': { symbol: 'WBTC', name: 'Wrapped BTC', decimals: 8, isBase: true },
  
  // Native
  '0x4200000000000000000000000000000000000042': { symbol: 'OP', name: 'Optimism', decimals: 18, coingeckoId: 'optimism' },
  
  // DeFi
  '0x350a791bfc2c21f9ed5d10980dad2e2638ffa7f6': { symbol: 'LINK', name: 'Chainlink', decimals: 18, coingeckoId: 'chainlink' },
  '0x6fd9d7ad17242c41f7131d257212c54a0e816691': { symbol: 'UNI', name: 'Uniswap', decimals: 18, coingeckoId: 'uniswap' },
  '0x76fb31fb4af56892a25e32cfc43de717950c9278': { symbol: 'AAVE', name: 'Aave', decimals: 18, coingeckoId: 'aave' },
  '0x9e1028f5f1d5ede59748ffcee5532509976840e0': { symbol: 'PERP', name: 'Perpetual Protocol', decimals: 18, coingeckoId: 'perpetual-protocol' },
  '0x1f32b1c2345538c0c6f582fcb022739c4a194ebb': { symbol: 'wstETH', name: 'Wrapped stETH', decimals: 18, coingeckoId: 'wrapped-steth' },
  '0xfdb794692724153d1488ccdbe0c56c252596735f': { symbol: 'LDO', name: 'Lido DAO', decimals: 18, coingeckoId: 'lido-dao' },
  '0x9560e827af36c94d2ac33a39bce1fe78631088db': { symbol: 'VELO', name: 'Velodrome', decimals: 18, coingeckoId: 'velodrome-finance' },
  '0x8c6f28f2f1a3c87f0f938b96d27520d9751ec8d9': { symbol: 'sUSD', name: 'Synth sUSD', decimals: 18, isStable: true },
  '0x8700daec35af8ff88c16bdf0418774cb3d7599b4': { symbol: 'SNX', name: 'Synthetix', decimals: 18, coingeckoId: 'synthetix-network-token' },
  '0x9bcef72be871e61ed4fbbc7630889bee758eb81d': { symbol: 'rETH', name: 'Rocket Pool ETH', decimals: 18, coingeckoId: 'rocket-pool-eth' },
};

// ═══════════════════════════════════════════════════════════════
// BASE (chainId: 8453)
// ═══════════════════════════════════════════════════════════════

const BASE_TOKENS: Record<string, TokenInfo> = {
  // Stables
  '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913': { symbol: 'USDC', name: 'USD Coin', decimals: 6, isStable: true },
  '0xd9aaec86b65d86f6a7b5b1b0c42ffa531710b6ca': { symbol: 'USDbC', name: 'Bridged USDC', decimals: 6, isStable: true },
  '0x50c5725949a6f0c72e6c4a641f24049a917db0cb': { symbol: 'DAI', name: 'Dai Stablecoin', decimals: 18, isStable: true },
  
  // Base
  '0x4200000000000000000000000000000000000006': { symbol: 'WETH', name: 'Wrapped Ether', decimals: 18, isBase: true },
  
  // DeFi
  '0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452': { symbol: 'wstETH', name: 'Wrapped stETH', decimals: 18, coingeckoId: 'wrapped-steth' },
  '0x2ae3f1ec7f1f5012cfeab0185bfc7aa3cf0dec22': { symbol: 'cbETH', name: 'Coinbase ETH', decimals: 18, coingeckoId: 'coinbase-wrapped-staked-eth' },
  '0xb6fe221fe9eef5aba221c348ba20a1bf5e73624c': { symbol: 'rETH', name: 'Rocket Pool ETH', decimals: 18, coingeckoId: 'rocket-pool-eth' },
  '0x940181a94a35a4569e4529a3cdfb74e38fd98631': { symbol: 'AERO', name: 'Aerodrome', decimals: 18, coingeckoId: 'aerodrome-finance' },
  '0x0578d8a44db98b23bf096a382e016e29a5ce0ffe': { symbol: 'HIGHER', name: 'Higher', decimals: 18, coingeckoId: 'higher' },
  '0x532f27101965dd16442e59d40670faf5ebb142e4': { symbol: 'BRETT', name: 'Brett', decimals: 18, coingeckoId: 'brett' },
  '0x4ed4e862860bed51a9570b96d89af5e1b0efefed': { symbol: 'DEGEN', name: 'Degen', decimals: 18, coingeckoId: 'degen-base' },
  '0xac1bd2486aaf3b5c0fc3fd868558b082a531b2b4': { symbol: 'TOSHI', name: 'Toshi', decimals: 18, coingeckoId: 'toshi' },
};

// ═══════════════════════════════════════════════════════════════
// COMBINED EXPORT
// ═══════════════════════════════════════════════════════════════

export const TOKENS_BY_CHAIN: TokenUniverseMap = {
  1: ETH_TOKENS,
  42161: ARB_TOKENS,
  10: OP_TOKENS,
  8453: BASE_TOKENS,
};

/**
 * Get token info from universe
 */
export function getTokenFromUniverse(chainId: number, address: string): TokenInfo | null {
  const chain = TOKENS_BY_CHAIN[chainId];
  if (!chain) return null;
  return chain[address.toLowerCase()] || null;
}

/**
 * Get all known addresses for a chain
 */
export function getUniverseAddresses(chainId: number): string[] {
  const chain = TOKENS_BY_CHAIN[chainId];
  if (!chain) return [];
  return Object.keys(chain);
}

/**
 * Get alt tokens only (not stables/base)
 */
export function getAltTokenAddresses(chainId: number): string[] {
  const chain = TOKENS_BY_CHAIN[chainId];
  if (!chain) return [];
  return Object.entries(chain)
    .filter(([_, info]) => !info.isStable && !info.isBase)
    .map(([addr]) => addr);
}

/**
 * Get stable token addresses
 */
export function getStableAddresses(chainId: number): string[] {
  const chain = TOKENS_BY_CHAIN[chainId];
  if (!chain) return [];
  return Object.entries(chain)
    .filter(([_, info]) => info.isStable)
    .map(([addr]) => addr);
}

/**
 * Get base token addresses
 */
export function getBaseAddresses(chainId: number): string[] {
  const chain = TOKENS_BY_CHAIN[chainId];
  if (!chain) return [];
  return Object.entries(chain)
    .filter(([_, info]) => info.isBase)
    .map(([addr]) => addr);
}

// Stats
const stats = Object.entries(TOKENS_BY_CHAIN).map(([id, tokens]) => ({
  chainId: id,
  count: Object.keys(tokens).length,
}));

console.log(`[OnChain V2] Token Universe loaded: ${stats.map(s => `${s.chainId}=${s.count}`).join(', ')}`);
