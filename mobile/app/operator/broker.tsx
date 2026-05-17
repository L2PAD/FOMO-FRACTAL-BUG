/**
 * /operator/broker — route entry to BrokerScreen.
 *
 * Header layout (consistent with IntelligenceHeader / TradingHeader):
 *   [ ← Profile ]              [  FOMO logo  ]              [ Broker Bridge ]
 *
 * SAFE MODE pill removed from header — duplicated info, already shown on
 * the BROKER BRIDGE card just below. Logo size matches main app headers.
 */
import React from 'react';
import { View, StyleSheet, TouchableOpacity, Text, Image, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { router, Stack } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { BrokerScreen } from '../../src/modules/trading/broker/BrokerScreen';
import { RestrictedEnvironmentScreen } from '../../src/modules/trading/_restricted/RestrictedEnvironmentScreen';
import { useColors } from '../../src/core/useColors';
import { usePreferencesStore } from '../../src/stores/preferences.store';
import { useCapabilities } from '../../src/stores/capabilities.store';

const LOGO_DARK = require('../../assets/images/logo-white.png');
const LOGO_LIGHT = require('../../assets/images/logo-black.png');

export default function BrokerRoute() {
  const colors = useColors();
  const insets = useSafeAreaInsets();
  const resolvedTheme = usePreferencesStore((s) => s.resolvedTheme);
  const logoSource = resolvedTheme === 'light' ? LOGO_LIGHT : LOGO_DARK;
  const { capabilities, loaded: capsLoaded } = useCapabilities();

  const goBack = () => {
    try { router.back(); } catch { router.replace('/'); }
  };

  // TIER-2 gate at the route level — anyone without tradingOsVisible
  // lands on the apply/restricted card instead of a raw 403 banner.
  const showRestricted = capsLoaded && !capabilities.tradingOsVisible;

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerShown: false }} />

      <View style={[styles.headerWrap, {
        backgroundColor: colors.background,
        borderBottomColor: colors.border,
        paddingTop: insets.top + (Platform.OS === 'ios' ? 4 : 10),
      }]}>
        {/* Left: back chevron + Profile label */}
        <TouchableOpacity
          onPress={goBack}
          style={styles.left}
          hitSlop={{ top: 14, bottom: 14, left: 14, right: 14 }}
          testID="broker-back"
        >
          <Ionicons name="chevron-back" size={22} color={colors.textPrimary} />
          <Text style={[styles.backText, { color: colors.textPrimary }]} numberOfLines={1}>
            Profile
          </Text>
        </TouchableOpacity>

        {/* Center: brand logo (consistent with IntelligenceHeader/TradingHeader) */}
        <View style={styles.logoWrap} pointerEvents="none">
          <Image source={logoSource} style={styles.logo} resizeMode="contain" />
        </View>

        {/* Right: route label */}
        <View style={styles.right}>
          <Text
            style={[styles.routeLabel, { color: colors.textPrimary }]}
            numberOfLines={1}
            adjustsFontSizeToFit
            minimumFontScale={0.8}
          >
            Broker Bridge
          </Text>
        </View>
      </View>

      {/* Content */}
      <View style={{ flex: 1 }}>
        {showRestricted ? <RestrictedEnvironmentScreen /> : <BrokerScreen />}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  headerWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingBottom: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    minHeight: 52,
  },
  left: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
    width: 86,
    zIndex: 2,
  },
  backText: {
    fontSize: 15,
    fontWeight: '500',
  },
  logoWrap: {
    position: 'absolute',
    left: 96,
    right: 96,
    top: 0,
    bottom: 10,
    alignItems: 'center',
    justifyContent: 'flex-end',
  },
  logo: {
    height: 28,
    width: 110,
  },
  right: {
    marginLeft: 'auto',
    width: 96,
    alignItems: 'flex-end',
    zIndex: 2,
  },
  routeLabel: {
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
});
