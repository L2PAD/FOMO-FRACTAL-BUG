import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '../../../core/theme';
import { useColors } from '../../../core/useColors';
import { api } from '../../../services/api/api-client';
import { useAssetStore } from '../../../stores/asset.store';
import { FeatureGate } from '../../../components/FeatureGate';
import { openPaywall } from '../../../utils/paywall-controller';

import { t } from '../../../core/i18n';
const ACCENT = '#2FE6A6';

interface OnchainData {
  asset: string;
  state: string;
  confidence: number;
  exchangeFlows: { netflow: number; trend: string; interpretation: string };
  whales: { txCount: number; trend: string; interpretation: string };
  supply: { onExchangesPct: number; deltaPct: number; interpretation: string };
  holders: { lthPct: number; trend: string; interpretation: string };
  activity: { activeAddressesPct: number; txPct: number; interpretation: string };
  interpretation: string[];
  signal: { strength: string; direction: string };
}

export function OnchainIntelScreen() {
  const colors = useColors();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);

  const [data, setData] = useState<OnchainData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const currentAsset = useAssetStore((s) => s.currentAsset);

  const fetchData = async () => {
    try {
      const res = await api.get(`/api/mobile/intel/onchain?asset=${currentAsset}`);
      setData(res.data);
    } catch (err) {
      console.error('On-chain intel error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { setLoading(true); fetchData(); }, [currentAsset]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  };

  if (loading || !data) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={ACCENT} />
      </View>
    );
  }

  const stateColor = data.state === 'ACCUMULATION' ? colors.buy : data.state === 'DISTRIBUTION' ? colors.sell : colors.neutral;

  return (
    <FeatureGate feature="deep_intel" onUnlock={openPaywall}>
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={ACCENT} />}
    >
      {/* Verdict */}
      <View style={styles.verdictCard}>
        <View style={styles.verdictRow}>
          <View>
            <Text style={styles.verdictAsset}>{data.asset}</Text>
            <Text style={[styles.verdictState, { color: stateColor }]}>{data.state}</Text>
          </View>
          <View style={styles.verdictConfidence}>
            <Text style={styles.confidenceValue}>{Math.round(data.confidence * 100)}%</Text>
            <Text style={styles.confidenceLabel}>confidence</Text>
          </View>
        </View>
        <View style={[styles.verdictBar, { backgroundColor: stateColor + '20' }]}>
          <View style={[styles.verdictBarFill, { width: `${data.confidence * 100}%`, backgroundColor: stateColor }]} />
        </View>
      </View>

      {/* Exchange Flows */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={[styles.iconContainer, { backgroundColor: ACCENT + '20' }]}>
            <Ionicons name="swap-vertical" size={16} color={ACCENT} />
          </View>
          <Text style={styles.cardTitle}>{t('intelDeep.exchangeNetflow')}</Text>
          <View style={[styles.trendBadge, { backgroundColor: (data.exchangeFlows.trend === 'outflow' ? colors.buy : colors.sell) + '20' }]}>
            <Text style={[styles.trendText, { color: data.exchangeFlows.trend === 'outflow' ? colors.buy : colors.sell }]}>
              {data.exchangeFlows.trend.toUpperCase()}
            </Text>
          </View>
        </View>
        <Text style={[styles.cardValue, { color: data.exchangeFlows.netflow < 0 ? colors.buy : colors.sell }]}>
          {data.exchangeFlows.netflow.toLocaleString()} BTC
        </Text>
        <Text style={styles.interpret}>{data.exchangeFlows.interpretation}</Text>
      </View>

      {/* Whale Activity */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={[styles.iconContainer, { backgroundColor: colors.neutral + '20' }]}>
            <Ionicons name="fish" size={16} color={colors.neutral} />
          </View>
          <Text style={styles.cardTitle}>{t('intelDeep.whaleActivity')}</Text>
          <View style={[styles.trendBadge, { backgroundColor: colors.neutral + '20' }]}>
            <Text style={[styles.trendText, { color: colors.neutral }]}>{data.whales.trend.toUpperCase()}</Text>
          </View>
        </View>
        <Text style={styles.cardValue}>{data.whales.txCount} transactions</Text>
        <Text style={styles.cardSubValue}>{'>'}$1M in last 24h</Text>
        <Text style={styles.interpret}>{data.whales.interpretation}</Text>
      </View>

      {/* Supply on Exchanges */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={[styles.iconContainer, { backgroundColor: colors.sell + '20' }]}>
            <Ionicons name="server" size={16} color={colors.sell} />
          </View>
          <Text style={styles.cardTitle}>{t('intelDeep.supplyOnExchanges')}</Text>
        </View>
        <Text style={styles.cardValue}>{data.supply.onExchangesPct}%</Text>
        <Text style={[styles.cardDelta, { color: data.supply.deltaPct < 0 ? colors.buy : colors.sell }]}>
          {"\u0394"} {data.supply.deltaPct}%
        </Text>
        {/* Visual gauge */}
        <View style={styles.gauge}>
          <View style={[styles.gaugeFill, { width: `${data.supply.onExchangesPct}%`, backgroundColor: colors.sell }]} />
        </View>
        <Text style={styles.interpret}>{data.supply.interpretation}</Text>
      </View>

      {/* Long-term Holders */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={[styles.iconContainer, { backgroundColor: colors.buy + '20' }]}>
            <Ionicons name="shield-checkmark" size={16} color={colors.buy} />
          </View>
          <Text style={styles.cardTitle}>{t('intelDeep.longTermHolders')}</Text>
        </View>
        <Text style={[styles.cardValue, { color: colors.buy }]}>{data.holders.lthPct}%</Text>
        <Text style={[styles.cardDelta, { color: colors.buy }]}>{data.holders.trend}</Text>
        {/* Visual gauge */}
        <View style={styles.gauge}>
          <View style={[styles.gaugeFill, { width: `${data.holders.lthPct}%`, backgroundColor: colors.buy }]} />
        </View>
        <Text style={styles.interpret}>{data.holders.interpretation}</Text>
      </View>

      {/* Network Activity */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={[styles.iconContainer, { backgroundColor: colors.accent + '20' }]}>
            <Ionicons name="pulse" size={16} color={colors.accent} />
          </View>
          <Text style={styles.cardTitle}>{t('intelDeep.networkActivity')}</Text>
        </View>
        <View style={styles.activityRow}>
          <View style={styles.activityItem}>
            <Text style={styles.activityLabel}>{t('intelDeep.activeAddresses')}</Text>
            <Text style={[styles.activityValue, { color: colors.buy }]}>+{data.activity.activeAddressesPct}%</Text>
          </View>
          <View style={styles.activityDivider} />
          <View style={styles.activityItem}>
            <Text style={styles.activityLabel}>Transactions</Text>
            <Text style={[styles.activityValue, { color: colors.buy }]}>+{data.activity.txPct}%</Text>
          </View>
        </View>
        <Text style={styles.interpret}>{data.activity.interpretation}</Text>
      </View>

      {/* Signal Summary */}
      <View style={[styles.summaryCard, { borderColor: stateColor + '40' }]}>
        <View style={styles.summaryHeader}>
          <Ionicons name="analytics" size={18} color={stateColor} />
          <Text style={[styles.summaryTitle, { color: stateColor }]}>
            {data.signal.strength} {data.signal.direction}
          </Text>
        </View>
        {data.interpretation.map((item, i) => (
          <View key={i} style={styles.summaryItem}>
            <Text style={[styles.summaryBullet, { color: stateColor }]}>+</Text>
            <Text style={styles.summaryText}>{item}</Text>
          </View>
        ))}
      </View>

      <View style={{ height: 24 }} />
    </ScrollView>
    </FeatureGate>
  );
}

const makeStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: theme.spacing.md },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.background },
  verdictCard: { backgroundColor: colors.surface, borderRadius: theme.radius.lg, padding: theme.spacing.lg, marginBottom: theme.spacing.md },
  verdictRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: theme.spacing.md },
  verdictAsset: { fontSize: theme.fontSize.lg, fontWeight: '700', color: colors.textPrimary },
  verdictState: { fontSize: theme.fontSize['2xl'], fontWeight: '800', marginTop: 2 },
  verdictConfidence: { alignItems: 'flex-end' },
  confidenceValue: { fontSize: theme.fontSize['3xl'], fontWeight: '800', color: colors.textPrimary },
  confidenceLabel: { fontSize: 10, color: colors.textMuted },
  verdictBar: { height: 4, borderRadius: 2, overflow: 'hidden' },
  verdictBarFill: { height: '100%', borderRadius: 2 },
  card: { backgroundColor: colors.surface, borderRadius: theme.radius.md, padding: theme.spacing.md, marginBottom: theme.spacing.sm },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: theme.spacing.sm, marginBottom: theme.spacing.sm },
  iconContainer: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  cardTitle: { fontSize: theme.fontSize.sm, fontWeight: '600', color: colors.textSecondary, flex: 1 },
  trendBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: theme.radius.full },
  trendText: { fontSize: 9, fontWeight: '700', letterSpacing: 0.5 },
  cardValue: { fontSize: theme.fontSize.xl, fontWeight: '700', color: colors.textPrimary, marginBottom: 2 },
  cardSubValue: { fontSize: theme.fontSize.sm, color: colors.textMuted, marginBottom: theme.spacing.xs },
  cardDelta: { fontSize: theme.fontSize.sm, fontWeight: '600', marginBottom: theme.spacing.sm },
  gauge: { height: 6, borderRadius: 3, backgroundColor: colors.surfaceHover, overflow: 'hidden', marginBottom: theme.spacing.sm },
  gaugeFill: { height: '100%', borderRadius: 3 },
  interpret: { fontSize: theme.fontSize.sm, color: colors.textMuted, lineHeight: 18, marginTop: theme.spacing.xs },
  activityRow: { flexDirection: 'row', alignItems: 'center', marginBottom: theme.spacing.sm },
  activityItem: { flex: 1, alignItems: 'center' },
  activityLabel: { fontSize: 10, color: colors.textMuted, marginBottom: 2 },
  activityValue: { fontSize: theme.fontSize.lg, fontWeight: '700' },
  activityDivider: { width: 1, height: 30, backgroundColor: colors.border },
  summaryCard: { backgroundColor: colors.surface, borderRadius: theme.radius.lg, padding: theme.spacing.lg, marginTop: theme.spacing.sm, borderWidth: 1 },
  summaryHeader: { flexDirection: 'row', alignItems: 'center', gap: theme.spacing.sm, marginBottom: theme.spacing.md },
  summaryTitle: { fontSize: theme.fontSize.lg, fontWeight: '800' },
  summaryItem: { flexDirection: 'row', gap: theme.spacing.sm, marginBottom: 4 },
  summaryBullet: { fontSize: theme.fontSize.base, fontWeight: '700', width: 14 },
  summaryText: { fontSize: theme.fontSize.sm, color: colors.textSecondary, flex: 1, lineHeight: 18 },
});
