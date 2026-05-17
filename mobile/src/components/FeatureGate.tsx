import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Platform,
} from 'react-native';
import { BlurView } from 'expo-blur';
import { Ionicons } from '@expo/vector-icons';
import { useSessionStore } from '../stores/session.store';
import { theme } from '../core/theme';
import { useColors } from '../core/useColors';
import { usePreferencesStore } from '../stores/preferences.store';
import { useT } from '../core/i18n';

export type FeatureType =
  | 'deep_intel'
  | 'edge'
  | 'feed_explanation'
  | 'signal_reason';

function getFeatureConfig(t: (key: string) => string): Record<FeatureType, { title: string; desc: string; teasers: string[] }> {
  return {
    deep_intel: {
      title: t('pro.deepIntel.title'),
      desc: t('pro.deepIntel.desc'),
      teasers: [t('pro.deepIntel.t1'), t('pro.deepIntel.t2'), t('pro.deepIntel.t3')],
    },
    edge: {
      title: t('pro.edge.title'),
      desc: t('pro.edge.desc'),
      teasers: [t('pro.edge.t1'), t('pro.edge.t2'), t('pro.edge.t3')],
    },
    feed_explanation: {
      title: t('pro.feedExp.title'),
      desc: t('pro.feedExp.desc'),
      teasers: [t('pro.feedExp.t1'), t('pro.feedExp.t2'), t('pro.feedExp.t3')],
    },
    signal_reason: {
      title: t('pro.signalReason.title'),
      desc: t('pro.signalReason.desc'),
      teasers: [t('pro.signalReason.t1'), t('pro.signalReason.t2'), t('pro.signalReason.t3')],
    },
  };
}

export function FeatureGate({
  feature,
  children,
  onUnlock,
}: {
  feature: FeatureType;
  children: React.ReactNode;
  onUnlock?: () => void;
}) {
  const colors = useColors();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);
  const user = useSessionStore((s) => s.user);
  const isPro = user?.plan === 'PRO' || user?.plan === 'INSTITUTIONAL';
  const t = useT();

  if (isPro) return <>{children}</>;

  const config = getFeatureConfig(t)[feature];

  return (
    <View style={styles.container}>
      {/* Dimmed content behind */}
      <View style={styles.contentBehind} pointerEvents="none">
        {children}
      </View>

      {/* Blur overlay */}
      {Platform.OS === 'web' ? (
        <View style={[styles.overlay, styles.webBlur]}>
          <LockContent config={config} onUnlock={onUnlock} />
        </View>
      ) : (
        <BlurView intensity={50} tint={usePreferencesStore.getState().resolvedTheme} style={styles.overlay}>
          <LockContent config={config} onUnlock={onUnlock} />
        </BlurView>
      )}
    </View>
  );
}

function LockContent({
  config,
  onUnlock,
}: {
  config: { title: string; desc: string; teasers: string[] };
  onUnlock?: () => void;
}) {
  const colors = useColors();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);
  const t = useT();
  return (
    <View style={styles.lockContent}>
      <View style={styles.lockIconWrap}>
        <Ionicons name="lock-closed" size={24} color={colors.accent} />
      </View>

      <Text style={styles.lockTitle}>{t('pro.feature')}</Text>
      <Text style={styles.lockDesc}>{config.desc}</Text>

      <View style={styles.teaserList}>
        {config.teasers.map((item, i) => (
          <View key={i} style={styles.teaserRow}>
            <Ionicons name="checkmark-circle" size={14} color={colors.buy} />
            <Text style={styles.teaserText}>{item}</Text>
          </View>
        ))}
      </View>

      <TouchableOpacity
        style={styles.unlockBtn}
        onPress={onUnlock}
        activeOpacity={0.8}
      >
        <Ionicons name="flash" size={16} color="#000" />
        <Text style={styles.unlockBtnText}>{t('pro.unlock')}</Text>
      </TouchableOpacity>
    </View>
  );
}

const makeStyles = (colors: any) => StyleSheet.create({
  container: {
    position: 'relative',
    overflow: 'hidden',
    borderRadius: theme.radius.lg,
    minHeight: 200,
  },
  contentBehind: {
    opacity: 0.15,
  },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  webBlur: {
    backgroundColor: colors.background + 'D9',
  },
  lockContent: {
    alignItems: 'center',
    maxWidth: 280,
  },
  lockIconWrap: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.accent + '20',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  lockTitle: {
    color: colors.accent,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 2,
    marginBottom: 8,
  },
  lockDesc: {
    color: colors.textPrimary,
    fontSize: 15,
    fontWeight: '600',
    textAlign: 'center',
    marginBottom: 16,
    lineHeight: 20,
  },
  teaserList: {
    gap: 8,
    marginBottom: 20,
    alignSelf: 'stretch',
  },
  teaserRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  teaserText: {
    color: colors.textSecondary,
    fontSize: 13,
  },
  unlockBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.buy,
    paddingVertical: 12,
    paddingHorizontal: 28,
    borderRadius: 12,
    gap: 6,
    minHeight: 48,
    minWidth: 180,
  },
  unlockBtnText: {
    color: '#000',
    fontSize: 15,
    fontWeight: '700',
  },
});
