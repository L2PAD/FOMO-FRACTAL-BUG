/**
 * Chain Contracts — Phase G0.1
 * ==============================
 * Types and validation for multi-chain registry.
 */

export type ChainKey = 'eth' | 'arb' | 'op' | 'base';

export interface ChainConfig {
  chainId: number;
  key: ChainKey;
  name: string;
  rpcUrl: string;
  explorerUrl: string;
  nativeSymbol: string;
  enabled: boolean;
  priority: number;
}

export const VALID_CHAIN_KEYS: ChainKey[] = ['eth', 'arb', 'op', 'base'];

export function isValidChainKey(k: string): k is ChainKey {
  return VALID_CHAIN_KEYS.includes(k as ChainKey);
}
