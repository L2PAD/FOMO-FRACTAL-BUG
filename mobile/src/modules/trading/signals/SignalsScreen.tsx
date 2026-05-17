/**
 * Trading OS · EXECUTION CONSOLE
 *
 * The heart of the system. This is where users perceive that an AI is
 * actually making decisions — not just showing numbers.
 *
 * Layer stack (top → bottom):
 *
 *   1. PIPELINE              RAW → META → FINAL  (animated dots, dir + conf)
 *   2. CONVICTION ENGINE     live confidence + delta (BUILDING ↑ / WEAKENING ↓)
 *   3. PARALLEL UNIVERSES    Universe A (RAW) · B (META) · C (FINAL) PnL
 *   4. WHY EXECUTED / WHY BLOCKED   per-module breakdown (5 AI modules)
 *   5. EXECUTION STRUCTURE   Entry / Stop / Targets / Invalidation / Size / Risk / RR / TF
 *   6. AI MEMORY             last 5 decisions with retrospective outcome
 *   7. EXECUTE BUTTON        (paper)
 *
 * READ-ONLY where data is read-only. NO LIVE EXECUTION.
 * No backend changes — pulls from existing endpoints only.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl, Animated, Easing, Platform, Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../../core/useColors';
import { useAssetStore } from '../../../stores/asset.store';
import { useAppMode } from '../../../stores/app-mode.store';
import { mobileApi } from '../../../services/api/mobile-api';
import { mbrainApi } from '../../../services/api/mbrain-api';
import { hapticMedium } from '../../../services/haptics.service';
import {
  CognitiveTimeline, AIThoughtProcess, DecisionPathChain, FlowState,
} from '../../../widgets/trading-bridge/CognitiveMemoryStream';
import { ConvictionEvolution } from '../../../widgets/cognition/ConvictionEvolution';
import { ShadowDeploymentPosture } from '../../../widgets/cognition/ShadowDeploymentPosture';
import { PaperRuntimeNotActive } from '../../../widgets/cognition/PaperRuntimeNotActive';
import { CognitiveBadge } from '../../../widgets/cognition/CognitiveBadge';
import {
  cognitionStyle, decisionStyle, explanationStyle, telemetryStyle,
} from '../../../widgets/cognition/cognitiveType';
import { tokenForState } from '../../../widgets/cognition/cognitiveTokens';
import { CognitiveAnchor } from '../../../widgets/cognition/CognitiveAnchor';
import { CognitiveRail } from '../../../widgets/cognition/CognitiveRail';
import { BusPulse } from '../../../widgets/cognition/bus/cognitiveBus';

import { t } from '../../../core/i18n';
// ─── helpers ────────────────────────────────────────────────────────
type Dir = 'LONG' | 'SHORT' | 'HOLD' | 'WAIT' | 'BUY' | 'SELL' | 'BULLISH' | 'BEARISH' | 'NEUTRAL' | string;

function dirColor(d: Dir | undefined | null, c: any): string {
  if (!d) return c.textMuted;
  if (d === 'LONG' || d === 'BUY' || d === 'BULLISH') return c.buy;
  if (d === 'SHORT' || d === 'SELL' || d === 'BEARISH') return c.sell;
  return c.textMuted;
}
function pct(n: number | null | undefined, d = 1): string {
  if (n == null || isNaN(n)) return '—';
  return `${(n * 100).toFixed(d)}%`;
}
function pctRaw(n: number | null | undefined, d = 1): string {
  if (n == null || isNaN(n)) return '—';
  const sign = n >= 0 ? '+' : '';
  return `${sign}${n.toFixed(d)}%`;
}
function fmtNum(n: number | null | undefined, d = 2): string {
  if (n == null || isNaN(n)) return '—';
  return n.toFixed(d);
}

// ─── pulse dot ──────────────────────────────────────────────────────
function PulseDot({ color, size = 10 }: { color: string; size?: number }) {
  const scale = useMemo(() => new Animated.Value(1), []);
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(scale, { toValue: 1.7, duration: 900, easing: Easing.out(Easing.ease), useNativeDriver: true }),
        Animated.timing(scale, { toValue: 1, duration: 900, easing: Easing.in(Easing.ease), useNativeDriver: true }),
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
        backgroundColor: color, opacity: 0.35, transform: [{ scale }],
      }} />
      <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: color }} />
    </View>
  );
}

// ─── main screen ────────────────────────────────────────────────────
export function SignalsScreen() {
  const colors = useColors();
  const asset = useAssetStore((s) => s.currentAsset);
  const setTradingTab = useAppMode((s) => s.setTradingTab);
  const styles = useMemo(() => mk(colors), [colors]);

  const [signal, setSignal] = useState<any>(null);
  const [fractal, setFractal] = useState<any>(null);
  const [sentiment, setSentiment] = useState<any>(null);
  const [marketState, setMarketState] = useState<any>(null);
  const [intel, setIntel] = useState<any>(null);
  const [verdicts, setVerdicts] = useState<any[]>([]);
  const [parallel, setParallel] = useState<any>(null);
  const [openPositions, setOpenPositions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [executing, setExecuting] = useState(false);

  const fetchAll = useCallback(async () => {
    const r = await Promise.allSettled([
      mobileApi.getSignal(asset),
      mobileApi.getFractal(asset),
      mobileApi.getSentiment(asset),
      mobileApi.getMarketState(),
      mobileApi.getIntelOverview(asset),
      mbrainApi.listVerdicts(50),
      mbrainApi.parallelPortfolios(200, true),
      mobileApi.getPositions('OPEN'),
    ]);
    const get = (i: number) => (r[i].status === 'fulfilled' ? (r[i] as any).value : null);
    const s = get(0); setSignal(s?.signal || s || null);
    setFractal(get(1));
    setSentiment(get(2));
    setMarketState(get(3));
    setIntel(get(4));
    const v = get(5); setVerdicts(v?.cards || []);
    setParallel(get(6));
    const p = get(7); setOpenPositions(p?.positions || []);
    setLoading(false);
    setRefreshing(false);
  }, [asset]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Focused verdict for current asset (highest-conf final directional).
  const focused = useMemo(() => {
    if (!verdicts.length) return null;
    const sym = `${asset}USDT`;
    const exact = verdicts.filter((c: any) => c.symbol === sym);
    const pool = exact.length ? exact : verdicts;
    return pool.slice().sort((a: any, b: any) => (b.confidence_final || 0) - (a.confidence_final || 0))[0] || null;
  }, [verdicts, asset]);

  const handleExecute = useCallback(async () => {
    if (!signal || signal.action === 'WAIT') return;
    if (Platform.OS !== 'web') hapticMedium();
    setExecuting(true);
    try {
      const res = await mobileApi.openTrade(
        signal.asset || asset,
        signal.action,
        signal.price || 0,
        signal.confidence || 0,
        'execution_console',
      );
      if (res?.ok) {
        await fetchAll();
        mobileApi.trackEvent('trade_open', {
          asset: signal.asset || asset, action: signal.action, source: 'execution_console',
        });
      } else if (Platform.OS !== 'web') {
        Alert.alert('Cannot open', res?.error || 'Try again');
      }
    } catch {} finally { setExecuting(false); }
  }, [signal, asset, fetchAll]);

  if (loading) {
    return <View style={styles.center}><ActivityIndicator color={colors.accent} /></View>;
  }

  // ── Pipeline stages: derive from focused verdict, fallback to mobile signal
  const pipeStages = focused?.stages
    ? [
        { key: 'RAW',   ...focused.stages.raw },
        { key: 'META',  ...(focused.stages.after_meta_brain || focused.stages.after_rules) },
        { key: 'FINAL', ...focused.stages.final },
      ]
    : signal
    ? [
        { key: 'RAW',   direction: signal.action === 'BUY' ? 'LONG' : signal.action === 'SELL' ? 'SHORT' : 'HOLD', confidence: signal.confidence },
        { key: 'META',  direction: signal.action === 'WAIT' ? 'HOLD' : (signal.action === 'BUY' ? 'LONG' : 'SHORT'), confidence: signal.confidence },
        { key: 'FINAL', direction: signal.action === 'WAIT' ? 'HOLD' : (signal.action === 'BUY' ? 'LONG' : 'SHORT'), confidence: signal.confidence },
      ]
    : [];

  // ── Conviction trend
  const finalConf = focused?.confidence_final ?? signal?.confidence ?? null;
  const rawConf = focused?.stages?.raw?.confidence ?? null;
  const convictionTrend: 'BUILDING' | 'WEAKENING' | 'STABLE' =
    rawConf != null && finalConf != null
      ? (finalConf - rawConf > 0.05 ? 'BUILDING'
         : finalConf - rawConf < -0.05 ? 'WEAKENING'
         : 'STABLE')
      : (finalConf != null && finalConf >= 0.6 ? 'BUILDING'
         : finalConf != null && finalConf <= 0.35 ? 'WEAKENING'
         : 'STABLE');

  // ── 5 AI modules (alignment / blockers)
  const modules = buildModuleStates(signal, fractal, sentiment, marketState, intel);
  const aligned = modules.filter((m) => m.contribution === 'enable');
  const blocking = modules.filter((m) => m.contribution === 'block');

  // ── Execution structure
  const entry = signal?.price ?? signal?.entry ?? signal?.trigger ?? null;
  const stop = signal?.stop ?? signal?.invalidation ?? null;
  const target = signal?.target ?? (entry != null ? entry * (signal?.action === 'BUY' ? 1.05 : 0.95) : null);
  const sizeUSD = 1000;  // paper-default; UI hint
  const rr = (entry != null && stop != null && target != null)
    ? Math.abs(target - entry) / Math.max(Math.abs(entry - stop), 1e-9)
    : null;
  const horizon = signal?.horizon || focused?.horizon || 'swing';
  const riskTier = focused?.risk
    || (finalConf != null ? (finalConf >= 0.7 ? 'MEDIUM' : finalConf >= 0.5 ? 'HIGH' : 'EXTREME') : 'UNKNOWN');

  // ── AI memory
  const memory = (verdicts || [])
    .filter((v: any) => v !== focused)
    .slice(0, 5)
    .map((v: any) => buildMemoryEntry(v));

  // ── Final action decision
  const finalDir = focused?.final_action || (signal?.action === 'BUY' ? 'LONG' : signal?.action === 'SELL' ? 'SHORT' : 'WAIT');
  const dCol = dirColor(finalDir, colors);
  const isBlocked = finalDir === 'WAIT' || finalDir === 'HOLD';
  const hasOpen = openPositions.some((p: any) => p.asset === (signal?.asset || asset));

  // ── Parallel universes
  const universes = parallel?.portfolios;

  return (
    <ScrollView
      testID="execution-screen"
      style={styles.container}
      contentContainerStyle={styles.content}
      stickyHeaderIndices={[0]}
      refreshControl={<RefreshControl refreshing={refreshing}
        onRefresh={() => { setRefreshing(true); fetchAll(); }}
        tintColor={colors.accent} />}
    >
      {/* ITERATION P5 · execution pulses the strongest cognitive signal in the system */}
      <BusPulse energy={isBlocked ? 'suppression' : 'readiness'} amount={isBlocked ? 0.7 : 0.5} />

      {/* ITERATION 4·β · ambient cognition anchor */}
      <CognitiveAnchor
        cognition={isBlocked ? 'SUPPRESSED' : finalDir}
        readiness={finalConf}
        colors={colors}
      />

      {/* HEADER */}
      <View style={styles.headerRow}>
        <View>
          <Text style={[styles.headerLabel, { color: colors.textMuted }]}>{t('trade.executionConsole')}</Text>
          <Text style={[styles.headerAsset, { color: colors.textPrimary }]}>{asset}</Text>
        </View>
        <View style={[styles.tfPill, { borderColor: colors.border, backgroundColor: colors.surface }]}>
          <Text style={[styles.tfText, { color: colors.textMuted }]}>{horizon}</Text>
        </View>
      </View>

      {/* FINAL DECISION HERO */}
      <View style={[styles.hero, { backgroundColor: colors.surface, borderColor: dCol + '50' }]}>
        <View style={styles.heroRow}>
          {!isBlocked && finalDir !== 'WAIT' ? <PulseDot color={dCol} /> : <View style={[styles.dotStatic, { backgroundColor: dCol }]} />}
          <Text style={[telemetryStyle(colors)]}>{t('trade.finalDecision')}</Text>
        </View>
        <Text style={[
          cognitionStyle(colors,
            isBlocked ? tokenForState('cognition', 'SUPPRESSED').energy : undefined,
            'xxl'),
        ]}>
          {isBlocked ? 'SUPPRESSED' : finalDir}
        </Text>
        <Text style={[explanationStyle(colors)]}>
          {isBlocked
            ? `${blocking.length || 'multiple'} modules blocking`
            : `${aligned.length} module${aligned.length === 1 ? '' : 's'} aligned`}
          {finalConf != null ? `  ·  ${pct(finalConf, 0)} conviction` : ''}
        </Text>
      </View>

      {/* ITERATION 4·β · cognitive rail — thought unfolding */}
      {isBlocked && blocking.length > 0 && (
        <CognitiveRail
          caps="WHY"
          head="AI rejected deployment"
          headExpanded="AI rejected deployment · because"
          reasons={blocking.slice(0, 4).map((b: any) =>
            `${(b.name || 'module').toLowerCase()} · ${(b.reason || 'no alignment').toLowerCase()}`,
          )}
          tone="suppression"
          colors={colors}
        />
      )}

      {/* STAGE A-8 · SHADOW DEPLOYMENT POSTURE — restraint context BEFORE
          raw → meta → final pipeline.  Surfaces Stage A-7 shadow runtime.
          NOT a trade signal.  Truthful absence: renders nothing when no
          shadow verdict exists for this symbol. */}
      <ShadowDeploymentPosture
        symbol={(focused?.symbol || asset || 'BTC').toString().replace(/USDT$/i, '').toUpperCase()}
        colors={colors}
        marginTop={4}
        marginBottom={8}
      />

      {/* PHASE C · PAPER RUNTIME NOT ACTIVE — observational gate state.
          NOT a CTA.  Hides entirely when paper gate opens. */}
      <PaperRuntimeNotActive colors={colors} marginTop={4} marginBottom={8} />

      {/* PIPELINE */}
      {pipeStages.length > 0 && (
        <>
          <SectionTitle text="PIPELINE" colors={colors} />
          <View style={[styles.pipe, { backgroundColor: colors.surface, borderColor: colors.border }]}>
            {pipeStages.map((stage: any, i: number) => {
              const sCol = dirColor(stage.direction, colors);
              const prev = i > 0 ? pipeStages[i - 1] : null;
              const flipped = prev && prev.direction !== stage.direction;
              return (
                <View key={stage.key} style={styles.pipeStep}>
                  <View style={styles.pipeLeft}>
                    <View style={[styles.pipeDot, { backgroundColor: sCol }]} />
                    {i < pipeStages.length - 1 && (
                      <View style={[styles.pipeLine, { backgroundColor: colors.border }]} />
                    )}
                  </View>
                  <View style={styles.pipeRight}>
                    <View style={styles.pipeHead}>
                      <Text style={[styles.pipeStage, { color: colors.textMuted }]}>{stage.key}</Text>
                      <Text style={[styles.pipeDir, { color: sCol, fontWeight: flipped ? '900' : '700' }]}>
                        {stage.direction || '—'}{flipped ? '  ⇄' : ''}
                      </Text>
                    </View>
                    <Text style={[styles.pipeConf, { color: colors.textMuted }]}>
                      conf {pct(stage.confidence)}
                      {stage.expectedReturn != null ? `  ·  expected ${pct(stage.expectedReturn)}` : ''}
                    </Text>
                  </View>
                </View>
              );
            })}
          </View>

          {/* ITERATION 3B · CONVICTION EVOLUTION — Execution evolves a single thought */}
          <View style={{ height: 12 }} />
          <ConvictionEvolution
            stages={pipeStages.map((s: any) => ({
              key: s.key,
              conf: s.confidence,
              dir: s.direction,
            }))}
            colors={colors}
          />
        </>
      )}

      {/* CONVICTION ENGINE */}
      <SectionTitle text="CONVICTION ENGINE" colors={colors} />
      <View style={[styles.conviction, {
        backgroundColor: colors.surface,
        borderColor: convictionTrend === 'BUILDING' ? colors.buy + '40'
          : convictionTrend === 'WEAKENING' ? colors.sell + '40' : colors.border,
      }]}>
        <View style={{ flex: 1 }}>
          <Text style={[styles.convLabel, {
            color: convictionTrend === 'BUILDING' ? colors.buy
              : convictionTrend === 'WEAKENING' ? colors.sell : colors.textMuted,
          }]}>
            {convictionTrend === 'BUILDING' ? 'CONVICTION BUILDING ↑'
              : convictionTrend === 'WEAKENING' ? 'CONVICTION WEAKENING ↓'
              : 'CONVICTION STABLE'}
          </Text>
          <Text style={[styles.convNum, { color: colors.textPrimary }]}>{pct(finalConf, 0)}</Text>
          {rawConf != null && finalConf != null && (
            <Text style={[styles.convDelta, { color: colors.textMuted }]}>
              raw {pct(rawConf, 0)} → final {pct(finalConf, 0)}
              {'  ·  Δ '}{pctRaw(finalConf - rawConf, 1)}
            </Text>
          )}
        </View>
        <ConvictionGauge value={finalConf ?? 0} colors={colors} trend={convictionTrend} />
      </View>

      {/* PARALLEL UNIVERSES */}
      {universes && (
        <>
          <SectionTitle text="PARALLEL UNIVERSES" colors={colors} subtext="what would have happened" />
          <View style={styles.uniRow}>
            <UniverseCard label="A · RAW"
              sublabel="without protection"
              pnl={universes.raw?.active_pnl_total} winRate={universes.raw?.win_rate}
              n={universes.raw?.n_active} colors={colors} accent={colors.textMuted} />
            <UniverseCard label="B · META"
              sublabel="meta-brain filtered"
              pnl={universes.meta?.active_pnl_total} winRate={universes.meta?.win_rate}
              n={universes.meta?.n_active} colors={colors} accent={colors.warning ?? '#f5a623'} />
            <UniverseCard label="C · FINAL"
              sublabel="capital deployed"
              pnl={universes.final?.active_pnl_total} winRate={universes.final?.win_rate}
              n={universes.final?.n_active} colors={colors} accent={colors.accent} />
          </View>
          {parallel?.headline && (
            <Text style={[styles.uniNarrative, { color: colors.textMuted }]}>
              {parallel.headline.suppressed_alpha_pct >= 0
                ? `Meta-brain saved ${pctRaw(parallel.headline.suppressed_alpha_pct, 2)} drawdown ·`
                : `Meta-brain cost ${pctRaw(parallel.headline.suppressed_alpha_pct, 2)} alpha ·`}
              {' '}{parallel.headline.directional_trades_killed_to_hold} suppressed → HOLD ·
              {' '}{parallel.headline.directional_trades_flipped} flipped
            </Text>
          )}
        </>
      )}

      {/* HERO + Pipeline already shown above. ITERATION 2 layer: */}
      {/* DECISION PATH visualization */}
      {(() => {
        const path: FlowState[] = isBlocked
          ? ['WATCHING', 'BUILDING', 'READY', 'SUPPRESSED']
          : hasOpen
          ? ['WATCHING', 'BUILDING', 'READY', 'EXECUTED', 'PROTECTED']
          : ['WATCHING', 'BUILDING', 'READY', 'EXECUTED'];
        const idx = isBlocked ? 3
          : hasOpen ? 4
          : (finalConf != null && finalConf >= 0.6 ? 3 : finalConf != null && finalConf >= 0.4 ? 2 : 1);
        return (
          <View style={{ marginTop: 18 }}>
            <SectionTitle text="DECISION PATH" colors={colors}
              subtext={`${asset} lifecycle journey`} />
            <View style={{ backgroundColor: colors.surface, borderColor: colors.border,
              borderWidth: 1, borderRadius: 12, paddingVertical: 6 }}>
              <DecisionPathChain states={path} currentIndex={idx} />
            </View>
          </View>
        );
      })()}

      {/* AI THOUGHT PROCESS (per-asset narrative) */}
      <AIThoughtProcess asset={asset} />

      {/* COGNITIVE TIMELINE (per-trade memory replay) */}
      <CognitiveTimeline scope="EXECUTION" asset={asset} maxEvents={6}
        title={t('trade.howAiArrivedHere')} subtitle="memory replay · causal chain" />

      {/* WHY EXECUTED / WHY BLOCKED */}
      <SectionTitle
        text={isBlocked ? 'WHY BLOCKED' : 'WHY EXECUTED'}
        colors={colors}
        subtext={isBlocked
          ? 'modules suppressing this trade'
          : 'modules aligned on this trade'}
      />
      <View style={styles.modulesGrid}>
        {modules.map((m) => (
          <ModuleRow key={m.key} module={m} colors={colors} isBlocked={isBlocked} />
        ))}
      </View>

      {/* EXECUTION STRUCTURE */}
      <SectionTitle text="EXECUTION STRUCTURE" colors={colors}
        subtext={isBlocked ? 'paper trade · would-be parameters' : 'paper trade · ready to execute'} />
      <View style={[styles.structure, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        <StructRow label="entry"        value={entry != null ? `$${fmtNum(entry, 2)}` : 'awaiting alignment'} colors={colors} />
        <StructRow label="stop"         value={stop != null ? `$${fmtNum(stop, 2)}` : 'derived on entry'} colors={colors} />
        <StructRow label="target"       value={target != null ? `$${fmtNum(target, 2)}` : 'derived on entry'} colors={colors} />
        <StructRow label="invalidation" value={signal?.invalidation || focused?.stages?.final?.invalidation || 'structure break'} colors={colors} />
        <StructRow label="size"         value={`$${sizeUSD.toLocaleString()}  ·  paper`} colors={colors} />
        <StructRow label="risk"         value={riskTier} colors={colors}
          tone={riskTier === 'EXTREME' ? 'sell' : riskTier === 'HIGH' ? 'warn' : 'normal'} />
        <StructRow label="R:R"          value={rr != null ? `${rr.toFixed(2)} : 1` : '—'} colors={colors} />
        <StructRow label="timeframe"    value={horizon} colors={colors} last />
      </View>

      {/* EXECUTE / SUPPRESSED */}
      {!isBlocked && !hasOpen ? (
        <TouchableOpacity
          testID="execute-trade-btn"
          style={[styles.execBtn, { backgroundColor: dCol }]}
          onPress={handleExecute}
          disabled={executing}
          activeOpacity={0.85}
        >
          {executing ? <ActivityIndicator color="#fff" /> : (
            <>
              <Ionicons name="flash" size={18} color="#fff" />
              <Text style={styles.execText}>EXECUTE {finalDir}  ·  PAPER</Text>
            </>
          )}
        </TouchableOpacity>
      ) : hasOpen ? (
        <View style={[styles.execNote, { borderColor: colors.border, backgroundColor: colors.surface }]}>
          <Ionicons name="checkmark-circle" size={16} color={colors.buy} />
          <Text style={[styles.execNoteText, { color: colors.textMuted }]}>
            Position already open · manage in Portfolio
          </Text>
        </View>
      ) : (
        <View style={[styles.execNote, { borderColor: colors.sell + '40', backgroundColor: colors.sell + '08' }]}>
          <Ionicons name="ban" size={16} color={colors.sell} />
          <Text style={[styles.execNoteText, { color: colors.textPrimary }]}>
            Trade suppressed · waiting for asymmetric setup
          </Text>
        </View>
      )}

      {/* AI MEMORY */}
      {memory.length > 0 && (
        <>
          <SectionTitle text="AI MEMORY" colors={colors}
            subtext={`last ${memory.length} decisions · retrospective`} />
          <View style={[styles.memory, { backgroundColor: colors.surface, borderColor: colors.border }]}>
            {memory.map((m: any, i: number) => {
              const dC = dirColor(m.direction, colors);
              const oC = m.outcomeTone === 'good' ? colors.buy
                : m.outcomeTone === 'bad' ? colors.sell : colors.textMuted;
              return (
                <TouchableOpacity
                  key={`${m.symbol}-${i}`}
                  testID={`memory-row-${m.symbol}`}
                  style={[styles.memRow, i === memory.length - 1 && styles.memRowLast, { borderColor: colors.border }]}
                  onPress={() => setTradingTab('TRADE')}
                  activeOpacity={0.75}
                >
                  <View style={{ flex: 1 }}>
                    <View style={styles.memHead}>
                      <Text style={[styles.memSym, { color: colors.textPrimary }]}>{m.symbol}</Text>
                      <View style={[styles.memDir, { borderColor: dC, backgroundColor: dC + '20' }]}>
                        <Text style={[styles.memDirText, { color: dC }]}>{m.direction}</Text>
                      </View>
                      <Text style={[styles.memArrow, { color: colors.textMuted }]}>→</Text>
                      <Text style={[styles.memVerb, { color: colors.textMuted }]}>{m.verb}</Text>
                      <Text style={[styles.memArrow, { color: colors.textMuted }]}>→</Text>
                      <Text style={[styles.memOutcome, { color: oC }]}>{m.outcomeLabel}</Text>
                    </View>
                  </View>
                </TouchableOpacity>
              );
            })}
          </View>
        </>
      )}

      <Text style={[styles.disclaimer, { color: colors.textMuted }]}>
        Read-only execution console · paper-only trading · no live orders ·
        Verdict layer is observability — does not affect production fusion.
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

function ConvictionGauge({ value, colors, trend }: any) {
  const pctVal = Math.max(0, Math.min(1, value || 0));
  const c = trend === 'BUILDING' ? colors.buy : trend === 'WEAKENING' ? colors.sell : colors.accent;
  return (
    <View style={{ width: 56, height: 56, alignItems: 'center', justifyContent: 'center' }}>
      <View style={{
        position: 'absolute', width: 56, height: 56, borderRadius: 28,
        borderWidth: 4, borderColor: colors.border,
      }} />
      <View style={{
        position: 'absolute', width: 56, height: 56, borderRadius: 28,
        borderWidth: 4, borderColor: c, borderRightColor: 'transparent', borderBottomColor: 'transparent',
        transform: [{ rotate: `${-45 + pctVal * 360}deg` }],
        opacity: 0.85,
      }} />
      <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textPrimary }}>
        {Math.round(pctVal * 100)}
      </Text>
    </View>
  );
}

