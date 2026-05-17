/**
 * NotificationsScreen — Decision history, not a log
 *
 * Production-hardening polish:
 *   • Source badge (🐦 Actor · 🐋 Whale · 🧠 MetaBrain · 🎯 Poly · 📰 News · 🚀 Listing · ⚠️ Exploit · 💎 ETF · ⚖️ Regulation)
 *   • Priority visual: CRITICAL red glow · HIGH amber tint · MEDIUM neutral
 *   • Grouping: Today · Earlier
 *   • Unified tap: asset → EDGE · no asset → FEED (mirrors Hero behavior)
 */

import React, { useEffect, useMemo, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, SectionList,
  ActivityIndicator, RefreshControl, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useNotificationsStore, NotificationItem } from '../../../stores/notifications.store';
import { useAppMode } from '../../../stores/app-mode.store';
import { useAssetStore } from '../../../stores/asset.store';
import { useColors } from '../../../core/useColors';
import { hapticLight } from '../../../services/haptics.service';
import { CoinIcon } from '../../../components/CoinIcon';

import { t } from '../../../core/i18n';
const TABS = [
  { key: 'ALL' as const, label: 'All' },
  { key: 'PORTFOLIO' as const, label: 'Portfolio' },
  { key: 'EDGE' as const, label: 'Edge' },
  { key: 'SIGNAL' as const, label: 'Signals' },
] as const;

type Tab = (typeof TABS)[number]['key'];
type PrioLabel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const h = Math.floor(diff / 3600000);
  if (h < 1) return 'just now';
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

/** Source badge resolution — mirrors backend priority.engine + selector. */
function resolveSourceBadge(pushType: string | undefined, rawSource: string | undefined | null)
: { icon: string; label: string } | null {
  const t = String(pushType || '').toUpperCase();
  const s = String(rawSource || '').toLowerCase();
  if (t === 'LISTING')       return { icon: '🚀', label: 'Listing' };
  if (t === 'EXPLOIT')       return { icon: '⚠️', label: 'Exploit' };
  if (t === 'ETF')           return { icon: '💎', label: 'ETF' };
  if (t === 'REGULATION')    return { icon: '⚖️', label: 'Regulation' };
  if (t.startsWith('POLY_')) return { icon: '🎯', label: 'Polymarket' };
  if (t === 'NEWS')          return { icon: '📰', label: 'News' };
  if (t === 'METABRAIN_DECISION_SHIFT' || t === 'METABRAIN_CONVICTION_JUMP') return { icon: '🧠', label: 'MetaBrain' };
  if (t.startsWith('ACTOR_')) return { icon: '🐦', label: 'Actor' };
  if (t.startsWith('WHALE_')) return { icon: '🐋', label: 'Whale' };
  if (s === 'news')       return { icon: '📰', label: 'News' };
  if (s === 'polymarket') return { icon: '🎯', label: 'Polymarket' };
  if (s === 'sentiment')  return { icon: '📡', label: 'Sentiment' };
  if (s === 'actor')      return { icon: '🐦', label: 'Actor' };
  if (s === 'whale')      return { icon: '🐋', label: 'Whale' };
  if (s === 'metabrain')  return { icon: '🧠', label: 'MetaBrain' };
  return null;  // Non-push-router types (PNL, WATCHLIST, FOMO) — no badge
}

/** Frontend-side priority approximation when backend didn't send one. */
function priorityFromPushType(pushType: string | undefined): PrioLabel {
  const t = String(pushType || '').toUpperCase();
  if (['LISTING', 'EXPLOIT', 'ETF', 'POLY_MISPRICING', 'METABRAIN_DECISION_SHIFT'].includes(t)) return 'CRITICAL';
  if (['REGULATION', 'POLY_OVERHEATED', 'POLY_THESIS_WEAKENED', 'NEWS',
       'WHALE_EXCHANGE_INFLOW', 'WHALE_EXCHANGE_OUTFLOW',
       'ACTOR_NARRATIVE_PUSH', 'ACTOR_MENTION_SPIKE',
       'METABRAIN_CONVICTION_JUMP', 'POLY_REPRICING',
       'CONFIRMED', 'PERSONAL'].includes(t)) return 'HIGH';
  if (t === 'MISSED') return 'MEDIUM';
  return 'LOW';
}

