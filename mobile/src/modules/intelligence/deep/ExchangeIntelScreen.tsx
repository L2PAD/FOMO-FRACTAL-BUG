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
interface ExchangeData {
  asset: string;
  bias: string;
  confidence: number;
  funding: { current: number; delta: number; trend: string; interpretation: string };
  openInterest: { value: number; deltaPct: number; interpretation: string };
  liquidations: { short: number; long: number; ratio: number; interpretation: string };
  orderFlow: { buyPct: number; sellPct: number; interpretation: string };
  interpretation: string[];
  signal: { strength: string; direction: string };
}

export function ExchangeIntelScreen() {
  const colors = useColors();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);

  const [data, setData] = useState<ExchangeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const currentAsset = useAssetStore((s) => s.currentAsset);

  const fetchData = async () => {
    try {
      const res = await api.get(`/api/mobile/intel/exchange?asset=${currentAsset}`);
      setData(res.data);
    } catch (err) {
      console.error('Exchange intel error:', err);
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
        <ActivityIndicator size="large" color={colors.buy} />
      </View>
    );
  }

  const biasColor = data.bias === 'BULLISH' ? colors.buy : data.bias === 'BEARISH' ? colors.sell : colors.neutral;

  return (
    <FeatureGate feature="deep_intel" onUnlock={openPaywall}>
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
    >
      {/* Verdict */}
      <View style={styles.verdictCard}>
        <View style={styles.verdictRow}>
          <View>
            <Text style={styles.verdictAsset}>{data.asset}</Text>
            <Text style={[styles.verdictBias, { color: biasColor }]}>{data.bias}</Text>
          </View>
          <View style={styles.verdictConfidence}>
            <Text style={styles.confidenceValue}>{Math.round(data.confidence * 100)}%</Text>
            <Text style={styles.confidenceLabel}>confidence</Text>
          </View>
        </View>
        <View style={[styles.verdictBar, { backgroundColor: biasColor + '20' }]}>
          <View style={[styles.verdictBarFill, { width: `${data.confidence * 100}%`, backgroundColor: biasColor }]} />
        </View>
      </View>

      {/* Funding */}
      <IntelCard
        icon="trending-up"
        iconColor={data.funding.delta > 0 ? colors.buy : colors.sell}
        title={t('intelDeep.fundingRate')}
        value={`${data.funding.current > 0 ? '+' : ''}${data.funding.current}%`}
        delta={`\u0394 ${data.funding.delta > 0 ? '+' : ''}${data.funding.delta}%`}
        deltaColor={data.funding.delta > 0 ? colors.buy : colors.sell}
        tag={data.funding.trend.toUpperCase()}
        tagColor={data.funding.trend === 'increasing' ? colors.buy : colors.sell}
        interpretation={data.funding.interpretation}
      />

      {/* Open Interest */}
      <IntelCard
        icon="layers"
        iconColor={data.openInterest.deltaPct > 0 ? colors.buy : colors.sell}
        title={t('intelDeep.openInterest')}
        value={`$${(data.openInterest.value / 1e9).toFixed(1)}B`}
        delta={`\u0394 ${data.openInterest.deltaPct > 0 ? '+' : ''}${data.openInterest.deltaPct}%`}
        deltaColor={data.openInterest.deltaPct > 0 ? colors.buy : colors.sell}
        interpretation={data.openInterest.interpretation}
      />

      {/* Liquidations */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={[styles.cardIconContainer, { backgroundColor: colors.sell + '20' }]}>
            <Ionicons name="flash" size={16} color={colors.sell} />
          </View>
          <Text style={styles.cardTitle}>Liquidations</Text>
          <Text style={styles.cardTag}>{data.liquidations.ratio}x ratio</Text>
        </View>
        <View style={styles.liqRow}>
          <View style={styles.liqItem}>
            <Text style={styles.liqLabel}>{t('intelDeep.shortLiq')}</Text>
            <Text style={[styles.liqValue, { color: colors.sell }]}>${(data.liquidations.short / 1e6).toFixed(0)}M</Text>
          </View>
          <View style={styles.liqDivider} />
          <View style={styles.liqItem}>
            <Text style={styles.liqLabel}>{t('intelDeep.longLiq')}</Text>
            <Text style={[styles.liqValue, { color: colors.buy }]}>${(data.liquidations.long / 1e6).toFixed(0)}M</Text>
          </View>
        </View>
        {/* Visual bar */}
        <View style={styles.liqBar}>
          <View style={[styles.liqBarShort, { flex: data.liquidations.short }]} />
          <View style={[styles.liqBarLong, { flex: data.liquidations.long }]} />
        </View>
        <Text style={styles.interpretation}>{data.liquidations.interpretation}</Text>
      </View>

      {/* Order Flow */}
      {data.orderFlow && (
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={[styles.cardIconContainer, { backgroundColor: colors.accent + '20' }]}>
              <Ionicons name="swap-horizontal" size={16} color={colors.accent} />
            </View>
            <Text style={styles.cardTitle}>{t('intelDeep.orderFlow')}</Text>
          </View>
          <View style={styles.flowRow}>
            <Text style={[styles.flowValue, { color: colors.buy }]}>Buy {data.orderFlow.buyPct}%</Text>
            <Text style={[styles.flowValue, { color: colors.sell }]}>Sell {data.orderFlow.sellPct}%</Text>
          </View>
          <View style={styles.flowBar}>
            <View style={[styles.flowBarBuy, { flex: data.orderFlow.buyPct }]} />
            <View style={[styles.flowBarSell, { flex: data.orderFlow.sellPct }]} />
          </View>
          <Text style={styles.interpretation}>{data.orderFlow.interpretation}</Text>
        </View>
      )}

      {/* Signal Summary */}
      <View style={[styles.summaryCard, { borderColor: biasColor + '40' }]}>
        <View style={styles.summaryHeader}>
          <Ionicons name="shield-checkmark" size={18} color={biasColor} />
          <Text style={[styles.summaryTitle, { color: biasColor }]}>
            {data.signal.strength} {data.signal.direction}
          </Text>
        </View>
        {data.interpretation.map((item, i) => (
          <View key={i} style={styles.summaryItem}>
            <Text style={[styles.summaryBullet, { color: biasColor }]}>{i < 3 ? '+' : '-'}</Text>
            <Text style={styles.summaryText}>{item}</Text>
          </View>
        ))}
      </View>

      <View style={{ height: 24 }} />
    </ScrollView>
    </FeatureGate>
  );
}

