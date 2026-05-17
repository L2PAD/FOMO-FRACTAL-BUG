import React, { useEffect } from 'react';
import { View, ActivityIndicator, Platform, StyleSheet } from 'react-native';
import { useLocalSearchParams } from 'expo-router';

/**
 * /legal/:page — Privacy / ToS pages live inside admin SPA.
 */
export default function LegalRedirect() {
  const { page } = useLocalSearchParams<{ page: string }>();
  useEffect(() => {
    if (Platform.OS !== 'web') return;
    const p = Array.isArray(page) ? page[0] : page;
    if (!p) return;
    const hash = typeof window !== 'undefined' ? window.location.hash || '' : '';
    const search = typeof window !== 'undefined' ? window.location.search || '' : '';
    window.location.replace(`/api/panel/legal/${encodeURIComponent(p)}` + search + hash);
  }, [page]);

  return (
    <View style={styles.root}>
      <ActivityIndicator color="#4DA3FF" size="large" />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#0B0F14' },
});
