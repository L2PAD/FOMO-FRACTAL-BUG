/**
 * Unified Notification Engine — Frontend API
 */
import { api } from './client';

const BASE = '/api/notifications';

// ── Events ──
export const publishEvent = (event) => api.post(`${BASE}/events/publish`, event).then(r => r.data);
export const getEvents = (params = {}) => api.get(`${BASE}/events`, { params }).then(r => r.data);
export const getEventStats = () => api.get(`${BASE}/events-stats`).then(r => r.data);

// ── Feed (Bell + Notifications Page) ──
export const getFeed = (audience = 'user', limit = 20) =>
  api.get(`${BASE}/feed`, { params: { audience, limit } }).then(r => r.data);

export const getUnreadCount = (audience = 'user') =>
  api.get(`${BASE}/unread-count`, { params: { audience } }).then(r => r.data);

export const markAsRead = (notificationId) =>
  api.post(`${BASE}/read/${notificationId}`).then(r => r.data);

export const markAllRead = (audience = 'user') =>
  api.post(`${BASE}/read-all`, null, { params: { audience } }).then(r => r.data);

// ── Rules ──
export const getRules = () => api.get(`${BASE}/rules`).then(r => r.data);
export const createRule = (rule) => api.post(`${BASE}/rules`, rule).then(r => r.data);
export const updateRule = (ruleId, updates) => api.put(`${BASE}/rules/${ruleId}`, updates).then(r => r.data);
export const deleteRule = (ruleId) => api.delete(`${BASE}/rules/${ruleId}`).then(r => r.data);

// ── Stats ──
export const getNotificationStats = () => api.get(`${BASE}/stats`).then(r => r.data);

// ── Init ──
export const initNotifications = () => api.post(`${BASE}/init`).then(r => r.data);
