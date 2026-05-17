/**
 * LockedPreviewCard — Home-embedded lock state
 * 
 * Shows in HomeScreen for FREE/EXPIRED users
 * Creates tension → drives to paywall
 */

import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import Ionicons from '@expo/vector-icons/Ionicons';
import { useColors } from '../core/useColors';
import { openPaywall } from '../utils/paywall-controller';

type LockedPreviewProps = {
  mode: 'expired' | 'free';
};

export function LockedPreviewCard({ mode }: LockedPreviewProps) {
  const colors = useColors();

  const isExpired = mode === 'expired';

  const header = isExpired
    ? "Your Edge Is Gone"
    : "PRO users see what's driving this signal";

  const subtitle = isExpired
    ? "You've lost access to the signal drivers behind this move."
    : "Unlock the reasoning, drivers, and edge behind the move.";

  const ctaText = isExpired ? 'Restore PRO Access' : 'Unlock PRO';

  const handleUnlock = () => {
    openPaywall(isExpired ? 'expired' : 'default');
  };

  return (
    <View
      style={[
        styles.container,
        {
          backgroundColor: colors.surface,
          borderColor: isExpired ? colors.sell + '30' : colors.border,
        },
      ]}
    >
      {/* Header */}
      <View style={styles.header}>
        <Ionicons
          name={isExpired ? 'alert-circle' : 'lock-closed'}
          size={20}
          color={isExpired ? colors.sell : colors.textMuted}
        />
        <Text
          style={[
            styles.headerText,
            { color: isExpired ? colors.sell : colors.textPrimary },
          ]}
        >
          {header}
        </Text>
      </View>

      {/* Subtitle */}
      <Text style={[styles.subtitle, { color: colors.textSecondary }]}>
        {subtitle}
      </Text>

      {/* Locked Preview Box */}
      <View
        style={[
          styles.previewBox,
          {
            backgroundColor: colors.background,
            borderColor: colors.border,
          },
        ]}
      >
        <View style={styles.previewRow}>
          <Text style={[styles.previewLabel, { color: colors.textMuted }]}>
            Primary Driver:
          </Text>
          <Text style={[styles.previewValue, { color: colors.textMuted }]}>
            Exchange — ███████
          </Text>
        </View>
        <View style={styles.previewRow}>
          <Text style={[styles.previewLabel, { color: colors.textMuted }]}>
            Supporting:
          </Text>
          <Text style={[styles.previewValue, { color: colors.textMuted }]}>
            ███████████
          </Text>
        </View>
        <View style={styles.previewRow}>
          <Text style={[styles.previewLabel, { color: colors.textMuted }]}>
            Entry Zone:
          </Text>
          <Text style={[styles.previewValue, { color: colors.textMuted }]}>
            ███████████
          </Text>
        </View>
        <View style={styles.previewRow}>
          <Text style={[styles.previewLabel, { color: colors.textMuted }]}>
            Hidden Edge:
          </Text>
          <Text style={[styles.previewValue, { color: colors.textMuted }]}>
            ████████████
          </Text>
        </View>
      </View>

      {/* Footer text */}
      <Text style={[styles.footerText, { color: colors.textMuted }]}>
        {isExpired
          ? 'Restore access to reveal this now'
          : 'Unlock to reveal this now'}
      </Text>

      {/* CTA Button */}
      <TouchableOpacity
        style={[
          styles.ctaButton,
          { backgroundColor: isExpired ? colors.sell : colors.accent },
        ]}
        onPress={handleUnlock}
        activeOpacity={0.8}
      >
        <Ionicons
          name={isExpired ? 'refresh' : 'lock-open'}
          size={16}
          color={colors.background}
        />
        <Text style={[styles.ctaText, { color: colors.background }]}>
          {ctaText}
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    marginVertical: 16,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  headerText: {
    fontSize: 16,
    fontWeight: '700',
    flex: 1,
  },
  subtitle: {
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 16,
  },
  previewBox: {
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderStyle: 'dashed',
    marginBottom: 12,
    opacity: 0.5,
  },
  previewRow: {
    flexDirection: 'row',
    marginBottom: 6,
  },
  previewLabel: {
    fontSize: 13,
    width: 110,
  },
  previewValue: {
    fontSize: 13,
    flex: 1,
  },
  footerText: {
    fontSize: 12,
    fontStyle: 'italic',
    marginBottom: 12,
  },
  ctaButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 10,
  },
  ctaText: {
    fontSize: 15,
    fontWeight: '700',
  },
});