function UniverseCard({ label, sublabel, pnl, winRate, n, colors, accent }: any) {
  const pCol = pnl == null ? colors.textMuted : pnl > 0 ? colors.buy : pnl < 0 ? colors.sell : colors.textMuted;
  return (
    <View style={[uStyles.card, { backgroundColor: colors.surface, borderColor: accent + '40' }]}>
      <Text style={[uStyles.label, { color: accent }]}>{label}</Text>
      <Text style={[uStyles.sub, { color: colors.textMuted }]} numberOfLines={1}>{sublabel}</Text>
      <Text style={[uStyles.pnl, { color: pCol }]}>{pnl == null ? '—' : pctRaw(pnl * 100, 2)}</Text>
      <Text style={[uStyles.meta, { color: colors.textMuted }]}>
        n {n ?? '—'} · win {winRate != null ? `${(winRate * 100).toFixed(0)}%` : '—'}
      </Text>
    </View>
  );
}
const uStyles = StyleSheet.create({
  card: { flex: 1, borderRadius: 12, borderWidth: 1, padding: 10, alignItems: 'center', gap: 2 },
  label: { fontSize: 10, fontWeight: '900', letterSpacing: 0.6 },
  sub: { fontSize: 9, marginTop: 2 },
  pnl: { fontSize: 16, fontWeight: '900', marginTop: 4 },
  meta: { fontSize: 9, marginTop: 2 },
});

