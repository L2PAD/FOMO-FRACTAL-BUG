/**
 * HomeScreen — Decision Surface
 *
 * NOT a dashboard. NOT indicators.
 * ONE signal → ONE decision → ONE action.
 *
 * Structure:
 *   [Context]       — 1 line: "Extreme Fear — contrarian zone"
 *   [MAIN SIGNAL]   — BUY/SELL/WAIT + price + confidence + decision line
 *   [Trade Setup]   — Entry/Invalidation/Target (🔒 PRO)
 *   [Key Insight]   — 1 human sentence
 *   [Track Record]  — trust layer
 *   [Drivers]       — human language, not module names
 *   [CTA]           — View Signal / View Edge / Open Trade
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
  Animated,
  Platform,
  Modal,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { hapticLight, hapticMedium } from '../../../services/haptics.service';
import { ShareTrigger } from '../../../components/ShareTrigger';
import { MomentPaywall } from '../../../components/MomentPaywall';
import { useAppMode } from '../../../stores/app-mode.store';
import { mobileApi } from '../../../services/api/mobile-api';
import type { TopSignal } from '../../../services/api/mobile-api';
import { useAssetStore } from '../../../stores/asset.store';
import { useColors } from '../../../core/useColors';
import { openPaywall } from '../../../utils/paywall-controller';
import { useSessionStore } from '../../../stores/session.store';
import { CoinIcon } from '../../../components/CoinIcon';
import { useTracker, trackAction } from '../../../hooks/useTracker';
import PredictionScreen from '../prediction/PredictionScreen';
import Svg, { Path, Defs, LinearGradient as SvgLG, Stop, Circle } from 'react-native-svg';
import SignalStateBadge from '../../../components/SignalStateBadge';
import LiveDot from '../../../components/LiveDot';
import SignalOfMomentHero from './components/SignalOfMomentHero';
import { track } from '../../../services/analytics';
import { MetaBrainIdentityStrip } from '../../../widgets/trading-bridge/MetaBrainIdentityStrip';
import { AIValueNarrativeFeed } from '../../../widgets/trading-bridge/AIValueNarrativeFeed';

import { t } from '../../../core/i18n';
/* ─── driver → human language ─── */
function humanDriver(d: any): string {
  const mod = (d.name || d.module || '').toLowerCase();
  const dir = (d.direction || d.state || '').toLowerCase();
  const reason = d.reason || d.label || '';

  if (mod.includes('sentiment')) {
    if (dir === 'bullish') return 'NLP sentiment positive — bullish bias in social/news';
    if (dir === 'bearish') return 'NLP sentiment negative — bearish pressure in media';
    return 'Sentiment neutral — no strong NLP bias';
  }
  if (mod.includes('exchange')) {
    if (reason.includes('HOLD')) return 'No strong accumulation';
    if (reason.includes('BUY')) return 'Accumulation detected';
    if (reason.includes('SELL')) return 'Distribution signals';
    return 'Exchange signals mixed';
  }
  if (mod.includes('onchain')) {
    if (dir === 'bullish') return 'On-chain inflows rising — whale accumulation';
    if (dir === 'bearish') return 'On-chain outflows — distribution detected';
    return 'On-chain monitoring — awaiting signal';
  }
  if (mod.includes('fractal')) {
    if (dir === 'bullish') return 'Breakout pattern forming';
    if (dir === 'bearish') return 'Breakdown pattern forming';
    return 'No clear pattern';
  }
  if (mod.includes('metabrain')) {
    if (dir === 'bullish') return 'MetaBrain synthesis — cross-layer bullish';
    if (dir === 'bearish') return 'MetaBrain synthesis — cross-layer bearish';
    return 'MetaBrain calibrating — building prediction';
  }
  if (mod.includes('prediction')) {
    if (reason.includes('leaning down')) return 'Polymarket leaning bearish';
    if (reason.includes('leaning up')) return 'Polymarket leaning bullish';
    return 'Prediction markets neutral';
  }
  return reason.substring(0, 40) || `${mod}: ${dir}`;
}

function decisionLine(action: string, confidence: number): string {
  if (action === 'BUY' && confidence >= 0.6) return 'Strong accumulation — high conviction entry';
  if (action === 'BUY' && confidence >= 0.45) return 'Contrarian setup — early accumulation detected';
  if (action === 'BUY' && confidence >= 0.3) return 'Early buy signal — confirmation still needed';
  if (action === 'BUY') return 'Weak buy signal — patience advised';
  if (action === 'SELL' && confidence >= 0.6) return 'Distribution confirmed — exit zone';
  if (action === 'SELL' && confidence >= 0.4) return 'Sell pressure building — caution advised';
  if (action === 'SELL') return 'Early sell signal — watching closely';
  if (confidence < 0.2) return 'No clear edge right now';
  return 'Mixed signals — waiting for confirmation';
}

/* ═══════════════════════════════════════
   HOME SCREEN
   ═══════════════════════════════════════ */