function isToday(dateStr: string): boolean {
  const d = new Date(dateStr);
  const now = new Date();
  return d.getFullYear() === now.getFullYear()
    && d.getMonth() === now.getMonth()
    && d.getDate() === now.getDate();
}

export function NotificationsScreen({ onClose }: { onClose: () => void }) {
  const insets = useSafeAreaInsets();
  const colors = useColors();
  const s = useMemo(() => mk(colors), [colors]);
  const { setIntelTab } = useAppMode();
  const setCurrentAsset = useAssetStore((st) => st.setCurrentAsset);

  const {
    items, loading, fetchNotifications, markAllRead,
    tab, setTab, refreshing, doRefresh, markRead,
  } = useNotificationsStore();

  useEffect(() => { fetchNotifications(); }, []);

  const filteredItems = useMemo(() => {
    if (tab === 'ALL') return items;
    if (tab === 'PORTFOLIO') return items.filter(n => n.type === 'PNL_ALERT' || n.type === 'WATCHLIST_ALERT' || n.type === 'FOMO');
    if (tab === 'EDGE') return items.filter(n => n.type === 'EDGE' || n.data?.pushType === 'PERSONAL');
    if (tab === 'SIGNAL') return items.filter(n => n.type === 'SIGNAL');
    return items;
  }, [items, tab]);

  // Group by Today / Earlier — kills the "infinite scroll" feel.
  const sections = useMemo(() => {
    const today: NotificationItem[] = [];
    const earlier: NotificationItem[] = [];
    for (const it of filteredItems) {
      if (it.createdAt && isToday(it.createdAt)) today.push(it);
      else earlier.push(it);
    }
    const result: { title: string; data: NotificationItem[] }[] = [];
    if (today.length) result.push({ title: 'Today', data: today });
    if (earlier.length) result.push({ title: 'Earlier', data: earlier });
    return result;
  }, [filteredItems]);

  // Unified tap — mirrors Hero / Feed strip behavior.
  //   asset present  → EDGE tab (setup detail)
  //   no asset       → FEED tab (market context)
  //   legacy (PNL/WATCHLIST/EDGE/FOMO) → route per type as before
  const handleTap = useCallback((item: NotificationItem) => {
    hapticLight();
    markRead(item.id);
    onClose();

    const pushType = item.data?.pushType;
    const asset = item.data?.asset;

    // Push-router events (Wave 1-4) — single policy
    if (pushType) {
      if (asset) {
        setCurrentAsset(asset);
        setIntelTab('EDGE');
      } else {
        setIntelTab('FEED');
      }
      return;
    }

    // Legacy routes
    const screen = item.data?.screen;
    if (screen === 'portfolio' || item.type === 'PNL_ALERT') setIntelTab('FEED');
    else if (screen === 'edge' || item.type === 'EDGE') setIntelTab('EDGE');
    else if (screen === 'home' || item.type === 'FOMO') setIntelTab('HOME');
    else if (screen === 'feed' || item.type === 'WATCHLIST_ALERT') setIntelTab('FEED');
    else setIntelTab('HOME');
  }, [onClose, setIntelTab, setCurrentAsset, markRead]);

  const renderItem = useCallback(({ item }: { item: NotificationItem }) => {
    const pushType = item.data?.pushType;
    const rawSource = item.data?.rawSource;
    const isPushEvent = !!pushType;

    const isPnl = item.type === 'PNL_ALERT';
    const isWatchlist = item.type === 'WATCHLIST_ALERT';
    const isEdge = item.type === 'EDGE';
    const isFomo = item.type === 'FOMO';
    const isSystem = item.type === 'SYSTEM';

    const pnlPct = item.data?.pnlPct;
    const change24h = item.data?.change24h;
    const symbol = item.data?.symbol || item.data?.asset;

    // ── Priority resolution — prefer backend priority, fall back to pushType ──
    const priority = ((item.data as any)?.priority as PrioLabel | undefined)
      || (isPushEvent ? priorityFromPushType(pushType) : (item.priority as PrioLabel) || 'MEDIUM');

    // ── Source badge (left of title, pill-style) ──────────────────────────
    const badge = resolveSourceBadge(pushType, rawSource);

    // ── Accent color ──────────────────────────────────────────────────────
    const priorityAccent = priority === 'CRITICAL' ? colors.sell
      : priority === 'HIGH' ? colors.wait
      : colors.textSecondary;

    // For push-router events — priority wins. For legacy PNL/WATCHLIST — type-driven.
    const accentColor = isPushEvent ? priorityAccent
      : isPnl ? (pnlPct >= 0 ? colors.buy : colors.sell)
      : isWatchlist ? colors.accent
      : isEdge ? colors.accent
      : isFomo ? colors.sell
      : colors.textMuted;

    const iconName: keyof typeof Ionicons.glyphMap = isPushEvent ? 'pulse'
      : isPnl ? (pnlPct >= 0 ? 'trending-up' : 'trending-down')
      : isWatchlist ? 'eye'
      : isEdge ? 'flash'
      : isFomo ? 'alert-circle'
      : 'notifications-outline';

    const ctaText = isPushEvent
      ? (item.data?.ctaLabel || (pushType === 'MISSED' ? "→ Don't miss next one" : '→ See setup'))
      : isPnl ? (pnlPct >= 0 ? 'See your position →' : 'Review position →')
      : isWatchlist ? 'View asset →'
      : isEdge ? 'Position Early →'
      : isFomo ? 'See current edges →'
      : null;

    // ── Visual emphasis for CRITICAL (red glow), HIGH (amber tint) ────────
    const isCritical = priority === 'CRITICAL';
    const isHigh = priority === 'HIGH';
    const cardBg = isCritical ? colors.sell + '0F' : isHigh ? colors.wait + '0A' : colors.surface;
    const cardBorder = item.read
      ? colors.border
      : isCritical ? colors.sell + '55'
      : isHigh ? colors.wait + '40'
      : accentColor + '40';

    const glowShadow = isCritical && !item.read
      ? Platform.select({
          ios: { shadowColor: colors.sell, shadowOpacity: 0.20, shadowRadius: 8, shadowOffset: { width: 0, height: 2 } },
          android: { elevation: 2 },
          default: {},
        })
      : {};

    return (
      <TouchableOpacity
        testID={`notification-${item.id}`}
        style={[
          s.card,
          { borderColor: cardBorder, backgroundColor: cardBg },
          !item.read && { borderLeftWidth: 3, borderLeftColor: accentColor },
          glowShadow as any,
        ]}
        onPress={() => handleTap(item)}
        activeOpacity={0.7}
      >
        {/* Top row: badge chip + priority pill + time */}
        {isPushEvent && badge && (
          <View style={s.badgeRow}>
            <View style={[s.sourceChip, { backgroundColor: colors.bgSecondary, borderColor: colors.border }]}>
              <Text style={s.sourceChipIcon}>{badge.icon}</Text>
              <Text style={[s.sourceChipLabel, { color: colors.textPrimary }]}>{badge.label}</Text>
              {item.data?.asset ? (
                <Text style={[s.sourceChipAsset, { color: colors.textMuted }]}>· {item.data.asset}</Text>
              ) : null}
            </View>
            <View style={[s.prioPill, { backgroundColor: priorityAccent + '18' }]}>
              <Text style={[s.prioPillText, { color: priorityAccent }]}>{priority}</Text>
            </View>
            <Text style={[s.timeText, { color: colors.textMuted }]}>
              {item.createdAt ? timeAgo(item.createdAt) : ''}
            </Text>
          </View>
        )}

        <View style={s.cardTop}>
          {(isPnl || isWatchlist) && symbol ? (
            <View style={[s.coinIconWrap, { backgroundColor: accentColor + '12' }]}>
              <CoinIcon symbol={symbol} size={22} />
            </View>
          ) : (
            <View style={[s.iconWrap, { backgroundColor: accentColor + '15' }]}>
              <Ionicons name={iconName} size={16} color={accentColor} />
            </View>
          )}
          <View style={s.cardContent}>
            <Text style={[s.cardTitle, { color: colors.textPrimary }]} numberOfLines={2}>
              {item.title}
            </Text>
            <Text style={[s.cardBody, { color: colors.textMuted }]} numberOfLines={2}>
              {item.body}
            </Text>
          </View>
          {isPnl && pnlPct != null ? (
            <View style={[s.pnlBadge, { backgroundColor: (pnlPct >= 0 ? colors.buy : colors.sell) + '15' }]}>
              <Text style={[s.pnlBadgeText, { color: pnlPct >= 0 ? colors.buy : colors.sell }]}>
                {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(1)}%
              </Text>
            </View>
          ) : isWatchlist && change24h != null ? (
            <View style={[s.pnlBadge, { backgroundColor: (change24h >= 0 ? colors.buy : colors.sell) + '15' }]}>
              <Text style={[s.pnlBadgeText, { color: change24h >= 0 ? colors.buy : colors.sell }]}>
                {change24h >= 0 ? '+' : ''}{change24h.toFixed(1)}%
              </Text>
            </View>
          ) : !isPushEvent ? (
            <Text style={[s.timeText, { color: colors.textMuted }]}>
              {item.createdAt ? timeAgo(item.createdAt) : ''}
            </Text>
          ) : null}
        </View>

        {ctaText && !isSystem && (
          <View style={s.ctaRow}>
            <Text style={[s.ctaText, { color: accentColor }]}>{ctaText}</Text>
            {item.createdAt && (isPnl || isWatchlist) && (
              <Text style={[s.timeTextSmall, { color: colors.textMuted }]}>
                {timeAgo(item.createdAt)}
              </Text>
            )}
          </View>
        )}
      </TouchableOpacity>
    );
  }, [colors, s, handleTap]);

  return (
    <View style={[s.container, { paddingTop: insets.top, backgroundColor: colors.background }]}>
      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity testID="notif-back" style={s.backBtn} onPress={onClose}>
          <Ionicons name="chevron-back" size={20} color={colors.textSecondary} />
        </TouchableOpacity>
        <Text style={[s.headerTitle, { color: colors.textPrimary }]}>Notifications</Text>
        <TouchableOpacity onPress={markAllRead}>
          <Text style={[s.readAll, { color: colors.accent }]}>{t('intel.readAll')}</Text>
        </TouchableOpacity>
      </View>

      {/* Tabs */}
      <View style={s.tabs}>
        {TABS.map(t => {
          const active = tab === t.key;
          const count = t.key === 'ALL' ? items.filter(n => !n.read).length
            : t.key === 'PORTFOLIO' ? items.filter(n => !n.read && (n.type === 'PNL_ALERT' || n.type === 'WATCHLIST_ALERT' || n.type === 'FOMO')).length
            : t.key === 'EDGE' ? items.filter(n => !n.read && (n.type === 'EDGE')).length
            : t.key === 'SIGNAL' ? items.filter(n => !n.read && n.type === 'SIGNAL').length
            : 0;
          return (
            <TouchableOpacity
              key={t.key}
              testID={`notif-tab-${t.key.toLowerCase()}`}
              style={[s.tab, active && { borderBottomColor: colors.accent, borderBottomWidth: 2 }]}
              onPress={() => setTab(t.key as Tab)}
            >
              <Text style={[s.tabText, { color: active ? colors.accent : colors.textMuted }]}>
                {t.label}{count > 0 ? ` (${count})` : ''}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Grouped list */}
      {loading ? (
        <View style={s.center}><ActivityIndicator color={colors.accent} /></View>
      ) : (
        <SectionList
          testID="notif-list"
          sections={sections}
          keyExtractor={item => item.id}
          renderItem={renderItem}
          stickySectionHeadersEnabled={false}
          renderSectionHeader={({ section: { title } }) => (
            <Text style={[s.sectionHeader, { color: colors.textMuted, backgroundColor: colors.background }]}>
              {title}
            </Text>
          )}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={doRefresh} tintColor={colors.accent} />}
          contentContainerStyle={[s.listContent, { paddingBottom: insets.bottom + 20 }]}
          ListEmptyComponent={
            <View style={s.center}>
              <Ionicons name="pulse-outline" size={36} color={colors.textMuted} />
              <Text style={[s.emptyText, { color: colors.textPrimary, fontWeight: '700', fontSize: 15 }]}>{t('intel.noSignalsYet')}</Text>
              <Text style={[s.emptyText, { color: colors.textMuted, fontSize: 12, textAlign: 'center', paddingHorizontal: 32 }]}>
                We'll notify you when something starts forming.
              </Text>
            </View>
          }
        />
      )}
    </View>
  );
}

const mk = (c: any) => StyleSheet.create({
  container: { flex: 1 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 10 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: c.surface, justifyContent: 'center', alignItems: 'center' },
  headerTitle: { fontSize: 18, fontWeight: '700' },
  readAll: { fontSize: 13, fontWeight: '600' },

  tabs: { flexDirection: 'row', paddingHorizontal: 12, borderBottomWidth: 1, borderBottomColor: c.border },
  tab: { paddingHorizontal: 12, paddingVertical: 10 },
  tabText: { fontSize: 13, fontWeight: '600' },

  listContent: { paddingHorizontal: 16, paddingTop: 8 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingTop: 60, gap: 8 },
  emptyText: { fontSize: 14 },

  sectionHeader: {
    fontSize: 11,
    fontWeight: '800',
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    paddingTop: 10,
    paddingBottom: 6,
  },

  card: { borderRadius: 12, padding: 14, borderWidth: 1, marginBottom: 8 },
  badgeRow: {
    flexDirection: 'row', alignItems: 'center',
    gap: 6, marginBottom: 8,
  },
  sourceChip: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 8, paddingVertical: 3,
    borderRadius: 999, borderWidth: 1, gap: 4,
  },
  sourceChipIcon: { fontSize: 11 },
  sourceChipLabel: { fontSize: 11, fontWeight: '700' },
  sourceChipAsset: { fontSize: 10.5, fontWeight: '600' },
  prioPill: { paddingHorizontal: 7, paddingVertical: 2, borderRadius: 6 },
  prioPillText: { fontSize: 9.5, fontWeight: '800', letterSpacing: 0.4 },

  cardTop: { flexDirection: 'row', gap: 10 },
  iconWrap: { width: 32, height: 32, borderRadius: 16, justifyContent: 'center', alignItems: 'center', marginTop: 2 },
  coinIconWrap: { width: 36, height: 36, borderRadius: 18, justifyContent: 'center', alignItems: 'center', marginTop: 2 },
  cardContent: { flex: 1 },
  cardTitle: { fontSize: 14, fontWeight: '700', lineHeight: 20 },
  cardBody: { fontSize: 12, lineHeight: 17, marginTop: 2 },
  timeText: { fontSize: 10, marginLeft: 'auto' },
  timeTextSmall: { fontSize: 10 },

  pnlBadge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8, marginTop: 2, alignSelf: 'flex-start' },
  pnlBadgeText: { fontSize: 13, fontWeight: '800', fontVariant: ['tabular-nums'] as any },

  ctaRow: { marginTop: 8, paddingTop: 8, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: c.border, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  ctaText: { fontSize: 12, fontWeight: '700' },
});
