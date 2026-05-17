import { create } from 'zustand';

export interface AssetInfo {
  symbol: string;
  name: string;
  category: string;
  rank: number;
  binance: string;
  bybit: string;
}

interface AssetState {
  currentAsset: string;
  allAssets: AssetInfo[];
  recentAssets: string[];
  favorites: string[];
  isLoaded: boolean;

  setCurrentAsset: (symbol: string) => void;
  setAllAssets: (assets: AssetInfo[]) => void;
  addRecent: (symbol: string) => void;
  toggleFavorite: (symbol: string) => void;
  setLoaded: (v: boolean) => void;
}

export const useAssetStore = create<AssetState>((set, get) => ({
  currentAsset: 'BTC',
  allAssets: [],
  recentAssets: ['BTC', 'ETH', 'SOL'],
  favorites: ['BTC', 'ETH'],
  isLoaded: false,

  setCurrentAsset: (symbol) => {
    set({ currentAsset: symbol });
    // Also add to recents
    get().addRecent(symbol);
  },

  setAllAssets: (assets) => set({ allAssets: assets, isLoaded: true }),

  addRecent: (symbol) => {
    const prev = get().recentAssets.filter((s) => s !== symbol);
    set({ recentAssets: [symbol, ...prev].slice(0, 8) });
  },

  toggleFavorite: (symbol) => {
    const favs = get().favorites;
    if (favs.includes(symbol)) {
      set({ favorites: favs.filter((s) => s !== symbol) });
    } else {
      set({ favorites: [...favs, symbol] });
    }
  },

  setLoaded: (v) => set({ isLoaded: v }),
}));
