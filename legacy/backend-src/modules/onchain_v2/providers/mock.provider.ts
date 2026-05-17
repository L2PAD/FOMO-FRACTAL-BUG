/**
 * OnChain V2 — Mock Provider
 * ===========================
 * 
 * Deterministic mock provider for on-chain data.
 * Same (symbol, t0) → same snapshot.
 * 
 * USE CASES:
 * - Development
 * - Testing
 * - CI/CD pipelines
 * - Staging environments without RPC access
 */

import {
  OnchainSnapshot,
  OnchainWindow,
  OnchainChain,
  OnchainSourceType,
  OnchainProviderHealth,
  SOURCE_QUALITY,
  ONCHAIN_THRESHOLDS,
} from '../core/contracts.js';

import { IOnchainProvider } from './provider.interface.js';

// ═══════════════════════════════════════════════════════════════
// MOCK DATA CONFIGURATION
// ═══════════════════════════════════════════════════════════════

const SYMBOL_CHAIN_MAP: Record<string, OnchainChain> = {
  BTCUSDT: 'bitcoin',
  ETHUSDT: 'ethereum',
  SOLUSDT: 'solana',
  BNBUSDT: 'ethereum',
  XRPUSDT: 'ethereum',
  ARBUSDT: 'arbitrum',
  OPUSDT: 'optimism',
  MATICUSDT: 'polygon',
};

const ASSET_PARAMS: Record<string, {
  avgDailyVolume: number;
  avgActiveAddresses: number;
  avgTxCount: number;
  avgFees: number;
  volatility: number;
}> = {
  BTCUSDT: {
    avgDailyVolume: 10_000_000_000,
    avgActiveAddresses: 800_000,
    avgTxCount: 300_000,
    avgFees: 1_500_000,
    volatility: 0.3,
  },
  ETHUSDT: {
    avgDailyVolume: 8_000_000_000,
    avgActiveAddresses: 500_000,
    avgTxCount: 1_200_000,
    avgFees: 5_000_000,
    volatility: 0.35,
  },
  SOLUSDT: {
    avgDailyVolume: 2_000_000_000,
    avgActiveAddresses: 200_000,
    avgTxCount: 5_000_000,
    avgFees: 100_000,
    volatility: 0.5,
  },
  DEFAULT: {
    avgDailyVolume: 500_000_000,
    avgActiveAddresses: 50_000,
    avgTxCount: 100_000,
    avgFees: 50_000,
    volatility: 0.4,
  },
};

const WINDOW_MULT: Record<OnchainWindow, number> = {
  '1h': 1 / 24,
  '4h': 4 / 24,
  '24h': 1,
  '7d': 7,
};

const SUPPORTED_CHAINS: OnchainChain[] = [
  'bitcoin', 'ethereum', 'solana', 'arbitrum', 'base', 'optimism', 'polygon'
];

// ═══════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

function hashSeed(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return Math.abs(hash);
}

function getDirectionBias(seed: number): number {
  const raw = ((seed >> 5) % 200) - 100;
  return raw / 100;
}

// ═══════════════════════════════════════════════════════════════
// MOCK PROVIDER IMPLEMENTATION
// ═══════════════════════════════════════════════════════════════

export class MockProvider implements IOnchainProvider {
  readonly providerId = 'mock_onchain_v2';
  readonly providerName = 'Mock OnChain Provider V2';
  readonly providerMode: OnchainSourceType = 'mock';
  
  private initialized = false;
  private initTime = 0;
  
  async initialize(): Promise<void> {
    if (this.initialized) return;
    
    this.initTime = Date.now();
    this.initialized = true;
    
    console.log('[MockProvider] Initialized');
  }
  
