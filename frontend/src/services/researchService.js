/**
 * Research Data Layer — PHASE F1
 * 
 * Unified data service for Research UI.
 * All Research components use this single data model.
 * 
 * UI → Research Data Layer → Backend API
 */

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

// ============================================
// TYPES / INTERFACES
// ============================================

/**
 * @typedef {Object} MarketState
 * @property {string} symbol
 * @property {string} timeframe
 * @property {number} price
 * @property {number} change
 * @property {number} high
 * @property {number} low
 */

/**
 * @typedef {Object} RegimeState
 * @property {string} state - TRENDING_UP, TRENDING_DOWN, RANGE, VOLATILE
 * @property {number} confidence
 * @property {number} transitionRisk
 */

/**
 * @typedef {Object} CapitalFlowState
 * @property {string} bias - BULLISH, BEARISH, NEUTRAL
 * @property {string} rotation - RISK_ON, RISK_OFF, NEUTRAL
 * @property {number} strength
 * @property {number} confidence
 */

/**
 * @typedef {Object} FractalState
 * @property {string} alignment - BULLISH, BEARISH, NEUTRAL
 * @property {string} match - Pattern name
 * @property {number} similarity
 * @property {number} confidence
 */

/**
 * @typedef {Object} SignalState
 * @property {string} direction
 * @property {number} confidence
 * @property {string} strength
 * @property {string} summary
 * @property {Array} drivers
 * @property {Array} conflicts
 */

/**
 * @typedef {Object} HypothesisItem
 * @property {string} hypothesis_id
 * @property {string} name
 * @property {string} type
 * @property {string} direction
 * @property {number} confidence
 * @property {number} reliability
 * @property {string} alphaFamily
 * @property {string} decayStage
 * @property {number} scenarioAlignment
 * @property {number} capitalFlowAlignment
 * @property {number} fractalAlignment
 * @property {string} explanation
 * @property {Array} conflicts
 * @property {boolean} executionEligibility
 */

/**
 * @typedef {Object} ChartData
 * @property {Array} candles
 * @property {Array} volume
 * @property {Array} indicators
 * @property {Array} patterns
 * @property {Array} supportResistance
 * @property {Array} liquidityZones
 * @property {Object} hypothesis
 * @property {Array} fractalMatches
 */

/**
 * @typedef {Object} ResearchState
 * @property {MarketState} market
 * @property {RegimeState} regime
 * @property {CapitalFlowState} capitalFlow
 * @property {FractalState} fractal
 * @property {SignalState} signal
 * @property {Object} hypothesis - { top: HypothesisItem, list: HypothesisItem[] }
 * @property {ChartData} chart
 * @property {boolean} loading
 * @property {string|null} error
 * @property {number} lastUpdated
 */

// ============================================
// DEFAULT STATE
// ============================================

const DEFAULT_RESEARCH_STATE = {
  market: {
    symbol: 'BTCUSDT',
    timeframe: '1h',
    price: 0,
    change: 0,
    high: 0,
    low: 0,
  },
  regime: {
    state: 'LOADING',
    confidence: 0,
    transitionRisk: 0,
  },
  capitalFlow: {
    bias: 'NEUTRAL',
    rotation: 'NEUTRAL',
    strength: 0,
    confidence: 0,
  },
  fractal: {
    alignment: 'NEUTRAL',
    match: '',
    similarity: 0,
    confidence: 0,
  },
  signal: {
    direction: 'neutral',
    confidence: 0,
    strength: 'NEUTRAL',
    summary: '',
    drivers: [],
    conflicts: [],
  },
  hypothesis: {
    top: null,
    list: [],
  },
  chart: {
    candles: [],
    volume: [],
    indicators: [],
    patterns: [],
    supportResistance: [],
    liquidityZones: [],
    hypothesis: null,
    fractalMatches: [],
  },
  loading: false,
  error: null,
  lastUpdated: 0,
};

// ============================================
// CACHE
// ============================================

let cache = {
  data: null,
  timestamp: 0,
  key: '',
};

const CACHE_TTL = 30000; // 30 seconds

const getCacheKey = (symbol, timeframe) => `${symbol}_${timeframe}`;

const isCacheValid = (symbol, timeframe) => {
  const key = getCacheKey(symbol, timeframe);
  return cache.key === key && (Date.now() - cache.timestamp) < CACHE_TTL;
};

/**
 * Deep clone the default state to avoid mutation
 */
const createFreshState = () => JSON.parse(JSON.stringify(DEFAULT_RESEARCH_STATE));

// ============================================
// API HELPERS
// ============================================

const fetchWithTimeout = async (url, options = {}, timeout = 10000) => {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(id);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    return response.json();
  } catch (error) {
    clearTimeout(id);
    throw error;
  }
};

const safeApiCall = async (apiCall, fallback = null) => {
  try {
    return await apiCall();
  } catch (error) {
    console.warn('[ResearchService] API call failed:', error.message);
    return fallback;
  }
};

