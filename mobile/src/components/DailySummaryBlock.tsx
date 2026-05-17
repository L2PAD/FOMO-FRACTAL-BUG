import React, { useEffect, useState, useRef } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Animated } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '../core/theme';
import { useColors } from '../core/useColors';
import { openPaywall } from '../utils/paywall-controller';
import { useSessionStore } from '../stores/session.store';
import { mobileApi } from '../services/api/mobile-api';
import { useAssetStore } from '../stores/asset.store';

interface DailySummary {
  asset: string;
  date: string;
  bias: string;
  confidence: number;
  price: number;
  change24h: number;
  marketState: string;
  signalsToday: number;
  closedToday: number;
  winsToday: number;
  lossesToday: number;
  totalPnlToday: number;
  bestMove: { asset: string; action: string; pnlPct: number; confidence: number; horizon: string } | null;
  topReason: string | null;
  missedTeaser: { count: number; avgMovePct: number } | null;
  lockedInsights: number;
  summaryText: string;
  freeTeaser: string | null;
  proSummary: string | null;
}

export function DailySummaryBlock() {
  const colors = useColors();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);

  const currentAsset = useAssetStore((s) => s.currentAsset);
  const user = useSessionStore((s) => s.user);
  const isPro = user?.plan === 'PRO' || user?.plan === 'INSTITUTIONAL';

  const [summary, setSummary] = useState<DailySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const fadeAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    const fetchSummary = async () => {
      try {
        const res = await mobileApi.getDailySummary(currentAsset);
        if (!cancelled) {
          setSummary(res as DailySummary);
          Animated.timing(fadeAnim, {
            toValue: 1,
            duration: 400,
            useNativeDriver: true,
          }).start();
        }
      } catch (e) {
        // Silent fail
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchSummary();
    return () => { cancelled = true; };
  }, [currentAsset]);

  if (loading) {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <Ionicons name="today-outline" size={13} color={colors.accent} />
          <Text style={styles.headerTitle}>DAILY SUMMARY</Text>
        </View>
        <Text style={styles.loadingText}>Loading today's recap...</Text>
      </View>
    );
  }

  if (!summary || summary.signalsToday === 0) {
    return null;
  }

  const biasColor = summary.bias === 'BUY' ? colors.buy
    : summary.bias === 'SELL' ? colors.sell
    : colors.wait;

  const stateEmoji = summary.marketState === 'VOLATILE' ? 'V'
    : summary.marketState === 'TRENDING' ? 'T'
    : summary.marketState === 'RANGING' ? 'R'
    : 'C';

  return (
    <Animated.View style={[styles.container, { opacity: fadeAnim }]}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Ionicons name="today-outline" size={13} color={colors.accent} />
          <Text style={styles.headerTitle}>DAILY SUMMARY</Text>
        </View>
        <Text style={styles.dateText}>{summary.date}</Text>
      </View>

      {/* Main Bias */}
      <View style={styles.biasRow}>
        <View style={[styles.biasBadge, { backgroundColor: biasColor + '20', borderColor: biasColor + '40' }]}>
          <Text style={[styles.biasText, { color: biasColor }]}>
            {summary.bias}
          </Text>
          <Text style={[styles.confText, { color: biasColor }]}>
            {Math.round(summary.confidence * 100)}%
          </Text>
        </View>
        <View style={styles.stateContainer}>
          <Text style={styles.stateLabel}>MARKET</Text>
          <Text style={styles.stateValue}>{summary.marketState}</Text>
        </View>
      </View>

      {/* Metrics Row */}
      <View style={styles.metricsRow}>
        <View style={styles.metricItem}>
          <Text style={styles.metricValue}>{summary.signalsToday}</Text>
          <Text style={styles.metricLabel}>Signals</Text>
        </View>
        <View style={styles.metricDivider} />
        <View style={styles.metricItem}>
          <Text style={[styles.metricValue, { color: colors.buy }]}>{summary.winsToday}</Text>
          <Text style={styles.metricLabel}>Wins</Text>
        </View>
        <View style={styles.metricDivider} />
        <View style={styles.metricItem}>
          <Text style={[styles.metricValue, { color: colors.sell }]}>{summary.lossesToday}</Text>
          <Text style={styles.metricLabel}>Losses</Text>
        </View>
        {summary.totalPnlToday !== 0 && (
          <>
            <View style={styles.metricDivider} />
            <View style={styles.metricItem}>
              <Text style={[styles.metricValue, {
                color: summary.totalPnlToday > 0 ? colors.buy : colors.sell,
              }]}>
                {summary.totalPnlToday > 0 ? '+' : ''}{summary.totalPnlToday}%
              </Text>
              <Text style={styles.metricLabel}>PnL</Text>
            </View>
          </>
        )}
      </View>

      {/* Best Move */}
      {summary.bestMove && (
        <View style={styles.bestMoveRow}>
          <Text style={styles.bestMoveLabel}>Best move</Text>
          <Text style={[styles.bestMoveValue, { color: colors.buy }]}>
            {summary.bestMove.action} +{summary.bestMove.pnlPct}%
          </Text>
        </View>
      )}

      {/* Top Reason */}
      {summary.topReason && (
        <View style={styles.reasonRow}>
          <Ionicons name="bulb-outline" size={12} color={colors.accent} />
          <Text style={styles.reasonText} numberOfLines={2}>
            {summary.topReason}
          </Text>
        </View>
      )}

      {/* FREE Teaser */}
      {!isPro && summary.freeTeaser && (
        <TouchableOpacity style={styles.teaserRow} onPress={openPaywall}>
          <Ionicons name="lock-closed" size={12} color={colors.sell} />
          <Text style={styles.teaserText} numberOfLines={1}>
            {summary.freeTeaser}
          </Text>
          <Ionicons name="chevron-forward" size={14} color={colors.accent} />
        </TouchableOpacity>
      )}

      {/* PRO Extended Summary */}
      {isPro && summary.proSummary && (
        <View style={styles.proRow}>
          <Text style={styles.proText}>{summary.proSummary}</Text>
        </View>
      )}
    </Animated.View>
  );
}

