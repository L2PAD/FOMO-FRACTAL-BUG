import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Pressable,
  RefreshControl,
  ActivityIndicator,
  Animated,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { mobileApi } from '../../../services/api/mobile-api';
import { useSessionStore } from '../../../stores/session.store';
import { useColors } from '../../../core/useColors';
import { openPaywall } from '../../../utils/paywall-controller';
import { SignalDetailScreen } from './SignalDetailScreen';
import { trackAction } from '../../../hooks/useTracker';
import SignalStateBadge from '../../../components/SignalStateBadge';
import { TradingBridgeCTA } from '../../../widgets/trading-bridge/TradingBridgeCTA';
import { CognitiveAnchor } from '../../../widgets/cognition/CognitiveAnchor';
import { BusPulse } from '../../../widgets/cognition/bus/cognitiveBus';
import { MetaBrainIdentityStrip } from '../../../widgets/trading-bridge/MetaBrainIdentityStrip';

import { t } from '../../../core/i18n';
type Driver = {
  module: string;
  name: string;
  direction: string;
  confidence: number;
  weight: number;
  value: string;
  reason: string;
};

type Signal = {
  asset: string;
  action: 'BUY' | 'SELL' | 'WAIT';
  confidence: number;
  score: number;
  direction: string;
  horizon: string;
  price: number | null;
  drivers: Driver[];
  driverSummary: { bullish: number; bearish: number; neutral: number };
  summary: string;
  entryZone: string | null;
  takeProfit: string | null;
  stopLoss: string | null;
  updatedAt: string;
  // Event metadata
  eventTitle?: string;
  stateLabel?: string;
  isNew?: boolean;
  confInterpretation?: string;
  scarcityText?: string;
  timelineText?: string;
  lossText?: string;
  weeklySignalCount?: number;
  signalAgeHours?: number | null;
};

const HORIZONS = ['swing', 'intraday', 'macro'] as const;
const ASSET_FILTERS = ['All', 'BTC', 'ETH', 'Alts'] as const;

