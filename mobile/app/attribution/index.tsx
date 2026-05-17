/**
 * Attribution Summary — Forensic layer (Sprint 5 P0.5).
 *
 * NOT a dashboard. NOT a runtime. Just three forensic sections:
 *   1. Exposure Suppression  — how many directional signals Meta-Brain killed
 *   2. Economic Effect       — realized avoided_loss / missed_gain / net_alpha
 *   3. Horizon Breakdown     — 1D vs 7D vs 30D verdict per horizon
 *
 * READ-ONLY. NO ORDERS. NO EXECUTION.
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import Constants from 'expo-constants';
import { useRouter } from 'expo-router';

import { t } from '../../src/core/i18n';
const API_URL =
  Constants.expoConfig?.extra?.apiUrl ||
  process.env.EXPO_PUBLIC_BACKEND_URL ||
  '';

const COLORS = {
  bg: '#0a0e1a',
  surface: '#0f1422',
  surfaceHi: '#162033',
  border: '#1d2940',
  text: '#e8ecf4',
  textDim: '#8b96a8',
  textFaint: '#5a657a',
  long: '#39d98a',
  short: '#ff5a5a',
  hold: '#7a8294',
  warn: '#f5a623',
  alert: '#e879f9',
  block: '#d0021b',
  accent: '#4da3ff',
};

type RealizedHeadline = {
  avoided_loss_pct: number;
  missed_gain_pct: number;
  net_alpha_pct: number;
  n_killed_to_hold: number;
  n_killed_loss_avoided: number;
  n_killed_gain_missed: number;
  verdict: 'META_NET_POSITIVE' | 'META_NET_NEGATIVE' | 'NEUTRAL';
  suppressed_shorts: { n: number; would_have_total: number;
    would_have_mean: number | null; win_rate_if_executed: number | null };
  suppressed_longs: { n: number; would_have_total: number;
    would_have_mean: number | null; win_rate_if_executed: number | null };
};

type RealizedResponse = {
  ok: boolean;
  n: number;
  stage_summary: {
    raw: { realized_pnl_total: number; directional_accuracy: number | null;
           sharpe_proxy: number | null; n_active: number; exposure: any };
    final: { realized_pnl_total: number; directional_accuracy: number | null;
             sharpe_proxy: number | null; n_active: number; exposure: any };
    meta: { realized_pnl_total: number; directional_accuracy: number | null;
            n_active: number; exposure: any };
  };
  headline: RealizedHeadline;
  attribution_breakdown: Record<string, number>;
  by_horizon: Record<string, {
    n: number;
    headline: RealizedHeadline;
    raw: { directional_accuracy: number | null; realized_pnl_total: number };
    final: { directional_accuracy: number | null; realized_pnl_total: number };
    exposure_suppression_rate: number | null;
  }>;
  by_asset: Record<string, {
    n: number; net_alpha_pct: number;
    verdict: string; final_pnl_total: number;
  }>;
};

function fmtPct(n: number | null | undefined, d = 2): string {
  if (n === null || n === undefined || isNaN(n)) return '—';
  const sign = n >= 0 ? '+' : '';
  return `${sign}${n.toFixed(d)}%`;
}
function verdictColor(v: string): string {
  if (v === 'META_NET_POSITIVE') return COLORS.long;
  if (v === 'META_NET_NEGATIVE') return COLORS.short;
  return COLORS.hold;
}
function verdictLabel(v: string): string {
  if (v === 'META_NET_POSITIVE') return 'PROTECTIVE';
  if (v === 'META_NET_NEGATIVE') return 'DESTRUCTIVE';
  return 'NEUTRAL';
}

export default function AttributionScreen() {
  const router = useRouter();
  const [data, setData] = useState<RealizedResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/mbrain/attribution/realized?limit=2000`);
      const j: RealizedResponse = await res.json();
      if (j?.ok) setData(j);
      else setError('Failed to load realized attribution');
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <SafeAreaView style={styles.root} edges={['top']}>
        <View style={styles.center}>
          <ActivityIndicator color={COLORS.accent} />
          <Text style={[styles.dim, { marginTop: 12 }]}>
            Computing realized attribution…
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  if (!data || data.n === 0) {
    return (
      <SafeAreaView style={styles.root} edges={['top']}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Ionicons name="chevron-back" size={20} color={COLORS.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>{t('app.realizedAttribution')}</Text>
        </View>
        <View style={styles.center}>
          <Ionicons name="time-outline" size={36} color={COLORS.textFaint} />
          <Text style={[styles.empty, { marginTop: 14 }]}>
            No resolved outcomes yet
          </Text>
          <Text style={[styles.dim, { textAlign: 'center', marginTop: 6,
                                       paddingHorizontal: 32 }]}>
            Forward-tracking outcomes need to mature (1D / 7D / 30D).
            Trigger M2B resolve from the Positions screen once horizons
            elapse.
          </Text>
          <TouchableOpacity
            style={[styles.linkBtn, { marginTop: 18 }]}
            onPress={() => router.push('/positions' as any)}
          >
            <Text style={styles.linkBtnText}>{t('app.openPositions')}</Text>
            <Ionicons name="chevron-forward" size={14} color={COLORS.accent} />
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const { headline, by_horizon, by_asset, attribution_breakdown,
          stage_summary } = data;
  const verdictCol = verdictColor(headline.verdict);

  const sortedHorizons = Object.entries(by_horizon)
    .sort((a, b) => a[0].localeCompare(b[0]));
  const sortedAssets = Object.entries(by_asset)
    .sort((a, b) => Math.abs(b[1].net_alpha_pct) - Math.abs(a[1].net_alpha_pct));

  // Compute exposure suppression numbers
  const totalRawDir =
    (stage_summary.raw?.exposure?.long || 0) +
    (stage_summary.raw?.exposure?.short || 0);
  const totalFinalDir =
    (stage_summary.final?.exposure?.long || 0) +
    (stage_summary.final?.exposure?.short || 0);
  const supressionPct = totalRawDir > 0
    ? Math.round((1 - totalFinalDir / totalRawDir) * 100)
    : 0;

  return (
    <SafeAreaView style={styles.root} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="chevron-back" size={20} color={COLORS.text} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>{t('app.realizedAttribution')}</Text>
          <Text style={styles.headerSub}>
            Forensic summary · {data.n} resolved outcomes
          </Text>
        </View>
        <TouchableOpacity
          onPress={() => router.push('/positions' as any)}
          style={styles.linkBtn}
        >
          <Text style={styles.linkBtnText}>Positions</Text>
          <Ionicons name="chevron-forward" size={14} color={COLORS.accent} />
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={{ paddingBottom: 60 }}
        refreshControl={<RefreshControl refreshing={refreshing}
          onRefresh={() => { setRefreshing(true); load(); }}
          tintColor={COLORS.accent} />}
      >
        {error && (
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}

        {/* TOP VERDICT CARD */}
        <View style={[styles.verdictCard,
          { backgroundColor: verdictCol + '14', borderColor: verdictCol }]}>
          <Text style={[styles.verdictTag, { color: verdictCol }]}>
            META {verdictLabel(headline.verdict)}
          </Text>
          <Text style={[styles.verdictValue, { color: verdictCol }]}>
            net alpha {fmtPct(headline.net_alpha_pct, 1)}
          </Text>
          <Text style={styles.verdictSub}>
            +{headline.avoided_loss_pct.toFixed(1)}% avoided ·{' '}
            −{headline.missed_gain_pct.toFixed(1)}% missed
          </Text>
        </View>

        {/* SECTION 1 — Exposure Suppression */}
        <Text style={styles.sectionTitle}>1 · Exposure Suppression</Text>
        <View style={styles.section}>
          <View style={styles.suppressionRow}>
            <View style={styles.suppCell}>
              <Text style={styles.suppNum}>{totalRawDir}</Text>
              <Text style={styles.suppLabel}>{t('app.rawDirectional')}</Text>
            </View>
            <Ionicons name="arrow-forward" size={16} color={COLORS.textFaint} />
            <View style={styles.suppCell}>
              <Text style={[styles.suppNum, { color: COLORS.warn }]}>
                {totalFinalDir}
              </Text>
              <Text style={styles.suppLabel}>{t('app.finalDirectional')}</Text>
            </View>
            <Ionicons name="arrow-forward" size={16} color={COLORS.textFaint} />
            <View style={styles.suppCell}>
              <Text style={[styles.suppNum, { color: COLORS.short }]}>
                {supressionPct}%
              </Text>
              <Text style={styles.suppLabel}>suppressed</Text>
            </View>
          </View>
          <Text style={styles.dimNote}>
            {headline.suppressed_shorts.n} shorts ·{' '}
            {headline.suppressed_longs.n} longs killed → HOLD
          </Text>
        </View>

        {/* SECTION 2 — Economic Effect */}
        <Text style={styles.sectionTitle}>2 · Economic Effect</Text>
        <View style={styles.section}>
          <View style={styles.econGrid}>
            <View style={[styles.econCell, { borderColor: COLORS.long }]}>
              <Text style={styles.econLabel}>{t('app.avoidedLoss')}</Text>
              <Text style={[styles.econNum, { color: COLORS.long }]}>
                +{headline.avoided_loss_pct.toFixed(2)}%
              </Text>
              <Text style={styles.econSub}>
                {headline.n_killed_loss_avoided} losers killed
              </Text>
            </View>
            <View style={[styles.econCell, { borderColor: COLORS.short }]}>
              <Text style={styles.econLabel}>{t('app.missedGain')}</Text>
              <Text style={[styles.econNum, { color: COLORS.short }]}>
                −{headline.missed_gain_pct.toFixed(2)}%
              </Text>
              <Text style={styles.econSub}>
                {headline.n_killed_gain_missed} winners killed
              </Text>
            </View>
          </View>
          <View style={[styles.econNetBox, { borderColor: verdictCol }]}>
            <Text style={[styles.econNetLabel, { color: verdictCol }]}>
              NET
            </Text>
            <Text style={[styles.econNetNum, { color: verdictCol }]}>
              {fmtPct(headline.net_alpha_pct, 2)}
            </Text>
            <Text style={styles.econNetSub}>
              {headline.verdict === 'META_NET_POSITIVE'
                ? 'opportunity preservation'
                : headline.verdict === 'META_NET_NEGATIVE'
                ? 'opportunity destruction'
                : 'no net effect'}
            </Text>
          </View>

          {/* Attribution breakdown */}
          <View style={styles.breakdownGrid}>
            {Object.entries(attribution_breakdown)
              .sort((a, b) => b[1] - a[1])
              .map(([cls, n]) => {
                const tone = cls.includes('avoid') || cls.includes('correct')
                  ? COLORS.long
                  : cls.includes('miss') || cls.includes('wrong')
                  ? COLORS.short
                  : COLORS.hold;
                return (
                  <View key={cls} style={[styles.breakdownChip,
                    { borderColor: tone + '88' }]}>
                    <Text style={[styles.breakdownNum, { color: tone }]}>
                      {n}
                    </Text>
                    <Text style={styles.breakdownLabel}>
                      {cls.replace(/_/g, ' ').toUpperCase()}
                    </Text>
                  </View>
                );
              })}
          </View>
        </View>

        {/* SECTION 3 — Horizon Breakdown */}
        <Text style={styles.sectionTitle}>3 · Horizon Breakdown</Text>
        <View style={styles.section}>
          {sortedHorizons.map(([h, hd]) => {
            const c = verdictColor(hd.headline.verdict);
            return (
              <View key={h} style={[styles.horizonRow, { borderColor: c + '44' }]}>
                <View style={styles.horizonRowLeft}>
                  <Text style={styles.horizonRowLabel}>{h}</Text>
                  <Text style={[styles.horizonRowVerdict, { color: c }]}>
                    {verdictLabel(hd.headline.verdict)}
                  </Text>
                </View>
                <View style={styles.horizonRowMid}>
                  <Text style={[styles.horizonRowNet, { color: c }]}>
                    {fmtPct(hd.headline.net_alpha_pct, 1)}
                  </Text>
                  <Text style={styles.horizonRowSub}>
                    n={hd.n} · suppress{' '}
                    {hd.exposure_suppression_rate !== null
                      ? `${(hd.exposure_suppression_rate * 100).toFixed(0)}%`
                      : '—'}
                  </Text>
                </View>
                <View style={styles.horizonRowRight}>
                  <Text style={styles.horizonRowDetail}>
                    avoid +{hd.headline.avoided_loss_pct.toFixed(1)}%
                  </Text>
                  <Text style={[styles.horizonRowDetail,
                    { color: COLORS.short }]}>
                    miss −{hd.headline.missed_gain_pct.toFixed(1)}%
                  </Text>
                </View>
              </View>
            );
          })}
        </View>

        {/* By asset (compact) */}
        {sortedAssets.length > 0 && (
          <>
            <Text style={styles.sectionTitle}>4 · By Asset</Text>
            <View style={styles.section}>
              {sortedAssets.slice(0, 12).map(([a, ad]) => (
                <TouchableOpacity
                  key={a}
                  style={styles.assetRow}
                  onPress={() => router.push(
                    `/positions?symbol=${encodeURIComponent(a)}` as any
                  )}
                  activeOpacity={0.75}
                >
                  <Text style={styles.assetSym}>{a}</Text>
                  <Text style={[styles.assetNet,
                    { color: verdictColor(ad.verdict) }]}>
                    {fmtPct(ad.net_alpha_pct, 1)}
                  </Text>
                  <Text style={styles.assetN}>n={ad.n}</Text>
                  <Ionicons name="chevron-forward" size={14}
                            color={COLORS.textFaint} />
                </TouchableOpacity>
              ))}
            </View>
          </>
        )}

        <Text style={styles.disclaimer}>
          Read-only forensic summary over RESOLVED forward-tracking outcomes.{'\n'}
          NO ORDERS. NO EXECUTION. NO COMMITS. NO trading_os WRITES.{'\n'}
          Net alpha = avoided_loss − missed_gain over Meta-Brain HOLD-conversions.{'\n'}
          1D may be protective while 30D destructive — DO NOT patch policy
          on a single horizon.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.bg },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  dim: { color: COLORS.textDim, fontSize: 12 },
  empty: { color: COLORS.text, fontSize: 16, fontWeight: '700' },

  header: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 12, paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: COLORS.border, gap: 6,
  },
  backBtn: { width: 32, height: 32, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { color: COLORS.text, fontSize: 18, fontWeight: '800' },
  headerSub: { color: COLORS.textDim, fontSize: 11, marginTop: 2 },
  linkBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 10, paddingVertical: 8,
    borderWidth: 1, borderColor: COLORS.accent, borderRadius: 999,
  },
  linkBtnText: { color: COLORS.accent, fontSize: 12, fontWeight: '700' },

  errorBox: {
    backgroundColor: COLORS.warn + '11', padding: 10, borderRadius: 8,
    margin: 12, borderWidth: 1, borderColor: COLORS.warn + '33',
  },
  errorText: { color: COLORS.warn, fontSize: 12 },

  verdictCard: {
    margin: 12, padding: 18, borderRadius: 14, borderWidth: 1,
    alignItems: 'center',
  },
  verdictTag: { fontSize: 11, fontWeight: '900', letterSpacing: 1.2 },
  verdictValue: { fontSize: 30, fontWeight: '900', marginTop: 6 },
  verdictSub: { color: COLORS.textDim, fontSize: 11, marginTop: 6 },

  sectionTitle: {
    color: COLORS.textDim, fontSize: 11, fontWeight: '800',
    letterSpacing: 1.2, paddingHorizontal: 16, paddingTop: 18, paddingBottom: 6,
    textTransform: 'uppercase',
  },
  section: {
    backgroundColor: COLORS.surface, marginHorizontal: 12,
    borderRadius: 12, padding: 14,
    borderWidth: StyleSheet.hairlineWidth, borderColor: COLORS.border,
  },

  suppressionRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around',
    paddingVertical: 6,
  },
  suppCell: { alignItems: 'center' },
  suppNum: { color: COLORS.text, fontSize: 22, fontWeight: '900' },
  suppLabel: { color: COLORS.textFaint, fontSize: 10, marginTop: 2,
               letterSpacing: 0.5 },
  dimNote: { color: COLORS.textFaint, fontSize: 10, textAlign: 'center',
             marginTop: 10 },

  econGrid: { flexDirection: 'row', gap: 8 },
  econCell: {
    flex: 1, backgroundColor: COLORS.bg, borderRadius: 10,
    padding: 12, borderWidth: 1, alignItems: 'center',
  },
  econLabel: { color: COLORS.textFaint, fontSize: 9, fontWeight: '800',
               letterSpacing: 0.5 },
  econNum: { fontSize: 22, fontWeight: '900', marginTop: 4 },
  econSub: { color: COLORS.textFaint, fontSize: 10, marginTop: 2 },
  econNetBox: {
    marginTop: 10, padding: 12, borderRadius: 10, borderWidth: 1,
    alignItems: 'center', backgroundColor: COLORS.bg,
  },
  econNetLabel: { fontSize: 10, fontWeight: '900', letterSpacing: 1 },
  econNetNum: { fontSize: 28, fontWeight: '900', marginVertical: 2 },
  econNetSub: { color: COLORS.textFaint, fontSize: 11 },

  breakdownGrid: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 14,
  },
  breakdownChip: {
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8,
    borderWidth: 1, alignItems: 'center', minWidth: 84,
  },
  breakdownNum: { fontSize: 16, fontWeight: '900' },
  breakdownLabel: { color: COLORS.textFaint, fontSize: 8.5, fontWeight: '700',
                    letterSpacing: 0.4 },

  horizonRow: {
    flexDirection: 'row', alignItems: 'center',
    paddingVertical: 12, gap: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  horizonRowLeft: { width: 90 },
  horizonRowLabel: { color: COLORS.text, fontSize: 14, fontWeight: '900' },
  horizonRowVerdict: { fontSize: 9, fontWeight: '800',
                       letterSpacing: 0.5, marginTop: 2 },
  horizonRowMid: { flex: 1 },
  horizonRowNet: { fontSize: 18, fontWeight: '900' },
  horizonRowSub: { color: COLORS.textFaint, fontSize: 10, marginTop: 2 },
  horizonRowRight: { alignItems: 'flex-end' },
  horizonRowDetail: { color: COLORS.long, fontSize: 11, fontWeight: '700' },

  assetRow: {
    flexDirection: 'row', alignItems: 'center',
    paddingVertical: 10, gap: 12,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: COLORS.border,
  },
  assetSym: { color: COLORS.text, fontSize: 13, fontWeight: '700', width: 100 },
  assetNet: { fontSize: 14, fontWeight: '900', flex: 1 },
  assetN: { color: COLORS.textFaint, fontSize: 11 },

  disclaimer: {
    color: COLORS.textFaint, fontSize: 10,
    paddingHorizontal: 16, paddingTop: 24, lineHeight: 14,
  },
});
