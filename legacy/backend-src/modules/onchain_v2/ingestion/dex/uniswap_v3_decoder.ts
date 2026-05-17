/**
 * OnChain V2 — Uniswap V3 Swap Decoder
 * =====================================
 * 
 * Decodes Uniswap V3 Swap events from raw logs.
 * 
 * Event signature:
 * Swap(address indexed sender, address indexed recipient, int256 amount0, int256 amount1, uint160 sqrtPriceX96, uint128 liquidity, int24 tick)
 */

import { ethers } from 'ethers';

// Uniswap V3 Swap event topic
export const UNISWAP_V3_SWAP_TOPIC = ethers.id(
  'Swap(address,address,int256,int256,uint160,uint128,int24)'
);

// Minimal ABI for decoding
const SWAP_ABI = [
  'event Swap(address indexed sender, address indexed recipient, int256 amount0, int256 amount1, uint160 sqrtPriceX96, uint128 liquidity, int24 tick)'
];

const swapInterface = new ethers.Interface(SWAP_ABI);

export interface DecodedSwap {
  sender: string;
  recipient: string;
  amount0: string;  // BigInt as string (can be negative)
  amount1: string;  // BigInt as string (can be negative)
  sqrtPriceX96: string;
  liquidity: string;
  tick: number;
}

export interface RawLog {
  address: string;
  topics: string[];
  data: string;
  blockNumber: number;
  blockHash?: string;
  transactionHash: string;
  transactionIndex: number;
  logIndex: number;
}

/**
 * Check if a log is a Uniswap V3 Swap event
 */
export function isUniswapV3Swap(log: RawLog): boolean {
  return log.topics[0] === UNISWAP_V3_SWAP_TOPIC;
}

/**
 * Decode a Uniswap V3 Swap event from raw log
 */
export function decodeUniswapV3Swap(log: RawLog): DecodedSwap | null {
  try {
    if (!isUniswapV3Swap(log)) {
      return null;
    }

    // Parse the log using ethers
    const parsed = swapInterface.parseLog({
      topics: log.topics as string[],
      data: log.data,
    });

    if (!parsed) {
      return null;
    }

    return {
      sender: parsed.args.sender.toLowerCase(),
      recipient: parsed.args.recipient.toLowerCase(),
      amount0: parsed.args.amount0.toString(),
      amount1: parsed.args.amount1.toString(),
      sqrtPriceX96: parsed.args.sqrtPriceX96.toString(),
      liquidity: parsed.args.liquidity.toString(),
      tick: Number(parsed.args.tick),
    };
  } catch (err) {
    // Log decode errors for debugging but don't crash
    console.error('[UniswapV3Decoder] Failed to decode swap:', err);
    return null;
  }
}

/**
 * Determine swap direction relative to token0
 * - Positive amount0 = token0 going INTO pool = SELL token0
 * - Negative amount0 = token0 going OUT of pool = BUY token0
 */
export function determineSwapDirection(amount0: string): 'buy' | 'sell' | 'unknown' {
  try {
    const amt = BigInt(amount0);
    if (amt > 0n) return 'sell';  // Token0 going in = selling token0
    if (amt < 0n) return 'buy';   // Token0 going out = buying token0
    return 'unknown';
  } catch {
    return 'unknown';
  }
}

/**
 * Check if swap is a "whale" swap based on raw amounts
 * This is a rough heuristic - real implementation should use USD values
 */
export function isWhaleSwap(amount0: string, amount1: string, decimals0 = 18, decimals1 = 18): boolean {
  try {
    const amt0 = Math.abs(Number(amount0) / Math.pow(10, decimals0));
    const amt1 = Math.abs(Number(amount1) / Math.pow(10, decimals1));
    
    // Very rough heuristic: > 100 ETH or > 100,000 USDC equivalent
    // This should be refined with actual USD pricing
    return amt0 > 100 || amt1 > 100000;
  } catch {
    return false;
  }
}

// Well-known Uniswap V3 pools on Ethereum mainnet
export const MAINNET_POOLS = {
  // WETH/USDC pools
  'WETH_USDC_500': '0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640',   // 0.05% fee
  'WETH_USDC_3000': '0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8',  // 0.3% fee
  
  // WETH/USDT pools
  'WETH_USDT_500': '0x11b815efb8f581194ae79006d24e0d814b7697f6',   // 0.05% fee
  'WETH_USDT_3000': '0x4e68ccd3e89f51c3074ca5072bbac773960dfa36',  // 0.3% fee
  
  // WBTC/WETH pools
  'WBTC_WETH_500': '0x4585fe77225b41b697c938b018e2ac67ac5a20c0',   // 0.05% fee
  'WBTC_WETH_3000': '0xcbcdf9626bc03e24f779434178a73a0b4bad62ed',  // 0.3% fee
  
  // WETH/DAI pool
  'WETH_DAI_3000': '0xc2e9f25be6257c210d7adf0d4cd6e3e881ba25f8',   // 0.3% fee
};

