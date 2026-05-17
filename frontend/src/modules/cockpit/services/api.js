// Cockpit API Service — Sprint 1: Fixed endpoints
// Maps to REAL backend routes (canonical paths)
const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

export const CockpitAPI = {
  // Dashboard / Overview — remapped to existing routes
  async getDashboardState(symbol = 'BTC') {
    const res = await fetch(`${API_BASE}/api/dashboard/state`);
    return res.json();
  },

  async getDashboardMulti() {
    const res = await fetch(`${API_BASE}/api/dashboard/state`);
    return res.json();
  },

  async getPortfolioSummary() {
    const res = await fetch(`${API_BASE}/api/portfolio/summary`);
    return res.json();
  },

  async getRiskSummary() {
    const res = await fetch(`${API_BASE}/api/risk/dashboard`);
    return res.json();
  },

  async getAlerts() {
    const res = await fetch(`${API_BASE}/api/alerts/feed?limit=10`);
    return res.json();
  },

  // Chart / Research — remapped to real TA routes
  async getChartFullAnalysis(symbol, timeframe) {
    const res = await fetch(`${API_BASE}/api/v1/chart/full-analysis/${symbol}/${timeframe}`);
    return res.json();
  },

  async getResearchPayload(symbol = 'BTCUSDT', timeframe = '4h') {
    const res = await fetch(`${API_BASE}/api/v1/research-analytics/full-payload/${symbol}/${timeframe}`);
    return res.json();
  },

  async getSignalExplanation(symbol, timeframe) {
    const res = await fetch(`${API_BASE}/api/v1/signal/explanation/${symbol}/${timeframe}`);
    return res.json();
  },

  // Market Regime — remapped to dashboard regime
  async getMarketRegime() {
    const res = await fetch(`${API_BASE}/api/dashboard/regime`);
    return res.json();
  },

  // Capital Flow
  async getCapitalFlowSummary() {
    const res = await fetch(`${API_BASE}/api/v1/capital-flow/summary`);
    return res.json();
  },

  // Fractal
  async getFractalMatches(symbol) {
    const res = await fetch(`${API_BASE}/api/v1/fractal/summary/${symbol}`);
    return res.json();
  },

  // Microstructure
  async getMicrostructureState(symbol) {
    const res = await fetch(`${API_BASE}/api/terminal/state/${symbol}/micro`);
    return res.json();
  },

  // Hypotheses — remapped to real hypothesis routes
  async getHypothesisList() {
    const res = await fetch(`${API_BASE}/api/hypothesis/list`);
    return res.json();
  },

  // Execution — remapped to Runtime decisions (canonical path)
  async getApprovalPending() {
    const res = await fetch(`${API_BASE}/api/runtime/decisions/pending`);
    return res.json();
  },

  async approveExecution(decisionId) {
    const res = await fetch(`${API_BASE}/api/runtime/decisions/${decisionId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    return res.json();
  },

  async rejectExecution(decisionId, reason) {
    const res = await fetch(`${API_BASE}/api/runtime/decisions/${decisionId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason })
    });
    return res.json();
  },

  async getExecutionDetail(symbol) {
    const res = await fetch(`${API_BASE}/api/v1/execution/active/${symbol}`);
    return res.json();
  },

  async getActiveOrders() {
    const res = await fetch(`${API_BASE}/api/terminal/orders/open`);
    return res.json();
  },

  async getFills() {
    const res = await fetch(`${API_BASE}/api/trades/fills`);
    return res.json();
  },

  // Portfolio — remapped to real portfolio routes
  async getPortfolioState() {
    const res = await fetch(`${API_BASE}/api/portfolio/state`);
    return res.json();
  },

  // Risk — remapped to real risk routes
  async getRiskState() {
    const res = await fetch(`${API_BASE}/api/risk/state`);
    return res.json();
  },

  async getRiskBudgetSummary() {
    const res = await fetch(`${API_BASE}/api/risk/dashboard`);
    return res.json();
  },

  // System — remapped to real system routes
  async getSystemStatus() {
    const res = await fetch(`${API_BASE}/api/system/health`);
    return res.json();
  },

  async getValidationReport() {
    const res = await fetch(`${API_BASE}/api/validation/stats`);
    return res.json();
  },

  // TA Engine (existing — already correct)
  async getTARegistry() {
    const res = await fetch(`${API_BASE}/api/ta/registry`);
    return res.json();
  },

  async getTAPatterns() {
    const res = await fetch(`${API_BASE}/api/ta/patterns`);
    return res.json();
  },

  async analyzeTechnical(symbol, timeframe) {
    const res = await fetch(`${API_BASE}/api/ta/analyze?symbol=${symbol}&timeframe=${timeframe}`, {
      method: 'POST'
    });
    return res.json();
  }
};

export default CockpitAPI;
