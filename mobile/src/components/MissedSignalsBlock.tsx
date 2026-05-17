import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '../core/theme';
import { useColors } from '../core/useColors';
import { openPaywall } from '../utils/paywall-controller';
import { useSessionStore } from '../stores/session.store';
import { MissedData } from '../services/api/mobile-api';

interface Props {
  data: MissedData | null;
  loading?: boolean;
}

export function MissedSignalsBlock({ data, loading }: Props) {
  const colors = useColors();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);

  const user = useSessionStore((s) => s.user);
  const isPro = user?.plan === 'PRO' || user?.plan === 'INSTITUTIONAL';

  // Loading state
  if (loading) {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <View style={styles.headerLeft}>
            <Ionicons name="eye-off" size={13} color={colors.sell} />
            <Text style={styles.headerTitle}>MISSED SIGNALS</Text>
          </View>
        </View>
        <Text style={styles.loadingText}>Checking missed opportunities...</Text>
      </View>
    );
  }

  // No data or empty
  if (!data || data.count === 0) {
    return null;
  }

  const first = data.items?.[0];

  return (
    <TouchableOpacity
      style={styles.container}
      onPress={isPro ? undefined : openPaywall}
      activeOpacity={isPro ? 1 : 0.7}
    >
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Ionicons name="eye-off" size={13} color={colors.sell} />
          <Text style={styles.headerTitle}>MISSED SIGNALS</Text>
        </View>
        <View style={styles.countBadge}>
          <Text style={styles.countText}>{data.count}</Text>
        </View>
      </View>

      {/* Main FOMO headline */}
      <View style={styles.headlineRow}>
        <Text style={styles.headlineText}>
          You missed {data.count} signal{data.count > 1 ? 's' : ''}
        </Text>
        <Text style={styles.headlineMove}>
          +{data.avgMovePct}% avg move
        </Text>
      </View>

      {/* Signal items */}
      {data.items.length > 0 && (
        <View style={styles.itemsList}>
          {data.items.map((item, index) => (
            <View key={item.id || index} style={styles.itemRow}>
              <View style={styles.itemLeft}>
                <View style={[
                  styles.actionDot,
                  { backgroundColor: item.action === 'BUY' ? colors.buy : colors.sell }
                ]} />
                <Text style={styles.itemAsset}>{item.asset}</Text>
                <Text style={styles.itemAction}>{item.action}</Text>
              </View>
              <View style={styles.itemRight}>
                <Text style={styles.itemConf}>
                  {Math.round(item.confidence * 100)}%
                </Text>
                <Text style={[
                  styles.itemPnl,
                  { color: item.pnlPct > 0 ? colors.buy : colors.sell }
                ]}>
                  {item.pnlPct > 0 ? '+' : ''}{item.pnlPct}%
                </Text>
              </View>
            </View>
          ))}
        </View>
      )}

      {/* CTA for FREE users */}
      {!isPro && (
        <View style={styles.ctaRow}>
          <Ionicons name="lock-closed" size={12} color={colors.accent} />
          <Text style={styles.ctaText}>Unlock early access</Text>
          <Ionicons name="chevron-forward" size={14} color={colors.accent} />
        </View>
      )}

      {/* PRO users see light context */}
      {isPro && first && (
        <View style={styles.proContext}>
          <Text style={styles.proContextText}>
            Last: {first.asset} {first.action} at ${first.entryPrice?.toLocaleString()} closed at ${first.closePrice?.toLocaleString()}
          </Text>
        </View>
      )}
    </TouchableOpacity>
  );
}

const makeStyles = (colors: any) => StyleSheet.create({
  container: {
    backgroundColor: colors.card || colors.surface,
    borderRadius: theme.radius.lg,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.sell + '30',
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
    color: colors.sell,
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 1.5,
  },
  countBadge: {
    backgroundColor: colors.sell + '20',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
  },
  countText: {
    color: colors.sell,
    fontSize: 11,
    fontWeight: '800',
  },
  headlineRow: {
    marginBottom: 10,
  },
  headlineText: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: '700',
  },
  headlineMove: {
    color: colors.sell,
    fontSize: 20,
    fontWeight: '900',
    marginTop: 2,
  },
  itemsList: {
    gap: 6,
    marginBottom: 10,
  },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.background,
    borderRadius: theme.radius.sm,
    paddingHorizontal: 10,
    paddingVertical: 7,
  },
  itemLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  actionDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  itemAsset: {
    color: colors.textPrimary,
    fontSize: 12,
    fontWeight: '700',
  },
  itemAction: {
    color: colors.textMuted,
    fontSize: 11,
  },
  itemRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  itemConf: {
    color: colors.textSecondary,
    fontSize: 10,
    fontWeight: '600',
  },
  itemPnl: {
    fontSize: 13,
    fontWeight: '800',
  },
  ctaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  ctaText: {
    color: colors.accent,
    fontSize: 12,
    fontWeight: '700',
    flex: 1,
  },
  proContext: {
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  proContextText: {
    color: colors.textMuted,
    fontSize: 10,
    lineHeight: 14,
  },
  loadingText: {
    color: colors.textMuted,
    fontSize: 12,
    marginTop: 2,
  },
});
