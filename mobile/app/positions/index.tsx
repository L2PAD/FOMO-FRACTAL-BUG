/**
 * Position Runtime — Expo Trading Runtime v1 — paper-only.
 *
 * Three parallel universes:
 *   RAW    — what would happen if we acted on raw model directions
 *   META   — what happens after Rules + Meta-Brain
 *   FINAL  — what happens after the full pipeline (current behavior)
 *
 * Adds:
 *   • Timeline Replay Card  — narrative storylines (RAW → META → move → end).
 *   • Inline chips per row  — SUPPRESSED / FLIPPED / DOWNGRADED / WIN / LOSS /
 *                              LOSS_AVOIDED / GAIN_MISSED.
 *   • Bidirectional links to Verdict Inspector (?symbol=&h=).
 *   • Manual M2B resolve trigger (does NOT activate live execution).
 *
 * READ-ONLY. NO ORDERS. NO EXECUTION. NO LIVE. NO COMMITS.
 */
import React, { useEffect, useMemo, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import Constants from 'expo-constants';
import { useRouter, useLocalSearchParams } from 'expo-router';

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
  positive: '#39d98a',
  negative: '#ff5a5a',
  accent: '#4da3ff',
  good: '#39d98a',
  info: '#8b96a8',
};

type ChipTone = 'good' | 'warn' | 'block' | 'alert' | 'info';
type Chip = { type: string; label: string; tone: ChipTone };

type Narrative = {
  symbol: string;
  horizon: string;
  ts: string;
  raw: string;
  final: string;
  move_pct: number;
  end_label: string;
  end_tone: ChipTone;
  raw_pnl_pct: number;
  final_pnl_pct: number;
  realized?: boolean;
};

type Position = {
  symbol: string;
  horizon: string;
  ts: string;
  direction: 'LONG' | 'SHORT' | 'HOLD';
  entry: number | null;
  close: number | null;
  pnl: number | null;
  price_move_pct?: number;
  raw_dir?: string;
  meta_dir?: string;
  final_dir?: string;
  raw_pnl?: number | null;
  final_pnl?: number | null;
  raw_expected_return?: number | null;
  outcome_class?: string;
  regime?: string | null;
  modelId?: string | null;
  missing_price?: boolean;
  chips?: Chip[];
};

type PortfolioSummary = {
  label: string;
  n: number;
  n_active: number;
  exposure: { long: number; short: number; hold: number };
  unrealized_pnl_total: number;
  unrealized_pnl_mean: number;
  active_pnl_total: number;
  active_pnl_mean: number | null;
  win_rate: number | null;
  sharpe_proxy: number | null;
  hold_count: number;
  positions: Position[];
};

type ParallelResponse = {
  ok: boolean;
  n: number;
  portfolios: { raw: PortfolioSummary; meta: PortfolioSummary; final: PortfolioSummary };
  headline: {
    suppressed_alpha_pct: number;
    meta_brain_pnl_delta_pct: number;
    directional_trades_killed_to_hold: number;
    directional_trades_flipped: number;
    n_total: number;
    n_priced: number;
  };
  narratives?: Narrative[];
  by_symbol: Record<string, {
    n: number; raw_pnl: number; meta_pnl: number; final_pnl: number;
    current_price: number | null;
  }>;
};

type AttributionResponse = {
  ok: boolean;
  n: number;
  n_priced: number;
  n_resolved: number;
  n_pending: number;
  headline: {
    avoided_loss_pct: number;
    missed_gain_pct: number;
    net_alpha_pct: number;
    n_killed_to_hold: number;
    n_killed_loss_avoided: number;
    n_killed_gain_missed: number;
    verdict: 'META_NET_POSITIVE' | 'META_NET_NEGATIVE' | 'NEUTRAL';
  };
  suppressed_shorts: { label: string; n: number; would_have_pnl_total: number;
                       would_have_pnl_mean: number | null;
                       win_rate_if_executed: number | null };
  suppressed_longs: { label: string; n: number; would_have_pnl_total: number;
                      would_have_pnl_mean: number | null;
                      win_rate_if_executed: number | null };
  meta?: { include_resolved: boolean; data_window: string };
};

type RealizedHeadline = {
  avoided_loss_pct: number;
  missed_gain_pct: number;
  net_alpha_pct: number;
  n_killed_to_hold: number;
  n_killed_loss_avoided: number;
  n_killed_gain_missed: number;
  verdict: 'META_NET_POSITIVE' | 'META_NET_NEGATIVE' | 'NEUTRAL';
  suppressed_shorts: {
    n: number; would_have_total: number;
    would_have_mean: number | null; win_rate_if_executed: number | null;
  };
  suppressed_longs: {
    n: number; would_have_total: number;
    would_have_mean: number | null; win_rate_if_executed: number | null;
  };
};

type RealizedResponse = {
  ok: boolean;
  n: number;
  filter?: { horizon?: string };
  stage_summary: {
    raw: { realized_pnl_total: number; directional_accuracy: number | null;
           sharpe_proxy: number | null; n_active: number };
    meta: any;
    final: { realized_pnl_total: number; directional_accuracy: number | null;
             sharpe_proxy: number | null; n_active: number };
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
    n: number; net_alpha_pct: number; verdict: string; final_pnl_total: number;
  }>;
};

