/**
 * BrokerScreen — T10.2A · Operator Desk · BROKER tab.
 *
 * OPERATIONAL TRANSPARENCY, NOT TRADING CONTROLS.
 *
 * This screen is deliberately **not** a "BUY/SELL NOW" UI. It surfaces the
 * state of the broker bridge (Sprint T10.1) so the operator can SEE:
 *
 *   1. BROKER HEADER     — provider · mode · connection · safe-mode · heartbeat
 *   2. GATE MATRIX       — 11 live-submit checks, grouped CONFIG / MARKET /
 *                          RISK / EXECUTION (not flat).
 *   3. MARKETS           — curated tradable list (every `tradable=false` today)
 *   4. RISK ACKNOWLEDGE  — UI checkbox + explicit "UI ack ≠ authority" pill.
 *                          Backend authority is env-controlled. Local UI
 *                          checkbox persists only in-memory.
 *   5. AUDIT FEED        — every live/submit attempt with finalStatus row
 *                          chip (refused / simulated / submitted / failed /
 *                          cancelled), newest-first, refusal reason inline.
 *
 * Invariants that MUST hold even if T10.2B/C wires real submit:
 *   * No button on this screen ever places an order
 *   * The only POST this screen issues is `dryRunLiveSubmit` against the
 *     T10.1 safe-mode endpoint — which is hard-coded to refuse.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../../core/useColors';
import {
  brokerBridgeApi,
  BrokerStatus,
  AuditRow,
  BrokerMarket,
  GATE_GROUPS,
  GATE_LABELS,
  AuditFinalStatus,
} from '../../../services/api/broker-bridge-api';

const POLL_INTERVAL_MS = 30_000;

export function BrokerScreen() {
  const colors = useColors();
  const styles = useMemo(() => makeStyles(colors), [colors]);

  const [status, setStatus] = useState<BrokerStatus | null>(null);
  const [markets, setMarkets] = useState<BrokerMarket[]>([]);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  // We pull a representative gate run by issuing a dry-run "preflight + submit"
  // against the symbol the user is most likely watching. Default BTC.
  const [gateChecks, setGateChecks] = useState<{ name: string; passed: boolean; detail: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // UI-only acknowledgement state — has zero effect on backend gate
  const [uiAck, setUiAck] = useState(false);

  const load = useCallback(async () => {
    try {
      setError(null);

      // Read-only observability calls fail loud — they should always succeed
      // for anyone with tradingOsVisible (route already gates that).
      const [s, m, a] = await Promise.all([
        brokerBridgeApi.getStatus(),
        brokerBridgeApi.getMarkets(),
        brokerBridgeApi.getAudit(50),
      ]);
      setStatus(s);
      setMarkets(m.markets || []);
      setAudit((a.audit || []) as AuditRow[]);

      // Gate-matrix probe: T10.1 invariant says this ALWAYS refuses, but
      // TIER-2 backend gates the endpoint on liveTrading capability. For
      // a paper / operator-console caller that's an honest 403 — we degrade
      // the gate-matrix block to "live gate hidden, requires live operator"
      // instead of crashing the whole page.
      try {
        const dryRun = await brokerBridgeApi.dryRunLiveSubmit({ symbol: 'BTC', action: 'LONG', sizeUsd: 100 });
        setGateChecks(dryRun.gateChecks || []);
      } catch (gateErr: any) {
        // 403 here is expected for paper-only operators. Anything else
        // is a real surface error worth surfacing.
        const sc = gateErr?.response?.status;
        if (sc !== 403) {
          // Non-auth probe error — still keep page usable but surface it.
          // Do NOT block status/markets/audit observability.
          console.warn('[broker] gate probe failed:', gateErr?.message);
        }
        setGateChecks([]);
      }
    } catch (e: any) {
      // Only observability failures land here — those are real outages.
      setError(e?.message || 'failed to load broker state');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [load]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    load();
  }, [load]);

  if (loading && !status) {
    return (
      <View style={[styles.center, { backgroundColor: colors.background }]}>
        <ActivityIndicator color={colors.accent} />
        <Text style={[styles.muted, { color: colors.textMuted, marginTop: 8 }]}>
          loading broker bridge state…
        </Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.background }}
      contentContainerStyle={styles.scroll}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          tintColor={colors.accent}
        />
      }
      testID="broker-screen"
    >
      {error && (
        <View style={[styles.errorBanner, { borderLeftColor: colors.sell || '#ef4444', backgroundColor: colors.surface }]}>
          <Text style={[styles.errorText, { color: colors.sell || '#ef4444' }]}>{error}</Text>
        </View>
      )}

      {/* ── 1. BROKER HEADER ───────────────────────────────────────── */}
      {status && <BrokerHeader status={status} colors={colors} />}

      {/* ── 2. GATE MATRIX (grouped) ───────────────────────────────── */}
      <GateMatrix checks={gateChecks} colors={colors} />

      {/* ── 3. MARKETS ─────────────────────────────────────────────── */}
      <MarketsBlock markets={markets} colors={colors} />

      {/* ── 4. RISK ACKNOWLEDGEMENT ────────────────────────────────── */}
      {status && (
        <RiskAcknowledgement
          status={status}
          uiAck={uiAck}
          onToggle={() => setUiAck(v => !v)}
          colors={colors}
        />
      )}

      {/* ── 5. AUDIT FEED ──────────────────────────────────────────── */}
      <AuditFeed rows={audit} colors={colors} />

      <Text style={[styles.footnote, { color: colors.textMuted }]}>
        Operational transparency layer · no orders are submitted from this screen
      </Text>
    </ScrollView>
  );
}

