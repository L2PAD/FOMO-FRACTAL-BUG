/**
 * Market Store — PHASE F1
 * 
 * Global state for symbol/timeframe selection.
 * Shared across Research UI components.
 * 
 * Uses React Context + useReducer for state management.
 */

import React, { createContext, useContext, useReducer, useCallback, useEffect } from 'react';
import ResearchService from '../services/researchService';

// ============================================
// INITIAL STATE
// ============================================

const initialState = {
  // Market selection
  symbol: 'BTCUSDT',
  timeframe: '1h',
  
  // Research data (from ResearchService)
  researchState: null,
  
  // Loading states
  loading: false,
  error: null,
  
  // UI state
  lastUpdated: null,
  autoRefresh: true,
  refreshInterval: 30000, // 30 seconds
};

// ============================================
// ACTIONS
// ============================================

const ActionTypes = {
  SET_SYMBOL: 'SET_SYMBOL',
  SET_TIMEFRAME: 'SET_TIMEFRAME',
  SET_LOADING: 'SET_LOADING',
  SET_ERROR: 'SET_ERROR',
  SET_RESEARCH_STATE: 'SET_RESEARCH_STATE',
  CLEAR_ERROR: 'CLEAR_ERROR',
  SET_AUTO_REFRESH: 'SET_AUTO_REFRESH',
};

// ============================================
// REDUCER
// ============================================

function marketReducer(state, action) {
  switch (action.type) {
    case ActionTypes.SET_SYMBOL:
      return {
        ...state,
        symbol: action.payload,
        researchState: null, // Clear on symbol change
      };
      
    case ActionTypes.SET_TIMEFRAME:
      return {
        ...state,
        timeframe: action.payload,
        researchState: null, // Clear on timeframe change
      };
      
    case ActionTypes.SET_LOADING:
      return {
        ...state,
        loading: action.payload,
      };
      
    case ActionTypes.SET_ERROR:
      return {
        ...state,
        error: action.payload,
        loading: false,
      };
      
    case ActionTypes.SET_RESEARCH_STATE:
      return {
        ...state,
        researchState: action.payload,
        loading: false,
        error: null,
        lastUpdated: Date.now(),
      };
      
    case ActionTypes.CLEAR_ERROR:
      return {
        ...state,
        error: null,
      };
      
    case ActionTypes.SET_AUTO_REFRESH:
      return {
        ...state,
        autoRefresh: action.payload,
      };
      
    default:
      return state;
  }
}

// ============================================
// CONTEXT
// ============================================

const MarketContext = createContext(null);

// ============================================
// PROVIDER
// ============================================

export function MarketProvider({ children }) {
  const [state, dispatch] = useReducer(marketReducer, initialState);

  // ============================================
  // ACTIONS
  // ============================================
  
  const setSymbol = useCallback((symbol) => {
    dispatch({ type: ActionTypes.SET_SYMBOL, payload: symbol.toUpperCase() });
  }, []);

  const setTimeframe = useCallback((timeframe) => {
    dispatch({ type: ActionTypes.SET_TIMEFRAME, payload: timeframe });
  }, []);

  const setAutoRefresh = useCallback((enabled) => {
    dispatch({ type: ActionTypes.SET_AUTO_REFRESH, payload: enabled });
  }, []);

  const clearError = useCallback(() => {
    dispatch({ type: ActionTypes.CLEAR_ERROR });
  }, []);

  // ============================================
  // DATA FETCHING
  // ============================================
  
  const loadResearchState = useCallback(async (forceRefresh = false) => {
    const { symbol, timeframe } = state;
    
    dispatch({ type: ActionTypes.SET_LOADING, payload: true });
    
    try {
      const data = forceRefresh 
        ? await ResearchService.refresh(symbol, timeframe)
        : await ResearchService.getResearchState(symbol, timeframe);
      
      dispatch({ type: ActionTypes.SET_RESEARCH_STATE, payload: data });
      return data;
    } catch (error) {
      dispatch({ type: ActionTypes.SET_ERROR, payload: error.message });
      return null;
    }
  }, [state.symbol, state.timeframe]);

  const refresh = useCallback(() => {
    return loadResearchState(true);
  }, [loadResearchState]);

  // ============================================
  // AUTO-REFRESH
  // ============================================
  
  useEffect(() => {
    // Load initial data
    loadResearchState();
  }, [state.symbol, state.timeframe]); // Reload on symbol/timeframe change

  useEffect(() => {
    if (!state.autoRefresh) return;

    const interval = setInterval(() => {
      loadResearchState();
    }, state.refreshInterval);

    return () => clearInterval(interval);
  }, [state.autoRefresh, state.refreshInterval, loadResearchState]);

  // ============================================
  // CONTEXT VALUE
  // ============================================
  
  const value = {
    // State
    symbol: state.symbol,
    timeframe: state.timeframe,
    researchState: state.researchState,
    loading: state.loading,
    error: state.error,
    lastUpdated: state.lastUpdated,
    autoRefresh: state.autoRefresh,
    
    // Actions
    setSymbol,
    setTimeframe,
    setAutoRefresh,
    clearError,
    refresh,
    loadResearchState,
    
    // Computed
    isReady: !state.loading && state.researchState !== null,
    hasError: state.error !== null,
  };

  return (
    <MarketContext.Provider value={value}>
      {children}
    </MarketContext.Provider>
  );
}

