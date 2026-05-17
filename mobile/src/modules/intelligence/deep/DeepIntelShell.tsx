import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppMode, DeepIntelModule } from '../../../stores/app-mode.store';
import { theme } from '../../../core/theme';
import { useColors } from '../../../core/useColors';
import { ExchangeIntelScreen } from './ExchangeIntelScreen';
import { OnchainIntelScreen } from './OnchainIntelScreen';
import { SentimentIntelScreen } from './SentimentIntelScreen';
import { FractalIntelScreen } from './FractalIntelScreen';
import { AssetIntelligenceScreen } from '../assets/AssetIntelligenceScreen';

const MODULE_CONFIG_FACTORY = (colors: any): Record<string, { title: string; icon: keyof typeof Ionicons.glyphMap; color: string }> => ({
  exchange: { title: 'EXCHANGE INTELLIGENCE', icon: 'bar-chart', color: colors.buy },
  onchain: { title: 'ON-CHAIN INTELLIGENCE', icon: 'link', color: '#2FE6A6' },
  sentiment: { title: 'SENTIMENT INTELLIGENCE', icon: 'chatbubbles', color: colors.neutral },
  fractal: { title: 'FRACTAL INTELLIGENCE', icon: 'git-network', color: colors.accent },
});

export function DeepIntelShell() {
  const colors = useColors();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);
  const MODULE_CONFIG = React.useMemo(() => MODULE_CONFIG_FACTORY(colors), [colors]);

  const { deepIntelModule, setDeepIntelModule } = useAppMode();

  if (!deepIntelModule) return null;

  // Asset Intelligence has its own header/back navigation
  if (deepIntelModule === 'asset-intel') {
    return <AssetIntelligenceScreen />;
  }

  const config = MODULE_CONFIG[deepIntelModule];

  const handleBack = () => {
    setDeepIntelModule(null);
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={handleBack} style={styles.backButton}>
          <Ionicons name="chevron-back" size={24} color={colors.textPrimary} />
        </TouchableOpacity>
        <View style={styles.headerCenter}>
          <Ionicons name={config.icon} size={16} color={config.color} />
          <Text style={[styles.headerTitle, { color: config.color }]}>{config.title}</Text>
        </View>
        <View style={{ width: 40 }} />
      </View>

      {/* Screen Content */}
      {deepIntelModule === 'exchange' && <ExchangeIntelScreen />}
      {deepIntelModule === 'onchain' && <OnchainIntelScreen />}
      {deepIntelModule === 'sentiment' && <SentimentIntelScreen />}
      {deepIntelModule === 'fractal' && <FractalIntelScreen />}
    </View>
  );
}

const makeStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: theme.spacing.md,
    paddingVertical: Platform.OS === 'web' ? 10 : 8,
    backgroundColor: colors.background,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backButton: {
    padding: theme.spacing.xs,
    width: 40,
  },
  headerCenter: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  headerTitle: {
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1,
  },
});
