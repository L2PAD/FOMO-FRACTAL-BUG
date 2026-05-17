/**
 * CONVICTION EVOLUTION  ·  Iteration 3B · Execution Console
 *
 *   raw 58%  →  meta 31%  →  final WAIT
 *
 * Visualises how a single trade thought evolved across the 3 cognitive
 * stages.  Arrows between stages animate in left-to-right (FadeIn with
 * delay) — once, then calm.
 *
 * Verb (weakening / strengthening / collapsed / stabilizing / flipped)
 * is rendered as a single ambient line below the path, in a tone that
 * matches the verb.
 *
 * Context lines below emerge one by one (1.2s, 2.6s, 4.2s) — same
 * cognitive grammar as ScannerLifecycleCard.
 */
import React, { useMemo } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Animated from 'react-native-reanimated';
import { softEntry, slowEmergence } from './motion';
import {
  ConvictionVerb, convictionVerb, convictionVerbColorKey,
} from './cognitiveLabel';

type Stage = {
  key: string;     // 'RAW' | 'META' | 'FINAL'
  conf?: number | null;     // 0..1
  dir?: string | null;      // 'LONG' / 'SHORT' / 'WAIT' / 'HOLD'
};

type Props = {
  stages: Stage[];
  colors: any;
  /** optional override of the verb derivation. */
  verb?: ConvictionVerb;
};

function pct(n: number | null | undefined): string {
  if (n == null || isNaN(n)) return '—';
  return `${Math.round(n * 100)}%`;
}

function dirColor(d: string | null | undefined, c: any): string {
  if (d === 'LONG' || d === 'BUY' || d === 'BULLISH')  return c.buy;
  if (d === 'SHORT' || d === 'SELL' || d === 'BEARISH') return c.sell;
  if (d === 'WAIT' || d === 'HOLD')                     return c.textMuted;
  return c.textMuted;
}

function buildContextLines(stages: Stage[], v: ConvictionVerb): string[] {
  if (stages.length < 2) return [];
  const raw = stages[0];
  const final = stages[stages.length - 1];
  const out: string[] = [];

  const dRaw = pct(raw.conf);
  const dFin = pct(final.conf);

  if (v === 'collapsed') {
    out.push(`raw instinct read ${dRaw} · meta-brain dropped it to ${dFin}`);
    out.push('directional thesis lost integrity along the chain');
  } else if (v === 'flipped') {
    out.push(`polarity flipped: raw said ${raw.dir || '—'}, final ${final.dir || '—'}`);
    out.push('meta override · raw direction overruled');
  } else if (v === 'weakening') {
    out.push(`conviction stepped down from ${dRaw} to ${dFin} across the chain`);
    out.push('alignment cooling · structure not holding');
  } else if (v === 'strengthening') {
    out.push(`conviction firmed from ${dRaw} to ${dFin} after meta-review`);
    out.push('alignment improving · structure compounding');
  } else {
    out.push(`conviction stable at ${dFin} across all stages`);
    out.push('thesis preserved through meta-brain · no regime conflict');
  }

  return out;
}

export function ConvictionEvolution({ stages, colors, verb }: Props) {
  if (stages.length < 2) return null;
  const raw = stages[0];
  const final = stages[stages.length - 1];

  const v: ConvictionVerb = useMemo(
    () => verb ?? convictionVerb({
      rawConf: raw.conf,
      finalConf: final.conf,
      rawDir: raw.dir,
      finalDir: final.dir,
    }),
    [verb, raw.conf, final.conf, raw.dir, final.dir],
  );
  const verbTone = (colors as any)[convictionVerbColorKey(v)] || colors.textMuted;
  const lines = useMemo(() => buildContextLines(stages, v), [stages, v]);

  return (
    <View style={[styles.wrap, { backgroundColor: colors.surface, borderColor: colors.border }]}>
      <View style={styles.headRow}>
        <Text style={[styles.label, { color: colors.textMuted }]}>CONVICTION EVOLUTION</Text>
        <Text style={[styles.verb, { color: verbTone }]}>{v}</Text>
      </View>

      {/* RAW → META → FINAL path */}
      <View style={styles.pathRow}>
        {stages.map((stage, i) => {
          const dCol = dirColor(stage.dir, colors);
          const isLast = i === stages.length - 1;
          return (
            <React.Fragment key={stage.key}>
              <Animated.View
                entering={softEntry(i * 350)}
                style={styles.stageBox}
              >
                <Text style={[styles.stageKey, { color: colors.textMuted }]}>{stage.key}</Text>
                <Text style={[styles.stageConf, { color: dCol }]}>
                  {stage.conf != null ? pct(stage.conf) : (stage.dir || '—')}
                </Text>
                {stage.dir && stage.conf != null && (
                  <Text style={[styles.stageDir, { color: dCol }]}>{stage.dir}</Text>
                )}
              </Animated.View>
              {!isLast && (
                <Animated.View
                  entering={softEntry(180 + i * 350)}
                  style={styles.arrowWrap}
                >
                  <View style={[styles.arrowLine, { backgroundColor: verbTone + '60' }]} />
                  <Text style={[styles.arrowChar, { color: verbTone }]}>→</Text>
                </Animated.View>
              )}
            </React.Fragment>
          );
        })}
      </View>

      {/* context lines — emerge one-by-one */}
      <View style={styles.lineWrap}>
        {lines.map((line, i) => (
          <Animated.View
            key={`evo-line-${i}`}
            entering={slowEmergence(1200 + i * 1400)}
            style={styles.lineRow}
          >
            <View style={[styles.lineMark, { backgroundColor: verbTone + '70' }]} />
            <Text style={[styles.lineText, { color: colors.textPrimary }]}>{line}</Text>
          </Animated.View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { borderRadius: 14, borderWidth: 1, padding: 14 },

  headRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  label: { fontSize: 9, fontWeight: '900', letterSpacing: 1.5 },
  verb: { fontSize: 11, fontWeight: '900', letterSpacing: 1.1, textTransform: 'lowercase' },

  pathRow: { flexDirection: 'row', alignItems: 'center', marginTop: 12, gap: 4 },
  stageBox: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 6,
  },
  stageKey: { fontSize: 9, fontWeight: '900', letterSpacing: 1.2 },
  stageConf: { fontSize: 22, fontWeight: '900', letterSpacing: 0.4, marginTop: 2 },
  stageDir: { fontSize: 9, fontWeight: '800', letterSpacing: 0.8, marginTop: 1 },

  arrowWrap: {
    width: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
  arrowLine: { position: 'absolute', left: 0, right: 0, height: 1.5, top: '50%' },
  arrowChar: { fontSize: 18, fontWeight: '900' },

  lineWrap: { marginTop: 10, gap: 6 },
  lineRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  lineMark: { width: 4, height: 4, borderRadius: 2 },
  lineText: { flex: 1, fontSize: 12, lineHeight: 17 },
});