// ============================================
// HOOK
// ============================================

export function useMarket() {
  const context = useContext(MarketContext);
  
  if (!context) {
    throw new Error('useMarket must be used within a MarketProvider');
  }
  
  return context;
}

// ============================================
// SELECTORS (computed values)
// ============================================

export function useMarketPrice() {
  const { researchState } = useMarket();
  return researchState?.market || { price: 0, change: 0 };
}

export function useMarketRegime() {
  const { researchState } = useMarket();
  return researchState?.regime || { state: 'LOADING', confidence: 0 };
}

export function useCapitalFlow() {
  const { researchState } = useMarket();
  return researchState?.capitalFlow || { bias: 'NEUTRAL', rotation: 'NEUTRAL', strength: 0 };
}

export function useFractalState() {
  const { researchState } = useMarket();
  return researchState?.fractal || { alignment: 'NEUTRAL', match: '', similarity: 0 };
}

export function useSignalExplanation() {
  const { researchState } = useMarket();
  return researchState?.signal || { direction: 'neutral', summary: '', drivers: [], conflicts: [] };
}

export function useHypotheses() {
  const { researchState } = useMarket();
  return researchState?.hypothesis || { top: null, list: [] };
}

export function useChartData() {
  const { researchState } = useMarket();
  return researchState?.chart || { candles: [], indicators: [], patterns: [] };
}

// ============================================
// RENDER PLAN HOOK
// ============================================

export function useRenderPlan() {
  const [renderPlan, setRenderPlan] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const { symbol, timeframe } = useMarket();

  const fetchRenderPlan = React.useCallback(async () => {
    if (!symbol) return;
    
    setLoading(true);
    try {
      const apiSymbol = symbol.replace('USDT', '');
      // Map timeframes to supported TFs
      const tfMap = { '1h': '4H', '4h': '4H', '1d': '1D', '7d': '7D', '30d': '30D' };
      const apiTf = tfMap[timeframe?.toLowerCase()] || '1D';
      const base = process.env.REACT_APP_BACKEND_URL || '';
      
      // Use render-plan-v2 with 6 layers
      const res = await fetch(`${base}/api/ta-engine/render-plan-v2/${apiSymbol}?timeframe=${apiTf}`);
      if (res.ok) {
        const data = await res.json();
        if (data.ok) {
          setRenderPlan(data.render_plan);
        }
      }
    } catch (err) {
      console.error('[useRenderPlan] Error:', err);
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe]);

  React.useEffect(() => {
    fetchRenderPlan();
  }, [fetchRenderPlan]);

  return { renderPlan, loading, refresh: fetchRenderPlan };
}

export default MarketProvider;
