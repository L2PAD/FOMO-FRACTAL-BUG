import React, { useMemo, useState, useEffect, useRef } from 'react';
import { View, Modal, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAppMode } from '../../stores/app-mode.store';
import { useSessionStore } from '../../stores/session.store';
import { IntelligenceBottomNav } from '../../widgets/navigation/IntelligenceBottomNav';
import { IntelligenceHeader } from '../../widgets/navigation/IntelligenceHeader';
import { HomeScreen } from '../../modules/intelligence/home/HomeScreen';
import { FeedScreen } from '../../modules/intelligence/feed/FeedScreen';
import { PortfolioIntelligenceScreen } from '../../modules/intelligence/feed/PortfolioIntelligenceScreen';
import { usePortfolioStore } from '../../stores/portfolio.store';
import { SignalsScreen } from '../../modules/intelligence/signals/SignalsScreen';
import { EdgeScreen } from '../../modules/intelligence/edge/EdgeScreen';
import { ProfileScreen } from '../../modules/intelligence/profile/ProfileScreen';
import { PaywallScreen } from '../../modules/paywall/PaywallScreen';
import { NotificationsScreen } from '../../modules/intelligence/notifications/NotificationsScreen';
import { NewsIntelligenceScreen } from '../../modules/intelligence/news/NewsIntelligenceScreen';
import { DeepIntelShell } from '../../modules/intelligence/deep/DeepIntelShell';
import { registerPaywallOpener, PaywallReason } from '../../utils/paywall-controller';
import { useColors } from '../useColors';

/** Wrapper: Feed or Portfolio Intelligence based on store state */
function FeedWithPortfolio() {
  const showIntel = usePortfolioStore((st) => st.showIntelScreen);
  if (showIntel) return <PortfolioIntelligenceScreen />;
  return <FeedScreen />;
}

export function IntelligenceShell() {
  const { intelTab, deepIntelModule } = useAppMode();
  const user = useSessionStore((s) => s.user);
  const colors = useColors();

  const [paywallVisible, setPaywallVisible] = useState(false);
  const [paywallReason, setPaywallReason] = useState<PaywallReason>('default');
  const [notificationsVisible, setNotificationsVisible] = useState(false);
  const [newsVisible, setNewsVisible] = useState(false);
  const [profileVisible, setProfileVisible] = useState(false);
  
  const expiredTriggerFired = useRef(false);

  useEffect(() => {
    registerPaywallOpener((reason) => {
      setPaywallReason(reason || 'default');
      setPaywallVisible(true);
    });
  }, []);

  // 🔥 AUTO PAYWALL TRIGGER - Aggressive re-activation on first load after expiry
  useEffect(() => {
    if (!user || expiredTriggerFired.current) return;

    const isExpired = user.planStatus === 'EXPIRED';
    
    if (isExpired) {
      // Check if recently expired (< 7 days)
      const expiredAt = user.subscription?.expiredAt;
      const now = new Date();
      const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      
      let recentlyExpired = true;
      if (expiredAt) {
        const expiredDate = new Date(expiredAt);
        recentlyExpired = expiredDate > sevenDaysAgo;
      }

      // 💣 TRIGGER: Open paywall immediately for recently expired users
      if (recentlyExpired) {
        expiredTriggerFired.current = true;
        setTimeout(() => {
          setPaywallReason('expired');
          setPaywallVisible(true);
        }, 1500); // Delay 1.5s to let app settle
      }
    }
  }, [user]);

  const renderScreen = () => {
    switch (intelTab) {
      case 'HOME': return <HomeScreen />;
      case 'FEED': return <FeedWithPortfolio />;
      case 'SIGNALS': return <SignalsScreen />;
      case 'EDGE': return <EdgeScreen />;
      default: return <HomeScreen />;
    }
  };

  // Deep Intel overlay replaces main content
  if (deepIntelModule) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
        <DeepIntelShell />
        <Modal visible={paywallVisible} animationType="slide" presentationStyle="pageSheet"
          onRequestClose={() => setPaywallVisible(false)}>
          <PaywallScreen onClose={() => setPaywallVisible(false)} reason={paywallReason} />
        </Modal>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
      {/* Main content layer — always rendered underneath */}
      {!profileVisible && !notificationsVisible && !newsVisible && (
        <>
          <IntelligenceHeader
            onBellPress={() => setNotificationsVisible(true)}
            onProfilePress={() => setProfileVisible(true)}
            onNewsPress={() => setNewsVisible(true)}
          />
          <View style={styles.content}>
            {renderScreen()}
          </View>
          <IntelligenceBottomNav />
        </>
      )}

      {/* Profile overlay */}
      {profileVisible && (
        <ProfileScreen onClose={() => setProfileVisible(false)} />
      )}

      {/* Notifications overlay */}
      {notificationsVisible && (
        <NotificationsScreen onClose={() => setNotificationsVisible(false)} />
      )}

      {/* News Intelligence overlay — full-screen, separate surface */}
      {newsVisible && (
        <NewsIntelligenceScreen onClose={() => setNewsVisible(false)} />
      )}

      {/* Paywall — always accessible as Modal from ANY overlay */}
      <Modal visible={paywallVisible} animationType="slide" presentationStyle="pageSheet"
        onRequestClose={() => setPaywallVisible(false)}>
        <PaywallScreen onClose={() => setPaywallVisible(false)} reason={paywallReason} />
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    flex: 1,
  },
});
