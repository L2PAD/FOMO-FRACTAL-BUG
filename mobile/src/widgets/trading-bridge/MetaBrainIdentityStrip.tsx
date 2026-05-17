/**
 * MetaBrainIdentityStrip — global AI performance identity.
 *
 * A single, persistent strip showing meta-brain's earned credibility:
 *   META-BRAIN  ·  +42.0% net alpha  ·  14 losses avoided  ·  30 resolved
 *
 * Drop this near the top of:
 *   - Intel Home (super-app entry point)
 *   - Trading OS Command (cross-reinforcement)
 *   - Trading OS Portfolio (proof layer)
 *
 * Designed to be lightweight: pulls realized attribution and shows whatever
 * is available. Self-fetches and caches in module scope to avoid hammering
 * the side-car endpoint when shown on multiple screens.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../core/useColors';
import { mbrainApi } from '../../services/api/mbrain-api';
import { useOpenInTradingOS } from './useOpenInTradingOS';

// Module-scope cache so we hit the endpoint at most once per ~60s session-wide.
let _cache: { data: any; ts: number } | null = null;
const CACHE_MS = 60 * 1000;

async function fetchIdentity() {
  if (_cache && Date.now() - _cache.ts < CACHE_MS) return _cache.data;
  try {
    const data = await mbrainApi.realizedAttribution(2000);
    _cache = { data, ts: Date.now() };
    return data;
  } catch {
    return null;
  }
}

function pctRaw(n: number | null | undefined, d = 1): string {
  if (n == null || isNaN(n)) return '—';
  const sign = n >= 0 ? '+' : '';
  return `${sign}${n.toFixed(d)}%`;
}

interface Props {
  /** if true, tapping the strip opens Trading OS Portfolio (proof). */
  tappable?: boolean;
  /** compact = single-line, full = multi-line w/ ribbon. */
  variant?: 'compact' | 'full';
}

export function MetaBrainIdentityStrip({ tappable = true, variant = 'compact' }: Props) {
  const colors = useColors();
  const open = useOpenInTradingOS();
  const [data, setData] = useState<any>(_cache?.data ?? null);

  useEffect(() => {
    let alive = true;
    fetchIdentity().then((d) => { if (alive && d) setData(d); });
    return () => { alive = false; };
  }, []);

  const h = data?.headline;
  if (!h) return null;

  const verdict = h.verdict;
  const isPositive = verdict === 'META_NET_POSITIVE';
  const accent = isPositive ? colors.buy : verdict === 'META_NET_NEGATIVE' ? colors.sell : colors.textMuted;
  const onPress = tappable ? () => open(null, 'PORTFOLIO') : undefined;

  if (variant === 'full') {
    return (
      <TouchableOpacity
        testID="meta-brain-identity-full"
        activeOpacity={onPress ? 0.85 : 1}
        onPress={onPress}
        style={[s.full, { backgroundColor: colors.surface, borderColor: accent + '40' }]}
      >
        <View style={s.fullTop}>
          <View style={[s.dot, { backgroundColor: accent }]} />
          <Text style={[s.fullTitle, { color: colors.textMuted }]}>META-BRAIN</Text>
          <Text style={[s.fullVerdict, { color: accent }]}>
            {verdict.replace('META_NET_', '')}
          </Text>
        </View>
        <View style={s.fullStats}>
          <Stat tone={accent} colors={colors} label="net alpha"
            value={pctRaw(h.net_alpha_pct, 1)} />
          <Stat tone={colors.buy} colors={colors} label="losses avoided"
            value={`${h.n_killed_loss_avoided}`} />
          <Stat tone={colors.textPrimary} colors={colors} label="resolved"
            value={`${data.n}`} />
        </View>
        {onPress && (
          <Text style={[s.fullCta, { color: colors.accent }]}>view proof in Portfolio  ›</Text>
        )}
      </TouchableOpacity>
    );
  }

  return (
    <TouchableOpacity
      testID="meta-brain-identity-strip"
      activeOpacity={onPress ? 0.85 : 1}
      onPress={onPress}
      style={[s.compact, { backgroundColor: colors.surface, borderColor: accent + '40' }]}
    >
      <View style={[s.dot, { backgroundColor: accent }]} />
      <Text style={[s.compactLabel, { color: colors.textMuted }]}>META-BRAIN</Text>
      <Text style={[s.compactValue, { color: accent }]}>
        {pctRaw(h.net_alpha_pct, 1)} alpha
      </Text>
      <View style={s.dotSep} />
      <Text style={[s.compactValue, { color: colors.buy }]}>
        {h.n_killed_loss_avoided} avoided
      </Text>
      <View style={{ flex: 1 }} />
      {onPress && <Ionicons name="chevron-forward" size={14} color={colors.textMuted} />}
    </TouchableOpacity>
  );
}

function Stat({ value, label, tone, colors }: any) {
  return (
    <View style={s.stat}>
      <Text style={[s.statValue, { color: tone }]}>{value}</Text>
      <Text style={[s.statLabel, { color: colors.textMuted }]}>{label}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  compact: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 12, paddingVertical: 8,
    borderRadius: 999, borderWidth: 1, marginVertical: 4,
  },
  compactLabel: { fontSize: 9, fontWeight: '900', letterSpacing: 1 },
  compactValue: { fontSize: 11, fontWeight: '800' },
  dot: { width: 6, height: 6, borderRadius: 3 },
  dotSep: { width: 3, height: 3, borderRadius: 1.5, backgroundColor: '#7a8294', opacity: 0.4 },

  full: { borderRadius: 12, borderWidth: 1, padding: 12, marginVertical: 6 },
  fullTop: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  fullTitle: { fontSize: 9, fontWeight: '900', letterSpacing: 1.4 },
  fullVerdict: { fontSize: 10, fontWeight: '900', letterSpacing: 0.6, marginLeft: 'auto' },
  fullStats: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 10 },
  stat: { alignItems: 'center', flex: 1 },
  statValue: { fontSize: 16, fontWeight: '900' },
  statLabel: { fontSize: 9, marginTop: 2 },
  fullCta: { fontSize: 10, fontWeight: '700', textAlign: 'right', marginTop: 8 },
});
