/**
 * On-Chain Lite Provider Interface
 * =================================
 * 
 * Abstract interface for onchain data providers.
 * Allows switching between preview (Infura/APIs) and production (engine/indexer).
 * 
 * ONCHAIN_MODE=preview → LiteProvider (Infura + DefiLlama)
 * ONCHAIN_MODE=production → EngineProvider (full indexer)
 */

export interface OnchainSummary {
  blockHeight: number;
  gasPrice: number;          // gwei
  tps: number;
  activeAddresses24h: number;
  blockTime: number;         // seconds
  pendingTxCount: number;
  provider: string;
  updatedAt: number;
}

export interface OnchainFlows {
  exchangeInflow24h: number;   // USD
  exchangeOutflow24h: number;  // USD
  exchangeNetflow24h: number;  // USD
  stablecoinInflow24h: number;
  stablecoinOutflow24h: number;
  stablecoinNetflow24h: number;
  provider: string;
  updatedAt: number;
}

export interface OnchainWhaleTransfer {
  hash: string;
  from: string;
  to: string;
  valueEth: number;
  valueUsd: number;
  timestamp: number;
  block: number;
}

export interface OnchainWhales {
  largeTransfers24h: number;
  topTransfers: OnchainWhaleTransfer[];
  totalWhaleVolume24h: number;
  provider: string;
  updatedAt: number;
}

export interface OnchainActivity {
  dexVolume24h: number;
  topPairs: Array<{ pair: string; volume: number }>;
  newContracts24h: number;
  totalValueLocked: number;
  liquidityChange24h: number;
  provider: string;
  updatedAt: number;
}

export interface IOnchainProvider {
  getSummary(): Promise<OnchainSummary>;
  getFlows(): Promise<OnchainFlows>;
  getWhales(): Promise<OnchainWhales>;
  getActivity(): Promise<OnchainActivity>;
}

console.log('[Onchain-Lite] Provider types loaded');
