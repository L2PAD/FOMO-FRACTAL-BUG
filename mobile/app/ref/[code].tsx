import React, { useEffect } from 'react';
import { View, ActivityIndicator, Platform, StyleSheet } from 'react-native';
import { useLocalSearchParams } from 'expo-router';

/**
 * /ref/:code — Referral landing shim. Forwards to the React SPA route
 * /api/panel/ref/:code which handles referral validation + sign-up.
 */
export default function RefRedirect() {
  const { code } = useLocalSearchParams<{ code: string }>();
  useEffect(() => {
    if (Platform.OS !== 'web') return;
    const c = Array.isArray(code) ? code[0] : code;
    if (!c) return;
    const hash = typeof window !== 'undefined' ? window.location.hash || '' : '';
    const search = typeof window !== 'undefined' ? window.location.search || '' : '';
    window.location.replace(`/api/panel/ref/${encodeURIComponent(c)}` + search + hash);
  }, [code]);

  return (
    <View style={styles.root}>
      <ActivityIndicator color="#4DA3FF" size="large" />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#0B0F14' },
});
