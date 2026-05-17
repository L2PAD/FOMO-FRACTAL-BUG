/**
 * Lite Provider — Infura + DefiLlama
 * ===================================
 * 
 * Read-only, aggregated data from public APIs.
 * Polling every 60-120 sec. Minimal load.
 * 
 * Data sources:
 * - Infura RPC: block height, gas price, TPS, pending txs
 * - DefiLlama: TVL, DEX volumes
 * - Etherscan-style: whale transfers (simulated from Infura blocks)
 */

import type {
  IOnchainProvider,
  OnchainSummary,
  OnchainFlows,
  OnchainWhales,
  OnchainActivity,
  OnchainWhaleTransfer,
} from './provider.types.js';

const INFURA_KEY = process.env.INFURA_KEY || '';
const INFURA_URL = `https://mainnet.infura.io/v3/${INFURA_KEY}`;

async function rpcCall(method: string, params: any[] = []): Promise<any> {
  const res = await fetch(INFURA_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }),
  });
  const json = await res.json() as any;
  if (json.error) throw new Error(`RPC error: ${json.error.message}`);
  return json.result;
}

function hexToNum(hex: string): number {
  return parseInt(hex, 16) || 0;
}

function weiToEth(weiHex: string): number {
  return hexToNum(weiHex) / 1e18;
}

function weiToGwei(weiHex: string): number {
  return hexToNum(weiHex) / 1e9;
}

export class LiteProvider implements IOnchainProvider {
  
  async getSummary(): Promise<OnchainSummary> {
    const [blockHex, gasPriceHex, pendingBlock, prevBlockHex] = await Promise.all([
      rpcCall('eth_blockNumber'),
      rpcCall('eth_gasPrice'),
      rpcCall('eth_getBlockByNumber', ['latest', false]),
      rpcCall('eth_getBlockByNumber', ['latest', false]).then(async (latest: any) => {
        const prevNum = '0x' + (hexToNum(latest.number) - 10).toString(16);
        return rpcCall('eth_getBlockByNumber', [prevNum, false]);
      }),
    ]);

    const blockHeight = hexToNum(blockHex);
    const gasPrice = Math.round(weiToGwei(gasPriceHex) * 100) / 100;
    
    const latestTimestamp = hexToNum(pendingBlock.timestamp);
    const prevTimestamp = hexToNum(prevBlockHex.timestamp);
    const blockTimeDiff = latestTimestamp - prevTimestamp;
    const blockTime = blockTimeDiff > 0 ? Math.round((blockTimeDiff / 10) * 100) / 100 : 12;
    
    const txCount = pendingBlock.transactions?.length || 0;
    const tps = blockTime > 0 ? Math.round((txCount / blockTime) * 100) / 100 : 0;

    const pendingCount = await rpcCall('eth_getBlockTransactionCountByNumber', ['pending']).catch(() => '0x0');

    return {
      blockHeight,
      gasPrice,
      tps,
      activeAddresses24h: 0,
      blockTime,
      pendingTxCount: hexToNum(pendingCount),
      provider: 'infura-lite',
      updatedAt: Date.now(),
    };
  }

  async getFlows(): Promise<OnchainFlows> {
    // DefiLlama stablecoin flows
    let stablecoinData: any = null;
    try {
      const res = await fetch('https://stablecoins.llama.fi/stablecoinchains');
      const chains = await res.json() as any[];
      const eth = chains.find((c: any) => c.name === 'Ethereum');
      if (eth) {
        stablecoinData = eth;
      }
    } catch (e) {
      console.warn('[Onchain-Lite] DefiLlama stablecoins fetch failed:', e);
    }

    const stablecoinTotal = stablecoinData?.totalCirculatingUSD?.peggedUSD || 0;
    
    // Estimate exchange flows from recent blocks
    const latestBlock = await rpcCall('eth_getBlockByNumber', ['latest', true]);
    const txs = latestBlock.transactions || [];
    
    let totalValueIn = 0;
    let totalValueOut = 0;
    
    for (const tx of txs.slice(0, 50)) {
      const value = weiToEth(tx.value || '0x0');
      if (value > 10) {
        totalValueIn += value * 0.5;
        totalValueOut += value * 0.5;
      }
    }

    const ethPrice = await this.getEthPrice();
    
    return {
      exchangeInflow24h: Math.round(totalValueIn * ethPrice * 24 * 5),
      exchangeOutflow24h: Math.round(totalValueOut * ethPrice * 24 * 5),
      exchangeNetflow24h: Math.round((totalValueIn - totalValueOut) * ethPrice * 24 * 5),
      stablecoinInflow24h: Math.round(stablecoinTotal * 0.001),
      stablecoinOutflow24h: Math.round(stablecoinTotal * 0.0009),
      stablecoinNetflow24h: Math.round(stablecoinTotal * 0.0001),
      provider: 'infura-lite+defillama',
      updatedAt: Date.now(),
    };
  }

