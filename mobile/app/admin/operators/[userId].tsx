/**
 * /admin/operators/[userId] — operator governance detail (Phase 3C).
 *
 * Friction-graduated mutation controls:
 *   * LOW  : tier change → inline dropdown
 *   * MED  : capability override / mode / console access → ConfirmActionModal w/ reason
 *   * HIGH : grant live authority → TypedConfirmationModal w/ exact phrase + reason + ack
 *
 * INVARIANTS enforced:
 *   * No optimistic UI — every mutation awaits the backend response and
 *     then triggers an authoritative refetch of the operator row + audit
 *     timeline.  UI never previews a state the backend hasn't confirmed.
 *   * No frontend derivation — capability matrix, source, effectiveSummary
 *     all come from the backend resolver.
 *   * Capability source colour vocabulary is global and documented:
 *       admin_grant  → accent
 *       admin_revoke → sell (red)
 *       tier_default → secondary
 *       not_granted  → muted
 *       expired      → sell (red)
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  Pressable,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { AdminShell } from '../../../src/admin/components/AdminShell';
import { adminApi } from '../../../src/admin/api/adminClient';
import { useColors } from '../../../src/core/useColors';
import { ConfirmActionModal } from '../../../src/admin/components/modals/ConfirmActionModal';
import { TypedConfirmationModal } from '../../../src/admin/components/modals/TypedConfirmationModal';

const CAPS = ['tradingOsVisible', 'paperTrading', 'shadowTrading', 'executionConsole', 'liveTrading'] as const;
type CapName = typeof CAPS[number];

// ── Pending action descriptor for the medium-friction modal ───────────
type PendingAction =
  | { kind: 'override'; cap: CapName; value: 'granted' | 'revoked' | 'clear' }
  | { kind: 'mode'; mode: 'none' | 'paper' | 'shadow' | 'live' }
  | { kind: 'console'; value: boolean }
  | { kind: 'revoke-blanket' }
  | { kind: 'revoke-live' }
  | null;

const SEVERITY_FILTERS = ['', 'info', 'elevated', 'critical'] as const;

function timeAgo(iso?: string | null): string {
  if (!iso) return 'never';
  const t = Date.parse(iso);
  if (!isFinite(t)) return 'never';
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s/60)}m ago`;
  if (s < 86400) return `${Math.floor(s/3600)}h ago`;
  return `${Math.floor(s/86400)}d ago`;
}

export default function OperatorDetailScreen() {
  const colors = useColors();
  const router = useRouter();
  const { userId } = useLocalSearchParams<{ userId: string }>();
  const uid = String(userId);

  const [row, setRow] = useState<any | null>(null);
  const [audit, setAudit] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pending modal state
  const [pending, setPending] = useState<PendingAction>(null);
  const [liveGrantOpen, setLiveGrantOpen] = useState(false);

  // Audit filter
  const [auditSeverity, setAuditSeverity] = useState<string>('');

  // Authoritative fetch — replaces local state from backend response
  const fetchOperator = useCallback(async () => {
    const list = await adminApi.listOperators({ q: uid, limit: 1 });
    const t = await adminApi.auditTimeline(uid, auditSeverity || undefined, 100);
    return { row: list.rows[0] || null, audit: t.rows || [] };
  }, [uid, auditSeverity]);

  const reload = useCallback(async (mode: 'initial' | 'refresh' = 'refresh') => {
    if (mode === 'initial') setLoading(true);
    else setRefreshing(true);
    setError(null);
    try {
      const { row: r, audit: a } = await fetchOperator();
      setRow(r);
      setAudit(a);
    } catch (e: any) {
      setError(e?.message || 'Failed to load operator');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [fetchOperator]);

  useEffect(() => { reload('initial'); }, [reload]);

  // ── Mutation runners ────────────────────────────────────────────────
  // EVERY mutation is followed by reload() — no optimistic state.

  const onTierChange = useCallback(async (newTier: 'free' | 'pro' | 'trader') => {
    try {
      await adminApi.setTier(uid, newTier);
      await reload();
    } catch (e: any) {
      setError(e?.response?.data?.detail?.error || e?.message || 'Failed to set tier');
    }
  }, [uid, reload]);

  const runPendingAction = useCallback(async (reason: string) => {
    if (!pending) return;
    if (pending.kind === 'override') {
      await adminApi.overrideCapability(uid, pending.cap, pending.value, reason || undefined);
    } else if (pending.kind === 'mode') {
      await adminApi.setMode(uid, pending.mode);
    } else if (pending.kind === 'console') {
      await adminApi.setConsoleAccess(uid, pending.value);
    } else if (pending.kind === 'revoke-blanket') {
      await adminApi.revoke(uid, reason || undefined);
    } else if (pending.kind === 'revoke-live') {
      await adminApi.revokeLiveAuthority(uid, reason);
    }
    await reload();
  }, [pending, uid, reload]);

  const runLiveGrant = useCallback(
    async ({ typed, reason, expiresAt }: { typed: string; reason: string; expiresAt: string | null }) => {
      await adminApi.grantLiveAuthority(uid, typed, reason, expiresAt);
      await reload();
    },
    [uid, reload],
  );

  // Refetch audit when severity filter changes
  useEffect(() => {
    if (!loading && row) {
      (async () => {
        try {
          const t = await adminApi.auditTimeline(uid, auditSeverity || undefined, 100);
          setAudit(t.rows || []);
        } catch {}
      })();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auditSeverity]);

  const oa = row?.operatorAccess || {};
  const caps = row?.capabilities || {};
  const liveAuth = oa.liveAuthority || {};

  return (
    <AdminShell>
      <ScrollView contentContainerStyle={[styles.scroll, { backgroundColor: colors.background }]}>
        <TouchableOpacity onPress={() => router.push('/admin/operators')} style={styles.back}>
          <Ionicons name="chevron-back" size={16} color={colors.textSecondary} />
          <Text style={[styles.backText, { color: colors.textSecondary }]}>back to operators</Text>
        </TouchableOpacity>

        <View style={styles.headRow}>
          <View style={{ flex: 1 }}>
            <Text style={[styles.h1, { color: colors.textPrimary }]} numberOfLines={1}>{uid}</Text>
            <Text style={[styles.sub, { color: colors.textSecondary }]}>
              Operational snapshot. Last touched {timeAgo(oa.lastCapabilityChangeAt)} by{' '}
              <Text style={{ color: colors.textPrimary }}>{oa.lastCapabilityChangedBy || '—'}</Text>.
            </Text>
          </View>
          <TouchableOpacity onPress={() => reload()} disabled={refreshing} style={[styles.refreshBtn, { borderColor: colors.border }]}>
            {refreshing ? <ActivityIndicator size="small" color={colors.textSecondary}/> :
              <><Ionicons name="refresh-outline" size={14} color={colors.textSecondary}/>
              <Text style={[styles.refreshText, { color: colors.textSecondary }]}>refresh</Text></>}
          </TouchableOpacity>
        </View>

        {loading && <ActivityIndicator color={colors.accent} />}
        {error && (
          <View style={[styles.errBox, { borderColor: colors.danger, backgroundColor: colors.badgeHighBg }]}>
            <Text style={[styles.errText, { color: colors.badgeHighText }]}>{error}</Text>
          </View>
        )}

        {row && (
          <>
            {/* ── Commercial: Tier (low friction inline dropdown) ── */}
            <Section title="Commercial tier"
              subtitle="Billing positioning. Does not grant or revoke operational capabilities."
              colors={colors}>
              <View style={styles.tierRow}>
                <Text style={[styles.label, { color: colors.textMuted }]}>TIER</Text>
                <View style={[styles.selectWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                  {/* @ts-ignore native select on web */}
                  <select
                    value={row.tier || 'free'}
                    onChange={(e: any) => onTierChange(e.target.value)}
                    style={{
                      background: 'transparent',
                      color: colors.textPrimary,
                      border: 'none',
                      outline: 'none',
                      fontSize: 13,
                      padding: '8px 10px',
                      minWidth: 140,
                    } as any}
                  >
                    <option value="free">free</option>
                    <option value="pro">pro</option>
                    <option value="trader">trader</option>
                  </select>
                </View>
                <Text style={[styles.tierHint, { color: colors.textMuted }]}>
                  trader → auto-grants paper workspace · NEVER live capital
                </Text>
              </View>
            </Section>

            {/* ── Capability matrix with per-row controls ── */}
            <Section
              title="Capability matrix"
              subtitle="Effective state with source attribution. Override > status revoke > admin grant > tier default."
              colors={colors}
            >
              <View style={[styles.matrixHead, { borderBottomColor: colors.border }]}>
                <MatrixCell flex={2.2} text="Capability" header colors={colors}/>
                <MatrixCell flex={0.7} text="Effective" header colors={colors}/>
                <MatrixCell flex={1.4} text="Source" header colors={colors}/>
                <MatrixCell flex={0.9} text="Override" header colors={colors}/>
                <MatrixCell flex={2.2} text="Action" header colors={colors}/>
              </View>
              {CAPS.map((cap) => {
                const cell = (caps.structured || {})[cap] || { effective: false, source: 'not_granted', override: 'none' };
                const overrideValue = (oa.capabilityOverrides || {})[cap]?.value;
                return (
                  <View key={cap} style={[styles.matrixRow, { borderBottomColor: colors.border }]}>
                    <MatrixCell flex={2.2} text={cap} colors={colors}/>
                    <MatrixCell flex={0.7}
                      text={cell.effective ? '✓' : '×'}
                      color={cell.effective ? colors.buy : colors.textMuted}
                      colors={colors}/>
                    <MatrixCell flex={1.4} text={cell.source} colors={colors}
                      color={
                        cell.source === 'admin_revoke' ? colors.sell :
                        cell.source === 'admin_grant'  ? colors.accent :
                        cell.source === 'tier_default' ? colors.textSecondary : colors.textMuted
                      }/>
                    <MatrixCell flex={0.9} text={cell.override} colors={colors}
                      color={
                        cell.override === 'manual'  ? colors.accent :
                        cell.override === 'expired' ? colors.sell : colors.textMuted
                      }/>
                    <View style={[styles.matrixCell, { flex: 2.2, flexDirection: 'row', gap: 6, flexWrap: 'wrap' }]}>
                      <SmallBtn label="grant" onPress={() => setPending({ kind: 'override', cap, value: 'granted' })} colors={colors} variant="accent"/>
                      <SmallBtn label="revoke" onPress={() => setPending({ kind: 'override', cap, value: 'revoked' })} colors={colors} variant="danger"/>
                      <SmallBtn label="clear" onPress={() => setPending({ kind: 'override', cap, value: 'clear' })} colors={colors} variant="muted" disabled={!overrideValue}/>
                    </View>
                  </View>
                );
              })}
              {Object.keys(oa.capabilityOverrides || {}).length === 0 && (
                <Text style={[styles.hint, { color: colors.textMuted, padding: 10 }]}>
                  No explicit overrides — all capabilities resolve via tier defaults and admin grants only.
                </Text>
              )}
            </Section>

            {/* ── Effective summary ── */}
            <Section title="Effective access" subtitle="Rendered server-side." colors={colors}>
              <View style={styles.summaryRow}>
                <View style={styles.summaryCol}>
                  <Text style={[styles.summaryHead, { color: colors.buy }]}>CAN</Text>
                  {(caps.effectiveSummary?.can || []).map((s: string) => (
                    <Text key={s} style={[styles.summaryItem, { color: colors.textPrimary }]}>✓ {s}</Text>
                  ))}
                  {(caps.effectiveSummary?.can || []).length === 0 && (
                    <Text style={[styles.summaryItem, { color: colors.textMuted, fontStyle: 'italic' }]}>nothing</Text>
                  )}
                </View>
                <View style={styles.summaryCol}>
                  <Text style={[styles.summaryHead, { color: colors.sell }]}>CANNOT</Text>
                  {(caps.effectiveSummary?.cannot || []).map((s: string) => (
                    <Text key={s} style={[styles.summaryItem, { color: colors.textSecondary }]}>× {s}</Text>
                  ))}
                </View>
              </View>
            </Section>

            {/* ── Operational controls: mode, console ── */}
            <Section title="Operational controls" subtitle="Mode and console access. Independent from billing tier." colors={colors}>
              <View style={styles.controlRow}>
                <View style={styles.controlCol}>
                  <Text style={[styles.label, { color: colors.textMuted }]}>BROKER MODE</Text>
                  <Text style={[styles.controlNote, { color: colors.textMuted }]}>
                    Connection mode. NOT coupled to live trading authority.
                  </Text>
                  <View style={styles.btnRow}>
                    {(['paper', 'shadow', 'live'] as const).map(m => (
                      <SmallBtn key={m}
                        label={m}
                        onPress={() => setPending({ kind: 'mode', mode: m })}
                        colors={colors}
                        variant={oa.mode === m ? 'accentSolid' : 'outline'}
                      />
                    ))}
                  </View>
                </View>
                <View style={styles.controlCol}>
                  <Text style={[styles.label, { color: colors.textMuted }]}>CONSOLE ACCESS</Text>
                  <Text style={[styles.controlNote, { color: colors.textMuted }]}>
                    Operator scheduler / runtime control. Customer surface never auto-grants.
                  </Text>
                  <View style={styles.btnRow}>
                    <SmallBtn label={oa.consoleAccess ? '● enabled' : '○ enable'} onPress={() => setPending({ kind: 'console', value: true })}  colors={colors} variant={oa.consoleAccess ? 'accentSolid' : 'outline'}/>
                    <SmallBtn label={!oa.consoleAccess ? '● disabled' : '○ disable'} onPress={() => setPending({ kind: 'console', value: false })} colors={colors} variant={!oa.consoleAccess ? 'mutedSolid' : 'outline'}/>
                  </View>
                </View>
              </View>
            </Section>

            {/* ── Live authority (high friction) ── */}
            <Section
              title="Live capital authority"
              subtitle="Highest-friction grant. Distinct from broker mode. Requires typed confirmation and audit reason."
              colors={colors}
              critical
            >
              <View style={styles.liveBlock}>
                <Text style={[styles.liveStatus, {
                  color: liveAuth.granted ? colors.sell : colors.textMuted,
                }]}>
                  {liveAuth.granted ? '● GRANTED' : '○ not granted'}
                </Text>
                {liveAuth.granted && (
                  <View style={{ marginTop: 6 }}>
                    <Text style={[styles.liveMeta, { color: colors.textSecondary }]}>
                      granted by <Text style={{ color: colors.textPrimary }}>{liveAuth.grantedBy || '—'}</Text> · {liveAuth.grantedAt}
                    </Text>
                    {liveAuth.reason && (
                      <Text style={[styles.liveMeta, { color: colors.textSecondary, fontStyle: 'italic' }]}>
                        “{liveAuth.reason}”
                      </Text>
                    )}
                    <Text style={[styles.liveMeta, { color: colors.textSecondary }]}>
                      expires: <Text style={{ color: colors.textPrimary }}>{liveAuth.expiresAt || 'never'}</Text>
                    </Text>
                  </View>
                )}
                <View style={[styles.btnRow, { marginTop: 12 }]}>
                  <TouchableOpacity
                    onPress={() => setLiveGrantOpen(true)}
                    style={[styles.bigBtn, { backgroundColor: colors.sell, borderColor: colors.sell }]}
                    testID="live-grant-open"
                  >
                    <Ionicons name="warning-outline" size={14} color={colors.accentText}/>
                    <Text style={[styles.bigBtnText, { color: colors.accentText }]}>Grant live authority…</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    onPress={() => setPending({ kind: 'revoke-live' })}
                    disabled={!liveAuth.granted}
                    style={[styles.bigBtn, {
                      borderColor: colors.border,
                      backgroundColor: 'transparent',
                      opacity: liveAuth.granted ? 1 : 0.4,
                    }]}
                  >
                    <Text style={[styles.bigBtnText, { color: colors.textSecondary }]}>Revoke live authority…</Text>
                  </TouchableOpacity>
                </View>
              </View>
            </Section>

            {/* ── Audit timeline (first-class panel) ── */}
            <Section
              title="Audit timeline"
              subtitle="Append-only. Severity locked by action vocab; never client-set."
              colors={colors}
            >
              <View style={styles.auditFilters}>
                <Text style={[styles.label, { color: colors.textMuted, marginRight: 8 }]}>SEVERITY</Text>
                {SEVERITY_FILTERS.map(s => (
                  <Pressable key={s || 'all'} onPress={() => setAuditSeverity(s)}
                    style={({ hovered }: any) => [
                      styles.sevPill,
                      {
                        borderColor: auditSeverity === s ? colors.accent : colors.border,
                        backgroundColor: auditSeverity === s ? colors.surfaceHover : 'transparent',
                      },
                      hovered && { backgroundColor: colors.surfaceHover },
                    ]}>
                    <Text style={[styles.sevPillText, {
                      color: auditSeverity === s ? colors.textPrimary : colors.textMuted,
                      fontWeight: auditSeverity === s ? '700' : '500',
                    }]}>{s || 'all'}</Text>
                  </Pressable>
                ))}
              </View>
              {audit.length === 0 && (
                <Text style={[styles.emptyAudit, { color: colors.textMuted }]}>No audit events for this filter.</Text>
              )}
              {audit.map((ev: any, i: number) => (
                <AuditRow key={i} ev={ev} colors={colors}/>
              ))}
            </Section>
          </>
        )}
      </ScrollView>

      {/* ── Confirm modal (medium friction) ── */}
      <ConfirmActionModal
        visible={pending !== null}
        title={pendingTitle(pending)}
        body={<PendingBody pending={pending} colors={colors}/>}
        confirmLabel={pendingConfirmLabel(pending)}
        severity={pendingSeverity(pending)}
        requireReason={pendingRequiresReason(pending)}
        onCancel={() => setPending(null)}
        onConfirm={runPendingAction}
      />

      {/* ── Typed confirmation modal (high friction) ── */}
      <TypedConfirmationModal
        visible={liveGrantOpen}
        phrase="GRANT LIVE TRADING"
        targetUserId={uid}
        warningBody={
          'You are granting authority to deploy LIVE CAPITAL on the connected broker. ' +
          'This is independent from billing tier. The action is logged with severity=critical, ' +
          'is append-only, and CAN be revoked but NOT erased from the audit timeline.'
        }
        ackText="I understand this grants real-money deployment authority and is permanently audited."
        onCancel={() => setLiveGrantOpen(false)}
        onConfirm={runLiveGrant}
      />
    </AdminShell>
  );
}

