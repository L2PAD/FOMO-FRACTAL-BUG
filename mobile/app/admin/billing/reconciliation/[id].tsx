/**
 * /admin/billing/reconciliation/[id] — TIER-4B.2
 *
 * Finding detail surface.  Shows the IMMUTABLE evidence snapshot
 * captured at detection time plus the append-only attestation
 * timeline.  Operator can attest (acknowledge or mark resolved
 * later) — these are SECONDARY events and never mutate the finding
 * itself.
 *
 * UI INVARIANTS:
 *   * Evidence is rendered as a read-only snapshot view, never as
 *     editable JSON
 *   * No "Resolve issue" / "Fix automatically" controls
 *   * Acknowledge ≠ Mark resolved later — visually distinguished
 *   * Attestation timeline is full append-only history
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Pressable, Modal,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { AdminShell } from '../../../../src/admin/components/AdminShell';
import { adminApi } from '../../../../src/admin/api/adminClient';
import { useColors } from '../../../../src/core/useColors';

const CATEGORY_LABEL: Record<string, string> = {
  stuck_pending:               'Stuck pending invoice',
  entitlement_mismatch:        'Entitlement mismatch',
  tier_without_billing_trail:  'Tier without billing trail',
  failed_activation:           'Failed activation',
  refunded_but_not_downgraded: 'Refunded but not downgraded',
  orphan_audit_row:            'Orphan audit row',
};
const CATEGORY_BLURB: Record<string, string> = {
  stuck_pending:               'A pending invoice has remained unconfirmed past the integrity threshold. Cause may be legitimate payment-rail delay or a stalled manual confirmation — review and escalate.',
  entitlement_mismatch:        'A paid invoice and the user’s current tier do not agree. May indicate manual tier rewrite, missed activation, or post-refund timing drift.',
  tier_without_billing_trail:  'A user carries a paid tier without any matching paid invoice. May be an admin grant / comp / promotional uplift — confirm with the granting operator.',
  failed_activation:           'A paid invoice was never followed by an entitlement_activated audit row. Customer paid but did not receive their entitlement — critical.',
  refunded_but_not_downgraded: 'A refund event was recorded without a matching downgrade event. Tier was not walked back commercially — integrity break.',
  orphan_audit_row:            'A billing_audit row references an invoiceId that no longer exists. Usually a sign of manual db cleanup or a partial delete.',
};

function fmtTs(iso?: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toISOString().replace('T', ' ').replace(/\..+/, ' UTC');
  } catch { return iso || '—'; }
}

interface Finding {
  findingId: string;
  findingType: string;
  severity: 'info' | 'elevated' | 'critical';
  userId: string | null;
  invoiceId: string | null;
  detectedAt: string;
  scanId: string;
  parentFindingId: string | null;
  status: 'open' | 'acknowledged' | 'resolved_later';
  evidence: any;
}
interface Attestation {
  attestationId: string;
  findingId: string;
  action: 'acknowledge' | 'mark_resolved_later';
  actor: string;
  reason: string | null;
  note: string | null;
  ts: string;
}

export default function FindingDetailScreen() {
  const colors = useColors();
  const router = useRouter();
  const params = useLocalSearchParams<{ id: string }>();
  const findingId = decodeURIComponent(String(params.id || ''));

  const [finding, setFinding] = useState<Finding | null>(null);
  const [attestations, setAttestations] = useState<Attestation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [modalOpen, setModalOpen] = useState<null | 'acknowledge' | 'mark_resolved_later'>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await adminApi.reconciliationGetFinding(findingId);
      setFinding(res.finding);
      setAttestations(res.attestations || []);
    } catch (e: any) {
      setError(e?.response?.data?.detail?.error || e?.message || 'Failed to load finding');
    } finally {
      setLoading(false);
    }
  }, [findingId]);

  useEffect(() => { load(); }, [load]);

  if (loading && !finding) {
    return (
      <AdminShell>
        <View style={[styles.center, { backgroundColor: colors.background }]}>
          <ActivityIndicator color={colors.accent} />
        </View>
      </AdminShell>
    );
  }
  if (!finding) {
    return (
      <AdminShell>
        <ScrollView contentContainerStyle={[styles.scroll, { backgroundColor: colors.background }]}>
          <BackLink onPress={() => router.replace('/admin/billing/reconciliation' as any)} />
          <View style={[styles.errBox, { borderColor: colors.danger, backgroundColor: colors.badgeHighBg }]}>
            <Text style={[styles.errText, { color: colors.badgeHighText }]}>
              {error || 'Finding not found.'}
            </Text>
          </View>
        </ScrollView>
      </AdminShell>
    );
  }

  return (
    <AdminShell>
      <ScrollView contentContainerStyle={[styles.scroll, { backgroundColor: colors.background }]}>
        <BackLink onPress={() => router.replace('/admin/billing/reconciliation' as any)} />

        {/* Header */}
        <View style={styles.head}>
          <View style={{ flex: 1 }}>
            <Text style={[styles.h1, { color: colors.textPrimary }]}>
              {CATEGORY_LABEL[finding.findingType] || finding.findingType}
            </Text>
            <View style={styles.headMetaRow}>
              <SevPill severity={finding.severity} colors={colors} />
              <StatusPill status={finding.status} colors={colors} />
              <Text style={[styles.headMeta, { color: colors.textMuted }]}>·</Text>
              <Text style={[styles.headMeta, { color: colors.textMuted }]}>
                detected <Text style={{ color: colors.textSecondary, fontWeight: '700' }}>{fmtTs(finding.detectedAt)}</Text>
              </Text>
            </View>
            <Text style={[styles.blurb, { color: colors.textSecondary }]}>
              {CATEGORY_BLURB[finding.findingType] || ''}
            </Text>
          </View>

          {/* Attestation cluster — no Resolve / Fix controls anywhere */}
          <View style={styles.actions}>
            <ActionBtn
              icon="checkmark-outline"
              label="Acknowledge"
              kind="info"
              onPress={() => setModalOpen('acknowledge')}
              colors={colors}
            />
            <ActionBtn
              icon="time-outline"
              label="Mark resolved later"
              kind="positive"
              onPress={() => setModalOpen('mark_resolved_later')}
              colors={colors}
            />
          </View>
        </View>

        {/* Reminder banner */}
        <View style={[styles.banner, { borderColor: colors.border, backgroundColor: colors.surface }]}>
          <Ionicons name="information-circle-outline" size={16} color={colors.textMuted} />
          <Text style={[styles.bannerText, { color: colors.textMuted }]}>
            Reconciliation observes commercial integrity. It never auto-heals, refunds, rewrites tiers or revokes
            authority — these remain explicit operator actions inside /admin/billing or /admin/operators.
            Attesting a finding does not close it; the finding stays in the ledger as a historical observation.
          </Text>
        </View>

        {/* Two-column body */}
        <View style={styles.cols}>
          {/* LEFT: finding record + evidence snapshot */}
          <View style={styles.colLeft}>
            <Section title="Finding record" colors={colors}>
              <KV k="Finding ID"    v={finding.findingId} mono colors={colors} />
              <KV k="Type"          v={finding.findingType} mono colors={colors} />
              <KV k="Severity"      v={finding.severity.toUpperCase()} colors={colors} />
              <KV k="Status"        v={finding.status.replace('_', ' ').toUpperCase()} colors={colors} />
              <KV k="Detected"      v={fmtTs(finding.detectedAt)} mono colors={colors} />
              <KV k="Scan"          v={finding.scanId} mono colors={colors} />
              <KV k="User"          v={finding.userId || '—'} mono colors={colors} />
              <KV k="Invoice"       v={finding.invoiceId || '—'} mono colors={colors} />
              {finding.parentFindingId && (
                <KV k="Escalated from" v={finding.parentFindingId} mono colors={colors} />
              )}
            </Section>

            <Section
              title="Evidence snapshot at detection"
              subtitle="Captured at detection time. Immutable — future state changes do not drift this view."
              colors={colors}
            >
              <View style={[styles.snapshotBox, { borderColor: colors.border, backgroundColor: colors.background }]}>
                <Text style={[styles.snapshotJson, { color: colors.textSecondary }]} selectable>
                  {JSON.stringify(finding.evidence ?? {}, null, 2)}
                </Text>
              </View>
            </Section>
          </View>

          {/* RIGHT: attestation timeline */}
          <View style={styles.colRight}>
            <Section title="Attestation timeline" subtitle="Append-only · separate from the finding itself" colors={colors}>
              {attestations.length === 0 ? (
                <Text style={[styles.muted, { color: colors.textMuted }]}>
                  No attestations yet. This finding is still open.
                </Text>
              ) : (
                <View style={{ gap: 12 }}>
                  {attestations.map(a => (
                    <View key={a.attestationId} style={[styles.attCard, { borderColor: colors.border, backgroundColor: colors.background }]}>
                      <View style={styles.attHead}>
                        <AttActionPill action={a.action} colors={colors} />
                        <View style={{ flex: 1 }} />
                        <Text style={[styles.attTs, { color: colors.textMuted }]}>{fmtTs(a.ts)}</Text>
                      </View>
                      <Text style={[styles.attActor, { color: colors.textSecondary }]}>
                        actor · <Text style={{ color: colors.textPrimary, fontFamily: 'monospace', fontWeight: '700' }}>{a.actor}</Text>
                      </Text>
                      {a.reason && (
                        <Text style={[styles.attReason, { color: colors.textSecondary }]}>
                          reason · {a.reason}
                        </Text>
                      )}
                      {a.note && (
                        <Text style={[styles.attReason, { color: colors.textSecondary }]}>
                          note · {a.note}
                        </Text>
                      )}
                    </View>
                  ))}
                </View>
              )}
            </Section>
          </View>
        </View>
      </ScrollView>

      <AttestationModal
        visible={modalOpen !== null}
        action={modalOpen || 'acknowledge'}
        findingId={finding.findingId}
        onCancel={() => setModalOpen(null)}
        onConfirm={async ({ reason, note }) => {
          await adminApi.reconciliationAttest(finding.findingId, modalOpen!, reason, note);
          await load();
        }}
      />
    </AdminShell>
  );
}

