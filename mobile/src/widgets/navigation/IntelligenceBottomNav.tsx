import React, { useMemo } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppMode, IntelTab } from '../../stores/app-mode.store';
import { usePreferencesStore } from '../../stores/preferences.store';
import { getTheme } from '../../core/themes';
import { useT } from '../../core/i18n';
import { useCapabilities } from '../../stores/capabilities.store';

type TabConfig = {
  key: IntelTab;
  labelKey: string;
  icon: keyof typeof Ionicons.glyphMap;
  iconActive: keyof typeof Ionicons.glyphMap;
};

// Phase E1 — Narrative Convergence:
// "Signals" tab renamed to "Observations" (restraint vocabulary).
// The internal store key (IntelTab='SIGNALS') is preserved as a stable
// identifier so analytics / runtime contract stay intact. Only the
// user-visible label and icon semantics change.
const tabs: TabConfig[] = [
  { key: 'HOME', labelKey: 'nav.home', icon: 'home-outline', iconActive: 'home' },
  { key: 'FEED', labelKey: 'nav.feed', icon: 'pulse-outline', iconActive: 'pulse' },
  { key: 'SIGNALS', labelKey: 'nav.observations', icon: 'analytics-outline', iconActive: 'analytics' },
  { key: 'EDGE', labelKey: 'nav.edge', icon: 'diamond-outline', iconActive: 'diamond' },
];

export function IntelligenceBottomNav() {
  const { intelTab, setIntelTab, switchToTrading } = useAppMode();
  const resolvedTheme = usePreferencesStore((s) => s.resolvedTheme);
  const colors = useMemo(() => getTheme(resolvedTheme).colors, [resolvedTheme]);
  const t = useT();
  const { capabilities, loaded: capsLoaded } = useCapabilities();
  // Trade button visual state: locked when free / not yet authorized.
  // Tap still works — leads to RestrictedEnvironmentScreen where the user
  // can apply for operator access. Lock is a *signal*, not a barrier.
  const tradeLocked = capsLoaded && !capabilities.tradingOsVisible;

  return (
    <View style={[styles.container, {
      backgroundColor: colors.surface,
      borderTopColor: colors.border,
    }]}>
      {tabs.map((tab) => {
        const isActive = intelTab === tab.key;
        return (
          <TouchableOpacity
            key={tab.key}
            style={styles.tab}
            onPress={() => setIntelTab(tab.key)}
          >
            <Ionicons
              name={isActive ? tab.iconActive : tab.icon}
              size={22}
              color={isActive ? colors.accent : colors.textMuted}
            />
            <Text style={[
              styles.label,
              { color: isActive ? colors.accent : colors.textMuted },
              isActive && styles.labelActive,
            ]}>
              {t(tab.labelKey)}
            </Text>
            {isActive && <View style={[styles.activeIndicator, { backgroundColor: colors.accent }]} />}
          </TouchableOpacity>
        );
      })}
      
      {/* Trading Shell switch — bridge to trading workspace.
          Locked-styled for free users (no executionConsole). The tap still
          opens TradingShell → RestrictedEnvironmentScreen where they can
          apply. Visual lock = honest signal, not a paywall barrier. */}
      <TouchableOpacity
        style={styles.tab}
        onPress={switchToTrading}
        testID="trade-nav-button"
      >
        <View style={styles.iconWrap}>
          <Ionicons
            name={tradeLocked ? 'lock-closed' : 'swap-vertical-outline'}
            size={22}
            color={tradeLocked ? colors.textMuted : colors.accent}
          />
        </View>
        <Text style={[
          styles.label,
          { color: tradeLocked ? colors.textMuted : colors.accent },
          !tradeLocked && styles.labelActive,
        ]}>
          {t('nav.trade')}
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    borderTopWidth: 1,
    paddingBottom: Platform.OS === 'ios' ? 20 : 8,
    paddingTop: 8,
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 4,
    position: 'relative',
  },
  label: {
    fontSize: 10,
    marginTop: 2,
  },
  labelActive: {
    fontWeight: '600',
  },
  activeIndicator: {
    position: 'absolute',
    top: -8,
    width: 20,
    height: 2,
    borderRadius: 1,
  },
  iconWrap: {
    position: 'relative',
    alignItems: 'center',
    justifyContent: 'center',
  },
});
