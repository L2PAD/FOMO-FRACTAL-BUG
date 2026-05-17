/**
 * TypedConfirmationModal — highest-friction governance action.
 *
 * Reserved for liveTrading authority grants.  Three independent gates
 * before the confirm button enables:
 *
 *   1. Exact typed confirmation matching `phrase` (case-sensitive,
 *      whitespace-trimmed).  Backend also validates this.
 *   2. Mandatory non-empty `reason`.
 *   3. Mandatory acknowledgement checkbox ("I understand…").
 *
 * Optional expiresAt input (ISO datetime).  Backend treats it as a
 * schema-ready field; expiry enforcement already lives in the resolver.
 */
import React, { useState } from 'react';
import {
  Modal, View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, ScrollView, Pressable,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../../core/useColors';

export interface TypedConfirmationModalProps {
  visible: boolean;
  phrase: string;             // exact phrase user must type, e.g. "GRANT LIVE TRADING"
  targetUserId: string;
  warningBody: React.ReactNode;
  ackText: string;            // checkbox text
  onCancel: () => void;
  onConfirm: (args: { typed: string; reason: string; expiresAt: string | null }) => Promise<void>;
}

export function TypedConfirmationModal(props: TypedConfirmationModalProps) {
  const colors = useColors();
  const [typed, setTyped] = useState('');
  const [reason, setReason] = useState('');
  const [expiry, setExpiry] = useState('');
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const phraseMatches = typed === props.phrase;
  const reasonOk = reason.trim().length > 0;
  const canConfirm = !busy && phraseMatches && reasonOk && ack;

  const close = () => {
    if (busy) return;
    setTyped(''); setReason(''); setExpiry(''); setAck(false); setError(null);
    props.onCancel();
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await props.onConfirm({
        typed,
        reason: reason.trim(),
        expiresAt: expiry.trim() ? expiry.trim() : null,
      });
      setTyped(''); setReason(''); setExpiry(''); setAck(false);
      props.onCancel();
    } catch (e: any) {
      const code = e?.response?.data?.detail?.error;
      setError(code || e?.message || 'Action failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal visible={props.visible} transparent animationType="fade" onRequestClose={close}>
      <View style={[styles.backdrop, { backgroundColor: 'rgba(0,0,0,0.65)' }]}>
        <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.sell }]}>
          <View style={styles.head}>
            <Ionicons name="warning" size={22} color={colors.sell} />
            <Text style={[styles.title, { color: colors.textPrimary }]}>
              Grant live capital authority
            </Text>
          </View>
          <Text style={[styles.target, { color: colors.textMuted }]}>
            Target operator: <Text style={{ color: colors.textPrimary, fontWeight: '700' }}>{props.targetUserId}</Text>
          </Text>

          <ScrollView style={styles.body}>
            <View style={[styles.warning, { borderColor: colors.sell, backgroundColor: colors.badgeHighBg }]}>
              <Text style={[styles.warningText, { color: colors.badgeHighText }]}>
                {props.warningBody}
              </Text>
            </View>

            <Text style={[styles.label, { color: colors.textMuted, marginTop: 16 }]}>
              TYPE TO CONFIRM <Text style={{ color: colors.sell }}>*</Text>
            </Text>
            <Text style={[styles.phraseHint, { color: colors.textSecondary }]}>
              Type exactly: <Text style={{ color: colors.textPrimary, fontFamily: 'monospace', fontWeight: '700' }}>{props.phrase}</Text>
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
              testID="typed-confirmation-input"
            />

            <Text style={[styles.label, { color: colors.textMuted, marginTop: 16 }]}>
              REASON <Text style={{ color: colors.sell }}>*</Text>
            </Text>
            <TextInput
              value={reason}
              onChangeText={setReason}
              placeholder="Mandatory governance justification…"
              placeholderTextColor={colors.textMuted}
              multiline
              style={[
                styles.input,
                { color: colors.textPrimary, borderColor: colors.border, backgroundColor: colors.background, minHeight: 70 },
              ]}
              editable={!busy}
              testID="typed-confirmation-reason"
            />

            <Text style={[styles.label, { color: colors.textMuted, marginTop: 16 }]}>
              EXPIRES AT (optional, ISO 8601)
            </Text>
            <TextInput
              value={expiry}
              onChangeText={setExpiry}
              placeholder="e.g. 2026-12-31T23:59:59+00:00"
              placeholderTextColor={colors.textMuted}
              style={[
                styles.input,
                { color: colors.textPrimary, borderColor: colors.border, backgroundColor: colors.background },
              ]}
              editable={!busy}
              autoCapitalize="none"
            />

            <Pressable
              onPress={() => setAck(v => !v)}
              disabled={busy}
              style={styles.ackRow}
            >
              <View style={[
                styles.checkbox,
                { borderColor: ack ? colors.sell : colors.border, backgroundColor: ack ? colors.sell : 'transparent' },
              ]}>
                {ack && <Ionicons name="checkmark" size={14} color={colors.accentText} />}
              </View>
              <Text style={[styles.ackText, { color: colors.textPrimary }]}>{props.ackText}</Text>
            </Pressable>

            {error && (
              <View style={[styles.err, { borderColor: colors.danger, backgroundColor: colors.badgeHighBg }]}>
                <Text style={[styles.errText, { color: colors.badgeHighText }]}>
                  {error === 'TYPED_CONFIRMATION_MISMATCH' ? 'Backend rejected: typed confirmation does not match.'
                  : error === 'REASON_REQUIRED' ? 'Backend rejected: reason is required.'
                  : error === 'NOT_APPROVED' ? 'Operator must be approved before granting live authority.'
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
              testID="typed-confirmation-submit"
            >
              {busy ? (
                <ActivityIndicator color={colors.accentText} />
              ) : (
                <Text style={[styles.btnText, { color: colors.accentText, fontWeight: '700' }]}>
                  Grant live authority
                </Text>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  card: { width: '100%', maxWidth: 560, borderWidth: 2, borderRadius: 12, padding: 22, maxHeight: '92%' },
  head: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  title: { fontSize: 16, fontWeight: '800' },
  target: { fontSize: 12, marginTop: 6 },
  body: { marginTop: 12, maxHeight: 460 },
  warning: { borderLeftWidth: 3, padding: 12, borderRadius: 4 },
  warningText: { fontSize: 12, lineHeight: 18 },
  label: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2, marginBottom: 4 },
  phraseHint: { fontSize: 12, marginBottom: 6 },
  input: {
    borderWidth: 1, borderRadius: 6, padding: 10,
    fontSize: 13,
  },
  ackRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 16 },
  checkbox: {
    width: 18, height: 18, borderRadius: 4, borderWidth: 1.5,
    alignItems: 'center', justifyContent: 'center',
  },
  ackText: { fontSize: 12, flex: 1 },
  err: { borderLeftWidth: 3, padding: 8, marginTop: 14, borderRadius: 4 },
  errText: { fontSize: 12 },
  foot: { flexDirection: 'row', justifyContent: 'flex-end', gap: 10, marginTop: 16 },
  btn: { paddingHorizontal: 16, paddingVertical: 10, borderRadius: 6, borderWidth: 1, minWidth: 110, alignItems: 'center' },
  btnConfirm: {},
  btnText: { fontSize: 13, fontWeight: '500' },
});
