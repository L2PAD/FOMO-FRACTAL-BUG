/**
 * BillingRefundModal — TIER-4B.1
 *
 * Refund is a commercial-only mutation: it downgrades tier to `free`
 * and emits an elevated `refund` + `downgrade` audit pair.  It NEVER
 * touches liveAuthority / consoleAccess / capabilityOverrides — those
 * are governance, not finance.
 *
 * Two gates before confirm enables:
 *   1. Exact typed phrase `REFUND` (case-sensitive)
 *   2. Mandatory non-empty `reason`
 *
 * The invariant message is shown prominently inside the modal so the
 * operator is reminded that operational authority is not affected.
 */
import React, { useState } from 'react';
import {
  Modal, View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../../core/useColors';

export interface BillingRefundModalProps {
  visible: boolean;
  invoiceId: string;
  userId: string;
  productCode: string;
  priceUsd: number;
  onCancel: () => void;
  onConfirm: (args: { reason: string }) => Promise<void>;
}

const REQUIRED_PHRASE = 'REFUND';

export function BillingRefundModal(props: BillingRefundModalProps) {
  const colors = useColors();
  const [typed, setTyped] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const phraseMatches = typed === REQUIRED_PHRASE;
  const reasonOk = reason.trim().length > 0;
  const canConfirm = !busy && phraseMatches && reasonOk;

  const close = () => {
    if (busy) return;
    setTyped(''); setReason(''); setError(null);
    props.onCancel();
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await props.onConfirm({ reason: reason.trim() });
      setTyped(''); setReason('');
      props.onCancel();
    } catch (e: any) {
      const code = e?.response?.data?.detail?.error;
      setError(code || e?.message || 'Refund failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal visible={props.visible} transparent animationType="fade" onRequestClose={close}>
      <View style={styles.backdrop}>
        <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.sell }]}>
          <View style={styles.head}>
            <Ionicons name="return-down-back" size={20} color={colors.sell} />
            <Text style={[styles.title, { color: colors.textPrimary }]}>Refund invoice</Text>
          </View>

          <View style={styles.meta}>
            <MetaRow k="Invoice"  v={props.invoiceId}   mono colors={colors} />
            <MetaRow k="Customer" v={props.userId}      mono colors={colors} />
            <MetaRow k="Product"  v={props.productCode} colors={colors} />
            <MetaRow k="Amount"   v={`$${props.priceUsd.toFixed(2)}`} colors={colors} />
          </View>

          <ScrollView style={styles.body}>
            {/* Architectural invariant — always shown */}
            <View style={[styles.warn, { borderColor: colors.sell, backgroundColor: colors.badgeHighBg }]}>
              <Ionicons name="shield-half-outline" size={16} color={colors.badgeHighText} />
              <View style={{ flex: 1 }}>
                <Text style={[styles.warnTitle, { color: colors.badgeHighText }]}>
                  Commercial mutation only
                </Text>
                <Text style={[styles.warnText, { color: colors.badgeHighText }]}>
                  Refund downgrades commercial entitlement only.
                  Live operational authority is governed separately.
                </Text>
              </View>
            </View>

            <Text style={[styles.label, { color: colors.textMuted, marginTop: 16 }]}>
              TYPE TO CONFIRM <Text style={{ color: colors.sell }}>*</Text>
            </Text>
            <Text style={[styles.phraseHint, { color: colors.textSecondary }]}>
              Type exactly: <Text style={{ color: colors.textPrimary, fontFamily: 'monospace', fontWeight: '700' }}>{REQUIRED_PHRASE}</Text>
            </Text>
            <TextInput
              value={typed}
              onChangeText={setTyped}
              autoCapitalize="characters"
              autoCorrect={false}
              style={[
                styles.input,
                {
                  color: colors.textPrimary,
                  borderColor: phraseMatches ? colors.buy : colors.border,
                  backgroundColor: colors.background,
                },
              ]}
              editable={!busy}
              testID="refund-typed-input"
            />

            <Text style={[styles.label, { color: colors.textMuted, marginTop: 16 }]}>
              REASON <Text style={{ color: colors.sell }}>*</Text>
            </Text>
            <TextInput
              value={reason}
              onChangeText={setReason}
              placeholder="Customer dispute · provider chargeback · billing correction…"
              placeholderTextColor={colors.textMuted}
              multiline
              style={[
                styles.input,
                {
                  color: colors.textPrimary,
                  borderColor: colors.border,
                  backgroundColor: colors.background,
                  minHeight: 70,
                },
              ]}
              editable={!busy}
              testID="refund-reason-input"
            />

            <View style={[styles.fxBox, { borderColor: colors.border }]}>
              <Text style={[styles.fxTitle, { color: colors.textMuted }]}>RESULTING AUDIT EVENTS</Text>
              <FxLine text="billing_audit · refund" color={colors.sell} />
              <FxLine text="billing_audit · downgrade (tier → free)" color={colors.sell} />
              <FxLine text="operator_access_audit · set-tier (actor=billing_system)" color={colors.textSecondary} />
            </View>

            {error && (
              <View style={[styles.err, { borderColor: colors.danger, backgroundColor: colors.badgeHighBg }]}>
                <Text style={[styles.errText, { color: colors.badgeHighText }]}>
                  {error === 'REASON_REQUIRED' ? 'Backend rejected: reason is required.'
                  : error === 'INVOICE_NOT_PAID' ? 'Only paid invoices may be refunded.'
                  : error === 'INVOICE_NOT_FOUND' ? 'Invoice no longer exists.'
                  : error}
                </Text>
              </View>
            )}
          </ScrollView>

          <View style={styles.foot}>
            <TouchableOpacity
              onPress={close}
              disabled={busy}
              style={[styles.btn, { borderColor: colors.border }]}
            >
              <Text style={[styles.btnText, { color: colors.textSecondary }]}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity
              onPress={submit}
              disabled={!canConfirm}
              style={[
                styles.btn, styles.btnConfirm,
                {
                  backgroundColor: canConfirm ? colors.sell : colors.surfaceHover,
                  borderColor: canConfirm ? colors.sell : colors.border,
                  opacity: canConfirm ? 1 : 0.5,
                },
              ]}
              testID="refund-submit"
            >
              {busy
                ? <ActivityIndicator color={colors.accentText} />
                : <Text style={[styles.btnText, { color: colors.accentText, fontWeight: '700' }]}>Issue refund</Text>}
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

function MetaRow({ k, v, mono, colors }: { k: string; v: string; mono?: boolean; colors: any }) {
  return (
    <View style={styles.metaRow}>
      <Text style={[styles.metaKey, { color: colors.textMuted }]}>{k}</Text>
      <Text style={[styles.metaVal, { color: colors.textPrimary, fontFamily: mono ? 'monospace' : undefined }]}
        numberOfLines={1}>{v}</Text>
    </View>
  );
}

function FxLine({ text, color }: { text: string; color: string }) {
  return (
    <View style={styles.fxLine}>
      <Ionicons name="arrow-forward" size={11} color={color} />
      <Text style={[styles.fxText, { color }]}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1, alignItems: 'center', justifyContent: 'center',
    padding: 24, backgroundColor: 'rgba(0,0,0,0.65)',
  },
  card: { width: '100%', maxWidth: 560, borderWidth: 2, borderRadius: 12, padding: 22, maxHeight: '92%' },
  head: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  title: { fontSize: 16, fontWeight: '800' },
  meta: { marginTop: 12, gap: 4 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  metaKey: { fontSize: 10, fontWeight: '700', letterSpacing: 1, width: 80 },
  metaVal: { fontSize: 12, flex: 1 },
  body: { marginTop: 14, maxHeight: 440 },
  warn: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, borderLeftWidth: 3, padding: 12, borderRadius: 4 },
  warnTitle: { fontSize: 12, fontWeight: '800', letterSpacing: 0.3, marginBottom: 4 },
  warnText: { fontSize: 12, lineHeight: 18 },
  label: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2, marginBottom: 4 },
  phraseHint: { fontSize: 12, marginBottom: 6 },
  input: { borderWidth: 1, borderRadius: 6, padding: 10, fontSize: 13 },
  fxBox: { borderWidth: 1, borderRadius: 6, padding: 10, marginTop: 16, gap: 6 },
  fxTitle: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2 },
  fxLine: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  fxText: { fontSize: 11, fontFamily: 'monospace' },
  err: { borderLeftWidth: 3, padding: 8, marginTop: 14, borderRadius: 4 },
  errText: { fontSize: 12 },
  foot: { flexDirection: 'row', justifyContent: 'flex-end', gap: 10, marginTop: 16 },
  btn: { paddingHorizontal: 16, paddingVertical: 10, borderRadius: 6, borderWidth: 1, minWidth: 110, alignItems: 'center' },
  btnConfirm: {},
  btnText: { fontSize: 13, fontWeight: '500' },
});
