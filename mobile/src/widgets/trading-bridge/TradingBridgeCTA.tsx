/**
 * TradingBridgeCTA — reusable cross-app cognition handoff card.
 * Phase E1 — Narrative Convergence (2026-05-12): copy reframed off trading
 * vocabulary onto observation/deployment/structure language.
 *
 * Drop this anywhere inside an analytical surface (Feed / Edge / Observations /
 * IntelHome) to give the user a one-tap escalation path into Operator Desk
 * with asset context preserved.
 *
 * Variants:
 *   - 'open-execution'      → opens DEPLOYMENT tab
 *   - 'why-ai-cares'        → opens COMMAND tab
 *   - 'watch-execution'     → opens DEPLOYMENT tab (passive watcher framing)
 *   - 'building-conviction' → opens COMMAND tab (anticipatory)
 */
import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../core/useColors';
import { useOpenInTradingOS } from './useOpenInTradingOS';
import { TradingTab } from '../../stores/app-mode.store';

type Variant = 'open-execution' | 'why-ai-cares' | 'watch-execution' | 'building-conviction';

const VARIANTS: Record<Variant, {
  title: string;
  sub: string;
  cta: string;
  icon: keyof typeof Ionicons.glyphMap;
  tab: TradingTab;
}> = {
  'open-execution': {
    title: 'Asymmetric structure forming',
    sub: 'open deployment cognition',
    cta: 'OPEN IN OPERATOR DESK',
    icon: 'git-network',
    tab: 'EXECUTION',
  },
  'why-ai-cares': {
    title: 'Why the system is watching this',
    sub: 'see the system reasoning loop',
    cta: 'OPEN COMMAND',
    icon: 'speedometer',
    tab: 'COMMAND',
  },
  'watch-execution': {
    title: 'Observe deployment reasoning',
    sub: 'pipeline · universes · modules',
    cta: 'OPEN DEPLOYMENT',
    icon: 'git-network',
    tab: 'EXECUTION',
  },
  'building-conviction': {
    title: 'Conviction building',
    sub: 'see the readiness gates',
    cta: 'OPEN COMMAND',
    icon: 'pulse',
    tab: 'COMMAND',
  },
};

interface Props {
  variant?: Variant;
  asset?: string | null;
  modulesAligned?: number;
  modulesTotal?: number;
  customSub?: string;
  compact?: boolean;
}

export function TradingBridgeCTA({
  variant = 'open-execution',
  asset,
  modulesAligned,
  modulesTotal = 5,
  customSub,
  compact = false,
}: Props) {
  const colors = useColors();
  const open = useOpenInTradingOS();
  const v = VARIANTS[variant];
  const sub = customSub
    || (modulesAligned != null
      ? `${modulesAligned}/${modulesTotal} modules aligning`
      : v.sub);

  const onPress = () => open(asset || null, v.tab);

  if (compact) {
    return (
      <TouchableOpacity
        testID={`trading-bridge-cta-${variant}`}
        onPress={onPress}
        activeOpacity={0.8}
        style={[s.compact, { backgroundColor: colors.accent + '14', borderColor: colors.accent + '50' }]}
      >
        <Ionicons name={v.icon} size={14} color={colors.accent} />
        <Text style={[s.compactText, { color: colors.accent }]}>
          {asset ? `${asset.toUpperCase()} · ` : ''}{v.cta}
        </Text>
        <Ionicons name="chevron-forward" size={12} color={colors.accent} />
      </TouchableOpacity>
    );
  }

  return (
    <TouchableOpacity
      testID={`trading-bridge-cta-${variant}`}
      onPress={onPress}
      activeOpacity={0.85}
      style={[s.card, { backgroundColor: colors.surface, borderColor: colors.accent + '40' }]}
    >
      <View style={[s.iconWrap, { backgroundColor: colors.accent + '20' }]}>
        <Ionicons name={v.icon} size={20} color={colors.accent} />
      </View>
      <View style={s.textCol}>
        <Text
          style={[s.title, { color: colors.textPrimary }]}
          numberOfLines={2}
          ellipsizeMode="tail"
        >
          {asset ? `${asset.toUpperCase()} · ` : ''}{v.title}
        </Text>
        <Text
          style={[s.sub, { color: colors.textMuted }]}
          numberOfLines={2}
          ellipsizeMode="tail"
        >
          {sub}
        </Text>
      </View>
      <View style={[s.cta, { borderColor: colors.accent }]}>
        <Text
          style={[s.ctaText, { color: colors.accent }]}
          numberOfLines={1}
          ellipsizeMode="clip"
        >
          {v.cta}
        </Text>
        <Ionicons name="chevron-forward" size={12} color={colors.accent} />
      </View>
    </TouchableOpacity>
  );
}

const s = StyleSheet.create({
  card: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    padding: 12, borderRadius: 12, borderWidth: 1, marginVertical: 8,
  },
  iconWrap: {
    width: 38, height: 38, borderRadius: 10,
    alignItems: 'center', justifyContent: 'center',
    flexShrink: 0,
  },
  /**
   * CRITICAL: flexShrink:1 + minWidth:0 is required to allow the text column
   * to shrink below its intrinsic content width when the row siblings (icon +
   * CTA pill) are fixed-width. Without minWidth:0, RN/Web flex would refuse
   * to shrink the column and the long title would force character-by-character
   * wrap inside a 1-char-wide column.
   */
  textCol: { flex: 1, flexShrink: 1, minWidth: 0 },
  title: { fontSize: 13, fontWeight: '800' },
  sub: { fontSize: 11, marginTop: 2 },
  cta: {
    flexDirection: 'row', alignItems: 'center', gap: 2,
    paddingHorizontal: 8, paddingVertical: 5,
    borderRadius: 999, borderWidth: 1,
    flexShrink: 0,            // CTA pill keeps its natural width
    maxWidth: 160,            // hard cap so a long CTA can't squeeze the title
  },
  ctaText: { fontSize: 9, fontWeight: '900', letterSpacing: 0.5 },

  compact: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999, borderWidth: 1,
    alignSelf: 'flex-start', marginTop: 8,
  },
  compactText: { fontSize: 10, fontWeight: '800', letterSpacing: 0.4 },
});