// Well-known Uniswap V3 pools on Arbitrum
export const ARBITRUM_POOLS = {
  // WETH/USDC pools
  'WETH_USDC_500': '0xc31e54c7a869b9fcbecc14363cf510d1c41fa443',   // 0.05% fee
  'WETH_USDC_3000': '0x17c14d2c404d167802b16c450d3c99f88f2c4f4d',  // 0.3% fee
  
  // WETH/USDT pools
  'WETH_USDT_500': '0x641c00a822e8b671738d32a431a4fb6074e5c79d',   // 0.05% fee
  
  // ARB/USDC pools
  'ARB_USDC_500': '0xcda53b1f66614552f834ceef361a8d12b0b8dad8',    // 0.05% fee
  'ARB_USDC_3000': '0xb0f6ca40411360c03d41c5ffc5f179b8403cdcf8',   // 0.3% fee
  
  // ARB/WETH pools
  'ARB_WETH_500': '0xc6f780497a95e246eb9449f5e4770916dcd6396a',    // 0.05% fee
  'ARB_WETH_3000': '0xe51635ae8136aBAc44906A8f230C2D235E9c195F',   // 0.3% fee
  
  // GMX/WETH pool
  'GMX_WETH_3000': '0x80a9ae39310abf666a87c743d6ebbd0e8c42158e',   // 0.3% fee
  
  // WBTC/WETH pool
  'WBTC_WETH_500': '0x2f5e87c9312fa29aed5c179e456625d79015299c',   // 0.05% fee
};

// Well-known Uniswap V3 pools on Optimism
export const OPTIMISM_POOLS = {
  // WETH/USDC pools
  'WETH_USDC_500': '0x85149247691df622eaf1a8bd0cafd40bc45154a9',   // 0.05% fee
  'WETH_USDC_3000': '0xc1738d90e2e26c35784a0d3e3d8a9f795074bca4', // 0.3% fee
  
  // WETH/USDT pool
  'WETH_USDT_500': '0xc858a329bf053be78d6239c4a4343b8fbd21472b',   // 0.05% fee
  
  // OP/USDC pool
  'OP_USDC_3000': '0x1c3140ab59d6caf9fa7459c6f83d4b52ba881d36',    // 0.3% fee
  
  // OP/WETH pool
  'OP_WETH_3000': '0x68f5c0a2de713a54991e01858fd27a3832401849',    // 0.3% fee
  
  // WBTC/WETH pool
  'WBTC_WETH_500': '0x73b14a78a0d396c521f954532d43fd5fce7c76c0',   // 0.05% fee
  
  // wstETH/WETH pool
  'WSTETH_WETH_100': '0xb589969d38ce76d3d7aa319de7133bc9755fd840', // 0.01% fee
};

// Well-known Uniswap V3 pools on Base
export const BASE_POOLS = {
  // WETH/USDC pools
  'WETH_USDC_500': '0xd0b53d9277642d899df5c87a3966a349a798f224',   // 0.05% fee
  'WETH_USDC_3000': '0x4c36388be6f416a29c8d8eee81c771ce6be14b18',  // 0.3% fee
  
  // WETH/USDbC (bridged USDC)
  'WETH_USDbC_500': '0x4c36388be6f416a29c8d8eee81c771ce6be14b18',  // 0.05% fee
  
  // cbETH/WETH pool
  'CBETH_WETH_500': '0x257fcbae4ac6b26a02e4fc5e1a11e4174b5ce395',  // 0.05% fee
  
  // wstETH/WETH pool
  'WSTETH_WETH_100': '0x7ed3f364668cd2b9449a8660974a26a092c64849', // 0.01% fee
  
  // DEGEN/WETH pool
  'DEGEN_WETH_3000': '0xc9034c3e7f58003e6ae0c8438e7c8f4598d5acaa',  // 0.3% fee
  
  // AERO/WETH pool
  'AERO_WETH_3000': '0x7e8dda0d1e4fb4a8b8e7aa1773b5152bcf01c108',  // 0.3% fee
};

// Token addresses for reference
export const MAINNET_TOKENS = {
  WETH: '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2',
  USDC: '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
  USDT: '0xdac17f958d2ee523a2206206994597c13d831ec7',
  WBTC: '0x2260fac5e5542a773aa44fbcfedf7c193bc2c599',
  DAI: '0x6b175474e89094c44da98b954eedeac495271d0f',
};

console.log('[OnChain V2] Uniswap V3 Decoder loaded');
