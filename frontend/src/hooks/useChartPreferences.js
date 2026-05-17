/**
 * useChartPreferences — Save/Load Chart Zoom & Display Preferences
 * =================================================================
 * 
 * Persists user chart preferences to localStorage:
 * - Zoom level per timeframe
 * - Visible range (start/end times)
 * - Overlay visibility states
 * - Chart height
 */
import { useState, useEffect, useCallback } from 'react';

const STORAGE_KEY = 'ta_engine_chart_preferences';

// Default preferences per timeframe
const DEFAULT_PREFERENCES = {
  '4H': { visibleBars: 60, fitContent: false },
  '1D': { visibleBars: 90, fitContent: false },
  '7D': { visibleBars: 0, fitContent: true },
  '1M': { visibleBars: 0, fitContent: true },
  '6M': { visibleBars: 0, fitContent: true },
  '1Y': { visibleBars: 0, fitContent: true },
};

// Overlay default states
const DEFAULT_OVERLAYS = {
  fib: false,
  pattern: true,
  setup: false,
  ta: false,
};

/**
 * Get preferences from localStorage
 */
function loadPreferences() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (err) {
    console.warn('[ChartPrefs] Failed to load preferences:', err);
  }
  return null;
}

/**
 * Save preferences to localStorage
 */
function savePreferences(prefs) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch (err) {
    console.warn('[ChartPrefs] Failed to save preferences:', err);
  }
}

/**
 * useChartPreferences Hook
 */
export function useChartPreferences(symbol = 'BTCUSDT') {
  const [preferences, setPreferences] = useState(() => {
    const stored = loadPreferences();
    return stored || {
      symbols: {},
      global: {
        overlays: DEFAULT_OVERLAYS,
        chartHeight: 400,
        autoFit: true,
      },
    };
  });

  // Save to localStorage whenever preferences change
  useEffect(() => {
    savePreferences(preferences);
  }, [preferences]);

  /**
   * Get zoom preference for specific timeframe
   */
  const getZoomForTimeframe = useCallback((timeframe) => {
    const symbolPrefs = preferences.symbols[symbol] || {};
    const tfPrefs = symbolPrefs[timeframe];
    
    if (tfPrefs) {
      return tfPrefs;
    }
    
    // Return default for timeframe
    return DEFAULT_PREFERENCES[timeframe] || { visibleBars: 60, fitContent: false };
  }, [preferences, symbol]);

  /**
   * Save zoom preference for specific timeframe
   */
  const saveZoomForTimeframe = useCallback((timeframe, zoomConfig) => {
    setPreferences(prev => ({
      ...prev,
      symbols: {
        ...prev.symbols,
        [symbol]: {
          ...(prev.symbols[symbol] || {}),
          [timeframe]: {
            visibleBars: zoomConfig.visibleBars || 60,
            fitContent: zoomConfig.fitContent || false,
            visibleRange: zoomConfig.visibleRange || null,
            lastUpdated: Date.now(),
          },
        },
      },
    }));
  }, [symbol]);

  /**
   * Get visible range (from/to times) for timeframe
   */
  const getVisibleRange = useCallback((timeframe) => {
    const tfPrefs = getZoomForTimeframe(timeframe);
    return tfPrefs.visibleRange || null;
  }, [getZoomForTimeframe]);

  /**
   * Save visible range after user scrolls/zooms
   */
  const saveVisibleRange = useCallback((timeframe, from, to) => {
    setPreferences(prev => ({
      ...prev,
      symbols: {
        ...prev.symbols,
        [symbol]: {
          ...(prev.symbols[symbol] || {}),
          [timeframe]: {
            ...(prev.symbols[symbol]?.[timeframe] || getZoomForTimeframe(timeframe)),
            visibleRange: { from, to },
            lastUpdated: Date.now(),
          },
        },
      },
    }));
  }, [symbol, getZoomForTimeframe]);

  /**
   * Get overlay visibility states
   */
  const getOverlays = useCallback(() => {
    return preferences.global?.overlays || DEFAULT_OVERLAYS;
  }, [preferences]);

  /**
   * Toggle overlay visibility
   */
  const toggleOverlay = useCallback((overlayKey) => {
    setPreferences(prev => ({
      ...prev,
      global: {
        ...prev.global,
        overlays: {
          ...(prev.global?.overlays || DEFAULT_OVERLAYS),
          [overlayKey]: !(prev.global?.overlays?.[overlayKey] ?? DEFAULT_OVERLAYS[overlayKey]),
        },
      },
    }));
  }, []);

  /**
   * Set overlay visibility
   */
  const setOverlay = useCallback((overlayKey, visible) => {
    setPreferences(prev => ({
      ...prev,
      global: {
        ...prev.global,
        overlays: {
          ...(prev.global?.overlays || DEFAULT_OVERLAYS),
          [overlayKey]: visible,
        },
      },
    }));
  }, []);

  /**
   * Get chart height
   */
  const getChartHeight = useCallback(() => {
    return preferences.global?.chartHeight || 400;
  }, [preferences]);

  /**
   * Set chart height
   */
  const setChartHeight = useCallback((height) => {
    setPreferences(prev => ({
      ...prev,
      global: {
        ...prev.global,
        chartHeight: height,
      },
    }));
  }, []);

  /**
   * Reset preferences for symbol
   */
  const resetSymbolPreferences = useCallback(() => {
    setPreferences(prev => ({
      ...prev,
      symbols: {
        ...prev.symbols,
        [symbol]: {},
      },
    }));
  }, [symbol]);

  /**
   * Reset all preferences
   */
  const resetAllPreferences = useCallback(() => {
    setPreferences({
      symbols: {},
      global: {
        overlays: DEFAULT_OVERLAYS,
        chartHeight: 400,
        autoFit: true,
      },
    });
  }, []);

  return {
    // Zoom
    getZoomForTimeframe,
    saveZoomForTimeframe,
    getVisibleRange,
    saveVisibleRange,
    
    // Overlays
    overlays: getOverlays(),
    toggleOverlay,
    setOverlay,
    
    // Chart
    chartHeight: getChartHeight(),
    setChartHeight,
    
    // Reset
    resetSymbolPreferences,
    resetAllPreferences,
    
    // Raw
    preferences,
  };
}

export default useChartPreferences;
