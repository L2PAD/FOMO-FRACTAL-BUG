/**
 * INTENTION TRACK  ·  Iteration 3B · Command
 *
 *   DORMANT → OBSERVING → BUILDING → READY
 *
 * Visualises the AI's progression of intent over the 4 cognitive phases.
 * The marker smoothly drifts (2s ease-out cubic) to the active state.
 * Reached states are tinted; pending states are muted.
 *
 * Soft delta lines (e.g. "readiness +4 since last scan") are passed in
 * by the caller and emerge with a 700ms delayed FadeIn — single
 * appearance, then calm.
 *
 * No looping animations.
 */
import React, { useEffect } from 'react';
import { View, Text, StyleSheet, LayoutChangeEvent } from 'react-native';
import Animated, {
  useSharedValue, useAnimatedStyle, withTiming,
} from 'react-native-reanimated';
import { softEntry, slowEmergence, intentionStep } from './motion';

type Props = {
  /** Ordered states. e.g. ['DORMANT','OBSERVING','BUILDING','READY']. */
  states: readonly string[];
  /** Active state. */
  current: string;
  /** Map state → theme color key. */
  toneKeyMap: Record<string, string>;
  colors: any;
  headLabel: string;
  /** Verb describing the active phase (e.g. 'alignment forming · convictions assembling'). */
  caption: string;
  /** Soft deltas — emerge one by one. e.g. ['readiness +4 since last scan']. */
  deltas?: string[];
};

export function IntentionTrack({
  states, current, toneKeyMap, colors, headLabel, caption, deltas = [],
}: Props) {
  const [trackW, setTrackW] = React.useState(0);
  const marker = useSharedValue(0);
  const idx = Math.max(0, states.indexOf(current));
  const tone = (colors as any)[toneKeyMap[current]] || colors.accent;

  useEffect(() => {
    if (trackW <= 0) return;
    const step = trackW / Math.max(1, states.length - 1);
    const target = step * idx - 6; // 6 = half marker width
    marker.value = withTiming(target, intentionStep);
  }, [idx, trackW, marker, states.length]);

  const markerStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: marker.value }],
  }));

  const onLayout = (e: LayoutChangeEvent) => setTrackW(e.nativeEvent.layout.width);

  return (
    <View
      style={[styles.wrap, { backgroundColor: colors.surface, borderColor: colors.border }]}
    >
      <View style={styles.headRow}>
        <Text style={[styles.label, { color: colors.textMuted }]}>{headLabel}</Text>
        <Text style={[styles.state, { color: tone }]}>{current}</Text>
      </View>

      {/* track */}
      <View style={styles.trackWrap} onLayout={onLayout}>
        {/* base line */}
        <View style={[styles.line, { backgroundColor: colors.border }]} />
        {/* progress line up to current */}
        <View
          style={[
            styles.lineProgress,
            {
              backgroundColor: tone,
              width: `${(idx / Math.max(1, states.length - 1)) * 100}%`,
            },
          ]}
        />
        {/* dots */}
        <View style={styles.dotsRow}>
          {states.map((s, i) => {
            const reached = i <= idx;
            const c = reached ? ((colors as any)[toneKeyMap[s]] || tone) : colors.border;
            return (
              <View
                key={s}
                style={[
                  styles.dot,
                  {
                    backgroundColor: c,
                    opacity: reached ? 1 : 0.55,
                    borderColor: i === idx ? tone : 'transparent',
                  },
                ]}
              />
            );
          })}
        </View>
        {/* drifting marker */}
        <Animated.View
          style={[
            styles.marker,
            { backgroundColor: tone, shadowColor: tone },
            markerStyle,
          ]}
          pointerEvents="none"
        />
      </View>

      {/* labels */}
      <View style={styles.labelsRow}>
        {states.map((s, i) => (
          <Text
            key={s}
            style={[
              styles.stepLabel,
              {
                color: i === idx ? tone
                  : i < idx ? colors.textPrimary
                  : colors.textMuted,
                fontWeight: i === idx ? '900' as any : '700' as any,
                opacity: i <= idx ? 1 : 0.6,
              },
            ]}
          >
            {s}
          </Text>
        ))}
      </View>

      {/* caption */}
      <Animated.Text
        entering={softEntry()}
        style={[styles.caption, { color: colors.textPrimary }]}
      >
        AI is {caption}
      </Animated.Text>

      {/* soft deltas — emerge one by one */}
      {deltas.length > 0 && (
        <View style={styles.deltasWrap}>
          {deltas.map((d, i) => (
            <Animated.View
              key={`${current}-d-${i}`}
              entering={slowEmergence(900 + i * 1300)}
              style={styles.deltaRow}
            >
              <View style={[styles.deltaMark, { backgroundColor: tone + '70' }]} />
              <Text style={[styles.deltaText, { color: colors.textMuted }]}>{d}</Text>
            </Animated.View>
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { borderRadius: 14, borderWidth: 1, padding: 14 },
  headRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  label: { fontSize: 9, fontWeight: '900', letterSpacing: 1.5 },
  state: { fontSize: 11, fontWeight: '900', letterSpacing: 1.2 },

  trackWrap: { marginTop: 18, height: 18, justifyContent: 'center', paddingHorizontal: 6 },
  line: { position: 'absolute', left: 6, right: 6, height: 2, borderRadius: 1, top: 8 },
  lineProgress: { position: 'absolute', left: 6, height: 2, borderRadius: 1, top: 8 },
  dotsRow: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', height: 18,
  },
  dot: {
    width: 10, height: 10, borderRadius: 5,
    borderWidth: 2,
  },
  marker: {
    position: 'absolute',
    top: 3, left: 6,
    width: 14, height: 14, borderRadius: 7,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.5,
    shadowRadius: 8,
    elevation: 4,
  },

  labelsRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 6, paddingHorizontal: 0 },
  stepLabel: { fontSize: 9, letterSpacing: 0.6 },

  caption: { fontSize: 12, lineHeight: 17, marginTop: 12 },

  deltasWrap: { marginTop: 8, gap: 6 },
  deltaRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  deltaMark: { width: 4, height: 4, borderRadius: 2 },
  deltaText: { flex: 1, fontSize: 11, fontStyle: 'italic' },
});
