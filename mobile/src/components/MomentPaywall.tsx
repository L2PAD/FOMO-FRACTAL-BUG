/**
 * MomentPaywall — inline paywall trigger at emotion points.
 * NOT a full-screen paywall. Shows at: profit, regret, edge, urgency moments.
 * 
 * Types:
 *   profit  → "You caught this early. Do it consistently."
 *   regret  → "You saw this. You didn't act. PRO users did."
 *   urgency → "This setup will confirm soon. Unlock before it does."
 *   edge    → "You see the opportunity. PRO users see the exact entry."
 *   social  → "Top 10 are all PRO users."
 */
import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../core/useColors';
import { useSessionStore } from '../stores/session.store';
import { openPaywall } from '../utils/paywall-controller';

type MomentType = 'profit' | 'regret' | 'urgency' | 'edge' | 'social' | 'portfolio';

interface Props {
  type: MomentType;
  asset?: string;
  pnl?: number;
  compact?: boolean;
}

const CONFIGS: Record<MomentType, { icon: string; title: string; sub: string; cta: string; color: 'accent' | 'buy' | 'sell' }> = {
  profit: {
    icon: 'trending-up',
    title: 'Entry zone identified.',
    sub: 'PRO users already positioned. This setup previously returned profit.',
    cta: 'Unlock exact entry',
    color: 'buy',
  },
  regret: {
    icon: 'alert-circle',
    title: 'You saw this. You hesitated.',
    sub: 'PRO users had entry, target, and invalidation. They acted.',
    cta: 'Don\'t miss again',
    color: 'sell',
  },
  urgency: {
    icon: 'time',
    title: 'Setup confirming now.',
    sub: 'PRO users are positioning. Entry window closing.',
    cta: 'Unlock before confirmation',
    color: 'accent',
  },
  edge: {
    icon: 'eye',
    title: 'Entry zone identified.',
    sub: 'PRO users see exact entry, target, and invalidation. You see direction only.',
    cta: 'See the full picture',
    color: 'accent',
  },
  social: {
    icon: 'people',
    title: 'Top performers are all PRO.',
    sub: 'They see entries earlier and act faster. You\'re competing blind.',
    cta: 'Join PRO',
    color: 'accent',
  },
  portfolio: {
    icon: 'briefcase',
    title: 'Your portfolio needs precision.',
    sub: 'Full allocation strategy with entry zones is PRO-only.',
    cta: 'Unlock strategy',
    color: 'accent',
  },
};

export function MomentPaywall({ type, asset, pnl, compact }: Props) {
  const colors = useColors();
  const user = useSessionStore(s => s.user);
  const isPro = user?.plan === 'PRO' || user?.plan === 'INSTITUTIONAL';

  if (isPro) return null;

  const cfg = CONFIGS[type];
  const accentColor = cfg.color === 'buy' ? colors.buy : cfg.color === 'sell' ? colors.sell : colors.accent;

  // Dynamic title with asset/pnl
  let title = cfg.title;
  if (type === 'profit' && asset && pnl) title = `${asset} +${pnl.toFixed(1)}% — you caught this early.`;
  if (type === 'regret' && asset && pnl) title = `${asset} +${Math.abs(pnl).toFixed(1)}%. You hesitated.`;
  if (type === 'urgency' && asset) title = `${asset} setup confirming soon.`;

  if (compact) {
    return (
      <TouchableOpacity testID={`moment-paywall-${type}`} style={[s.compact, { borderColor: accentColor + '30' }]} onPress={() => openPaywall('contextual')} activeOpacity={0.7}>
        <Ionicons name={cfg.icon as any} size={14} color={accentColor} />
        <Text style={[s.compactText, { color: accentColor }]}>{cfg.cta} — {cfg.sub.split('.')[0]}</Text>
        <Ionicons name="chevron-forward" size={14} color={accentColor} />
      </TouchableOpacity>
    );
  }

  return (
    <View testID={`moment-paywall-${type}`} style={[s.container, { borderColor: accentColor + '25', backgroundColor: accentColor + '06' }]}>
      <View style={s.header}>
        <View style={[s.iconCircle, { backgroundColor: accentColor + '15' }]}>
          <Ionicons name={cfg.icon as any} size={18} color={accentColor} />
        </View>
        <View style={s.textBlock}>
          <Text style={[s.title, { color: colors.textPrimary }]}>{title}</Text>
          <Text style={[s.sub, { color: colors.textMuted }]}>{cfg.sub}</Text>
        </View>
      </View>
      <TouchableOpacity testID={`moment-paywall-${type}-cta`} style={[s.cta, { backgroundColor: accentColor }]} onPress={() => openPaywall('contextual')} activeOpacity={0.8}>
        <Ionicons name="diamond" size={14} color="#fff" />
        <Text style={s.ctaText}>{cfg.cta}</Text>
      </TouchableOpacity>
    </View>
  );
}

const s = StyleSheet.create({
  container: { borderWidth: 1, borderRadius: 14, padding: 16, marginBottom: 10 },
  header: { flexDirection: 'row', gap: 12, marginBottom: 12 },
  iconCircle: { width: 36, height: 36, borderRadius: 18, justifyContent: 'center', alignItems: 'center' },
  textBlock: { flex: 1 },
  title: { fontSize: 14, fontWeight: '700', marginBottom: 3 },
  sub: { fontSize: 12, lineHeight: 17 },
  cta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 12, borderRadius: 10 },
  ctaText: { color: '#fff', fontSize: 14, fontWeight: '700' },
  compact: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 8, paddingHorizontal: 12, borderWidth: 1, borderRadius: 8, marginTop: 8 },
  compactText: { flex: 1, fontSize: 12, fontWeight: '600' },
});
