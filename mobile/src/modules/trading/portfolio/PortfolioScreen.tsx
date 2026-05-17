/**
 * ExposureScreen (formerly PortfolioScreen) — T2 UI wiring.
 *
 * Lists OPEN paper positions from GET /api/trading/paper/positions with
 * live unrealized P&L, plus account summary and CLOSED history.
 * Close button calls POST /api/trading/paper/close.
 *
 * Replaces the old portfolio facade with real T1 runtime data.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl, Alert, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../../core/useColors';
import {
  tradingRuntimeApi, PaperAccount, PaperPosition,
} from '../../../services/api/trading-runtime-api';

function fmtNum(n: number | null | undefined, decimals = 2): string {
  if (n == null || isNaN(n)) return '—';
  return n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return '—';
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(2)}%`;
}

function fmtUsd(n: number | null | undefined): string {
  if (n == null) return '—';
  const sign = n > 0 ? '+' : '';
  return `${sign}$${Math.abs(n).toFixed(2)}`;
}

export function PortfolioScreen() {
  const colors = useColors();
  const styles = useMemo(() => makeStyles(colors), [colors]);

  const [account, setAccount] = useState<PaperAccount | null>(null);
  const [openPos, setOpenPos] = useState<PaperPosition[]>([]);
  const [closedPos, setClosedPos] = useState<PaperPosition[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [closingId, setClosingId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<'OPEN' | 'CLOSED'>('OPEN');

  const load = useCallback(async () => {
    try {
      setErr(null);
      const [acc, open, closed] = await Promise.all([
        tradingRuntimeApi.account(),
        tradingRuntimeApi.positions('OPEN'),
        tradingRuntimeApi.positions('CLOSED'),
      ]);
      setAccount(acc);
      setOpenPos(open.positions || []);
      setClosedPos(closed.positions || []);
    } catch (e: any) {
      setErr(e?.message || 'failed to load exposure');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    const id = setInterval(load, 20_000);
    return () => clearInterval(id);
  }, [load]);

  const onRefresh = useCallback(() => { setRefreshing(true); void load(); }, [load]);

  const onClose = useCallback(async (pos: PaperPosition) => {
    const confirm = () => new Promise<boolean>((resolve) => {
      const msg = `Close ${pos.symbol} ${pos.side}\n` +
        `Entry $${fmtNum(pos.entryPrice)} · Current $${fmtNum(pos.currentPrice)}\n` +
        `P&L: ${fmtUsd(pos.unrealizedPnlUsd)} (${fmtPct(pos.unrealizedPnlPct)})`;
      if (Platform.OS === 'web') {
        resolve(window.confirm(msg));
      } else {
        Alert.alert('Close paper position', msg, [
          { text: 'Cancel', style: 'cancel', onPress: () => resolve(false) },
          { text: 'Close', style: 'destructive', onPress: () => resolve(true) },
        ]);
      }
    });
    const ok = await confirm();
    if (!ok) return;
    setClosingId(pos.positionId);
    try {
      const res = await tradingRuntimeApi.close(pos.positionId, 'manual');
      if (res.ok) {
        const msg = `Closed ${pos.symbol} at $${fmtNum(res.closePrice)}\nRealized P&L: ${fmtUsd(res.pnlUsd)} (${fmtPct(res.pnlPct)})`;
        if (Platform.OS === 'web') window.alert(msg);
        else Alert.alert('Position closed', msg);
      } else {
        const msg = res.error || 'close failed';
        if (Platform.OS === 'web') window.alert(msg);
        else Alert.alert('Close failed', msg);
      }
    } catch (e: any) {
      const msg = e?.message || 'close error';
      if (Platform.OS === 'web') window.alert(msg);
      else Alert.alert('Close error', msg);
    } finally {
      setClosingId(null);
      void load();
    }
  }, [load]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} />
        <Text style={styles.muted} testID="exposure-loading">Loading exposure…</Text>
      </View>
    );
  }

  if (err || !account) {
    return (
      <View style={styles.center}>
        <Ionicons name="alert-circle" size={28} color={colors.sell || '#ef4444'} />
        <Text style={styles.error} testID="exposure-error">{err || 'no account'}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={() => load()} testID="exposure-retry">
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const winRate = account.totalTrades > 0
    ? ((account.wins / account.totalTrades) * 100).toFixed(0) + '%'
    : '—';

  const positions = tab === 'OPEN' ? openPos : closedPos;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
      testID="exposure-screen"
    >
      {/* ACCOUNT SUMMARY */}
      <View style={[styles.accountCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        <Text style={styles.sectionTitle}>PAPER ACCOUNT</Text>
        {/* Equity gets its own row so the large value never collides with
            the balance/unrealized stack on narrow viewports. */}
        <View style={styles.equityBlock}>
          <Text style={styles.equityLabel}>equity</Text>
          <Text
            style={styles.equityValue}
            testID="exposure-equity"
            numberOfLines={1}
            adjustsFontSizeToFit
            minimumFontScale={0.7}
          >
            ${fmtNum(account.equityUsd, 2)}
          </Text>
        </View>
        {/* Balance / Unrealized — wraps on narrow widths instead of clipping. */}
        <View style={styles.equitySplit}>
          <View style={styles.equitySplitItem}>
            <Text style={styles.statLabel}>balance</Text>
            <Text style={styles.statValue} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.8}>
              ${fmtNum(account.balanceUsd, 2)}
            </Text>
          </View>
          <View style={styles.equitySplitItem}>
            <Text style={styles.statLabel}>unrealized</Text>
            <Text
              style={[styles.statValue, { color: (account.unrealizedPnlUsd || 0) >= 0 ? colors.buy : colors.sell }]}
              testID="exposure-unrealized"
              numberOfLines={1}
              adjustsFontSizeToFit
              minimumFontScale={0.8}
            >
              {fmtUsd(account.unrealizedPnlUsd)}
            </Text>
          </View>
        </View>
        <View style={styles.statsRow}>
          <Stat label="open" value={String(account.openPositions)} colors={colors} testID="stat-open" />
          <Stat label="trades" value={String(account.totalTrades)} colors={colors} testID="stat-trades" />
          <Stat label="wins" value={String(account.wins)} colors={colors} testID="stat-wins" />
          <Stat label="losses" value={String(account.losses)} colors={colors} testID="stat-losses" />
          <Stat label="winrate" value={winRate} colors={colors} testID="stat-winrate" />
          <Stat label="realized" value={fmtUsd(account.realizedPnlUsd)} colors={colors} testID="stat-realized" />
        </View>
      </View>

      {/* TABS */}
      <View style={styles.tabRow}>
        <TabBtn label={`OPEN (${openPos.length})`} active={tab === 'OPEN'} onPress={() => setTab('OPEN')} colors={colors} testID="tab-open" />
        <TabBtn label={`CLOSED (${closedPos.length})`} active={tab === 'CLOSED'} onPress={() => setTab('CLOSED')} colors={colors} testID="tab-closed" />
      </View>

      {/* POSITIONS */}
      {positions.length === 0 ? (
        <View style={[styles.emptyBox, { borderColor: colors.border }]} testID={`exposure-empty-${tab.toLowerCase()}`}>
          <Ionicons name="folder-open-outline" size={32} color={colors.textMuted} />
          <Text style={styles.muted}>
            {tab === 'OPEN' ? 'No open paper positions' : 'No closed positions yet'}
          </Text>
          {tab === 'OPEN' && (
            <Text style={[styles.muted, { fontSize: 11 }]}>
              Open one from the Deployment screen when verdict is LONG/SHORT.
            </Text>
          )}
        </View>
      ) : (
        positions.map((p) => (
          <PositionCard
            key={p.positionId}
            position={p}
            colors={colors}
            onClose={tab === 'OPEN' ? () => onClose(p) : undefined}
            closing={closingId === p.positionId}
          />
        ))
      )}
    </ScrollView>
  );
}

