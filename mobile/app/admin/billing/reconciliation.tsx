/**
 * /admin/billing/reconciliation — TIER-4B.2
 *
 * Integrity observability surface.  Feels like SOC/NOC, not a finance
 * spreadsheet:
 *
 *   * severity distribution strip (info / elevated / critical)
 *   * category breakdown (six detector buckets)
 *   * findings stream — append-only ledger; rows are immutable
 *   * manual "Run scan" trigger (NO scheduler yet — by design)
 *   * each row drillable into a snapshot-at-detection detail surface
 *
 * UI INVARIANTS (strict):
 *   * NEVER auto-heal — no Resolve/Fix/Apply controls anywhere
 *   * NEVER mutate findings — only operator ATTESTATION (acknowledge or
 *     mark-resolved-later) which writes a separate append-only event
 *   * ACKNOWLEDGED ≠ RESOLVED — visually separated
 *   * findings are immutable forever even when underlying issue clears
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, Pressable,
  ActivityIndicator, TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { AdminShell } from '../../../src/admin/components/AdminShell';
import { adminApi } from '../../../src/admin/api/adminClient';
import { useColors } from '../../../src/core/useColors';

const STATUS_OPTIONS = ['', 'open', 'acknowledged', 'resolved_later'] as const;
const SEVERITY_OPTIONS = ['', 'info', 'elevated', 'critical'] as const;
const CATEGORY_OPTIONS = ['',
  'stuck_pending', 'entitlement_mismatch', 'tier_without_billing_trail',
  'failed_activation', 'refunded_but_not_downgraded', 'orphan_audit_row',
] as const;
const CATEGORY_LABEL: Record<string, string> = {
  stuck_pending:               'Stuck pending',
  entitlement_mismatch:        'Entitlement mismatch',
  tier_without_billing_trail:  'Tier without billing trail',
  failed_activation:           'Failed activation',
  refunded_but_not_downgraded: 'Refunded · not downgraded',
  orphan_audit_row:            'Orphan audit row',
};

interface Finding {
  findingId: string;
  findingType: string;
  severity: 'info' | 'elevated' | 'critical';
  userId: string | null;
  invoiceId: string | null;
  detectedAt: string;
  scanId: string;
  parentFindingId: string | null;
  status: 'open' | 'acknowledged' | 'resolved_later';
  evidence: any;
}
interface Summary {
  totalFindings: number;
  bySeverity: { info: number; elevated: number; critical: number };
  byCategory: Record<string, number>;
  byStatus: { open: number; acknowledged: number; resolved_later: number };
  lastScan: { scanId: string; startedAt: string; durationMs: number; newFindingsCount: number } | null;
}

function timeAgo(iso?: string | null): string {
  if (!iso) return '—';
  const t = Date.parse(iso);
  if (!isFinite(t)) return '—';
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s/60)}m ago`;
  if (s < 86400) return `${Math.floor(s/3600)}h ago`;
  return `${Math.floor(s/86400)}d ago`;
}

export default function BillingReconciliationScreen() {
  const colors = useColors();
  const router = useRouter();

  const [summary, setSummary] = useState<Summary | null>(null);
  const [rows, setRows] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [status, setStatus] = useState<string>('');
  const [severity, setSeverity] = useState<string>('');
  const [category, setCategory] = useState<string>('');

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [sumRes, listRes] = await Promise.all([
        adminApi.reconciliationSummary(),
        adminApi.reconciliationListFindings({
          status: (status || undefined) as any,
          severity: (severity || undefined) as any,
          findingType: category || undefined,
          limit: 200,
        }),
      ]);
      setSummary(sumRes);
      setRows(listRes.rows || []);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.error || e?.message || 'Failed to load reconciliation surface');
    } finally {
      setLoading(false);
    }
  }, [status, severity, category]);

  useEffect(() => { load(); }, [load]);

  const runScan = async () => {
    setScanning(true);
    try {
      await adminApi.reconciliationScan();
      await load();
    } catch (e: any) {
      setError(e?.response?.data?.detail?.error || e?.message || 'Scan failed');
    } finally {
      setScanning(false);
    }
  };

  return (
    <AdminShell>
      <ScrollView contentContainerStyle={[styles.scroll, { backgroundColor: colors.background }]}>
        {/* Sub-nav within Billing domain */}
        <View style={styles.subnav}>
          <SubNavLink label="Invoices" onPress={() => router.replace('/admin/billing' as any)} colors={colors} />
          <SubNavLink label="Reconciliation" active colors={colors} />
          <SubNavLink label="Analytics" onPress={() => router.replace('/admin/billing/analytics' as any)} colors={colors} />
        </View>

        {/* Heading */}
        <View style={styles.head}>
          <View style={{ flex: 1 }}>
            <Text style={[styles.h1, { color: colors.textPrimary }]}>Reconciliation</Text>
            <Text style={[styles.sub, { color: colors.textSecondary }]}>
              Integrity observability layer. Detect, classify, surface, escalate. Never auto-heal.
              {' '}Findings are immutable records of what the system observed at detection time.
            </Text>
          </View>
          <TouchableOpacity
            onPress={runScan}
            disabled={scanning}
            style={[
              styles.scanBtn,
              { backgroundColor: scanning ? colors.surfaceHover : colors.accent, borderColor: colors.accent },
            ]}
            testID="recon-scan-btn"
          >
            {scanning
              ? <ActivityIndicator color={colors.accentText} size="small" />
              : <Ionicons name="scan-outline" size={14} color={colors.accentText} />}
            <Text style={[styles.scanBtnText, { color: colors.accentText }]}>
              {scanning ? 'Scanning…' : 'Run scan'}
            </Text>
          </TouchableOpacity>
        </View>

        {error && (
          <View style={[styles.errBox, { borderColor: colors.danger, backgroundColor: colors.badgeHighBg }]}>
            <Text style={[styles.errText, { color: colors.badgeHighText }]}>{error}</Text>
          </View>
        )}

        {/* Severity distribution strip */}
        {summary && (
          <View style={[styles.strip, { backgroundColor: colors.surface, borderColor: colors.border }]}>
            <SevTile label="critical"  value={summary.bySeverity.critical}  tone={colors.sell}             colors={colors} />
            <SevTile label="elevated"  value={summary.bySeverity.elevated}  tone={colors.accent}           colors={colors} />
            <SevTile label="info"      value={summary.bySeverity.info}      tone={colors.textSecondary}    colors={colors} />
            <View style={[styles.stripDivider, { backgroundColor: colors.border }]} />
            <StatusTile label="OPEN"           value={summary.byStatus.open}           tone={colors.sell}          colors={colors} />
            <StatusTile label="ACKNOWLEDGED"   value={summary.byStatus.acknowledged}   tone={colors.accent}        colors={colors} />
            <StatusTile label="RESOLVED LATER" value={summary.byStatus.resolved_later} tone={colors.buy}           colors={colors} />
            <View style={{ flex: 1 }} />
            <View style={styles.lastScanBox}>
              <Text style={[styles.lastScanLabel, { color: colors.textMuted }]}>LAST SCAN</Text>
              <Text style={[styles.lastScanValue, { color: colors.textPrimary }]}>
                {summary.lastScan ? `${timeAgo(summary.lastScan.startedAt)} · ${summary.lastScan.durationMs}ms · +${summary.lastScan.newFindingsCount}` : 'never run'}
              </Text>
            </View>
          </View>
        )}

        {/* Category breakdown chips */}
        {summary && (
          <View style={styles.catGroup}>
            <Text style={[styles.catGroupLabel, { color: colors.textMuted }]}>BY CATEGORY</Text>
            <View style={styles.catRow}>
              {Object.keys(CATEGORY_LABEL).map(c => {
                const v = summary.byCategory[c] || 0;
                const active = category === c;
                return (
                  <Pressable
                    key={c}
                    onPress={() => setCategory(active ? '' : c)}
                    style={({ hovered }: any) => [
                      styles.catChip,
                      {
                        borderColor: active ? colors.accent : colors.border,
                        backgroundColor: active ? colors.surfaceHover : colors.surface,
                      },
                      hovered && !active && { borderColor: colors.textSecondary },
                    ]}
                  >
                    <Text style={[styles.catChipCount, { color: v > 0 ? colors.textPrimary : colors.textMuted }]}>
                      {v}
                    </Text>
                    <Text style={[styles.catChipLabel, { color: colors.textSecondary }]}>{CATEGORY_LABEL[c]}</Text>
                  </Pressable>
                );
              })}
            </View>
          </View>
        )}

        {/* Filters */}
        <View style={[styles.filterRow, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <FilterSelect label="Status"   value={status}   onChange={setStatus}   options={STATUS_OPTIONS as any}/>
          <FilterSelect label="Severity" value={severity} onChange={setSeverity} options={SEVERITY_OPTIONS as any}/>
          <FilterSelect label="Category" value={category} onChange={setCategory} options={CATEGORY_OPTIONS as any}/>
          <TouchableOpacity onPress={load} style={[styles.refreshBtn, { borderColor: colors.border }]}>
            <Ionicons name="refresh-outline" size={14} color={colors.textSecondary} />
            <Text style={[styles.refreshText, { color: colors.textSecondary }]}>refresh</Text>
          </TouchableOpacity>
        </View>

        {/* Findings stream */}
        <View style={[styles.table, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <View style={[styles.thead, { borderBottomColor: colors.border }]}>
            <Th flex={0.9}>Severity</Th>
            <Th flex={1.7}>Category</Th>
            <Th flex={1.5}>Target</Th>
            <Th flex={1.5}>Detected</Th>
            <Th flex={1.1}>Status</Th>
            <Th flex={0.4}> </Th>
          </View>
          {!loading && rows.length === 0 && (
            <View style={styles.empty}>
              <Ionicons name="checkmark-done-circle-outline" size={22} color={colors.textMuted} />
              <Text style={[styles.emptyText, { color: colors.textMuted }]}>
                No findings match the current filters. Run a fresh scan to refresh the integrity view.
              </Text>
            </View>
          )}
          {loading && (
            <View style={styles.empty}><ActivityIndicator color={colors.accent} /></View>
          )}
          {!loading && rows.map(r => (
            <FindingRow
              key={r.findingId}
              row={r}
              onPress={() => router.push(`/admin/billing/reconciliation/${encodeURIComponent(r.findingId)}` as any)}
            />
          ))}
        </View>

        <Text style={[styles.footnote, { color: colors.textMuted }]}>
          Findings are append-only. Severity, evidence and detectedAt are immutable. Acknowledgement is a separate attestation event — it never closes the underlying record.
        </Text>
      </ScrollView>
    </AdminShell>
  );
}

// ── Components ─────────────────────────────────────────────────────────

function SubNavLink({ label, active, onPress, colors }: { label: string; active?: boolean; onPress?: () => void; colors: any }) {
  return (
    <Pressable
      onPress={onPress}
      disabled={active}
      style={[
        styles.subnavLink,
        { borderBottomColor: active ? colors.accent : 'transparent' },
      ]}
    >
      <Text style={[
        styles.subnavLinkText,
        { color: active ? colors.textPrimary : colors.textSecondary, fontWeight: active ? '700' : '500' },
      ]}>
        {label}
      </Text>
    </Pressable>
  );
}

function FindingRow({ row, onPress }: { row: Finding; onPress: () => void }) {
  const colors = useColors();
  return (
    <Pressable
      onPress={onPress}
      style={({ hovered }: any) => [
        styles.tr,
        { borderBottomColor: colors.border },
        hovered && { backgroundColor: colors.surfaceHover },
      ]}
      testID={`finding-row-${row.findingId}`}
    >
      <Td flex={0.9}>
        <SevPill severity={row.severity} colors={colors} />
      </Td>
      <Td flex={1.7}>
        <Text style={[styles.tdText, { color: colors.textPrimary }]} numberOfLines={1}>
          {CATEGORY_LABEL[row.findingType] || row.findingType}
        </Text>
        {row.parentFindingId && (
          <Text style={[styles.tdSub, { color: colors.textMuted }]} numberOfLines={1}>
            escalated from elevated
          </Text>
        )}
      </Td>
      <Td flex={1.5}>
        {row.invoiceId && (
          <Text style={[styles.tdText, { color: colors.textSecondary, fontFamily: 'monospace' }]} numberOfLines={1}>
            {row.invoiceId}
          </Text>
        )}
        {row.userId && (
          <Text style={[styles.tdSub, { color: colors.textMuted, fontFamily: 'monospace' }]} numberOfLines={1}>
            {row.userId}
          </Text>
        )}
      </Td>
      <Td flex={1.5}>
        <Text style={[styles.tdText, { color: colors.textSecondary }]} numberOfLines={1}>
          {timeAgo(row.detectedAt)}
        </Text>
      </Td>
      <Td flex={1.1}>
        <StatusPill status={row.status} colors={colors} />
      </Td>
      <Td flex={0.4}>
        <Ionicons name="chevron-forward" size={14} color={colors.textMuted} />
      </Td>
    </Pressable>
  );
}

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

function SevPill({ severity, colors }: { severity: string; colors: any }) {
  const map: Record<string, { bg: string; fg: string }> = {
    info:     { bg: colors.badgeLowBg || colors.surfaceHover, fg: colors.badgeLowText || colors.buy },
    elevated: { bg: colors.badgeMidBg || colors.surfaceHover, fg: colors.badgeMidText || colors.accent },
    critical: { bg: colors.badgeHighBg, fg: colors.badgeHighText },
  };
  const p = map[severity] || map.info;
  return (
    <View style={[styles.pill, { backgroundColor: p.bg }]}>
      <Text style={[styles.pillText, { color: p.fg }]}>{severity.toUpperCase()}</Text>
    </View>
  );
}

function StatusPill({ status, colors }: { status: string; colors: any }) {
  // Visual separation invariant: acknowledged ≠ resolved_later ≠ open.
  const map: Record<string, { bg: string; fg: string; label: string }> = {
    open:           { bg: colors.badgeHighBg, fg: colors.badgeHighText, label: 'STILL OPEN' },
    acknowledged:   { bg: colors.badgeMidBg || colors.surfaceHover, fg: colors.badgeMidText || colors.accent, label: 'ACKNOWLEDGED' },
    resolved_later: { bg: colors.badgeLowBg || colors.surfaceHover, fg: colors.badgeLowText || colors.buy, label: 'RESOLVED LATER' },
  };
  const p = map[status] || map.open;
  return (
    <View style={[styles.statusPill, { backgroundColor: p.bg }]}>
      <Text style={[styles.statusPillText, { color: p.fg }]}>{p.label}</Text>
    </View>
  );
}

function SevTile({ label, value, tone, colors }: { label: string; value: number; tone: string; colors: any }) {
  return (
    <View style={[styles.sevTile, { backgroundColor: colors.background, borderLeftColor: tone }]}>
      <Text style={[styles.sevTileValue, { color: tone }]}>{value}</Text>
      <Text style={[styles.sevTileLabel, { color: colors.textMuted }]}>{label}</Text>
    </View>
  );
}

function StatusTile({ label, value, tone, colors }: { label: string; value: number; tone: string; colors: any }) {
  return (
    <View style={styles.statusTile}>
      <Text style={[styles.statusTileLabel, { color: colors.textMuted }]}>{label}</Text>
      <Text style={[styles.statusTileValue, { color: value > 0 ? tone : colors.textMuted }]}>{value}</Text>
    </View>
  );
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
            background: 'transparent', color: colors.textPrimary,
            border: 'none', outline: 'none', fontSize: 12,
            padding: '6px 8px', width: '100%',
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

const styles = StyleSheet.create({
  scroll: { padding: 24, gap: 16 },
  subnav: { flexDirection: 'row', gap: 8, marginBottom: -4 },
  subnavLink: { paddingVertical: 6, paddingHorizontal: 4, borderBottomWidth: 2, marginRight: 8 },
  subnavLinkText: { fontSize: 12, letterSpacing: 0.3 },

  head: { flexDirection: 'row', alignItems: 'flex-start', gap: 16 },
  h1: { fontSize: 24, fontWeight: '800', letterSpacing: -0.2 },
  sub: { fontSize: 13, lineHeight: 19, maxWidth: 760, marginTop: 4 },
  scanBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 14, paddingVertical: 9, borderRadius: 6, borderWidth: 1,
  },
  scanBtnText: { fontSize: 12, fontWeight: '700', letterSpacing: 0.2 },

  strip: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    padding: 12, borderRadius: 10, borderWidth: 1,
  },
  stripDivider: { width: 1, alignSelf: 'stretch', marginHorizontal: 4 },
  sevTile: {
    paddingVertical: 8, paddingHorizontal: 14, borderRadius: 6,
    borderLeftWidth: 3, minWidth: 86,
  },
  sevTileValue: { fontSize: 18, fontWeight: '800', fontFamily: 'monospace' },
  sevTileLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 1, marginTop: 1 },
  statusTile: { paddingHorizontal: 8, gap: 2 },
  statusTileLabel: { fontSize: 9, fontWeight: '700', letterSpacing: 0.8 },
  statusTileValue: { fontSize: 16, fontWeight: '800', fontFamily: 'monospace' },
  lastScanBox: { alignItems: 'flex-end' },
  lastScanLabel: { fontSize: 9, fontWeight: '700', letterSpacing: 1 },
  lastScanValue: { fontSize: 11, fontFamily: 'monospace', marginTop: 2 },

  catGroup: { gap: 6 },
  catGroupLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2 },
  catRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  catChip: {
    paddingHorizontal: 12, paddingVertical: 10, borderRadius: 8, borderWidth: 1,
    minWidth: 140,
  },
  catChipCount: { fontSize: 16, fontWeight: '800', fontFamily: 'monospace' },
  catChipLabel: { fontSize: 10, marginTop: 2, fontWeight: '600', letterSpacing: 0.3 },

  filterRow: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 12,
    padding: 14, borderRadius: 10, borderWidth: 1, alignItems: 'flex-end',
  },
  filter: { gap: 4, minWidth: 140 },
  filterLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2 },
  selectWrap: { borderWidth: 1, borderRadius: 6 },
  refreshBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: 6, borderWidth: 1,
    height: 30,
  },
  refreshText: { fontSize: 11, fontWeight: '600' },

  errBox: { borderLeftWidth: 3, padding: 10, borderRadius: 4 },
  errText: { fontSize: 12 },

  table: { borderRadius: 10, borderWidth: 1, overflow: 'hidden' },
  thead: { flexDirection: 'row', paddingHorizontal: 14, paddingVertical: 10, borderBottomWidth: 1 },
  th: { paddingHorizontal: 6 },
  thText: { fontSize: 10, fontWeight: '700', letterSpacing: 1 },
  tr: { flexDirection: 'row', paddingHorizontal: 14, paddingVertical: 12, borderBottomWidth: 1, alignItems: 'center' },
  td: { paddingHorizontal: 6 },
  tdText: { fontSize: 12 },
  tdSub: { fontSize: 10, marginTop: 2 },
  empty: { padding: 32, alignItems: 'center', gap: 8 },
  emptyText: { fontSize: 12, textAlign: 'center', maxWidth: 400 },

  pill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4, alignSelf: 'flex-start' },
  pillText: { fontSize: 10, fontWeight: '800', letterSpacing: 0.6 },
  statusPill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4, alignSelf: 'flex-start' },
  statusPillText: { fontSize: 9, fontWeight: '800', letterSpacing: 0.8 },

  footnote: { fontSize: 11, fontStyle: 'italic', marginTop: 4 },
});
