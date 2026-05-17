/**
 * Telegram Intelligence API - Extended
 * Full API client for Telegram Intelligence module
 */
import { api } from './client';

const API_BASE = '/api/admin/telegram-intel';
const API_PUBLIC = '/api/telegram-intel';

// Health check
export async function getTelegramIntelHealth() {
  const response = await api.get(`${API_BASE}/health`);
  return response.data;
}

// ==================== Intel Ranking ====================

export async function getIntelTop(params = {}) {
  const response = await api.get(`${API_PUBLIC}/intel/top`, { params });
  return response.data;
}

/**
 * Get intel leaderboard
 * Supports mode=intel|momentum (PATCH-1)
 */
export async function getIntelLeaderboard(params = {}) {
  const response = await api.get(`${API_PUBLIC}/intel/list`, { params });
  // Normalize response to ensure consistent structure
  const data = response.data;
  return {
    ...data,
    limit: data.limit || params.limit || 25,
    stats: data.stats || {
      total: data.total || 0,
      trackedChannels: data.stats?.trackedChannels || data.total || 0,
      avgIntel: data.stats?.avgIntel || 0,
      avgMomentum: data.stats?.avgMomentum || 0,
      highAlpha: data.stats?.highAlphaCount || 0,
      highFraud: data.stats?.highFraudCount || 0,
    },
  };
}

export async function getChannelIntel(username) {
  const response = await api.get(`${API_PUBLIC}/intel/${username}`);
  return response.data;
}

export async function computeChannelIntel(username) {
  const response = await api.post(`${API_BASE}/intel/compute/channel`, { username });
  return response.data;
}

export async function recomputeIntel(limit = 200) {
  const response = await api.post(`${API_BASE}/intel/recompute`, { limit });
  return response.data;
}

// ==================== Network Alpha ====================

export async function getNetworkAlphaTop(params = {}) {
  const response = await api.get(`${API_PUBLIC}/network-alpha/top`, { params });
  return response.data;
}

export async function getChannelNetworkAlpha(username) {
  const response = await api.get(`${API_PUBLIC}/network-alpha/channel/${username}`);
  return response.data;
}

export async function getTokenNetworkAlpha(token) {
  const response = await api.get(`${API_PUBLIC}/network-alpha/token/${token}`);
  return response.data;
}

export async function runNetworkAlpha(lookbackDays = 90) {
  const response = await api.post(`${API_BASE}/network-alpha/run`, { lookbackDays });
  return response.data;
}

// ==================== Temporal ====================

export async function getChannelTemporal(username, days = 90) {
  const response = await api.get(`${API_PUBLIC}/temporal/${username}`, { params: { days } });
  return response.data;
}

export async function getTopMovers(params = {}) {
  const response = await api.get(`${API_PUBLIC}/temporal/top-movers`, { params });
  return response.data;
}

export async function runTemporalSnapshot(limit = 500) {
  const response = await api.post(`${API_BASE}/temporal/snapshot/run`, { limit });
  return response.data;
}

// ==================== Explain ====================

export async function getChannelExplain(username) {
  const response = await api.get(`${API_PUBLIC}/intel/explain/${username}`);
  return response.data;
}

// ==================== Channel Token Mentions (Public) ====================

/**
 * Get channel token mentions with returns data
 * Used by Channel Detail Page - Token Mentions Table
 * @param {string} username - Channel username
 * @param {object} opts - Options { days, limit, evaluated }
 */
export async function getChannelTokenMentions(username, opts = {}) {
  const { days = 90, limit = 100, evaluated = false } = opts;
  const response = await api.get(`${API_PUBLIC}/channel/${username}/mentions`, {
    params: { days, limit, evaluated },
  });
  return response.data;
}

// ==================== Network Evidence (Block UI-4) ====================

/**
 * Get channel's network alpha evidence - tokens where channel was early
 * @param {string} username - Channel username
 * @param {number} limit - Max number of tokens to return
 */
export async function getChannelNetworkEvidence(username, limit = 25) {
  const response = await api.get(`${API_PUBLIC}/channel/${username}/network-evidence`, {
    params: { limit },
  });
  return response.data;
}

// ==================== Compare Panel (Block UI-5) ====================

/**
 * Get channel's position comparison in the network
 * @param {string} username - Channel username
 */
export async function getChannelCompare(username) {
  const response = await api.get(`${API_PUBLIC}/channel/${username}/compare`);
  return response.data;
}

// ==================== Alpha v2 ====================

export async function getAlphaLeaderboard(limit = 20) {
  const response = await api.get(`${API_BASE}/alpha/v2/leaderboard`, { params: { limit } });
  return response.data;
}

export async function computeAlphaBatch(limit = 50, days = 90) {
  const response = await api.post(`${API_BASE}/alpha/v2/compute/batch`, { limit, days });
  return response.data;
}

// ==================== Credibility ====================

export async function getCredibilityLeaderboard(limit = 20) {
  const response = await api.get(`${API_BASE}/credibility/leaderboard`, { params: { limit } });
  return response.data;
}