// ── 1. BROKER HEADER ────────────────────────────────────────────────


function BrokerHeader({ status, colors }: { status: BrokerStatus; colors: any }) {
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const modeBadge = (() => {
    if (status.liveSubmitEnabled) {
      return { label: 'LIVE ARMED', tone: colors.sell || '#ef4444' };
    }
    if (status.mode === 'live') {
      return { label: 'LIVE DISABLED', tone: '#9ca3af' };
    }
    return { label: 'SAFE MODE', tone: '#f59e0b' };
  })();
  const connTone = status.connected ? (colors.buy || '#22c55e') : '#9ca3af';
  const heartbeatRaw = status.lastSuccessfulHeartbeat || status.asOf;
  const heartbeat = new Date(heartbeatRaw).toLocaleTimeString();

  // T10.2B — CAPABILITY is the most important badge. Promoted above provider.
  const cap = status.capability || 'unconfigured';
  const capInfo = (() => {
    switch (cap) {
      case 'readonly_verified':
        return { label: 'READ-ONLY VERIFIED', tone: colors.buy || '#22c55e', tonal: 'good' };
      case 'trading_permissions_detected':
        return {
          label: 'DEGRADED — TRADING PERMISSIONS DETECTED',
          tone: colors.sell || '#ef4444',
          tonal: 'bad',
        };
      case 'degraded':
        return { label: 'DEGRADED', tone: '#f59e0b', tonal: 'warn' };
      default:
        return { label: 'UNCONFIGURED', tone: '#9ca3af', tonal: 'neutral' };
    }
  })();

  return (
    <View style={[styles.headerCard, { backgroundColor: colors.surface, borderColor: modeBadge.tone }]} testID="broker-header">
      <View style={styles.headerTopRow}>
        <Text style={[styles.headerTitle, { color: colors.textPrimary }]}>BROKER BRIDGE</Text>
        <View style={[styles.modePill, { backgroundColor: modeBadge.tone }]} testID="broker-mode-badge">
          <Text style={styles.modePillText}>{modeBadge.label}</Text>
        </View>
      </View>

      {/* T10.2B — Capability row, prominent above everything else */}
      <View style={[styles.capabilityRow, { borderColor: capInfo.tone }]} testID="broker-capability">
        <View style={styles.capabilityLeft}>
          <Text style={[styles.capabilityLabel, { color: colors.textMuted }]}>CAPABILITY</Text>
          <Text style={[styles.capabilityValue, { color: capInfo.tone }]} numberOfLines={2}>
            {capInfo.label}
          </Text>
        </View>
        <Ionicons
          name={
            cap === 'readonly_verified' ? 'shield-checkmark' :
            cap === 'trading_permissions_detected' ? 'alert-circle' :
            'shield-half'
          }
          size={26}
          color={capInfo.tone}
        />
      </View>

      <View style={styles.headerGrid}>
        <HeaderCell label="PROVIDER" value={status.config.provider} colors={colors} />
        <HeaderCell label="MODE" value={status.mode.toUpperCase()} colors={colors} />
        <HeaderCell label="ADAPTER" value={status.adapter} colors={colors} />
        <HeaderCell
          label="CONNECTION"
          value={status.connected ? 'connected' : 'offline'}
          tone={connTone}
          colors={colors}
        />
        <HeaderCell
          label="RISK ACK (ENV)"
          value={status.config.riskAckSigned ? 'signed' : 'unsigned'}
          tone={status.config.riskAckSigned ? (colors.buy || '#22c55e') : '#9ca3af'}
          colors={colors}
        />
        <HeaderCell
          label="LAST HEARTBEAT"
          value={heartbeat}
          tone={status.lastSuccessfulHeartbeat ? colors.textPrimary : '#9ca3af'}
          colors={colors}
        />
      </View>

      {status.lastError && (
        <View style={[styles.errorBanner, { borderLeftColor: '#f59e0b', backgroundColor: 'rgba(245, 158, 11, 0.08)' }]} testID="broker-last-error">
          <Text style={[styles.lastErrText, { color: '#f59e0b' }]} numberOfLines={2}>
            last error · {status.lastError}
          </Text>
        </View>
      )}

      <Text style={[styles.headerVersion, { color: colors.textMuted }]}>
        {status.version}
      </Text>
    </View>
  );
}

