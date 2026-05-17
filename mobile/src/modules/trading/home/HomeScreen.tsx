/**
 * Trading OS · COMMAND CENTER
 *
 * AI Intention Layer.  NOT a dashboard.  NOT a portfolio summary.
 * This screen answers four questions in natural language:
 *
 *   1. What is AI doing right now?
 *   2. Why is it doing it?
 *   3. What is AI waiting for?
 *   4. What must happen for AI to start acting?
 *
 * Sections (top → bottom):
 *
 *   1. GLOBAL AI STATE          natural-language belief about the market
 *   2. AI FOCUS                 watching / waiting for
 *   3. CAPITAL POSTURE          defensive / rotating / aggressive · with reasons
 *   4. AI READINESS ENGINE      readiness % + activation gates
 *   5. LIVE MODULE CONSENSUS    5-module agreement matrix
 *   6. MARKET PRESSURE MAP      AI interpretation of overheated / weak / suppressed pockets
 *   7. AI WATCHLIST             HIGH ATTENTION · BUILDING · AVOIDING
 *   8. SYSTEM MEMORY            awaited / received / missed / avoided
 *
 * Read-only · paper · no live execution · no backend changes.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator, Animated, Easing,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../../core/useColors';
import { useAppMode } from '../../../stores/app-mode.store';
import { useAssetStore } from '../../../stores/asset.store';
import { mobileApi } from '../../../services/api/mobile-api';
import { mbrainApi } from '../../../services/api/mbrain-api';
import { AIValueNarrativeFeed } from '../../../widgets/trading-bridge/AIValueNarrativeFeed';
import {
  CognitiveTimeline, WhatAIWaitsFor, AIThoughtProcess, DecisionPathChain,
} from '../../../widgets/trading-bridge/CognitiveMemoryStream';
import { IntentionTrack } from '../../../widgets/cognition/IntentionTrack';
import {
  INTENTION_ORDER, intentionVerb, readinessToIntention,
} from '../../../widgets/cognition/cognitiveLabel';
import { CognitiveBadge } from '../../../widgets/cognition/CognitiveBadge';
import {
  cognitionStyle, decisionStyle, explanationStyle, telemetryStyle, telemetryNumberStyle,
} from '../../../widgets/cognition/cognitiveType';
import { tokenForState } from '../../../widgets/cognition/cognitiveTokens';
import { CognitiveAnchor } from '../../../widgets/cognition/CognitiveAnchor';
import { CognitiveRail } from '../../../widgets/cognition/CognitiveRail';
import { CognitiveFragmentLayer } from '../../../widgets/cognition/CognitiveFragment';
import { BusPulseFromState } from '../../../widgets/cognition/bus/cognitiveBus';
import { CurrentDeploymentConditions } from '../../../widgets/cognition/CurrentDeploymentConditions';

import { t } from '../../../core/i18n';
// ─── helpers ────────────────────────────────────────────────────────
function pct(n: number | null | undefined, d = 0): string {
  if (n == null || isNaN(n)) return '—';
  return `${(n * 100).toFixed(d)}%`;
}
function pctRaw(n: number | null | undefined, d = 1): string {
  if (n == null || isNaN(n)) return '—';
  const sign = n >= 0 ? '+' : '';
  return `${sign}${n.toFixed(d)}%`;
}

// ─── pulse dot ──────────────────────────────────────────────────────
function PulseDot({ color, size = 10 }: { color: string; size?: number }) {
  const scale = useMemo(() => new Animated.Value(1), []);
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(scale, { toValue: 1.6, duration: 1100, easing: Easing.out(Easing.ease), useNativeDriver: true }),
        Animated.timing(scale, { toValue: 1, duration: 1100, easing: Easing.in(Easing.ease), useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [scale]);
  return (
    <View style={{ width: size * 2, height: size * 2, alignItems: 'center', justifyContent: 'center' }}>
      <Animated.View style={{
        position: 'absolute',
        width: size, height: size, borderRadius: size / 2,
        backgroundColor: color, opacity: 0.3, transform: [{ scale }],
      }} />
      <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: color }} />
    </View>
  );
}

// ─── readiness state ────────────────────────────────────────────────
type Readiness = 'DORMANT' | 'BUILDING' | 'READY' | 'AGGRESSIVE' | 'DEFENSIVE' | 'ROTATING';

function deriveReadiness(args: {
  topConfFinal: number;
  topConfRaw: number;
  hasActionable: boolean;
  positions: number;
  recentClosed: number;
  suppressedCount: number;
}): { state: Readiness; pct: number; gates: string[] } {
  const { topConfFinal, topConfRaw, hasActionable, positions, recentClosed, suppressedCount } = args;

  const gates: string[] = [];
  // Heuristics for activation gates
  if (topConfRaw < 0.55) gates.push('TA confirmation');
  if (suppressedCount >= 3) gates.push('suppression release');
  if (topConfFinal < topConfRaw - 0.1) gates.push('meta-brain alignment');
  if (positions === 0 && !hasActionable) gates.push('asymmetric setup');
  if (gates.length === 0) gates.push('momentum trigger');

  if (recentClosed >= 3 && positions <= 4 && positions > 0) {
    return { state: 'ROTATING', pct: 0.6, gates };
  }
  if (suppressedCount >= 5 && positions === 0) {
    return { state: 'DEFENSIVE', pct: 0.25, gates };
  }
  if (hasActionable && topConfFinal >= 0.7) {
    return { state: 'AGGRESSIVE', pct: topConfFinal, gates: [] };
  }
  if (hasActionable && topConfFinal >= 0.55) {
    return { state: 'READY', pct: topConfFinal, gates };
  }
  if (topConfFinal >= 0.4) {
    return { state: 'BUILDING', pct: topConfFinal, gates };
  }
  return { state: 'DORMANT', pct: Math.max(0.15, topConfFinal), gates };
}

const READINESS_META: Record<Readiness, { color: keyof any; icon: keyof typeof Ionicons.glyphMap }> = {
  DORMANT:    { color: 'textMuted', icon: 'moon-outline' },
  BUILDING:   { color: 'warning',   icon: 'construct-outline' },
  READY:      { color: 'accent',    icon: 'checkmark-circle-outline' },
  AGGRESSIVE: { color: 'buy',       icon: 'flash' },
  DEFENSIVE:  { color: 'sell',      icon: 'shield-checkmark-outline' },
  ROTATING:   { color: 'accent',    icon: 'sync-outline' },
};

// ─── global AI state generator ──────────────────────────────────────
function deriveGlobalState(args: {
  regime: string | null;
  metaVerdict: string | null;
  netAlpha: number | null;
  alignedCount: number;
  positionsCount: number;
  topConfFinal: number;
}): string {
  const { regime, metaVerdict, netAlpha, alignedCount, positionsCount, topConfFinal } = args;
  const regimeLine = regime
    ? `market is in ${String(regime).replace(/_/g, ' ').toLowerCase()} regime`
    : 'market structure is unclear';

  const opportunityLine =
    topConfFinal >= 0.7 ? 'asymmetric opportunities are visible'
    : topConfFinal >= 0.5 ? 'asymmetric opportunities are forming'
    : 'asymmetric opportunities are weak right now';

  const capitalLine = positionsCount === 0
    ? metaVerdict === 'META_NET_POSITIVE'
      ? 'capital is preserved on purpose'
      : 'capital is on the sidelines'
    : 'capital is deployed selectively';

  const alphaLine = netAlpha != null
    ? netAlpha >= 5 ? `meta-brain has earned ${pctRaw(netAlpha, 1)} alpha so far`
    : netAlpha >= 0 ? `meta-brain is net-positive at ${pctRaw(netAlpha, 1)} alpha`
    : `meta-brain is net-negative at ${pctRaw(netAlpha, 1)} alpha — under review`
    : '';

  return [regimeLine, opportunityLine, capitalLine, alphaLine].filter(Boolean).join('. ') + '.';
}

// ─── module consensus ──────────────────────────────────────────────
type ModState = 'ALIGN' | 'BLOCK' | 'NEUTRAL' | 'WAIT' | 'N/A';

function deriveModuleConsensus(signal: any, fractal: any, sentiment: any, marketState: any, intel: any) {
  const out: { name: string; state: ModState; detail: string }[] = [];

  // TA
  const taAct = signal?.action;
  out.push({
    name: 'TA',
    state: taAct === 'BUY' || taAct === 'SELL' ? 'ALIGN'
      : taAct === 'WAIT' ? 'WAIT' : 'N/A',
    detail: signal?.confidence != null ? `${pct(signal.confidence)} confidence` : 'no signal',
  });

  // Fractal
  const frDir = fractal?.direction || fractal?.fractal?.direction || fractal?.bias || null;
  out.push({
    name: 'Fractal',
    state: frDir && frDir !== 'NEUTRAL' ? 'ALIGN' : frDir === 'NEUTRAL' ? 'NEUTRAL' : 'N/A',
    detail: fractal?.pattern || fractal?.fractal?.pattern || (frDir || 'unaligned').toString().toLowerCase(),
  });

  // Exchange
  const xchgFunding = marketState?.market_state?.funding ?? marketState?.funding;
  const xchgDir = marketState?.market_state?.exchangeBias || marketState?.exchangeBias;
  out.push({
    name: 'Exchange',
    state: xchgDir ? 'ALIGN' : xchgFunding != null ? 'NEUTRAL' : 'BLOCK',
    detail: xchgFunding != null
      ? `funding ${(Number(xchgFunding) * 100).toFixed(3)}%`
      : 'orderbook · funding',
  });

  // Sentiment
  const senScoreRaw = sentiment?.score ?? sentiment?.sentiment?.score;
  const senScore = senScoreRaw == null ? null
    : Math.abs(senScoreRaw) > 1.5 ? senScoreRaw / 100 : senScoreRaw;
  out.push({
    name: 'Sentiment',
    state: senScore == null ? 'N/A'
      : senScore > 0.6 || senScore < 0.4 ? 'ALIGN' : 'NEUTRAL',
    detail: senScore != null ? `${pct(senScore)} score` : 'unavailable',
  });

  // On-chain
  const ocModule = (intel?.modules || []).find((m: any) =>
    String(m.id || m.key || '').toLowerCase().includes('onchain'));
  out.push({
    name: 'On-chain',
    state: ocModule?.direction === 'BULLISH' || ocModule?.direction === 'BEARISH' ? 'ALIGN'
      : ocModule?.direction === 'NEUTRAL' ? 'NEUTRAL' : 'N/A',
    detail: ocModule?.summary?.slice?.(0, 36) || 'unavailable',
  });

  return out;
}

// ─── focus generator (watching / waiting) ──────────────────────────
function describeFocus(verdicts: any[], regime: string | null) {
  const pool = (verdicts || []).slice(0, 8);
  const watching: string[] = [];
  const waiting: string[] = [];

  // "Watching" = top verdicts by confidence with descriptive language
  pool
    .slice()
    .sort((a, b) => (b.confidence_final || 0) - (a.confidence_final || 0))
    .slice(0, 3)
    .forEach((v) => {
      const sym = String(v.symbol || '').replace('USDT', '');
      const isSuppressed = (v.badges || []).some((b: any) => b.type === 'SUPPRESSED');
      const isFlipped = (v.badges || []).some((b: any) => b.type === 'FLIPPED');
      const desc = isSuppressed ? `${sym} suppressed setup`
        : isFlipped ? `${sym} polarity flip`
        : v.final_action === 'LONG' ? `${sym} breakout compression`
        : v.final_action === 'SHORT' ? `${sym} breakdown pressure`
        : `${sym} drift`;
      watching.push(desc);
    });
  if (watching.length === 0 && regime) {
    watching.push(`${String(regime).replace(/_/g, ' ').toLowerCase()} structure`);
  }

  // "Waiting for" = aggregated blockers across verdicts
  const blockerCount: Record<string, number> = {};
  pool.forEach((v) => {
    (v.badges || []).forEach((b: any) => {
      if (['SUPPRESSED', 'DOWNGRADED', 'BLOCKED', 'FLIPPED'].includes(b.type)) {
        const key = String(b.label || b.type).toLowerCase();
        blockerCount[key] = (blockerCount[key] || 0) + 1;
      }
    });
  });
  const sortedBlockers = Object.entries(blockerCount).sort((a, b) => b[1] - a[1]);
  sortedBlockers.slice(0, 3).forEach(([label]) => {
    if (/sentiment|euphor|fear|greed/i.test(label)) waiting.push('sentiment reset');
    else if (/funding|oi|open.?interest/i.test(label)) waiting.push('funding normalization');
    else if (/ta|trend|momentum|breakout/i.test(label)) waiting.push('TA confirmation');
    else if (/volat|atr|chop/i.test(label)) waiting.push('volatility expansion');
    else if (/macro|regime/i.test(label)) waiting.push('macro alignment');
    else waiting.push(label);
  });
  if (waiting.length === 0) {
    waiting.push('confirmation candle', 'asymmetric setup');
  }
  return { watching, waiting: Array.from(new Set(waiting)) };
}

// ─── market pressure interpretation ────────────────────────────────
function describeMarketPressure(verdicts: any[]): string[] {
  const out: string[] = [];
  const pool = (verdicts || []).slice(0, 12);
  pool.forEach((v) => {
    const sym = String(v.symbol || '').replace('USDT', '');
    const conf = v.confidence_final || 0;
    const suppressed = (v.badges || []).some((b: any) => b.type === 'SUPPRESSED');
    if (suppressed && v.raw_action === 'LONG') {
      out.push(`overheated longs on ${sym}`);
    } else if (suppressed && v.raw_action === 'SHORT') {
      out.push(`crowded shorts on ${sym}`);
    } else if (conf >= 0.7) {
      out.push(`high-asymmetry setup on ${sym}`);
    } else if (conf < 0.3 && v.final_action === 'HOLD') {
      out.push(`weak continuation on ${sym}`);
    }
  });
  return Array.from(new Set(out)).slice(0, 4);
}

// ─── AI watchlist ──────────────────────────────────────────────────
function buildAIWatchlist(verdicts: any[]) {
  const high: string[] = [];
  const building: string[] = [];
  const avoiding: string[] = [];
  (verdicts || []).forEach((v) => {
    const sym = String(v.symbol || '').replace('USDT', '');
    const conf = v.confidence_final || 0;
    const suppressed = (v.badges || []).some((b: any) => b.type === 'SUPPRESSED');
    if (suppressed) {
      if (!avoiding.includes(sym)) avoiding.push(sym);
    } else if (conf >= 0.65 && (v.final_action === 'LONG' || v.final_action === 'SHORT')) {
      if (!high.includes(sym)) high.push(sym);
    } else if (conf >= 0.4) {
      if (!building.includes(sym)) building.push(sym);
    }
  });
  return {
    high: high.slice(0, 4),
    building: building.slice(0, 4),
    avoiding: avoiding.slice(0, 4),
  };
}

// ─── main screen ────────────────────────────────────────────────────
export function HomeScreen() {
  const colors = useColors();
  const setTradingTab = useAppMode((s) => s.setTradingTab);
  const asset = useAssetStore((s) => s.currentAsset);
  const styles = useMemo(() => mk(colors), [colors]);

  const [portfolio, setPortfolio] = useState<any>(null);
  const [marketState, setMarketState] = useState<any>(null);
  const [parallel, setParallel] = useState<any>(null);
  const [realized, setRealized] = useState<any>(null);
  const [verdicts, setVerdicts] = useState<any[]>([]);
  const [signal, setSignal] = useState<any>(null);
  const [fractal, setFractal] = useState<any>(null);
  const [sentiment, setSentiment] = useState<any>(null);
  const [intel, setIntel] = useState<any>(null);
  const [openPositions, setOpenPositions] = useState<any[]>([]);
  const [closedPositions, setClosedPositions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchAll = useCallback(async () => {
    const r = await Promise.allSettled([
      mobileApi.getPortfolio(),
      mobileApi.getMarketState(),
      mbrainApi.parallelPortfolios(200, true),
      mbrainApi.realizedAttribution(2000),
      mbrainApi.listVerdicts(50),
      mobileApi.getSignal(asset),
      mobileApi.getFractal(asset),
      mobileApi.getSentiment(asset),
      mobileApi.getIntelOverview(asset),
      mobileApi.getPositions('OPEN'),
      mobileApi.getPositions('CLOSED'),
    ]);
    const get = (i: number) => (r[i].status === 'fulfilled' ? (r[i] as any).value : null);
    setPortfolio(get(0));
    setMarketState(get(1));
    setParallel(get(2));
    setRealized(get(3));
    setVerdicts(get(4)?.cards || []);
    const s = get(5); setSignal(s?.signal || s || null);
    setFractal(get(6));
    setSentiment(get(7));
    setIntel(get(8));
    setOpenPositions(get(9)?.positions || []);
    setClosedPositions(get(10)?.positions || []);
    setLoading(false);
    setRefreshing(false);
  }, [asset]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  if (loading) {
    return <View style={styles.center}><ActivityIndicator color={colors.accent} /></View>;
  }

  // ── Derived state
  const regime = marketState?.market_state?.regime || marketState?.regime || marketState?.state || null;
  const realizedH = realized?.headline;
  const headline = parallel?.headline;

  const topVerdict = (verdicts || [])
    .slice()
    .sort((a, b) => (b.confidence_final || 0) - (a.confidence_final || 0))[0];
  const topConfFinal = topVerdict?.confidence_final ?? signal?.confidence ?? 0;
  const topConfRaw = topVerdict?.stages?.raw?.confidence ?? signal?.confidence ?? 0;
  const hasActionable = !!(topVerdict && (topVerdict.final_action === 'LONG' || topVerdict.final_action === 'SHORT'))
    || (signal?.action === 'BUY' || signal?.action === 'SELL');

  const recentClosed = closedPositions.filter((c: any) => {
    const t = c.closedAt || c.closed_at;
    if (!t) return false;
    const ms = typeof t === 'number' ? t : new Date(t).getTime();
    return Date.now() - ms < 7 * 24 * 3600 * 1000;
  }).length;

  const readiness = deriveReadiness({
    topConfFinal,
    topConfRaw,
    hasActionable,
    positions: openPositions.length,
    recentClosed,
    suppressedCount: headline?.directional_trades_killed_to_hold || 0,
  });
  const rMeta = READINESS_META[readiness.state];
  const rColor = (colors as any)[rMeta.color] || colors.accent;

  const moduleConsensus = deriveModuleConsensus(signal, fractal, sentiment, marketState, intel);
  const alignedCount = moduleConsensus.filter((m) => m.state === 'ALIGN').length;

  const globalState = deriveGlobalState({
    regime,
    metaVerdict: realizedH?.verdict || null,
    netAlpha: realizedH?.net_alpha_pct ?? null,
    alignedCount,
    positionsCount: openPositions.length,
    topConfFinal,
  });

  const focus = describeFocus(verdicts, regime);
  const pressure = describeMarketPressure(verdicts);
  const watchlist = buildAIWatchlist(verdicts);

  // Capital posture reasons
  const postureLabel = openPositions.length === 0
    ? readiness.state === 'DEFENSIVE' ? 'DEFENSIVE'
      : readiness.state === 'DORMANT' ? 'DORMANT'
      : 'OBSERVING'
    : openPositions.length >= 4 ? 'CONCENTRATED'
    : 'SELECTIVE';
  const postureReasons: string[] = [];
  if (alignedCount < 3) postureReasons.push('low multi-module alignment');
  if (regime && /chop|range|unstable/i.test(regime)) postureReasons.push('unstable market structure');
  if (headline?.directional_trades_killed_to_hold > 5) postureReasons.push('elevated suppression rate');
  if (realizedH?.verdict === 'META_NET_POSITIVE' && openPositions.length === 0) postureReasons.push('meta-brain protective stance');
  if (postureReasons.length === 0) postureReasons.push('balanced exposure');

  return (
    <ScrollView
      testID="command-screen"
      style={styles.container}
      contentContainerStyle={styles.content}
      stickyHeaderIndices={[0]}
      refreshControl={<RefreshControl refreshing={refreshing}
        onRefresh={() => { setRefreshing(true); fetchAll(); }}
        tintColor={colors.accent} />}
    >
      {/* ITERATION P5 · pulse cognition bus from readiness state */}
      <BusPulseFromState category="cognition" state={readiness.state} amount={0.5} />

      {/* ITERATION 4·β · ambient cognition anchor */}
      <CognitiveAnchor
        cognition={readiness.state}
        capital={postureLabel}
        readiness={readiness.pct}
        colors={colors}
      />

      {/* 1. GLOBAL AI STATE */}
      <View style={[styles.beliefCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        <View style={styles.beliefHeader}>
          <PulseDot color={rColor} />
          <Text style={[styles.beliefLabel, { color: colors.textMuted }]}>{t('homeTrade.aiCurrentlyBelieves')}</Text>
        </View>
        <Text style={[styles.beliefText, { color: colors.textPrimary }]}>{globalState}</Text>
      </View>

      {/* PHASE X · GLOBAL VALUE PERCEPTION (right after belief, max emotional weight) */}
      <AIValueNarrativeFeed
        layout="horizontal"
        title={t('homeTrade.whyThisAiMatters')}
        subtitle="recent decisions · narrative · not metrics"
        limit={6}
      />

      {/* ITERATION 2 · TEMPORAL COGNITION */}
      <AIThoughtProcess />
      <CognitiveTimeline scope="COMMAND" maxEvents={6} />

      {/* 2. AI FOCUS */}
      <SectionTitle text="AI FOCUS" subtext="active scan layer" colors={colors} />
      <View style={styles.focusRow}>
        <View style={[styles.focusCol, { backgroundColor: colors.surface, borderColor: colors.buy + '30' }]}>
          <Text style={[styles.focusLabel, { color: colors.buy }]}>WATCHING</Text>
          {focus.watching.length > 0 ? focus.watching.map((w, i) => (
            <Text key={i} style={[styles.focusLine, { color: colors.textPrimary }]}>· {w}</Text>
          )) : (
            <Text style={[styles.focusLine, { color: colors.textMuted }]}>idle scan</Text>
          )}
        </View>
        <View style={[styles.focusCol, { backgroundColor: colors.surface, borderColor: colors.warning + '30' }]}>
          <Text style={[styles.focusLabel, { color: colors.warning ?? '#f5a623' }]}>{t('homeTrade.waitingFor')}</Text>
          {focus.waiting.length > 0 ? focus.waiting.slice(0, 4).map((w, i) => (
            <Text key={i} style={[styles.focusLine, { color: colors.textPrimary }]}>· {w}</Text>
          )) : (
            <Text style={[styles.focusLine, { color: colors.textMuted }]}>nothing</Text>
          )}
        </View>
      </View>

      {/* 3. CAPITAL POSTURE */}
      <SectionTitle text="CAPITAL POSTURE" colors={colors} />
      <View style={[styles.postureCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        <Text style={[
          cognitionStyle(colors,
            tokenForState('capital', postureLabel).energy,
            'xl',
            'institutional'),
        ]}>
          {postureLabel}
        </Text>
        <View style={styles.postureReasons}>
          {postureReasons.map((r, i) => (
            <Text key={i} style={[explanationStyle(colors), { marginTop: i === 0 ? 6 : 2 }]}>· {r}</Text>
          ))}
        </View>
      </View>

      {/* 4. AI READINESS */}
      <SectionTitle text="AI READINESS ENGINE" colors={colors} />
      <View style={[styles.readinessCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        <View style={styles.readinessTop}>
          <View style={{ flex: 1, gap: 6 }}>
            <CognitiveBadge category="cognition" state={readiness.state} colors={colors} />
            <Text style={[telemetryNumberStyle(colors, undefined, 'lg'), { color: colors.textPrimary, opacity: 0.95 }]}>
              {Math.round(readiness.pct * 100)}%
            </Text>
          </View>
          <ReadinessGauge value={readiness.pct} color={rColor} colors={colors} />
        </View>
        <View style={styles.readinessTrack}>
          <View style={[styles.readinessTrackFill, {
            width: `${Math.max(2, readiness.pct * 100)}%`,
            backgroundColor: rColor,
          }]} />
        </View>
        {readiness.gates.length > 0 && (
          <View style={styles.gatesBlock}>
            <Text style={[telemetryStyle(colors)]}>{t('homeTrade.waitingFor')}</Text>
            {readiness.gates.slice(0, 3).map((g, i) => (
              <Text key={i} style={[explanationStyle(colors), { marginTop: 2 }]}>· {g}</Text>
            ))}
          </View>
        )}
      </View>

      {/* PHASE X · P6·γ — Command Presence Fragment (present pressure residue)
          One layer, scope='command', max=1.  Rare ambient emission of
          present pressure between Readiness and Activation Gates.
          NOT timeline.  NOT replay.  NOT history list.  Command does
          NOT write haunting — present does not accumulate residue. */}
      <CognitiveFragmentLayer scope="command" max={1} colors={colors} marginTop={4} marginBottom={4} />

      {/* ITERATION 2 · Specific gates (replaces generic t('homeTrade.waitingFor')) */}
      <WhatAIWaitsFor topConf={topConfFinal} />

      {/* STAGE A-8 · CURRENT DEPLOYMENT CONDITIONS — per-symbol cognitive
          climate.  NOT signals.  NOT direction.  Atmospheric posture
          reading: "restraint held / pressure unresolved / compressed".
          Surfaces Stage A-7 shadow runtime substrate.  Truthful absence:
          renders nothing when no shadow verdicts exist yet. */}
      <CurrentDeploymentConditions colors={colors} marginTop={16} marginBottom={4} />

      {/* ITERATION 3B · INTENTION DRIFT — Command shifts intention */}
      <SectionTitle text="AI INTENTION DRIFT"
        subtext="four phases of mental state · cognitive arc"
        colors={colors} />
      <IntentionTrack
        states={INTENTION_ORDER}
        current={readinessToIntention(readiness.state, readiness.pct)}
        toneKeyMap={{
          DORMANT:   'textMuted',
          OBSERVING: 'textMuted',
          BUILDING:  'warning',
          READY:     'buy',
        }}
        colors={colors}
        headLabel="INTENTION"
        caption={intentionVerb(readinessToIntention(readiness.state, readiness.pct))}
        deltas={(() => {
          const d: string[] = [];
          const pct100 = Math.round(readiness.pct * 100);
          if (alignedCount >= 3)        d.push(`alignment improving · ${alignedCount}/5 modules aligned`);
          else if (alignedCount === 0)  d.push('alignment still weak · no module conviction yet');
          else                          d.push(`alignment partial · ${alignedCount}/5 modules engaged`);
          if (readiness.gates.length > 0)
            d.push(`${readiness.gates.length} gate${readiness.gates.length === 1 ? '' : 's'} still holding readiness back`);
          else if (pct100 >= 70)
            d.push('all activation gates clear · capital ready to deploy');
          d.push(`capital posture · ${postureLabel.toLowerCase()}`);
          return d;
        })()}
      />

      {/* 5. LIVE MODULE CONSENSUS */}
      <SectionTitle text="LIVE MODULE CONSENSUS"
        subtext={`${alignedCount}/5 aligned · ${alignedCount >= 3 ? 'deployable' : 'insufficient for deployment'}`}
        colors={colors} />
      <View style={[styles.matrix, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        {moduleConsensus.map((m, i) => {
          return (
            <View key={m.name}
              style={[styles.matrixRow, i < moduleConsensus.length - 1 && { borderBottomWidth: StyleSheet.hairlineWidth, borderColor: colors.border }]}>
              <Text style={[decisionStyle(colors, undefined, 'sm'), { color: colors.textPrimary }]}>{m.name}</Text>
              <Text style={[explanationStyle(colors), { flex: 1, marginLeft: 8 }]} numberOfLines={1}>{m.detail}</Text>
              <CognitiveBadge category="cognition" state={m.state} colors={colors} inline />
            </View>
          );
        })}
      </View>

      {/* 6. MARKET PRESSURE MAP */}
      <SectionTitle text="MARKET PRESSURE MAP" subtext="AI interpretation layer" colors={colors} />
      <View style={[styles.pressureCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        {pressure.length > 0 ? pressure.map((p, i) => {
          const tone = /overheated|crowded|weak/i.test(p) ? colors.sell
            : /high-asymmetry|breakout/i.test(p) ? colors.buy
            : colors.textMuted;
          return (
            <View key={i} style={styles.pressureRow}>
              <View style={[styles.pressureDot, { backgroundColor: tone }]} />
              <Text style={[styles.pressureText, { color: colors.textPrimary }]}>AI detects: {p}</Text>
            </View>
          );
        }) : (
          <Text style={[styles.pressureText, { color: colors.textMuted, fontStyle: 'italic' }]}>
            no actionable pressure detected · regime ambient
          </Text>
        )}
      </View>

      {/* 7. AI WATCHLIST */}
      <SectionTitle text="AI WATCHLIST" subtext="AI-curated, not user-defined" colors={colors} />
      <View style={[styles.watchlist, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        <WatchlistRow label={t('homeTrade.highAttention')}
          symbols={watchlist.high} colors={colors} tint={colors.buy} icon="eye" />
        <WatchlistRow label="BUILDING"
          symbols={watchlist.building} colors={colors} tint={colors.warning ?? '#f5a623'} icon="trending-up" />
        <WatchlistRow label="AVOIDING"
          symbols={watchlist.avoiding} colors={colors} tint={colors.sell} icon="ban" last />
      </View>

      {/* 8. SYSTEM MEMORY */}
      <SectionTitle text="SYSTEM MEMORY" subtext="awaited · received · missed · avoided" colors={colors} />
      <View style={[styles.memCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        <MemPill colors={colors} icon="time-outline" tone="neutral"
          label="awaited"
          value={focus.waiting[0] ? focus.waiting[0] : 'idle'} />
        <MemPill colors={colors} icon="checkmark-circle-outline" tone="good"
          label="received"
          value={hasActionable ? `${topVerdict?.symbol?.replace('USDT', '') || asset} ${topVerdict?.final_action || signal?.action || 'signal'}` : 'no actionable'} />
        <MemPill colors={colors} icon="alert-circle-outline" tone="bad"
          label="missed"
          value={realized?.top_missed?.[0]?.symbol
            ? `${realized.top_missed[0].symbol} (${pct(realized.top_missed[0].realized_return || 0, 1)})`
            : 'none'} />
        <MemPill colors={colors} icon="shield-checkmark-outline" tone="good"
          label="avoided"
          value={realized?.top_avoided?.[0]?.symbol
            ? `${realized.top_avoided[0].symbol} (${pctRaw((realized.top_avoided[0].realized_return || 0) * 100, 1)})`
            : 'none'}
          last />
      </View>

      {/* QUICK NAV TO DEEPER LAYERS */}
      <View style={styles.quickNav}>
        <QuickBtn icon="flash" label="Execution" colors={colors}
          onPress={() => setTradingTab('EXECUTION')} />
        <QuickBtn icon="briefcase" label="Portfolio" colors={colors}
          onPress={() => setTradingTab('PORTFOLIO')} />
        <QuickBtn icon="pulse" label="Market" colors={colors}
          onPress={() => setTradingTab('MARKET')} />
      </View>

      <Text style={[styles.disclaimer, { color: colors.textMuted }]}>
        Read-only AI command center · paper-only · no live orders · all
        narratives are derived from the meta-brain side-car. Verdict layer is
        observability — does not affect production fusion.
      </Text>
      <View style={{ height: 24 }} />
    </ScrollView>
  );
}

// ─── sub-components ─────────────────────────────────────────────────
function SectionTitle({ text, subtext, colors }: any) {
  return (
    <View style={{ marginTop: 18, marginBottom: 8 }}>
      <Text style={{ fontSize: 10, fontWeight: '800', letterSpacing: 1.4, color: colors.textMuted }}>
        {text}
      </Text>
      {subtext && (
        <Text style={{ fontSize: 10, color: colors.textMuted, marginTop: 2, fontStyle: 'italic' }}>
          {subtext}
        </Text>
      )}
    </View>
  );
}

function ReadinessGauge({ value, color, colors }: any) {
  const v = Math.max(0, Math.min(1, value || 0));
  return (
    <View style={{ width: 60, height: 60, alignItems: 'center', justifyContent: 'center' }}>
      <View style={{
        position: 'absolute', width: 60, height: 60, borderRadius: 30,
        borderWidth: 5, borderColor: colors.border,
      }} />
      <View style={{
        position: 'absolute', width: 60, height: 60, borderRadius: 30,
        borderWidth: 5, borderColor: color, borderRightColor: 'transparent', borderBottomColor: 'transparent',
        transform: [{ rotate: `${-45 + v * 360}deg` }], opacity: 0.85,
      }} />
      <Text style={{ fontSize: 13, fontWeight: '800', color: colors.textPrimary }}>
        {Math.round(v * 100)}
      </Text>
    </View>
  );
}

function WatchlistRow({ label, symbols, colors, tint, icon, last }: any) {
  return (
    <View style={[
      wStyles.row,
      !last && { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    ]}>
      <View style={wStyles.head}>
        <Ionicons name={icon} size={14} color={tint} />
        <Text style={[wStyles.label, { color: tint }]}>{label}</Text>
      </View>
      {symbols && symbols.length > 0 ? (
        <View style={wStyles.symbols}>
          {symbols.map((s: string, i: number) => (
            <View key={i} style={[wStyles.sym, { borderColor: tint + '50', backgroundColor: tint + '14' }]}>
              <Text style={[wStyles.symText, { color: tint }]}>{s}</Text>
            </View>
          ))}
        </View>
      ) : (
        <Text style={[wStyles.empty, { color: colors.textMuted }]}>—</Text>
      )}
    </View>
  );
}
const wStyles = StyleSheet.create({
  row: { paddingVertical: 10, paddingHorizontal: 12, gap: 6 },
  head: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  label: { fontSize: 10, fontWeight: '900', letterSpacing: 0.8 },
  symbols: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  sym: { paddingHorizontal: 8, paddingVertical: 3, borderWidth: 1, borderRadius: 6 },
  symText: { fontSize: 11, fontWeight: '800' },
  empty: { fontSize: 11, fontStyle: 'italic' },
});

function MemPill({ icon, label, value, colors, tone, last }: any) {
  const c = tone === 'good' ? colors.buy : tone === 'bad' ? colors.sell : colors.textMuted;
  return (
    <View style={[
      memStyles.row,
      !last && { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    ]}>
      <Ionicons name={icon} size={14} color={c} />
      <Text style={[memStyles.label, { color: colors.textMuted }]}>{label}</Text>
      <Text style={[memStyles.value, { color: colors.textPrimary }]} numberOfLines={1}>{value}</Text>
    </View>
  );
}
const memStyles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 9, paddingHorizontal: 12 },
  label: { width: 70, fontSize: 10, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase' },
  value: { flex: 1, fontSize: 12, fontWeight: '700', textAlign: 'right' },
});

function QuickBtn({ icon, label, colors, onPress }: any) {
  return (
    <TouchableOpacity
      style={[qStyles.btn, { backgroundColor: colors.surface, borderColor: colors.border }]}
      onPress={onPress}
      activeOpacity={0.8}
    >
      <Ionicons name={icon} size={18} color={colors.accent} />
      <Text style={[qStyles.label, { color: colors.textPrimary }]}>{label}</Text>
    </TouchableOpacity>
  );
}
const qStyles = StyleSheet.create({
  btn: { flex: 1, alignItems: 'center', paddingVertical: 12, borderRadius: 10, borderWidth: 1, gap: 4 },
  label: { fontSize: 11, fontWeight: '700', marginTop: 4 },
});

// ─── styles ─────────────────────────────────────────────────────────
const mk = (c: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: c.background },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: c.background },
  content: { padding: 16, paddingBottom: 60 },

  beliefCard: { borderRadius: 14, padding: 16, borderWidth: 1, marginBottom: 4 },
  beliefHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  beliefLabel: { fontSize: 9, fontWeight: '900', letterSpacing: 1.5 },
  beliefText: { fontSize: 14, lineHeight: 20, marginTop: 8, fontWeight: '600' },

  focusRow: { flexDirection: 'row', gap: 8 },
  focusCol: { flex: 1, borderRadius: 12, borderWidth: 1, padding: 12 },
  focusLabel: { fontSize: 9, fontWeight: '900', letterSpacing: 1, marginBottom: 6 },
  focusLine: { fontSize: 12, lineHeight: 17 },

  postureCard: { borderRadius: 12, borderWidth: 1, padding: 14 },
  postureLabel: { fontSize: 18, fontWeight: '900', letterSpacing: 0.5 },
  postureReasons: { marginTop: 8, gap: 2 },
  postureReason: { fontSize: 12, lineHeight: 17 },

  readinessCard: { borderRadius: 12, borderWidth: 1, padding: 14 },
  readinessTop: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  readinessLabelRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  readinessLabel: { fontSize: 10, fontWeight: '900', letterSpacing: 1 },
  readinessNum: { fontSize: 28, fontWeight: '900', marginTop: 4 },
  readinessTrack: {
    height: 6, backgroundColor: c.border, borderRadius: 999, marginTop: 12, overflow: 'hidden',
  },
  readinessTrackFill: { height: 6, borderRadius: 999 },
  gatesBlock: { marginTop: 12 },
  gatesLabel: { fontSize: 9, fontWeight: '900', letterSpacing: 1, marginBottom: 4 },
  gateLine: { fontSize: 12, lineHeight: 17 },

  matrix: { borderRadius: 12, borderWidth: 1, overflow: 'hidden' },
  matrixRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingVertical: 12, paddingHorizontal: 12,
  },
  matrixModule: { width: 70, fontSize: 12, fontWeight: '800' },
  matrixDetail: { flex: 1, fontSize: 11 },
  matrixBadge: { paddingHorizontal: 8, paddingVertical: 3, borderWidth: 1, borderRadius: 999 },
  matrixBadgeText: { fontSize: 9, fontWeight: '900', letterSpacing: 0.6 },

  pressureCard: { borderRadius: 12, borderWidth: 1, padding: 14, gap: 8 },
  pressureRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  pressureDot: { width: 6, height: 6, borderRadius: 3 },
  pressureText: { flex: 1, fontSize: 12, lineHeight: 17 },

  watchlist: { borderRadius: 12, borderWidth: 1, overflow: 'hidden' },

  memCard: { borderRadius: 12, borderWidth: 1, overflow: 'hidden' },

  quickNav: { flexDirection: 'row', gap: 8, marginTop: 18 },
  disclaimer: { fontSize: 10, marginTop: 18, lineHeight: 14, paddingHorizontal: 4 },
});
