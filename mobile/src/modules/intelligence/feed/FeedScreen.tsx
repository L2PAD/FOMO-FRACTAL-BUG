/**
 * FeedScreen 4.0 — Execution-Grade Intelligence
 *
 * Every card = ready trade.
 * Top = Psychology. Bottom = Money.
 *
 * Tap Trade Setup → opens TradeScreen prefilled
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { mobileApi } from '../../../services/api/mobile-api';
import type { TopSignal } from '../../../services/api/mobile-api';
import { useAssetStore } from '../../../stores/asset.store';
import { useColors } from '../../../core/useColors';
import { useSessionStore } from '../../../stores/session.store';
import { useAppMode } from '../../../stores/app-mode.store';
import { usePortfolioStore } from '../../../stores/portfolio.store';
import { CoinIcon } from '../../../components/CoinIcon';
import { TradingBridgeCTA } from '../../../widgets/trading-bridge/TradingBridgeCTA';
import { CognitiveAnchor } from '../../../widgets/cognition/CognitiveAnchor';
import { useCognitionEffect, BusPulse } from '../../../widgets/cognition/bus/cognitiveBus';
import { MetaBrainIdentityStrip } from '../../../widgets/trading-bridge/MetaBrainIdentityStrip';
import { AIValueNarrativeFeed } from '../../../widgets/trading-bridge/AIValueNarrativeFeed';

import { t } from '../../../core/i18n';
/* ─── types ─── */
interface TradeSetup {
  asset: string;
  direction: string;
  action: string;
  entry: string;
  entryRaw: number;
  target: string;
  targetRaw: number;
  invalidation: string;
  invalidationRaw: number;
  expectedMove: string;
  expectedMoveRaw: number;
  rr: string;
  rrRaw: number;
  latePenalty: string;
  confirmed: boolean;
}

interface Card {
  id: string;
  type: string;
  asset: string;
  title: string;
  archetype: string;
  headline: string;
  crowd: string;
  reality: string[];
  tradeSetup: TradeSetup;
  conviction: string;
  danger: string;
  identity: string;
  microDynamic: string;
  cta: string;
  urgency: string;
  urgencyLevel: string;
  edgeVerdict: string;
  truth: string;
  edge: number;
  marketProb: number;
  modelProb: number;
  impact: string;
  volume: number;
  timestamp: string;
}

const ARCH_CFG: Record<string, { icon: string; label: string; ck: string }> = {
  CONTRARIAN: { icon: 'swap-horizontal', label: 'CONTRARIAN', ck: 'sell' },
  EARLY: { icon: 'flash', label: 'EARLY SIGNAL', ck: 'buy' },
  TRAP: { icon: 'warning', label: 'TRAP', ck: 'sell' },
  SMART_MONEY: { icon: 'analytics', label: 'SMART MONEY', ck: 'accent' },
};

/* ═══════════════════════════════════════
   FEED SCREEN
   ═══════════════════════════════════════ */