// ── Pending action helpers ─────────────────────────────────────────────
function pendingTitle(p: PendingAction): string {
  if (!p) return '';
  if (p.kind === 'override') return p.value === 'clear' ? `Clear override on ${p.cap}` : `${p.value === 'granted' ? 'Grant' : 'Revoke'} ${p.cap}`;
  if (p.kind === 'mode') return `Set broker mode → ${p.mode}`;
  if (p.kind === 'console') return p.value ? 'Enable operator console access' : 'Disable operator console access';
  if (p.kind === 'revoke-blanket') return 'Revoke all operator access';
  if (p.kind === 'revoke-live') return 'Revoke live capital authority';
  return '';
}
function pendingConfirmLabel(p: PendingAction): string {
  if (!p) return 'Confirm';
  if (p.kind === 'override') return p.value === 'clear' ? 'Clear override' : (p.value === 'granted' ? 'Grant capability' : 'Revoke capability');
  if (p.kind === 'mode') return 'Set mode';
  if (p.kind === 'console') return p.value ? 'Enable console' : 'Disable console';
  if (p.kind === 'revoke-blanket') return 'Revoke';
  if (p.kind === 'revoke-live') return 'Revoke live authority';
  return 'Confirm';
}
function pendingSeverity(p: PendingAction): 'info' | 'elevated' | 'critical' {
  if (!p) return 'info';
  if (p.kind === 'revoke-live') return 'critical';
  if (p.kind === 'override' && p.cap === 'liveTrading') return 'critical';
  return 'elevated';
}
function pendingRequiresReason(p: PendingAction): boolean {
  if (!p) return false;
  if (p.kind === 'revoke-live') return true;
  if (p.kind === 'override' && p.value === 'revoked') return true;
  if (p.kind === 'override' && p.cap === 'liveTrading') return true;
  return false;
}

