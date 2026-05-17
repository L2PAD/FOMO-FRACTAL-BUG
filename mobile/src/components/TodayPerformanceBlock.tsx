import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '../core/theme';
import { useColors } from '../core/useColors';
import { openPaywall } from '../utils/paywall-controller';
import { useSessionStore } from '../stores/session.store';

interface TodayData {
  signalsToday: number;
  closedToday: number;
  totalMove: number;
  winsToday: number;
  openSignals: number;
  missedCount: number;
  missedMove: number;
  missedSignals: { asset: string; action: string; pnlPct: number }[];
}

interface Props {
  data: TodayData | null;
}

export function TodayPerformanceBlock({ data }: Props) {
  const colors = useColors();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);

  const user = useSessionStore((s) => s.user);
  const isPro = user?.plan === 'PRO' || user?.plan === 'INSTITUTIONAL';

  if (!data || (data.signalsToday === 0 && data.closedToday === 0 && data.openSignals === 0)) {
    return null;
  }

  return (
    <View style={styles.container}>
      {/* Today stats */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Ionicons name="today" size={13} color={colors.accent} />
          <Text style={styles.headerTitle}>TODAY</Text>
        </View>
        <Text style={styles.headerRight}>
          {data.openSignals > 0 ? `${data.openSignals} live` : ''}
        </Text>
      </View>

      <View style={styles.statsRow}>
        <View style={styles.statItem}>
          <Text style={styles.statValue}>{data.signalsToday}</Text>
          <Text style={styles.statLabel}>Signals</Text>
        </View>
        <View style={styles.statDivider} />
        <View style={styles.statItem}>
          <Text style={[styles.statValue, { color: colors.buy }]}>
            {data.totalMove > 0 ? `+${data.totalMove}%` : '0%'}
          </Text>
          <Text style={styles.statLabel}>Total Move</Text>
        </View>
        <View style={styles.statDivider} />
        <View style={styles.statItem}>
          <Text style={[styles.statValue, { color: data.winsToday > 0 ? colors.buy : colors.textMuted }]}>
            {data.winsToday}
          </Text>
          <Text style={styles.statLabel}>Wins</Text>
        </View>
      </View>

      {/* Missed signals for FREE users */}
      {!isPro && data.missedCount > 0 && (
        <TouchableOpacity style={styles.missedRow} onPress={openPaywall} activeOpacity={0.7}>
          <Ionicons name="alert-circle" size={14} color={colors.sell} />
          <Text style={styles.missedText}>
            You missed {data.missedCount} signal{data.missedCount > 1 ? 's' : ''} today
            {data.missedMove > 0 ? ` (+${data.missedMove}%)` : ''}
          </Text>
          <Ionicons name="chevron-forward" size={14} color={colors.sell} />
        </TouchableOpacity>
      )}

      {/* Show missed signal details */}
      {!isPro && data.missedSignals.length > 0 && (
        <View style={styles.missedList}>
          {data.missedSignals.map((s, i) => (
            <View key={i} style={styles.missedItem}>
              <Text style={styles.missedAsset}>{s.asset}</Text>
              <Text style={styles.missedAction}>{s.action}</Text>
              <Text style={[styles.missedPnl, { color: colors.buy }]}>+{s.pnlPct}%</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

const makeStyles = (colors: any) => StyleSheet.create({
  container: {
    backgroundColor: colors.card || colors.surface,
    borderRadius: theme.radius.lg,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.border,
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
  headerRight: {
    color: colors.buy,
    fontSize: 10,
    fontWeight: '600',
  },
  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  statItem: {
    flex: 1,
    alignItems: 'center',
  },
  statDivider: {
    width: 1,
    height: 24,
    backgroundColor: colors.border,
  },
  statValue: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.textPrimary,
  },
  statLabel: {
    fontSize: 9,
    color: colors.textMuted,
    marginTop: 1,
    fontWeight: '500',
    letterSpacing: 0.5,
  },
  missedRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    marginTop: 10,
  },
  missedText: {
    color: colors.sell,
    fontSize: 12,
    fontWeight: '600',
    flex: 1,
  },
  missedList: {
    marginTop: 6,
    gap: 4,
  },
  missedItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingLeft: 20,
  },
  missedAsset: {
    color: colors.textPrimary,
    fontSize: 12,
    fontWeight: '700',
    width: 36,
  },
  missedAction: {
    color: colors.textMuted,
    fontSize: 11,
    flex: 1,
  },
  missedPnl: {
    fontSize: 12,
    fontWeight: '700',
  },
});