export function SignalsScreen() {
  const colors = useColors();
  const s = React.useMemo(() => makeStyles(colors), [colors]);
  const user = useSessionStore((st) => st.user);

  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [horizon, setHorizon] = useState<string>('swing');
  const [assetFilter, setAssetFilter] = useState<string>('All');
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);

  const fetchSignals = async () => {
    try {
      const result = await mobileApi.getSignals(horizon);
      if (result.ok && result.signals) {
        setSignals(result.signals);
      }
    } catch (e) {
      console.error('Signals fetch error:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchSignals();
  }, [horizon]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchSignals();
    setRefreshing(false);
  }, [horizon]);

  const filteredSignals = signals.filter((sig) => {
    if (assetFilter === 'All') return true;
    if (assetFilter === 'Alts') return !['BTC', 'ETH'].includes(sig.asset);
    return sig.asset === assetFilter;
  });

  // Sort: active signals (BUY/SELL) first, then by confidence
  const sortedSignals = [...filteredSignals].sort((a, b) => {
    const aActive = a.action !== 'WAIT' ? 1 : 0;
    const bActive = b.action !== 'WAIT' ? 1 : 0;
    if (aActive !== bActive) return bActive - aActive;
    return b.confidence - a.confidence;
  });

  const onSignalClick = useCallback((signal: Signal) => {
    // Track signal click
    trackAction('signal_click', {
      symbol: signal.asset,
      verdict: signal.action,
      confidence: signal.confidence,
      stateLabel: signal.stateLabel,
    });
    setSelectedSignal(signal);
  }, []);

  // Signal Detail overlay
  if (selectedSignal) {
    return (
      <SignalDetailScreen
        signal={selectedSignal}
        onClose={() => setSelectedSignal(null)}
      />
    );
  }

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator size="large" color={colors.accent} />
        <Text style={[s.loadingText, { color: colors.textMuted }]}>{t('intelSignals.scanningMarkets')}</Text>
      </View>
    );
  }

  // Count active signals
  const activeCount = sortedSignals.filter(sg => sg.action !== 'WAIT').length;

  return (
    <ScrollView
      style={s.container}
      stickyHeaderIndices={[0]}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
      showsVerticalScrollIndicator={false}
    >
      {/* ITERATION 4·γ · cognition dialect — Signals = AI introspecting modules */}
      <BusPulse energy="dormant" amount={0.35} />
      <CognitiveAnchor
        cognition="INTROSPECTING"
        capital="OBSERVING"
        colors={colors}
      />

      {/* Header */}
      <View style={s.header}>
        <Text style={[s.title, { color: colors.textPrimary }]}>SIGNALS</Text>
        <Text style={[s.subtitle, { color: colors.textMuted }]}>
          {activeCount > 0
            ? `${activeCount} active signal${activeCount > 1 ? 's' : ''} detected`
            : 'All modules scanning — no edge yet'}
        </Text>
      </View>

      {/* PHASE X · Trading bridge */}
      <View style={{ paddingHorizontal: 16 }}>
        <MetaBrainIdentityStrip variant="compact" tappable />
        <TradingBridgeCTA
          variant="watch-execution"
          customSub="see how AI fuses these signals into a verdict"
        />
      </View>

      {/* Filters */}
      <View style={s.filtersWrap}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.filterRow}>
          {HORIZONS.map((h) => (
            <TouchableOpacity
              key={h}
              style={[
                s.chip,
                { borderColor: horizon === h ? colors.accent : colors.border },
                horizon === h && { backgroundColor: colors.accent + '18' },
              ]}
              onPress={() => setHorizon(h)}
            >
              <Text style={[s.chipText, { color: horizon === h ? colors.accent : colors.textMuted }]}>
                {h.charAt(0).toUpperCase() + h.slice(1)}
              </Text>
            </TouchableOpacity>
          ))}
          <View style={{ width: 12 }} />
          {ASSET_FILTERS.map((f) => (
            <TouchableOpacity
              key={f}
              style={[
                s.chip,
                { backgroundColor: assetFilter === f ? colors.accent : 'transparent', borderColor: assetFilter === f ? colors.accent : colors.border },
              ]}
              onPress={() => setAssetFilter(f)}
            >
              <Text style={[s.chipText, { color: assetFilter === f ? '#fff' : colors.textMuted }]}>
                {f}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      {/* Signal Event Cards */}
      {sortedSignals.map((signal) => (
        <SignalEventCard
          key={signal.asset}
          signal={signal}
          colors={colors}
          s={s}
          onPress={onSignalClick}
        />
      ))}

      {sortedSignals.length === 0 && (
        <View style={s.emptyState}>
          <Ionicons name="flash-off" size={48} color={colors.textMuted} />
          <Text style={[s.emptyText, { color: colors.textMuted }]}>{t('intelSignals.noSignalsForThisFilter')}</Text>
        </View>
      )}

      <View style={{ height: 32 }} />
    </ScrollView>
  );
}


/* ═══════════════════════════════════════
   SIGNAL EVENT CARD — The core upgrade
   Signal = Event, not data
   ═══════════════════════════════════════ */

function SignalEventCard({
  signal,
  colors,
  s,
  onPress,
}: {
  signal: Signal;
  colors: any;
  s: any;
  onPress: (sig: Signal) => void;
}) {
  const isActive = signal.action !== 'WAIT';
  const ac = signal.action === 'BUY' ? colors.buy : signal.action === 'SELL' ? colors.sell : colors.textMuted;
  const bull = signal.driverSummary?.bullish || 0;
  const bear = signal.driverSummary?.bearish || 0;
  const totalAligned = bull + bear;

  // Track signal_view when card mounts
  const viewTracked = useRef(false);
  useEffect(() => {
    if (!viewTracked.current) {
      viewTracked.current = true;
      trackAction('signal_view', {
        symbol: signal.asset,
        verdict: signal.action,
        confidence: signal.confidence,
        stateLabel: signal.stateLabel,
        mode: 'shadow',
      });
    }
  }, []);

  // Pulse animation for active signals
  const pulseAnim = useRef(new Animated.Value(1)).current;
  useEffect(() => {
    if (isActive) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, { toValue: 1.02, duration: 1800, useNativeDriver: true }),
          Animated.timing(pulseAnim, { toValue: 1, duration: 1800, useNativeDriver: true }),
        ])
      ).start();
    }
  }, [isActive]);

  return (
    <Pressable onPress={() => onPress(signal)}>
      <Animated.View
        style={[
          s.card,
          {
            borderLeftColor: ac,
            borderLeftWidth: isActive ? 4 : 2,
            transform: isActive ? [{ scale: pulseAnim }] : [],
          },
        ]}
      >
        {/* ── Row 0: Stage state badge (FORMING / CONFIRMED / BREAKING DOWN) ── */}
        <View style={s.badgeRow}>
          <SignalStateBadge
            stage={(signal as any).stage || (signal as any).decisionFramework?.stage}
            action={signal.action}
            direction={signal.direction}
            isActive={isActive}
            timelineText={signal.timelineText}
            compact
          />
        </View>

        {/* ── Row 1: Event Title (the big shift) ── */}
        <Text style={[
          s.eventTitle,
          { color: isActive ? colors.textPrimary : colors.textMuted },
        ]}>
          {signal.eventTitle || `${signal.asset} — ${signal.action}`}
        </Text>

        {/* ── Row 2: Verdict + Price ── */}
        <View style={s.verdictRow}>
          <View style={[s.verdictBadge, { backgroundColor: ac + '18' }]}>
            <Text style={[s.verdictText, { color: ac }]}>{signal.action}</Text>
          </View>
          {signal.price != null && (
            <Text style={[s.priceText, { color: colors.textSecondary }]}>
              ${signal.price.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </Text>
          )}
          {/* Confidence interpretation instead of raw % */}
          <Text style={[s.confInterp, { color: ac }]} numberOfLines={1}>
            {signal.confInterpretation || `${Math.round(signal.confidence * 100)}%`}
          </Text>
        </View>

        {/* ── Row 3: Confidence bar (compact) ── */}
        <View style={s.confBarRow}>
          <View style={[s.confBarBg, { backgroundColor: colors.border }]}>
            <View style={[s.confBarFill, { width: `${Math.round(signal.confidence * 100)}%`, backgroundColor: ac }]} />
          </View>
          <Text style={[s.confPct, { color: ac }]}>{Math.round(signal.confidence * 100)}%</Text>
        </View>

        {/* ── Row 4: Module alignment chips ── */}
        {totalAligned > 0 && (
          <View style={s.alignRow}>
            {bull > 0 && (
              <View style={[s.alignChip, { backgroundColor: colors.buy + '12' }]}>
                <Text style={[s.alignText, { color: colors.buy }]}>{bull}/{bull + bear + (signal.driverSummary?.neutral || 0)} aligned</Text>
              </View>
            )}
            {bear > 0 && (
              <View style={[s.alignChip, { backgroundColor: colors.sell + '12' }]}>
                <Ionicons name="arrow-down" size={10} color={colors.sell} />
                <Text style={[s.alignText, { color: colors.sell }]}>{bear} bearish</Text>
              </View>
            )}
          </View>
        )}

        {/* ── Row 5: TRUTH STRIP — system performance ── */}
        {signal.truth && !signal.truth.learning && signal.truth.totalTrades > 0 ? (
          <View style={[s.truthStrip, { backgroundColor: colors.surface }]}>
            <Text style={[s.truthText, { color: colors.textMuted }]}>
              Last {signal.truth.totalTrades} signals: {Math.round(signal.truth.winRate * 100)}% profitable
            </Text>
            {signal.truth.streak > 0 ? (
              <Text style={[s.truthStreak, { color: colors.buy }]}>
                {signal.truth.streak} win streak
              </Text>
            ) : signal.truth.streak < 0 ? (
              <Text style={[s.truthStreak, { color: colors.textMuted }]}>
                Next setup forming
              </Text>
            ) : null}
          </View>
        ) : signal.truth?.learning ? (
          <View style={[s.truthStrip, { backgroundColor: colors.surface }]}>
            <Text style={[s.truthText, { color: colors.textMuted }]}>
              System learning — first outcomes soon
            </Text>
          </View>
        ) : null}

        {/* ── Row 5b: Recent outcomes chips ── */}
        {signal.truth?.recent && signal.truth.recent.length > 0 ? (
          <View style={s.outcomesRow}>
            {signal.truth.recent.slice(0, 5).map((pnl: number, i: number) => (
              <View key={i} style={[s.outcomeChip, { backgroundColor: pnl > 0 ? colors.buy + '15' : colors.sell + '15' }]}>
                <Text style={[s.outcomeText, { color: pnl > 0 ? colors.buy : colors.sell }]}>
                  {pnl > 0 ? '+' : ''}{pnl}%
                </Text>
              </View>
            ))}
          </View>
        ) : null}

        {/* ── Row 6: Meta line — Scarcity ── */}
        {signal.scarcityText && isActive ? (
          <View style={[s.metaLine, { backgroundColor: colors.surface }]}>
            <Ionicons name="diamond-outline" size={11} color={colors.accent} />
            <Text style={[s.metaText, { color: colors.textMuted }]}>{signal.scarcityText}</Text>
          </View>
        ) : null}

        {/* ── Row 6: Loss aversion footer (only for active signals) ── */}
        {signal.lossText && isActive ? (
          <Text style={[s.lossFooter, { color: colors.sell + 'CC' }]}>
            {signal.lossText}
          </Text>
        ) : null}

        {/* ── Row 7: Drivers mini + arrow ── */}
        <View style={s.driversRow}>
          {signal.drivers.slice(0, 4).map((d) => {
            const dc = d.direction === 'Bullish' ? colors.buy : d.direction === 'Bearish' ? colors.sell : colors.textMuted;
            return (
              <View key={d.module} style={s.miniDriver}>
                <View style={[s.miniDot, { backgroundColor: dc }]} />
                <Text style={[s.miniName, { color: colors.textMuted }]}>{d.name.slice(0, 5)}</Text>
              </View>
            );
          })}
          <Ionicons name="chevron-forward" size={14} color={colors.textMuted} style={{ marginLeft: 'auto' }} />
        </View>
      </Animated.View>
    </Pressable>
  );
}


