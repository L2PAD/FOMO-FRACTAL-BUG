/**
 * IntelligenceScreen — T5 · Epistemic Transparency Layer
 *
 * Renders what the system has actually learned about its own cognition
 * for the selected symbol. Strict vocabulary rules apply:
 *
 *   ALLOWED:   weak sample · emerging · usable · strong historical reliability
 *              historical disagreement · historical instability ·
 *              historically weak follow-through
 *   FORBIDDEN: good / bad / strong signal / high probability / accuracy
 *
 * Three sections:
 *   A. Historical Reliability   — all buckets for this symbol, sorted by sample
 *   B. Toxic Structures         — sample ≥ 10 AND winRate < 0.45
 *   C. Stable Structures        — sample ≥ 10 AND winRate ≥ 0.55
 *
 * NOT a heatmap. NOT a quant theater. Just what the system has held up on
 * and what it has consistently failed at.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, ActivityIndicator,
  RefreshControl, TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../../core/useColors';
import { useAssetStore } from '../../../stores/asset.store';
import { api } from '../../../services/api/api-client';

type Reliability = 'weak_sample' | 'emerging' | 'usable' | 'strong';

interface CalibrationBucket {
  symbol: string;
  side: 'LONG' | 'SHORT';
  alignmentBucket: string;
  risk: string;
  sample: number;
  wins: number;
  losses: number;
  winRate: number;
  targetRate: number;
  stopRate: number;
  avgPnlPct: number;
  avgBarsHeld: number;
  reliability: Reliability;
  updatedAt: string;
}

interface CalibrationReport {
  ok: boolean;
  symbol: string;
  totalSample: number;
  totalWins: number;
  totalLosses: number;
  overallWinRate: number;
  reliability: Reliability;
  buckets: CalibrationBucket[];
  warnings: string[];
  thresholds: { observe_only_max: number; warn_only_max: number; soft_adjust_max: number; hard_gate_min: number };
  asOf: string;
}

const RELIABILITY_LABEL: Record<Reliability, string> = {
  weak_sample: 'weak sample',
  emerging: 'emerging reliability',
  usable: 'usable reliability',
  strong: 'strong historical reliability',
};

function reliabilityColor(r: Reliability, colors: any): string {
  switch (r) {
    case 'weak_sample': return colors.textMuted || '#888';
    case 'emerging':    return '#f59e0b';
    case 'usable':      return '#3b82f6';
    case 'strong':      return colors.buy || '#22c55e';
  }
}

function fmtPct(n: number | null | undefined): string {
  if (n == null || isNaN(n)) return '—';
  return `${(n * 100).toFixed(0)}%`;
}
function fmtBucket(b: string): string {
  if (b === '0_0.33')      return 'alignment 0–0.33';
  if (b === '0.33_0.67')   return 'alignment 0.33–0.67';
  if (b === '0.67_1.0')    return 'alignment 0.67–1.0';
  return b;
}

export function IntelligenceScreen() {
  const colors = useColors();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const selectedSymbol = useAssetStore((s) => s.currentAsset) || 'BTC';
  const [report, setReport] = useState<CalibrationReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setErr(null);
      const r = await api.get(`/api/trading/intelligence/calibration?symbol=${selectedSymbol}`);
      setReport(r.data as CalibrationReport);
    } catch (e: any) {
      setErr(e?.message || 'failed to load calibration');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedSymbol]);

  useEffect(() => { void load(); }, [load]);

  const onRefresh = useCallback(() => { setRefreshing(true); void load(); }, [load]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} />
        <Text style={styles.muted}>Reading historical reliability…</Text>
      </View>
    );
  }

  if (err || !report) {
    return (
      <View style={styles.center}>
        <Ionicons name="alert-circle" size={28} color={colors.sell || '#ef4444'} />
        <Text style={styles.error}>{err || 'no calibration data'}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={() => load()}>
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const buckets = report.buckets || [];
  const toxic = buckets.filter((b) => b.sample >= 10 && b.winRate < 0.45);
  const stable = buckets.filter((b) => b.sample >= 10 && b.winRate >= 0.55);
  const overallRelCol = reliabilityColor(report.reliability, colors);

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
      testID="intelligence-screen"
    >
      {/* HEADER */}
      <View style={styles.headerRow}>
        <View>
          <Text style={styles.symbol} testID="intel-symbol">{report.symbol}</Text>
          <Text style={styles.muted}>
            what the system has held up on
          </Text>
        </View>
        <View style={[styles.relPill, { borderColor: overallRelCol }]} testID="intel-reliability-pill">
          <Text style={[styles.relPillText, { color: overallRelCol }]} numberOfLines={2}>
            {RELIABILITY_LABEL[report.reliability]}
          </Text>
        </View>
      </View>

      {/* OVERVIEW */}
      <View style={[styles.overviewCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        <View style={styles.overviewRow}>
          <Stat label="trades" value={String(report.totalSample)} colors={colors} testID="overview-sample" />
          <Stat label="wins" value={String(report.totalWins)} colors={colors} testID="overview-wins" />
          <Stat label="losses" value={String(report.totalLosses)} colors={colors} testID="overview-losses" />
          <Stat label="win rate" value={fmtPct(report.overallWinRate)} colors={colors} testID="overview-winrate" />
        </View>
        {report.warnings.length > 0 && (
          <View style={styles.warnings} testID="intel-warnings">
            {report.warnings.map((w, i) => (
              <Text key={i} style={styles.warningItem} testID={`intel-warning-${i}`}>· {w}</Text>
            ))}
          </View>
        )}
      </View>

      {/* SECTION A — Historical Reliability */}
      <SectionHeader title="A · HISTORICAL RELIABILITY" colors={colors} />
      <Text style={styles.sectionFootnote}>
        Per-bucket record. The system distinguishes WHERE its cognition has held up,
        not whether it «predicts well».
      </Text>
      {buckets.length === 0 ? (
        <EmptyBox text="No outcomes recorded yet. Reliability emerges with sample." colors={colors} />
      ) : (
        buckets.map((b, i) => (
          <BucketCard key={`hist-${i}`} bucket={b} colors={colors} testID={`bucket-${b.side}-${b.alignmentBucket}-${b.risk}`} />
        ))
      )}

      {/* SECTION B — Toxic Structures */}
      <SectionHeader title="B · TOXIC STRUCTURES" colors={colors} accent={colors.sell || '#ef4444'} />
      <Text style={styles.sectionFootnote}>
        Buckets with sample ≥ 10 where historical follow-through is consistently weak (win rate &lt; 45%).
        The verdict engine downgrades confidence here automatically.
      </Text>
      {toxic.length === 0 ? (
        <EmptyBox text="No toxic structures identified. Either sample is still emerging, or no buckets meet the threshold." colors={colors} />
      ) : (
        toxic.map((b, i) => (
          <BucketCard key={`tox-${i}`} bucket={b} colors={colors} tone="warn" testID={`toxic-${b.side}-${b.alignmentBucket}-${b.risk}`} />
        ))
      )}

      {/* SECTION C — Stable Structures */}
      <SectionHeader title="C · STABLE STRUCTURES" colors={colors} accent={colors.buy || '#22c55e'} />
      <Text style={styles.sectionFootnote}>
        Buckets with sample ≥ 10 where historical follow-through has held up (win rate ≥ 55%).
      </Text>
      {stable.length === 0 ? (
        <EmptyBox text="No stable structures yet. They require sample and sustained follow-through." colors={colors} />
      ) : (
        stable.map((b, i) => (
          <BucketCard key={`stab-${i}`} bucket={b} colors={colors} tone="ok" testID={`stable-${b.side}-${b.alignmentBucket}-${b.risk}`} />
        ))
      )}

      {/* FOOTER */}
      <Text style={styles.asOf}>
        as of {new Date(report.asOf).toLocaleTimeString()} · thresholds:
        observe&lt;{report.thresholds.observe_only_max} · warn&lt;{report.thresholds.warn_only_max}
        {' '}· adjust&lt;{report.thresholds.soft_adjust_max} · gate≥{report.thresholds.hard_gate_min}
      </Text>
    </ScrollView>
  );
}

