import axios, { AxiosInstance, InternalAxiosRequestConfig, AxiosError } from 'axios';
import Constants from 'expo-constants';
import {
  getAccessToken,
  getRefreshToken,
  setSession,
  clearSession,
  getUserIdentity,
} from '../../core/auth/auth-bridge';
import { tokenStorage } from '../token-storage';

/**
 * api-client.ts — HTTP transport layer.
 *
 * After Task 5 (2026-05-12) this module DOES NOT import the session store.
 * It reads the access token, refresh token, and session mutations through
 * the neutral `auth-bridge` so the `session.store ↔ api-client` require
 * cycle is broken at the module-graph level.
 *
 * The bridge is registered by `session.store.ts` after `create()` returns;
 * until that registration happens, `getAccessToken()` returns `null`, which
 * is the same posture as a logged-out user — no exceptions, no undefined.
 */

const API_URL = Constants.expoConfig?.extra?.apiUrl ||
                process.env.EXPO_PUBLIC_BACKEND_URL ||
                'https://expo-telegram-web.preview.emergentagent.com';

export const api: AxiosInstance = axios.create({
  baseURL: API_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Track whether we are currently refreshing to avoid infinite loops
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string | null) => void;
  reject: (error: any) => void;
}> = [];

function processQueue(error: any, token: string | null = null) {
  failedQueue.forEach((p) => {
    if (error) {
      p.reject(error);
    } else {
      p.resolve(token);
    }
  });
  failedQueue = [];
}

// Request interceptor — inject Bearer token from the auth bridge, plus
// the TIER-2 `X-User-Id` fallback so backend capability enforcement can
// resolve a principal even before the JWT path is fully wired.
api.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    const accessToken = getAccessToken();
    if (accessToken && config.headers) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    // X-User-Id fallback. Production: backend prefers the Bearer-derived
    // sub. Dev / not-yet-logged-in: backend uses this header to look up
    // operator_access. `dev_user` is the deterministically-seeded
    // principal (tier=pro, mode=paper) in the sandbox.
    if (config.headers && !config.headers['X-User-Id']) {
      const identity = getUserIdentity();
      config.headers['X-User-Id'] = identity || 'dev_user';
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// Response interceptor — handle 401 with token refresh
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Only attempt refresh on 401 and not on auth endpoints themselves
    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/')
    ) {
      if (isRefreshing) {
        // Queue requests while refresh is in progress
        return new Promise((resolve, reject) => {
          failedQueue.push({
            resolve: (token) => {
              if (token && originalRequest.headers) {
                originalRequest.headers.Authorization = `Bearer ${token}`;
              }
              resolve(api(originalRequest));
            },
            reject,
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const currentRefresh = getRefreshToken();
        if (!currentRefresh) {
          throw new Error('No refresh token available');
        }

        // Call refresh endpoint directly (no interceptors)
        const res = await axios.post(`${API_URL}/api/mobile/auth/refresh`, {
          refreshToken: currentRefresh,
        });

        const { accessToken, refreshToken, user } = res.data;

        // Persist new tokens
        await tokenStorage.set(accessToken, refreshToken);
        setSession({ user, accessToken, refreshToken });

        processQueue(null, accessToken);

        // Retry original request with new token
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${accessToken}`;
        }
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        // Refresh failed — force logout
        await tokenStorage.clear();
        clearSession();
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  },
);
