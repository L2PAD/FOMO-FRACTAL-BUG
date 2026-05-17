/**
 * SignalStateBadge — Unified signal state indicator
 *
 * Resolves (stage, action, direction) into ONE of 3 states:
 *   🟡 FORMING NOW  — pulse, building pressure (yellow)
 *   🟢 CONFIRMED    — solid, entry ready (green)
 *   🔴 BREAKING DOWN — solid + subtle glow (red)
 *
 * Uses theme tokens ONLY (no hardcoded #fff / #000).
 */

import React, { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, Animated } from 'react-native';
import { useColors } from '../core/useColors';
import { t } from '../core/i18n';

export type SignalStage =
  | 'EARLY'
  | 'FORMING'
  | 'CONFIRMING'
  | 'SIGNAL'
  | 'CONFIRMED'
  | 'BREAKING_DOWN'
  | string
  | undefined;

export type SignalAction = 'BUY' | 'SELL' | 'WAIT' | string;

type ResolvedState = 'FORMING' | 'CONFIRMED' | 'BREAKING';

interface Props {
  stage?: SignalStage;
  action?: SignalAction;
  direction?: string; // Bullish | Bearish | Neutral
  isActive?: boolean; // set true if signal is currently live
  timelineText?: string;
  compact?: boolean; // smaller badge for signal cards / feed
}

export function resolveSignalState(args: {
  stage?: SignalStage;
  action?: SignalAction;
  direction?: string;
}): ResolvedState {
  const { stage, action, direction } = args;
  const st = String(stage || '').toUpperCase();
  const act = String(action || '').toUpperCase();
  const dir = String(direction || '').toLowerCase();

  // Explicit breaking-down state wins
  if (st === 'BREAKING_DOWN' || st === 'BREAKING' || st === 'INVALIDATED') return 'BREAKING';

  // Confirmed = backend SIGNAL/CONFIRMED stage AND actionable verdict
  if ((st === 'SIGNAL' || st === 'CONFIRMED') && (act === 'BUY' || act === 'SELL')) {
    // SELL + bearish = treat as BREAKING DOWN for emotional weight
    if (act === 'SELL' && (dir === 'bearish' || !dir)) return 'BREAKING';
    return 'CONFIRMED';
  }

  // Forming / confirming / early / WAIT = pressure building
  return 'FORMING';
}

export default function SignalStateBadge({
  stage,
  action,
  direction,
  isActive = true,
  timelineText,
  compact = false,
}: Props) {
  const colors = useColors();
  const pulseAnim = useRef(new Animated.Value(0)).current;

  const state = resolveSignalState({ stage, action, direction });

  // Pulse animation only for FORMING state
  useEffect(() => {
    if (state !== 'FORMING' || !isActive) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 1, duration: 900, useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 0, duration: 900, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [state, isActive, pulseAnim]);

  const meta = (() => {
    if (state === 'CONFIRMED') {
      return {
        label: t('stage.confirmed'),
        color: colors.buy,
        bg: colors.buy + '1A',
        border: colors.buy + '33',
        dot: colors.buy,
      };
    }
    if (state === 'BREAKING') {
      return {
        label: t('stage.weakening'),
        color: colors.sell,
        bg: colors.sell + '1A',
        border: colors.sell + '33',
        dot: colors.sell,
      };
    }
    return {
      label: t('stage.forming'),
      color: colors.wait,
      bg: colors.wait + '1A',
      border: colors.wait + '33',
      dot: colors.wait,
    };
  })();

  const pulseScale = pulseAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 2.6],
  });
  const pulseOpacity = pulseAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [0.55, 0],
  });

  const dotSize = compact ? 6 : 7;
  const padH = compact ? 8 : 10;
  const padV = compact ? 3 : 4;
  const fontSize = compact ? 10 : 11;

  return (
    <View style={styles.wrap}>
      <View
        style={[
          styles.badge,
          {
            backgroundColor: meta.bg,
            borderColor: meta.border,
            paddingHorizontal: padH,
            paddingVertical: padV,
          },
        ]}
      >
        <View style={[styles.dotHost, { width: dotSize, height: dotSize }]}>
          {state === 'FORMING' && isActive && (
            <Animated.View
              style={[
                styles.pulseRing,
                {
                  width: dotSize,
                  height: dotSize,
                  borderRadius: dotSize / 2,
                  backgroundColor: meta.dot,
                  transform: [{ scale: pulseScale }],
                  opacity: pulseOpacity,
                },
              ]}
            />
          )}
          <View
            style={[
              styles.dotCore,
              {
                width: dotSize,
                height: dotSize,
                borderRadius: dotSize / 2,
                backgroundColor: meta.dot,
              },
            ]}
          />
        </View>
        <Text
          style={[
            styles.label,
            { color: meta.color, fontSize, letterSpacing: compact ? 1 : 1.3 },
          ]}
        >
          {meta.label}
        </Text>
      </View>

      {!!timelineText && (
        <Text style={[styles.timeline, { color: colors.textMuted, fontSize }]}>
          {timelineText}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    alignSelf: 'flex-start',
  },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderRadius: 8,
    borderWidth: 1,
  },
  dotHost: {
    position: 'relative',
    alignItems: 'center',
    justifyContent: 'center',
  },
  pulseRing: {
    position: 'absolute',
  },
  dotCore: {
    // solid dot, drawn above the pulse ring
  },
  label: {
    fontWeight: '800',
  },
  timeline: {
    fontWeight: '500',
  },
});