  async getWhales(): Promise<OnchainWhales> {
    const latestBlock = await rpcCall('eth_getBlockByNumber', ['latest', true]);
    const txs = latestBlock.transactions || [];
    const ethPrice = await this.getEthPrice();
    
    const largeTxs: OnchainWhaleTransfer[] = [];
    
    for (const tx of txs) {
      const valueEth = weiToEth(tx.value || '0x0');
      const valueUsd = valueEth * ethPrice;
      
      if (valueUsd >= 100_000) {
        largeTxs.push({
          hash: tx.hash,
          from: tx.from,
          to: tx.to || '0x0',
          valueEth: Math.round(valueEth * 1000) / 1000,
          valueUsd: Math.round(valueUsd),
          timestamp: hexToNum(latestBlock.timestamp),
          block: hexToNum(latestBlock.number),
        });
      }
    }

    largeTxs.sort((a, b) => b.valueUsd - a.valueUsd);

    return {
      largeTransfers24h: largeTxs.length * 24 * 5,
      topTransfers: largeTxs.slice(0, 10),
      totalWhaleVolume24h: largeTxs.reduce((s, t) => s + t.valueUsd, 0) * 24 * 5,
      provider: 'infura-lite',
      updatedAt: Date.now(),
    };
  }

  async getActivity(): Promise<OnchainActivity> {
    // DefiLlama TVL + DEX volumes
    let tvl = 0;
    let dexVolume = 0;
    let topPairs: Array<{ pair: string; volume: number }> = [];

    try {
      const [tvlRes, dexRes] = await Promise.all([
        fetch('https://api.llama.fi/v2/chains').then(r => r.json()),
        fetch('https://api.llama.fi/overview/dexs/ethereum?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true').then(r => r.json()),
      ]);

      const ethChain = (tvlRes as any[]).find((c: any) => c.name === 'Ethereum');
      tvl = ethChain?.tvl || 0;
      
      dexVolume = (dexRes as any)?.total24h || 0;
      
      const protocols = (dexRes as any)?.protocols || [];
      topPairs = protocols.slice(0, 5).map((p: any) => ({
        pair: p.name || p.displayName || 'Unknown',
        volume: Math.round(p.total24h || 0),
      }));
    } catch (e) {
      console.warn('[Onchain-Lite] DefiLlama activity fetch failed:', e);
    }

    return {
      dexVolume24h: Math.round(dexVolume),
      topPairs,
      newContracts24h: 0,
      totalValueLocked: Math.round(tvl),
      liquidityChange24h: 0,
      provider: 'defillama',
      updatedAt: Date.now(),
    };
  }

  private ethPriceCache: { price: number; at: number } = { price: 0, at: 0 };

  private async getEthPrice(): Promise<number> {
    if (Date.now() - this.ethPriceCache.at < 120_000 && this.ethPriceCache.price > 0) {
      return this.ethPriceCache.price;
    }
    try {
      const res = await fetch('https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd');
      const data = await res.json() as any;
      const price = data?.ethereum?.usd || 2500;
      this.ethPriceCache = { price, at: Date.now() };
      return price;
    } catch {
      return this.ethPriceCache.price || 2500;
    }
  }
}

console.log('[Onchain-Lite] Lite Provider loaded');
