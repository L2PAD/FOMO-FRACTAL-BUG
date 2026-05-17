/**
 * /admin/billing/analytics — TIER-4B.3
 *
 * Derived business-intelligence surface.  CALM/AGGREGATED feel —
 * NOT a SOC alert dashboard.  Cards, ratios, gentle pills, subdued
 * severity usage.  Window switcher (7d/30d/90d).
 *
 * UI INVARIANTS:
 *   * Analytics is DERIVED — never source of truth.  Display this
 *     directly in the heading so operators don't mistake it for the
 *     ledger.
 *   * Refunds are DUAL-TRACKED visually — gross / refunded / net
 *     shown side by side.  Never display only a netted number.
 *   * Churn is SEPARATED — refund-driven vs voluntary, two
 *     distinct blocks.  Never aggregated into a single "churn".
 *   * MRR is labelled as APPROXIMATION (these are one-time invoices,
 *     not recurring subscriptions).
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, Pressable,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { AdminShell } from '../../../src/admin/components/AdminShell';
import { adminApi } from '../../../src/admin/api/adminClient';
import { useColors } from '../../../src/core/useColors';

type Window = '7d' | '30d' | '90d';

interface Summary {
  window: Window;
  windowDays: number;
  windowStart: string;
  windowEnd: string;
  computedAt: string;
  revenue: {
    grossRevenue: number;
    grossPaidCount: number;
    refundedRevenue: number;
    refundedCount: number;
    netRevenue: number;
  };
  mrr: {
    mrrApproxUsd: number;
    trailingWindowDays: number;
    trailingGrossRevenue: number;
    trailingRefundedRevenue: number;
  };
  conversion: {
    createdCount: number;
    paidCount: number;
    refundedCount: number;
    failedCount: number;
    pendingCount: number;
    stuckPendingCount: number;
    activatedCount: number;
    conversionRatePct: number;
    failureRatePct: number;
    stuckRatePct: number;
    activationRatePct: number;
  };
  productMix: {
    pro:    { count: number; grossRevenue: number; countShare: number; revShare: number };
    trader: { count: number; grossRevenue: number; countShare: number; revShare: number };
    totalPaidPlusRefunded: number;
    totalGrossRevenue: number;
  };
  refundRate: {
    overallRefundRatePct: number;
    pro:    { paidCount: number; refundedCount: number; refundRatePct: number };
    trader: { paidCount: number; refundedCount: number; refundRatePct: number };
  };
  churn: {
    refundDriven: { proToFree: number; traderToFree: number; total: number };
    voluntary:    { proToFree: number; traderToFree: number; total: number };
  };
}

const fmtUsd = (n: number) => `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtPct = (n: number) => `${n.toFixed(2)}%`;

export default function BillingAnalyticsScreen() {
  const colors = useColors();
  const router = useRouter();
  const [windowSel, setWindowSel] = useState<Window>('30d');
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await adminApi.billingAnalyticsSummary(windowSel);
      setSummary(res);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.error || e?.message || 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  }, [windowSel]);

  useEffect(() => { load(); }, [load]);

  return (
    <AdminShell>
      <ScrollView contentContainerStyle={[styles.scroll, { backgroundColor: colors.background }]}>
        {/* Sub-nav inside Billing */}
        <View style={styles.subnav}>
          <SubNavLink label="Invoices" onPress={() => router.replace('/admin/billing' as any)} colors={colors} />
          <SubNavLink label="Reconciliation" onPress={() => router.replace('/admin/billing/reconciliation' as any)} colors={colors} />
          <SubNavLink label="Analytics" active colors={colors} />
        </View>

        {/* Heading + window switcher */}
        <View style={styles.head}>
          <View style={{ flex: 1 }}>
            <Text style={[styles.h1, { color: colors.textPrimary }]}>Analytics</Text>
            <Text style={[styles.sub, { color: colors.textSecondary }]}>
              Derived business intelligence — read model. Source of truth remains the
              <Text style={{ fontWeight: '700', color: colors.textSecondary }}> invoice ledger</Text>,
              <Text style={{ fontWeight: '700', color: colors.textSecondary }}> audit timeline </Text>
              and <Text style={{ fontWeight: '700', color: colors.textSecondary }}>reconciliation findings</Text>.
              Refresh on demand; this surface never mutates billing state.
            </Text>
          </View>
          <View style={[styles.windowSwitcher, { borderColor: colors.border, backgroundColor: colors.surface }]}>
            {(['7d', '30d', '90d'] as Window[]).map(w => {
              const active = w === windowSel;
              return (
                <Pressable
                  key={w}
                  onPress={() => setWindowSel(w)}
                  style={[
                    styles.windowBtn,
                    {
                      backgroundColor: active ? colors.accent : 'transparent',
                    },
                  ]}
                  testID={`window-${w}`}
                >
                  <Text style={[
                    styles.windowBtnText,
                    { color: active ? colors.accentText : colors.textSecondary },
                  ]}>
                    {w}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>

        {error && (
          <View style={[styles.errBox, { borderColor: colors.danger, backgroundColor: colors.badgeHighBg }]}>
            <Text style={[styles.errText, { color: colors.badgeHighText }]}>{error}</Text>
          </View>
        )}
        {loading && !summary && (
          <View style={styles.loadingBox}><ActivityIndicator color={colors.accent} /></View>
        )}

        {summary && (
          <>
            {/* ── Revenue (gross / refunded / net) ─────────────────── */}
            <SectionHeader title="Revenue" colors={colors}
              subtitle={`Rolling ${summary.windowDays} days · gross and refunded are tracked separately and never silently netted`} />
            <View style={styles.cardRow}>
              <BigCard
                label="GROSS REVENUE"
                value={fmtUsd(summary.revenue.grossRevenue)}
                meta={`${summary.revenue.grossPaidCount} paid events`}
                tone={colors.textPrimary}
                accent={colors.buy}
                colors={colors}
              />
              <BigCard
                label="REFUNDED REVENUE"
                value={fmtUsd(summary.revenue.refundedRevenue)}
                meta={`${summary.revenue.refundedCount} refunded events`}
                tone={colors.textPrimary}
                accent={colors.sell}
                colors={colors}
              />
              <BigCard
                label="NET REVENUE"
                value={fmtUsd(summary.revenue.netRevenue)}
                meta="gross − refunded"
                tone={colors.textPrimary}
                accent={colors.accent}
                colors={colors}
                highlighted
              />
            </View>

            {/* ── MRR approximation ───────────────────────────────── */}
            <View style={[styles.mrrCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
              <View style={{ flex: 1 }}>
                <Text style={[styles.cardLabel, { color: colors.textMuted }]}>MRR APPROXIMATION</Text>
                <Text style={[styles.cardValue, { color: colors.textPrimary }]}>{fmtUsd(summary.mrr.mrrApproxUsd)}</Text>
                <Text style={[styles.mrrCaveat, { color: colors.textMuted }]}>
                  Trailing 30-day net revenue. Products are one-time invoice issuances, not recurring subscriptions —
                  this is an approximation, not a strict recurring-revenue figure.
                </Text>
              </View>
              <View style={styles.mrrSplitRow}>
                <View style={styles.mrrSplitCol}>
                  <Text style={[styles.mrrSplitLabel, { color: colors.textMuted }]}>30d gross</Text>
                  <Text style={[styles.mrrSplitValue, { color: colors.textSecondary }]}>{fmtUsd(summary.mrr.trailingGrossRevenue)}</Text>
                </View>
                <View style={styles.mrrSplitCol}>
                  <Text style={[styles.mrrSplitLabel, { color: colors.textMuted }]}>30d refunded</Text>
                  <Text style={[styles.mrrSplitValue, { color: colors.textSecondary }]}>{fmtUsd(summary.mrr.trailingRefundedRevenue)}</Text>
                </View>
              </View>
            </View>

            {/* ── Conversion funnel ───────────────────────────────── */}
            <SectionHeader title="Conversion funnel" colors={colors}
              subtitle="Invoices created in window → paid → activated. Cross-reference with reconciliation for stuck/failed details." />
            <View style={styles.funnelRow}>
              <FunnelStep label="Created"   value={summary.conversion.createdCount}    colors={colors} />
              <FunnelArrow colors={colors} />
              <FunnelStep label="Paid"      value={summary.conversion.paidCount + summary.conversion.refundedCount}
                          meta={`${fmtPct(summary.conversion.conversionRatePct)} of created`} colors={colors} />
              <FunnelArrow colors={colors} />
              <FunnelStep label="Activated" value={summary.conversion.activatedCount}
                          meta={`${fmtPct(summary.conversion.activationRatePct)} of paid+refunded`} colors={colors} />
            </View>
            <View style={styles.ratioRow}>
              <RatioPill label="Conversion (paid+refunded / created)"
                         value={fmtPct(summary.conversion.conversionRatePct)} tone={colors.buy} colors={colors} />
              <RatioPill label="Failed"
                         value={fmtPct(summary.conversion.failureRatePct)}    tone={colors.sell} colors={colors} />
              <RatioPill label="Stuck pending (>24h)"
                         value={fmtPct(summary.conversion.stuckRatePct)}      tone={colors.accent} colors={colors}
                         meta={`${summary.conversion.stuckPendingCount} invoice${summary.conversion.stuckPendingCount === 1 ? '' : 's'}`} />
              <RatioPill label="Currently pending"
                         value={`${summary.conversion.pendingCount}`}         tone={colors.textSecondary} colors={colors} />
            </View>

            {/* ── Product mix ─────────────────────────────────────── */}
            <SectionHeader title="Product mix" colors={colors}
              subtitle="Paid + refunded invoices in window, by commercial product" />
            <View style={styles.productRow}>
              <ProductCard
                code="PRO"
                count={summary.productMix.pro.count}
                revenue={summary.productMix.pro.grossRevenue}
                countShare={summary.productMix.pro.countShare}
                revShare={summary.productMix.pro.revShare}
                colors={colors}
              />
              <ProductCard
                code="TRADER"
                count={summary.productMix.trader.count}
                revenue={summary.productMix.trader.grossRevenue}
                countShare={summary.productMix.trader.countShare}
                revShare={summary.productMix.trader.revShare}
                colors={colors}
              />
            </View>

            {/* ── Refund rate ─────────────────────────────────────── */}
            <SectionHeader title="Refund rate" colors={colors}
              subtitle="Refunds as a share of paid events in window — per product, plus overall" />
            <View style={styles.refundRow}>
              <RefundCard
                title="Overall"
                paidCount={summary.refundRate.pro.paidCount + summary.refundRate.trader.paidCount}
                refundedCount={summary.refundRate.pro.refundedCount + summary.refundRate.trader.refundedCount}
                rate={summary.refundRate.overallRefundRatePct}
                colors={colors}
                emphasized
              />
              <RefundCard
                title="PRO"
                paidCount={summary.refundRate.pro.paidCount}
                refundedCount={summary.refundRate.pro.refundedCount}
                rate={summary.refundRate.pro.refundRatePct}
                colors={colors}
              />
              <RefundCard
                title="TRADER"
                paidCount={summary.refundRate.trader.paidCount}
                refundedCount={summary.refundRate.trader.refundedCount}
                rate={summary.refundRate.trader.refundRatePct}
                colors={colors}
              />
            </View>

            {/* ── Churn (dual-tracked) ────────────────────────────── */}
            <SectionHeader title="Churn" colors={colors}
              subtitle="Refund-driven (commercial) and voluntary (governance) downgrades are tracked separately — two different operational stories" />
            <View style={styles.churnRow}>
              <ChurnCard
                title="Refund-driven"
                subtitle="Tier walked back automatically by the refund flow"
                proToFree={summary.churn.refundDriven.proToFree}
                traderToFree={summary.churn.refundDriven.traderToFree}
                total={summary.churn.refundDriven.total}
                tone={colors.sell}
                colors={colors}
              />
              <ChurnCard
                title="Voluntary"
                subtitle="Admin-initiated set-tier downgrades via /admin/operators"
                proToFree={summary.churn.voluntary.proToFree}
                traderToFree={summary.churn.voluntary.traderToFree}
                total={summary.churn.voluntary.total}
                tone={colors.accent}
                colors={colors}
              />
            </View>

            <Text style={[styles.footnote, { color: colors.textMuted }]}>
              Computed at {new Date(summary.computedAt).toLocaleString()}.
              Window {summary.window} · {new Date(summary.windowStart).toLocaleDateString()} → {new Date(summary.windowEnd).toLocaleDateString()}.
              Analytics is a derived read model. To investigate any number, drill into{' '}
              <Text style={{ color: colors.textSecondary, fontWeight: '700' }}>Invoices</Text> or{' '}
              <Text style={{ color: colors.textSecondary, fontWeight: '700' }}>Reconciliation</Text>.
            </Text>
          </>
        )}
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
      style={[styles.subnavLink, { borderBottomColor: active ? colors.accent : 'transparent' }]}
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

function SectionHeader({ title, subtitle, colors }: { title: string; subtitle?: string; colors: any }) {
  return (
    <View style={styles.sectionHeader}>
      <Text style={[styles.sectionTitle, { color: colors.textPrimary }]}>{title}</Text>
      {subtitle && <Text style={[styles.sectionSub, { color: colors.textMuted }]}>{subtitle}</Text>}
    </View>
  );
}

function BigCard({
  label, value, meta, accent, colors, highlighted,
}: { label: string; value: string; meta?: string; tone?: string; accent: string; colors: any; highlighted?: boolean }) {
  return (
    <View style={[
      styles.bigCard,
      {
        backgroundColor: colors.surface,
        borderColor: highlighted ? accent : colors.border,
        borderLeftWidth: 3, borderLeftColor: accent,
      },
    ]}>
      <Text style={[styles.cardLabel, { color: colors.textMuted }]}>{label}</Text>
      <Text style={[styles.cardValue, { color: colors.textPrimary }]}>{value}</Text>
      {meta && <Text style={[styles.cardMeta, { color: colors.textMuted }]}>{meta}</Text>}
    </View>
  );
}

function FunnelStep({ label, value, meta, colors }: { label: string; value: number; meta?: string; colors: any }) {
  return (
    <View style={[styles.funnelCell, { backgroundColor: colors.surface, borderColor: colors.border }]}>
      <Text style={[styles.cardLabel, { color: colors.textMuted }]}>{label.toUpperCase()}</Text>
      <Text style={[styles.cardValue, { color: colors.textPrimary }]}>{value}</Text>
      {meta && <Text style={[styles.cardMeta, { color: colors.textMuted }]}>{meta}</Text>}
    </View>
  );
}

function FunnelArrow({ colors }: { colors: any }) {
  return (
    <View style={styles.funnelArrow}>
      <Ionicons name="arrow-forward" size={18} color={colors.textMuted} />
    </View>
  );
}

function RatioPill({
  label, value, tone, colors, meta,
}: { label: string; value: string; tone: string; colors: any; meta?: string }) {
  return (
    <View style={[styles.ratioPill, { backgroundColor: colors.surface, borderColor: colors.border }]}>
      <Text style={[styles.ratioPillValue, { color: tone }]}>{value}</Text>
      <Text style={[styles.ratioPillLabel, { color: colors.textMuted }]}>{label}</Text>
      {meta && <Text style={[styles.ratioPillMeta, { color: colors.textSecondary }]}>{meta}</Text>}
    </View>
  );
}

function ProductCard({
  code, count, revenue, countShare, revShare, colors,
}: { code: string; count: number; revenue: number; countShare: number; revShare: number; colors: any }) {
  return (
    <View style={[styles.productCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
      <View style={styles.productHead}>
        <Text style={[styles.productCode, { color: colors.textPrimary }]}>{code}</Text>
        <View style={[styles.productPill, { backgroundColor: colors.surfaceHover }]}>
          <Text style={[styles.productPillText, { color: colors.textSecondary }]}>
            {fmtPct(revShare)} of revenue
          </Text>
        </View>
      </View>
      <View style={styles.productGrid}>
        <View style={styles.productCell}>
          <Text style={[styles.cardLabel, { color: colors.textMuted }]}>COUNT</Text>
          <Text style={[styles.cardValue, { color: colors.textPrimary }]}>{count}</Text>
          <Text style={[styles.cardMeta, { color: colors.textMuted }]}>{fmtPct(countShare)} of volume</Text>
        </View>
        <View style={styles.productCell}>
          <Text style={[styles.cardLabel, { color: colors.textMuted }]}>GROSS REVENUE</Text>
          <Text style={[styles.cardValue, { color: colors.textPrimary }]}>{fmtUsd(revenue)}</Text>
        </View>
      </View>
      {/* split bar */}
      <View style={[styles.splitBar, { backgroundColor: colors.surfaceHover }]}>
        <View style={[styles.splitFill, { width: `${revShare}%`, backgroundColor: colors.accent }]} />
      </View>
    </View>
  );
}

function RefundCard({
  title, paidCount, refundedCount, rate, colors, emphasized,
}: { title: string; paidCount: number; refundedCount: number; rate: number; colors: any; emphasized?: boolean }) {
  return (
    <View style={[
      styles.refundCard,
      {
        backgroundColor: colors.surface,
        borderColor: emphasized ? colors.accent : colors.border,
        borderTopWidth: emphasized ? 2 : 1,
      },
    ]}>
      <Text style={[styles.refundTitle, { color: colors.textMuted }]}>{title.toUpperCase()}</Text>
      <Text style={[styles.refundRate, { color: colors.textPrimary }]}>{fmtPct(rate)}</Text>
      <View style={styles.refundMeta}>
        <Text style={[styles.refundMetaText, { color: colors.textSecondary }]}>
          {refundedCount} refunded / {paidCount} paid
        </Text>
      </View>
    </View>
  );
}

function ChurnCard({
  title, subtitle, proToFree, traderToFree, total, tone, colors,
}: { title: string; subtitle: string; proToFree: number; traderToFree: number; total: number; tone: string; colors: any }) {
  return (
    <View style={[styles.churnCard, { backgroundColor: colors.surface, borderColor: colors.border, borderLeftColor: tone, borderLeftWidth: 3 }]}>
      <Text style={[styles.churnTitle, { color: colors.textPrimary }]}>{title}</Text>
      <Text style={[styles.churnSub, { color: colors.textMuted }]}>{subtitle}</Text>
      <View style={styles.churnGrid}>
        <View style={styles.churnCell}>
          <Text style={[styles.cardLabel, { color: colors.textMuted }]}>TOTAL</Text>
          <Text style={[styles.cardValue, { color: tone }]}>{total}</Text>
        </View>
        <View style={styles.churnCell}>
          <Text style={[styles.cardLabel, { color: colors.textMuted }]}>PRO → FREE</Text>
          <Text style={[styles.cardValue, { color: colors.textPrimary }]}>{proToFree}</Text>
        </View>
        <View style={styles.churnCell}>
          <Text style={[styles.cardLabel, { color: colors.textMuted }]}>TRADER → FREE</Text>
          <Text style={[styles.cardValue, { color: colors.textPrimary }]}>{traderToFree}</Text>
        </View>
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
  sub: { fontSize: 13, lineHeight: 19, maxWidth: 780, marginTop: 4 },

  windowSwitcher: { flexDirection: 'row', borderWidth: 1, borderRadius: 8, padding: 3, gap: 2 },
  windowBtn: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 6, minWidth: 50, alignItems: 'center' },
  windowBtnText: { fontSize: 12, fontWeight: '700', letterSpacing: 0.4 },

  errBox: { borderLeftWidth: 3, padding: 10, borderRadius: 4 },
  errText: { fontSize: 12 },
  loadingBox: { padding: 40, alignItems: 'center' },

  sectionHeader: { gap: 4, marginTop: 8 },
  sectionTitle: { fontSize: 16, fontWeight: '800', letterSpacing: 0.2 },
  sectionSub: { fontSize: 12, lineHeight: 17, maxWidth: 780 },

  cardRow: { flexDirection: 'row', gap: 12, flexWrap: 'wrap' },
  bigCard: { flex: 1, minWidth: 220, padding: 16, borderRadius: 10, borderWidth: 1, gap: 4 },
  cardLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2 },
  cardValue: { fontSize: 24, fontWeight: '800', fontFamily: 'monospace', marginTop: 4 },
  cardMeta: { fontSize: 11, marginTop: 2 },

  mrrCard: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 24,
    padding: 16, borderRadius: 10, borderWidth: 1, flexWrap: 'wrap',
  },
  mrrCaveat: { fontSize: 11, lineHeight: 16, marginTop: 6, maxWidth: 540 },
  mrrSplitRow: { flexDirection: 'row', gap: 24, paddingTop: 6 },
  mrrSplitCol: { gap: 2 },
  mrrSplitLabel: { fontSize: 9, fontWeight: '700', letterSpacing: 1 },
  mrrSplitValue: { fontSize: 14, fontFamily: 'monospace', fontWeight: '700' },

  funnelRow: { flexDirection: 'row', gap: 8, alignItems: 'stretch', flexWrap: 'wrap' },
  funnelCell: { flex: 1, minWidth: 150, padding: 14, borderRadius: 10, borderWidth: 1, gap: 4 },
  funnelArrow: { alignItems: 'center', justifyContent: 'center', paddingHorizontal: 4 },

  ratioRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  ratioPill: { paddingHorizontal: 14, paddingVertical: 10, borderRadius: 8, borderWidth: 1, gap: 2, minWidth: 150 },
  ratioPillValue: { fontSize: 18, fontWeight: '800', fontFamily: 'monospace' },
  ratioPillLabel: { fontSize: 10, fontWeight: '600', letterSpacing: 0.3 },
  ratioPillMeta: { fontSize: 10, marginTop: 2 },

  productRow: { flexDirection: 'row', gap: 12, flexWrap: 'wrap' },
  productCard: { flex: 1, minWidth: 280, padding: 16, borderRadius: 10, borderWidth: 1, gap: 12 },
  productHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  productCode: { fontSize: 18, fontWeight: '800', letterSpacing: 0.5 },
  productPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 4 },
  productPillText: { fontSize: 10, fontWeight: '700' },
  productGrid: { flexDirection: 'row', gap: 16 },
  productCell: { flex: 1, gap: 2 },
  splitBar: { height: 6, borderRadius: 3, overflow: 'hidden' },
  splitFill: { height: '100%', borderRadius: 3 },

  refundRow: { flexDirection: 'row', gap: 12, flexWrap: 'wrap' },
  refundCard: { flex: 1, minWidth: 180, padding: 14, borderRadius: 10, borderWidth: 1, gap: 4 },
  refundTitle: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2 },
  refundRate: { fontSize: 28, fontWeight: '800', fontFamily: 'monospace' },
  refundMeta: { marginTop: 4 },
  refundMetaText: { fontSize: 11 },

  churnRow: { flexDirection: 'row', gap: 12, flexWrap: 'wrap' },
  churnCard: { flex: 1, minWidth: 320, padding: 16, borderRadius: 10, borderWidth: 1, gap: 8 },
  churnTitle: { fontSize: 14, fontWeight: '800', letterSpacing: 0.2 },
  churnSub: { fontSize: 11, lineHeight: 16, marginBottom: 6 },
  churnGrid: { flexDirection: 'row', gap: 16, marginTop: 6 },
  churnCell: { flex: 1, gap: 2 },

  footnote: { fontSize: 11, fontStyle: 'italic', marginTop: 4, lineHeight: 16 },
});
