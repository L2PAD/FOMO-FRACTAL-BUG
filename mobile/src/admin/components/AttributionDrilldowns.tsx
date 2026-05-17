/**
 * /admin/attribution — T11.2B — Drilldown components.
 *
 * Investigative-tier panels for the Performance Attribution
 * Observatory.  Architectural rules enforced visually:
 *
 *   1. COLLAPSED BY DEFAULT — first-fold of /admin/attribution is the
 *      epistemic observatory (T11.2A).  Drilldowns are secondary.
 *      Operators must intentionally OPEN a drilldown — never landed in.
 *
 *   2. SUBDUED TONE — drilldown headers use textSecondary, dividers
 *      sit on bgSecondary, value cells use textPrimary but NEVER any
 *      green/success palette for wins.  Forensic, not marketing.
 *
 *   3. NO CTA SURFACE — there is no "tune this rule", "set band",
 *      "apply confidence threshold".  Drilldowns are read-only by
 *      design AND by visual affordance.
 *
 *   4. LAZY LOAD — payloads are fetched on first expand only.  Closing
 *      and re-opening does NOT re-fetch (data is immutable so a
 *      single read per session suffices unless the window changes).
 *
 *   5. WINDOW PROPAGATION — drilldowns receive the same window from
 *      the parent (no independent window selectors).  Single canonical
 *      time-range across the whole surface.
 *
 *   6. FRAMING NOTES RENDERED VERBATIM — each drilldown ends with the
 *      backend's framingNote shown in italic; this is what prevents
 *      hindsight-bias UX.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { View, Text, Pressable, ActivityIndicator, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { adminApi } from '../api/adminClient';

type AttrWindow = '7d' | '30d' | '90d' | 'all';

const fmtUsd = (n: number | null | undefined) =>
  typeof n === 'number'
    ? `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : '—';
const fmtNum = (n: number | null | undefined) =>
  typeof n === 'number' ? n.toLocaleString('en-US') : '—';
const fmtPct = (n: number | null | undefined) =>
  typeof n === 'number' ? `${n.toFixed(2)}%` : '—';
const fmtPctSigned = (n: number | null | undefined) => {
  if (typeof n !== 'number') return '—';
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(2)}%`;
};

// ── Shared collapsible shell ───────────────────────────────────────────

interface DrilldownShellProps<T> {
  colors: any;
  title: string;
  description: string;
  fetcher: () => Promise<T>;
  window: AttrWindow;
  testID?: string;
  children: (data: T) => React.ReactNode;
}

export function DrilldownShell<T>({
  colors, title, description, fetcher, window: windowSel, testID, children,
}: DrilldownShellProps<T>) {
  const [expanded, setExpanded] = useState(false);
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Track which window the cached data was for; refetch if window changes.
  const cachedWindow = useRef<AttrWindow | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await fetcher();
      setData(d);
      cachedWindow.current = windowSel;
    } catch (e: any) {
      setError(
        e?.response?.data?.detail?.error ||
        e?.message ||
        'Failed to load drilldown',
      );
    } finally {
      setLoading(false);
    }
  }, [fetcher, windowSel]);

  // First expand → fetch.  Subsequent toggles → no refetch unless
  // window changed beneath us.
  useEffect(() => {
    if (expanded && (data === null || cachedWindow.current !== windowSel)) {
      load();
    }
  }, [expanded, windowSel, data, load]);

  // If the parent's window changes while we're expanded, refetch.
  useEffect(() => {
    if (expanded && cachedWindow.current !== null && cachedWindow.current !== windowSel) {
      setData(null);
    }
  }, [windowSel, expanded]);

  return (
    <View
      style={[styles.shell, { backgroundColor: colors.surface, borderColor: colors.border }]}
      testID={testID}
    >
      <Pressable
        onPress={() => setExpanded(e => !e)}
        style={({ pressed }) => [
          styles.shellHeader,
          {
            backgroundColor: pressed ? colors.surfaceHover : 'transparent',
            borderBottomColor: expanded ? colors.border : 'transparent',
          },
        ]}
        testID={testID ? `${testID}-toggle` : undefined}
      >
        <Ionicons
          name={expanded ? 'chevron-down' : 'chevron-forward'}
          size={14}
          color={colors.textMuted}
        />
        <View style={{ flex: 1 }}>
          <Text style={[styles.shellTitle, { color: colors.textSecondary }]}>{title}</Text>
          <Text style={[styles.shellDesc, { color: colors.textMuted }]}>{description}</Text>
        </View>
        {loading && expanded && <ActivityIndicator size="small" color={colors.textMuted} />}
      </Pressable>
      {expanded && (
        <View style={styles.shellBody}>
          {error && (
            <Text style={[styles.errText, { color: colors.danger }]} testID="drilldown-error">
              {error}
            </Text>
          )}
          {data !== null && !loading && children(data)}
        </View>
      )}
    </View>
  );
}

// ── Per-asset drilldown ────────────────────────────────────────────────

interface AssetsPayload {
  ok: boolean;
  pipelineVersion: string;
  window: AttrWindow;
  n: number;
  rows: Array<{
    symbol: string;
    outcomes: any;
    gateBlocks: any;
    lineage: { outcomesInWindow: number; rawSamples: number; lineageCompletePct: number };
  }>;
  framingNote: string;
}

export function PerAssetDrilldown({ colors, window: windowSel }: { colors: any; window: AttrWindow }) {
  return (
    <DrilldownShell<AssetsPayload>
      colors={colors}
      title="Per-asset drilldown"
      description="Investigative · is one asset dominating aggregate, or lineage coverage uneven across symbols?"
      window={windowSel}
      fetcher={() => adminApi.attributionAssets(windowSel)}
      testID="drilldown-assets"
    >
      {(d) => (
        <View>
          <View style={[styles.tableHead, { borderBottomColor: colors.border }]}>
            <Text style={[styles.thAsset, { color: colors.textMuted }]}>SYMBOL</Text>
            <Text style={[styles.thNum, { color: colors.textMuted }]}>TRADES</Text>
            <Text style={[styles.thNum, { color: colors.textMuted }]}>HIT-RATE</Text>
            <Text style={[styles.thNum, { color: colors.textMuted }]}>MEAN RET %</Text>
            <Text style={[styles.thNum, { color: colors.textMuted }]}>CUM PnL</Text>
            <Text style={[styles.thNum, { color: colors.textMuted }]}>MAX DD %</Text>
            <Text style={[styles.thNum, { color: colors.textMuted }]}>GATE BLOCKS</Text>
            <Text style={[styles.thNum, { color: colors.textMuted }]}>LINEAGE %</Text>
          </View>
          {d.rows.length === 0 ? (
            <Text style={[styles.empty, { color: colors.textMuted }]}>
              No assets observed in this window.
            </Text>
          ) : (
            d.rows.map((r) => (
              <View key={r.symbol} style={[styles.tableRow, { borderBottomColor: colors.border }]}>
                <Text style={[styles.tdAsset, { color: colors.textPrimary }]}>{r.symbol}</Text>
                <Text style={[styles.tdNum, { color: colors.textPrimary }]}>{fmtNum(r.outcomes.tradeCount)}</Text>
                <Text style={[styles.tdNum, { color: colors.textPrimary }]}>{fmtPct(r.outcomes.hitRatePct)}</Text>
                <Text style={[styles.tdNum, { color: colors.textPrimary }]}>{fmtPctSigned(r.outcomes.meanReturnPct)}</Text>
                <Text style={[styles.tdNum, { color: colors.textPrimary }]}>{fmtUsd(r.outcomes.cumulativePnlUsd)}</Text>
                <Text style={[styles.tdNum, { color: colors.textPrimary }]}>{fmtPct(r.outcomes.maxDrawdownPct)}</Text>
                <Text style={[styles.tdNum, { color: colors.textPrimary }]}>{fmtNum(r.gateBlocks?.blockedCount ?? 0)}</Text>
                <Text style={[styles.tdNum, { color: colors.textPrimary }]}>{fmtPct(r.lineage.lineageCompletePct)}</Text>
              </View>
            ))
          )}
          <Text style={[styles.frame, { color: colors.textMuted, borderTopColor: colors.border }]}>
            {d.framingNote}
          </Text>
        </View>
      )}
    </DrilldownShell>
  );
}

// ── Gate-rule breakdown ────────────────────────────────────────────────

interface RulePayload {
  ok: boolean;
  pipelineVersion: string;
  totalBlocks: number;
  rules: Array<{
    rule: string;
    count: number;
    preventedNotionalUsd: number;
    topSymbols: Array<{ symbol: string; count: number }>;
    recentExamples: Array<{ decisionId?: string; symbol?: string; ts?: string; lineageId?: string | null }>;
  }>;
  framingNote: string;
}

const RULE_LABEL: Record<string, string> = {
  drawdownBreaker:     'Drawdown breaker',
  cooldown:            'Loss-streak cooldown',
  correlationCluster:  'Correlation cluster',
  sameSideExposure:    'Same-side exposure',
  exposureCap:         'Exposure cap',
};

export function GateRuleDrilldown({ colors, window: windowSel }: { colors: any; window: AttrWindow }) {
  return (
    <DrilldownShell<RulePayload>
      colors={colors}
      title="Gate-rule breakdown"
      description="Per-rule frequency · prevented notional · top-symbols · recent examples (no profitability scoring)."
      window={windowSel}
      fetcher={() => adminApi.attributionGateRuleBreakdown(windowSel)}
      testID="drilldown-rules"
    >
      {(d) => (
        <View>
          <Text style={[styles.totalLine, { color: colors.textSecondary }]}>
            Total observed blocks in window: <Text style={{ color: colors.textPrimary, fontFamily: 'monospace' }}>{fmtNum(d.totalBlocks)}</Text>
          </Text>
          {d.rules.map((r) => (
            <View key={r.rule} style={[styles.ruleBlock, { borderColor: colors.border }]}>
              <View style={styles.ruleHead}>
                <Text style={[styles.ruleName, { color: colors.textPrimary }]}>
                  {RULE_LABEL[r.rule] || r.rule}
                </Text>
                <Text style={[styles.ruleCount, { color: colors.textSecondary }]}>
                  {fmtNum(r.count)} fired · {fmtUsd(r.preventedNotionalUsd)} prevented
                </Text>
              </View>
              {r.topSymbols.length > 0 && (
                <View style={styles.ruleSection}>
                  <Text style={[styles.ruleSubLabel, { color: colors.textMuted }]}>TOP SYMBOLS</Text>
                  <View style={styles.pillRow}>
                    {r.topSymbols.map(s => (
                      <View key={s.symbol} style={[styles.symPill, { backgroundColor: colors.bgSecondary, borderColor: colors.border }]}>
                        <Text style={[styles.symPillText, { color: colors.textPrimary }]}>{s.symbol}</Text>
                        <Text style={[styles.symPillCount, { color: colors.textMuted }]}>×{s.count}</Text>
                      </View>
                    ))}
                  </View>
                </View>
              )}
              {r.recentExamples.length > 0 && (
                <View style={styles.ruleSection}>
                  <Text style={[styles.ruleSubLabel, { color: colors.textMuted }]}>RECENT EXAMPLES</Text>
                  {r.recentExamples.map((e, i) => (
                    <Text
                      key={e.decisionId || `${e.ts}-${i}`}
                      style={[styles.exampleLine, { color: colors.textSecondary }]}
                      numberOfLines={1}
                    >
                      {e.ts ? new Date(e.ts).toLocaleString() : '—'} · {e.symbol || '—'} · {e.decisionId || '—'}
                    </Text>
                  ))}
                </View>
              )}
            </View>
          ))}
          <Text style={[styles.frame, { color: colors.textMuted, borderTopColor: colors.border }]}>
            {d.framingNote}
          </Text>
        </View>
      )}
    </DrilldownShell>
  );
}

// ── Confidence distribution ────────────────────────────────────────────

interface ConfidencePayload {
  ok: boolean;
  pipelineVersion: string;
  totalOutcomes: number;
  buckets: Array<{
    bucket: 'low' | 'mid' | 'high' | 'unknown';
    sharePct: number;
    tradeCount: number;
    winCount: number;
    lossCount: number;
    hitRatePct: number;
    meanReturnPct: number;
    cumulativePnlUsd: number;
  }>;
  framingNote: string;
}

const BUCKET_LABEL: Record<string, string> = {
  low:     'low (<0.40)',
  mid:     'mid (0.40-0.70)',
  high:    'high (≥0.70)',
  unknown: 'unknown (pre-T11.1b)',
};
const BUCKET_ORDER = ['low', 'mid', 'high', 'unknown'] as const;

export function ConfidenceDrilldown({ colors, window: windowSel }: { colors: any; window: AttrWindow }) {
  return (
    <DrilldownShell<ConfidencePayload>
      colors={colors}
      title="Confidence distribution"
      description="Outcome aggregate per cognition confidence bucket · surfaces calibration alignment, not optimisation target."
      window={windowSel}
      fetcher={() => adminApi.attributionConfidenceDistribution(windowSel)}
      testID="drilldown-confidence"
    >
      {(d) => {
        const orderedBuckets = BUCKET_ORDER
          .map(label => d.buckets.find(b => b.bucket === label))
          .filter(Boolean) as ConfidencePayload['buckets'];
        return (
          <View>
            <Text style={[styles.totalLine, { color: colors.textSecondary }]}>
              Total outcomes in window: <Text style={{ color: colors.textPrimary, fontFamily: 'monospace' }}>{fmtNum(d.totalOutcomes)}</Text>
            </Text>
            <View style={[styles.tableHead, { borderBottomColor: colors.border }]}>
              <Text style={[styles.thBucket, { color: colors.textMuted }]}>BUCKET</Text>
              <Text style={[styles.thNum, { color: colors.textMuted }]}>SHARE</Text>
              <Text style={[styles.thNum, { color: colors.textMuted }]}>TRADES</Text>
              <Text style={[styles.thNum, { color: colors.textMuted }]}>HIT-RATE</Text>
              <Text style={[styles.thNum, { color: colors.textMuted }]}>MEAN RET %</Text>
              <Text style={[styles.thNum, { color: colors.textMuted }]}>CUM PnL</Text>
            </View>
            {orderedBuckets.map((b) => (
              <View key={b.bucket} style={[styles.tableRow, { borderBottomColor: colors.border }]}>
                <Text style={[styles.tdBucket, { color: colors.textPrimary }]}>{BUCKET_LABEL[b.bucket]}</Text>
                <Text style={[styles.tdNum, { color: colors.textPrimary }]}>{fmtPct(b.sharePct)}</Text>
                <Text style={[styles.tdNum, { color: colors.textPrimary }]}>{fmtNum(b.tradeCount)}</Text>
                <Text style={[styles.tdNum, { color: colors.textPrimary }]}>{fmtPct(b.hitRatePct)}</Text>
                <Text style={[styles.tdNum, { color: colors.textPrimary }]}>{fmtPctSigned(b.meanReturnPct)}</Text>
                <Text style={[styles.tdNum, { color: colors.textPrimary }]}>{fmtUsd(b.cumulativePnlUsd)}</Text>
              </View>
            ))}
            <Text style={[styles.frame, { color: colors.textMuted, borderTopColor: colors.border }]}>
              {d.framingNote}
            </Text>
          </View>
        );
      }}
    </DrilldownShell>
  );
}

// ── Exposure histograms ────────────────────────────────────────────────

interface ExposurePayload {
  ok: boolean;
  pipelineVersion: string;
  totalOutcomes: number;
  bands: Array<{
    band: string;
    tradeCount: number;
    winCount: number;
    lossCount: number;
    hitRatePct: number;
    meanReturnPct: number;
    cumulativePnlUsd: number;
    meanSizeUsd: number;
  }>;
  framingNote: string;
}

export function ExposureDrilldown({ colors, window: windowSel }: { colors: any; window: AttrWindow }) {
  return (
    <DrilldownShell<ExposurePayload>
      colors={colors}
      title="Exposure histograms"
      description="Outcome aggregate per notional band · surfaces downstream effect of adaptive sizing."
      window={windowSel}
      fetcher={() => adminApi.attributionExposureHistograms(windowSel)}
      testID="drilldown-exposure"
    >
      {(d) => {
        const maxTradeCount = Math.max(1, ...d.bands.map(b => b.tradeCount));
        return (
          <View>
            <Text style={[styles.totalLine, { color: colors.textSecondary }]}>
              Total outcomes in window: <Text style={{ color: colors.textPrimary, fontFamily: 'monospace' }}>{fmtNum(d.totalOutcomes)}</Text>
            </Text>
            <View style={[styles.tableHead, { borderBottomColor: colors.border }]}>
              <Text style={[styles.thBand, { color: colors.textMuted }]}>BAND ($)</Text>
              <Text style={[styles.thNum, { color: colors.textMuted }]}>TRADES</Text>
              <Text style={[styles.thNum, { color: colors.textMuted }]}>HIT-RATE</Text>
              <Text style={[styles.thNum, { color: colors.textMuted }]}>MEAN RET %</Text>
              <Text style={[styles.thNum, { color: colors.textMuted }]}>CUM PnL</Text>
              <Text style={[styles.thNum, { color: colors.textMuted }]}>MEAN SIZE</Text>
            </View>
            {d.bands.map((b) => {
              const widthPct = (b.tradeCount / maxTradeCount) * 100;
              return (
                <View key={b.band}>
                  <View style={[styles.tableRow, { borderBottomColor: colors.border }]}>
                    <Text style={[styles.tdBand, { color: colors.textPrimary }]}>{b.band}</Text>
                    <Text style={[styles.tdNum, { color: colors.textPrimary }]}>{fmtNum(b.tradeCount)}</Text>
                    <Text style={[styles.tdNum, { color: colors.textPrimary }]}>{fmtPct(b.hitRatePct)}</Text>
                    <Text style={[styles.tdNum, { color: colors.textPrimary }]}>{fmtPctSigned(b.meanReturnPct)}</Text>
                    <Text style={[styles.tdNum, { color: colors.textPrimary }]}>{fmtUsd(b.cumulativePnlUsd)}</Text>
                    <Text style={[styles.tdNum, { color: colors.textPrimary }]}>{fmtUsd(b.meanSizeUsd)}</Text>
                  </View>
                  {/* Subtle distribution bar — uses textMuted, not accent, so it doesn't read as a 'best band' highlight */}
                  <View style={[styles.histBarTrack, { backgroundColor: colors.bgSecondary }]}>
                    <View style={[styles.histBarFill, { width: `${widthPct}%`, backgroundColor: colors.textMuted }]} />
                  </View>
                </View>
              );
            })}
            <Text style={[styles.frame, { color: colors.textMuted, borderTopColor: colors.border }]}>
              {d.framingNote}
            </Text>
          </View>
        );
      }}
    </DrilldownShell>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  shell: { borderWidth: 1, borderRadius: 10, overflow: 'hidden' },
  shellHeader: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 10,
    paddingHorizontal: 14, paddingVertical: 12, borderBottomWidth: 1,
  },
  shellTitle: { fontSize: 13, fontWeight: '700', letterSpacing: 0.2 },
  shellDesc: { fontSize: 11, lineHeight: 15, marginTop: 2 },
  shellBody: { paddingHorizontal: 14, paddingVertical: 12, gap: 8 },

  errText: { fontSize: 12, fontStyle: 'italic' },

  totalLine: { fontSize: 12, marginBottom: 8 },

  tableHead: { flexDirection: 'row', borderBottomWidth: 1, paddingVertical: 8, alignItems: 'center' },
  tableRow:  { flexDirection: 'row', borderBottomWidth: 1, paddingVertical: 8, alignItems: 'center' },
  thAsset:   { flex: 1.2, minWidth: 80,  fontSize: 10, fontWeight: '700', letterSpacing: 1 },
  thBucket:  { flex: 1.6, minWidth: 130, fontSize: 10, fontWeight: '700', letterSpacing: 1 },
  thBand:    { flex: 1.2, minWidth: 90,  fontSize: 10, fontWeight: '700', letterSpacing: 1 },
  thNum:     { flex: 1.0, minWidth: 80,  fontSize: 10, fontWeight: '700', letterSpacing: 1, textAlign: 'right' },
  tdAsset:   { flex: 1.2, minWidth: 80,  fontSize: 12, fontFamily: 'monospace', fontWeight: '700' },
  tdBucket:  { flex: 1.6, minWidth: 130, fontSize: 12 },
  tdBand:    { flex: 1.2, minWidth: 90,  fontSize: 12, fontFamily: 'monospace' },
  tdNum:     { flex: 1.0, minWidth: 80,  fontSize: 12, fontFamily: 'monospace', textAlign: 'right' },

  empty: { fontSize: 12, fontStyle: 'italic', textAlign: 'center', padding: 16 },

  // Histogram bar
  histBarTrack: { height: 3, borderRadius: 2, overflow: 'hidden', marginBottom: 8 },
  histBarFill:  { height: '100%', borderRadius: 2 },

  // Rule breakdown
  ruleBlock:   { borderWidth: 1, borderRadius: 8, padding: 12, marginVertical: 4, gap: 10 },
  ruleHead:    { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' },
  ruleName:    { fontSize: 13, fontWeight: '700' },
  ruleCount:   { fontSize: 12, fontFamily: 'monospace' },
  ruleSection: { gap: 4 },
  ruleSubLabel:{ fontSize: 9, fontWeight: '700', letterSpacing: 1.2 },
  pillRow:     { flexDirection: 'row', gap: 6, flexWrap: 'wrap' },
  symPill: {
    flexDirection: 'row', alignItems: 'baseline', gap: 6,
    paddingHorizontal: 10, paddingVertical: 4, borderRadius: 6, borderWidth: 1,
  },
  symPillText:  { fontSize: 11, fontWeight: '700', fontFamily: 'monospace' },
  symPillCount: { fontSize: 10 },
  exampleLine:  { fontSize: 11, fontFamily: 'monospace', lineHeight: 15 },

  frame: { fontSize: 11, fontStyle: 'italic', lineHeight: 16, marginTop: 12, paddingTop: 10, borderTopWidth: 1 },
});
