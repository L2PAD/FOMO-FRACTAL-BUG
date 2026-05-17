/**
 * /admin/billing/[id] — invoice detail (TIER-4B.1).
 *
 * Ledger surface, not CMS:
 *   * NO editable fields
 *   * frozen productSnapshot prominent (core audit primitive)
 *   * FSM-aware actions:
 *       pending  → Confirm Payment | Mark Failed
 *       paid     → Refund (typed)
 *       failed   → immutable
 *       refunded → immutable
 *   * audit timeline as a first-class section (not collapsed)
 *
 * Invariant guard (UI level): no control here ever mutates governance —
 * the only state changes are commercial (status · tier-via-billing).
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, Pressable,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { AdminShell } from '../../../src/admin/components/AdminShell';
import { adminApi } from '../../../src/admin/api/adminClient';
import { useColors } from '../../../src/core/useColors';
import { BillingRefundModal } from '../../../src/admin/components/modals/BillingRefundModal';
import { ConfirmActionModal } from '../../../src/admin/components/modals/ConfirmActionModal';

interface Invoice {
  invoiceId: string;
  userId: string;
  productCode: 'PRO' | 'TRADER';
  productSnapshot: {
    code: string;
    type: string;
    title: string;
    subtitle: string;
    tier: string;
    priceUsd: number;
    grants: string[];
    doesNotGrant: string[];
  };
  priceUsd: number;
  status: 'pending' | 'paid' | 'failed' | 'refunded';
  paymentReference: string | null;
  createdAt: string;
  paidAt: string | null;
  failedAt: string | null;
  refundedAt: string | null;
}

interface AuditEvent {
  ts: string;
  action: string;
  severity: 'info' | 'elevated' | 'critical';
  actor: string;
  before: any;
  after: any;
  invoiceId?: string | null;
  reason?: string | null;
  note?: string | null;
}

function fmtTs(iso?: string | null): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toISOString().replace('T', ' ').replace(/\..+/, ' UTC');
  } catch { return iso || '—'; }
}

export default function InvoiceDetailScreen() {
  const colors = useColors();
  const router = useRouter();
  const params = useLocalSearchParams<{ id: string }>();
  const invoiceId = decodeURIComponent(String(params.id || ''));

  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<'confirm' | 'fail' | null>(null);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [failOpen, setFailOpen] = useState(false);
  const [refundOpen, setRefundOpen] = useState(false);

  // Authoritative load — invoice + per-customer audit, then filter by invoiceId.
  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      // We don't have a per-invoice GET endpoint — fetch via list with the
      // userId-less filter (admin sees all) and pick the row, or do a list
      // by invoiceId.  Simpler: fetch all (admin), then find.  Dataset is
      // capped server-side; for production this would be a dedicated GET.
      const listRes = await adminApi.billingListInvoices({ limit: 500 });
      const inv = (listRes.rows || []).find((r: any) => r.invoiceId === invoiceId) as Invoice | undefined;
      if (!inv) {
        setInvoice(null);
        setAudit([]);
        setError('INVOICE_NOT_FOUND');
        return;
      }
      setInvoice(inv);
      // Audit timeline is per-user; we filter to this invoice's rows.
      const auditRes = await adminApi.billingAuditTimeline(inv.userId, 200);
      const rows: AuditEvent[] = (auditRes.rows || []).filter(
        (e: any) => !e.invoiceId || e.invoiceId === inv.invoiceId,
      );
      setAudit(rows);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.error || e?.message || 'Failed to load invoice');
    } finally {
      setLoading(false);
    }
  }, [invoiceId]);

  useEffect(() => { load(); }, [load]);

  // ConfirmActionModal's onConfirm signature is (reason: string) => Promise<void>.
  // It auto-closes on success; on throw, the modal stays open and shows error.
  // We do NOT use optimistic UI: every mutation is followed by load() (authoritative refetch).
  const doConfirm = async (_reason: string) => {
    setBusy('confirm');
    try {
      await adminApi.billingConfirmInvoice(invoiceId);
      await load();
    } finally {
      setBusy(null);
    }
  };
  const doFail = async (reason: string) => {
    setBusy('fail');
    try {
      await adminApi.billingFailInvoice(invoiceId, reason || undefined);
      await load();
    } finally {
      setBusy(null);
    }
  };
  const doRefund = async ({ reason }: { reason: string }) => {
    await adminApi.billingRefundInvoice(invoiceId, reason);
    await load();
  };

  if (loading && !invoice) {
    return (
      <AdminShell>
        <View style={[styles.center, { backgroundColor: colors.background }]}>
          <ActivityIndicator color={colors.accent} />
        </View>
      </AdminShell>
    );
  }
  if (error && !invoice) {
    return (
      <AdminShell>
        <ScrollView contentContainerStyle={[styles.scroll, { backgroundColor: colors.background }]}>
          <BackLink onPress={() => router.replace('/admin/billing' as any)} />
          <View style={[styles.errBox, { borderColor: colors.danger, backgroundColor: colors.badgeHighBg }]}>
            <Text style={[styles.errText, { color: colors.badgeHighText }]}>
              {error === 'INVOICE_NOT_FOUND' ? 'Invoice not found.' : error}
            </Text>
          </View>
        </ScrollView>
      </AdminShell>
    );
  }
  if (!invoice) return null;

  const isPending = invoice.status === 'pending';
  const isPaid    = invoice.status === 'paid';
  const isFinal   = invoice.status === 'failed' || invoice.status === 'refunded';

  return (
    <AdminShell>
      <ScrollView contentContainerStyle={[styles.scroll, { backgroundColor: colors.background }]}>
        <BackLink onPress={() => router.replace('/admin/billing' as any)} />

        {/* Header */}
        <View style={styles.head}>
          <View style={{ flex: 1 }}>
            <Text style={[styles.h1, { color: colors.textPrimary }]} testID="invoice-id">
              {invoice.invoiceId}
            </Text>
            <View style={styles.headMetaRow}>
              <StatusPill status={invoice.status} colors={colors} />
              <Text style={[styles.headMeta, { color: colors.textMuted }]}>
                customer <Text style={{ color: colors.textSecondary, fontWeight: '700' }}>{invoice.userId}</Text>
              </Text>
              <Text style={[styles.headMeta, { color: colors.textMuted }]}>·</Text>
              <Text style={[styles.headMeta, { color: colors.textMuted }]}>
                product <Text style={{ color: colors.textSecondary, fontWeight: '700' }}>{invoice.productCode}</Text>
              </Text>
              <Text style={[styles.headMeta, { color: colors.textMuted }]}>·</Text>
              <Text style={[styles.headMeta, { color: colors.textMuted }]}>
                amount <Text style={{ color: colors.textSecondary, fontWeight: '700', fontFamily: 'monospace' }}>
                  ${invoice.priceUsd.toFixed(2)}
                </Text>
              </Text>
            </View>
          </View>

          {/* FSM-aware action cluster */}
          <View style={styles.actions}>
            {isPending && (
              <>
                <ActionBtn
                  testID="invoice-confirm-btn"
                  icon="checkmark-circle-outline"
                  label="Confirm payment"
                  kind="primary"
                  onPress={() => setConfirmOpen(true)}
                  busy={busy === 'confirm'}
                  colors={colors}
                />
                <ActionBtn
                  testID="invoice-fail-btn"
                  icon="close-circle-outline"
                  label="Mark failed"
                  kind="warn"
                  onPress={() => setFailOpen(true)}
                  busy={busy === 'fail'}
                  colors={colors}
                />
              </>
            )}
            {isPaid && (
              <ActionBtn
                testID="invoice-refund-btn"
                icon="return-down-back"
                label="Refund"
                kind="danger"
                onPress={() => setRefundOpen(true)}
                colors={colors}
              />
            )}
            {isFinal && (
              <View style={[styles.frozenBadge, { borderColor: colors.border, backgroundColor: colors.surface }]}>
                <Ionicons name="lock-closed-outline" size={14} color={colors.textSecondary} />
                <Text style={[styles.frozenText, { color: colors.textSecondary }]}>Immutable record</Text>
              </View>
            )}
          </View>
        </View>

        {/* Why actions are unavailable (transparency) */}
        {!isPending && !isPaid && (
          <View style={[styles.fsmNote, { borderColor: colors.border, backgroundColor: colors.surface }]}>
            <Ionicons name="information-circle-outline" size={14} color={colors.textMuted} />
            <Text style={[styles.fsmNoteText, { color: colors.textMuted }]}>
              {invoice.status === 'failed'
                ? 'This invoice was marked failed. Failed invoices are terminal; no further commercial transitions are possible.'
                : 'This invoice was refunded. Refunded invoices are terminal; entitlement was downgraded at the time of refund.'}
            </Text>
          </View>
        )}

        {/* Two-column body */}
        <View style={styles.cols}>
          {/* LEFT: invoice + product snapshot */}
          <View style={styles.colLeft}>
            <Section title="Invoice record" colors={colors}>
              <KV k="Invoice ID"        v={invoice.invoiceId}            mono colors={colors} />
              <KV k="Customer"          v={invoice.userId}               mono colors={colors} />
              <KV k="Product code"      v={invoice.productCode}          colors={colors} />
              <KV k="Price (charged)"   v={`$${invoice.priceUsd.toFixed(2)}`} mono colors={colors} />
              <KV k="Payment reference" v={invoice.paymentReference || '—'} mono colors={colors} />
              <Divider colors={colors} />
              <KV k="Created"  v={fmtTs(invoice.createdAt)}  mono colors={colors} />
              <KV k="Paid"     v={fmtTs(invoice.paidAt)}     mono colors={colors} />
              <KV k="Failed"   v={fmtTs(invoice.failedAt)}   mono colors={colors} />
              <KV k="Refunded" v={fmtTs(invoice.refundedAt)} mono colors={colors} />
            </Section>

            <Section
              title="Product snapshot at purchase time"
              subtitle="Frozen at issuance. This is the source of truth for entitlement — regardless of how the live catalog evolves later."
              colors={colors}
            >
              <KV k="Title"     v={invoice.productSnapshot.title}     colors={colors} />
              <KV k="Type"      v={invoice.productSnapshot.type}      colors={colors} />
              <KV k="Tier on activation" v={invoice.productSnapshot.tier} colors={colors} />
              <KV k="Snapshot price"     v={`$${invoice.productSnapshot.priceUsd.toFixed(2)}`} mono colors={colors} />
              <Divider colors={colors} />
              <View style={styles.grantBlock}>
                <Text style={[styles.grantHead, { color: colors.buy }]}>GRANTS</Text>
                <View style={styles.grantPills}>
                  {invoice.productSnapshot.grants.map((g) => (
                    <View key={g} style={[styles.gp, { backgroundColor: colors.badgeLowBg || colors.surfaceHover }]}>
                      <Text style={[styles.gpText, { color: colors.badgeLowText || colors.buy }]}>{g}</Text>
                    </View>
                  ))}
                </View>
              </View>
              <View style={styles.grantBlock}>
                <Text style={[styles.grantHead, { color: colors.textMuted }]}>DOES NOT GRANT</Text>
                <View style={styles.grantPills}>
                  {invoice.productSnapshot.doesNotGrant.map((g) => (
                    <View key={g} style={[styles.gpMuted, { borderColor: colors.border }]}>
                      <Text style={[styles.gpTextMuted, { color: colors.textMuted, textDecorationLine: 'line-through' }]}>
                        {g}
                      </Text>
                    </View>
                  ))}
                </View>
                <Text style={[styles.grantFoot, { color: colors.textMuted }]}>
                  These capabilities are governance grants — they can only be issued by an operator via
                  /admin/operators. Billing has never granted them and never will.
                </Text>
              </View>
            </Section>
          </View>

          {/* RIGHT: audit timeline (first-class) */}
          <View style={styles.colRight}>
            <Section title="Audit timeline" subtitle="Append-only · immutable · newest first" colors={colors}>
              {audit.length === 0 ? (
                <Text style={[styles.muted, { color: colors.textMuted }]}>No audit events yet.</Text>
              ) : (
                <View style={{ gap: 14 }}>
                  {audit.map((ev, idx) => (
                    <AuditCard key={`${ev.ts}-${idx}`} ev={ev} colors={colors} />
                  ))}
                </View>
              )}
            </Section>
          </View>
        </View>
      </ScrollView>

      <ConfirmActionModal
        visible={confirmOpen}
        title="Confirm payment"
        body={
          <Text>
            Mark this invoice <Text style={{ fontWeight: '700' }}>paid</Text> and activate the
            commercial entitlement. Tier will move to <Text style={{ fontWeight: '700' }}>{invoice.productSnapshot.tier}</Text>.
            No operational governance fields are touched.
          </Text>
        }
        confirmLabel="Confirm payment"
        severity="info"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={doConfirm}
      />
      <ConfirmActionModal
        visible={failOpen}
        title="Mark invoice failed"
        body={
          <Text>
            Marks this pending invoice as <Text style={{ fontWeight: '700' }}>failed</Text>. No entitlement is granted.
            This transition is terminal — the record becomes immutable.
          </Text>
        }
        confirmLabel="Mark failed"
        severity="elevated"
        onCancel={() => setFailOpen(false)}
        onConfirm={doFail}
      />
      <BillingRefundModal
        visible={refundOpen}
        invoiceId={invoice.invoiceId}
        userId={invoice.userId}
        productCode={invoice.productCode}
        priceUsd={invoice.priceUsd}
        onCancel={() => setRefundOpen(false)}
        onConfirm={doRefund}
      />
    </AdminShell>
  );
}