type ModuleState = {
  key: 'TA' | 'FRACTAL' | 'EXCHANGE' | 'SENTIMENT' | 'ONCHAIN';
  title: string;
  icon: keyof typeof Ionicons.glyphMap;
  direction: string | null;
  signalText: string;
  contribution: 'enable' | 'block' | 'neutral';
  available: boolean;
};

function buildModuleStates(signal: any, fractal: any, sentiment: any, marketState: any, intel: any): ModuleState[] {
  // TA
  const taDir = signal?.action === 'BUY' ? 'LONG' : signal?.action === 'SELL' ? 'SHORT' : signal?.action === 'WAIT' ? 'NEUTRAL' : null;
  const taConf = signal?.confidence;
  const ta: ModuleState = {
    key: 'TA',
    title: 'Technical Analysis',
    icon: 'analytics-outline',
    direction: taDir,
    signalText: taConf != null
      ? `${(taConf * 100).toFixed(0)}% conf · ${signal?.summary ? signal.summary.slice(0, 50) : 'price action'}`
      : 'no signal',
    contribution: taDir && taDir !== 'NEUTRAL' && taConf != null && taConf >= 0.55 ? 'enable'
      : (taDir === 'NEUTRAL' || (taConf != null && taConf < 0.4)) ? 'block' : 'neutral',
    available: !!signal,
  };

  // FRACTAL
  const frDir = fractal?.direction || fractal?.fractal?.direction || fractal?.bias || null;
  const frConf = fractal?.confidence ?? fractal?.fractal?.confidence ?? null;
  const fr: ModuleState = {
    key: 'FRACTAL',
    title: 'Fractal',
    icon: 'git-network-outline',
    direction: frDir,
    signalText: frDir
      ? `${(frConf || 0) > 0 ? `${((frConf || 0) * 100).toFixed(0)}% · ` : ''}${fractal?.pattern || fractal?.fractal?.pattern || 'wave structure'}`
      : 'unaligned',
    contribution: frDir === 'BULLISH' || frDir === 'LONG' ? 'enable'
      : frDir === 'BEARISH' || frDir === 'SHORT' ? 'enable'
      : 'block',
    available: !!fractal && Object.keys(fractal || {}).length > 0,
  };

  // EXCHANGE
  const xchgFunding = marketState?.market_state?.funding ?? marketState?.funding;
  const xchgOI = marketState?.market_state?.openInterest ?? marketState?.openInterest;
  const xchgDir = marketState?.market_state?.exchangeBias || marketState?.exchangeBias || null;
  const xchgAvail = xchgFunding != null || xchgOI != null || !!xchgDir;
  const xchg: ModuleState = {
    key: 'EXCHANGE',
    title: 'Exchange Flow',
    icon: 'swap-horizontal-outline',
    direction: xchgDir,
    signalText: xchgFunding != null
      ? `funding ${(Number(xchgFunding) * 100).toFixed(3)}%${xchgOI != null ? ` · OI ${Number(xchgOI).toLocaleString()}` : ''}`
      : 'orderbook · liquidations · funding',
    contribution: xchgDir === 'BULLISH' ? 'enable'
      : xchgDir === 'BEARISH' ? 'enable'
      : xchgAvail ? 'neutral' : 'block',
    available: xchgAvail,
  };

  // SENTIMENT
  const senScoreRaw = sentiment?.score ?? sentiment?.sentiment?.score;
  const senScore = senScoreRaw == null ? null
    : Math.abs(senScoreRaw) > 1.5 ? senScoreRaw / 100 : senScoreRaw;
  const senDir = senScore == null ? null : senScore > 0.55 ? 'BULLISH' : senScore < 0.45 ? 'BEARISH' : 'NEUTRAL';
  const sen: ModuleState = {
    key: 'SENTIMENT',
    title: 'Sentiment',
    icon: 'megaphone-outline',
    direction: senDir,
    signalText: senScore != null
      ? `${(senScore * 100).toFixed(0)}% · ${(sentiment?.summary || sentiment?.sentiment?.summary || 'social pressure').slice(0, 50)}`
      : 'unavailable',
    contribution: senDir === 'BULLISH' || senDir === 'BEARISH' ? 'enable'
      : senDir === 'NEUTRAL' ? 'neutral' : 'block',
    available: senScore != null,
  };

  // ONCHAIN
  const ocModule = (intel?.modules || []).find((m: any) =>
    String(m.id || m.key || '').toLowerCase().includes('onchain'));
  const oc: ModuleState = {
    key: 'ONCHAIN',
    title: 'On-chain',
    icon: 'cube-outline',
    direction: ocModule?.direction || null,
    signalText: ocModule?.summary || 'unavailable',
    contribution: ocModule?.direction === 'BULLISH' || ocModule?.direction === 'BEARISH' ? 'enable'
      : ocModule?.direction === 'NEUTRAL' ? 'neutral' : 'block',
    available: !!ocModule,
  };

  return [ta, fr, xchg, sen, oc];
}

