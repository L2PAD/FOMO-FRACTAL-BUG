import { create } from 'zustand';

interface PortfolioStore {
  pendingPortfolio: any[] | null;
  pendingMeta: any | null;
  showIntelScreen: boolean;
  setPendingPortfolio: (positions: any[], meta?: any) => void;
  clearPendingPortfolio: () => void;
  setShowIntelScreen: (show: boolean) => void;
}

export const usePortfolioStore = create<PortfolioStore>((set) => ({
  pendingPortfolio: null,
  pendingMeta: null,
  showIntelScreen: false,
  setPendingPortfolio: (positions, meta) => set({
    pendingPortfolio: positions,
    pendingMeta: meta || null,
    showIntelScreen: true,
  }),
  clearPendingPortfolio: () => set({
    pendingPortfolio: null,
    pendingMeta: null,
    showIntelScreen: false,
  }),
  setShowIntelScreen: (show) => set({ showIntelScreen: show }),
}));