/* ═══════════ STYLES ═══════════ */

const makeStyles = (colors: any) =>
  StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background },
    center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
    loadingText: { marginTop: 12, fontSize: 14 },
    header: { paddingHorizontal: 16, paddingTop: 16, paddingBottom: 4 },
    title: { fontSize: 24, fontWeight: '800', letterSpacing: 1 },
    subtitle: { fontSize: 13, marginTop: 2 },
    filtersWrap: { marginTop: 8, marginBottom: 4 },
    filterRow: { paddingHorizontal: 16, gap: 8, flexDirection: 'row', alignItems: 'center' },
    chip: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 16, borderWidth: 1 },
    chipText: { fontSize: 12, fontWeight: '600' },

    /* ── Signal Event Card ── */
    card: {
      marginHorizontal: 16,
      marginVertical: 6,
      backgroundColor: colors.surface,
      borderRadius: 14,
      padding: 14,
      borderWidth: 1,
      borderColor: 'transparent',
    },

    /* Badge row */
    badgeRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      marginBottom: 8,
    },
    newBadge: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 5,
      paddingHorizontal: 8,
      paddingVertical: 3,
      borderRadius: 6,
    },
    liveDot: {
      width: 6,
      height: 6,
      borderRadius: 3,
    },
    newBadgeText: {
      fontSize: 9,
      fontWeight: '800',
      letterSpacing: 1.2,
    },
    timelineText: {
      fontSize: 10,
      fontWeight: '500',
    },

    /* Event title */
    eventTitle: {
      fontSize: 16,
      fontWeight: '800',
      lineHeight: 22,
      marginBottom: 6,
    },

    /* Verdict row */
    verdictRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
      marginBottom: 6,
    },
    verdictBadge: {
      paddingHorizontal: 10,
      paddingVertical: 3,
      borderRadius: 6,
    },
    verdictText: {
      fontSize: 12,
      fontWeight: '800',
      letterSpacing: 0.5,
    },
    priceText: {
      fontSize: 13,
      fontWeight: '600',
    },
    confInterp: {
      fontSize: 11,
      fontWeight: '600',
      flex: 1,
      textAlign: 'right',
    },

    /* Confidence bar */
    confBarRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
      marginBottom: 6,
    },
    confBarBg: {
      flex: 1,
      height: 3,
      borderRadius: 2,
      overflow: 'hidden',
    },
    confBarFill: {
      height: '100%',
      borderRadius: 2,
    },
    confPct: {
      fontSize: 11,
      fontWeight: '700',
      width: 30,
      textAlign: 'right',
    },

    /* Alignment chips */
    alignRow: {
      flexDirection: 'row',
      gap: 6,
      marginBottom: 6,
    },
    alignChip: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 3,
      paddingHorizontal: 8,
      paddingVertical: 3,
      borderRadius: 8,
    },
    alignText: {
      fontSize: 10,
      fontWeight: '600',
    },

    /* Meta line (scarcity) */
    metaLine: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 5,
      paddingHorizontal: 8,
      paddingVertical: 5,
      borderRadius: 6,
      marginBottom: 6,
    },
    metaText: {
      fontSize: 10,
      fontWeight: '500',
    },

    /* Loss aversion footer */
    lossFooter: {
      fontSize: 10,
      fontWeight: '600',
      fontStyle: 'italic',
      marginBottom: 6,
    },

    /* Drivers mini */
    driversRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 10,
      marginTop: 2,
    },
    miniDriver: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 3,
    },
    miniDot: {
      width: 5,
      height: 5,
      borderRadius: 2.5,
    },
    miniName: {
      fontSize: 10,
      fontWeight: '500',
    },

    /* Truth strip */
    truthStrip: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingHorizontal: 8,
      paddingVertical: 5,
      borderRadius: 6,
      marginBottom: 6,
    },
    truthText: {
      fontSize: 10,
      fontWeight: '500',
    },
    truthStreak: {
      fontSize: 10,
      fontWeight: '700',
    },
    outcomesRow: {
      flexDirection: 'row',
      gap: 4,
      marginBottom: 6,
    },
    outcomeChip: {
      paddingHorizontal: 6,
      paddingVertical: 2,
      borderRadius: 4,
    },
    outcomeText: {
      fontSize: 9,
      fontWeight: '700',
    },

    /* Empty */
    emptyState: { alignItems: 'center', paddingTop: 60 },
    emptyText: { fontSize: 14, marginTop: 12 },
  });
