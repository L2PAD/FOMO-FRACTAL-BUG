/**
 * auth-bridge.ts — direction-breaker for the session.store ↔ api-client cycle.
 *
 * BACKGROUND
 * ----------
 * Before Task 5 (2026-05-12) the auth surface had a circular import:
 *
 *     stores/session.store.ts  ──imports──▶  services/api/api-client.ts
 *     services/api/api-client  ──imports──▶  stores/session.store
 *
 * Metro emitted `Require cycle: …` warnings on every cold start, and on
 * React Native that pattern produces non-deterministic uninitialized values:
 * the zustand store can be re-exported before its `create()` body has run,
 * which makes `useSessionStore.getState().accessToken` evaluate to
 * `undefined` on the very first request after a cold launch / deep link /
 * background wakeup.
 *
 * SHAPE OF THE FIX
 * ----------------
 * This module owns NOTHING. It is a one-way registration channel:
 *
 *   * `session.store` (owner of auth state) registers a bridge implementation
 *     after it has created the zustand store.
 *   * `api-client` (transport) READS through the bridge — it no longer knows
 *     anything about zustand, hydration order, or store internals.
 *
 * Direction of imports after this fix:
 *
 *     session.store  ──▶  api-client  ──▶  auth-bridge
 *           │                                ▲
 *           └────────────────────────────────┘
 *
 * (Three-node DAG, no cycle.)
 *
 * WHY NOT A DI CONTAINER / SERVICE LOCATOR / CONTEXT REWRITE
 * ----------------------------------------------------------
 * Per product directive: keep the fix surgical. A function pointer is
 * enough. We deliberately:
 *
 *   * do NOT introduce a DI container
 *   * do NOT introduce a global singleton registry
 *   * do NOT rewrite React Context plumbing
 *   * do NOT add a third party state library
 *
 * The bridge is intentionally untyped against zustand so this module has
 * zero coupling to the chosen state manager. If session state is ever
 * migrated off zustand, only `session.store.ts` changes.
 */

export interface SessionPayload {
  user: any;
  accessToken: string;
  refreshToken: string;
}

export interface AuthBridge {
  getAccessToken: () => string | null;
  getRefreshToken: () => string | null;
  setSession: (payload: SessionPayload) => void;
  clearSession: () => void;
  /**
   * TIER-2 backend security uses `X-User-Id` as a deterministic fallback
   * identity when JWT is absent (dev / pre-auth-wired environments).
   * Returns the operator identity to send in the header — typically the
   * user's email or numeric id when logged in, or null when no session
   * has been established yet. The api-client falls back to `dev_user`
   * in that case so the seeded dev principal still resolves.
   */
  getUserIdentity?: () => string | null;
}

let bridge: AuthBridge | null = null;

/**
 * Registered exactly once by the session store after `create()` returns.
 * Calling it again replaces the previous bridge (test reset friendly).
 */
export function registerAuthBridge(impl: AuthBridge): void {
  bridge = impl;
}

/**
 * Honest accessors. They return `null` (or no-op) when the bridge has not
 * been registered yet — instead of throwing, instead of pretending. The
 * api-client's request interceptor treats a null token as "unauthenticated"
 * which is the same posture as a logged-out user, so cold-start behaviour
 * is well-defined and idempotent.
 */
export function getAccessToken(): string | null {
  return bridge ? bridge.getAccessToken() : null;
}

export function getRefreshToken(): string | null {
  return bridge ? bridge.getRefreshToken() : null;
}

/**
 * TIER-2 helper: returns the deterministic identity string for the
 * `X-User-Id` fallback header. Never throws.  Never returns the user
 * object — only a string the backend can hash into `operator_access`.
 *
 *   * `dev_user` when no session has been established yet (dev shell)
 *   * the user's email when logged in via email/password
 *   * the user's id when logged in via Google/Telegram
 *
 * The api-client request interceptor reads this and attaches it to
 * every outgoing request. JWT (Bearer) still wins server-side when
 * both are present.
 */
export function getUserIdentity(): string | null {
  if (!bridge || !bridge.getUserIdentity) return null;
  try {
    return bridge.getUserIdentity();
  } catch {
    return null;
  }
}

export function setSession(payload: SessionPayload): void {
  if (bridge) bridge.setSession(payload);
}

export function clearSession(): void {
  if (bridge) bridge.clearSession();
}

/**
 * Diagnostic helper — used only in tests / debug screens to assert that the
 * store has wired itself in. Never use this in production request paths.
 */
export function isAuthBridgeReady(): boolean {
  return bridge !== null;
}