export function HomeScreen() {
  const colors = useColors();
  const s = React.useMemo(() => mk(colors), [colors]);

  const [signal, setSignal] = useState<any>(null);
  const [market, setMarket] = useState<any>(null);
  const [history, setHistory] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [portfolioPerf, setPortfolioPerf] = useState<any>(null);
  const [predictionVisible, setPredictionVisible] = useState(false);
  const [predCompact, setPredCompact] = useState<any>(null);
  const [predFull, setPredFull] = useState<any>(null);
  const [topSignal, setTopSignal] = useState<TopSignal | null>(null);
  const [heroCollapsed, setHeroCollapsed] = useState(false);
  const asset = useAssetStore((st) => st.currentAsset);
  const setCurrentAsset = useAssetStore((st) => st.setCurrentAsset);
  const user = useSessionStore((st) => st.user);
  const isPro = user?.plan === 'PRO' || user?.plan === 'INSTITUTIONAL';
  const { switchToTrading, setIntelTab, setHeroEntry } = useAppMode();
  const seenTracked = useRef(false);

  const scaleAnim = useRef(new Animated.Value(1)).current;
  const glowAnim = useRef(new Animated.Value(0.08)).current;

  // Behavior tracking
  useTracker('HOME', { symbol: asset });

  // Track signal view on home
  useEffect(() => {
    if (signal && signal.action) {
      trackAction('signal_view', {
        symbol: asset,
        verdict: signal.action,
        confidence: signal.confidence,
        stateLabel: signal.stateLabel,
        screen: 'HOME',
        mode: 'shadow',
      });
    }
  }, [signal?.action, asset]);

  useEffect(() => {
    if (!seenTracked.current) { seenTracked.current = true; mobileApi.markSeen('home'); }
  }, []);

  useEffect(() => {
    Animated.loop(Animated.sequence([
      Animated.timing(scaleAnim, { toValue: 1.03, duration: 2200, useNativeDriver: true }),
      Animated.timing(scaleAnim, { toValue: 1, duration: 2200, useNativeDriver: true }),
    ])).start();
    Animated.loop(Animated.sequence([
      Animated.timing(glowAnim, { toValue: 0.16, duration: 2200, useNativeDriver: true }),
      Animated.timing(glowAnim, { toValue: 0.06, duration: 2200, useNativeDriver: true }),
    ])).start();
  }, []);

  const fetchData = useCallback(async () => {
    try {
      const [sigRes, mktRes, histRes] = await Promise.all([
        mobileApi.getSignal(asset).catch(() => null),
        mobileApi.getMarketState().catch(() => null),
        mobileApi.getHistory(asset).catch(() => null),
      ]);
      if (sigRes?.signal) setSignal(sigRes.signal);
      if (mktRes?.ok) setMarket(mktRes);
      if (histRes) setHistory(histRes);
      // Non-blocking top-signal fetch (🔥 Signal of the Moment hero)
      mobileApi.getTopSignal().then(d => {
        if (d?.ok) setTopSignal(d.data);
      }).catch(() => {});
      // Non-blocking prediction fetch (for Home preview card)
      mobileApi.getPredictionChart('BTC', '30D').then(d => {
        if (d?.ok) setPredFull(d);
      }).catch(() => {});
      // Non-blocking portfolio fetch
      mobileApi.getPortfolioPerformance().then(d => { if (d?.ok) setPortfolioPerf(d); }).catch(() => {});
    } catch {} finally { setLoading(false); }
  }, [asset]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    if (Platform.OS !== 'web') hapticLight();
    await fetchData();
    setRefreshing(false);
  }, [fetchData]);

  useEffect(() => { setLoading(true); fetchData(); }, [fetchData]);

  // G1: detect "return_after_missed" — fires once if user came back to Home
  //      after having tapped the MISSED card on a prior visit.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const raw = await AsyncStorage.getItem('pending_return_after_missed');
        if (!raw) return;
        const payload = JSON.parse(raw);
        // Consume one-shot; fire event with original asset/signalId context.
        await AsyncStorage.removeItem('pending_return_after_missed');
        if (cancelled) return;
        track('return_after_missed', {
          asset: payload?.asset || null,
          signalId: payload?.signalId || null,
          source: 'missed',
          priority: 'MISSED',
          context: {
            screen: 'home',
            from: 'return_after_missed',
            delayMs: payload?.at ? Date.now() - payload.at : null,
          },
        });
      } catch {}
    })();
    return () => { cancelled = true; };
  }, []);

  // 🔥 Signal of the Moment — collapse state (persisted memory per signal.id).
  //   First view → FULL; revisit of same id → SLIM; new id → FULL again.
  // NOTE: Hook must be BEFORE any early return (React rules of hooks).
  useEffect(() => {
    if (!topSignal?.id) {
      setHeroCollapsed(false);
      return;
    }
    let cancelled = false;
    AsyncStorage.getItem(`hero_seen_${topSignal.id}`)
      .then(v => {
        if (!cancelled) setHeroCollapsed(!!v);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [topSignal?.id]);

  if (loading) {
    return <View style={s.center}><ActivityIndicator size="large" color={colors.accent} /><Text style={[s.loadText, { color: colors.textMuted }]}>{t('homeIntel.loadingIntelligence')}</Text></View>;
  }
  if (!signal) {
    return <View style={s.center}><Text style={[s.loadText, { color: colors.textMuted }]}>{t('homeIntel.noSignalData')}</Text><TouchableOpacity onPress={fetchData} style={[s.retryBtn, { backgroundColor: colors.accent }]}><Text style={{ color: '#fff', fontWeight: '700' }}>Retry</Text></TouchableOpacity></View>;
  }

  const ac = signal.action === 'BUY' ? colors.buy : signal.action === 'SELL' ? colors.sell : colors.textMuted;
  const conf = Math.round((signal.confidence || 0) * 100);
  const price = signal.price || market?.topSignal?.price || 0;
  const drivers = signal.drivers || [];
  const primary = drivers.find((d: any) => (d.confidence || 0) >= 0.5) || drivers[0];
  const supporting = drivers.filter((d: any) => d !== primary).slice(0, 2);

  const stats = history?.stats || {};
  const totalSig = stats.total || 0;
  const winRate = stats.winRate || stats.signalAccuracy || 0;
  const avgPnl = stats.avgPnlPct || 0;

  // Missed signals — Retention Loop (shown to ALL users including guests; mock fallback for speed)
  const realMissed = (history?.missedSignals || []).slice(0, 2);
  const isSignedIn = !!user?.id;
  const fallbackMissed = [{ asset: 'BTC', pnlPct: 4.5, timeAgo: '2h ago' }];
  const missed = realMissed.length > 0 ? realMissed : fallbackMissed;
  const hasRealHistory = realMissed.length > 0;

  // FORMING NOW counter (addiction loop — reason to come back)
  const formingFromDrivers = Math.max(signal.driverSummary?.neutral || 0, 0);
  const formingFromMarket = Number((market as any)?.formingSignals ?? (history as any)?.stats?.formingSignals ?? 0);
  const formingCount = Math.max(formingFromMarket, formingFromDrivers, 6);

  const showTopSignal = !!topSignal && topSignal.priority !== 'LOW';
  const handleTopSignalPress = () => {
    if (!topSignal) return;
    if (Platform.OS !== 'web') hapticMedium();
    trackAction('signal_of_moment_tap', {
      type: topSignal.type,
      source: topSignal.source,
      priority: topSignal.priority,
      asset: topSignal.asset,
      ageMinutes: topSignal.ageMinutes,
      collapsed: heroCollapsed,
    });
    // Mark seen — on the NEXT visit of Home this signal will render as slim bar.
    AsyncStorage.setItem(`hero_seen_${topSignal.id}`, String(Date.now())).catch(() => {});
    // Pass context to Edge/Feed for reinforcement copy + paywall urgency.
    setHeroEntry({
      signalId: topSignal.id,
      priority: topSignal.priority,
      type: topSignal.type,
      asset: topSignal.asset,
      sourcesCount: topSignal.sourcesCount || 0,
      at: Date.now(),
    });
    if (topSignal.asset) {
      setCurrentAsset(topSignal.asset);
      setIntelTab('EDGE');
    } else {
      setIntelTab('FEED');
    }
  };

  return (
    <>
    <ScrollView
      testID="home-screen"
      style={s.container}
      contentContainerStyle={s.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
    >
      {/* PHASE X · GLOBAL META-BRAIN IDENTITY (cross-app proof) */}
      <View style={{ paddingHorizontal: 16, paddingTop: 4 }}>
        <MetaBrainIdentityStrip variant="full" tappable />
        <AIValueNarrativeFeed
          layout="horizontal"
          title={t('homeIntel.whyThisAiMatters')}
          subtitle="recent decisions · narrative · not metrics"
          limit={5}
        />
      </View>

      {/* ═══ 🔥 SIGNAL OF THE MOMENT — Hero Card (TOP OF SCREEN) ═══
          The single most important push-router signal across all sources.
          Renders BEFORE market context so user sees the trigger first,
          then confirmation (main signal), then explanation (context).
          Hidden when priority === 'LOW' or no signal in the last 6h.
          Collapses to slim bar on revisit (AsyncStorage: hero_seen_<id>). */}
      {showTopSignal && topSignal && (
        <SignalOfMomentHero
          signal={topSignal}
          colors={colors}
          collapsed={heroCollapsed}
          onPress={handleTopSignalPress}
        />
      )}

      {/* ═══ 🔔 TELEGRAM FALLBACK — persistent nudge for users without TG ═══
          Gets signals 2–5 min earlier via Telegram. Shown only for FREE users
          or those without a Telegram provider linked. Quiet, not in-your-face. */}
      {!user?.authProviders?.telegram && (
        <TouchableOpacity
          activeOpacity={0.85}
          onPress={() => { setIntelTab('HOME'); /* Profile linking lives in account modal */ }}
          style={[
            s.telegramBanner,
            { backgroundColor: colors.accent + '0E', borderColor: colors.accent + '35' },
          ]}
        >
          <View style={[s.telegramBannerIcon, { backgroundColor: colors.accent + '1F' }]}>
            <Text style={{ fontSize: 14 }}>🔔</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[s.telegramBannerTitle, { color: colors.textPrimary }]} numberOfLines={1}>
              {t('home.tg.title')}
            </Text>
            <Text style={[s.telegramBannerSub, { color: colors.textMuted }]} numberOfLines={1}>
              {t('home.tg.sub')}
            </Text>
          </View>
          <Text style={[s.telegramBannerCta, { color: colors.accent }]}>{t('home.tg.cta')}</Text>
        </TouchableOpacity>
      )}

      {/* ═══ BLOCK 1: MAIN SIGNAL — EVENT, NOT DATA ═══ */}
      <View style={s.signalBlock}>
        {/* Stage state badge (FORMING / CONFIRMED / BREAKING DOWN) */}
        <View style={{ alignSelf: 'center', marginBottom: 8 }}>
          <SignalStateBadge
            stage={(signal as any).stage || (signal as any).decisionFramework?.stage || signal.stateLabel}
            action={signal.action}
            direction={signal.direction}
            isActive={signal.action !== 'WAIT'}
            timelineText={signal.timelineText}
          />
        </View>

        {/* Event title — the big framing shift */}
        {signal.eventTitle && signal.action !== 'WAIT' ? (
          <Text style={[s.eventTitle, { color: colors.textPrimary }]}>
            {signal.eventTitle}
          </Text>
        ) : null}

        <Animated.View style={[s.signalCore, { transform: [{ scale: scaleAnim }] }]}>
          <Animated.View style={[s.glow, { backgroundColor: ac, opacity: glowAnim }]} />
          <Text style={[s.signalAction, { color: ac }]}>{signal.action}</Text>
        </Animated.View>

        {price > 0 && (
          <Text style={[s.price, { color: colors.textPrimary }]}>${price.toLocaleString()}</Text>
        )}

        {/* Confidence interpretation (human-readable) instead of just bar */}
        {signal.confInterpretation ? (
          <Text style={[s.confInterpText, { color: ac }]}>
            {signal.confInterpretation}
          </Text>
        ) : null}

        {/* Confidence bar */}
        <View style={s.confRow}>
          <View style={[s.confBg, { backgroundColor: colors.border }]}>
            <View style={[s.confFill, { width: `${conf}%`, backgroundColor: ac }]} />
          </View>
          <Text style={[s.confText, { color: ac }]}>{conf}%</Text>
        </View>

        {/* Alignment chips */}
        <View style={s.alignRow}>
          {signal.driverSummary && (
            <>
              {signal.driverSummary.bullish > 0 && (
                <View style={[s.alignChip, { backgroundColor: colors.buy + '15' }]}>
                  <Text style={[s.alignChipText, { color: colors.buy }]}>{signal.driverSummary.bullish} {t('home.driver.bullish')}</Text>
                </View>
              )}
              {signal.driverSummary.neutral > 0 && (
                <View style={[s.alignChip, { backgroundColor: colors.textMuted + '12' }]}>
                  <Text style={[s.alignChipText, { color: colors.textMuted }]}>{signal.driverSummary.neutral} {t('home.driver.neutral')}</Text>
                </View>
              )}
              {signal.driverSummary.bearish > 0 && (
                <View style={[s.alignChip, { backgroundColor: colors.sell + '15' }]}>
                  <Text style={[s.alignChipText, { color: colors.sell }]}>{signal.driverSummary.bearish} {t('home.driver.bearish')}</Text>
                </View>
              )}
            </>
          )}
        </View>

        {/* Decision line — from backend summary, no frontend logic */}
        <Text style={[s.decisionLine, { color: colors.textMuted }]}>
          {signal.summary || t('home.scanningForAlignment')}
        </Text>

        {/* System watching indicator — restraint observability cue */}
        <View style={s.watchRow}>
          <LiveDot colors={colors} />
          <Text style={[s.watchText, { color: colors.textMuted }]}>
            {t('home.systemWatching')}
          </Text>
        </View>

        {/* Truth strip — system performance (restraint vocabulary) */}
        {signal.truth && !signal.truth.learning && signal.truth.totalTrades > 0 ? (
          <View style={[s.scarcityRow, { backgroundColor: colors.accent + '08' }]}>
            <Text style={{ fontSize: 10, fontWeight: '600', color: colors.textMuted }}>
              {t('home.truthStrip.observations')
                .replace('{n}', String(signal.truth.totalTrades))
                .replace('{pct}', String(Math.round(signal.truth.winRate * 100)))}
              {signal.truth.streak > 0
                ? ` · ${t('home.truthStrip.streak').replace('{n}', String(signal.truth.streak))}`
                : ''}
            </Text>
          </View>
        ) : signal.truth?.learning ? (
          <Text style={{ fontSize: 10, color: colors.textMuted, marginTop: 4, fontStyle: 'italic', textAlign: 'center' }}>
            {t('home.systemLearning')}
          </Text>
        ) : null}

        {/* Recent outcome chips */}
        {signal.truth?.recent && signal.truth.recent.length > 0 ? (
          <View style={{ flexDirection: 'row', gap: 4, marginTop: 4, justifyContent: 'center' }}>
            {signal.truth.recent.slice(0, 5).map((pnl: number, i: number) => (
              <View key={i} style={{ paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, backgroundColor: pnl > 0 ? colors.buy + '15' : colors.sell + '15' }}>
                <Text style={{ fontSize: 9, fontWeight: '700', color: pnl > 0 ? colors.buy : colors.sell }}>
                  {pnl > 0 ? '+' : ''}{pnl}%
                </Text>
              </View>
            ))}
          </View>
        ) : null}

        {/* Scarcity marker */}
        {signal.scarcityText && signal.action !== 'WAIT' ? (
          <View style={[s.scarcityRow, { backgroundColor: colors.accent + '08' }]}>
            <Ionicons name="diamond-outline" size={11} color={colors.accent} />
            <Text style={[s.scarcityText, { color: colors.textMuted }]}>
              {signal.scarcityText}
            </Text>
          </View>
        ) : null}

        {/* Loss aversion text */}
        {signal.lossText && signal.action !== 'WAIT' ? (
          <Text style={[s.lossText, { color: colors.sell + 'CC' }]}>
            {signal.lossText}
          </Text>
        ) : null}
      </View>

        {/* ═══ BTC PREDICTION SNAPSHOT — CORE LAYER (integrated, not a button) ═══ */}
        {(() => {
          const p = predFull;
          const activeTf = p?.timeframes?.find((t: any) => t.key === (p?.activeHorizon || '30D'));
          const dir = String(activeTf?.direction || p?.summary?.bias || 'NEUTRAL').toUpperCase();
          const bias = dir.includes('BULL') || dir === 'UP' ? t('home.bias.bullish')
                     : dir.includes('BEAR') || dir === 'DOWN' ? t('home.bias.bearish') : t('home.bias.neutral');
          const predColor = bias === t('home.bias.bullish') ? colors.buy : bias === t('home.bias.bearish') ? colors.sell : colors.textMuted;
          const biasEmoji = bias === t('home.bias.bullish') ? '↑' : bias === t('home.bias.bearish') ? '↓' : '→';
          const confPct = p?.summary?.confidence ?? 0;           // agreement
          const convPct = p?.summary?.conviction ?? 0;           // strength
          const move = p?.summary?.expectedMove ?? '';
          const hasConflict = !!p?.summary?.hasConflict;
          const bullD = p?.summary?.bullishDrivers || [];
          const bearD = p?.summary?.bearishDrivers || [];
          const marketState = p?.summary?.marketState || 'SCANNING';
          const stateText = p?.summary?.marketStateText || '';
          const stateColorName = p?.summary?.marketStateColor || 'gray';
          const stateColor = stateColorName === 'green' ? colors.buy
                           : stateColorName === 'red' ? colors.sell
                           : stateColorName === 'gold' ? '#FFB020'
                           : colors.textMuted;

          // Mini sparkline geometry
          const series = [
            ...(p?.priceSeries?.slice(-20) || []),
            ...(activeTf?.projectedSeries?.slice(0, 20) || []),
          ];
          const historyLen = Math.min(20, p?.priceSeries?.length || 0);
          const W = 120, H = 32;
          let sparkPath = '', projPath = '';
          let nowX = 0, nowY = 0, endX = 0, endY = 0;
          if (series.length > 1) {
            const vals = series.map(s => s.v).filter(v => v > 0);
            const mn = Math.min(...vals), mx = Math.max(...vals);
            const xF = (i: number) => (i / (series.length - 1)) * W;
            const yF = (v: number) => H - ((v - mn) / Math.max(mx - mn, 1)) * H;
            sparkPath = series.slice(0, historyLen).map((s, i) => `${i === 0 ? 'M' : 'L'}${xF(i).toFixed(1)},${yF(s.v).toFixed(1)}`).join(' ');
            if (historyLen > 0 && series.length > historyLen) {
              nowX = xF(historyLen - 1);
              nowY = yF(series[historyLen - 1].v);
              projPath = `M${nowX.toFixed(1)},${nowY.toFixed(1)} ` + series.slice(historyLen).map((s, i) => `L${xF(historyLen + i).toFixed(1)},${yF(s.v).toFixed(1)}`).join(' ');
              const lastIdx = series.length - 1;
              endX = xF(lastIdx);
              endY = yF(series[lastIdx].v);
            }
          }

          return (
            <TouchableOpacity
              testID="home-view-prediction"
              style={s.predSnapshot}
              activeOpacity={0.75}
              onPress={() => {
                if (Platform.OS !== 'web') hapticMedium();
                trackAction('prediction_opened', { source: 'home' });
                setPredictionVisible(true);
              }}
            >
              {/* Divider on top to visually chain from main decision */}
              <View style={[s.predDivider, { backgroundColor: colors.border }]} />

              {/* Label row */}
              <View style={s.predSnapHeader}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <Text style={[s.predSnapLabel, { color: predColor }]}>{t('homeIntel.predictionSnapshot')}</Text>
                  {marketState && marketState !== 'SCANNING' && (
                    <View style={[s.stateChip, { borderColor: stateColor + '66', backgroundColor: stateColor + '18' }]}>
                      <Text style={[s.stateChipT, { color: stateColor }]}>{marketState.replace('_', ' ')}</Text>
                    </View>
                  )}
                </View>
                <Text style={[s.predSnapHorizon, { color: colors.textMuted }]}>
                  {p?.activeHorizon || '30D'} · MetaBrain
                </Text>
              </View>

              {/* Main row: bias + sparkline */}
              <View style={s.predSnapMain}>
                <View style={{ flex: 1 }}>
                  <Text style={[s.predSnapBias, { color: predColor }]}>
                    BTC {biasEmoji} {bias}
                  </Text>
                  {!!move && (
                    <Text style={[s.predSnapMove, { color: colors.textSecondary }]}>
                      {t('home.expectedPrefix')} {move}
                    </Text>
                  )}
                </View>

                {sparkPath ? (
                  <Svg width={W} height={H + 4}>
                    <Defs>
                      <SvgLG id="homeProjFade" x1="0" y1="0" x2="1" y2="0">
                        <Stop offset="0" stopColor={predColor} stopOpacity="1" />
                        <Stop offset="1" stopColor={predColor} stopOpacity="0.3" />
                      </SvgLG>
                    </Defs>
                    <Path d={sparkPath} fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth={1.2} />
                    {projPath ? (
                      <Path d={projPath} fill="none" stroke="url(#homeProjFade)" strokeWidth={1.8} strokeDasharray="3,2" />
                    ) : null}
                    {projPath ? (
                      <>
                        <Circle cx={nowX} cy={nowY} r={2.2} fill={predColor} />
                        <Circle cx={endX} cy={endY} r={2.2} fill={predColor} opacity={0.6} />
                      </>
                    ) : null}
                  </Svg>
                ) : null}
              </View>

              {/* Dual-metric row: confidence (agreement) + conviction (strength) */}
              <View style={s.predMetricsRow}>
                <View style={s.predMetricCol}>
                  <Text style={[s.predMetricVal, { color: colors.textPrimary }]}>{confPct}%</Text>
                  <Text style={[s.predMetricLbl, { color: colors.textMuted }]}>{t('home.metric.agreement')}</Text>
                </View>
                <View style={[s.predMetricSep, { backgroundColor: colors.border }]} />
                <View style={s.predMetricCol}>
                  <Text style={[s.predMetricVal, { color: colors.textPrimary }]}>{convPct}%</Text>
                  <Text style={[s.predMetricLbl, { color: colors.textMuted }]}>{t('home.metric.conviction')}</Text>
                </View>
                <View style={[s.predMetricSep, { backgroundColor: colors.border }]} />
                <View style={s.predMetricCol}>
                  <Ionicons name="chevron-forward" size={14} color={predColor} style={{ alignSelf: 'center' }} />
                  <Text style={[s.predMetricLbl, { color: colors.textMuted, textAlign: 'center' }]}>{t('home.metric.details')}</Text>
                </View>
              </View>

              {/* State / Conflict callout — shown when not CALM/ALIGNED */}
              {['TENSION', 'CONFLICT', 'BREAKOUT_FORMING'].includes(marketState) && !!stateText && (
                <View style={[s.predConflict, { borderColor: stateColor + '55', backgroundColor: stateColor + '10' }]}>
                  <Ionicons
                    name={marketState === 'TENSION' ? 'flash' : marketState === 'BREAKOUT_FORMING' ? 'rocket-outline' : 'git-compare-outline'}
                    size={13}
                    color={stateColor}
                  />
                  <Text style={[s.predConflictText, { color: colors.textPrimary }]} numberOfLines={2}>
                    {stateText}
                  </Text>
                </View>
              )}
            </TouchableOpacity>
          );
        })()}

      {/* ═══ BLOCK 2: MARKET CONTEXT (explanation — after the decision) ═══
          Moved AFTER main signal: user first sees the trigger (hero),
          then the decision (main signal), then the context that frames it. */}
      {market && (
        <View style={[s.contextRow, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <View style={[s.liveDot, { backgroundColor: colors.buy }]} />
          <Text style={[s.contextLabel, { color: colors.textMuted }]}>Market:</Text>
          <Text style={[s.contextValue, { color: market.bias === 'Bullish' ? colors.buy : market.bias === 'Bearish' ? colors.sell : colors.textSecondary }]}>
            {market.bias}
          </Text>
          <Text style={[s.contextSep, { color: colors.textMuted }]}>·</Text>
          <Text style={[s.contextValue, { color: colors.textSecondary }]}>{market.market}</Text>
        </View>
      )}

      {/* ═══ BLOCK 1.5: YOUR PORTFOLIO — EMOTIONAL ANCHOR ═══ */}
      {portfolioPerf && portfolioPerf.positions && portfolioPerf.positions.length > 0 && (() => {
        const totalPnl = portfolioPerf.totalPnlPct || 0;
        const totalColor = totalPnl >= 0 ? colors.buy : colors.sell;
        const sorted = [...portfolioPerf.positions].sort((a: any, b: any) => (b.pnlPct || 0) - (a.pnlPct || 0));
        const leader = sorted[0];
        const leaderPnl = leader?.pnlPct || 0;

        // Emotional insight based on PnL
        const insight = totalPnl > 3 ? "System is delivering. You trusted it."
          : totalPnl > 1 ? "You're ahead of the market."
          : totalPnl > 0 ? "Positioned. Momentum building."
          : totalPnl > -1 ? "Positioned. Waiting for the move."
          : totalPnl > -3 ? "Position early. Not wrong yet."
          : "Pressure building. Patience is the edge.";

        return (
          <TouchableOpacity
            style={[s.pfCard, { borderColor: totalColor + '20', backgroundColor: colors.surface }]}
            onPress={() => setIntelTab('FEED')}
            activeOpacity={0.7}
          >
            {/* Header row: label + "today" */}
            <View style={s.pfHeader}>
              <Text style={[s.pfLabel, { color: colors.accent }]}>{t('homeIntel.yourPortfolio')}</Text>
              <Text style={[s.pfToday, { color: colors.textMuted }]}>today</Text>
            </View>

            {/* BIG PnL — the emotional anchor */}
            <Text style={[s.pfHeroPnl, { color: totalColor }]}>
              {totalPnl >= 0 ? '+' : ''}{totalPnl.toFixed(1)}%
            </Text>

            {/* Leader highlight */}
            {leader && leaderPnl !== 0 && (
              <View style={[s.pfLeaderRow, { backgroundColor: totalColor + '08' }]}>
                <CoinIcon symbol={leader.symbol} size={16} />
                <Text style={[s.pfLeaderText, { color: totalColor }]}>
                  {leader.symbol} {leaderPnl >= 0 ? 'leading' : 'lagging'} {leaderPnl >= 0 ? '+' : ''}{leaderPnl.toFixed(1)}%
                </Text>
              </View>
            )}

            {/* Position rows */}
            {sorted.slice(0, 3).map((p: any, i: number) => {
              const pnl = p.pnlPct || 0;
              const pc = pnl >= 0 ? colors.buy : colors.sell;
              return (
                <View key={i} style={s.pfRow}>
                  <View style={s.pfRowLeft}>
                    <CoinIcon symbol={p.symbol} size={18} />
                    <Text style={[s.pfSymbol, { color: colors.textPrimary }]}>{p.symbol}</Text>
                    <Text style={[s.pfRole, { color: colors.textMuted }]}>{p.roleLabel || p.role}</Text>
                  </View>
                  <Text style={[s.pfPnl, { color: pc }]}>
                    {pnl >= 0 ? '+' : ''}{pnl.toFixed(1)}%
                  </Text>
                </View>
              );
            })}

            {/* Emotional insight */}
            <Text style={[s.pfInsight, { color: colors.textMuted }]}>{insight}</Text>
            <Text style={[s.pfCta, { color: colors.accent }]}>See full positioning →</Text>
            {/* PnL SHARE TRIGGER — after portfolio profit */}
            {totalPnl > 1.5 && <ShareTrigger type="profit" asset={leader?.asset || asset} pnl={leaderPnl} />}
          </TouchableOpacity>
        );
      })()}

      {/* ═══ BLOCK 2: TRADE SETUP (🔒 PRO) ═══ */}
      <View style={[s.card, { borderColor: colors.border, backgroundColor: colors.surface }]}>
        <Text style={[s.cardLabel, { color: colors.textMuted }]}>{t('homeIntel.tradeSetup')}</Text>
        {signal.action === 'WAIT' ? (
          <View style={s.noSetup}>
            <Ionicons name="pulse-outline" size={20} color={colors.accent} />
            <Text style={[s.noSetupText, { color: colors.textSecondary }]}>Nothing confirmed yet — but pressure building.</Text>
          </View>
        ) : !signal.entryZone && !signal.stopLoss && !signal.takeProfit ? (
          /* Honest state: signal exists but setup not fully confirmed */
          <View style={s.noSetup}>
            <Ionicons name="time-outline" size={20} color={colors.accent} />
            <Text style={[s.noSetupText, { color: colors.textSecondary }]}>{t('homeIntel.noEntryYetMarketPreparing')}</Text>
          </View>
        ) : (
          <>
            {[
              { label: 'Entry', value: signal.entryZone, color: ac },
              { label: 'Invalidation', value: signal.stopLoss, color: colors.sell },
              { label: 'Target', value: signal.takeProfit, color: colors.buy },
            ].map((item, i) => (
              <View key={i}>
                <View style={s.setupRow}>
                  <View style={s.setupLeft}>
                    <View style={[s.setupDot, { backgroundColor: item.color }]} />
                    <Text style={[s.setupLabel, { color: colors.textMuted }]}>{item.label}</Text>
                  </View>
                  {isPro && item.value ? (
                    <Text style={[s.setupValue, { color: item.color }]}>{item.value}</Text>
                  ) : isPro ? (
                    <Text style={[s.setupNA, { color: colors.textMuted }]}>pending</Text>
                  ) : (
                    <TouchableOpacity onPress={() => openPaywall('contextual')} style={s.setupLockRow}>
                      {/* Blurred-looking fake value + lock overlay for FREE users */}
                      <Text style={[s.setupBlurred, { color: colors.textMuted }]}>••••••</Text>
                      <View style={[s.proPill, { backgroundColor: colors.accent, borderColor: colors.accent }]}>
                        <Ionicons name="lock-closed" size={10} color={colors.accentText} />
                        <Text style={[s.proText, { color: colors.accentText }]}>PRO</Text>
                      </View>
                    </TouchableOpacity>
                  )}
                </View>
                {i < 2 && <View style={[s.divider, { backgroundColor: colors.border }]} />}
              </View>
            ))}
          </>
        )}
        {!isPro && signal.action !== 'WAIT' && (
          <MomentPaywall type="edge" asset={asset} />
        )}
      </View>

      {/* ═══ BLOCK 3: KEY INSIGHT ═══ */}
      <View style={[s.insightCard, { backgroundColor: colors.surface, borderLeftColor: colors.accent }]}>
        <View style={s.insightHeader}>
          <Ionicons name="bulb" size={13} color={colors.accent} />
          <Text style={[s.insightLabel, { color: colors.accent }]}>{t('homeIntel.keyInsight')}</Text>
        </View>
        <Text style={[s.insightBody, { color: colors.textSecondary }]}>
          {signal.summary || 'No clear signal — waiting for market direction'}
        </Text>
      </View>

      {/* ═══ BLOCK 4: TRACK RECORD ═══ */}
      {totalSig > 0 && (
        <View style={[s.card, { borderColor: colors.border, backgroundColor: colors.surface }]}>
          <Text style={[s.cardLabel, { color: colors.textMuted }]}>{t('homeIntel.systemPerformance')}</Text>
          <View style={s.perfRow}>
            <View style={s.perfItem}>
              <Text style={[s.perfValue, { color: colors.textPrimary }]}>{totalSig}</Text>
              <Text style={[s.perfLabel, { color: colors.textMuted }]}>signals</Text>
            </View>
            <View style={s.perfItem}>
              <Text style={[s.perfValue, { color: winRate >= 50 ? colors.buy : colors.sell }]}>{Math.round(winRate)}%</Text>
              <Text style={[s.perfLabel, { color: colors.textMuted }]}>accuracy</Text>
            </View>
            <View style={s.perfItem}>
              <Text style={[s.perfValue, { color: avgPnl >= 0 ? colors.buy : colors.sell }]}>{avgPnl >= 0 ? '+' : ''}{avgPnl.toFixed(1)}%</Text>
              <Text style={[s.perfLabel, { color: colors.textMuted }]}>avg move</Text>
            </View>
          </View>

          {hasRealHistory && realMissed.length > 0 && (
            <View style={[s.missedWrap, { borderTopColor: colors.border }]}>
              <Text style={[s.missedTitle, { color: colors.textMuted }]}>Missed:</Text>
              {realMissed.map((m: any, i: number) => (
                <View key={i} style={[s.missedBadge, { backgroundColor: (m.pnlPct >= 0 ? colors.buy : colors.sell) + '15' }]}>
                  <Text style={[s.missedBadgeText, { color: m.pnlPct >= 0 ? colors.buy : colors.sell }]}>
                    {m.asset} {m.pnlPct >= 0 ? '+' : ''}{m.pnlPct?.toFixed(1)}%
                  </Text>
                </View>
              ))}
            </View>
          )}
        </View>
      )}

      {/* ═══ BLOCK 5: RETENTION LOOP — Missed signals (FOMO trigger, shown to ALL) ═══ */}
      {missed.length > 0 && (() => {
        const lead = missed[0];
        const pnl = Math.abs(lead.pnlPct || 0);
        const headline = isSignedIn && hasRealHistory
          ? 'You saw this. You hesitated.'
          : `${lead.asset} moved +${pnl.toFixed(1)}% without you`;
        const subline = isSignedIn && hasRealHistory
          ? `${lead.asset} ${lead.pnlPct >= 0 ? '+' : ''}${pnl.toFixed(1)}% since signal. You were early, but didn't act.`
          : 'You were early, but didn\'t act.';
        const missedCtx = {
          screen: 'home',
          from: 'missed',
          asset: lead.asset,
          hasRealHistory,
          leadPnlPct: lead.pnlPct,
        };
        // G1: missed_seen (fire-once guard handled by analytics dedupe window)
        track('missed_seen', {
          asset: lead.asset,
          signalId: lead.signalId || lead.id || null,
          source: 'missed',
          priority: 'MISSED',
          context: missedCtx,
        });
        return (
          <TouchableOpacity
            testID="home-missed-retention"
            style={[
              s.missedEdgeCard,
              {
                borderColor: colors.sell + '40',
                backgroundColor: colors.sell + '08',
              },
            ]}
            onPress={() => {
              if (Platform.OS !== 'web') hapticMedium();
              track('missed_click', {
                asset: lead.asset,
                signalId: lead.signalId || lead.id || null,
                source: 'missed',
                priority: 'MISSED',
                context: missedCtx,
              });
              // Mark pending return-after-missed, to be resolved on next Home mount.
              try {
                AsyncStorage.setItem('pending_return_after_missed', JSON.stringify({
                  asset: lead.asset,
                  signalId: lead.signalId || lead.id || null,
                  at: Date.now(),
                }));
              } catch {}
              setIntelTab('EDGE');
            }}
            activeOpacity={0.85}
          >
            <View style={s.missedEdgeHeader}>
              <Ionicons name="warning" size={15} color={colors.sell} />
              <Text style={[s.missedEdgeTitle, { color: colors.sell }]}>{t('homeIntel.missedSignal')}</Text>
              {!hasRealHistory && (
                <Text style={{ fontSize: 9, color: colors.textMuted, marginLeft: 'auto', fontWeight: '600' }}>
                  {(lead as any).timeAgo || 'recent'}
                </Text>
              )}
            </View>

            <Text style={{ fontSize: 16, fontWeight: '800', color: colors.textPrimary, marginTop: 6 }}>
              {headline}
            </Text>
            <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 4, lineHeight: 19 }}>
              {subline}
            </Text>

            {/* Hope line — боль → надежда (баланс интенсивности) */}
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 10 }}>
              <LiveDot color={colors.wait} size={6} colors={colors} />
              <Text style={{ fontSize: 12, fontWeight: '700', color: colors.wait }}>
                Next setup forming now
              </Text>
            </View>

            {/* Explicit CTA — drives tap to EDGE (second-chance setup, never back to old signal) */}
            <Text style={{
              fontSize: 13,
              fontWeight: '800',
              color: colors.accent,
              marginTop: 10,
              letterSpacing: 0.2,
            }}>
              → Don't miss next one
            </Text>

            {/* Additional missed items if real history */}
            {hasRealHistory && missed.length > 1 && (
              <View style={{ flexDirection: 'row', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
                {missed.slice(1, 3).map((m: any, i: number) => (
                  <View
                    key={i}
                    style={{
                      flexDirection: 'row',
                      alignItems: 'center',
                      gap: 4,
                      paddingHorizontal: 8,
                      paddingVertical: 3,
                      borderRadius: 6,
                      backgroundColor: colors.sell + '12',
                    }}
                  >
                    <Text style={{ fontSize: 11, fontWeight: '700', color: colors.textPrimary }}>
                      {m.asset}
                    </Text>
                    <Text style={{ fontSize: 11, fontWeight: '700', color: m.pnlPct >= 0 ? colors.buy : colors.sell }}>
                      {m.pnlPct >= 0 ? '+' : ''}{(m.pnlPct || 0).toFixed(1)}%
                    </Text>
                  </View>
                ))}
              </View>
            )}

            {/* CTA row */}
            <View
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                gap: 6,
                marginTop: 14,
                paddingTop: 12,
                borderTopWidth: StyleSheet.hairlineWidth,
                borderTopColor: colors.sell + '30',
              }}
            >
              <Ionicons name="arrow-forward" size={15} color={colors.accent} />
              <Text style={{ fontSize: 14, fontWeight: '800', color: colors.accent, flex: 1 }}>
                Don't miss next one
              </Text>
              <Ionicons name="chevron-forward" size={15} color={colors.accent} />
            </View>

            {/* REGRET triggers — only when we have real history */}
            {hasRealHistory && (
              <>
                <ShareTrigger type="regret" asset={lead.asset} pnl={pnl} />
                <MomentPaywall type="regret" asset={lead.asset} pnl={pnl} />
              </>
            )}
          </TouchableOpacity>
        );
      })()}

      {/* ═══ BLOCK 5.5: FORMING NOW (Addiction loop — reason to come back) ═══ */}
      {formingCount > 0 && (
        <TouchableOpacity
          testID="home-forming-now"
          style={[
            s.formingCard,
            {
              borderColor: colors.wait + '40',
              backgroundColor: colors.wait + '0D',
            },
          ]}
          onPress={() => { if (Platform.OS !== 'web') hapticLight(); setIntelTab('EDGE'); }}
          activeOpacity={0.85}
        >
          <View style={[s.formingDotHost, { backgroundColor: colors.wait + '20' }]}>
            <LiveDot color={colors.wait} size={8} colors={colors} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[s.formingTitle, { color: colors.textPrimary }]}>
              {formingCount} signals forming right now
            </Text>
            <Text style={[s.formingSub, { color: colors.textSecondary }]}>
              Market is building pressure. Check back shortly.
            </Text>
            <Text style={[s.formingHint, { color: colors.wait }]}>
              → See what's forming
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.wait} />
        </TouchableOpacity>
      )}

      {/* ═══ BLOCK 6: DRIVERS ═══ */}
      <View style={[s.card, { borderColor: colors.border, backgroundColor: colors.surface }]}>
        <Text style={[s.cardLabel, { color: colors.textMuted }]}>{t('homeIntel.whatSDrivingTheMarket')}</Text>

        {/* Primary driver — from backend insight, no frontend logic */}
        {primary && (
          <View style={[s.primaryDriver, { borderLeftColor: primary.direction === 'Bullish' ? colors.buy : primary.direction === 'Bearish' ? colors.sell : colors.textMuted }]}>
            <Text style={[s.driverModuleName, { color: colors.textPrimary }]}>{primary.name}</Text>
            <Text style={[s.driverHuman, { color: colors.textSecondary }]}>
              {primary.insight || primary.reason || primary.value || 'Monitoring'}
            </Text>
          </View>
        )}

        {/* Supporting — render backend insight directly */}
        {supporting.length > 0 && (
          <View style={s.supportingList}>
            {supporting.map((d: any, i: number) => {
              const dc = d.direction === 'Bullish' ? colors.buy : d.direction === 'Bearish' ? colors.sell : colors.textMuted;
              return (
                <View key={i} style={s.supportingRow}>
                  <View style={[s.supportingDot, { backgroundColor: dc }]} />
                  <Text style={[s.supportingLabel, { color: colors.textSecondary }]}>{d.name}:</Text>
                  <Text style={[s.supportingValue, { color: dc }]} numberOfLines={1}>
                    {d.insight || d.reason || d.value || 'Monitoring'}
                  </Text>
                </View>
              );
            })}
          </View>
        )}
      </View>

      {/* ═══ BLOCK 6: CTA ═══ */}
      <View style={s.ctaBlock}>
        <View style={s.ctaRow}>
          <TouchableOpacity
            testID="home-view-signal"
            style={[s.ctaSecondary, { borderColor: colors.border, backgroundColor: colors.surface }]}
            onPress={() => setIntelTab('SIGNALS')}
          >
            <Ionicons name="analytics-outline" size={14} color={colors.textSecondary} />
            <Text style={[s.ctaSecText, { color: colors.textSecondary }]}>{t('homeIntel.viewFullSignal')}</Text>
          </TouchableOpacity>

          <TouchableOpacity
            testID="home-view-edge"
            style={[s.ctaTertiary, { borderColor: colors.border }]}
            onPress={() => { if (Platform.OS !== 'web') hapticLight(); setIntelTab('EDGE'); }}
          >
            <Ionicons name="diamond-outline" size={14} color={colors.textMuted} />
            <Text style={[s.ctaTerText, { color: colors.textMuted }]}>{t('homeIntel.earlyEdge')}</Text>
          </TouchableOpacity>
        </View>

        {/* Terminal link — soft, secondary */}
        <TouchableOpacity
          testID="home-open-terminal"
          style={[s.terminalLink, { borderColor: colors.border }]}
          onPress={() => { if (Platform.OS !== 'web') hapticLight(); switchToTrading(); }}
        >
          <Ionicons name="swap-horizontal" size={14} color={colors.textMuted} />
          <Text style={[s.terminalText, { color: colors.textMuted }]}>{t('homeIntel.openTerminal')}</Text>
        </TouchableOpacity>
      </View>

      <View style={{ height: 24 }} />
    </ScrollView>

    <Modal
      visible={predictionVisible}
      animationType="slide"
      presentationStyle="fullScreen"
      statusBarTranslucent
      onRequestClose={() => setPredictionVisible(false)}
    >
      <PredictionScreen onClose={() => setPredictionVisible(false)} />
    </Modal>
    </>
  );
}

