import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useColors } from '../../../core/useColors';
import { useSessionStore } from '../../../stores/session.store';
import { openPaywall } from '../../../utils/paywall-controller';
import { useAppMode } from '../../../stores/app-mode.store';
import { CoinIcon } from '../../../components/CoinIcon';
import { useTracker, trackAction } from '../../../hooks/useTracker';
import { mobileApi } from '../../../services/api/mobile-api';
import { hapticLight } from '../../../services/haptics.service';
import GatedBlock from '../../../components/gating/GatedBlock';

import { t } from '../../../core/i18n';
/* ─── types ─── */
type Driver = {
  module: string;
  name: string;
  direction: string;
  confidence: number;
  weight: number;
  value: string;
  reason: string;
  entry?: number;
  takeProfit?: number;
  stopLoss?: number;
};

type Signal = {
  asset: string;
  action: 'BUY' | 'SELL' | 'WAIT';
  confidence: number;
  score: number;
  direction: string;
  horizon: string;
  price: number | null;
  drivers: Driver[];
  driverSummary: { bullish: number; bearish: number; neutral: number };
  summary: string;
  entryZone: string | null;
  takeProfit: string | null;
  stopLoss: string | null;
  updatedAt: string;
};

/* ─── helpers ─── */

function strengthMeta(c: number) {
  if (c >= 0.70) return { label: 'High Conviction', level: 'strong' as const, pct: Math.round(c * 100) };
  if (c >= 0.50) return { label: 'Moderate', level: 'moderate' as const, pct: Math.round(c * 100) };
  if (c >= 0.35) return { label: 'Early Setup', level: 'weak' as const, pct: Math.round(c * 100) };
  return { label: 'Forming', level: 'minimal' as const, pct: Math.round(c * 100) };
}

function setupLabel(action: string) {
  if (action === 'BUY') return 'Long Setup';
  if (action === 'SELL') return 'Short Setup';
  return 'No Active Setup';
}

function driverIcon(mod: string): keyof typeof Ionicons.glyphMap {
  const map: Record<string, keyof typeof Ionicons.glyphMap> = {
    exchange: 'swap-horizontal',
    sentiment: 'heart-circle',
    fractal: 'git-branch',
    onchain: 'link',
    metabrain: 'hardware-chip',
    prediction: 'analytics',
    social: 'chatbubbles',
    technical: 'bar-chart',
  };
  return map[mod] || 'ellipse';
}

/* ═══════════════════════════════════════════════════
   SIGNAL DETAIL SCREEN — Final Product Version
   ═══════════════════════════════════════════════════ */

