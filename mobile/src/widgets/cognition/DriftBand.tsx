/**
 * DRIFT BAND  ·  shared cognition primitive
 *
 * Generalised version of PressureFieldDrift.  A horizontal band of N
 * states with a soft cursor that smoothly drifts (2.4s ease-in-out
 * cubic) when the active state changes.
 *
 * The cursor only moves when perception genuinely shifts.  No looping.
 *
 * Used by:
 *   · Market    → "FIELD DRIFT"   (quiet → compressing → unstable → expanding)
 *   · Portfolio → "CAPITAL DRIFT" (idle → waiting → protected → exposed)
 */
import React, { useEffect } from 'react';
import { View, Text, StyleSheet, LayoutChangeEvent } from 'react-native';
import Animated, {
  useSharedValue, useAnimatedStyle, withTiming,
} from 'react-native-reanimated';
import { lateralDrift } from './motion';

type Props = {
  /** Ordered states (left → right). */
  states: readonly string[];
  /** Currently active state. */
  current: string;
  /** Map state → theme color key (e.g. 'accent', 'sell', 'buy', 'warning'). */
  toneKeyMap: Record<string, string>;
  colors: any;
  /** Header small caps, e.g. "FIELD DRIFT" or "CAPITAL DRIFT". */
  headLabel: string;
  /** AI's prose interpretation of the current state. */
  description: string;
};

export function DriftBand({
  states, current, toneKeyMap, colors, headLabel, description,
}: Props) {
  const [bandWidth, setBandWidth] = React.useState(0);
  const cursor = useSharedValue(0);
  const idx = Math.max(0, states.indexOf(current));

  useEffect(() => {
    if (bandWidth <= 0) return;
    const seg = bandWidth / states.length;
    const target = seg * idx + seg / 2 - 7;
    cursor.value = withTiming(target, lateralDrift);
  }, [idx, bandWidth, cursor, states.length]);

  const cursorStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: cursor.value }],
  }));

  const onLayout = (e: LayoutChangeEvent) => setBandWidth(e.nativeEvent.layout.width);
  const tone = (colors as any)[toneKeyMap[current]] || colors.textMuted;

  return (
    <View
      style={[styles.wrap, { backgroundColor: colors.surface, borderColor: colors.border }]}
    >
      <View style={styles.headRow}>
        <Text style={[styles.label, { color: colors.textMuted }]}>{headLabel}</Text>
        <Text style={[styles.state, { color: tone }]}>{current}</Text>
      </View>

      <View style={styles.bandWrap} onLayout={onLayout}>
        <View style={styles.band}>
          {states.map((s) => {
            const c = (colors as any)[toneKeyMap[s]] || colors.textMuted;
            return (
              <View
                key={s}
                style={[
                  styles.bandSegment,
                  { backgroundColor: c + (s === current ? '40' : '14') },
                ]}
              />
            );
          })}
        </View>
        <Animated.View
          style={[
            styles.cursor,
            {
              backgroundColor: tone,
              shadowColor: tone,
            },
            cursorStyle,
          ]}
          pointerEvents="none"
        />
      </View>

      <View style={styles.legendRow}>
        {states.map((s) => (
          <Text
            key={s}
            style={[
              styles.legend,
              {
                color: s === current ? tone : colors.textMuted,
                fontWeight: s === current ? '900' as any : '600' as any,
              },
            ]}
          >
            {s}
          </Text>
        ))}
      </View>

      <Text style={[styles.desc, { color: colors.textPrimary }]}>
        AI reads: {description}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { borderRadius: 14, borderWidth: 1, padding: 14 },
  headRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  label: { fontSize: 9, fontWeight: '900', letterSpacing: 1.5 },
  state: { fontSize: 11, fontWeight: '900', letterSpacing: 1.2, textTransform: 'uppercase' },

  bandWrap: { marginTop: 12, height: 14, justifyContent: 'center' },
  band: {
    flexDirection: 'row',
    height: 4,
    borderRadius: 2,
    overflow: 'hidden',
  },
  bandSegment: { flex: 1, height: '100%' },
  cursor: {
    position: 'absolute',
    width: 14, height: 14, borderRadius: 7,
    top: 0, left: 0,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.55,
    shadowRadius: 8,
    elevation: 4,
  },

  legendRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 },
  legend: { fontSize: 9, letterSpacing: 0.6 },
  desc: { fontSize: 12, lineHeight: 17, marginTop: 10 },
});
