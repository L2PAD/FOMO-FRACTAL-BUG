/**
 * COGNITIVE PULSE  ·  shared cognition primitive
 *
 * Generalised version of MarketPulseField.  Renders an ambient strip
 * that slowly rotates through cognition observations.
 *
 *   · 6 second hold
 *   · 1.6 second exp-fade between observations
 *   · No looping pulse, no shimmer, no flashing
 *
 * Caller decides what the AI is sensing — the visual primitive stays the
 * same so that the whole Trading OS feels like one organism.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Animated, {
  useSharedValue, useAnimatedStyle, withTiming,
} from 'react-native-reanimated';
import { TIMING, pulseFadeIn, pulseFadeOut } from './motion';

const HOLD_MS = TIMING.pulseHold;
const FADE_MS = TIMING.pulseFade;

type Props = {
  observations: string[];
  colors: any;
  /** small caps header on the left, e.g. "AI · SENSING" or "AI · INTENTION". */
  headLabel?: string;
  /** override accent (defaults to theme accent). */
  accent?: string;
};

export function CognitivePulse({
  observations, colors, headLabel = 'AI · SENSING', accent,
}: Props) {
  const tone = accent || colors.accent;
  const list = useMemo(
    () => (observations.length ? observations : ['no perception emerging']),
    [observations],
  );
  const [idx, setIdx] = useState(0);
  const opacity = useSharedValue(0);
  const translateY = useSharedValue(6);

  useEffect(() => {
    opacity.value = 0;
    translateY.value = 6;
    opacity.value = withTiming(1, pulseFadeIn);
    translateY.value = withTiming(0, pulseFadeIn);
  }, [idx, opacity, translateY]);

  useEffect(() => {
    if (list.length <= 1) return;
    const t = setTimeout(() => {
      opacity.value = withTiming(0, pulseFadeOut);
      translateY.value = withTiming(-6, pulseFadeOut);
      const advance = setTimeout(() => {
        setIdx((i) => (i + 1) % list.length);
      }, FADE_MS);
      return () => clearTimeout(advance);
    }, HOLD_MS);
    return () => clearTimeout(t);
  }, [idx, list.length, opacity, translateY]);

  const animStyle = useAnimatedStyle(() => ({
    opacity: opacity.value,
    transform: [{ translateY: translateY.value }],
  }));

  return (
    <View
      style={[
        styles.wrap,
        { backgroundColor: colors.surface, borderColor: colors.border },
      ]}
    >
      <View style={styles.headRow}>
        <View style={[styles.cursor, { backgroundColor: tone + '70' }]} />
        <Text style={[styles.label, { color: colors.textMuted }]}>{headLabel}</Text>
        <View style={styles.dots}>
          {list.map((_, i) => (
            <View
              key={i}
              style={[
                styles.dot,
                {
                  backgroundColor: i === idx ? tone : colors.border,
                  width: i === idx ? 14 : 4,
                },
              ]}
            />
          ))}
        </View>
      </View>
      <Animated.Text
        style={[styles.observation, { color: colors.textPrimary }, animStyle]}
        numberOfLines={2}
      >
        {list[idx]}
      </Animated.Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    borderRadius: 14,
    borderWidth: 1,
    paddingVertical: 14,
    paddingHorizontal: 16,
    marginTop: 14,
  },
  headRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  cursor: { width: 6, height: 6, borderRadius: 3 },
  label: { fontSize: 9, fontWeight: '900', letterSpacing: 1.6 },
  dots: { flexDirection: 'row', alignItems: 'center', gap: 4, marginLeft: 'auto' },
  dot: { height: 4, borderRadius: 2 },
  observation: {
    fontSize: 14,
    fontWeight: '600',
    lineHeight: 20,
    marginTop: 10,
    letterSpacing: 0.1,
  },
});
