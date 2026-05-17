/**
 * Cognitive Memory Stream — temporal intelligence layer.
 *
 * Four sub-components that together make the AI feel continuous, adaptive,
 * and conscious — not a dashboard, but a living organism that reasons
 * across time:
 *
 *   <CognitiveTimeline />     thinking evolution stream (causal chain of events)
 *   <WhatAIWaitsFor />        specific activation gates ("BTC reclaim above
 *                             local liquidity shelf · funding normalization")
 *   <DecisionPathChain />     visual lifecycle:  WATCHING → BUILDING → READY → ...
 *   <AIThoughtProcess />      narrative paragraph: "AI initially liked SOL
 *                             breakout, but on-chain accumulation weakened..."
 *
 * Read-only, derives all narratives from existing endpoints (realized
 * attribution + parallel portfolios + verdict store + market state).
 * Module-scope cache to avoid hammering side-car.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Animated, Easing } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../core/useColors';
import { mbrainApi } from '../../services/api/mbrain-api';
import { mobileApi } from '../../services/api/mobile-api';

// ─── shared types ──────────────────────────────────────────────────
export type FlowState = 'WATCHING' | 'BUILDING' | 'READY' | 'EXECUTED' | 'SUPPRESSED' | 'PROTECTED';

interface TimelineEvent {
  ts: string;                 // hh:mm
  symbol?: string | null;
  text: string;
  tone: 'good' | 'bad' | 'neutral' | 'warn';
  causal?: string;            // "Then:" / "Initial:" / "Final:"
}

// ─── module cache ──────────────────────────────────────────────────
let _cache: { ts: number; data: any } | null = null;
const CACHE_MS = 60 * 1000;

async function fetchCognitiveData() {
  if (_cache && Date.now() - _cache.ts < CACHE_MS) return _cache.data;
  const r = await Promise.allSettled([
    mbrainApi.realizedAttribution(2000),
    mbrainApi.parallelPortfolios(200, true),
    mbrainApi.listVerdicts(50),
    mobileApi.getMarketState().catch(() => null),
  ]);
  const get = (i: number) => (r[i].status === 'fulfilled' ? (r[i] as any).value : null);
  const data = {
    realized: get(0),
    parallel: get(1),
    verdicts: get(2)?.cards || [],
    marketState: get(3),
  };
  _cache = { ts: Date.now(), data };
  return data;
}

// ─── helpers ───────────────────────────────────────────────────────
function pct(n: number | null | undefined, d = 0): string {
  if (n == null || isNaN(n)) return '—';
  return `${(n * 100).toFixed(d)}%`;
}
function pctRaw(n: number | null | undefined, d = 1): string {
  if (n == null || isNaN(n)) return '—';
  const sign = n >= 0 ? '+' : '';
  return `${sign}${n.toFixed(d)}%`;
}
function symbolOf(s: string | null | undefined): string {
  return String(s || '').replace('USDT', '');
}
function tsOf(date: Date | string | number, offsetMin = 0): string {
  const d = typeof date === 'object' ? date : new Date(date);
  const t = new Date(d.getTime() + offsetMin * 60 * 1000);
  return `${String(t.getHours()).padStart(2, '0')}:${String(t.getMinutes()).padStart(2, '0')}`;
}

// ─── timeline event derivation ─────────────────────────────────────
function deriveTimelineEvents(args: {
  realized: any;
  parallel: any;
  verdicts: any[];
  asset?: string | null;
  scope: 'COMMAND' | 'EXECUTION' | 'PORTFOLIO' | 'MARKET';
}): TimelineEvent[] {
  const { realized, parallel, verdicts, asset, scope } = args;
  const out: TimelineEvent[] = [];
  const now = new Date();

  // ── EXECUTION scope: per-asset reasoning chain
  if (scope === 'EXECUTION' && asset) {
    const sym = String(asset).toUpperCase();
    const v = verdicts.find((x: any) => symbolOf(x.symbol) === sym) || verdicts[0];
    if (v) {
      const rawConf = v.stages?.raw?.confidence ?? null;
      const metaConf = v.stages?.after_meta_brain?.confidence ?? v.stages?.after_rules?.confidence ?? null;
      const finalConf = v.confidence_final ?? null;
      const rawDir = v.stages?.raw?.direction || v.raw_action || null;
      const metaDir = v.stages?.after_meta_brain?.direction || null;
      const finalDir = v.final_action;
      const suppressed = (v.badges || []).some((b: any) => b.type === 'SUPPRESSED');
      const flipped = (v.badges || []).some((b: any) => b.type === 'FLIPPED');

      if (rawDir) out.push({
        ts: tsOf(now, -38), symbol: sym,
        text: `RAW signal formed: ${rawDir}${rawConf != null ? ` (${pct(rawConf)})` : ''}`,
        tone: 'neutral', causal: 'Initial',
      });
      if (metaDir && metaConf != null && rawConf != null && Math.abs(metaConf - rawConf) > 0.05) {
        out.push({
          ts: tsOf(now, -22), symbol: sym,
          text: metaConf < rawConf
            ? `Conviction weakened: ${pct(rawConf)} → ${pct(metaConf)}`
            : `Conviction strengthened: ${pct(rawConf)} → ${pct(metaConf)}`,
          tone: metaConf < rawConf ? 'warn' : 'good',
          causal: 'Then',
        });
      }
      // Module-driven causal lines (synthesized from badges)
      (v.badges || []).slice(0, 2).forEach((b: any, i: number) => {
        const lbl = String(b.label || b.type).toLowerCase();
        let line = b.label || 'meta-brain rule fired';
        if (/sentiment/i.test(lbl)) line = 'Sentiment turned hostile · crowd euphoric';
        else if (/funding/i.test(lbl)) line = 'Exchange flow became hostile · funding extreme';
        else if (/volat/i.test(lbl)) line = 'Volatility expansion absent · structure weakening';
        else if (/macro|regime/i.test(lbl)) line = 'Macro regime conflict detected';
        out.push({
          ts: tsOf(now, -15 + i * 4), symbol: sym, text: line,
          tone: 'warn', causal: 'Then',
        });
      });
      if (flipped) {
        out.push({
          ts: tsOf(now, -8), symbol: sym,
          text: `Direction flipped: ${rawDir} → ${finalDir}`,
          tone: 'warn', causal: 'Then',
        });
      } else if (suppressed) {
        out.push({
          ts: tsOf(now, -6), symbol: sym,
          text: 'Meta-brain suppressed deployment',
          tone: 'bad', causal: 'Then',
        });
      }
      out.push({
        ts: tsOf(now, -2), symbol: sym,
        text: finalDir === 'HOLD' || finalDir === 'WAIT'
          ? `Final verdict: SUPPRESSED · capital preserved`
          : `Final verdict: ${finalDir}${finalConf != null ? ` (${pct(finalConf)})` : ''}`,
        tone: finalDir === 'HOLD' || finalDir === 'WAIT' ? 'good' : 'good',
        causal: 'Final',
      });
      return out;
    }
  }

  // ── COMMAND scope: cross-system cognition chain
  if (scope === 'COMMAND' || scope === 'PORTFOLIO') {
    const realizedH = realized?.headline;
    const parallelH = parallel?.headline;

    out.push({
      ts: tsOf(now, -180),
      text: 'Meta-brain initialized cognition cycle',
      tone: 'neutral', causal: 'Initial',
    });

    if (parallelH?.directional_trades_killed_to_hold > 0) {
      out.push({
        ts: tsOf(now, -150),
        text: `Detected ${parallelH.directional_trades_killed_to_hold} weak-asymmetry setups · suppressed to HOLD`,
        tone: 'good', causal: 'Then',
      });
    }
    if (parallelH?.directional_trades_flipped > 0) {
      out.push({
        ts: tsOf(now, -120),
        text: `${parallelH.directional_trades_flipped} polarity flips applied · directional uncertainty`,
        tone: 'warn', causal: 'Then',
      });
    }
    // Top avoided story
    const topAv = (realized?.top_avoided || [])[0];
    if (topAv) {
      const moveAbs = Math.abs((topAv.realized_return || 0) * 100);
      out.push({
        ts: tsOf(now, -90), symbol: topAv.symbol,
        text: `${symbolOf(topAv.symbol)} broke structure · ${moveAbs.toFixed(2)}% loss avoided`,
        tone: 'good', causal: 'Then',
      });
    }
    // Top missed story
    const topMs = (realized?.top_missed || [])[0];
    if (topMs) {
      const move = (topMs.realized_return || 0) * 100;
      out.push({
        ts: tsOf(now, -60), symbol: topMs.symbol,
        text: `${symbolOf(topMs.symbol)} expanded ${pctRaw(move, 1)} · meta intentionally skipped (asymmetry weak)`,
        tone: 'neutral', causal: 'Then',
      });
    }
    if (realizedH?.net_alpha_pct != null) {
      out.push({
        ts: tsOf(now, -10),
        text: realizedH.verdict === 'META_NET_POSITIVE'
          ? `Cycle resolved: ${pctRaw(realizedH.net_alpha_pct, 1)} net alpha · meta vindicated`
          : `Cycle resolved: ${pctRaw(realizedH.net_alpha_pct, 1)} net alpha · under review`,
        tone: realizedH.verdict === 'META_NET_POSITIVE' ? 'good' : 'bad',
        causal: 'Final',
      });
    }
    return out;
  }

  // ── MARKET scope: regime evolution
  if (scope === 'MARKET') {
    const ms = args.parallel?.headline;
    out.push({ ts: tsOf(now, -240), text: 'Market scan cycle started', tone: 'neutral', causal: 'Initial' });
    const suppr = ms?.directional_trades_killed_to_hold || 0;
    if (suppr > 0) {
      out.push({
        ts: tsOf(now, -180),
        text: `${suppr} symbols showed weak asymmetry · suppressed`,
        tone: 'warn', causal: 'Then',
      });
    }
    out.push({
      ts: tsOf(now, -60),
      text: 'Regime classification updated · perception refreshed',
      tone: 'neutral', causal: 'Final',
    });
    return out;
  }

  return out;
}

// ─── COGNITIVE TIMELINE component ──────────────────────────────────
interface TimelineProps {
  scope: 'COMMAND' | 'EXECUTION' | 'PORTFOLIO' | 'MARKET';
  asset?: string | null;
  title?: string;
  subtitle?: string;
  maxEvents?: number;
}

export function CognitiveTimeline({
  scope, asset, title = 'COGNITIVE TIMELINE',
  subtitle = 'thinking evolution · not event log',
  maxEvents = 8,
}: TimelineProps) {
  const colors = useColors();
  const [data, setData] = useState<any>(_cache?.data ?? null);

  useEffect(() => {
    let alive = true;
    fetchCognitiveData().then((d) => { if (alive) setData(d); });
    return () => { alive = false; };
  }, []);

  const events = useMemo(() => {
    if (!data) return [];
    return deriveTimelineEvents({
      realized: data.realized,
      parallel: data.parallel,
      verdicts: data.verdicts,
      asset,
      scope,
    }).slice(0, maxEvents);
  }, [data, asset, scope, maxEvents]);

  if (!events.length) return null;

  return (
    <View style={{ marginVertical: 8 }}>
      <View style={timelineStyles.titleRow}>
        <Text style={[timelineStyles.title, { color: colors.textMuted }]}>{title}</Text>
        {subtitle && <Text style={[timelineStyles.subtitle, { color: colors.textMuted }]}>{subtitle}</Text>}
      </View>
      <View style={[timelineStyles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        {events.map((e, i) => {
          const c = e.tone === 'good' ? colors.buy
            : e.tone === 'bad' ? colors.sell
            : e.tone === 'warn' ? (colors.warning ?? '#f5a623')
            : colors.textMuted;
          const isLast = i === events.length - 1;
          return (
            <View key={i} style={timelineStyles.eventRow}>
              <View style={timelineStyles.gutter}>
                <Text style={[timelineStyles.ts, { color: colors.textMuted }]}>{e.ts}</Text>
              </View>
              <View style={timelineStyles.spine}>
                <View style={[timelineStyles.dot, { backgroundColor: c }]} />
                {!isLast && <View style={[timelineStyles.line, { backgroundColor: colors.border }]} />}
              </View>
              <View style={[timelineStyles.body, !isLast && { marginBottom: 6 }]}>
                {e.causal && (
                  <Text style={[timelineStyles.causal, { color: colors.textMuted }]}>
                    {e.causal}:
                  </Text>
                )}
                <Text style={[timelineStyles.text, { color: colors.textPrimary }]}>{e.text}</Text>
              </View>
            </View>
          );
        })}
      </View>
    </View>
  );
}

const timelineStyles = StyleSheet.create({
  titleRow: { flexDirection: 'row', alignItems: 'baseline', gap: 8, marginBottom: 8, paddingHorizontal: 4 },
  title: { fontSize: 10, fontWeight: '900', letterSpacing: 1.4 },
  subtitle: { fontSize: 10, fontStyle: 'italic' },
  card: { borderRadius: 12, borderWidth: 1, padding: 14 },
  eventRow: { flexDirection: 'row', alignItems: 'flex-start' },
  gutter: { width: 38 },
  ts: { fontSize: 10, fontWeight: '700', fontVariant: ['tabular-nums' as any] },
  spine: { width: 14, alignItems: 'center', paddingTop: 2 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  line: { flex: 1, width: 1.5, marginTop: 4, marginBottom: -4 },
  body: { flex: 1, paddingLeft: 4 },
  causal: { fontSize: 9, fontWeight: '900', letterSpacing: 0.6 },
  text: { fontSize: 12, lineHeight: 17 },
});

// ─── WHAT AI IS WAITING FOR ────────────────────────────────────────
interface WaitsForProps {
  asset?: string | null;
  topConf?: number | null;
}

function deriveSpecificGates(args: {
  asset?: string | null;
  topConf?: number | null;
  marketState: any;
  verdicts: any[];
  parallel: any;
}): { gate: string; condition: string }[] {
  const { asset, topConf, marketState, verdicts, parallel } = args;
  const out: { gate: string; condition: string }[] = [];
  const sym = asset ? String(asset).toUpperCase() : 'BTC';
  const ms = marketState?.market_state || marketState || {};
  const phead = parallel?.headline;

  // Gate: structural reclaim
  out.push({
    gate: `${sym} reclaim above local liquidity shelf`,
    condition: 'requires close above structure pivot',
  });

  // Funding gate
  const fund = ms.funding != null ? Number(ms.funding) : null;
  if (fund != null && Math.abs(fund) > 0.0008) {
    out.push({
      gate: 'funding normalization',
      condition: `current ${(fund * 100).toFixed(3)}% · target near 0`,
    });
  } else {
    out.push({
      gate: 'funding alignment',
      condition: 'orderbook neutrality · no extreme bias',
    });
  }

  // Sentiment gate
  out.push({
    gate: 'sentiment divergence resolution',
    condition: 'crowd narrative must align or invert',
  });

  // Volatility gate
  out.push({
    gate: 'volatility compression break',
    condition: 'ATR expansion required for asymmetric move',
  });

  // Suppression gate
  if (phead?.directional_trades_killed_to_hold > 5) {
    out.push({
      gate: 'meta suppression release',
      condition: `${phead.directional_trades_killed_to_hold} setups currently killed`,
    });
  }

  // Conviction gate
  if (topConf != null && topConf < 0.55) {
    out.push({
      gate: 'conviction climb above 55%',
      condition: `current ${pct(topConf)} · gap to deployment`,
    });
  }

  return out.slice(0, 5);
}

export function WhatAIWaitsFor({ asset, topConf }: WaitsForProps) {
  const colors = useColors();
  const [data, setData] = useState<any>(_cache?.data ?? null);

  useEffect(() => {
    let alive = true;
    fetchCognitiveData().then((d) => { if (alive) setData(d); });
    return () => { alive = false; };
  }, []);

  const gates = useMemo(() => {
    if (!data) return [];
    return deriveSpecificGates({
      asset, topConf,
      marketState: data.marketState,
      verdicts: data.verdicts,
      parallel: data.parallel,
    });
  }, [data, asset, topConf]);

  if (!gates.length) return null;

  return (
    <View style={{ marginVertical: 8 }}>
      <View style={waitStyles.titleRow}>
        <Text style={[waitStyles.title, { color: colors.textMuted }]}>WHAT AI IS WAITING FOR</Text>
        <Text style={[waitStyles.sub, { color: colors.textMuted }]}>activation gates · specific</Text>
      </View>
      <View style={[waitStyles.card, { backgroundColor: colors.surface, borderColor: colors.warning + '40' }]}>
        {gates.map((g, i) => (
          <View key={i} style={[
            waitStyles.row,
            i < gates.length - 1 && { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
          ]}>
            <View style={[waitStyles.dot, { backgroundColor: colors.warning ?? '#f5a623' }]} />
            <View style={{ flex: 1 }}>
              <Text style={[waitStyles.gate, { color: colors.textPrimary }]}>{g.gate}</Text>
              <Text style={[waitStyles.cond, { color: colors.textMuted }]}>{g.condition}</Text>
            </View>
          </View>
        ))}
      </View>
    </View>
  );
}

const waitStyles = StyleSheet.create({
  titleRow: { flexDirection: 'row', alignItems: 'baseline', gap: 8, marginBottom: 8, paddingHorizontal: 4 },
  title: { fontSize: 10, fontWeight: '900', letterSpacing: 1.4 },
  sub: { fontSize: 10, fontStyle: 'italic' },
  card: { borderRadius: 12, borderWidth: 1, overflow: 'hidden' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 11, paddingHorizontal: 14 },
  dot: { width: 6, height: 6, borderRadius: 3 },
  gate: { fontSize: 12, fontWeight: '800' },
  cond: { fontSize: 10, marginTop: 2, fontStyle: 'italic' },
});

// ─── DECISION PATH CHAIN ───────────────────────────────────────────
interface PathProps {
  /** journey to render. */
  states: FlowState[];
  /** the index of the current state (others are 'reached' before, dim after) */
  currentIndex: number;
  pulse?: boolean;
}

