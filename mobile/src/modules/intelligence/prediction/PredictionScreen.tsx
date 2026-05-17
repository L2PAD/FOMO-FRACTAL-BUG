import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView, ActivityIndicator,
  StyleSheet, Dimensions, Platform, Animated, Easing, StatusBar as RNStatusBar,
  BackHandler,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import Svg, { Path, Defs, LinearGradient, Stop, Circle, Line, Text as SvgText } from 'react-native-svg';
import { useRouter } from 'expo-router';
import { mobileApi } from '../../../services/api/mobile-api';

import { t } from '../../../core/i18n';
const { width: SCREEN_W } = Dimensions.get('window');
const CHART_W = SCREEN_W - 32;
const CHART_H = 240;
const PAD = { top: 22, right: 16, bottom: 30, left: 54 };

const HORIZONS = ['7D', '30D', '90D', '180D', '365D'];

const C = {
  bg: '#0B0F14', card: '#0F141B', border: '#16202B',
  text: '#E6EDF3', sub: '#9FB0C0', muted: '#6B7C8F',
  green: '#2FE6A6', red: '#FF6B6B', neutral: '#6B7C8F',
  gold: '#F5C451',
};

/* Animated SVG primitives */
const ACircle = Animated.createAnimatedComponent(Circle);
const APath = Animated.createAnimatedComponent(Path);

/* Normalize any backend direction → UI bias */
const toBias = (d: any): 'Bullish' | 'Bearish' | 'Neutral' => {
  const s = String(d || '').toUpperCase();
  if (s.includes('BULL') || s === 'UP') return 'Bullish';
  if (s.includes('BEAR') || s === 'DOWN') return 'Bearish';
  return 'Neutral';
};

const biasColor = (bias: string) =>
  bias === 'Bullish' ? C.green : bias === 'Bearish' ? C.red : C.neutral;

const confColor = (conf: number, bias: string) => {
  const base = biasColor(bias);
  if (bias === 'Neutral') return C.neutral;
  if (conf >= 65) return base;
  if (conf >= 45) return base;
  return C.muted;
};

interface TF {
  key: string; days: number; direction: string; confidence: number; expectedReturn: number;
  projectedSeries?: { t: string; v: number }[]; upperBand?: { t: string; v: number }[];
  lowerBand?: { t: string; v: number }[]; target?: number; locked?: boolean;
}
interface PD {
  ok: boolean; symbol: string; currentPrice: number; dailyChange: number;
  activeHorizon: string; regime: string;
  summary: { bias: string; biasEmoji: string; confidence: number; expectedMove: string; summaryText: string };
  priceSeries: { t: string; v: number }[]; timeframes: TF[];
  scenarios: Record<string, any>; interpretation: string[];
  truth: any; signalConnection: any; accessLevel: string;
}

