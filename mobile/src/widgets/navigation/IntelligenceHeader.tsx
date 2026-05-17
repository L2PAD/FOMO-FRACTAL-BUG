import React, { useState, useMemo, useEffect } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Image } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAssetStore } from '../../stores/asset.store';
import { usePreferencesStore } from '../../stores/preferences.store';
import { useNotificationsStore } from '../../stores/notifications.store';
import { useAppMode } from '../../stores/app-mode.store';
import { hapticNotification } from '../../services/haptics.service';
import { getTheme } from '../../core/themes';
import { AssetSelectorModal } from '../../components/AssetSelectorModal';
import { AssetLogo } from '../../components/AssetLogo';

// Logo assets
const LOGO_DARK = require('../../../assets/images/logo-white.png');
const LOGO_LIGHT = require('../../../assets/images/logo-black.png');

interface Props {
  onBellPress?: () => void;
  onProfilePress?: () => void;
  onNewsPress?: () => void;
}

export function IntelligenceHeader({ onBellPress, onProfilePress, onNewsPress }: Props) {
  const insets = useSafeAreaInsets();
  const currentAsset = useAssetStore((s) => s.currentAsset);
  const [selectorOpen, setSelectorOpen] = useState(false);
  const resolvedTheme = usePreferencesStore((s) => s.resolvedTheme);
  const colors = useMemo(() => getTheme(resolvedTheme).colors, [resolvedTheme]);
  const unreadCount = useNotificationsStore((s) => s.unreadCount);
  const fetchUnreadCount = useNotificationsStore((s) => s.fetchUnreadCount);
  const { setDeepIntelModule } = useAppMode();

  const logoSource = resolvedTheme === 'light' ? LOGO_LIGHT : LOGO_DARK;

  // Poll unread count every 30s
  useEffect(() => {
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 30000);
    return () => clearInterval(interval);
  }, []);

  const badgeText = unreadCount > 99 ? '99+' : unreadCount > 0 ? String(unreadCount) : '';

  return (
    <>
      <View style={[styles.container, {
        paddingTop: insets.top + 8,
        backgroundColor: colors.background,
        borderBottomColor: colors.border,
      }]}>
        {/* Asset selector — left */}
        <TouchableOpacity
          style={[styles.assetBtn, {
            backgroundColor: colors.surface,
            borderColor: colors.border,
          }]}
          onPress={() => setSelectorOpen(true)}
          activeOpacity={0.7}
        >
          <AssetLogo
            symbol={currentAsset}
            size={16}
            fallback={(currentAsset || 'BTC').slice(0, 1)}
            style={styles.assetIcon}
          />
          <Text style={[styles.assetLabel, { color: colors.textPrimary }]}>{currentAsset}</Text>
          <Ionicons name="chevron-down" size={14} color={colors.textSecondary} />
        </TouchableOpacity>

        {/* Center logo */}
        <View style={styles.logoWrap}>
          <Image source={logoSource} style={styles.logo} resizeMode="contain" />
        </View>

        {/* Right actions — News + bell with badge + profile */}
        <View style={styles.rightActions}>
          <TouchableOpacity
            style={styles.iconButton}
            onPress={onNewsPress}
            activeOpacity={0.7}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            testID="header-news-btn"
          >
            <Ionicons name="reader-outline" size={19} color={colors.textSecondary} />
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.iconButton}
            onPress={onBellPress}
            activeOpacity={0.7}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            testID="header-notif-btn"
          >
            <Ionicons
              name={unreadCount > 0 ? 'notifications' : 'notifications-outline'}
              size={20}
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

      <AssetSelectorModal
        visible={selectorOpen}
        onClose={() => setSelectorOpen(false)}
        onOpenIntel={(symbol) => {
          setSelectorOpen(false);
          setDeepIntelModule('asset-intel');
        }}
      />
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingBottom: 10,
    borderBottomWidth: 1,
  },
  assetBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 7,
    borderWidth: 1,
    minWidth: 64,
  },
  assetIcon: {
    width: 16,
    height: 16,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  assetIconText: {
    fontSize: 8,
    fontWeight: '800',
  },
  assetLabel: {
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
  logoWrap: {
    position: 'absolute',
    left: 76,
    right: 76,
    alignItems: 'center',
    justifyContent: 'center',
    pointerEvents: 'none',
  },
  logo: {
    height: 28,
    width: 110,
  },
  rightActions: {
    flexDirection: 'row',
    gap: 2,
    minWidth: 60,
    justifyContent: 'flex-end',
    alignItems: 'center',
  },
  iconButton: {
    padding: 4,
    position: 'relative',
  },
  badge: {
    position: 'absolute',
    top: -2,
    right: -6,
    minWidth: 16,
    height: 16,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 3,
  },
  badgeText: {
    color: '#ffffff',
    fontSize: 9,
    fontWeight: '800',
    lineHeight: 12,
  },
});
