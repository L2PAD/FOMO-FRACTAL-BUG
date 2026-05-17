/**
 * AdminShell — top-level frame for every authenticated /admin/* page.
 *
 * Owns the domain navigation tabs (Users vs Operators) plus the session
 * status / logout control.  Users and Operators are TWO DIFFERENT
 * domains with TWO DIFFERENT vocabularies — never merge.
 */
import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, usePathname } from 'expo-router';
import { useAdminAuth } from '../auth/AdminAuthContext';
import { useColors } from '../../core/useColors';

function fmtExpiry(ms: number | null): string {
  if (!ms) return '';
  const left = Math.max(0, ms - Date.now());
  const h = Math.floor(left / 3600000);
  const m = Math.floor((left % 3600000) / 60000);
  if (h >= 1) return `${h}h ${m}m`;
  return `${m}m`;
}

export function AdminShell({ children }: { children: React.ReactNode }) {
  const colors = useColors();
  const { logout, inactivityExpiresAt } = useAdminAuth();
  const router = useRouter();
  const path = usePathname();

  const tabs: Array<{ key: string; label: string; href: string; subtitle: string }> = [
    { key: 'users',       label: 'Users',       href: '/admin/users',       subtitle: 'Commercial · plans · subscriptions' },
    { key: 'operators',   label: 'Operators',   href: '/admin/operators',   subtitle: 'Governance · authority · audit' },
    { key: 'billing',     label: 'Billing',     href: '/admin/billing',     subtitle: 'Finance · invoices · reconciliation' },
    { key: 'attribution', label: 'Attribution', href: '/admin/attribution', subtitle: 'Epistemic observatory · read-only forensic' },
  ];

  const activeTab = path?.startsWith('/admin/users') ? 'users'
                  : path?.startsWith('/admin/operators') ? 'operators'
                  : path?.startsWith('/admin/billing') ? 'billing'
                  : path?.startsWith('/admin/attribution') ? 'attribution'
                  : null;

  return (
    <View style={[styles.root, { backgroundColor: colors.background }]}>
      {/* Top bar */}
      <View style={[styles.topbar, { backgroundColor: colors.surface, borderBottomColor: colors.border }]}>
        <View style={styles.brand}>
          <Ionicons name="shield-checkmark-outline" size={20} color={colors.accent} />
          <Text style={[styles.brandText, { color: colors.textPrimary }]}>
            FOMO · Operations
          </Text>
        </View>
        <View style={styles.topbarRight}>
          <Text style={[styles.sessionText, { color: colors.textMuted }]}>
            session expires in {fmtExpiry(inactivityExpiresAt)}
          </Text>
          <TouchableOpacity
            onPress={async () => { await logout(); router.replace('/admin/login'); }}
            style={[styles.logoutBtn, { borderColor: colors.border }]}
          >
            <Ionicons name="log-out-outline" size={14} color={colors.textSecondary} />
            <Text style={[styles.logoutText, { color: colors.textSecondary }]}>Sign out</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Domain tabs — separate vocabularies, never merged */}
      <View style={[styles.tabs, { backgroundColor: colors.surface, borderBottomColor: colors.border }]}>
        {tabs.map(t => {
          const active = activeTab === t.key;
          return (
            <Pressable
              key={t.key}
              onPress={() => router.push(t.href as any)}
              style={({ hovered }: any) => [
                styles.tab,
                { borderBottomColor: active ? colors.accent : 'transparent' },
                hovered && { backgroundColor: colors.surfaceHover },
              ]}
            >
              <Text style={[styles.tabLabel, { color: active ? colors.textPrimary : colors.textSecondary, fontWeight: active ? '700' : '500' }]}>
                {t.label}
              </Text>
              <Text style={[styles.tabSubtitle, { color: colors.textMuted }]} numberOfLines={1}>
                {t.subtitle}
              </Text>
            </Pressable>
          );
        })}
      </View>

      {/* Body */}
      <View style={{ flex: 1 }}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  topbar: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 24, paddingVertical: 14, borderBottomWidth: 1,
  },
  brand: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  brandText: { fontSize: 14, fontWeight: '800', letterSpacing: 0.3 },
  topbarRight: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  sessionText: { fontSize: 11 },
  logoutBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: 6, borderWidth: 1,
  },
  logoutText: { fontSize: 11, fontWeight: '500' },
  tabs: { flexDirection: 'row', paddingHorizontal: 12, borderBottomWidth: 1 },
  tab: {
    paddingHorizontal: 18, paddingVertical: 12, borderBottomWidth: 2,
    minWidth: 200,
  },
  tabLabel: { fontSize: 14 },
  tabSubtitle: { fontSize: 10, marginTop: 2 },
});
