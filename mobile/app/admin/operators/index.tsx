/**
 * /admin/operators — governance domain.
 *
 * Operational vocabulary ONLY: authority, override, capability, mode,
 * audit, governance, revoke, grant, console access.  Commercial terms
 * (plan / subscription / upgrade / paywall) DO NOT appear here.
 *
 * Phase 3B contract:
 *   * loads operators from backend list endpoint with filters + pagination
 *   * dense information row — every operator shows tier, status, mode,
 *     consoleAccess, liveAuthority, override count, last-change recency
 *   * row click → /admin/operators/[userId] (detail stub for 3C)
 *   * NO mutations — grant/revoke/override land in 3C
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, Pressable, TextInput,
  ActivityIndicator, TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { AdminShell } from '../../../src/admin/components/AdminShell';
import {
  adminApi, OperatorRow, OperatorListFilters,
} from '../../../src/admin/api/adminClient';
import { useColors } from '../../../src/core/useColors';

const TIER_OPTIONS = ['', 'free', 'pro', 'trader'] as const;
const STATUS_OPTIONS = ['', 'none', 'invited', 'pending_review', 'approved', 'revoked'] as const;
const MODE_OPTIONS = ['', 'none', 'paper', 'shadow', 'live'] as const;
const OVERRIDE_OPTIONS = ['', 'with', 'without'] as const;
const PAGE_SIZE = 50;

function timeAgo(iso?: string | null): string {
  if (!iso) return 'never';
  const t = Date.parse(iso);
  if (!isFinite(t)) return 'never';
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s/60)}m ago`;
  if (s < 86400) return `${Math.floor(s/3600)}h ago`;
  return `${Math.floor(s/86400)}d ago`;
}

export default function OperatorsListScreen() {
  const colors = useColors();
  const router = useRouter();

  const [tier, setTier] = useState<string>('');
  const [status, setStatus] = useState<string>('');
  const [mode, setMode] = useState<string>('');
  const [override, setOverride] = useState<string>('');
  const [q, setQ] = useState<string>('');
  const [offset, setOffset] = useState(0);

  const [rows, setRows] = useState<OperatorRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filters: OperatorListFilters = useMemo(() => ({
    tier: (tier || undefined) as any,
    status: (status || undefined) as any,
    mode: (mode || undefined) as any,
    hasOverrides: override === 'with' ? true : override === 'without' ? false : undefined,
    q: q.trim() || undefined,
    limit: PAGE_SIZE,
    offset,
  }), [tier, status, mode, override, q, offset]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.listOperators(filters);
      setRows(res.rows);
      setTotal(res.total);
    } catch (e: any) {
      setError(e?.message || 'Failed to load operators');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  return (
    <AdminShell>
      <ScrollView contentContainerStyle={[styles.scroll, { backgroundColor: colors.background }]}>
        {/* Heading */}
        <View style={styles.head}>
          <Text style={[styles.h1, { color: colors.textPrimary }]}>Operators</Text>
          <Text style={[styles.sub, { color: colors.textSecondary }]}>
            Operational governance — capability state, authority grants, audit trail.
            Tier here is informational; capability decisions are independent of billing.
          </Text>
        </View>

        {/* Filter row */}
        <View style={[styles.filterRow, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <FilterSelect label="Tier"     value={tier}     onChange={v=>{setOffset(0);setTier(v)}}     options={TIER_OPTIONS as any}/>
          <FilterSelect label="Status"   value={status}   onChange={v=>{setOffset(0);setStatus(v)}}   options={STATUS_OPTIONS as any}/>
          <FilterSelect label="Mode"     value={mode}     onChange={v=>{setOffset(0);setMode(v)}}     options={MODE_OPTIONS as any}/>
          <FilterSelect label="Overrides" value={override} onChange={v=>{setOffset(0);setOverride(v)}} options={OVERRIDE_OPTIONS as any}/>
          <View style={[styles.searchWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
            <Ionicons name="search" size={14} color={colors.textMuted} />
            <TextInput
              value={q}
              onChangeText={(t) => { setOffset(0); setQ(t); }}
              placeholder="search userId"
              placeholderTextColor={colors.textMuted}
              style={[styles.searchInput, { color: colors.textPrimary }]}
              autoCapitalize="none"
              autoCorrect={false}
            />
          </View>
          <TouchableOpacity onPress={load} style={[styles.refreshBtn, { borderColor: colors.border }]}>
            <Ionicons name="refresh-outline" size={14} color={colors.textSecondary} />
            <Text style={[styles.refreshText, { color: colors.textSecondary }]}>refresh</Text>
          </TouchableOpacity>
        </View>

        {/* Status bar */}
        <View style={styles.metaRow}>
          <Text style={[styles.metaText, { color: colors.textMuted }]}>
            {loading ? 'loading…' : `${rows.length} of ${total} — page offset ${offset}`}
          </Text>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <PageBtn
              disabled={offset === 0 || loading}
              onPress={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              label="← Prev" colors={colors}
            />
            <PageBtn
              disabled={offset + PAGE_SIZE >= total || loading}
              onPress={() => setOffset(offset + PAGE_SIZE)}
              label="Next →" colors={colors}
            />
          </View>
        </View>

        {error && (
          <View style={[styles.errBox, { borderColor: colors.danger, backgroundColor: colors.badgeHighBg }]}>
            <Text style={[styles.errText, { color: colors.badgeHighText }]}>{error}</Text>
          </View>
        )}

        {/* Table */}
        <View style={[styles.table, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <View style={[styles.thead, { borderBottomColor: colors.border }]}>
            <Th flex={2.6}>Operator</Th>
            <Th flex={0.9}>Tier</Th>
            <Th flex={1.2}>Status</Th>
            <Th flex={0.9}>Mode</Th>
            <Th flex={1.1}>Console</Th>
            <Th flex={1.2}>Live Auth</Th>
            <Th flex={1.0}>Overrides</Th>
            <Th flex={1.5}>Last change</Th>
          </View>
          {!loading && rows.length === 0 && (
            <View style={styles.empty}>
              <Ionicons name="file-tray-outline" size={22} color={colors.textMuted} />
              <Text style={[styles.emptyText, { color: colors.textMuted }]}>
                No operators match the current filters.
              </Text>
            </View>
          )}
          {loading && (
            <View style={styles.empty}>
              <ActivityIndicator color={colors.accent} />
            </View>
          )}
          {!loading && rows.map((r) => (
            <OperatorRowItem
              key={r.userId}
              row={r}
              onPress={() => router.push(`/admin/operators/${encodeURIComponent(r.userId)}` as any)}
            />
          ))}
        </View>
      </ScrollView>
    </AdminShell>
  );
}

// ── Row ────────────────────────────────────────────────────────────────────────

function OperatorRowItem({ row, onPress }: { row: OperatorRow; onPress: () => void }) {
  const colors = useColors();
  const oa = row.operatorAccess || {};
  const overrideCount = Object.keys(oa.capabilityOverrides || {}).length;
  const liveAuthGranted = !!(oa.liveAuthority && oa.liveAuthority.granted);
  const liveAuthExpiry = oa.liveAuthority?.expiresAt;

  return (
    <Pressable
      onPress={onPress}
      style={({ hovered }: any) => [
        styles.tr,
        { borderBottomColor: colors.border },
        hovered && { backgroundColor: colors.surfaceHover },
      ]}
      testID={`operator-row-${row.userId}`}
    >
      <Td flex={2.6}>
        <Text style={[styles.userId, { color: colors.textPrimary }]} numberOfLines={1}>
          {row.userId}
        </Text>
        <Text style={[styles.userIdSub, { color: colors.textMuted }]} numberOfLines={1}>
          updated {timeAgo(row.updatedAt)}
        </Text>
      </Td>
      <Td flex={0.9}><Pill text={row.tier} kind={tierKind(row.tier)} colors={colors} /></Td>
      <Td flex={1.2}><Pill text={oa.status || 'none'} kind={statusKind(oa.status)} colors={colors} /></Td>
      <Td flex={0.9}><Pill text={oa.mode || 'none'} kind="neutral" colors={colors} /></Td>
      <Td flex={1.1}>
        <Pill
          text={oa.consoleAccess ? 'on' : 'off'}
          kind={oa.consoleAccess ? 'positive' : 'neutral'}
          colors={colors}
        />
      </Td>
      <Td flex={1.2}>
        <Pill
          text={liveAuthGranted ? (liveAuthExpiry ? 'until ⏱' : 'granted') : 'none'}
          kind={liveAuthGranted ? 'critical' : 'neutral'}
          colors={colors}
        />
      </Td>
      <Td flex={1.0}>
        <Pill
          text={overrideCount > 0 ? `${overrideCount}` : '—'}
          kind={overrideCount > 0 ? 'elevated' : 'neutral'}
          colors={colors}
        />
      </Td>
      <Td flex={1.5}>
        <Text style={[styles.tdText, { color: colors.textSecondary }]} numberOfLines={1}>
          {timeAgo(oa.lastCapabilityChangeAt)}
        </Text>
        <Text style={[styles.tdSub, { color: colors.textMuted }]} numberOfLines={1}>
          {oa.lastCapabilityChangedBy || '—'}
        </Text>
      </Td>
    </Pressable>
  );
}

// ── Primitives ─────────────────────────────────────────────────────────────────────
function Th({ flex, children }: { flex: number; children: React.ReactNode }) {
  const colors = useColors();
  return (
    <View style={[styles.th, { flex }]}>
      <Text style={[styles.thText, { color: colors.textMuted }]} numberOfLines={1}>{children}</Text>
    </View>
  );
}
function Td({ flex, children }: { flex: number; children: React.ReactNode }) {
  return <View style={[styles.td, { flex }]}>{children}</View>;
}

type PillKind = 'neutral' | 'positive' | 'elevated' | 'critical' | 'danger';
function Pill({ text, kind, colors }: { text: string; kind: PillKind; colors: any }) {
  const palette: Record<PillKind, { bg: string; fg: string }> = {
    neutral:  { bg: colors.surfaceHover, fg: colors.textSecondary },
    positive: { bg: colors.badgeLowBg || colors.surfaceHover, fg: colors.badgeLowText || colors.buy },
    elevated: { bg: colors.badgeMidBg || colors.surfaceHover, fg: colors.badgeMidText || colors.accent },
    critical: { bg: colors.badgeHighBg, fg: colors.badgeHighText },
    danger:   { bg: colors.badgeHighBg, fg: colors.badgeHighText },
  };
  const p = palette[kind];
  return (
    <View style={[styles.pill, { backgroundColor: p.bg }]}>
      <Text style={[styles.pillText, { color: p.fg }]} numberOfLines={1}>{text}</Text>
    </View>
  );
}

function tierKind(t: string): PillKind {
  if (t === 'trader') return 'elevated';
  if (t === 'pro') return 'positive';
  return 'neutral';
}
function statusKind(s?: string): PillKind {
  if (s === 'approved') return 'positive';
  if (s === 'pending_review' || s === 'invited') return 'elevated';
  if (s === 'revoked') return 'danger';
  return 'neutral';
}

function FilterSelect(props: {
  label: string; value: string; onChange: (v: string) => void;
  options: readonly string[];
}) {
  const colors = useColors();
  return (
    <View style={styles.filter}>
      <Text style={[styles.filterLabel, { color: colors.textMuted }]}>{props.label}</Text>
      <View style={[styles.selectWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
        {/* @ts-ignore native select on web */}
        <select
          value={props.value}
          onChange={(e: any) => props.onChange(e.target.value)}
          style={{
            background: 'transparent',
            color: colors.textPrimary,
            border: 'none',
            outline: 'none',
            fontSize: 12,
            padding: '6px 8px',
            width: '100%',
          } as any}
        >
          {props.options.map((o) => (
            <option key={o} value={o} style={{ color: '#000' }}>{o || 'any'}</option>
          ))}
        </select>
      </View>
    </View>
  );
}

function PageBtn({ disabled, onPress, label, colors }: { disabled: boolean; onPress: () => void; label: string; colors: any }) {
  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={disabled}
      style={[
        styles.pageBtn,
        { borderColor: colors.border, opacity: disabled ? 0.4 : 1 },
      ]}
    >
      <Text style={[styles.pageBtnText, { color: colors.textSecondary }]}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  scroll: { padding: 24, gap: 16 },
  head: { gap: 4 },
  h1: { fontSize: 24, fontWeight: '800', letterSpacing: -0.2 },
  sub: { fontSize: 13, lineHeight: 19, maxWidth: 720 },
  filterRow: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 12,
    padding: 14, borderRadius: 10, borderWidth: 1, alignItems: 'flex-end',
  },
  filter: { gap: 4, minWidth: 110 },
  filterLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2 },
  selectWrap: { borderWidth: 1, borderRadius: 6 },
  searchWrap: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    borderWidth: 1, borderRadius: 6,
    paddingHorizontal: 8, minWidth: 200, height: 30,
  },
  searchInput: { flex: 1, fontSize: 12, paddingVertical: 0 },
  refreshBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: 6, borderWidth: 1,
    height: 30,
  },
  refreshText: { fontSize: 11, fontWeight: '600' },
  metaRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  metaText: { fontSize: 11 },
  pageBtn: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 6, borderWidth: 1 },
  pageBtnText: { fontSize: 11, fontWeight: '600' },
  errBox: { borderLeftWidth: 3, padding: 10, borderRadius: 4 },
  errText: { fontSize: 12 },
  table: { borderRadius: 10, borderWidth: 1, overflow: 'hidden' },
  thead: { flexDirection: 'row', paddingHorizontal: 14, paddingVertical: 10, borderBottomWidth: 1 },
  th: { paddingHorizontal: 6 },
  thText: { fontSize: 10, fontWeight: '700', letterSpacing: 1 },
  tr: { flexDirection: 'row', paddingHorizontal: 14, paddingVertical: 12, borderBottomWidth: 1, alignItems: 'center' },
  td: { paddingHorizontal: 6 },
  tdText: { fontSize: 12 },
  tdSub: { fontSize: 10, marginTop: 1 },
  userId: { fontSize: 13, fontWeight: '600' },
  userIdSub: { fontSize: 10, marginTop: 2 },
  empty: { padding: 32, alignItems: 'center', gap: 8 },
  emptyText: { fontSize: 12 },
  pill: {
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4,
    alignSelf: 'flex-start',
  },
  pillText: { fontSize: 10, fontWeight: '700', letterSpacing: 0.3 },
});
