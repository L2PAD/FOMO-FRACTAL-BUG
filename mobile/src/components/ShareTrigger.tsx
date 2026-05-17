import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Share, Platform, Animated } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../core/useColors';
import { useSessionStore } from '../stores/session.store';

type TriggerType = 'profit' | 'regret' | 'edge' | 'streak';

interface Props {
  type: TriggerType;
  asset: string;
  pnl?: number;
  isLeader?: boolean;
  message?: string;
}

const PROFIT_VARIANTS = [
  (a: string, p: number) => `Caught ${a} before the move — +${p.toFixed(1)}%`,
  (a: string, p: number) => `Entered ${a} early — +${p.toFixed(1)}%`,
  (a: string, p: number) => `Positioned before others — ${a} +${p.toFixed(1)}%`,
  (a: string, p: number) => `${a} +${p.toFixed(1)}% — this was obvious early`,
];

const SHARE_PREFIXES = [
  'Top users already positioned.',
  'Most users entered later.',
  'Early positioning pays off.',
  'Before it was obvious.',
];

export function ShareTrigger({ type, asset, pnl = 0, isLeader, message }: Props) {
  const colors = useColors();
  const user = useSessionStore(s => s.user);
  const code = user?.referrals?.code || 'FOMO';
  const [phase, setPhase] = useState<'trigger' | 'feedback'>('trigger');
  const [fadeAnim] = useState(new Animated.Value(1));

  const variant = Math.floor(Math.random() * PROFIT_VARIANTS.length);
  const prefix = SHARE_PREFIXES[Math.floor(Math.random() * SHARE_PREFIXES.length)];

  const cfg = getConfig(type, asset, pnl, isLeader, variant);
  const headline = message || cfg.headline;
  const sub = cfg.sub;
  const cta = cfg.cta;
  const bgColor = type === 'regret' ? colors.sell + '08' : type === 'profit' ? colors.buy + '08' : colors.accent + '08';
  const borderColor = type === 'regret' ? colors.sell + '25' : type === 'profit' ? colors.buy + '25' : colors.accent + '25';
  const ctaColor = type === 'regret' ? colors.sell : colors.accent;

  const doShare = async () => {
    const shareUrl = `https://expo-telegram-web.preview.emergentagent.com/r/${code}?asset=${asset}`;
    const shareVariant = PROFIT_VARIANTS[variant](asset, pnl);
    const text = type === 'profit'
      ? `${prefix}\n${shareVariant}\n\nJoin FOMO — see the market before others.\n${shareUrl}`
      : type === 'regret'
      ? `${asset} moved +${Math.abs(pnl).toFixed(1)}%.\nI saw it forming. Next time — don't miss it.\n\n${shareUrl}`
      : `${asset} is forming — early positioning.\n${prefix}\n${shareUrl}`;

    try {
      await Share.share({ message: text });
      setPhase('feedback');
      setTimeout(() => {
        Animated.timing(fadeAnim, { toValue: 0, duration: 3000, useNativeDriver: true }).start();
      }, 4000);
    } catch {}
  };

  // Post-share feedback
  if (phase === 'feedback') {
    return (
      <Animated.View testID="share-feedback" style={[s.container, { backgroundColor: colors.buy + '08', borderColor: colors.buy + '25', opacity: fadeAnim }]}>
        <Ionicons name="checkmark-circle" size={20} color={colors.buy} />
        <View style={s.feedbackContent}>
          <Text style={[s.feedbackTitle, { color: colors.buy }]}>Shared successfully</Text>
          <Text style={[s.feedbackSub, { color: colors.textMuted }]}>Rank updates when they join. You're closer to Top 10.</Text>
        </View>
      </Animated.View>
    );
  }

  return (
    <View testID={`share-trigger-${type}`} style={[s.container, { backgroundColor: bgColor, borderColor }]}>
      <View style={s.content}>
        <Text style={[s.headline, { color: colors.textPrimary }]}>{headline}</Text>
        <Text style={[s.sub, { color: colors.textMuted }]}>{sub}</Text>
      </View>
      <TouchableOpacity testID={`share-trigger-${type}-btn`} style={[s.btn, { backgroundColor: ctaColor }]} onPress={doShare}>
        <Ionicons name="share-outline" size={14} color="#fff" />
        <Text style={s.btnText}>{cta}</Text>
      </TouchableOpacity>
    </View>
  );
}

function getConfig(type: TriggerType, a: string, p: number, isLeader?: boolean, v: number = 0) {
  switch (type) {
    case 'profit':
      return {
        headline: isLeader ? `${a} +${p.toFixed(1)}% — leading your portfolio` : `${a} +${p.toFixed(1)}%`,
        sub: isLeader ? 'Your best performer. Show how early works.' : 'Momentum continues. Share your edge.',
        cta: 'Share this →',
      };
    case 'regret':
      return {
        headline: 'You saw this. You hesitated.',
        sub: `${a} +${Math.abs(p).toFixed(1)}% since then. Next time — don't miss it.`,
        cta: 'Share →',
      };
    case 'edge':
      return {
        headline: `${a} — caught before the signal`,
        sub: 'Now it\'s moving. Let others see what early looks like.',
        cta: 'Share edge →',
      };
    case 'streak':
      return {
        headline: `${p}-day winning streak`,
        sub: 'You\'re getting consistent. Keep the momentum.',
        cta: 'Share streak →',
      };
  }
}

const s = StyleSheet.create({
  container: { borderWidth: 1, borderRadius: 12, padding: 14, marginTop: 10, flexDirection: 'row', alignItems: 'center', gap: 12 },
  content: { flex: 1 },
  headline: { fontSize: 14, fontWeight: '700', marginBottom: 2 },
  sub: { fontSize: 12, lineHeight: 16 },
  btn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8 },
  btnText: { color: '#fff', fontSize: 12, fontWeight: '700' },
  feedbackContent: { flex: 1 },
  feedbackTitle: { fontSize: 14, fontWeight: '700' },
  feedbackSub: { fontSize: 12, marginTop: 2 },
});
