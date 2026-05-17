/**
 * AIValueNarrativeFeed — Global value perception engine.
 *
 * Renders the most emotionally relevant AI-decision events as narrative
 * cards (NOT metrics). This is the addiction loop:
 *
 *   "AI prevented entry into SOL · capital preserved +18.4% · conviction
 *    collapsed 12m before dump"
 *
 * vs. the bad version:  "Avoided Loss: 18%"
 *
 * Six event types are surfaced:
 *
 *   1. AVOIDED_CATASTROPHE   — AI killed a setup before a major loss
 *   2. EMOTIONAL_SUPPRESSION — AI refused crowd-driven entry
 *   3. CAPITAL_PRESERVATION  — no-trade was the correct trade
 *   4. TIMING_SUPERIORITY    — AI waited longer, asymmetry improved
 *   5. INTENTIONAL_SKIP      — honest "AI skipped +X% on purpose"
 *   6. SUPPRESSED_BY_REGIME  — meta verdict suppressed entire pipeline
 *
 * Pulls from existing endpoints:
 *   - mbrainApi.realizedAttribution()  → top_avoided / top_missed
 *   - mbrainApi.parallelPortfolios()    → headline + narratives
 *
 * No backend changes. Read-only. Module-scope cache to avoid hammering.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../core/useColors';
import { mbrainApi } from '../../services/api/mbrain-api';
import { useOpenInTradingOS } from './useOpenInTradingOS';

type EventType =
  | 'AVOIDED_CATASTROPHE'
  | 'EMOTIONAL_SUPPRESSION'
  | 'CAPITAL_PRESERVATION'
  | 'TIMING_SUPERIORITY'
  | 'INTENTIONAL_SKIP'
  | 'SUPPRESSED_BY_REGIME';

interface NarrativeEvent {
  type: EventType;
  symbol?: string | null;
  title: string;
  detail: string;
  proof: string;       // the value line ("capital preserved +18.4%")
  proofTone: 'good' | 'bad' | 'neutral';
}

const ICON: Record<EventType, keyof typeof Ionicons.glyphMap> = {
  AVOIDED_CATASTROPHE:    'shield-checkmark',
  EMOTIONAL_SUPPRESSION:  'flame',
  CAPITAL_PRESERVATION:   'lock-closed',
  TIMING_SUPERIORITY:     'time',
  INTENTIONAL_SKIP:       'walk',
  SUPPRESSED_BY_REGIME:   'pause-circle',
};

// ─── module cache ───────────────────────────────────────────────────
let _cache: { ts: number; events: NarrativeEvent[] } | null = null;
const CACHE_MS = 60 * 1000;

function pctRaw(n: number | null | undefined, d = 1): string {
  if (n == null || isNaN(n)) return '—';
  const sign = n >= 0 ? '+' : '';
  return `${sign}${n.toFixed(d)}%`;
}
function absPct(n: number | null | undefined, d = 1): string {
  if (n == null || isNaN(n)) return '—';
  return `${Math.abs(n).toFixed(d)}%`;
}

// ─── narrative builder ─────────────────────────────────────────────
function buildEvents(realized: any, parallel: any): NarrativeEvent[] {
  const events: NarrativeEvent[] = [];
  const headline = realized?.headline;
  const phead = parallel?.headline;
  const avoided = realized?.top_avoided || [];
  const missed = realized?.top_missed || [];
  const narratives = parallel?.narratives || [];

  // 1. Avoided catastrophes — top 2 by abs realized_return
  avoided.slice(0, 2).forEach((s: any) => {
    const ret = (s.realized_return || 0) * 100;
    events.push({
      type: 'AVOIDED_CATASTROPHE',
      symbol: s.symbol,
      title: `AI prevented entry into ${s.symbol}`,
      detail: `before ${ret < 0 ? 'breakdown' : 'reversal'}`,
      proof: `capital preserved ${pctRaw(Math.abs(ret), 2)}`,
      proofTone: 'good',
    });
  });

  // 2. Intentional skips — top 2 missed
  missed.slice(0, 2).forEach((s: any) => {
    const ret = (s.realized_return || 0) * 100;
    events.push({
      type: 'INTENTIONAL_SKIP',
      symbol: s.symbol,
      title: `AI intentionally skipped ${s.symbol} ${pctRaw(ret, 1)} rally`,
      detail: 'asymmetry quality remained insufficient',
      proof: `risk-adjusted cognition · not chasing`,
      proofTone: 'neutral',
    });
  });

  // 3. Emotional suppression — meta-suppressed crowd longs (from narratives)
  const suppressedLong = narratives.find((n: any) =>
    /SUPPRESSED|HOLD/.test(n.final || '') && /LONG|BUY/.test(n.raw || ''));
  if (suppressedLong) {
    events.push({
      type: 'EMOTIONAL_SUPPRESSION',
      symbol: suppressedLong.symbol,
      title: 'Crowd turned euphoric on ' + symbolOf(suppressedLong.symbol),
      detail: 'AI refused deployment despite RAW signal',
      proof: `${suppressedLong.raw} → ${suppressedLong.final}`,
      proofTone: 'good',
    });
  }

  // 4. Capital preservation aggregate
  if (headline?.n_killed_loss_avoided && headline.n_killed_loss_avoided > 1) {
    events.push({
      type: 'CAPITAL_PRESERVATION',
      title: 'No trade was the correct trade',
      detail: `${headline.n_killed_loss_avoided} losing setups killed across recent regime`,
      proof: `+${absPct(headline.avoided_loss_pct, 2)} drawdown avoided in aggregate`,
      proofTone: 'good',
    });
  }

  // 5. Suppressed-by-regime aggregate
  if (phead?.directional_trades_killed_to_hold > 5) {
    events.push({
      type: 'SUPPRESSED_BY_REGIME',
      title: 'Meta-brain suppressed entire pipeline',
      detail: `${phead.directional_trades_killed_to_hold} directional setups → HOLD`,
      proof: `${pctRaw(phead.suppressed_alpha_pct, 2)} alpha vs RAW pipeline`,
      proofTone: phead.suppressed_alpha_pct >= 0 ? 'good' : 'bad',
    });
  }

  // 6. Timing superiority — flipped narratives
  const flipped = narratives.find((n: any) =>
    n.raw && n.final && n.raw !== n.final && n.move_pct != null);
  if (flipped) {
    events.push({
      type: 'TIMING_SUPERIORITY',
      symbol: flipped.symbol,
      title: `${symbolOf(flipped.symbol)} polarity flip caught by meta`,
      detail: `RAW said ${flipped.raw}, AI said ${flipped.final}`,
      proof: `asset moved ${pctRaw(flipped.move_pct, 2)} after override`,
      proofTone: flipped.move_pct >= 0 ? 'good' : 'bad',
    });
  }

  return events;
}

function symbolOf(s: string | null | undefined): string {
  return String(s || '').replace('USDT', '');
}

// ─── data hook ─────────────────────────────────────────────────────
async function fetchEvents(): Promise<NarrativeEvent[]> {
  if (_cache && Date.now() - _cache.ts < CACHE_MS) return _cache.events;
  try {
    const [realizedR, parallelR] = await Promise.allSettled([
      mbrainApi.realizedAttribution(2000),
      mbrainApi.parallelPortfolios(200, true),
    ]);
    const realized = realizedR.status === 'fulfilled' ? (realizedR as any).value : null;
    const parallel = parallelR.status === 'fulfilled' ? (parallelR as any).value : null;
    const events = buildEvents(realized, parallel);
    _cache = { ts: Date.now(), events };
    return events;
  } catch {
    return [];
  }
}

// ─── component ─────────────────────────────────────────────────────
interface Props {
  /** layout. 'horizontal' = horizontal scroll. 'list' = stacked vertical. */
  layout?: 'horizontal' | 'list';
  /** maximum events to show. */
  limit?: number;
  /** title above the feed. */
  title?: string;
  subtitle?: string;
  /** if true, tap on a card opens Trading OS Portfolio (proof). */
  tappable?: boolean;
}