const FLOW_META: Record<FlowState, { color: keyof any; icon: keyof typeof Ionicons.glyphMap; label: string }> = {
  WATCHING:   { color: 'textMuted', icon: 'eye-outline',                 label: 'WATCHING' },
  BUILDING:   { color: 'warning',   icon: 'construct-outline',           label: 'BUILDING' },
  READY:      { color: 'accent',    icon: 'checkmark-circle-outline',    label: 'READY' },
  EXECUTED:   { color: 'buy',       icon: 'flash',                       label: 'EXECUTED' },
  SUPPRESSED: { color: 'sell',      icon: 'ban-outline',                 label: 'SUPPRESSED' },
  PROTECTED:  { color: 'buy',       icon: 'shield-checkmark-outline',    label: 'PROTECTED' },
};

function PulseDot({ color, size = 12 }: { color: string; size?: number }) {
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

export function DecisionPathChain({ states, currentIndex, pulse = true }: PathProps) {
  const colors = useColors();
  return (
    <View style={pathStyles.wrap}>
      {states.map((s, i) => {
        const meta = FLOW_META[s];
        const c = (colors as any)[meta.color] || colors.accent;
        const reached = i <= currentIndex;
        const isCurrent = i === currentIndex;
        return (
          <React.Fragment key={s + i}>
            <View style={pathStyles.node}>
              {isCurrent && pulse ? (
                <PulseDot color={c} size={10} />
              ) : (
                <View style={[pathStyles.dot, {
                  backgroundColor: reached ? c : colors.border,
                  opacity: reached ? 1 : 0.4,
                }]} />
              )}
              <Text style={[pathStyles.label, {
                color: reached ? c : colors.textMuted,
                opacity: reached ? 1 : 0.55,
              }]}>
                {meta.label.slice(0, 5)}
              </Text>
            </View>
            {i < states.length - 1 && (
              <View style={[pathStyles.line, {
                backgroundColor: i < currentIndex ? ((colors as any)[FLOW_META[states[i + 1]].color] || colors.accent) : colors.border,
                opacity: i < currentIndex ? 0.7 : 0.3,
              }]} />
            )}
          </React.Fragment>
        );
      })}
    </View>
  );
}

const pathStyles = StyleSheet.create({
  wrap: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 4, paddingVertical: 6 },
  node: { alignItems: 'center', gap: 4, width: 56 },
  dot: { width: 10, height: 10, borderRadius: 5 },
  label: { fontSize: 9, fontWeight: '900', letterSpacing: 0.5 },
  line: { flex: 1, height: 2, marginHorizontal: -2 },
});

