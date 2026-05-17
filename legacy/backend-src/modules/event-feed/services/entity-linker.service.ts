/**
 * Entity Linker Service
 *
 * Maps raw text mentions to canonical asset tickers and entity names.
 * Alias resolution: "Ethereum" → ETH, "Satoshi" → BTC, "Solana" → SOL, etc.
 * Entity extraction: SEC, Binance, Coinbase, BlackRock, etc.
 *
 * Pure algorithmic — no AI, no external calls.
 */

// Asset alias map: alias → canonical ticker
const ASSET_ALIASES: Record<string, string> = {
  // BTC
  bitcoin: 'BTC', btc: 'BTC', satoshi: 'BTC', sats: 'BTC', xbt: 'BTC',
  // ETH
  ethereum: 'ETH', eth: 'ETH', ether: 'ETH',
  // SOL
  solana: 'SOL', sol: 'SOL',
  // BNB
  bnb: 'BNB', binancecoin: 'BNB',
  // XRP
  xrp: 'XRP', ripple: 'XRP',
  // ADA
  cardano: 'ADA', ada: 'ADA',
  // DOGE
  dogecoin: 'DOGE', doge: 'DOGE',
  // AVAX
  avalanche: 'AVAX', avax: 'AVAX',
  // DOT
  polkadot: 'DOT', dot: 'DOT',
  // MATIC / POL
  polygon: 'MATIC', matic: 'MATIC', pol: 'MATIC',
  // LINK
  chainlink: 'LINK', link: 'LINK',
  // UNI
  uniswap: 'UNI', uni: 'UNI',
  // AAVE
  aave: 'AAVE',
  // ARB
  arbitrum: 'ARB', arb: 'ARB',
  // OP
  optimism: 'OP',
  // ATOM
  cosmos: 'ATOM', atom: 'ATOM',
  // NEAR
  near: 'NEAR',
  // APT
  aptos: 'APT', apt: 'APT',
  // SUI
  sui: 'SUI',
  // TRX
  tron: 'TRX', trx: 'TRX',
  // LTC
  litecoin: 'LTC', ltc: 'LTC',
  // HYPE
  hyperliquid: 'HYPE', hype: 'HYPE',
  // FIL
  filecoin: 'FIL', fil: 'FIL',
  // STX
  stacks: 'STX', stx: 'STX',
  // INJ
  injective: 'INJ', inj: 'INJ',
  // TIA
  celestia: 'TIA', tia: 'TIA',
  // JUP
  jupiter: 'JUP', jup: 'JUP',
  // WLD
  worldcoin: 'WLD', wld: 'WLD',
  // PEPE
  pepe: 'PEPE',
  // SHIB
  shiba: 'SHIB', shib: 'SHIB',
  // Stablecoins (tracked but not traded)
  usdt: 'USDT', tether: 'USDT',
  usdc: 'USDC',
};

// Known entities (organizations, people, regulators)
const KNOWN_ENTITIES: [string, RegExp][] = [
  ['SEC',             /\bsec\b(?!ond|urity|ure|tor|tion)/i],
  ['CFTC',            /\bcftc\b/i],
  ['Federal Reserve', /\bfed\b|federal reserve/i],
  ['US Treasury',     /\bus treasury\b|treasury department/i],
  ['White House',     /white house/i],
  ['BlackRock',       /blackrock/i],
  ['Grayscale',       /grayscale/i],
  ['MicroStrategy',   /microstrategy|saylor/i],
  ['Coinbase',        /coinbase/i],
  ['Binance',         /binance/i],
  ['Kraken',          /kraken/i],
  ['VanEck',          /vaneck/i],
  ['Fidelity',        /fidelity/i],
  ['Galaxy Digital',  /galaxy digital/i],
  ['a16z',            /a16z|andreessen/i],
  ['Paradigm',        /paradigm/i],
  ['Circle',          /\bcircle\b/i],
  ['Tether',          /\btether\b/i],
  ['Trump',           /\btrump\b/i],
  ['Elon Musk',       /elon musk|\bmusk\b/i],
  ['SBF',             /bankman.?fried|\bsbf\b/i],
  ['CZ',              /\bcz\b|changpeng zhao/i],
  ['Vitalik',         /vitalik/i],
];

class EntityLinkerService {
  /**
   * Extract asset tickers from text.
   * Returns deduplicated, canonical tickers.
   */
  extractAssets(text: string): string[] {
    const assets = new Set<string>();
    const lower = text.toLowerCase();

    // Check $TICKER patterns first
    const tickerMatches = text.matchAll(/\$([A-Z]{2,10})/g);
    for (const m of tickerMatches) {
      const ticker = m[1].toUpperCase();
      if (ASSET_ALIASES[ticker.toLowerCase()]) {
        assets.add(ASSET_ALIASES[ticker.toLowerCase()]);
      } else {
        assets.add(ticker);
      }
    }

    // Check word-level aliases
    const words = lower.split(/[\s,;:()\[\]{}"']+/);
    for (const w of words) {
      const clean = w.replace(/[^a-z0-9]/g, '');
      if (clean.length >= 2 && ASSET_ALIASES[clean]) {
        assets.add(ASSET_ALIASES[clean]);
      }
    }

    // Exclude stablecoins from primary asset list (they're noise)
    const STABLES = new Set(['USDT', 'USDC', 'DAI', 'BUSD']);
    const result = [...assets].filter(a => !STABLES.has(a));

    // If only stablecoins found, include them
    return result.length > 0 ? result : [...assets];
  }

  /**
   * Extract named entities (organizations, people, regulators).
   */
  extractEntities(text: string): string[] {
    const entities: string[] = [];

    for (const [name, pattern] of KNOWN_ENTITIES) {
      if (pattern.test(text)) {
        entities.push(name);
      }
    }

    return entities;
  }

  /**
   * Link raw event data to assets and entities.
   * Combines explicit raw assets with text-extracted ones.
   */
  link(title: string, text: string, rawAssets?: string[], rawEntities?: string[]): {
    assets: string[];
    entities: string[];
  } {
    const combined = `${title} ${text}`;
    const textAssets = this.extractAssets(combined);
    const textEntities = this.extractEntities(combined);

    // Merge with raw data
    const assetSet = new Set([
      ...textAssets,
      ...(rawAssets || []).map(a => ASSET_ALIASES[a.toLowerCase()] || a.toUpperCase()),
    ]);
    const entitySet = new Set([...textEntities, ...(rawEntities || [])]);

    return {
      assets: [...assetSet],
      entities: [...entitySet],
    };
  }
}

export const entityLinkerService = new EntityLinkerService();
