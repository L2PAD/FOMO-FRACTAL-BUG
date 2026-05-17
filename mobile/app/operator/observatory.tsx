/**
 * /operator/observatory — route entry to OperatorObservatoryScreen.
 *
 * Header pattern mirrors /operator/broker:
 *   [ ← Profile ]              [  FOMO logo  ]              [ Observatory ]
 *
 * Capability gating happens at the route level — the operator
 * observatory is a Trading-OS surface, so anyone without
 * `tradingOsVisible` lands on the RestrictedEnvironmentScreen
 * paywall/apply card instead of a raw 403 from the API client.
 *
 * `executionConsole` is the deeper gate the inner screen ultimately
 * enforces; route-level we use `tradingOsVisible` so a paper-tier
 * trader gets a clean explanation of why this view is operator-only.
 */
import React from 'react';
import { View, StyleSheet, TouchableOpacity, Text, Image, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { router, Stack } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import OperatorObservatoryScreen from '../../src/modules/operator/OperatorObservatoryScreen';
import { RestrictedEnvironmentScreen } from '../../src/modules/trading/_restricted/RestrictedEnvironmentScreen';
import { useColors } from '../../src/core/useColors';
import { usePreferencesStore } from '../../src/stores/preferences.store';
import { useCapabilities } from '../../src/stores/capabilities.store';

const LOGO_DARK = require('../../assets/images/logo-white.png');
const LOGO_LIGHT = require('../../assets/images/logo-black.png');

export default function ObservatoryRoute() {
  const colors = useColors();
  const insets = useSafeAreaInsets();
  const resolvedTheme = usePreferencesStore((s) => s.resolvedTheme);
  const logoSource = resolvedTheme === 'light' ? LOGO_LIGHT : LOGO_DARK;
  const { capabilities, loaded: capsLoaded } = useCapabilities();

  const goBack = () => {
    try { router.back(); } catch { router.replace('/'); }
  };

  // Wait for capabilities to resolve to avoid a flash of restricted state
  const showRestricted = capsLoaded && !capabilities.tradingOsVisible;

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerShown: false }} />

      <View style={[styles.headerWrap, {
        backgroundColor: colors.background,
        borderBottomColor: colors.border,
        paddingTop: insets.top + (Platform.OS === 'ios' ? 4 : 10),
      }]}>
        <TouchableOpacity
          onPress={goBack}
          style={styles.left}
          hitSlop={{ top: 14, bottom: 14, left: 14, right: 14 }}
          testID="observatory-back"
        >
          <Ionicons name="chevron-back" size={22} color={colors.textPrimary} />
          <Text style={[styles.backText, { color: colors.textPrimary }]} numberOfLines={1}>
            Profile
          </Text>
        </TouchableOpacity>

        <View style={styles.logoWrap} pointerEvents="none">
          <Image source={logoSource} style={styles.logo} resizeMode="contain" />
        </View>

        <View style={styles.right}>
          <Text
            style={[styles.routeLabel, { color: colors.textPrimary }]}
            numberOfLines={1}
            adjustsFontSizeToFit
            minimumFontScale={0.8}
          >
            Observatory
          </Text>
        </View>
      </View>

      <View style={{ flex: 1 }}>
        {showRestricted ? <RestrictedEnvironmentScreen /> : <OperatorObservatoryScreen />}
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