/* ═══════════ STYLES ═══════════ */
const mk = (c: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: c.background },
  content: { paddingHorizontal: 20, paddingTop: 4, paddingBottom: 40 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: c.background, gap: 12 },
  loadText: { fontSize: 13 },
  retryBtn: { paddingHorizontal: 20, paddingVertical: 10, borderRadius: 10 },

  /* Context */
  contextRow: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, borderWidth: 1, marginBottom: 12 },
  liveDot: { width: 6, height: 6, borderRadius: 3 },
  contextLabel: { fontSize: 11, fontWeight: '600' },
  contextValue: { fontSize: 11, fontWeight: '700' },
  contextSep: { fontSize: 11 },

  /* Main Signal — Event Frame */
  signalBlock: { alignItems: 'center', paddingVertical: 12, marginBottom: 8 },
  telegramBanner: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    borderWidth: 1, borderRadius: 12,
    paddingHorizontal: 12, paddingVertical: 10,
    marginBottom: 14,
  },
  telegramBannerIcon: {
    width: 28, height: 28, borderRadius: 14,
    alignItems: 'center', justifyContent: 'center',
  },
  telegramBannerTitle: { fontSize: 13, fontWeight: '700' },
  telegramBannerSub: { fontSize: 11, fontWeight: '500', marginTop: 1 },
  telegramBannerCta: { fontSize: 12, fontWeight: '700' },
  stateBadge: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8, marginBottom: 8 },
  stateDot: { width: 6, height: 6, borderRadius: 3 },
  stateBadgeText: { fontSize: 10, fontWeight: '800', letterSpacing: 1 },
  stateTimeline: { fontSize: 10, fontWeight: '500' },
  eventTitle: { fontSize: 17, fontWeight: '800', textAlign: 'center', marginBottom: 4, letterSpacing: -0.3 },
  signalCore: { alignItems: 'center', position: 'relative' },
  glow: { position: 'absolute', width: 200, height: 200, borderRadius: 100, top: -55, zIndex: -1 },
  signalAction: { fontSize: 64, fontWeight: '900', letterSpacing: 4 },
  price: { fontSize: 22, fontWeight: '700', marginTop: 2 },
  confInterpText: { fontSize: 12, fontWeight: '600', marginTop: 6, marginBottom: 2 },
  confRow: { flexDirection: 'row', alignItems: 'center', gap: 10, width: '65%', marginTop: 6 },
  confBg: { flex: 1, height: 4, borderRadius: 2, overflow: 'hidden' },
  confFill: { height: '100%', borderRadius: 2 },
  confText: { fontSize: 14, fontWeight: '700', width: 36, textAlign: 'right' },
  alignRow: { flexDirection: 'row', gap: 8, marginTop: 8 },
  alignChip: { paddingHorizontal: 10, paddingVertical: 3, borderRadius: 12 },
  alignChipText: { fontSize: 11, fontWeight: '600' },
  decisionLine: { fontSize: 13, marginTop: 8, fontStyle: 'italic' },
  scarcityRow: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 8, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8 },
  scarcityText: { fontSize: 10, fontWeight: '500' },
  lossText: { fontSize: 10, fontWeight: '600', fontStyle: 'italic', marginTop: 6, textAlign: 'center' },

  /* Live dot + watching line */
  watchRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8 },
  watchText: { fontSize: 11, fontWeight: '600', letterSpacing: 0.4 },

  /* Forming now — addiction loop pulse */
  formingCard: { flexDirection: 'row', alignItems: 'center', gap: 10, borderRadius: 14, paddingHorizontal: 16, paddingVertical: 14, borderWidth: 1, marginBottom: 10 },
  formingDotHost: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  formingTitle: { fontSize: 15, fontWeight: '800', letterSpacing: -0.2 },
  formingSub: { fontSize: 12, fontWeight: '500', marginTop: 2 },
  formingHint: { fontSize: 11, fontWeight: '700', marginTop: 4 },

  /* Trade Setup */
  card: { borderRadius: 14, padding: 16, borderWidth: 1, marginBottom: 10 },
  cardLabel: { fontSize: 10, fontWeight: '800', letterSpacing: 1.5, marginBottom: 12 },
  /* Portfolio PnL — Emotional Anchor */
  pfCard: { borderRadius: 14, padding: 16, borderWidth: 1, marginBottom: 10 },
  pfHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  pfLabel: { fontSize: 10, fontWeight: '800', letterSpacing: 1.5 },
  pfToday: { fontSize: 10, fontWeight: '600' },
  pfHeroPnl: { fontSize: 42, fontWeight: '900', letterSpacing: -1, marginBottom: 4, fontVariant: ['tabular-nums'] as any },
  pfLeaderRow: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8, marginBottom: 10 },
  pfLeaderText: { fontSize: 12, fontWeight: '700' },
  pfTotalBig: { fontSize: 28, fontWeight: '800', marginBottom: 10 },
  pfRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 6 },
  pfRowLeft: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  pfSymbol: { fontSize: 14, fontWeight: '700' },
  pfRole: { fontSize: 10, fontWeight: '500', opacity: 0.6 },
  pfStatus: { fontSize: 10, fontWeight: '600', flex: 1, textAlign: 'right', marginRight: 10 },
  pfPnl: { fontSize: 14, fontWeight: '700', minWidth: 50, textAlign: 'right' },
  pfInsight: { fontSize: 11, fontStyle: 'italic', marginTop: 10 },
  pfCta: { fontSize: 12, fontWeight: '600', marginTop: 6 },
  noSetup: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 8 },
  noSetupText: { fontSize: 14 },
  setupRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 10 },
  setupLeft: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  setupDot: { width: 6, height: 6, borderRadius: 3 },
  setupLabel: { fontSize: 14, fontWeight: '500' },
  setupValue: { fontSize: 16, fontWeight: '700', fontVariant: ['tabular-nums'] },
  setupNA: { fontSize: 14 },
  divider: { height: StyleSheet.hairlineWidth },
  proPill: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 10, borderWidth: 1 },
  proText: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5 },
  setupLockRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  setupBlurred: { fontSize: 15, fontWeight: '700', letterSpacing: 3, opacity: 0.55 },
  proHint: { fontSize: 11, textAlign: 'center', marginTop: 8, fontStyle: 'italic' },

  /* Insight */
  insightCard: { borderRadius: 14, padding: 16, marginBottom: 10, borderLeftWidth: 3 },
  insightHeader: { flexDirection: 'row', alignItems: 'center', gap: 5, marginBottom: 8 },
  insightLabel: { fontSize: 9, fontWeight: '700', letterSpacing: 1 },
  insightBody: { fontSize: 15, lineHeight: 22, fontWeight: '500' },

  /* Track Record */
  perfRow: { flexDirection: 'row', justifyContent: 'space-around' },
  perfItem: { alignItems: 'center' },
  perfValue: { fontSize: 20, fontWeight: '800' },
  perfLabel: { fontSize: 11, marginTop: 2 },
  missedWrap: { borderTopWidth: 1, marginTop: 12, paddingTop: 10, flexDirection: 'row', flexWrap: 'wrap', gap: 8, alignItems: 'center' },
  missedTitle: { fontSize: 12, fontWeight: '600' },
  missedBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  missedBadgeText: { fontSize: 12, fontWeight: '700' },

  /* Missed Edge */
  missedEdgeCard: { borderRadius: 14, padding: 16, borderWidth: 1, marginBottom: 10 },
  missedEdgeHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 10 },
  missedEdgeTitle: { fontSize: 10, fontWeight: '800', letterSpacing: 1.5 },
  missedEdgeRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 4 },
  missedEdgeAsset: { fontSize: 14, fontWeight: '700', width: 40 },
  missedEdgePnl: { fontSize: 16, fontWeight: '800' },
  missedEdgeHint: { fontSize: 11, flex: 1 },
  missedEdgeCta: { fontSize: 12, fontWeight: '600', marginTop: 10, fontStyle: 'italic' },

  /* Drivers */
  primaryDriver: { borderLeftWidth: 3, paddingLeft: 12, paddingVertical: 6, marginBottom: 10 },
  driverModuleName: { fontSize: 13, fontWeight: '700', marginBottom: 2 },
  driverHuman: { fontSize: 14, lineHeight: 20 },
  supportingList: { gap: 8 },
  supportingRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  supportingDot: { width: 5, height: 5, borderRadius: 3 },
  supportingLabel: { fontSize: 12, fontWeight: '600' },
  supportingValue: { fontSize: 12, flex: 1 },

  /* CTA */
  ctaBlock: { marginTop: 6 },
  ctaRow: { flexDirection: 'row', gap: 10, marginTop: 10 },
  ctaSecondary: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, borderRadius: 10, borderWidth: 1 },
  ctaSecText: { fontSize: 12, fontWeight: '600' },
  ctaTertiary: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, paddingVertical: 10, borderRadius: 10, borderWidth: 1 },
  ctaTerText: { fontSize: 12, fontWeight: '500' },
  terminalLink: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, borderRadius: 8, borderWidth: 1, marginTop: 8 },
  terminalText: { fontSize: 12, fontWeight: '500' },
  predictionLink: { flexDirection: 'row', alignItems: 'center', padding: 14, borderRadius: 12, borderWidth: 1, marginTop: 10, marginHorizontal: 16 },
  predLinkTitle: { fontSize: 14, fontWeight: '700' },
  predLinkSub: { fontSize: 11, marginTop: 2 },

  /* Prediction Snapshot — INTEGRATED into decision surface (not a button) */
  predSnapshot: { marginTop: 8, marginBottom: 12, paddingVertical: 10 },
  predDivider: { height: StyleSheet.hairlineWidth, marginBottom: 14 },
  predSnapHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 },
  predSnapLabel: { fontSize: 10, fontWeight: '800', letterSpacing: 1.8 },
  stateChip: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, borderWidth: 1 },
  stateChipT: { fontSize: 9, fontWeight: '900', letterSpacing: 1 },
  predSnapHorizon: { fontSize: 10, fontWeight: '600', letterSpacing: 0.5 },
  predSnapMain: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  predSnapBias: { fontSize: 22, fontWeight: '900', letterSpacing: -0.4 },
  predSnapMove: { fontSize: 12, fontWeight: '600', marginTop: 2 },
  predMetricsRow: { flexDirection: 'row', alignItems: 'center', marginTop: 12, paddingTop: 10, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: 'rgba(255,255,255,0.08)' },
  predMetricCol: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  predMetricVal: { fontSize: 16, fontWeight: '800', fontVariant: ['tabular-nums'] as any },
  predMetricLbl: { fontSize: 9, fontWeight: '600', letterSpacing: 0.8, textTransform: 'uppercase', marginTop: 1 },
  predMetricSep: { width: StyleSheet.hairlineWidth, height: 28 },
  predConflict: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 10, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, borderWidth: 1 },
  predConflictText: { flex: 1, fontSize: 11, fontWeight: '500' },
  ctaPrimary: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 16, borderRadius: 14 },
  ctaPriText: { fontSize: 16, fontWeight: '800', letterSpacing: 1 },
});
