import React, { useEffect } from 'react';
import { View, ActivityIndicator, Platform, StyleSheet } from 'react-native';
import { useLocalSearchParams } from 'expo-router';

/**
 * /snapshot/:id — Shared prediction snapshot shim.
 */
export default function SnapshotRedirect() {
  const { id } = useLocalSearchParams<{ id: string }>();
  useEffect(() => {
    if (Platform.OS !== 'web') return;
    const v = Array.isArray(id) ? id[0] : id;
    if (!v) return;
    const hash = typeof window !== 'undefined' ? window.location.hash || '' : '';
    const search = typeof window !== 'undefined' ? window.location.search || '' : '';
    window.location.replace(`/api/panel/snapshot/${encodeURIComponent(v)}` + search + hash);
  }, [id]);

  return (
    <View style={styles.root}>
      <ActivityIndicator color="#4DA3FF" size="large" />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#0B0F14' },
});
