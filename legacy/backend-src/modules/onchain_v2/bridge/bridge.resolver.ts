/**
 * OnChain V2 — Bridge Resolver
 * ==============================
 * 
 * Resolves contract roles to actual addresses.
 * Priority: DB > ENV > STATIC > NONE
 */

import type { ResolvedContract, ContractRole } from './bridge.types.js';

// ═══════════════════════════════════════════════════════════════
// STATIC CONTRACT ADDRESSES (canonical, verified)
// ═══════════════════════════════════════════════════════════════

/**
 * Well-known canonical bridge contract addresses.
 * These are immutable mainnet addresses.
 */
export const STATIC_BRIDGE_ADDRESSES: Partial<Record<ContractRole, string>> = {
  // Optimism L1 Standard Bridge (mainnet)
  OP_L1_STANDARD_BRIDGE: '0x99C9fc46f92E8a1c0deC1b1747d010903E884bE1',
  // Optimism L2 Standard Bridge (OP mainnet)
  OP_L2_STANDARD_BRIDGE: '0x4200000000000000000000000000000000000010',
  
  // Base L1 Standard Bridge (mainnet)
  BASE_L1_STANDARD_BRIDGE: '0x3154Cf16ccdb4C6d922629664174b904d80F2C35',
  // Base L2 Standard Bridge (Base mainnet)
  BASE_L2_STANDARD_BRIDGE: '0x4200000000000000000000000000000000000010',
  
  // Arbitrum L1 Inbox (mainnet)
  ARB_L1_INBOX: '0x4Dbd4fc535Ac27206064B68FfCf827b0A60BAB3f',
  // Arbitrum L2 Gateway Router (Arbitrum One)
  ARB_L2_GATEWAY_ROUTER: '0x5288c571Fd7aD117beA99bF60FE0846C4E84F933',
};

// ═══════════════════════════════════════════════════════════════
// RESOLVER DEPS
// ═══════════════════════════════════════════════════════════════

export interface BridgeResolverDeps {
  env: NodeJS.ProcessEnv;
  staticMap?: Partial<Record<ContractRole, string>>;
  dbLookup?: (role: ContractRole) => Promise<string | null>;
}

// ═══════════════════════════════════════════════════════════════
// RESOLVER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Resolve contract roles to addresses.
 * Priority: DB > ENV > STATIC > NONE
 */
export async function resolveContracts(
  roles: ContractRole[],
  deps: BridgeResolverDeps
): Promise<ResolvedContract[]> {
  const out: ResolvedContract[] = [];
  const staticMap = deps.staticMap || STATIC_BRIDGE_ADDRESSES;

  for (const role of roles) {
    // 1) DB lookup (if available)
    if (deps.dbLookup) {
      try {
        const dbVal = await deps.dbLookup(role);
        if (dbVal && dbVal.trim().length > 0) {
          out.push({ role, address: dbVal.trim().toLowerCase(), source: 'DB' });
          continue;
        }
      } catch {
        // Ignore DB errors, fall through
      }
    }

    // 2) ENV lookup
    const envVal = deps.env[role];
    if (envVal && typeof envVal === 'string' && envVal.trim().length > 0) {
      out.push({ role, address: envVal.trim().toLowerCase(), source: 'ENV' });
      continue;
    }

    // 3) STATIC lookup
    const staticVal = staticMap[role];
    if (staticVal && staticVal.trim().length > 0) {
      out.push({ role, address: staticVal.trim().toLowerCase(), source: 'STATIC' });
      continue;
    }

    // NONE - not resolved
    out.push({ role, address: null, source: 'NONE' });
  }

  return out;
}

/**
 * Get missing (unresolved) roles
 */
export function getMissingRoles(resolved: ResolvedContract[]): ContractRole[] {
  return resolved.filter(c => !c.address).map(c => c.role);
}

/**
 * Check if all contracts are resolved
 */
export function allContractsResolved(resolved: ResolvedContract[]): boolean {
  return resolved.every(c => c.address !== null);
}

/**
 * Resolve single contract role
 */
export async function resolveContract(
  role: ContractRole,
  deps: BridgeResolverDeps
): Promise<ResolvedContract> {
  const results = await resolveContracts([role], deps);
  return results[0];
}

console.log('[OnChain V2] Bridge Resolver loaded');