function HeaderCell({ label, value, tone, colors }: { label: string; value: string; tone?: string; colors: any }) {
  const styles = useMemo(() => makeStyles(colors), [colors]);
  return (
    <View style={styles.headerCell}>
      <Text style={[styles.headerCellLabel, { color: colors.textMuted }]}>{label}</Text>
      <Text style={[styles.headerCellValue, { color: tone || colors.textPrimary }]} numberOfLines={1}>{value}</Text>
    </View>
  );
}

// ── 2. GATE MATRIX ──────────────────────────────────────────────────


function GateMatrix({
  checks, colors,
}: { checks: { name: string; passed: boolean; detail: string }[]; colors: any }) {
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const byName = useMemo(() => {
    const m: Record<string, { passed: boolean; detail: string }> = {};
    for (const c of checks) m[c.name] = { passed: c.passed, detail: c.detail };
    return m;
  }, [checks]);

  const passed = checks.filter(c => c.passed).length;
  const total = checks.length || 11;

  return (
    <View style={styles.section} testID="gate-matrix">
      <View style={styles.sectionTitleRow}>
        <Text style={[styles.sectionTitle, { color: colors.textMuted }]}>LIVE SUBMIT GATE</Text>
        <Text style={[styles.gateScore, { color: passed === total ? (colors.buy || '#22c55e') : '#f59e0b' }]}>
          {passed}/{total} passing
        </Text>
      </View>

      {Object.entries(GATE_GROUPS).map(([groupName, rules]) => {
        const groupPassed = rules.filter(r => byName[r]?.passed).length;
        const groupAll = rules.length;
        const groupTone = groupPassed === groupAll
          ? (colors.buy || '#22c55e')
          : groupPassed === 0 ? (colors.sell || '#ef4444') : '#f59e0b';
        return (
          <View
            key={groupName}
            style={[styles.gateGroup, { backgroundColor: colors.surface, borderColor: colors.border }]}
            testID={`gate-group-${groupName.toLowerCase()}`}
          >
            <View style={styles.gateGroupHeader}>
              <Text style={[styles.gateGroupTitle, { color: colors.textPrimary }]}>{groupName}</Text>
              <Text style={[styles.gateGroupCount, { color: groupTone }]}>
                {groupPassed}/{groupAll}
              </Text>
            </View>
            {rules.map((rule, i) => {
              const c = byName[rule];
              const passed = !!c?.passed;
              const tone = passed ? (colors.buy || '#22c55e') : (colors.sell || '#ef4444');
              return (
                <View
                  key={rule}
                  style={[styles.gateRow, i !== rules.length - 1 && { borderBottomColor: colors.border, borderBottomWidth: StyleSheet.hairlineWidth }]}
                  testID={`gate-row-${rule}`}
                >
                  <Ionicons
                    name={passed ? 'checkmark-circle' : 'close-circle'}
                    size={16}
                    color={tone}
                  />
                  <View style={styles.gateRowText}>
                    <Text style={[styles.gateRowName, { color: colors.textPrimary }]}>
                      {GATE_LABELS[rule] || rule}
                    </Text>
                    {!passed && c?.detail ? (
                      <Text style={[styles.gateRowDetail, { color: colors.textMuted }]} numberOfLines={2}>
                        {c.detail}
                      </Text>
                    ) : null}
                  </View>
                </View>
              );
            })}
          </View>
        );
      })}
    </View>
  );
}

