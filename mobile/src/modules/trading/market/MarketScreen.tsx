/**
 * Trading OS · MARKET INTELLIGENCE TERMINAL
 *
 * AI Market Perception Layer.  NOT a scanner. NOT a screener.
 *
 * Answers: "How does AI perceive the market right now?"
 *
 * Sections (top → bottom):
 *
 *   1. MULTI-LAYER REGIME       Macro / Liquidity / Volatility / Sentiment / Momentum
 *   2. PRESSURE & CHAOS FIELD   AI interpretation of instability
 *   3. OPPORTUNITY FIELD        AI-ranked asymmetry candidates with score 0-100
 *   4. STRUCTURAL STATE MAP     per-asset: compression / continuation / expansion / etc.
 *   5. MARKET FLOW ENGINE       lifecycle states across symbols
 *   6. OPPORTUNITY EVOLUTION    selected symbol journey: WATCHING → BUILDING → ... → EXITED
 *   7. NOISE REJECTION ENGINE   what AI filtered out, with reason
 *   8. AI MARKET MEMORY         what almost happened, what failed
 *
 * Read-only · paper · no live execution · no backend changes.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../../core/useColors';
import { useAppMode } from '../../../stores/app-mode.store';
import { useAssetStore } from '../../../stores/asset.store';
import { mobileApi } from '../../../services/api/mobile-api';
import { mbrainApi } from '../../../services/api/mbrain-api';
import { CognitivePulse } from '../../../widgets/cognition/CognitivePulse';
import { DriftBand } from '../../../widgets/cognition/DriftBand';
import { ScannerLifecycleCard } from '../../../widgets/trading-bridge/ScannerLifecycleCard';
import { deriveDrift, DRIFT_ORDER, driftDescription } from '../../../widgets/cognition/cognitiveLabel';

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
function dirColor(d: string | null | undefined, c: any): string {
  if (d === 'LONG' || d === 'BUY' || d === 'BULLISH') return c.buy;
  if (d === 'SHORT' || d === 'SELL' || d === 'BEARISH') return c.sell;
  return c.textMuted;
}

// ─── flow state derivation ─────────────────────────────────────────
type FlowState = 'WATCHING' | 'BUILDING' | 'READY' | 'EXECUTED' | 'DISCARDED' | 'AVOIDING';

const FLOW_META: Record<FlowState, { color: keyof any; icon: keyof typeof Ionicons.glyphMap; label: string }> = {
  WATCHING:  { color: 'textMuted', icon: 'eye-outline',                 label: 'WATCHING' },
  BUILDING:  { color: 'warning',   icon: 'construct-outline',           label: 'BUILDING' },
  READY:     { color: 'accent',    icon: 'checkmark-circle-outline',    label: 'READY' },
  EXECUTED:  { color: 'buy',       icon: 'flash',                       label: 'EXECUTED' },
  DISCARDED: { color: 'sell',      icon: 'ban-outline',                 label: 'DISCARDED' },
  AVOIDING:  { color: 'sell',      icon: 'shield-checkmark-outline',    label: 'AVOIDING' },
};

type StructuralState =
  | 'COMPRESSION' | 'INSTABILITY' | 'CONTINUATION' | 'EXPANSION'
  | 'EXHAUSTION' | 'ACCUMULATION' | 'DRIFT';

function deriveStructural(verdict: any, regime: string | null): StructuralState {
  const conf = verdict?.confidence_final || 0;
  const rawConf = verdict?.stages?.raw?.confidence || 0;
  const suppressed = (verdict?.badges || []).some((b: any) => b.type === 'SUPPRESSED');
  const flipped = (verdict?.badges || []).some((b: any) => b.type === 'FLIPPED');
  const reg = (regime || '').toLowerCase();

  if (flipped) return 'INSTABILITY';
  if (suppressed && rawConf >= 0.65) return 'EXHAUSTION';
  if (conf >= 0.7) return 'EXPANSION';
  if (conf >= 0.55 && /trend|continuation/i.test(reg)) return 'CONTINUATION';
  if (conf < 0.4 && /chop|range/i.test(reg)) return 'COMPRESSION';
  if (conf < 0.4 && verdict?.final_action === 'HOLD') return 'ACCUMULATION';
  return 'DRIFT';
}

const STRUCTURAL_META: Record<StructuralState, { color: keyof any; verb: string }> = {
  COMPRESSION:  { color: 'textMuted', verb: 'tightening before move' },
  INSTABILITY:  { color: 'sell',      verb: 'directional flip · unstable' },
  CONTINUATION: { color: 'accent',    verb: 'trend persisting' },
  EXPANSION:    { color: 'buy',       verb: 'volatility releasing' },
  EXHAUSTION:   { color: 'warning',   verb: 'momentum spent · reversal risk' },
  ACCUMULATION: { color: 'accent',    verb: 'silent positioning' },
  DRIFT:        { color: 'textMuted', verb: 'no clear edge' },
};

function flowStateFor(args: {
  verdict: any;
  hasPosition: boolean;
  recentlyClosed: boolean;
}): FlowState {
  const { verdict, hasPosition, recentlyClosed } = args;
  if (hasPosition) return 'EXECUTED';
  if (recentlyClosed) return 'DISCARDED';
  if (!verdict) return 'WATCHING';
  const suppressed = (verdict.badges || []).some((b: any) => b.type === 'SUPPRESSED');
  const conf = verdict.confidence_final || 0;
  if (suppressed) return 'AVOIDING';
  if (conf >= 0.6 && (verdict.final_action === 'LONG' || verdict.final_action === 'SHORT')) return 'READY';
  if (conf >= 0.4) return 'BUILDING';
  return 'WATCHING';
}

// ─── asymmetry score (0-100) ───────────────────────────────────────
function computeAsymmetry(verdict: any): number {
  if (!verdict) return 0;
  const conf = verdict.confidence_final || 0;
  const rawConf = verdict.stages?.raw?.confidence || 0;
  // Bonus: if META kept the trade alive at high conviction AND raw was strong → high asymmetry
  // Penalty: if META suppressed → score reflects uplift potential, not deployment readiness
  const suppressed = (verdict.badges || []).some((b: any) => b.type === 'SUPPRESSED');
  const flipped = (verdict.badges || []).some((b: any) => b.type === 'FLIPPED');
  const directional = verdict.final_action === 'LONG' || verdict.final_action === 'SHORT';
  let s = conf * 80 + rawConf * 15;
  if (directional) s += 8;
  if (suppressed) s -= 22;
  if (flipped) s -= 10;
  // High alignment between raw and final → cleaner asymmetry
  if (Math.abs(conf - rawConf) < 0.08 && conf >= 0.5) s += 5;
  return Math.max(0, Math.min(100, Math.round(s)));
}

// ─── helpers ────────────────────────────────────────────────────────
function symbolOf(v: any): string {
  return String(v?.symbol || '').replace('USDT', '');
}

// ─── multi-layer regime ────────────────────────────────────────────
function deriveMultiRegime(args: {
  marketState: any;
  realizedH: any;
  sentiment: any;
  verdicts: any[];
  parallelHeadline: any;
}): { layer: string; state: string; tone: 'good' | 'bad' | 'neutral' | 'warn' }[] {
  const { marketState, realizedH, sentiment, verdicts, parallelHeadline } = args;
  const ms = marketState?.market_state || marketState || {};
  const regime = ms.regime || ms.state || marketState?.regime || null;

  // Macro
  const macroState = realizedH?.verdict === 'META_NET_POSITIVE' ? 'DEFENSIVE'
    : realizedH?.verdict === 'META_NET_NEGATIVE' ? 'AGGRESSIVE'
    : 'NEUTRAL';
  const macroTone: any = macroState === 'DEFENSIVE' ? 'good' : macroState === 'AGGRESSIVE' ? 'warn' : 'neutral';

  // Liquidity
  const liqRaw = ms.liquidity ?? marketState?.liquidity ?? null;
  const liqState = liqRaw === 'thin' || liqRaw === 'low' ? 'THIN'
    : liqRaw === 'high' || liqRaw === 'deep' ? 'DEEP'
    : 'NORMAL';
  const liqTone: any = liqState === 'THIN' ? 'bad' : liqState === 'DEEP' ? 'good' : 'neutral';

  // Volatility
  const vol = ms.volatility ?? ms.atr ?? marketState?.volatility ?? null;
  const volState = vol == null ? (regime && /chop|range/i.test(regime) ? 'COMPRESSED' : 'NORMAL')
    : Number(vol) > 0.05 ? 'EXPANDING'
    : Number(vol) < 0.015 ? 'COMPRESSED'
    : 'NORMAL';
  const volTone: any = volState === 'EXPANDING' ? 'warn' : volState === 'COMPRESSED' ? 'neutral' : 'neutral';

  // Sentiment
  const senScoreRaw = sentiment?.score ?? sentiment?.sentiment?.score;
  const senScore = senScoreRaw == null ? null
    : Math.abs(senScoreRaw) > 1.5 ? senScoreRaw / 100 : senScoreRaw;
  const senState = senScore == null ? 'UNKNOWN'
    : senScore > 0.65 ? 'EUPHORIC'
    : senScore > 0.55 ? 'BULLISH'
    : senScore < 0.35 ? 'FEARFUL'
    : senScore < 0.45 ? 'BEARISH'
    : 'NEUTRAL';
  const senTone: any = senState === 'EUPHORIC' ? 'warn'
    : senState === 'FEARFUL' ? 'good'
    : senState === 'BULLISH' ? 'good'
    : senState === 'BEARISH' ? 'bad' : 'neutral';

  // Momentum (from verdict average direction strength)
  const directional = (verdicts || []).filter((v: any) =>
    v.final_action === 'LONG' || v.final_action === 'SHORT');
  const avgConf = directional.length
    ? directional.reduce((s: number, v: any) => s + (v.confidence_final || 0), 0) / directional.length
    : 0;
  const momState = avgConf >= 0.65 ? 'STRONG'
    : avgConf >= 0.45 ? 'BUILDING'
    : avgConf > 0 ? 'WEAK'
    : 'ABSENT';
  const momTone: any = momState === 'STRONG' ? 'good' : momState === 'BUILDING' ? 'warn' : 'bad';

  return [
    { layer: 'Macro',      state: macroState, tone: macroTone },
    { layer: 'Liquidity',  state: liqState,   tone: liqTone },
    { layer: 'Volatility', state: volState,   tone: volTone },
    { layer: 'Sentiment',  state: senState,   tone: senTone },
    { layer: 'Momentum',   state: momState,   tone: momTone },
  ];
}

function regimeExpectation(layers: { layer: string; state: string; tone: string }[]): string {
  const macro = layers.find((l) => l.layer === 'Macro')?.state;
  const vol = layers.find((l) => l.layer === 'Volatility')?.state;
  const mom = layers.find((l) => l.layer === 'Momentum')?.state;
  const sen = layers.find((l) => l.layer === 'Sentiment')?.state;

  if (vol === 'COMPRESSED' && mom === 'WEAK') return 'AI expects delayed expansion';
  if (vol === 'EXPANDING' && mom === 'STRONG') return 'AI expects continuation phase';
  if (sen === 'EUPHORIC' && mom !== 'STRONG') return 'AI expects mean reversion';
  if (macro === 'DEFENSIVE' && mom === 'WEAK') return 'AI expects extended consolidation';
  if (mom === 'BUILDING') return 'AI expects breakout window';
  return 'AI expects ambiguous price action';
}

// ─── pressure & chaos ──────────────────────────────────────────────
function describePressure(verdicts: any[], parallelH: any, marketState: any): string[] {
  const out: string[] = [];
  const suppressed = parallelH?.directional_trades_killed_to_hold || 0;
  const flipped = parallelH?.directional_trades_flipped || 0;
  if (suppressed >= 5) out.push(`${suppressed} setups suppressed · liquidation pressure aggregating`);
  if (flipped >= 3) out.push(`${flipped} polarity flips · directional uncertainty`);

  const overheated = verdicts.filter((v: any) =>
    (v.badges || []).some((b: any) => b.type === 'SUPPRESSED') && v.raw_action === 'LONG');
  if (overheated.length >= 2) out.push(`overheated longs across ${overheated.slice(0, 3).map(symbolOf).join(', ')}`);

  const ms = marketState?.market_state || marketState || {};
  if (ms.volatility != null && Number(ms.volatility) < 0.012) {
    out.push('suppressed volatility · expansion building');
  }

  const weakConts = verdicts.filter((v: any) => (v.confidence_final || 0) < 0.3 && v.final_action === 'HOLD').slice(0, 3);
  if (weakConts.length >= 2) out.push(`weak continuation on ${weakConts.map(symbolOf).join(', ')}`);

  if (out.length === 0) out.push('regime quiet · no chaos signature detected');
  return out.slice(0, 5);
}

// ─── pulse observations · ambient cognition stream ─────────────────
function buildPulseObservations(args: {
  pressure: string[];
  expectation: string;
  layers: { layer: string; state: string; tone: string }[];
  opportunities: { sym: string; verdict: any; score: number; flow: any }[];
  parallelH: any;
}): string[] {
  const { pressure, expectation, layers, opportunities, parallelH } = args;
  const out: string[] = [];

  // expectation always first — primary perception
  if (expectation) out.push(expectation);

  // top opportunity asymmetry as ambient signal
  const top = opportunities[0];
  if (top && top.score >= 55) {
    out.push(`${top.sym} carrying ${top.score} asymmetry · structure forming`);
  } else if (top && top.score < 30) {
    out.push(`field offers no clean asymmetry · highest is ${top.sym} at ${top.score}`);
  }

  // suppression as moral observation
  if (parallelH?.directional_trades_killed_to_hold >= 3) {
    out.push(
      `${parallelH.directional_trades_killed_to_hold} directional setups suppressed · capital preservation active`,
    );
  }

  // layer-driven perception
  const vol = layers.find((l) => l.layer === 'Volatility')?.state;
  const mom = layers.find((l) => l.layer === 'Momentum')?.state;
  const sen = layers.find((l) => l.layer === 'Sentiment')?.state;
  const liq = layers.find((l) => l.layer === 'Liquidity')?.state;
  if (vol === 'COMPRESSED') out.push('AI detecting volatility compression · expansion energy storing');
  if (vol === 'EXPANDING')  out.push('momentum expansion releasing across the field');
  if (sen === 'EUPHORIC')   out.push('sentiment euphoric · AI questioning crowd alignment');
  if (sen === 'FEARFUL')    out.push('sentiment fearful · AI scanning for hidden positioning');
  if (mom === 'BUILDING')   out.push('directional momentum slowly building · breakout window forming');
  if (liq === 'THIN')       out.push('liquidity becoming thinner · slippage risk rising');

  // pressure lines as cognitive observations
  pressure.forEach((p) => {
    if (!/regime quiet/i.test(p)) out.push(`field reading: ${p}`);
  });

  // de-dupe, cap at 8 to keep cycle calm
  return Array.from(new Set(out)).slice(0, 8);
}


function buildOpportunityField(verdicts: any[], openSyms: Set<string>, recentClosedSyms: Set<string>) {
  // One row per symbol, take best-asymmetry verdict.
  const bySym = new Map<string, any>();
  verdicts.forEach((v) => {
    const sym = symbolOf(v);
    const cur = bySym.get(sym);
    const score = computeAsymmetry(v);
    const cs = cur ? computeAsymmetry(cur) : -1;
    if (score > cs) bySym.set(sym, v);
  });
  const list = Array.from(bySym.entries()).map(([sym, v]) => {
    const score = computeAsymmetry(v);
    const flow = flowStateFor({
      verdict: v,
      hasPosition: openSyms.has(sym),
      recentlyClosed: recentClosedSyms.has(sym),
    });
    return { sym, verdict: v, score, flow };
  });
  return list.sort((a, b) => b.score - a.score);
}

// ─── opportunity evolution timeline ─────────────────────────────────
function buildEvolution(args: {
  sym: string;
  verdicts: any[];
  hasPosition: boolean;
  recentlyClosed: boolean;
}): { state: FlowState; reached: boolean }[] {
  const { sym, verdicts, hasPosition, recentlyClosed } = args;
  const v = verdicts.find((x) => symbolOf(x) === sym);
  const cur = flowStateFor({ verdict: v, hasPosition, recentlyClosed });
  const order: FlowState[] = ['WATCHING', 'BUILDING', 'READY', 'EXECUTED', 'DISCARDED'];
  const idx = order.indexOf(cur);
  return order.map((s, i) => ({
    state: s,
    reached: i <= idx || (cur === 'AVOIDING' && s === 'WATCHING'),
  }));
}

// ─── noise rejection ────────────────────────────────────────────────
function buildNoise(verdicts: any[]) {
  // Symbols with low conf, suppressed, or weak continuation.
  const out: { sym: string; reason: string }[] = [];
  const seen = new Set<string>();
  verdicts.forEach((v) => {
    const sym = symbolOf(v);
    if (seen.has(sym)) return;
    const conf = v.confidence_final || 0;
    const suppressed = (v.badges || []).some((b: any) => b.type === 'SUPPRESSED');
    const isHold = v.final_action === 'HOLD' || v.final_action === 'WAIT';
    if (suppressed && conf < 0.5) {
      out.push({ sym, reason: 'meta suppressed · weak asymmetry' });
      seen.add(sym);
    } else if (conf < 0.25 && isHold) {
      out.push({ sym, reason: 'unstable continuation' });
      seen.add(sym);
    } else if ((v.badges || []).some((b: any) => /sentiment|hype|social/i.test(b.label || ''))) {
      out.push({ sym, reason: 'social-only hype' });
      seen.add(sym);
    }
  });
  return out.slice(0, 5);
}

// ─── market memory ──────────────────────────────────────────────────
function buildMarketMemory(realized: any, parallelH: any): { tone: 'good' | 'bad' | 'neutral'; line: string }[] {
  const out: { tone: 'good' | 'bad' | 'neutral'; line: string }[] = [];
  if (realized?.top_avoided?.length) {
    realized.top_avoided.slice(0, 2).forEach((s: any) => {
      out.push({
        tone: 'good',
        line: `${s.symbol} almost expanded but failed · meta saved ${pctRaw(Math.abs((s.realized_return || 0) * 100), 1)}`,
      });
    });
  }
  if (realized?.top_missed?.length) {
    realized.top_missed.slice(0, 2).forEach((s: any) => {
      out.push({
        tone: 'bad',
        line: `${s.symbol} expansion captured by RAW · meta missed ${pctRaw((s.realized_return || 0) * 100, 1)}`,
      });
    });
  }
  if (parallelH?.directional_trades_killed_to_hold > 5) {
    out.push({
      tone: 'neutral',
      line: `${parallelH.directional_trades_killed_to_hold} setups built then collapsed · awaiting cleaner asymmetry`,
    });
  }
  if (out.length === 0) {
    out.push({ tone: 'neutral', line: 'no significant market memory yet · system observing' });
  }
  return out;
}

// ─── main screen ────────────────────────────────────────────────────
export function MarketScreen() {
  const colors = useColors();
  const setTradingTab = useAppMode((s) => s.setTradingTab);
  const setAsset = useAssetStore((s) => s.setCurrentAsset);
  const styles = useMemo(() => mk(colors), [colors]);

  const [verdicts, setVerdicts] = useState<any[]>([]);
  const [marketState, setMarketState] = useState<any>(null);
  const [sentiment, setSentiment] = useState<any>(null);
  const [parallel, setParallel] = useState<any>(null);
  const [realized, setRealized] = useState<any>(null);
  const [openPositions, setOpenPositions] = useState<any[]>([]);
  const [closedPositions, setClosedPositions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedSym, setSelectedSym] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    const r = await Promise.allSettled([
      mbrainApi.listVerdicts(50),
      mobileApi.getMarketState(),
      mobileApi.getSentiment('BTC'),
      mbrainApi.parallelPortfolios(200, true),
      mbrainApi.realizedAttribution(2000),
      mobileApi.getPositions('OPEN'),
      mobileApi.getPositions('CLOSED'),
    ]);
    const get = (i: number) => (r[i].status === 'fulfilled' ? (r[i] as any).value : null);
    setVerdicts(get(0)?.cards || []);
    setMarketState(get(1));
    setSentiment(get(2));
    setParallel(get(3));
    setRealized(get(4));
    setOpenPositions(get(5)?.positions || []);
    setClosedPositions(get(6)?.positions || []);
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  if (loading) {
    return <View style={styles.center}><ActivityIndicator color={colors.accent} /></View>;
  }

  const realizedH = realized?.headline;
  const parallelH = parallel?.headline;

  const layers = deriveMultiRegime({ marketState, realizedH, sentiment, verdicts, parallelHeadline: parallelH });
  const expectation = regimeExpectation(layers);
  const pressure = describePressure(verdicts, parallelH, marketState);

  const openSyms = new Set(openPositions.map((p: any) => String(p.asset || '').toUpperCase()));
  const recentClosedSyms = new Set(
    closedPositions
      .filter((c: any) => {
        const t = c.closedAt || c.closed_at;
        if (!t) return false;
        const ms = typeof t === 'number' ? t : new Date(t).getTime();
        return Date.now() - ms < 7 * 24 * 3600 * 1000;
      })
      .map((c: any) => String(c.asset || '').toUpperCase()),
  );

  const opportunities = buildOpportunityField(verdicts, openSyms, recentClosedSyms);
  const noise = buildNoise(verdicts);
  const memory = buildMarketMemory(realized, parallelH);
  const pulseObservations = buildPulseObservations({
    pressure, expectation, layers, opportunities, parallelH,
  });
  const drift = deriveDrift({ pressureLines: pressure, layers });

  // Flow state distribution
  const flowGroups: Record<FlowState, number> = {
    WATCHING: 0, BUILDING: 0, READY: 0, EXECUTED: 0, DISCARDED: 0, AVOIDING: 0,
  };
  opportunities.forEach((o) => { flowGroups[o.flow] = (flowGroups[o.flow] || 0) + 1; });

  // Selected symbol for evolution timeline
  const focusSym = selectedSym
    || opportunities[0]?.sym
    || 'BTC';
  const evolution = buildEvolution({
    sym: focusSym,
    verdicts,
    hasPosition: openSyms.has(focusSym),
    recentlyClosed: recentClosedSyms.has(focusSym),
  });

  return (
    <ScrollView
      testID="market-screen"
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing}
        onRefresh={() => { setRefreshing(true); fetchAll(); }}
        tintColor={colors.accent} />}
    >
      {/* HEADER */}
      <View style={styles.headerRow}>
        <View>
          <Text style={[styles.headerLabel, { color: colors.textMuted }]}>{t('trade.marketPerception')}</Text>
          <Text style={[styles.headerTitle, { color: colors.textPrimary }]}>{t('trade.opportunityField')}</Text>
        </View>
        <View style={[styles.expectPill, { backgroundColor: colors.surface, borderColor: colors.accent + '50' }]}>
          <Text style={[styles.expectLabel, { color: colors.textMuted }]}>EXPECTING</Text>
          <Text style={[styles.expectText, { color: colors.accent }]} numberOfLines={2}>
            {expectation.replace('AI expects ', '')}
          </Text>
        </View>
      </View>

      {/* AMBIENT COGNITION STRIP — PHASE X · ITERATION 3A · M-01 */}
      <CognitivePulse
        observations={pulseObservations}
        colors={colors}
        headLabel="AI · SENSING"
      />

      {/* 1. MULTI-LAYER REGIME */}
      <SectionTitle text="MULTI-LAYER REGIME" subtext="five layers · one perception" colors={colors} />
      <View style={[styles.layersCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        {layers.map((l, i) => {
          const tone = l.tone === 'good' ? colors.buy
            : l.tone === 'bad' ? colors.sell
            : l.tone === 'warn' ? (colors.warning ?? '#f5a623')
            : colors.textMuted;
          return (
            <View key={l.layer}
              style={[styles.layerRow, i < layers.length - 1 && {
                borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border,
              }]}>
              <Text style={[styles.layerLabel, { color: colors.textMuted }]}>{l.layer}</Text>
              <View style={styles.layerStateBox}>
                <View style={[styles.layerDot, { backgroundColor: tone }]} />
                <Text style={[styles.layerState, { color: colors.textPrimary }]}>{l.state}</Text>
              </View>
            </View>
          );
        })}
      </View>

      {/* 2. PRESSURE & CHAOS FIELD — PHASE X · ITERATION 3A · M-04 */}
      <SectionTitle text="PRESSURE & CHAOS FIELD" subtext="instability interpretation" colors={colors} />
      <DriftBand
        states={DRIFT_ORDER}
        current={drift}
        toneKeyMap={{
          quiet: 'textMuted',
          compressing: 'accent',
          unstable: 'sell',
          expanding: 'warning',
        }}
        colors={colors}
        headLabel="FIELD DRIFT"
        description={driftDescription(drift)}
      />

      {/* MARKET FLOW ENGINE — distribution */}
      <SectionTitle text="MARKET FLOW ENGINE" subtext="opportunity lifecycle distribution" colors={colors} />
      <View style={styles.flowRow}>
        {(['WATCHING', 'BUILDING', 'READY', 'EXECUTED', 'AVOIDING'] as FlowState[]).map((s) => {
          const meta = FLOW_META[s];
          const c = (colors as any)[meta.color] || colors.textMuted;
          const count = flowGroups[s] || 0;
          return (
            <View key={s} style={[styles.flowCell, { backgroundColor: colors.surface, borderColor: colors.border }]}>
              <Ionicons name={meta.icon} size={14} color={c} />
              <Text style={[styles.flowCount, { color: colors.textPrimary }]}>{count}</Text>
              <Text style={[styles.flowLabel, { color: c }]}>{meta.label}</Text>
            </View>
          );
        })}
      </View>

      {/* 3+4. OPPORTUNITY FIELD with structural state */}
      <SectionTitle text="OPPORTUNITY FIELD"
        subtext={`${opportunities.length} candidates · ranked by asymmetry`} colors={colors} />
      {opportunities.length === 0 ? (
        <View style={[styles.empty, { borderColor: colors.border }]}>
          <Ionicons name="search-outline" size={28} color={colors.textMuted} />
          <Text style={[styles.emptyText, { color: colors.textMuted }]}>
            no verdict-store candidates · awaiting next sweep
          </Text>
        </View>
      ) : (
        opportunities.slice(0, 8).map((opp) => {
          const struct = deriveStructural(opp.verdict, marketState?.market_state?.regime);
          const sMeta = STRUCTURAL_META[struct];
          const isFocus = opp.sym === focusSym;
          return (
            <ScannerLifecycleCard
              key={opp.sym}
              sym={opp.sym}
              verdict={opp.verdict}
              flow={opp.flow}
              asymmetry={opp.score}
              structuralVerb={`${opp.verdict.horizon || '—'}  ·  ${sMeta.verb}`}
              isFocus={isFocus}
              onPress={() => {
                setSelectedSym(opp.sym);
                if (typeof setAsset === 'function') setAsset(opp.sym);
              }}
              colors={colors}
            />
          );
        })
      )}

      {/* 6. OPPORTUNITY EVOLUTION TIMELINE */}
      <SectionTitle text="OPPORTUNITY EVOLUTION"
        subtext={`${focusSym} · lifecycle journey`} colors={colors} />
      <View style={[styles.evoCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        <View style={styles.evoTrack}>
          {evolution.map((step, i) => {
            const m = FLOW_META[step.state];
            const c = step.reached ? ((colors as any)[m.color] || colors.accent) : colors.border;
            return (
              <View key={step.state} style={styles.evoStep}>
                <View style={[styles.evoDot, { backgroundColor: c, opacity: step.reached ? 1 : 0.4 }]} />
                {i < evolution.length - 1 && (
                  <View style={[styles.evoLine, {
                    backgroundColor: evolution[i + 1].reached ? c : colors.border,
                    opacity: evolution[i + 1].reached ? 1 : 0.4,
                  }]} />
                )}
              </View>
            );
          })}
        </View>
        <View style={styles.evoLabels}>
          {evolution.map((step) => {
            const m = FLOW_META[step.state];
            const c = step.reached ? ((colors as any)[m.color] || colors.accent) : colors.textMuted;
            return (
              <Text key={step.state}
                style={[styles.evoLabel, { color: c, opacity: step.reached ? 1 : 0.55 }]}>
                {step.state.slice(0, 4)}
              </Text>
            );
          })}
        </View>
        <View style={styles.evoActions}>
          <TouchableOpacity
            style={[styles.evoBtn, { borderColor: colors.border }]}
            onPress={() => setTradingTab('EXECUTION')}
          >
            <Ionicons name="flash" size={12} color={colors.accent} />
            <Text style={[styles.evoBtnText, { color: colors.accent }]}>open in Execution</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* 7. NOISE REJECTION ENGINE */}
      <SectionTitle text="NOISE REJECTION ENGINE"
        subtext="filtered out · why" colors={colors} />
      {noise.length === 0 ? (
        <View style={[styles.empty, { borderColor: colors.border }]}>
          <Text style={[styles.emptyText, { color: colors.textMuted }]}>
            no noise to filter · pool is clean
          </Text>
        </View>
      ) : (
        <View style={[styles.noiseCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          {noise.map((n, i) => (
            <View key={n.sym}
              style={[styles.noiseRow, i < noise.length - 1 && {
                borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border,
              }]}>
              <Ionicons name="ban" size={14} color={colors.sell} />
              <Text style={[styles.noiseSym, { color: colors.textPrimary }]}>{n.sym}</Text>
              <Text style={[styles.noiseReason, { color: colors.textMuted }]}>{n.reason}</Text>
            </View>
          ))}
        </View>
      )}

      {/* 8. AI MARKET MEMORY */}
      <SectionTitle text="AI MARKET MEMORY"
        subtext="what almost happened · what was rejected" colors={colors} />
      <View style={[styles.memCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        {memory.map((m, i) => {
          const c = m.tone === 'good' ? colors.buy
            : m.tone === 'bad' ? colors.sell
            : colors.textMuted;
          return (
            <View key={i}
              style={[styles.memRow, i < memory.length - 1 && {
                borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border,
              }]}>
              <View style={[styles.memDot, { backgroundColor: c }]} />
              <Text style={[styles.memText, { color: colors.textPrimary }]}>{m.line}</Text>
            </View>
          );
        })}
      </View>

      <Text style={[styles.disclaimer, { color: colors.textMuted }]}>
        Read-only AI market terminal · no orderbook · no orderflow stream ·
        all narratives are derived from the meta-brain side-car. Asymmetry
        score is observability, not a signal.
      </Text>
      <View style={{ height: 28 }} />
    </ScrollView>
  );
}

// ─── shared sub-components ─────────────────────────────────────────
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

// ─── styles ─────────────────────────────────────────────────────────
const mk = (c: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: c.background },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: c.background },
  content: { padding: 16, paddingBottom: 60 },

  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  headerLabel: { fontSize: 9, fontWeight: '800', letterSpacing: 1.5 },
  headerTitle: { fontSize: 20, fontWeight: '900', marginTop: 2 },

  expectPill: {
    flex: 1, paddingHorizontal: 12, paddingVertical: 8,
    borderRadius: 12, borderWidth: 1, alignItems: 'flex-start',
  },
  expectLabel: { fontSize: 8, fontWeight: '900', letterSpacing: 1 },
  expectText: { fontSize: 11, fontWeight: '700', marginTop: 2 },

  layersCard: { borderRadius: 12, borderWidth: 1, overflow: 'hidden' },
  layerRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingVertical: 11, paddingHorizontal: 14,
  },
  layerLabel: { fontSize: 12, fontWeight: '700' },
  layerStateBox: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  layerDot: { width: 8, height: 8, borderRadius: 4 },
  layerState: { fontSize: 12, fontWeight: '800', letterSpacing: 0.4 },

  pressureCard: { borderRadius: 12, borderWidth: 1, padding: 14, gap: 8 },
  pressureRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  pressureDot: { width: 6, height: 6, borderRadius: 3 },
  pressureText: { flex: 1, fontSize: 12, lineHeight: 17 },

  flowRow: { flexDirection: 'row', gap: 6 },
  flowCell: {
    flex: 1, alignItems: 'center', gap: 2,
    paddingVertical: 10, borderRadius: 10, borderWidth: 1,
  },
  flowCount: { fontSize: 16, fontWeight: '900' },
  flowLabel: { fontSize: 8, fontWeight: '900', letterSpacing: 0.5 },

  empty: {
    alignItems: 'center', gap: 8,
    padding: 20, borderRadius: 12, borderWidth: 1, borderStyle: 'dashed',
  },
  emptyText: { fontSize: 12 },

  oppCard: { borderRadius: 12, borderWidth: 1, padding: 12, marginBottom: 6 },
  oppHead: { flexDirection: 'row', alignItems: 'center' },
  oppSym: { fontSize: 16, fontWeight: '900' },
  oppHorizon: { fontSize: 11, marginTop: 2 },
  oppRight: { alignItems: 'flex-end' },
  oppScore: { fontSize: 24, fontWeight: '900', letterSpacing: 0.5 },
  oppScoreLabel: { fontSize: 9, fontWeight: '700', letterSpacing: 0.5 },
  oppRow2: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8, flexWrap: 'wrap' },
  oppFlow: { flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 7, paddingVertical: 3, borderRadius: 999, borderWidth: 1 },
  oppFlowText: { fontSize: 9, fontWeight: '900', letterSpacing: 0.5 },
  oppStruct: { paddingHorizontal: 7, paddingVertical: 3, borderRadius: 999, borderWidth: 1 },
  oppStructText: { fontSize: 9, fontWeight: '900', letterSpacing: 0.5 },
  oppDir: { paddingHorizontal: 7, paddingVertical: 3, borderRadius: 6, borderWidth: 1 },
  oppDirText: { fontSize: 10, fontWeight: '900' },
  oppConf: { fontSize: 10, marginLeft: 'auto' },

  evoCard: { borderRadius: 12, borderWidth: 1, padding: 14 },
  evoTrack: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12 },
  evoStep: { flexDirection: 'row', alignItems: 'center', flex: 1 },
  evoDot: { width: 10, height: 10, borderRadius: 5 },
  evoLine: { flex: 1, height: 2 },
  evoLabels: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 8, paddingHorizontal: 4 },
  evoLabel: { fontSize: 9, fontWeight: '900', letterSpacing: 0.5 },
  evoActions: { flexDirection: 'row', justifyContent: 'flex-end', marginTop: 12 },
  evoBtn: { flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999, borderWidth: 1 },
  evoBtnText: { fontSize: 11, fontWeight: '800' },

  noiseCard: { borderRadius: 12, borderWidth: 1, overflow: 'hidden' },
  noiseRow: { flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingVertical: 11, paddingHorizontal: 14 },
  noiseSym: { fontSize: 13, fontWeight: '800', width: 56 },
  noiseReason: { flex: 1, fontSize: 11, fontStyle: 'italic' },

  memCard: { borderRadius: 12, borderWidth: 1, overflow: 'hidden' },
  memRow: { flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingVertical: 12, paddingHorizontal: 14 },
  memDot: { width: 6, height: 6, borderRadius: 3 },
  memText: { flex: 1, fontSize: 12, lineHeight: 17 },

  disclaimer: { fontSize: 10, marginTop: 18, lineHeight: 14, paddingHorizontal: 4 },
});