export function FeedScreen() {
  const colors = useColors();
  const s = React.useMemo(() => mk(colors), [colors]);
  const asset = useAssetStore((st) => st.currentAsset);
  const { setIntelTab } = useAppMode();
  const user = useSessionStore((st) => st.user);
  const isPro = user?.plan === 'PRO' || user?.plan === 'INSTITUTIONAL';

  const [mispricing, setMispricing] = useState<Card[]>([]);
  const [undervalued, setUndervalued] = useState<Card[]>([]);
  const [blindspots, setBlindspots] = useState<Card[]>([]);
  const [developing, setDeveloping] = useState<Card[]>([]);
  const [altOpps, setAltOpps] = useState<Card[]>([]);
  const [rotation, setRotation] = useState<any>(null);
  const [portfolio, setPortfolio] = useState<any>(null);
  const [signalImpact, setSignalImpact] = useState<any>(null);
  const [topSignal, setTopSignal] = useState<TopSignal | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const toggleCard = useCallback((id: string) => {
    setExpandedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const fetchData = useCallback(async () => {
    try {
      const data = await mobileApi.getFeedIntelligence(asset);
      if (data?.ok) {
        setMispricing(data.mispricing || []);
        setUndervalued(data.undervalued || []);
        setBlindspots(data.blindspots || []);
        setDeveloping(data.developing || []);
        setAltOpps(data.altOpportunities || []);
        setRotation(data.rotation || null);
        setPortfolio(data.portfolio || null);
        setSignalImpact(data.signalImpact || null);
      }
    } catch { /* silent */ } finally { setLoading(false); }
  }, [asset]);

  // Non-blocking top signal fetch — powers the MAIN SIGNAL NOW strip.
  useEffect(() => {
    let cancelled = false;
    mobileApi.getTopSignal()
      .then(r => { if (!cancelled && r?.ok) setTopSignal(r.data); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [asset]);

  useEffect(() => { setLoading(true); fetchData(); }, [fetchData]);
  const onRefresh = useCallback(async () => {
    setRefreshing(true); await fetchData(); setRefreshing(false);
  }, [fetchData]);

  const total = mispricing.length + undervalued.length + blindspots.length + developing.length + altOpps.length;

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator size="large" color={colors.accent} />
        <Text style={[s.loadText, { color: colors.textMuted }]}>{t('feed.scanningForBlindSpots')}</Text>
      </View>
    );
  }

  return (
    <ScrollView testID="feed-screen" style={s.root} contentContainerStyle={s.content}
      stickyHeaderIndices={[0]}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}>

      {/* ITERATION P5 · ambient cognition pulse — Feed contributes 'dormant' baseline */}
      <BusPulse energy="dormant" amount={0.35} />

      {/* ITERATION 4·γ · cognition dialect — Feed = AI noticing anomalies */}
      <CognitiveAnchor
        cognition="NOTICING"
        capital="OBSERVING"
        colors={colors}
      />

      {/* PHASE X · Cross-app cognition strip */}
      <View style={{ paddingHorizontal: 16 }}>
        <MetaBrainIdentityStrip variant="compact" tappable />
        <TradingBridgeCTA
          variant="why-ai-cares"
          customSub="every narrative here flows into AI cognition"
        />
      </View>

      {/* PHASE X · P2 — Global value perception */}
      <View style={{ paddingHorizontal: 16 }}>
        <AIValueNarrativeFeed
          layout="horizontal"
          title={t('feed.aiValueMoments')}
          subtitle="recent decisions · why this AI matters"
          limit={5}
        />
      </View>

      {/* ═══ 🔥 MAIN SIGNAL NOW — mirrors HomeScreen Hero ═══
          Confirms the user is seeing the "right" feed for the current top signal.
          Tap → jumps back to Home (memory of the original trigger). */}
      {topSignal && topSignal.priority !== 'LOW' && (() => {
        const happening = topSignal.priority === 'CRITICAL'
          && topSignal.ageMinutes < 10
          && topSignal.watchersCount > 20;
        const tail = happening ? 'happening' : topSignal.ageMinutes < 60 ? 'unfolding' : 'active';
        return (
          <TouchableOpacity
            activeOpacity={0.88}
            onPress={() => setIntelTab('HOME')}
            style={[
              s.mainSignalStrip,
              {
                backgroundColor: colors.accent + '12',
                borderColor: colors.accent + '40',
              },
            ]}
          >
            <View style={[s.mainSignalDot, { backgroundColor: colors.accent }]} />
            <Text style={[s.mainSignalLabel, { color: colors.accent }]} numberOfLines={1}>
              🔥 MAIN SIGNAL NOW · {tail}
            </Text>
            <Text style={[s.mainSignalTitle, { color: colors.textPrimary }]} numberOfLines={1}>
              {topSignal.title}
            </Text>
            <Text style={[s.mainSignalCta, { color: colors.accent }]}>→ View</Text>
          </TouchableOpacity>
        );
      })()}

      {/* Identity bar */}
      <View style={[s.idBar, { backgroundColor: colors.accent + '12' }]}>
        <Ionicons name="eye" size={12} color={colors.accent} />
        <Text style={[s.idBarTxt, { color: colors.accent }]}>You see the market before 92% of users</Text>
      </View>

      {/* Header */}
      <View style={s.hdr}>
        <Text style={[s.hdrTitle, { color: colors.textPrimary }]}>{t('feed.whereTheMarketIsWrong')}</Text>
        <Text style={[s.hdrSub, { color: colors.textMuted }]}>
          {total > 0 ? `${total} contradictions · ${mispricing.length} actionable` : 'No contradictions right now'}
        </Text>
      </View>

      {/* Mispricing */}
      {mispricing.length > 0 && (
        <View style={s.sec}>
          <SecHead icon="flash" text="MISPRICING" color={colors.sell} s={s} />
          {mispricing.map(c => <HeroCard key={c.id} card={c} colors={colors} s={s} expanded={expandedIds.has(c.id)} onToggle={toggleCard} />)}
        </View>
      )}

      {/* ═══ PORTFOLIO BLOCK 🔥 ═══ */}
      {portfolio && portfolio.positions && portfolio.positions.length > 0 && (
        <PortfolioBlock portfolio={portfolio} isPro={isPro} colors={colors} s={s} />
      )}

      {/* Blindspots */}
      {blindspots.length > 0 && (
        <View style={s.sec}>
          <SecHead icon="eye-off" text="BLIND SPOTS" color={colors.wait} s={s} />
          {blindspots.map(c => <BlindCard key={c.id} card={c} colors={colors} s={s} expanded={expandedIds.has(c.id)} onToggle={toggleCard} />)}
        </View>
      )}

      {/* ═══ ALT OPPORTUNITIES ═══ */}
      {altOpps.length > 0 && (
        <View style={s.sec}>
          <SecHead icon="swap-vertical" text="ALT OPPORTUNITIES" color={colors.accent} s={s} />
          <Text style={[s.altSubhead, { color: colors.textMuted }]}>{t('feed.altcoinsStartingToMoveCapital')}</Text>
          {altOpps.map(c => <EdgeCard key={c.id} card={c} colors={colors} s={s} />)}
        </View>
      )}

      {/* ═══ ROTATION ═══ */}
      {rotation && rotation.lines && rotation.lines.length > 0 && (
        <View style={[s.rotCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <Text style={[s.rotTitle, { color: colors.textMuted }]}>{t('feed.capitalRotation')}</Text>
          {rotation.lines.map((line: string, i: number) => (
            <Text key={i} style={[s.rotLine, { color: colors.textSecondary }]}>{line}</Text>
          ))}
          <Text style={[s.rotVerdict, { color: colors.accent }]}>{rotation.verdict}</Text>
        </View>
      )}

      {/* Impact */}
      {signalImpact && (signalImpact.supports > 0 || signalImpact.weakens > 0) && (
        <ImpactBar impact={signalImpact} asset={asset} colors={colors} s={s} />
      )}

      {/* Early Edge */}
      {undervalued.length > 0 && (
        <View style={s.sec}>
          <SecHead icon="trending-up" text="EARLY EDGE" color={colors.buy} s={s} />
          {undervalued.map(c => <EdgeCard key={c.id} card={c} colors={colors} s={s} />)}
        </View>
      )}

      {/* Developing */}
      {developing.length > 0 && (
        <View style={s.sec}>
          <Text style={[s.devTxt, { color: colors.textMuted }]}>
            DEVELOPING ({developing.length}) · Forming. No action yet.
          </Text>
        </View>
      )}

      <TouchableOpacity testID="feed-view-edge" style={[s.botCta, { borderColor: colors.accent }]}
        onPress={() => setIntelTab('EDGE')}>
        <Ionicons name="diamond-outline" size={14} color={colors.accent} />
        <Text style={[s.botCtaTxt, { color: colors.accent }]}>{t('feed.viewEarlyEdgeOpportunities')}</Text>
      </TouchableOpacity>

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

function SecHead({ icon, text, color, s }: any) {
  return (
    <View style={s.secH}><Ionicons name={icon} size={12} color={color} />
      <Text style={[s.secHTxt, { color }]}>{text}</Text></View>
  );
}


/* ═══════════════════════════════════════
   TRADE SETUP BLOCK — The money layer
   ═══════════════════════════════════════ */
function TradeBlock({ setup, colors, s }: { setup: TradeSetup; colors: any; s: any }) {
  const isLong = setup.direction === 'LONG';
  const dc = isLong ? colors.buy : colors.sell;

  const onTrade = useCallback(() => {
    // Track behavior
    mobileApi.trackEvent('feed_trade_tap', {
      asset: setup.asset,
      direction: setup.direction,
      entry: setup.entryRaw,
    });
  }, [setup]);

  return (
    <TouchableOpacity
      style={[s.tradeBlock, { backgroundColor: dc + '08', borderColor: dc + '25' }]}
      onPress={onTrade} activeOpacity={0.7}
    >
      {/* Direction + Asset + Timeframe */}
      <View style={s.tradeHead}>
        <View style={s.tradeHeadLeft}>
          <View style={[s.dirBadge, { backgroundColor: dc + '20' }]}>
            <Ionicons name={isLong ? 'trending-up' : 'trending-down'} size={12} color={dc} />
            <CoinIcon symbol={setup.asset} size={14} />
            <Text style={[s.dirTxt, { color: dc }]}>{setup.asset} {setup.direction}</Text>
          </View>
          {(setup as any).tf && (
            <View style={[s.tfBadge, { backgroundColor: colors.surfaceHover || '#121A23' }]}>
              <Text style={[s.tfTxt, { color: colors.textSecondary || '#aaa' }]}>{(setup as any).tf}</Text>
            </View>
          )}
        </View>
        <Text style={[s.moveTxt, { color: dc }]}>{setup.expectedMove}</Text>
      </View>

      {/* Entry / Target / Invalidation */}
      <View style={s.tradeGrid}>
        <View style={s.tradeCol}>
          <Text style={[s.tradeLbl, { color: colors.textMuted }]}>Entry</Text>
          <Text style={[s.tradeVal, { color: colors.textPrimary }]}>{setup.entry}</Text>
        </View>
        <View style={s.tradeCol}>
          <Text style={[s.tradeLbl, { color: colors.textMuted }]}>Target</Text>
          <Text style={[s.tradeVal, { color: dc }]}>{setup.target}</Text>
        </View>
        <View style={s.tradeCol}>
          <Text style={[s.tradeLbl, { color: colors.textMuted }]}>Risk</Text>
          <Text style={[s.tradeVal, { color: colors.sell }]}>{setup.invalidation}</Text>
        </View>
        {setup.rrRaw > 0 && (
          <View style={s.tradeCol}>
            <Text style={[s.tradeLbl, { color: colors.textMuted }]}>R:R</Text>
            <Text style={[s.tradeVal, { color: dc }]}>{setup.rr}</Text>
          </View>
        )}
      </View>

      {/* Late penalty */}
      {setup.latePenalty ? (
        <Text style={[s.penaltyTxt, { color: colors.sell }]}>{setup.latePenalty}</Text>
      ) : null}
    </TouchableOpacity>
  );
}


/* ═══════════════════════════════════════
   HERO CARD — Collapsible
   ═══════════════════════════════════════ */
function HeroCard({ card, colors, s, expanded, onToggle }: {
  card: Card; colors: any; s: any; expanded: boolean; onToggle: (id: string) => void;
}) {
  const arch = ARCH_CFG[card.archetype] || ARCH_CFG.EARLY;
  const ac = (colors as any)[arch.ck] || colors.accent;
  // COLOR RULE: LONG = green, SHORT = red. Always.
  const ts = card.tradeSetup;
  const isLong = ts ? ts.direction === 'LONG' : card.edge > 0;
  const ec = isLong ? colors.buy : colors.sell;

  return (
    <TouchableOpacity
      activeOpacity={0.85}
      onPress={() => onToggle(card.id)}
      style={[s.heroCard, { borderColor: ec + '40', backgroundColor: colors.surface }]}
    >
      {/* ── ALWAYS VISIBLE (collapsed summary) ── */}
      {/* Top row: archetype + expand icon */}
      <View style={s.collapseTopRow}>
        <View style={[s.archBdg, { backgroundColor: ac + '15', marginBottom: 0 }]}>
          <Ionicons name={arch.icon as any} size={10} color={ac} />
          <Text style={[s.archTxt, { color: ac }]}>{arch.label}</Text>
          {card.microDynamic ? (
            <View style={s.dynInline}>
              <View style={[s.dynDot, { backgroundColor: ec }]} />
              <Text style={[s.dynTxt, { color: ec }]}>{card.microDynamic}</Text>
            </View>
          ) : null}
        </View>
        <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textMuted} />
      </View>

      {/* Headline — always visible */}
      <Text style={[s.heroHL, { color: colors.textPrimary, marginBottom: expanded ? 14 : 8 }]}>
        {card.headline}
      </Text>

      {/* Compact trade line — always visible */}
      {ts && ts.entryRaw > 0 && (
        <View style={[s.compactTrade, { borderColor: ec + '20' }]}>
          <View style={s.compactTradeLeft}>
            <View style={[s.compactDir, { backgroundColor: ec + '18' }]}>
              <Ionicons name={ts.direction === 'LONG' ? 'trending-up' : 'trending-down'} size={11} color={ec} />
              <CoinIcon symbol={ts.asset} size={13} />
              <Text style={[s.compactDirTxt, { color: ec }]}>{ts.asset} {ts.direction}</Text>
            </View>
            {ts.tf && (
              <View style={[s.tfBadgeSm, { backgroundColor: colors.surfaceHover }]}>
                <Text style={[s.tfTxtSm, { color: colors.textMuted }]}>{ts.tf}</Text>
              </View>
            )}
          </View>
          <Text style={[s.compactEntry, { color: colors.textSecondary }]}>{ts.entry}</Text>
          <Text style={[s.compactMove, { color: ec }]}>{ts.expectedMove}</Text>
        </View>
      )}

      {/* Conviction — always visible as one-liner */}
      {!expanded && (
        <Text style={[s.compactConviction, { color: colors.textMuted }]} numberOfLines={1}>
          {card.conviction}
        </Text>
      )}

      {/* ── EXPANDED CONTENT ── */}
      {expanded && (
        <>
          {/* Crowd */}
          <View style={[s.crowdBox, { backgroundColor: colors.surfaceHover }]}>
            <Text style={[s.crowdLbl, { color: colors.textMuted }]}>{t('feed.theCrowd')}</Text>
            <Text style={[s.crowdVal, { color: colors.textSecondary }]}>{card.crowd}</Text>
          </View>

          {/* Reality */}
          <View style={s.punchBlk}>
            {(card.reality || []).map((r, i) => (
              <View key={i} style={s.pRow}>
                <Text style={[s.pArr, { color: ec }]}>→</Text>
                <Text style={[s.pTxt, { color: colors.textSecondary }]}>{r}</Text>
              </View>
            ))}
          </View>

          {/* Full Trade Setup */}
          {ts && ts.entryRaw > 0 && (
            <TradeBlock setup={ts} colors={colors} s={s} />
          )}

          {/* Conviction */}
          <Text style={[s.convTxt, { color: colors.textPrimary }]}>{card.conviction}</Text>

          {/* Urgency */}
          {card.urgency ? (
            <View style={[s.urgLine, { backgroundColor: ec + '10' }]}>
              <Ionicons name="time-outline" size={11} color={ec} />
              <Text style={[s.urgTxt, { color: ec }]}>{card.urgency}</Text>
            </View>
          ) : null}

          {/* Danger */}
          <Text style={[s.dangerTxt, { color: colors.sell }]}>{card.danger}</Text>

          {/* Identity */}
          <Text style={[s.idTxt, { color: colors.accent }]}>{card.identity}</Text>

          {/* Footer */}
          <View style={s.heroFoot}>
            <Text style={[s.verdictTxt, { color: ec }]}>{card.edgeVerdict}</Text>
            <View style={[s.ctaBtn, { backgroundColor: ec + '18' }]}>
              <Text style={[s.ctaBtnTxt, { color: ec }]}>{card.cta}</Text>
              <Ionicons name="arrow-forward" size={12} color={ec} />
            </View>
          </View>

          <Text style={[s.truthTxt, { color: colors.textMuted }]}>{card.truth}</Text>
        </>
      )}
    </TouchableOpacity>
  );
}


/* ═══════════════════════════════════════
   BLIND CARD — Collapsible
   ═══════════════════════════════════════ */
function BlindCard({ card, colors, s, expanded, onToggle }: {
  card: Card; colors: any; s: any; expanded: boolean; onToggle: (id: string) => void;
}) {
  const wc = colors.wait;
  const ts = card.tradeSetup;

  return (
    <TouchableOpacity
      activeOpacity={0.85}
      onPress={() => onToggle(card.id)}
      style={[s.blindCard, { borderColor: wc + '30', backgroundColor: colors.surface }]}
    >
      {/* Always visible */}
      <View style={s.collapseTopRow}>
        <View style={[s.archBdg, { backgroundColor: wc + '15', marginBottom: 0 }]}>
          <Ionicons name="eye-off" size={10} color={wc} />
          <Text style={[s.archTxt, { color: wc }]}>{t('feed.blindSpot')}</Text>
          {card.microDynamic ? (
            <View style={s.dynInline}>
              <View style={[s.dynDot, { backgroundColor: wc }]} />
              <Text style={[s.dynTxt, { color: wc }]}>{card.microDynamic}</Text>
            </View>
          ) : null}
        </View>
        <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textMuted} />
      </View>

      <Text style={[s.blindHL, { color: colors.textPrimary }]}>{card.headline}</Text>

      {/* Compact trade line */}
      {ts && ts.entryRaw > 0 && (
        <View style={[s.compactTrade, { borderColor: wc + '20' }]}>
          <View style={[s.compactDir, { backgroundColor: wc + '18' }]}>
            <Ionicons name={ts.direction === 'LONG' ? 'trending-up' : 'trending-down'} size={11} color={wc} />
            <CoinIcon symbol={ts.asset} size={13} />
            <Text style={[s.compactDirTxt, { color: wc }]}>{ts.asset} {ts.direction}</Text>
          </View>
          <Text style={[s.compactEntry, { color: colors.textSecondary }]}>{ts.entry}</Text>
          <Text style={[s.compactMove, { color: wc }]}>{ts.expectedMove}</Text>
        </View>
      )}

      {!expanded && (
        <Text style={[s.compactConviction, { color: colors.textMuted }]} numberOfLines={1}>
          {card.conviction}
        </Text>
      )}

      {/* Expanded */}
      {expanded && (
        <>
          <Text style={[s.blindCrd, { color: colors.textMuted }]}>{card.crowd}</Text>

          {(card.reality || []).map((r, i) => (
            <View key={i} style={s.pRow}>
              <Text style={[s.pArr, { color: wc }]}>→</Text>
              <Text style={[s.pTxt, { color: colors.textSecondary }]}>{r}</Text>
            </View>
          ))}

          {ts && ts.entryRaw > 0 && (
            <TradeBlock setup={ts} colors={colors} s={s} />
          )}

          <Text style={[s.blindConv, { color: colors.textPrimary }]}>{card.conviction}</Text>
          <Text style={[s.dangerTxt, { color: colors.sell }]}>{card.danger}</Text>
          <Text style={[s.idTxt, { color: colors.accent }]}>{card.identity}</Text>

          <View style={[s.blindCta, { backgroundColor: wc + '15' }]}>
            <Text style={[s.blindCtaTxt, { color: wc }]}>{card.cta}</Text>
            <Ionicons name="arrow-forward" size={11} color={wc} />
          </View>

          <Text style={[s.truthTxt, { color: colors.textMuted }]}>{card.truth}</Text>
        </>
      )}
    </TouchableOpacity>
  );
}


/* ═══════════════════════════════════════
   EDGE CARD
   ═══════════════════════════════════════ */
function EdgeCard({ card, colors, s }: { card: Card; colors: any; s: any }) {
  const arch = ARCH_CFG[card.archetype] || ARCH_CFG.EARLY;
  const ac = (colors as any)[arch.ck] || colors.accent;
  const ts = card.tradeSetup;
  // COLOR RULE: LONG = green, SHORT = red. Always.
  const isLong = ts ? ts.direction === 'LONG' : card.edge > 0;
  const ec = isLong ? colors.buy : colors.sell;

  return (
    <View style={[s.edgeCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
      <View style={s.edgeTop}>
        <View style={[s.archMini, { backgroundColor: ac + '12' }]}>
          <Text style={[s.archMiniTxt, { color: ac }]}>{arch.label}</Text>
        </View>
        {card.microDynamic ? (
          <View style={s.dynInline}>
            <View style={[s.dynDot, { backgroundColor: ec }]} />
            <Text style={[s.dynTxtSm, { color: ec }]}>{card.microDynamic}</Text>
          </View>
        ) : null}
      </View>

      <Text style={[s.edgeHL, { color: colors.textPrimary }]}>{card.headline}</Text>

      {(card.reality || []).slice(0, 2).map((r, i) => (
        <Text key={i} style={[s.edgePunch, { color: ec }]} numberOfLines={1}>→ {r}</Text>
      ))}

      {/* Compact trade info */}
      {ts && ts.entryRaw > 0 && (
        <View style={[s.edgeTrade, { borderColor: ec + '20' }]}>
          <CoinIcon symbol={ts.asset} size={14} />
          <Text style={[s.edgeTDir, { color: ec }]}>{ts.asset} {ts.direction}</Text>
          <Text style={[s.edgeTEntry, { color: colors.textSecondary }]}>Entry: {ts.entry}</Text>
          <Text style={[s.edgeTMove, { color: ec }]}>{ts.expectedMove}</Text>
        </View>
      )}

      <Text style={[s.edgeDanger, { color: colors.sell + 'CC' }]} numberOfLines={1}>{card.danger}</Text>

      <View style={s.edgeFoot}>
        <Text style={[s.edgeVerdict, { color: ec }]}>{card.edgeVerdict}</Text>
        <Text style={[s.edgeCtaTxt, { color: ec }]}>{card.cta} →</Text>
      </View>
    </View>
  );
}


/* ═══════════════════════════════════════
   PORTFOLIO BLOCK — The money decision
   ═══════════════════════════════════════ */
function PortfolioBlock({ portfolio, isPro, colors, s }: {
  portfolio: any; isPro: boolean; colors: any; s: any;
}) {
  const positions = portfolio.positions || [];
  const metrics = portfolio.metrics || {};
  const setPendingPortfolio = usePortfolioStore((st) => st.setPendingPortfolio);

  const onExecute = useCallback(() => {
    // Open Portfolio Intelligence Screen (analytical, NOT execution)
    setPendingPortfolio(positions, { metrics: portfolio.metrics, risk: portfolio.risk });
  }, [positions, setPendingPortfolio, portfolio]);

  return (
    <View style={[s.pfCard, { backgroundColor: colors.surface, borderColor: colors.accent + '30' }]}>
      <View style={s.pfHeader}>
        <Ionicons name="briefcase" size={14} color={colors.accent} />
        <Text style={[s.pfTitle, { color: colors.accent }]}>{t('feed.portfolioSetup')}</Text>
        <Text style={[s.pfCount, { color: colors.textMuted }]}>
          {portfolio.count} positions
        </Text>
      </View>

      {/* Positions */}
      {positions.map((p: any, i: number) => {
        const isLong = p.direction === 'LONG';
        const pc = isLong ? colors.buy : colors.sell;
        const locked = p.locked;

        return (
          <View key={i} style={[s.pfPos, { borderColor: colors.border }]}>
            <View style={s.pfPosLeft}>
              <CoinIcon symbol={p.asset} size={20} />
              <Text style={[s.pfAsset, { color: colors.textPrimary }]}>{p.asset}</Text>
              <Text style={[s.pfDir, { color: pc }]}>{p.direction}</Text>
            </View>
            <View style={s.pfPosRight}>
              {locked ? (
                <Text style={[s.pfLocked, { color: colors.textMuted }]}>🔒</Text>
              ) : (
                <>
                  <Text style={[s.pfEntry, { color: colors.textSecondary }]}>{p.entry}</Text>
                  <Text style={[s.pfAlloc, { color: colors.textPrimary }]}>{p.allocationPct}</Text>
                </>
              )}
            </View>
          </View>
        );
      })}

      {/* Hidden positions (FREE) */}
      {portfolio.hiddenCount > 0 && (
        <TouchableOpacity style={[s.pfHidden, { backgroundColor: colors.accent + '08' }]}>
          <Ionicons name="lock-closed" size={12} color={colors.accent} />
          <Text style={[s.pfHiddenTxt, { color: colors.accent }]}>
            +{portfolio.hiddenCount} positions hidden · Unlock full portfolio
          </Text>
          <Ionicons name="arrow-forward" size={12} color={colors.accent} />
        </TouchableOpacity>
      )}

      {/* Metrics */}
      <View style={[s.pfMetrics, { borderColor: colors.border }]}>
        <View style={s.pfMetric}>
          <Text style={[s.pfMetLbl, { color: colors.textMuted }]}>Expected</Text>
          <Text style={[s.pfMetVal, {
            color: (metrics.expectedMoveRaw || 0) >= 0 ? colors.buy : colors.sell,
          }]}>{metrics.expectedMove}</Text>
        </View>
        <View style={s.pfMetric}>
          <Text style={[s.pfMetLbl, { color: colors.textMuted }]}>Risk</Text>
          <Text style={[s.pfMetVal, { color: colors.textPrimary }]}>{metrics.riskLevel}</Text>
        </View>
        <View style={s.pfMetric}>
          <Text style={[s.pfMetLbl, { color: colors.textMuted }]}>Worst</Text>
          <Text style={[s.pfMetVal, { color: colors.sell }]}>{metrics.worstCase}</Text>
        </View>
      </View>

      {/* Identity */}
      <Text style={[s.pfIdentity, { color: colors.textMuted }]}>
        Most users trade 1 asset. You're trading the portfolio.
      </Text>

      {/* CTA */}
      <TouchableOpacity style={[s.pfCta, { backgroundColor: colors.accent }]} onPress={onExecute}>
        <Ionicons name="eye" size={13} color="#fff" />
        <Text style={s.pfCtaTxt}>{t('feed.viewStrategy')}</Text>
        <Ionicons name="arrow-forward" size={13} color="#fff" />
      </TouchableOpacity>
    </View>
  );
}


/* ═══════════════════════════════════════
   IMPACT BAR
   ═══════════════════════════════════════ */
function ImpactBar({ impact, asset, colors, s }: any) {
  const total = impact.supports + impact.weakens;
  const pct = total > 0 ? (impact.supports / total) * 100 : 50;
  return (
    <View style={[s.impCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
      <Text style={[s.impTitle, { color: colors.textMuted }]}>IMPACT ON {asset}</Text>
      <View style={s.impBarW}>
        <View style={[s.impBarBg, { backgroundColor: colors.border }]}>
          <View style={[s.impBarFill, { width: `${pct}%`, backgroundColor: colors.buy }]} />
        </View>
      </View>
      <View style={s.impRow}>
        <Text style={[s.impLbl, { color: colors.buy }]}>{impact.supports} support BUY</Text>
        <Text style={[s.impLbl, { color: colors.sell }]}>{impact.weakens} weaken BUY</Text>
      </View>
    </View>
  );
}


/* ═══════════ STYLES ═══════════ */
const mk = (c: any) => StyleSheet.create({
  root: { flex: 1, backgroundColor: c.background },
  content: { paddingHorizontal: 20, paddingTop: 4, paddingBottom: 40 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: c.background, gap: 12 },
  loadText: { fontSize: 13, fontStyle: 'italic' },

  idBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 8, borderRadius: 8, marginBottom: 12 },
  mainSignalStrip: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    borderWidth: 1, borderRadius: 12,
    paddingHorizontal: 12, paddingVertical: 10,
    marginBottom: 12,
  },
  mainSignalDot: { width: 6, height: 6, borderRadius: 3 },
  mainSignalLabel: { fontSize: 10.5, fontWeight: '800', letterSpacing: 0.6 },
  mainSignalTitle: { fontSize: 12.5, fontWeight: '600', flex: 1, flexShrink: 1 },
  mainSignalCta: { fontSize: 12.5, fontWeight: '700' },
  idBarTxt: { fontSize: 11, fontWeight: '600' },

  hdr: { marginBottom: 20 },
  hdrTitle: { fontSize: 20, fontWeight: '800', letterSpacing: -0.3 },
  hdrSub: { fontSize: 13, marginTop: 3 },

  sec: { marginBottom: 24 },
  secH: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 12 },
  secHTxt: { fontSize: 10, fontWeight: '800', letterSpacing: 2 },

  archBdg: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 6, alignSelf: 'flex-start', marginBottom: 10 },
  archTxt: { fontSize: 9, fontWeight: '800', letterSpacing: 1.2 },
  archMini: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4 },
  archMiniTxt: { fontSize: 8, fontWeight: '800', letterSpacing: 1 },

  dynInline: { flexDirection: 'row', alignItems: 'center', gap: 4, marginLeft: 8 },
  dynDot: { width: 5, height: 5, borderRadius: 3 },
  dynTxt: { fontSize: 10, fontWeight: '600', fontStyle: 'italic' },
  dynTxtSm: { fontSize: 9, fontWeight: '600', fontStyle: 'italic' },

  /* Hero */
  heroCard: { borderRadius: 16, borderWidth: 1.5, marginBottom: 12, padding: 18, gap: 0 },
  heroHL: { fontSize: 20, fontWeight: '800', lineHeight: 27, letterSpacing: -0.3, marginBottom: 14 },

  /* Collapse controls */
  collapseTopRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },

  /* Compact trade line (collapsed) */
  compactTrade: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderWidth: 1, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 7, marginBottom: 6 },
  compactTradeLeft: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  compactDir: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 5 },
  compactDirTxt: { fontSize: 11, fontWeight: '800' },
  compactEntry: { fontSize: 11 },
  compactMove: { fontSize: 14, fontWeight: '800' },
  compactConviction: { fontSize: 12, marginTop: 2 },
  tfBadgeSm: { paddingHorizontal: 5, paddingVertical: 2, borderRadius: 3 },
  tfTxtSm: { fontSize: 9, fontWeight: '700', letterSpacing: 0.3 },

  crowdBox: { borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10, marginBottom: 14 },
  crowdLbl: { fontSize: 9, fontWeight: '700', letterSpacing: 1.5, marginBottom: 3 },
  crowdVal: { fontSize: 14, fontStyle: 'italic', lineHeight: 19 },

  punchBlk: { marginBottom: 12, gap: 6 },
  pRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  pArr: { fontSize: 13, fontWeight: '700', marginTop: 1 },
  pTxt: { fontSize: 13, lineHeight: 18, flex: 1 },

  /* 💰 Trade Setup Block */
  tradeBlock: { borderRadius: 12, borderWidth: 1, padding: 14, marginBottom: 12 },
  tradeHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  tradeHeadLeft: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  dirBadge: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 6 },
  dirTxt: { fontSize: 12, fontWeight: '800' },
  tfBadge: { paddingHorizontal: 7, paddingVertical: 3, borderRadius: 4 },
  tfTxt: { fontSize: 10, fontWeight: '700', letterSpacing: 0.5 },
  moveTxt: { fontSize: 18, fontWeight: '800' },
  tradeGrid: { flexDirection: 'row', gap: 0 },
  tradeCol: { flex: 1, alignItems: 'center' },
  tradeLbl: { fontSize: 9, fontWeight: '600', letterSpacing: 0.5, marginBottom: 2 },
  tradeVal: { fontSize: 13, fontWeight: '700' },
  penaltyTxt: { fontSize: 11, fontWeight: '600', marginTop: 8, fontStyle: 'italic' },

  convTxt: { fontSize: 15, fontWeight: '700', lineHeight: 21, marginBottom: 8 },
  urgLine: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, marginBottom: 8 },
  urgTxt: { fontSize: 12, fontWeight: '600', flex: 1 },
  dangerTxt: { fontSize: 12, fontWeight: '600', marginBottom: 4 },
  idTxt: { fontSize: 12, fontWeight: '600', fontStyle: 'italic', marginBottom: 8 },

  heroFoot: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  verdictTxt: { fontSize: 12, fontWeight: '700', flex: 1 },
  ctaBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 10 },
  ctaBtnTxt: { fontSize: 12, fontWeight: '700' },
  truthTxt: { fontSize: 11, fontStyle: 'italic', lineHeight: 16 },

  /* Blind */
  blindCard: { borderRadius: 14, borderWidth: 1, padding: 16, marginBottom: 10, gap: 8 },
  blindHL: { fontSize: 17, fontWeight: '700', lineHeight: 23 },
  blindCrd: { fontSize: 13, fontStyle: 'italic' },
  blindConv: { fontSize: 14, fontWeight: '600', lineHeight: 19 },
  blindCta: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, alignSelf: 'flex-start' },
  blindCtaTxt: { fontSize: 12, fontWeight: '700' },

  /* Edge */
  edgeCard: { borderRadius: 12, borderWidth: 1, padding: 14, marginBottom: 8, gap: 5 },
  edgeTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 },
  edgeHL: { fontSize: 15, fontWeight: '700', lineHeight: 20 },
  edgePunch: { fontSize: 12, fontWeight: '500', lineHeight: 17 },
  edgeTrade: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderWidth: 1, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6, marginTop: 4 },
  edgeTDir: { fontSize: 11, fontWeight: '800' },
  edgeTEntry: { fontSize: 11 },
  edgeTMove: { fontSize: 13, fontWeight: '800' },
  edgeDanger: { fontSize: 11, fontWeight: '600', marginTop: 2 },
  edgeFoot: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 4 },
  edgeVerdict: { fontSize: 11, fontWeight: '700' },
  edgeCtaTxt: { fontSize: 11, fontWeight: '700' },

  /* Impact */
  impCard: { borderRadius: 14, borderWidth: 1, padding: 16, marginBottom: 24 },
  impTitle: { fontSize: 10, fontWeight: '800', letterSpacing: 1.5, marginBottom: 10 },
  impBarW: { marginBottom: 8 },
  impBarBg: { height: 5, borderRadius: 3, overflow: 'hidden' },
  impBarFill: { height: '100%', borderRadius: 3 },
  impRow: { flexDirection: 'row', justifyContent: 'space-between' },
  impLbl: { fontSize: 12, fontWeight: '600' },

  devTxt: { fontSize: 10, fontWeight: '800', letterSpacing: 1.5 },
  altSubhead: { fontSize: 12, fontStyle: 'italic', marginTop: -6, marginBottom: 10 },

  /* Rotation */
  rotCard: { borderRadius: 14, borderWidth: 1, padding: 16, marginBottom: 24 },
  rotTitle: { fontSize: 10, fontWeight: '800', letterSpacing: 1.5, marginBottom: 10 },
  rotLine: { fontSize: 13, fontWeight: '500', lineHeight: 20 },
  rotVerdict: { fontSize: 13, fontWeight: '700', marginTop: 8, fontStyle: 'italic' },

  /* Portfolio */
  pfCard: { borderRadius: 16, borderWidth: 1.5, padding: 18, marginBottom: 24 },
  pfHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 14 },
  pfTitle: { fontSize: 10, fontWeight: '800', letterSpacing: 1.5, flex: 1 },
  pfCount: { fontSize: 11 },
  pfPos: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 0.5 },
  pfPosLeft: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  pfDirDot: { width: 8, height: 8, borderRadius: 4 },
  pfAsset: { fontSize: 14, fontWeight: '700' },
  pfDir: { fontSize: 12, fontWeight: '600' },
  pfPosRight: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  pfEntry: { fontSize: 12 },
  pfAlloc: { fontSize: 14, fontWeight: '800', minWidth: 36, textAlign: 'right' },
  pfLocked: { fontSize: 16 },
  pfHidden: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 10, marginTop: 10 },
  pfHiddenTxt: { fontSize: 12, fontWeight: '600', flex: 1 },
  pfMetrics: { flexDirection: 'row', justifyContent: 'space-around', paddingTop: 14, marginTop: 12, borderTopWidth: 0.5 },
  pfMetric: { alignItems: 'center' },
  pfMetLbl: { fontSize: 9, fontWeight: '600', letterSpacing: 0.5, marginBottom: 2 },
  pfMetVal: { fontSize: 15, fontWeight: '800' },
  pfIdentity: { fontSize: 11, fontStyle: 'italic', textAlign: 'center', marginTop: 12 },
  pfCta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 12, borderRadius: 10, marginTop: 12 },
  pfCtaTxt: { fontSize: 13, fontWeight: '700', color: '#fff' },

  botCta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 14, borderRadius: 12, borderWidth: 1, marginTop: 8 },
  botCtaTxt: { fontSize: 13, fontWeight: '700' },
});