// ─── helpers ────────────────────────────────────────────────────────
function fmtPct(n: number | null | undefined, decimals = 2): string {
  if (n === null || n === undefined || isNaN(n)) return '—';
  const sign = n >= 0 ? '+' : '';
  return `${sign}${(n * 100).toFixed(decimals)}%`;
}
function fmtPctRaw(n: number | null | undefined, decimals = 2): string {
  if (n === null || n === undefined || isNaN(n)) return '—';
  const sign = n >= 0 ? '+' : '';
  return `${sign}${(n).toFixed(decimals)}%`;
}
function fmtNum(n: number | null | undefined, decimals = 2): string {
  if (n === null || n === undefined || isNaN(n)) return '—';
  return n.toFixed(decimals);
}
function dirColor(d: string): string {
  if (d === 'LONG') return COLORS.long;
  if (d === 'SHORT') return COLORS.short;
  return COLORS.hold;
}
function pnlColor(n: number | null | undefined): string {
  if (n === null || n === undefined) return COLORS.textDim;
  return n > 0 ? COLORS.positive : n < 0 ? COLORS.negative : COLORS.textDim;
}
function chipColor(tone: ChipTone): string {
  if (tone === 'good') return COLORS.good;
  if (tone === 'block') return COLORS.block;
  if (tone === 'warn') return COLORS.warn;
  if (tone === 'alert') return COLORS.alert;
  return COLORS.info;
}

// ─── small components ───────────────────────────────────────────────
function ChipPill({ chip }: { chip: Chip }) {
  const c = chipColor(chip.tone);
  return (
    <View style={[styles.chip, { borderColor: c + '88', backgroundColor: c + '14' }]}>
      <Text style={[styles.chipText, { color: c }]} numberOfLines={1}>
        {chip.label}
      </Text>
    </View>
  );
}

function PortfolioCard({ p, active, onPress }:
  { p: PortfolioSummary; active: boolean; onPress: () => void }) {
  const pnl = p.active_pnl_total;
  return (
    <TouchableOpacity
      style={[styles.universeCard,
              active && { borderColor: COLORS.accent, backgroundColor: COLORS.surfaceHi }]}
      onPress={onPress} activeOpacity={0.85}
      testID={`portfolio-${p.label.toLowerCase()}`}
    >
      <Text style={styles.universeLabel}>{p.label}</Text>
      <Text style={[styles.universePnl, { color: pnlColor(pnl) }]}>
        {fmtPct(pnl, 2)}
      </Text>
      <View style={styles.universeMeta}>
        <Text style={styles.universeMetaText}>
          {p.n_active}/{p.n} active
        </Text>
        <Text style={styles.universeMetaText}>
          win {p.win_rate !== null ? `${(p.win_rate * 100).toFixed(0)}%` : '—'}
        </Text>
      </View>
    </TouchableOpacity>
  );
}

function PositionRow({ pos, onPress }:
  { pos: Position; onPress: () => void }) {
  const dirCol = dirColor(pos.direction);
  const chips = pos.chips || [];
  return (
    <TouchableOpacity
      style={styles.posRow}
      activeOpacity={0.75}
      onPress={onPress}
      testID={`pos-row-${pos.symbol}-${pos.horizon}`}
    >
      <View style={styles.posTop}>
        <View style={{ flex: 1 }}>
          <Text style={styles.posSym}>
            {pos.symbol}{'  '}
            <Text style={styles.posSub}>{pos.horizon}</Text>
          </Text>
          <Text style={styles.posSubLine}>
            entry {fmtNum(pos.entry, 2)}  →  {fmtNum(pos.close, 2)}
            {pos.price_move_pct !== undefined ?
              `  (${fmtPct(pos.price_move_pct, 2)})` : ''}
          </Text>
        </View>
        <View style={[styles.dirCol]}>
          <View style={[styles.dirBadge, { borderColor: dirCol,
                                           backgroundColor: dirCol + '22' }]}>
            <Text style={[styles.dirBadgeText, { color: dirCol }]}>
              {pos.direction}
            </Text>
          </View>
        </View>
        <View style={{ width: 80, alignItems: 'flex-end' }}>
          <Text style={[styles.posPnl, { color: pnlColor(pos.pnl) }]}>
            {pos.pnl === null ? '—' : fmtPct(pos.pnl, 2)}
          </Text>
        </View>
      </View>
      {chips.length > 0 && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chipsRow}
          style={{ marginTop: 6 }}
        >
          {chips.map((c, i) => (
            <ChipPill key={`${pos.symbol}-${pos.horizon}-c${i}`} chip={c} />
          ))}
        </ScrollView>
      )}
    </TouchableOpacity>
  );
}