function Stat({ label, value, colors, testID }: { label: string; value: string; colors: any; testID?: string }) {
  return (
    <View style={statStyles.stat} testID={testID}>
      <Text style={[statStyles.label, { color: colors.textMuted }]}>{label}</Text>
      <Text style={[statStyles.value, { color: colors.text }]}>{value}</Text>
    </View>
  );
}

function TabBtn({ label, active, onPress, colors, testID }: { label: string; active: boolean; onPress: () => void; colors: any; testID?: string }) {
  return (
    <TouchableOpacity
      onPress={onPress}
      testID={testID}
      style={[
        tabStyles.tab,
        { borderColor: active ? colors.accent : colors.border, backgroundColor: active ? colors.accent + '22' : 'transparent' },
      ]}
    >
      <Text style={[tabStyles.tabLabel, { color: active ? colors.accent : colors.textMuted }]}>{label}</Text>
    </TouchableOpacity>
  );
}

function PositionCard({ position: p, colors, onClose, closing }: {
  position: PaperPosition; colors: any; onClose?: () => void; closing?: boolean;
}) {
  const isOpen = p.status === 'OPEN';
  const sideCol = p.side === 'LONG' ? (colors.buy || '#22c55e') : (colors.sell || '#ef4444');
  const pnl = isOpen ? p.unrealizedPnlUsd : p.realizedPnlUsd;
  const pnlPct = isOpen ? p.unrealizedPnlPct : p.realizedPnlPct;
  const pnlCol = (pnl || 0) >= 0 ? (colors.buy || '#22c55e') : (colors.sell || '#ef4444');

  return (
    <View
      style={[posStyles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}
      testID={`position-${p.positionId}`}
    >
      <View style={posStyles.headerRow}>
        <View style={posStyles.headerLeft}>
          <Text style={[posStyles.symbol, { color: colors.text }]}>{p.symbol}</Text>
          <View style={[posStyles.sidePill, { backgroundColor: sideCol }]}>
            <Text style={posStyles.sidePillText}>{p.side}</Text>
          </View>
        </View>
        <View style={posStyles.headerRight}>
          <Text style={[posStyles.pnl, { color: pnlCol }]} testID={`position-pnl-${p.positionId}`}>
            {fmtUsd(pnl)}
          </Text>
          <Text style={[posStyles.pnlPct, { color: pnlCol }]}>{fmtPct(pnlPct)}</Text>
        </View>
      </View>

      <View style={posStyles.levels}>
        <LevelCol label="entry" value={`$${fmtNum(p.entryPrice)}`} colors={colors} />
        <LevelCol label="stop" value={`$${fmtNum(p.stopPrice)}`} colors={colors} />
        <LevelCol label="target" value={`$${fmtNum(p.targetPrice)}`} colors={colors} />
        <LevelCol
          label={isOpen ? 'current' : 'closed at'}
          value={`$${fmtNum(isOpen ? p.currentPrice : p.closePrice)}`}
          colors={colors}
        />
      </View>

      <View style={posStyles.metaRow}>
        <Text style={[posStyles.meta, { color: colors.textMuted }]}>
          size ${fmtNum(p.sizeUsd, 2)} · opened {new Date(p.openedAt).toLocaleTimeString()}
        </Text>
        {!isOpen && p.closeReason && (
          <Text style={[posStyles.meta, { color: colors.textMuted }]}>
            · {p.closeReason}
          </Text>
        )}
      </View>

      {isOpen && onClose && (
        <TouchableOpacity
          testID={`close-btn-${p.positionId}`}
          onPress={onClose}
          disabled={closing}
          style={[posStyles.closeBtn, { borderColor: colors.border }]}
          activeOpacity={0.8}
        >
          {closing ? (
            <ActivityIndicator color={colors.text} size="small" />
          ) : (
            <>
              <Ionicons name="close-circle-outline" size={16} color={colors.text} />
              <Text style={[posStyles.closeBtnText, { color: colors.text }]}>CLOSE</Text>
            </>
          )}
        </TouchableOpacity>
      )}
    </View>
  );
}

function LevelCol({ label, value, colors }: { label: string; value: string; colors: any }) {
  return (
    <View style={posStyles.levelCol}>
      <Text style={[posStyles.levelLabel, { color: colors.textMuted }]}>{label}</Text>
      <Text style={[posStyles.levelValue, { color: colors.text }]}>{value}</Text>
    </View>
  );
}

const statStyles = StyleSheet.create({
  stat: { alignItems: 'flex-start', minWidth: 56 },
  label: { fontSize: 10, letterSpacing: 1, textTransform: 'uppercase' },
  value: { fontSize: 13, fontWeight: '700', marginTop: 2 },
});

const tabStyles = StyleSheet.create({
  tab: { flex: 1, paddingVertical: 10, borderWidth: 1, borderRadius: 10, alignItems: 'center' },
  tabLabel: { fontSize: 12, fontWeight: '700', letterSpacing: 1 },
});

const posStyles = StyleSheet.create({
  card: { borderWidth: 1, borderRadius: 12, padding: 14, marginBottom: 10 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  headerLeft: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  headerRight: { alignItems: 'flex-end' },
  symbol: { fontSize: 17, fontWeight: '800', letterSpacing: 0.5 },
  sidePill: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6 },
  sidePillText: { color: '#fff', fontSize: 10, fontWeight: '800', letterSpacing: 1 },
  pnl: { fontSize: 16, fontWeight: '800' },
  pnlPct: { fontSize: 11, fontWeight: '600', marginTop: 1 },
  levels: { flexDirection: 'row', gap: 6, marginBottom: 10 },
  levelCol: { flex: 1 },
  levelLabel: { fontSize: 9, letterSpacing: 1, textTransform: 'uppercase' },
  levelValue: { fontSize: 12, fontWeight: '700', marginTop: 2 },
  metaRow: { flexDirection: 'row', flexWrap: 'wrap' },
  meta: { fontSize: 10 },
  closeBtn: {
    marginTop: 10, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, paddingVertical: 9, borderWidth: 1, borderRadius: 8,
  },
  closeBtnText: { fontSize: 11, fontWeight: '700', letterSpacing: 1 },
});

const makeStyles = (colors: any) =>
  StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background },
    content: { padding: 16, paddingBottom: 80 },
    center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background, gap: 10 },
    muted: { color: colors.textMuted, fontSize: 12, textAlign: 'center' },
    error: { color: colors.sell || '#ef4444', fontSize: 14, marginTop: 8 },
    retryBtn: { paddingHorizontal: 18, paddingVertical: 8, borderRadius: 8, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, marginTop: 10 },
    retryText: { color: colors.text, fontWeight: '600' },
    accountCard: { borderWidth: 1, borderRadius: 12, padding: 14, marginBottom: 14 },
    sectionTitle: { fontSize: 11, letterSpacing: 1.5, color: colors.textMuted, marginBottom: 10, textTransform: 'uppercase', fontWeight: '700' },
    equityBlock: { marginBottom: 14 },
    equityLabel: { fontSize: 10, letterSpacing: 1, textTransform: 'uppercase', color: colors.textMuted },
    equityValue: { fontSize: 26, fontWeight: '800', color: colors.text, marginTop: 4 },
    equitySplit: { flexDirection: 'row', flexWrap: 'wrap', gap: 18, marginBottom: 4 },
    equitySplitItem: { minWidth: 110, flexShrink: 1 },
    statLabel: { fontSize: 9, letterSpacing: 1, textTransform: 'uppercase', color: colors.textMuted },
    statValue: { fontSize: 13, fontWeight: '700', color: colors.text, marginTop: 2 },
    statsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.border },
    tabRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
    emptyBox: { borderWidth: 1, borderStyle: 'dashed', borderRadius: 12, padding: 24, alignItems: 'center', gap: 8 },
  });
