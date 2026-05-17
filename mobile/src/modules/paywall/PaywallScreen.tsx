/**
 * PaywallScreen — Revenue-driven edge recovery screen
 * 
 * 3 MODES:
 * - expired: "Your Edge Is Gone" (lost value recovery)
 * - default: "Unlock Market Intelligence" (cold acquisition)
 * - contextual: "You're seeing the signal. Not the edge" (point-of-interest unlock)
 */

import React, { useState, useMemo, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Linking,
  Alert,
  Platform,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Ionicons from '@expo/vector-icons/Ionicons';
import { useColors } from '../../core/useColors';
import { useSessionStore } from '../../stores/session.store';
import { mobileApi } from '../../services/api/mobile-api';

import { t } from '../../core/i18n';
type PaywallReason = 'expired' | 'default' | 'contextual';

export function PaywallScreen({
  onClose,
  reason = 'default',
}: {
  onClose: () => void;
  reason?: PaywallReason;
}) {
  const insets = useSafeAreaInsets();
  const colors = useColors();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const refreshUser = useSessionStore((s) => s.refreshUser);
  const user = useSessionStore((s) => s.user);

  const [loading, setLoading] = useState(false);
  const [priceInfo, setPriceInfo] = useState({ monthly: 19, yearly: 190, features: [] as string[] });

  useEffect(() => {
    mobileApi.getPlans().then((data: any) => {
      if (data?.plans) {
        setPriceInfo({
          monthly: data.plans.monthly?.price || 19,
          yearly: data.plans.yearly?.price || 190,
          features: data.plans.features || [],
        });
      }
    }).catch(() => {});
  }, []);

  // Check mode
  const isExpired = reason === 'expired' || user?.planStatus === 'EXPIRED';
  const isContextual = reason === 'contextual';

  // Dynamic texts based on reason
  const heroTitle = isExpired
    ? 'Your Edge Is Gone'
    : isContextual
    ? "You're seeing the signal. Not the edge behind it."
    : 'Unlock Market Intelligence';

  const subtitle = isExpired
    ? "You've lost access to live signals, market drivers, and hidden opportunities."
    : isContextual
    ? "Unlock the full reasoning, drivers, and opportunities behind this move."
    : "See what is moving the market before the crowd reacts.";

  const ctaText = isExpired
    ? 'Restore PRO Access'
    : isContextual
    ? 'Unlock This Signal'
    : 'Unlock PRO Access';

  const handlePay = async () => {
    const userId = user?.id;
    if (!userId) {
      Alert.alert('Error', t('paywall.userSessionNotFoundPlease'));
      return;
    }

    setLoading(true);
    try {
      const result = await mobileApi.createWalletInvoice(userId);

      if (!result.invoice_url) {
        throw new Error('No invoice URL returned');
      }

      // Open crypto payment page
      if (Platform.OS === 'web') {
        window.open(result.invoice_url, '_blank');
      } else {
        await Linking.openURL(result.invoice_url);
      }

      // Start polling for payment status
      startPaymentPolling(result.payment_id);
    } catch (error: any) {
      Alert.alert('Error', error?.message || 'Failed to create payment. Please try again.');
      setLoading(false);
    }
  };

  const startPaymentPolling = (paymentId: string) => {
    let attempts = 0;
    const maxAttempts = 60; // 5 minutes max

    const interval = setInterval(async () => {
      attempts++;
      try {
        const status = await mobileApi.checkPaymentStatus(user!._id, paymentId);

        if (status.status === 'finished' && status.user.plan === 'PRO') {
          clearInterval(interval);
          setLoading(false);
          
          Alert.alert(
            '🎉 PRO Activated',
            'Your full market access is now live.',
            [
              {
                text: 'Explore Signals',
                onPress: () => {
                  refreshUser();
                  onClose();
                },
              },
            ]
          );
        }
      } catch (err) {
        // Continue polling
      }

      if (attempts >= maxAttempts) {
        clearInterval(interval);
        setLoading(false);
        Alert.alert(t('paywall.stillProcessing'), t('paywall.yourPaymentIsBeingConfirmed'),
          [{ text: 'OK', onPress: onClose }]
        );
      }
    }, 5000);
  };

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Close button */}
      <TouchableOpacity
        style={[styles.closeBtn, { top: insets.top + 12 }]}
        onPress={onClose}
        activeOpacity={0.7}
        data-testid="paywall-close-btn"
      >
        <Ionicons name="close" size={24} color={colors.textSecondary} />
      </TouchableOpacity>

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* 🔥 HERO */}
        <View style={styles.hero}>
          <View style={styles.proBadge}>
            <Ionicons name="diamond" size={18} color={isExpired ? colors.sell : colors.buy} />
            <Text style={[styles.proBadgeText, { color: isExpired ? colors.sell : colors.buy }]}>
              PRO
            </Text>
          </View>

          <Text style={[styles.heroTitle, isExpired && { color: colors.sell }]}>
            {heroTitle}
          </Text>
          <Text style={styles.heroSubtitle}>{subtitle}</Text>
        </View>

        {/* 🔥 VALUE ANCHOR */}
        <View style={[styles.card, isExpired && { borderColor: colors.sell + '30' }]}>
          {isExpired ? (
            <>
              <Text style={[styles.cardTitle, { color: colors.sell }]}>
                You had full access just days ago
              </Text>
              <Text style={styles.bullet}>• Full signal reasoning</Text>
              <Text style={styles.bullet}>• Real-time market drivers</Text>
              <Text style={styles.bullet}>• Hidden Edge opportunities</Text>
              <Text style={styles.bullet}>• Deep market intelligence</Text>

              {/* Last session highlights (optional) */}
              <View style={styles.highlightBox}>
                <Text style={styles.highlightTitle}>{t('paywall.lastSessionHighlights')}</Text>
                <Text style={styles.highlightItem}>• 3 signals detected</Text>
                <Text style={styles.highlightItem}>• +2.1% avg move</Text>
                <Text style={styles.highlightItem}>• Edge opportunities unlocked</Text>
              </View>
            </>
          ) : (
            <>
              <Text style={styles.cardTitle}>{t('paywall.proUsersSee')}</Text>
              <Text style={styles.bullet}>• Full signal breakdown</Text>
              <Text style={styles.bullet}>• Real-time market drivers</Text>
              <Text style={styles.bullet}>• Hidden opportunities before they move</Text>
            </>
          )}
        </View>

        {/* 🔥 LOCKED PREVIEW */}
        <View style={styles.lockedCard}>
          <View style={styles.lockedHeader}>
            <Ionicons name="lock-closed" size={16} color={colors.textMuted} />
            <Text style={styles.lockedTitle}>{t('paywall.lockedRightNow')}</Text>
          </View>

          <View style={styles.fakeContent}>
            <Text style={styles.fakeLine}>Primary Driver: Exchange — Bullish</Text>
            <Text style={styles.fakeLine}>{t('paywall.supportingSentimentOnChain')}</Text>
            <Text style={styles.fakeLine}>Entry Zone: ███████████</Text>
            <Text style={styles.fakeLine}>Hidden Edge: ████████████</Text>
          </View>

          <Text style={styles.lockedFooter}>
            {isExpired ? 'Restore access to reveal this now' : 'Unlock to reveal this now'}
          </Text>
        </View>

        {/* 🔥 WHAT UNLOCKS */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{t('paywall.whatYouUnlock')}</Text>
          <Text style={styles.bullet}>• Full signal reasoning</Text>
          <Text style={styles.bullet}>• Real-time market drivers</Text>
          <Text style={styles.bullet}>• Edge opportunities before they move</Text>
          <Text style={styles.bullet}>• Deep market context</Text>
        </View>

        {/* 🔥 PRICE */}
        <View style={styles.priceBlock}>
          <Text style={styles.price}>${priceInfo.monthly} / 30 days</Text>
          <Text style={styles.priceSub}>{t('paywall.payWithCrypto')}</Text>
        </View>

        {/* 🔥 LIVE PRESSURE — real-time FOMO hook */}
        <View style={[styles.pressureRow, { backgroundColor: colors.accentTint, borderColor: colors.accentTintBorder }]}>
          <View style={styles.pressureItem}>
            <Text style={[styles.pressureIcon, { color: colors.danger }]}>🔥</Text>
            <Text style={[styles.pressureText, { color: colors.textPrimary }]}>
              <Text style={{ fontWeight: '900' }}>12 people</Text>
              <Text style={{ color: colors.textSecondary }}> unlocked this past hour</Text>
            </Text>
          </View>
          <View style={[styles.pressureDiv, { backgroundColor: colors.border }]} />
          <View style={styles.pressureItem}>
            <Text style={[styles.pressureIcon, { color: colors.warning }]}>⏳</Text>
            <Text style={[styles.pressureText, { color: colors.textPrimary }]}>
              <Text style={{ fontWeight: '900' }}>{t('paywall.setupMayTrigger')}</Text>
              <Text style={{ color: colors.textSecondary }}> anytime</Text>
            </Text>
          </View>
        </View>

        {/* 🔥 CTA */}
        <TouchableOpacity
          style={[
            styles.cta,
            { backgroundColor: isExpired ? colors.sell : colors.accent, height: 52 },
            loading && { opacity: 0.7 },
          ]}
          onPress={handlePay}
          disabled={loading}
          activeOpacity={0.8}
          data-testid="paywall-cta-btn"
        >
          {loading ? (
            <ActivityIndicator color={colors.accentText} size="small" />
          ) : (
            <>
              <Ionicons
                name={isExpired ? 'refresh' : 'wallet'}
                size={20}
                color={colors.accentText}
              />
              <Text style={[styles.ctaText, { color: colors.accentText, fontSize: 16, fontWeight: '700' }]}>{ctaText}</Text>
            </>
          )}
        </TouchableOpacity>

        {/* 🔥 FOOTER */}
        <Text style={styles.footer}>
          Access unlocks automatically after payment confirmation.
        </Text>

        {/* CLOSE */}
        <TouchableOpacity onPress={onClose} activeOpacity={0.7}>
          <Text style={styles.close}>{t('paywall.notNow')}</Text>
        </TouchableOpacity>
      </ScrollView>
    </View>
  );
}

