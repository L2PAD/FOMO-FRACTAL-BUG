/**
 * COGNITIVE ANCHOR  ·  Iteration 4·β
 *
 * Ambient cognition anchor — NOT a toolbar, NOT navigation.
 *
 * Persistent AI-state memory that follows the user as they scroll
 * through a Trading OS surface.  Atmospheric, almost transparent.
 * The user should feel the AI's current state without being shown UI.
 *
 *   ─────────────────────────────────────────────────────────────
 *    · AI · SUPPRESSED        CAPITAL · RISK_OFF       26% READY
 *   ─────────────────────────────────────────────────────────────
 *
 *   · ultra-thin (28-32px tall)
 *   · hairline bottom border only
 *   · no surface fill (uses backdrop)
 *   · low contrast — atmosphere, not chrome
 *   · tone-only dot at the leading edge
 *
 * Render as the first child of a ScrollView and pass
 * `stickyHeaderIndices={[0]}` so the anchor pins at the top during
 * scroll without becoming chrome.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { tokenForState, tokenFor } from './cognitiveTokens';
import { telemetryStyle } from './cognitiveType';
import { useDominantCognition } from './bus/cognitiveBus';

type Theme = any;

type Props = {
  /** Cognition state ("OBSERVING" / "SUPPRESSED" / "DORMANT" / etc). */
  cognition?: string | null;
  /** Capital posture ("RISK_OFF" / "DEFENSIVE" / "ENGAGED" / etc). */
  capital?: string | null;
  /** Readiness 0..1.  Optional — omitted when not relevant. */
  readiness?: number | null;
  colors: Theme;
};

export function CognitiveAnchor({ cognition, capital, readiness, colors }: Props) {
  const cogTok = cognition ? tokenForState('cognition', cognition) : null;
  const capTok = capital ? tokenForState('capital', capital) : null;
  const cogColor = cogTok ? ((colors as any)[cogTok.colorKey] || colors.textMuted) : colors.textMuted;
  const capColor = capTok ? ((colors as any)[capTok.colorKey] || colors.textMuted) : colors.textMuted;

  const readinessPct = readiness != null ? Math.round(readiness * 100) : null;

  // ── tonal drift · the anchor's atmosphere shifts with state, NOT animation.
  // Suppression densifies (less airy, slightly tinted backdrop, firmer border).
  // Dormant / observing keep their natural airy posture.
  const localPriority = Math.max(cogTok?.priority ?? 0, capTok?.priority ?? 0);
  const localDominantColor = (cogTok?.priority ?? 0) >= (capTok?.priority ?? 0) ? cogColor : capColor;

  // ── P5 · cognitive residue blend
  // The bus carries persistent atmosphere across screens.  If its
  // dominant energy is loud enough (priority * weight beats local),
  // its colour bleeds into the anchor — the user FEELS continuity.
  const busDominant = useDominantCognition();
  let atmosphereColor = localDominantColor;
  let atmospherePriority = localPriority;
  let atmosphereWeight = 1.0;
  if (busDominant) {
    const busTok = tokenFor(busDominant.energy);
    const busScore = busDominant.score; // already weight * priority
    const localScore = localPriority * 0.85; // local is treated as ~persistent intent
    if (busScore > localScore && busDominant.weight >= 0.25) {
      atmosphereColor = (colors as any)[busTok.colorKey] || atmosphereColor;
      atmospherePriority = busTok.priority;
      atmosphereWeight = busDominant.weight;
    }
  }

  const isSuppressedAtmosphere = atmospherePriority >= 80;
  // tint alpha scales with weight (0.04 .. 0.10) when high-priority,
  // disappears below the threshold.
  const tintAlpha = isSuppressedAtmosphere
    ? Math.round(Math.min(0.12, 0.04 + atmosphereWeight * 0.10) * 255).toString(16).padStart(2, '0')
    : '00';
  const driftTint = isSuppressedAtmosphere ? (atmosphereColor + tintAlpha) : 'transparent';
  const borderColor = isSuppressedAtmosphere ? (atmosphereColor + '40') : colors.border;

  return (
    <View
      style={[
        styles.wrap,
        {
          // backdrop matches background — atmospheric, never overlay.
          // Tonal drift overlay sits as a hairline tint when suppression dominates.
          backgroundColor: colors.background,
          borderBottomColor: borderColor,
        },
      ]}
    >
      {/* tonal drift overlay — a near-invisible state-tinted skin */}
      {driftTint !== 'transparent' ? (
        <View
          pointerEvents="none"
          style={[StyleSheet.absoluteFill, { backgroundColor: driftTint }]}
        />
      ) : null}
      {/* leading tone dot */}
      <View style={[styles.dot, { backgroundColor: cogColor + 'aa' }]} />

      {/* AI cognition */}
      {cognition && (
        <View style={styles.cluster}>
          <Text style={[styles.k, { color: colors.textMuted }]}>AI</Text>
          <Text style={[styles.v, { color: cogColor }]} numberOfLines={1}>
            {String(cognition).toUpperCase()}
          </Text>
        </View>
      )}

      {/* capital posture */}
      {capital && (
        <View style={styles.cluster}>
          <View style={[styles.sep, { backgroundColor: colors.border }]} />
          <Text style={[styles.k, { color: colors.textMuted }]}>CAPITAL</Text>
          <Text style={[styles.v, { color: capColor }]} numberOfLines={1}>
            {String(capital).toUpperCase().replace(/_/g, ' ')}
          </Text>
        </View>
      )}

      {/* readiness */}
      {readinessPct != null && (
        <View style={[styles.cluster, { marginLeft: 'auto' }]}>
          <Text style={[styles.k, { color: colors.textMuted }]}>READY</Text>
          <Text style={[styles.pct, { color: colors.textPrimary }]}>
            {readinessPct}%
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    alignItems: 'center',
    height: 30,
    paddingHorizontal: 12,
    gap: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  dot: { width: 6, height: 6, borderRadius: 3 },
  cluster: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  sep: { width: StyleSheet.hairlineWidth, height: 12, marginHorizontal: 2 },
  k: { fontSize: 8.5, fontWeight: '800', letterSpacing: 1.4, opacity: 0.55 },
  v: { fontSize: 10, fontWeight: '900', letterSpacing: 1, opacity: 0.92 },
  pct: { fontSize: 10, fontWeight: '900', letterSpacing: 0.5, opacity: 0.78 },
});