// ── Components ────────────────────────────────────────────────────────

function BackLink({ onPress }: { onPress: () => void }) {
  const colors = useColors();
  return (
    <Pressable onPress={onPress} style={styles.backLink}>
      <Ionicons name="arrow-back" size={14} color={colors.textSecondary} />
      <Text style={[styles.backLinkText, { color: colors.textSecondary }]}>Back to billing</Text>
    </Pressable>
  );
}

function Section({
  title, subtitle, colors, children,
}: { title: string; subtitle?: string; colors: any; children: React.ReactNode }) {
  return (
    <View style={[styles.section, { backgroundColor: colors.surface, borderColor: colors.border }]}>
      <Text style={[styles.sectionTitle, { color: colors.textPrimary }]}>{title}</Text>
      {subtitle && <Text style={[styles.sectionSub, { color: colors.textMuted }]}>{subtitle}</Text>}
      <View style={{ marginTop: 10, gap: 6 }}>{children}</View>
    </View>
  );
}

function KV({ k, v, mono, colors }: { k: string; v: string; mono?: boolean; colors: any }) {
  return (
    <View style={styles.kv}>
      <Text style={[styles.kvKey, { color: colors.textMuted }]}>{k}</Text>
      <Text
        style={[styles.kvVal, { color: colors.textPrimary, fontFamily: mono ? 'monospace' : undefined }]}
        numberOfLines={1}
      >
        {v}
      </Text>
    </View>
  );
}