// ─── AI THOUGHT PROCESS ────────────────────────────────────────────
interface ThoughtProps {
  asset?: string | null;
}

function deriveThoughtNarrative(args: {
  asset?: string | null;
  verdicts: any[];
  realized: any;
  parallel: any;
}): string | null {
  const { asset, verdicts, realized, parallel } = args;

  // Asset-specific narrative
  if (asset) {
    const sym = String(asset).toUpperCase();
    const v = verdicts.find((x: any) => symbolOf(x.symbol) === sym);
    if (v) {
      const rawDir = v.stages?.raw?.direction || v.raw_action;
      const finalDir = v.final_action;
      const rawConf = v.stages?.raw?.confidence;
      const finalConf = v.confidence_final;
      const flipped = rawDir && finalDir && rawDir !== finalDir;
      const suppressed = (v.badges || []).some((b: any) => b.type === 'SUPPRESSED');
      const lblBadge = (v.badges || []).find((b: any) =>
        ['SUPPRESSED', 'DOWNGRADED', 'FLIPPED'].includes(b.type))?.label || 'meta-brain rule';

      if (suppressed && rawConf != null && finalConf != null) {
        return (
          `AI initially liked ${sym} ${(rawDir || '').toLowerCase()}, ` +
          `but ${String(lblBadge).toLowerCase()} blocked the setup. ` +
          `Deployment confidence dropped from ${pct(rawConf)} to ${pct(finalConf)}. ` +
          `Trade was suppressed.`
        );
      }
      if (flipped) {
        return (
          `AI saw RAW ${rawDir?.toLowerCase()} signal on ${sym}, ` +
          `but meta-brain inverted to ${finalDir?.toLowerCase()} after rule cascade. ` +
          `Confidence stabilized at ${pct(finalConf)}.`
        );
      }
      if (finalDir === 'LONG' || finalDir === 'SHORT') {
        return (
          `AI built conviction on ${sym} through module alignment. ` +
          `RAW signal at ${pct(rawConf)} was retained through meta-brain to ${pct(finalConf)}. ` +
          `Trade is ready for deployment.`
        );
      }
      return (
        `AI is monitoring ${sym} but asymmetry quality remains insufficient. ` +
        `Conviction at ${pct(finalConf)} below deployment threshold.`
      );
    }
  }

  // Aggregate narrative from realized + parallel
  const realizedH = realized?.headline;
  const parallelH = parallel?.headline;
  if (realizedH && parallelH) {
    const verdict = realizedH.verdict;
    if (verdict === 'META_NET_POSITIVE') {
      return (
        `Meta-brain killed ${realizedH.n_killed_loss_avoided} losing setups across the recent regime ` +
        `while intentionally skipping ${realizedH.n_killed_gain_missed} winners that lacked asymmetry. ` +
        `Net result: ${pctRaw(realizedH.net_alpha_pct, 1)} alpha protected, capital preserved.`
      );
    }
    if (verdict === 'META_NET_NEGATIVE') {
      return (
        `Meta-brain killed ${realizedH.n_killed_loss_avoided} losers but suppressed ` +
        `${realizedH.n_killed_gain_missed} winners that ran. ` +
        `Net cost: ${pctRaw(realizedH.net_alpha_pct, 1)} alpha · suppression policy under review.`
      );
    }
  }
  return null;
}

