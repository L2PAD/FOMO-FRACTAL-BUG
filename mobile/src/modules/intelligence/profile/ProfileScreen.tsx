import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
  Platform,
  Image,
  TextInput,
  Alert,
  Linking,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { hapticLight, hapticMedium } from '../../../services/haptics.service';
import { mobileApi } from '../../../services/api/mobile-api';
import { openPaywall } from '../../../utils/paywall-controller';
import { theme as staticTheme } from '../../../core/theme';
import { getTheme } from '../../../core/themes';
import { useColors } from '../../../core/useColors';
import { useT } from '../../../core/i18n';
import { useSessionStore } from '../../../stores/session.store';
import { useAssetStore } from '../../../stores/asset.store';
import { usePreferencesStore } from '../../../stores/preferences.store';
import { useAppMode } from '../../../stores/app-mode.store';
import { useCapabilities } from '../../../stores/capabilities.store';
import { router } from 'expo-router';
import { GrowthScreen } from './GrowthScreen';

function GrowthScreenEmbed() {
  return <GrowthScreen />;
}

// Sub-views
type ProfileView = 'main' | 'account' | 'subscription' | 'referrals' | 'preferences' | 'security' | 'connected' | 'notifications' | 'about';

interface ProfileData {
  id: string;
  email: string;
  name: string;
  avatarUrl?: string;
  plan: string;
  planStatus: string;
  memberSince: string;
  renewsAt: string;
  watchlist: string[];
  hasPassword: boolean;
  twoFactorEnabled: boolean;
  telegramUsername?: string;
  authProviders: { google: boolean; email: boolean; telegram: boolean };
  linkedApps: { web: boolean; miniapp: boolean; mobile: boolean };
  subscription: { plan: string; status: string; renewsAt: string; price: string };
  access: {
    miniSignals: boolean;
    fullSignals: boolean;
    fullIntel: boolean;
    edge: boolean;
    tradingPreview: boolean;
    tradingFull: boolean;
  };
  preferences: {
    defaultAsset: string;
    theme: string;
    language: string;
    notifications: boolean;
    startScreen: string;
    haptics: boolean;
    notificationSettings: Record<string, boolean>;
  };
  referrals: { code: string; invites: number; paidReferrals: number; earned: string };
  stats: { signalsViewed: number; edgeBetsPlaced: number; avgSessionMin: number };
}

// Haptic feedback via central service (respects preferences)
function doHaptic() {
  hapticLight();
}

// Format ISO date as compact "30 Apr '26" — fits a single line in stat tile.
function formatMember(iso?: string) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    const day = d.getDate();
    const mon = d.toLocaleDateString('en-US', { month: 'short' });
    const yy = String(d.getFullYear()).slice(-2);
    return `${day} ${mon} '${yy}`;
  } catch {
    return iso;
  }
}

/** Compact date for narrow stat tiles ("May '26") — never wraps. */
function formatMemberCompact(iso?: string) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '—';
    const mon = d.toLocaleDateString('en-US', { month: 'short' });
    const yy = String(d.getFullYear()).slice(-2);
    return `${mon} '${yy}`;
  } catch {
    return '—';
  }
}

export function ProfileScreen({ onClose }: { onClose?: () => void }) {
  const [data, setData] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [currentView, setCurrentView] = useState<ProfileView>('main');
  const clearSession = useSessionStore((s) => s.clearSession);
  const setCurrentAsset = useAssetStore((s) => s.setCurrentAsset);
  const colors = useColors();
  const t = useT();

  useEffect(() => {
    if (data?.preferences?.defaultAsset) {
      setCurrentAsset(data.preferences.defaultAsset);
    }
  }, [data?.preferences?.defaultAsset]);

  // Hydrate preferences store from profile data
  useEffect(() => {
    if (data?.preferences) {
      usePreferencesStore.getState().hydrateFromProfile(data.preferences);
    }
  }, [data]);

  const handleSignOut = () => {
    clearSession();
  };

  const fetchData = async () => {
    try {
      const result = await mobileApi.getProfile();
      setData(result as any);
    } catch (error: any) {
      // Any failure (401, 403, network error, refresh-token-missing) → guest mode
      console.log('[Profile] using guest fallback, reason:', error?.message || error);
      setData({
          id: 'guest',
          email: '',
          name: 'Guest',
          plan: 'FREE',
          planStatus: 'active',
          memberSince: new Date().toISOString(),
          renewsAt: '',
          watchlist: ['BTC', 'ETH', 'SOL'],
          hasPassword: false,
          twoFactorEnabled: false,
          authProviders: { google: false, email: false, telegram: false },
          linkedApps: { web: false, miniapp: false, mobile: true },
          subscription: { plan: 'FREE', status: 'active', renewsAt: '', price: '$0' },
          access: {
            miniSignals: true, fullSignals: false, fullIntel: false,
            edge: false, tradingPreview: true, tradingFull: false,
          },
          preferences: {
            defaultAsset: 'BTC',
            theme: usePreferencesStore.getState().themeMode || 'dark',
            language: 'en',
            notifications: true,
            startScreen: 'home',
            haptics: true,
            notificationSettings: {},
          },
          referrals: { code: '', invites: 0, paidReferrals: 0, earned: '$0' },
          stats: { signalsViewed: 0, edgeBetsPlaced: 0, avgSessionMin: 0 },
        } as any);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    doHaptic();
    await fetchData();
    setRefreshing(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, []);

  const navigateTo = (view: ProfileView) => {
    doHaptic();
    setCurrentView(view);
  };

  if (loading) {
    return (
      <View style={[styles.loadingContainer, { backgroundColor: colors.background }]}>
        <ActivityIndicator size="large" color={colors.accent} />
        <Text style={[styles.loadingText, { color: colors.textSecondary }]}>{t('loadingProfile')}</Text>
      </View>
    );
  }

  if (!data) {
    return (
      <View style={[styles.loadingContainer, { backgroundColor: colors.background }]}>
        <Text style={[styles.errorText, { color: colors.sell }]}>{t('failedProfile')}</Text>
      </View>
    );
  }

  if (currentView !== 'main') {
    return (
      <SubView
        view={currentView}
        data={data}
        onBack={() => setCurrentView('main')}
        onDataRefresh={fetchData}
      />
    );
  }

  const themeLabelMap: Record<string, string> = { dark: t('prefs.dark'), light: t('prefs.light'), system: t('prefs.system') };
  const themeLabel = themeLabelMap[data.preferences?.theme] || t('prefs.dark');

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: colors.background }]}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} colors={[colors.accent]} />
      }
    >
      {/* Back Button when opened from header */}
      {onClose && (
        <TouchableOpacity onPress={onClose} style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingTop: 8, paddingBottom: 4 }}>
          <Ionicons name="arrow-back" size={22} color={colors.accent} />
          <Text style={{ color: colors.accent, fontSize: 15, fontWeight: '600', marginLeft: 6 }}>{t('general.back')}</Text>
        </TouchableOpacity>
      )}
      {/* Profile Header */}
      <View style={[styles.profileHeader, { backgroundColor: colors.surface }]}>
        <TouchableOpacity style={styles.avatarContainer} onPress={async () => {
          try {
            const { launchImageLibraryAsync, MediaTypeOptions, requestMediaLibraryPermissionsAsync } = require('expo-image-picker');
            const { status } = await requestMediaLibraryPermissionsAsync();
            if (status !== 'granted') { Alert.alert('', t('account.photoPermission')); return; }
            const result = await launchImageLibraryAsync({ mediaTypes: MediaTypeOptions.Images, allowsEditing: true, aspect: [1, 1], quality: 0.5, base64: true });
            if (!result.canceled && result.assets[0]?.base64) {
              const b64 = `data:image/jpeg;base64,${result.assets[0].base64}`;
              const res = await mobileApi.uploadAvatar(b64);
              if (res.success) { fetchData(); }
            }
          } catch (e) { console.error('Avatar upload error:', e); }
        }} activeOpacity={0.7}>
          <View style={[styles.avatar, { backgroundColor: colors.surfaceHover, overflow: 'hidden' }]}>
            {data.avatarUrl ? (
              <Image source={{ uri: data.avatarUrl }} style={{ width: 60, height: 60, borderRadius: 30 }} />
            ) : (
              <Ionicons name="person" size={32} color={colors.textMuted} />
            )}
          </View>
          <View style={[styles.avatarEditBadge, { backgroundColor: colors.accent }]}>
            <Ionicons name="camera" size={10} color="#000" />
          </View>
          {data.planStatus === 'ACTIVE' && (
            <View style={[styles.statusDot, { backgroundColor: colors.buy, borderColor: colors.background }]} />
          )}
        </TouchableOpacity>
        <View style={styles.profileInfo}>
          <Text style={[styles.profileName, { color: colors.textPrimary }]}>{data.name}</Text>
          <Text style={[styles.profileEmail, { color: colors.textSecondary }]}>{data.email}</Text>
          <View style={[styles.planBadge, { backgroundColor: colors.accent + '20' }]}>
            <Text style={[styles.planBadgeText, { color: colors.accent }]}>{data.plan}</Text>
          </View>
        </View>
      </View>

      {/* Quick Stats */}
      <View style={[styles.statsRow, { backgroundColor: colors.surface }]}>
        <View style={styles.statItem}>
          <Text style={[styles.statValue, { color: colors.textPrimary }]} numberOfLines={1}>{data.stats.signalsViewed}</Text>
          <Text style={[styles.statLabel, { color: colors.textMuted }]} numberOfLines={1}>{t('profile.signals')}</Text>
        </View>
        <View style={[styles.statDivider, { backgroundColor: colors.border }]} />
        <View style={styles.statItem}>
          <Text style={[styles.statValue, { color: colors.textPrimary }]} numberOfLines={1}>{data.stats.edgeBetsPlaced}</Text>
          <Text style={[styles.statLabel, { color: colors.textMuted }]} numberOfLines={1}>{t('profile.edges')}</Text>
        </View>
        <View style={[styles.statDivider, { backgroundColor: colors.border }]} />
        <View style={styles.statItem}>
          <Text style={[styles.statValue, { color: colors.textPrimary }]} numberOfLines={1}>{data.stats.avgSessionMin}m</Text>
          <Text style={[styles.statLabel, { color: colors.textMuted }]} numberOfLines={1}>{t('profile.avgSession')}</Text>
        </View>
        <View style={[styles.statDivider, { backgroundColor: colors.border }]} />
        <View style={styles.statItem}>
          <Text style={[styles.statValue, { color: colors.textPrimary }]} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}>{formatMemberCompact(data.memberSince)}</Text>
          <Text style={[styles.statLabel, { color: colors.textMuted }]} numberOfLines={1}>{t('profile.member')}</Text>
        </View>
      </View>

      {/* Telegram Connect Banner — growth hook for users who haven't linked TG yet */}
      {(() => {
        const tgConnected = !!(
          data.telegramUsername ||
          data.authProviders?.telegram ||
          data.linkedApps?.miniapp
        );
        if (tgConnected) {
          return (
            <View style={[styles.tgBanner, { backgroundColor: colors.buy + '12', borderColor: colors.buy + '30' }]}>
              <View style={[styles.tgBannerIcon, { backgroundColor: colors.buy + '20' }]}>
                <Ionicons name="checkmark-circle" size={18} color={colors.buy} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[styles.tgBannerTitle, { color: colors.textPrimary }]}>{t('intelProfile.telegramConnected')}</Text>
                <Text style={[styles.tgBannerSub, { color: colors.textMuted }]}>
                  You'll get alerts 2–5 min earlier than in-app
                </Text>
              </View>
            </View>
          );
        }
        return (
          <TouchableOpacity
            testID="tg-connect-banner"
            activeOpacity={0.85}
            onPress={() => {
              try {
                const { Linking } = require('react-native');
                const bot = process.env.EXPO_PUBLIC_TG_BOT_USERNAME || 'FOMO_mini_bot';
                Linking.openURL(`https://t.me/${bot}?start=connect`);
              } catch (e) {}
            }}
            style={[styles.tgBanner, { backgroundColor: colors.accent + '10', borderColor: colors.accent + '40' }]}
          >
            <View style={[styles.tgBannerIcon, { backgroundColor: colors.accent + '20' }]}>
              <Ionicons name="notifications" size={18} color={colors.accent} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[styles.tgBannerTitle, { color: colors.textPrimary }]}>
                🔔 Get alerts 2–5 min earlier
              </Text>
              <Text style={[styles.tgBannerSub, { color: colors.textMuted }]}>
                Telegram = faster intelligence. Connect →
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.accent} />
          </TouchableOpacity>
        );
      })()}

      {/* Loss framing — retention/conversion hook for FREE users */}
      {data.plan === 'FREE' && (
        <TouchableOpacity
          onPress={() => navigateTo('subscription')}
          activeOpacity={0.85}
          style={[styles.lossCard, {
            backgroundColor: colors.surface,
            borderColor: colors.sell + '30',
          }]}
          testID="profile-loss-framing"
        >
          <View style={styles.lossIcon}>
            <Ionicons name="flash" size={18} color={colors.sell} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[styles.lossTitle, { color: colors.textPrimary }]}>
              You missed 3 signals this week
            </Text>
            <Text style={[styles.lossSub, { color: colors.textSecondary }]}>
              Unlock full entry + invalidation on every setup
            </Text>
          </View>
          <Ionicons name="arrow-forward" size={18} color={colors.accent} />
        </TouchableOpacity>
      )}

      <SectionCard icon="person-circle" title={t('profile.account')}
        subtitle={`${data.authProviders?.telegram ? 'Telegram ✓ • ' : ''}${data.email || ''}`}
        onPress={() => navigateTo('account')} colors={colors} />

      <SectionCard icon="shield-checkmark" title={t('profile.subscription')}
        subtitle={`${data.subscription.plan} \u2022 ${data.subscription.price}`}
        onPress={() => navigateTo('subscription')} colors={colors} />

      <SectionCard icon="trophy" title={t('intelProfile.growthLeaderboard')}
        subtitle={`${data.referrals.invites} invites \u2022 Rank & Rewards`}
        onPress={() => navigateTo('referrals')} colors={colors} />

      <SectionCard icon="settings" title={t('profile.preferences')}
        subtitle={`${themeLabel} \u2022 ${data.preferences.language.toUpperCase()}`}
        onPress={() => navigateTo('preferences')} colors={colors} />

      <SectionCard icon="apps" title={t('profile.connected')}
        subtitle={`Web${data.linkedApps.web ? ' \u2713' : ''} \u2022 MiniApp${(data.authProviders?.telegram && !!data.telegramUsername) || data.linkedApps.miniapp ? ' \u2713' : ''}`}
        onPress={() => navigateTo('connected')} colors={colors} />

      <SectionCard icon="lock-closed" title={t('profile.security')}
        subtitle={`2FA ${data.twoFactorEnabled ? 'ON' : 'OFF'} \u2022 1 ${t('account.sessions').toLowerCase()}`}
        onPress={() => navigateTo('security')} colors={colors} />

      <SectionCard icon="notifications" title={t('profile.notifications')}
        subtitle={`${data.preferences.notifications ? t('prefs.on') : t('prefs.off')}`}
        onPress={() => navigateTo('notifications')} colors={colors} />

      {/* Operator-only: Cognition Observatory entry (Phase B · Step 2).
          Reflective interpretive surface, NOT analytics. Visible only
          when executionConsole capability is granted. */}
      <OperatorObservatoryEntry colors={colors} />

      {/* Operator-only: Broker Bridge entry (T10.2A/B · Operational transparency).
          Observability layer · safe-mode default · no execution authority. */}
      <BrokerBridgeEntry colors={colors} />

      <SectionCard icon="information-circle" title={t('profile.about')}
        subtitle="v1.0.0"
        onPress={() => navigateTo('about')} isLast colors={colors} />

      <TouchableOpacity style={styles.signOutButton} onPress={handleSignOut}>
        <Ionicons name="log-out-outline" size={20} color={colors.sell} />
        <Text style={[styles.signOutText, { color: colors.sell }]}>{t('profile.signOut')}</Text>
      </TouchableOpacity>

      <View style={{ height: 30 }} />
    </ScrollView>
  );
}