export async function computeCredibilityBatch(limit = 50) {
  const response = await api.post(`${API_BASE}/credibility/batch`, { limit });
  return response.data;
}

// ==================== Governance ====================

export async function getActiveConfig() {
  const response = await api.get(`${API_BASE}/governance/config/active`);
  return response.data;
}

export async function setOverride(username, data) {
  const response = await api.post(`${API_BASE}/governance/override`, { username, ...data });
  return response.data;
}

// ==================== Legacy (keep for backwards compat) ====================

export async function ingestChannel(username) {
  const response = await api.post(`${API_BASE}/ingestion/channel`, { username });
  return response.data;
}

export async function runIngestionBatch(limit = 10) {
  const response = await api.post(`${API_BASE}/ingestion/run`, { limit });
  return response.data;
}

export async function getChannelState(username) {
  const response = await api.get(`${API_BASE}/state/${username}`);
  return response.data;
}

export async function getChannelMetrics(username) {
  const response = await api.get(`${API_BASE}/metrics/${username}`);
  return response.data;
}

export async function getChannelFraud(username) {
  const response = await api.get(`${API_BASE}/fraud/${username}`);
  return response.data;
}

export async function runPipelineChannel(username) {
  const response = await api.post(`${API_BASE}/pipeline/channel`, { username });
  return response.data;
}

export async function runPipelineFull() {
  const response = await api.post(`${API_BASE}/pipeline/run`);
  return response.data;
}

export async function scanChannelForTokens(username, days = 30, minConfidence = 0.35) {
  const response = await api.post(`${API_BASE}/alpha/scan/channel`, {
    username,
    days,
    minConfidence,
  });
  return response.data;
}

export async function getChannelMentions(username, days = 30, limit = 200) {
  const response = await api.get(`${API_BASE}/alpha/mentions/${username}`, {
    params: { days, limit },
  });
  return response.data;
}

export async function getAlphaStats(days = 30) {
  const response = await api.get(`${API_BASE}/alpha/stats`, {
    params: { days },
  });
  return response.data;
}

export async function scanBatchChannels(usernames, days = 30, minConfidence = 0.35) {
  const response = await api.post(`${API_BASE}/alpha/scan/batch`, {
    usernames,
    days,
    minConfidence,
  });
  return response.data;
}

// ==================== Block UI-2: Channel Full ====================

/**
 * Get full channel data in one request
 * Used by Channel Detail Page
 */
export async function getChannelFull(username) {
  const response = await api.get(`${API_PUBLIC}/channel/${username}/full`);
  return response.data;
}

// ==================== Block UI-6: Movers ====================

/**
 * Get top movers by score change
 * @param {object} params - { days, metric, limit }
 */
export async function getMovers(params = {}) {
  const response = await api.get(`${API_PUBLIC}/movers`, { params });
  return response.data;
}

// ==================== Block ALERTS ====================

/**
 * Get alerts list
 */
export async function getAlerts(params = {}) {
  const response = await api.get(`${API_PUBLIC}/alerts`, { params });
  return response.data;
}

/**
 * Run alerts watcher (admin)
 */
export async function runAlertsWatcher(days = 7) {
  const response = await api.post(`${API_BASE}/alerts/run`, { days });
  return response.data;
}

// ==================== Governance Admin ====================

/**
 * Get governance override for channel
 */
export async function getGovernanceOverride(username) {
  const response = await api.get(`${API_BASE}/governance/${username}`);
  return response.data;
}

/**
 * Apply governance override
 */
export async function applyGovernanceOverride(username, data) {
  const response = await api.post(`${API_BASE}/governance/${username}/override`, data);
  return response.data;
}

/**
 * Get current alert config
 */
export async function getAlertConfig() {
  const response = await api.get(`${API_BASE}/config/current`);
  return response.data;
}

// ==================== Momentum Engine (M-1, M-2, M-3) ====================

/**
 * Get top momentum channels
 */
export async function getMomentumTop(params = {}) {
  const response = await api.get(`${API_PUBLIC}/momentum/top`, { params });
  return response.data;
}

/**
 * Get channel momentum history
 */
export async function getChannelMomentum(username, params = {}) {
  const response = await api.get(`${API_PUBLIC}/channel/${username}/momentum`, { params });
  return response.data;
}

/**
 * Get momentum movers
 */
export async function getMomentumMovers(params = {}) {
  const response = await api.get(`${API_PUBLIC}/momentum/movers`, { params });
  return response.data;
}

/**
 * Run momentum pipeline (admin)
 */
export async function runMomentumPipeline(params = {}) {
  const response = await api.post(`${API_BASE}/momentum/pipeline`, params);
  return response.data;
}

/**
 * Build leaderboard snapshots (admin)
 */
export async function buildLeaderboard(params = {}) {
  const response = await api.post(`${API_BASE}/leaderboard/build`, params);
  return response.data;
}

// ==================== Watchlist (BLOCK 5.1) ====================

/**
 * Get user's watchlist
 */
export async function getWatchlist(params = {}) {
  const response = await api.get(`${API_PUBLIC}/watchlist`, { params });
  return response.data;
}

/**
 * Add channel to watchlist
 */
