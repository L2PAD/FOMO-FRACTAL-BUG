/**
 * Chains Module — Phase G0.1
 * ============================
 * Public exports for chain registry.
 */

export { ChainRegistry } from './chain.registry';
export { ChainModel } from './chain.model';
export { seedChains } from './chain.seed';
export { chainRoutes } from './chain.controller';
export type { ChainConfig, ChainKey } from './chain.contracts';
export { isValidChainKey, VALID_CHAIN_KEYS } from './chain.contracts';