function ModuleRow({ module: m, colors, isBlocked }: any) {
  const dC = dirColor(m.direction, colors);
  const tone = m.contribution === 'enable' ? colors.buy
    : m.contribution === 'block' ? colors.sell
    : colors.textMuted;
  // Highlight: if execution is blocked, blockers are loud. If executing, enablers are loud.
  const highlight = (isBlocked && m.contribution === 'block') || (!isBlocked && m.contribution === 'enable');
  return (
    <View style={[mStyles.row, {
      backgroundColor: colors.surface,
      borderColor: highlight ? tone + '60' : colors.border,
      opacity: m.available ? 1 : 0.55,
    }]}>
      <View style={[mStyles.iconWrap, { backgroundColor: dC + '20' }]}>
        <Ionicons name={m.icon} size={16} color={dC} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={[mStyles.title, { color: colors.textPrimary }]}>{m.title}</Text>
        <Text style={[mStyles.detail, { color: colors.textMuted }]} numberOfLines={1}>
          {m.signalText}
        </Text>
      </View>
      <View style={[mStyles.badge, { borderColor: tone, backgroundColor: tone + '14' }]}>
        <Text style={[mStyles.badgeText, { color: tone }]}>
          {m.contribution === 'enable' ? 'ALIGN' : m.contribution === 'block' ? 'BLOCK' : 'NEUTRAL'}
        </Text>
      </View>
    </View>
  );
}
const mStyles = StyleSheet.create({
  row: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingVertical: 10, paddingHorizontal: 12,
    borderRadius: 10, borderWidth: 1, marginBottom: 6,
  },
  iconWrap: { width: 28, height: 28, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 12, fontWeight: '800' },
  detail: { fontSize: 10, marginTop: 2 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderWidth: 1, borderRadius: 999 },
  badgeText: { fontSize: 9, fontWeight: '900', letterSpacing: 0.6 },
});