// ==================== Operator Observatory Entry ====================
// Phase B · Step 2 — operator-only menu entry to Cognition Observatory.
// Hidden when capability missing; deep-links to /operator/observatory.
function OperatorObservatoryEntry({ colors }: { colors: any }) {
  const t = useT();
  const { capabilities, loaded } = useCapabilities();
  if (!loaded || !capabilities?.executionConsole) return null;
  return (
    <SectionCard
      icon="telescope-outline"
      title={t('intelProfile.operatorObservatory')}
      subtitle="cognition continuity surface · reflective only"
      onPress={() => {
        try { router.push('/operator/observatory'); } catch {}
      }}
      colors={colors}
    />
  );
}

// ==================== Broker Bridge Entry ====================
// T10.2A/B — operator-only entry to the read-only broker bridge surface.
// Visible only when executionConsole capability is granted. Always
// renders as "safe mode" / observability — no execution authority surfaced.
function BrokerBridgeEntry({ colors }: { colors: any }) {
  const { capabilities, loaded } = useCapabilities();
  if (!loaded || !capabilities?.executionConsole) return null;
  return (
    <SectionCard
      icon="shield-checkmark-outline"
      title="Broker Bridge"
      subtitle="read-only observability · safe mode"
      onPress={() => {
        try { router.push('/operator/broker'); } catch {}
      }}
      colors={colors}
    />
  );
}

// ==================== Section Card ====================
function SectionCard({ icon, title, subtitle, onPress, accent, isLast, colors }: {
  icon: keyof typeof Ionicons.glyphMap; title: string; subtitle: string;
  onPress: () => void; accent?: boolean; isLast?: boolean; colors: any;
}) {
  return (
    <TouchableOpacity
      style={[styles.sectionCard, { backgroundColor: colors.surface },
        accent && { borderWidth: 1, borderColor: colors.accent + '30' },
        isLast && { marginBottom: 0 }]}
      onPress={onPress} activeOpacity={0.7}
    >
      <View style={[styles.sectionIconContainer, { backgroundColor: accent ? colors.accent + '20' : colors.surfaceHover }]}>
        <Ionicons name={icon} size={20} color={accent ? colors.accent : colors.textSecondary} />
      </View>
      <View style={styles.sectionContent}>
        <Text style={[styles.sectionTitle, { color: colors.textPrimary }]}>{title}</Text>
        <Text style={[styles.sectionSubtitle, { color: colors.textMuted }]}>{subtitle}</Text>
      </View>
      <Ionicons name="chevron-forward" size={18} color={colors.textMuted} />
    </TouchableOpacity>
  );
}

// ==================== SubView Wrapper ====================
function SubView({ view, data, onBack, onDataRefresh }: {
  view: ProfileView; data: ProfileData; onBack: () => void; onDataRefresh: () => void;
}) {
  const colors = useColors();
  const t = useT();
  const titleMap: Record<string, string> = {
    account: t('profile.account'), subscription: t('profile.subscription'),
    referrals: t('profile.referrals'), preferences: t('profile.preferences'),
    security: t('profile.security'), connected: t('profile.connected'),
    notifications: t('profile.notifications'), about: t('profile.about'), main: '',
  };

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={[styles.subHeader, { backgroundColor: colors.background, borderBottomColor: colors.border }]}>
        <TouchableOpacity onPress={onBack} style={styles.backButton}>
          <Ionicons name="chevron-back" size={24} color={colors.textPrimary} />
        </TouchableOpacity>
        <Text style={[styles.subHeaderTitle, { color: colors.textPrimary }]}>{titleMap[view]}</Text>
        <View style={{ width: 40 }} />
      </View>
      <ScrollView style={styles.subContent} contentContainerStyle={{ paddingBottom: 30 }}>
        {view === 'account' && <AccountView data={data} onDataRefresh={onDataRefresh} />}
        {view === 'subscription' && <SubscriptionView data={data} />}
        {view === 'referrals' && <GrowthScreenEmbed />}
        {view === 'preferences' && <PreferencesView data={data} />}
        {view === 'security' && <SecurityView data={data} onDataRefresh={onDataRefresh} />}
        {view === 'connected' && <ConnectedView data={data} />}
        {view === 'notifications' && <NotificationsView data={data} />}
        {view === 'about' && <AboutView />}
      </ScrollView>
    </View>
  );
}