/* ─── ANIMATED PREDICTION CHART ─── */
function PredChart({
  data, horizon, mode, bias,
}: { data: PD; horizon: string; mode: 'PATH' | 'RANGE'; bias: string }) {
  const drawAnim = useRef(new Animated.Value(0)).current;
  const pulseAnim = useRef(new Animated.Value(0)).current;
  const pulseOpacity = useRef(new Animated.Value(0.4)).current;

  useEffect(() => {
    drawAnim.stopAnimation();
    drawAnim.setValue(0);
    Animated.timing(drawAnim, {
      toValue: 1,
      duration: 1400,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: false,
    }).start();
  }, [horizon, mode]);

  useEffect(() => {
    Animated.loop(
      Animated.parallel([
        Animated.sequence([
          Animated.timing(pulseAnim, { toValue: 1, duration: 1200, easing: Easing.out(Easing.quad), useNativeDriver: false }),
          Animated.timing(pulseAnim, { toValue: 0, duration: 0, useNativeDriver: false }),
        ]),
        Animated.sequence([
          Animated.timing(pulseOpacity, { toValue: 0, duration: 1200, easing: Easing.out(Easing.quad), useNativeDriver: false }),
          Animated.timing(pulseOpacity, { toValue: 0.4, duration: 0, useNativeDriver: false }),
        ]),
      ])
    ).start();
  }, []);

  const tf = data.timeframes.find(t => t.key === horizon);
  const prices = data.priceSeries;
  const proj = tf?.projectedSeries || [];
  const upper = tf?.upperBand || [];
  const lower = tf?.lowerBand || [];
  if (!prices.length) return null;

  const allV = [
    ...prices.map(p => p.v),
    ...proj.map(p => p.v),
    ...(mode === 'RANGE' ? upper.map(p => p.v) : []),
    ...(mode === 'RANGE' ? lower.map(p => p.v) : []),
  ].filter(v => v > 0);
  const mn = Math.min(...allV) * 0.995, mx = Math.max(...allV) * 1.005;
  const total = prices.length + proj.length;
  const xF = (i: number) => PAD.left + (i / Math.max(total - 1, 1)) * (CHART_W - PAD.left - PAD.right);
  const yF = (v: number) => PAD.top + (1 - (v - mn) / (mx - mn)) * (CHART_H - PAD.top - PAD.bottom);

  const pricePath = prices.map((p, i) => `${i === 0 ? 'M' : 'L'}${xF(i).toFixed(1)},${yF(p.v).toFixed(1)}`).join(' ');
  const off = prices.length - 1;
  const projPath = proj.length > 0
    ? `M${xF(off).toFixed(1)},${yF(prices[off]?.v || 0).toFixed(1)} ` + proj.map((p, i) => `L${xF(off + i + 1).toFixed(1)},${yF(p.v).toFixed(1)}`).join(' ')
    : '';

  let bandPath = '';
  if (mode === 'RANGE' && upper.length && lower.length) {
    const uPts = upper.map((p, i) => `${xF(off + i + 1).toFixed(1)},${yF(p.v).toFixed(1)}`);
    const lPts = lower.map((p, i) => `${xF(off + i + 1).toFixed(1)},${yF(p.v).toFixed(1)}`).reverse();
    bandPath = `M${xF(off).toFixed(1)},${yF(prices[off]?.v || 0).toFixed(1)} ${uPts.map(p => `L${p}`).join(' ')} ${lPts.map(p => `L${p}`).join(' ')} Z`;
  }

  // Approximate projected path length for draw animation (chord length scaled)
  const projChords = proj.length;
  const approxLen = projChords > 0 ? Math.max(
    Math.hypot(xF(off + projChords) - xF(off), yF(proj[projChords - 1].v) - yF(prices[off]?.v || 0)) * 1.8,
    CHART_W * 0.6,
  ) : 0;
  const dashOffset = drawAnim.interpolate({ inputRange: [0, 1], outputRange: [approxLen, 0] });

  const nowX = xF(off), nowY = yF(prices[off]?.v || 0);
  const bc = biasColor(bias);
  const yLabels = Array.from({ length: 5 }, (_, i) => mn + (mx - mn) * (i / 4));

  const pulseR = pulseAnim.interpolate({ inputRange: [0, 1], outputRange: [4, 18] });

  return (
    <Svg width={CHART_W} height={CHART_H}>
      <Defs>
        <LinearGradient id="bandBg" x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor={bc} stopOpacity="0.18" />
          <Stop offset="1" stopColor={bc} stopOpacity="0.02" />
        </LinearGradient>
        {/* Horizontal fade: near = solid, far = semi-transparent */}
        <LinearGradient id="projFade" x1="0" y1="0" x2="1" y2="0">
          <Stop offset="0" stopColor={bc} stopOpacity="1" />
          <Stop offset="0.6" stopColor={bc} stopOpacity="0.75" />
          <Stop offset="1" stopColor={bc} stopOpacity="0.35" />
        </LinearGradient>
      </Defs>

      {/* Y-axis grid */}
      {yLabels.map((v, i) => (
        <React.Fragment key={i}>
          <Line x1={PAD.left} y1={yF(v)} x2={CHART_W - PAD.right} y2={yF(v)} stroke={C.border} strokeWidth={0.5} strokeDasharray="4,4" />
          <SvgText x={PAD.left - 6} y={yF(v) + 4} fill={C.muted} fontSize={9} textAnchor="end">
            {v >= 1000 ? `$${(v / 1000).toFixed(1)}K` : `$${v.toFixed(0)}`}
          </SvgText>
        </React.Fragment>
      ))}

      {/* NOW divider */}
      <Line x1={nowX} y1={PAD.top} x2={nowX} y2={CHART_H - PAD.bottom} stroke={C.muted} strokeWidth={0.5} strokeDasharray="3,5" />

      {/* RANGE band */}
      {bandPath ? <Path d={bandPath} fill="url(#bandBg)" /> : null}

      {/* History line (neutral, subtle) */}
      <Path d={pricePath} fill="none" stroke="rgba(255,255,255,0.72)" strokeWidth={1.5} strokeLinejoin="round" />

      {/* Projection line — bias-colored, drawn animated */}
      {projPath ? (
        <APath
          d={projPath}
          fill="none"
          stroke="url(#projFade)"
          strokeWidth={2.8}
          strokeDasharray={approxLen}
          strokeDashoffset={dashOffset as any}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ) : null}

      {/* NOW pulse ring */}
      <ACircle cx={nowX} cy={nowY} r={pulseR as any} fill={bc} opacity={pulseOpacity as any} />
      <Circle cx={nowX} cy={nowY} r={5} fill={C.bg} stroke={bc} strokeWidth={2} />
      <SvgText x={nowX} y={nowY - 12} fill={bc} fontSize={9} fontWeight="800" textAnchor="middle">NOW</SvgText>

      {/* Target point */}
      {proj.length > 0 && tf?.target ? (
        <>
          <Circle cx={xF(total - 1)} cy={yF(tf.target)} r={5} fill={bc} opacity={0.25} />
          <Circle cx={xF(total - 1)} cy={yF(tf.target)} r={3} fill={bc} />
          <SvgText x={xF(total - 1)} y={yF(tf.target) - 10} fill={bc} fontSize={10} fontWeight="800" textAnchor="middle">
            ${(tf.target / 1000).toFixed(1)}K
          </SvgText>
        </>
      ) : null}
    </Svg>
  );
}

