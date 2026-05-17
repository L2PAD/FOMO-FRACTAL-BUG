/**
 * NativeBlock — hard environmental boundary for the admin surface.
 *
 * Mounted only when Platform.OS !== 'web'.  It deliberately renders WITHOUT
 * any admin children, providers, hooks, fetches or stores so that:
 *
 *   * AdminAuthContext is NEVER initialized
 *   * adminClient axios instance is NEVER imported into a running tree
 *   * no governance mutations or fetches can leak onto a mobile device
 *
 * Operator governance is not a mobile workflow — this screen states that
 * explicitly and offers no escape hatch.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../core/useColors';

export function NativeBlock() {
  const colors = useColors();
  return (
    <View style={[styles.root, { backgroundColor: colors.background }]}>
      <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        <Ionicons name="desktop-outline" size={36} color={colors.textMuted} />
        <Text style={[styles.title, { color: colors.textPrimary }]}>Web only surface</Text>
        <Text style={[styles.body, { color: colors.textSecondary }]}>
          Operator governance — capability overrides, live-authority grants, audit
          review — is intentionally restricted to the web admin console.
        </Text>
        <Text style={[styles.body, { color: colors.textMuted, marginTop: 12 }]}>
          Open the FOMO operations console in a desktop browser to continue.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  card: {
    width: '100%', maxWidth: 480,
    borderWidth: 1, borderRadius: 12,
    padding: 24, alignItems: 'center', gap: 8,
  },
  title: { fontSize: 16, fontWeight: '700', marginTop: 12 },
  body: { fontSize: 13, lineHeight: 19, textAlign: 'center' },
});