// ==================== ACCOUNT VIEW ====================
function AccountView({ data, onDataRefresh }: { data: ProfileData; onDataRefresh: () => void }) {
  const colors = useColors();
  const t = useT();
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState(data.name);
  const [editingEmail, setEditingEmail] = useState(false);
  const [emailStep, setEmailStep] = useState<'input' | 'otp'>('input');
  const [emailValue, setEmailValue] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [devCode, setDevCode] = useState('');
  const [saving, setSaving] = useState('');
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState<'success' | 'error'>('success');
  // Telegram linking (via bot)
  const isTelegramLinked = data.authProviders?.telegram && !!data.telegramUsername;

  const saveName = async () => {
    if (!nameValue.trim()) return;
    setSaving('name');
    try {
      await mobileApi.updateProfile({ name: nameValue.trim() });
      data.name = nameValue.trim();
      setEditingName(false);
      setMessage('');
    } catch (e) { console.error(e); } finally { setSaving(''); }
  };

  const saveEmail = async () => {
    if (!emailValue.trim()) return;
    // Validate email format on client side
    const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    if (!emailRegex.test(emailValue.trim())) {
      setMessage(t('account.invalidEmail')); setMessageType('error'); return;
    }
    setSaving('email'); setMessage('');
    try {
      const result = await mobileApi.requestEmailChange(emailValue.trim());
      if (result.success && result.step === 'otp_sent') {
        setEmailStep('otp');
        if (result.devCode) { setDevCode(result.devCode); }
        if (result.deliveryMethod === 'email') {
          setMessage(t('account.otpSentEmail')); setMessageType('success');
        } else if (result.deliveryMethod === 'telegram') {
          setMessage(t('account.otpSentTelegram')); setMessageType('success');
        } else {
          setMessage(t('account.otpReady')); setMessageType('success');
        }
      } else { setMessage(result.message || t('failed')); setMessageType('error'); }
    } catch { setMessage(t('error')); setMessageType('error'); } finally { setSaving(''); }
  };

  const confirmEmailChange = async () => {
    if (otpCode.length !== 6) { setMessage(t('security.enter6digit')); setMessageType('error'); return; }
    setSaving('otp'); setMessage('');
    try {
      const result = await mobileApi.confirmEmailChange(otpCode);
      if (result.success) {
        setMessage(t('account.emailUpdated')); setMessageType('success');
        setEditingEmail(false); setEmailStep('input');
        setEmailValue(''); setOtpCode(''); setDevCode('');
        onDataRefresh();
      } else { setMessage(result.message || t('security.invalidCode')); setMessageType('error'); }
    } catch { setMessage(t('error')); setMessageType('error'); } finally { setSaving(''); }
  };

  const cancelEmailChange = () => {
    setEditingEmail(false); setEmailStep('input');
    setEmailValue(''); setOtpCode(''); setDevCode(''); setMessage('');
  };

  const unlinkTelegram = async () => {
    setSaving('telegram');
    try {
      const result = await mobileApi.unlinkTelegram();
      if (result.success) {
        data.authProviders.telegram = false;
        data.telegramUsername = undefined;
        setMessage(t('telegramUnlinked'));
        onDataRefresh();
      }
    } catch {} finally { setSaving(''); }
  };

  return (
    <View>
      <View style={styles.detailSection}>
        <Text style={[styles.detailSectionTitle, { color: colors.textMuted }]}>{t('account.personalInfo')}</Text>
        {editingName ? (
          <View style={[styles.editRow, { backgroundColor: colors.surface }]}>
            <TextInput style={[styles.editInput, { color: colors.textPrimary }]} value={nameValue}
              onChangeText={setNameValue} placeholder={t('account.name')} placeholderTextColor={colors.textMuted} autoFocus />
            <TouchableOpacity onPress={saveName} disabled={saving === 'name'} style={[styles.editSaveBtn, { backgroundColor: colors.accent }]}>
              <Text style={styles.editSaveBtnText}>{saving === 'name' ? '...' : t('account.save')}</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => { setEditingName(false); setNameValue(data.name); }}>
              <Ionicons name="close" size={18} color={colors.textMuted} />
            </TouchableOpacity>
          </View>
        ) : (
          <TouchableOpacity onPress={() => setEditingName(true)} style={[styles.actionRow, { borderBottomColor: colors.border }]}>
            <Ionicons name="person-outline" size={18} color={colors.textSecondary} />
            <View style={{ flex: 1 }}>
              <Text style={[{ fontSize: 12, color: colors.textPrimary, fontWeight: '600' }]}>{data.name}</Text>
              <Text style={[{ fontSize: 10, color: colors.textMuted }]}>{t('account.name')}</Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color={colors.textMuted} />
          </TouchableOpacity>
        )}
        {/* Email — 2-step change with OTP verification */}
        {editingEmail ? (
          <View style={{ marginTop: 8, padding: 12, backgroundColor: colors.surface, borderRadius: 10 }}>
            {emailStep === 'input' ? (
              <>
                <Text style={[styles.detailSectionTitle, { color: colors.textMuted }]}>{t('account.changeEmail')}</Text>
                <Text style={{ fontSize: 11, color: colors.textSecondary, marginBottom: 8 }}>{t('account.emailChangeDesc')}</Text>
                <Text style={{ fontSize: 11, color: colors.textMuted, marginBottom: 6 }}>
                  {t('account.currentEmailLabel')}: {data.email}
                </Text>
                <TextInput style={[styles.editInput, { color: colors.textPrimary, backgroundColor: colors.background, borderRadius: 8, padding: 10 }]}
                  value={emailValue} onChangeText={setEmailValue} placeholder={t('account.newEmail')}
                  placeholderTextColor={colors.textMuted} keyboardType="email-address" autoCapitalize="none" autoFocus />
                <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
                  <TouchableOpacity onPress={saveEmail} disabled={saving === 'email'}
                    style={[styles.editSaveBtn, { flex: 1, backgroundColor: colors.accent }]}>
                    <Text style={styles.editSaveBtnText}>{saving === 'email' ? '...' : t('account.sendCode')}</Text>
                  </TouchableOpacity>
                  <TouchableOpacity onPress={cancelEmailChange}
                    style={[styles.editSaveBtn, { flex: 1, backgroundColor: colors.border }]}>
                    <Text style={[styles.editSaveBtnText, { color: colors.textSecondary }]}>{t('general.cancel')}</Text>
                  </TouchableOpacity>
                </View>
              </>
            ) : (
              <>
                <Text style={[styles.detailSectionTitle, { color: colors.textMuted }]}>{t('account.confirmCode')}</Text>
                <Text style={{ fontSize: 11, color: colors.textSecondary, marginBottom: 8 }}>
                  {t('account.otpInstruction')}
                </Text>
                {devCode ? (
                  <View style={{ backgroundColor: colors.accent + '15', borderRadius: 8, padding: 10, marginBottom: 8 }}>
                    <Text style={{ fontSize: 11, color: colors.textMuted }}>{t('account.devCodeLabel')}</Text>
                    <Text style={{ fontSize: 20, fontWeight: '700', color: colors.accent, letterSpacing: 4 }}>{devCode}</Text>
                  </View>
                ) : null}
                <TextInput style={[styles.editInput, { color: colors.textPrimary, backgroundColor: colors.background, borderRadius: 8, padding: 10, fontSize: 18, letterSpacing: 4, textAlign: 'center' }]}
                  value={otpCode} onChangeText={(t) => setOtpCode(t.replace(/\D/g, '').slice(0, 6))} placeholder="000000"
                  placeholderTextColor={colors.textMuted} keyboardType="number-pad" autoFocus />
                <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
                  <TouchableOpacity onPress={confirmEmailChange} disabled={saving === 'otp'}
                    style={[styles.editSaveBtn, { flex: 1, backgroundColor: colors.accent }]}>
                    <Text style={styles.editSaveBtnText}>{saving === 'otp' ? '...' : t('account.confirm')}</Text>
                  </TouchableOpacity>
                  <TouchableOpacity onPress={cancelEmailChange}
                    style={[styles.editSaveBtn, { flex: 1, backgroundColor: colors.border }]}>
                    <Text style={[styles.editSaveBtnText, { color: colors.textSecondary }]}>{t('general.cancel')}</Text>
                  </TouchableOpacity>
                </View>
              </>
            )}
          </View>
        ) : (
          <TouchableOpacity onPress={() => setEditingEmail(true)} style={[styles.actionRow, { borderBottomColor: colors.border }]}>
            <Ionicons name="mail-outline" size={18} color={colors.textSecondary} />
            <View style={{ flex: 1 }}>
              <Text style={[{ fontSize: 12, color: colors.textPrimary, fontWeight: '600' }]}>{data.email}</Text>
              <Text style={[{ fontSize: 10, color: colors.textMuted }]}>{t('account.email')}</Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color={colors.textMuted} />
          </TouchableOpacity>
        )}
        {message ? (
          <Text style={[styles.feedbackText, { color: messageType === 'success' ? colors.buy : colors.sell }]}>{message}</Text>
        ) : null}
        <DetailRow label={t('account.memberSince')} value={formatMember(data.memberSince)} colors={colors} />
      </View>

      <View style={styles.detailSection}>
        <Text style={[styles.detailSectionTitle, { color: colors.textMuted }]}>Telegram</Text>
        {/* Telegram with bot-based linking */}
        <View style={[styles.providerRow, { borderBottomColor: colors.border }]}>
          <Ionicons name={isTelegramLinked ? 'checkmark-circle' : 'ellipse-outline'} size={18}
            color={isTelegramLinked ? colors.buy : colors.textMuted} />
          <Text style={[styles.providerName, { color: colors.textPrimary }]}>@FOMO_Trading_bot</Text>
          {isTelegramLinked ? (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Text style={{ fontSize: 11, color: colors.buy }}>@{data.telegramUsername}</Text>
              <TouchableOpacity onPress={unlinkTelegram} disabled={saving === 'telegram'}>
                <Text style={{ fontSize: 11, color: colors.sell }}>{t('telegram.unlink')}</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <TouchableOpacity onPress={async () => {
              setSaving('telegram');
              try {
                const result = await mobileApi.getTelegramLinkCode();
                if (result.success && result.botUrl) {
                  Linking.openURL(result.botUrl).catch(() => {});
                }
              } catch {} finally { setSaving(''); }
            }} disabled={saving === 'telegram'}>
              <Text style={{ fontSize: 11, color: colors.accent }}>{saving === 'telegram' ? '...' : t('telegram.connect')}</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>

      <View style={styles.detailSection}>
        <Text style={[styles.detailSectionTitle, { color: colors.textMuted }]}>{t('account.sessions')}</Text>
        <View style={[styles.sessionCard, { backgroundColor: colors.surface }]}>
          <Ionicons name="phone-portrait" size={20} color={colors.accent} />
          <View style={{ flex: 1, marginLeft: 8 }}>
            <Text style={[styles.sessionDevice, { color: colors.textPrimary }]}>{t('account.currentDevice')}</Text>
            <Text style={[styles.sessionMeta, { color: colors.textMuted }]}>{t('account.activeNow')}</Text>
          </View>
          <View style={[styles.currentBadge, { backgroundColor: colors.accent + '20' }]}>
            <Text style={[styles.currentBadgeText, { color: colors.accent }]}>{t('account.current')}</Text>
          </View>
        </View>
      </View>
    </View>
  );
}

// ==================== PREFERENCES VIEW ====================
function PreferencesView({ data }: { data: ProfileData }) {
  const colors = useColors();
  const t = useT();
  const { allAssets, isLoaded, setCurrentAsset } = useAssetStore();
  const { themeMode, language, startScreen, hapticsEnabled, setThemeMode, setLanguage, setStartScreen, setHapticsEnabled } = usePreferencesStore();
  const [selectedAsset, setSelectedAsset] = useState(data.preferences?.defaultAsset || 'BTC');
  const [saving, setSaving] = useState('');

  const displayAssets = isLoaded && allAssets.length > 0
    ? allAssets.slice(0, 12)
    : [{ symbol: 'BTC' }, { symbol: 'ETH' }, { symbol: 'SOL' }, { symbol: 'BNB' }, { symbol: 'XRP' }, { symbol: 'DOGE' }];

  const savePreference = async (key: string, value: string | boolean) => {
    setSaving(key);
    doHaptic();
    // Optimistic local update — apply IMMEDIATELY so UI reflects the change
    // even if the user is not logged in / backend is unreachable.
    if (key === 'defaultAsset') { setSelectedAsset(value as string); setCurrentAsset(value as string); }
    if (key === 'theme') { setThemeMode(value as any); }
    if (key === 'language') { setLanguage(value as any); }
    if (key === 'startScreen') { setStartScreen(value as any); }
    if (key === 'haptics') { setHapticsEnabled(value as boolean); }
    try {
      await mobileApi.updatePreferences({ [key]: value });
    } catch (e) {
      // Backend sync failed (e.g. guest session) — local state already applied,
      // and it will be persisted to AsyncStorage by each setter.
      console.warn('Pref sync skipped (offline/guest):', key, (e as any)?.message);
    } finally { setSaving(''); }
  };

  return (
    <View>
      <View style={styles.detailSection}>
        <Text style={[styles.detailSectionTitle, { color: colors.textMuted }]}>{t('prefs.appearance')}</Text>
        {([{ label: t('prefs.dark'), value: 'dark' }, { label: t('prefs.light'), value: 'light' }]).map((v) => (
          <TouchableOpacity key={v.value} onPress={() => savePreference('theme', v.value)}>
            <RadioOption label={v.label} value={v.value} current={themeMode} colors={colors}
              saving={saving === 'theme'} />
          </TouchableOpacity>
        ))}
      </View>

      <View style={styles.detailSection}>
        <Text style={[styles.detailSectionTitle, { color: colors.textMuted }]}>{t('prefs.dataSources')}</Text>
        {[
          { key: 'exchange', icon: 'bar-chart-outline', label: t('prefs.src.exchange') },
          { key: 'onchain', icon: 'git-network-outline', label: t('prefs.src.onchain') },
          { key: 'sentiment', icon: 'people-outline', label: t('prefs.src.sentiment') },
          { key: 'fractals', icon: 'analytics-outline', label: t('prefs.src.fractals') },
          { key: 'technicals', icon: 'pulse-outline', label: t('prefs.src.technicals') },
          { key: 'prediction', icon: 'telescope-outline', label: t('prefs.src.prediction') },
        ].map((src) => {
          const enabled = data.preferences?.dataSources?.[src.key] !== false;
          return (
            <TouchableOpacity key={src.key}
              style={[styles.notifRow, { borderBottomColor: colors.border }]}
              onPress={() => savePreference(`dataSources.${src.key}`, !enabled)}
              activeOpacity={0.7}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 }}>
                <Ionicons name={src.icon as any} size={18} color={enabled ? colors.accent : colors.textMuted} />
                <Text style={[styles.notifLabel, { color: enabled ? colors.textPrimary : colors.textMuted }]}>{src.label}</Text>
              </View>
              <View style={[styles.toggle, { backgroundColor: enabled ? colors.accent : colors.surfaceHover }]}>
                <View style={[styles.toggleDot, { backgroundColor: enabled ? '#FFFFFF' : colors.textMuted, alignSelf: enabled ? 'flex-end' : 'flex-start' }]} />
              </View>
            </TouchableOpacity>
          );
        })}
      </View>

      <View style={styles.detailSection}>
        <Text style={[styles.detailSectionTitle, { color: colors.textMuted }]}>{t('prefs.language')}</Text>
        {[{ label: 'English', value: 'en' }, { label: 'Русский', value: 'ru' }].map((l) => (
          <TouchableOpacity key={l.value} onPress={() => savePreference('language', l.value)}>
            <RadioOption label={l.label} value={l.value} current={language} colors={colors} />
          </TouchableOpacity>
        ))}
      </View>

      <View style={styles.detailSection}>
        <Text style={[styles.detailSectionTitle, { color: colors.textMuted }]}>{t('prefs.appBehavior')}</Text>
        {/* Start Screen */}
        <Text style={[{ fontSize: 11, color: colors.textSecondary, marginBottom: 4 }]}>{t('prefs.startScreen')}</Text>
        <View style={{ flexDirection: 'row', gap: 8, marginBottom: 12 }}>
          {(['HOME', 'FEED', 'EDGE'] as const).map((s) => (
            <TouchableOpacity key={s}
              style={[styles.assetChip, { borderColor: startScreen === s ? colors.accent : colors.border },
                startScreen === s && { backgroundColor: colors.accent + '15' }]}
              onPress={() => savePreference('startScreen', s)}>
              <Text style={[styles.assetChipText, { color: startScreen === s ? colors.accent : colors.textMuted }]}>{s}</Text>
            </TouchableOpacity>
          ))}
        </View>
        {/* Haptics toggle */}
        <TouchableOpacity style={[styles.notifRow, { borderBottomColor: colors.border }]}
          onPress={() => savePreference('haptics', !hapticsEnabled)}>
          <Text style={[styles.notifLabel, { color: colors.textPrimary }]}>{t('prefs.haptics')}</Text>
          <View style={[styles.toggle, { backgroundColor: hapticsEnabled ? colors.accent : colors.surfaceHover }]}>
            <View style={[styles.toggleDot, { backgroundColor: hapticsEnabled ? '#FFFFFF' : colors.textMuted, alignSelf: hapticsEnabled ? 'flex-end' : 'flex-start' }]} />
          </View>
        </TouchableOpacity>
      </View>
    </View>
  );
}

