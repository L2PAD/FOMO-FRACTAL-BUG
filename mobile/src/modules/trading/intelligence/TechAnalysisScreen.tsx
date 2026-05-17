/**
 * TechAnalysisScreen — Tech Analysis surface for Mobile (Expo).
 *
 * Shows for the currently selected asset:
 *   • Header: price, change %, action (LONG/SHORT/WAIT), RSI, trend
 *   • Sparkline (last 20 closes)
 *   • Multi-timeframe brief (4H, 1D, 7D, 30D) with state pills
 *   • Trade setup (if action != WAIT): entry / stop / target / R:R
 *   • Watchlist: 6-8 assets with compact action signals
 *
 * Data: /api/miniapp/tech-analysis?asset=...&timeframe=...
 *       /api/miniapp/tech-watchlist?symbols=...
 *
 * No mocks. Real-time OKX/CoinGecko candles via backend.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../../core/useColors';
import { useAssetStore } from '../../../stores/asset.store';
import { api } from '../../../services/api/api-client';

type TFAction = 'LONG' | 'SHORT' | 'WAIT';

interface MtfBrief {
  tf: string;
  ok: boolean;
  state?: string;
  action?: TFAction;
  color?: string;
  rsi?: number;
  price?: number;
  trend?: string;
}

interface TradeSetup {
  action: TFAction;
  entry: number;
  stop: number;
  target: number;
  rr: number;
  confidence: number;
}

interface TARes {
  ok: boolean;
  asset: string;
  pair: string;
  timeframe: string;
  price: number;
  changePct: number;
  rsi: number;
  trend: string;
  momentum: string;
  action: TFAction;
  emoji: string;
  support: number;
  resistance: number;
  sparkline: number[];
  reason: string;
  mtf: MtfBrief[];
  tradeSetup: TradeSetup | null;
  asOf: string;
}

interface WatchlistItem {
  symbol: string;
  action: TFAction;
  emoji: string;
  price: number;
  changePct: number;
  rsi: number;
  trend: string;
}

const TIMEFRAMES = ['4H', '1D', '7D', '30D'] as const;

export default function TechAnalysisScreen() {
  const colors = useColors();
  const symbol = useAssetStore((s) => s.symbol) || 'BTC';
  const [tf, setTf] = useState<string>('4H');
  const [data, setData] = useState<TARes | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const [ta, wl] = await Promise.all([
        api.get<TARes>(`/api/miniapp/tech-analysis?asset=${encodeURIComponent(symbol)}&timeframe=${tf}`),
        api.get<{ ok: boolean; items: WatchlistItem[] }>(
          '/api/miniapp/tech-watchlist?symbols=BTC,ETH,SOL,DOGE,ARB,XRP,BNB,AVAX'
        ),
      ]);
      if (ta?.ok) setData(ta);
      if (wl?.ok) setWatchlist(wl.items || []);
    } catch (e: any) {
      setError(e?.message || 'Failed to load TA');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [symbol, tf]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 30000); // refresh every 30s
    return () => clearInterval(interval);
  }, [load]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    load();
  }, [load]);

  const actionColor = (a?: TFAction) => {
    if (a === 'LONG') return colors.buy || '#10b981';
    if (a === 'SHORT') return colors.sell || '#ef4444';
    return colors.textMuted || '#94a3b8';
  };

  const styles = makeStyles(colors);

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={{ paddingBottom: 32 }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.text} />}
      testID="tech-analysis-screen"
    >
      {/* HEADER — symbol + price */}
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Text style={styles.symbol} testID="ta-symbol">{symbol}</Text>
          <Text style={styles.subtitle}>Tech Analysis · {tf}</Text>
        </View>
        {data ? (
          <View style={{ alignItems: 'flex-end' }}>
            <Text style={styles.price} testID="ta-price">
              ${data.price >= 1 ? data.price.toFixed(2) : data.price.toFixed(6)}
            </Text>
            <Text
              style={[styles.change, { color: data.changePct >= 0 ? (colors.buy || '#10b981') : (colors.sell || '#ef4444') }]}
              testID="ta-change"
            >
              {data.changePct >= 0 ? '+' : ''}{data.changePct.toFixed(2)}%
            </Text>
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
            testID={`ta-tf-${t}`}
          >
            <Text style={[styles.tfBtnText, tf === t && styles.tfBtnTextActive]}>{t}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* ERROR / LOADING */}
      {loading && !data && (
        <View style={styles.loadingBox}>
          <ActivityIndicator size="small" color={colors.text} />
          <Text style={styles.loadingText}>Loading market data…</Text>
        </View>
      )}
      {error && (
        <View style={styles.errorBox}>
          <Ionicons name="alert-circle" size={18} color={colors.sell || '#ef4444'} />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {/* ACTION CARD */}
      {data && (
        <View style={[styles.card, { borderColor: actionColor(data.action) }]} testID="ta-action-card">
          <View style={styles.actionRow}>
            <Text style={[styles.actionLabel, { color: actionColor(data.action) }]}>{data.emoji}  {data.action}</Text>
            <Text style={styles.rsiBadge}>RSI {data.rsi?.toFixed(0)}</Text>
          </View>
          <Text style={styles.reason}>{data.reason}</Text>
          <View style={styles.levelsRow}>
            <View style={styles.levelCol}>
              <Text style={styles.levelLabel}>Support</Text>
              <Text style={[styles.levelValue, { color: colors.buy || '#10b981' }]}>
                {data.support >= 1 ? data.support.toFixed(2) : data.support.toFixed(6)}
              </Text>
            </View>
            <View style={styles.levelCol}>
              <Text style={styles.levelLabel}>Resistance</Text>
              <Text style={[styles.levelValue, { color: colors.sell || '#ef4444' }]}>
                {data.resistance >= 1 ? data.resistance.toFixed(2) : data.resistance.toFixed(6)}
              </Text>
            </View>
            <View style={styles.levelCol}>
              <Text style={styles.levelLabel}>Trend</Text>
              <Text style={styles.levelValue}>{data.trend}</Text>
            </View>
          </View>
        </View>
      )}

      {/* SPARKLINE (ASCII-ish) */}
      {data?.sparkline && data.sparkline.length > 0 && (
        <View style={styles.card} testID="ta-sparkline">
          <Text style={styles.cardTitle}>Recent price (last 20 bars)</Text>
          <View style={styles.spark}>
            {data.sparkline.map((v, i) => (
              <View
                key={i}
                style={[
                  styles.sparkBar,
                  {
                    height: Math.max(4, (v / 100) * 60),
                    backgroundColor: data.trend === 'uptrend' ? (colors.buy || '#10b981') : (colors.sell || '#ef4444'),
                    opacity: 0.4 + (i / data.sparkline.length) * 0.6,
                  },
                ]}
              />
            ))}
          </View>
        </View>
      )}

      {/* MULTI-TIMEFRAME */}
      {data?.mtf && (
        <View style={styles.card} testID="ta-mtf">
          <Text style={styles.cardTitle}>Multi-timeframe</Text>
          {data.mtf.map((m) => (
            <View key={m.tf} style={styles.mtfRow}>
              <Text style={styles.mtfTf}>{m.tf}</Text>
              {m.ok ? (
                <>
                  <View style={[styles.mtfPill, { backgroundColor: m.color || '#94a3b8' }]}>
                    <Text style={styles.mtfPillText}>{m.state}</Text>
                  </View>
                  <Text style={styles.mtfRsi}>RSI {m.rsi?.toFixed(0)}</Text>
                  <Text style={[styles.mtfAction, { color: actionColor(m.action) }]}>{m.action}</Text>
                </>
              ) : (
                <Text style={styles.mtfNoData}>no data</Text>
              )}
            </View>
          ))}
        </View>
      )}

      {/* TRADE SETUP */}
      {data?.tradeSetup && (
        <View style={[styles.card, { borderColor: actionColor(data.tradeSetup.action) }]} testID="ta-trade-setup">
          <Text style={styles.cardTitle}>Trade Setup</Text>
          <View style={styles.tsRow}>
            <Text style={styles.tsLabel}>Entry</Text>
            <Text style={styles.tsValue}>${data.tradeSetup.entry.toFixed(2)}</Text>
          </View>
          <View style={styles.tsRow}>
            <Text style={styles.tsLabel}>Stop Loss</Text>
            <Text style={[styles.tsValue, { color: colors.sell || '#ef4444' }]}>
              ${data.tradeSetup.stop.toFixed(2)}
            </Text>
          </View>
          <View style={styles.tsRow}>
            <Text style={styles.tsLabel}>Target</Text>
            <Text style={[styles.tsValue, { color: colors.buy || '#10b981' }]}>
              ${data.tradeSetup.target.toFixed(2)}
            </Text>
          </View>
          <View style={styles.tsRow}>
            <Text style={styles.tsLabel}>R:R</Text>
            <Text style={styles.tsValue}>{data.tradeSetup.rr?.toFixed(2)}</Text>
          </View>
          <View style={styles.tsRow}>
            <Text style={styles.tsLabel}>Confidence</Text>
            <Text style={styles.tsValue}>{(data.tradeSetup.confidence * 100).toFixed(0)}%</Text>
          </View>
        </View>
      )}

      {/* WATCHLIST */}
      {watchlist.length > 0 && (
        <View style={styles.card} testID="ta-watchlist">
          <Text style={styles.cardTitle}>Watchlist</Text>
          {watchlist.map((w) => (
            <View key={w.symbol} style={styles.wlRow}>
              <Text style={styles.wlSymbol}>{w.symbol}</Text>
              <Text style={styles.wlPrice}>
                ${w.price >= 1 ? w.price.toFixed(2) : w.price.toFixed(4)}
              </Text>
              <Text
                style={[styles.wlChange, { color: w.changePct >= 0 ? (colors.buy || '#10b981') : (colors.sell || '#ef4444') }]}
              >
                {w.changePct >= 0 ? '+' : ''}{w.changePct?.toFixed(2)}%
              </Text>
              <View style={[styles.mtfPill, { backgroundColor: actionColor(w.action) }]}>
                <Text style={styles.mtfPillText}>{w.action}</Text>
              </View>
            </View>
          ))}
        </View>
      )}

      <Text style={styles.footer}>
        Updated {data?.asOf ? new Date(data.asOf).toLocaleTimeString() : '—'}
      </Text>
    </ScrollView>
  );
}

const makeStyles = (colors: any) =>
  StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.bg || '#0b0e14' },
    header: {
      flexDirection: 'row',
      alignItems: 'center',
      padding: 16,
      paddingTop: 24,
      borderBottomWidth: 1,
      borderBottomColor: colors.border || '#1f2937',
    },
    symbol: { fontSize: 22, fontWeight: '700', color: colors.text || '#e2e8f0' },
    subtitle: { fontSize: 12, color: colors.textMuted || '#64748b', marginTop: 2 },
    price: { fontSize: 18, fontWeight: '700', color: colors.text || '#e2e8f0' },
    change: { fontSize: 13, fontWeight: '600', marginTop: 2 },
    tfRow: { flexDirection: 'row', padding: 12, gap: 6 },
    tfBtn: {
      paddingVertical: 6,
      paddingHorizontal: 12,
      borderRadius: 8,
      backgroundColor: colors.card || '#1a1f2b',
      borderWidth: 1,
      borderColor: colors.border || '#1f2937',
    },
    tfBtnActive: { backgroundColor: colors.text || '#e2e8f0' },
    tfBtnText: { fontSize: 12, color: colors.textMuted || '#94a3b8', fontWeight: '600' },
    tfBtnTextActive: { color: colors.bg || '#0b0e14' },
    loadingBox: { flexDirection: 'row', alignItems: 'center', padding: 16, gap: 8 },
    loadingText: { color: colors.textMuted || '#94a3b8', fontSize: 13 },
    errorBox: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
      padding: 12,
      margin: 12,
      borderRadius: 8,
      backgroundColor: colors.cardError || '#3b1f1f',
    },
    errorText: { color: colors.sell || '#ef4444', fontSize: 13, flex: 1 },
    card: {
      margin: 12,
      padding: 14,
      borderRadius: 10,
      backgroundColor: colors.card || '#141821',
      borderWidth: 1,
      borderColor: colors.border || '#1f2937',
    },
    cardTitle: { fontSize: 12, fontWeight: '600', color: colors.textMuted || '#94a3b8', marginBottom: 10, textTransform: 'uppercase', letterSpacing: 0.5 },
    actionRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
    actionLabel: { fontSize: 24, fontWeight: '700' },
    rsiBadge: {
      fontSize: 12,
      fontWeight: '600',
      color: colors.text || '#e2e8f0',
      backgroundColor: colors.bg || '#0b0e14',
      paddingHorizontal: 8,
      paddingVertical: 3,
      borderRadius: 6,
    },
    reason: { color: colors.textMuted || '#94a3b8', fontSize: 13, marginBottom: 12 },
    levelsRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 6 },
    levelCol: { flex: 1 },
    levelLabel: { fontSize: 11, color: colors.textMuted || '#64748b', marginBottom: 2, textTransform: 'uppercase' },
    levelValue: { fontSize: 14, fontWeight: '600', color: colors.text || '#e2e8f0' },
    spark: { flexDirection: 'row', alignItems: 'flex-end', height: 60, gap: 2, marginTop: 4 },
    sparkBar: { flex: 1, borderRadius: 1 },
    mtfRow: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingVertical: 8,
      borderBottomWidth: 1,
      borderBottomColor: colors.border || '#1f2937',
    },
    mtfTf: { width: 50, fontSize: 13, fontWeight: '600', color: colors.text || '#e2e8f0' },
    mtfPill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, marginHorizontal: 6 },
    mtfPillText: { color: '#fff', fontSize: 10, fontWeight: '700' },
    mtfRsi: { fontSize: 12, color: colors.textMuted || '#94a3b8', flex: 1, textAlign: 'right' },
    mtfAction: { fontSize: 12, fontWeight: '700', width: 50, textAlign: 'right' },
    mtfNoData: { fontSize: 12, color: colors.textMuted || '#64748b', flex: 1, marginLeft: 8 },
    tsRow: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      paddingVertical: 6,
      borderBottomWidth: 1,
      borderBottomColor: colors.border || '#1f2937',
    },
    tsLabel: { fontSize: 13, color: colors.textMuted || '#94a3b8' },
    tsValue: { fontSize: 13, fontWeight: '600', color: colors.text || '#e2e8f0' },
    wlRow: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingVertical: 8,
      borderBottomWidth: 1,
      borderBottomColor: colors.border || '#1f2937',
    },
    wlSymbol: { width: 50, fontWeight: '600', color: colors.text || '#e2e8f0', fontSize: 13 },
    wlPrice: { flex: 1, color: colors.text || '#e2e8f0', fontSize: 13 },
    wlChange: { fontSize: 12, fontWeight: '600', width: 60, textAlign: 'right' },
    footer: { textAlign: 'center', fontSize: 11, color: colors.textMuted || '#64748b', marginTop: 16 },
  });
