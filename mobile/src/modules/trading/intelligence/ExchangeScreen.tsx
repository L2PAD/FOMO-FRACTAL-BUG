/**
 * ExchangeScreen — CEX intelligence surface for Mobile (Expo).
 *
 * Shows for the currently selected asset:
 *   • Spot price + 24h change + 24h volume
 *   • Funding rate (current + annualized) + bias
 *   • Open Interest in USD
 *   • Orderbook imbalance (buy/sell pressure)
 *   • Anomalies scanner (funding rate extremes, OI > $1B)
 *   • Watchlist with multi-asset bias signals
 *
 * Data:
 *   /api/miniapp/exchange?asset=...
 *   /api/miniapp/exchange-watchlist?symbols=...
 *   /api/exchange/anomalies
 *
 * No mocks. Real-time OKX public REST via backend.
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

type Bias = 'bullish' | 'bearish' | 'neutral';

interface OrderbookLevel { price: number; size: number }
interface ExchangeRes {
  ok: boolean;
  symbol: string;
  spotPair: string;
  swapPair: string;
  spotPrice: number;
  changePct24h: number | null;
  volCcy24h: number | null;
  fundingRate: number | null;
  fundingRatePct: number | null;
  annualizedFundingPct: number | null;
  openInterestUsd: number | null;
  orderbookImbalance: number;
  bias: Bias;
  bullishFactors: number;
  bearishFactors: number;
  orderbook: { bids: OrderbookLevel[]; asks: OrderbookLevel[] } | null;
}

interface WatchlistItem {
  symbol: string;
  price: number;
  changePct24h: number | null;
  volume24h: number | null;
  fundingRatePct: number | null;
  annualizedFundingPct: number | null;
  openInterestUsd: number | null;
  orderbookImbalance: number;
  bias: Bias;
}

interface AnomalyItem {
  symbol: string;
  fundingRateBps: number;
  annualizedPct: number;
  oiUsd: number | null;
  flags: string[];
  severity: 'high' | 'medium';
}

const fmtUsd = (n: number | null | undefined): string => {
  if (n == null || isNaN(n)) return '—';
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(2)}K`;
  return `$${n.toFixed(2)}`;
};

const fmtPrice = (n: number | null | undefined): string => {
  if (n == null || isNaN(n)) return '—';
  if (n >= 1) return `$${n.toFixed(2)}`;
  return `$${n.toFixed(6)}`;
};

export default function ExchangeScreen() {
  const colors = useColors();
  const symbol = useAssetStore((s) => s.symbol) || 'BTC';
  const [data, setData] = useState<ExchangeRes | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const [ex, wl, an] = await Promise.all([
        api.get<ExchangeRes>(`/api/miniapp/exchange?asset=${encodeURIComponent(symbol)}`),
        api.get<{ ok: boolean; items: WatchlistItem[] }>(
          '/api/miniapp/exchange-watchlist?symbols=BTC,ETH,SOL,DOGE,XRP,BNB,ARB,AVAX'
        ),
        api.get<{ ok: boolean; items: AnomalyItem[] }>('/api/exchange/anomalies?threshold_funding_bps=2'),
      ]);
      if (ex?.ok) setData(ex);
      if (wl?.ok) setWatchlist(wl.items || []);
      if (an?.ok) setAnomalies(an.items || []);
    } catch (e: any) {
      setError(e?.message || 'Failed to load exchange data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [symbol]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 20000);
    return () => clearInterval(interval);
  }, [load]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    load();
  }, [load]);

  const biasColor = (b?: Bias) => {
    if (b === 'bullish') return colors.buy || '#10b981';
    if (b === 'bearish') return colors.sell || '#ef4444';
    return colors.textMuted || '#94a3b8';
  };

  const styles = makeStyles(colors);

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={{ paddingBottom: 32 }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.text} />}
      testID="exchange-screen"
    >
      {/* HEADER */}
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Text style={styles.symbol} testID="ex-symbol">{symbol}</Text>
          <Text style={styles.subtitle}>Exchange · OKX live</Text>
        </View>
        {data ? (
          <View style={{ alignItems: 'flex-end' }}>
            <Text style={styles.price}>{fmtPrice(data.spotPrice)}</Text>
            <Text style={[styles.change, { color: (data.changePct24h ?? 0) >= 0 ? (colors.buy || '#10b981') : (colors.sell || '#ef4444') }]}>
              {(data.changePct24h ?? 0) >= 0 ? '+' : ''}{(data.changePct24h ?? 0).toFixed(2)}%
            </Text>
          </View>
        ) : null}
      </View>

      {/* LOADING / ERROR */}
      {loading && !data && (
        <View style={styles.loadingBox}>
          <ActivityIndicator size="small" color={colors.text} />
          <Text style={styles.loadingText}>Loading OKX derivatives…</Text>
        </View>
      )}
      {error && (
        <View style={styles.errorBox}>
          <Ionicons name="alert-circle" size={18} color={colors.sell || '#ef4444'} />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {/* BIAS CARD */}
      {data && (
        <View style={[styles.card, { borderColor: biasColor(data.bias) }]} testID="ex-bias-card">
          <View style={styles.biasRow}>
            <Text style={[styles.biasText, { color: biasColor(data.bias) }]}>
              {data.bias === 'bullish' ? '🟢' : data.bias === 'bearish' ? '🔴' : '⚪'} {data.bias.toUpperCase()}
            </Text>
            <Text style={styles.biasMeta}>{data.bullishFactors}B / {data.bearishFactors}S</Text>
          </View>
          <View style={styles.metricGrid}>
            <View style={styles.metricCol}>
              <Text style={styles.metricLabel}>Funding 8h</Text>
              <Text style={[styles.metricValue, { color: (data.fundingRatePct ?? 0) >= 0 ? (colors.sell || '#ef4444') : (colors.buy || '#10b981') }]}>
                {(data.fundingRatePct ?? 0) >= 0 ? '+' : ''}{(data.fundingRatePct ?? 0).toFixed(4)}%
              </Text>
              <Text style={styles.metricHint}>Annual {(data.annualizedFundingPct ?? 0).toFixed(2)}%</Text>
            </View>
            <View style={styles.metricCol}>
              <Text style={styles.metricLabel}>Open Interest</Text>
              <Text style={styles.metricValue}>{fmtUsd(data.openInterestUsd)}</Text>
              <Text style={styles.metricHint}>SWAP</Text>
            </View>
            <View style={styles.metricCol}>
              <Text style={styles.metricLabel}>OB Imbalance</Text>
              <Text style={[styles.metricValue, { color: data.orderbookImbalance >= 0 ? (colors.buy || '#10b981') : (colors.sell || '#ef4444') }]}>
                {data.orderbookImbalance >= 0 ? '+' : ''}{(data.orderbookImbalance * 100).toFixed(1)}%
              </Text>
              <Text style={styles.metricHint}>top 20 levels</Text>
            </View>
            <View style={styles.metricCol}>
              <Text style={styles.metricLabel}>Volume 24h</Text>
              <Text style={styles.metricValue}>{fmtUsd(data.volCcy24h)}</Text>
              <Text style={styles.metricHint}>spot</Text>
            </View>
          </View>
        </View>
      )}

      {/* ORDERBOOK */}
      {data?.orderbook && data.orderbook.bids.length > 0 && (
        <View style={styles.card} testID="ex-orderbook">
          <Text style={styles.cardTitle}>Orderbook (top 5 each side)</Text>
          <View style={styles.bookHeader}>
            <Text style={styles.bookHeaderText}>Price</Text>
            <Text style={styles.bookHeaderText}>Size</Text>
          </View>
          {data.orderbook.asks.slice().reverse().map((a, i) => (
            <View key={`a-${i}`} style={styles.bookRow}>
              <Text style={[styles.bookPrice, { color: colors.sell || '#ef4444' }]}>{fmtPrice(a.price)}</Text>
              <Text style={styles.bookSize}>{a.size.toFixed(4)}</Text>
            </View>
          ))}
          <View style={[styles.bookRow, { backgroundColor: colors.bg || '#0b0e14', paddingVertical: 4 }]}>
            <Text style={{ color: colors.textMuted, fontSize: 11 }}>SPREAD</Text>
            <Text style={{ color: colors.text, fontSize: 11 }}>
              {data.orderbook.asks[0] && data.orderbook.bids[0]
                ? fmtPrice(data.orderbook.asks[0].price - data.orderbook.bids[0].price)
                : '—'}
            </Text>
          </View>
          {data.orderbook.bids.map((b, i) => (
            <View key={`b-${i}`} style={styles.bookRow}>
              <Text style={[styles.bookPrice, { color: colors.buy || '#10b981' }]}>{fmtPrice(b.price)}</Text>
              <Text style={styles.bookSize}>{b.size.toFixed(4)}</Text>
            </View>
          ))}
        </View>
      )}

      {/* ANOMALIES */}
      {anomalies.length > 0 && (
        <View style={styles.card} testID="ex-anomalies">
          <Text style={styles.cardTitle}>Funding/OI Anomalies</Text>
          {anomalies.map((a) => (
            <View key={a.symbol} style={styles.anomalyRow}>
              <Text style={styles.anomalySymbol}>{a.symbol}</Text>
              <View style={[styles.severityPill, { backgroundColor: a.severity === 'high' ? (colors.sell || '#ef4444') : '#f59e0b' }]}>
                <Text style={styles.severityText}>{a.severity}</Text>
              </View>
              <Text style={styles.anomalyMeta}>fr {a.fundingRateBps.toFixed(1)}bps</Text>
              <Text style={styles.anomalyMeta}>{fmtUsd(a.oiUsd)} OI</Text>
            </View>
          ))}
        </View>
      )}

      {/* WATCHLIST */}
      {watchlist.length > 0 && (
        <View style={styles.card} testID="ex-watchlist">
          <Text style={styles.cardTitle}>Watchlist (Bias by funding+OB)</Text>
          {watchlist.map((w) => (
            <View key={w.symbol} style={styles.wlRow}>
              <Text style={styles.wlSymbol}>{w.symbol}</Text>
              <Text style={styles.wlPrice}>{fmtPrice(w.price)}</Text>
              <Text style={[styles.wlFunding, { color: (w.fundingRatePct ?? 0) >= 0 ? (colors.sell || '#ef4444') : (colors.buy || '#10b981') }]}>
                {(w.fundingRatePct ?? 0) >= 0 ? '+' : ''}{(w.fundingRatePct ?? 0).toFixed(4)}%
              </Text>
              <Text style={styles.wlOi}>{fmtUsd(w.openInterestUsd)}</Text>
              <View style={[styles.severityPill, { backgroundColor: biasColor(w.bias) }]}>
                <Text style={styles.severityText}>{w.bias}</Text>
              </View>
            </View>
          ))}
        </View>
      )}

      <Text style={styles.footer}>Source: OKX public REST · 20s refresh</Text>
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
    change: { fontSize: 13, fontWeight: '600', marginTop: 2 },
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
      fontSize: 12, fontWeight: '600', color: colors.textMuted || '#94a3b8',
      marginBottom: 10, textTransform: 'uppercase', letterSpacing: 0.5,
    },
    biasRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
    biasText: { fontSize: 22, fontWeight: '700' },
    biasMeta: {
      fontSize: 11, color: colors.textMuted || '#94a3b8',
      backgroundColor: colors.bg || '#0b0e14',
      paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6,
    },
    metricGrid: { flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: -6 },
    metricCol: { width: '50%', paddingHorizontal: 6, paddingVertical: 8 },
    metricLabel: { fontSize: 11, color: colors.textMuted || '#64748b', marginBottom: 2 },
    metricValue: { fontSize: 15, fontWeight: '600', color: colors.text || '#e2e8f0' },
    metricHint: { fontSize: 10, color: colors.textMuted || '#64748b', marginTop: 1 },
    bookHeader: {
      flexDirection: 'row', justifyContent: 'space-between',
      paddingVertical: 4, borderBottomWidth: 1, borderBottomColor: colors.border || '#1f2937',
    },
    bookHeaderText: { fontSize: 10, color: colors.textMuted || '#64748b', textTransform: 'uppercase' },
    bookRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 3 },
    bookPrice: { fontSize: 12, fontWeight: '600' },
    bookSize: { fontSize: 12, color: colors.textMuted || '#94a3b8' },
    anomalyRow: {
      flexDirection: 'row', alignItems: 'center', paddingVertical: 8, gap: 8,
      borderBottomWidth: 1, borderBottomColor: colors.border || '#1f2937',
    },
    anomalySymbol: { width: 50, fontWeight: '600', color: colors.text || '#e2e8f0', fontSize: 13 },
    severityPill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
    severityText: { color: '#fff', fontSize: 10, fontWeight: '700', textTransform: 'uppercase' },
    anomalyMeta: { fontSize: 11, color: colors.textMuted || '#94a3b8', flex: 1, textAlign: 'right' },
    wlRow: {
      flexDirection: 'row', alignItems: 'center', paddingVertical: 8, gap: 4,
      borderBottomWidth: 1, borderBottomColor: colors.border || '#1f2937',
    },
    wlSymbol: { width: 45, fontWeight: '600', color: colors.text || '#e2e8f0', fontSize: 12 },
    wlPrice: { flex: 1.2, color: colors.text || '#e2e8f0', fontSize: 12 },
    wlFunding: { flex: 1, fontSize: 11, textAlign: 'right' },
    wlOi: { flex: 1, fontSize: 11, color: colors.textMuted || '#94a3b8', textAlign: 'right' },
    footer: { textAlign: 'center', fontSize: 11, color: colors.textMuted || '#64748b', marginTop: 16 },
  });