const makeStyles = (colors: any) => StyleSheet.create({
  container: {
    backgroundColor: colors.card || colors.surface,
    borderRadius: theme.radius.lg,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.accent + '20',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  headerTitle: {
    color: colors.accent,
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 1.5,
  },
  dateText: {
    color: colors.textMuted,
    fontSize: 10,
  },
  biasRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  biasBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: theme.radius.sm,
    borderWidth: 1,
  },
  biasText: {
    fontSize: 18,
    fontWeight: '900',
    letterSpacing: 1,
  },
  confText: {
    fontSize: 14,
    fontWeight: '700',
  },
  stateContainer: {
    alignItems: 'flex-end',
  },
  stateLabel: {
    color: colors.textMuted,
    fontSize: 9,
    fontWeight: '600',
    letterSpacing: 1,
  },
  stateValue: {
    color: colors.textPrimary,
    fontSize: 12,
    fontWeight: '700',
    marginTop: 2,
  },
  metricsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    borderRadius: theme.radius.sm,
    paddingVertical: 8,
    paddingHorizontal: 12,
    marginBottom: 10,
  },
  metricItem: {
    alignItems: 'center',
    flex: 1,
  },
  metricValue: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: '800',
  },
  metricLabel: {
    color: colors.textMuted,
    fontSize: 9,
    fontWeight: '600',
    marginTop: 2,
  },
  metricDivider: {
    width: 1,
    height: 20,
    backgroundColor: colors.border,
    marginHorizontal: 8,
  },
  bestMoveRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  bestMoveLabel: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: '600',
  },
  bestMoveValue: {
    fontSize: 13,
    fontWeight: '800',
  },
  reasonRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 6,
    marginBottom: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  reasonText: {
    color: colors.textSecondary,
    fontSize: 11,
    flex: 1,
    lineHeight: 16,
  },
  teaserRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  teaserText: {
    color: colors.sell,
    fontSize: 11,
    fontWeight: '600',
    flex: 1,
  },
  proRow: {
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  proText: {
    color: colors.textSecondary,
    fontSize: 10,
    lineHeight: 14,
  },
  loadingText: {
    color: colors.textMuted,
    fontSize: 12,
    marginTop: 2,
  },
});