// ── Components ─────────────────────────────────────────────────────────

function AttestationModal({
  visible, action, findingId, onCancel, onConfirm,
}: {
  visible: boolean;
  action: 'acknowledge' | 'mark_resolved_later';
  findingId: string;
  onCancel: () => void;
  onConfirm: (args: { reason: string; note: string }) => Promise<void>;
}) {
  const colors = useColors();
  const [reason, setReason] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const close = () => {
    if (busy) return;
    setReason(''); setNote(''); setErr(null);
    onCancel();
  };

  const title = action === 'acknowledge' ? 'Acknowledge finding' : 'Mark finding resolved later';
  const explainer = action === 'acknowledge'
    ? 'Records that an operator has reviewed this finding. The underlying record remains open in the ledger — acknowledgement is a separate attestation event, not a resolution.'
    : 'Records that the underlying anomaly has resolved itself (e.g. delayed payment cleared, manual fix applied elsewhere). The finding remains in the ledger as historical evidence; this is a secondary attestation, not a deletion.';

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      await onConfirm({ reason: reason.trim(), note: note.trim() });
      setReason(''); setNote('');
      onCancel();
    } catch (e: any) {
      setErr(e?.response?.data?.detail?.error || e?.message || 'Attestation failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={close}>
      <View style={[styles.backdrop, { backgroundColor: 'rgba(0,0,0,0.55)' }]}>
        <View style={[styles.modalCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <View style={styles.modalHead}>
            <Ionicons
              name={action === 'acknowledge' ? 'checkmark-outline' : 'time-outline'}
              size={20}
              color={colors.accent}
            />
            <Text style={[styles.modalTitle, { color: colors.textPrimary }]}>{title}</Text>
          </View>
          <Text style={[styles.modalBlurb, { color: colors.textMuted }]}>
            {explainer}
          </Text>
          <Text style={[styles.modalIdHint, { color: colors.textMuted }]}>
            Finding: <Text style={{ fontFamily: 'monospace', color: colors.textSecondary }}>{findingId}</Text>
          </Text>

          <Text style={[styles.fieldLabel, { color: colors.textMuted, marginTop: 14 }]}>REASON (optional)</Text>
          <TextInput
            value={reason}
            onChangeText={setReason}
            placeholder="Operational note for the audit trail…"
            placeholderTextColor={colors.textMuted}
            style={[
              styles.input,
              { color: colors.textPrimary, borderColor: colors.border, backgroundColor: colors.background, minHeight: 60 },
            ]}
            multiline
            editable={!busy}
          />
          <Text style={[styles.fieldLabel, { color: colors.textMuted, marginTop: 14 }]}>NOTE (optional, free-form)</Text>
          <TextInput
            value={note}
            onChangeText={setNote}
            placeholder="Free-form context for future operators…"
            placeholderTextColor={colors.textMuted}
            style={[
              styles.input,
              { color: colors.textPrimary, borderColor: colors.border, backgroundColor: colors.background, minHeight: 60 },
            ]}
            multiline
            editable={!busy}
          />

          {err && (
            <View style={[styles.modalErr, { borderColor: colors.danger, backgroundColor: colors.badgeHighBg }]}>
              <Text style={[styles.errText, { color: colors.badgeHighText }]}>{err}</Text>
            </View>
          )}

          <View style={styles.modalFoot}>
            <TouchableOpacity onPress={close} disabled={busy} style={[styles.modalBtn, { borderColor: colors.border }]}>
              <Text style={[styles.modalBtnText, { color: colors.textSecondary }]}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity
              onPress={submit}
              disabled={busy}
              style={[
                styles.modalBtn,
                { backgroundColor: colors.accent, borderColor: colors.accent, opacity: busy ? 0.6 : 1 },
              ]}
            >
              {busy
                ? <ActivityIndicator color={colors.accentText} size="small" />
                : <Text style={[styles.modalBtnText, { color: colors.accentText, fontWeight: '700' }]}>
                    {action === 'acknowledge' ? 'Acknowledge' : 'Mark resolved later'}
                  </Text>}
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

function BackLink({ onPress }: { onPress: () => void }) {
  const colors = useColors();
  return (
    <Pressable onPress={onPress} style={styles.backLink}>
      <Ionicons name="arrow-back" size={14} color={colors.textSecondary} />
      <Text style={[styles.backLinkText, { color: colors.textSecondary }]}>Back to reconciliation</Text>
    </Pressable>
  );
}

function Section({
  title, subtitle, colors, children,
}: { title: string; subtitle?: string; colors: any; children: React.ReactNode }) {
  return (
    <View style={[styles.section, { backgroundColor: colors.surface, borderColor: colors.border }]}>
      <Text style={[styles.sectionTitle, { color: colors.textPrimary }]}>{title}</Text>
      {subtitle && <Text style={[styles.sectionSub, { color: colors.textMuted }]}>{subtitle}</Text>}
      <View style={{ marginTop: 10, gap: 6 }}>{children}</View>
    </View>
  );
}

function KV({ k, v, mono, colors }: { k: string; v: string; mono?: boolean; colors: any }) {
  return (
    <View style={styles.kv}>
      <Text style={[styles.kvKey, { color: colors.textMuted }]}>{k}</Text>
      <Text style={[styles.kvVal, { color: colors.textPrimary, fontFamily: mono ? 'monospace' : undefined }]} numberOfLines={1}>
        {v}
      </Text>
    </View>
  );
}

function SevPill({ severity, colors }: { severity: string; colors: any }) {
  const map: Record<string, { bg: string; fg: string }> = {
    info:     { bg: colors.badgeLowBg || colors.surfaceHover, fg: colors.badgeLowText || colors.buy },
    elevated: { bg: colors.badgeMidBg || colors.surfaceHover, fg: colors.badgeMidText || colors.accent },
    critical: { bg: colors.badgeHighBg, fg: colors.badgeHighText },
  };
  const p = map[severity] || map.info;
  return (
    <View style={[styles.pill, { backgroundColor: p.bg }]}>
      <Text style={[styles.pillText, { color: p.fg }]}>{severity.toUpperCase()}</Text>
    </View>
  );
}

function StatusPill({ status, colors }: { status: string; colors: any }) {
  const map: Record<string, { bg: string; fg: string; label: string }> = {
    open:           { bg: colors.badgeHighBg, fg: colors.badgeHighText, label: 'STILL OPEN' },
    acknowledged:   { bg: colors.badgeMidBg || colors.surfaceHover, fg: colors.badgeMidText || colors.accent, label: 'ACKNOWLEDGED' },
    resolved_later: { bg: colors.badgeLowBg || colors.surfaceHover, fg: colors.badgeLowText || colors.buy, label: 'RESOLVED LATER' },
  };
  const p = map[status] || map.open;
  return (
    <View style={[styles.pill, { backgroundColor: p.bg }]}>
      <Text style={[styles.pillText, { color: p.fg }]}>{p.label}</Text>
    </View>
  );
}

function AttActionPill({ action, colors }: { action: string; colors: any }) {
  const map: Record<string, { bg: string; fg: string; label: string }> = {
    acknowledge:        { bg: colors.badgeMidBg || colors.surfaceHover, fg: colors.badgeMidText || colors.accent, label: 'ACKNOWLEDGE' },
    mark_resolved_later:{ bg: colors.badgeLowBg || colors.surfaceHover, fg: colors.badgeLowText || colors.buy, label: 'RESOLVED LATER' },
  };
  const p = map[action] || map.acknowledge;
  return (
    <View style={[styles.pill, { backgroundColor: p.bg }]}>
      <Text style={[styles.pillText, { color: p.fg }]}>{p.label}</Text>
    </View>
  );
}

function ActionBtn({
  icon, label, kind, onPress, colors,
}: { icon: any; label: string; kind: 'info' | 'positive'; onPress: () => void; colors: any }) {
  const bg = kind === 'info' ? colors.accent : colors.buy;
  return (
    <TouchableOpacity onPress={onPress} style={[styles.actionBtn, { backgroundColor: bg, borderColor: bg }]}>
      <Ionicons name={icon} size={14} color={colors.accentText} />
      <Text style={[styles.actionBtnText, { color: colors.accentText }]}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  scroll: { padding: 24, gap: 16 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  backLink: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  backLinkText: { fontSize: 12, fontWeight: '600' },

  head: { flexDirection: 'row', alignItems: 'flex-start', gap: 16 },
  h1: { fontSize: 22, fontWeight: '800', letterSpacing: -0.2 },
  headMetaRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10, flexWrap: 'wrap' },
  headMeta: { fontSize: 12 },
  blurb: { fontSize: 13, lineHeight: 19, marginTop: 10, maxWidth: 780 },
  actions: { flexDirection: 'column', gap: 8, alignItems: 'flex-end' },
  actionBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 6, borderWidth: 1, minWidth: 180,
    justifyContent: 'center',
  },
  actionBtnText: { fontSize: 12, fontWeight: '700', letterSpacing: 0.2 },

  banner: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, padding: 12, borderRadius: 8, borderWidth: 1 },
  bannerText: { fontSize: 12, flex: 1, lineHeight: 17 },

  cols: { flexDirection: 'row', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' },
  colLeft: { flex: 1.1, minWidth: 360, gap: 16 },
  colRight: { flex: 1, minWidth: 320 },
  section: { borderWidth: 1, borderRadius: 10, padding: 16 },
  sectionTitle: { fontSize: 14, fontWeight: '800', letterSpacing: 0.2 },
  sectionSub: { fontSize: 11, marginTop: 4, lineHeight: 16 },

  kv: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  kvKey: { fontSize: 10, fontWeight: '700', letterSpacing: 1, width: 130 },
  kvVal: { fontSize: 12, flex: 1 },

  snapshotBox: { borderWidth: 1, borderRadius: 6, padding: 12, marginTop: 6 },
  snapshotJson: { fontSize: 10, fontFamily: 'monospace', lineHeight: 14 },

  muted: { fontSize: 12 },

  errBox: { borderLeftWidth: 3, padding: 10, borderRadius: 4 },
  errText: { fontSize: 12 },

  attCard: { borderWidth: 1, borderRadius: 8, padding: 12, gap: 4 },
  attHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  attTs: { fontSize: 10, fontFamily: 'monospace' },
  attActor: { fontSize: 11 },
  attReason: { fontSize: 11, fontStyle: 'italic' },

  pill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4, alignSelf: 'flex-start' },
  pillText: { fontSize: 9, fontWeight: '800', letterSpacing: 0.8 },

  // modal
  backdrop: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  modalCard: { width: '100%', maxWidth: 520, borderWidth: 1, borderRadius: 12, padding: 22 },
  modalHead: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  modalTitle: { fontSize: 16, fontWeight: '800' },
  modalBlurb: { fontSize: 12, lineHeight: 17, marginTop: 8 },
  modalIdHint: { fontSize: 11, marginTop: 6 },
  fieldLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2 },
  input: { borderWidth: 1, borderRadius: 6, padding: 10, fontSize: 13 },
  modalErr: { borderLeftWidth: 3, padding: 8, marginTop: 10, borderRadius: 4 },
  modalFoot: { flexDirection: 'row', justifyContent: 'flex-end', gap: 10, marginTop: 16 },
  modalBtn: { paddingHorizontal: 16, paddingVertical: 10, borderRadius: 6, borderWidth: 1, minWidth: 110, alignItems: 'center' },
  modalBtnText: { fontSize: 13, fontWeight: '500' },
});