// ── 3. MARKETS ──────────────────────────────────────────────────────


function MarketsBlock({ markets, colors }: { markets: BrokerMarket[]; colors: any }) {
  const styles = useMemo(() => makeStyles(colors), [colors]);
  return (
    <View style={styles.section} testID="markets-block">
      <Text style={[styles.sectionTitle, { color: colors.textMuted }]}>SUPPORTED MARKETS</Text>
      <View style={[styles.marketsTable, { borderColor: colors.border, backgroundColor: colors.surface }]}>
        {markets.map((m, i) => (
          <View
            key={m.symbol}
            style={[
              styles.marketRow,
              i !== markets.length - 1 && { borderBottomColor: colors.border, borderBottomWidth: StyleSheet.hairlineWidth },
            ]}
            testID={`market-row-${m.symbol}`}
          >
            <View style={{ flex: 1 }}>
              <Text style={[styles.marketSymbol, { color: colors.textPrimary }]}>{m.symbol}</Text>
              <Text style={[styles.marketSub, { color: colors.textMuted }]}>
                {m.pair} · min ${m.minNotionalUsd}
              </Text>
            </View>
            <View style={[
              styles.tradableBadge,
              { backgroundColor: m.tradable ? (colors.buy || '#22c55e') : (colors.border || 'rgba(127,127,127,0.18)') },
              { borderWidth: m.tradable ? 0 : 1, borderColor: colors.border },
            ]}>
              <Text style={[
                styles.tradableBadgeText,
                { color: m.tradable ? '#FFFFFF' : colors.textSecondary },
              ]}>
                {m.tradable ? 'tradable' : 'not tradable'}
              </Text>
            </View>
          </View>
        ))}
      </View>
    </View>
  );
}

// ── 4. RISK ACKNOWLEDGEMENT ─────────────────────────────────────────


