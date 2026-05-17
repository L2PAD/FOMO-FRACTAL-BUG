/**
 * Onchain v2 Feature Flags — Phase 5, Block 5.3
 * ================================================
 *
 * Centralized feature flag barrier for pre-freeze control.
 * All flags read from env; defaults are SAFE (restrictive).
 *
 * Flags:
 *   ONCHAIN_FREEZE_MODE        — locks all mutation (discovery, activation)
 *   MULTICHAIN_ENABLED         — allows chainId != 1
 *   POOL_AUTO_ACTIVATION       — allows scoring to auto-ACTIVE pools
 *   DISCOVERY_WRITE            — allows discovery job to insert new pools
 */

function envBool(key: string, fallback: boolean): boolean {
  const v = process.env[key];
  if (v === undefined) return fallback;
  return v === 'true' || v === '1';
}

export const ONCHAIN_FLAGS = {
  /** Master switch: when true, all writes are blocked */
  get FREEZE_MODE(): boolean {
    return envBool('ONCHAIN_FREEZE_MODE', false);
  },

  /** Allow chains other than ETH mainnet (chainId=1) */
  get MULTICHAIN_ENABLED(): boolean {
    return envBool('MULTICHAIN_ENABLED', false);
  },

  /** Pool scoring can set status=ACTIVE automatically */
  get POOL_AUTO_ACTIVATION(): boolean {
    if (this.FREEZE_MODE) return false;
    return envBool('POOL_AUTO_ACTIVATION_ENABLED', true);
  },

  /** Discovery job can write new pools to DB */
  get DISCOVERY_WRITE(): boolean {
    if (this.FREEZE_MODE) return false;
    return envBool('DISCOVERY_WRITE_ENABLED', true);
  },
};

/** Guard: reject non-ETH chains when multichain is off */
export function assertChainAllowed(chainId: number): void {
  if (chainId === 1) return;
  if (!ONCHAIN_FLAGS.MULTICHAIN_ENABLED) {
    throw new Error(`Chain ${chainId} blocked: MULTICHAIN_ENABLED=false`);
  }
}

/** Guard: reject writes in freeze mode */
export function assertNotFrozen(context: string): void {
  if (ONCHAIN_FLAGS.FREEZE_MODE) {
    throw new Error(`Write blocked (${context}): ONCHAIN_FREEZE_MODE=true`);
  }
}
