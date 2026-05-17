import React, { useMemo, useState } from 'react';
import { View, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAppMode } from '../../stores/app-mode.store';
import { useCapabilities } from '../../stores/capabilities.store';
import { TradingBottomNav } from '../../widgets/navigation/TradingBottomNav';
import { TradingHeader } from '../../widgets/navigation/TradingHeader';
import { HomeScreen } from '../../modules/trading/home/HomeScreen';
import { MarketScreen } from '../../modules/trading/market/MarketScreen';
import { TradeScreen } from '../../modules/trading/trade/TradeScreen';
import { PortfolioScreen } from '../../modules/trading/portfolio/PortfolioScreen';
import { IntelligenceScreen } from '../../modules/trading/intelligence/IntelligenceScreen';
import { ProfileScreen } from '../../modules/intelligence/profile/ProfileScreen';
import { RestrictedEnvironmentScreen } from '../../modules/trading/_restricted/RestrictedEnvironmentScreen';
import { useColors } from '../useColors';

export function TradingShell() {
  const tradingTab = useAppMode((s) => s.tradingTab);
  const colors = useColors();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const [profileVisible, setProfileVisible] = useState(false);

  // Stage 0 capability gate.
  // The bottom-nav is rendered for ALL users so they can see the operational
  // environment exists.  The interior screens are ONLY rendered when the
  // user has `executionConsole` (operatorAccess.enabled && status==='approved').
  // Otherwise the user lands on RestrictedEnvironmentScreen — the semantic
  // seal between public intelligence and restricted operational cognition.
  const { capabilities, loaded: capsLoaded } = useCapabilities();
  const operatorAuthorized = capsLoaded && capabilities.executionConsole;

  const renderScreen = () => {
    if (!operatorAuthorized) {
      return <RestrictedEnvironmentScreen />;
    }
    switch (tradingTab) {
      case 'COMMAND':
        return <HomeScreen />;
      case 'MARKET':
        return <MarketScreen />;
      case 'EXECUTION':
        return <TradeScreen />;
      case 'TRADE':
        return <TradeScreen />;
      case 'PORTFOLIO':
        return <PortfolioScreen />;
      case 'INTELLIGENCE':
        return <IntelligenceScreen />;
      default:
        return <HomeScreen />;
    }
  };

  if (profileVisible) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <ProfileScreen onClose={() => setProfileVisible(false)} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <TradingHeader onProfilePress={() => setProfileVisible(true)} />
      <View style={styles.content}>{renderScreen()}</View>
      <TradingBottomNav />
    </SafeAreaView>
  );
}

const makeStyles = (colors: any) =>
  StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background },
    content: { flex: 1 },
  });
