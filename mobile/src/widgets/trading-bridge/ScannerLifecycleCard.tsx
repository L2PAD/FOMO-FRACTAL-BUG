/**
 * SCANNER LIFECYCLE CARD  ·  PHASE X · ITERATION 3A · M-02 + M-03 + M-05
 *
 * Per-asset opportunity card with EMERGENT cognition.
 *
 *   1.  state-label is a continuous cognition verb (not a category).
 *   2.  context lines below the state EMERGE one by one (delayed fade-in
 *       at 1.2s, 2.6s, 4.2s after mount), creating the feel that AI is
 *       building its perception over time — not dumping a bullet list.
 *   3.  conviction shows as a delta (raw vs final = real dispersion
 *       between AI's instinct and AI's judgement).
 *
 * No pulsing.  No looping animation.  Each emergence happens once, then
 * the card is calm.
 */
import React, { useMemo } from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Animated from 'react-native-reanimated';
import { softEntry } from '../cognition/motion';
import {
  cognitiveLabel, cognitiveTok, cognitiveColorKey,
  toCognitive, LegacyFlowState,
} from '../cognition/cognitiveLabel';

type Verdict = any;

type Props = {
  sym: string;
  verdict: Verdict;
  flow: LegacyFlowState;
  asymmetry: number;
  structuralVerb: string;
  isFocus: boolean;
  onPress: () => void;
  colors: any;
};

function buildContextLines(v: Verdict, flow: LegacyFlowState): string[] {
  const lines: string[] = [];
  const finalConf = v?.confidence_final || 0;
  const rawConf = v?.stages?.raw?.confidence || 0;
  const delta = Math.round((finalConf - rawConf) * 100);
  const badges = v?.badges || [];
  const suppressed = badges.some((b: any) => b.type === 'SUPPRESSED');
  const flipped    = badges.some((b: any) => b.type === 'FLIPPED');

  // line 1 — conviction posture (always present)
  if (Math.abs(delta) >= 5) {
    if (delta > 0) lines.push(`alignment improving · +${delta} conviction over raw`);
    else           lines.push(`alignment weakening · ${delta} conviction below raw`);
  } else if (finalConf >= 0.5) {
    lines.push(`conviction stable at ${Math.round(finalConf * 100)}%`);
  } else {
    lines.push(`conviction unsettled at ${Math.round(finalConf * 100)}%`);
  }

  // line 2 — structural posture
  if (suppressed && rawConf >= 0.55) {
    lines.push('meta override · directional setup denied');
  } else if (flipped) {
    lines.push('polarity flip detected · raw direction overruled');
  } else if (flow === 'READY') {
    lines.push('all gates clearing · deployment window opening');
  } else if (flow === 'BUILDING') {
    const stages = v?.stages ? Object.keys(v.stages).length : 0;
    if (stages) lines.push(`${stages}/5 modules aligning · structure forming`);
    else        lines.push('structure forming · awaiting more alignment');
  } else if (flow === 'AVOIDING') {
    lines.push('exchange divergence detected · capital protected');
  }

  // line 3 — micro-context (optional)
  if (v?.horizon) {
    lines.push(`horizon ${v.horizon} · ${flow === 'READY' ? 'ready to act' : 'still maturing'}`);
  }

  return lines.slice(0, 3);
}

