import React, { useEffect } from 'react';
import { View, ActivityIndicator, Platform, StyleSheet } from 'react-native';
import { useLocalSearchParams } from 'expo-router';

/**
 * /privacy/* — catch-all for privacy sub-pages (e.g. /privacy/chrome-extension).
 */
export default function PrivacyRedirect() {
  const params = useLocalSearchParams<{ rest: string | string[] }>();
  useEffect(() => {
    if (Platform.OS !== 'web') return;
    const rest = params.rest;
    const joined = Array.isArray(rest) ? rest.join('/') : (rest || '');
    if (!joined) return;
    const hash = typeof window !== 'undefined' ? window.location.hash || '' : '';
    const search = typeof window !== 'undefined' ? window.location.search || '' : '';
    window.location.replace(`/api/panel/privacy/${joined}` + search + hash);
  }, [params.rest]);

  return (
    <View style={styles.root}>
      <ActivityIndicator color="#4DA3FF" size="large" />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#0B0F14' },
});
