/**
 * Portfolio Intelligence Screen
 *
 * NOT trading. NOT execution.
 * WHY money is distributed this way.
 *
 * Explains the THESIS behind each position.
 */

import React, { useMemo } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../../core/useColors';
import { usePortfolioStore } from '../../../stores/portfolio.store';
import { CoinIcon } from '../../../components/CoinIcon';

import { t } from '../../../core/i18n';
const ROLE_ICONS: Record<string, string> = {
  CORE: 'shield-checkmark',
  EARLY_BETA: 'flash',
  CONFIRMATION: 'checkmark-circle',
  BETA: 'trending-up',
};

export function PortfolioIntelligenceScreen() {
  const colors = useColors();
  const s = useMemo(() => mk(colors), [colors]);
  const portfolio = usePortfolioStore((st) => st.pendingPortfolio);
  const portfolioMeta = usePortfolioStore((st) => st.pendingMeta);

  const goBack = () => {
    usePortfolioStore.getState().setShowIntelScreen(false);
  };

  if (!portfolio || portfolio.length === 0) {
    return (
      <View style={s.center}>
        <Text style={[s.emptyTxt, { color: colors.textMuted }]}>{t('intelFeed.noPortfolioStrategyAvailable')}</Text>
        <TouchableOpacity onPress={goBack}>
          <Text style={[s.backLink, { color: colors.accent }]}>{t('intelFeed.backToFeed')}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const metrics = portfolioMeta?.metrics || {};
  const risk = portfolioMeta?.risk || {};

  return (
    <ScrollView style={s.root} contentContainerStyle={s.content}>
      {/* Back */}
      <TouchableOpacity style={s.backRow} onPress={goBack}>
        <Ionicons name="arrow-back" size={18} color={colors.textMuted} />
        <Text style={[s.backTxt, { color: colors.textMuted }]}>Feed</Text>
      </TouchableOpacity>

      {/* Hero */}
      <View style={s.hero}>
        <Text style={[s.heroTitle, { color: colors.textPrimary }]}>{t('intelFeed.portfolioStrategy')}</Text>
        <Text style={[s.heroSub, { color: colors.accent }]}>
          You see positioning before the market
        </Text>
        <Text style={[s.heroCaption, { color: colors.textMuted }]}>
          BTC leads. Alts follow with higher beta.
        </Text>
      </View>

      {/* Metrics bar */}
      <View style={[s.metricsBar, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        <View style={s.metricItem}>
          <Text style={[s.metLbl, { color: colors.textMuted }]}>Expected</Text>
          <Text style={[s.metVal, { color: colors.buy }]}>{metrics.expectedMove || '+22.1%'}</Text>
        </View>
        <View style={s.metricItem}>
          <Text style={[s.metLbl, { color: colors.textMuted }]}>Worst</Text>
          <Text style={[s.metVal, { color: colors.sell }]}>{metrics.worstCase || '-8.9%'}</Text>
        </View>
        <View style={s.metricItem}>
          <Text style={[s.metLbl, { color: colors.textMuted }]}>Risk</Text>
          <Text style={[s.metVal, { color: colors.textPrimary }]}>{metrics.riskLevel || 'Moderate'}</Text>
        </View>
        <View style={s.metricItem}>
          <Text style={[s.metLbl, { color: colors.textMuted }]}>Horizon</Text>
          <Text style={[s.metVal, { color: colors.textPrimary }]}>3-10 days</Text>
        </View>
      </View>

      {/* Position cards */}
      {portfolio.map((pos: any, i: number) => {
        const isLong = pos.direction === 'LONG';
        const pc = isLong ? colors.buy : colors.sell;
        const roleColor = pos.color || colors.textPrimary;
        const icon = ROLE_ICONS[pos.role] || 'ellipse';

        return (
          <View key={i} style={[s.posCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
            {/* Role header */}
            <View style={s.posHead}>
              <View style={s.posHeadLeft}>
                <CoinIcon symbol={pos.asset} size={20} />
                <Text style={[s.posAsset, { color: colors.textPrimary }]}>{pos.asset}</Text>
                <View style={[s.posDirBadge, { backgroundColor: pc + '18' }]}>
                  <Text style={[s.posDirTxt, { color: pc }]}>{pos.direction}</Text>
                </View>
              </View>
              <Text style={[s.posAlloc, { color: roleColor }]}>{pos.allocationPct}</Text>
            </View>

            {/* Role label */}
            <Text style={[s.posRole, { color: roleColor }]}>{pos.roleLabel || pos.role}</Text>

            {/* Thesis bullets */}
            {(pos.thesis || []).map((t: string, j: number) => (
              <View key={j} style={s.thesisRow}>
                <Text style={[s.thesisArrow, { color: pc }]}>→</Text>
                <Text style={[s.thesisTxt, { color: colors.textSecondary }]}>{t}</Text>
              </View>
            ))}

            {/* Conclusion */}
            <Text style={[s.posConc, { color: colors.textPrimary }]}>{pos.conclusion}</Text>
          </View>
        );
      })}

      {/* Capital Rotation */}
      <View style={[s.rotBlock, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        <Text style={[s.rotTitle, { color: colors.textMuted }]}>{t('intelFeed.capitalRotation')}</Text>
        {portfolio.map((pos: any, i: number) => (
          <Text key={i} style={[s.rotLine, { color: colors.textSecondary }]}>
            {pos.asset} → {pos.role === 'CORE' ? 'market leader' : pos.role === 'EARLY_BETA' ? 'early positioning' : 'confirmation play'}
          </Text>
        ))}
        <Text style={[s.rotInsight, { color: colors.accent }]}>
          BTC moves first. Alts amplify the move.
        </Text>
      </View>

      {/* Risk Block */}
      {risk.scenarios && (
        <View style={[s.riskBlock, { backgroundColor: colors.sell + '08', borderColor: colors.sell + '20' }]}>
          <Text style={[s.riskTitle, { color: colors.sell }]}>{t('intelFeed.whatCanGoWrong')}</Text>
          {(risk.scenarios || []).map((sc: string, i: number) => (
            <Text key={i} style={[s.riskLine, { color: colors.textSecondary }]}>→ {sc}</Text>
          ))}
          <Text style={[s.riskAction, { color: colors.sell }]}>{risk.action}</Text>
        </View>
      )}

      {/* Edge */}
      <View style={[s.edgeBlock, { backgroundColor: colors.accent + '08' }]}>
        <Text style={[s.edgeTitle, { color: colors.accent }]}>{t('intelFeed.whyThisWorks')}</Text>
        <Text style={[s.edgeTxt, { color: colors.textSecondary }]}>
          Most users trade 1 asset.{'\n'}You're trading market structure.
        </Text>
        <Text style={[s.edgeSub, { color: colors.accent }]}>
          Diversification across roles, not coins.
        </Text>
      </View>

      {/* CTA — NOT execute, but track */}
      <TouchableOpacity style={[s.cta, { borderColor: colors.accent }]} onPress={goBack}>
        <Ionicons name="eye" size={14} color={colors.accent} />
        <Text style={[s.ctaTxt, { color: colors.accent }]}>{t('intelFeed.followThisPositioning')}</Text>
      </TouchableOpacity>

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}


const mk = (c: any) => StyleSheet.create({
  root: { flex: 1, backgroundColor: c.background },
  content: { paddingHorizontal: 20, paddingTop: 8, paddingBottom: 40 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: c.background, gap: 16 },
  emptyTxt: { fontSize: 14 },
  backLink: { fontSize: 14, fontWeight: '600' },
  backRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 16 },
  backTxt: { fontSize: 13 },

  hero: { marginBottom: 20 },
  heroTitle: { fontSize: 22, fontWeight: '800', letterSpacing: -0.3 },
  heroSub: { fontSize: 13, fontWeight: '600', marginTop: 4 },
  heroCaption: { fontSize: 12, marginTop: 3, fontStyle: 'italic' },

  metricsBar: { flexDirection: 'row', justifyContent: 'space-around', paddingVertical: 14, borderRadius: 14, borderWidth: 1, marginBottom: 20 },
  metricItem: { alignItems: 'center' },
  metLbl: { fontSize: 9, fontWeight: '600', letterSpacing: 0.5, marginBottom: 2 },
  metVal: { fontSize: 15, fontWeight: '800' },

  posCard: { borderRadius: 14, borderWidth: 1, padding: 16, marginBottom: 12, gap: 8 },
  posHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  posHeadLeft: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  posAsset: { fontSize: 16, fontWeight: '800' },
  posDirBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 5 },
  posDirTxt: { fontSize: 11, fontWeight: '700' },
  posAlloc: { fontSize: 18, fontWeight: '800' },
  posRole: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2, textTransform: 'uppercase' },
  thesisRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  thesisArrow: { fontSize: 13, fontWeight: '700', marginTop: 1 },
  thesisTxt: { fontSize: 13, lineHeight: 18, flex: 1 },
  posConc: { fontSize: 13, fontWeight: '600', lineHeight: 18, marginTop: 4 },

  rotBlock: { borderRadius: 14, borderWidth: 1, padding: 16, marginBottom: 16 },
  rotTitle: { fontSize: 10, fontWeight: '800', letterSpacing: 1.5, marginBottom: 8 },
  rotLine: { fontSize: 13, lineHeight: 20 },
  rotInsight: { fontSize: 13, fontWeight: '600', fontStyle: 'italic', marginTop: 8 },

  riskBlock: { borderRadius: 14, borderWidth: 1, padding: 16, marginBottom: 16, gap: 6 },
  riskTitle: { fontSize: 10, fontWeight: '800', letterSpacing: 1.5 },
  riskLine: { fontSize: 13, lineHeight: 18 },
  riskAction: { fontSize: 13, fontWeight: '600', marginTop: 4 },

  edgeBlock: { borderRadius: 14, padding: 16, marginBottom: 16 },
  edgeTitle: { fontSize: 10, fontWeight: '800', letterSpacing: 1.5, marginBottom: 8 },
  edgeTxt: { fontSize: 13, lineHeight: 20 },
  edgeSub: { fontSize: 13, fontWeight: '600', fontStyle: 'italic', marginTop: 8 },

  cta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 14, borderRadius: 12, borderWidth: 1 },
  ctaTxt: { fontSize: 13, fontWeight: '700' },
});