export function SignalDetailScreen({
  signal,
  onClose,
}: {
  signal: Signal;
  onClose: () => void;
}) {
  const colors = useColors();
  const insets = useSafeAreaInsets();
  const s = React.useMemo(() => makeStyles(colors), [colors]);
  const user = useSessionStore((st) => st.user);
  const isPro = user?.plan === 'PRO' || user?.plan === 'INSTITUTIONAL';
  const isExpired = user?.planStatus === 'EXPIRED';

  const ac = signal.action === 'BUY' ? colors.buy
    : signal.action === 'SELL' ? colors.sell
    : colors.textMuted;

  const dirColor = (dir: string) =>
    dir === 'Bullish' ? colors.buy : dir === 'Bearish' ? colors.sell : colors.textMuted;

  const strength = strengthMeta(signal.confidence);
  const strengthColor = strength.level === 'strong' ? colors.buy
    : strength.level === 'moderate' ? '#FFCC00'
    : strength.level === 'weak' ? '#FF8C00'
    : colors.textMuted;

  const hasSetup = signal.action !== 'WAIT' && signal.entryZone;
  const bullCount = signal.driverSummary.bullish;
  const bearCount = signal.driverSummary.bearish;
  const neutralCount = signal.driverSummary.neutral;
  const totalDrivers = signal.drivers.length;
  const { setIntelTab } = useAppMode();

  // ═══ DECISION FRAMEWORK from backend ═══
  const df = (signal as any).decisionFramework || {};
  const conflictData = (signal as any).conflict || {};
  const backendStage = df.stage || 'EARLY';
  const stageLabel = df.stageLabel || 'Scanning for alignment';
  const alignedCount = df.alignedCount || Math.max(bullCount, bearCount);
  const alignmentText = df.alignment || `${alignedCount} of ${totalDrivers} aligned`;
  const timingLabel = df.timingLabel || '';
  const mattersPoints: string[] = df.mattersPoints || [];

  // Stage (from backend decision framework, not confidence)
  const stage = backendStage === 'SIGNAL' ? 'SIGNAL'
    : backendStage === 'CONFIRMING' ? 'CONFIRMING'
    : backendStage === 'FORMING' ? 'FORMING'
    : 'EARLY';
  const stageColor = stage === 'SIGNAL' ? colors.buy
    : stage === 'CONFIRMING' ? '#FFCC00'
    : stage === 'FORMING' ? '#FF8C00'
    : colors.textMuted;
  const stageSubtitle = stageLabel;

  // Alignment-based description (not percentage)
  const strengthDesc = `${alignmentText}. ${timingLabel}`;

  // Action guidance based on stage
  const actionTitle = stage === 'SIGNAL' ? 'Positioning window open'
    : stage === 'CONFIRMING' ? 'Early positioning possible'
    : stage === 'FORMING' ? 'Setup forming — watch closely'
    : 'Scanning — no position yet';
  const actionDesc = stage === 'SIGNAL' ? `${alignedCount} modules confirm. Best risk/reward window.`
    : stage === 'CONFIRMING' ? 'Before full confirmation = best entries. Small size.'
    : stage === 'FORMING' ? 'Structure building. Not confirmed yet.'
    : 'Watching for module convergence.';

  // Conflict
  const hasConflict = conflictData.hasConflict || false;
  const conflictSummary = conflictData.summary || '';

  // Behavior tracking
  useTracker('SIGNAL_DETAIL', { symbol: signal.asset });

  // Track signal_detail_open event with full metadata
  useEffect(() => {
    trackAction('signal_detail_open', {
      symbol: signal.asset,
      verdict: signal.action,
      confidence: signal.confidence,
      direction: signal.direction,
      stage,
      bullCount,
      bearCount,
    });
  }, [signal.asset]);

  // Portfolio position
  const [portfolioPerf, setPortfolioPerf] = useState<any>(null);
  useEffect(() => {
    mobileApi.getPortfolioPerformance().then(d => {
      if (d?.ok) setPortfolioPerf(d);
    }).catch(() => {});
  }, []);
  const position = portfolioPerf?.positions?.find(
    (p: any) => p.symbol === signal.asset && p.status === 'OPEN'
  );

  // Confirmation triggers
  const confirmTriggers = signal.drivers
    .filter(d => d.direction === 'Neutral' || d.confidence < 0.4)
    .map(d => `${d.name} confirmation`)
    .slice(0, 3);
  if (confirmTriggers.length === 0) {
    confirmTriggers.push('Momentum expansion', 'Volume confirmation', 'Price reclaim level');
  }

  return (
    <View style={[s.overlay, { paddingTop: insets.top }]}>

      {/* ─── TOP BAR ─── */}
      <View style={s.topBar}>
        <TouchableOpacity
          testID="signal-detail-back"
          style={s.backBtn}
          onPress={onClose}
          hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
        >
          <Ionicons name="chevron-back" size={20} color={colors.textSecondary} />
        </TouchableOpacity>
        <Text style={[s.topBarTitle, { color: colors.textSecondary }]}>
          {signal.asset} Signal
        </Text>
        <View style={{ width: 36 }} />
      </View>

      <ScrollView
        testID="signal-detail-scroll"
        showsVerticalScrollIndicator={false}
        contentContainerStyle={s.scrollContent}
      >

        {/* ═══════════ 1. STAGE-BASED HERO ═══════════ */}
        <View style={s.verdictSection}>
          {/* Asset icon + name */}
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <CoinIcon symbol={signal.asset} size={28} />
            <Text style={[s.verdictAction, { color: colors.textPrimary, fontSize: 28 }]}>{signal.asset}</Text>
          </View>

          {/* Stage state badge (FORMING / CONFIRMED / BREAKING DOWN) */}
          <View style={{ marginBottom: 10 }}>
            <SignalStateBadge
              stage={stage}
              action={signal.action}
              direction={signal.direction}
              isActive={signal.action !== 'WAIT'}
            />
          </View>

          <Text style={[s.verdictSubtitle, { color: colors.textMuted }]}>
            {stageSubtitle}
          </Text>

          {/* Signal strength description */}
          <View style={[{ backgroundColor: colors.surface, borderRadius: 10, padding: 10, width: '100%', marginTop: 8 }]}>
            <Text style={[{ fontSize: 12, color: strengthColor, fontWeight: '700', textAlign: 'center' }]}>
              Signal strength: {strength.label.toUpperCase()}
            </Text>
            <Text style={[{ fontSize: 12, color: colors.textMuted, textAlign: 'center', marginTop: 2 }]}>
              {strengthDesc}
            </Text>
          </View>

          {/* Alignment chips */}
          <View style={s.alignRow}>
            {bullCount > 0 && (
              <View style={[s.alignChip, { backgroundColor: colors.buy + '18' }]}>
                <Ionicons name="arrow-up" size={11} color={colors.buy} />
                <Text style={[s.alignText, { color: colors.buy }]}>{bullCount} bullish</Text>
              </View>
            )}
            {bearCount > 0 && (
              <View style={[s.alignChip, { backgroundColor: colors.sell + '18' }]}>
                <Ionicons name="arrow-down" size={11} color={colors.sell} />
                <Text style={[s.alignText, { color: colors.sell }]}>{bearCount} bearish</Text>
              </View>
            )}
            {neutralCount > 0 && (
              <View style={[s.alignChip, { backgroundColor: colors.textMuted + '12' }]}>
                <Text style={[s.alignText, { color: colors.textMuted }]}>{neutralCount} waiting</Text>
              </View>
            )}
          </View>
        </View>

        {/* ═══════════ 1.5 WHAT TO DO NOW (Action Block) ═══════════ */}
        <View style={[s.card, {
          borderColor: stageColor + '30',
          backgroundColor: stageColor + '05',
        }]}>
          <Text style={[s.cardLabel, { color: stageColor }]}>{t('signalDetail.whatToDoNow')}</Text>
          <Text style={[{ fontSize: 17, fontWeight: '700', color: colors.textPrimary }]}>
            {actionTitle}
          </Text>
          <Text style={[{ fontSize: 13, color: colors.textMuted, marginTop: 4, lineHeight: 19 }]}>
            {actionDesc}
          </Text>

          {/* CTA based on stage */}
          {stage !== 'NOT READY' && (
            <TouchableOpacity
              style={[{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 12, paddingVertical: 10, paddingHorizontal: 16, borderRadius: 10, backgroundColor: stageColor + '15', alignSelf: 'flex-start' }]}
              onPress={() => {
                hapticLight();
                onClose();
                setIntelTab('TRADE' as any);
              }}
              activeOpacity={0.7}
            >
              <Ionicons name="flash" size={14} color={stageColor} />
              <Text style={[{ fontSize: 13, fontWeight: '700', color: stageColor }]}>
                {stage === 'CONFIRMED' ? 'Enter Position' : 'Position Early'}
              </Text>
            </TouchableOpacity>
          )}
        </View>

        {/* ═══════════ 1.6 ALREADY POSITIONED ═══════════ */}
        {position && (
          <View style={[s.card, {
            borderColor: ((position.pnlPct || 0) >= 0 ? colors.buy : colors.sell) + '30',
            backgroundColor: ((position.pnlPct || 0) >= 0 ? colors.buy : colors.sell) + '05',
          }]}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Ionicons name="checkmark-circle" size={18} color={(position.pnlPct || 0) >= 0 ? colors.buy : colors.sell} />
              <Text style={[{ fontSize: 14, fontWeight: '700', color: colors.textPrimary }]}>{t('signalDetail.youAreAlreadyPositioned')}</Text>
            </View>
            <Text style={[{ fontSize: 12, color: colors.textMuted, marginTop: 4 }]}>
              {stage === 'CONFIRMED' ? 'Entered before confirmation' : 'Positioned before the crowd'}
            </Text>
            <Text style={[{ fontSize: 18, fontWeight: '800', color: (position.pnlPct || 0) >= 0 ? colors.buy : colors.sell, marginTop: 4 }]}>
              PnL: {(position.pnlPct || 0) >= 0 ? '+' : ''}{(position.pnlPct || 0).toFixed(1)}%
            </Text>
          </View>
        )}

        {/* ═══════════ 2. WHAT MATTERS NOW ═══════════ */}
        {mattersPoints.length > 0 && (
          <View style={[s.card, { borderColor: colors.accent + '25', backgroundColor: colors.accent + '06' }]}>
            <View style={s.cardHeader}>
              <Ionicons name="eye" size={14} color={colors.accent} />
              <Text style={[s.cardLabel, { color: colors.accent }]}>{t('signalDetail.whatMattersNow')}</Text>
            </View>
            {mattersPoints.slice(0, 4).map((point: string, i: number) => (
              <View key={i} style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8, marginTop: i === 0 ? 4 : 6 }}>
                <Text style={{ fontSize: 11, color: colors.textMuted, marginTop: 1 }}>•</Text>
                <Text style={{ fontSize: 14, color: colors.textPrimary, lineHeight: 20, flex: 1 }}>{point}</Text>
              </View>
            ))}
          </View>
        )}

        {/* ═══════════ 2.1 CONFLICT ENGINE ═══════════ */}
        {hasConflict && conflictSummary ? (
          <View style={[s.card, { borderColor: '#FF8C00' + '30', backgroundColor: '#FF8C00' + '08' }]}>
            <View style={s.cardHeader}>
              <Ionicons name="flash" size={14} color="#FF8C00" />
              <Text style={[s.cardLabel, { color: '#FF8C00' }]}>{t('signalDetail.marketConflict')}</Text>
            </View>
            <Text style={{ fontSize: 14, color: colors.textPrimary, lineHeight: 20, marginTop: 4 }}>
              {conflictSummary}
            </Text>
            <Text style={{ fontSize: 12, color: colors.textMuted, marginTop: 6, fontStyle: 'italic' }}>
              Conflict between modules often signals opportunity — this is where reversals start.
            </Text>
          </View>
        ) : null}

        {/* ═══════════ 2.2 KEY INSIGHT ═══════════ */}
        <View style={[s.card, { borderColor: colors.border, backgroundColor: colors.surface }]}>
          <View style={s.cardHeader}>
            <Ionicons name="bulb" size={14} color={colors.accent} />
            <Text style={[s.cardLabel, { color: colors.accent }]}>{t('signalDetail.keyInsight')}</Text>
          </View>
          <Text style={[s.summaryBody, { color: colors.textSecondary }]}>
            {signal.summary}
          </Text>
        </View>

        {/* ═══════════ 2.25 EARLY PAYWALL (A/B Test #2) ═══════════ */}
        {!isPro && (() => {
          const ep = (signal as any).partialReveal?.earlyPaywall;
          if (!ep) return null;
          return (
            <View style={[s.card, { borderColor: colors.accent + '30', backgroundColor: colors.accent + '06', borderWidth: 1 }]}>
              <Text style={{ fontSize: 15, fontWeight: '800', color: colors.textPrimary, marginBottom: 4 }}>{ep.headline}</Text>
              {ep.subline ? <Text style={{ fontSize: 13, color: colors.textSecondary, marginBottom: 10 }}>{ep.subline}</Text> : null}
              <Text style={{ fontSize: 12, color: colors.textMuted, marginBottom: 12, fontStyle: 'italic' }}>{ep.sub}</Text>
              <TouchableOpacity
                style={{ backgroundColor: colors.accent, paddingVertical: 12, borderRadius: 10, alignItems: 'center' }}
                onPress={() => {
                  // Track funnel event
                  try { mobileApi.trackBehavior('cta_click', { signalId: signal.asset, source: 'earlyPaywall' }); } catch {}
                  setShowPaywall?.(true);
                }}
                activeOpacity={0.8}
              >
                <Text style={{ fontSize: 14, fontWeight: '700', color: '#FFFFFF' }}>{ep.cta}</Text>
              </TouchableOpacity>
            </View>
          );
        })()}

        {/* ═══════════ 2.3 ENTRY WINDOW ═══════════ */}
        {(() => {
          const ew = (signal as any).entryWindow || {};
          const ewState = ew.state || 'SCANNING';
          const ewColor = ewState === 'ACTIVE' ? colors.buy
            : ewState === 'OPEN' ? colors.buy
            : ewState === 'CLOSING' ? '#FF8C00'
            : ewState === 'CLOSED' ? colors.sell
            : colors.textMuted;
          return ewState !== 'SCANNING' ? (
            <View style={[s.card, { borderColor: ewColor + '30', backgroundColor: ewColor + '08' }]}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                  <Ionicons name={ewState === 'CLOSED' ? 'close-circle' : 'time'} size={14} color={ewColor} />
                  <Text style={{ fontSize: 13, fontWeight: '800', color: ewColor, letterSpacing: 0.5 }}>{ew.label}</Text>
                </View>
                <Text style={{ fontSize: 11, color: colors.textMuted }}>{ew.urgency}</Text>
              </View>
              {ew.moneyFrame && (
                <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 6 }}>{ew.moneyFrame}</Text>
              )}
              {ew.topTraders && (
                <Text style={{ fontSize: 11, color: colors.accent, marginTop: 4, fontStyle: 'italic' }}>{ew.topTraders}</Text>
              )}
            </View>
          ) : null;
        })()}

        {/* ═══════════ 3. TRADE SETUP ═══════════ */}
        <View style={[s.card, { borderColor: colors.border, backgroundColor: colors.surface }]}>
          <Text style={[s.cardLabel, { color: colors.textMuted }]}>{t('signalDetail.tradeSetup')}</Text>

          {signal.action === 'WAIT' ? (
            <View style={s.noSetupWrap}>
              <Ionicons name="pulse-outline" size={22} color={colors.accent} />
              <Text style={[s.noSetupText, { color: colors.textSecondary }]}>
                No entry yet. Market preparing move.
              </Text>
            </View>
          ) : (
            <GatedBlock blockKey="entry" surface="signal_detail">
            <View>
              {/* Entry */}
              <View style={s.setupRow}>
                <View style={s.setupLeft}>
                  <View style={[s.setupDot, { backgroundColor: ac }]} />
                  <Text style={[s.setupLabel, { color: colors.textMuted }]}>Entry</Text>
                </View>
                {isPro && hasSetup ? (
                  <Text style={[s.setupValue, { color: colors.textPrimary }]}>{signal.entryZone}</Text>
                ) : (
                  <TouchableOpacity onPress={() => openPaywall('contextual')}>
                    <View style={[s.lockedPill, { backgroundColor: colors.accent + '15' }]}>
                      <Ionicons name="lock-closed" size={11} color={colors.accent} />
                      <Text style={[s.lockedText, { color: colors.accent }]}>PRO</Text>
                    </View>
                  </TouchableOpacity>
                )}
              </View>

              <View style={[s.setupDivider, { backgroundColor: colors.border }]} />

              {/* Invalidation */}
              <View style={s.setupRow}>
                <View style={s.setupLeft}>
                  <View style={[s.setupDot, { backgroundColor: colors.sell }]} />
                  <Text style={[s.setupLabel, { color: colors.textMuted }]}>Invalidation</Text>
                </View>
                {isPro && signal.stopLoss ? (
                  <Text style={[s.setupValue, { color: colors.sell }]}>{signal.stopLoss}</Text>
                ) : isPro ? (
                  <Text style={[s.setupNA, { color: colors.textMuted }]}>—</Text>
                ) : (
                  <View style={[s.lockedPill, { backgroundColor: colors.accent + '15' }]}>
                    <Ionicons name="lock-closed" size={11} color={colors.accent} />
                    <Text style={[s.lockedText, { color: colors.accent }]}>PRO</Text>
                  </View>
                )}
              </View>

              <View style={[s.setupDivider, { backgroundColor: colors.border }]} />

              {/* Target */}
              <View style={s.setupRow}>
                <View style={s.setupLeft}>
                  <View style={[s.setupDot, { backgroundColor: colors.buy }]} />
                  <Text style={[s.setupLabel, { color: colors.textMuted }]}>Target</Text>
                </View>
                {isPro && signal.takeProfit ? (
                  <Text style={[s.setupValue, { color: colors.buy }]}>{signal.takeProfit}</Text>
                ) : isPro ? (
                  <Text style={[s.setupNA, { color: colors.textMuted }]}>—</Text>
                ) : (
                  <View style={[s.lockedPill, { backgroundColor: colors.accent + '15' }]}>
                    <Ionicons name="lock-closed" size={11} color={colors.accent} />
                    <Text style={[s.lockedText, { color: colors.accent }]}>PRO</Text>
                  </View>
                )}
              </View>
            </View>
            </GatedBlock>
          )}
        </View>

        {/* ═══════════ 4. MARKET DRIVERS ═══════════ */}
        <Text style={[s.sectionTitle, { color: colors.textMuted }]}>{t('signalDetail.marketDrivers')}</Text>

        {signal.drivers.map((d, i) => {
          const dc = dirColor(d.direction);
          const ico = driverIcon(d.module);
          const confPct = Math.round(d.confidence * 100);
          const isNeutral = d.direction === 'Neutral';

          // Meaningful neutral explanation
          const neutralExplain = isNeutral
            ? `No strong signal yet. ${d.name} not aligned.`
            : '';

          // FREE: first driver partial, rest locked
          if (!isPro && i >= 1) {
            return (
              <TouchableOpacity
                key={d.module}
                style={[s.driverCard, { backgroundColor: colors.surface, borderColor: colors.border }]}
                onPress={() => openPaywall('contextual')}
                activeOpacity={0.7}
              >
                <View style={s.driverTop}>
                  <View style={s.driverNameRow}>
                    <Ionicons name={ico} size={14} color={colors.textMuted} />
                    <Text style={[s.driverName, { color: colors.textPrimary }]}>{d.name}</Text>
                  </View>
                  <View style={[s.lockedPill, { backgroundColor: colors.accent + '15' }]}>
                    <Ionicons name="lock-closed" size={10} color={colors.accent} />
                    <Text style={[s.lockedText, { color: colors.accent }]}>PRO</Text>
                  </View>
                </View>
              </TouchableOpacity>
            );
          }

          return (
            <View key={d.module} style={[s.driverCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
              <View style={s.driverTop}>
                <View style={s.driverNameRow}>
                  <Ionicons name={ico} size={14} color={dc} />
                  <Text style={[s.driverName, { color: colors.textPrimary }]}>{d.name}</Text>
                </View>
                <View style={[s.driverBadge, { backgroundColor: dc + '18' }]}>
                  <Text style={[s.driverBadgeText, { color: dc }]}>
                    {isNeutral ? 'Waiting' : d.direction}
                  </Text>
                </View>
              </View>

              {/* Confidence bar */}
              <View style={s.driverConfRow}>
                <View style={[s.driverConfBg, { backgroundColor: colors.border }]}>
                  <View style={[s.driverConfFill, { width: `${confPct}%`, backgroundColor: dc }]} />
                </View>
                <Text style={[s.driverConfPct, { color: dc }]}>{confPct}%</Text>
              </View>

              {/* Value + Reason — neutral gets explanation */}
              {isNeutral ? (
                <Text style={[s.driverReason, { color: colors.textMuted, marginTop: 6 }]}>
                  {neutralExplain}
                </Text>
              ) : (
                <>
                  <Text style={[s.driverValue, { color: colors.textSecondary }]}>{d.value}</Text>
                  {/* Insight (money phrasing) — shown to all, PRO gets full detail */}
                  {(d as any).insight && (
                    <Text style={[s.driverReason, { color: colors.accent + 'CC', marginTop: 3, fontStyle: 'italic' }]} numberOfLines={isPro ? 3 : 2}>
                      {(d as any).insight}
                    </Text>
                  )}
                  {isPro && d.reason && (
                    <Text style={[s.driverReason, { color: colors.textMuted, marginTop: 2 }]} numberOfLines={2}>
                      {d.reason}
                    </Text>
                  )}
                </>
              )}
            </View>
          );
        })}

        {/* ═══════════ 5. WHAT CONFIRMS THIS SIGNAL ═══════════ */}
        <View style={[s.card, { borderColor: colors.border, backgroundColor: colors.surface, marginTop: 16 }]}>
          <View style={s.cardHeader}>
            <Ionicons name="checkmark-done" size={14} color={colors.accent} />
            <Text style={[s.cardLabel, { color: colors.accent, marginBottom: 0 }]}>{t('signalDetail.whatConfirmsThisSignal')}</Text>
          </View>
          {confirmTriggers.map((t, i) => (
            <View key={i} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 5 }}>
              <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: colors.accent }} />
              <Text style={{ fontSize: 13, color: colors.textSecondary }}>{t}</Text>
            </View>
          ))}
          <Text style={{ fontSize: 11, color: colors.textMuted, fontStyle: 'italic', marginTop: 8 }}>
            When these align, signal strengthens → push notification
          </Text>
        </View>

        {/* ═══════════ 5.5 STRUCTURE (PRO) ═══════════ */}
        {isPro && (
          <View style={[s.card, { borderColor: colors.border, backgroundColor: colors.surface, marginTop: 12 }]}>
            <Text style={[s.cardLabel, { color: colors.textMuted }]}>{t('signalDetail.marketStructure')}</Text>
            {signal.drivers.map((d) => (
              <View key={d.module + '_s'} style={s.structRow}>
                <Text style={[s.structModule, { color: colors.textSecondary }]}>{d.name}</Text>
                <View style={[s.structDot, { backgroundColor: dirColor(d.direction) }]} />
                <Text style={[s.structDir, { color: dirColor(d.direction) }]}>{d.direction}</Text>
                <Text style={[s.structWeight, { color: colors.textMuted }]}>{Math.round(d.weight * 100)}%</Text>
              </View>
            ))}
            <View style={[s.structDivider, { backgroundColor: colors.border }]} />
            <Text style={[s.structConclusion, { color: colors.textSecondary }]}>
              {bullCount >= 4 ? 'Strong bullish alignment' :
               bearCount >= 4 ? 'Strong bearish convergence' :
               bullCount > bearCount ? `Lean bullish — ${bullCount} modules supporting` :
               bearCount > bullCount ? `Lean bearish — ${bearCount} modules pressuring` :
               'Mixed signals — no dominant force'}
            </Text>
          </View>
        )}

        {/* ═══════════ 6. EDGE LINK ═══════════ */}
        <TouchableOpacity
          style={[s.card, { borderColor: colors.accent + '20', backgroundColor: colors.accent + '05', marginTop: 12, flexDirection: 'row', alignItems: 'center', gap: 10 }]}
          onPress={() => { onClose(); setIntelTab('EDGE'); }}
          activeOpacity={0.7}
        >
          <Ionicons name="flash" size={18} color={colors.accent} />
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 13, fontWeight: '700', color: colors.accent }}>{t('signalDetail.seeEarlyFormationInEdge')}</Text>
            <Text style={{ fontSize: 11, color: colors.textMuted, marginTop: 2 }}>
              Edge detected this before the signal formed
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.accent} />
        </TouchableOpacity>

        {/* ═══════════ 7. MICRO-FOMO ═══════════ */}
        <Text style={{ fontSize: 11, color: colors.textMuted, textAlign: 'center', fontStyle: 'italic', marginTop: 16 }}>
          {stage === 'CONFIRMED' ? 'Signal now visible. The crowd is entering.' :
           stage === 'FORMING' ? 'Signal not visible to most users yet' :
           'Most users will see this after confirmation. You are early.'}
        </Text>

        {/* ═══════════ 8. PARTIAL REVEAL + PAYWALL (FREE only) ═══════════ */}
        {!isPro && signal.partialReveal?.locked && (
          <View style={[s.paywallCard, { borderColor: colors.accent + '30', backgroundColor: colors.surface }]}>
            {/* Trade setup teaser */}
            <View style={{ marginBottom: 14 }}>
              <Text style={{ fontSize: 11, fontWeight: '700', color: colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 10 }}>
                TRADE SETUP
              </Text>

              {signal.partialReveal.direction && (
                <Text style={{ fontSize: 16, fontWeight: '800', color: colors.accent, marginBottom: 8 }}>
                  {signal.partialReveal.direction} setup forming
                </Text>
              )}

              {/* Entry teaser */}
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.border }}>
                <Text style={{ fontSize: 13, color: colors.textPrimary }}>Entry</Text>
                <Text style={{ fontSize: 13, fontWeight: '600', color: colors.accent }}>
                  {signal.partialReveal.entryTeaser || 'Zone detected'}
                </Text>
              </View>

              {/* Target teaser */}
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.border }}>
                <Text style={{ fontSize: 13, color: colors.textPrimary }}>Target</Text>
                <Text style={{ fontSize: 13, fontWeight: '600', color: colors.buy }}>
                  {signal.partialReveal.potentialRange || 'Upside detected'}
                </Text>
              </View>

              {/* Stop teaser */}
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8 }}>
                <Text style={{ fontSize: 13, color: colors.textPrimary }}>Risk</Text>
                <Text style={{ fontSize: 13, fontWeight: '600', color: colors.sell }}>
                  {signal.partialReveal.stopTeaser || 'Level defined'}
                </Text>
              </View>
            </View>

            {/* Truth line */}
            {signal.partialReveal.truthLine && (
              <View style={{ paddingVertical: 8, paddingHorizontal: 10, backgroundColor: colors.buy + '08', borderRadius: 8, borderWidth: 1, borderColor: colors.buy + '15', marginBottom: 10 }}>
                <Text style={{ fontSize: 12, fontWeight: '600', color: colors.buy }}>
                  {signal.partialReveal.truthLine}
                </Text>
              </View>
            )}

            {/* Pressure line */}
            {signal.partialReveal.pressureLine && (
              <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textPrimary, textAlign: 'center', marginBottom: 10 }}>
                {signal.partialReveal.pressureLine}
              </Text>
            )}

            {/* CTA button */}
            <TouchableOpacity
              testID="signal-detail-unlock-btn"
              style={[s.paywallBtn, { backgroundColor: colors.accent }]}
              onPress={() => openPaywall('contextual')}
              activeOpacity={0.8}
            >
              <Text style={s.paywallBtnText}>
                {signal.partialReveal.cta || t('signalDetail.unlockExactEntry')}
              </Text>
            </TouchableOpacity>

            {/* Micro-FOMO */}
            {signal.partialReveal.microFomo && (
              <Text style={{ fontSize: 10, color: colors.textMuted, textAlign: 'center', marginTop: 8, fontStyle: 'italic' }}>
                {signal.partialReveal.microFomo}
              </Text>
            )}

            {/* Timing urgency */}
            {signal.partialReveal.timing && (
              <Text style={{ fontSize: 10, fontWeight: '600', color: colors.accent, textAlign: 'center', marginTop: 4 }}>
                {signal.partialReveal.timing}
              </Text>
            )}

            {/* "Almost decided" — one step away */}
            {signal.partialReveal.almostLine && (
              <Text style={{ fontSize: 11, fontWeight: '600', color: colors.textSecondary, textAlign: 'center', marginTop: 8 }}>
                {signal.partialReveal.almostLine}
              </Text>
            )}
          </View>
        )}

        {/* PRO: show full trade setup (already in existing code above) */}
        {!isPro && !signal.partialReveal?.locked && (
          <View style={[s.paywallCard, { borderColor: colors.accent + '30', backgroundColor: colors.surface }]}>
            <View style={[s.paywallIcon, { backgroundColor: colors.accent + '15' }]}>
              <Ionicons name="flash" size={20} color={colors.accent} />
            </View>
            <Text style={[s.paywallTitle, { color: colors.textPrimary }]}>
              Entry zone identified. PRO users already positioned.
            </Text>
            <Text style={[s.paywallDesc, { color: colors.textMuted }]}>
              PRO unlocks exact entry, target, and invalidation levels.
            </Text>
            <TouchableOpacity
              style={[s.paywallBtn, { backgroundColor: colors.buy }]}
              onPress={() => openPaywall('contextual')}
              activeOpacity={0.8}
            >
              <Text style={s.paywallBtnText}>{t('signalDetail.unlockExactEntry')}</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* ═══════════ META ═══════════ */}
        <View style={[s.metaRow, { borderTopColor: colors.border }]}>
          <Text style={[s.metaText, { color: colors.textMuted }]}>
            {signal.horizon.charAt(0).toUpperCase() + signal.horizon.slice(1)} · Updated {new Date(signal.updatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </Text>
        </View>

        <View style={{ height: insets.bottom + 24 }} />
      </ScrollView>
    </View>
  );
}

/* ═══════════ STYLES ═══════════ */

const makeStyles = (colors: any) =>
  StyleSheet.create({
    overlay: {
      ...StyleSheet.absoluteFillObject,
      backgroundColor: colors.background,
      zIndex: 100,
    },

    /* Top bar */
    topBar: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingHorizontal: 16,
      paddingVertical: 10,
    },
    backBtn: {
      width: 36,
      height: 36,
      borderRadius: 18,
      backgroundColor: colors.surface,
      justifyContent: 'center',
      alignItems: 'center',
    },
    topBarTitle: {
      fontSize: 14,
      fontWeight: '600',
    },

    scrollContent: {
      paddingHorizontal: 20,
    },

    /* ─── 1. VERDICT ─── */
    verdictSection: {
      alignItems: 'center',
      paddingVertical: 16,
    },
    verdictBadge: {
      paddingHorizontal: 24,
      paddingVertical: 10,
      borderRadius: 12,
      marginBottom: 6,
    },
    verdictAction: {
      fontSize: 36,
      fontWeight: '900',
      letterSpacing: 2,
    },
    verdictSubtitle: {
      fontSize: 13,
      fontWeight: '500',
      marginBottom: 16,
    },

    /* Confidence block */
    confBlock: {
      alignItems: 'center',
      marginBottom: 12,
    },
    confRingOuter: {
      width: 72,
      height: 72,
      borderRadius: 36,
      borderWidth: 3,
      justifyContent: 'center',
      alignItems: 'center',
      marginBottom: 6,
    },
    confRingFill: {
      ...StyleSheet.absoluteFillObject,
      borderRadius: 36,
      borderWidth: 3,
    },
    confValue: {
      fontSize: 22,
      fontWeight: '800',
    },
    confLabel: {
      fontSize: 12,
      fontWeight: '700',
      textTransform: 'uppercase',
      letterSpacing: 1,
    },

    /* Alignment chips */
    alignRow: {
      flexDirection: 'row',
      gap: 8,
      marginTop: 4,
    },
    alignChip: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 4,
      paddingHorizontal: 10,
      paddingVertical: 4,
      borderRadius: 12,
    },
    alignText: {
      fontSize: 11,
      fontWeight: '600',
    },

    /* ─── CARDS ─── */
    card: {
      borderRadius: 14,
      padding: 16,
      borderWidth: 1,
      marginTop: 12,
    },
    cardHeader: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 6,
      marginBottom: 10,
    },
    cardLabel: {
      fontSize: 10,
      fontWeight: '800',
      letterSpacing: 1.5,
      marginBottom: 12,
    },
    summaryBody: {
      fontSize: 15,
      lineHeight: 22,
      fontWeight: '500',
    },

    /* ─── 3. TRADE SETUP ─── */
    noSetupWrap: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 8,
      paddingVertical: 14,
    },
    noSetupText: {
      fontSize: 14,
    },
    setupRow: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      paddingVertical: 11,
    },
    setupLeft: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
    },
    setupDot: {
      width: 6,
      height: 6,
      borderRadius: 3,
    },
    setupLabel: {
      fontSize: 14,
      fontWeight: '500',
    },
    setupValue: {
      fontSize: 16,
      fontWeight: '700',
      fontVariant: ['tabular-nums'],
    },
    setupNA: {
      fontSize: 14,
    },
    setupDivider: {
      height: StyleSheet.hairlineWidth,
    },
    lockedPill: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 4,
      paddingHorizontal: 10,
      paddingVertical: 4,
      borderRadius: 10,
    },
    lockedText: {
      fontSize: 11,
      fontWeight: '700',
    },

    /* ─── SECTION TITLE ─── */
    sectionTitle: {
      fontSize: 10,
      fontWeight: '800',
      letterSpacing: 1.5,
      marginTop: 24,
      marginBottom: 10,
    },

    /* ─── 4. DRIVERS ─── */
    driverCard: {
      borderRadius: 12,
      padding: 14,
      marginBottom: 8,
      borderWidth: 1,
    },
    driverTop: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
    },
    driverNameRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
    },
    driverName: {
      fontSize: 14,
      fontWeight: '700',
    },
    driverBadge: {
      paddingHorizontal: 10,
      paddingVertical: 3,
      borderRadius: 8,
    },
    driverBadgeText: {
      fontSize: 11,
      fontWeight: '700',
    },
    driverConfRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
      marginTop: 10,
    },
    driverConfBg: {
      flex: 1,
      height: 3,
      borderRadius: 2,
      overflow: 'hidden',
    },
    driverConfFill: {
      height: '100%',
      borderRadius: 2,
    },
    driverConfPct: {
      fontSize: 11,
      fontWeight: '700',
      width: 32,
      textAlign: 'right',
    },
    driverValue: {
      fontSize: 12,
      fontWeight: '600',
      marginTop: 8,
    },
    driverReason: {
      fontSize: 12,
      lineHeight: 17,
      marginTop: 3,
    },

    /* ─── 5. STRUCTURE ─── */
    structRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
      paddingVertical: 4,
    },
    structModule: {
      fontSize: 13,
      fontWeight: '500',
      flex: 1,
    },
    structDot: {
      width: 6,
      height: 6,
      borderRadius: 3,
    },
    structDir: {
      fontSize: 13,
      fontWeight: '700',
      width: 60,
    },
    structWeight: {
      fontSize: 11,
      width: 28,
      textAlign: 'right',
    },
    structDivider: {
      height: 1,
      marginVertical: 10,
    },
    structConclusion: {
      fontSize: 14,
      fontWeight: '600',
      lineHeight: 20,
    },

    /* ─── 6. PAYWALL ─── */
    paywallCard: {
      marginTop: 20,
      padding: 24,
      borderRadius: 16,
      borderWidth: 1,
      alignItems: 'center',
    },
    paywallIcon: {
      width: 44,
      height: 44,
      borderRadius: 22,
      justifyContent: 'center',
      alignItems: 'center',
      marginBottom: 14,
    },
    paywallTitle: {
      fontSize: 17,
      fontWeight: '700',
      textAlign: 'center',
      marginBottom: 8,
    },
    paywallDesc: {
      fontSize: 13,
      lineHeight: 20,
      textAlign: 'center',
      marginBottom: 18,
    },
    paywallBtn: {
      paddingHorizontal: 32,
      paddingVertical: 14,
      borderRadius: 12,
      width: '100%',
      alignItems: 'center',
    },
    paywallBtnText: {
      color: '#fff',
      fontSize: 15,
      fontWeight: '700',
    },
    proofBlock: {
      width: '100%',
      padding: 12,
      borderRadius: 10,
      borderWidth: 1,
      marginBottom: 16,
    },
    proofLabel: {
      fontSize: 11,
      fontWeight: '700',
      marginBottom: 4,
    },
    proofLine: {
      fontSize: 14,
      fontWeight: '700',
    },
    proofHint: {
      fontSize: 11,
      marginTop: 4,
      fontStyle: 'italic',
    },

    /* META */
    metaRow: {
      marginTop: 20,
      paddingTop: 12,
      borderTopWidth: 1,
      alignItems: 'center',
    },
    metaText: {
      fontSize: 11,
    },
  });
;
