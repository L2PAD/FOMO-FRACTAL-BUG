/**
 * COGNITIVE BADGE  ·  Iteration 4·α
 *
 * NOT a Badge component.  A semantic state renderer.
 *
 * Reads a SemanticToken from cognitiveTokens.ts and composes:
 *   · color (from tone, never hex)
 *   · spacing (from density)
 *   · border energy (firmness)
 *   · opacity (state loudness)
 *   · icon cadence (present / subdued / absent)
 *   · entry motion (slow-fade-emerge / breathe / static)
 *
 * Two states with the same hue (e.g. WAIT and OBSERVING both grey) read
 * differently because their density / opacity / border differ.  This is
 * the core promise of slice 4·α — stability of language without
 * inflating the palette.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Animated from 'react-native-reanimated';
import { softEntry, subtleExpansion } from './motion';
import {
  CognitiveCategory,
  tokenForState,
  paddingFor,
  borderWidthFor,
  SemanticEnergy,
} from './cognitiveTokens';

type Theme = any;

type Props = {
  /** One of cognition / capital / conviction / regime. */
  category: CognitiveCategory;
  /** State label, e.g. 'OBSERVING' / 'SUPPRESSED' / 'STRENGTHENING'. */
  state: string | null | undefined;
  colors: Theme;
  /** Override the displayed label (defaults to upper-cased state). */
  label?: string;
  /** Force-override density (advanced: usually leave default). */
  densityOverride?: 'compressed' | 'normal' | 'airy';
  /** Optional icon glyph (consulted only if token's iconCadence allows). */
  iconName?: keyof typeof Ionicons.glyphMap;
  /** Optional small-caps prefix label (e.g. "STATE"). */
  prefix?: string;
  /**
   * Dense-surface variant.  When true: no icon, hairline border, lower
   * weight, tighter letter-spacing.  Use in list rows where multiple
   * semantic surfaces share the same line — prevents semantic shouting
   * while preserving the suppression family identity.
   */
  inline?: boolean;
};

/** Map iconCadence + presence to (render?, scale, opacity). */
function iconRules(token: ReturnType<typeof tokenForState>) {
  if (token.icon === 'absent')  return { show: false, size: 0, opacity: 0 };
  if (token.icon === 'subdued') return { show: true,  size: 10, opacity: 0.55 };
  return { show: true, size: 12, opacity: 1.0 };
}

/** Default per-energy iconography — used when caller does not supply one. */
const DEFAULT_ICON: Partial<Record<SemanticEnergy, keyof typeof Ionicons.glyphMap>> = {
  suppression: 'shield-checkmark-outline',
  readiness:   'flash-outline',
  expansion:   'trending-up-outline',
  caution:     'alert-circle-outline',
};

export function CognitiveBadge({
  category, state, colors, label, densityOverride, iconName, prefix, inline = false,
}: Props) {
  const token = tokenForState(category, state);
  const tone = (colors as any)[token.colorKey] || colors.textMuted;

  const density = densityOverride ?? (inline ? 'compressed' : token.density);
  const pad = paddingFor(density);
  const bw = inline ? 0.5 : borderWidthFor(token.border);

  const iconCfg = iconRules(token);
  const iconGlyph = (iconName ?? DEFAULT_ICON[token.energy]);
  const showIcon = !inline && iconCfg.show && !!iconGlyph;

  const motionWrapper = (children: React.ReactNode) => {
    // inline badges in dense lists never animate — quiet, calm rows.
    if (inline) return <View>{children}</View>;
    if (token.motion === 'slow-fade-emerge') {
      return (
        <Animated.View entering={softEntry()}>
          {children}
        </Animated.View>
      );
    }
    if (token.motion === 'breathe') {
      return (
        <Animated.View entering={subtleExpansion()}>
          {children}
        </Animated.View>
      );
    }
    return <View>{children}</View>;
  };

  const displayLabel = (label ?? String(state ?? '—')).toUpperCase();

  // border alpha: firm 'cc' / soft '88' / minimal '44' — inline is 33 (whisper).
  const borderAlpha = inline ? '33'
    : token.border === 'firm' ? 'cc'
    : token.border === 'soft' ? '88'
    : '44';
  // background alpha: inline is whisper '0a'; otherwise firm '22' / soft '14'.
  const bgAlpha = inline ? '0a'
    : token.border === 'firm' ? '22' : '14';

  return motionWrapper(
    <View
      style={[
        styles.box,
        {
          paddingVertical: pad.v,
          paddingHorizontal: pad.h,
          borderWidth: bw,
          borderColor: tone + borderAlpha,
          backgroundColor: tone + bgAlpha,
          opacity: inline ? 0.92 : token.opacity,
        },
      ]}
    >
      {prefix ? (
        <Text style={[styles.prefix, { color: colors.textMuted }]}>{prefix}</Text>
      ) : null}
      {showIcon ? (
        <Ionicons
          name={iconGlyph as any}
          size={iconCfg.size}
          color={tone}
          style={{ opacity: iconCfg.opacity }}
        />
      ) : null}
      <Text
        style={[
          styles.label,
          {
            color: tone,
            fontWeight: inline ? '700'
              : token.border === 'firm' ? '900' : '800',
            letterSpacing: inline ? 0.6
              : density === 'compressed' ? 0.6
              : density === 'airy' ? 1.2 : 0.9,
          },
        ]}
      >
        {displayLabel}
      </Text>
    </View>,
  );
}

const styles = StyleSheet.create({
  box: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 5,
    borderRadius: 999,
  },
  prefix: { fontSize: 8, fontWeight: '900', letterSpacing: 1.4, opacity: 0.6 },
  label: { fontSize: 10 },
});