// Reusable Intel Card
function IntelCard({
  icon, iconColor, title, value, delta, deltaColor, tag, tagColor, interpretation,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  iconColor: string;
  title: string;
  value: string;
  delta: string;
  deltaColor: string;
  tag?: string;
  tagColor?: string;
  interpretation: string;
}) {
  const colors = useColors();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);
  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <View style={[styles.cardIconContainer, { backgroundColor: iconColor + '20' }]}>
          <Ionicons name={icon} size={16} color={iconColor} />
        </View>
        <Text style={styles.cardTitle}>{title}</Text>
        {tag && (
          <View style={[styles.tagBadge, { backgroundColor: (tagColor || colors.textMuted) + '20' }]}>
            <Text style={[styles.tagText, { color: tagColor || colors.textMuted }]}>{tag}</Text>
          </View>
        )}
      </View>
      <Text style={styles.cardValue}>{value}</Text>
      <Text style={[styles.cardDelta, { color: deltaColor }]}>{delta}</Text>
      <Text style={styles.interpretation}>{interpretation}</Text>
    </View>
  );
}

const makeStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: theme.spacing.md },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.background },

  // Verdict
  verdictCard: {
    backgroundColor: colors.surface,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.lg,
    marginBottom: theme.spacing.md,
  },
  verdictRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: theme.spacing.md },
  verdictAsset: { fontSize: theme.fontSize.lg, fontWeight: '700', color: colors.textPrimary },
  verdictBias: { fontSize: theme.fontSize['2xl'], fontWeight: '800', marginTop: 2 },
  verdictConfidence: { alignItems: 'flex-end' },
  confidenceValue: { fontSize: theme.fontSize['3xl'], fontWeight: '800', color: colors.textPrimary },
  confidenceLabel: { fontSize: 10, color: colors.textMuted },
  verdictBar: { height: 4, borderRadius: 2, overflow: 'hidden' },
  verdictBarFill: { height: '100%', borderRadius: 2 },

  // Card
  card: {
    backgroundColor: colors.surface,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
    marginBottom: theme.spacing.sm,
  },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: theme.spacing.sm, marginBottom: theme.spacing.sm },
  cardIconContainer: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  cardTitle: { fontSize: theme.fontSize.sm, fontWeight: '600', color: colors.textSecondary, flex: 1 },
  cardValue: { fontSize: theme.fontSize.xl, fontWeight: '700', color: colors.textPrimary, marginBottom: 2 },
  cardDelta: { fontSize: theme.fontSize.sm, fontWeight: '600', marginBottom: theme.spacing.sm },
  tagBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: theme.radius.full },
  tagText: { fontSize: 9, fontWeight: '700', letterSpacing: 0.5 },
  interpretation: { fontSize: theme.fontSize.sm, color: colors.textMuted, lineHeight: 18, marginTop: theme.spacing.xs },

  // Liquidations
  liqRow: { flexDirection: 'row', alignItems: 'center', marginBottom: theme.spacing.sm },
  liqItem: { flex: 1, alignItems: 'center' },
  liqLabel: { fontSize: 10, color: colors.textMuted, marginBottom: 2 },
  liqValue: { fontSize: theme.fontSize.lg, fontWeight: '700' },
  liqDivider: { width: 1, height: 30, backgroundColor: colors.border },
  liqBar: { flexDirection: 'row', height: 6, borderRadius: 3, overflow: 'hidden', marginBottom: theme.spacing.sm },
  liqBarShort: { backgroundColor: colors.sell, borderTopLeftRadius: 3, borderBottomLeftRadius: 3 },
  liqBarLong: { backgroundColor: colors.buy, borderTopRightRadius: 3, borderBottomRightRadius: 3 },

  // Order Flow
  flowRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: theme.spacing.xs },
  flowValue: { fontSize: theme.fontSize.base, fontWeight: '700' },
  flowBar: { flexDirection: 'row', height: 8, borderRadius: 4, overflow: 'hidden', marginBottom: theme.spacing.sm },
  flowBarBuy: { backgroundColor: colors.buy },
  flowBarSell: { backgroundColor: colors.sell },

  // Summary
  summaryCard: {
    backgroundColor: colors.surface,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.lg,
    marginTop: theme.spacing.sm,
    borderWidth: 1,
  },
  summaryHeader: { flexDirection: 'row', alignItems: 'center', gap: theme.spacing.sm, marginBottom: theme.spacing.md },
  summaryTitle: { fontSize: theme.fontSize.lg, fontWeight: '800' },
  summaryItem: { flexDirection: 'row', gap: theme.spacing.sm, marginBottom: 4 },
  summaryBullet: { fontSize: theme.fontSize.base, fontWeight: '700', width: 14 },
  summaryText: { fontSize: theme.fontSize.sm, color: colors.textSecondary, flex: 1, lineHeight: 18 },
});
