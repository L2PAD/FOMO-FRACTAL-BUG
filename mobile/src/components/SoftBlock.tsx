/**
 * SoftBlock — Interstitial after closing paywall
 * 
 * Shows after 1-2 meaningful actions on Home/Edge for expired users
 * Shown once per session
 */

import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Modal } from 'react-native';
import Ionicons from '@expo/vector-icons/Ionicons';
import { useColors } from '../core/useColors';
import { openPaywall } from '../utils/paywall-controller';

type SoftBlockProps = {
  visible: boolean;
  onClose: () => void;
};

export function SoftBlock({ visible, onClose }: SoftBlockProps) {
  const colors = useColors();

  const handleRestore = () => {
    onClose();
    openPaywall('expired');
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={[styles.card, { backgroundColor: colors.background, borderColor: colors.border }]}>
          {/* Icon */}
          <View style={[styles.iconCircle, { backgroundColor: colors.sell + '20' }]}>
            <Ionicons name="lock-closed" size={32} color={colors.sell} />
          </View>

          {/* Header */}
          <Text style={[styles.header, { color: colors.sell }]}>Your access is still locked</Text>

          {/* Subtitle */}
          <Text style={[styles.subtitle, { color: colors.textSecondary }]}>
            Restore PRO to continue with live signals and market drivers.
          </Text>

          {/* CTA */}
          <TouchableOpacity
            style={[styles.ctaButton, { backgroundColor: colors.sell }]}
            onPress={handleRestore}
            activeOpacity={0.8}
          >
            <Ionicons name="refresh" size={18} color={colors.background} />
            <Text style={[styles.ctaText, { color: colors.background }]}>Restore Access</Text>
          </TouchableOpacity>

          {/* Close */}
          <TouchableOpacity onPress={onClose} style={styles.closeButton} activeOpacity={0.7}>
            <Text style={[styles.closeText, { color: colors.textMuted }]}>Not now</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  card: {
    width: '100%',
    maxWidth: 340,
    padding: 24,
    borderRadius: 16,
    borderWidth: 1,
    alignItems: 'center',
  },
  iconCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  header: {
    fontSize: 20,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 12,
  },
  subtitle: {
    fontSize: 15,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 24,
  },
  ctaButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 16,
    paddingHorizontal: 24,
    borderRadius: 12,
    width: '100%',
    marginBottom: 12,
  },
  ctaText: {
    fontSize: 16,
    fontWeight: '700',
  },
  closeButton: {
    paddingVertical: 8,
  },
  closeText: {
    fontSize: 14,
  },
});
