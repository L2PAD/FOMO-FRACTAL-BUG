/**
 * Node ID Normalizer
 * 
 * Deterministic node ID generation.
 * Format: type:identifier:chain (or type:identifier if no chain)
 * 
 * Examples:
 *   wallet:0x123:ethereum
 *   token:usdc:solana
 *   dex:uniswap:ethereum
 *   cex:binance
 *   bridge:wormhole
 */

export function normalizeNodeId(type, identifier, chain) {
  const normalizedType = (type || 'wallet').toLowerCase();
  const normalizedId = (identifier || '').toLowerCase();

  if (!chain || chain === 'multi' || chain === 'unknown') {
    return `${normalizedType}:${normalizedId}`;
  }

  return `${normalizedType}:${normalizedId}:${chain.toLowerCase()}`;
}

export function parseNodeId(id) {
  const parts = (id || '').split(':');
  return {
    type: parts[0] || 'wallet',
    identifier: parts[1] || '',
    chain: parts[2] || null,
  };
}

export function shortenAddress(addr) {
  if (!addr || addr.length < 10) return addr || '';
  return addr.slice(0, 6) + '...' + addr.slice(-4);
}