export function AIValueNarrativeFeed({
  layout = 'horizontal',
  limit = 6,
  title = 'AI VALUE MOMENTS',
  subtitle = 'narrative · not metrics',
  tappable = true,
}: Props) {
  const colors = useColors();
  const open = useOpenInTradingOS();
  const [events, setEvents] = useState<NarrativeEvent[]>(_cache?.events ?? []);

  useEffect(() => {
    let alive = true;
    fetchEvents().then((e) => { if (alive) setEvents(e); });
    return () => { alive = false; };
  }, []);

  const shown = useMemo(() => events.slice(0, limit), [events, limit]);
  if (shown.length === 0) return null;

  const handleTap = () => { if (tappable) open(null, 'PORTFOLIO'); };

  if (layout === 'horizontal') {
    return (
      <View style={s.wrapper}>
        <View style={s.titleRow}>
          <Text style={[s.title, { color: colors.textMuted }]}>{title}</Text>
          {subtitle && (
            <Text style={[s.subtitle, { color: colors.textMuted }]}>{subtitle}</Text>
          )}
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}
          contentContainerStyle={{ paddingHorizontal: 4, gap: 10 }}>
          {shown.map((e, i) => (
            <NarrativeCard key={i} event={e} colors={colors} onPress={handleTap} compact />
          ))}
        </ScrollView>
      </View>
    );
  }

  return (
    <View style={s.wrapper}>
      <View style={s.titleRow}>
        <Text style={[s.title, { color: colors.textMuted }]}>{title}</Text>
        {subtitle && (
          <Text style={[s.subtitle, { color: colors.textMuted }]}>{subtitle}</Text>
        )}
      </View>
      {shown.map((e, i) => (
        <NarrativeCard key={i} event={e} colors={colors} onPress={handleTap} />
      ))}
    </View>
  );
}

