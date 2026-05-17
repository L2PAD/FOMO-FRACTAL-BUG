/**
 * AssetSelectorModal — Asset Intelligence Layer entry point.
 *
 * NOT a list of coins.
 * System suggests → User explores → Intelligence opens.
 *
 * Structure:
 *   Search → System Picks → Watchlist → All Assets
 *   Each asset shows: symbol, status badge, reason, star
 *   onSelect → setCurrentAsset + open AssetIntelligenceScreen (NOT trade)
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, Modal, TextInput,
  FlatList, ActivityIndicator, Image,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useColors } from '../core/useColors';
import { useAssetStore, AssetInfo } from '../stores/asset.store';
import { useSessionStore } from '../stores/session.store';
import { mobileApi } from '../services/api/mobile-api';
import { getCryptoIconUrl } from '../utils/crypto-icons';

interface Props { visible: boolean; onClose: () => void; onOpenIntel?: (symbol: string) => void; }

/* Status color mapping */
const STATUS_COLORS: Record<string, string> = {
  CORE: '#FFFFFF', EARLY: '#00E676', CONFIRMATION: '#448AFF',
  ROTATION: '#FF9100', TRAP: '#FF5252', NEUTRAL: '#666',
};
const STATUS_ICONS: Record<string, string> = {
  CORE: 'shield-checkmark', EARLY: 'flash', CONFIRMATION: 'checkmark-circle',
  ROTATION: 'swap-horizontal', TRAP: 'warning', NEUTRAL: 'ellipse',
};

