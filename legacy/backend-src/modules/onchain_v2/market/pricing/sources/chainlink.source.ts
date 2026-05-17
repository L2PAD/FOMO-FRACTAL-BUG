/**
 * OnChain V2 — Chainlink Price Source
 * =====================================
 * 
 * STEP 1: USD Valuation Layer
 * Gets token prices from Chainlink price feeds.
 * Highest confidence source (0.95) — oracle-grade data.
 */

import type { PriceProvider, PriceQuote, PriceSource } from '../pricing.types';
import { rpcPool, RpcChainId } from '../../../rpc-pool';

// Chainlink Feed Registry (ETH Mainnet)
const CHAINLINK_FEEDS: Record<string, string> = {
  // ETH/USD for WETH
  '1:0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2': '0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419',
  // BTC/USD for WBTC
  '1:0x2260fac5e5542a773aa44fbcfedf7c193bc2c599': '0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c',
  // LINK/USD
  '1:0x514910771af9ca656af840dff83e8264ecf986ca': '0x2c1d072e956AFFC0D435Cb7AC38EF18d24d9127c',
  // UNI/USD
  '1:0x1f9840a85d5af5bf1d1762f925bdaddc4201f984': '0x553303d460EE0afB37EdFf9bE42922D8FF63220e',
  // AAVE/USD
  '1:0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9': '0x547a514d5e3769680Ce22B2361c10Ea13619e8a9',
  // USDC/USD
  '1:0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48': '0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6',
  // USDT/USD
  '1:0xdac17f958d2ee523a2206206994597c13d831ec7': '0x3E7d1eAB13ad0104d2750B8863b489D65364e32D',
  // DAI/USD
  '1:0x6b175474e89094c44da98b954eedeac495271d0f': '0xAed0c38402a5d19df6E4c03F4E2DceD6e29c1ee9',
};

export class ChainlinkSource implements PriceProvider {
  readonly name: PriceSource = 'CHAINLINK';
  
  async getUsdPrice(args: { chainId: number; token: string }): Promise<PriceQuote | null> {
    const token = args.token.toLowerCase();
    const key = `${args.chainId}:${token}`;
    
    const feedAddress = CHAINLINK_FEEDS[key];
    if (!feedAddress) return null;
    
    try {
      // Get decimals
      const decimalsData = await this.callContract(args.chainId as RpcChainId, feedAddress, '0x313ce567');
      const decimals = parseInt(decimalsData, 16);
      
      if (!Number.isFinite(decimals) || decimals < 0 || decimals > 18) {
        return null;
      }
      
      // Get latestRoundData
      const roundData = await this.callContract(args.chainId as RpcChainId, feedAddress, '0xfeaf968c');
      
      if (!roundData || roundData.length < 130) {
        return null;
      }
      
      const hex = roundData.slice(2);
      const answerHex = hex.slice(64, 128);
      const updatedAtHex = hex.slice(192, 256);
      
      const answer = this.parseSignedInt256(answerHex);
      const oracleUpdatedAt = parseInt(updatedAtHex, 16);
      
      const price = Number(answer) / Math.pow(10, decimals);
      
      if (!Number.isFinite(price) || price <= 0) {
        console.warn(`[ChainlinkSource] Invalid price for ${token}: ${price}`);
        return null;
      }
      
      const staleThreshold = 24 * 60 * 60;
      const ageSeconds = Math.floor(Date.now() / 1000) - oracleUpdatedAt;
      let confidence = 0.95;
      
      if (ageSeconds > staleThreshold) {
        confidence = 0.6;
        console.warn(`[ChainlinkSource] Stale data for ${token}: ${ageSeconds}s old`);
      }
      
      return {
        chainId: args.chainId,
        token,
        priceUsd: price,
        confidence,
        source: 'CHAINLINK',
        updatedAt: Date.now(),
        meta: { feedAddress, oracleUpdatedAt, oracleDecimals: decimals, ageSeconds },
      };
    } catch (error) {
      console.error(`[ChainlinkSource] Error fetching price for ${token}:`, error);
      return null;
    }
  }
  
  private async callContract(chainId: RpcChainId, to: string, data: string): Promise<string> {
    return rpcPool.call<string>(chainId, 'eth_call', [{ to, data }, 'latest']);
  }
  
  private parseSignedInt256(hex: string): bigint {
    const value = BigInt('0x' + hex);
    const isNegative = (value >> 255n) === 1n;
    if (isNegative) return value - (1n << 256n);
    return value;
  }
  
  hasFeed(chainId: number, token: string): boolean {
    return `${chainId}:${token.toLowerCase()}` in CHAINLINK_FEEDS;
  }
}

export const chainlinkSource = new ChainlinkSource();
console.log('[OnChain V2] Chainlink Price Source loaded');