function Divider({ colors }: { colors: any }) {
  return <View style={[styles.divider, { backgroundColor: colors.border }]} />;
}

function StatusPill({ status, colors }: { status: string; colors: any }) {
  const map: Record<string, { bg: string; fg: string }> = {
    pending:  { bg: colors.badgeMidBg || colors.surfaceHover, fg: colors.badgeMidText || colors.accent },
    paid:     { bg: colors.badgeLowBg || colors.surfaceHover, fg: colors.badgeLowText || colors.buy },
    failed:   { bg: colors.badgeHighBg, fg: colors.badgeHighText },
    refunded: { bg: colors.surfaceHover, fg: colors.textSecondary },
  };
  const p = map[status] || map.refunded;
  return (
    <View style={[styles.statusPill, { backgroundColor: p.bg }]}>
      <Text style={[styles.statusPillText, { color: p.fg }]}>{status.toUpperCase()}</Text>
    </View>
  );
}

function ActionBtn({
  icon, label, kind, onPress, busy, colors, testID,
}: {
  icon: any; label: string; kind: 'primary' | 'warn' | 'danger';
  onPress: () => void; busy?: boolean; colors: any; testID?: string;
}) {
  const bg =
    kind === 'primary' ? colors.accent
    : kind === 'warn'  ? colors.badgeMidBg || colors.surface
    : colors.sell;
  const fg =
    kind === 'primary' ? colors.accentText
    : kind === 'warn'  ? (colors.badgeMidText || colors.accent)
    : colors.accentText;
  const border =
    kind === 'primary' ? colors.accent
    : kind === 'warn'  ? colors.border
    : colors.sell;

  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={busy}
      style={[styles.actionBtn, { backgroundColor: bg, borderColor: border, opacity: busy ? 0.6 : 1 }]}
      testID={testID}
    >
      {busy
        ? <ActivityIndicator color={fg} size="small" />
        : <Ionicons name={icon} size={14} color={fg} />}
      <Text style={[styles.actionBtnText, { color: fg }]}>{label}</Text>
    </TouchableOpacity>
  );
}