// ============================================
// RESEARCH SERVICE
// ============================================

export const ResearchService = {
  /**
   * Get full research state for symbol/timeframe
   * Primary endpoint: /chart/full-analysis
   */
  async getResearchState(symbol, timeframe) {
    // Check cache
    if (isCacheValid(symbol, timeframe) && cache.data) {
      return { ...cache.data, fromCache: true };
    }

    const state = createFreshState();
    state.loading = true;
    state.market.symbol = symbol;
    state.market.timeframe = timeframe;

    try {
      // Primary endpoint - TA Engine MTF (FIXED: was /api/v1/chart/full-analysis which doesn't exist)
      const mtfResponse = await fetchWithTimeout(
        `${API_BASE}/api/ta-engine/mtf/${symbol.replace('USDT', '')}?timeframes=${timeframe}`
      );
      
      // Extract TF data from MTF response
      const chartAnalysis = mtfResponse?.tf_map?.[timeframe] || {};

      if (chartAnalysis) {
        // Parse chart data
        state.chart.candles = chartAnalysis.candles || [];
        state.chart.volume = chartAnalysis.volume || [];
        state.chart.indicators = chartAnalysis.indicators || [];
        state.chart.patterns = chartAnalysis.patterns || [];
        state.chart.supportResistance = chartAnalysis.support_resistance || [];
        state.chart.liquidityZones = chartAnalysis.liquidity_zones || [];
        state.chart.hypothesis = chartAnalysis.hypothesis || null;
        state.chart.fractalMatches = chartAnalysis.fractal_matches || [];

        // Parse market state from candles
        if (state.chart.candles.length > 0) {
          const candles = state.chart.candles;
          const latest = candles[candles.length - 1];
          const first = candles[0];
          
          state.market.price = latest.close || latest.c || 0;
          state.market.high = Math.max(...candles.map(c => c.high || c.h || 0));
          state.market.low = Math.min(...candles.map(c => c.low || c.l || Infinity));
          state.market.change = first.open ? ((latest.close - first.open) / first.open * 100) : 0;
        }

        // Parse regime from chart analysis
        if (chartAnalysis.market_regime) {
          state.regime.state = chartAnalysis.market_regime;
          state.regime.confidence = chartAnalysis.regime_confidence || 75;
        }

        // Parse hypothesis visualization
        if (chartAnalysis.hypothesis) {
          state.signal.direction = chartAnalysis.hypothesis.direction || 'neutral';
          state.signal.confidence = chartAnalysis.hypothesis.confidence || 0;
        }
      }

      // Fetch additional data in parallel
      const [capitalFlow, fractalSummary, signalExplanation, hypothesisList, hypothesisTop] = await Promise.all([
        safeApiCall(() => fetchWithTimeout(`${API_BASE}/api/v1/capital-flow/summary`)),
        safeApiCall(() => fetchWithTimeout(`${API_BASE}/api/v1/fractal/summary/${symbol}`)),
        safeApiCall(() => fetchWithTimeout(`${API_BASE}/api/v1/signal/explanation/${symbol}/${timeframe}`)),
        safeApiCall(() => fetchWithTimeout(`${API_BASE}/api/hypothesis/list`)),
        safeApiCall(() => fetchWithTimeout(`${API_BASE}/api/hypothesis/top?limit=1`)),
      ]);

      // Parse capital flow
      if (capitalFlow) {
        const cs = capitalFlow.current_state || capitalFlow.score || {};
        state.capitalFlow.bias = cs.flow_bias || 'NEUTRAL';
        state.capitalFlow.strength = Math.round((cs.flow_strength || 0) * 100);
        state.capitalFlow.confidence = Math.round((cs.flow_confidence || 0) * 100);
        state.capitalFlow.rotation = cs.rotation_type || capitalFlow.rotation?.rotation_type || 'NEUTRAL';
      }

      // Parse fractal
      if (fractalSummary && fractalSummary.current) {
        state.fractal.alignment = fractalSummary.current.bias || 'NEUTRAL';
        state.fractal.confidence = Math.round((fractalSummary.current.confidence || 0) * 100);
        state.fractal.similarity = Math.round((fractalSummary.current.alignment || 0) * 100);
        // Use state distribution to derive pattern name
        if (fractalSummary.state_distribution) {
          const dist = fractalSummary.state_distribution;
          const dominant = Object.entries(dist).sort((a, b) => b[1] - a[1])[0];
          if (dominant && dominant[1] > 0) {
            state.fractal.match = dominant[0].replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
          }
        }
      }
      // Override with chart fractal matches if available
      if (state.chart.fractalMatches && state.chart.fractalMatches.length > 0) {
        const topMatch = state.chart.fractalMatches[0];
        state.fractal.match = topMatch.historical_period || topMatch.pattern_name || state.fractal.match || 'Pattern Match';
        state.fractal.similarity = Math.round((topMatch.similarity || 0) * 100);
      }

      // Parse signal explanation
      if (signalExplanation) {
        state.signal.direction = signalExplanation.direction || 'neutral';
        state.signal.confidence = Math.round((signalExplanation.confidence || 0) * 100);
        state.signal.strength = signalExplanation.strength || 'NEUTRAL';
        state.signal.summary = signalExplanation.summary || '';
        state.signal.drivers = (signalExplanation.drivers || []).map(d => ({
          name: d.name,
          contribution: d.contribution,
          type: d.driver_type || d.type,
          description: d.description,
        }));
        state.signal.conflicts = (signalExplanation.conflicts || []).map(c => ({
          name: c.name,
          severity: c.severity,
          description: c.description,
        }));
      }

      // Parse hypothesis list
      if (hypothesisList && hypothesisList.hypotheses) {
        state.hypothesis.list = hypothesisList.hypotheses.map(h => mapHypothesis(h));
      }

      // Parse top hypothesis
      if (hypothesisTop && hypothesisTop.top_hypotheses && hypothesisTop.top_hypotheses.length > 0) {
        state.hypothesis.top = mapHypothesis(hypothesisTop.top_hypotheses[0]);
      } else if (state.hypothesis.list.length > 0) {
        // Use first from list as top
        state.hypothesis.top = state.hypothesis.list[0];
      }

      state.loading = false;
      state.error = null;
      state.lastUpdated = Date.now();

      // Update cache
      cache = {
        data: state,
        timestamp: Date.now(),
        key: getCacheKey(symbol, timeframe),
      };

      return state;
    } catch (error) {
      console.error('[ResearchService] Failed to load research state:', error);
      state.loading = false;
      state.error = error.message;
      return state;
    }
  },

  /**
   * Get chart presets
   */
  async getPresets() {
    return safeApiCall(
      () => fetchWithTimeout(`${API_BASE}/api/v1/chart/presets`),
      { presets: [], count: 0 }
    );
  },

  /**
   * Get specific preset
   */
  async getPreset(presetId) {
    return safeApiCall(
      () => fetchWithTimeout(`${API_BASE}/api/v1/chart/preset/${presetId}`),
      null
    );
  },

  /**
   * Get system suggestions for symbol
   */
  async getSuggestions(symbol, timeframe) {
    return safeApiCall(
      () => fetchWithTimeout(`${API_BASE}/api/v1/research-analytics/suggestions/${symbol}/${timeframe}`),
      null
    );
  },

  /**
   * Get hypothesis by ID
   */
  async getHypothesis(hypothesisId) {
    const result = await safeApiCall(
      () => fetchWithTimeout(`${API_BASE}/api/hypothesis/${hypothesisId}`),
      null
    );
    return result && result.hypothesis ? mapHypothesis(result.hypothesis) : null;
  },

  /**
   * Get hypothesis results
   */
  async getHypothesisResults(hypothesisId) {
    return safeApiCall(
      () => fetchWithTimeout(`${API_BASE}/api/hypothesis/${hypothesisId}/results`),
      { results: [] }
    );
  },

  /**
   * Clear cache
   */
  clearCache() {
    cache = { data: null, timestamp: 0, key: '' };
  },

  /**
   * Force refresh
   */
  async refresh(symbol, timeframe) {
    this.clearCache();
    return this.getResearchState(symbol, timeframe);
  },
};