function NarrativeCard({ n, onPress }: { n: Narrative; onPress: () => void }) {
  const tone = chipColor(n.end_tone);
  const moveCol = n.move_pct >= 0 ? COLORS.long : COLORS.short;
  return (
    <TouchableOpacity
      style={[styles.narrativeCard, { borderColor: tone + '88' }]}
      activeOpacity={0.8}
      onPress={onPress}
      testID={`narrative-${n.symbol}-${n.horizon}`}
    >
      <View style={styles.narrativeHeader}>
        <Text style={styles.narrativeSym}>{n.symbol}</Text>
        <Text style={styles.narrativeHorizon}>{n.horizon}</Text>
        {n.realized ? (
          <View style={styles.realizedTagSm}>
            <Text style={styles.realizedTagSmText}>R</Text>
          </View>
        ) : null}
        <View style={{ flex: 1 }} />
        <Ionicons name="chevron-forward" size={14} color={COLORS.textDim} />
      </View>
      <View style={styles.narrativeFlow}>
        <Text style={styles.narrativeStep}>{n.raw}</Text>
        <Text style={styles.narrativeArrow}>↓</Text>
        <Text style={[styles.narrativeStep,
          { color: n.final.includes('HOLD') ? COLORS.warn : COLORS.text }]}>
          {n.final}
        </Text>
        <Text style={styles.narrativeArrow}>↓</Text>
        <Text style={[styles.narrativeMove, { color: moveCol }]}>
          {n.symbol.replace('USDT', '')} moved {fmtPctRaw(n.move_pct, 2)}
        </Text>
        <Text style={styles.narrativeArrow}>↓</Text>
        <Text style={[styles.narrativeEnd, { color: tone }]}>
          {n.end_label}
        </Text>
      </View>
    </TouchableOpacity>
  );
}