// ─── narrative card ────────────────────────────────────────────────
function NarrativeCard({ event, colors, onPress, compact }: any) {
  const e = event as NarrativeEvent;
  const tone = e.proofTone === 'good' ? colors.buy
    : e.proofTone === 'bad' ? colors.sell
    : colors.textMuted;

  const Body = (
    <View style={[
      compact ? s.cardCompact : s.card,
      { backgroundColor: colors.surface, borderColor: tone + '40' },
    ]}>
      <View style={[s.iconWrap, { backgroundColor: tone + '20' }]}>
        <Ionicons name={ICON[e.type]} size={compact ? 14 : 16} color={tone} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={[s.cardTitle, { color: colors.textPrimary }]} numberOfLines={compact ? 2 : 3}>
          {e.title}
        </Text>
        <Text style={[s.cardDetail, { color: colors.textMuted }]} numberOfLines={compact ? 2 : 3}>
          {e.detail}
        </Text>
        <Text style={[s.cardProof, { color: tone }]} numberOfLines={2}>
          {e.proof}
        </Text>
      </View>
    </View>
  );

  if (onPress) {
    return (
      <TouchableOpacity onPress={onPress} activeOpacity={0.85}>
        {Body}
      </TouchableOpacity>
    );
  }
  return Body;
}

const s = StyleSheet.create({
  wrapper: { marginVertical: 8 },
  titleRow: {
    flexDirection: 'row', alignItems: 'baseline', gap: 8, marginBottom: 8, paddingHorizontal: 4,
  },
  title: { fontSize: 10, fontWeight: '900', letterSpacing: 1.4 },
  subtitle: { fontSize: 10, fontStyle: 'italic' },
  card: {
    flexDirection: 'row', gap: 10, padding: 12,
    borderRadius: 12, borderWidth: 1, marginBottom: 6,
  },
  cardCompact: {
    width: 240, padding: 12, borderRadius: 12, borderWidth: 1,
    flexDirection: 'row', gap: 10,
  },
  iconWrap: {
    width: 32, height: 32, borderRadius: 8,
    alignItems: 'center', justifyContent: 'center',
  },
  cardTitle: { fontSize: 12, fontWeight: '800', lineHeight: 16 },
  cardDetail: { fontSize: 10, marginTop: 3, lineHeight: 14, fontStyle: 'italic' },
  cardProof: { fontSize: 11, fontWeight: '900', marginTop: 5, letterSpacing: 0.2 },
});