function StructRow({ label, value, colors, last, tone }: any) {
  const valueColor = tone === 'sell' ? colors.sell : tone === 'warn' ? (colors.warning ?? '#f5a623') : colors.textPrimary;
  return (
    <View style={[
      sStyles.row,
      !last && { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    ]}>
      <Text style={[sStyles.k, { color: colors.textMuted }]}>{label}</Text>
      <Text style={[sStyles.v, { color: valueColor }]} numberOfLines={1}>{value}</Text>
    </View>
  );
}
const sStyles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', paddingVertical: 9, paddingHorizontal: 12 },
  k: { width: 100, fontSize: 10, fontWeight: '800', letterSpacing: 0.6, textTransform: 'uppercase' },
  v: { flex: 1, fontSize: 13, fontWeight: '700', textAlign: 'right' },
});

// ─── memory entry derivation ────────────────────────────────────────
function buildMemoryEntry(v: any) {
  const dir = v.final_action;
  const isBlock = dir === 'HOLD' || dir === 'WAIT' || (v.badges || []).some((b: any) => b.type === 'SUPPRESSED');
  const flipped = (v.badges || []).some((b: any) => b.type === 'FLIPPED');

  // Verb describes the meta-action.
  const verb = isBlock ? 'blocked'
    : flipped ? 'flipped'
    : 'executed';

  // Retrospective outcome (best-effort, derived from chips/badges if present)
  const lossAvoided = (v.badges || []).some((b: any) => b.type === 'LOSS_AVOIDED');
  const gainMissed = (v.badges || []).some((b: any) => b.type === 'GAIN_MISSED');
  const win = (v.badges || []).some((b: any) => b.type === 'WIN');
  const loss = (v.badges || []).some((b: any) => b.type === 'LOSS');

  let outcomeLabel = 'pending';
  let outcomeTone: 'good' | 'bad' | 'neutral' = 'neutral';
  if (lossAvoided) { outcomeLabel = 'avoided loss'; outcomeTone = 'good'; }
  else if (gainMissed) { outcomeLabel = 'missed gain'; outcomeTone = 'bad'; }
  else if (win) { outcomeLabel = 'realized win'; outcomeTone = 'good'; }
  else if (loss) { outcomeLabel = 'realized loss'; outcomeTone = 'bad'; }
  else if (isBlock) { outcomeLabel = 'no exposure'; outcomeTone = 'neutral'; }

  return {
    symbol: v.symbol,
    direction: dir,
    verb,
    outcomeLabel,
    outcomeTone,
  };
}

