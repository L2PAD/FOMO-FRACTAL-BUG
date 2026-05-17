/**
 * DeploymentScreen — T2 UI wiring for Native Trading Runtime.
 *
 * Replaces the old "pending trigger / TBD" theatre with real verdict from
 * GET /api/trading/verdict/{symbol}. Submit calls /api/trading/paper/submit.
 *
 * Acceptance:
 *   • WAIT → show blockedBy + reasons, NO Submit button
 *   • LONG/SHORT → show entry/stop/target/RR/risk/size + Submit Paper button
 *   • Module alignment (TA / Sentiment / Fractal) visible at a glance
 *   • All numbers are live from backend, zero placeholders.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl, Alert, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../../core/useColors';
import { useAssetStore } from '../../../stores/asset.store';
import {
  tradingRuntimeApi,
  TradingVerdict,
  TradingAction,
} from '../../../services/api/trading-runtime-api';

function fmtNum(n: number | null | undefined, decimals = 2): string {
  if (n == null || isNaN(n)) return '—';
  return n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtConf(n: number | null | undefined): string {
  if (n == null) return '—';
  return `${(n * 100).toFixed(0)}%`;
}

function actionColor(action: TradingAction, c: any): string {
  if (action === 'LONG') return c.buy || '#22c55e';
  if (action === 'SHORT') return c.sell || '#ef4444';
  return c.textMuted || '#888';
}

export function TradeScreen() {
  const colors = useColors();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const selectedSymbol = useAssetStore((s) => s.currentAsset) || 'BTC';

  const [verdict, setVerdict] = useState<TradingVerdict | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setErr(null);
      const v = await tradingRuntimeApi.verdict(selectedSymbol);
      setVerdict(v);
    } catch (e: any) {
      setErr(e?.message || 'failed to load verdict');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedSymbol]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    const id = setInterval(load, 30_000); // auto-refresh every 30s
    return () => clearInterval(id);
  }, [load]);

  const onRefresh = useCallback(() => { setRefreshing(true); void load(); }, [load]);

  const onSubmitPaper = useCallback(async () => {
    if (!verdict || verdict.action === 'WAIT') return;
    const confirm = () => new Promise<boolean>((resolve) => {
      if (Platform.OS === 'web') {
        const ok = window.confirm(
          `Submit PAPER ${verdict.action} ${verdict.symbol}\n` +
          `Entry $${fmtNum(verdict.entry)} · Stop $${fmtNum(verdict.stop)} · Target $${fmtNum(verdict.target)}\n` +
          `Size $${fmtNum(verdict.sizeUsd, 2)} · R:R ${verdict.rr?.toFixed(2) ?? '—'}`
        );
        resolve(ok);
      } else {
        Alert.alert(
          `Submit Paper ${verdict.action}`,
          `${verdict.symbol} · entry $${fmtNum(verdict.entry)} · size $${fmtNum(verdict.sizeUsd, 2)}`,
          [
            { text: 'Cancel', style: 'cancel', onPress: () => resolve(false) },
            { text: 'Submit', style: 'default', onPress: () => resolve(true) },
          ]
        );
      }
    });
    const ok = await confirm();
    if (!ok) return;
    setSubmitting(true);
    try {
      const res = await tradingRuntimeApi.submit(verdict.symbol);
      if (res.ok) {
        Alert.alert?.('Paper position opened', `${res.symbol} ${res.side} · ${res.positionId}`);
        if (Platform.OS === 'web') window.alert(`Paper position opened\n${res.symbol} ${res.side}\nID: ${res.positionId}`);
      } else {
        const msg = `${res.error || 'submit failed'}${res.detail ? '\n' + res.detail : ''}`;
        if (Platform.OS === 'web') window.alert(msg);
        else Alert.alert('Submit failed', msg);
      }
    } catch (e: any) {
      const msg = e?.message || 'submit error';
      if (Platform.OS === 'web') window.alert(msg);
      else Alert.alert('Submit error', msg);
    } finally {
      setSubmitting(false);
      void load();
    }
  }, [verdict, load]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} />
        <Text style={styles.muted} testID="deployment-loading">Loading trading verdict…</Text>
      </View>
    );
  }

  if (err || !verdict) {
    return (
      <View style={styles.center}>
        <Ionicons name="alert-circle" size={28} color={colors.sell || '#ef4444'} />
        <Text style={styles.error} testID="deployment-error">{err || 'no verdict'}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={() => load()} testID="deployment-retry">
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const dCol = actionColor(verdict.action, colors);
  const isWait = verdict.action === 'WAIT';

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
      testID="deployment-screen"
    >
      {/* HEADER */}
      <View style={styles.headerRow}>
        <View>
          <Text style={styles.symbol} testID="deployment-symbol">{verdict.symbol}</Text>
          <Text style={styles.muted}>
            current ${fmtNum(verdict.currentPrice)} · confidence {fmtConf(verdict.confidence)}
          </Text>
        </View>
        <View style={[styles.actionPill, { backgroundColor: dCol }]} testID="deployment-action">
          <Text style={styles.actionPillText}>{verdict.action}</Text>
        </View>
      </View>

      {/* MODULE ALIGNMENT */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>MODULE ALIGNMENT</Text>
        <View style={styles.alignRow}>
          <AlignChip label="TA" bias={verdict.alignment.ta} conf={verdict.moduleConfidence.ta} colors={colors} />
          <AlignChip label="Sentiment" bias={verdict.alignment.sentiment} conf={verdict.moduleConfidence.sentiment} colors={colors} />
          <AlignChip label="Fractal" bias={verdict.alignment.fractal} conf={verdict.moduleConfidence.fractal} colors={colors} />
        </View>
        <Text style={styles.alignFootnote}>
          {verdict.alignment.longVotes}/3 LONG · {verdict.alignment.shortVotes}/3 SHORT · {verdict.alignment.waitVotes}/3 WAIT
          {'  '}· alignment score {(verdict.alignment.score * 100).toFixed(0)}%
        </Text>
      </View>

      {/* CALIBRATION LAYER — modifier between alignment and structure */}
      {verdict.calibration && (
        <CalibrationSection
          verdict={verdict}
          colors={colors}
        />
      )}

      {/* EXECUTION STRUCTURE — only when there's a directional verdict OR price is known */}
      {!isWait && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>EXECUTION STRUCTURE</Text>
          <View style={[styles.structure, { borderColor: colors.border, backgroundColor: colors.surface }]}>
            <StructRow label="entry" value={`$${fmtNum(verdict.entry)}`} colors={colors} testID="row-entry" />
            <StructRow label="stop" value={`$${fmtNum(verdict.stop)}`} colors={colors} testID="row-stop" />
            <StructRow label="target" value={`$${fmtNum(verdict.target)}`} colors={colors} testID="row-target" />
            <StructRow label="R:R" value={verdict.rr != null ? `${verdict.rr.toFixed(2)} : 1` : '—'} colors={colors} testID="row-rr" />
            <StructRow label="risk" value={verdict.risk} colors={colors}
              tone={verdict.risk === 'HIGH' ? 'warn' : 'normal'} testID="row-risk" />
            <StructRow label="size" value={`$${fmtNum(verdict.sizeUsd, 2)} · paper`} colors={colors} last testID="row-size" />
          </View>
        </View>
      )}

      {/* T8 — ADAPTIVE SIZING (epistemic transparency on capital restraint) */}
      {verdict.sizing && (
        <AdaptiveSizingSection verdict={verdict} colors={colors} />
      )}

      {/* T9 — PORTFOLIO GATE (exposure caps · correlation · drawdown · cooldown) */}
      {verdict.portfolioGate && (
        <PortfolioGateSection verdict={verdict} colors={colors} />
      )}

      {/* BLOCKED — show blockers prominently */}
      {isWait && verdict.blockedBy.length > 0 && (
        <View style={[styles.section, styles.blockedBox, { borderColor: colors.border, backgroundColor: colors.surface }]} testID="deployment-blocked">
          <View style={styles.blockedHeader}>
            <Ionicons name="lock-closed" size={16} color={colors.textMuted} />
            <Text style={styles.blockedTitle}>BLOCKED</Text>
          </View>
          {verdict.blockedBy.map((b, i) => (
            <Text key={i} style={styles.blockedItem} testID={`blocked-item-${i}`}>· {b}</Text>
          ))}
          {verdict.currentPrice && (
            <View style={{ marginTop: 8 }}>
              <Text style={styles.muted}>current ${fmtNum(verdict.currentPrice)}</Text>
              {verdict.support != null && verdict.resistance != null && (
                <Text style={styles.muted}>
                  range: ${fmtNum(verdict.support)} support · ${fmtNum(verdict.resistance)} resistance
                </Text>
              )}
            </View>
          )}
        </View>
      )}

      {/* REASONS */}
      {verdict.reasons.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>REASONS</Text>
          {verdict.reasons.map((r, i) => (
            <Text key={i} style={styles.reasonItem} testID={`reason-item-${i}`}>· {r}</Text>
          ))}
        </View>
      )}

      {/* SUBMIT */}
      {!isWait ? (
        <TouchableOpacity
          testID="deployment-submit-btn"
          style={[styles.submitBtn, { backgroundColor: dCol }]}
          onPress={onSubmitPaper}
          disabled={submitting}
          activeOpacity={0.85}
        >
          {submitting ? <ActivityIndicator color="#fff" /> : (
            <>
              <Ionicons name="flash" size={18} color="#fff" />
              <Text style={styles.submitText}>SUBMIT PAPER {verdict.action}</Text>
            </>
          )}
        </TouchableOpacity>
      ) : (
        <View style={[styles.suppressedBox, { borderColor: colors.border }]} testID="deployment-suppressed">
          <Text style={styles.suppressedText}>
            Paper submit disabled — verdict is WAIT.{"\n"}
            Resolve blockers above to enable deployment.
          </Text>
        </View>
      )}

      {/* META */}
      <Text style={styles.asOf} testID="deployment-asof">
        snapshot: {new Date(verdict.asOf).toLocaleTimeString()} · source: {verdict.source}
      </Text>
    </ScrollView>
  );
}

