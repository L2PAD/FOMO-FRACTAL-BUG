import React, { useEffect } from 'react';
import { View, ActivityIndicator, Platform, StyleSheet, Text } from 'react-native';

/**
 * /exchange — Emergent Auth callback shim.
 *
 * The admin SPA's AuthProvider computes its redirect URL as:
 *   window.location.origin + "/exchange"
 * so after Google sign-in the user is redirected back here with a
 * #session_id=<token> hash. We must forward that hash into the SPA
 * (served at /api/panel/) which runs the actual POST /api/auth/session
 * exchange on mount.
 */
export default function ExchangeRedirect() {
  useEffect(() => {
    if (Platform.OS !== 'web') return;
    const hash = typeof window !== 'undefined' ? window.location.hash || '' : '';
    const search = typeof window !== 'undefined' ? window.location.search || '' : '';
    // Land back on /info so post-auth the user is on the landing page,
    // already signed in. The SPA reads the hash globally on mount.
    window.location.replace('/api/panel/info' + search + hash);
  }, []);

  return (
    <View style={styles.root}>
      <ActivityIndicator color="#4DA3FF" size="large" />
      <Text style={styles.caption}>Finishing sign-in…</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#0B0F14', gap: 12 },
  caption: { color: '#a1a1aa', fontSize: 13, marginTop: 12 },
});
