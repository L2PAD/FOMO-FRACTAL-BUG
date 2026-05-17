/**
 * /pricing — TIER-4C.1 Public Entitlement Surface
 *
 * The first place a user encounters the FREE / PRO / TRADER tiers
 * and the architectural boundary that separates them.
 *
 * UI INVARIANTS (locked):
 *   1. TRADER ≠ live trading.  Each product card shows TWO sections:
 *      WHAT YOU GET (grants) and WHAT THIS DOES NOT GRANT
 *      (doesNotGrant) — both rendered straight from backend
 *      productCatalog, never derived on the frontend.
 *   2. CURRENT PLAN block at the top reflects backend-authoritative
 *      entitlement (tier + capabilities).read straight from
 *      /api/me/billing/entitlement.
 *   3. Self-serve creates an invoice INTENT only.  Activation
 *      requires an operator to confirm.  Tier never moves on the
 *      client side; we always refetch entitlement to render state.
 *   4. No fake-urgency UX patterns — no countdown timers, no
 *      scarcity, no "best value" / "most popular" tags, no
 *      subscription language.  One-time invoice issuance only.
 *   5. No live-trading copywriting anywhere.  This is enforced both
 *      visually (we only render what backend returns) and
 *      structurally (catalog `grants`/`doesNotGrant`).
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, Pressable,
  ActivityIndicator, TouchableOpacity, useWindowDimensions,
  Modal,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { api } from '../src/services/api/api-client';
import { useColors } from '../src/core/useColors';

// ── Types ──────────────────────────────────────────────────────────

interface Product {
  code: 'PRO' | 'TRADER';
  type: string;
  title: string;
  subtitle: string;
  tier: string;
  priceUsd: number;
  grants: string[];
  doesNotGrant: string[];
}
interface Invoice {
  invoiceId: string;
  userId: string;
  productCode: 'PRO' | 'TRADER';
  priceUsd: number;
  status: 'pending' | 'paid' | 'failed' | 'refunded';
  createdAt: string;
  paidAt: string | null;
  refundedAt: string | null;
}
interface Entitlement {
  userId: string;
  tier: 'free' | 'pro' | 'trader';
  capabilities: any;
  pendingInvoices: Invoice[];
  paidInvoices: Invoice[];
}

// Human-readable capability labels — mapped from the canonical names
// returned by the backend in productSnapshot.grants / doesNotGrant.
const CAPABILITY_LABELS: Record<string, string> = {
  analyticsBasic:    'Basic market visibility',
  analyticsPro:      'Pro-level analytics & verdicts',
  tradingOsVisible:  'Trading OS surface',
  paperTrading:      'Paper execution workspace',
  shadowTrading:     'Shadow simulations',
  executionConsole:  'Execution console (operator)',
  liveTrading:       'Live capital deployment',
};

// What the FREE tier offers — derived directly from backend
// capability resolver (no claim is made about "FREE features" beyond
// what the backend actually returns).  Rendered as a card alongside
// the paid options for completeness of the public entitlement
// boundary view.
const FREE_GRANTS = ['analyticsBasic'];
const FREE_DOES_NOT_GRANT = [
  'analyticsPro', 'tradingOsVisible', 'paperTrading',
  'shadowTrading', 'executionConsole', 'liveTrading',
];

// ── Screen ─────────────────────────────────────────────────────────

export default function PricingScreen() {
  const colors = useColors();
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isWide = width >= 900;

  const [products, setProducts] = useState<Product[]>([]);
  const [entitlement, setEntitlement] = useState<Entitlement | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [purchasing, setPurchasing] = useState<null | 'PRO' | 'TRADER'>(null);
  const [purchaseResult, setPurchaseResult] = useState<{
    invoice: Invoice;
    deduplicated: boolean;
    paymentInstructions: any;
  } | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [p, e] = await Promise.all([
        api.get('/api/me/billing/products'),
        api.get('/api/me/billing/entitlement'),
      ]);
      setProducts(p.data?.products || []);
      setEntitlement(e.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail?.error || err?.message || 'Failed to load pricing');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const initiateUpgrade = async (code: 'PRO' | 'TRADER') => {
    setPurchasing(code);
    try {
      const r = await api.post('/api/me/billing/invoices', { productCode: code });
      setPurchaseResult({
        invoice:              r.data.invoice,
        deduplicated:         !!r.data.deduplicated,
        paymentInstructions:  r.data.paymentInstructions,
      });
      // Authoritative refetch — entitlement state always comes from backend
      await load();
    } catch (err: any) {
      setError(err?.response?.data?.detail?.error || err?.message || 'Could not initiate upgrade');
    } finally {
      setPurchasing(null);
    }
  };

  const tier = entitlement?.tier || 'free';
  const pendingByProduct = useMemo(() => {
    const m: Record<string, Invoice> = {};
    for (const inv of entitlement?.pendingInvoices || []) {
      m[inv.productCode] = inv;
    }
    return m;
  }, [entitlement]);

  return (
    <SafeAreaView style={[{ flex: 1, backgroundColor: colors.background }]} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scroll}>
        {/* Top bar with back-link */}
        <View style={styles.topbar}>
          <Pressable onPress={() => router.back()} style={styles.backBtn} hitSlop={10}>
            <Ionicons name="chevron-back" size={20} color={colors.textSecondary} />
            <Text style={[styles.backText, { color: colors.textSecondary }]}>Back</Text>
          </Pressable>
        </View>

        {/* Heading */}
        <Text style={[styles.h1, { color: colors.textPrimary }]}>Plans</Text>
        <Text style={[styles.sub, { color: colors.textSecondary }]}>
          Three product boundaries.  Pick the one that matches the depth of cognition you need.
          Each plan lists explicitly what it grants — and what it does not.
        </Text>

        {error && (
          <View style={[styles.errBox, { borderColor: colors.danger, backgroundColor: colors.badgeHighBg }]}>
            <Text style={{ color: colors.badgeHighText, fontSize: 12 }}>{error}</Text>
          </View>
        )}

        {/* Current entitlement panel — backend-authoritative */}
        {entitlement && (
          <View style={[styles.currentCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
            <View style={styles.currentHead}>
              <Text style={[styles.currentLabel, { color: colors.textMuted }]}>CURRENT PLAN</Text>
              <Text style={[styles.currentTier, { color: colors.textPrimary }]}>{tier.toUpperCase()}</Text>
            </View>
            <Text style={[styles.currentSub, { color: colors.textSecondary }]}>
              Capabilities below are resolved by the platform — they cannot be altered from the client.
            </Text>
            <View style={styles.currentChips}>
              {(entitlement.capabilities?.effectiveSummary?.can || []).map((c: string) => (
                <View key={`can-${c}`} style={[styles.canChip, { backgroundColor: colors.badgeLowBg || colors.surfaceHover }]}>
                  <Ionicons name="checkmark" size={11} color={colors.badgeLowText || colors.buy} />
                  <Text style={[styles.canChipText, { color: colors.badgeLowText || colors.buy }]}>{c}</Text>
                </View>
              ))}
              {(entitlement.capabilities?.effectiveSummary?.cannot || []).slice(0, 6).map((c: string) => (
                <View key={`cannot-${c}`} style={[styles.cannotChip, { borderColor: colors.border }]}>
                  <Ionicons name="close" size={11} color={colors.textMuted} />
                  <Text style={[styles.cannotChipText, { color: colors.textMuted }]}>{c}</Text>
                </View>
              ))}
            </View>
          </View>
        )}

        {/* Pricing grid */}
        {loading && !entitlement ? (
          <View style={styles.loadingBox}><ActivityIndicator color={colors.accent} /></View>
        ) : (
          <View style={[styles.grid, { flexDirection: isWide ? 'row' : 'column' }]}>
            {/* FREE */}
            <PlanCard
              code="FREE"
              title="Free"
              subtitle="Market visibility"
              priceUsd={0}
              grants={FREE_GRANTS}
              doesNotGrant={FREE_DOES_NOT_GRANT}
              currentTier={tier}
              pendingInvoice={undefined}
              purchasing={null}
              onPurchase={undefined}
              colors={colors}
            />
            {/* PRO + TRADER */}
            {products.map(p => (
              <PlanCard
                key={p.code}
                code={p.code}
                title={p.title.replace(/^[A-Z]+\s*—\s*/, '')}
                subtitle={p.subtitle}
                priceUsd={p.priceUsd}
                grants={p.grants}
                doesNotGrant={p.doesNotGrant}
                currentTier={tier}
                pendingInvoice={pendingByProduct[p.code]}
                purchasing={purchasing}
                onPurchase={() => initiateUpgrade(p.code)}
                colors={colors}
              />
            ))}
          </View>
        )}

        {/* Architectural boundary disclaimer (always visible) */}
        <View style={[styles.boundary, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <Ionicons name="shield-checkmark-outline" size={20} color={colors.accent} />
          <View style={{ flex: 1 }}>
            <Text style={[styles.boundaryTitle, { color: colors.textPrimary }]}>
              The commercial / operational boundary
            </Text>
            <Text style={[styles.boundaryText, { color: colors.textSecondary }]}>
              <Text style={{ fontWeight: '700', color: colors.textPrimary }}>TRADER unlocks paper trading only. </Text>
              Live capital access is never purchased automatically. Deploying live capital is a separate operator
              authorisation governed under {' '}
              <Text
                style={{ color: colors.accent, fontWeight: '700' }}
                onPress={() => router.push('/operator' as any)}
              >/operator</Text>
              {' '}— it cannot be acquired through any pricing card.
            </Text>
          </View>
        </View>

        <Text style={[styles.footnote, { color: colors.textMuted }]}>
          One-time invoice issuance · no subscription billing · entitlement activates after operator confirmation.
        </Text>
      </ScrollView>

      <PurchaseResultModal
        visible={purchaseResult !== null}
        result={purchaseResult}
        onClose={() => setPurchaseResult(null)}
      />
    </SafeAreaView>
  );
}

// ── Card ───────────────────────────────────────────────────────────

function PlanCard({
  code, title, subtitle, priceUsd, grants, doesNotGrant,
  currentTier, pendingInvoice, purchasing, onPurchase, colors,
}: {
  code: 'FREE' | 'PRO' | 'TRADER';
  title: string;
  subtitle: string;
  priceUsd: number;
  grants: string[];
  doesNotGrant: string[];
  currentTier: 'free' | 'pro' | 'trader';
  pendingInvoice?: Invoice;
  purchasing: 'PRO' | 'TRADER' | null;
  onPurchase?: () => void;
  colors: any;
}) {
  const tierLower = code.toLowerCase();
  const isCurrent = tierLower === currentTier;
  const isFree = code === 'FREE';
  const isPending = !!pendingInvoice;

  const accent = code === 'TRADER' ? colors.accent : code === 'PRO' ? colors.buy : colors.textMuted;

  return (
    <View style={[
      styles.planCard,
      {
        backgroundColor: colors.surface,
        borderColor: isCurrent ? accent : colors.border,
        borderTopColor: accent,
        borderTopWidth: 3,
      },
    ]} testID={`plan-card-${code}`}>
      {/* Header */}
      <View style={styles.planHead}>
        <Text style={[styles.planCode, { color: colors.textPrimary }]}>{code}</Text>
        {isCurrent && (
          <View style={[styles.currentPill, { backgroundColor: accent }]}>
            <Text style={[styles.currentPillText, { color: colors.accentText }]}>CURRENT</Text>
          </View>
        )}
      </View>
      <Text style={[styles.planTitle, { color: colors.textSecondary }]}>{title}</Text>
      <Text style={[styles.planSub, { color: colors.textMuted }]}>{subtitle}</Text>
      <Text style={[styles.planPrice, { color: colors.textPrimary }]}>
        {isFree ? 'free' : `$${priceUsd.toFixed(0)}`}
        {!isFree && <Text style={[styles.planPriceSub, { color: colors.textMuted }]}>  · one-time</Text>}
      </Text>

      {/* WHAT YOU GET */}
      <Text style={[styles.sectionLabel, { color: colors.buy }]}>WHAT YOU GET</Text>
      <View style={styles.featList}>
        {grants.map(g => (
          <View key={g} style={styles.featRow}>
            <Ionicons name="checkmark-circle" size={14} color={colors.buy} />
            <Text style={[styles.featText, { color: colors.textPrimary }]}>
              {CAPABILITY_LABELS[g] || g}
            </Text>
          </View>
        ))}
      </View>

      {/* WHAT THIS DOES NOT GRANT — mandatory section per architectural invariant */}
      <Text style={[styles.sectionLabel, { color: colors.textMuted, marginTop: 10 }]}>WHAT THIS DOES NOT GRANT</Text>
      <View style={styles.featList}>
        {doesNotGrant.map(g => {
          const isLive = g === 'liveTrading' || g === 'executionConsole';
          return (
            <View key={g} style={styles.featRow}>
              <Ionicons name="remove-circle-outline" size={14} color={isLive ? colors.sell : colors.textMuted} />
              <Text style={[
                styles.featText,
                {
                  color: isLive ? colors.textSecondary : colors.textMuted,
                  textDecorationLine: 'line-through',
                  fontWeight: isLive ? '700' : '400',
                },
              ]}>
                {CAPABILITY_LABELS[g] || g}
              </Text>
            </View>
          );
        })}
      </View>

      {/* TRADER-specific reinforcement disclaimer */}
      {code === 'TRADER' && (
        <View style={[styles.traderDisclaimer, { borderColor: colors.border, backgroundColor: colors.background }]}>
          <Ionicons name="information-circle-outline" size={13} color={colors.textMuted} />
          <Text style={[styles.traderDisclaimerText, { color: colors.textSecondary }]}>
            <Text style={{ fontWeight: '700' }}>TRADER unlocks paper trading only.</Text>
            {' '}Live capital access is never purchased automatically.
          </Text>
        </View>
      )}

      {/* CTA */}
      <View style={{ flex: 1 }} />
      <View style={styles.ctaSlot}>
        {isFree ? (
          <View style={[styles.ctaDisabled, { borderColor: colors.border }]}>
            <Text style={[styles.ctaDisabledText, { color: colors.textMuted }]}>
              {isCurrent ? 'You are on the free plan' : 'Default plan'}
            </Text>
          </View>
        ) : isCurrent ? (
          <View style={[styles.ctaDisabled, { borderColor: accent, backgroundColor: colors.surfaceHover }]}>
            <Ionicons name="checkmark-circle" size={14} color={accent} />
            <Text style={[styles.ctaDisabledText, { color: accent }]}>You are on this plan</Text>
          </View>
        ) : isPending ? (
          <View style={[styles.ctaPending, { backgroundColor: colors.background, borderColor: colors.border }]}>
            <Ionicons name="time-outline" size={14} color={colors.textSecondary} />
            <View style={{ flex: 1 }}>
              <Text style={[styles.ctaPendingTitle, { color: colors.textPrimary }]}>
                Invoice pending operator confirmation
              </Text>
              <Text style={[styles.ctaPendingSub, { color: colors.textMuted }]}>
                {pendingInvoice!.invoiceId}
              </Text>
            </View>
          </View>
        ) : (
          <TouchableOpacity
            onPress={onPurchase}
            disabled={purchasing !== null}
            style={[
              styles.cta,
              {
                backgroundColor: accent,
                borderColor: accent,
                opacity: purchasing !== null && purchasing !== code ? 0.5 : 1,
              },
            ]}
            testID={`upgrade-cta-${code}`}
          >
            {purchasing === code
              ? <ActivityIndicator color={colors.accentText} size="small" />
              : (
                <>
                  <Text style={[styles.ctaText, { color: colors.accentText }]}>Upgrade to {code}</Text>
                  <Ionicons name="arrow-forward" size={14} color={colors.accentText} />
                </>
              )}
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

// ── Purchase result modal ───────────────────────────────────────────

function PurchaseResultModal({
  visible, result, onClose,
}: {
  visible: boolean;
  result: { invoice: Invoice; deduplicated: boolean; paymentInstructions: any } | null;
  onClose: () => void;
}) {
  const colors = useColors();
  if (!result) return null;
  const { invoice, deduplicated, paymentInstructions } = result;
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={[styles.modalBackdrop, { backgroundColor: 'rgba(0,0,0,0.55)' }]}>
        <View style={[styles.modalCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <View style={styles.modalHead}>
            <Ionicons
              name={deduplicated ? 'time-outline' : 'receipt-outline'}
              size={22}
              color={colors.accent}
            />
            <Text style={[styles.modalTitle, { color: colors.textPrimary }]}>
              {deduplicated ? 'Invoice already pending' : 'Invoice created'}
            </Text>
          </View>
          <Text style={[styles.modalBody, { color: colors.textSecondary }]}>
            {deduplicated
              ? 'You already have a pending invoice for this product. We will not create a duplicate — wait for the existing one to be confirmed.'
              : 'Your purchase intent has been recorded. An operator will confirm activation manually. Entitlement is not active until confirmation.'}
          </Text>
          <View style={[styles.modalReceipt, { backgroundColor: colors.background, borderColor: colors.border }]}>
            <ReceiptRow label="Invoice"  value={invoice.invoiceId} mono colors={colors} />
            <ReceiptRow label="Product"  value={invoice.productCode} colors={colors} />
            <ReceiptRow label="Amount"   value={`$${invoice.priceUsd.toFixed(2)}`} mono colors={colors} />
            <ReceiptRow label="Status"   value={invoice.status.toUpperCase()} colors={colors} />
          </View>
          <View style={[styles.modalPayment, { borderColor: colors.border }]}>
            <Text style={[styles.modalPaymentLabel, { color: colors.textMuted }]}>
              PAYMENT
            </Text>
            <Text style={[styles.modalPaymentText, { color: colors.textSecondary }]}>
              {paymentInstructions?.message ||
                'Awaiting operator confirmation. Tier entitlement will be granted on confirmation.'}
            </Text>
          </View>
          <TouchableOpacity onPress={onClose} style={[styles.modalCta, { backgroundColor: colors.accent }]}>
            <Text style={[styles.modalCtaText, { color: colors.accentText }]}>Got it</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

function ReceiptRow({ label, value, mono, colors }: { label: string; value: string; mono?: boolean; colors: any }) {
  return (
    <View style={styles.receiptRow}>
      <Text style={[styles.receiptKey, { color: colors.textMuted }]}>{label}</Text>
      <Text style={[styles.receiptVal, { color: colors.textPrimary, fontFamily: mono ? 'monospace' : undefined }]} numberOfLines={1}>
        {value}
      </Text>
    </View>
  );
}

// ── Styles ─────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  scroll: { padding: 20, paddingBottom: 60, gap: 16 },
  topbar: { flexDirection: 'row', alignItems: 'center' },
  backBtn: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  backText: { fontSize: 14, fontWeight: '600' },

  h1: { fontSize: 28, fontWeight: '800', letterSpacing: -0.3 },
  sub: { fontSize: 14, lineHeight: 20, maxWidth: 680 },

  errBox: { borderLeftWidth: 3, padding: 10, borderRadius: 6 },

  currentCard: { borderWidth: 1, borderRadius: 12, padding: 16, gap: 8 },
  currentHead: { flexDirection: 'row', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' },
  currentLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 1.3 },
  currentTier: { fontSize: 20, fontWeight: '800', letterSpacing: 0.5 },
  currentSub: { fontSize: 11, lineHeight: 16 },
  currentChips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 4 },
  canChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4 },
  canChipText: { fontSize: 10, fontWeight: '700' },
  cannotChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4, borderWidth: 1 },
  cannotChipText: { fontSize: 10, fontWeight: '500' },

  loadingBox: { paddingVertical: 40, alignItems: 'center' },
  grid: { gap: 14, flexWrap: 'wrap' },
  planCard: {
    flex: 1, minWidth: 280, borderRadius: 14, borderWidth: 1, padding: 18, gap: 6,
    minHeight: 480,
  },
  planHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  planCode: { fontSize: 22, fontWeight: '800', letterSpacing: 1 },
  currentPill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4 },
  currentPillText: { fontSize: 9, fontWeight: '800', letterSpacing: 1 },
  planTitle: { fontSize: 13, fontWeight: '600' },
  planSub: { fontSize: 12, lineHeight: 16 },
  planPrice: { fontSize: 28, fontWeight: '800', fontFamily: 'monospace', marginTop: 10, marginBottom: 4 },
  planPriceSub: { fontSize: 12, fontWeight: '500', fontFamily: undefined },

  sectionLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2, marginTop: 8, marginBottom: 4 },
  featList: { gap: 4 },
  featRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 6 },
  featText: { fontSize: 12, flex: 1, lineHeight: 17 },

  traderDisclaimer: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 6,
    padding: 10, borderRadius: 6, borderWidth: 1, marginTop: 10,
  },
  traderDisclaimerText: { fontSize: 11, flex: 1, lineHeight: 15 },

  ctaSlot: { marginTop: 14 },
  cta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 12, borderRadius: 8, borderWidth: 1 },
  ctaText: { fontSize: 13, fontWeight: '700', letterSpacing: 0.3 },
  ctaDisabled: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 12, borderRadius: 8, borderWidth: 1 },
  ctaDisabledText: { fontSize: 12, fontWeight: '600' },
  ctaPending: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, padding: 10, borderRadius: 8, borderWidth: 1 },
  ctaPendingTitle: { fontSize: 12, fontWeight: '700' },
  ctaPendingSub: { fontSize: 10, fontFamily: 'monospace', marginTop: 2 },

  boundary: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 10,
    padding: 16, borderRadius: 12, borderWidth: 1,
  },
  boundaryTitle: { fontSize: 14, fontWeight: '800', marginBottom: 4 },
  boundaryText: { fontSize: 12, lineHeight: 18 },

  footnote: { fontSize: 11, fontStyle: 'italic', textAlign: 'center' },

  // modal
  modalBackdrop: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 22 },
  modalCard: { width: '100%', maxWidth: 480, borderWidth: 1, borderRadius: 14, padding: 20, gap: 10 },
  modalHead: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  modalTitle: { fontSize: 17, fontWeight: '800' },
  modalBody: { fontSize: 13, lineHeight: 18 },
  modalReceipt: { borderWidth: 1, borderRadius: 8, padding: 12, gap: 6 },
  receiptRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  receiptKey: { fontSize: 10, fontWeight: '700', letterSpacing: 1, width: 80 },
  receiptVal: { fontSize: 12, flex: 1 },
  modalPayment: { borderLeftWidth: 3, paddingLeft: 10, paddingVertical: 4 },
  modalPaymentLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2 },
  modalPaymentText: { fontSize: 12, marginTop: 4, lineHeight: 17 },
  modalCta: { paddingVertical: 12, borderRadius: 8, alignItems: 'center', marginTop: 4 },
  modalCtaText: { fontSize: 13, fontWeight: '700', letterSpacing: 0.3 },
});