// ─── main screen ────────────────────────────────────────────────────
export default function PositionsScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ symbol?: string; h?: string }>();
  const symbolFilter = (params.symbol || '').toString().toUpperCase();
  const horizonFilter = (params.h || '').toString().toUpperCase();

  const [data, setData] = useState<ParallelResponse | null>(null);
  const [attribution, setAttribution] = useState<AttributionResponse | null>(null);
  const [realized, setRealized] = useState<RealizedResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<'raw' | 'meta' | 'final'>('final');
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchAll = useCallback(async () => {
    setError(null);
    try {
      const [resPar, resAttr, resRealized] = await Promise.all([
        fetch(`${API_URL}/api/mbrain/positions/parallel?limit=400&include_resolved=true`),
        fetch(`${API_URL}/api/mbrain/positions/attribution?include_resolved=true&limit=500`),
        fetch(`${API_URL}/api/mbrain/attribution/realized?limit=2000`),
      ]);
      const par: ParallelResponse = await resPar.json();
      const attr: AttributionResponse = await resAttr.json();
      const real: RealizedResponse = await resRealized.json();
      if (par?.ok) setData(par); else setError('Failed to load portfolios');
      if (attr?.ok) setAttribution(attr);
      if (real?.ok) setRealized(real);
      setLastUpdate(new Date());
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const triggerResolve = useCallback(() => {
    if (resolving) return;
    Alert.alert(
      'Trigger M2B resolve?',
      'Manually resolve realized asymmetry on outcomes that have matured (1D/7D/30D). Read-only — no orders, no execution. Continues paper-snapshot mode.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Resolve now',
          onPress: async () => {
            setResolving(true);
            try {
              const res = await fetch(
                `${API_URL}/api/mbrain/integrity/asymmetry/resolve?only_ready=true`,
                { method: 'POST' });
              const j = await res.json();
              if (j?.ok) {
                Alert.alert('Resolve complete',
                  `Resolved ${j.n_resolved ?? 0} outcomes; ${j.n_skipped ?? 0} not yet matured.`);
                await fetchAll();
              } else {
                Alert.alert('Resolve failed', j?.error || 'Unknown error');
              }
            } catch (e: any) {
              Alert.alert('Resolve error', String(e?.message || e));
            } finally {
              setResolving(false);
            }
          },
        },
      ],
    );
  }, [resolving, fetchAll]);

  // Derived: filter positions by query symbol/horizon if present
  const filteredPortfolio = useMemo(() => {
    if (!data) return null;
    const portfolio = data.portfolios[tab];
    if (!symbolFilter && !horizonFilter) return portfolio;
    return {
      ...portfolio,
      positions: portfolio.positions.filter((p) => {
        const symMatch = !symbolFilter ||
          p.symbol.toUpperCase().includes(symbolFilter);
        const hMatch = !horizonFilter ||
          p.horizon.toUpperCase() === horizonFilter;
        return symMatch && hMatch;
      }),
    };
  }, [data, tab, symbolFilter, horizonFilter]);

  const filteredNarratives = useMemo(() => {
    if (!data?.narratives) return [];
    if (!symbolFilter && !horizonFilter) return data.narratives;
    return data.narratives.filter((n) => {
      const symMatch = !symbolFilter ||
        n.symbol.toUpperCase().includes(symbolFilter);
      const hMatch = !horizonFilter ||
        n.horizon.toUpperCase() === horizonFilter;
      return symMatch && hMatch;
    });
  }, [data, symbolFilter, horizonFilter]);

  if (loading) {
    return (
      <SafeAreaView style={styles.root} edges={['top']}>
        <View style={styles.center}>
          <ActivityIndicator color={COLORS.accent} />
          <Text style={[styles.dim, { marginTop: 12 }]}>
            Computing parallel portfolios…
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  const headline = data?.headline;

  const goToVerdict = (sym: string, h: string) => {
    router.push(`/verdicts?symbol=${encodeURIComponent(sym)}&h=${encodeURIComponent(h)}` as any);
  };

  return (
    <SafeAreaView style={styles.root} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}
                          testID="positions-back">
          <Ionicons name="chevron-back" size={20} color={COLORS.text} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>{t('app.positionsRuntime')}</Text>
          <Text style={styles.headerSub}>
            paper-only · {data?.n || 0} hypothetical positions
            {symbolFilter ? `  ·  ${symbolFilter}` : ''}
            {horizonFilter ? `  ·  ${horizonFilter}` : ''}
          </Text>
        </View>
        <TouchableOpacity onPress={triggerResolve}
                          disabled={resolving}
                          style={[styles.resolveBtn, resolving && { opacity: 0.5 }]}
                          testID="positions-resolve-btn">
          {resolving ? (
            <ActivityIndicator color={COLORS.warn} size="small" />
          ) : (
            <>
              <Ionicons name="time-outline" size={14} color={COLORS.warn} />
              <Text style={styles.resolveBtnText}>M2B</Text>
            </>
          )}
        </TouchableOpacity>
        <TouchableOpacity
          onPress={() => router.push('/attribution' as any)}
          style={styles.linkBtn} testID="positions-to-attribution">
          <Ionicons name="analytics-outline" size={12} color={COLORS.accent} />
          <Text style={styles.linkBtnText}>Attr</Text>
        </TouchableOpacity>
        <TouchableOpacity
          onPress={() => router.push(
            `/verdicts${symbolFilter || horizonFilter
              ? `?symbol=${encodeURIComponent(symbolFilter)}&h=${encodeURIComponent(horizonFilter)}`
              : ''}` as any
          )}
          style={styles.linkBtn} testID="positions-to-verdicts">
          <Text style={styles.linkBtnText}>Verdicts</Text>
          <Ionicons name="chevron-forward" size={14} color={COLORS.accent} />
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={{ paddingBottom: 60 }}
        refreshControl={<RefreshControl refreshing={refreshing}
          onRefresh={() => { setRefreshing(true); fetchAll(); }}
          tintColor={COLORS.accent} />}
      >
        {error && (
          <View style={styles.errorBox}>
            <Ionicons name="alert-circle" size={16} color={COLORS.warn} />
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}

        {/* REALIZED ATTRIBUTION (priority) — shown when resolved outcomes exist */}
        {realized && realized.n > 0 && (
          <View style={styles.attrSection} testID="realized-overlay">
            <View style={[styles.attrVerdict, {
              backgroundColor: (realized.headline.verdict === 'META_NET_POSITIVE'
                ? COLORS.long : realized.headline.verdict === 'META_NET_NEGATIVE'
                ? COLORS.short : COLORS.hold) + '14',
              borderColor: realized.headline.verdict === 'META_NET_POSITIVE'
                ? COLORS.long : realized.headline.verdict === 'META_NET_NEGATIVE'
                ? COLORS.short : COLORS.hold,
            }]}>
              <Text style={styles.realizedTag}>REALIZED · {realized.n} resolved outcomes</Text>
              <Text style={[styles.attrVerdictLabel, {
                color: realized.headline.verdict === 'META_NET_POSITIVE'
                  ? COLORS.long : realized.headline.verdict === 'META_NET_NEGATIVE'
                  ? COLORS.short : COLORS.hold,
              }]}>
                META {realized.headline.verdict.replace('META_NET_', '')}
              </Text>
              <Text style={[styles.attrNetAlpha, {
                color: realized.headline.net_alpha_pct >= 0 ? COLORS.long : COLORS.short,
              }]}>
                net alpha {fmtPctRaw(realized.headline.net_alpha_pct, 1)}
              </Text>
              <Text style={styles.realizedNarrative}>
                {realized.headline.verdict === 'META_NET_POSITIVE'
                  ? `META prevented ${realized.headline.avoided_loss_pct.toFixed(1)}% downside`
                  : realized.headline.verdict === 'META_NET_NEGATIVE'
                  ? `META destroyed ${Math.abs(realized.headline.net_alpha_pct).toFixed(1)}% alpha`
                  : 'No net economic impact yet'}
                {realized.headline.missed_gain_pct > 0.05
                  ? ` but missed ${realized.headline.missed_gain_pct.toFixed(1)}% upside`
                  : ''}
              </Text>
            </View>
            <View style={styles.attrGrid}>
              <View style={[styles.attrCell, { borderColor: COLORS.long + '44' }]}>
                <Text style={styles.attrCellLabel}>{t('app.avoidedLoss')}</Text>
                <Text style={[styles.attrCellNum, { color: COLORS.long }]}>
                  +{fmtNum(realized.headline.avoided_loss_pct, 2)}%
                </Text>
                <Text style={styles.attrCellSub}>
                  {realized.headline.n_killed_loss_avoided} losers killed
                </Text>
              </View>
              <View style={[styles.attrCell, { borderColor: COLORS.short + '44' }]}>
                <Text style={styles.attrCellLabel}>{t('app.missedGain')}</Text>
                <Text style={[styles.attrCellNum, { color: COLORS.short }]}>
                  −{fmtNum(realized.headline.missed_gain_pct, 2)}%
                </Text>
                <Text style={styles.attrCellSub}>
                  {realized.headline.n_killed_gain_missed} winners killed
                </Text>
              </View>
            </View>

            {/* Horizon breakdown */}
            {Object.keys(realized.by_horizon || {}).length > 0 && (
              <View style={styles.horizonGrid}>
                {Object.entries(realized.by_horizon)
                  .sort((a, b) => a[0].localeCompare(b[0]))
                  .map(([h, hd]) => {
                    const v = hd.headline.verdict;
                    const c = v === 'META_NET_POSITIVE' ? COLORS.long
                      : v === 'META_NET_NEGATIVE' ? COLORS.short : COLORS.hold;
                    return (
                      <View key={h} style={[styles.horizonCell, { borderColor: c + '44' }]}>
                        <Text style={styles.horizonLabel}>{h}</Text>
                        <Text style={[styles.horizonNum, { color: c }]}>
                          {fmtPctRaw(hd.headline.net_alpha_pct, 1)}
                        </Text>
                        <Text style={styles.horizonSub}>
                          {v === 'META_NET_POSITIVE' ? 'protective'
                            : v === 'META_NET_NEGATIVE' ? 'destructive' : 'neutral'}
                        </Text>
                        <Text style={styles.horizonSub}>
                          n={hd.n} · sup{hd.exposure_suppression_rate !== null
                            ? `·${(hd.exposure_suppression_rate * 100).toFixed(0)}%` : ''}
                        </Text>
                      </View>
                    );
                  })}
              </View>
            )}
          </View>
        )}

        {/* PAPER attribution (fallback) — shown when no resolved data */}
        {(!realized || realized.n === 0) && attribution && attribution.headline && (
          <View style={styles.attrSection} testID="attribution-overlay">
            <View style={[styles.attrVerdict, {
              backgroundColor: (attribution.headline.verdict === 'META_NET_POSITIVE'
                ? COLORS.long : COLORS.short) + '14',
              borderColor: attribution.headline.verdict === 'META_NET_POSITIVE'
                ? COLORS.long : COLORS.short,
            }]}>
              <Text style={[styles.attrVerdictLabel, {
                color: attribution.headline.verdict === 'META_NET_POSITIVE'
                  ? COLORS.long : COLORS.short,
              }]}>
                META-BRAIN {attribution.headline.verdict.replace('META_NET_', '')}
              </Text>
              <Text style={[styles.attrNetAlpha, {
                color: attribution.headline.net_alpha_pct >= 0 ? COLORS.long : COLORS.short,
              }]}>
                net alpha {fmtPctRaw(attribution.headline.net_alpha_pct, 1)}
              </Text>
              <Text style={styles.attrSubLabel}>
                {attribution.meta?.data_window === 'realized' ? 'realized' : 'paper · 24h snapshot'}
                {' · '}n={attribution.n_priced}/{attribution.n}
              </Text>
            </View>
            <View style={styles.attrGrid}>
              <View style={[styles.attrCell, { borderColor: COLORS.long + '44' }]}>
                <Text style={styles.attrCellLabel}>{t('app.avoidedLoss')}</Text>
                <Text style={[styles.attrCellNum, { color: COLORS.long }]}>
                  +{fmtNum(attribution.headline.avoided_loss_pct, 2)}%
                </Text>
                <Text style={styles.attrCellSub}>
                  {attribution.headline.n_killed_loss_avoided} killed losers
                </Text>
              </View>
              <View style={[styles.attrCell, { borderColor: COLORS.short + '44' }]}>
                <Text style={styles.attrCellLabel}>{t('app.missedGain')}</Text>
                <Text style={[styles.attrCellNum, { color: COLORS.short }]}>
                  −{fmtNum(attribution.headline.missed_gain_pct, 2)}%
                </Text>
                <Text style={styles.attrCellSub}>
                  {attribution.headline.n_killed_gain_missed} killed winners
                </Text>
              </View>
            </View>
          </View>
        )}

        {/* TIMELINE REPLAY CARDS */}
        {filteredNarratives.length > 0 && (
          <View style={styles.timelineSection}>
            <View style={styles.timelineHeaderRow}>
              <Text style={styles.sectionTitle}>{t('app.timelineReplayTopStories')}</Text>
              <Text style={styles.timelineHint}>tap → verdict</Text>
            </View>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={{ paddingHorizontal: 12, paddingBottom: 4 }}
            >
              {filteredNarratives.slice(0, 8).map((n, i) => (
                <NarrativeCard
                  key={`${n.symbol}-${n.horizon}-${i}`}
                  n={n}
                  onPress={() => goToVerdict(n.symbol, n.horizon)}
                />
              ))}
            </ScrollView>
          </View>
        )}

        {/* HEADLINE row */}
        {headline && (
          <View style={styles.headlineSection}>
            <Text style={styles.sectionTitle}>{t('app.parallelUniverseHeadline')}</Text>
            <View style={styles.headlineGrid}>
              <View style={styles.headlineCell}>
                <Text style={styles.headlineLabel}>{t('app.suppressedAlpha')}</Text>
                <Text style={[styles.headlineNumber,
                  { color: pnlColor(headline.suppressed_alpha_pct) }]}>
                  {fmtPctRaw(headline.suppressed_alpha_pct, 2)}
                </Text>
                <Text style={styles.headlineSub}>RAW − FINAL</Text>
              </View>
              <View style={styles.headlineCell}>
                <Text style={styles.headlineLabel}>META-BRAIN Δ</Text>
                <Text style={[styles.headlineNumber,
                  { color: pnlColor(headline.meta_brain_pnl_delta_pct) }]}>
                  {fmtPctRaw(headline.meta_brain_pnl_delta_pct, 2)}
                </Text>
                <Text style={styles.headlineSub}>FINAL − META</Text>
              </View>
            </View>
            <View style={styles.headlineGrid}>
              <View style={styles.headlineCell}>
                <Text style={styles.headlineLabel}>{t('app.killedToHold')}</Text>
                <Text style={[styles.headlineNumber, { color: COLORS.warn }]}>
                  {headline.directional_trades_killed_to_hold}
                </Text>
                <Text style={styles.headlineSub}>directional → HOLD</Text>
              </View>
              <View style={styles.headlineCell}>
                <Text style={styles.headlineLabel}>FLIPPED</Text>
                <Text style={[styles.headlineNumber, { color: COLORS.alert }]}>
                  {headline.directional_trades_flipped}
                </Text>
                <Text style={styles.headlineSub}>L↔S inversion</Text>
              </View>
            </View>
          </View>
        )}

        {/* THREE UNIVERSES */}
        <Text style={styles.sectionTitle}>{t('app.threePortfolios')}</Text>
        <View style={styles.universeRow}>
          {data?.portfolios.raw && (
            <PortfolioCard p={data.portfolios.raw} active={tab === 'raw'}
                           onPress={() => setTab('raw')} />
          )}
          {data?.portfolios.meta && (
            <PortfolioCard p={data.portfolios.meta} active={tab === 'meta'}
                           onPress={() => setTab('meta')} />
          )}
          {data?.portfolios.final && (
            <PortfolioCard p={data.portfolios.final} active={tab === 'final'}
                           onPress={() => setTab('final')} />
          )}
        </View>

        {filteredPortfolio && (
          <>
            <View style={styles.metricsBlock}>
              <View style={styles.metricsCol}>
                <Text style={styles.miniLabel}>{t('app.activePnl')}</Text>
                <Text style={[styles.miniValue,
                  { color: pnlColor(filteredPortfolio.active_pnl_total) }]}>
                  {fmtPct(filteredPortfolio.active_pnl_total, 2)}
                </Text>
              </View>
              <View style={styles.metricsCol}>
                <Text style={styles.miniLabel}>{t('app.meanPos')}</Text>
                <Text style={[styles.miniValue,
                  { color: pnlColor(filteredPortfolio.unrealized_pnl_mean) }]}>
                  {fmtPct(filteredPortfolio.unrealized_pnl_mean, 3)}
                </Text>
              </View>
              <View style={styles.metricsCol}>
                <Text style={styles.miniLabel}>{t('app.winRate')}</Text>
                <Text style={styles.miniValue}>
                  {filteredPortfolio.win_rate !== null ?
                    `${(filteredPortfolio.win_rate * 100).toFixed(0)}%` : '—'}
                </Text>
              </View>
              <View style={styles.metricsCol}>
                <Text style={styles.miniLabel}>Sharpe*</Text>
                <Text style={styles.miniValue}>
                  {filteredPortfolio.sharpe_proxy !== null ?
                    filteredPortfolio.sharpe_proxy.toFixed(2) : '—'}
                </Text>
              </View>
            </View>

            <View style={styles.exposureRow}>
              <View style={[styles.expChip, { borderColor: COLORS.long }]}>
                <Text style={[styles.expChipText, { color: COLORS.long }]}>
                  LONG {filteredPortfolio.exposure.long}
                </Text>
              </View>
              <View style={[styles.expChip, { borderColor: COLORS.short }]}>
                <Text style={[styles.expChipText, { color: COLORS.short }]}>
                  SHORT {filteredPortfolio.exposure.short}
                </Text>
              </View>
              <View style={[styles.expChip, { borderColor: COLORS.hold }]}>
                <Text style={[styles.expChipText, { color: COLORS.hold }]}>
                  HOLD {filteredPortfolio.exposure.hold}
                </Text>
              </View>
            </View>

            <Text style={styles.sectionTitle}>
              Positions ({filteredPortfolio.label}) — tap row → verdict
            </Text>
            <View style={{ paddingHorizontal: 16 }}>
              {filteredPortfolio.positions
                .slice()
                .sort((a, b) => (b.pnl || 0) - (a.pnl || 0))
                .slice(0, 80)
                .map((p, i) => (
                  <PositionRow
                    key={`${p.symbol}-${p.horizon}-${p.ts}-${i}`}
                    pos={p}
                    onPress={() => goToVerdict(p.symbol, p.horizon)}
                  />
                ))}
              {filteredPortfolio.positions.length === 0 && (
                <Text style={[styles.dim, { padding: 24, textAlign: 'center' }]}>
                  No positions match {symbolFilter || horizonFilter
                    ? `filter ${symbolFilter} ${horizonFilter}`.trim()
                    : 'this universe'}.
                </Text>
              )}
            </View>
          </>
        )}

        <Text style={styles.disclaimer}>
          Paper-only computation. No orders. No execution. No commits in side-car.
          Hypothetical PnL = entry → current spot, {data?.headline.n_priced || 0}/{data?.n || 0}{' '}
          positions priced.{'\n\n'}
          Sharpe* — proxy on active subset, not annualized.{'\n'}
          Positive RAW − FINAL number means Meta-Brain destroyed alpha;{'\n'}
          negative number means Meta-Brain saved capital.{'\n'}
          {lastUpdate && `Last update ${lastUpdate.toLocaleTimeString()}`}
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.bg },
  header: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 12, paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: COLORS.border,
    gap: 6,
  },
  backBtn: { width: 32, height: 32, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { color: COLORS.text, fontSize: 18, fontWeight: '800' },
  headerSub: { color: COLORS.textDim, fontSize: 11, marginTop: 2 },
  resolveBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 10, paddingVertical: 8,
    borderWidth: 1, borderColor: COLORS.warn, borderRadius: 999,
  },
  resolveBtnText: { color: COLORS.warn, fontSize: 11, fontWeight: '800' },
  linkBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 10, paddingVertical: 8,
    borderWidth: 1, borderColor: COLORS.accent, borderRadius: 999,
  },
  linkBtnText: { color: COLORS.accent, fontSize: 12, fontWeight: '700' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  dim: { color: COLORS.textDim, fontSize: 12 },
  errorBox: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: COLORS.warn + '11', padding: 10, borderRadius: 8,
    margin: 12, borderWidth: 1, borderColor: COLORS.warn + '33',
  },
  errorText: { color: COLORS.warn, fontSize: 12, flex: 1 },
  sectionTitle: {
    color: COLORS.textDim, fontSize: 11, fontWeight: '700',
    letterSpacing: 1, paddingHorizontal: 16, paddingTop: 18, paddingBottom: 8,
    textTransform: 'uppercase',
  },

  // attribution overlay
  attrSection: { paddingTop: 8 },
  attrVerdict: {
    marginHorizontal: 12, marginVertical: 8,
    borderWidth: 1, borderRadius: 12, padding: 14, alignItems: 'center',
  },
  attrVerdictLabel: { fontSize: 11, fontWeight: '900', letterSpacing: 1 },
  attrNetAlpha: { fontSize: 26, fontWeight: '900', marginTop: 4 },
  attrSubLabel: { color: COLORS.textFaint, fontSize: 10, marginTop: 4 },
  attrGrid: { flexDirection: 'row', paddingHorizontal: 12, gap: 8 },
  attrCell: {
    flex: 1, backgroundColor: COLORS.surface, borderRadius: 10,
    padding: 12, marginVertical: 4, borderWidth: 1,
  },
  attrCellLabel: { color: COLORS.textFaint, fontSize: 9, fontWeight: '700',
                   letterSpacing: 0.6 },
  attrCellNum: { fontSize: 22, fontWeight: '900', marginTop: 4 },
  attrCellSub: { color: COLORS.textFaint, fontSize: 10, marginTop: 2 },
  realizedTag: {
    color: COLORS.warn, fontSize: 9, fontWeight: '900',
    letterSpacing: 1, marginBottom: 4,
  },
  realizedNarrative: {
    color: COLORS.text, fontSize: 12, fontWeight: '600',
    marginTop: 8, paddingHorizontal: 8, textAlign: 'center', lineHeight: 16,
  },
  horizonGrid: {
    flexDirection: 'row', paddingHorizontal: 12, gap: 6, marginTop: 4,
  },
  horizonCell: {
    flex: 1, backgroundColor: COLORS.surface, borderRadius: 8,
    padding: 10, borderWidth: 1, alignItems: 'center',
  },
  horizonLabel: { color: COLORS.textFaint, fontSize: 10, fontWeight: '800',
                  letterSpacing: 0.5 },
  horizonNum: { fontSize: 16, fontWeight: '900', marginTop: 4 },
  horizonSub: { color: COLORS.textFaint, fontSize: 9, marginTop: 2 },
  realizedTagSm: {
    backgroundColor: COLORS.warn + '22', borderColor: COLORS.warn,
    borderWidth: 1, borderRadius: 4, paddingHorizontal: 4, paddingVertical: 1,
  },
  realizedTagSmText: {
    color: COLORS.warn, fontSize: 9, fontWeight: '900', letterSpacing: 0.5,
  },

  // timeline replay
  timelineSection: { marginTop: 4 },
  timelineHeaderRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
  },
  timelineHint: {
    color: COLORS.textFaint, fontSize: 10, paddingRight: 18, paddingTop: 18,
    fontStyle: 'italic',
  },
  narrativeCard: {
    width: 220, marginRight: 10,
    backgroundColor: COLORS.surface, borderRadius: 12,
    padding: 12, borderWidth: 1,
  },
  narrativeHeader: { flexDirection: 'row', alignItems: 'center', gap: 8,
                     marginBottom: 8 },
  narrativeSym: { color: COLORS.text, fontSize: 13, fontWeight: '800' },
  narrativeHorizon: { color: COLORS.textDim, fontSize: 11, fontWeight: '600' },
  narrativeFlow: { gap: 2, alignItems: 'flex-start' },
  narrativeStep: { color: COLORS.text, fontSize: 13, fontWeight: '700' },
  narrativeArrow: { color: COLORS.textFaint, fontSize: 14, marginVertical: 1 },
  narrativeMove: { fontSize: 13, fontWeight: '800' },
  narrativeEnd: { fontSize: 13, fontWeight: '900', marginTop: 2,
                  letterSpacing: 0.3 },

  headlineSection: { paddingBottom: 4 },
  headlineGrid: { flexDirection: 'row', paddingHorizontal: 12, gap: 8 },
  headlineCell: {
    flex: 1, backgroundColor: COLORS.surface, borderRadius: 10,
    paddingHorizontal: 14, paddingVertical: 12, marginVertical: 4,
    borderWidth: StyleSheet.hairlineWidth, borderColor: COLORS.border,
  },
  headlineLabel: { color: COLORS.textFaint, fontSize: 9, fontWeight: '700',
                   letterSpacing: 0.6 },
  headlineNumber: { fontSize: 20, fontWeight: '900', marginTop: 4 },
  headlineSub: { color: COLORS.textFaint, fontSize: 9, marginTop: 2 },

  universeRow: {
    flexDirection: 'row', paddingHorizontal: 12, gap: 8, marginBottom: 4,
  },
  universeCard: {
    flex: 1, backgroundColor: COLORS.surface,
    borderWidth: 1, borderColor: COLORS.border,
    borderRadius: 12, padding: 14, alignItems: 'center',
  },
  universeLabel: { color: COLORS.textDim, fontSize: 11,
                   fontWeight: '800', letterSpacing: 1 },
  universePnl: { fontSize: 22, fontWeight: '900', marginTop: 6 },
  universeMeta: { flexDirection: 'row', gap: 8, marginTop: 4 },
  universeMetaText: { color: COLORS.textFaint, fontSize: 10 },

  metricsBlock: {
    flexDirection: 'row', backgroundColor: COLORS.surface,
    marginHorizontal: 12, marginVertical: 8, borderRadius: 10, padding: 12,
    borderWidth: StyleSheet.hairlineWidth, borderColor: COLORS.border,
  },
  metricsCol: { flex: 1, alignItems: 'center' },
  miniLabel: { color: COLORS.textFaint, fontSize: 9, fontWeight: '700',
               letterSpacing: 0.5 },
  miniValue: { color: COLORS.text, fontSize: 14, fontWeight: '700', marginTop: 4 },
  exposureRow: {
    flexDirection: 'row', justifyContent: 'center', gap: 8, marginVertical: 4,
  },
  expChip: {
    borderWidth: 1, paddingHorizontal: 12, paddingVertical: 5, borderRadius: 999,
  },
  expChipText: { fontSize: 11, fontWeight: '800' },

  // position rows
  posRow: {
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: COLORS.border,
  },
  posTop: { flexDirection: 'row', alignItems: 'center' },
  posSym: { color: COLORS.text, fontSize: 14, fontWeight: '700' },
  posSub: { color: COLORS.textDim, fontSize: 11, fontWeight: '500' },
  posSubLine: { color: COLORS.textFaint, fontSize: 10, marginTop: 2 },
  dirCol: { width: 70, alignItems: 'center' },
  dirBadge: { borderWidth: 1, paddingHorizontal: 8, paddingVertical: 2,
              borderRadius: 4 },
  dirBadgeText: { fontSize: 10, fontWeight: '900' },
  posPnl: { fontSize: 13, fontWeight: '700' },

  // chips
  chipsRow: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingRight: 16 },
  chip: {
    paddingHorizontal: 8, paddingVertical: 3,
    borderRadius: 999, borderWidth: 1,
  },
  chipText: { fontSize: 10, fontWeight: '800', letterSpacing: 0.4 },

  disclaimer: {
    color: COLORS.textFaint, fontSize: 10,
    paddingHorizontal: 16, paddingTop: 24, lineHeight: 14,
  },
});
