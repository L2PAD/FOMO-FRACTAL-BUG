import React, { useEffect } from 'react';
import { View, ActivityIndicator, Platform, StyleSheet } from 'react-native';

/**
 * /info — short-URL shim.
 * The real FOMO landing page (React SPA with Google Sign-In) lives at
 * /api/panel/info inside the admin_build bundle served by FastAPI.
 * On web we immediately redirect there, preserving any URL hash
 * (e.g. #session_id=... from the Emergent Auth callback).
 */
export default function InfoRedirect() {
  useEffect(() => {
    if (Platform.OS !== 'web') return;
    const hash = typeof window !== 'undefined' ? window.location.hash || '' : '';
    const search = typeof window !== 'undefined' ? window.location.search || '' : '';
    window.location.replace('/api/panel/info' + search + hash);
  }, []);

  return (
    <View style={styles.root}>
      <ActivityIndicator color="#4DA3FF" size="large" />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#0B0F14' },
});
