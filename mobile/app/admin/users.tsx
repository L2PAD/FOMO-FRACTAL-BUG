/**
 * /admin/users — commercial domain.
 *
 * Language constraint: this page speaks ONLY commercial / billing
 * vocabulary — `plan`, `subscription`, `upgrade`, `tier`, `paywall`.
 * Words like `authority`, `override`, `live capability`, `governance`
 * do not appear here.  They live in /admin/operators.
 *
 * Phase 3B: skeleton only.  Real user CRUD lands when billing surface
 * (TIER-4) wires through.
 */
import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AdminShell } from '../../src/admin/components/AdminShell';
import { useColors } from '../../src/core/useColors';

export default function AdminUsersScreen() {
  const colors = useColors();
  return (
    <AdminShell>
      <ScrollView contentContainerStyle={[styles.scroll, { backgroundColor: colors.background }]}>
        <View style={styles.head}>
          <Text style={[styles.h1, { color: colors.textPrimary }]}>Users</Text>
          <Text style={[styles.sub, { color: colors.textSecondary }]}>
            Commercial customers. Plan, subscription state and billing history.
          </Text>
        </View>

        <View style={[styles.placeholder, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <Ionicons name="card-outline" size={28} color={colors.textMuted} />
          <Text style={[styles.phTitle, { color: colors.textPrimary }]}>Billing surface lands in TIER-4</Text>
          <Text style={[styles.phBody, { color: colors.textSecondary }]}>
            Plan management (free · pro · trader), subscription renewals,
            invoice history and upgrade paths will surface here once the
            multi-product billing layer is wired (NOWPayments invoices for
            the TRADER tier).
          </Text>
          <Text style={[styles.phHint, { color: colors.textMuted }]}>
            For operator capability governance (authority grants, overrides,
            audit timeline) → switch to the Operators tab above.
          </Text>
        </View>
      </ScrollView>
    </AdminShell>
  );
}

const styles = StyleSheet.create({
  scroll: { padding: 28, gap: 18 },
  head: { gap: 6 },
  h1: { fontSize: 24, fontWeight: '800', letterSpacing: -0.2 },
  sub: { fontSize: 13 },
  placeholder: {
    marginTop: 12, padding: 24, borderRadius: 12, borderWidth: 1, gap: 8,
    alignItems: 'flex-start',
  },
  phTitle: { fontSize: 15, fontWeight: '700', marginTop: 6 },
  phBody: { fontSize: 13, lineHeight: 19 },
  phHint: { fontSize: 12, marginTop: 8, fontStyle: 'italic' },
});
