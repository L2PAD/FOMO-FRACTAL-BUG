/**
 * TradingBottomNav — Operator Desk subsystem navigation.
 * Phase E1 — Narrative Convergence (2026-05-12)
 *
 *   PULSE ↺   COMMAND   STRUCTURE   DEPLOYMENT   EXPOSURE
 *   (exit)
 *
 * The first button is NOT a tab — it's a bridge that returns the user to the
 * analytical shell (Home / Feed / Observations / Edge / Context root nav).
 * The remaining 4 buttons are subsystem tabs.
 *
 * Naming history (DO NOT use these words in user-visible copy):
 *   FOMO       → Pulse        (was: fear-of-missing-out anchor, now: rhythm/cadence anchor)
 *   MARKET     → Structure    (frames market as structural object, not transactional venue)
 *   EXECUTION  → Deployment   (cognitive deployment of attention, not trade execution)
 *   PORTFOLIO  → Exposure     (risk/posture exposure, not P&L portfolio)
 *
 * Internal store keys (TradingTab='COMMAND'|'MARKET'|'EXECUTION'|'PORTFOLIO')
 * are preserved as stable identifiers so runtime contract / analytics /
 * invariant tests remain intact. Only the user-visible label changes.
 *
 * TRADE remains a deep screen reached from COMMAND (Strongest Alignment) or
 * STRUCTURE (candidate row). Not a tab.
 */
import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppMode, TradingTab } from '../../stores/app-mode.store';
import { useColors } from '../../core/useColors';
import { useT } from '../../core/i18n';

type TabConfig = {
  key: TradingTab;
  labelKey: string;
  icon: keyof typeof Ionicons.glyphMap;
  iconActive: keyof typeof Ionicons.glyphMap;
};

const tabs: TabConfig[] = [
  { key: 'COMMAND',   labelKey: 'desk.command',    icon: 'compass-outline',     iconActive: 'compass' },
  { key: 'MARKET',    labelKey: 'desk.structure',  icon: 'grid-outline',        iconActive: 'grid' },
  { key: 'EXECUTION', labelKey: 'desk.deployment', icon: 'flash-outline',       iconActive: 'flash' },
  { key: 'PORTFOLIO', labelKey: 'desk.exposure',   icon: 'pie-chart-outline',   iconActive: 'pie-chart' },
];

export function TradingBottomNav() {
  const tradingTab = useAppMode((s) => s.tradingTab);
  const setTradingTab = useAppMode((s) => s.setTradingTab);
  const switchToIntelligence = useAppMode((s) => s.switchToIntelligence);
  const colors = useColors();
  const t = useT();

  return (
    <View
      style={[
        styles.container,
        { backgroundColor: colors.surface, borderTopColor: colors.border },
      ]}
    >
      {/* FOMO RETURN — bridge back to analytical shell */}
      <TouchableOpacity
        testID="operator-desk-tab-pulse-exit"
        style={styles.tab}
        onPress={switchToIntelligence}
        activeOpacity={0.7}
      >
        <View style={styles.fomoIconWrap}>
          <Ionicons name="flame-outline" size={22} color={colors.accent} />
          <View style={[styles.exitDot, { backgroundColor: colors.accent, borderColor: colors.surface }]}>
            <Ionicons name="arrow-back" size={8} color={colors.background} />
          </View>
        </View>
        <Text style={[styles.label, styles.labelActive, { color: colors.accent }]} numberOfLines={1}>
          {t('desk.exit')}
        </Text>
      </TouchableOpacity>

      {/* 4 Operator Desk subsystem tabs */}
      {tabs.map((tab) => {
        const isActive = tradingTab === tab.key;
        const tint = isActive ? colors.accent : colors.textMuted;
        return (
          <TouchableOpacity
            key={tab.key}
            testID={`operator-desk-tab-${tab.key.toLowerCase()}`}
            style={styles.tab}
            onPress={() => setTradingTab(tab.key)}
            activeOpacity={0.7}
          >
            {isActive && (
              <View style={[styles.activeIndicator, { backgroundColor: colors.accent }]} />
            )}
            <Ionicons
              name={isActive ? tab.iconActive : tab.icon}
              size={22}
              color={tint}
            />
            <Text
              style={[
                styles.label,
                { color: tint },
                isActive && styles.labelActive,
              ]}
            >
              {t(tab.labelKey)}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    borderTopWidth: 1,
    paddingBottom: Platform.OS === 'ios' ? 20 : 8,
    paddingTop: 6,
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 4,
    position: 'relative',
  },
  activeIndicator: {
    position: 'absolute',
    top: 0,
    width: 28,
    height: 2,
    borderRadius: 1,
  },
  fomoIconWrap: {
    width: 22,
    height: 22,
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
  },
  exitDot: {
    position: 'absolute',
    top: -4,
    right: -6,
    width: 12,
    height: 12,
    borderRadius: 6,
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
  },
  label: { fontSize: 10, marginTop: 2 },
  labelActive: { fontWeight: '700' },
});