// ==================== SECURITY VIEW ====================
function SecurityView({ data, onDataRefresh }: { data: ProfileData; onDataRefresh: () => void }) {
  const colors = useColors();
  const t = useT();
  const hasPassword = data?.hasPassword || false;
  const is2FAEnabled = data?.twoFactorEnabled || false;

  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [currentPwd, setCurrentPwd] = useState('');
  const [newPwd, setNewPwd] = useState('');
  const [confirmPwd, setConfirmPwd] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState<'success' | 'error'>('success');

  // Eye toggle visibility
  const [showCurrentPwd, setShowCurrentPwd] = useState(false);
  const [showNewPwd, setShowNewPwd] = useState(false);
  const [showConfirmPwd, setShowConfirmPwd] = useState(false);

  // 2FA state
  const [show2FASetup, setShow2FASetup] = useState(false);
  const [tfaSecret, setTfaSecret] = useState('');
  const [tfaCode, setTfaCode] = useState('');
  const [tfaSaving, setTfaSaving] = useState(false);
  const [tfaMessage, setTfaMessage] = useState('');
  const [showDisable2FA, setShowDisable2FA] = useState(false);
  const [disableCode, setDisableCode] = useState('');

  // Password validation rules
  const pwdHasMinLen = newPwd.length >= 8;
  const pwdHasUpper = /[A-Z]/.test(newPwd);
  const pwdHasDigit = /[0-9]/.test(newPwd);
  const pwdHasSpecial = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?~`]/.test(newPwd);
  const pwdIsLatin = newPwd.length === 0 || !/[а-яА-ЯёЁ]/.test(newPwd);
  const pwdMatch = newPwd.length > 0 && newPwd === confirmPwd;
  const allValid = pwdHasMinLen && pwdHasUpper && pwdHasDigit && pwdHasSpecial && pwdIsLatin && pwdMatch && totpCode.length === 6;

  const handlePassword = async () => {
    setMessage('');
    if (!pwdHasMinLen) { setMessage(t('security.minChars')); setMessageType('error'); return; }
    if (!pwdIsLatin) { setMessage(t('security.latinOnly')); setMessageType('error'); return; }
    if (!pwdHasUpper) { setMessage(t('security.needUppercase')); setMessageType('error'); return; }
    if (!pwdHasDigit) { setMessage(t('security.needDigit')); setMessageType('error'); return; }
    if (!pwdHasSpecial) { setMessage(t('security.needSpecial')); setMessageType('error'); return; }
    if (!pwdMatch) { setMessage(t('security.noMatch')); setMessageType('error'); return; }
    if (totpCode.length !== 6) { setMessage(t('security.enter6digit')); setMessageType('error'); return; }
    setSaving(true);
    try {
      let result;
      if (hasPassword) {
        if (!currentPwd) { setMessage(t('security.currentRequired')); setMessageType('error'); setSaving(false); return; }
        result = await mobileApi.changePassword(currentPwd, newPwd, totpCode);
      } else {
        result = await mobileApi.setPassword(newPwd, totpCode);
      }
      if (result.success) {
        setMessage(result.message || t('security.passwordSaved')); setMessageType('success');
        setShowPasswordForm(false); setCurrentPwd(''); setNewPwd(''); setConfirmPwd(''); setTotpCode('');
        onDataRefresh();
      } else { setMessage(result.message || t('failed')); setMessageType('error'); }
    } catch { setMessage(t('error')); setMessageType('error'); } finally { setSaving(false); }
  };

  const start2FASetup = async () => {
    setTfaSaving(true); setTfaMessage('');
    try {
      const result = await mobileApi.setup2FA();
      setTfaSecret(result.secret);
      setShow2FASetup(true);
    } catch (e: any) {
      setTfaMessage(e?.response?.data?.detail || t('security.failedSetup2fa'));
    } finally { setTfaSaving(false); }
  };

  const verify2FA = async () => {
    if (tfaCode.length !== 6) { setTfaMessage(t('security.enter6digit')); return; }
    setTfaSaving(true); setTfaMessage('');
    try {
      const result = await mobileApi.verify2FA(tfaCode);
      if (result.success) {
        setTfaMessage(t('security.2faEnabled!')); setShow2FASetup(false); setTfaCode('');
        data.twoFactorEnabled = true;
        onDataRefresh();
      } else { setTfaMessage(result.message || t('security.invalidCode')); }
    } catch { setTfaMessage(t('security.errorVerifying')); } finally { setTfaSaving(false); }
  };

  const handleDisable2FA = async () => {
    if (disableCode.length !== 6) { setTfaMessage(t('security.enter6digit')); return; }
    setTfaSaving(true); setTfaMessage('');
    try {
      const result = await mobileApi.disable2FA(disableCode);
      if (result.success) {
        setTfaMessage(t('security.2faDisabled')); setShowDisable2FA(false); setDisableCode('');
        data.twoFactorEnabled = false;
        onDataRefresh();
      } else { setTfaMessage(result.message || t('security.invalidCode')); }
    } catch { setTfaMessage(t('error')); } finally { setTfaSaving(false); }
  };

  // Reusable password input with eye icon
  const PasswordInput = ({ value, onChangeText, placeholder, secureVisible, onToggleSecure }: {
    value: string; onChangeText: (v: string) => void; placeholder: string;
    secureVisible: boolean; onToggleSecure: () => void;
  }) => (
    <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: colors.surface, borderRadius: 8, marginTop: 8 }}>
      <TextInput
        style={[styles.editInput, { flex: 1, color: colors.textPrimary, padding: 10, borderRadius: 8, marginBottom: 0 }]}
        value={value} onChangeText={onChangeText} placeholder={placeholder}
        placeholderTextColor={colors.textMuted} secureTextEntry={!secureVisible}
        autoCapitalize="none" autoCorrect={false} />
      <TouchableOpacity onPress={onToggleSecure} style={{ padding: 10 }}>
        <Ionicons name={secureVisible ? 'eye-off-outline' : 'eye-outline'} size={20} color={colors.textMuted} />
      </TouchableOpacity>
    </View>
  );

  // Password validation rule indicator
  const RuleCheck = ({ passed, label }: { passed: boolean; label: string }) => (
    <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 4 }}>
      <Ionicons name={passed ? 'checkmark-circle' : 'ellipse-outline'} size={14}
        color={passed ? colors.buy : colors.textMuted} />
      <Text style={{ fontSize: 11, color: passed ? colors.buy : colors.textMuted, marginLeft: 6 }}>{label}</Text>
    </View>
  );

  return (
    <View>
      {/* 2FA Section — ABOVE Password so user enables it first */}
      <View style={styles.detailSection}>
        <Text style={[styles.detailSectionTitle, { color: colors.textMuted }]}>{t('security.twoFactor')}</Text>
        <View style={[styles.securityCard, { backgroundColor: colors.surface }]}>
          <Ionicons name={is2FAEnabled ? 'shield-checkmark' : 'shield-outline'} size={24}
            color={is2FAEnabled ? colors.buy : colors.textMuted} />
          <View style={{ flex: 1, marginLeft: 8 }}>
            <Text style={[styles.securityCardTitle, { color: colors.textPrimary }]}>
              {is2FAEnabled ? t('security.2faEnabled') : t('security.2faNotEnabled')}
            </Text>
            <Text style={[styles.securityCardDesc, { color: colors.textMuted }]}>
              {is2FAEnabled ? t('security.2faProtected') : t('security.2faProtect')}
            </Text>
          </View>
        </View>

        {/* 2FA Setup Flow */}
        {!is2FAEnabled && !show2FASetup && (
          <TouchableOpacity style={[styles.editSaveBtn, { backgroundColor: colors.accent, alignSelf: 'flex-start', marginTop: 8 }]}
            onPress={start2FASetup} disabled={tfaSaving}>
            <Text style={styles.editSaveBtnText}>{tfaSaving ? '...' : t('security.enable2fa')}</Text>
          </TouchableOpacity>
        )}

        {show2FASetup && (
          <View style={{ marginTop: 12 }}>
            <Text style={[styles.detailSectionTitle, { color: colors.textMuted }]}>{t('2fa.setupTitle')}</Text>
            <Text style={{ fontSize: 12, color: colors.textSecondary, marginBottom: 8 }}>{t('2fa.scanOrEnter')}</Text>
            <View style={{ backgroundColor: colors.surfaceHover, padding: 12, borderRadius: 8, marginBottom: 12 }}>
              <Text selectable style={{ fontSize: 16, fontWeight: '700', color: colors.accent, letterSpacing: 2, textAlign: 'center' }}>
                {tfaSecret}
              </Text>
            </View>
            <TextInput
              style={[styles.editInput, { color: colors.textPrimary, backgroundColor: colors.surface, borderRadius: 8, padding: 10, textAlign: 'center', fontSize: 18, letterSpacing: 4 }]}
              value={tfaCode} onChangeText={(v) => setTfaCode(v.replace(/\D/g, '').slice(0, 6))}
              placeholder={t('2fa.enterCode')} placeholderTextColor={colors.textMuted}
              keyboardType="number-pad" maxLength={6} />
            <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
              <TouchableOpacity onPress={verify2FA} disabled={tfaSaving || tfaCode.length !== 6}
                style={[styles.editSaveBtn, { flex: 1, backgroundColor: colors.accent }]}>
                <Text style={styles.editSaveBtnText}>{tfaSaving ? '...' : t('2fa.verify')}</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => { setShow2FASetup(false); setTfaCode(''); }}
                style={[styles.editSaveBtn, { flex: 1, backgroundColor: colors.border }]}>
                <Text style={[styles.editSaveBtnText, { color: colors.textSecondary }]}>{t('general.cancel')}</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        {/* Disable 2FA */}
        {is2FAEnabled && !showDisable2FA && (
          <TouchableOpacity style={[styles.editSaveBtn, { backgroundColor: colors.sell + '20', alignSelf: 'flex-start', marginTop: 8 }]}
            onPress={() => setShowDisable2FA(true)}>
            <Text style={[styles.editSaveBtnText, { color: colors.sell }]}>{t('security.disable2fa')}</Text>
          </TouchableOpacity>
        )}

        {showDisable2FA && (
          <View style={{ marginTop: 12 }}>
            <Text style={{ fontSize: 12, color: colors.textSecondary, marginBottom: 8 }}>{t('2fa.disablePrompt')}</Text>
            <TextInput
              style={[styles.editInput, { color: colors.textPrimary, backgroundColor: colors.surface, borderRadius: 8, padding: 10, textAlign: 'center', fontSize: 18, letterSpacing: 4 }]}
              value={disableCode} onChangeText={(v) => setDisableCode(v.replace(/\D/g, '').slice(0, 6))}
              placeholder="000000" placeholderTextColor={colors.textMuted}
              keyboardType="number-pad" maxLength={6} />
            <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
              <TouchableOpacity onPress={handleDisable2FA} disabled={tfaSaving || disableCode.length !== 6}
                style={[styles.editSaveBtn, { flex: 1, backgroundColor: colors.sell }]}>
                <Text style={[styles.editSaveBtnText, { color: '#fff' }]}>{tfaSaving ? '...' : t('2fa.confirmDisable')}</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => { setShowDisable2FA(false); setDisableCode(''); }}
                style={[styles.editSaveBtn, { flex: 1, backgroundColor: colors.border }]}>
                <Text style={[styles.editSaveBtnText, { color: colors.textSecondary }]}>{t('general.cancel')}</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        {tfaMessage ? (
          <Text style={[styles.feedbackText, { color: tfaMessage.includes('enabled') || tfaMessage.includes('disabled') || tfaMessage.includes('включена') || tfaMessage.includes('отключена') ? colors.buy : colors.sell }]}>{tfaMessage}</Text>
        ) : null}
      </View>

      {/* Password Section */}
      <View style={styles.detailSection}>
        <Text style={[styles.detailSectionTitle, { color: colors.textMuted }]}>{t('security.password')}</Text>

        {!is2FAEnabled ? (
          /* 2FA not enabled — password locked */
          <View style={[styles.securityCard, { backgroundColor: colors.surface }]}>
            <Ionicons name="lock-closed" size={22} color={colors.textMuted} />
            <View style={{ flex: 1, marginLeft: 8 }}>
              <Text style={[styles.securityCardTitle, { color: colors.textPrimary }]}>
                {t('security.2faRequiredForPwd')}
              </Text>
              <Text style={[styles.securityCardDesc, { color: colors.textMuted }]}>
                {t('security.2faRequiredDesc')}
              </Text>
            </View>
          </View>
        ) : !showPasswordForm ? (
          /* 2FA enabled — show button to open form */
          <TouchableOpacity style={[styles.actionRow, { borderBottomColor: colors.border }]} onPress={() => setShowPasswordForm(true)}>
            <Ionicons name="key" size={18} color={colors.textSecondary} />
            <Text style={[styles.actionRowText, { color: colors.textPrimary }]}>{hasPassword ? t('security.changePassword') : t('security.setPassword')}</Text>
            <Ionicons name="chevron-forward" size={16} color={colors.textMuted} />
          </TouchableOpacity>
        ) : (
          /* Password form with validation */
          <View style={styles.passwordForm}>
            {hasPassword && (
              <PasswordInput value={currentPwd} onChangeText={setCurrentPwd}
                placeholder={t('security.currentPwd')} secureVisible={showCurrentPwd}
                onToggleSecure={() => setShowCurrentPwd(!showCurrentPwd)} />
            )}
            <PasswordInput value={newPwd} onChangeText={setNewPwd}
              placeholder={t('security.newPwd')} secureVisible={showNewPwd}
              onToggleSecure={() => setShowNewPwd(!showNewPwd)} />

            {/* Real-time validation rules */}
            {newPwd.length > 0 && (
              <View style={{ marginTop: 6, marginBottom: 4, paddingHorizontal: 4 }}>
                <RuleCheck passed={pwdHasMinLen} label={t('security.minChars')} />
                <RuleCheck passed={pwdHasUpper} label={t('security.needUppercase')} />
                <RuleCheck passed={pwdHasDigit} label={t('security.needDigit')} />
                <RuleCheck passed={pwdHasSpecial} label={t('security.needSpecial')} />
                <RuleCheck passed={pwdIsLatin} label={t('security.latinOnly')} />
              </View>
            )}

            <PasswordInput value={confirmPwd} onChangeText={setConfirmPwd}
              placeholder={t('security.confirmPwd')} secureVisible={showConfirmPwd}
              onToggleSecure={() => setShowConfirmPwd(!showConfirmPwd)} />

            {confirmPwd.length > 0 && (
              <View style={{ marginTop: 4, paddingHorizontal: 4 }}>
                <RuleCheck passed={pwdMatch} label={pwdMatch ? t('security.passwordSaved').split('.')[0] : t('security.noMatch')} />
              </View>
            )}

            {/* 2FA code for verification */}
            <TextInput
              style={[styles.editInput, { color: colors.textPrimary, backgroundColor: colors.surface, borderRadius: 8, padding: 10, marginTop: 10, textAlign: 'center', fontSize: 18, letterSpacing: 4 }]}
              value={totpCode} onChangeText={(v) => setTotpCode(v.replace(/\D/g, '').slice(0, 6))}
              placeholder={t('security.totpCode')} placeholderTextColor={colors.textMuted}
              keyboardType="number-pad" maxLength={6} />

            <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
              <TouchableOpacity onPress={handlePassword} disabled={saving || !allValid}
                style={[styles.editSaveBtn, { flex: 1, backgroundColor: allValid ? colors.accent : colors.border }]}>
                <Text style={[styles.editSaveBtnText, { color: allValid ? '#fff' : colors.textMuted }]}>{saving ? '...' : t('account.save')}</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => { setShowPasswordForm(false); setMessage(''); setCurrentPwd(''); setNewPwd(''); setConfirmPwd(''); setTotpCode(''); }}
                style={[styles.editSaveBtn, { flex: 1, backgroundColor: colors.border }]}>
                <Text style={[styles.editSaveBtnText, { color: colors.textSecondary }]}>{t('general.cancel')}</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}
        {message ? (
          <Text style={[styles.feedbackText, { color: messageType === 'success' ? colors.buy : colors.sell }]}>{message}</Text>
        ) : null}
      </View>

      {/* Login History */}
      <View style={styles.detailSection}>
        <Text style={[styles.detailSectionTitle, { color: colors.textMuted }]}>{t('security.loginHistory')}</Text>
        <View style={[styles.historyItem, { borderBottomColor: colors.border }]}>
          <Text style={[styles.historyDevice, { color: colors.textPrimary }]}>{t('security.mobileApp')}</Text>
          <Text style={[styles.historyMeta, { color: colors.textMuted }]}>{t('security.activeSession')}</Text>
        </View>
      </View>
    </View>
  );
}

// ==================== SUBSCRIPTION VIEW ====================
function SubscriptionView({ data }: { data: ProfileData }) {
  const colors = useColors();
  const t = useT();
  const accessItems = [
    { name: t('sub.miniSignals'), key: 'miniSignals' as const },
    { name: t('sub.fullSignals'), key: 'fullSignals' as const },
    { name: t('sub.fullIntel'), key: 'fullIntel' as const },
    { name: t('sub.edgeMarkets'), key: 'edge' as const },
    { name: t('sub.tradingPreview'), key: 'tradingPreview' as const },
    { name: t('sub.tradingFull'), key: 'tradingFull' as const },
  ];

  const isExpired = data.subscription.status === 'EXPIRED' || data.planStatus === 'EXPIRED';

  const handleUpgrade = () => {
    openPaywall();
  };

  const handleReactivate = () => {
    // Re-activation flow (same as upgrade - opens paywall)
    openPaywall();
  };

  const handleManageBilling = () => {
    // Opens web platform for billing management
    // Placeholder URL until real platform is deployed
    const billingUrl = 'https://t.me/FOMO_Trading_bot/app';
    Linking.openURL(billingUrl).catch(() => {});
  };

  return (
    <View>
      {/* Expired Warning Banner */}
      {isExpired && (
        <View style={[styles.expiredBanner, { backgroundColor: colors.sell + '15', borderColor: colors.sell + '40' }]}>
          <Ionicons name="alert-circle" size={24} color={colors.sell} />
          <View style={{ flex: 1, marginLeft: 12 }}>
            <Text style={[styles.expiredTitle, { color: colors.sell }]}>{t('intelProfile.yourProAccessHasExpired')}</Text>
            <Text style={[styles.expiredSubtitle, { color: colors.textSecondary }]}>
              Reactivate now to regain access to full signals, Edge markets, and advanced analytics.
            </Text>
          </View>
        </View>
      )}

      <View style={[styles.planCard, { backgroundColor: colors.surface, borderColor: isExpired ? colors.sell + '30' : colors.accent + '30' }]}>
        <View style={styles.planCardHeader}>
          <View>
            <Text style={[styles.planCardTitle, { color: isExpired ? colors.sell : colors.accent }]}>{data.subscription.plan}</Text>
            <Text style={[styles.planCardStatus, { color: isExpired ? colors.sell : colors.buy }]}>
              {isExpired ? 'Expired' : data.subscription.status}
            </Text>
          </View>
          <Text style={[styles.planCardPrice, { color: colors.textPrimary }]}>{data.subscription.price}</Text>
        </View>
        <View style={[styles.planCardDivider, { backgroundColor: colors.border }]} />
        {!isExpired && (
          <Text style={[styles.planRenewal, { color: colors.textSecondary }]}>{t('sub.renews')} {data.subscription.renewsAt || '—'}</Text>
        )}
        {isExpired && (
          <Text style={[styles.planRenewal, { color: colors.sell }]}>{t('intelProfile.accessEndedRestoreToContinue')}</Text>
        )}
      </View>

      <View style={styles.detailSection}>
        <Text style={[styles.detailSectionTitle, { color: colors.textMuted }]}>{t('sub.yourAccess')}</Text>
        {accessItems.map(item => (
          <View key={item.key} style={[styles.accessRow, { borderBottomColor: colors.border }]}>
            <Ionicons name={data.access[item.key] ? 'checkmark-circle' : 'lock-closed'} size={18}
              color={data.access[item.key] ? colors.buy : colors.textMuted} />
            <Text style={[styles.accessName, { color: data.access[item.key] ? colors.textPrimary : colors.textMuted }]}>{item.name}</Text>
            <Text style={{ fontSize: 11, fontWeight: '600', color: data.access[item.key] ? colors.buy : colors.textMuted }}>
              {data.access[item.key] ? t('sub.available') : t('sub.locked')}
            </Text>
          </View>
        ))}
      </View>

      {isExpired && (
        <TouchableOpacity style={[styles.reactivateButton, { backgroundColor: colors.sell }]} onPress={handleReactivate} activeOpacity={0.8}>
          <Ionicons name="refresh" size={18} color={colors.background} />
          <Text style={[styles.upgradeButtonText, { color: colors.background }]}>{t('intelProfile.restoreProAccess')}</Text>
        </TouchableOpacity>
      )}
      {!data.access.tradingFull && !isExpired && (
        <TouchableOpacity style={[styles.upgradeButton, { backgroundColor: colors.accent }]} onPress={handleUpgrade} activeOpacity={0.8}>
          <Ionicons name="rocket" size={18} color={colors.background} />
          <Text style={[styles.upgradeButtonText, { color: colors.background }]}>{t('sub.upgradeTrading')}</Text>
        </TouchableOpacity>
      )}
      <TouchableOpacity style={[styles.secondaryButton, { borderColor: colors.accent + '30' }]} onPress={handleManageBilling} activeOpacity={0.7}>
        <Ionicons name="open-outline" size={16} color={colors.accent} />
        <Text style={[styles.secondaryButtonText, { color: colors.accent }]}>{t('sub.manageBilling')}</Text>
      </TouchableOpacity>
    </View>
  );
}

// ==================== REFERRALS VIEW ====================
function ReferralsView({ data }: { data: ProfileData }) {
  const colors = useColors();
  const t = useT();
  const [referralData, setReferralData] = useState(data.referrals);
  const [promoCode, setPromoCode] = useState('');
  const [promoMessage, setPromoMessage] = useState('');
  const [applying, setApplying] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    mobileApi.getReferrals().then((result) => {
      if (result.code) setReferralData({ code: result.code, invites: result.invites, paidReferrals: result.paidReferrals, earned: result.earned });
    }).catch(() => {});
  }, []);

  const copyCode = async () => {
    try {
      const { default: Clipboard } = await import('expo-clipboard');
      await Clipboard.setStringAsync(referralData.code);
      setCopied(true); doHaptic();
      setTimeout(() => setCopied(false), 2000);
    } catch {
      try {
        if (Platform.OS === 'web' && (navigator as any)?.clipboard) {
          await (navigator as any).clipboard.writeText(referralData.code);
          setCopied(true); setTimeout(() => setCopied(false), 2000);
        }
      } catch {}
    }
  };

  const shareInvite = async () => {
    try {
      const { Share } = require('react-native');
      await Share.share({
        message: t('referrals.shareMessage').replace('{code}', referralData.code).replace('{url}', `https://fomo.ai/r/${referralData.code}`),
      });
    } catch {}
  };

  const applyPromo = async () => {
    if (!promoCode.trim()) return;
    setApplying(true); setPromoMessage('');
    try {
      const result = await mobileApi.applyReferralCode(promoCode.trim());
      if (result.success) { setPromoMessage(result.message || t('referrals.codeApplied')); setPromoCode(''); }
      else { setPromoMessage(result.message || t('referrals.invalidCode')); }
    } catch { setPromoMessage(t('error')); } finally { setApplying(false); }
  };

  return (
    <View>
      <View style={[styles.referralStats, { backgroundColor: colors.surface }]}>
        <View style={styles.referralStatItem}>
          <Text style={[styles.referralStatValue, { color: colors.textPrimary }]}>{referralData.invites}</Text>
          <Text style={[styles.referralStatLabel, { color: colors.textMuted }]}>{t('referrals.invites')}</Text>
        </View>
        <View style={styles.referralStatItem}>
          <Text style={[styles.referralStatValue, { color: colors.textPrimary }]}>{referralData.paidReferrals}</Text>
          <Text style={[styles.referralStatLabel, { color: colors.textMuted }]}>{t('referrals.paid')}</Text>
        </View>
        <View style={styles.referralStatItem}>
          <Text style={[styles.referralStatValue, { color: colors.buy }]}>{referralData.earned}</Text>
          <Text style={[styles.referralStatLabel, { color: colors.textMuted }]}>{t('referrals.earned')}</Text>
        </View>
      </View>

      <View style={[styles.codeCard, { backgroundColor: colors.surface }]}>
        <Text style={[styles.codeLabel, { color: colors.textMuted }]}>{t('referrals.yourCode')}</Text>
        <View style={styles.codeRow}>
          <Text style={[styles.codeValue, { color: colors.accent }]}>{referralData.code || '...'}</Text>
          <TouchableOpacity style={styles.copyButton} onPress={copyCode}>
            <Ionicons name={copied ? 'checkmark' : 'copy'} size={16} color={copied ? colors.buy : colors.accent} />
            <Text style={[styles.copyButtonText, { color: copied ? colors.buy : colors.accent }]}>
              {copied ? t('referrals.copied') : t('referrals.copy')}
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      <TouchableOpacity style={[styles.shareButton, { backgroundColor: colors.accent }]} onPress={shareInvite}>
        <Ionicons name="share-social" size={18} color={colors.background} />
        <Text style={[styles.shareButtonText, { color: colors.background }]}>{t('referrals.shareInvite')}</Text>
      </TouchableOpacity>

      <View style={styles.detailSection}>
        <Text style={[styles.detailSectionTitle, { color: colors.textMuted }]}>{t('referrals.applyCode')}</Text>
        <View style={[styles.editRow, { backgroundColor: colors.surface }]}>
          <TextInput style={[styles.editInput, { flex: 1, color: colors.textPrimary }]} value={promoCode}
            onChangeText={setPromoCode} placeholder={t('referrals.enterCode')}
            placeholderTextColor={colors.textMuted} autoCapitalize="characters" />
          <TouchableOpacity onPress={applyPromo} disabled={applying || !promoCode.trim()}
            style={[styles.editSaveBtn, { backgroundColor: colors.accent }]}>
            <Text style={styles.editSaveBtnText}>{applying ? '...' : t('referrals.apply')}</Text>
          </TouchableOpacity>
        </View>
        {promoMessage ? (
          <Text style={[styles.feedbackText, { color: promoMessage.includes('!') && !promoMessage.includes('Invalid') && !promoMessage.includes('expired') && !promoMessage.includes('limit') && !promoMessage.includes('already') ? colors.buy : colors.sell }]}>{promoMessage}</Text>
        ) : null}
      </View>
    </View>
  );
}