function AuditCard({ ev, colors }: { ev: AuditEvent; colors: any }) {
  const sevMap: Record<string, { bg: string; fg: string }> = {
    info:     { bg: colors.badgeLowBg || colors.surfaceHover, fg: colors.badgeLowText || colors.buy },
    elevated: { bg: colors.badgeMidBg || colors.surfaceHover, fg: colors.badgeMidText || colors.accent },
    critical: { bg: colors.badgeHighBg, fg: colors.badgeHighText },
  };
  const sev = sevMap[ev.severity] || sevMap.info;
  return (
    <View style={[styles.auditCard, { borderColor: colors.border, backgroundColor: colors.background }]}>
      <View style={styles.auditHead}>
        <View style={[styles.sevPill, { backgroundColor: sev.bg }]}>
          <Text style={[styles.sevPillText, { color: sev.fg }]}>{ev.severity.toUpperCase()}</Text>
        </View>
        <Text style={[styles.auditAction, { color: colors.textPrimary }]} numberOfLines={1}>{ev.action}</Text>
        <View style={{ flex: 1 }} />
        <Text style={[styles.auditTs, { color: colors.textMuted }]} numberOfLines={1}>{fmtTs(ev.ts)}</Text>
      </View>
      <View style={styles.auditMeta}>
        <Text style={[styles.auditActor, { color: colors.textSecondary }]}>
          actor · <Text style={{ color: colors.textPrimary, fontWeight: '700', fontFamily: 'monospace' }}>{ev.actor}</Text>
        </Text>
        {ev.reason && (
          <Text style={[styles.auditReason, { color: colors.textSecondary }]}>
            reason · {ev.reason}
          </Text>
        )}
      </View>
      {(ev.before || ev.after) && (
        <View style={styles.auditDiff}>
          <View style={[styles.diffCol, { borderColor: colors.border, backgroundColor: colors.surface }]}>
            <Text style={[styles.diffLabel, { color: colors.textMuted }]}>BEFORE</Text>
            <Text style={[styles.diffJson, { color: colors.textSecondary }]} numberOfLines={6}>
              {JSON.stringify(ev.before || {}, null, 2)}
            </Text>
          </View>
          <View style={[styles.diffCol, { borderColor: colors.border, backgroundColor: colors.surface }]}>
            <Text style={[styles.diffLabel, { color: colors.textMuted }]}>AFTER</Text>
            <Text style={[styles.diffJson, { color: colors.textPrimary }]} numberOfLines={6}>
              {JSON.stringify(ev.after || {}, null, 2)}
            </Text>
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  scroll: { padding: 24, gap: 16 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  backLink: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  backLinkText: { fontSize: 12, fontWeight: '600' },
  head: { flexDirection: 'row', alignItems: 'flex-start', gap: 16 },
  h1: { fontSize: 22, fontWeight: '800', fontFamily: 'monospace', letterSpacing: -0.2 },
  headMetaRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8, flexWrap: 'wrap' },
  headMeta: { fontSize: 12 },
  statusPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 4 },
  statusPillText: { fontSize: 10, fontWeight: '800', letterSpacing: 1 },
  actions: { flexDirection: 'row', gap: 8, flexWrap: 'wrap', alignItems: 'center' },
  actionBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 6, borderWidth: 1,
  },
  actionBtnText: { fontSize: 12, fontWeight: '700', letterSpacing: 0.2 },
  frozenBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 10, paddingVertical: 8, borderRadius: 6, borderWidth: 1,
  },
  frozenText: { fontSize: 11, fontWeight: '700', letterSpacing: 0.4 },
  fsmNote: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 8,
    borderWidth: 1, padding: 10, borderRadius: 6,
  },
  fsmNoteText: { fontSize: 12, flex: 1, lineHeight: 17 },
  cols: { flexDirection: 'row', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' },
  colLeft: { flex: 1, minWidth: 340, gap: 16 },
  colRight: { flex: 1.2, minWidth: 360 },
  section: { borderWidth: 1, borderRadius: 10, padding: 16 },
  sectionTitle: { fontSize: 14, fontWeight: '800', letterSpacing: 0.2 },
  sectionSub: { fontSize: 11, marginTop: 4, lineHeight: 16 },
  kv: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  kvKey: { fontSize: 10, fontWeight: '700', letterSpacing: 1, width: 140 },
  kvVal: { fontSize: 12, flex: 1 },
  divider: { height: StyleSheet.hairlineWidth, marginVertical: 6 },
  grantBlock: { marginTop: 8, gap: 6 },
  grantHead: { fontSize: 10, fontWeight: '700', letterSpacing: 1 },
  grantPills: { flexDirection: 'row', flexWrap: 'wrap', gap: 4 },
  gp: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4 },
  gpMuted: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4, borderWidth: 1 },
  gpText: { fontSize: 10, fontWeight: '700' },
  gpTextMuted: { fontSize: 10, fontWeight: '500' },
  grantFoot: { fontSize: 10, fontStyle: 'italic', marginTop: 4, lineHeight: 15 },
  muted: { fontSize: 12 },
  errBox: { borderLeftWidth: 3, padding: 10, borderRadius: 4 },
  errText: { fontSize: 12 },
  // audit
  auditCard: { borderWidth: 1, borderRadius: 8, padding: 12, gap: 8 },
  auditHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  sevPill: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 3 },
  sevPillText: { fontSize: 9, fontWeight: '800', letterSpacing: 0.8 },
  auditAction: { fontSize: 12, fontWeight: '700', fontFamily: 'monospace' },
  auditTs: { fontSize: 10, fontFamily: 'monospace' },
  auditMeta: { gap: 2 },
  auditActor: { fontSize: 11 },
  auditReason: { fontSize: 11, fontStyle: 'italic' },
  auditDiff: { flexDirection: 'row', gap: 8 },
  diffCol: { flex: 1, borderWidth: 1, borderRadius: 6, padding: 8, gap: 4 },
  diffLabel: { fontSize: 9, fontWeight: '700', letterSpacing: 1 },
  diffJson: { fontSize: 10, fontFamily: 'monospace', lineHeight: 14 },
});