// ============================================
// HELPERS
// ============================================

/**
 * Map backend hypothesis to frontend format
 */
function mapHypothesis(h) {
  const eo = h.expected_outcome || {};
  return {
    hypothesis_id: h.hypothesis_id || h.id,
    name: h.name || h.type?.replace(/_/g, ' ') || 'Unknown',
    type: h.type || h.category || 'DIRECTIONAL',
    direction: h.direction || eo.direction || 'NEUTRAL',
    confidence: h.confidence || (eo.confidence ? Math.round(eo.confidence * 100) : 0) || (h.win_rate ? Math.round(h.win_rate * 100) : 0),
    reliability: h.reliability || (h.profit_factor ? Math.round(h.profit_factor * 50) : 0),
    alphaFamily: h.alpha_family || h.category || 'Unknown',
    decayStage: h.decay_stage || 'FRESH',
    scenarioAlignment: h.scenario_alignment || (h.win_rate ? Math.round(h.win_rate * 100) : 70),
    capitalFlowAlignment: h.capital_flow_alignment || 65,
    fractalAlignment: h.fractal_alignment || (h.fractal_similarity_score ? Math.round(h.fractal_similarity_score * 100) : 60),
    explanation: h.explanation || h.description || '',
    conflicts: h.conflicts || [],
    executionEligibility: h.execution_eligible !== false,
    status: h.status || 'ACTIVE',
    conditions: h.conditions || h.condition_set || [],
    expectedOutcome: eo,
    targetMovePct: eo.target_move_pct || null,
    timeHorizonCandles: eo.time_horizon_candles || null,
    applicableRegimes: h.applicable_regimes || [],
    applicableTimeframes: h.applicable_timeframes || [],
    tags: h.tags || [],
  };
}

export default ResearchService;
