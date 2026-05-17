/**
 * 🔥 Signal of the Moment — Hero card for HomeScreen
 * ===================================================
 * Two rendering modes:
 *   - Full hero (first view of a given signal.id)
 *   - Slim bar (user has already seen THIS signal → collapsed memory row)
 *
 * Collapse policy lives in HomeScreen (AsyncStorage: hero_seen_<signalId>).
 * A new signal.id resets the view to full.
 *
 * Tap behavior (handled by parent):
 *   - signal.asset exists  → EDGE tab
 *   - signal.asset is null → FEED tab
 */

import React, { useEffect, useRef, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Animated, Platform } from 'react-native';
import type { TopSignal } from '../../../../services/api/mobile-api';
import { useColors } from '../../../../core/useColors';
import { canShareSignal, shareSignal } from '../../../../services/share';
import { track } from '../../../../services/analytics';
import { t } from '../../../../core/i18n';

type Colors = ReturnType<typeof useColors>;

function priorityColor(priority: TopSignal['priority'], colors: Colors): string {
  switch (priority) {
    case 'CRITICAL': return colors.sell;          // red
    case 'HIGH':     return colors.wait;          // amber
    case 'MEDIUM':   return colors.textSecondary; // neutral
    default:         return colors.textMuted;
  }
}

function ageLabel(ageMinutes: number): { text: string; tone: 'fresh' | 'mid' | 'stale' } {
  if (ageMinutes < 10) return { text: 'just now', tone: 'fresh' };
  if (ageMinutes < 60) return { text: `${ageMinutes}m ago`, tone: 'mid' };
  if (ageMinutes < 120) return { text: `${Math.floor(ageMinutes / 60)}h ago`, tone: 'mid' };
  const h = Math.floor(ageMinutes / 60);
  return { text: `earlier signal · ${h}h ago`, tone: 'stale' };
}

/**
 * Collapsed-bar tail — urgency decays gracefully instead of screaming forever:
 *   < 10 min → "happening now"  (accent)
 *   10–30 min → "still active"  (warm)
 *   30–120 min → "active"       (neutral)
 *   > 2h → "earlier signal · Nh ago"  (stale)
 */
function slimTail(signal: TopSignal): { text: string; tone: 'fresh' | 'warm' | 'mid' | 'stale' } {
  if (signal.priority === 'CRITICAL' && signal.ageMinutes < 10 && signal.watchersCount > 20) {
    return { text: 'happening now', tone: 'fresh' };
  }
  if (signal.ageMinutes < 10) return { text: 'happening now', tone: 'fresh' };
  if (signal.ageMinutes < 30) return { text: 'still active', tone: 'warm' };
  if (signal.ageMinutes < 120) return { text: 'active', tone: 'mid' };
  return ageLabel(signal.ageMinutes);
}

/**
 * True only when urgency is real: CRITICAL + fresh (< 10min) + real social proof.
 * "happening now" is an expensive badge; do not burn its authority on weak signals.
 */
function isHappeningNow(signal: TopSignal): boolean {
  return signal.priority === 'CRITICAL'
    && signal.ageMinutes < 10
    && signal.watchersCount > 20;
}

interface Props {
  signal: TopSignal;
  colors: Colors;
  collapsed?: boolean;
  onPress: () => void;
}

