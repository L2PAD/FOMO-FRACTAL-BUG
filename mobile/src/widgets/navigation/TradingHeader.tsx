/**
 * TradingHeader — Trading OS shell header (cohesion-pass v3).
 *
 * Topology mirrors IntelligenceHeader:
 *   left   · identity text "Trading OS"  (clean, no BETA badge)
 *   center · brand logo                  (same asset as Intelligence)
 *   right  · trading notifications · profile  (parity with Intelligence)
 *
 * No wallet chip in this pass.  Notifications icon is scoped to the
 * trading runtime — taps route to the same notification surface the
 * Intelligence shell uses (single source of truth for the user).
 */
import React, { useMemo } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Image } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useColors } from '../../core/useColors';
import { usePreferencesStore } from '../../stores/preferences.store';
import { useAppMode } from '../../stores/app-mode.store';
import { useT } from '../../core/i18n';

const LOGO_DARK = require('../../../assets/images/logo-white.png');
const LOGO_LIGHT = require('../../../assets/images/logo-black.png');

interface Props {
  onProfilePress?: () => void;
  onBellPress?: () => void;
  unreadCount?: number;
}

export function TradingHeader({ onProfilePress, onBellPress, unreadCount = 0 }: Props) {
  const colors = useColors();
  const insets = useSafeAreaInsets();
  const resolvedTheme = usePreferencesStore((s) => s.resolvedTheme);
  const logoSource = resolvedTheme === 'light' ? LOGO_LIGHT : LOGO_DARK;
  const styles = useMemo(() => makeStyles(colors, insets.top), [colors, insets.top]);
  const badgeText = unreadCount > 99 ? '99+' : String(unreadCount);
  const t = useT();
  const tradingTab = useAppMode((s) => s.tradingTab);
  const setTradingTab = useAppMode((s) => s.setTradingTab);
  const isIntel = tradingTab === 'INTELLIGENCE';

  return (
    <View style={styles.container}>
      {/* Left identity — Operator Desk (was: Trading OS) */}
      <View style={styles.left}>
        <Text style={styles.identity} numberOfLines={1}>{t('desk.title')}</Text>
      </View>

      {/* Center logo — shared brand anchor across shells */}
      <View style={styles.logoWrap} pointerEvents="none">
        <Image source={logoSource} style={styles.logo} resizeMode="contain" />
      </View>

      {/* Right actions — calibration · notifications · profile */}
      <View style={styles.right}>
        <TouchableOpacity
          style={styles.iconButton}
          onPress={() => setTradingTab(isIntel ? 'COMMAND' : 'INTELLIGENCE')}
          activeOpacity={0.7}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          testID="trading-header-intel-btn"
        >
          <Ionicons
            name={isIntel ? 'school' : 'school-outline'}
            size={19}
            color={isIntel ? colors.accent : colors.textSecondary}
          />
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.iconButton}
          onPress={onBellPress}
          activeOpacity={0.7}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          testID="trading-header-notif-btn"
        >
          <Ionicons
            name={unreadCount > 0 ? 'notifications' : 'notifications-outline'}
            size={19}
            color={unreadCount > 0 ? colors.accent : colors.textSecondary}
          />
          {unreadCount > 0 && (
            <View style={[styles.badge, { backgroundColor: colors.sell }]}>
              <Text style={styles.badgeText}>{badgeText}</Text>
            </View>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.iconButton}
          onPress={onProfilePress}
          activeOpacity={0.7}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <Ionicons name="person-circle-outline" size={22} color={colors.textSecondary} />
        </TouchableOpacity>
      </View>
    </View>
  );
}

const makeStyles = (colors: any, safeTop: number) =>
  StyleSheet.create({
    container: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingHorizontal: 14,
      paddingTop: safeTop + 8,
      paddingBottom: 10,
      backgroundColor: colors.background,
      borderBottomWidth: 1,
      borderBottomColor: colors.border,
    },
    left: {
      flexDirection: 'row',
      alignItems: 'center',
      minWidth: 80,
    },
    identity: {
      fontSize: 14,
      fontWeight: '700',
      color: colors.textPrimary,
      letterSpacing: 0.3,
    },
    logoWrap: {
      position: 'absolute',
      top: safeTop + 8,
      left: 80,
      right: 80,
      bottom: 8,
      alignItems: 'center',
      justifyContent: 'center',
    },
    logo: {
      height: 28,
      width: 110,
    },
    right: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 2,
      minWidth: 60,
      justifyContent: 'flex-end',
    },
    iconButton: {
      padding: 4,
      position: 'relative',
    },
    badge: {
      position: 'absolute',
      top: -2,
      right: -2,
      minWidth: 16,
      height: 16,
      borderRadius: 8,
      alignItems: 'center',
      justifyContent: 'center',
      paddingHorizontal: 3,
    },
    badgeText: {
      color: '#fff',
      fontSize: 9,
      fontWeight: '700',
      lineHeight: 12,
    },
  });
