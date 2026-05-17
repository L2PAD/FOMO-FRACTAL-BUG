/**
 * AssetIntelligenceScreen — The decision point.
 *
 * User feels: "I understand → I want to act → I need PRO"
 *
 * Structure: Hero → WhyNow → Narrative → Setup(🔒) → Modules(🔒) → Role(🔒) → Paywall → CTA
 */

import React, { useEffect, useState, useMemo } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, Image,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../../core/useColors';
import { useAssetStore } from '../../../stores/asset.store';
import { useSessionStore } from '../../../stores/session.store';
import { useAppMode } from '../../../stores/app-mode.store';
import { mobileApi } from '../../../services/api/mobile-api';
import { getCryptoIconUrl } from '../../../utils/crypto-icons';

import { t } from '../../../core/i18n';
const STATUS_COLORS: Record<string, string> = {
  CORE: '#FFFFFF', EARLY: '#00E676', CONFIRMATION: '#448AFF',
  ROTATION: '#FF9100', TRAP: '#FF5252', NEUTRAL: '#666',
};

export function AssetIntelligenceScreen() {
  const colors = useColors();
  const s = useMemo(() => mk(colors), [colors]);
  const asset = useAssetStore((st) => st.currentAsset);
  const user = useSessionStore((st) => st.user);
  const isPro = user?.plan === 'PRO' || user?.plan === 'INSTITUTIONAL';
  const { setDeepIntelModule } = useAppMode();

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    mobileApi.getAssetIntelligence(asset).then((d) => {
      if (d?.ok) setData(d);
    }).catch(() => {}).finally(() => setLoading(false));
  }, [asset]);

  const goBack = () => setDeepIntelModule(null);

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator size="large" color={colors.accent} />
        <Text style={[s.loadTxt, { color: colors.textMuted }]}>{t('intel.loadingIntelligence')}</Text>
      </View>
    );
  }

  if (!data) {
    return (
      <View style={s.center}>
        <Text style={[s.loadTxt, { color: colors.textMuted }]}>No data for {asset}</Text>
        <TouchableOpacity onPress={goBack}>
          <Text style={[s.backLink, { color: colors.accent }]}>{t('intel.goBack')}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const sc = STATUS_COLORS[data.status] || '#666';
  const isLong = data.direction === 'LONG';
  const dc = isLong ? colors.buy : colors.sell;
  const ts = data.tradeSetup || {};
  const modules = data.modules || [];

  return (
    <ScrollView style={s.root} contentContainerStyle={s.content}>
      {/* Back */}
      <TouchableOpacity style={s.backRow} onPress={goBack}>
        <Ionicons name="arrow-back" size={18} color={colors.textMuted} />
        <Text style={[s.backTxt, { color: colors.textMuted }]}>Back</Text>
      </TouchableOpacity>

      {/* ═══ HERO ═══ */}
      <View style={s.hero}>
        <View style={s.heroTop}>
          <Image source={{ uri: getCryptoIconUrl(asset) }} style={s.heroIcon} />
          <View>
            <Text style={[s.heroSymbol, { color: colors.textPrimary }]}>{data.symbol}</Text>
            <View style={[s.statusBadge, { backgroundColor: sc + '18' }]}>
              <Text style={[s.statusTxt, { color: sc }]}>{data.statusLabel}</Text>
            </View>
          </View>
          <View style={s.heroRight}>
            <Text style={[s.heroConf, { color: sc }]}>{data.confidence}%</Text>
            <Text style={[s.heroConfLabel, { color: colors.textMuted }]}>confidence</Text>
          </View>
        </View>
        <Text style={[s.heroNarr, { color: colors.textPrimary }]}>{data.narrative}</Text>
      </View>

      {/* ═══ WHY NOW ═══ */}
      <View style={[s.block, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        <Text style={[s.blockTitle, { color: colors.textMuted }]}>{t('intel.whyNow')}</Text>
        {(data.reasons || []).slice(0, 3).map((r: string, i: number) => (
          <View key={i} style={s.reasonRow}>
            <Text style={[s.reasonArrow, { color: dc }]}>→</Text>
            <Text style={[s.reasonTxt, { color: colors.textSecondary }]}>{r}</Text>
          </View>
        ))}
      </View>

      {/* ═══ TRADE SETUP (🔒 PRO) ═══ */}
      <View style={[s.block, { backgroundColor: colors.surface, borderColor: isPro ? dc + '30' : colors.border }]}>
        <View style={s.blockHead}>
          <Text style={[s.blockTitle, { color: colors.textMuted }]}>{t('intel.tradeSetup')}</Text>
          {ts.tf && <Text style={[s.tfBadge, { color: colors.textMuted, backgroundColor: colors.surfaceHover }]}>{ts.tf}</Text>}
        </View>

        {/* Direction always visible */}
        <View style={[s.dirRow, { backgroundColor: dc + '12' }]}>
          <Ionicons name={isLong ? 'trending-up' : 'trending-down'} size={14} color={dc} />
          <Text style={[s.dirTxt, { color: dc }]}>{data.symbol} {data.direction}</Text>
          <Text style={[s.moveTxt, { color: dc }]}>{ts.expectedMove}</Text>
        </View>

        {isPro ? (
          /* PRO: Full setup */
          <View style={s.setupGrid}>
            <View style={s.setupCol}>
              <Text style={[s.setupLbl, { color: colors.textMuted }]}>Entry</Text>
              <Text style={[s.setupVal, { color: colors.textPrimary }]}>{ts.entry}</Text>
            </View>
            <View style={s.setupCol}>
              <Text style={[s.setupLbl, { color: colors.textMuted }]}>Target</Text>
              <Text style={[s.setupVal, { color: dc }]}>{ts.target}</Text>
            </View>
            <View style={s.setupCol}>
              <Text style={[s.setupLbl, { color: colors.textMuted }]}>Risk</Text>
              <Text style={[s.setupVal, { color: colors.sell }]}>{ts.invalidation}</Text>
            </View>
          </View>
        ) : (
          /* FREE: Locked */
          <View style={s.setupGrid}>
            <View style={s.setupCol}>
              <Text style={[s.setupLbl, { color: colors.textMuted }]}>Entry</Text>
              <Text style={[s.setupLocked, { color: colors.textMuted }]}>🔒</Text>
            </View>
            <View style={s.setupCol}>
              <Text style={[s.setupLbl, { color: colors.textMuted }]}>Target</Text>
              <Text style={[s.setupLocked, { color: colors.textMuted }]}>🔒</Text>
            </View>
            <View style={s.setupCol}>
              <Text style={[s.setupLbl, { color: colors.textMuted }]}>Risk</Text>
              <Text style={[s.setupLocked, { color: colors.textMuted }]}>🔒</Text>
            </View>
          </View>
        )}
      </View>

      {/* ═══ MODULES (partial for FREE) ═══ */}
      <View style={[s.block, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        <Text style={[s.blockTitle, { color: colors.textMuted }]}>{t('intel.signalBreakdown')}</Text>
        {(isPro ? modules : modules.slice(0, 1)).map((m: any, i: number) => {
          const mc = m.direction === 'Bullish' ? colors.buy : m.direction === 'Bearish' ? colors.sell : colors.textMuted;
          return (
            <View key={i} style={[s.modRow, { borderColor: colors.border }]}>
              <Text style={[s.modName, { color: colors.textPrimary }]}>{m.name}</Text>
              <View style={[s.modBadge, { backgroundColor: mc + '15' }]}>
                <Text style={[s.modDir, { color: mc }]}>{m.direction}</Text>
              </View>
              <Text style={[s.modReason, { color: colors.textMuted }]} numberOfLines={1}>{m.reason}</Text>
            </View>
          );
        })}
        {!isPro && modules.length > 1 && (
          <Text style={[s.hiddenTxt, { color: colors.textMuted }]}>
            + {modules.length - 1} signals hidden
          </Text>
        )}
      </View>

      {/* ═══ PORTFOLIO ROLE (🔒 PRO) ═══ */}
      {isPro ? (
        <View style={[s.block, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <Text style={[s.blockTitle, { color: colors.textMuted }]}>{t('intel.roleInPortfolio')}</Text>
          <Text style={[s.roleTxt, { color: sc }]}>{data.portfolioRole}</Text>
          <Text style={[s.roleDesc, { color: colors.textSecondary }]}>
            {data.status === 'CORE' ? 'Market anchor. Lower risk. Foundation.' :
             data.status === 'EARLY' ? 'High beta. Early upside capture.' :
             data.status === 'CONFIRMATION' ? 'Mid-risk continuation play.' :
             data.status === 'TRAP' ? 'Overcrowded. Watch for reversal.' :
             'Diversification asset.'}
          </Text>
        </View>
      ) : (
        <View style={[s.lockedBlock, { borderColor: colors.border }]}>
          <Ionicons name="lock-closed" size={14} color={colors.textMuted} />
          <Text style={[s.lockedTxt, { color: colors.textMuted }]}>{t('intel.portfolioRoleHidden')}</Text>
        </View>
      )}

      {/* ═══ PAYWALL (FREE only) ═══ */}
      {!isPro && (
        <View style={[s.paywall, { backgroundColor: colors.accent + '08', borderColor: colors.accent + '25' }]}>
          <Text style={[s.pwTitle, { color: colors.accent }]}>
            You see the idea.{'\n'}You don't see the execution.
          </Text>
          <Text style={[s.pwSub, { color: colors.textMuted }]}>
            Most users enter after confirmation.{'\n'}You can enter before.
          </Text>
          <TouchableOpacity style={[s.pwBtn, { backgroundColor: colors.accent }]}>
            <Text style={s.pwBtnTxt}>{t('intel.unlockFullAccess')}</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* ═══ CTA ═══ */}
      <TouchableOpacity style={[s.ctaPrimary, { borderColor: colors.accent }]}>
        <Ionicons name="eye" size={14} color={colors.accent} />
        <Text style={[s.ctaPrimaryTxt, { color: colors.accent }]}>{t('intel.trackThisSetup')}</Text>
      </TouchableOpacity>

      <TouchableOpacity style={[s.ctaSecondary, { borderColor: colors.border }]}>
        <Ionicons name="swap-horizontal" size={14} color={colors.textMuted} />
        <Text style={[s.ctaSecondaryTxt, { color: colors.textMuted }]}>{t('intel.openInTradeTerminal')}</Text>
      </TouchableOpacity>
      <Text style={[s.disclaimer, { color: colors.textMuted }]}>
        Execution engine may differ from analysis
      </Text>

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}


const mk = (c: any) => StyleSheet.create({
  root: { flex: 1, backgroundColor: c.background },
  content: { paddingHorizontal: 20, paddingTop: 8, paddingBottom: 40 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: c.background, gap: 12 },
  loadTxt: { fontSize: 13, fontStyle: 'italic' },
  backLink: { fontSize: 14, fontWeight: '600' },
  backRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 16, paddingVertical: 4 },
  backTxt: { fontSize: 13 },

  /* Hero */
  hero: { marginBottom: 20 },
  heroTop: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 14 },
  heroIcon: { width: 48, height: 48, borderRadius: 24 },
  heroSymbol: { fontSize: 24, fontWeight: '800' },
  heroRight: { marginLeft: 'auto', alignItems: 'flex-end' },
  heroConf: { fontSize: 22, fontWeight: '800' },
  heroConfLabel: { fontSize: 10, fontWeight: '600', letterSpacing: 0.5 },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 5, marginTop: 3, alignSelf: 'flex-start' },
  statusTxt: { fontSize: 10, fontWeight: '700', letterSpacing: 0.5 },
  heroNarr: { fontSize: 17, fontWeight: '700', lineHeight: 24, letterSpacing: -0.2 },

  /* Blocks */
  block: { borderRadius: 14, borderWidth: 1, padding: 16, marginBottom: 14, gap: 10 },
  blockTitle: { fontSize: 10, fontWeight: '800', letterSpacing: 1.5 },
  blockHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  tfBadge: { fontSize: 10, fontWeight: '700', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, overflow: 'hidden' },

  /* Why Now */
  reasonRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  reasonArrow: { fontSize: 13, fontWeight: '700', marginTop: 1 },
  reasonTxt: { fontSize: 13, lineHeight: 18, flex: 1 },

  /* Trade Setup */
  dirRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8 },
  dirTxt: { fontSize: 13, fontWeight: '700', flex: 1 },
  moveTxt: { fontSize: 18, fontWeight: '800' },
  setupGrid: { flexDirection: 'row', justifyContent: 'space-around', paddingTop: 6 },
  setupCol: { alignItems: 'center' },
  setupLbl: { fontSize: 9, fontWeight: '600', letterSpacing: 0.5, marginBottom: 2 },
  setupVal: { fontSize: 14, fontWeight: '700' },
  setupLocked: { fontSize: 18 },

  /* Modules */
  modRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6, borderBottomWidth: 0.5 },
  modName: { fontSize: 13, fontWeight: '600', width: 80 },
  modBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4 },
  modDir: { fontSize: 11, fontWeight: '700' },
  modReason: { fontSize: 11, flex: 1 },
  hiddenTxt: { fontSize: 12, fontStyle: 'italic', textAlign: 'center', paddingTop: 4 },

  /* Role */
  roleTxt: { fontSize: 14, fontWeight: '700' },
  roleDesc: { fontSize: 13, lineHeight: 18 },

  /* Locked */
  lockedBlock: { flexDirection: 'row', alignItems: 'center', gap: 8, borderWidth: 1, borderRadius: 14, padding: 16, marginBottom: 14, borderStyle: 'dashed' },
  lockedTxt: { fontSize: 13, fontStyle: 'italic' },

  /* Paywall */
  paywall: { borderRadius: 16, borderWidth: 1.5, padding: 20, marginBottom: 14, alignItems: 'center', gap: 10 },
  pwTitle: { fontSize: 16, fontWeight: '700', textAlign: 'center', lineHeight: 23 },
  pwSub: { fontSize: 13, textAlign: 'center', lineHeight: 19 },
  pwBtn: { paddingHorizontal: 28, paddingVertical: 12, borderRadius: 10, marginTop: 4 },
  pwBtnTxt: { color: '#fff', fontSize: 13, fontWeight: '800', letterSpacing: 1 },

  /* CTAs */
  ctaPrimary: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 14, borderRadius: 12, borderWidth: 1, marginBottom: 8 },
  ctaPrimaryTxt: { fontSize: 13, fontWeight: '700' },
  ctaSecondary: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 12, borderRadius: 12, borderWidth: 1, marginBottom: 4 },
  ctaSecondaryTxt: { fontSize: 12, fontWeight: '600' },
  disclaimer: { fontSize: 10, textAlign: 'center', fontStyle: 'italic', marginTop: 2 },
});
