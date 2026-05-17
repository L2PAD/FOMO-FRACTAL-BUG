/**
 * /admin/attribution — T11.2A — Performance Attribution Observatory
 *
 * EPISTEMIC OBSERVATORY, NOT OPERATOR CONTROL SURFACE.
 *
 * Architectural invariants enforced visually:
 *
 *   1. Forensic palette only.  No bright greens, no "alpha" framing,
 *      no "edge", no "AI improved returns".  Cards are subdued; only
 *      the active state and pipeline-version banner use the brand
 *      accent.  Reality, not marketing.
 *
 *   2. Canonical lineage order is LOCKED in the comparison table —
 *      RAW → CALIBRATED → SIZED → GATED.  No reorder, no sort
 *      controls, no customisation.  Pipeline order = architectural
 *      truth.
 *
 *   3. Mixed-availability honesty.  When `rawLayerSupported=false`
 *      we render an explicit note ("Raw lineage accumulation is in
 *      progress…") rather than filling cells with fake reconstructed
 *      values.  Pre-T11.1b outcomes naturally lack rawVerdictSnapshot.
 *
 *   4. Capital Preservation is VISUALLY SEPARATE from Lost Opportunity.
 *      Capital Preservation is framed as "risk containment".  Lost
 *      Opportunity is framed as "counterfactual observation" — NEVER
 *      as "missed profit".  No hero-card treatment for blocked PnL.
 *
 *   5. Window selector includes "all" — attribution semantically
 *      requires long-horizon (different from billing analytics).
 *
 *   6. Observational-only disclaimer rendered persistently at top.
 *      This surface NEVER recommends operational changes.
 *
 *   7. PipelineVersion banner is calm but unmissable — without it
 *      cross-version comparisons become epistemically dirty.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, Pressable,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AdminShell } from '../../../src/admin/components/AdminShell';
import { adminApi } from '../../../src/admin/api/adminClient';
import { useColors } from '../../../src/core/useColors';
import {
  PerAssetDrilldown,
  GateRuleDrilldown,
  ConfidenceDrilldown,
  ExposureDrilldown,
} from '../../../src/admin/components/AttributionDrilldowns';

type AttrWindow = '7d' | '30d' | '90d' | 'all';

interface LayerAgg {
  tradeCount: number;
  winCount: number;
  lossCount: number;
  hitRatePct: number;
  meanReturnPct: number;
  cumulativePnlUsd: number;
  cumulativePnlPct: number;
  maxDrawdownPct: number;
  sharpeLike: number;
  meanBarsHeld: number;
  note?: string;
}

interface AttributionSummary {
  ok: boolean;
  pipelineVersion: string;
  window: AttrWindow;
  windowDays: number | null;
  windowStart: string | null;
  windowEnd: string;
  computedAt: string;
  layers: {
    raw: LayerAgg;
    calibrated: LayerAgg;
    sized: LayerAgg;
    gated: LayerAgg;
  };
  deltas: {
    calibratedVsRaw: any;
    sizedVsCalibrated: any;
    gatedVsSized: any;
  };
  gateBlocks: {
    totalDecisionsObserved: number;
    allowed: number;
    blocked: number;
    capitalPreservation: {
      blockedCount: number;
      preventedNotionalUsd: number;
      byRule: {
        drawdownBreaker: number;
        cooldown: number;
        correlationCluster: number;
        sameSideExposure: number;
        exposureCap: number;
      };
      framingNote: string;
    };
  };
  dataAvailability: {
    outcomesInWindow: number;
    gateDecisionsInWindow: number;
    rawLayerSupported: boolean;
    rawSamples: number;
    note: string;
  };
}

interface LostOpportunityResp {
  ok: boolean;
  pipelineVersion: string;
  window: AttrWindow;
  n: number;
  rows: Array<{
    decisionId?: string;
    symbol?: string;
    permission?: string;
    blockReason?: string;
    ts?: string;
    pipelineVersion?: string;
    counterfactual?: {
      theoreticalEntry?: number | null;
      theoreticalStop?: number | null;
      theoreticalTarget?: number | null;
      theoreticalSizeUsd?: number | null;
      marketPriceAtDecision?: number | null;
    };
    lineageId?: string | null;
  }>;
  framingNote: string;
}

const WINDOWS: AttrWindow[] = ['7d', '30d', '90d', 'all'];

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

const RULE_LABEL: Record<string, string> = {
  daily_drawdown_circuit_breaker: 'drawdown breaker',
  loss_streak_cooldown: 'loss-streak cooldown',
  max_correlated_exposure: 'correlation cluster cap',
  max_same_side_exposure: 'same-side exposure cap',
  max_open_positions: 'open-positions cap',
  max_total_notional: 'total-notional cap',
  max_per_symbol_exposure: 'per-symbol exposure cap',
};

export default function AttributionScreen() {
  const colors = useColors();
  const [windowSel, setWindowSel] = useState<AttrWindow>('30d');
  const [summary, setSummary] = useState<AttributionSummary | null>(null);
  const [lost, setLost] = useState<LostOpportunityResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, l] = await Promise.all([
        adminApi.attributionSummary(windowSel),
        adminApi.attributionLostOpportunity(windowSel, 50),
      ]);
      setSummary(s);
      setLost(l);
    } catch (e: any) {
      setError(
        e?.response?.data?.detail?.error ||
        e?.message ||
        'Failed to load attribution observatory',
      );
    } finally {
      setLoading(false);
    }
  }, [windowSel]);

  useEffect(() => {
    load();
  }, [load]);

  // Lineage completeness — share of outcomes that carry rawVerdictSnapshot.
  const lineageCompletenessPct = summary
    ? summary.dataAvailability.outcomesInWindow > 0
      ? (summary.dataAvailability.rawSamples /
         summary.dataAvailability.outcomesInWindow) * 100
      : 0
    : 0;

  return (
    <AdminShell>
      <ScrollView contentContainerStyle={[styles.scroll, { backgroundColor: colors.background }]}>
        {/* ── Heading + observational-only disclaimer ─────────────── */}
        <View style={styles.head}>
          <View style={{ flex: 1 }}>
            <Text style={[styles.h1, { color: colors.textPrimary }]}>Attribution</Text>
            <Text style={[styles.sub, { color: colors.textSecondary }]}>
              Cross-layer epistemic observatory.{' '}
              <Text style={{ fontWeight: '700' }}>
                This surface explains historical paper-runtime behavior. It does
                not recommend operational changes.
              </Text>
              {' '}Read-only, forward-only, counterfactual.
            </Text>
          </View>
          <View style={[styles.windowSwitcher, { borderColor: colors.border, backgroundColor: colors.surface }]}>
            {WINDOWS.map(w => {
              const active = w === windowSel;
              return (
                <Pressable
                  key={w}
                  onPress={() => setWindowSel(w)}
                  style={[
                    styles.windowBtn,
                    { backgroundColor: active ? colors.accent : 'transparent' },
                  ]}
                  testID={`attribution-window-${w}`}
                >
                  <Text
                    style={[
                      styles.windowBtnText,
                      { color: active ? colors.accentText : colors.textSecondary },
                    ]}
                  >
                    {w}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>

        {/* ── Error / loading ─────────────────────────────────────── */}
        {error && (
          <View style={[styles.errBox, { borderColor: colors.danger, backgroundColor: colors.badgeHighBg }]}>
            <Text style={[styles.errText, { color: colors.badgeHighText }]}>{error}</Text>
          </View>
        )}
        {loading && !summary && (
          <View style={styles.loadingBox}>
            <ActivityIndicator color={colors.accent} />
          </View>
        )}

        {summary && (
          <>
            {/* ── Top strip — pipeline version + coverage ─────────── */}
            <View style={[styles.topStrip, { backgroundColor: colors.surface, borderColor: colors.border }]}>
              <View style={styles.pipelineCell}>
                <View style={styles.pipelineHeadRow}>
                  <Ionicons name="git-branch-outline" size={14} color={colors.accent} />
                  <Text style={[styles.cardLabel, { color: colors.textMuted, marginLeft: 6 }]}>
                    PIPELINE VERSION
                  </Text>
                </View>
                <Text style={[styles.pipelineValue, { color: colors.textPrimary }]} numberOfLines={1}>
                  {summary.pipelineVersion}
                </Text>
                <Text style={[styles.pipelineCaption, { color: colors.textMuted }]}>
                  Comparisons are valid only within the same pipeline composition.
                </Text>
              </View>

              <View style={[styles.divider, { backgroundColor: colors.border }]} />

              <View style={styles.coverageCell}>
                <Text style={[styles.cardLabel, { color: colors.textMuted }]}>LINEAGE COVERAGE</Text>
                <Text style={[styles.coverageValue, { color: colors.textPrimary }]}>
                  {fmtPct(lineageCompletenessPct)}
                </Text>
                <Text style={[styles.coverageCaption, { color: colors.textMuted }]}>
                  {summary.dataAvailability.rawSamples} of {summary.dataAvailability.outcomesInWindow} outcomes carry a raw snapshot.
                </Text>
                <View style={[styles.coverageBar, { backgroundColor: colors.surfaceHover }]}>
                  <View
                    style={[
                      styles.coverageFill,
                      {
                        width: `${Math.min(100, Math.max(0, lineageCompletenessPct))}%`,
                        backgroundColor: colors.accent,
                      },
                    ]}
                  />
                </View>
              </View>

              <View style={[styles.divider, { backgroundColor: colors.border }]} />

              <View style={styles.coverageCell}>
                <Text style={[styles.cardLabel, { color: colors.textMuted }]}>GATE DECISIONS</Text>
                <Text style={[styles.coverageValue, { color: colors.textPrimary }]}>
                  {fmtNum(summary.gateBlocks.totalDecisionsObserved)}
                </Text>
                <View style={styles.gateSplitRow}>
                  <Text style={[styles.gateSplit, { color: colors.textSecondary }]}>
                    {summary.gateBlocks.allowed} allowed
                  </Text>
                  <Text style={[styles.gateSplit, { color: colors.textMuted }]}>·</Text>
                  <Text style={[styles.gateSplit, { color: colors.textSecondary }]}>
                    {summary.gateBlocks.blocked} blocked
                  </Text>
                </View>
              </View>

              <View style={[styles.divider, { backgroundColor: colors.border }]} />

              <View style={styles.coverageCell}>
                <Text style={[styles.cardLabel, { color: colors.textMuted }]}>WINDOW</Text>
                <Text style={[styles.coverageValue, { color: colors.textPrimary }]}>
                  {summary.window}
                </Text>
                <Text style={[styles.coverageCaption, { color: colors.textMuted }]}>
                  {summary.windowDays === null
                    ? 'All history (forward-only)'
                    : `Rolling ${summary.windowDays} days`}
                </Text>
              </View>
            </View>

            {/* ── Mixed-availability honesty banner ──────────────── */}
            {!summary.dataAvailability.rawLayerSupported && (
              <View style={[styles.honestyBanner, { backgroundColor: colors.bgSecondary, borderColor: colors.border }]}>
                <Ionicons name="information-circle-outline" size={16} color={colors.textSecondary} />
                <View style={{ flex: 1 }}>
                  <Text style={[styles.honestyTitle, { color: colors.textPrimary }]}>
                    Raw lineage accumulation is in progress
                  </Text>
                  <Text style={[styles.honestyBody, { color: colors.textSecondary }]}>
                    Raw lineage coverage began with T11.1b. Historical outcomes
                    before this point do not contain raw snapshots and are not
                    retroactively reconstructed. Comparative attribution
                    confidence increases as new paper outcomes settle.
                  </Text>
                </View>
              </View>
            )}

            {/* ── Lineage Comparison Table — ORDER LOCKED ────────── */}
            <SectionHeader
              colors={colors}
              title="Lineage comparison"
              subtitle="Same decision · four stages. Canonical pipeline order — never reordered. Empty deltas mean the stage did not produce a distinct outcome series in this window."
            />
            <View style={[styles.lineageTable, { backgroundColor: colors.surface, borderColor: colors.border }]}>
              {/* Header row */}
              <View style={[styles.lineageRow, styles.lineageHeader, { borderBottomColor: colors.border }]}>
                <View style={[styles.layerCell, styles.layerCellHead]}>
                  <Text style={[styles.lineageHeadText, { color: colors.textMuted }]}>STAGE</Text>
                </View>
                <View style={[styles.metricCell, styles.metricCellHead]}>
                  <Text style={[styles.lineageHeadText, { color: colors.textMuted }]}>TRADES</Text>
                </View>
                <View style={[styles.metricCell, styles.metricCellHead]}>
                  <Text style={[styles.lineageHeadText, { color: colors.textMuted }]}>HIT-RATE</Text>
                </View>
                <View style={[styles.metricCell, styles.metricCellHead]}>
                  <Text style={[styles.lineageHeadText, { color: colors.textMuted }]}>MEAN RET %</Text>
                </View>
                <View style={[styles.metricCell, styles.metricCellHead]}>
                  <Text style={[styles.lineageHeadText, { color: colors.textMuted }]}>CUM PnL</Text>
                </View>
                <View style={[styles.metricCell, styles.metricCellHead]}>
                  <Text style={[styles.lineageHeadText, { color: colors.textMuted }]}>MAX DD %</Text>
                </View>
                <View style={[styles.metricCell, styles.metricCellHead]}>
                  <Text style={[styles.lineageHeadText, { color: colors.textMuted }]}>SHARPE-LIKE</Text>
                </View>
              </View>
              {/* CANONICAL ORDER — DO NOT REORDER */}
              <LineageRow
                colors={colors}
                stage="RAW"
                description="Pre-calibration cognition output. Forward-only from T11.1b."
                agg={summary.layers.raw}
                supported={summary.dataAvailability.rawLayerSupported}
              />
              <LineageRow
                colors={colors}
                stage="CALIBRATED"
                description="Alignment / risk / RR applied."
                agg={summary.layers.calibrated}
                supported
              />
              <LineageRow
                colors={colors}
                stage="SIZED"
                description="Adaptive capital-restraint sizing applied."
                agg={summary.layers.sized}
                supported
              />
              <LineageRow
                colors={colors}
                stage="GATED"
                description="Portfolio exposure / drawdown / cooldown gate applied. Final."
                agg={summary.layers.gated}
                supported
                isFinal
              />
            </View>
            <Text style={[styles.tableCaption, { color: colors.textMuted }]}>
              Counterfactual outcomes for gate-blocked decisions are NOT
              reconstructed against later market prices. Honest reporting
              over fabrication — deltas accumulate forward-only.
            </Text>

            {/* ── Capital Preservation panel (SEPARATE block) ────── */}
            <SectionHeader
              colors={colors}
              title="Capital preservation"
              subtitle="Risk-adjusted gate attribution. Evidence counts, not value judgments."
            />
            <View style={[styles.preservationPanel, { backgroundColor: colors.surface, borderColor: colors.border }]}>
              <View style={styles.preservationTopRow}>
                <PreservationStat
                  colors={colors}
                  label="BLOCKED DECISIONS"
                  value={fmtNum(summary.gateBlocks.capitalPreservation.blockedCount)}
                  caption="Counts every gate-blocked submission in window."
                />
                <PreservationStat
                  colors={colors}
                  label="PREVENTED NOTIONAL"
                  value={fmtUsd(summary.gateBlocks.capitalPreservation.preventedNotionalUsd)}
                  caption="Total theoretical capital not deployed (frozen at decision time)."
                />
              </View>
              <View style={[styles.preservationRules, { borderTopColor: colors.border }]}>
                <Text style={[styles.cardLabel, { color: colors.textMuted, marginBottom: 8 }]}>
                  BY RULE
                </Text>
                <View style={styles.preservationRulesRow}>
                  <RulePill
                    colors={colors}
                    label="Drawdown breaker"
                    value={summary.gateBlocks.capitalPreservation.byRule.drawdownBreaker}
                  />
                  <RulePill
                    colors={colors}
                    label="Loss-streak cooldown"
                    value={summary.gateBlocks.capitalPreservation.byRule.cooldown}
                  />
                  <RulePill
                    colors={colors}
                    label="Correlation cluster"
                    value={summary.gateBlocks.capitalPreservation.byRule.correlationCluster}
                  />
                  <RulePill
                    colors={colors}
                    label="Same-side exposure"
                    value={summary.gateBlocks.capitalPreservation.byRule.sameSideExposure}
                  />
                  <RulePill
                    colors={colors}
                    label="Exposure cap"
                    value={summary.gateBlocks.capitalPreservation.byRule.exposureCap}
                  />
                </View>
              </View>
              <View style={[styles.framingBlock, { borderTopColor: colors.border }]}>
                <Ionicons name="shield-outline" size={14} color={colors.textMuted} />
                <Text style={[styles.framingText, { color: colors.textSecondary }]}>
                  {summary.gateBlocks.capitalPreservation.framingNote}
                </Text>
              </View>
            </View>

            {/* ── Lost Opportunity panel — SUBDUED ────────────────── */}
            <SectionHeader
              colors={colors}
              title="Lost opportunity"
              subtitle="Counterfactual observation. Each row is a deployment the gate prevented — not a retrospective mistake."
              subdued
            />
            {lost && (
              <View style={[styles.lostPanel, { backgroundColor: colors.surface, borderColor: colors.border }]}>
                <View style={[styles.lostHeadRow, { borderBottomColor: colors.border }]}>
                  <Text style={[styles.lostHeadCell, styles.lostColTime, { color: colors.textMuted }]}>
                    TIME
                  </Text>
                  <Text style={[styles.lostHeadCell, styles.lostColSym, { color: colors.textMuted }]}>
                    SYMBOL
                  </Text>
                  <Text style={[styles.lostHeadCell, styles.lostColRule, { color: colors.textMuted }]}>
                    RULE
                  </Text>
                  <Text style={[styles.lostHeadCell, styles.lostColSize, { color: colors.textMuted }]}>
                    THEORETICAL SIZE
                  </Text>
                  <Text style={[styles.lostHeadCell, styles.lostColPrice, { color: colors.textMuted }]}>
                    PRICE @ DECISION
                  </Text>
                </View>
                {lost.rows.length === 0 ? (
                  <View style={styles.lostEmpty}>
                    <Text style={[styles.lostEmptyText, { color: colors.textMuted }]}>
                      No gate-blocked decisions in this window.
                    </Text>
                  </View>
                ) : (
                  lost.rows.slice(0, 25).map((r, i) => (
                    <View
                      key={r.decisionId || `${r.ts}-${i}`}
                      style={[styles.lostRow, { borderBottomColor: colors.border }]}
                    >
                      <Text style={[styles.lostCell, styles.lostColTime, { color: colors.textSecondary }]} numberOfLines={1}>
                        {r.ts ? new Date(r.ts).toLocaleString() : '—'}
                      </Text>
                      <Text style={[styles.lostCell, styles.lostColSym, { color: colors.textPrimary }]} numberOfLines={1}>
                        {r.symbol || '—'}
                      </Text>
                      <Text style={[styles.lostCell, styles.lostColRule, { color: colors.textSecondary }]} numberOfLines={1}>
                        {RULE_LABEL[r.blockReason || ''] || r.blockReason || '—'}
                      </Text>
                      <Text style={[styles.lostCell, styles.lostColSize, { color: colors.textPrimary, fontFamily: 'monospace' }]} numberOfLines={1}>
                        {fmtUsd(r.counterfactual?.theoreticalSizeUsd)}
                      </Text>
                      <Text style={[styles.lostCell, styles.lostColPrice, { color: colors.textSecondary, fontFamily: 'monospace' }]} numberOfLines={1}>
                        {fmtUsd(r.counterfactual?.marketPriceAtDecision)}
                      </Text>
                    </View>
                  ))
                )}
                {lost.rows.length > 25 && (
                  <View style={styles.lostMoreRow}>
                    <Text style={[styles.lostMoreText, { color: colors.textMuted }]}>
                      + {lost.rows.length - 25} more in window
                    </Text>
                  </View>
                )}
                <View style={[styles.framingBlock, { borderTopColor: colors.border }]}>
                  <Ionicons name="information-circle-outline" size={14} color={colors.textMuted} />
                  <Text style={[styles.framingText, { color: colors.textSecondary }]}>
                    {lost.framingNote}
                  </Text>
                </View>
              </View>
            )}

            {/* ── T11.2B — Drilldowns (collapsible, secondary, investigative) ── */}
            <SectionHeader
              colors={colors}
              title="Drilldowns"
              subtitle="Investigative · collapsed by default · read-only. These panels surface where the aggregate is uneven — they do not propose operational changes."
              subdued
            />
            <PerAssetDrilldown    colors={colors} window={windowSel} />
            <GateRuleDrilldown    colors={colors} window={windowSel} />
            <ConfidenceDrilldown  colors={colors} window={windowSel} />
            <ExposureDrilldown    colors={colors} window={windowSel} />

            {/* ── Footer — provenance + read-only reassurance ────── */}
            <Text style={[styles.footnote, { color: colors.textMuted }]}>
              Computed at {new Date(summary.computedAt).toLocaleString()}
              {summary.windowStart
                ? ` · Window ${summary.window} · ${new Date(summary.windowStart).toLocaleDateString()} → ${new Date(summary.windowEnd).toLocaleDateString()}`
                : ` · Window ${summary.window} · forward-only history`}
              .{'\n'}
              Attribution is observation, not adjudication. The gate is never
              evaluated as right or wrong from PnL alone — it trades expected
              return for drawdown containment.
            </Text>
          </>
        )}
      </ScrollView>
    </AdminShell>
  );
}

// ── Components ─────────────────────────────────────────────────────────

function SectionHeader({
  title, subtitle, colors, subdued,
}: { title: string; subtitle?: string; colors: any; subdued?: boolean }) {
  return (
    <View style={styles.sectionHeader}>
      <Text style={[
        styles.sectionTitle,
        { color: subdued ? colors.textSecondary : colors.textPrimary },
      ]}>
        {title}
      </Text>
      {subtitle && (
        <Text style={[styles.sectionSub, { color: colors.textMuted }]}>{subtitle}</Text>
      )}
    </View>
  );
}

function LineageRow({
  stage, description, agg, colors, supported, isFinal,
}: {
  stage: string;
  description: string;
  agg: LayerAgg;
  colors: any;
  supported: boolean;
  isFinal?: boolean;
}) {
  return (
    <View style={[
      styles.lineageRow,
      { borderBottomColor: colors.border },
      isFinal && { backgroundColor: colors.bgSecondary },
    ]}>
      <View style={styles.layerCell}>
        <View style={styles.layerStageRow}>
          <View style={[
            styles.stageDot,
            { backgroundColor: isFinal ? colors.accent : colors.textSecondary },
          ]} />
          <Text style={[
            styles.stageName,
            {
              color: supported ? colors.textPrimary : colors.textMuted,
              fontWeight: isFinal ? '800' : '700',
            },
          ]}>
            {stage}
          </Text>
        </View>
        <Text style={[styles.stageDesc, { color: colors.textMuted }]}>
          {description}
        </Text>
        {!supported && agg.note && (
          <Text style={[styles.stageNote, { color: colors.textMuted }]} numberOfLines={2}>
            {agg.note}
          </Text>
        )}
      </View>

      {supported ? (
        <>
          <MetricCell value={fmtNum(agg.tradeCount)} colors={colors} />
          <MetricCell value={fmtPct(agg.hitRatePct)} colors={colors} />
          <MetricCell value={fmtPctSigned(agg.meanReturnPct)} colors={colors} />
          <MetricCell value={fmtUsd(agg.cumulativePnlUsd)} colors={colors} />
          <MetricCell value={fmtPct(agg.maxDrawdownPct)} colors={colors} />
          <MetricCell value={fmtNum(agg.sharpeLike)} colors={colors} />
        </>
      ) : (
        <View style={styles.unsupportedCell}>
          <Text style={[styles.unsupportedText, { color: colors.textMuted }]}>
            n/a — raw lineage forward-only from T11.1b
          </Text>
        </View>
      )}
    </View>
  );
}

function MetricCell({ value, colors }: { value: string; colors: any }) {
  return (
    <View style={styles.metricCell}>
      <Text style={[styles.metricValue, { color: colors.textPrimary }]}>{value}</Text>
    </View>
  );
}

function PreservationStat({
  label, value, caption, colors,
}: { label: string; value: string; caption: string; colors: any }) {
  return (
    <View style={styles.preservationStat}>
      <Text style={[styles.cardLabel, { color: colors.textMuted }]}>{label}</Text>
      <Text style={[styles.preservationValue, { color: colors.textPrimary }]}>{value}</Text>
      <Text style={[styles.preservationCaption, { color: colors.textMuted }]}>{caption}</Text>
    </View>
  );
}

function RulePill({
  label, value, colors,
}: { label: string; value: number; colors: any }) {
  return (
    <View style={[styles.rulePill, { backgroundColor: colors.bgSecondary, borderColor: colors.border }]}>
      <Text style={[styles.rulePillValue, { color: colors.textPrimary }]}>{value}</Text>
      <Text style={[styles.rulePillLabel, { color: colors.textMuted }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  scroll: { padding: 24, gap: 16 },

  head: { flexDirection: 'row', alignItems: 'flex-start', gap: 16 },
  h1: { fontSize: 24, fontWeight: '800', letterSpacing: -0.2 },
  sub: { fontSize: 13, lineHeight: 19, maxWidth: 820, marginTop: 4 },

  windowSwitcher: { flexDirection: 'row', borderWidth: 1, borderRadius: 8, padding: 3, gap: 2 },
  windowBtn: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 6, minWidth: 56, alignItems: 'center' },
  windowBtnText: { fontSize: 12, fontWeight: '700', letterSpacing: 0.4 },

  errBox: { borderLeftWidth: 3, padding: 10, borderRadius: 4 },
  errText: { fontSize: 12 },
  loadingBox: { padding: 40, alignItems: 'center' },

  // Top strip
  topStrip: {
    flexDirection: 'row',
    borderWidth: 1,
    borderRadius: 10,
    padding: 16,
    gap: 16,
    flexWrap: 'wrap',
    alignItems: 'flex-start',
  },
  pipelineCell: { flex: 2, minWidth: 240, gap: 4 },
  pipelineHeadRow: { flexDirection: 'row', alignItems: 'center' },
  pipelineValue: { fontSize: 18, fontWeight: '800', fontFamily: 'monospace', marginTop: 2 },
  pipelineCaption: { fontSize: 11, lineHeight: 15, marginTop: 4, maxWidth: 320 },

  divider: { width: 1, alignSelf: 'stretch' },

  coverageCell: { flex: 1, minWidth: 160, gap: 4 },
  coverageValue: { fontSize: 22, fontWeight: '800', fontFamily: 'monospace', marginTop: 2 },
  coverageCaption: { fontSize: 11, lineHeight: 15, marginTop: 2 },
  coverageBar: { height: 4, borderRadius: 2, marginTop: 8, overflow: 'hidden' },
  coverageFill: { height: '100%', borderRadius: 2 },
  gateSplitRow: { flexDirection: 'row', gap: 6, marginTop: 2 },
  gateSplit: { fontSize: 11, fontFamily: 'monospace' },

  cardLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2 },

  // Honesty banner
  honestyBanner: {
    flexDirection: 'row',
    gap: 12,
    padding: 14,
    borderRadius: 10,
    borderWidth: 1,
    alignItems: 'flex-start',
  },
  honestyTitle: { fontSize: 13, fontWeight: '700', marginBottom: 4 },
  honestyBody: { fontSize: 12, lineHeight: 17 },

  // Section header
  sectionHeader: { gap: 4, marginTop: 8 },
  sectionTitle: { fontSize: 16, fontWeight: '800', letterSpacing: 0.2 },
  sectionSub: { fontSize: 12, lineHeight: 17, maxWidth: 820 },

  // Lineage comparison table
  lineageTable: { borderWidth: 1, borderRadius: 10, overflow: 'hidden' },
  lineageRow: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    alignItems: 'stretch',
    minHeight: 56,
  },
  lineageHeader: { paddingVertical: 6 },
  lineageHeadText: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2 },

  layerCell: { flex: 2.4, minWidth: 220, paddingHorizontal: 14, paddingVertical: 12, justifyContent: 'center', gap: 3 },
  layerCellHead: { paddingVertical: 8 },
  layerStageRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  stageDot: { width: 8, height: 8, borderRadius: 4 },
  stageName: { fontSize: 12, fontWeight: '700', letterSpacing: 1 },
  stageDesc: { fontSize: 11, lineHeight: 15, marginLeft: 16 },
  stageNote: { fontSize: 10, lineHeight: 14, marginLeft: 16, marginTop: 2, fontStyle: 'italic' },

  metricCell: { flex: 1, minWidth: 90, paddingHorizontal: 8, paddingVertical: 12, alignItems: 'flex-end', justifyContent: 'center' },
  metricCellHead: { paddingVertical: 8 },
  metricValue: { fontSize: 13, fontFamily: 'monospace', fontWeight: '700' },

  unsupportedCell: { flex: 6, paddingHorizontal: 8, paddingVertical: 12, justifyContent: 'center', alignItems: 'flex-end' },
  unsupportedText: { fontSize: 11, fontStyle: 'italic' },

  tableCaption: { fontSize: 11, lineHeight: 16, fontStyle: 'italic', maxWidth: 820 },

  // Preservation panel
  preservationPanel: { borderWidth: 1, borderRadius: 10, padding: 16, gap: 16 },
  preservationTopRow: { flexDirection: 'row', gap: 24, flexWrap: 'wrap' },
  preservationStat: { flex: 1, minWidth: 220, gap: 4 },
  preservationValue: { fontSize: 26, fontWeight: '800', fontFamily: 'monospace', marginTop: 4 },
  preservationCaption: { fontSize: 11, lineHeight: 15 },

  preservationRules: { borderTopWidth: 1, paddingTop: 14 },
  preservationRulesRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },

  rulePill: {
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
    minWidth: 130,
    gap: 2,
  },
  rulePillValue: { fontSize: 18, fontWeight: '800', fontFamily: 'monospace' },
  rulePillLabel: { fontSize: 10, fontWeight: '500' },

  framingBlock: {
    borderTopWidth: 1,
    paddingTop: 10,
    flexDirection: 'row',
    gap: 8,
    alignItems: 'flex-start',
  },
  framingText: { fontSize: 11, lineHeight: 16, flex: 1, fontStyle: 'italic' },

  // Lost opportunity panel
  lostPanel: { borderWidth: 1, borderRadius: 10, overflow: 'hidden' },
  lostHeadRow: { flexDirection: 'row', borderBottomWidth: 1, paddingHorizontal: 14, paddingVertical: 10 },
  lostHeadCell: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2 },
  lostRow: { flexDirection: 'row', borderBottomWidth: 1, paddingHorizontal: 14, paddingVertical: 10, alignItems: 'center' },
  lostCell: { fontSize: 12 },
  lostColTime:  { flex: 1.4, minWidth: 140 },
  lostColSym:   { flex: 0.7, minWidth: 80 },
  lostColRule:  { flex: 1.4, minWidth: 140 },
  lostColSize:  { flex: 1.0, minWidth: 100, textAlign: 'right' },
  lostColPrice: { flex: 1.0, minWidth: 100, textAlign: 'right' },
  lostEmpty: { padding: 24, alignItems: 'center' },
  lostEmptyText: { fontSize: 12, fontStyle: 'italic' },
  lostMoreRow: { paddingHorizontal: 14, paddingVertical: 8 },
  lostMoreText: { fontSize: 11, fontStyle: 'italic' },

  footnote: { fontSize: 11, fontStyle: 'italic', marginTop: 4, lineHeight: 17 },
});
