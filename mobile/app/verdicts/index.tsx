/**
 * Verdict Inspector — Expo Trading Runtime v1 — main observability screen.
 *
 * Goal: show users the FULL pipeline of how a verdict was reached:
 *
 *   RAW MODEL  →  RULES  →  META-BRAIN  →  CALIBRATION  →  FINAL ACTION
 *
 * with the suppression/downgrade/blocking reasons surfaced as badges.
 *
 * This is the killer feature highlighted by the audit phase: every
 * verdict becomes observable — users can see where their signal died,
 * why it was downgraded, and what macro/funding/risk overlays fired.
 *
 * READ-ONLY. No execution. No order routing. No leverage. No commit.
 * Lists only. Backed by /api/mbrain/verdicts/list and /sweep.
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl, Modal, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import Constants from 'expo-constants';
import { useRouter, useLocalSearchParams } from 'expo-router';

import type { VerdictCard, StageBlock, StageName } from '../../src/types/verdict';

import { t } from '../../src/core/i18n';
const API_URL =
  Constants.expoConfig?.extra?.apiUrl ||
  process.env.EXPO_PUBLIC_BACKEND_URL ||
  '';

const STAGES: StageName[] = [
  'raw', 'after_rules', 'after_meta_brain', 'after_calibration', 'final',
];

const STAGE_LABELS: Record<StageName, string> = {
  raw: 'Raw model',
  after_rules: 'Rules',
  after_meta_brain: 'Meta-Brain',
  after_calibration: 'Calibration',
  final: 'Final action',
};

const COLORS = {
  bg: '#0a0e1a',
  surface: '#0f1422',
  surfaceHi: '#162033',
  border: '#1d2940',
  text: '#e8ecf4',
  textDim: '#8b96a8',
  textFaint: '#5a657a',
  long: '#39d98a',
  short: '#ff5a5a',
  hold: '#7a8294',
  warn: '#f5a623',
  block: '#d0021b',
  alert: '#e879f9',
  accent: '#4da3ff',
};

function dirColor(d?: string): string {
  if (d === 'LONG') return COLORS.long;
  if (d === 'SHORT') return COLORS.short;
  return COLORS.hold;
}

function fmtPct(n: number | null | undefined): string {
  if (n === null || n === undefined || isNaN(n)) return '—';
  return `${(n * 100).toFixed(1)}%`;
}

function fmtConf(n: number | null | undefined): string {
  if (n === null || n === undefined || isNaN(n)) return '—';
  return `${(n * 100).toFixed(0)}%`;
}

// Tiny stage pill used in card preview row.
function StagePill({ stage, info }: { stage: StageName; info?: StageBlock }) {
  const dir = info?.direction || 'HOLD';
  const collapsed = info?.collapsed_to_hold;
  return (
    <View style={[styles.stagePill, { borderColor: dirColor(dir) }]}>
      <Text style={[styles.stagePillLabel, { color: COLORS.textDim }]}>
        {STAGE_LABELS[stage].split(' ')[0].toUpperCase()}
      </Text>
      <Text style={[styles.stagePillDir, { color: dirColor(dir) }]}>
        {dir}{collapsed ? '*' : ''}
      </Text>
    </View>
  );
}

function CardRow({ card, onPress, onPressPaper }:
  { card: VerdictCard; onPress: () => void; onPressPaper: () => void }) {
  return (
    <TouchableOpacity
      style={styles.card}
      activeOpacity={0.85}
      onPress={onPress}
      testID={`verdict-card-${card.symbol}-${card.horizon}`}
    >
      <View style={styles.cardTop}>
        <View style={{ flex: 1 }}>
          <Text style={styles.cardSymbol}>{card.symbol}</Text>
          <Text style={styles.cardSub}>
            {card.horizon}  •  {card.regime || '—'}  •  {card.modelId || '—'}
          </Text>
        </View>
        <View style={{ alignItems: 'flex-end' }}>
          <View style={[styles.actionBadge,
            { backgroundColor: dirColor(card.final_action) + '22',
              borderColor: dirColor(card.final_action) }]}>
            <Text style={[styles.actionBadgeText,
              { color: dirColor(card.final_action) }]}>
              {card.final_action}
            </Text>
          </View>
          <Text style={[styles.cardConf, { color: COLORS.textDim }]}>
            conf {fmtConf(card.confidence_final)}
          </Text>
        </View>
      </View>
      <View style={styles.stageRow}>
        {STAGES.map((s) => (
          <StagePill key={s} stage={s} info={card.stages[s]} />
        ))}
      </View>
      {card.badges.length > 0 && (
        <View style={styles.badgeRow}>
          {card.badges.map((b, i) => (
            <View key={i} style={[styles.badge, {
              backgroundColor: (b.tone === 'block' ? COLORS.block :
                                b.tone === 'alert' ? COLORS.alert :
                                COLORS.warn) + '22',
              borderColor: (b.tone === 'block' ? COLORS.block :
                            b.tone === 'alert' ? COLORS.alert :
                            COLORS.warn),
            }]} testID={`verdict-badge-${b.type}`}>
              <Text style={[styles.badgeText, {
                color: b.tone === 'block' ? COLORS.block :
                       b.tone === 'alert' ? COLORS.alert : COLORS.warn,
              }]}>{b.label}</Text>
            </View>
          ))}
        </View>
      )}
      <TouchableOpacity
        style={styles.paperLink}
        onPress={(e) => { e?.stopPropagation?.(); onPressPaper(); }}
        testID={`verdict-card-paperlink-${card.symbol}-${card.horizon}`}
        activeOpacity={0.7}
      >
        <Ionicons name="trending-up" size={12} color={COLORS.accent} />
        <Text style={styles.paperLinkText}>view paper PnL</Text>
        <Ionicons name="chevron-forward" size={12} color={COLORS.accent} />
      </TouchableOpacity>
    </TouchableOpacity>
  );
}

function StageDetailRow({ stage, info, prev }:
  { stage: StageName; info: StageBlock; prev?: StageBlock }) {
  const dir = info.direction;
  const conf = info.confidence;
  const er = info.expectedReturn;
  const dirChanged = prev && prev.direction !== dir;
  return (
    <View style={styles.detailRow}>
      <View style={styles.detailLeft}>
        <View style={[styles.stageDot, { backgroundColor: dirColor(dir) }]} />
        <View style={styles.stageLine} />
      </View>
      <View style={styles.detailRight}>
        <Text style={styles.detailStage}>{STAGE_LABELS[stage]}</Text>
        <View style={styles.detailMetricsRow}>
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>direction</Text>
            <Text style={[styles.metricValue,
              { color: dirColor(dir),
                fontWeight: dirChanged ? '800' : '600' }]}>
              {dir}{info.collapsed_to_hold ? ' (collapsed)' : ''}
            </Text>
          </View>
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>confidence</Text>
            <Text style={styles.metricValue}>{fmtConf(conf)}</Text>
          </View>
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>expected</Text>
            <Text style={styles.metricValue}>{fmtPct(er)}</Text>
          </View>
        </View>
      </View>
    </View>
  );
}

function InspectorModal({ card, onClose, onPressPaper }:
  { card: VerdictCard | null; onClose: () => void;
    onPressPaper: (c: VerdictCard) => void }) {
  if (!card) return null;
  const stages = STAGES.map((s, idx) => ({
    s, info: card.stages[s], prev: idx === 0 ? undefined : card.stages[STAGES[idx - 1]],
  }));
  return (
    <Modal visible={!!card} animationType="slide" transparent
           onRequestClose={onClose}>
      <View style={styles.modalBackdrop}>
        <SafeAreaView style={styles.modalSheet} edges={['bottom']}>
          <View style={styles.modalHeader}>
            <View style={{ flex: 1 }}>
              <Text style={styles.modalTitle}>{card.symbol} • {card.horizon}</Text>
              <Text style={styles.modalSub}>
                {new Date(card.ts).toLocaleString()}
              </Text>
            </View>
            <TouchableOpacity
              style={styles.paperLinkLg}
              onPress={() => onPressPaper(card)}
              testID="inspector-paper-btn"
              activeOpacity={0.75}
            >
              <Ionicons name="trending-up" size={14} color={COLORS.accent} />
              <Text style={styles.paperLinkLgText}>paper PnL</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={onClose} style={styles.closeBtn}
                              testID="inspector-close-btn">
              <Ionicons name="close" size={22} color={COLORS.text} />
            </TouchableOpacity>
          </View>
          <ScrollView contentContainerStyle={{ paddingBottom: 32 }}>
            <View style={styles.modalActionBlock}>
              <Text style={styles.modalLabelSmall}>{t('app.finalAction')}</Text>
              <Text style={[styles.modalAction,
                { color: dirColor(card.final_action) }]}>
                {card.final_action}
              </Text>
              <Text style={styles.modalLabelSmall}>
                Confidence {fmtConf(card.confidence_final)}
                {card.risk ? `  •  Risk ${card.risk}` : ''}
              </Text>
            </View>

            {card.badges.length > 0 && (
              <View style={[styles.badgeRow, { paddingHorizontal: 16 }]}>
                {card.badges.map((b, i) => (
                  <View key={i} style={[styles.badge, {
                    backgroundColor: (b.tone === 'block' ? COLORS.block :
                                      b.tone === 'alert' ? COLORS.alert :
                                      COLORS.warn) + '22',
                    borderColor: (b.tone === 'block' ? COLORS.block :
                                  b.tone === 'alert' ? COLORS.alert :
                                  COLORS.warn),
                  }]}>
                    <Text style={[styles.badgeText, {
                      color: b.tone === 'block' ? COLORS.block :
                             b.tone === 'alert' ? COLORS.alert : COLORS.warn,
                    }]}>{b.label}</Text>
                  </View>
                ))}
              </View>
            )}

            <Text style={styles.sectionTitle}>Pipeline</Text>
            <View style={styles.pipelineWrap}>
              {stages.map(({ s, info, prev }) => (
                <StageDetailRow key={s} stage={s} info={info} prev={prev} />
              ))}
            </View>

            {card.raw_appliedRules.length > 0 && (
              <>
                <Text style={styles.sectionTitle}>{t('app.rulesFired')}</Text>
                {card.raw_appliedRules.map((r, i) => (
                  <View key={i} style={styles.kvRow}>
                    <Text style={[styles.kvKey, {
                      color: r.severity === 'BLOCK' ? COLORS.block :
                             r.severity === 'WARN' ? COLORS.warn : COLORS.textDim,
                    }]}>{r.severity}</Text>
                    <Text style={styles.kvVal} numberOfLines={2}>
                      {r.id}{r.message ? ` — ${r.message}` : ''}
                    </Text>
                  </View>
                ))}
              </>
            )}

            {card.raw_adjustments.length > 0 && (
              <>
                <Text style={styles.sectionTitle}>Adjustments</Text>
                {card.raw_adjustments.map((a, i) => (
                  <View key={i} style={styles.kvRow}>
                    <Text style={styles.kvKey}>{a.stage}</Text>
                    <Text style={styles.kvVal}>
                      {a.key || a.notes || ''}
                      {a.deltaConfidence !== undefined ?
                        `  Δconf ${(a.deltaConfidence * 100).toFixed(1)}%` : ''}
                      {a.deltaReturn !== undefined ?
                        `  Δer ${(a.deltaReturn * 100).toFixed(2)}%` : ''}
                    </Text>
                  </View>
                ))}
              </>
            )}

            <Text style={styles.disclaimer}>
              Read-only observability layer. No execution. No persistence in
              side-car. No production fusion influence. Verdict id: {card.verdictId || 'n/a'}.
            </Text>
          </ScrollView>
        </SafeAreaView>
      </View>
    </Modal>
  );
}

export default function VerdictsScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ symbol?: string; h?: string }>();
  const symbolFilter = (params.symbol || '').toString().toUpperCase();
  const horizonFilter = (params.h || '').toString().toUpperCase();
  const [cards, setCards] = useState<VerdictCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [sweeping, setSweeping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<VerdictCard | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const goPaper = (sym: string, h: string) => {
    setSelected(null);
    router.push(
      `/positions?symbol=${encodeURIComponent(sym)}&h=${encodeURIComponent(h)}` as any
    );
  };

  const fetchList = async () => {
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/mbrain/verdicts/list?limit=50`);
      const data = await res.json();
      if (data?.ok) {
        setCards(data.cards || []);
        setLastUpdate(new Date());
      } else {
        setError(data?.error || 'Failed to load verdicts');
      }
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const triggerSweep = async () => {
    if (sweeping) return;
    setSweeping(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_URL}/api/mbrain/verdicts/sweep` +
        `?assets=BTC,ETH,SOL,BNB,XRP,DOGE&horizons=1D,7D,30D&range=7d`,
        { method: 'GET' },
      );
      const data = await res.json();
      if (data?.ok) {
        setCards(data.cards || []);
        setLastUpdate(new Date());
      } else {
        setError('Sweep failed');
      }
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setSweeping(false);
    }
  };

  useEffect(() => {
    fetchList();
  }, []);

  const filteredCards = useMemo(() => {
    if (!symbolFilter && !horizonFilter) return cards;
    return cards.filter((c) => {
      const symMatch = !symbolFilter ||
        c.symbol.toUpperCase().includes(symbolFilter);
      const hMatch = !horizonFilter ||
        c.horizon.toUpperCase() === horizonFilter;
      return symMatch && hMatch;
    });
  }, [cards, symbolFilter, horizonFilter]);

  const stats = useMemo(() => {
    let l = 0, s = 0, h = 0, supp = 0;
    for (const c of filteredCards) {
      if (c.final_action === 'LONG') l++;
      else if (c.final_action === 'SHORT') s++;
      else h++;
      if (c.badges.some((b) => b.type === 'SUPPRESSED')) supp++;
    }
    return { l, s, h, supp, n: filteredCards.length };
  }, [filteredCards]);

  return (
    <SafeAreaView style={styles.root} edges={['top']}>
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>Verdicts</Text>
          <Text style={styles.headerSub}>
            Observability layer — read-only
            {symbolFilter ? `  ·  ${symbolFilter}` : ''}
            {horizonFilter ? `  ·  ${horizonFilter}` : ''}
          </Text>
        </View>
        <TouchableOpacity
          onPress={() => router.push(
            `/positions${symbolFilter || horizonFilter
              ? `?symbol=${encodeURIComponent(symbolFilter)}&h=${encodeURIComponent(horizonFilter)}`
              : ''}` as any
          )}
          style={styles.toPositionsBtn}
          testID="verdicts-to-positions"
          activeOpacity={0.75}
        >
          <Ionicons name="trending-up" size={14} color={COLORS.accent} />
          <Text style={styles.toPositionsBtnText}>Positions</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.sweepBtn, sweeping && { opacity: 0.5 }]}
          onPress={triggerSweep}
          disabled={sweeping}
          testID="verdicts-sweep-btn"
        >
          {sweeping ? (
            <ActivityIndicator color={COLORS.accent} size="small" />
          ) : (
            <>
              <Ionicons name="refresh" size={16} color={COLORS.accent} />
              <Text style={styles.sweepBtnText}>Sweep</Text>
            </>
          )}
        </TouchableOpacity>
      </View>

      <View style={styles.statsRow}>
        <View style={styles.stat}>
          <Text style={[styles.statN, { color: COLORS.long }]}>{stats.l}</Text>
          <Text style={styles.statLabel}>LONG</Text>
        </View>
        <View style={styles.stat}>
          <Text style={[styles.statN, { color: COLORS.short }]}>{stats.s}</Text>
          <Text style={styles.statLabel}>SHORT</Text>
        </View>
        <View style={styles.stat}>
          <Text style={[styles.statN, { color: COLORS.hold }]}>{stats.h}</Text>
          <Text style={styles.statLabel}>HOLD</Text>
        </View>
        <View style={styles.stat}>
          <Text style={[styles.statN, { color: COLORS.warn }]}>{stats.supp}</Text>
          <Text style={styles.statLabel}>SUPPRESSED</Text>
        </View>
        <View style={styles.stat}>
          <Text style={styles.statN}>{stats.n}</Text>
          <Text style={styles.statLabel}>TOTAL</Text>
        </View>
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={COLORS.accent} />
          <Text style={[styles.dim, { marginTop: 12 }]}>Loading verdicts…</Text>
        </View>
      ) : (
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ padding: 16, paddingBottom: 48 }}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => { setRefreshing(true); fetchList(); }}
              tintColor={COLORS.accent}
            />
          }
        >
          {error && (
            <View style={styles.errorBox}>
              <Ionicons name="alert-circle" size={16} color={COLORS.warn} />
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}
          {filteredCards.length === 0 ? (
            <View style={styles.emptyBox}>
              <Ionicons name="search" size={28} color={COLORS.textFaint} />
              <Text style={[styles.emptyTitle]}>
                {(symbolFilter || horizonFilter)
                  ? 'No verdicts match this filter'
                  : 'No verdicts in store'}
              </Text>
              <Text style={[styles.dim, { textAlign: 'center', marginTop: 6 }]}>
                {(symbolFilter || horizonFilter)
                  ? `Filter: ${symbolFilter || ''} ${horizonFilter || ''}`.trim()
                  : 'Side-car has no committed verdicts yet (audit-only mode). Tap "Sweep" to trigger a fresh evaluation.'}
              </Text>
              {lastUpdate && (
                <Text style={[styles.dim, { marginTop: 12, fontSize: 11 }]}>
                  last update {lastUpdate.toLocaleTimeString()}
                </Text>
              )}
            </View>
          ) : (
            filteredCards.map((c, i) => (
              <CardRow key={`${c.symbol}-${c.horizon}-${i}`} card={c}
                       onPress={() => setSelected(c)}
                       onPressPaper={() => goPaper(c.symbol, c.horizon)} />
            ))
          )}
        </ScrollView>
      )}

      <InspectorModal
        card={selected}
        onClose={() => setSelected(null)}
        onPressPaper={(c) => goPaper(c.symbol, c.horizon)}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.bg },
  header: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 16, paddingTop: 8, paddingBottom: 12,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: COLORS.border,
  },
  headerTitle: { color: COLORS.text, fontSize: 22, fontWeight: '800' },
  headerSub: { color: COLORS.textDim, fontSize: 11, marginTop: 2 },
  sweepBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 12, paddingVertical: 8,
    borderWidth: 1, borderColor: COLORS.accent, borderRadius: 999,
  },
  sweepBtnText: { color: COLORS.accent, fontSize: 12, fontWeight: '700' },
  toPositionsBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 10, paddingVertical: 8, marginRight: 6,
    borderWidth: 1, borderColor: COLORS.accent, borderRadius: 999,
  },
  toPositionsBtnText: { color: COLORS.accent, fontSize: 12, fontWeight: '700' },
  paperLink: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    alignSelf: 'flex-start', marginTop: 10,
    paddingHorizontal: 8, paddingVertical: 4,
    borderWidth: StyleSheet.hairlineWidth, borderColor: COLORS.accent + '88',
    borderRadius: 999, backgroundColor: COLORS.accent + '0e',
  },
  paperLinkText: { color: COLORS.accent, fontSize: 11, fontWeight: '700' },
  paperLinkLg: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 10, paddingVertical: 7, marginRight: 8,
    borderWidth: 1, borderColor: COLORS.accent, borderRadius: 999,
  },
  paperLinkLgText: { color: COLORS.accent, fontSize: 12, fontWeight: '800' },
  statsRow: {
    flexDirection: 'row', justifyContent: 'space-around',
    paddingVertical: 12, backgroundColor: COLORS.surface,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: COLORS.border,
  },
  stat: { alignItems: 'center' },
  statN: { color: COLORS.text, fontSize: 18, fontWeight: '800' },
  statLabel: { color: COLORS.textFaint, fontSize: 9, fontWeight: '700',
               letterSpacing: 0.5, marginTop: 2 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  dim: { color: COLORS.textDim, fontSize: 12 },
  card: {
    backgroundColor: COLORS.surface, borderRadius: 12,
    padding: 14, marginBottom: 10,
    borderWidth: StyleSheet.hairlineWidth, borderColor: COLORS.border,
  },
  cardTop: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 10 },
  cardSymbol: { color: COLORS.text, fontSize: 16, fontWeight: '800' },
  cardSub: { color: COLORS.textDim, fontSize: 11, marginTop: 2 },
  cardConf: { fontSize: 10, marginTop: 4 },
  actionBadge: {
    borderWidth: 1, paddingHorizontal: 10, paddingVertical: 3,
    borderRadius: 6, alignSelf: 'flex-end',
  },
  actionBadgeText: { fontSize: 12, fontWeight: '900', letterSpacing: 0.5 },
  stageRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  stagePill: {
    borderWidth: 1, paddingHorizontal: 7, paddingVertical: 3,
    borderRadius: 4, minWidth: 60,
  },
  stagePillLabel: { fontSize: 8, fontWeight: '700', letterSpacing: 0.5 },
  stagePillDir: { fontSize: 11, fontWeight: '800', marginTop: 1 },
  badgeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 10 },
  badge: {
    borderWidth: 1, paddingHorizontal: 8, paddingVertical: 3,
    borderRadius: 999,
  },
  badgeText: { fontSize: 10, fontWeight: '700' },
  errorBox: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: COLORS.warn + '11', padding: 10, borderRadius: 8,
    marginBottom: 12, borderWidth: 1, borderColor: COLORS.warn + '33',
  },
  errorText: { color: COLORS.warn, fontSize: 12, flex: 1 },
  emptyBox: {
    paddingVertical: 60, alignItems: 'center',
    paddingHorizontal: 32,
  },
  emptyTitle: {
    color: COLORS.text, fontSize: 16, fontWeight: '700',
    marginTop: 12, marginBottom: 4,
  },
  modalBackdrop: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'flex-end',
  },
  modalSheet: {
    backgroundColor: COLORS.bg, maxHeight: '92%',
    borderTopLeftRadius: 20, borderTopRightRadius: 20,
    borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: COLORS.border,
  },
  modalHeader: {
    flexDirection: 'row', alignItems: 'flex-start',
    paddingHorizontal: 16, paddingTop: 16, paddingBottom: 12,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: COLORS.border,
  },
  modalTitle: { color: COLORS.text, fontSize: 18, fontWeight: '800' },
  modalSub: { color: COLORS.textDim, fontSize: 11, marginTop: 4 },
  closeBtn: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: COLORS.surface, alignItems: 'center', justifyContent: 'center',
  },
  modalActionBlock: { padding: 16, alignItems: 'center' },
  modalAction: { fontSize: 36, fontWeight: '900', letterSpacing: 1, marginVertical: 6 },
  modalLabelSmall: { color: COLORS.textDim, fontSize: 11 },
  sectionTitle: {
    color: COLORS.textDim, fontSize: 11, fontWeight: '700',
    letterSpacing: 1, paddingHorizontal: 16, marginTop: 18, marginBottom: 8,
  },
  pipelineWrap: { paddingHorizontal: 16 },
  detailRow: { flexDirection: 'row' },
  detailLeft: { width: 24, alignItems: 'center', paddingTop: 6 },
  stageDot: { width: 12, height: 12, borderRadius: 6 },
  stageLine: { flex: 1, width: 2, backgroundColor: COLORS.border, minHeight: 28 },
  detailRight: {
    flex: 1, paddingBottom: 16, paddingLeft: 4,
  },
  detailStage: { color: COLORS.text, fontSize: 13, fontWeight: '700' },
  detailMetricsRow: { flexDirection: 'row', gap: 16, marginTop: 6 },
  metric: { flex: 1 },
  metricLabel: { color: COLORS.textFaint, fontSize: 9, fontWeight: '700',
                 letterSpacing: 0.5 },
  metricValue: { color: COLORS.text, fontSize: 13, fontWeight: '600', marginTop: 2 },
  kvRow: {
    flexDirection: 'row', paddingHorizontal: 16, paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: COLORS.border,
  },
  kvKey: { color: COLORS.textDim, fontSize: 10, fontWeight: '800',
           width: 90, letterSpacing: 0.5 },
  kvVal: { color: COLORS.text, fontSize: 12, flex: 1 },
  disclaimer: {
    color: COLORS.textFaint, fontSize: 10,
    paddingHorizontal: 16, paddingTop: 24, lineHeight: 14,
  },
});
