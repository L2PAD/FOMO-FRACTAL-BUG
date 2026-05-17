/**
 * News Intelligence Screen — Market Tension Engine
 * =================================================
 * Not a news reader. A decision engine that makes users FEEL tension and act.
 *
 * Core formula (client-side, computed from /api/news/feed + /api/sentiment):
 *   news_alpha_score = impact × market_alignment × sentiment_strength × velocity × (1 - saturation)
 *
 * Signal Stages derived from alpha + velocity + saturation:
 *   EARLY      — velocity high, saturation low     → "Momentum building — early positioning window"
 *   FORMING    — alpha + tech ok                    → "Setup forming — watch entry zone"
 *   CONFIRMED  — breakout (high alpha + sentiment)  → "Move started — follow momentum"
 *   SATURATED  — saturation high                    → "Move extended — risk of late entry"
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl, Linking, LayoutAnimation, Platform, UIManager,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { api } from '../../../services/api/api-client';
import { useColors } from '../../../core/useColors';
import { useAppMode } from '../../../stores/app-mode.store';
import { hapticSelection, hapticMedium, hapticLight } from '../../../services/haptics.service';

import { t } from '../../../core/i18n';
// Enable LayoutAnimation on Android for smooth expand
if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

const RECENT_ASSETS_KEY = 'fomo.news.recent_assets.v1';
const MAX_RECENT_ASSETS = 10;

type TabKey = 'BRIEF' | 'EVENTS' | 'TWITTER' | 'RADAR';
type SignalStage = 'EARLY' | 'FORMING' | 'CONFIRMED' | 'SATURATED';

interface NewsCluster {
  clusterId: string;
  title: string;
  eventType: string;
  primaryAsset: string | null;
  assets: string[];
  importance: number;
  importanceBand: 'high' | 'medium' | 'low';
  isBreaking: boolean;
  sourcesCount: number;
  sources: string[];
  firstSeenAt: string;
  lastSeenAt: string;
  sentimentHint: string | null;
  representativeUrl: string | null;
  representativeSource: string | null;
}
interface TrendsData {
  eventTypes: Record<string, number>;
  importance: { high: number; medium: number; low: number };
  clustering: { totalRaw: number; totalClusters: number; avgClusterSize: number };
}
interface SentimentRow {
  symbol: string;
  bias: number;
  confidence: number;
  direction: 'LONG' | 'SHORT' | 'NEUTRAL';
  eventsCount: number;
  expectedReturnPct: number;
}

interface EnrichedCluster extends NewsCluster {
  alpha: number;
  stage: SignalStage;
  velocity: number;
  saturation: number;
  sentimentStrength: number;
  minutesOld: number;
  interpretation: string;   // Bloomberg-like narrative
  ifContinues: string;
  ctaLabel: string;         // soft verb
  timePressure: string;
  alphaLabel: string;       // "strong signal" / "developing" / "weak signal"
  confidenceLabel: string;  // "high confidence" / "building confidence" / "low confidence"
  signalLine: string;       // "TRX momentum building" — reads like a news lead
  marketImpact: string;     // "Impact: Likely to move TRX short-term"
}

interface Props { onClose: () => void; }

const TABS: { key: TabKey; label: string }[] = [
  { key: 'BRIEF', label: 'Brief' },
  { key: 'EVENTS', label: 'Events' },
  { key: 'TWITTER', label: 'Twitter AI' },
  { key: 'RADAR', label: 'Radar' },
];

// ──────────────────────────────────────────────────────────────────
// LIVE TIME LABEL — dynamic descriptor based on age + velocity + saturation
// Replaces static "Active 4h" with vocabulary that feels alive
// ──────────────────────────────────────────────────────────────────
function getLiveTimeLabel(ageMin: number, velocity: number, saturation: number, sourcesCount: number): string {
  if (ageMin < 10) return 'Just forming';
  if (velocity > 1.5 && saturation < 0.5) return 'Momentum building';
  if (saturation > 0.6) return 'Coverage expanding';
  if (ageMin < 60) return 'Still developing';
  if (sourcesCount >= 4) return 'Narrative spreading';
  return 'Still tracking';
}

// ──────────────────────────────────────────────────────────────────
// CARD EXPAND CONTENT — "Why it matters" + "Market reaction"
// Max 2 lines each, narrative tone, no numbers
// ──────────────────────────────────────────────────────────────────
function getWhyItMatters(c: EnrichedCluster): string {
  const asset = c.primaryAsset || 'this asset';
  const type = (c.eventType || '').toLowerCase();
  if (type === 'regulation' || type === 'legal') return `Regulatory shifts historically trigger multi-day moves on ${asset}.`;
  if (type === 'etf') return `ETF-related flow reshapes institutional positioning on ${asset}.`;
  if (type === 'hack' || type === 'exploit') return `Security events typically compress ${asset} short-term and bleed into adjacent tokens.`;
  if (type === 'macro') return `Macro narratives drive crypto beta — ${asset} likely to follow risk tone.`;
  if (type === 'listing') return `New listings expand liquidity and attract flow into ${asset}.`;
  if (type === 'whale') return `Large wallet behavior often precedes visible ${asset} price action.`;
  if (type === 'partnership' || type === 'adoption') return `Adoption narratives slowly reprice ${asset} as coverage broadens.`;
  if (type === 'funding') return `Capital flowing into ${asset} ecosystem signals builder momentum.`;
  return `This narrative historically impacts ${asset} short-term volatility.`;
}
function getMarketReaction(c: EnrichedCluster): string {
  if (c.stage === 'EARLY') return 'No strong reaction yet — still early in the cycle.';
  if (c.stage === 'FORMING') return 'Market acknowledging — volume picking up across sources.';
  if (c.stage === 'CONFIRMED') return 'Price already reacting — narrative in motion.';
  return 'Reaction plateauing — narrative mostly priced in.';
}

// ──────────────────────────────────────────────────────────────────
// ALPHA SCORE + SIGNAL STAGE CALCULATION (client-side)
// ──────────────────────────────────────────────────────────────────
const EVENT_WEIGHT: Record<string, number> = {
  regulation: 1.0, etf: 1.0, hack: 0.9, exploit: 0.9,
  macro: 0.8, listing: 0.7, funding: 0.7,
  whale: 0.6, legal: 0.8, adoption: 0.6,
  partnership: 0.5, price: 0.4, market: 0.5,
};

function computeEnriched(
  c: NewsCluster,
  allClusters: NewsCluster[],
  sentByAsset: Map<string, SentimentRow>,
): EnrichedCluster {
  const now = Date.now();
  const firstSeen = new Date(c.firstSeenAt).getTime();
  const lastSeen = new Date(c.lastSeenAt).getTime();
  const minutesOld = Math.max(0, Math.round((now - lastSeen) / 60000));
  const spreadMin = Math.max(1, (lastSeen - firstSeen) / 60000);

  // 1. impact_score — normalized 0..1
  const eventW = EVENT_WEIGHT[c.eventType] ?? 0.5;
  const impact = (c.importance / 100) * eventW;

  // 2. sentiment_strength = |bias| × confidence  (via sentiment store)
  const sent = c.primaryAsset ? sentByAsset.get(c.primaryAsset) : undefined;
  const sentimentStrength = sent ? Math.abs(sent.bias) * sent.confidence : 0.2;

  // 3. velocity — sources per minute spread (more sources in less time = hotter)
  const rawVelocity = c.sourcesCount / Math.max(1, spreadMin / 15);
  const velocity = Math.min(3, rawVelocity); // cap at 3

  // 4. saturation — how many similar-type clusters already exist / avg
  const sameType = allClusters.filter(x => x.eventType === c.eventType).length;
  const avgPerType = allClusters.length / Math.max(1, new Set(allClusters.map(x => x.eventType)).size);
  const saturation = Math.min(1, sameType / Math.max(1, avgPerType * 2));

  // 5. market_alignment — sentiment direction match (simplified)
  const sentHint = (c.sentimentHint || '').toLowerCase();
  const isBullish = sentHint === 'bullish' || sentHint === 'positive';
  const isBearish = sentHint === 'bearish' || sentHint === 'negative';
  let alignment = 0.7;
  if (sent) {
    if ((isBullish && sent.direction === 'LONG') || (isBearish && sent.direction === 'SHORT')) alignment = 1.0;
    else if ((isBullish && sent.direction === 'SHORT') || (isBearish && sent.direction === 'LONG')) alignment = 0.4;
  }

  // FINAL alpha score 0..1
  const alpha = impact * alignment * (0.4 + 0.6 * sentimentStrength) * (0.5 + 0.5 * (velocity / 3)) * (1 - saturation * 0.7);

  // Signal stage
  let stage: SignalStage;
  if (saturation > 0.7 && minutesOld > 60) stage = 'SATURATED';
  else if (alpha > 0.55 && minutesOld < 30 && sentimentStrength > 0.25) stage = 'CONFIRMED';
  else if (velocity > 1.3 && saturation < 0.4 && minutesOld < 30) stage = 'EARLY';
  else stage = 'FORMING';

  // Auto-interpretation per stage — narrative, not trader lingo
  const asset = c.primaryAsset || 'market';
  const interpretationByStage: Record<SignalStage, string> = {
    EARLY: `Momentum building on ${asset} as coverage expands.`,
    FORMING: `Market reacting to ${asset} narrative — pressure forming across sources.`,
    CONFIRMED: `${asset} narrative accelerating — multiple sources aligned.`,
    SATURATED: `${asset} story widely covered — narrative mature.`,
  };
  // Signal line reads like a news lead, not a metric
  const signalLineByStage: Record<SignalStage, string> = {
    EARLY: `${asset} gaining attention`,
    FORMING: `${asset} momentum building`,
    CONFIRMED: `${asset} narrative accelerating`,
    SATURATED: `${asset} story mature`,
  };
  const ifContinuesByStage: Record<SignalStage, string> = {
    EARLY: `If continues → ${asset} breakout likely`,
    FORMING: `If ignored → missed context`,
    CONFIRMED: `Momentum still active`,
    SATURATED: `Move already in consensus`,
  };
  const ctaByStage: Record<SignalStage, string> = {
    EARLY: `Track ${asset} setup`,
    FORMING: `See ${asset} setup forming`,
    CONFIRMED: `Follow ${asset} momentum`,
    SATURATED: `View ${asset} narrative`,
  };

  // Time pressure — ALIVE descriptor (no stale "X ago")
  const liveTimeLabel = getLiveTimeLabel(minutesOld, velocity, saturation, c.sourcesCount);
  let timePressure: string;
  if (minutesOld < 60) timePressure = `${liveTimeLabel} · ${minutesOld}m`;
  else timePressure = `${liveTimeLabel} · ${Math.round(minutesOld / 60)}h`;

  // Human-readable labels
  const alpha100 = Math.round(alpha * 100);
  const alphaLabel = alpha100 >= 10 ? 'strong signal' : alpha100 >= 5 ? 'developing' : 'weak signal';
  const confPct = sentimentStrength * 100;
  const confidenceLabel = confPct >= 50 ? 'high confidence' : confPct >= 20 ? 'building confidence' : 'low confidence';

  // Market Impact — single line, human
  let marketImpact: string;
  if (sent && sent.direction !== 'NEUTRAL') {
    const dirWord = sent.direction === 'LONG' ? 'upward' : 'downward';
    if (alignment >= 1.0) marketImpact = `Impact: Market reacting ${dirWord} on ${asset}`;
    else if (alignment <= 0.5) marketImpact = `Impact: Narrative diverging from price`;
    else marketImpact = `Impact: Likely to move ${asset} short-term`;
  } else if (c.sourcesCount >= 4) {
    marketImpact = `Impact: Wide coverage · watch for reaction`;
  } else {
    marketImpact = `Impact: Weak — no market reaction yet`;
  }

  return {
    ...c,
    alpha: Math.max(0, Math.min(1, alpha)),
    stage, velocity, saturation, sentimentStrength, minutesOld,
    interpretation: interpretationByStage[stage],
    signalLine: signalLineByStage[stage],
    ifContinues: ifContinuesByStage[stage],
    ctaLabel: c.primaryAsset ? ctaByStage[stage] : 'See full context',
    timePressure,
    alphaLabel, confidenceLabel, marketImpact,
  };
}

// ──────────────────────────────────────────────────────────────────
// MAIN COMPONENT
// ──────────────────────────────────────────────────────────────────
export function NewsIntelligenceScreen({ onClose }: Props) {
  const colors = useColors();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const [tab, setTab] = useState<TabKey>('BRIEF');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [rawClusters, setRawClusters] = useState<NewsCluster[]>([]);
  const [trends, setTrends] = useState<TrendsData | null>(null);
  const [sentiment, setSentiment] = useState<SentimentRow[]>([]);
  const [recentAssets, setRecentAssets] = useState<string[]>([]);

  const setIntelTab = useAppMode((s) => s.setIntelTab);

  // Load recently-viewed assets (behavior-based relevance)
  useEffect(() => {
    (async () => {
      try {
        const raw = await AsyncStorage.getItem(RECENT_ASSETS_KEY);
        if (raw) {
          const list = JSON.parse(raw);
          if (Array.isArray(list)) setRecentAssets(list);
        }
      } catch { /* noop */ }
    })();
  }, []);

  const rememberAsset = useCallback(async (asset: string | null) => {
    if (!asset) return;
    setRecentAssets((prev) => {
      const next = [asset, ...prev.filter((a) => a !== asset)].slice(0, MAX_RECENT_ASSETS);
      AsyncStorage.setItem(RECENT_ASSETS_KEY, JSON.stringify(next)).catch(() => {});
      return next;
    });
  }, []);

  const load = useCallback(async () => {
    try {
      const [feedRes, trendsRes, sentRes] = await Promise.all([
        api.get('/api/news/feed', { params: { limit: 40, hoursBack: 24 } }),
        api.get('/api/news/trends'),
        api.get('/api/sentiment/aggregate/all', { params: { window: '24H' } }),
      ]);
      setRawClusters(feedRes.data?.data?.clusters || []);
      setTrends(trendsRes.data?.data || null);
      setSentiment((sentRes.data?.data || []).slice(0, 20));
    } catch (_e) {
      // graceful
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  const onRefresh = () => { setRefreshing(true); load(); };

  // Enrich every cluster with alpha/stage
  const sentByAsset = useMemo(() => {
    const m = new Map<string, SentimentRow>();
    sentiment.forEach(s => m.set(s.symbol, s));
    return m;
  }, [sentiment]);

  const clusters = useMemo<EnrichedCluster[]>(() => {
    return rawClusters.map(c => computeEnriched(c, rawClusters, sentByAsset))
      .sort((a, b) => b.alpha - a.alpha); // rank by alpha, not recency
  }, [rawClusters, sentByAsset]);

  const goToSignal = (asset: string | null) => {
    hapticMedium();
    if (asset) {
      rememberAsset(asset);
      setIntelTab('SIGNALS');
    }
    onClose();
  };
  const goToEdge = () => { hapticMedium(); setIntelTab('EDGE'); onClose(); };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={onClose} style={styles.backBtn} testID="news-close">
          <Ionicons name="chevron-back" size={24} color={colors.textPrimary} />
        </TouchableOpacity>
        <View style={styles.headerTitle}>
          <Text style={styles.headerLabel}>News</Text>
          <Text style={styles.headerSubtitle}>{t('intel.marketTensionEngine')}</Text>
        </View>
        <View style={{ width: 40 }} />
      </View>

      {/* Tabs */}
      <View style={styles.tabs}>
        {TABS.map(({ key, label }) => (
          <TouchableOpacity
            key={key}
            onPress={() => { hapticSelection(); setTab(key); }}
            style={[styles.tab, tab === key && styles.tabActive]}
            testID={`news-tab-${key.toLowerCase()}`}
          >
            <Text style={[styles.tabLabel, tab === key && { color: colors.accentText }]}>{label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <View style={styles.loader}><ActivityIndicator color={colors.accent} size="large" /></View>
      ) : (
        <>
          <ScrollView
            style={{ flex: 1 }}
            contentContainerStyle={styles.scroll}
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
          >
            {tab === 'BRIEF' && (
              <BriefTab colors={colors} styles={styles} clusters={clusters} trends={trends}
                sentiment={sentiment} onOpenSignal={goToSignal} onOpenEdge={goToEdge}
                onOpenEvents={() => setTab('EVENTS')} recentAssets={recentAssets} />
            )}
            {tab === 'EVENTS' && (
              <EventsTab colors={colors} styles={styles} clusters={clusters} onOpenSignal={goToSignal} recentAssets={recentAssets} />
            )}
            {tab === 'TWITTER' && (
              <TwitterTab colors={colors} styles={styles} sentiment={sentiment} />
            )}
            {tab === 'RADAR' && (
              <RadarTab colors={colors} styles={styles} trends={trends} clusters={clusters} onOpenEdge={goToEdge} />
            )}
            <View style={{ height: 90 }} />
          </ScrollView>

          {/* FIXED BOTTOM CTA — always visible */}
          <View style={[styles.stickyCta, { backgroundColor: colors.background, borderTopColor: colors.border }]}>
            <TouchableOpacity
              style={[styles.stickyCtaBtn, { backgroundColor: colors.accent }]}
              onPress={() => goToEdge()}
              testID="news-sticky-cta"
            >
              <Ionicons name="flash" size={18} color={colors.accentText} />
              <Text style={[styles.stickyCtaText, { color: colors.accentText }]}>{t('intel.seeSetupsFormingNow')}</Text>
            </TouchableOpacity>
          </View>
        </>
      )}
    </SafeAreaView>
  );
}

// ══════════════════════════════════════════════════════════════════
// BRIEF — tension HERO + breaking + what you're missing
// ══════════════════════════════════════════════════════════════════
function BriefTab({ colors, styles, clusters, trends, sentiment, onOpenSignal, onOpenEdge, onOpenEvents, recentAssets }: any) {
  const enriched = clusters as EnrichedCluster[];
  const breaking = enriched.filter(c => c.isBreaking || c.stage === 'CONFIRMED').slice(0, 3);
  const topAlpha = enriched.slice(0, 3);
  const earlySignals = enriched.filter(c => c.stage === 'EARLY').slice(0, 3);

  const highImpactCount = enriched.filter(c => c.importance >= 70).length;
  const confirmedCount = enriched.filter(c => c.stage === 'CONFIRMED').length;
  const earlyCount = enriched.filter(c => c.stage === 'EARLY').length;
  const recentCount = enriched.filter(c => c.minutesOld <= 20).length;

  // HERO tension copy — Bloomberg-like narrative, not stats
  const topAsset = enriched[0]?.primaryAsset || 'BTC';
  const heroState = useMemo(() => {
    if (confirmedCount >= 2) {
      return {
        badge: '● MARKET MOVING',
        title: `${topAsset} narrative accelerating across the market`,
        sub: `${confirmedCount} confirmed moves · ${earlyCount} early signals`,
        cta: 'See what\'s driving it',
        color: colors.sell || '#FF6B6B',
      };
    }
    if (earlyCount >= 2 || highImpactCount >= 3) {
      return {
        badge: '● SIGNALS FORMING',
        title: `${topAsset} gaining attention across multiple signals`,
        sub: `Watching ${enriched.length} signals across market`,
        cta: 'See what\'s building',
        color: colors.accent,
      };
    }
    if (enriched.length > 5) {
      return {
        badge: '● MARKET WATCHING',
        title: 'Narratives diverging across crypto',
        sub: `${enriched.length} events unfolding`,
        cta: 'See the context',
        color: colors.textSecondary,
      };
    }
    return {
      badge: '● MARKET QUIET',
      title: 'Waiting for catalyst',
      sub: `${enriched.length} events tracked`,
      cta: 'See what\'s tracked',
      color: colors.textSecondary,
    };
  }, [confirmedCount, earlyCount, highImpactCount, enriched.length, topAsset, colors]);

  // HERO SUBTEXT ROTATION — every 6.5s, rotates through contextual phrases
  // Gives the screen "pulse" without animation overhead.
  const rotatingSubs = useMemo(() => {
    const list = [heroState.sub];
    if (recentCount > 0) list.push(`${recentCount} new signals forming in last 20 min`);
    if (earlyCount > 0) list.push(`Coverage expanding on ${topAsset}`);
    if (confirmedCount > 0) list.push(`${confirmedCount} narrative${confirmedCount > 1 ? 's' : ''} in motion right now`);
    list.push('Narratives diverging across crypto');
    list.push(`Watching ${enriched.length} signals across market`);
    // De-dupe
    return Array.from(new Set(list.filter(Boolean)));
  }, [heroState.sub, recentCount, earlyCount, confirmedCount, topAsset, enriched.length]);

  const [heroIdx, setHeroIdx] = useState(0);
  useEffect(() => {
    if (rotatingSubs.length <= 1) return;
    const id = setInterval(() => {
      setHeroIdx((i) => (i + 1) % rotatingSubs.length);
    }, 6500);
    return () => clearInterval(id);
  }, [rotatingSubs.length]);
  // Keep in bounds when list size changes
  const safeHeroSub = rotatingSubs[heroIdx % rotatingSubs.length] || heroState.sub;

  return (
    <>
      {/* TENSION HERO — subtext rotates every 6.5s for "live" feel */}
      <View style={[styles.hero, { borderColor: heroState.color + '60', backgroundColor: heroState.color + '12' }]}>
        <Text style={[styles.heroBadge, { color: heroState.color }]}>{heroState.badge}</Text>
        <Text style={[styles.heroTitle, { color: colors.textPrimary }]}>{heroState.title}</Text>
        <Text style={[styles.heroSub, { color: colors.textSecondary }]}>{safeHeroSub}</Text>
        <TouchableOpacity
          style={[styles.heroCta, { backgroundColor: heroState.color }]}
          onPress={onOpenEvents}
          testID="news-hero-cta"
        >
          <Text style={[styles.heroCtaText, { color: colors.accentText }]}>→ {heroState.cta}</Text>
        </TouchableOpacity>
      </View>

      {/* BREAKING / CONFIRMED */}
      {breaking.length > 0 && (
        <Section title={t('intel.confirmedMoves')} subtitle="alpha-ranked · not chronological" colors={colors}>
          {breaking.map(c => (
            <IntelligenceCard key={c.clusterId} cluster={c} colors={colors} onOpenSignal={onOpenSignal} recentAssets={recentAssets} />
          ))}
        </Section>
      )}

      {/* EARLY SIGNALS */}
      {earlySignals.length > 0 && (
        <Section title={t('intel.earlySignalsForming')} subtitle="positioning window open" colors={colors}>
          {earlySignals.map(c => (
            <IntelligenceCard key={c.clusterId} cluster={c} colors={colors} onOpenSignal={onOpenSignal} recentAssets={recentAssets} />
          ))}
        </Section>
      )}

      {/* TOP by ALPHA */}
      {breaking.length === 0 && earlySignals.length === 0 && (
        <Section title={t('intel.highestAlphaEvents')} colors={colors}>
          {topAlpha.map(c => (
            <IntelligenceCard key={c.clusterId} cluster={c} colors={colors} onOpenSignal={onOpenSignal} recentAssets={recentAssets} />
          ))}
        </Section>
      )}

      {/* WHAT YOU'RE MISSING — dynamic, time-fresh FOMO */}
      <WhatYoureMissing
        colors={colors}
        styles={styles}
        earlyCount={earlyCount}
        confirmedCount={confirmedCount}
        highImpactCount={highImpactCount}
        enriched={enriched}
        onUnlock={() => onOpenEdge()}
      />

      {/* RETURN TRIGGER — programs a return visit */}
      <View style={styles.returnTrigger}>
        <Text style={[styles.returnTriggerText, { color: colors.textSecondary }]}>
          Market still developing · check back shortly
        </Text>
      </View>
    </>
  );
}

function WhatYoureMissing({ colors, styles, earlyCount, confirmedCount, highImpactCount, enriched, onUnlock }: any) {
  // Count signals forming in last 20 min — time-fresh FOMO
  const recent = (enriched as EnrichedCluster[]).filter(c => c.minutesOld <= 20);
  const items: string[] = [];
  if (recent.length > 0) items.push(`${recent.length} new signals forming in last 20 min`);
  if (earlyCount > 0) items.push(`${earlyCount} narrative${earlyCount > 1 ? 's' : ''} developing right now`);
  if (confirmedCount > 0) items.push(`${confirmedCount} confirmed move${confirmedCount > 1 ? 's' : ''} unfolding`);
  if (items.length === 0 && highImpactCount > 0) items.push(`${highImpactCount} high-impact events active`);
  if (items.length === 0) return null;
  return (
    <View style={[styles.missing, { borderColor: colors.accent + '60', backgroundColor: colors.accent + '10' }]}>
      <Text style={[styles.missingTitle, { color: colors.accent }]}>⚠️ YOU MIGHT BE MISSING</Text>
      {items.map((t, i) => (
        <Text key={i} style={[styles.missingItem, { color: colors.textPrimary }]}>• {t}</Text>
      ))}
      <TouchableOpacity style={[styles.missingBtn, { borderColor: colors.accent, backgroundColor: colors.accent }]} onPress={onUnlock} testID="news-missing-cta">
        <Text style={[styles.missingBtnText, { color: colors.accentText }]}>→ See what's developing</Text>
      </TouchableOpacity>
    </View>
  );
}

// ══════════════════════════════════════════════════════════════════
// EVENTS — filtered + ranked by alpha, scroll interruptions every 4 cards
// ══════════════════════════════════════════════════════════════════
function EventsTab({ colors, styles, clusters, onOpenSignal, recentAssets }: any) {
  const [filter, setFilter] = useState<string>('ALL');
  const enriched = clusters as EnrichedCluster[];
  const types = useMemo(() => {
    const set = new Set<string>();
    enriched.forEach(c => c.eventType && set.add(c.eventType));
    return ['ALL', ...Array.from(set)];
  }, [enriched]);
  const filtered = filter === 'ALL' ? enriched : enriched.filter(c => c.eventType === filter);

  // Count fresh signals for interruption block
  const freshCount = enriched.filter(c => c.minutesOld <= 15).length;
  const earlyStageCount = enriched.filter(c => c.stage === 'EARLY').length;

  return (
    <>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipsRow} contentContainerStyle={{ gap: 8, paddingHorizontal: 4 }}>
        {types.map((t) => (
          <TouchableOpacity
            key={t}
            onPress={() => { hapticSelection(); setFilter(t); }}
            style={[styles.chip, {
              backgroundColor: filter === t ? colors.accent : colors.surface,
              borderColor: filter === t ? colors.accent : colors.border,
            }]}
            testID={`news-filter-${t.toLowerCase()}`}
          >
            <Text style={[styles.chipText, { color: filter === t ? '#000' : colors.textPrimary }]}>
              {t.replace(/_/g, ' ').toUpperCase()}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
      {filtered.map((c, i) => {
        // Inject interruption block every 4 cards (but not at very end)
        const showInterruption = (i + 1) % 4 === 0 && i !== filtered.length - 1 && filtered.length > 4;
        return (
          <React.Fragment key={c.clusterId}>
            <IntelligenceCard cluster={c} colors={colors} onOpenSignal={onOpenSignal} recentAssets={recentAssets} />
            {showInterruption && (
              <ScrollInterruption
                colors={colors}
                styles={styles}
                freshCount={freshCount}
                earlyCount={earlyStageCount}
                index={i}
              />
            )}
          </React.Fragment>
        );
      })}
      {filtered.length === 0 && (
        <Text style={[styles.empty, { color: colors.textSecondary }]}>{t('intel.noEventsInThisCategory')}</Text>
      )}
    </>
  );
}

// ScrollInterruption — non-pushy mid-feed pulse, varies by position
function ScrollInterruption({ colors, styles, freshCount, earlyCount, index }: any) {
  // Rotate message by position to avoid repetition
  const messages = [
    {
      title: '⚠️ Market shifting',
      body: freshCount > 0 ? `${freshCount} new signals forming in last 15 min` : `${earlyCount} narratives developing right now`,
    },
    {
      title: '● Signals below building',
      body: 'Coverage expanding — keep scrolling',
    },
    {
      title: '⚡ Still unfolding',
      body: earlyCount > 0 ? `${earlyCount} early-stage narrative${earlyCount > 1 ? 's' : ''} active` : 'Narratives evolving across the feed',
    },
  ];
  const msg = messages[(Math.floor(index / 4)) % messages.length];
  return (
    <View style={[styles.interruption, { borderColor: colors.accent + '40', backgroundColor: colors.accent + '08' }]}>
      <Text style={[styles.interruptionTitle, { color: colors.accent }]}>{msg.title}</Text>
      <Text style={[styles.interruptionBody, { color: colors.textSecondary }]}>{msg.body}</Text>
    </View>
  );
}

// ══════════════════════════════════════════════════════════════════
// TWITTER AI — sentiment pressure bars
// ══════════════════════════════════════════════════════════════════
function TwitterTab({ colors, styles, sentiment }: any) {
  if (!sentiment?.length) {
    return <Text style={[styles.empty, { color: colors.textSecondary }]}>Collecting Twitter signals…</Text>;
  }
  return (
    <Section title={t('intel.sentimentPressure24H')} colors={colors}>
      {(sentiment as SentimentRow[]).map((s) => {
        const dirColor = s.direction === 'LONG' ? (colors.bullish || colors.buy || '#2FE6A6')
                       : s.direction === 'SHORT' ? (colors.bearish || colors.sell || '#FF6B6B')
                       : colors.textSecondary;
        const confPct = Math.round((s.confidence || 0) * 100);
        const biasPct = Math.round(Math.abs(s.bias || 0) * 100);
        return (
          <View key={s.symbol} style={[styles.sentRow, { backgroundColor: colors.surface, borderColor: colors.border }]}>
            <View style={styles.sentLeft}>
              <Text style={[styles.sentSymbol, { color: colors.textPrimary }]}>{s.symbol}</Text>
              <Text style={[styles.sentEvents, { color: colors.textSecondary }]}>{s.eventsCount} events</Text>
            </View>
            <View style={styles.sentMiddle}>
              <View style={[styles.sentBarBg, { backgroundColor: colors.border }]}>
                <View style={[styles.sentBarFill, { width: `${Math.min(100, biasPct)}%`, backgroundColor: dirColor }]} />
              </View>
              <Text style={[styles.sentConf, { color: colors.textSecondary }]}>conf {confPct}%</Text>
            </View>
            <Text style={[styles.sentDir, { color: dirColor }]}>{s.direction}</Text>
          </View>
        );
      })}
    </Section>
  );
}

// ══════════════════════════════════════════════════════════════════
// RADAR — "NEXT MOVES FORMING"
// ══════════════════════════════════════════════════════════════════
function RadarTab({ colors, styles, trends, clusters, onOpenEdge }: any) {
  const enriched = clusters as EnrichedCluster[];
  // Group by eventType → primary affected asset with highest alpha
  const narratives = useMemo(() => {
    const map = new Map<string, { asset: string; alpha: number; count: number }>();
    for (const c of enriched) {
      const asset = c.primaryAsset || (c.assets?.[0] ?? '?');
      const cur = map.get(c.eventType);
      if (!cur || c.alpha > cur.alpha) {
        map.set(c.eventType, { asset, alpha: c.alpha, count: (cur?.count ?? 0) + 1 });
      } else {
        cur.count += 1;
      }
    }
    return Array.from(map.entries())
      .map(([type, v]) => ({ type, ...v }))
      .sort((a, b) => b.alpha - a.alpha)
      .slice(0, 8);
  }, [enriched]);

  return (
    <>
      <View style={[styles.radarHero, { borderColor: colors.accentTintBorder, backgroundColor: colors.accentTint }]}>
        <Text style={[styles.radarHeroBadge, { color: colors.accent }]}>⚡ NEXT MOVES FORMING</Text>
        <Text style={[styles.radarHeroSub, { color: colors.textSecondary }]}>
          narratives ranked by alpha · not volume
        </Text>
      </View>
      {narratives.map((n) => (
        <View key={n.type} style={[styles.radarRow, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <View style={{ flex: 1 }}>
            <Text style={[styles.radarType, { color: colors.textPrimary }]}>
              {n.type.toUpperCase()} → {n.asset}
            </Text>
            <View style={[styles.radarBarWrap, { backgroundColor: colors.border }]}>
              <View style={[styles.radarBar, { width: `${Math.round(n.alpha * 100)}%`, backgroundColor: colors.accent }]} />
            </View>
          </View>
          <View style={{ alignItems: 'flex-end', gap: 2 }}>
            <Text style={[styles.radarAlpha, { color: colors.accent }]}>α {Math.round(n.alpha * 100)}</Text>
            <Text style={[styles.radarCount, { color: colors.textSecondary }]}>{n.count} ev</Text>
          </View>
        </View>
      ))}
      <TouchableOpacity
        style={[styles.radarExploreBtn, { backgroundColor: colors.accent, borderColor: colors.accent }]}
        onPress={onOpenEdge}
        testID="news-radar-edge"
      >
        <Ionicons name="scan-outline" size={18} color={colors.accentText} />
        <Text style={[styles.radarExploreText, { color: colors.accentText }]}>{t('intel.exploreSetups')}</Text>
      </TouchableOpacity>
    </>
  );
}

// ══════════════════════════════════════════════════════════════════
// INTELLIGENCE CARD — signal stage, tap to expand, personal relevance
// ══════════════════════════════════════════════════════════════════
function IntelligenceCard({ cluster, colors, onOpenSignal, recentAssets }: any) {
  const styles = makeStyles(colors);
  const c = cluster as EnrichedCluster;
  const [expanded, setExpanded] = useState(false);

  const stageConfig: Record<SignalStage, { label: string; color: string; icon: any }> = {
    EARLY: { label: '⚡ EARLY', color: colors.accent, icon: 'rocket-outline' },
    FORMING: { label: '● FORMING', color: colors.bullish || colors.buy || '#2FE6A6', icon: 'construct-outline' },
    CONFIRMED: { label: '🚀 CONFIRMED', color: colors.sell || '#FF6B6B', icon: 'trending-up' },
    SATURATED: { label: '● SATURATED', color: colors.textSecondary, icon: 'hourglass-outline' },
  };
  const cfg = stageConfig[c.stage];

  // Personal Relevance — show ONLY if user actually tapped this asset before
  // No fake watchlists. Silent if no data.
  const isRelevant = !!c.primaryAsset && Array.isArray(recentAssets) && recentAssets.includes(c.primaryAsset);

  const openSource = () => {
    if (c.representativeUrl) Linking.openURL(c.representativeUrl).catch(() => {});
  };

  const toggleExpand = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    hapticLight();
    setExpanded((v) => !v);
  };

  return (
    <TouchableOpacity
      activeOpacity={0.92}
      onPress={toggleExpand}
      style={[styles.card, { backgroundColor: colors.surface, borderColor: cfg.color + '40' }]}
      testID={`news-card-${c.clusterId}`}
    >
      {/* Personal Relevance strip — only when behavior-matched */}
      {isRelevant && (
        <View style={styles.relevanceStrip}>
          <Ionicons name="bookmark" size={11} color={colors.accent} />
          <Text style={[styles.relevanceText, { color: colors.accent }]}>{t('intel.relatedToYourRecentActivity')}</Text>
        </View>
      )}

      {/* Stage badge + alpha with label */}
      <View style={styles.cardHeader}>
        <View style={[styles.cardStage, { backgroundColor: cfg.color + '20', borderColor: cfg.color + '80' }]}>
          <Text style={[styles.cardStageText, { color: cfg.color }]}>{cfg.label}</Text>
        </View>
        <Text style={[styles.cardType, { color: colors.textSecondary }]}>
          {c.eventType.toUpperCase()}
        </Text>
        <View style={{ flex: 1 }} />
        <Text style={[styles.cardAlpha, { color: cfg.color }]}>α {Math.round(c.alpha * 100)}</Text>
        <Text style={[styles.cardAlphaLabel, { color: colors.textSecondary }]}>· {c.alphaLabel}</Text>
      </View>

      {/* Signal line — reads like a news lead */}
      {c.primaryAsset && (
        <View style={styles.cardSignal}>
          <Ionicons name={cfg.icon} size={14} color={cfg.color} />
          <Text style={[styles.cardSignalText, { color: cfg.color }]}>
            {c.signalLine} · {c.confidenceLabel}
          </Text>
        </View>
      )}

      {/* Headline */}
      <Text style={[styles.cardTitle, { color: colors.textPrimary }]} numberOfLines={2}>{c.title}</Text>

      {/* Interpretation — Bloomberg-like narrative */}
      <Text style={[styles.cardInterp, { color: colors.textPrimary }]}>{c.interpretation}</Text>

      {/* MARKET IMPACT — one decisive line */}
      <View style={[styles.cardImpact, { borderLeftColor: cfg.color }]}>
        <Text style={[styles.cardImpactText, { color: colors.textSecondary }]}>{c.marketImpact}</Text>
      </View>

      {/* EXPANDED CONTENT — depth without navigation */}
      {expanded && (
        <View style={[styles.cardExpanded, { borderTopColor: colors.border }]}>
          <View style={styles.expandRow}>
            <Text style={[styles.expandLabel, { color: colors.textSecondary }]}>{t('intel.whyItMatters')}</Text>
            <Text style={[styles.expandBody, { color: colors.textPrimary }]} numberOfLines={2}>
              {getWhyItMatters(c)}
            </Text>
          </View>
          <View style={styles.expandRow}>
            <Text style={[styles.expandLabel, { color: colors.textSecondary }]}>{t('intel.marketReaction')}</Text>
            <Text style={[styles.expandBody, { color: colors.textPrimary }]} numberOfLines={2}>
              {getMarketReaction(c)}
            </Text>
          </View>
        </View>
      )}

      {/* Time pressure + sources */}
      <View style={styles.cardMeta}>
        <View style={styles.cardMetaLeft}>
          <Ionicons name="pulse-outline" size={11} color={cfg.color} />
          <Text style={[styles.cardTime, { color: cfg.color }]}>{c.timePressure}</Text>
        </View>
        {(c.assets || []).length > 0 && (
          <View style={styles.cardAssetsRow}>
            {c.assets.slice(0, 3).map((a) => (
              <Text key={a} style={[styles.cardAssetTag, { color: colors.accent, borderColor: colors.accent + '60' }]}>
                {a}
              </Text>
            ))}
          </View>
        )}
      </View>

      {/* Expand hint + Soft CTA — news voice, not trader voice */}
      <View style={styles.cardActions}>
        {c.primaryAsset && (
          <TouchableOpacity
            style={[styles.cardAction, { backgroundColor: cfg.color + '12', borderColor: cfg.color + '50' }]}
            onPress={(e) => { e.stopPropagation?.(); onOpenSignal(c.primaryAsset); }}
            testID={`news-card-cta-${c.clusterId}`}
          >
            <Text style={[styles.cardActionText, { color: cfg.color }]}>→ {c.ctaLabel}</Text>
          </TouchableOpacity>
        )}
        <TouchableOpacity
          onPress={(e) => { e.stopPropagation?.(); toggleExpand(); }}
          style={styles.cardSource}
          testID={`news-card-expand-${c.clusterId}`}
        >
          <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={13} color={colors.textSecondary} />
          <Text style={[styles.cardSourceText, { color: colors.textSecondary }]}>
            {expanded ? 'Less' : 'More'}
          </Text>
        </TouchableOpacity>
        {c.representativeUrl && (
          <TouchableOpacity
            style={styles.cardSource}
            onPress={(e) => { e.stopPropagation?.(); openSource(); }}
          >
            <Ionicons name="open-outline" size={13} color={colors.textSecondary} />
            <Text style={[styles.cardSourceText, { color: colors.textSecondary }]}>Source</Text>
          </TouchableOpacity>
        )}
      </View>
    </TouchableOpacity>
  );
}

function Section({ title, subtitle, colors, children }: any) {
  const s = makeStyles(colors);
  return (
    <View style={s.section}>
      <View style={s.sectionHead}>
        <Text style={[s.sectionTitle, { color: colors.textSecondary }]}>{title.toUpperCase()}</Text>
        {subtitle && <Text style={[s.sectionSub, { color: colors.textSecondary }]}>· {subtitle}</Text>}
      </View>
      {children}
    </View>
  );
}

// ──────────────────────────────────────────────────────────────────
// STYLES
// ──────────────────────────────────────────────────────────────────
const makeStyles = (c: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: c.background },
  header: {
    flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 10,
    borderBottomWidth: 1, borderBottomColor: c.border,
  },
  backBtn: { padding: 6, width: 40 },
  headerTitle: { flex: 1, alignItems: 'center' },
  headerLabel: { fontSize: 16, fontWeight: '700', color: c.textPrimary },
  headerSubtitle: { fontSize: 11, color: c.textSecondary, marginTop: 2 },
  tabs: {
    flexDirection: 'row', paddingHorizontal: 12, paddingVertical: 10, gap: 6,
    borderBottomWidth: 1, borderBottomColor: c.border,
  },
  tab: {
    flex: 1, paddingVertical: 8, borderRadius: 8, alignItems: 'center',
    backgroundColor: c.surface, borderWidth: 1, borderColor: c.border,
  },
  tabActive: { backgroundColor: c.accent, borderColor: c.accent },
  tabLabel: { fontSize: 12, fontWeight: '700', color: c.textSecondary },
  tabLabelActive: { color: '#000' },
  loader: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  scroll: { padding: 12, gap: 14 },

  // HERO — tension
  hero: { borderRadius: 16, borderWidth: 1.5, padding: 18, gap: 8 },
  heroBadge: { fontSize: 11, fontWeight: '900', letterSpacing: 1.2 },
  heroTitle: { fontSize: 24, fontWeight: '900', lineHeight: 28, marginTop: 2 },
  heroSub: { fontSize: 13, fontWeight: '500', lineHeight: 18 },
  heroCta: {
    alignItems: 'center', justifyContent: 'center',
    paddingVertical: 13, borderRadius: 10, marginTop: 8,
  },
  heroCtaText: { fontSize: 14, fontWeight: '800', letterSpacing: 0.3 },

  // SECTIONS
  section: { gap: 10 },
  sectionHead: { flexDirection: 'row', alignItems: 'baseline', gap: 6, marginBottom: 2 },
  sectionTitle: { fontSize: 11, fontWeight: '800', letterSpacing: 1 },
  sectionSub: { fontSize: 10, fontWeight: '500', fontStyle: 'italic' },
  empty: { fontSize: 13, fontStyle: 'italic', textAlign: 'center', paddingVertical: 24 },

  // CHIPS
  chipsRow: { flexGrow: 0, marginBottom: 4 },
  chip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, borderWidth: 1 },
  chipText: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5 },

  // CARD
  card: { borderRadius: 12, borderWidth: 1.5, padding: 14, gap: 8 },
  relevanceStrip: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingBottom: 6, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: c.border,
    marginBottom: 2,
  },
  relevanceText: { fontSize: 10, fontWeight: '800', letterSpacing: 0.5 },
  cardExpanded: {
    borderTopWidth: StyleSheet.hairlineWidth,
    paddingTop: 10, marginTop: 2, gap: 10,
  },
  expandRow: { gap: 3 },
  expandLabel: { fontSize: 10, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase' },
  expandBody: { fontSize: 12, lineHeight: 16, fontWeight: '500' },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  cardStage: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, borderWidth: 1 },
  cardStageText: { fontSize: 10, fontWeight: '900', letterSpacing: 0.5 },
  cardType: { fontSize: 10, fontWeight: '700', letterSpacing: 0.5 },
  cardAlpha: { fontSize: 13, fontWeight: '900', letterSpacing: 0.3 },
  cardAlphaLabel: { fontSize: 11, fontWeight: '600', marginLeft: 4 },
  cardSignal: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  cardSignalText: { fontSize: 11, fontWeight: '700' },
  cardTitle: { fontSize: 15, fontWeight: '800', lineHeight: 20, marginTop: 2 },
  cardInterp: { fontSize: 13, lineHeight: 18, fontWeight: '600' },
  cardIf: { borderLeftWidth: 3, paddingLeft: 10, paddingVertical: 4, marginLeft: 2 },
  cardIfText: { fontSize: 12, fontStyle: 'italic', lineHeight: 16 },
  cardImpact: { borderLeftWidth: 3, paddingLeft: 10, paddingVertical: 5, marginLeft: 2 },
  cardImpactText: { fontSize: 12, fontWeight: '700', lineHeight: 16 },

  cardMeta: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  cardMetaLeft: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  cardTime: { fontSize: 11, fontWeight: '700' },
  cardAssetsRow: { flexDirection: 'row', gap: 4, marginLeft: 'auto' },
  cardAssetTag: { fontSize: 10, fontWeight: '700', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, borderWidth: 1 },
  cardActions: { flexDirection: 'row', gap: 10, marginTop: 4, alignItems: 'center' },
  cardAction: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, borderRadius: 8, borderWidth: 1 },
  cardActionText: { fontSize: 13, fontWeight: '800' },
  cardSource: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 6 },
  cardSourceText: { fontSize: 12, fontWeight: '600' },

  // SCROLL INTERRUPTION — mid-feed pulse
  interruption: {
    borderRadius: 10, borderWidth: 1, borderStyle: 'dashed',
    paddingVertical: 10, paddingHorizontal: 14, gap: 2, marginVertical: 2,
  },
  interruptionTitle: { fontSize: 12, fontWeight: '900', letterSpacing: 0.6 },
  interruptionBody: { fontSize: 11, fontWeight: '600', lineHeight: 15 },

  // WHAT YOU'RE MISSING
  missing: { borderRadius: 14, borderWidth: 1.5, padding: 16, gap: 8, marginTop: 6 },
  missingTitle: { fontSize: 12, fontWeight: '900', letterSpacing: 1 },
  missingItem: { fontSize: 14, fontWeight: '700', lineHeight: 20 },
  missingBtn: { alignItems: 'center', justifyContent: 'center', paddingVertical: 12, borderRadius: 10, borderWidth: 1, marginTop: 6 },
  missingBtnText: { fontSize: 14, fontWeight: '800', letterSpacing: 0.3 },

  // RETURN TRIGGER — programs next visit
  returnTrigger: { alignItems: 'center', paddingVertical: 16, marginTop: 4 },
  returnTriggerText: { fontSize: 12, fontStyle: 'italic', fontWeight: '600', letterSpacing: 0.3 },

  // SENTIMENT ROW
  sentRow: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: 10, borderWidth: 1 },
  sentLeft: { width: 60 },
  sentSymbol: { fontSize: 14, fontWeight: '800' },
  sentEvents: { fontSize: 10, marginTop: 2 },
  sentMiddle: { flex: 1, gap: 4 },
  sentBarBg: { height: 6, borderRadius: 3, overflow: 'hidden' },
  sentBarFill: { height: '100%', borderRadius: 3 },
  sentConf: { fontSize: 10 },
  sentDir: { fontSize: 11, fontWeight: '800', letterSpacing: 0.5, minWidth: 60, textAlign: 'right' },

  // RADAR
  radarHero: { borderRadius: 12, borderWidth: 1.5, padding: 14, gap: 4, marginBottom: 4 },
  radarHeroBadge: { fontSize: 13, fontWeight: '900', letterSpacing: 1 },
  radarHeroSub: { fontSize: 11, fontStyle: 'italic' },
  radarRow: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: 10, borderWidth: 1 },
  radarType: { fontSize: 12, fontWeight: '800', letterSpacing: 0.5, marginBottom: 6 },
  radarBarWrap: { height: 6, borderRadius: 3, overflow: 'hidden' },
  radarBar: { height: '100%', borderRadius: 3 },
  radarAlpha: { fontSize: 13, fontWeight: '900' },
  radarCount: { fontSize: 10, fontWeight: '600' },
  radarExploreBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    paddingVertical: 14, borderRadius: 12, borderWidth: 1, marginTop: 8,
  },
  radarExploreText: { fontSize: 14, fontWeight: '800' },

  // STICKY BOTTOM CTA
  stickyCta: {
    borderTopWidth: 1, paddingHorizontal: 12, paddingVertical: 10,
    paddingBottom: 16,
  },
  stickyCtaBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    paddingVertical: 14, borderRadius: 12,
  },
  stickyCtaText: { fontSize: 15, fontWeight: '900', color: '#000', letterSpacing: 0.3 },
});
