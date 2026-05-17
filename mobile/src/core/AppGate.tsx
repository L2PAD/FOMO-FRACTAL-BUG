import React, { useEffect } from 'react';
import { View, ActivityIndicator, StyleSheet, Platform } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { useSessionStore } from '../stores/session.store';
import { usePreferencesStore } from '../stores/preferences.store';
import { useAccessStore } from '../stores/access.store';
import { hydrateSession } from '../services/auth.service';
import { WelcomeScreen } from '../modules/auth/WelcomeScreen';
import { AppShell } from './app-shell/AppShell';
import { useColors } from './useColors';
import { extractRefFromEnvironment, saveTempRef, applyTempRefAfterLogin } from '../services/referral.service';

export function AppGate() {
  const colors = useColors();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);

  const user = useSessionStore((s) => s.user);
  const isHydrated = useSessionStore((s) => s.isHydrated);
  const prefsHydrated = usePreferencesStore((s) => s.prefsHydrated);

  // P1 Web Soft Gate bootstrap — fetch access preview + track guest visit.
  const fetchAccessPreview = useAccessStore((s) => s.fetchPreview);
  const trackAccessEvent = useAccessStore((s) => s.trackEvent);
  const ensureGuestSession = useAccessStore((s) => s.ensureGuestSession);

  useEffect(() => {
    // 1) Capture deep-link ref BEFORE login (guest-safe)
    //    Source priority: Telegram WebApp start_param > URL ?ref= > URL ?startapp=ref_
    try {
      const ref = extractRefFromEnvironment();
      if (ref) {
        void saveTempRef(ref);
      }
    } catch {}

    // 2) Hydrate session
    hydrateSession();
  }, []);

  // Whenever a fresh user appears (post-login), apply any pending temp_ref.
  const userId = user?.id;
  useEffect(() => {
    if (!isHydrated) return;
    if (!userId) return;
    void applyTempRefAfterLogin();
  }, [isHydrated, userId]);

  useEffect(() => {
    if (Platform.OS !== 'web') return;
    // On Web always fetch preview — even for guests (backend decides level).
    ensureGuestSession();
    fetchAccessPreview();
    trackAccessEvent('web_visit_guest', { surface: 'app_bootstrap' });
  }, [fetchAccessPreview, trackAccessEvent, ensureGuestSession]);

  // Refetch access preview when auth state flips (guest → authed or vice versa).
  useEffect(() => {
    if (Platform.OS !== 'web') return;
    if (!isHydrated) return;
    fetchAccessPreview();
  }, [user, isHydrated, fetchAccessPreview]);

  // Wait for BOTH session and preferences to hydrate — prevents theme flash
  if (!isHydrated || !prefsHydrated) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  // P1 Web Soft Gate: on Web let guests into AppShell. Mobile stays with
  // Welcome-first behaviour (mobile auth already works, we don't break it).
  if (!user) {
    if (Platform.OS === 'web') {
      return <AppShell />;
    }
    return <WelcomeScreen />;
  }

  // Authenticated → show App
  return <AppShell />;
}

const makeStyles = (colors: any) => StyleSheet.create({
  loading: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
