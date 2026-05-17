/**
 * FractalScreen — Fractal intelligence surface for Mobile (Expo).
 *
 * Combines:
 *   • Native fractal runtime engine (phase/state/direction + reasons)
 *   • Similarity engine (top historical analogs + outcome bias)
 *   • Forecast path (next-N bars projection from similar windows)
 *   • Heatmap (asset × horizon phase)
 *   • Watchlist (multi-asset bias signals)
 *
 * Data:
 *   /api/miniapp/fractal?asset=...&timeframe=...
 *   /api/miniapp/fractal-watchlist?symbols=...
 *
 * No mocks. Real-time fractal engine + OKX OHLC similarity.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, ActivityIndicator,
  RefreshControl, TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../../core/useColors';
import { useAssetStore } from '../../../stores/asset.store';
import { api } from '../../../services/api/api-client';

type Direction = 'LONG_BIAS' | 'SHORT_BIAS' | 'WAIT';
type Phase = 'compression' | 'rangebound' | 'expansion' | 'breakdown' | 'unavailable';

interface ForecastStep {
  step: number;
  projected: number;
  high: number;
  low: number;
  uncertainty: number;
}

interface FractalRes {
  ok: boolean;
  asset: string;
  timeframe: string;
  price: number | null;
  phase: Phase;
  state: string;
  direction: Direction;
  runtimeConfidence: number;
  evidence: any;
  reasons: string[];
  similarity: {
    consensus: Direction;
    confidence: number;
    avgReturnPct: number;
    longCount: number;
    shortCount: number;
    matchCount: number;
  };
  forecast: {
    consensus: Direction;
    avgReturnPct: number;
    horizonBars: number;
    confidence: number;
    pathHead: ForecastStep[];
  };
}

interface WatchlistItem {
  symbol: string;
  price: number;
  phase: Phase;
  direction: Direction;
  runtimeConf: number;
  simConsensus: Direction;
  simConf: number;
  avgReturnPct: number;
}

const TIMEFRAMES = ['4H', '1D', '7D', '30D'] as const;

const fmtPrice = (n: number | null | undefined) => {
  if (n == null || isNaN(n)) return '—';
  if (n >= 1) return `$${n.toFixed(2)}`;
  return `$${n.toFixed(6)}`;
};

export default function FractalScreen() {
  const colors = useColors();
  const symbol = useAssetStore((s) => s.symbol) || 'BTC';
  const [tf, setTf] = useState<string>('1D');
  const [data, setData] = useState<FractalRes | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const [fr, wl] = await Promise.all([
        api.get<FractalRes>(`/api/miniapp/fractal?asset=${encodeURIComponent(symbol)}&timeframe=${tf}`),
        api.get<{ ok: boolean; items: WatchlistItem[] }>(
          '/api/miniapp/fractal-watchlist?symbols=BTC,ETH,SOL,DOGE,XRP,BNB,ARB,AVAX'
        ),
      ]);
      if (fr?.ok) setData(fr);
      if (wl?.ok) setWatchlist(wl.items || []);
    } catch (e: any) {
      setError(e?.message || 'Failed to load fractal data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [symbol, tf]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 45000); // refresh every 45s
    return () => clearInterval(interval);
  }, [load]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    load();
  }, [load]);

  const dirColor = (d?: Direction) => {
    if (d === 'LONG_BIAS') return colors.buy || '#10b981';
    if (d === 'SHORT_BIAS') return colors.sell || '#ef4444';
    return colors.textMuted || '#94a3b8';
  };

  const phaseColor = (p?: Phase) => {
    if (p === 'expansion') return '#3b82f6';
    if (p === 'compression') return '#f59e0b';
    if (p === 'rangebound') return '#94a3b8';
    if (p === 'breakdown') return colors.sell || '#ef4444';
    return colors.textMuted || '#64748b';
  };

  const styles = makeStyles(colors);

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={{ paddingBottom: 32 }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.text} />}
      testID="fractal-screen"
    >
      {/* HEADER */}
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Text style={styles.symbol} testID="fr-symbol">{symbol}</Text>
          <Text style={styles.subtitle}>Fractal · structural perception</Text>
        </View>
        {data ? (
          <View style={{ alignItems: 'flex-end' }}>
            <Text style={styles.price}>{fmtPrice(data.price)}</Text>
            <Text style={styles.tfLabel}>{data.timeframe}</Text>
          </View>
        ) : null}
      </View>

      {/* TIMEFRAME PICKER */}
      <View style={styles.tfRow}>
        {TIMEFRAMES.map((t) => (
          <TouchableOpacity
            key={t}
            style={[styles.tfBtn, tf === t && styles.tfBtnActive]}
            onPress={() => setTf(t)}
            testID={`fr-tf-${t}`}
          >
            <Text style={[styles.tfBtnText, tf === t && styles.tfBtnTextActive]}>{t}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* LOADING / ERROR */}
      {loading && !data && (
        <View style={styles.loadingBox}>
          <ActivityIndicator size="small" color={colors.text} />
          <Text style={styles.loadingText}>Computing fractal similarity…</Text>
        </View>
      )}
      {error && (
        <View style={styles.errorBox}>
          <Ionicons name="alert-circle" size={18} color={colors.sell || '#ef4444'} />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {/* RUNTIME CARD */}
      {data && (
        <View style={[styles.card, { borderColor: dirColor(data.direction) }]} testID="fr-runtime-card">
          <View style={styles.row}>
            <View style={[styles.phasePill, { backgroundColor: phaseColor(data.phase) }]}>
              <Text style={styles.phasePillText}>{data.phase}</Text>
            </View>
            <Text style={[styles.directionText, { color: dirColor(data.direction) }]}>
              {data.direction === 'LONG_BIAS' ? '📈' : data.direction === 'SHORT_BIAS' ? '📉' : '⏸'} {data.direction.replace('_', ' ')}
            </Text>
          </View>
          <Text style={styles.metricLabel}>Native runtime confidence</Text>
          <Text style={styles.metricValue}>{(data.runtimeConfidence * 100).toFixed(1)}%</Text>
          {data.reasons && data.reasons.length > 0 && (
            <View style={{ marginTop: 10 }}>
              <Text style={styles.cardTitle}>Reasons</Text>
              {data.reasons.slice(0, 3).map((r, i) => (
                <Text key={i} style={styles.reasonText}>• {r}</Text>
              ))}
            </View>
          )}
        </View>
      )}

      {/* SIMILARITY CARD */}
      {data?.similarity && (
        <View style={[styles.card, { borderColor: dirColor(data.similarity.consensus) }]} testID="fr-similarity-card">
          <Text style={styles.cardTitle}>Historical Analogs Engine</Text>
          <View style={styles.row}>
            <Text style={[styles.directionText, { color: dirColor(data.similarity.consensus) }]}>
              {data.similarity.consensus.replace('_', ' ')}
            </Text>
            <Text style={[styles.bigReturn, { color: data.similarity.avgReturnPct >= 0 ? (colors.buy || '#10b981') : (colors.sell || '#ef4444') }]}>
              {data.similarity.avgReturnPct >= 0 ? '+' : ''}{data.similarity.avgReturnPct.toFixed(2)}%
            </Text>
          </View>
          <View style={styles.metricGrid}>
            <View style={styles.metricCol}>
              <Text style={styles.metricLabel}>Long count</Text>
              <Text style={[styles.metricValueSmall, { color: colors.buy || '#10b981' }]}>{data.similarity.longCount}</Text>
            </View>
            <View style={styles.metricCol}>
              <Text style={styles.metricLabel}>Short count</Text>
              <Text style={[styles.metricValueSmall, { color: colors.sell || '#ef4444' }]}>{data.similarity.shortCount}</Text>
            </View>
            <View style={styles.metricCol}>
              <Text style={styles.metricLabel}>Confidence</Text>
              <Text style={styles.metricValueSmall}>{(data.similarity.confidence * 100).toFixed(0)}%</Text>
            </View>
            <View style={styles.metricCol}>
              <Text style={styles.metricLabel}>Matches</Text>
              <Text style={styles.metricValueSmall}>{data.similarity.matchCount}</Text>
            </View>
          </View>
        </View>
      )}

      {/* FORECAST PATH */}
      {data?.forecast?.pathHead && data.forecast.pathHead.length > 0 && (
        <View style={styles.card} testID="fr-forecast-card">
          <Text style={styles.cardTitle}>Forecast (next {data.forecast.horizonBars} bars)</Text>
          <View style={styles.row}>
            <Text style={[styles.directionText, { color: dirColor(data.forecast.consensus) }]}>
              {data.forecast.consensus.replace('_', ' ')}
            </Text>
            <Text style={styles.metricValueSmall}>conf {(data.forecast.confidence * 100).toFixed(0)}%</Text>
          </View>
          {data.forecast.pathHead.map((p) => (
            <View key={p.step} style={styles.forecastRow}>
              <Text style={styles.forecastStep}>+{p.step}</Text>
              <Text style={styles.forecastValue}>{fmtPrice(p.projected)}</Text>
              <Text style={styles.forecastBand}>
                {fmtPrice(p.low)} – {fmtPrice(p.high)}
              </Text>
            </View>
          ))}
        </View>
      )}

      {/* WATCHLIST */}
      {watchlist.length > 0 && (
        <View style={styles.card} testID="fr-watchlist">
          <Text style={styles.cardTitle}>Fractal Watchlist</Text>
          {watchlist.map((w) => (
            <View key={w.symbol} style={styles.wlRow}>
              <Text style={styles.wlSymbol}>{w.symbol}</Text>
              <Text style={styles.wlPrice}>{fmtPrice(w.price)}</Text>
              <View style={[styles.phasePill, { backgroundColor: phaseColor(w.phase) }]}>
                <Text style={styles.phasePillText}>{w.phase}</Text>
              </View>
              <Text style={[styles.wlReturn, { color: w.avgReturnPct >= 0 ? (colors.buy || '#10b981') : (colors.sell || '#ef4444') }]}>
                {w.avgReturnPct >= 0 ? '+' : ''}{w.avgReturnPct.toFixed(1)}%
              </Text>
              <View style={[styles.dirPill, { backgroundColor: dirColor(w.simConsensus) }]}>
                <Text style={styles.dirPillText}>{w.simConsensus === 'LONG_BIAS' ? 'L' : w.simConsensus === 'SHORT_BIAS' ? 'S' : 'W'}</Text>
              </View>
            </View>
          ))}
        </View>
      )}

      <Text style={styles.footer}>Source: native fractal engine + OKX historical analogs · 45s refresh</Text>
    </ScrollView>
  );
}

const makeStyles = (colors: any) =>
  StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.bg || '#0b0e14' },
    header: {
      flexDirection: 'row', alignItems: 'center', padding: 16, paddingTop: 24,
      borderBottomWidth: 1, borderBottomColor: colors.border || '#1f2937',
    },
    symbol: { fontSize: 22, fontWeight: '700', color: colors.text || '#e2e8f0' },
    subtitle: { fontSize: 12, color: colors.textMuted || '#64748b', marginTop: 2 },
    price: { fontSize: 18, fontWeight: '700', color: colors.text || '#e2e8f0' },
    tfLabel: { fontSize: 12, color: colors.textMuted || '#64748b', marginTop: 2 },
    tfRow: { flexDirection: 'row', padding: 12, gap: 6 },
    tfBtn: {
      paddingVertical: 6, paddingHorizontal: 12, borderRadius: 8,
      backgroundColor: colors.card || '#1a1f2b',
      borderWidth: 1, borderColor: colors.border || '#1f2937',
    },
    tfBtnActive: { backgroundColor: colors.text || '#e2e8f0' },
    tfBtnText: { fontSize: 12, color: colors.textMuted || '#94a3b8', fontWeight: '600' },
    tfBtnTextActive: { color: colors.bg || '#0b0e14' },
    loadingBox: { flexDirection: 'row', alignItems: 'center', padding: 16, gap: 8 },
    loadingText: { color: colors.textMuted || '#94a3b8', fontSize: 13 },
    errorBox: {
      flexDirection: 'row', alignItems: 'center', gap: 8,
      padding: 12, margin: 12, borderRadius: 8,
      backgroundColor: colors.cardError || '#3b1f1f',
    },
    errorText: { color: colors.sell || '#ef4444', fontSize: 13, flex: 1 },
    card: {
      margin: 12, padding: 14, borderRadius: 10,
      backgroundColor: colors.card || '#141821',
      borderWidth: 1, borderColor: colors.border || '#1f2937',
    },
    cardTitle: {
      fontSize: 11, fontWeight: '600', color: colors.textMuted || '#94a3b8',
      marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5,
    },
    row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
    phasePill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 6 },
    phasePillText: { color: '#fff', fontSize: 11, fontWeight: '700', textTransform: 'uppercase' },
    directionText: { fontSize: 16, fontWeight: '700' },
    metricLabel: { fontSize: 11, color: colors.textMuted || '#64748b', marginTop: 4 },
    metricValue: { fontSize: 22, fontWeight: '700', color: colors.text || '#e2e8f0' },
    metricValueSmall: { fontSize: 14, fontWeight: '600', color: colors.text || '#e2e8f0' },
    bigReturn: { fontSize: 18, fontWeight: '700' },
    reasonText: { fontSize: 11, color: colors.textMuted || '#94a3b8', marginVertical: 2 },
    metricGrid: { flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: -6 },
    metricCol: { width: '25%', paddingHorizontal: 6, paddingVertical: 8 },
    forecastRow: {
      flexDirection: 'row', paddingVertical: 5, alignItems: 'center',
      borderBottomWidth: 1, borderBottomColor: colors.border || '#1f2937',
    },
    forecastStep: { width: 36, fontWeight: '600', color: colors.text || '#e2e8f0', fontSize: 12 },
    forecastValue: { flex: 1, color: colors.text || '#e2e8f0', fontSize: 12, fontWeight: '600' },
    forecastBand: { fontSize: 10, color: colors.textMuted || '#64748b' },
    wlRow: {
      flexDirection: 'row', alignItems: 'center', paddingVertical: 8, gap: 5,
      borderBottomWidth: 1, borderBottomColor: colors.border || '#1f2937',
    },
    wlSymbol: { width: 45, fontWeight: '600', color: colors.text || '#e2e8f0', fontSize: 12 },
    wlPrice: { flex: 1.2, color: colors.text || '#e2e8f0', fontSize: 12 },
    wlReturn: { flex: 0.8, fontSize: 11, textAlign: 'right' },
    dirPill: { width: 22, height: 22, borderRadius: 11, alignItems: 'center', justifyContent: 'center' },
    dirPillText: { color: '#fff', fontSize: 10, fontWeight: '700' },
    footer: { textAlign: 'center', fontSize: 10, color: colors.textMuted || '#64748b', marginTop: 16, paddingHorizontal: 16 },
  });
