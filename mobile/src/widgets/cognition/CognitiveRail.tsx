/**
 * COGNITIVE RAIL  ·  Iteration 4·β
 *
 *   THOUGHT UNFOLDING — NOT an accordion.
 *
 * A normal-looking thought line that, when tapped, reveals more of the
 * AI's reasoning line-by-line with staggered FadeIn (250ms / 700ms /
 * 1150ms / …).  No chevron rotation, no border frame, no accordion UI
 * chrome.  The reasons APPEAR like the AI is finishing the thought, not
 * like a panel is opening.
 *
 *
 *   collapsed:    "deployment rejected · what changed?"
 *
 *   expanded:     "deployment rejected · because"
 *                 · funding overheated
 *                 · exchange divergence detected
 *                 · volatility asymmetry collapsed
 *                 (each appearing 450ms apart)
 *
 *
 *   Rules:
 *     · no border on the rail when expanded
 *     · no chevron rotation animation
 *     · NEVER show a placeholder "loading…" — thought just emerges
 *     · the head changes wording slightly when expanded (cue to user
 *       that they are now inside the AI's mind, not a settings panel)
 */
import React, { useState } from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import Animated from 'react-native-reanimated';
import { sequencedReveal, fadeCollapse } from './motion';
import { explanationStyle, decisionStyle } from './cognitiveType';
import { SemanticEnergy, tokenFor } from './cognitiveTokens';

type Theme = any;

type Props = {
  /** Head line shown collapsed (e.g. "deployment rejected"). */
  head: string;
  /** Head line shown expanded (e.g. "deployment rejected · because"). */
  headExpanded?: string;
  /** The reasons that emerge below — one per line. */
  reasons: string[];
  colors: Theme;
  /** Optional tone (default: suppression for blocking rails). */
  tone?: SemanticEnergy;
  /** Optional small caps label above the head (e.g. "WHY"). */
  caps?: string;
  /** Start expanded? */
  initiallyOpen?: boolean;
};

export function CognitiveRail({
  head, headExpanded, reasons, colors, tone, caps, initiallyOpen = false,
}: Props) {
  const [open, setOpen] = useState(initiallyOpen);
  const toneCol = tone ? ((colors as any)[tokenFor(tone).colorKey] || colors.textMuted) : colors.textMuted;
  // unfinished-thought affordance: trailing ellipsis when collapsed.
  // NEVER show "tap to read" — that puts us back in UI-land.
  const headText = open
    ? (headExpanded || `${head} · because`)
    : `${head}…`;

  return (
    <Pressable
      onPress={() => setOpen((v) => !v)}
      hitSlop={6}
      style={styles.wrap}
    >
      {caps ? (
        <Text style={[styles.caps, { color: colors.textMuted }]}>{caps}</Text>
      ) : null}
      <View style={styles.headRow}>
        <View style={[styles.headDot, { backgroundColor: toneCol + '88' }]} />
        <Text style={[
          decisionStyle(colors, tone, 'md'),
          { flex: 1 },
        ]}>
          {headText}
        </Text>
      </View>

      {open && (
        <View style={styles.reasonsWrap}>
          {reasons.map((r, i) => (
            <Animated.View
              key={`${r}-${i}`}
              entering={sequencedReveal(i, 250)}
              exiting={fadeCollapse()}
              style={styles.reasonRow}
            >
              <View style={[styles.reasonLine, { backgroundColor: toneCol + '55' }]} />
              <Text style={[explanationStyle(colors), { flex: 1 }]}>{r}</Text>
            </Animated.View>
          ))}
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrap: { paddingVertical: 6 },
  caps: { fontSize: 9, fontWeight: '900', letterSpacing: 1.4, marginBottom: 4, opacity: 0.6 },
  headRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  headDot: { width: 5, height: 5, borderRadius: 2.5 },
  cue: { fontSize: 9, fontStyle: 'italic', opacity: 0.5, letterSpacing: 0.3 },
  reasonsWrap: { marginTop: 8, gap: 6, paddingLeft: 13 },
  reasonRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  reasonLine: { width: 8, height: 1.5, borderRadius: 1 },
});
