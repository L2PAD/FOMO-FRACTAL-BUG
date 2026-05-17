/**
 * EdgeScreen — Early Money Engine
 * 
 * Edge = signal BEFORE signal.
 * 3 types: FLOW (capital), SOCIAL (attention), CATALYST (event)
 * 
 * Conversion path: Edge → curiosity → click → detail → locked → paywall
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { mobileApi } from '../../../services/api/mobile-api';
import { useColors } from '../../../core/useColors';
import { useSessionStore } from '../../../stores/session.store';
import { openPaywall } from '../../../utils/paywall-controller';
import { CoinIcon } from '../../../components/CoinIcon';
import { useTracker, trackAction } from '../../../hooks/useTracker';
import { useAppMode } from '../../../stores/app-mode.store';
import { hapticLight } from '../../../services/haptics.service';
import { track } from '../../../services/analytics';
import { canShareSignal, shareSignal } from '../../../services/share';
import { TradingBridgeCTA } from '../../../widgets/trading-bridge/TradingBridgeCTA';
import { CognitiveAnchor } from '../../../widgets/cognition/CognitiveAnchor';
import { BusPulse } from '../../../widgets/cognition/bus/cognitiveBus';
import { MetaBrainIdentityStrip } from '../../../widgets/trading-bridge/MetaBrainIdentityStrip';
import { useAssetStore } from '../../../stores/asset.store';
import { t } from '../../../core/i18n';
/* ─── types ─── */
type EdgeDriver = {
  icon: string;
  text: string;
  positive: boolean;
};

type EdgeOpportunity = {
  id: string;
  asset: string;
  type: 'FLOW' | 'SOCIAL' | 'CATALYST';
  badge: string;
  confidence: number;
  title: string;
  drivers: EdgeDriver[];
  tension: string;
  timing: string;
  signalLink: string | null;
  preMoveStarted: boolean;
  preMoveValue: string;
  detectedBefore: number;
  updatedAt: string;
};

/* ─── filter tabs ─── */
const FILTERS = [
  { key: 'ALL', label: 'All' },
  { key: 'FLOW', label: 'Whales' },
  { key: 'SOCIAL', label: 'Social' },
  { key: 'CATALYST', label: 'Events' },
  { key: 'PREDICTION', label: 'Polymarket' },
] as const;

type FilterKey = (typeof FILTERS)[number]['key'];