// ==================== NOTIFICATIONS VIEW ====================
function NotificationsView({ data }: { data: ProfileData }) {
  const colors = useColors();
  const t = useT();
  const { notificationSettings, updateNotificationSetting } = usePreferencesStore();

  const toggle = async (key: string) => {
    const newVal = !notificationSettings[key];
    updateNotificationSetting(key, newVal);
    doHaptic();
    try {
      await mobileApi.updatePreferences({ notificationSettings: { [key]: newVal } });
    } catch (e) { console.error('Toggle notif error:', e); }
  };

  return (
    <View>
      <View style={styles.detailSection}>
        <Text style={[styles.detailSectionTitle, { color: colors.textMuted }]}>{t('notif.signalAlerts')}</Text>
        <NotifToggle label={t('notif.decisionChanges')} enabled={notificationSettings.decisionChanges} onToggle={() => toggle('decisionChanges')} colors={colors} />
        <NotifToggle label={t('notif.confidenceShifts')} enabled={notificationSettings.confidenceShifts} onToggle={() => toggle('confidenceShifts')} colors={colors} />
        <NotifToggle label={t('notif.keyEvents')} enabled={notificationSettings.keyEvents} onToggle={() => toggle('keyEvents')} colors={colors} />
      </View>
      <View style={styles.detailSection}>
        <Text style={[styles.detailSectionTitle, { color: colors.textMuted }]}>{t('notif.edgeAlerts')}</Text>
        <NotifToggle label={t('notif.edgeOpportunities')} enabled={notificationSettings.edgeOpportunities} onToggle={() => toggle('edgeOpportunities')} colors={colors} />
        <NotifToggle label={t('notif.edgeHigh')} enabled={notificationSettings.edgeHigh} onToggle={() => toggle('edgeHigh')} colors={colors} />
      </View>
      <View style={styles.detailSection}>
        <Text style={[styles.detailSectionTitle, { color: colors.textMuted }]}>{t('notif.feed')}</Text>
        <NotifToggle label={t('notif.highImpactOnly')} enabled={notificationSettings.highImpactFeed} onToggle={() => toggle('highImpactFeed')} colors={colors} />
        <NotifToggle label={t('notif.allEvents')} enabled={notificationSettings.allFeedEvents} onToggle={() => toggle('allFeedEvents')} colors={colors} />
      </View>
      <View style={styles.detailSection}>
        <Text style={[styles.detailSectionTitle, { color: colors.textMuted }]}>{t('notif.system')}</Text>
        <NotifToggle label={t('notif.billing')} enabled={notificationSettings.billing} onToggle={() => toggle('billing')} colors={colors} />
        <NotifToggle label={t('notif.systemUpdates')} enabled={notificationSettings.systemUpdates} onToggle={() => toggle('systemUpdates')} colors={colors} />
      </View>
      <View style={styles.detailSection}>
        <Text style={[styles.detailSectionTitle, { color: colors.textMuted }]}>{t('notif.delivery')}</Text>
        <NotifToggle label={t('notif.push')} enabled={notificationSettings.push} onToggle={() => toggle('push')} colors={colors} />
        <NotifToggle label={t('notif.email')} enabled={notificationSettings.email} onToggle={() => toggle('email')} colors={colors} />
      </View>
    </View>
  );
}

