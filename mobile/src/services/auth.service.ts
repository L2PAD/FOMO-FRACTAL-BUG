import { authApi } from './api/auth-api';
import { tokenStorage } from './token-storage';
import { useSessionStore } from '../stores/session.store';
import { usePreferencesStore } from '../stores/preferences.store';
import { useAppMode } from '../stores/app-mode.store';
import { applyTempRefAfterLogin } from './referral.service';

function hydratePrefs(user: any) {
  if (user?.preferences) {
    usePreferencesStore.getState().hydrateFromProfile(user.preferences);

    // Apply start screen preference
    const startScreen = user.preferences.startScreen;
    if (startScreen && ['HOME', 'FEED', 'EDGE'].includes(startScreen)) {
      useAppMode.getState().setIntelTab(startScreen as any);
    }
  }
}

export async function signInWithGoogle(idToken: string) {
  useSessionStore.getState().setLoading(true);
  try {
    const data = await authApi.google(idToken);
    await tokenStorage.set(data.accessToken, data.refreshToken);
    useSessionStore.getState().setSession({
      user: data.user,
      accessToken: data.accessToken,
      refreshToken: data.refreshToken,
    });
    hydratePrefs(data.user);
    // G1: attach any pending deep-link referral to this user (one-shot)
    void applyTempRefAfterLogin();
    return data;
  } finally {
    useSessionStore.getState().setLoading(false);
  }
}

export async function devLogin(email?: string, name?: string) {
  useSessionStore.getState().setLoading(true);
  try {
    const data = await authApi.devLogin(email, name);
    await tokenStorage.set(data.accessToken, data.refreshToken);
    useSessionStore.getState().setSession({
      user: data.user,
      accessToken: data.accessToken,
      refreshToken: data.refreshToken,
    });
    hydratePrefs(data.user);
    // G1: attach any pending deep-link referral to this user (one-shot)
    void applyTempRefAfterLogin();
    return data;
  } finally {
    useSessionStore.getState().setLoading(false);
  }
}

export async function hydrateSession() {
  const { accessToken, refreshToken } = await tokenStorage.get();

  if (!refreshToken) {
    useSessionStore.getState().setHydrated(true);
    return;
  }

  try {
    const data = await authApi.refresh(refreshToken);
    await tokenStorage.set(data.accessToken, data.refreshToken);
    useSessionStore.getState().setSession({
      user: data.user,
      accessToken: data.accessToken,
      refreshToken: data.refreshToken,
    });
    hydratePrefs(data.user);
    // G1: apply any pending deep-link ref to restored session too
    void applyTempRefAfterLogin();
  } catch {
    await tokenStorage.clear();
    useSessionStore.getState().clearSession();
  } finally {
    useSessionStore.getState().setHydrated(true);
  }
}

export async function logout() {
  const refreshToken = useSessionStore.getState().refreshToken;
  if (refreshToken) {
    try {
      await authApi.logout(refreshToken);
    } catch {
      // ignore - logout is idempotent
    }
  }
  await tokenStorage.clear();
  useSessionStore.getState().clearSession();
}