export async function addToWatchlist(username, data = {}) {
  const response = await api.post(`${API_PUBLIC}/watchlist`, { username, ...data });
  return response.data;
}

/**
 * Remove channel from watchlist
 */
export async function removeFromWatchlist(username) {
  const response = await api.delete(`${API_PUBLIC}/watchlist/${username}`);
  return response.data;
}

/**
 * Update watchlist item
 */
export async function updateWatchlistItem(username, data) {
  const response = await api.patch(`${API_PUBLIC}/watchlist/${username}`, data);
  return response.data;
}

/**
 * Check if channel is in watchlist
 */
export async function checkWatchlist(username) {
  const response = await api.get(`${API_PUBLIC}/watchlist/check/${username}`);
  return response.data;
}

/**
 * Bulk check watchlist status
 */
export async function bulkCheckWatchlist(usernames) {
  const response = await api.post(`${API_PUBLIC}/watchlist/check-bulk`, { usernames });
  return response.data;
}

/**
 * Get watchlist tags
 */
export async function getWatchlistTags() {
  const response = await api.get(`${API_PUBLIC}/watchlist/tags`);
  return response.data;
}

/**
 * Get watchlist count
 */
export async function getWatchlistCount() {
  const response = await api.get(`${API_PUBLIC}/watchlist/count`);
  return response.data;
}

// ==================== User Alerts (BLOCK 5.2) ====================

/**
 * Get personalized alerts for current user
 */
export async function getUserAlerts(params = {}) {
  const response = await api.get(`${API_PUBLIC}/user/alerts`, { params });
  return response.data;
}

/**
 * Mark alerts as read
 */
export async function markAlertsRead(alertIds) {
  const response = await api.post(`${API_PUBLIC}/user/alerts/read`, { alertIds });
  return response.data;
}

/**
 * Mark all alerts as read
 */
export async function markAllAlertsRead() {
  const response = await api.post(`${API_PUBLIC}/user/alerts/read-all`);
  return response.data;
}

/**
 * Get unread alert count
 */
export async function getUnreadAlertCount() {
  const response = await api.get(`${API_PUBLIC}/user/alerts/unread-count`);
  return response.data;
}

/**
 * Delete alert
 */
export async function deleteUserAlert(id) {
  const response = await api.delete(`${API_PUBLIC}/user/alerts/${id}`);
  return response.data;
}

/**
 * Run personalized alerts engine (admin)
 */
export async function runUserAlerts(params = {}) {
  const response = await api.post(`${API_BASE}/user-alerts/run`, params);
  return response.data;
}

// ==================== Recommendations (U-8) ====================

/**
 * Get similar channels based on utility metrics
 * @param {string} username - Channel username
 * @param {number} limit - Max number of similar channels (default 6)
 */
export async function getSimilarChannels(username, limit = 6) {
  const response = await api.get(`${API_PUBLIC}/channel/${username}/similar`, {
    params: { limit },
  });
  return response.data;
}

// ==================== Lifecycle Transitions (U-9) ====================

/**
 * Get lifecycle transitions
 * @param {object} params - { days, limit, filter }
 */
export async function getLifecycleTransitions(params = {}) {
  const response = await api.get(`${API_PUBLIC}/lifecycle/transitions`, { params });
  return response.data;
}

/**
 * Run lifecycle transitions computation (admin)
 */
export async function runLifecycleTransitions(days = 7) {
  const response = await api.post(`${API_BASE}/lifecycle/transitions/run`, null, {
    params: { days },
  });
  return response.data;
}

// ==================== Signals (U-10) ====================

/**
 * Get signals list
 * @param {object} params - { days, limit, type, severity }
 */
export async function getSignals(params = {}) {
  const response = await api.get(`${API_PUBLIC}/signals`, { params });
  return response.data;
}

/**
 * Get single signal by ID
 */
export async function getSignal(id) {
  const response = await api.get(`${API_PUBLIC}/signals/${id}`);
  return response.data;
}

/**
 * Run signal generation (admin)
 */
export async function runSignals(days = 7) {
  const response = await api.post(`${API_BASE}/signals/run`, null, {
    params: { days },
  });
  return response.data;
}

export default {
  getTelegramIntelHealth,
  getIntelTop,
  getChannelIntel,
  computeChannelIntel,
  recomputeIntel,
  getNetworkAlphaTop,
  getChannelNetworkAlpha,
  getTokenNetworkAlpha,
  runNetworkAlpha,
  getChannelTemporal,
  getTopMovers,
  runTemporalSnapshot,
  getChannelExplain,
  getChannelTokenMentions,
  getChannelNetworkEvidence,
  getChannelCompare,
  getAlphaLeaderboard,
  computeAlphaBatch,
  getCredibilityLeaderboard,
  computeCredibilityBatch,
  getActiveConfig,
  setOverride,
  ingestChannel,
  runIngestionBatch,
  getChannelState,
  getChannelMetrics,
  getChannelFraud,
  runPipelineChannel,
  runPipelineFull,
  scanChannelForTokens,
  getChannelMentions,
  getAlphaStats,
  scanBatchChannels,
};