// ==================== CONNECTED APPS VIEW ====================
function ConnectedView({ data }: { data: ProfileData }) {
  const colors = useColors();
  const t = useT();
  const [linking, setLinking] = React.useState(false);

  const connectTelegramMiniApp = async () => {
    setLinking(true);
    try {
      const result = await mobileApi.getTelegramLinkCode();
      if (result.success && result.botUrl) {
        Linking.openURL(result.botUrl).catch(() => {});
      }
    } catch {} finally { setLinking(false); }
  };

  const isTelegramLinked = data.authProviders?.telegram && !!data.telegramUsername;

  const apps = [
    { name: t('connected.webPlatform'), key: 'web' as const, icon: 'desktop-outline' as const, connected: data.linkedApps.web },
    { name: t('connected.telegramMiniApp'), key: 'miniapp' as const, icon: 'paper-plane-outline' as const, connected: isTelegramLinked || data.linkedApps.miniapp },
  ];

  return (
    <View>
      <View style={styles.ecosystemHeader}>
        <Image source={require('../../../../assets/branding/logo-dark.png')} style={styles.ecosystemLogo} resizeMode="contain" />
        <Text style={[styles.ecosystemTitle, { color: colors.textPrimary }]}>{t('connected.ecosystem')}</Text>
        <Text style={[styles.ecosystemSubtitle, { color: colors.textSecondary }]}>{t('connected.oneAccount')}</Text>
      </View>
      {apps.map(app => (
        <View key={app.key} style={[styles.connectedAppCard, { backgroundColor: colors.surface }]}>
          <View style={[styles.connectedAppIcon, { backgroundColor: app.connected ? colors.accent + '20' : colors.surfaceHover }]}>
            <Ionicons name={app.icon} size={22} color={app.connected ? colors.accent : colors.textMuted} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[styles.connectedAppName, { color: colors.textPrimary }]}>{app.name}</Text>
            <Text style={[styles.connectedAppStatus, { color: colors.textMuted }]}>
              {app.connected
                ? (app.key === 'miniapp' && data.telegramUsername
                    ? `@${data.telegramUsername} \u2022 ${(data.plan || 'FREE').toUpperCase()}`
                    : `${t('account.connected')} \u2022 ${(data.plan || 'FREE').toUpperCase()}`)
                : t('account.notConnected')}
            </Text>
          </View>
          {app.connected ? (
            <Ionicons name="checkmark-circle" size={20} color={colors.buy} />
          ) : (
            <TouchableOpacity
              style={[styles.connectButton, { backgroundColor: colors.accent + '20' }]}
              onPress={app.key === 'miniapp' ? connectTelegramMiniApp : undefined}
              disabled={linking}
            >
              <Text style={[styles.connectButtonText, { color: colors.accent }]}>
                {linking && app.key === 'miniapp' ? '...' : t('connected.connect')}
              </Text>
            </TouchableOpacity>
          )}
        </View>
      ))}
      <View style={styles.syncInfo}>
        <Ionicons name="sync" size={14} color={colors.textMuted} />
        <Text style={[styles.syncText, { color: colors.textMuted }]}>{t('connected.syncInfo')}</Text>
      </View>
    </View>
  );
}

