/**
 * capabilities.store — Stage 0 capability topology.
 *
 *   Single source of truth for the semantic gate between:
 *     PUBLIC INTELLIGENCE SURFACE       (Home / Feed / Signals / Edge)
 *     RESTRICTED OPERATIONAL ENVIRONMENT (Command / Market / Execution / Portfolio)
 *
 *   NOT a billing store.  NOT RBAC.  NOT a Pro-upgrade flow.
 *
 *   Mirrors the backend `/api/me/capabilities` response.  Until the auth
 *   sidecar lands, the backend defaults to `dev_user` and seeds an
 *   approved+paper record so the developer environment renders the
 *   full operator surface.  Other users are seeded as free + no access.
 *
 *   Forbidden language: VIP / Elite / Premium / Alpha / Unlock.
 *   Allowed language:   Operator Access · Restricted Environment · Authorized Execution Layer.
 */
import { create } from 'zustand';
import { api } from '../services/api/api-client';

// ─── Types (mirror backend shape exactly) ──────────────────────────────
export type Tier = 'free' | 'pro';

export type AccessStatus =
  | 'none'
  | 'invited'
  | 'pending_review'
  | 'approved'
  | 'revoked';

export type AccessMode = 'none' | 'paper' | 'shadow' | 'live';

export interface OperatorAccess {
  enabled: boolean;
  status: AccessStatus;
  mode: AccessMode;
  riskAcknowledgedAt: string | null;
  termsAcceptedAt: string | null;
  appliedAt: string | null;
  approvedAt: string | null;
  approvedBy: string | null;
  maxCapitalExposureUsd: number | null;
  allowedExchanges: string[];
}

export interface Capabilities {
  tier: Tier;
  analyticsBasic: boolean;
  analyticsPro: boolean;
  tradingOsVisible: boolean;   // bottom-nav 'Trade' tab rendered
  executionConsole: boolean;   // Trading OS internals revealed
  paperTrading: boolean;
  shadowTrading: boolean;
  liveTrading: boolean;
}

interface CapabilitiesState {
  userId: string | null;
  tier: Tier;
  operatorAccess: OperatorAccess;
  capabilities: Capabilities;
  loaded: boolean;
  loading: boolean;
  error: string | null;
  fetch: () => Promise<void>;
  applyForOperator: (termsAccepted: boolean, note?: string) => Promise<void>;
  acknowledgeRisk: () => Promise<void>;
  reset: () => void;
}

// ─── Defaults (most-restrictive — used while loading / on error) ───────
const DEFAULT_OA: OperatorAccess = {
  enabled: false,
  status: 'none',
  mode: 'none',
  riskAcknowledgedAt: null,
  termsAcceptedAt: null,
  appliedAt: null,
  approvedAt: null,
  approvedBy: null,
  maxCapitalExposureUsd: null,
  allowedExchanges: [],
};

const DEFAULT_CAPS: Capabilities = {
  tier: 'free',
  analyticsBasic: true,
  analyticsPro: false,
  tradingOsVisible: false,
  executionConsole: false,
  paperTrading: false,
  shadowTrading: false,
  liveTrading: false,
};

// ─── HTTP helpers — use the shared `api` client so auth + base URL are
//     resolved exactly the same way as everywhere else in the app.
async function _get(path: string): Promise<any> {
  const res = await api.get(path);
  return res.data;
}

async function _post(path: string, body: any): Promise<any> {
  const res = await api.post(path, body || {});
  return res.data;
}

// ─── Store ─────────────────────────────────────────────────────────────
export const useCapabilitiesStore = create<CapabilitiesState>((set, get) => ({
  userId: null,
  tier: 'free',
  operatorAccess: { ...DEFAULT_OA },
  capabilities: { ...DEFAULT_CAPS },
  loaded: false,
  loading: false,
  error: null,

  async fetch() {
    if (get().loading) return;
    set({ loading: true, error: null });
    try {
      const d = await _get('/api/me/capabilities');
      set({
        userId: d.userId,
        tier: d.tier,
        operatorAccess: { ...DEFAULT_OA, ...(d.operatorAccess || {}) },
        capabilities: { ...DEFAULT_CAPS, ...(d.capabilities || {}) },
        loaded: true,
        loading: false,
      });
    } catch (err: any) {
      // Most-restrictive on failure. NO fake bullish defaults.
      set({
        loading: false,
        loaded: true,
        error: err?.message || 'capabilities_fetch_failed',
        operatorAccess: { ...DEFAULT_OA },
        capabilities: { ...DEFAULT_CAPS },
      });
    }
  },

  async applyForOperator(termsAccepted, note) {
    await _post('/api/me/operator-access/apply', { termsAccepted, note });
    await get().fetch();
  },

  async acknowledgeRisk() {
    await _post('/api/me/operator-access/risk-ack', { acknowledged: true });
    await get().fetch();
  },

  reset() {
    set({
      userId: null,
      tier: 'free',
      operatorAccess: { ...DEFAULT_OA },
      capabilities: { ...DEFAULT_CAPS },
      loaded: false,
      loading: false,
      error: null,
    });
  },
}));

// ─── Hook helpers ──────────────────────────────────────────────────────

/**
 * Read-only capability hook.  Triggers a one-time background fetch if the
 * store hasn't loaded yet.  Safe to call from any component.
 *
 * Returns the most-restrictive view while loading — UI must NEVER assume
 * access until `loaded === true` AND the relevant flag is true.
 */
export function useCapabilities() {
  const state = useCapabilitiesStore();
  // Kick off fetch on first read.
  if (!state.loaded && !state.loading) {
    // fire-and-forget; intentional during render — store de-dupes via `loading`
    void state.fetch();
  }
  return state;
}

/**
 * Convenience: returns the resolved operator-mode label or null.
 *
 *   approved + paper   → 'PAPER OPERATOR'
 *   approved + shadow  → 'SHADOW OPERATOR'
 *   approved + live    → 'LIVE OPERATOR'
 *   pending_review     → 'OPERATOR REVIEW'
 *   invited            → 'INVITED OPERATOR'
 *   revoked            → 'ACCESS REVOKED'
 *   anything else      → null
 */
export function useOperatorBadge(): string | null {
  const { operatorAccess: oa, loaded } = useCapabilitiesStore();
  if (!loaded) return null;
  if (!oa.enabled && oa.status === 'none') return null;
  if (oa.status === 'approved') {
    return `${oa.mode.toUpperCase()} OPERATOR`;
  }
  if (oa.status === 'pending_review') return 'OPERATOR REVIEW';
  if (oa.status === 'invited') return 'INVITED OPERATOR';
  if (oa.status === 'revoked') return 'ACCESS REVOKED';
  return null;
}