function AlignChip({ label, bias, conf, colors }: { label: string; bias: TradingAction; conf: number; colors: any }) {
  const col = actionColor(bias, colors);
  return (
    <View style={[chipStyles.chip, { borderColor: col }]} testID={`align-${label.toLowerCase()}`}>
      <Text style={[chipStyles.chipLabel, { color: colors.textMuted }]}>{label}</Text>
      <Text style={[chipStyles.chipBias, { color: col }]}>{bias}</Text>
      <Text style={[chipStyles.chipConf, { color: colors.textMuted }]}>{(conf * 100).toFixed(0)}%</Text>
    </View>
  );
}

function StructRow({ label, value, colors, last, tone, testID }: {
  label: string; value: string; colors: any; last?: boolean; tone?: 'warn' | 'normal'; testID?: string;
}) {
  return (
    <View style={[rowStyles.row, !last && { borderBottomColor: colors.border, borderBottomWidth: 1 }]} testID={testID}>
      <Text style={[rowStyles.label, { color: colors.textMuted }]}>{label}</Text>
      <Text style={[rowStyles.value, { color: tone === 'warn' ? (colors.sell || '#ef4444') : colors.text }]}>{value}</Text>
    </View>
  );
}

// ── Calibration section (T5) ──────────────────────────────────────────