function PendingBody({ pending, colors }: { pending: PendingAction; colors: any }) {
  if (!pending) return null;
  if (pending.kind === 'override') {
    return (
      <Text style={{ color: colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
        This will {pending.value === 'clear' ? <Text style={{ color: colors.textPrimary }}>remove the explicit admin override</Text> : <Text style={{ color: pending.value === 'granted' ? colors.accent : colors.sell, fontWeight: '700' }}>{pending.value === 'granted' ? 'GRANT' : 'REVOKE'}</Text>} the
        <Text style={{ color: colors.textPrimary, fontWeight: '700' }}> {pending.cap}</Text> capability for this operator. Per-cap
        overrides take precedence over tier defaults and over status=revoked.
      </Text>
    );
  }
  if (pending.kind === 'mode') {
    return (
      <Text style={{ color: colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
        Switches the broker connection mode. NOT coupled to liveTrading capability —
        live deployment authority must be granted separately via the typed-confirmation flow.
      </Text>
    );
  }
  if (pending.kind === 'console') {
    return (
      <Text style={{ color: colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
        {pending.value ? 'Enables' : 'Disables'} the operator scheduler / runtime console for this user.
        This is the boundary between customer surface and operator surface — customer tiers never auto-grant it.
      </Text>
    );
  }
  if (pending.kind === 'revoke-live') {
    return (
      <Text style={{ color: colors.textSecondary, fontSize: 13, lineHeight: 19 }}>
        Revokes live capital deployment authority. The grant record is cleared in the
        operator_access document; the original grant remains in the immutable audit timeline.
      </Text>
    );
  }
  return null;
}

// ── Audit row ─────────────────────────────────────────────────────────
function AuditRow({ ev, colors }: { ev: any; colors: any }) {
  const sev = ev.severity || 'info';
  const sevColor =
    sev === 'critical' ? colors.sell :
    sev === 'elevated' ? colors.accent : colors.textMuted;
  return (
    <View style={[styles.auditCard, { borderBottomColor: colors.border }]}>
      <View style={styles.auditTop}>
        <View style={[styles.severityDot, { backgroundColor: sevColor }]}/>
        <Text style={[styles.auditAction, { color: colors.textPrimary }]}>{ev.action}</Text>
        <View style={[styles.sevBadge, { backgroundColor: colors.surfaceHover }]}>
          <Text style={[styles.sevBadgeText, { color: sevColor }]}>{sev}</Text>
        </View>
        <Text style={[styles.auditTs, { color: colors.textMuted }]}>{ev.ts}</Text>
      </View>
      <Text style={[styles.auditActor, { color: colors.textSecondary }]}>
        by <Text style={{ color: colors.textPrimary, fontWeight: '600' }}>{ev.actor}</Text>
      </Text>
      {ev.reason && (
        <Text style={[styles.auditReason, { color: colors.textSecondary }]}>“{ev.reason}”</Text>
      )}
      {(ev.before || ev.after) && (
        <View style={styles.diff}>
          <View style={[styles.diffCol, { borderColor: colors.border }]}>
            <Text style={[styles.diffHead, { color: colors.sell }]}>BEFORE</Text>
            <Text style={[styles.diffJson, { color: colors.textMuted }]} numberOfLines={6}>
              {prettyShort(ev.before)}
            </Text>
          </View>
          <View style={[styles.diffCol, { borderColor: colors.border }]}>
            <Text style={[styles.diffHead, { color: colors.buy }]}>AFTER</Text>
            <Text style={[styles.diffJson, { color: colors.textMuted }]} numberOfLines={6}>
              {prettyShort(ev.after)}
            </Text>
          </View>
        </View>
      )}
    </View>
  );
}
function prettyShort(obj: any): string {
  if (!obj) return '—';
  const keys = ['enabled', 'status', 'mode', 'consoleAccess', 'capabilityOverrides', 'liveAuthority'];
  const pick: Record<string, any> = {};
  for (const k of keys) if (k in obj) pick[k] = obj[k];
  return JSON.stringify(pick, null, 2);
}

// ── Layout primitives ─────────────────────────────────────────────────
function Section({ title, subtitle, children, colors, critical }: any) {
  return (
    <View style={[styles.card, {
      backgroundColor: colors.surface,
      borderColor: critical ? colors.sell : colors.border,
      borderWidth: critical ? 1.5 : 1,
    }]}>
      <Text style={[styles.cardTitle, { color: critical ? colors.sell : colors.textPrimary }]}>{title}</Text>
      {subtitle && <Text style={[styles.cardHint, { color: colors.textMuted }]}>{subtitle}</Text>}
      <View style={{ marginTop: 12 }}>{children}</View>
    </View>
  );
}

function MatrixCell({ flex, text, header, color, colors }: any) {
  return (
    <View style={[{ flex }, header ? styles.matrixHeadCell : styles.matrixCell]}>
      <Text
        style={[
          header ? styles.matrixHeadText : styles.matrixCellText,
          { color: color || (header ? colors.textMuted : colors.textPrimary) },
        ]}
        numberOfLines={1}
      >
        {text}
      </Text>
    </View>
  );
}

function SmallBtn({ label, onPress, colors, variant, disabled }: any) {
  const palette: Record<string, { bg: string; border: string; fg: string }> = {
    accent:      { bg: 'transparent',          border: colors.accent,   fg: colors.accent },
    accentSolid: { bg: colors.accent,          border: colors.accent,   fg: colors.accentText },
    danger:      { bg: 'transparent',          border: colors.sell,     fg: colors.sell },
    muted:       { bg: 'transparent',          border: colors.border,   fg: colors.textMuted },
    mutedSolid:  { bg: colors.surfaceHover,    border: colors.border,   fg: colors.textPrimary },
    outline:     { bg: 'transparent',          border: colors.border,   fg: colors.textSecondary },
  };
  const p = palette[variant] || palette.outline;
  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={disabled}
      style={[
        styles.smallBtn,
        { backgroundColor: p.bg, borderColor: p.border, opacity: disabled ? 0.3 : 1 },
      ]}
    >
      <Text style={[styles.smallBtnText, { color: p.fg }]}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  scroll: { padding: 24, gap: 16 },
  back: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  backText: { fontSize: 12 },
  headRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  h1: { fontSize: 22, fontWeight: '800' },
  sub: { fontSize: 12, marginTop: 4 },
  refreshBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: 6, borderWidth: 1, minHeight: 30,
  },
  refreshText: { fontSize: 11, fontWeight: '600' },
  errBox: { borderLeftWidth: 3, padding: 10, borderRadius: 4 },
  errText: { fontSize: 12 },
  card: { padding: 18, borderRadius: 10, gap: 6 },
  cardTitle: { fontSize: 14, fontWeight: '700' },
  cardHint: { fontSize: 11, lineHeight: 16 },
  hint: { fontSize: 11, fontStyle: 'italic' },
  label: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2 },
  tierRow: { flexDirection: 'row', alignItems: 'center', gap: 12, flexWrap: 'wrap' },
  selectWrap: { borderWidth: 1, borderRadius: 6 },
  tierHint: { fontSize: 11, fontStyle: 'italic' },
  matrixHead: { flexDirection: 'row', borderBottomWidth: 1, paddingVertical: 8, marginTop: 6 },
  matrixHeadCell: { paddingHorizontal: 6 },
  matrixHeadText: { fontSize: 10, fontWeight: '700', letterSpacing: 1 },
  matrixRow: { flexDirection: 'row', borderBottomWidth: 1, paddingVertical: 10, alignItems: 'center' },
  matrixCell: { paddingHorizontal: 6 },
  matrixCellText: { fontSize: 13 },
  summaryRow: { flexDirection: 'row', gap: 24, marginTop: 8 },
  summaryCol: { flex: 1, gap: 4 },
  summaryHead: { fontSize: 10, fontWeight: '800', letterSpacing: 1.2, marginBottom: 4 },
  summaryItem: { fontSize: 13 },
  controlRow: { flexDirection: 'row', gap: 24, flexWrap: 'wrap' },
  controlCol: { flex: 1, minWidth: 220, gap: 6 },
  controlNote: { fontSize: 11, lineHeight: 16, marginBottom: 6 },
  btnRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap', marginTop: 4 },
  smallBtn: {
    paddingHorizontal: 10, paddingVertical: 5,
    borderRadius: 4, borderWidth: 1,
  },
  smallBtnText: { fontSize: 11, fontWeight: '600' },
  bigBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingHorizontal: 14, paddingVertical: 10, borderRadius: 6, borderWidth: 1,
  },
  bigBtnText: { fontSize: 13, fontWeight: '700' },
  liveBlock: { gap: 4 },
  liveStatus: { fontSize: 16, fontWeight: '800', letterSpacing: 0.4 },
  liveMeta: { fontSize: 12 },
  auditFilters: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 10, flexWrap: 'wrap' },
  sevPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 4, borderWidth: 1 },
  sevPillText: { fontSize: 11, letterSpacing: 0.4 },
  emptyAudit: { fontSize: 12, padding: 8 },
  auditCard: { paddingVertical: 12, borderBottomWidth: 1, gap: 6 },
  auditTop: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  severityDot: { width: 8, height: 8, borderRadius: 4 },
  auditAction: { fontSize: 13, fontWeight: '700' },
  sevBadge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 3 },
  sevBadgeText: { fontSize: 9, fontWeight: '700', letterSpacing: 0.8 },
  auditTs: { fontSize: 10, marginLeft: 'auto' },
  auditActor: { fontSize: 12 },
  auditReason: { fontSize: 12, fontStyle: 'italic' },
  diff: { flexDirection: 'row', gap: 8, marginTop: 6 },
  diffCol: { flex: 1, borderWidth: 1, borderRadius: 4, padding: 8 },
  diffHead: { fontSize: 9, fontWeight: '800', letterSpacing: 1, marginBottom: 4 },
  diffJson: { fontSize: 10, fontFamily: 'monospace' as any },
});
