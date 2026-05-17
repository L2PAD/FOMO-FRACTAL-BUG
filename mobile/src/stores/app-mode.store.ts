import { create } from 'zustand';

export type AppMode = 'INTELLIGENCE' | 'TRADING';
export type IntelTab = 'HOME' | 'FEED' | 'SIGNALS' | 'EDGE';

/**
 * Trading OS subsystem tabs.
 *
 *   COMMAND     — AI operating center (status, focus, why-waiting)
 *   MARKET      — scanner / candidates / regime
 *   EXECUTION   — execution intelligence (5 AI modules: TA/Fractal/Exchange/Sentiment/Onchain)
 *   PORTFOLIO   — autonomous portfolio + attribution
 *
 *   TRADE       — deep screen (NOT a nav tab). Reached from COMMAND best
 *                 opportunity, MARKET candidate row, etc.
 */
export type TradingTab = 'COMMAND' | 'MARKET' | 'EXECUTION' | 'TRADE' | 'PORTFOLIO' | 'INTELLIGENCE';
export type DeepIntelModule = 'exchange' | 'onchain' | 'sentiment' | 'fractal' | 'asset-intel' | null;

/**
 * Marker set when a user taps the 🔥 Signal of the Moment hero. Consumed by
 * EdgeScreen / FeedScreen to show reinforcement copy ("You're early on this
 * setup") and strengthen the upsell line for FREE users.
 *
 * One-shot: cleared on the next navigation or when consumer calls clearHeroEntry().
 */
export interface HeroEntry {
  signalId: string;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  type: string;
  asset: string | null;
  sourcesCount: number;
  at: number;
}

interface AppModeState {
  mode: AppMode;
  intelTab: IntelTab;
  tradingTab: TradingTab;
  deepIntelModule: DeepIntelModule;
  heroEntry: HeroEntry | null;
  setMode: (mode: AppMode) => void;
  setIntelTab: (tab: IntelTab) => void;
  setTradingTab: (tab: TradingTab) => void;
  setDeepIntelModule: (module: DeepIntelModule) => void;
  switchToTrading: () => void;
  switchToIntelligence: () => void;
  setHeroEntry: (entry: HeroEntry) => void;
  clearHeroEntry: () => void;
}

export const useAppMode = create<AppModeState>((set) => ({
  mode: 'INTELLIGENCE',
  intelTab: 'HOME',
  tradingTab: 'COMMAND',
  deepIntelModule: null,
  heroEntry: null,
  setMode: (mode) => set({ mode }),
  setIntelTab: (tab) => set({ intelTab: tab, deepIntelModule: null }),
  setTradingTab: (tab) => set({ tradingTab: tab }),
  setDeepIntelModule: (module) => set({ deepIntelModule: module }),
  switchToTrading: () => set({ mode: 'TRADING', tradingTab: 'COMMAND' }),
  switchToIntelligence: () => set({ mode: 'INTELLIGENCE', intelTab: 'HOME', deepIntelModule: null }),
  setHeroEntry: (entry) => set({ heroEntry: entry }),
  clearHeroEntry: () => set({ heroEntry: null }),
}));