/* ─── MAIN SCREEN ─── */
export default function PredictionScreen({ onClose }: { onClose?: () => void } = {}) {
  const router = useRouter();
  const ins = useSafeAreaInsets();
  const [data, setData] = useState<PD | null>(null);
  const [loading, setLoading] = useState(true);
  const [horizon, setHorizon] = useState('30D');
  const [mode, setMode] = useState<'PATH' | 'RANGE'>('PATH');

  const fetch = useCallback(async (h: string) => {
    setLoading(true);
    try {
      const r = await mobileApi.getPredictionChart('BTC', h);
      setData(r);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch(horizon); }, [horizon]);

  // Handle Android hardware back button
  useEffect(() => {
    const handler = () => {
      if (onClose) { onClose(); return true; }
      return false;
    };
    const sub = BackHandler.addEventListener('hardwareBackPress', handler);
    return () => sub.remove();
  }, [onClose]);

  const doClose = useCallback(() => {
    if (onClose) onClose();
    else router.back();
  }, [onClose, router]);

  // Bias of the ACTIVE horizon (not global), ensures color matches horizon
  const activeBias = useMemo(() => {
    if (!data) return 'Neutral';
    const tf = data.timeframes.find(t => t.key === horizon);
    return toBias(tf?.direction || data.summary.bias);
  }, [data, horizon]);
  const bc = biasColor(activeBias);

  if (loading && !data) return (
    <SafeAreaView style={st.root} edges={['top', 'left', 'right']}>
      <StatusBar style="light" translucent backgroundColor="transparent" />
      <ActivityIndicator size="large" color={C.neutral} style={{ marginTop: 120 }} />
    </SafeAreaView>
  );
  if (!data?.ok) return (
    <SafeAreaView style={st.root} edges={['top', 'left', 'right']}>
      <StatusBar style="light" translucent backgroundColor="transparent" />
      <Text style={{ color: C.sub, textAlign: 'center', marginTop: 120 }}>{t('intelPrediction.failedToLoad')}</Text>
    </SafeAreaView>
  );

  const { summary, scenarios, interpretation, regime, truth, signalConnection } = data;

  return (
    <SafeAreaView
      style={st.root}
      edges={['top', 'left', 'right']}
      testID="prediction-screen"
    >
      <StatusBar style="light" translucent backgroundColor="transparent" />

      {/* Fixed header — stays put while content scrolls */}
      <View style={st.hdrWrap}>
        <View style={st.hdr}>
          <TouchableOpacity
            onPress={doClose}
            testID="prediction-back-btn"
            style={st.backBtn}
            hitSlop={{ top: 20, bottom: 20, left: 20, right: 20 }}
            activeOpacity={0.5}
          >
            <Ionicons name="chevron-back" size={26} color={C.text} />
          </TouchableOpacity>
          <View style={{ flex: 1, marginLeft: 6 }}>
            <Text style={st.hdrTitle} numberOfLines={1}>{t('intelPrediction.btcPrediction')}</Text>
            <Text style={st.hdrSub} numberOfLines={1}>Model Output · {horizon} path</Text>
          </View>
          <View style={[st.badge, { borderColor: bc }]}>
            <Text style={[st.badgeT, { color: bc }]}>{regime}</Text>
          </View>
          <TouchableOpacity
            onPress={doClose}
            testID="prediction-close-x"
            style={st.closeX}
            hitSlop={{ top: 20, bottom: 20, left: 20, right: 20 }}
            activeOpacity={0.5}
          >
            <Ionicons name="close" size={22} color={C.text} />
          </TouchableOpacity>
        </View>
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={{ paddingTop: 12, paddingBottom: 60 }}
        bounces={true}
      >
        {/* Hero */}
        <View style={st.hero} testID="prediction-hero">
          <View style={st.heroTop}>
            <View>
              <Text style={st.price}>${data.currentPrice.toLocaleString()}</Text>
              <Text style={[st.chg, { color: data.dailyChange >= 0 ? C.green : C.red }]}>
                {data.dailyChange >= 0 ? '+' : ''}{data.dailyChange}% 24h
              </Text>
            </View>
            <View style={{ alignItems: 'flex-end' }}>
              <View style={[st.pill, { backgroundColor: bc + '18', borderColor: bc }]}>
                <Text style={[st.pillT, { color: bc }]}>{summary.biasEmoji} {activeBias}</Text>
              </View>
              <Text style={[st.conf, { color: confColor(summary.confidence, activeBias) }]}>{summary.confidence}% confidence</Text>
            </View>
          </View>
          <View style={[st.moveRow, { borderTopColor: C.border }]}>
            <Ionicons name="flash" size={14} color={C.gold} />
            <Text style={st.moveT}>Expected move: {summary.expectedMove}</Text>
          </View>
          <Text style={st.sumT}>{summary.summaryText}</Text>
        </View>

        {/* ═══ MARKET STATE BANNER (3rd layer: State Engine) ═══ */}
        {(() => {
          const state = (summary as any).marketState || 'SCANNING';
          const stateText = (summary as any).marketStateText || '';
          const stateColorName = (summary as any).marketStateColor || 'gray';
          const stateColor = stateColorName === 'green' ? C.green
                           : stateColorName === 'red' ? C.red
                           : stateColorName === 'gold' ? C.gold
                           : C.neutral;
          const icon: any = state === 'TENSION' ? 'flash'
                          : state === 'CONFLICT' ? 'git-compare-outline'
                          : state === 'BREAKOUT_FORMING' ? 'rocket-outline'
                          : state === 'ALIGNED' ? 'checkmark-circle'
                          : state === 'CALM' ? 'moon-outline'
                          : 'pulse-outline';
          const drivers = data.metabrain?.drivers || {};
          const driverList = Object.entries(drivers).map(([k, v]: any) => ({
            key: k,
            name: k.charAt(0).toUpperCase() + k.slice(1).replace('_', ' '),
            direction: v.direction || 'Neutral',
            confidence: v.confidence || 0,
            weight: v.weight || 0,
          })).filter(d => d.weight > 0).sort((a, b) => b.weight - a.weight);
          const showBreakdown = state === 'CONFLICT' || state === 'TENSION' || (summary as any).hasConflict;

          return (
            <View style={[st.stateBanner, { borderColor: stateColor + '55', backgroundColor: stateColor + '0E' }]} testID="market-state-banner">
              <View style={st.stateTop}>
                <Ionicons name={icon} size={18} color={stateColor} />
                <Text style={[st.stateLabel, { color: stateColor }]}>{t('intelPrediction.marketState')}</Text>
                <View style={{ flex: 1 }} />
                <View style={[st.statePill, { borderColor: stateColor, backgroundColor: stateColor + '25' }]}>
                  <Text style={[st.statePillT, { color: stateColor }]}>{state.replace('_', ' ')}</Text>
                </View>
              </View>
              {!!stateText && <Text style={st.stateText}>{stateText}</Text>}

              {/* ACTION VERB — tells user what to do RIGHT NOW */}
              {(summary as any).actionVerb && (
                <View style={[st.actionRow, { backgroundColor: stateColor + '18', borderColor: stateColor + '55' }]}>
                  <Text style={[st.actionVerb, { color: stateColor }]}>→ {(summary as any).actionVerb}</Text>
                  <Text style={[st.actionHint, { color: C.text }]}>{(summary as any).actionHint}</Text>
                </View>
              )}

              {/* Dual metric with labels */}
              <View style={[st.stateMetrics, { borderTopColor: stateColor + '30' }]}>
                <View style={st.stateMetric}>
                  <Text style={[st.stateMetricVal, { color: C.text }]}>{summary.confidence}%</Text>
                  <Text style={[st.stateMetricLbl, { color: stateColor }]}>{(summary as any).confidenceLabel || 'LOW'} AGREEMENT</Text>
                </View>
                <View style={[st.stateMetricSep, { backgroundColor: stateColor + '30' }]} />
                <View style={st.stateMetric}>
                  <Text style={[st.stateMetricVal, { color: C.text }]}>{(summary as any).conviction || 0}%</Text>
                  <Text style={[st.stateMetricLbl, { color: stateColor }]}>{(summary as any).convictionLabel || 'LOW'} CONVICTION</Text>
                </View>
              </View>

              {/* Module breakdown — narratives (not just arrows) */}
              {showBreakdown && driverList.length > 0 && (
                <View style={[st.driverBreakdown, { borderTopColor: stateColor + '30' }]}>
                  <Text style={[st.driverBreakdownTitle, { color: C.muted }]}>{t('intelPrediction.moduleBreakdown')}</Text>
                  {driverList.slice(0, 5).map((d: any) => {
                    const dirColor = d.direction === 'Bullish' ? C.green
                                   : d.direction === 'Bearish' ? C.red : C.neutral;
                    const arr = d.direction === 'Bullish' ? '↑'
                              : d.direction === 'Bearish' ? '↓' : '→';
                    const dv = (data.metabrain?.drivers || {})[d.key] || {};
                    const narr = dv.narrative || '';
                    return (
                      <View key={d.key} style={st.driverRow}>
                        <View style={{ flex: 1 }}>
                          <Text style={st.driverName}>{d.name}</Text>
                          {!!narr && <Text style={[st.driverNarr, { color: dirColor + 'AA' }]}>{narr}</Text>}
                        </View>
                        <Text style={[st.driverDir, { color: dirColor }]}>{arr}</Text>
                      </View>
                    );
                  })}
                </View>
              )}
            </View>
          );
        })()}

        {/* ═══ NEXT MOVE LEVELS (actionable break points) ═══ */}
        {(data as any).nextMoveLevels?.breakAbove && (
          <View style={st.sec} testID="next-move-levels">
            <Text style={st.secT}>{t('intelPrediction.nextMoveLevels')}</Text>
            <View style={st.nextMoveCard}>
              <View style={[st.nextRow, { borderBottomWidth: 1, borderBottomColor: C.border }]}>
                <View style={st.nextIconWrap}>
                  <Ionicons name="arrow-up" size={14} color={C.green} />
                </View>
                <View style={{ flex: 1, marginLeft: 8 }}>
                  <Text style={[st.nextPrice, { color: C.green }]}>Break above ${((data as any).nextMoveLevels.breakAbove.price || 0).toLocaleString()}</Text>
                  <Text style={st.nextScenario}>{(data as any).nextMoveLevels.breakAbove.scenario}</Text>
                </View>
                <Text style={[st.nextDist, { color: C.green }]}>+{(data as any).nextMoveLevels.breakAbove.distancePct}%</Text>
              </View>
              <View style={st.nextRow}>
                <View style={st.nextIconWrap}>
                  <Ionicons name="arrow-down" size={14} color={C.red} />
                </View>
                <View style={{ flex: 1, marginLeft: 8 }}>
                  <Text style={[st.nextPrice, { color: C.red }]}>Break below ${((data as any).nextMoveLevels.breakBelow.price || 0).toLocaleString()}</Text>
                  <Text style={st.nextScenario}>{(data as any).nextMoveLevels.breakBelow.scenario}</Text>
                </View>
                <Text style={[st.nextDist, { color: C.red }]}>{(data as any).nextMoveLevels.breakBelow.distancePct}%</Text>
              </View>
            </View>
          </View>
        )}

        {/* ═══ STATE HISTORY STATS ═══ */}
        {(data as any).stateHistory?.available && (
          <View style={st.sec} testID="state-history">
            <Text style={st.secT}>{t('intelPrediction.stateTrackRecord')}</Text>
            <View style={[st.historyCard, { borderColor: bc + '55' }]}>
              <Text style={[st.historyLead, { color: C.sub }]}>
                Last {(data as any).stateHistory.occurrences}× this state appeared → avg move
              </Text>
              <Text style={[st.historyBig, { color: bc }]}>
                ±{(data as any).stateHistory.avgAbsMove}%
              </Text>
              {(data as any).stateHistory.recentMoves?.length > 0 && (
                <View style={st.historyMoves}>
                  {(data as any).stateHistory.recentMoves.slice(0, 5).map((m: number, i: number) => (
                    <View key={i} style={[st.historyChip, { borderColor: m > 0 ? C.green : C.red }]}>
                      <Text style={[st.historyChipT, { color: m > 0 ? C.green : C.red }]}>
                        {m > 0 ? '+' : ''}{m}%
                      </Text>
                    </View>
                  ))}
                </View>
              )}
            </View>
          </View>
        )}

        {/* Horizons — colored by their OWN direction, not a single accent */}
        <View style={st.hzRow} testID="horizon-selector">
          {HORIZONS.map(h => {
            const active = h === horizon;
            const tf = data.timeframes.find(t => t.key === h);
            const hBias = toBias(tf?.direction);
            const hColor = biasColor(hBias);
            const conf = Math.round((tf?.confidence || 0) * 100);
            return (
              <TouchableOpacity
                key={h}
                testID={`hz-${h}`}
                onPress={() => setHorizon(h)}
                style={[
                  st.hzBtn,
                  active && { backgroundColor: hColor + '22', borderColor: hColor },
                ]}
              >
                <Text style={[st.hzLbl, { color: active ? C.text : C.muted }]}>{h}</Text>
                {conf > 0 && (
                  <Text style={[st.hzConf, { color: active ? hColor : confColor(conf, hBias) }]}>
                    {conf}%
                  </Text>
                )}
                {/* thin direction bar under label */}
                <View style={[st.hzBar, { backgroundColor: hColor, opacity: active ? 1 : 0.35 }]} />
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Chart + PATH / RANGE toggle */}
        <View style={st.chartWrap} testID="prediction-chart">
          <View style={st.chartModeRow}>
            <Text style={st.chartModeLbl}>MODE</Text>
            <View style={st.chartModeSwitch}>
              <TouchableOpacity
                testID="mode-path"
                onPress={() => setMode('PATH')}
                style={[st.modeBtn, mode === 'PATH' && { backgroundColor: bc + '22', borderColor: bc }]}
              >
                <Text style={[st.modeBtnT, { color: mode === 'PATH' ? bc : C.muted }]}>PATH</Text>
              </TouchableOpacity>
              <TouchableOpacity
                testID="mode-range"
                onPress={() => setMode('RANGE')}
                style={[st.modeBtn, mode === 'RANGE' && { backgroundColor: bc + '22', borderColor: bc }]}
              >
                <Text style={[st.modeBtnT, { color: mode === 'RANGE' ? bc : C.muted }]}>RANGE</Text>
              </TouchableOpacity>
            </View>
          </View>
          {loading
            ? <ActivityIndicator color={bc} style={{ marginVertical: 100 }} />
            : <PredChart data={data} horizon={horizon} mode={mode} bias={activeBias} />
          }
          <Text style={st.chartFoot}>
            {mode === 'PATH' ? 'Most likely path' : 'Range of probable outcomes'} · productized model output
          </Text>
        </View>

        {/* Scenarios */}
        {scenarios && Object.keys(scenarios).length > 0 && (
          <View style={st.sec} testID="scenarios">
            <Text style={st.secT}>Scenarios</Text>
            {Object.entries(scenarios).map(([k, sc]: [string, any]) => {
              // Scenarios: base = activeBias, bull = Bullish, risk = Bearish
              const scBias = k === 'bull' ? 'Bullish' : k === 'risk' ? 'Bearish' : activeBias;
              const scColor = biasColor(scBias);
              return (
                <View key={k} style={[st.scCard, sc.locked && { opacity: 0.5 }, { borderLeftColor: scColor, borderLeftWidth: 3 }]}>
                  {sc.locked ? (
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                      <Ionicons name="lock-closed" size={13} color={C.muted} />
                      <Text style={{ color: C.muted, fontSize: 13 }}>{sc.label} — PRO</Text>
                    </View>
                  ) : (
                    <>
                      <Text style={[st.scLbl, { color: scColor }]}>{sc.label}</Text>
                      <Text style={st.scDesc}>{sc.description}</Text>
                      {sc.target > 0 && (
                        <View style={st.scTargetRow}>
                          <Ionicons name="flag" size={12} color={scColor} />
                          <Text style={[st.scTarget, { color: scColor }]}>Target: ${sc.target?.toLocaleString()}</Text>
                          {sc.probability > 0 && <Text style={st.scProb}>{Math.round(sc.probability * 100)}%</Text>}
                        </View>
                      )}
                    </>
                  )}
                </View>
              );
            })}
          </View>
        )}

        {/* What model sees */}
        {interpretation?.length > 0 && (
          <View style={st.sec} testID="interpretation">
            <Text style={st.secT}>{t('intelPrediction.whatModelSeesNow')}</Text>
            {interpretation.map((b, i) => (
              <View key={i} style={st.bulRow}>
                <View style={[st.bulDot, { backgroundColor: bc, opacity: 1 - i * 0.15 }]} />
                <Text style={st.bulT}>{b}</Text>
              </View>
            ))}
          </View>
        )}

        {/* Signal Connection */}
        {signalConnection && (
          <View style={st.sec} testID="signal-conn">
            <Text style={st.secT}>{t('intelPrediction.signalConnection')}</Text>
            <View style={st.connCard}>
              <View style={st.connRow}>
                <Text style={st.connL}>{t('intelPrediction.signalStage')}</Text>
                <View style={[st.connPill, { borderColor: bc }]}>
                  <Text style={[st.connV, { color: bc }]}>{signalConnection.stage}</Text>
                </View>
              </View>
              <View style={st.connRow}>
                <Text style={st.connL}>{t('intelPrediction.entryWindow')}</Text>
                <Text style={[st.connV, { color: signalConnection.entryWindowActive ? C.green : C.muted }]}>
                  {signalConnection.entryWindowActive ? '● Active' : '○ Waiting'}
                </Text>
              </View>
            </View>
          </View>
        )}

        {/* Truth */}
        {truth?.available && (
          <View style={st.sec} testID="truth">
            <Text style={st.secT}>{t('intelPrediction.historicalAccuracy')}</Text>
            <View style={st.truthRow}>
              {[
                { n: `${truth.winRate}%`, l: 'Win Rate', c: truth.winRate > 55 ? C.green : C.text },
                { n: truth.totalForecasts, l: 'Forecasts', c: C.text },
                { n: truth.streak, l: 'Streak', c: C.green },
              ].map((it, i) => (
                <View key={i} style={st.truthItem}>
                  <Text style={[st.truthN, { color: it.c }]}>{it.n}</Text>
                  <Text style={st.truthL}>{it.l}</Text>
                </View>
              ))}
            </View>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  hdrWrap: {
    borderBottomWidth: 1,
    borderBottomColor: C.border,
    backgroundColor: C.bg,
    ...(Platform.OS === 'android' ? { paddingTop: (RNStatusBar.currentHeight || 0) } : {}),
  },
  hdr: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 10,
    minHeight: 56,
  },
  backBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
  },
  closeX: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 6,
    backgroundColor: C.card,
  },
  hdrTitle: { fontSize: 17, fontWeight: '800', color: C.text, letterSpacing: -0.3 },
  hdrSub: { fontSize: 11, color: C.sub, marginTop: 1 },
  badge: { borderWidth: 1, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3, marginLeft: 8 },
  badgeT: { fontSize: 9, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 1 },
  hero: { margin: 16, padding: 16, backgroundColor: C.card, borderRadius: 16, borderWidth: 1, borderColor: C.border },

  /* State Banner — 3rd layer (State Engine) */
  stateBanner: { marginHorizontal: 16, marginTop: 2, marginBottom: 14, padding: 14, borderRadius: 14, borderWidth: 1 },
  stateTop: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  stateLabel: { fontSize: 10, fontWeight: '800', letterSpacing: 1.5 },
  statePill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 6, borderWidth: 1 },
  statePillT: { fontSize: 10, fontWeight: '900', letterSpacing: 1.2 },
  stateText: { fontSize: 13, color: C.text, marginTop: 8, lineHeight: 19 },
  stateMetrics: { flexDirection: 'row', alignItems: 'center', marginTop: 12, paddingTop: 12, borderTopWidth: 1 },
  stateMetric: { flex: 1, alignItems: 'center' },
  stateMetricVal: { fontSize: 20, fontWeight: '900', fontVariant: ['tabular-nums'] as any },
  stateMetricLbl: { fontSize: 9, fontWeight: '800', letterSpacing: 1, marginTop: 2 },
  stateMetricSep: { width: 1, height: 36 },
  driverBreakdown: { marginTop: 12, paddingTop: 10, borderTopWidth: 1 },
  driverBreakdownTitle: { fontSize: 9, fontWeight: '800', letterSpacing: 1.5, marginBottom: 8 },
  driverRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 5 },
  driverName: { fontSize: 13, color: C.text, fontWeight: '600' },
  driverDir: { fontSize: 12, fontWeight: '700', marginRight: 10 },
  driverConf: { fontSize: 11, color: C.muted, fontWeight: '600', minWidth: 32, textAlign: 'right' },
  reversalHint: { fontSize: 11, fontWeight: '700', marginTop: 8, fontStyle: 'italic', textAlign: 'center' },
  driverNarr: { fontSize: 11, marginTop: 2, fontWeight: '500' },

  /* Action verb row (tells user what to do NOW) */
  actionRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 12, padding: 10, borderRadius: 10, borderWidth: 1 },
  actionVerb: { fontSize: 12, fontWeight: '900', letterSpacing: 1 },
  actionHint: { flex: 1, fontSize: 12, fontWeight: '600' },

  /* Next Move Levels */
  nextMoveCard: { backgroundColor: C.card, borderRadius: 12, borderWidth: 1, borderColor: C.border, overflow: 'hidden' },
  nextRow: { flexDirection: 'row', alignItems: 'center', padding: 12 },
  nextIconWrap: { width: 26, height: 26, borderRadius: 13, alignItems: 'center', justifyContent: 'center', backgroundColor: C.border },
  nextPrice: { fontSize: 13, fontWeight: '800' },
  nextScenario: { fontSize: 11, color: C.muted, marginTop: 2 },
  nextDist: { fontSize: 13, fontWeight: '800', fontVariant: ['tabular-nums'] as any },

  /* State History */
  historyCard: { backgroundColor: C.card, borderRadius: 12, padding: 14, borderWidth: 1, alignItems: 'center' },
  historyLead: { fontSize: 12, textAlign: 'center' },
  historyBig: { fontSize: 34, fontWeight: '900', marginTop: 4, fontVariant: ['tabular-nums'] as any },
  historyMoves: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 10, justifyContent: 'center' },
  historyChip: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 5, borderWidth: 1 },
  historyChipT: { fontSize: 11, fontWeight: '800', fontVariant: ['tabular-nums'] as any },
  heroTop: { flexDirection: 'row', justifyContent: 'space-between' },
  price: { fontSize: 30, fontWeight: '900', color: C.text, letterSpacing: -0.5 },
  chg: { fontSize: 13, fontWeight: '600', marginTop: 3 },
  pill: { borderWidth: 1, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 5 },
  pillT: { fontSize: 14, fontWeight: '800' },
  conf: { fontSize: 11, marginTop: 5, fontWeight: '600' },
  moveRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 14, paddingTop: 12, borderTopWidth: 1 },
  moveT: { fontSize: 14, fontWeight: '700', color: C.gold },
  sumT: { fontSize: 13, color: C.sub, marginTop: 8, lineHeight: 19 },

  hzRow: { flexDirection: 'row', paddingHorizontal: 16, gap: 6, marginBottom: 4 },
  hzBtn: { flex: 1, alignItems: 'center', paddingVertical: 10, borderRadius: 10, borderWidth: 1, borderColor: C.border, backgroundColor: C.card, overflow: 'hidden' },
  hzLbl: { fontSize: 11, fontWeight: '800' },
  hzConf: { fontSize: 9, fontWeight: '700', marginTop: 2 },
  hzBar: { height: 2, width: '60%', marginTop: 6, borderRadius: 1 },

  chartWrap: { marginHorizontal: 16, marginTop: 10, backgroundColor: C.card, borderRadius: 16, borderWidth: 1, borderColor: C.border, padding: 10, alignItems: 'center', minHeight: CHART_H + 60 },
  chartModeRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', alignSelf: 'stretch', marginBottom: 8, paddingHorizontal: 4 },
  chartModeLbl: { fontSize: 9, fontWeight: '800', letterSpacing: 1.5, color: C.muted },
  chartModeSwitch: { flexDirection: 'row', gap: 6 },
  modeBtn: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8, borderWidth: 1, borderColor: C.border, backgroundColor: C.bg },
  modeBtnT: { fontSize: 10, fontWeight: '800', letterSpacing: 1 },
  chartFoot: { fontSize: 10, color: C.muted, marginTop: 6, fontStyle: 'italic' },

  sec: { marginHorizontal: 16, marginTop: 22 },
  secT: { fontSize: 14, fontWeight: '800', color: C.text, marginBottom: 10, letterSpacing: -0.2 },
  scCard: { backgroundColor: C.card, borderRadius: 12, padding: 14, marginBottom: 8, borderWidth: 1, borderColor: C.border },
  scLbl: { fontSize: 10, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 5 },
  scDesc: { fontSize: 14, color: C.text, lineHeight: 20 },
  scTargetRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8 },
  scTarget: { fontSize: 13, fontWeight: '800' },
  scProb: { fontSize: 11, color: C.muted, marginLeft: 'auto' },

  bulRow: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 10, gap: 10 },
  bulDot: { width: 6, height: 6, borderRadius: 3, marginTop: 6 },
  bulT: { flex: 1, fontSize: 13, color: C.sub, lineHeight: 19 },

  connCard: { backgroundColor: C.card, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: C.border },
  connRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  connL: { fontSize: 13, color: C.sub },
  connPill: { borderWidth: 1, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
  connV: { fontSize: 13, fontWeight: '700' },

  truthRow: { flexDirection: 'row', backgroundColor: C.card, borderRadius: 12, padding: 16, borderWidth: 1, borderColor: C.border },
  truthItem: { flex: 1, alignItems: 'center' },
  truthN: { fontSize: 24, fontWeight: '900' },
  truthL: { fontSize: 10, color: C.muted, marginTop: 3 },
});
