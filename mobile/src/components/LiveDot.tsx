/**
 * LiveDot — tiny pulsing dot for "system is watching" / "live monitoring" indicators.
 * Pure visual, no logic. Uses theme tokens for the color (defaults to colors.buy).
 */

import React, { useEffect, useRef } from 'react';
import { View, Animated, StyleSheet } from 'react-native';
import { useColors } from '../core/useColors';

interface Props {
  color?: string;
  size?: number;
  colors?: any; // allow passing resolved colors from parent to save one hook call
}

export default function LiveDot({ color, size = 6, colors: passedColors }: Props) {
  const defaultColors = useColors();
  const colors = passedColors || defaultColors;
  const c = color || colors.buy;
  const pulseAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 1, duration: 1100, useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 0, duration: 1100, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [pulseAnim]);

  const scale = pulseAnim.interpolate({ inputRange: [0, 1], outputRange: [1, 2.4] });
  const opacity = pulseAnim.interpolate({ inputRange: [0, 1], outputRange: [0.55, 0] });

  return (
    <View
      style={[
        styles.host,
        { width: size, height: size },
      ]}
    >
      <Animated.View
        style={[
          styles.ring,
          {
            width: size,
            height: size,
            borderRadius: size / 2,
            backgroundColor: c,
            opacity,
            transform: [{ scale }],
          },
        ]}
      />
      <View
        style={{
          width: size,
          height: size,
          borderRadius: size / 2,
          backgroundColor: c,
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  host: { position: 'relative', alignItems: 'center', justifyContent: 'center' },
  ring: { position: 'absolute' },
});
