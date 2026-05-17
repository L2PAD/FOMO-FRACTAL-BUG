/**
 * Referral Deep Link Service (Growth Layer G1)
 * =============================================
 * Workflow:
 *   1. App boot → parse query (?ref=, ?startapp=ref_XXX) → saveTempRef()
 *   2. User logs in → applyTempRefAfterLogin() → existing /referrals/apply endpoint
 *   3. Temp ref cleared (one-shot)
 *
 * Strict rules:
 *  - NEVER create a new referral table — rely on existing mobile_auth /referrals/apply
 *  - Save BEFORE login (guest flow) and attach AFTER login
 *  - One-shot: clear on success to avoid double-apply
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';
import { api } from './api/api-client';

const STORAGE_KEY = 'temp_ref_v1';
const STORAGE_KEY_META = 'temp_ref_meta_v1';

/** Normalize various deeplink shapes into a clean ref code. */
function normalize(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const s = String(raw).trim();
  if (!s) return null;
  // Accept: FOMO-XXXXXX / ref_FOMO-XXXX / bare XXXXXX
  if (s.toLowerCase().startsWith('ref_')) {
    const code = s.slice(4);
    return code ? code.toUpperCase() : null;
  }
  return s.toUpperCase();
}

/** Parse ref from URL query (web) or Telegram WebApp initData (miniapp). */
export function extractRefFromEnvironment(): string | null {
  try {
    if (Platform.OS !== 'web') return null;
    if (typeof window === 'undefined') return null;

    // 1) Telegram WebApp startapp / start_param
    const tg: any = (window as any).Telegram?.WebApp;
    const startParam: string | undefined = tg?.initDataUnsafe?.start_param;
    if (startParam) {
      // startapp patterns: ref_FOMO-XXXXXX, news_BTC (no ref), news_BTC&ref=ABC (rare)
      if (startParam.toLowerCase().startsWith('ref_')) {
        return normalize(startParam);
      }
      // Fallback: look for embedded &ref= inside start_param
      const m = /[?&]ref=([^&]+)/i.exec(startParam);
      if (m) return normalize(m[1]);
    }

    // 2) URL query ?ref=XXX
    const sp = new URLSearchParams(window.location.search);
    const r = sp.get('ref') || sp.get('startapp');
    if (r) return normalize(r);
  } catch {
    // noop
  }
  return null;
}

export async function saveTempRef(code: string): Promise<void> {
  const clean = normalize(code);
  if (!clean) return;
  try {
    await AsyncStorage.setItem(STORAGE_KEY, clean);
    await AsyncStorage.setItem(
      STORAGE_KEY_META,
      JSON.stringify({ savedAt: Date.now(), surface: 'deeplink' })
    );
  } catch {}
}

export async function getTempRef(): Promise<string | null> {
  try {
    return await AsyncStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export async function clearTempRef(): Promise<void> {
  try {
    await AsyncStorage.removeItem(STORAGE_KEY);
    await AsyncStorage.removeItem(STORAGE_KEY_META);
  } catch {}
}

/**
 * Apply any saved temp_ref to the currently authenticated user.
 * Called from auth.service.ts after signInWithGoogle / devLogin / hydrateSession.
 * Uses EXISTING endpoint /api/mobile/auth/referrals/apply (no new tables).
 */
export async function applyTempRefAfterLogin(): Promise<{ applied: boolean; code?: string; reason?: string }> {
  const code = await getTempRef();
  if (!code) return { applied: false, reason: 'no_temp_ref' };
  try {
    const { data } = await api.post('/api/mobile/auth/referrals/apply', { code });
    // One-shot: always clear after attempt so we do not retry forever.
    await clearTempRef();
    if (data?.success) {
      return { applied: true, code };
    }
    return { applied: false, code, reason: data?.detail || data?.message || 'backend_rejected' };
  } catch (err: any) {
    // On server 400 (already used / self-ref / invalid) → clear so we do not loop.
    const status = err?.response?.status;
    if (status && status >= 400 && status < 500) {
      await clearTempRef();
    }
    return { applied: false, code, reason: err?.response?.data?.detail || 'network_error' };
  }
}

/** Ensure current user has a referralCode; auto-generates on backend via GET /referrals. */
export async function ensureOwnRefCode(): Promise<string | null> {
  try {
    const { data } = await api.get('/api/mobile/auth/referrals');
    return data?.code || null;
  } catch {
    return null;
  }
}