function RiskAcknowledgement({
  status, uiAck, onToggle, colors,
}: { status: BrokerStatus; uiAck: boolean; onToggle: () => void; colors: any }) {
  const styles = useMemo(() => makeStyles(colors), [colors]);
  return (
    <View style={styles.section} testID="risk-ack">
      <Text style={[styles.sectionTitle, { color: colors.textMuted }]}>RISK ACKNOWLEDGEMENT</Text>
      <View style={[styles.ackCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        <Text style={[styles.ackBody, { color: colors.textPrimary }]}>
          The broker bridge is currently in <Text style={{ fontWeight: '700' }}>safe mode</Text>.
          No real orders can be placed regardless of any action on this screen.
        </Text>
        <Text style={[styles.ackBody, { color: colors.textPrimary, marginTop: 8 }]}>
          When the system is ready for live execution, the operator must
          understand: deployments are capped, position size is restrained by
          the adaptive layer, and any single trade can be refused by the
          portfolio gate or drawdown breaker.
        </Text>

        <TouchableOpacity
          style={styles.ackCheckboxRow}
          onPress={onToggle}
          activeOpacity={0.7}
          testID="risk-ack-checkbox"
        >
          <Ionicons
            name={uiAck ? 'checkbox' : 'square-outline'}
            size={22}
            color={uiAck ? (colors.buy || '#22c55e') : colors.textMuted}
          />
          <Text style={[styles.ackCheckboxLabel, { color: colors.textPrimary }]}>
            I understand this is operational transparency only.
          </Text>
        </TouchableOpacity>

        <View style={[styles.ackPill, { borderColor: '#f59e0b' }]}>
          <Ionicons name="information-circle" size={14} color="#f59e0b" />
          <Text style={styles.ackPillText}>
            UI acknowledgement only · backend live gate remains env-controlled
          </Text>
        </View>

        <View style={styles.ackEnvRow}>
          <Text style={[styles.ackEnvLabel, { color: colors.textMuted }]}>
            BACKEND RISK_ACK_SIGNED
          </Text>
          <Text style={[
            styles.ackEnvValue,
            { color: status.config.riskAckSigned ? (colors.buy || '#22c55e') : '#9ca3af' },
          ]}>
            {status.config.riskAckSigned ? 'signed (env)' : 'unsigned'}
          </Text>
        </View>
      </View>
    </View>
  );
}

// ── 5. AUDIT FEED ───────────────────────────────────────────────────


const STATUS_TONE: Record<AuditFinalStatus, string> = {
  refused: '#9ca3af',
  refused_t10_1_safe_mode: '#f59e0b',
  simulated: '#3b82f6',
  submitted: '#22c55e',
  failed: '#ef4444',
  cancelled: '#9ca3af',
};

const STATUS_LABEL: Record<AuditFinalStatus, string> = {
  refused: 'REFUSED',
  refused_t10_1_safe_mode: 'SAFE-MODE',
  simulated: 'SIMULATED',
  submitted: 'SUBMITTED',
  failed: 'FAILED',
  cancelled: 'CANCELLED',
};


function AuditFeed({ rows, colors }: { rows: AuditRow[]; colors: any }) {
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const [expanded, setExpanded] = useState<string | null>(null);
  if (!rows || rows.length === 0) {
    return (
      <View style={styles.section} testID="audit-feed-empty">
        <Text style={[styles.sectionTitle, { color: colors.textMuted }]}>AUDIT FEED</Text>
        <Text style={[styles.muted, { color: colors.textMuted, paddingVertical: 12 }]}>
          no submit attempts yet
        </Text>
      </View>
    );
  }
  return (
    <View style={styles.section} testID="audit-feed">
      <View style={styles.sectionTitleRow}>
        <Text style={[styles.sectionTitle, { color: colors.textMuted }]}>AUDIT FEED</Text>
        <Text style={[styles.muted, { color: colors.textMuted }]}>
          {rows.length} attempt{rows.length === 1 ? '' : 's'} · newest first
        </Text>
      </View>
      {rows.slice(0, 20).map((row) => {
        const tone = STATUS_TONE[row.finalStatus] || colors.textMuted;
        const label = STATUS_LABEL[row.finalStatus] || row.finalStatus;
        const time = new Date(row.attemptAt).toLocaleTimeString();
        const isOpen = expanded === row.auditId;
        return (
          <TouchableOpacity
            key={row.auditId}
            style={[
              styles.auditRow,
              { backgroundColor: colors.surface, borderColor: colors.border, borderLeftColor: tone },
            ]}
            onPress={() => setExpanded(isOpen ? null : row.auditId)}
            activeOpacity={0.8}
            testID={`audit-row-${row.auditId}`}
          >
            <View style={styles.auditRowTop}>
              <View style={[styles.auditStatusPill, { backgroundColor: tone }]}>
                <Text style={styles.auditStatusText}>{label}</Text>
              </View>
              <Text style={[styles.auditSymbol, { color: colors.textPrimary }]}>
                {row.symbol} · {row.action}
              </Text>
              <Text style={[styles.auditSize, { color: colors.textMuted }]}>
                ${row.requestedSizeUsd}
              </Text>
              <Text style={[styles.auditTime, { color: colors.textMuted }]}>{time}</Text>
            </View>
            {row.refusedReasons && row.refusedReasons.length > 0 && (
              <Text
                style={[styles.auditReason, { color: colors.textMuted }]}
                numberOfLines={isOpen ? undefined : 1}
              >
                {row.refusedReasons.join(' · ')}
              </Text>
            )}
            {isOpen && (
              <View style={styles.auditExpanded}>
                <Text style={[styles.auditMeta, { color: colors.textMuted }]}>
                  audit {row.auditId} · gate {row.gateSnapshot?.permission || '—'}
                  {row.gateSnapshot?.blockReason ? ` (${row.gateSnapshot.blockReason})` : ''}
                </Text>
                <Text style={[styles.auditMeta, { color: colors.textMuted, marginTop: 2 }]}>
                  sizing.final ${row.sizingSnapshot?.final ?? '—'} ·
                  drawdown {row.gateSnapshot?.drawdownPct ?? '—'}%
                </Text>
              </View>
            )}
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

// ── Styles ──────────────────────────────────────────────────────────


const makeStyles = (colors: any) => StyleSheet.create({
  scroll: { padding: 16, paddingBottom: 40 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  muted: { fontSize: 11 },

  errorBanner: { borderLeftWidth: 3, paddingLeft: 12, paddingVertical: 8, marginBottom: 16, borderRadius: 6 },
  errorText: { fontSize: 12, fontWeight: '600' },

  // Header
  headerCard: { borderWidth: 1.5, borderRadius: 12, padding: 14, marginBottom: 16 },
  headerTopRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  headerTitle: { fontSize: 13, fontWeight: '800', letterSpacing: 1.5 },
  modePill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 4 },
  modePillText: { fontSize: 10, fontWeight: '800', letterSpacing: 1.2, color: '#FFFFFF' },
  capabilityRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    borderWidth: 1, borderRadius: 8, padding: 10, marginBottom: 12,
  },
  capabilityLeft: { flex: 1 },
  capabilityLabel: { fontSize: 9, letterSpacing: 1.2, textTransform: 'uppercase', fontWeight: '700' },
  capabilityValue: { fontSize: 13, fontWeight: '800', marginTop: 3, letterSpacing: 0.5 },
  lastErrText: { fontSize: 10, fontWeight: '600' },
  headerGrid: { flexDirection: 'row', flexWrap: 'wrap' },
  headerCell: { width: '50%', paddingVertical: 6 },
  headerCellLabel: { fontSize: 9, letterSpacing: 1, textTransform: 'uppercase' },
  headerCellValue: { fontSize: 12, fontWeight: '700', marginTop: 2 },
  headerVersion: { fontSize: 9, marginTop: 8, letterSpacing: 0.5 },

  // Sections
  section: { marginBottom: 20 },
  sectionTitle: { fontSize: 11, letterSpacing: 1.5, fontWeight: '700', textTransform: 'uppercase' },
  sectionTitleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  gateScore: { fontSize: 11, fontWeight: '700' },

  // Gate Matrix
  gateGroup: { borderWidth: 1, borderRadius: 10, padding: 10, marginBottom: 8 },
  gateGroupHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  gateGroupTitle: { fontSize: 11, fontWeight: '800', letterSpacing: 1.5 },
  gateGroupCount: { fontSize: 11, fontWeight: '700' },
  gateRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, paddingVertical: 7 },
  gateRowText: { flex: 1 },
  gateRowName: { fontSize: 12, fontWeight: '600' },
  gateRowDetail: { fontSize: 10, marginTop: 2, lineHeight: 14 },

  // Markets
  marketsTable: { borderWidth: 1, borderRadius: 10 },
  marketRow: { flexDirection: 'row', alignItems: 'center', padding: 12 },
  marketSymbol: { fontSize: 13, fontWeight: '700' },
  marketSub: { fontSize: 10, marginTop: 2 },
  tradableBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4 },
  tradableBadgeText: { fontSize: 9, fontWeight: '700', letterSpacing: 0.8, textTransform: 'uppercase' },

  // Risk Ack
  ackCard: { borderWidth: 1, borderRadius: 10, padding: 14 },
  ackBody: { fontSize: 12, lineHeight: 17 },
  ackCheckboxRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, marginTop: 4 },
  ackCheckboxLabel: { fontSize: 12, fontWeight: '600', flex: 1 },
  ackPill: { flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 6, marginTop: 6 },
  ackPillText: { fontSize: 10, fontWeight: '600', color: '#f59e0b', flex: 1 },
  ackEnvRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 10, paddingTop: 8, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  ackEnvLabel: { fontSize: 9, letterSpacing: 1, textTransform: 'uppercase' },
  ackEnvValue: { fontSize: 11, fontWeight: '700' },

  // Audit Feed
  auditRow: { borderWidth: 1, borderLeftWidth: 3, borderRadius: 8, padding: 10, marginBottom: 6 },
  auditRowTop: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  auditStatusPill: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 3 },
  auditStatusText: { fontSize: 9, fontWeight: '800', letterSpacing: 0.5, color: '#FFFFFF' },
  auditSymbol: { fontSize: 12, fontWeight: '700' },
  auditSize: { fontSize: 11 },
  auditTime: { fontSize: 10, marginLeft: 'auto' },
  auditReason: { fontSize: 10, marginTop: 6, lineHeight: 14 },
  auditExpanded: { marginTop: 8, paddingTop: 8, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  auditMeta: { fontSize: 10 },

  footnote: { fontSize: 10, textAlign: 'center', marginTop: 12, fontStyle: 'italic' },
});