export function ScannerLifecycleCard({
  sym, verdict, flow, asymmetry, structuralVerb, isFocus, onPress, colors,
}: Props) {
  const cog = useMemo(
    () => toCognitive(flow, verdict?.confidence_final || 0),
    [flow, verdict?.confidence_final],
  );
  const cogColor = (colors as any)[cognitiveColorKey(cog)] || colors.textMuted;
  const finalConf = Math.round((verdict?.confidence_final || 0) * 100);
  const rawConf   = Math.round((verdict?.stages?.raw?.confidence || 0) * 100);
  const delta = finalConf - rawConf;

  const lines = useMemo(() => buildContextLines(verdict, flow), [verdict, flow]);

  // delta visual: arrow + magnitude
  const deltaTone =
    delta > 4 ? colors.buy
    : delta < -4 ? colors.sell
    : colors.textMuted;
  const deltaArrow = delta > 4 ? '↑' : delta < -4 ? '↓' : '·';
  const deltaVerb =
    delta > 4 ? 'accelerating'
    : delta < -4 ? 'weakening'
    : 'holding';

  return (
    <TouchableOpacity
      testID={`opportunity-${sym}`}
      activeOpacity={0.85}
      onPress={onPress}
      style={[
        styles.card,
        {
          backgroundColor: colors.surface,
          borderColor: isFocus ? colors.accent : colors.border,
        },
      ]}
    >
      {/* HEAD ROW — symbol + asymmetry */}
      <View style={styles.headRow}>
        <View style={{ flex: 1 }}>
          <Text style={[styles.sym, { color: colors.textPrimary }]}>{sym}</Text>
          <Text style={[styles.verb, { color: colors.textMuted }]} numberOfLines={1}>
            {structuralVerb}
          </Text>
        </View>
        <View style={styles.asymBox}>
          <Text style={[styles.asymVal, { color: cogColor }]}>{asymmetry}</Text>
          <Text style={[styles.asymLabel, { color: colors.textMuted }]}>asymmetry</Text>
        </View>
      </View>

      {/* COGNITIVE STATE — large emerging label */}
      <Animated.View
        entering={softEntry()}
        style={[styles.stateRow, { borderTopColor: colors.border }]}
      >
        <View style={[styles.stateDot, { backgroundColor: cogColor }]} />
        <Text style={[styles.stateTok, { color: cogColor }]}>{cognitiveTok(cog)}</Text>
        <Text style={[styles.stateVerb, { color: colors.textPrimary }]}>
          {cognitiveLabel(cog)}
        </Text>
      </Animated.View>

      {/* CONVICTION DELTA — single line, large */}
      <Animated.View
        entering={softEntry(700)}
        style={styles.convRow}
      >
        <Text style={[styles.convNum, { color: colors.textPrimary }]}>{finalConf}%</Text>
        <Text style={[styles.convArrow, { color: deltaTone }]}>{deltaArrow}</Text>
        <Text style={[styles.convVerb, { color: deltaTone }]}>{deltaVerb}</Text>
        {Math.abs(delta) >= 1 && (
          <Text style={[styles.convDelta, { color: colors.textMuted }]}>
            {delta > 0 ? '+' : ''}{delta} from raw conviction
          </Text>
        )}
      </Animated.View>

      {/* CONTEXT LINES — emerge one by one (1.2s, 2.6s, 4.2s) */}
      <View style={styles.linesWrap}>
        {lines.map((line, i) => (
          <Animated.View
            key={`${sym}-line-${i}`}
            entering={FadeIn
              .duration(1100)
              .delay(1200 + i * 1400)
              .easing(Easing.out(Easing.exp))}
            style={styles.lineRow}
          >
            <View style={[styles.lineMark, { backgroundColor: cogColor + '70' }]} />
            <Text style={[styles.lineText, { color: colors.textPrimary }]}>{line}</Text>
          </Animated.View>
        ))}
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 14,
    marginBottom: 8,
  },

  headRow: { flexDirection: 'row', alignItems: 'center' },
  sym: { fontSize: 17, fontWeight: '900', letterSpacing: 0.2 },
  verb: { fontSize: 11, marginTop: 2, fontStyle: 'italic' },
  asymBox: { alignItems: 'flex-end' },
  asymVal: { fontSize: 26, fontWeight: '900', letterSpacing: 0.5 },
  asymLabel: { fontSize: 9, fontWeight: '700', letterSpacing: 0.5 },

  stateRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    marginTop: 12, paddingTop: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  stateDot: { width: 6, height: 6, borderRadius: 3 },
  stateTok: { fontSize: 9, fontWeight: '900', letterSpacing: 1.4 },
  stateVerb: { fontSize: 12, fontWeight: '700', flex: 1 },

  convRow: { flexDirection: 'row', alignItems: 'baseline', gap: 8, marginTop: 8, flexWrap: 'wrap' },
  convNum: { fontSize: 22, fontWeight: '900', letterSpacing: 0.3 },
  convArrow: { fontSize: 16, fontWeight: '900' },
  convVerb: { fontSize: 12, fontWeight: '800', letterSpacing: 0.3 },
  convDelta: { fontSize: 10, marginLeft: 'auto' },

  linesWrap: { marginTop: 8, gap: 6 },
  lineRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  lineMark: { width: 4, height: 4, borderRadius: 2 },
  lineText: { flex: 1, fontSize: 12, lineHeight: 17 },
});