export function AssetSelectorModal({ visible, onClose, onOpenIntel }: Props) {
  const insets = useSafeAreaInsets();
  const colors = useColors();
  const s = React.useMemo(() => mk(colors), [colors]);
  const { currentAsset, allAssets, isLoaded, setCurrentAsset, setAllAssets } = useAssetStore();
  const userId = useSessionStore((st) => st.user?.id || 'dev_user');

  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [systemPicks, setSystemPicks] = useState<any[]>([]);
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [searchResults, setSearchResults] = useState<any[]>([]);

  // Load data on open — non-blocking
  useEffect(() => {
    if (!visible) return;

    // Load assets list (fast, needed for All Assets)
    if (!isLoaded) {
      setLoading(true);
      mobileApi.getAssets().then(assets => {
        setAllAssets(assets as AssetInfo[]);
      }).catch(() => {}).finally(() => setLoading(false));
    } else {
      setLoading(false);
    }

    // Load system picks (may be slow, but non-blocking)
    mobileApi.getSystemPicks().then(setSystemPicks).catch(() => {});

    // Load watchlist
    mobileApi.getWatchlist(userId).then(setWatchlist).catch(() => {});
  }, [visible]);

  // Search with intel
  useEffect(() => {
    if (query.length < 2) { setSearchResults([]); return; }
    const t = setTimeout(() => {
      mobileApi.searchAssetsIntel(query).then(setSearchResults).catch(() => {});
    }, 300);
    return () => clearTimeout(t);
  }, [query]);

  const handleSelect = useCallback((symbol: string) => {
    setCurrentAsset(symbol);
    setQuery('');
    onClose();
    // Open Asset Intelligence Screen
    if (onOpenIntel) onOpenIntel(symbol);
  }, [setCurrentAsset, onClose, onOpenIntel]);

  const toggleWatch = useCallback(async (symbol: string) => {
    if (watchlist.includes(symbol)) {
      const updated = await mobileApi.removeFromWatchlist(symbol, userId);
      setWatchlist(updated);
    } else {
      const updated = await mobileApi.addToWatchlist(symbol, userId);
      setWatchlist(updated);
    }
  }, [watchlist, userId]);

  const isWatched = (sym: string) => watchlist.includes(sym);
  const showSearch = query.length >= 2;

  // Watchlist assets with info
  const watchAssets = allAssets.filter(a => watchlist.includes(a.symbol));

  return (
    <Modal visible={visible} animationType="slide" transparent={false}>
      <View style={[s.root, { paddingTop: insets.top, backgroundColor: colors.background }]}>
        {/* Header */}
        <View style={s.header}>
          <Text style={[s.headerTitle, { color: colors.textPrimary }]}>Select Asset</Text>
          <TouchableOpacity onPress={onClose}><Ionicons name="close" size={24} color={colors.textSecondary} /></TouchableOpacity>
        </View>

        {/* Search */}
        <View style={[s.searchWrap, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <Ionicons name="search" size={16} color={colors.textMuted} />
          <TextInput style={[s.searchInput, { color: colors.textPrimary }]}
            placeholder="Search opportunities..." placeholderTextColor={colors.textMuted}
            value={query} onChangeText={setQuery} autoCapitalize="characters" autoCorrect={false} />
          {query.length > 0 && (
            <TouchableOpacity onPress={() => setQuery('')}><Ionicons name="close-circle" size={16} color={colors.textMuted} /></TouchableOpacity>
          )}
        </View>

        {loading ? (
          <View style={s.loadWrap}><ActivityIndicator size="large" color={colors.accent} /></View>
        ) : showSearch ? (
          /* ═══ SEARCH RESULTS ═══ */
          <FlatList data={searchResults}
            keyExtractor={i => i.symbol}
            renderItem={({ item }) => (
              <AssetRow item={item} colors={colors} s={s} isWatched={isWatched(item.symbol)}
                onSelect={handleSelect} onToggleWatch={toggleWatch} active={item.symbol === currentAsset} />
            )}
            contentContainerStyle={s.listContent}
            ListEmptyComponent={<Text style={[s.emptyTxt, { color: colors.textMuted }]}>No results</Text>}
          />
        ) : (
          /* ═══ MAIN CONTENT ═══ */
          <FlatList data={allAssets}
            keyExtractor={i => i.symbol}
            extraData={[systemPicks.length, watchlist.length, currentAsset]}
            renderItem={({ item }) => (
              <SimpleRow item={item} colors={colors} s={s} isWatched={isWatched(item.symbol)}
                onSelect={handleSelect} onToggleWatch={toggleWatch} active={item.symbol === currentAsset} />
            )}
            contentContainerStyle={s.listContent}
            ListHeaderComponent={
              <View>
                {/* ═══ SYSTEM PICKS ═══ */}
                {systemPicks.length > 0 && (
                  <View style={s.section}>
                    <View style={s.secHead}>
                      <Ionicons name="flash" size={12} color={colors.accent} />
                      <Text style={[s.secTitle, { color: colors.accent }]}>SUGGESTED BY SYSTEM</Text>
                    </View>
                    {systemPicks.map(pick => (
                      <AssetRow key={pick.symbol} item={pick} colors={colors} s={s}
                        isWatched={isWatched(pick.symbol)} onSelect={handleSelect}
                        onToggleWatch={toggleWatch} active={pick.symbol === currentAsset} highlight />
                    ))}
                  </View>
                )}

                {/* ═══ WATCHLIST ═══ */}
                {watchAssets.length > 0 && (
                  <View style={s.section}>
                    <View style={s.secHead}>
                      <Ionicons name="star" size={12} color="#FFD700" />
                      <Text style={[s.secTitle, { color: '#FFD700' }]}>YOUR WATCHLIST</Text>
                    </View>
                    {watchAssets.map(a => (
                      <SimpleRow key={a.symbol} item={a} colors={colors} s={s}
                        isWatched={true} onSelect={handleSelect} onToggleWatch={toggleWatch}
                        active={a.symbol === currentAsset} />
                    ))}
                  </View>
                )}

                <Text style={[s.secTitle, { color: colors.textMuted, marginTop: 16, marginBottom: 8, marginLeft: 4 }]}>ALL ASSETS</Text>
              </View>
            }
          />
        )}
      </View>
    </Modal>
  );
}

/* ═══ ASSET ROW (with status from system picks / search) ═══ */
function AssetRow({ item, colors, s, isWatched, onSelect, onToggleWatch, active, highlight }: any) {
  const sc = STATUS_COLORS[item.status] || '#666';

  return (
    <TouchableOpacity
      style={[s.row, active && s.rowActive, highlight && { borderLeftWidth: 3, borderLeftColor: sc }]}
      onPress={() => onSelect(item.symbol)} activeOpacity={0.7}
    >
      <View style={s.rowLeft}>
        <Image source={{ uri: getCryptoIconUrl(item.symbol) }} style={s.rowIconImg} />
        <View style={s.rowInfo}>
          <View style={s.rowNameRow}>
            <Text style={[s.rowSymbol, { color: colors.textPrimary }]}>{item.symbol}</Text>
            <View style={[s.statusBadge, { backgroundColor: sc + '18' }]}>
              <Text style={[s.statusTxt, { color: sc }]}>{item.statusLabel || item.status}</Text>
            </View>
          </View>
          <Text style={[s.rowReason, { color: colors.textMuted }]} numberOfLines={1}>
            {item.shortReason || item.reasons?.[0] || item.name || ''}
          </Text>
        </View>
      </View>
      <View style={s.rowRight}>
        {item.confidence > 0 && (
          <Text style={[s.confTxt, { color: sc }]}>{item.confidence}%</Text>
        )}
        <TouchableOpacity onPress={() => onToggleWatch(item.symbol)} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Ionicons name={isWatched ? 'star' : 'star-outline'} size={16} color={isWatched ? '#FFD700' : colors.textMuted} />
        </TouchableOpacity>
      </View>
    </TouchableOpacity>
  );
}

/* ═══ SIMPLE ROW (for all assets without status) ═══ */
function SimpleRow({ item, colors, s, isWatched, onSelect, onToggleWatch, active }: any) {
  return (
    <TouchableOpacity
      style={[s.row, active && s.rowActive]}
      onPress={() => onSelect(item.symbol)} activeOpacity={0.7}
    >
      <View style={s.rowLeft}>
        <Image source={{ uri: getCryptoIconUrl(item.symbol) }} style={s.rowIconImg} />
        <View style={s.rowInfo}>
          <Text style={[s.rowSymbol, { color: colors.textPrimary }]}>{item.symbol}</Text>
          <Text style={[s.rowReason, { color: colors.textMuted }]} numberOfLines={1}>{item.name || ''}</Text>
        </View>
      </View>
      <TouchableOpacity onPress={() => onToggleWatch(item.symbol)} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
        <Ionicons name={isWatched ? 'star' : 'star-outline'} size={16} color={isWatched ? '#FFD700' : colors.textMuted} />
      </TouchableOpacity>
    </TouchableOpacity>
  );
}

/* ═══ STYLES ═══ */
const mk = (c: any) => StyleSheet.create({
  root: { flex: 1 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 20, paddingVertical: 12 },
  headerTitle: { fontSize: 18, fontWeight: '700' },
  searchWrap: { flexDirection: 'row', alignItems: 'center', marginHorizontal: 20, paddingHorizontal: 12, paddingVertical: 10, borderRadius: 10, borderWidth: 1, gap: 8, marginBottom: 12 },
  searchInput: { flex: 1, fontSize: 14, padding: 0 },
  loadWrap: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  listContent: { paddingHorizontal: 16, paddingBottom: 40 },
  emptyTxt: { textAlign: 'center', marginTop: 40, fontSize: 14 },

  section: { marginBottom: 20 },
  secHead: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },
  secTitle: { fontSize: 10, fontWeight: '800', letterSpacing: 1.5 },

  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 10, paddingHorizontal: 8, borderRadius: 10, marginBottom: 2 },
  rowActive: { backgroundColor: c.accent + '10' },
  rowLeft: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 },
  rowIconImg: { width: 36, height: 36, borderRadius: 18 },
  rowInfo: { flex: 1 },
  rowNameRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  rowSymbol: { fontSize: 14, fontWeight: '700' },
  statusBadge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  statusTxt: { fontSize: 9, fontWeight: '700', letterSpacing: 0.5 },
  rowReason: { fontSize: 11, marginTop: 1 },
  rowRight: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  confTxt: { fontSize: 12, fontWeight: '700' },
});