const RELIABILITY_LABEL: Record<string, string> = {
  weak_sample: 'weak sample',
  emerging: 'emerging reliability',
  usable: 'usable reliability',
  strong: 'strong historical reliability',
};

function reliabilityColor(r: string | undefined, colors: any): string {
  switch (r) {
    case 'weak_sample': return colors.textMuted || '#888';
    case 'emerging':    return '#f59e0b';
    case 'usable':      return '#3b82f6';
    case 'strong':      return colors.buy || '#22c55e';
    default:            return colors.textMuted || '#888';
  }
}

function fmtBucket(b: string | undefined): string {
  if (b === '0_0.33')    return 'alignment 0–0.33';
  if (b === '0.33_0.67') return 'alignment 0.33–0.67';
  if (b === '0.67_1.0')  return 'alignment 0.67–1.0';
  return b || '—';
}

function CalibrationSection({ verdict, colors }: { verdict: TradingVerdict; colors: any }) {
  const c = verdict.calibration!;
  const rel = c.reliability;
  const relCol = reliabilityColor(rel, colors);
  const adj = c.appliedAdjustment;

  // No applied adjustment when verdict is WAIT
  const isNonAct = adj === 'none_wait_verdict';
  const isWarn = adj === 'soft_adjust' || adj === 'hard_gate_wait';

  // Honest natural-language status (strict vocabulary)
  let statusLine: string;
  if (c.sample === 0) {
    statusLine = 'no historical sample yet · cognition runs without correction';
  } else if (rel === 'weak_sample') {
    statusLine = `${c.sample} historical trades · sample still limited · cognition runs without correction`;
  } else if (rel === 'emerging') {
    statusLine = `${c.sample} historical trades · reliability emerging · observe before trusting`;
  } else if (adj === 'soft_adjust') {
    statusLine = `${c.sample} historical trades · ${Math.round((c.winRate || 0) * 100)}% target reach · confidence reduced by calibration layer`;
  } else if (adj === 'hard_gate_wait') {
    statusLine = `${c.sample} historical trades · ${Math.round((c.winRate || 0) * 100)}% target reach · historically weak follow-through · action blocked`;
  } else if (rel === 'usable') {
    statusLine = `${c.sample} historical trades · ${Math.round((c.winRate || 0) * 100)}% target reach · usable reliability · no correction needed`;
  } else if (rel === 'strong') {
    statusLine = `${c.sample} historical trades · ${Math.round((c.winRate || 0) * 100)}% target reach · strong historical reliability`;
  } else {
    statusLine = `${c.sample} historical trades · ${RELIABILITY_LABEL[rel] || rel}`;
  }

  return (
    <View style={calibStyles.wrap} testID="deployment-calibration">
      <Text style={[calibStyles.title, { color: colors.textMuted }]}>CALIBRATION LAYER</Text>
      <View style={[calibStyles.card, { backgroundColor: colors.surface, borderColor: isWarn ? '#f59e0b' : colors.border }]}>
        <View style={calibStyles.headerRow}>
          <Text style={[calibStyles.bucket, { color: colors.text }]}>{fmtBucket(c.alignmentBucket)}</Text>
          {!isNonAct && (
            <Text style={[calibStyles.relLabel, { color: relCol }]}>{RELIABILITY_LABEL[rel] || rel}</Text>
          )}
        </View>

        <Text style={[calibStyles.statusLine, { color: colors.text }]} testID="calibration-status">
          {statusLine}
        </Text>

        {/* Metrics row — only show if there's any sample */}
        {c.sample > 0 && !isNonAct && (
          <View style={calibStyles.metricsRow}>
            <CalMetric label="trades" value={String(c.sample)} colors={colors} />
            {c.winRate != null && (
              <CalMetric label="win rate" value={`${Math.round(c.winRate * 100)}%`} colors={colors} />
            )}
            {c.targetRate != null && (
              <CalMetric label="target reach" value={`${Math.round(c.targetRate * 100)}%`} colors={colors} />
            )}
            {c.avgPnlPct != null && (
              <CalMetric label="avg pnl" value={`${c.avgPnlPct >= 0 ? '+' : ''}${c.avgPnlPct.toFixed(2)}%`} colors={colors}
                color={c.avgPnlPct >= 0 ? (colors.buy || '#22c55e') : (colors.sell || '#ef4444')} />
            )}
          </View>
        )}

        {/* Adjustment banner */}
        {adj === 'soft_adjust' && (
          <View style={[calibStyles.banner, { borderLeftColor: '#f59e0b' }]} testID="calibration-banner-soft">
            <Text style={[calibStyles.bannerText, { color: '#f59e0b' }]}>
              Confidence reduced · risk bumped one tier
            </Text>
            {verdict.riskBeforeCalibration && (
              <Text style={[calibStyles.bannerSub, { color: colors.textMuted }]}>
                was {verdict.riskBeforeCalibration} → now {verdict.risk}
              </Text>
            )}
          </View>
        )}
        {adj === 'hard_gate_wait' && (
          <View style={[calibStyles.banner, { borderLeftColor: colors.sell || '#ef4444' }]} testID="calibration-banner-gate">
            <Text style={[calibStyles.bannerText, { color: colors.sell || '#ef4444' }]}>
              Historically weak follow-through · deployment refused
            </Text>
            {verdict.actionBeforeCalibration && (
              <Text style={[calibStyles.bannerSub, { color: colors.textMuted }]}>
                cognition wanted {verdict.actionBeforeCalibration} · calibration overrode to WAIT
              </Text>
            )}
          </View>
        )}
        {adj === 'warn_only' && c.sample > 0 && (
          <Text style={[calibStyles.bannerSub, { color: colors.textMuted, marginTop: 6 }]} testID="calibration-banner-warn">
            sample still emerging · not yet enough to adjust verdict
          </Text>
        )}
      </View>
    </View>
  );
}