// ==================== ABOUT VIEW ====================
function AboutView() {
  const colors = useColors();
  const t = useT();
  const [subView, setSubView] = React.useState<'main' | 'faq' | 'terms' | 'privacy'>('main');

  if (subView === 'faq') return <FAQView onBack={() => setSubView('main')} />;
  if (subView === 'terms') return <LegalView type="terms" onBack={() => setSubView('main')} />;
  if (subView === 'privacy') return <LegalView type="privacy" onBack={() => setSubView('main')} />;

  const openTelegramSupport = () => {
    const url = 'https://t.me/FOMO_Trading_bot?start=support';
    Linking.openURL(url).catch(() => {});
  };

  return (
    <View>
      <View style={styles.aboutHeader}>
        <Image source={require('../../../../assets/branding/logo-dark.png')} style={styles.aboutLogo} resizeMode="contain" />
        <Text style={[styles.aboutVersion, { color: colors.textMuted }]}>{t('about.version')}</Text>
      </View>
      <View style={styles.detailSection}>
        {[
          { icon: 'chatbubble-ellipses-outline', label: t('about.supportChat'), action: openTelegramSupport },
          { icon: 'help-circle-outline', label: t('about.faq'), action: () => setSubView('faq') },
        ].map((item) => (
          <TouchableOpacity key={item.label} style={[styles.actionRow, { borderBottomColor: colors.border }]} onPress={item.action}>
            <Ionicons name={item.icon as any} size={18} color={colors.textSecondary} />
            <Text style={[styles.actionRowText, { color: colors.textPrimary }]}>{item.label}</Text>
            <Ionicons name="chevron-forward" size={16} color={colors.textMuted} />
          </TouchableOpacity>
        ))}
      </View>
      <View style={styles.detailSection}>
        {[
          { icon: 'document-text-outline', label: t('about.terms'), action: () => setSubView('terms') },
          { icon: 'shield-outline', label: t('about.privacy'), action: () => setSubView('privacy') },
        ].map((item) => (
          <TouchableOpacity key={item.label} style={[styles.actionRow, { borderBottomColor: colors.border }]} onPress={item.action}>
            <Ionicons name={item.icon as any} size={18} color={colors.textSecondary} />
            <Text style={[styles.actionRowText, { color: colors.textPrimary }]}>{item.label}</Text>
            <Ionicons name="chevron-forward" size={16} color={colors.textMuted} />
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

// ==================== FAQ View ====================
function FAQView({ onBack }: { onBack: () => void }) {
  const colors = useColors();
  const t = useT();
  const lang = usePreferencesStore((s) => s.language);
  const [expanded, setExpanded] = React.useState<number | null>(null);

  const faqItems = lang === 'ru' ? [
    { q: 'Что такое FOMO?', a: 'FOMO — это AI-платформа для трейдинга, которая анализирует рынок по множеству факторов (деривативы, on-chain, сентимент, фрактальный анализ) и выдаёт понятные сигналы BUY / SELL / WAIT с уровнем уверенности.' },
    { q: 'Как работают сигналы?', a: 'Наш движок собирает данные из 4+ модулей: биржевые деривативы (фандинг, OI, ликвидации), on-chain метрики (китовые кошельки, потоки на биржи), сентимент (Fear & Greed, социальные сети) и технический анализ. Все модули голосуют и формируют итоговый вердикт.' },
    { q: 'Что такое Edge?', a: 'Edge — это разница между нашей моделью и рыночными вероятностями. Когда модель оценивает актив иначе, чем рынок — это и есть edge, возможность для сделки с преимуществом.' },
    { q: 'Чем отличается FREE от PRO?', a: 'FREE даёт базовые сигналы. PRO открывает: полную аналитику по модулям (Deep Intelligence), Edge-возможности, обоснования сигналов, расширенную ленту событий и приоритетные уведомления.' },
    { q: 'Как подключить Telegram?', a: 'В разделе «Привязанные приложения» нажмите «Connect» рядом с Telegram MiniApp. Приложение откроет бота @FOMO_Trading_bot, который автоматически привяжет ваш Telegram к аккаунту. После привязки подписка и данные синхронизируются между всеми платформами.' },
    { q: 'Как отменить подписку?', a: 'Управление подпиской происходит через веб-платформу. В разделе «Подписка и доступ» нажмите «Управление оплатой на вебе». Подписка действует до конца оплаченного периода.' },
    { q: 'Данные безопасны?', a: 'Да. Мы используем шифрование, двухфакторную аутентификацию (2FA) и никогда не передаём персональные данные третьим лицам. Ваши ключи API от бирж не хранятся на наших серверах.' },
    { q: 'Как связаться с поддержкой?', a: 'Напишите нашему боту @FOMO_Trading_bot в Telegram — команда /support. Мы ответим в ближайшее время.' },
  ] : [
    { q: 'What is FOMO?', a: 'FOMO is an AI-powered trading intelligence platform that analyzes markets using multiple factors (derivatives, on-chain, sentiment, fractal analysis) and delivers clear BUY / SELL / WAIT signals with confidence levels.' },
    { q: 'How do signals work?', a: 'Our engine collects data from 4+ modules: exchange derivatives (funding, OI, liquidations), on-chain metrics (whale wallets, exchange flows), sentiment (Fear & Greed, social media), and technical analysis. All modules vote to form the final verdict.' },
    { q: 'What is Edge?', a: 'Edge is the difference between our model probability and market probability. When our model values an asset differently than the market — that is edge, an opportunity to trade with an advantage.' },
    { q: 'What is the difference between FREE and PRO?', a: 'FREE gives you basic signals. PRO unlocks: full module analytics (Deep Intelligence), Edge opportunities, signal reasoning, extended event feed, and priority notifications.' },
    { q: 'How do I connect Telegram?', a: 'In "Connected Apps", tap "Connect" next to Telegram MiniApp. The app will open @FOMO_Trading_bot which automatically links your Telegram to your account. After linking, your subscription and data sync across all platforms.' },
    { q: 'How do I cancel my subscription?', a: 'Subscription management is on the web platform. In "Subscription & Access", click "Manage Billing on Web". Your subscription remains active until the end of the paid period.' },
    { q: 'Is my data safe?', a: 'Yes. We use encryption, two-factor authentication (2FA), and never share personal data with third parties. Your exchange API keys are never stored on our servers.' },
    { q: 'How do I contact support?', a: 'Message our bot @FOMO_Trading_bot on Telegram — use the /support command. We will respond as soon as possible.' },
  ];

  return (
    <ScrollView style={{ flex: 1 }}>
      <Text style={[styles.sectionLabel, { color: colors.textMuted, marginBottom: 16 }]}>
        {lang === 'ru' ? 'ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ' : 'FREQUENTLY ASKED QUESTIONS'}
      </Text>
      {faqItems.map((item, idx) => (
        <TouchableOpacity
          key={idx}
          style={[styles.faqItem, { backgroundColor: colors.surface, borderColor: expanded === idx ? colors.accent + '40' : 'transparent' }]}
          onPress={() => setExpanded(expanded === idx ? null : idx)}
          activeOpacity={0.7}
        >
          <View style={styles.faqHeader}>
            <Text style={[styles.faqQuestion, { color: colors.textPrimary }]}>{item.q}</Text>
            <Ionicons name={expanded === idx ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textMuted} />
          </View>
          {expanded === idx && (
            <Text style={[styles.faqAnswer, { color: colors.textSecondary, borderTopColor: colors.border }]}>{item.a}</Text>
          )}
        </TouchableOpacity>
      ))}
    </ScrollView>
  );
}

// ==================== Legal View (Terms / Privacy) ====================
function LegalView({ type, onBack }: { type: 'terms' | 'privacy'; onBack: () => void }) {
  const colors = useColors();
  const lang = usePreferencesStore((s) => s.language);

  const termsRu = `ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ\nFOMO Intelligence Platform\nДата вступления в силу: 1 января 2025\n\n1. ОБЩИЕ ПОЛОЖЕНИЯ\n\n1.1. Настоящее Соглашение регулирует отношения между FOMO Intelligence («Платформа», «мы», «наш») и пользователем («вы», «Пользователь»).\n\n1.2. Используя Платформу, вы подтверждаете, что ознакомились с настоящим Соглашением и принимаете его условия.\n\n2. ОПИСАНИЕ СЕРВИСА\n\n2.1. FOMO предоставляет аналитические данные и AI-сигналы для рынков криптовалют. Сервис включает:\n- Генерацию торговых сигналов (BUY/SELL/WAIT)\n- Аналитику деривативов, on-chain метрик и сентимента\n- Edge-возможности (расхождение модели и рынка)\n- Push-уведомления о важных событиях\n\n2.2. Платформа НЕ является финансовым советником. Все сигналы носят информационный характер.\n\n3. ОТВЕТСТВЕННОСТЬ\n\n3.1. FOMO не несёт ответственности за финансовые потери, понесённые в результате использования сигналов или аналитики Платформы.\n\n3.2. Вы принимаете на себя полную ответственность за свои торговые решения.\n\n4. ПОДПИСКА И ОПЛАТА\n\n4.1. Базовый доступ (FREE) предоставляется бесплатно с ограниченным функционалом.\n\n4.2. Подписка PRO оплачивается ежемесячно или ежегодно через крипто-платежи (NOWPayments).\n\n4.3. Возврат средств возможен в течение 7 дней с момента оплаты.\n\n5. ИНТЕЛЛЕКТУАЛЬНАЯ СОБСТВЕННОСТЬ\n\n5.1. Все алгоритмы, модели, интерфейсы и контент Платформы являются интеллектуальной собственностью FOMO.\n\n5.2. Запрещено копирование, реверс-инжиниринг или перепродажа данных Платформы.\n\n6. ПРЕКРАЩЕНИЕ\n\n6.1. Мы оставляем за собой право приостановить или прекратить доступ к Платформе в случае нарушения условий Соглашения.`;

  const termsEn = `TERMS OF SERVICE\nFOMO Intelligence Platform\nEffective Date: January 1, 2025\n\n1. GENERAL PROVISIONS\n\n1.1. This Agreement governs the relationship between FOMO Intelligence ("Platform", "we", "our") and the user ("you", "User").\n\n1.2. By using the Platform, you confirm that you have read and accept the terms of this Agreement.\n\n2. SERVICE DESCRIPTION\n\n2.1. FOMO provides analytical data and AI signals for cryptocurrency markets. The service includes:\n- Trading signal generation (BUY/SELL/WAIT)\n- Derivatives, on-chain metrics, and sentiment analytics\n- Edge opportunities (model vs market divergence)\n- Push notifications for important events\n\n2.2. The Platform is NOT a financial advisor. All signals are informational in nature.\n\n3. LIABILITY\n\n3.1. FOMO is not responsible for financial losses incurred as a result of using the Platform's signals or analytics.\n\n3.2. You assume full responsibility for your trading decisions.\n\n4. SUBSCRIPTION AND PAYMENT\n\n4.1. Basic access (FREE) is provided free of charge with limited functionality.\n\n4.2. PRO subscription is paid monthly or annually via crypto payments (NOWPayments).\n\n4.3. Refunds are available within 7 days of payment.\n\n5. INTELLECTUAL PROPERTY\n\n5.1. All algorithms, models, interfaces, and content of the Platform are the intellectual property of FOMO.\n\n5.2. Copying, reverse engineering, or reselling Platform data is prohibited.\n\n6. TERMINATION\n\n6.1. We reserve the right to suspend or terminate access to the Platform in case of violation of the Agreement terms.`;

  const privacyRu = `ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ\nFOMO Intelligence Platform\nДата вступления в силу: 1 января 2025\n\n1. СОБИРАЕМЫЕ ДАННЫЕ\n\n1.1. При регистрации: email, имя, аватар (через Google OAuth).\n\n1.2. При использовании: предпочтения (тема, язык, актив), история активности, device token для push-уведомлений.\n\n1.3. При подписке: платежи обрабатываются через крипто-шлюз NOWPayments. Мы не храним данные кошельков.\n\n2. ИСПОЛЬЗОВАНИЕ ДАННЫХ\n\n2.1. Для предоставления сервиса: персонализация сигналов, уведомления, аналитика.\n\n2.2. Для улучшения: анонимная статистика использования для развития продукта.\n\n2.3. Мы НЕ продаём и НЕ передаём персональные данные третьим лицам, кроме случаев, предусмотренных законом.\n\n3. ХРАНЕНИЕ\n\n3.1. Данные хранятся на защищённых серверах с шифрованием.\n\n3.2. Пароли хранятся в виде bcrypt-хэшей.\n\n3.3. Сессии защищены JWT-токенами с ограниченным сроком действия.\n\n4. ПРАВА ПОЛЬЗОВАТЕЛЯ\n\n4.1. Вы имеете право запросить копию своих данных.\n\n4.2. Вы имеете право на удаление аккаунта и всех связанных данных.\n\n4.3. Вы можете отказаться от push-уведомлений и email-рассылки.\n\n5. БЕЗОПАСНОСТЬ\n\n5.1. Мы используем HTTPS, шифрование данных в покое, двухфакторную аутентификацию (2FA/TOTP).\n\n5.2. Регулярные аудиты безопасности.\n\n6. КОНТАКТЫ\n\nПо вопросам конфиденциальности: @FOMO_Trading_bot (Telegram, команда /support)`;

  const privacyEn = `PRIVACY POLICY\nFOMO Intelligence Platform\nEffective Date: January 1, 2025\n\n1. DATA COLLECTED\n\n1.1. During registration: email, name, avatar (via Google OAuth).\n\n1.2. During usage: preferences (theme, language, asset), activity history, device token for push notifications.\n\n1.3. During subscription: payments are processed via NOWPayments crypto gateway. We do not store wallet data.\n\n2. DATA USAGE\n\n2.1. To provide the service: signal personalization, notifications, analytics.\n\n2.2. To improve: anonymous usage statistics for product development.\n\n2.3. We do NOT sell or share personal data with third parties, except as required by law.\n\n3. STORAGE\n\n3.1. Data is stored on encrypted, secure servers.\n\n3.2. Passwords are stored as bcrypt hashes.\n\n3.3. Sessions are protected by JWT tokens with limited validity.\n\n4. USER RIGHTS\n\n4.1. You have the right to request a copy of your data.\n\n4.2. You have the right to delete your account and all related data.\n\n4.3. You can opt out of push notifications and email newsletters.\n\n5. SECURITY\n\n5.1. We use HTTPS, data-at-rest encryption, two-factor authentication (2FA/TOTP).\n\n5.2. Regular security audits.\n\n6. CONTACT\n\nFor privacy inquiries: @FOMO_Trading_bot (Telegram, /support command)`;

  const content = type === 'terms'
    ? (lang === 'ru' ? termsRu : termsEn)
    : (lang === 'ru' ? privacyRu : privacyEn);

  return (
    <ScrollView style={{ flex: 1 }}>
      <Text style={[styles.legalText, { color: colors.textPrimary }]}>{content}</Text>
      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

// ==================== Utility Components ====================
function DetailRow({ label, value, editable, colors }: { label: string; value: string; editable?: boolean; colors: any }) {
  return (
    <View style={[styles.detailRow, { borderBottomColor: colors.border }]}>
      <Text style={[styles.detailLabel, { color: colors.textSecondary }]}>{label}</Text>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
        <Text style={[styles.detailValue, { color: colors.textPrimary }]}>{value}</Text>
        {editable && <Ionicons name="pencil" size={12} color={colors.accent} />}
      </View>
    </View>
  );
}

function ProviderRow({ name, connected, colors }: { name: string; connected: boolean; colors: any }) {
  const t = useT();
  return (
    <View style={[styles.providerRow, { borderBottomColor: colors.border }]}>
      <Ionicons name={connected ? 'checkmark-circle' : 'ellipse-outline'} size={18} color={connected ? colors.buy : colors.textMuted} />
      <Text style={[styles.providerName, { color: colors.textPrimary }]}>{name}</Text>
      <Text style={{ fontSize: 11, color: connected ? colors.buy : colors.textMuted }}>
        {connected ? t('account.connected') : t('account.notConnected')}
      </Text>
    </View>
  );
}

function RadioOption({ label, value, current, colors, saving }: { label: string; value: string; current: string; colors: any; saving?: boolean }) {
  const isActive = current === value;
  return (
    <View style={styles.themeOption}>
      <View style={[styles.themeRadio, { borderColor: isActive ? colors.accent : colors.textMuted }]}>
        {isActive && <View style={[styles.themeRadioDot, { backgroundColor: colors.accent }]} />}
      </View>
      <Text style={[styles.themeLabel, { color: isActive ? colors.textPrimary : colors.textSecondary }]}>{label}</Text>
    </View>
  );
}

function NotifToggle({ label, enabled, onToggle, colors }: { label: string; enabled: boolean; onToggle?: () => void; colors: any }) {
  return (
    <TouchableOpacity style={[styles.notifRow, { borderBottomColor: colors.border }]} onPress={onToggle} activeOpacity={0.7}>
      <Text style={[styles.notifLabel, { color: colors.textPrimary }]}>{label}</Text>
      <View style={[styles.toggle, { backgroundColor: enabled ? colors.accent : colors.surfaceHover }]}>
        <View style={[styles.toggleDot, { backgroundColor: enabled ? '#FFFFFF' : colors.textMuted, alignSelf: enabled ? 'flex-end' : 'flex-start' }]} />
      </View>
    </TouchableOpacity>
  );
}

// ==================== STYLES ====================
const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { paddingHorizontal: 16, paddingTop: 16 },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  loadingText: { marginTop: 16 },
  errorText: { fontSize: 14 },
  profileHeader: { flexDirection: 'row', alignItems: 'center', padding: 24, borderRadius: 16, marginBottom: 16 },
  avatarContainer: { position: 'relative' },
  avatarEditBadge: { position: 'absolute', bottom: 0, right: 0, width: 20, height: 20, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  avatar: { width: 60, height: 60, borderRadius: 30, alignItems: 'center', justifyContent: 'center' },
  statusDot: { position: 'absolute', top: 0, right: 0, width: 12, height: 12, borderRadius: 6, borderWidth: 2 },
  profileInfo: { marginLeft: 16, flex: 1 },
  profileName: { fontSize: 16, fontWeight: '700' },
  profileEmail: { fontSize: 12, marginTop: 2 },
  planBadge: { marginTop: 6, paddingHorizontal: 10, paddingVertical: 3, borderRadius: 9999, alignSelf: 'flex-start' },
  planBadgeText: { fontSize: 10, fontWeight: '700', letterSpacing: 1 },
  statsRow: { flexDirection: 'row', borderRadius: 10, padding: 16, marginBottom: 24 },
  /* Telegram Connect / Connected banner (growth hook) */
  tgBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    borderRadius: 12,
    borderWidth: 1,
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginBottom: 18,
  },
  tgBannerIcon: {
    width: 36, height: 36, borderRadius: 18,
    alignItems: 'center', justifyContent: 'center',
  },
  tgBannerTitle: { fontSize: 14, fontWeight: '800', letterSpacing: -0.2 },
  tgBannerSub: { fontSize: 12, fontWeight: '500', marginTop: 2 },
  lossCard: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 12, marginBottom: 20, borderWidth: 1 },
  lossIcon: { width: 36, height: 36, borderRadius: 10, backgroundColor: 'rgba(220,38,38,0.08)', alignItems: 'center', justifyContent: 'center' },
  lossTitle: { fontSize: 14, fontWeight: '700', letterSpacing: -0.1 },
  lossSub: { fontSize: 12, marginTop: 2, fontWeight: '500' },
  statItem: { flex: 1, alignItems: 'center' },
  statValue: { fontSize: 14, fontWeight: '700' },
  statLabel: { fontSize: 9, marginTop: 2 },
  statDivider: { width: 1, marginVertical: 2 },
  sectionCard: { flexDirection: 'row', alignItems: 'center', padding: 16, borderRadius: 10, marginBottom: 8 },
  sectionIconContainer: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  sectionContent: { flex: 1, marginLeft: 16 },
  sectionTitle: { fontSize: 14, fontWeight: '600' },
  sectionSubtitle: { fontSize: 11, marginTop: 2 },
  signOutButton: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: 16, marginTop: 24, gap: 8 },
  signOutText: { fontSize: 14, fontWeight: '600' },
  editRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8, paddingHorizontal: 12, borderRadius: 10, marginBottom: 8 },
  editInput: { flex: 1, fontSize: 14, paddingVertical: 4 },
  editSaveBtn: { paddingHorizontal: 12, paddingVertical: 5, borderRadius: 6 },
  editSaveBtnText: { color: '#fff', fontSize: 12, fontWeight: '700' },
  subHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 8, borderBottomWidth: 1 },
  backButton: { padding: 4 },
  subHeaderTitle: { fontSize: 16, fontWeight: '700' },
  subContent: { flex: 1, paddingHorizontal: 16, paddingTop: 16 },
  detailSection: { marginBottom: 24 },
  detailSectionTitle: { fontSize: 9, fontWeight: '700', letterSpacing: 1, marginBottom: 8 },
  detailRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 8, borderBottomWidth: 1 },
  detailLabel: { fontSize: 12 },
  detailValue: { fontSize: 12, fontWeight: '600' },
  providerRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8, borderBottomWidth: 1 },
  providerName: { fontSize: 12, flex: 1 },
  sessionCard: { flexDirection: 'row', alignItems: 'center', padding: 16, borderRadius: 10 },
  sessionDevice: { fontSize: 12, fontWeight: '600' },
  sessionMeta: { fontSize: 11, marginTop: 2 },
  currentBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 9999 },
  currentBadgeText: { fontSize: 10, fontWeight: '700' },
  feedbackText: { fontSize: 11, marginTop: 6, paddingHorizontal: 4 },
  passwordForm: { marginBottom: 8 },
  planCard: { padding: 24, borderRadius: 16, marginBottom: 24, borderWidth: 1 },
  planCardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  planCardTitle: { fontSize: 18, fontWeight: '800' },
  planCardStatus: { fontSize: 11, marginTop: 2, fontWeight: '600' },
  planCardPrice: { fontSize: 16, fontWeight: '700' },
  planCardDivider: { height: 1, marginVertical: 16 },
  planRenewal: { fontSize: 12 },
  accessRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8, borderBottomWidth: 1 },
  accessName: { fontSize: 12, flex: 1 },
  upgradeButton: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: 16, borderRadius: 10, gap: 8, marginBottom: 8 },
  expiredBanner: { flexDirection: 'row', alignItems: 'center', padding: 16, borderRadius: 12, marginBottom: 16, borderWidth: 1 },
  expiredTitle: { fontSize: 14, fontWeight: '700', marginBottom: 4 },
  expiredSubtitle: { fontSize: 12, lineHeight: 18 },
  reactivateButton: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: 16, borderRadius: 10, gap: 8, marginBottom: 8 },

  upgradeButtonText: { fontSize: 14, fontWeight: '700' },
  secondaryButton: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: 16, gap: 8, borderWidth: 1, borderRadius: 10 },
  secondaryButtonText: { fontSize: 12, fontWeight: '600' },
  referralStats: { flexDirection: 'row', borderRadius: 16, padding: 24, marginBottom: 24 },
  referralStatItem: { flex: 1, alignItems: 'center' },
  referralStatValue: { fontSize: 18, fontWeight: '800' },
  referralStatLabel: { fontSize: 10, marginTop: 4 },
  codeCard: { padding: 24, borderRadius: 10, marginBottom: 16 },
  codeLabel: { fontSize: 9, fontWeight: '700', letterSpacing: 1, marginBottom: 8 },
  codeRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  codeValue: { fontSize: 18, fontWeight: '700', letterSpacing: 2 },
  copyButton: { flexDirection: 'row', alignItems: 'center', gap: 4, padding: 8 },
  copyButtonText: { fontSize: 12, fontWeight: '600' },
  shareButton: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: 16, borderRadius: 10, gap: 8, marginBottom: 24 },
  shareButtonText: { fontSize: 14, fontWeight: '700' },
  themeOption: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8 },
  themeRadio: { width: 22, height: 22, borderRadius: 11, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  themeRadioDot: { width: 12, height: 12, borderRadius: 6 },
  themeLabel: { fontSize: 14 },
  assetGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  assetChip: { paddingHorizontal: 24, paddingVertical: 8, borderRadius: 9999, borderWidth: 1 },
  assetChipText: { fontSize: 12, fontWeight: '600' },
  actionRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 16, borderBottomWidth: 1 },
  actionRowText: { fontSize: 14, flex: 1 },
  securityCard: { flexDirection: 'row', alignItems: 'center', padding: 16, borderRadius: 10, marginBottom: 8 },
  securityCardTitle: { fontSize: 12, fontWeight: '600' },
  securityCardDesc: { fontSize: 11, marginTop: 2 },
  historyItem: { paddingVertical: 8, borderBottomWidth: 1 },
  historyDevice: { fontSize: 12, fontWeight: '600' },
  historyMeta: { fontSize: 11, marginTop: 2 },
  ecosystemHeader: { alignItems: 'center', marginBottom: 24 },
  ecosystemLogo: { width: 80, height: 28, marginBottom: 8 },
  ecosystemTitle: { fontSize: 16, fontWeight: '700' },
  ecosystemSubtitle: { fontSize: 12, marginTop: 4 },
  connectedAppCard: { flexDirection: 'row', alignItems: 'center', padding: 16, borderRadius: 10, marginBottom: 8 },
  connectedAppIcon: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center', marginRight: 16 },
  connectedAppName: { fontSize: 14, fontWeight: '600' },
  connectedAppStatus: { fontSize: 11, marginTop: 2 },
  connectButton: { paddingHorizontal: 16, paddingVertical: 6, borderRadius: 9999 },
  connectButtonText: { fontSize: 11, fontWeight: '600' },
  syncInfo: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, padding: 16, marginTop: 8 },
  syncText: { fontSize: 11, flex: 1, lineHeight: 16 },
  notifRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1 },
  notifLabel: { fontSize: 12, flex: 1, marginRight: 16 },
  toggle: { width: 42, height: 24, borderRadius: 12, backgroundColor: '#16202B', justifyContent: 'center', paddingHorizontal: 2 },
  toggleDot: { width: 20, height: 20, borderRadius: 10, backgroundColor: '#6B7C8F' },
  toggleDotActive: { backgroundColor: '#0B0F14', alignSelf: 'flex-end' },
  aboutHeader: { alignItems: 'center', marginBottom: 24, paddingVertical: 24 },
  aboutLogo: { width: 120, height: 40, marginBottom: 8 },
  aboutVersion: { fontSize: 12 },
  // FAQ styles
  faqItem: { borderRadius: 10, padding: 16, marginBottom: 8, borderWidth: 1 },
  faqHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  faqQuestion: { fontSize: 14, fontWeight: '600', flex: 1, marginRight: 8 },
  faqAnswer: { fontSize: 13, lineHeight: 20, marginTop: 12, paddingTop: 12, borderTopWidth: 1 },
  // Legal styles
  legalText: { fontSize: 13, lineHeight: 22 },
  sectionLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 1 },
});