function SectionHeader({ title, colors, accent }: { title: string; colors: any; accent?: string }) {
  return (
    <View style={[secStyles.row, accent ? { borderLeftColor: accent } : { borderLeftColor: colors.accent }]}>
      <Text style={[secStyles.title, { color: colors.text }]}>{title}</Text>
    </View>
  );
}

function EmptyBox({ text, colors }: { text: string; colors: any }) {
  return (
    <View style={[emptyStyles.box, { borderColor: colors.border }]}>
      <Text style={[emptyStyles.text, { color: colors.textMuted }]}>{text}</Text>
    </View>
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

function BucketCard({ bucket: b, colors, tone, testID }: {
  bucket: CalibrationBucket; colors: any; tone?: 'warn' | 'ok'; testID?: string;
}) {
  const relCol = reliabilityColor(b.reliability, colors);
  const accent = tone === 'warn' ? colors.sell : tone === 'ok' ? colors.buy : colors.textMuted;

  // Compose the honest natural-language status
  let status: string;
  if (b.sample < 5) {
    status = 'sample still limited';
  } else if (b.sample < 10) {
    status = 'reliability emerging';
  } else if (b.winRate < 0.40) {
    status = 'historically weak follow-through';
  } else if (b.winRate < 0.50) {
    status = 'historical instability';
  } else if (b.winRate < 0.60) {
    status = 'mixed historical follow-through';
  } else {
    status = 'historical follow-through has held up';
  }

  return (
    <View style={[bucketStyles.card, { backgroundColor: colors.surface, borderColor: colors.border }]} testID={testID}>
      <View style={bucketStyles.headerRow}>
        <View style={bucketStyles.headerLeft}>
          <View style={[bucketStyles.sidePill, { backgroundColor: b.side === 'LONG' ? (colors.buy || '#22c55e') : (colors.sell || '#ef4444') }]}>
            <Text style={bucketStyles.sidePillText}>{b.side}</Text>
          </View>
          <Text style={[bucketStyles.bucketLabel, { color: colors.text }]} numberOfLines={1}>{fmtBucket(b.alignmentBucket)}</Text>
          <Text style={[bucketStyles.riskLabel, { color: colors.textMuted }]} numberOfLines={1}>· risk {b.risk}</Text>
        </View>
        <Text
          style={[bucketStyles.relLabel, { color: relCol }]}
          numberOfLines={2}
        >
          {RELIABILITY_LABEL[b.reliability]}
        </Text>
      </View>

      <View style={bucketStyles.metrics}>
        <Metric label="trades" value={String(b.sample)} colors={colors} />
        <Metric label="win rate" value={fmtPct(b.winRate)} colors={colors} accent={accent} />
        <Metric label="target reach" value={fmtPct(b.targetRate)} colors={colors} />
        <Metric label="avg pnl" value={`${(b.avgPnlPct >= 0 ? '+' : '')}${b.avgPnlPct.toFixed(2)}%`} colors={colors} accent={b.avgPnlPct >= 0 ? colors.buy : colors.sell} />
        <Metric label="avg hold" value={`${Math.round(b.avgBarsHeld)} bars`} colors={colors} />
      </View>

      <Text style={[bucketStyles.statusLine, { color: colors.textMuted, fontStyle: 'italic' }]}>
        status: <Text style={{ color: relCol }}>{status}</Text>
      </Text>
    </View>
  );
}

function Metric({ label, value, colors, accent }: { label: string; value: string; colors: any; accent?: string }) {
  return (
    <View style={bucketStyles.metric}>
      <Text style={[bucketStyles.metricLabel, { color: colors.textMuted }]}>{label}</Text>
      <Text style={[bucketStyles.metricValue, { color: accent || colors.text }]}>{value}</Text>
    </View>
  );
}

const secStyles = StyleSheet.create({
  row: { borderLeftWidth: 3, paddingLeft: 10, paddingVertical: 6, marginTop: 18, marginBottom: 4 },
  title: { fontSize: 12, letterSpacing: 1.5, fontWeight: '800' },
});
const emptyStyles = StyleSheet.create({
  box: { borderWidth: 1, borderStyle: 'dashed', borderRadius: 10, padding: 14, marginBottom: 10 },
  text: { fontSize: 12, lineHeight: 17, textAlign: 'center' },
});
const statStyles = StyleSheet.create({
  stat: { flex: 1, alignItems: 'flex-start' },
  label: { fontSize: 10, letterSpacing: 1, textTransform: 'uppercase' },
  value: { fontSize: 16, fontWeight: '800', marginTop: 2 },
});
const bucketStyles = StyleSheet.create({
  card: { borderWidth: 1, borderRadius: 12, padding: 14, marginBottom: 8 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10, gap: 8, flexWrap: 'wrap' },
  headerLeft: { flexDirection: 'row', alignItems: 'center', gap: 8, flexShrink: 1, minWidth: 0 },
  sidePill: { paddingHorizontal: 7, paddingVertical: 2, borderRadius: 5 },
  sidePillText: { color: '#fff', fontSize: 10, fontWeight: '800', letterSpacing: 1 },
  bucketLabel: { fontSize: 13, fontWeight: '700', flexShrink: 1 },
  riskLabel: { fontSize: 11, flexShrink: 1 },
  relLabel: { fontSize: 10, fontWeight: '700', textTransform: 'lowercase', letterSpacing: 0.3, flexShrink: 1, maxWidth: 130, textAlign: 'right' },
  metrics: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginBottom: 8 },
  metric: { minWidth: 60 },
  metricLabel: { fontSize: 9, letterSpacing: 1, textTransform: 'uppercase' },
  metricValue: { fontSize: 14, fontWeight: '700', marginTop: 2 },
  statusLine: { fontSize: 11 },
});

const makeStyles = (colors: any) =>
  StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background },
    content: { padding: 16, paddingBottom: 80 },
    center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background, gap: 10 },
    muted: { color: colors.textMuted, fontSize: 12 },
    error: { color: colors.sell || '#ef4444', fontSize: 14, marginTop: 8 },
    retryBtn: { paddingHorizontal: 18, paddingVertical: 8, borderRadius: 8, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, marginTop: 10 },
    retryText: { color: colors.text, fontWeight: '600' },
    headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14, gap: 10, flexWrap: 'wrap' },
    symbol: { fontSize: 22, fontWeight: '800', color: colors.text, letterSpacing: 0.5 },
    relPill: { borderWidth: 1, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 16, flexShrink: 1, maxWidth: 220 },
    relPillText: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5, textAlign: 'center' },
    overviewCard: { borderWidth: 1, borderRadius: 12, padding: 14, marginBottom: 8 },
    overviewRow: { flexDirection: 'row', gap: 6 },
    warnings: { marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.border },
    warningItem: { color: colors.textMuted, fontSize: 11, lineHeight: 16 },
    sectionFootnote: { color: colors.textMuted, fontSize: 11, lineHeight: 16, marginBottom: 8, paddingHorizontal: 4 },
    asOf: { color: colors.textMuted, fontSize: 10, textAlign: 'center', marginTop: 16, lineHeight: 14 },
  });