function CalMetric({ label, value, colors, color }: { label: string; value: string; colors: any; color?: string }) {
  return (
    <View style={calibStyles.metric}>
      <Text style={[calibStyles.metricLabel, { color: colors.textMuted }]}>{label}</Text>
      <Text style={[calibStyles.metricValue, { color: color || colors.text }]}>{value}</Text>
    </View>
  );
}

const calibStyles = StyleSheet.create({
  wrap: { marginBottom: 16 },
  title: { fontSize: 11, letterSpacing: 1.5, marginBottom: 8, textTransform: 'uppercase', fontWeight: '700' },
  card: { borderWidth: 1, borderRadius: 12, padding: 14 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  bucket: { fontSize: 13, fontWeight: '700' },
  relLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 0.3, textTransform: 'lowercase' },
  statusLine: { fontSize: 12, lineHeight: 17 },
  metricsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 14, marginTop: 10 },
  metric: { minWidth: 60 },
  metricLabel: { fontSize: 9, letterSpacing: 1, textTransform: 'uppercase' },
  metricValue: { fontSize: 13, fontWeight: '700', marginTop: 2 },
  banner: { borderLeftWidth: 3, paddingLeft: 10, paddingVertical: 6, marginTop: 10 },
  bannerText: { fontSize: 12, fontWeight: '700' },
  bannerSub: { fontSize: 11, marginTop: 2, lineHeight: 15 },
});