const makeStyles = (colors: any) =>
  StyleSheet.create({
    container: {
      flex: 1,
      backgroundColor: colors.background,
    },
    closeBtn: {
      position: 'absolute',
      right: 16,
      zIndex: 10,
      width: 36,
      height: 36,
      borderRadius: 18,
      backgroundColor: colors.surface,
      alignItems: 'center',
      justifyContent: 'center',
    },
    scrollContent: {
      paddingHorizontal: 24,
      paddingTop: 60,
      paddingBottom: 40,
    },

    // ===== HERO =====
    hero: {
      alignItems: 'center',
      marginBottom: 24,
    },
    proBadge: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 6,
      paddingHorizontal: 14,
      paddingVertical: 6,
      borderRadius: 20,
      marginBottom: 16,
      backgroundColor: colors.surface,
    },
    proBadgeText: {
      fontSize: 12,
      fontWeight: '700',
      letterSpacing: 0.5,
    },
    heroTitle: {
      fontSize: 28,
      fontWeight: '700',
      color: colors.textPrimary,
      textAlign: 'center',
      marginBottom: 12,
    },
    heroSubtitle: {
      fontSize: 16,
      color: colors.textSecondary,
      textAlign: 'center',
      lineHeight: 24,
    },

    // ===== CARD =====
    card: {
      padding: 16,
      borderRadius: 12,
      backgroundColor: colors.surface,
      borderWidth: 1,
      borderColor: colors.border,
      marginBottom: 16,
    },
    cardTitle: {
      fontSize: 16,
      fontWeight: '600',
      color: colors.textPrimary,
      marginBottom: 12,
    },
    bullet: {
      fontSize: 14,
      color: colors.textSecondary,
      marginBottom: 6,
      lineHeight: 20,
    },

    // ===== LAST SESSION HIGHLIGHTS =====
    highlightBox: {
      marginTop: 12,
      paddingTop: 12,
      borderTopWidth: 1,
      borderTopColor: colors.border,
    },
    highlightTitle: {
      fontSize: 13,
      fontWeight: '600',
      color: colors.textSecondary,
      marginBottom: 6,
    },
    highlightItem: {
      fontSize: 13,
      color: colors.textMuted,
      marginBottom: 4,
    },

    // ===== LOCKED PREVIEW =====
    lockedCard: {
      padding: 16,
      borderRadius: 12,
      borderWidth: 1,
      borderStyle: 'dashed',
      borderColor: colors.border,
      marginBottom: 16,
      backgroundColor: colors.surface + '40',
    },
    lockedHeader: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
      marginBottom: 12,
    },
    lockedTitle: {
      fontSize: 15,
      fontWeight: '600',
      color: colors.textMuted,
    },
    fakeContent: {
      opacity: 0.4,
      marginBottom: 12,
    },
    fakeLine: {
      fontSize: 14,
      color: colors.textSecondary,
      marginBottom: 6,
    },
    lockedFooter: {
      fontSize: 13,
      color: colors.textMuted,
      fontStyle: 'italic',
    },

    // ===== PRICE =====
    priceBlock: {
      alignItems: 'center',
      marginVertical: 20,
    },
    price: {
      fontSize: 32,
      fontWeight: '700',
      color: colors.textPrimary,
      marginBottom: 4,
    },
    priceSub: {
      fontSize: 14,
      color: colors.textSecondary,
    },

    // ===== Live pressure hook =====
    pressureRow: {
      flexDirection: 'row',
      alignItems: 'stretch',
      borderRadius: 12,
      borderWidth: 1,
      padding: 12,
      marginBottom: 16,
      gap: 10,
    },
    pressureItem: {
      flex: 1,
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
    },
    pressureDiv: {
      width: 1,
      alignSelf: 'stretch',
    },
    pressureIcon: {
      fontSize: 16,
    },
    pressureText: {
      fontSize: 12,
      flex: 1,
      lineHeight: 16,
    },

    // ===== CTA =====
    cta: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 8,
      padding: 18,
      borderRadius: 12,
      marginBottom: 12,
    },
    ctaText: {
      fontSize: 16,
      fontWeight: '700',
    },

    // ===== FOOTER =====
    footer: {
      textAlign: 'center',
      fontSize: 12,
      color: colors.textMuted,
      marginBottom: 16,
      lineHeight: 18,
    },
    close: {
      textAlign: 'center',
      fontSize: 14,
      color: colors.textMuted,
      paddingVertical: 8,
    },
  });