/* ─── component ─── */
export function EdgeScreen() {
  const colors = useColors();
  const insets = useSafeAreaInsets();
  const s = React.useMemo(() => makeStyles(colors), [colors]);
  const user = useSessionStore((st) => st.user);
  const isPro = user?.plan === 'PRO' || user?.plan === 'INSTITUTIONAL';
  // 🔥 Hero-entry context — set by HomeScreen on "Signal of the Moment" tap.
  // Powers reinforcement copy ("You're early on this setup") + paywall urgency.
  const heroEntry = useAppMode((st) => st.heroEntry);
  const clearHeroEntry = useAppMode((st) => st.clearHeroEntry);
  const asset = useAssetStore((st) => st.currentAsset);
  // Clear on unmount so next organic entry does NOT inherit stale context.
  useEffect(() => () => { clearHeroEntry(); }, [clearHeroEntry]);

  const [opportunities, setOpportunities] = useState<EdgeOpportunity[]>([]);
  const [predictionMarkets, setPredictionMarkets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<FilterKey>('ALL');
  const [selectedEdge, setSelectedEdge] = useState<EdgeOpportunity | null>(null);
  const [viewCount, setViewCount] = useState(0);

  // G1: track edge_open once when list screen mounts (with hero-entry context if present)
  useEffect(() => {
    track('edge_open', {
      asset: heroEntry?.asset || null,
      source: heroEntry?.type || null,
      priority: heroEntry?.priority || null,
      context: {
        screen: 'edge',
        from: heroEntry ? 'hero_entry' : 'organic',
        heroEntryAgeMs: heroEntry ? Date.now() - heroEntry.at : null,
      },
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchData = useCallback(async () => {
    try {
      const [edgeRes, predRes] = await Promise.all([
        mobileApi.getEdgeOpportunities(),
        mobileApi.getPredictionMarkets?.() || Promise.resolve({ markets: [] }),
      ]);
      if (edgeRes?.opportunities) setOpportunities(edgeRes.opportunities);
      if (predRes?.markets) setPredictionMarkets(predRes.markets);
    } catch {
      setOpportunities([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  }, [fetchData]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const filtered = filter === 'ALL'
    ? opportunities
    : opportunities.filter(o => o.type === filter);

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator size="large" color={colors.accent} />
        <Text style={[s.loadingText, { color: colors.textMuted }]}>{t('edge.scanningForOpportunities')}</Text>
      </View>
    );
  }

  // ─── EDGE DETAIL OVERLAY ───
  if (selectedEdge) {
    return (
      <EdgeDetailView
        edge={selectedEdge}
        isPro={isPro}
        colors={colors}
        onClose={() => setSelectedEdge(null)}
      />
    );
  }

  return (
    <ScrollView
      testID="edge-screen"
      style={s.container}
      contentContainerStyle={{ paddingBottom: insets.bottom + 20 }}
      stickyHeaderIndices={[0]}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />
      }
    >
      {/* ITERATION 4·γ · cognition dialect — Edge = AI detecting asymmetric pressure */}
      <BusPulse energy="dormant" amount={0.35} />
      <CognitiveAnchor
        cognition="DETECTING"
        capital="OBSERVING"
        colors={colors}
      />

      {/* ─── HEADER ─── */}
      <View style={s.header}>
        <Text style={[s.headerTitle, { color: colors.textPrimary }]}>{t('edge.earlyOpportunities')}</Text>
        <Text style={[s.headerSub, { color: colors.textMuted }]}>{t('edge.signalsBeforeTheyBecomeObvious')}</Text>
      </View>

      {/* ─── PHASE X · CROSS-APP BRIDGE ─── */}
      <View style={{ paddingHorizontal: 16 }}>
        <MetaBrainIdentityStrip variant="compact" tappable />
        <TradingBridgeCTA
          variant="open-execution"
          asset={asset}
          customSub="every signal here can be opened in execution cognition"
        />
      </View>

      {/* ═══ 🔥 HERO-ENTRY REINFORCEMENT ═══
          Shown ONLY when user just tapped Signal of the Moment (within last 5m).
          Closes the loop: "You're in the right place — this is THE setup right now".
          - CRITICAL : "You're early on this setup"
          - HIGH     : "Setup is building — you're on time"
          - Progress line: "N more drivers needed" if driver data available
          - FREE user: extra paywall urgency + social-proof line */}
      {heroEntry && Date.now() - heroEntry.at < 5 * 60 * 1000 && (() => {
        const accentColor = heroEntry.priority === 'CRITICAL' ? colors.sell : colors.accent;
        // Progress-to-action line — uses current asset opportunities as proxy for driver count.
        const assetDrivers = opportunities.filter((o: EdgeOpportunity) => o.asset === heroEntry.asset).length;
        const progressLine = heroEntry.priority === 'CRITICAL'
          ? '→ confirmation building · watch for acceleration'
          : assetDrivers > 0
            ? `→ ${Math.max(1, 3 - assetDrivers)} more drivers needed for confirmation`
            : '→ 3 more drivers needed for confirmation';

        return (
          <TouchableOpacity
            activeOpacity={isPro ? 1 : 0.88}
            onPress={() => { if (!isPro) openPaywall('contextual'); }}
            style={[
              s.heroReinforce,
              { backgroundColor: accentColor + '12', borderColor: accentColor + '55' },
            ]}
          >
            <Text style={[s.heroReinforceTitle, { color: accentColor }]} numberOfLines={1}>
              {heroEntry.priority === 'CRITICAL'
                ? `🔥 You're early on this setup${heroEntry.asset ? ` · ${heroEntry.asset}` : ''}`
                : `🔥 Setup is building — you're on time${heroEntry.asset ? ` · ${heroEntry.asset}` : ''}`}
            </Text>
            <Text style={[s.heroReinforceProgress, { color: colors.textSecondary }]} numberOfLines={1}>
              {progressLine}
            </Text>
            {heroEntry.sourcesCount > 0 && (
              <Text style={[s.heroReinforceSources, { color: colors.textMuted }]} numberOfLines={1}>
                ● based on {heroEntry.sourcesCount} signal{heroEntry.sourcesCount === 1 ? '' : 's'}
              </Text>
            )}
            {!isPro && (
              <>
                <Text style={[s.heroReinforceSub, { color: colors.textSecondary }]} numberOfLines={1}>
                  This setup is unfolding now — Unlock entry, timing & invalidation
                </Text>
                <View style={s.heroReinforceSocialRow}>
                  <View style={[s.heroReinforceSocialDot, { backgroundColor: colors.buy }]} />
                  <Text style={[s.heroReinforceSocialText, { color: colors.buy }]} numberOfLines={1}>
                    Traders are entering now
                  </Text>
                </View>
              </>
            )}
          </TouchableOpacity>
        );
      })()}

      {/* ─── FILTERS ─── */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.filterRow}>
        {FILTERS.map(f => {
          const active = filter === f.key;
          return (
            <TouchableOpacity
              key={f.key}
              testID={`edge-filter-${f.key.toLowerCase()}`}
              style={[s.filterChip, active && { backgroundColor: colors.accent + '20', borderColor: colors.accent }]}
              onPress={() => setFilter(f.key)}
            >
              <Text style={[s.filterText, { color: active ? colors.accent : colors.textMuted }]}>{f.label}</Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      {/* ─── EDGE CARDS / PREDICTION MARKETS ─── */}
      {filter === 'PREDICTION' ? (
        predictionMarkets.length === 0 ? (
          <View style={s.emptyWrap}>
            <Ionicons name="analytics" size={32} color={colors.textMuted} />
            <Text style={[s.emptyText, { color: colors.textMuted }]}>{t('edge.loadingPredictionMarkets')}</Text>
          </View>
        ) : (
          predictionMarkets.map((m: any, idx: number) => {
            const actionBg = m.actionColor === 'green' ? colors.buy + '15' : m.actionColor === 'red' ? colors.sell + '15' : m.actionColor === 'orange' ? '#FF8C00' + '15' : colors.surface;
            const actionTextColor = m.actionColor === 'green' ? colors.buy : m.actionColor === 'red' ? colors.sell : m.actionColor === 'orange' ? '#FF8C00' : colors.textMuted;
            const edgeColor = m.edge > 0.02 ? colors.buy : m.edge < -0.02 ? colors.sell : colors.textMuted;
            return (
              <View key={m.id || idx} style={[s.edgeCard, { backgroundColor: colors.surface, borderColor: actionTextColor + '20' }]}>
                {/* Action label + edge + time */}
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                    <View style={{ backgroundColor: actionBg, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4 }}>
                      <Text style={{ fontSize: 10, fontWeight: '800', color: actionTextColor, letterSpacing: 0.5 }}>{m.actionLabel}</Text>
                    </View>
                    {m.edgePercent > 1 && (
                      <Text style={{ fontSize: 10, fontWeight: '700', color: edgeColor }}>
                        {m.edge > 0 ? '+' : ''}{m.edgePercent.toFixed(1)}%
                      </Text>
                    )}
                    {m.size && m.size !== 'NONE' && (
                      <Text style={{ fontSize: 9, color: colors.textMuted, fontWeight: '600' }}>{m.size}</Text>
                    )}
                  </View>
                  {m.timeLeft ? (
                    <Text style={{ fontSize: 10, color: colors.sell, fontWeight: '600' }}>{m.timeLeft}</Text>
                  ) : null}
                </View>

                {/* Tags */}
                {m.tags && m.tags.length > 0 && (
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginBottom: 6 }}>
                    {m.tags.slice(0, 4).map((tag: string, ti: number) => (
                      <View key={ti} style={{ backgroundColor: colors.accent + '12', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 3 }}>
                        <Text style={{ fontSize: 9, color: colors.accent, fontWeight: '600' }}>{tag}</Text>
                      </View>
                    ))}
                  </View>
                )}

                {/* Question */}
                <Text style={{ fontSize: 14, fontWeight: '700', color: colors.textPrimary, lineHeight: 20, marginBottom: 8 }} numberOfLines={2}>
                  {m.question}
                </Text>

                {/* Market vs Model probabilities */}
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <View style={{ flex: 1 }}>
                    <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 }}>
                      <Text style={{ fontSize: 11, color: colors.textMuted }}>Market</Text>
                      <Text style={{ fontSize: 11, fontWeight: '700', color: colors.textPrimary }}>{Math.round(m.marketProb * 100)}%</Text>
                    </View>
                    <View style={{ height: 4, backgroundColor: colors.border, borderRadius: 2, overflow: 'hidden' }}>
                      <View style={{ height: 4, width: `${Math.round(m.marketProb * 100)}%`, backgroundColor: colors.accent, borderRadius: 2 }} />
                    </View>
                    <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginTop: 4 }}>
                      <Text style={{ fontSize: 11, color: colors.textMuted }}>Model</Text>
                      <Text style={{ fontSize: 11, fontWeight: '700', color: edgeColor }}>{Math.round(m.modelProb * 100)}%</Text>
                    </View>
                  </View>
                </View>

                {/* Edge analysis box */}
                <View style={{ padding: 10, backgroundColor: colors.background, borderRadius: 8, marginTop: 4 }}>
                  <Text style={{ fontSize: 12, color: colors.textSecondary }}>{m.edgeText}</Text>
                  <View style={{ flexDirection: 'row', gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
                    <Text style={{ fontSize: 10, fontWeight: '700', color: edgeColor }}>Edge: {m.edge > 0 ? '+' : ''}{m.edgePercent.toFixed(1)}%</Text>
                    <Text style={{ fontSize: 10, color: m.conviction === 'HIGH' ? colors.buy : colors.textMuted }}>{m.conviction?.toLowerCase()} conf</Text>
                    {m.entryAction !== 'do_not_enter' && (
                      <Text style={{ fontSize: 10, color: colors.buy, fontWeight: '600' }}>{m.entryAction?.replace(/_/g, ' ')}</Text>
                    )}
                  </View>
                </View>

                {/* Volume */}
                {m.volume > 0 && (
                  <View style={{ flexDirection: 'row', gap: 12, marginTop: 8 }}>
                    <Text style={{ fontSize: 10, color: colors.textMuted }}>Vol: ${m.volume?.toLocaleString()}</Text>
                    <Text style={{ fontSize: 10, color: colors.textMuted }}>Liq: ${m.liquidity?.toLocaleString()}</Text>
                  </View>
                )}
              </View>
            );
          })
        )
      ) : filtered.length === 0 ? (
        <View style={s.emptyWrap}>
          <Ionicons name="search" size={32} color={colors.textMuted} />
          <Text style={[s.emptyText, { color: colors.textMuted }]}>{t('edge.noOpportunitiesDetectedRightNow')}</Text>
          <Text style={[s.emptyHint, { color: colors.textMuted }]}>Pull to refresh — new edges emerge constantly</Text>
        </View>
      ) : (
        filtered.map((edge, idx) => (
          <EdgeCard
            key={edge.id}
            edge={edge}
            isPro={isPro}
            colors={colors}
            index={idx}
            onPress={() => {
              setViewCount(prev => prev + 1);
              setSelectedEdge(edge);
            }}
          />
        ))
      )}

      {/* ─── MICRO-TRIGGER: view count ─── */}
      {viewCount >= 2 && !isPro && (
        <View style={[s.triggerCard, { backgroundColor: colors.accent + '08', borderColor: colors.accent + '20' }]}>
          <Text style={[s.triggerText, { color: colors.textSecondary }]}>
            You've viewed {viewCount} early opportunities today
          </Text>
          <Text style={[s.triggerSub, { color: colors.textMuted }]}>
            Signals are forming while you're watching
          </Text>
        </View>
      )}

      {/* ─── STICKY PRO HINT ─── */}
      {!isPro && filtered.length > 0 && (
        <View style={[s.stickyHint, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <Ionicons name="flash-outline" size={14} color={colors.accent} />
          <Text style={[s.stickyText, { color: colors.textMuted }]}>{t('edge.proUsersEnterBeforeConfirmation')}</Text>
        </View>
      )}
    </ScrollView>
  );
}


/* ═══════════════════════════════════════
   EDGE CARD
   ═══════════════════════════════════════ */

function EdgeCard({
  edge, isPro, colors, index, onPress,
}: {
  edge: EdgeOpportunity;
  isPro: boolean;
  colors: any;
  index: number;
  onPress: () => void;
}) {
  const s = React.useMemo(() => makeStyles(colors), [colors]);

  const badgeColor = edge.badge === 'EARLY SIGNAL' ? colors.accent
    : edge.badge === 'SOCIAL SPIKE' ? '#FF6B35'
    : edge.badge === 'SETUP FORMING' ? colors.buy
    : edge.badge === 'MARKET EVENT' ? '#9B59B6'
    : edge.badge === 'CAUTION' ? colors.sell
    : colors.textMuted;

  const confColor = edge.confidence >= 70 ? colors.buy
    : edge.confidence >= 50 ? '#FFCC00'
    : colors.textMuted;

  // FREE: show only 1 driver, rest locked
  const visibleDrivers = isPro ? edge.drivers : edge.drivers.slice(0, 1);
  const lockedCount = isPro ? 0 : Math.max(0, edge.drivers.length - 1);

  return (
    <TouchableOpacity
      testID={`edge-card-${edge.id}`}
      style={[s.edgeCard, { borderColor: colors.border, backgroundColor: colors.surface }]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      {/* Badge + Confidence + State */}
      <View style={s.edgeTop}>
        <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center' }}>
          <View style={[s.edgeBadge, { backgroundColor: badgeColor + '18' }]}>
            <Text style={[s.edgeBadgeText, { color: badgeColor }]}>{edge.badge}</Text>
          </View>
          {(edge as any).edgeState && (
            <View style={[s.edgeBadge, { backgroundColor: colors.textMuted + '15' }]}>
              <Text style={[s.edgeBadgeText, { color: colors.textMuted }]}>{(edge as any).edgeState}</Text>
            </View>
          )}
        </View>
        <Text style={[s.edgeConf, { color: confColor }]}>{edge.confidence}%</Text>
      </View>

      {/* Asset + Title */}
      <View style={s.edgeAssetRow}>
        <Text style={[s.edgeAsset, { color: colors.textPrimary }]}>{edge.asset}</Text>
      </View>
      <Text style={[s.edgeTitle, { color: colors.textSecondary }]}>{edge.title}</Text>

      {/* Drivers — money-oriented phrasing */}
      <View style={s.edgeDrivers}>
        {visibleDrivers.length > 0 && (
          <Text style={[s.edgeMomentum, { color: colors.textSecondary }]}>
            {edge.type === 'SOCIAL'
              ? 'Social momentum is building before price reacts.'
              : edge.type === 'FLOW'
              ? 'Capital is moving before the crowd sees it.'
              : 'Catalyst forming. Window narrowing.'}
          </Text>
        )}
        {visibleDrivers.map((d, i) => (
          <View key={i} style={s.edgeDriverRow}>
            <Ionicons
              name={d.positive ? 'add-circle' : 'remove-circle'}
              size={14}
              color={d.positive ? colors.buy : colors.sell}
            />
            <Text style={[s.edgeDriverText, { color: colors.textSecondary }]} numberOfLines={1}>{d.text}</Text>
          </View>
        ))}
        {lockedCount > 0 && (
          <View style={s.edgeDriverRow}>
            <Ionicons name="lock-closed" size={12} color={colors.accent} />
            <Text style={[s.edgeDriverText, { color: colors.accent }]}>+{lockedCount} more drivers (PRO)</Text>
          </View>
        )}
      </View>

      {/* Tension line */}
      <Text style={[s.edgeTension, { color: colors.accent }]}>{edge.tension}</Text>

      {/* Pre-move indicator */}
      {edge.preMoveStarted && (
        <View style={[s.preMove, { backgroundColor: colors.buy + '10' }]}>
          <Ionicons name="pulse" size={12} color={colors.buy} />
          <Text style={[s.preMoveText, { color: colors.buy }]}>{edge.preMoveValue}</Text>
        </View>
      )}

      {/* Timing + CTA */}
      <View style={s.edgeBottom}>
        <View style={s.edgeTimingRow}>
          <Ionicons name="time-outline" size={12} color={colors.textMuted} />
          <Text style={[s.edgeTiming, { color: colors.textMuted }]}>Window: {edge.timing}</Text>
        </View>
        <View style={[s.edgeCta, { backgroundColor: colors.buy + '18' }]}>
          <Text style={[s.edgeCtaText, { color: colors.buy }]}>{t('edge.positionEarly')}</Text>
          <Ionicons name="arrow-forward" size={12} color={colors.buy} />
        </View>
      </View>

      {/* Organic micro-FOMO */}
      <Text style={[s.detectedBefore, { color: colors.textMuted }]}>
        This edge gets smaller once the signal is public
      </Text>
    </TouchableOpacity>
  );
}


/* ═══════════════════════════════════════
   EDGE DETAIL VIEW
   ═══════════════════════════════════════ */

function EdgeDetailView({
  edge, isPro, colors, onClose,
}: {
  edge: EdgeOpportunity;
  isPro: boolean;
  colors: any;
  onClose: () => void;
}) {
  const insets = useSafeAreaInsets();
  const s = React.useMemo(() => makeStyles(colors), [colors]);
  const { setIntelTab } = useAppMode();
  const [portfolioPerf, setPortfolioPerf] = useState<any>(null);
  const [tracked, setTracked] = useState(false);
  // G1 share state
  const [sharing, setSharing] = useState(false);
  const [shared, setShared] = useState(false);

  // Track edge view
  useTracker('EDGE_DETAIL', { symbol: edge.asset });

  // G1: edge_paywall_view fires once per detail-open for FREE users
  useEffect(() => {
    if (!isPro) {
      track('edge_paywall_view', {
        asset: edge.asset,
        signalId: edge.id,
        source: 'edge',
        priority: edge.badge,
        context: { screen: 'edge', from: 'detail', confidence: edge.confidence },
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // G1: derive share eligibility — Edge detail uses badge/confidence as priority proxy
  const mapPriority = (): string => {
    if ((edge.badge || '').toUpperCase().includes('EARLY')) return 'CRITICAL';
    if (edge.confidence >= 70) return 'HIGH';
    return 'MEDIUM';
  };
  const edgePriority = mapPriority();
  const edgeShareVisible = canShareSignal({
    priority: edgePriority,
    source: 'edge',
    watchersCount: Math.max(0, Math.round(edge.confidence)),
  }) || edge.confidence >= 70; // Edge detail is already a high-intent surface

  const handleEdgeShare = async () => {
    if (sharing || shared) return;
    track('share_click', {
      signalId: edge.id,
      asset: edge.asset,
      source: 'edge',
      priority: edgePriority,
      context: { screen: 'edge', from: 'detail' },
    });
    setSharing(true);
    try {
      const res = await shareSignal({
        asset: edge.asset,
        source: 'edge',
        priority: edgePriority,
        title: edge.title,
      });
      if (res.ok) {
        track('share_complete', {
          signalId: edge.id,
          asset: edge.asset,
          source: 'edge',
          priority: edgePriority,
          context: { screen: 'edge', from: 'detail', via: res.via, hasRef: !!res.refCode },
        });
        setShared(true);
        setTimeout(() => setShared(false), 3000);
      }
    } finally {
      setSharing(false);
    }
  };

  const handlePaywallClick = () => {
    track('edge_paywall_click', {
      asset: edge.asset,
      signalId: edge.id,
      source: 'edge',
      priority: edgePriority,
      context: { screen: 'edge', from: 'detail_paywall' },
    });
    openPaywall('contextual');
  };

  // Fetch portfolio to check if already positioned
  useEffect(() => {
    mobileApi.getPortfolioPerformance().then(d => {
      if (d?.ok) setPortfolioPerf(d);
    }).catch(() => {});
  }, []);

  const position = portfolioPerf?.positions?.find(
    (p: any) => p.symbol === edge.asset && p.status === 'OPEN'
  );
  const positionPnl = position?.pnlPct || 0;

  // Portfolio roles
  const ROLES: Record<string, string> = { BTC: 'Core Anchor', ETH: 'Confirmation', SOL: 'Early Beta', LINK: 'Alt Discovery', DOGE: 'Momentum Play', ADA: 'Recovery Play', XRP: 'Utility Pivot', BNB: 'Infrastructure', AVAX: 'L1 Rotation' };
  const role = ROLES[edge.asset] || 'Discovery';

  const handleTrack = () => {
    hapticLight();
    setTracked(true);
    trackAction('TRACK_EDGE', { symbol: edge.asset, edgeId: edge.id, confidence: edge.confidence });
    // Save to backend edge tracking
    mobileApi.trackEdge(edge.id, edge.asset, 'track').catch(() => {});
  };

  const badgeColor = edge.badge === 'EARLY SIGNAL' ? colors.accent
    : edge.badge === 'SOCIAL SPIKE' ? '#FF6B35'
    : edge.badge === 'SETUP FORMING' ? colors.buy
    : edge.badge === 'MARKET EVENT' ? '#9B59B6'
    : edge.badge === 'CAUTION' ? colors.sell
    : colors.textMuted;

  const confColor = edge.confidence >= 70 ? colors.buy : edge.confidence >= 50 ? '#FFCC00' : colors.textMuted;

  return (
    <View style={[s.detailOverlay, { paddingTop: insets.top }]}>
      {/* Top Bar */}
      <View style={s.detailTopBar}>
        <TouchableOpacity testID="edge-detail-back" style={s.backBtn} onPress={onClose}>
          <Ionicons name="chevron-back" size={20} color={colors.textSecondary} />
        </TouchableOpacity>
        <Text style={[s.detailTopTitle, { color: colors.textSecondary }]}>{t('edge.earlyOpportunity')}</Text>
        {edgeShareVisible ? (
          <TouchableOpacity
            testID="edge-detail-share"
            onPress={handleEdgeShare}
            disabled={sharing || shared}
            style={[
              s.edgeShareIcon,
              {
                backgroundColor: shared ? colors.buy + '18' : colors.accent + '12',
                borderColor: shared ? colors.buy + '55' : colors.accent + '40',
              },
            ]}
            activeOpacity={0.8}
          >
            <Ionicons
              name={shared ? 'checkmark' : 'arrow-redo-outline'}
              size={16}
              color={shared ? colors.buy : colors.accent}
            />
          </TouchableOpacity>
        ) : (
          <View style={{ width: 36 }} />
        )}
      </View>

      <ScrollView contentContainerStyle={s.detailScroll}>
        {/* Badge */}
        <View style={[s.edgeBadge, { backgroundColor: badgeColor + '18', alignSelf: 'center', marginBottom: 8 }]}>
          <Text style={[s.edgeBadgeText, { color: badgeColor }]}>{edge.badge}</Text>
        </View>

        {/* Asset + Confidence */}
        <Text style={[s.detailAsset, { color: colors.textPrimary }]}>{edge.asset}</Text>
        <Text style={[s.detailConf, { color: confColor }]}>{edge.confidence}% confidence</Text>

        {/* Title / Summary */}
        <View style={[s.detailCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <Text style={[s.detailCardLabel, { color: colors.textMuted }]}>{t('edge.whyThisOpportunity')}</Text>
          <Text style={[s.detailSummary, { color: colors.textSecondary }]}>{edge.title}</Text>
        </View>

        {/* Drivers */}
        <View style={[s.detailCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <Text style={[s.detailCardLabel, { color: colors.textMuted }]}>DRIVERS</Text>
          {edge.drivers.map((d, i) => {
            // FREE: first driver visible, rest locked
            if (!isPro && i >= 1) {
              return (
                <View key={i} style={[s.detailDriverRow, { opacity: 0.4 }]}>
                  <Ionicons name="lock-closed" size={14} color={colors.accent} />
                  <View style={[s.detailDriverBlur, { backgroundColor: colors.border }]} />
                </View>
              );
            }
            return (
              <View key={i} style={s.detailDriverRow}>
                <Ionicons
                  name={d.positive ? 'checkmark-circle' : 'close-circle'}
                  size={16}
                  color={d.positive ? colors.buy : colors.sell}
                />
                <Text style={[s.detailDriverText, { color: colors.textSecondary }]}>{d.text}</Text>
              </View>
            );
          })}
        </View>

        {/* Timing + Signal Evolution */}
        <View style={[s.detailCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <Text style={[s.detailCardLabel, { color: colors.textMuted }]}>{t('edge.beforeSignal')}</Text>
          <Text style={[s.detailTiming, { color: colors.textSecondary }]}>
            Current state: pre-signal formation
          </Text>
          <Text style={[s.detailTiming, { color: colors.textMuted, marginTop: 4 }]}>
            Confirmation threshold: not yet reached
          </Text>

          {/* Signal formation progress */}
          <View style={[s.formationBar, { marginTop: 12 }]}>
            {/* Chip-based alignment visual [■■□□□□] 2/6 aligned */}
            {(() => {
              const positiveCount = (edge.drivers || []).filter((d) => d.positive).length;
              const totalCount = Math.max((edge.drivers || []).length, 6);
              const aligned = Math.min(positiveCount, totalCount);
              const needed = Math.max(totalCount - aligned, 0);
              const chips = Array.from({ length: totalCount });
              const pressureText =
                aligned >= totalCount - 1
                  ? 'ready to fire'
                  : aligned >= Math.ceil(totalCount / 2)
                  ? 'building pressure'
                  : 'early formation';
              return (
                <View style={{ marginBottom: 10 }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                    <View style={{ flexDirection: 'row', gap: 4 }}>
                      {chips.map((_, i) => (
                        <View
                          key={i}
                          style={{
                            width: 14,
                            height: 14,
                            borderRadius: 3,
                            backgroundColor: i < aligned ? colors.accent : 'transparent',
                            borderWidth: 1.5,
                            borderColor: i < aligned ? colors.accent : colors.border,
                          }}
                        />
                      ))}
                    </View>
                    <Text style={{ fontSize: 12, fontWeight: '800', color: colors.accent }}>
                      {aligned}/{totalCount} aligned
                    </Text>
                  </View>
                  <Text
                    style={{
                      fontSize: 11,
                      fontWeight: '600',
                      color: colors.textMuted,
                      marginTop: 4,
                      fontStyle: 'italic',
                    }}
                  >
                    {pressureText}
                  </Text>
                  {needed > 0 && (
                    <Text
                      style={{
                        fontSize: 11,
                        fontWeight: '700',
                        color: colors.accent,
                        marginTop: 4,
                      }}
                    >
                      → {needed} more signal{needed > 1 ? 's' : ''} needed
                    </Text>
                  )}
                </View>
              );
            })()}
            <View style={[s.formationBg, { backgroundColor: colors.border }]}>
              <View style={[s.formationFill, { width: `${Math.min(edge.confidence, 100)}%`, backgroundColor: colors.accent }]} />
            </View>
            <Text style={[s.formationPct, { color: colors.accent }]}>Signal formation: {edge.confidence}%</Text>
          </View>

          {/* IF CONFIRMED block */}
          {edge.signalLink && (
            <View style={[s.ifConfirmed, { backgroundColor: colors.buy + '08', borderColor: colors.buy + '20', marginTop: 12 }]}>
              <Text style={[s.ifConfirmedLabel, { color: colors.buy }]}>{t('edge.ifConfirmed')}</Text>
              <Text style={[s.ifConfirmedText, { color: colors.textSecondary }]}>
                Will trigger: {edge.confidence >= 60 ? 'BUY' : 'Potential BUY'} signal
              </Text>
              <Text style={[s.ifConfirmedText, { color: colors.textMuted, marginTop: 2 }]}>
                Will appear in Signals after confirmation
              </Text>
            </View>
          )}

          <Text style={[s.detailTiming, { color: colors.textMuted, marginTop: 8, fontStyle: 'italic' }]}>
            Window: {edge.timing} · Most users will see this after confirmation
          </Text>
        </View>

        {/* ═══ WHY THIS MATTERS NOW ═══ */}
        <View style={[s.mattersCard, { borderLeftColor: colors.accent, backgroundColor: colors.surface }]}>
          <Text style={[s.mattersLabel, { color: colors.accent }]}>{t('edge.whyThisMattersNow')}</Text>
          <Text style={[s.mattersText, { color: colors.textPrimary }]}>
            This is the phase before the signal becomes obvious.
          </Text>
          <Text style={[s.mattersSubtext, { color: colors.textMuted }]}>
            After confirmation, the edge is smaller.{'\n'}You are not early after confirmation. You are early now.
          </Text>
        </View>

        {/* Positioning hint for PRO */}
        {isPro && (
          <View style={[s.positionCard, { borderColor: colors.buy + '30', backgroundColor: colors.buy + '05' }]}>
            <Text style={[s.positionLabel, { color: colors.buy }]}>{t('edge.preConfirmationEntry')}</Text>
            <Text style={[s.positionEntry, { color: colors.textPrimary }]}>
              Early accumulation zone
            </Text>
            <Text style={[s.positionRisk, { color: colors.sell }]}>
              Risk undefined until confirmation
            </Text>
            <Text style={[s.positionSize, { color: colors.textMuted }]}>
              Size smaller. Move earlier.
            </Text>
          </View>
        )}

        {/* ═══ 8. ROLE IN PORTFOLIO ═══ */}
        <View style={[s.detailCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <Text style={[s.detailCardLabel, { color: colors.textMuted }]}>{t('edge.roleInYourPortfolio')}</Text>
          <View style={s.roleRow}>
            <CoinIcon symbol={edge.asset} size={20} />
            <Text style={[s.roleAsset, { color: colors.textPrimary }]}>{edge.asset}</Text>
            <View style={[s.roleBadge, { backgroundColor: colors.accent + '15' }]}>
              <Text style={[s.roleText, { color: colors.accent }]}>{role}</Text>
            </View>
          </View>
          <TouchableOpacity
            style={s.roleCtaRow}
            onPress={() => { onClose(); setIntelTab('FEED'); }}
            activeOpacity={0.7}
          >
            <Text style={[s.roleCta, { color: colors.accent }]}>See full portfolio context →</Text>
          </TouchableOpacity>
        </View>

        {/* ═══ 9. ALREADY POSITIONED STATE ═══ */}
        {position && (
          <View style={[s.positionedCard, {
            borderColor: (positionPnl >= 0 ? colors.buy : colors.sell) + '30',
            backgroundColor: (positionPnl >= 0 ? colors.buy : colors.sell) + '05',
          }]}>
            <Ionicons name="checkmark-circle" size={18} color={positionPnl >= 0 ? colors.buy : colors.sell} />
            <View style={s.positionedContent}>
              <Text style={[s.positionedTitle, { color: colors.textPrimary }]}>{t('edge.youAreAlreadyPositioned')}</Text>
              <Text style={[s.positionedSub, { color: colors.textMuted }]}>
                Entered before confirmation
              </Text>
              <Text style={[s.positionedPnl, { color: positionPnl >= 0 ? colors.buy : colors.sell }]}>
                PnL: {positionPnl >= 0 ? '+' : ''}{positionPnl.toFixed(1)}%
              </Text>
            </View>
          </View>
        )}

        {/* ═══ 10. EDGE WINDOW TIMER ═══ */}
        <View style={[s.windowCard, { borderColor: colors.accent + '20', backgroundColor: colors.surface }]}>
          <View style={s.windowRow}>
            <Ionicons name="time-outline" size={16} color={colors.accent} />
            <Text style={[s.windowLabel, { color: colors.accent }]}>{t('edge.edgeWindow')}</Text>
            <Text style={[s.windowTime, { color: colors.textPrimary }]}>{edge.timing}</Text>
          </View>
          <View style={[s.windowBarBg, { backgroundColor: colors.border }]}>
            <View style={[s.windowBarFill, {
              width: `${Math.min(90, edge.confidence + 10)}%`,
              backgroundColor: colors.accent,
            }]} />
          </View>
          <Text style={[s.windowHint, { color: colors.textMuted }]}>
            Window narrows as signal forms
          </Text>
        </View>

        {/* ═══ 11. MICRO-FOMO ═══ */}
        <Text style={[s.detailDetected, { color: colors.textMuted }]}>
          The crowd enters later. Price adjusts first.
        </Text>

        {/* ═══ 12. CTA BLOCK ═══ */}
        <View style={s.ctaBlock}>
          <TouchableOpacity
            style={[s.trackBtn, {
              backgroundColor: tracked ? colors.buy + '15' : colors.accent + '15',
              borderColor: tracked ? colors.buy : colors.accent,
            }]}
            onPress={handleTrack}
            disabled={tracked}
            activeOpacity={0.7}
          >
            <Ionicons name={tracked ? 'checkmark-circle' : 'notifications-outline'} size={16} color={tracked ? colors.buy : colors.accent} />
            <Text style={[s.trackBtnText, { color: tracked ? colors.buy : colors.accent }]}>
              {tracked ? 'Edge tracked' : 'Track this edge'}
            </Text>
          </TouchableOpacity>
        </View>

        {/* Paywall — Edge-specific, contextual */}
        {!isPro && (
          <View style={[s.edgePaywall, { borderColor: colors.accent + '30', backgroundColor: colors.surface }]}>
            <View style={[s.paywallIconWrap, { backgroundColor: colors.accent + '15' }]}>
              <Ionicons name="flash" size={20} color={colors.accent} />
            </View>
            <Text style={[s.edgePaywallTitle, { color: colors.textPrimary }]}>
              You see the idea. You don't see the positioning.
            </Text>
            <Text style={[s.edgePaywallSub, { color: colors.textMuted }]}>
              PRO users enter before confirmation.{'\n'}Full entry zone, risk, and triggers unlocked.
            </Text>
            <TouchableOpacity
              testID="edge-unlock-btn"
              style={[s.edgePaywallBtn, { backgroundColor: colors.buy }]}
              onPress={handlePaywallClick}
              activeOpacity={0.8}
            >
              <Text style={s.edgePaywallBtnText}>{t('edge.unlockEarlyAccess')}</Text>
            </TouchableOpacity>
          </View>
        )}

        <View style={{ height: insets.bottom + 32 }} />
      </ScrollView>
    </View>
  );
}


/* ═══════════ STYLES ═══════════ */

const makeStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.background },
  loadingText: { marginTop: 12, fontSize: 13 },

  /* Header */
  header: { paddingHorizontal: 20, paddingTop: 8, paddingBottom: 4 },
  headerTitle: { fontSize: 22, fontWeight: '800' },
  heroReinforce: {
    marginHorizontal: 16, marginTop: 10, marginBottom: 2,
    paddingHorizontal: 14, paddingVertical: 12,
    borderRadius: 12, borderWidth: 1,
  },
  heroReinforceTitle: { fontSize: 13.5, fontWeight: '800', letterSpacing: 0.2 },
  heroReinforceProgress: { fontSize: 12, fontWeight: '600', marginTop: 4, opacity: 0.9 },
  heroReinforceSources: { fontSize: 11, fontWeight: '500', marginTop: 3, letterSpacing: 0.2 },
  heroReinforceSub: { fontSize: 12, fontWeight: '500', marginTop: 6 },
  heroReinforceSocialRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 },
  heroReinforceSocialDot: { width: 6, height: 6, borderRadius: 3 },
  heroReinforceSocialText: { fontSize: 11.5, fontWeight: '700' },
  headerSub: { fontSize: 13, marginTop: 2 },

  /* Filters */
  filterRow: { paddingHorizontal: 16, paddingVertical: 12, gap: 8 },
  filterChip: { paddingHorizontal: 16, paddingVertical: 7, borderRadius: 20, borderWidth: 1, borderColor: colors.border },
  filterText: { fontSize: 13, fontWeight: '600' },

  /* Edge Card */
  edgeCard: { marginHorizontal: 16, marginBottom: 12, padding: 16, borderRadius: 14, borderWidth: 1 },
  edgeTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  edgeBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  edgeBadgeText: { fontSize: 10, fontWeight: '800', letterSpacing: 0.5 },
  edgeConf: { fontSize: 18, fontWeight: '800' },
  edgeAssetRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  edgeAsset: { fontSize: 20, fontWeight: '900' },
  edgeTitle: { fontSize: 15, fontWeight: '600', lineHeight: 21, marginBottom: 10 },
  edgeDrivers: { gap: 6, marginBottom: 10 },
  edgeMomentum: { fontSize: 13, fontWeight: '600', fontStyle: 'italic', marginBottom: 4, lineHeight: 19 },
  edgeDriverRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  edgeDriverText: { fontSize: 13, flex: 1 },
  edgeTension: { fontSize: 13, fontWeight: '600', fontStyle: 'italic', marginBottom: 8 },
  preMove: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, marginBottom: 8 },
  preMoveText: { fontSize: 12, fontWeight: '600' },
  edgeBottom: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  edgeTimingRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  edgeTiming: { fontSize: 11, fontWeight: '500' },
  edgeCta: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8 },
  edgeCtaText: { fontSize: 12, fontWeight: '700' },
  detectedBefore: { fontSize: 10, marginTop: 8, textAlign: 'right', fontStyle: 'italic' },

  /* Empty */
  emptyWrap: { alignItems: 'center', paddingTop: 60, gap: 8 },
  emptyText: { fontSize: 15, fontWeight: '600' },
  emptyHint: { fontSize: 12 },

  /* Trigger */
  triggerCard: { marginHorizontal: 16, marginTop: 8, padding: 16, borderRadius: 12, borderWidth: 1, alignItems: 'center' },
  triggerText: { fontSize: 13, fontWeight: '600' },
  triggerSub: { fontSize: 12, marginTop: 2 },

  /* Sticky Hint */
  stickyHint: { flexDirection: 'row', alignItems: 'center', gap: 8, marginHorizontal: 16, marginTop: 12, padding: 12, borderRadius: 10, borderWidth: 1 },
  stickyText: { fontSize: 12 },

  /* ─── DETAIL ─── */
  detailOverlay: { ...StyleSheet.absoluteFillObject, backgroundColor: colors.background, zIndex: 100 },
  detailTopBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 10 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: colors.surface, justifyContent: 'center', alignItems: 'center' },
  detailTopTitle: { fontSize: 14, fontWeight: '600' },
  edgeShareIcon: { width: 36, height: 36, borderRadius: 18, borderWidth: 1, justifyContent: 'center', alignItems: 'center' },
  edgeShareFeedback: { fontSize: 11.5, fontWeight: '700', textAlign: 'center', paddingVertical: 6 },
  detailScroll: { paddingHorizontal: 20, alignItems: 'center' },
  detailAsset: { fontSize: 32, fontWeight: '900', marginTop: 8 },
  detailConf: { fontSize: 14, fontWeight: '700', marginBottom: 16 },
  detailCard: { width: '100%', padding: 16, borderRadius: 14, borderWidth: 1, marginBottom: 12 },
  detailCardLabel: { fontSize: 10, fontWeight: '800', letterSpacing: 1.5, marginBottom: 10 },
  detailSummary: { fontSize: 16, fontWeight: '600', lineHeight: 23 },
  detailDriverRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6 },
  detailDriverText: { fontSize: 14, flex: 1, lineHeight: 20 },
  detailDriverBlur: { flex: 1, height: 14, borderRadius: 4 },
  detailTiming: { fontSize: 14, lineHeight: 20 },
  detailSignalHint: { fontSize: 14, fontWeight: '700', marginTop: 8 },

  /* WHY THIS MATTERS NOW — anchor block */
  mattersCard: { width: '100%', padding: 16, borderRadius: 14, borderLeftWidth: 3, marginBottom: 12, borderWidth: 0 },
  mattersLabel: { fontSize: 10, fontWeight: '800', letterSpacing: 1.5, marginBottom: 8 },
  mattersText: { fontSize: 16, fontWeight: '700', lineHeight: 23 },
  mattersSubtext: { fontSize: 13, lineHeight: 19, marginTop: 6 },

  /* POSITIONING — dominant money block */
  positionCard: { width: '100%', padding: 18, borderRadius: 14, borderWidth: 1, marginBottom: 12 },
  positionLabel: { fontSize: 10, fontWeight: '900', letterSpacing: 2, marginBottom: 10 },
  positionEntry: { fontSize: 17, fontWeight: '700', lineHeight: 24 },
  positionRisk: { fontSize: 13, fontWeight: '600', marginTop: 4 },
  positionSize: { fontSize: 12, marginTop: 4, fontStyle: 'italic' },

  formationBar: {},
  formationBg: { height: 4, borderRadius: 2, overflow: 'hidden', marginBottom: 6 },
  formationFill: { height: '100%', borderRadius: 2 },
  formationPct: { fontSize: 11, fontWeight: '600' },
  ifConfirmed: { padding: 12, borderRadius: 10, borderWidth: 1 },
  ifConfirmedLabel: { fontSize: 10, fontWeight: '800', letterSpacing: 1, marginBottom: 4 },
  ifConfirmedText: { fontSize: 13, lineHeight: 19 },
  lockedRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6 },
  lockedLabel: { fontSize: 14 },

  /* Role in Portfolio */
  roleRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10 },
  roleAsset: { fontSize: 16, fontWeight: '800' },
  roleBadge: { paddingHorizontal: 10, paddingVertical: 3, borderRadius: 8 },
  roleText: { fontSize: 11, fontWeight: '700' },
  roleCtaRow: { paddingTop: 8, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  roleCta: { fontSize: 12, fontWeight: '600' },

  /* Already Positioned */
  positionedCard: { width: '100%', flexDirection: 'row', padding: 14, borderRadius: 14, borderWidth: 1, marginBottom: 12, gap: 10, alignItems: 'flex-start' },
  positionedContent: { flex: 1 },
  positionedTitle: { fontSize: 14, fontWeight: '700' },
  positionedSub: { fontSize: 12, marginTop: 2 },
  positionedPnl: { fontSize: 16, fontWeight: '800', marginTop: 4 },

  /* Edge Window Timer */
  windowCard: { width: '100%', padding: 14, borderRadius: 14, borderWidth: 1, marginBottom: 12 },
  windowRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  windowLabel: { fontSize: 10, fontWeight: '800', letterSpacing: 1 },
  windowTime: { fontSize: 14, fontWeight: '700', marginLeft: 'auto' },
  windowBarBg: { height: 4, borderRadius: 2, overflow: 'hidden', marginBottom: 6 },
  windowBarFill: { height: '100%', borderRadius: 2 },
  windowHint: { fontSize: 11, fontStyle: 'italic' },

  /* CTA Block */
  ctaBlock: { width: '100%', marginBottom: 12 },
  trackBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 14, borderRadius: 12, borderWidth: 1 },
  trackBtnText: { fontSize: 14, fontWeight: '700' },

  /* Edge Paywall */
  edgePaywall: { width: '100%', padding: 24, borderRadius: 16, borderWidth: 1, alignItems: 'center', marginTop: 8 },
  paywallIconWrap: { width: 44, height: 44, borderRadius: 22, justifyContent: 'center', alignItems: 'center', marginBottom: 14 },
  edgePaywallTitle: { fontSize: 17, fontWeight: '700', textAlign: 'center' },
  edgePaywallSub: { fontSize: 13, marginTop: 4, marginBottom: 18, textAlign: 'center' },
  edgePaywallBtn: { width: '100%', paddingVertical: 14, borderRadius: 12, alignItems: 'center' },
  edgePaywallBtnText: { color: '#fff', fontSize: 14, fontWeight: '700' },

  detailDetected: { fontSize: 11, marginTop: 16, textAlign: 'center' },
});