  async getSnapshot(
    symbol: string,
    t0: number,
    window: OnchainWindow
  ): Promise<OnchainSnapshot> {
    const params = ASSET_PARAMS[symbol] || ASSET_PARAMS.DEFAULT;
    const windowMult = WINDOW_MULT[window];
    
    const seed = hashSeed(`${symbol}:${t0}:${window}`);
    
    const baseVolume = params.avgDailyVolume * windowMult;
    const baseAddresses = Math.round(params.avgActiveAddresses * windowMult);
    const baseTxCount = Math.round(params.avgTxCount * windowMult);
    const baseFees = params.avgFees * windowMult;
    
    const variance = (seed % 1000) / 1000;
    const direction = ((seed >> 10) % 2) === 0 ? 1 : -1;
    const volatilityFactor = params.volatility * variance * direction;
    
    const exchangeBias = getDirectionBias(seed);
    const exchangeInflowUsd = Math.round(baseVolume * 0.15 * (1 + exchangeBias * 0.3));
    const exchangeOutflowUsd = Math.round(baseVolume * 0.15 * (1 - exchangeBias * 0.3));
    const exchangeNetUsd = exchangeInflowUsd - exchangeOutflowUsd;
    
    const flowBias = getDirectionBias(seed + 1000);
    const netInflowUsd = Math.round(baseVolume * 0.2 * (1 + flowBias * 0.2));
    const netOutflowUsd = Math.round(baseVolume * 0.2 * (1 - flowBias * 0.2));
    const netFlowUsd = netInflowUsd - netOutflowUsd;
    
    const activityMult = 1 + volatilityFactor * 0.5;
    const activeAddresses = Math.round(baseAddresses * activityMult);
    const txCount = Math.round(baseTxCount * activityMult);
    const feesUsd = Math.round(baseFees * (1 + volatilityFactor * 0.8));
    
    const whaleSeed = (seed >> 15) % 100;
    const largeTransfersCount = Math.max(0, Math.round(
      (5 + whaleSeed / 10) * windowMult * (1 + Math.abs(volatilityFactor))
    ));
    const avgLargeTransfer = ONCHAIN_THRESHOLDS.LARGE_TRANSFER_USD * (3 + whaleSeed / 50);
    const largeTransfersVolumeUsd = Math.round(largeTransfersCount * avgLargeTransfer);
    
    return {
      symbol,
      chain: SYMBOL_CHAIN_MAP[symbol] || 'ethereum',
      t0,
      snapshotTimestamp: t0 - 60_000,
      window,
      
      exchangeInflowUsd,
      exchangeOutflowUsd,
      exchangeNetUsd,
      
      netInflowUsd,
      netOutflowUsd,
      netFlowUsd,
      
      activeAddresses,
      txCount,
      feesUsd,
      
      largeTransfersCount,
      largeTransfersVolumeUsd,
      
      source: 'mock',
      sourceProvider: this.providerId,
      sourceQuality: SOURCE_QUALITY.mock,
      missingFields: ['topHolderDeltaUsd'],
    };
  }
  
  async getLatestBlock(chain: OnchainChain): Promise<number> {
    // Mock block numbers based on chain
    const baseBlocks: Record<OnchainChain, number> = {
      bitcoin: 820000,
      ethereum: 18800000,
      solana: 230000000,
      arbitrum: 160000000,
      base: 9000000,
      optimism: 115000000,
      polygon: 52000000,
    };
    
    const base = baseBlocks[chain] || 18800000;
    const elapsed = Math.floor((Date.now() - this.initTime) / 12000);
    
    return base + elapsed;
  }
  
  async getHealth(): Promise<OnchainProviderHealth> {
    return {
      providerId: this.providerId,
      providerName: this.providerName,
      providerMode: 'mock',
      status: 'UP',
      chains: SUPPORTED_CHAINS,
      lastSuccessAt: Date.now(),
      successRate24h: 1.0,
      avgLatencyMs: 5,
      checkedAt: Date.now(),
    };
  }
  
  supportsChain(chain: OnchainChain): boolean {
    return SUPPORTED_CHAINS.includes(chain);
  }
  
  getSupportedChains(): OnchainChain[] {
    return [...SUPPORTED_CHAINS];
  }
}

console.log('[OnChain V2] Mock Provider loaded');
