import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '../core/theme';
import { useColors } from '../core/useColors';
import { openPaywall } from '../utils/paywall-controller';
import { useSessionStore } from '../stores/session.store';
import { HistoryData } from '../services/api/mobile-api';

interface Props {
  data: HistoryData | null;
  loading: boolean;
}

export function TrackRecordBlock({ data, loading }: Props) {
  const colors = useColors();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);

  const user = useSessionStore((s) => s.user);
  const isPro = user?.plan === 'PRO' || user?.plan === 'INSTITUTIONAL';

  // 1. Loading state
  if (loading) {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <View style={styles.headerLeft}>
            <Ionicons name="trophy" size={14} color={colors.accent} />
            <Text style={styles.headerTitle}>TRACK RECORD</Text>
          </View>
        </View>
        <View style={styles.loadingBody}>
          <ActivityIndicator size="small" color={colors.accent} />
          <Text style={styles.loadingText}>Loading performance...</Text>
        </View>
      </View>
    );
  }

  // 2. Empty state
  if (!data || !data.stats || data.stats.total === 0) {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <View style={styles.headerLeft}>
            <Ionicons name="trophy" size={14} color={colors.accent} />
            <Text style={styles.headerTitle}>TRACK RECORD</Text>
          </View>
        </View>
        <View style={styles.emptyBody}>
          <Ionicons name="hourglass-outline" size={20} color={colors.textMuted} />
          <Text style={styles.emptyText}>Building performance history...</Text>
          <Text style={styles.emptySubtext}>Results appear after signals close</Text>
        </View>
      </View>
    );
  }

  const { stats, items, currentSignal } = data;

  // PRO lock: FREE users see first 2, PRO sees all
  const visibleItems = isPro ? items : items.slice(0, 2);
  const hiddenCount = items.length - 2;

  // Use reframed metrics for display
  const displayAccuracy = stats.highConfWinRate ?? stats.signalAccuracy ?? stats.winRate ?? 0;
  const displayMove = stats.avgMovePct ?? 0;
  const displayLast5 = stats.last5Move ?? 0;

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Ionicons name="trophy" size={14} color={colors.accent} />
          <Text style={styles.headerTitle}>TRACK RECORD</Text>
        </View>
        <View style={styles.badge}>
          <Text style={styles.badgeText}>{stats.total} signals</Text>
        </View>
      </View>

      {/* Stats row: Signal Accuracy | Avg Signal Move | High-Conf */}
      <View style={styles.statsRow}>
        <View style={styles.statItem}>
          <Text style={[styles.statValue, {
            color: displayAccuracy >= 55 ? colors.buy : colors.accent,
          }]}>
            {displayAccuracy > 0 ? `${displayAccuracy}%` : '\u2014'}
          </Text>
          <Text style={styles.statLabel}>Accuracy</Text>
        </View>
        <View style={styles.statDivider} />
        <View style={styles.statItem}>
          <Text style={[styles.statValue, { color: colors.buy }]}>
            {displayMove > 0 ? `+${displayMove}%` : '\u2014'}
          </Text>
          <Text style={styles.statLabel}>Avg Move</Text>
        </View>
        <View style={styles.statDivider} />
        <View style={styles.statItem}>
          <Text style={[styles.statValue, { color: colors.buy }]}>
            {displayLast5 > 0 ? `+${displayLast5}%` : '\u2014'}
          </Text>
          <Text style={styles.statLabel}>Last 5</Text>
        </View>
      </View>

      {/* Current open signal (LIVE) */}
      {currentSignal && (
        <View style={styles.currentSignal}>
          <View style={styles.liveDot} />
          <Text style={styles.currentText}>
            LIVE: {currentSignal.action} @ ${currentSignal.entryPrice?.toLocaleString()}
          </Text>
          <Text style={styles.currentConf}>{Math.round(currentSignal.confidence * 100)}%</Text>
        </View>
      )}

      {/* Signal list */}
      <View style={styles.signalsList}>
        {visibleItems.map((item, i) => (
          <View key={i} style={styles.signalRow}>
            <View style={styles.signalLeft}>
              <Text style={styles.outcomeIcon}>
                {item.outcome === 'WIN' ? '\uD83D\uDFE2' : item.outcome === 'LOSS' ? '\uD83D\uDD34' : '\u26AA'}
              </Text>
              <Text style={styles.signalAction}>{item.action}</Text>
              <Text style={styles.signalDuration}>{item.duration}</Text>
            </View>
            <Text style={[styles.signalPnl, {
              color: item.pnlPct >= 0 ? colors.buy : colors.sell,
            }]}>
              {item.pnlPct > 0 ? '+' : ''}{item.pnlPct}%
            </Text>
          </View>
        ))}
      </View>

      {/* PRO CTA: unlock full track record */}
      {!isPro && hiddenCount > 0 && (
        <TouchableOpacity style={styles.unlockRow} onPress={openPaywall} activeOpacity={0.7}>
          <Ionicons name="lock-closed" size={13} color={colors.accent} />
          <Text style={styles.unlockText}>
            Unlock full track record ({hiddenCount} more)
          </Text>
          <Ionicons name="chevron-forward" size={14} color={colors.accent} />
        </TouchableOpacity>
      )}

      {/* PRO: show remaining items */}
      {isPro && items.length > 2 && (
        <View style={[styles.signalsList, { marginTop: 6 }]}>
          {items.slice(2).map((item, i) => (
            <View key={i} style={styles.signalRow}>
              <View style={styles.signalLeft}>
                <Text style={styles.outcomeIcon}>
                  {item.outcome === 'WIN' ? '\uD83D\uDFE2' : item.outcome === 'LOSS' ? '\uD83D\uDD34' : '\u26AA'}
                </Text>
                <Text style={styles.signalAction}>{item.action}</Text>
                <Text style={styles.signalDuration}>{item.duration}</Text>
              </View>
              <Text style={[styles.signalPnl, {
                color: item.pnlPct >= 0 ? colors.buy : colors.sell,
              }]}>
                {item.pnlPct > 0 ? '+' : ''}{item.pnlPct}%
              </Text>
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
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 14,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  headerTitle: {
    color: colors.accent,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.5,
  },
  badge: {
    backgroundColor: colors.accent + '15',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
  },
  badgeText: {
    color: colors.accent,
    fontSize: 10,
    fontWeight: '600',
  },

  // Loading
  loadingBody: {
    alignItems: 'center',
    paddingVertical: 16,
    gap: 8,
  },
  loadingText: {
    color: colors.textMuted,
    fontSize: 12,
  },

  // Empty
  emptyBody: {
    alignItems: 'center',
    paddingVertical: 16,
    gap: 6,
  },
  emptyText: {
    color: colors.textSecondary,
    fontSize: 13,
    fontWeight: '600',
  },
  emptySubtext: {
    color: colors.textMuted,
    fontSize: 11,
  },

  // Stats
  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 14,
    paddingBottom: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  statItem: {
    flex: 1,
    alignItems: 'center',
  },
  statDivider: {
    width: 1,
    height: 30,
    backgroundColor: colors.border,
  },
  statValue: {
    fontSize: 18,
    fontWeight: '800',
    color: colors.textPrimary,
  },
  statLabel: {
    fontSize: 10,
    color: colors.textMuted,
    marginTop: 2,
    fontWeight: '500',
    letterSpacing: 0.5,
  },

  // Current signal
  currentSignal: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.accent + '10',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    marginBottom: 12,
    gap: 6,
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.buy,
  },
  currentText: {
    color: colors.textPrimary,
    fontSize: 12,
    fontWeight: '600',
    flex: 1,
  },
  currentConf: {
    color: colors.accent,
    fontSize: 12,
    fontWeight: '700',
  },

  // Signals list
  signalsList: {
    gap: 8,
  },
  signalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  signalLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  outcomeIcon: {
    fontSize: 12,
  },
  signalAction: {
    color: colors.textPrimary,
    fontSize: 13,
    fontWeight: '600',
  },
  signalDuration: {
    color: colors.textMuted,
    fontSize: 11,
  },
  signalPnl: {
    fontSize: 14,
    fontWeight: '700',
  },

  // Unlock CTA
  unlockRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingTop: 12,
    paddingBottom: 2,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    marginTop: 8,
  },
  unlockText: {
    color: colors.accent,
    fontSize: 12,
    fontWeight: '600',
    flex: 1,
  },
});
