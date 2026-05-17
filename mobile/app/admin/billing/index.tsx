/**
 * /admin/billing — finance operations surface (TIER-4B.1).
 *
 * Commercial vocabulary ONLY: invoice, product, entitlement, refund,
 * customer.  This screen NEVER mutates operator_access governance —
 * the only state change that can ripple through is `tier`, achieved by
 * billing confirm/refund flows that the backend isolates explicitly.
 *
 * Behaviour contract:
 *   * loads invoices from /api/billing/invoices with filters
 *   * Create-Invoice opens a constrained modal (userId + product + opt price)
 *   * NO inline edits, NO mutable cells — ledger feel
 *   * row click → /admin/billing/[invoiceId]
 *   * no optimistic UI: every mutation followed by authoritative refetch
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, Pressable, TextInput,
  ActivityIndicator, TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { AdminShell } from '../../../src/admin/components/AdminShell';
import { adminApi } from '../../../src/admin/api/adminClient';
import { useColors } from '../../../src/core/useColors';
import { CreateInvoiceModal } from '../../../src/admin/components/modals/CreateInvoiceModal';

const STATUS_OPTIONS = ['', 'pending', 'paid', 'failed', 'refunded'] as const;
const PRODUCT_OPTIONS = ['', 'PRO', 'TRADER'] as const;
const PAGE_SIZE = 100;

interface Invoice {
  invoiceId: string;
  userId: string;
  productCode: 'PRO' | 'TRADER';
  productSnapshot: any;
  priceUsd: number;
  status: 'pending' | 'paid' | 'failed' | 'refunded';
  paymentReference: string | null;
  createdAt: string;
  paidAt: string | null;
  failedAt: string | null;
  refundedAt: string | null;
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

export default function BillingListScreen() {
  const colors = useColors();
  const router = useRouter();

  const [status, setStatus] = useState<string>('');
  const [productCode, setProductCode] = useState<string>('');
  const [q, setQ] = useState<string>('');

  const [rows, setRows] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [products, setProducts] = useState<any[]>([]);
  const [createOpen, setCreateOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const filters: any = { limit: PAGE_SIZE };
      if (status) filters.status = status;
      if (q.trim()) filters.userId = q.trim().toLowerCase();
      const res = await adminApi.billingListInvoices(filters);
      let r: Invoice[] = res.rows || [];
      // client-side product filter — backend doesn't support it yet,
      // dataset is admin-bound so the page-size cap is safe.
      if (productCode) r = r.filter(x => x.productCode === productCode);
      setRows(r);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.error || e?.message || 'Failed to load invoices');
    } finally {
      setLoading(false);
    }
  }, [status, productCode, q]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    // Load product catalog once for Create modal.
    adminApi.billingProducts().then(r => setProducts(r?.products || [])).catch(() => {});
  }, []);

  // Aggregate counts for sticky status strip.
  const counts = useMemo(() => {
    const acc = { pending: 0, paid: 0, failed: 0, refunded: 0, gmv: 0 };
    for (const r of rows) {
      acc[r.status] += 1;
      if (r.status === 'paid') acc.gmv += r.priceUsd;
    }
    return acc;
  }, [rows]);

  return (
    <AdminShell>
      <ScrollView contentContainerStyle={[styles.scroll, { backgroundColor: colors.background }]}>
        {/* Sub-nav within Billing domain */}
        <View style={styles.subnav}>
          <Pressable
            disabled
            style={[styles.subnavLink, { borderBottomColor: colors.accent }]}
          >
            <Text style={[styles.subnavLinkText, { color: colors.textPrimary, fontWeight: '700' }]}>Invoices</Text>
          </Pressable>
          <Pressable
            onPress={() => router.push('/admin/billing/reconciliation' as any)}
            style={[styles.subnavLink, { borderBottomColor: 'transparent' }]}
          >
            <Text style={[styles.subnavLinkText, { color: colors.textSecondary, fontWeight: '500' }]}>Reconciliation</Text>
          </Pressable>
          <Pressable
            onPress={() => router.push('/admin/billing/analytics' as any)}
            style={[styles.subnavLink, { borderBottomColor: 'transparent' }]}
          >
            <Text style={[styles.subnavLinkText, { color: colors.textSecondary, fontWeight: '500' }]}>Analytics</Text>
          </Pressable>
        </View>

        {/* Heading */}
        <View style={styles.head}>
          <View style={{ flex: 1 }}>
            <Text style={[styles.h1, { color: colors.textPrimary }]}>Billing</Text>
            <Text style={[styles.sub, { color: colors.textSecondary }]}>
              Finance ledger · invoices and entitlement transitions.
              Commercial mutations only — operational authority is governed in <Text style={{ fontWeight: '700', color: colors.textSecondary }}>/admin/operators</Text>.
            </Text>
          </View>
          <TouchableOpacity
            onPress={() => setCreateOpen(true)}
            style={[styles.createBtn, { backgroundColor: colors.accent, borderColor: colors.accent }]}
            testID="billing-create-btn"
          >
            <Ionicons name="add" size={14} color={colors.accentText} />
            <Text style={[styles.createBtnText, { color: colors.accentText }]}>Create invoice</Text>
          </TouchableOpacity>
        </View>

        {/* Counts strip */}
        <View style={[styles.countsStrip, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <CountChip label="pending"  value={counts.pending}  kind="elevated" colors={colors} />
          <CountChip label="paid"     value={counts.paid}     kind="positive" colors={colors} />
          <CountChip label="failed"   value={counts.failed}   kind="danger"   colors={colors} />
          <CountChip label="refunded" value={counts.refunded} kind="neutral"  colors={colors} />
          <View style={{ flex: 1 }} />
          <View style={styles.gmvBox}>
            <Text style={[styles.gmvLabel, { color: colors.textMuted }]}>GMV (this page · paid only)</Text>
            <Text style={[styles.gmvValue, { color: colors.textPrimary }]}>
              ${counts.gmv.toFixed(2)}
            </Text>
          </View>
        </View>

        {/* Filter row */}
        <View style={[styles.filterRow, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <FilterSelect label="Status"  value={status}      onChange={setStatus}      options={STATUS_OPTIONS as any}/>
          <FilterSelect label="Product" value={productCode} onChange={setProductCode} options={PRODUCT_OPTIONS as any}/>
          <View style={[styles.searchWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
            <Ionicons name="search" size={14} color={colors.textMuted} />
            <TextInput
              value={q}
              onChangeText={setQ}
              placeholder="search customer userId"
              placeholderTextColor={colors.textMuted}
              style={[styles.searchInput, { color: colors.textPrimary }]}
              autoCapitalize="none"
              autoCorrect={false}
              onSubmitEditing={load}
            />
          </View>
          <TouchableOpacity onPress={load} style={[styles.refreshBtn, { borderColor: colors.border }]}>
            <Ionicons name="refresh-outline" size={14} color={colors.textSecondary} />
            <Text style={[styles.refreshText, { color: colors.textSecondary }]}>refresh</Text>
          </TouchableOpacity>
        </View>

        {error && (
          <View style={[styles.errBox, { borderColor: colors.danger, backgroundColor: colors.badgeHighBg }]}>
            <Text style={[styles.errText, { color: colors.badgeHighText }]}>{error}</Text>
          </View>
        )}

        {/* Ledger table */}
        <View style={[styles.table, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <View style={[styles.thead, { borderBottomColor: colors.border }]}>
            <Th flex={2.2}>Invoice</Th>
            <Th flex={1.8}>Customer</Th>
            <Th flex={1.0}>Product</Th>
            <Th flex={1.0}>Price (USD)</Th>
            <Th flex={1.0}>Status</Th>
            <Th flex={1.2}>Issued</Th>
            <Th flex={1.3}>Last transition</Th>
          </View>
          {!loading && rows.length === 0 && (
            <View style={styles.empty}>
              <Ionicons name="file-tray-outline" size={22} color={colors.textMuted} />
              <Text style={[styles.emptyText, { color: colors.textMuted }]}>
                No invoices match the current filters.
              </Text>
            </View>
          )}
          {loading && (
            <View style={styles.empty}>
              <ActivityIndicator color={colors.accent} />
            </View>
          )}
          {!loading && rows.map((r) => (
            <InvoiceRow
              key={r.invoiceId}
              row={r}
              onPress={() => router.push(`/admin/billing/${encodeURIComponent(r.invoiceId)}` as any)}
            />
          ))}
        </View>

        <Text style={[styles.footnote, { color: colors.textMuted }]}>
          Records below are append-only. Status transitions are immutable and audited.
        </Text>
      </ScrollView>

      <CreateInvoiceModal
        visible={createOpen}
        products={products as any}
        onCancel={() => setCreateOpen(false)}
        onConfirm={async ({ userId, productCode: code, priceUsdOverride }) => {
          const r = await adminApi.billingCreateInvoice(userId, code);
          // Backend takes only userId+productCode for now; price override is recorded
          // separately if the API extends.  Authoritative refetch follows regardless.
          void priceUsdOverride; // reserved for future param wiring
          await load();
          // Navigate straight into the new invoice so the operator can confirm.
          const id = r?.invoice?.invoiceId;
          if (id) router.push(`/admin/billing/${encodeURIComponent(id)}` as any);
        }}
      />
    </AdminShell>
  );
}

// ── Row ───────────────────────────────────────────────────────────────

function InvoiceRow({ row, onPress }: { row: Invoice; onPress: () => void }) {
  const colors = useColors();
  const lastTs =
    row.refundedAt || row.failedAt || row.paidAt || row.createdAt;
  const lastLabel =
    row.refundedAt ? 'refunded'
    : row.failedAt ? 'failed'
    : row.paidAt ? 'paid'
    : 'created';

  return (
    <Pressable
      onPress={onPress}
      style={({ hovered }: any) => [
        styles.tr,
        { borderBottomColor: colors.border },
        hovered && { backgroundColor: colors.surfaceHover },
      ]}
      testID={`invoice-row-${row.invoiceId}`}
    >
      <Td flex={2.2}>
        <Text style={[styles.invoiceId, { color: colors.textPrimary }]} numberOfLines={1}>
          {row.invoiceId}
        </Text>
        {row.paymentReference && (
          <Text style={[styles.invoiceSub, { color: colors.textMuted }]} numberOfLines={1}>
            ref · {row.paymentReference}
          </Text>
        )}
      </Td>
      <Td flex={1.8}>
        <Text style={[styles.tdText, { color: colors.textSecondary }]} numberOfLines={1}>{row.userId}</Text>
      </Td>
      <Td flex={1.0}>
        <Pill text={row.productCode} kind={row.productCode === 'TRADER' ? 'elevated' : 'positive'} colors={colors} />
      </Td>
      <Td flex={1.0}>
        <Text style={[styles.tdText, { color: colors.textPrimary, fontFamily: 'monospace' }]}>
          {row.priceUsd.toFixed(2)}
        </Text>
      </Td>
      <Td flex={1.0}>
        <Pill text={row.status} kind={statusKind(row.status)} colors={colors} />
      </Td>
      <Td flex={1.2}>
        <Text style={[styles.tdText, { color: colors.textSecondary }]} numberOfLines={1}>{timeAgo(row.createdAt)}</Text>
      </Td>
      <Td flex={1.3}>
        <Text style={[styles.tdText, { color: colors.textSecondary }]} numberOfLines={1}>
          {timeAgo(lastTs)}
        </Text>
        <Text style={[styles.tdSub, { color: colors.textMuted }]} numberOfLines={1}>{lastLabel}</Text>
      </Td>
    </Pressable>
  );
}

// ── Primitives ────────────────────────────────────────────────────────

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
function statusKind(s: string): PillKind {
  if (s === 'paid')     return 'positive';
  if (s === 'pending')  return 'elevated';
  if (s === 'failed')   return 'danger';
  if (s === 'refunded') return 'neutral';
  return 'neutral';
}

function CountChip({ label, value, kind, colors }: { label: string; value: number; kind: PillKind; colors: any }) {
  const palette: Record<PillKind, { bg: string; fg: string }> = {
    neutral:  { bg: colors.surfaceHover, fg: colors.textSecondary },
    positive: { bg: colors.badgeLowBg || colors.surfaceHover, fg: colors.badgeLowText || colors.buy },
    elevated: { bg: colors.badgeMidBg || colors.surfaceHover, fg: colors.badgeMidText || colors.accent },
    critical: { bg: colors.badgeHighBg, fg: colors.badgeHighText },
    danger:   { bg: colors.badgeHighBg, fg: colors.badgeHighText },
  };
  const p = palette[kind];
  return (
    <View style={[styles.countChip, { backgroundColor: p.bg }]}>
      <Text style={[styles.countValue, { color: p.fg }]}>{value}</Text>
      <Text style={[styles.countLabel, { color: p.fg }]}>{label}</Text>
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
  sub: { fontSize: 13, lineHeight: 19, maxWidth: 720, marginTop: 4 },
  createBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 14, paddingVertical: 9, borderRadius: 6, borderWidth: 1,
  },
  createBtnText: { fontSize: 12, fontWeight: '700', letterSpacing: 0.2 },
  countsStrip: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    padding: 12, borderRadius: 10, borderWidth: 1,
  },
  countChip: {
    flexDirection: 'row', alignItems: 'baseline', gap: 6,
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: 6,
  },
  countValue: { fontSize: 16, fontWeight: '800', fontFamily: 'monospace' },
  countLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 0.8 },
  gmvBox: { alignItems: 'flex-end' },
  gmvLabel: { fontSize: 9, fontWeight: '700', letterSpacing: 1 },
  gmvValue: { fontSize: 16, fontWeight: '800', fontFamily: 'monospace', marginTop: 2 },
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
    paddingHorizontal: 8, minWidth: 230, height: 30,
  },
  searchInput: { flex: 1, fontSize: 12, paddingVertical: 0 },
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
  tdSub: { fontSize: 10, marginTop: 1 },
  invoiceId: { fontSize: 12, fontWeight: '700', fontFamily: 'monospace' },
  invoiceSub: { fontSize: 10, marginTop: 2, fontFamily: 'monospace' },
  empty: { padding: 32, alignItems: 'center', gap: 8 },
  emptyText: { fontSize: 12 },
  pill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4, alignSelf: 'flex-start' },
  pillText: { fontSize: 10, fontWeight: '700', letterSpacing: 0.3 },
  footnote: { fontSize: 11, fontStyle: 'italic', marginTop: 4 },
});
