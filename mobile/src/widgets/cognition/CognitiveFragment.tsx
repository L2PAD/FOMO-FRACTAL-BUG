/**
 * COGNITIVE FRAGMENT  ·  PHASE X · P6·α
 *
 *   Memory surfacing — NOT animation.
 *
 *   A fragment is the visible remainder of a cognitive event whose
 *   residue still has weight in the bus.  It is not a card.  It is not
 *   a list row.  It is a half-finished thought that resolves itself
 *   over the first second of life.
 *
 *
 *   EMERGENCE PROTOCOL (the rules are the design)
 *
 *     1. The container is NOT animated.  No fade on the wrapper.  No
 *        scale.  No translate.  The space simply exists.
 *
 *     2. The lead text surfaces via `slowEmergence()` (≈1.1s).  This is
 *        the first half of the thought.
 *
 *     3. The tail text surfaces via `hesitationReveal()` (≈800ms pause,
 *        then a 900ms reveal).  This is the resolution.
 *
 *     4. Asymmetry is mandatory.  Each fragment receives a stable
 *        `indentSeed` ∈ [0,1].  We use it to vary:
 *           · horizontal indent (left or right shifted)
 *           · whether the tail begins on the same line or a new one
 *           · whether the tail receives a soft connective ('·') or none
 *        Two fragments side by side must never feel like list rows.
 *
 *     5. No icons.  No timestamps.  No tap affordance.  No chrome.
 *        The fragment is text suspended in negative space.
 *
 *
 *   LAYER ROLE
 *
 *     `<CognitiveFragmentLayer>` is the container that reads fragments
 *     from the bus and renders 0..N of them.  An empty layer renders
 *     NOTHING — not a placeholder, not a header, not an empty card.
 *     Absence is the default.
 */
import React from 'react';
import { View, Text, StyleSheet, ViewStyle } from 'react-native';
import Animated from 'react-native-reanimated';
import { CognitiveFragment } from './bus/composeFragment';
import { useCognitiveFragments } from './bus/cognitiveBus';
import type { FragmentScope } from './bus/composeFragment';
import { cognitionStyle, explanationStyle } from './cognitiveType';
import { tokenFor } from './cognitiveTokens';
import { slowEmergence, hesitationReveal } from './motion';

// ─── single fragment renderer ─────────────────────────────────────

function FragmentBody({ fragment, colors }: { fragment: CognitiveFragment; colors: any }) {
  const tok = tokenFor(fragment.tone);
  // Lead uses L1-ambient typography but in fragment.tone — quiet, wide
  // letter-spacing, not authoritative.
  const leadStyle = cognitionStyle(colors, fragment.tone, 'lg', fragment.pressure === 'authority' ? 'institutional' : 'ambient');
  const tailStyle = explanationStyle(colors, fragment.tone);

  // Asymmetric framing — never two fragments alike.
  const seed = fragment.indentSeed;
  const baseInset = 14 + Math.round(seed * 22);           // 14..36 px
  const isRightLean = (Math.floor(seed * 7) % 2) === 0;   // half-leans right
  const tailOnNewLine = seed > 0.42;
  const tailWithBullet = !tailOnNewLine && seed > 0.18;
  const tailInsetExtra = Math.round(seed * 18);

  const wrapStyle: ViewStyle = {
    paddingLeft: isRightLean ? baseInset * 0.45 : baseInset,
    paddingRight: isRightLean ? baseInset : baseInset * 0.45,
    paddingTop: 8 + Math.round(seed * 6),
    paddingBottom: 8 + Math.round((1 - seed) * 6),
    // Subtle hairline on one side only — a faint indication that a
    // residue weight is present here, never a box.
    borderLeftWidth: isRightLean ? 0 : StyleSheet.hairlineWidth,
    borderRightWidth: isRightLean ? StyleSheet.hairlineWidth : 0,
    borderColor: ((colors as any)[tok.colorKey] || colors.textMuted) + '40',
    opacity: tok.opacity * 0.95,
  };

  return (
    <View style={[styles.row, wrapStyle]}>
      <Animated.View entering={slowEmergence(fragment.indentSeed * 120)}>
        <Text style={[leadStyle, styles.leadText]}>
          {fragment.lead}
          {fragment.tail && !tailOnNewLine ? (
            <Text style={tailStyle}>
              {tailWithBullet ? '  ·  ' : '  '}
              {fragment.tail}
            </Text>
          ) : null}
        </Text>
      </Animated.View>
      {fragment.tail && tailOnNewLine && (
        <Animated.View entering={hesitationReveal()}>
          <Text style={[tailStyle, { paddingLeft: tailInsetExtra }]}>
            {fragment.tail}
          </Text>
        </Animated.View>
      )}
    </View>
  );
}

// ─── layer container ──────────────────────────────────────────────

export function CognitiveFragmentLayer(props: {
  scope?: FragmentScope;
  max?: number;
  colors: any;
  /**
   * Optional outer vertical margin.  Defaults are intentionally airy so
   * the layer reads as negative space when no fragments are present.
   */
  marginTop?: number;
  marginBottom?: number;
}) {
  const fragments = useCognitiveFragments({ scope: props.scope ?? 'any', max: props.max ?? 1 });

  // Empty layer renders nothing.  Absence is the default state.
  if (fragments.length === 0) return null;

  return (
    <View
      style={{
        marginTop: props.marginTop ?? 8,
        marginBottom: props.marginBottom ?? 8,
      }}
      // For testing / accessibility we expose a stable testID but no
      // visible header.
      testID="cognitive-fragment-layer"
    >
      {fragments.map((f) => (
        <FragmentBody key={f.id} fragment={f} colors={props.colors} />
      ))}
    </View>
  );
}

// ─── styles ───────────────────────────────────────────────────────

const styles = StyleSheet.create({
  row: {
    // No background, no surface, no card.  Fragment lives in negative
    // space.  The hairline border is applied dynamically per-fragment.
  },
  leadText: {
    // Wider tracking than normal headlines — closer to a breath than a
    // declaration.
    letterSpacing: 1.0,
  },
});