// ─── styles ─────────────────────────────────────────────────────────
const mk = (c: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: c.background },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: c.background },
  content: { padding: 16, paddingBottom: 60 },

  headerRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    marginBottom: 12,
  },
  headerLabel: { fontSize: 9, fontWeight: '800', letterSpacing: 1.5 },
  headerAsset: { fontSize: 22, fontWeight: '900', marginTop: 2 },
  tfPill: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999, borderWidth: 1 },
  tfText: { fontSize: 11, fontWeight: '700' },

  hero: { borderRadius: 14, borderWidth: 1, padding: 16, marginBottom: 6, alignItems: 'center' },
  heroRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  heroLabel: { fontSize: 10, fontWeight: '800', letterSpacing: 1.4 },
  heroAction: { fontSize: 30, fontWeight: '900', letterSpacing: 1, marginTop: 6 },
  heroSub: { fontSize: 12, marginTop: 6 },
  dotStatic: { width: 10, height: 10, borderRadius: 5 },

  pipe: { borderRadius: 12, borderWidth: 1, padding: 12 },
  pipeStep: { flexDirection: 'row' },
  pipeLeft: { width: 22, alignItems: 'center' },
  pipeDot: { width: 10, height: 10, borderRadius: 5, marginTop: 4 },
  pipeLine: { flex: 1, width: 2, marginTop: 2 },
  pipeRight: { flex: 1, paddingBottom: 10, paddingLeft: 4 },
  pipeHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  pipeStage: { fontSize: 10, fontWeight: '800', letterSpacing: 1 },
  pipeDir: { fontSize: 13 },
  pipeConf: { fontSize: 11, marginTop: 2 },

  conviction: { flexDirection: 'row', alignItems: 'center', gap: 12,
    borderRadius: 12, borderWidth: 1, padding: 14 },
  convLabel: { fontSize: 10, fontWeight: '900', letterSpacing: 1 },
  convNum: { fontSize: 24, fontWeight: '900', marginTop: 4 },
  convDelta: { fontSize: 10, marginTop: 4 },

  uniRow: { flexDirection: 'row', gap: 6 },
  uniNarrative: { fontSize: 11, marginTop: 8, lineHeight: 16 },

  modulesGrid: {},

  structure: { borderRadius: 12, borderWidth: 1, overflow: 'hidden' },

  execBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    paddingVertical: 16, borderRadius: 14, marginTop: 18,
  },
  execText: { color: '#fff', fontSize: 14, fontWeight: '900', letterSpacing: 1 },
  execNote: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingVertical: 14, paddingHorizontal: 14, borderWidth: 1, borderRadius: 12, marginTop: 18,
  },
  execNoteText: { fontSize: 12, fontWeight: '700' },

  memory: { borderRadius: 12, borderWidth: 1, overflow: 'hidden' },
  memRow: {
    paddingVertical: 12, paddingHorizontal: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  memRowLast: { borderBottomWidth: 0 },
  memHead: { flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' },
  memSym: { fontSize: 13, fontWeight: '800' },
  memDir: { paddingHorizontal: 6, paddingVertical: 2, borderWidth: 1, borderRadius: 4 },
  memDirText: { fontSize: 10, fontWeight: '900' },
  memArrow: { fontSize: 11 },
  memVerb: { fontSize: 11, fontWeight: '700' },
  memOutcome: { fontSize: 11, fontWeight: '800' },

  disclaimer: { fontSize: 10, marginTop: 18, lineHeight: 14, paddingHorizontal: 4 },
});