// ── Adaptive Sizing section (T8) ─────────────────────────────────────

function fmtMultiplier(w: number): string {
  return `×${w.toFixed(2)}`;
}

function fmtUsd(n: number): string {
  return `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function scaleTone(w: number, colors: any): string {
  // ≤0.5 strong restraint (red), <1.0 mild restraint (amber), =1.0 neutral, >1.0 boost (green)
  if (w === 0) return colors.sell || '#ef4444';
  if (w < 0.70) return colors.sell || '#ef4444';
  if (w < 1.0) return '#f59e0b';
  if (w > 1.0) return colors.buy || '#22c55e';
  return colors.text;
}

const FORCED_ZERO_TITLE: Record<string, string> = {
  verdict_is_wait: 'WAIT verdict — no deployable size',
  no_structural_base_size: 'no structural base — adaptive layer skipped',
  book_saturated: 'book saturated — exposure scale at 0',
  size_below_min_deployable: 'restraints reduced size below $1 floor',
};

function AdaptiveSizingSection({ verdict, colors }: { verdict: TradingVerdict; colors: any }) {
  const s = verdict.sizing!;
  const zeroed = s.final === 0;
  const borderCol = zeroed
    ? (colors.sell || '#ef4444')
    : (colors.border);

  return (
    <View style={sizeStyles.wrap} testID="deployment-sizing">
      <Text style={[sizeStyles.title, { color: colors.textMuted }]}>ADAPTIVE SIZING</Text>
      <View style={[sizeStyles.card, { backgroundColor: colors.surface, borderColor: borderCol }]}>

        {/* Header — base & final */}
        <View style={sizeStyles.headerRow}>
          <View>
            <Text style={[sizeStyles.label, { color: colors.textMuted }]}>BASE SIZE</Text>
            <Text style={[sizeStyles.bigVal, { color: colors.text }]} testID="sizing-base">
              {fmtUsd(s.baseSize)}
            </Text>
          </View>
          <Ionicons name="arrow-forward" size={18} color={colors.textMuted} />
          <View style={{ alignItems: 'flex-end' }}>
            <Text style={[sizeStyles.label, { color: colors.textMuted }]}>FINAL SIZE</Text>
            <Text style={[
              sizeStyles.bigVal,
              { color: zeroed ? (colors.sell || '#ef4444') : (colors.buy || '#22c55e'), fontWeight: '800' },
            ]} testID="sizing-final">
              {fmtUsd(s.final)}
            </Text>
          </View>
        </View>

        {/* Scale rows */}
        <View style={sizeStyles.divider} />

        <SizingScaleRow
          label="LIFETIME SCALE"
          weight={s.lifetimeWeight}
          note={s.labels.lifetime}
          colors={colors}
          testID="sizing-lifetime"
        />
        <SizingScaleRow
          label="REGIME SCALE"
          weight={s.regimeWeight}
          note={s.labels.regime}
          colors={colors}
          testID="sizing-regime"
        />
        <SizingScaleRow
          label="EXPOSURE SCALE"
          weight={s.exposureWeight}
          note={s.labels.exposure}
          colors={colors}
          testID="sizing-exposure"
        />
        <SizingScaleRow
          label="UNCERTAINTY PENALTY"
          weight={s.uncertaintyPenalty}
          note={s.labels.uncertainty}
          colors={colors}
          last
          testID="sizing-uncertainty"
        />

        <View style={sizeStyles.divider} />

        {/* Explanation line — verbatim from backend */}
        <Text style={[sizeStyles.explanation, { color: colors.text }]} testID="sizing-explanation">
          {s.explanation}
        </Text>

        {/* Forced-zero banner if applicable */}
        {zeroed && s.forcedZeroReason && (
          <View style={[sizeStyles.banner, { borderLeftColor: colors.sell || '#ef4444' }]} testID="sizing-banner-zero">
            <Text style={[sizeStyles.bannerText, { color: colors.sell || '#ef4444' }]}>
              {FORCED_ZERO_TITLE[s.forcedZeroReason] || s.forcedZeroReason}
            </Text>
          </View>
        )}

        {/* Components — book state for transparency */}
        <View style={sizeStyles.miniRow}>
          <Text style={[sizeStyles.miniMuted, { color: colors.textMuted }]}>
            book: {s.components.openCount} open · ${fmtNum(s.components.notionalExposureUsd, 0)} notional
            {' · '}
            base risk {s.baseRiskPct}% (${fmtNum(s.baseRiskUsd, 0)})
          </Text>
        </View>
      </View>
    </View>
  );
}

function SizingScaleRow({
  label, weight, note, colors, last, testID,
}: {
  label: string; weight: number; note: string; colors: any; last?: boolean; testID?: string;
}) {
  const tone = scaleTone(weight, colors);
  return (
    <View style={[sizeStyles.scaleRow, !last && { borderBottomColor: colors.border, borderBottomWidth: StyleSheet.hairlineWidth }]} testID={testID}>
      <View style={sizeStyles.scaleLeft}>
        <Text style={[sizeStyles.scaleLabel, { color: colors.textMuted }]}>{label}</Text>
        <Text style={[sizeStyles.scaleNote, { color: colors.textMuted }]} numberOfLines={2}>{note}</Text>
      </View>
      <Text style={[sizeStyles.scaleMult, { color: tone }]}>{fmtMultiplier(weight)}</Text>
    </View>
  );
}

const sizeStyles = StyleSheet.create({
  wrap: { marginBottom: 16 },
  title: { fontSize: 11, letterSpacing: 1.5, marginBottom: 8, textTransform: 'uppercase', fontWeight: '700' },
  card: { borderWidth: 1, borderRadius: 12, padding: 14 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 12 },
  label: { fontSize: 9, letterSpacing: 1, textTransform: 'uppercase', fontWeight: '700' },
  bigVal: { fontSize: 18, fontWeight: '700', marginTop: 2 },
  divider: { height: 1, backgroundColor: 'rgba(127,127,127,0.18)', marginVertical: 10 },
  scaleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 8, gap: 12 },
  scaleLeft: { flex: 1 },
  scaleLabel: { fontSize: 10, letterSpacing: 1, textTransform: 'uppercase', fontWeight: '700' },
  scaleNote: { fontSize: 10, lineHeight: 14, marginTop: 2 },
  scaleMult: { fontSize: 16, fontWeight: '800', minWidth: 64, textAlign: 'right' },
  explanation: { fontSize: 11, lineHeight: 16 },
  banner: { borderLeftWidth: 3, paddingLeft: 10, paddingVertical: 6, marginTop: 10 },
  bannerText: { fontSize: 12, fontWeight: '700' },
  miniRow: { marginTop: 10 },
  miniMuted: { fontSize: 10, lineHeight: 14 },
});

// ── Portfolio Gate section (T9) ──────────────────────────────────────

const GATE_BLOCK_LABEL: Record<string, string> = {
  max_open_positions: 'too many open positions',
  max_total_notional: 'total notional cap exceeded',
  max_per_symbol_exposure: 'per-symbol exposure cap exceeded',
  max_same_side_exposure: 'same-side exposure cap exceeded',
  max_correlated_exposure: 'correlated cluster cap exceeded',
  daily_drawdown_circuit_breaker: 'daily drawdown circuit breaker engaged',
  loss_streak_cooldown: 'cooldown active after loss streak',
};

function ratioTone(ratio: number, max: number, colors: any): string {
  const r = ratio / max;
  if (r >= 1.0) return colors.sell || '#ef4444';
  if (r >= 0.80) return '#f59e0b';
  if (r >= 0.50) return colors.text;
  return colors.textMuted || '#888';
}

function PortfolioGateSection({ verdict, colors }: { verdict: TradingVerdict; colors: any }) {
  const g = verdict.portfolioGate!;
  const blocked = g.permission === 'blocked';
  const borderCol = blocked ? (colors.sell || '#ef4444') : (colors.buy || '#22c55e');
  return (
    <View style={gateStyles.wrap} testID="deployment-gate">
      <Text style={[gateStyles.title, { color: colors.textMuted }]}>PORTFOLIO GATE</Text>
      <View style={[gateStyles.card, { backgroundColor: colors.surface, borderColor: borderCol }]}>

        {/* Permission header */}
        <View style={gateStyles.permRow}>
          <Text style={[gateStyles.permLabel, { color: colors.textMuted }]}>FINAL PERMISSION</Text>
          <Text
            testID="gate-permission"
            style={[
              gateStyles.permValue,
              { color: blocked ? (colors.sell || '#ef4444') : (colors.buy || '#22c55e') },
            ]}
          >
            {blocked ? 'BLOCKED' : 'ALLOWED'}
          </Text>
        </View>

        {blocked && g.blockReason && (
          <View style={[gateStyles.banner, { borderLeftColor: colors.sell || '#ef4444' }]} testID="gate-block-banner">
            <Text style={[gateStyles.bannerText, { color: colors.sell || '#ef4444' }]}>
              {GATE_BLOCK_LABEL[g.blockReason] || g.blockReason}
            </Text>
            {(g.reasons || []).slice(0, 2).map((r, i) => (
              <Text key={i} style={[gateStyles.bannerSub, { color: colors.textMuted }]}>{r}</Text>
            ))}
          </View>
        )}

        <View style={sizeStyles.divider} />

        {/* CAPS subsection */}
        <Text style={[gateStyles.subTitle, { color: colors.textMuted }]}>EXPOSURE CAPS</Text>
        <GateRow
          label="OPEN POSITIONS"
          value={`${g.caps.openPositions.current} → ${g.caps.openPositions.prospective} / ${g.caps.openPositions.max}`}
          tone={ratioTone(g.caps.openPositions.prospective, g.caps.openPositions.max, colors)}
          colors={colors}
          testID="gate-cap-open"
        />
        <GateRow
          label="TOTAL NOTIONAL"
          value={`${g.caps.totalNotional.ratio.toFixed(2)}× / ${g.caps.totalNotional.max}× equity`}
          tone={ratioTone(g.caps.totalNotional.ratio, g.caps.totalNotional.max, colors)}
          colors={colors}
          testID="gate-cap-total"
        />
        <GateRow
          label={`${g.caps.perSymbol.symbol} EXPOSURE`}
          value={`${g.caps.perSymbol.ratio.toFixed(2)}× / ${g.caps.perSymbol.max}× equity`}
          tone={ratioTone(g.caps.perSymbol.ratio, g.caps.perSymbol.max, colors)}
          colors={colors}
          testID="gate-cap-symbol"
        />
        <GateRow
          label={`${g.caps.sameSide.side || 'SIDE'} EXPOSURE`}
          value={`${g.caps.sameSide.ratio.toFixed(2)}× / ${g.caps.sameSide.max}× equity`}
          tone={ratioTone(g.caps.sameSide.ratio, g.caps.sameSide.max, colors)}
          colors={colors}
          testID="gate-cap-sameside"
        />

        <View style={sizeStyles.divider} />

        {/* CORRELATION subsection */}
        <Text style={[gateStyles.subTitle, { color: colors.textMuted }]}>CORRELATION GUARD</Text>
        {g.correlation.cluster ? (
          <>
            <GateRow
              label={`CLUSTER · ${g.correlation.cluster}`}
              value={`${g.correlation.sameSideCountInCluster} same-side · members ${g.correlation.clusterMembers.join('/')}`}
              tone={colors.text}
              colors={colors}
              testID="gate-cluster"
            />
            <GateRow
              label="CLUSTER EXPOSURE"
              value={`${g.correlation.ratio.toFixed(2)}× / ${g.correlation.max}× equity`}
              tone={ratioTone(g.correlation.ratio, g.correlation.max, colors)}
              colors={colors}
              testID="gate-cluster-ratio"
            />
          </>
        ) : (
          <Text style={[gateStyles.muted, { color: colors.textMuted }]}>
            {verdict.symbol} not in any correlation cluster — treated as independent
          </Text>
        )}

        <View style={sizeStyles.divider} />

        {/* DRAWDOWN subsection */}
        <Text style={[gateStyles.subTitle, { color: colors.textMuted }]}>DAILY DRAWDOWN</Text>
        <GateRow
          label="REALIZED TODAY"
          value={`${g.drawdown.realizedTodayUsd >= 0 ? '+' : ''}$${fmtNum(g.drawdown.realizedTodayUsd, 2)}`}
          tone={g.drawdown.realizedTodayUsd < 0 ? (colors.sell || '#ef4444') : colors.text}
          colors={colors}
          testID="gate-dd-realized"
        />
        <GateRow
          label="UNREALIZED"
          value={`${g.drawdown.unrealizedUsd >= 0 ? '+' : ''}$${fmtNum(g.drawdown.unrealizedUsd, 2)}`}
          tone={g.drawdown.unrealizedUsd < 0 ? (colors.sell || '#ef4444') : colors.text}
          colors={colors}
          testID="gate-dd-unrealized"
        />
        <GateRow
          label="DRAWDOWN"
          value={`${g.drawdown.drawdownPct.toFixed(2)}% · threshold ${g.drawdown.thresholdPct}%`}
          tone={g.drawdown.breakerActive ? (colors.sell || '#ef4444') : (g.drawdown.drawdownPct < 0 ? '#f59e0b' : colors.text)}
          colors={colors}
          testID="gate-dd-pct"
        />
        {g.drawdown.breakerActive && (
          <Text style={[gateStyles.warnLine, { color: colors.sell || '#ef4444' }]}>
            CIRCUIT BREAKER ENGAGED · no new deployments
          </Text>
        )}

        <View style={sizeStyles.divider} />

        {/* COOLDOWN subsection */}
        <Text style={[gateStyles.subTitle, { color: colors.textMuted }]}>LOSS STREAK COOLDOWN</Text>
        <GateRow
          label="STREAK"
          value={`${g.cooldown.recentLossStreak} loss${g.cooldown.recentLossStreak === 1 ? '' : 'es'} · threshold ${g.cooldown.threshold}`}
          tone={g.cooldown.cooldownActive ? (colors.sell || '#ef4444') : colors.text}
          colors={colors}
          testID="gate-cooldown-streak"
        />
        {g.cooldown.cooldownActive && g.cooldown.cooldownUntil && (
          <Text style={[gateStyles.warnLine, { color: colors.sell || '#ef4444' }]}>
            COOLDOWN ACTIVE · ends {new Date(g.cooldown.cooldownUntil).toLocaleTimeString()}
          </Text>
        )}
      </View>
    </View>
  );
}

function GateRow({
  label, value, tone, colors, testID,
}: {
  label: string; value: string; tone: string; colors: any; testID?: string;
}) {
  return (
    <View style={gateStyles.row} testID={testID}>
      <Text style={[gateStyles.rowLabel, { color: colors.textMuted }]}>{label}</Text>
      <Text style={[gateStyles.rowValue, { color: tone }]}>{value}</Text>
    </View>
  );
}

const gateStyles = StyleSheet.create({
  wrap: { marginBottom: 16 },
  title: { fontSize: 11, letterSpacing: 1.5, marginBottom: 8, textTransform: 'uppercase', fontWeight: '700' },
  card: { borderWidth: 1, borderRadius: 12, padding: 14 },
  permRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  permLabel: { fontSize: 10, letterSpacing: 1.2, textTransform: 'uppercase', fontWeight: '700' },
  permValue: { fontSize: 18, fontWeight: '800', letterSpacing: 1.5 },
  banner: { borderLeftWidth: 3, paddingLeft: 10, paddingVertical: 6, marginTop: 10 },
  bannerText: { fontSize: 12, fontWeight: '700' },
  bannerSub: { fontSize: 11, marginTop: 2, lineHeight: 15 },
  subTitle: { fontSize: 10, letterSpacing: 1.4, marginBottom: 6, textTransform: 'uppercase', fontWeight: '700' },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 5 },
  rowLabel: { fontSize: 10, letterSpacing: 0.8, textTransform: 'uppercase', flex: 1 },
  rowValue: { fontSize: 12, fontWeight: '600', textAlign: 'right' },
  muted: { fontSize: 11, lineHeight: 15 },
  warnLine: { fontSize: 11, fontWeight: '700', marginTop: 6, letterSpacing: 0.5 },
});

const chipStyles = StyleSheet.create({
  chip: {
    flex: 1,
    borderWidth: 1,
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 8,
    alignItems: 'center',
    gap: 2,
  },
  chipLabel: { fontSize: 10, letterSpacing: 1, textTransform: 'uppercase' },
  chipBias: { fontSize: 14, fontWeight: '700', letterSpacing: 0.5 },
  chipConf: { fontSize: 10 },
});

const rowStyles = StyleSheet.create({
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 12, paddingHorizontal: 14 },
  label: { fontSize: 12, letterSpacing: 1, textTransform: 'uppercase' },
  value: { fontSize: 14, fontWeight: '600' },
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
    headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
    symbol: { fontSize: 24, fontWeight: '800', color: colors.text, letterSpacing: 0.5 },
    actionPill: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 20 },
    actionPillText: { color: '#fff', fontWeight: '800', letterSpacing: 1 },
    section: { marginBottom: 16 },
    sectionTitle: { fontSize: 11, letterSpacing: 1.5, color: colors.textMuted, marginBottom: 8, textTransform: 'uppercase', fontWeight: '700' },
    alignRow: { flexDirection: 'row', gap: 8 },
    alignFootnote: { fontSize: 11, color: colors.textMuted, marginTop: 8 },
    structure: { borderWidth: 1, borderRadius: 12, overflow: 'hidden' },
    blockedBox: { borderWidth: 1, borderRadius: 12, padding: 14 },
    blockedHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
    blockedTitle: { fontSize: 12, letterSpacing: 1.5, color: colors.textMuted, fontWeight: '700' },
    blockedItem: { fontSize: 13, color: colors.text, lineHeight: 18, marginBottom: 2 },
    reasonItem: { fontSize: 12, color: colors.textMuted, lineHeight: 17, marginBottom: 2 },
    submitBtn: {
      flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
      paddingVertical: 14, borderRadius: 12, marginTop: 8,
    },
    submitText: { color: '#fff', fontWeight: '800', fontSize: 14, letterSpacing: 1 },
    suppressedBox: { borderWidth: 1, borderRadius: 12, padding: 14, alignItems: 'center', marginTop: 8 },
    suppressedText: { color: colors.textMuted, fontSize: 12, textAlign: 'center', lineHeight: 18 },
    asOf: { color: colors.textMuted, fontSize: 10, textAlign: 'center', marginTop: 16 },
  });