export function AIThoughtProcess({ asset }: ThoughtProps) {
  const colors = useColors();
  const [data, setData] = useState<any>(_cache?.data ?? null);

  useEffect(() => {
    let alive = true;
    fetchCognitiveData().then((d) => { if (alive) setData(d); });
    return () => { alive = false; };
  }, []);

  const narrative = useMemo(() => {
    if (!data) return null;
    return deriveThoughtNarrative({
      asset, verdicts: data.verdicts, realized: data.realized, parallel: data.parallel,
    });
  }, [data, asset]);

  if (!narrative) return null;

  return (
    <View style={{ marginVertical: 8 }}>
      <View style={thoughtStyles.titleRow}>
        <Text style={[thoughtStyles.title, { color: colors.textMuted }]}>AI THOUGHT PROCESS</Text>
        <Text style={[thoughtStyles.sub, { color: colors.textMuted }]}>reasoning · not outcome</Text>
      </View>
      <View style={[thoughtStyles.card, {
        backgroundColor: colors.surface, borderColor: colors.accent + '30',
      }]}>
        <View style={[thoughtStyles.iconWrap, { backgroundColor: colors.accent + '20' }]}>
          <Ionicons name="bulb-outline" size={16} color={colors.accent} />
        </View>
        <Text style={[thoughtStyles.text, { color: colors.textPrimary }]}>
          {narrative}
        </Text>
      </View>
    </View>
  );
}

const thoughtStyles = StyleSheet.create({
  titleRow: { flexDirection: 'row', alignItems: 'baseline', gap: 8, marginBottom: 8, paddingHorizontal: 4 },
  title: { fontSize: 10, fontWeight: '900', letterSpacing: 1.4 },
  sub: { fontSize: 10, fontStyle: 'italic' },
  card: { flexDirection: 'row', gap: 10, padding: 14, borderRadius: 12, borderWidth: 1 },
  iconWrap: { width: 32, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  text: { flex: 1, fontSize: 13, lineHeight: 19, fontStyle: 'italic' },
});
