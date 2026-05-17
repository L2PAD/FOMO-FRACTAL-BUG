/**
 * taPredictionApi.js
 * 
 * Single source of truth for TA-Prediction-Intelligence (R5..R10) admin observability.
 * 
 * Principles (PHASE 2 / I1):
 *   - Read-only. No mutations.
 *   - Honest envelopes. NEVER fabricate values when backend says null/unavailable.
 */

const API_BASE = (process.env.REACT_APP_BACKEND_URL || '').replace(/\/$/, '');

export class TaApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function getJson(path) {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url);
  if (!res.ok) {
    let body = null;
    try { body = await res.json(); } catch { /* ignore */ }
    throw new TaApiError(`GET ${path} → HTTP ${res.status}`, res.status, body);
  }
  return res.json();
}

export function fetchLive(symbol, tf) {
  const qs = `symbol=${encodeURIComponent(symbol)}&tf=${encodeURIComponent(tf)}`;
  return getJson(`/api/ta-prediction-intelligence/live?${qs}`);
}

export function fetchDataHealth() {
  return getJson(`/api/ta-prediction-intelligence/data-health`);
}

export function fetchShadowGateStats() {
  return getJson(`/api/ta-prediction-intelligence/shadow-gate/stats`);
}

export function fetchShadowGateRecent(limit = 20) {
  return getJson(`/api/ta-prediction-intelligence/shadow-gate/recent?limit=${limit}`);
}

export function fetchShadowGateEvalSummary() {
  return getJson(`/api/ta-prediction-intelligence/shadow-gate-eval/summary`);
}

export function fetchShadowGateAnalyticsReport() {
  return getJson(`/api/ta-prediction-intelligence/shadow-gate-analytics/report`);
}