export default function SignalOfMomentHero({ signal, colors, collapsed = false, onPress }: Props) {
  const pColor = priorityColor(signal.priority, colors);
  const happeningNow = isHappeningNow(signal);

  // G1 Analytics — track hero view once per signal.id (+mode)
  const viewedId = useRef<string | null>(null);
  useEffect(() => {
    const key = `${signal.id}|${collapsed ? 'slim' : 'full'}`;
    if (viewedId.current === key) return;
    viewedId.current = key;
    track('signal_hero_view', {
      signalId: signal.id,
      asset: signal.asset || null,
      source: signal.source,
      priority: signal.priority,
      context: { screen: 'home', from: 'hero', mode: collapsed ? 'slim' : 'full' },
    });
  }, [signal.id, collapsed, signal.asset, signal.source, signal.priority]);

  // G1 Share state
  const [sharing, setSharing] = useState(false);
  const [shared, setShared] = useState(false);
  const shareVisible = !collapsed && canShareSignal(signal);

  const handleTap = () => {
    track('signal_hero_tap', {
      signalId: signal.id,
      asset: signal.asset || null,
      source: signal.source,
      priority: signal.priority,
      context: { screen: 'home', from: 'hero', mode: collapsed ? 'slim' : 'full' },
    });
    onPress();
  };

  const handleShare = async (e?: any) => {
    if (e && typeof e.stopPropagation === 'function') e.stopPropagation();
    if (sharing || shared) return;
    track('share_click', {
      signalId: signal.id,
      asset: signal.asset || null,
      source: signal.source,
      priority: signal.priority,
      context: { screen: 'home', from: 'hero' },
    });
    setSharing(true);
    try {
      const res = await shareSignal({
        asset: signal.asset,
        source: signal.source,
        priority: signal.priority,
        title: signal.title,
      });
      if (res.ok) {
        track('share_complete', {
          signalId: signal.id,
          asset: signal.asset || null,
          source: signal.source,
          priority: signal.priority,
          context: { screen: 'home', from: 'hero', via: res.via, hasRef: !!res.refCode },
        });
        setShared(true);
        setTimeout(() => setShared(false), 3000);
      }
    } finally {
      setSharing(false);
    }
  };

  // ─── Replace animation on signal.id change (fade + subtle scale up) ───────
  const replaceOpacity = useRef(new Animated.Value(1)).current;
  const replaceScale = useRef(new Animated.Value(1)).current;
  const lastId = useRef<string | null>(null);
  useEffect(() => {
    if (lastId.current && lastId.current !== signal.id) {
      replaceOpacity.setValue(0);
      replaceScale.setValue(0.98);
      Animated.parallel([
        Animated.timing(replaceOpacity, { toValue: 1, duration: 260, delay: 100, useNativeDriver: true }),
        Animated.timing(replaceScale, { toValue: 1, duration: 260, delay: 100, useNativeDriver: true }),
      ]).start();
    }
    lastId.current = signal.id;
  }, [signal.id, replaceOpacity, replaceScale]);

  // ─── CRITICAL pulse ring ─────────────────────────────────────────────────
  const pulse = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (signal.priority !== 'CRITICAL' || collapsed) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 1400, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: 1400, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [signal.priority, collapsed, pulse]);

  // ═══════════════════════════════════════════════════════════════════
  // SLIM MODE — persistent memory row. Height ~48px. Tap → full expand.
  // ═══════════════════════════════════════════════════════════════════
  if (collapsed) {
    const { text: tailText, tone } = slimTail(signal);
    const tailColor = tone === 'fresh'
      ? pColor
      : tone === 'warm'
      ? colors.wait
      : tone === 'mid'
      ? colors.textSecondary
      : colors.textMuted;
    return (
      <Animated.View style={{ opacity: replaceOpacity, transform: [{ scale: replaceScale }] }}>
        <TouchableOpacity
          activeOpacity={0.85}
          onPress={handleTap}
          testID="signal-of-moment-slim"
          style={[
            styles.slim,
            { backgroundColor: colors.surface, borderColor: pColor + '40' },
          ]}
        >
          <Text style={styles.slimEyebrow}>🔥</Text>
          <Text
            style={[styles.slimTitle, { color: colors.textPrimary }]}
            numberOfLines={1}
          >
            {signal.title}
          </Text>
          <Text style={[styles.slimDot, { color: colors.textMuted }]}>·</Text>
          <Text style={[styles.slimTail, { color: tailColor }]} numberOfLines={1}>
            {tailText}
          </Text>
          <Text style={[styles.slimCta, { color: colors.accent }]}>→ View</Text>
        </TouchableOpacity>
      </Animated.View>
    );
  }

  // ═══════════════════════════════════════════════════════════════════
  // FULL MODE — hero card
  // ═══════════════════════════════════════════════════════════════════
  const { text: ageText, tone: ageTone } = ageLabel(signal.ageMinutes);
  const ageColor = ageTone === 'fresh' ? colors.buy : ageTone === 'stale' ? colors.textMuted : colors.textSecondary;

  const pulseScale = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.015] });
  const pulseOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.22, 0.38] });

  const bodyOneLiner = (signal.body || '')
    .replace(/→|·\s*→/g, '')
    .split('\n')[0]
    .trim()
    .slice(0, 110);

  const ctaText = signal.ctaLabel
    || (signal.asset ? `→ See ${signal.asset} setup` : '→ See market impact');

  return (
    <Animated.View style={{ opacity: replaceOpacity, transform: [{ scale: Animated.multiply(replaceScale, pulseScale) }] }}>
      <TouchableOpacity
        activeOpacity={0.92}
        onPress={handleTap}
        testID="signal-of-moment"
        style={[
          styles.card,
          {
            backgroundColor: colors.surface,
            borderColor: pColor + '30',
            ...Platform.select({
              ios: {
                shadowColor: pColor,
                shadowOpacity: 0.25,
                shadowRadius: 12,
                shadowOffset: { width: 0, height: 4 },
              },
              android: { elevation: 4 },
              default: {},
            }),
          },
        ]}
      >
        {signal.priority === 'CRITICAL' && (
          <Animated.View
            pointerEvents="none"
            style={[styles.criticalGlow, { backgroundColor: pColor, opacity: pulseOpacity }]}
          />
        )}

        {/* Eyebrow */}
        <View style={styles.eyebrowRow}>
          <Text style={[styles.eyebrow, { color: colors.textMuted }]} numberOfLines={1}>
            🔥 SIGNAL OF THE MOMENT
          </Text>
          {happeningNow ? (
            <View style={[styles.happeningPill, { backgroundColor: pColor + '20', borderColor: pColor + '50' }]}>
              <View style={[styles.happeningDot, { backgroundColor: pColor }]} />
              <Text style={[styles.happeningText, { color: pColor }]} numberOfLines={1}>
                happening now
              </Text>
            </View>
          ) : (
            <Text style={[styles.age, { color: ageColor }]} numberOfLines={1}>
              ● {ageText}
            </Text>
          )}
        </View>

        {/* Header: source chip + priority pill */}
        <View style={styles.headerRow}>
          <View style={[styles.sourceChip, { backgroundColor: colors.bgSecondary }]}>
            <Text style={styles.sourceIcon}>{signal.sourceIcon}</Text>
            <Text style={[styles.sourceLabel, { color: colors.textPrimary }]} numberOfLines={1}>
              {signal.sourceLabel}
              {signal.asset ? <Text style={{ color: colors.textMuted }}>  ·  {signal.asset}</Text> : null}
            </Text>
          </View>
          <View style={[styles.priorityPill, { backgroundColor: pColor + '20' }]}>
            <Text style={[styles.priorityPillText, { color: pColor }]} numberOfLines={1}>
              {signal.priority}
            </Text>
          </View>
        </View>

        <Text style={[styles.title, { color: colors.textPrimary }]} numberOfLines={2}>
          {signal.title}
        </Text>

        {/* Confidence layer — 1-line muted argument under the title.
            Turns "signal" into "signal + why to believe it". */}
        {signal.confidenceText ? (
          <Text
            style={[styles.confidence, { color: colors.textMuted }]}
            numberOfLines={1}
          >
            {signal.confidenceText}
          </Text>
        ) : null}

        {bodyOneLiner ? (
          <Text style={[styles.body, { color: colors.textSecondary }]} numberOfLines={1}>
            {bodyOneLiner}
          </Text>
        ) : null}

        <View style={styles.liveRow}>
          {signal.watchersCount > 0 ? (
            <View style={styles.liveCell}>
              <View style={[styles.dot, { backgroundColor: colors.buy }]} />
              <Text style={[styles.liveText, { color: colors.textSecondary }]}>
                {signal.watchersCount} people watching
              </Text>
            </View>
          ) : null}
          <View style={styles.liveCell}>
            <View style={[styles.dot, { backgroundColor: colors.buy }]} />
            <Text style={[styles.liveText, { color: colors.textSecondary }]}>
              {t('home.systemWatching')}
            </Text>
          </View>
        </View>

        <Text style={[styles.cta, { color: colors.accent }]} numberOfLines={1}>
          {ctaText}
        </Text>

        {/* ── G1 Share row — only for high-signal moments ── */}
        {shareVisible ? (
          <View style={styles.shareRow}>
            <TouchableOpacity
              testID="signal-of-moment-share"
              onPress={handleShare}
              activeOpacity={0.75}
              disabled={sharing || shared}
              style={[
                styles.shareBtn,
                {
                  borderColor: shared ? colors.buy + '80' : colors.accent + '55',
                  backgroundColor: shared ? colors.buy + '15' : colors.accent + '12',
                },
              ]}
            >
              <Text style={[styles.shareBtnText, { color: shared ? colors.buy : colors.accent }]} numberOfLines={1}>
                {shared ? '✓ Shared' : sharing ? 'Sharing…' : '↗ Share signal'}
              </Text>
            </TouchableOpacity>
            {shared ? (
              <Text style={[styles.shareFeedback, { color: colors.buy }]} numberOfLines={1}>
                ● You're ahead of the market
              </Text>
            ) : null}
          </View>
        ) : null}
      </TouchableOpacity>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    marginBottom: 16,
    overflow: 'hidden',
  },
  criticalGlow: { ...StyleSheet.absoluteFillObject, borderRadius: 16 },
  eyebrowRow: {
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between', marginBottom: 10,
  },
  eyebrow: {
    fontSize: 10.5, fontWeight: '700', letterSpacing: 0.8,
    textTransform: 'uppercase', flex: 1,
  },
  age: { fontSize: 11, fontWeight: '600', marginLeft: 8 },
  happeningPill: {
    flexDirection: 'row', alignItems: 'center',
    paddingVertical: 3, paddingHorizontal: 8, borderRadius: 999,
    borderWidth: 1, gap: 5, marginLeft: 8,
  },
  happeningDot: { width: 6, height: 6, borderRadius: 3 },
  happeningText: { fontSize: 10.5, fontWeight: '700', letterSpacing: 0.3 },
  headerRow: {
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between', marginBottom: 10, gap: 8,
  },
  sourceChip: {
    flexDirection: 'row', alignItems: 'center',
    paddingVertical: 5, paddingHorizontal: 10, borderRadius: 999,
    gap: 6, flexShrink: 1,
  },
  sourceIcon: { fontSize: 14 },
  sourceLabel: { fontSize: 12.5, fontWeight: '600' },
  priorityPill: { paddingVertical: 4, paddingHorizontal: 10, borderRadius: 8 },
  priorityPillText: { fontSize: 10.5, fontWeight: '700', letterSpacing: 0.6 },
  title: { fontSize: 18, fontWeight: '700', lineHeight: 23, marginBottom: 4 },
  confidence: {
    fontSize: 11.5,
    fontWeight: '600',
    letterSpacing: 0.15,
    textTransform: 'uppercase',
    marginBottom: 8,
    opacity: 0.85,
  },
  body: { fontSize: 13.5, lineHeight: 18, marginBottom: 10 },
  liveRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 14, marginBottom: 10 },
  liveCell: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  dot: { width: 6, height: 6, borderRadius: 3 },
  liveText: { fontSize: 12, fontWeight: '500' },
  cta: { fontSize: 14, fontWeight: '700', marginTop: 2 },

  // G1 Share
  shareRow: {
    flexDirection: 'row', alignItems: 'center',
    marginTop: 10, gap: 10, flexWrap: 'wrap',
  },
  shareBtn: {
    paddingVertical: 7, paddingHorizontal: 14,
    borderRadius: 999, borderWidth: 1,
  },
  shareBtnText: { fontSize: 12.5, fontWeight: '700', letterSpacing: 0.3 },
  shareFeedback: { fontSize: 11.5, fontWeight: '600' },

  // Slim (collapsed) row — persistent memory, ~48px
  slim: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 14, paddingVertical: 12, borderRadius: 12,
    borderWidth: 1, marginBottom: 12, gap: 8,
  },
  slimEyebrow: { fontSize: 14 },
  slimTitle: { fontSize: 13.5, fontWeight: '700', flexShrink: 1 },
  slimDot: { fontSize: 13 },
  slimTail: { fontSize: 12, fontWeight: '600', flexShrink: 1 },
  slimCta: { fontSize: 12.5, fontWeight: '700', marginLeft: 'auto' },
});
