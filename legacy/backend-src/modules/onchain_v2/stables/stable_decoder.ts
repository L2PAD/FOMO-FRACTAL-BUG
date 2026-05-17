/**
 * OnChain V2 — Stablecoin Mint/Burn Decoder
 * ==========================================
 * 
 * Decodes ERC20 Transfer events to detect mint/burn.
 * Mint: from = 0x0
 * Burn: to = 0x0
 */

import { Interface } from 'ethers';

// ═══════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════

const ZERO_ADDRESS = '0x0000000000000000000000000000000000000000';

// ERC20 Transfer event
const ERC20_ABI = [
  'event Transfer(address indexed from, address indexed to, uint256 value)',
];

const iface = new Interface(ERC20_ABI);

// Transfer topic hash
export const TRANSFER_TOPIC = iface.getEvent('Transfer')!.topicHash;

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface DecodedMintBurn {
  direction: 'MINT' | 'BURN';
  rawAmount: string;
  participant: string;  // minter (to) or burner (from)
}

// ═══════════════════════════════════════════════════════════════
// DECODER
// ═══════════════════════════════════════════════════════════════

/**
 * Decode ERC20 Transfer log to detect mint/burn
 * Returns null if not a mint/burn event
 */
export function decodeMintBurn(log: {
  topics: string[];
  data: string;
}): DecodedMintBurn | null {
  try {
    const parsed = iface.parseLog({ topics: log.topics, data: log.data });
    
    if (!parsed || parsed.name !== 'Transfer') {
      return null;
    }
    
    const from = String(parsed.args.from).toLowerCase();
    const to = String(parsed.args.to).toLowerCase();
    const value = parsed.args.value.toString();
    
    // Mint: from = 0x0
    if (from === ZERO_ADDRESS) {
      return {
        direction: 'MINT',
        rawAmount: value,
        participant: to,
      };
    }
    
    // Burn: to = 0x0
    if (to === ZERO_ADDRESS) {
      return {
        direction: 'BURN',
        rawAmount: value,
        participant: from,
      };
    }
    
    // Regular transfer, not mint/burn
    return null;
  } catch (e) {
    return null;
  }
}

/**
 * Convert raw amount to normalized float
 */
export function normalizeAmount(rawAmount: string, decimals: number): number {
  try {
    const raw = BigInt(rawAmount);
    const divisor = BigInt(10 ** decimals);
    const intPart = raw / divisor;
    const fracPart = raw % divisor;
    
    // Convert to float
    return Number(intPart) + Number(fracPart) / Number(divisor);
  } catch {
    return 0;
  }
}

/**
 * Check if log is a Transfer event
 */
export function isTransferLog(log: { topics: string[] }): boolean {
  return log.topics[0]?.toLowerCase() === TRANSFER_TOPIC.toLowerCase();
}

console.log('[OnChain V2] Stable Mint/Burn Decoder loaded');
