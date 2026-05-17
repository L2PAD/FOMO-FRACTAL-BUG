/**
 * Explorer URL utility — supports multiple chains
 * Not hardcoded to Etherscan — ready for Arbiscan, Basescan, etc.
 */

const EXPLORERS: Record<number, { name: string; url: string; short: string }> = {
  1:     { name: 'Etherscan',    url: 'https://etherscan.io',            short: 'etherscan' },
  42161: { name: 'Arbiscan',     url: 'https://arbiscan.io',             short: 'arbiscan' },
  8453:  { name: 'Basescan',     url: 'https://basescan.org',            short: 'basescan' },
  137:   { name: 'Polygonscan',  url: 'https://polygonscan.com',         short: 'polygonscan' },
  10:    { name: 'Optimism',     url: 'https://optimistic.etherscan.io', short: 'optimism' },
  56:    { name: 'BscScan',      url: 'https://bscscan.com',             short: 'bscscan' },
  43114: { name: 'Snowtrace',    url: 'https://snowtrace.io',            short: 'snowtrace' },
};

export function getExplorer(chainId: number) {
  return EXPLORERS[chainId] || EXPLORERS[1];
}

export function addressUrl(address: string, chainId: number = 1): string {
  return `${getExplorer(chainId).url}/address/${address}`;
}

export function txUrl(txHash: string, chainId: number = 1): string {
  return `${getExplorer(chainId).url}/tx/${txHash}`;
}

export function tokenUrl(tokenAddress: string, chainId: number = 1): string {
  return `${getExplorer(chainId).url}/token/${tokenAddress}`;
}

export function explorerName(chainId: number = 1): string {
  return getExplorer(chainId).short;
}
