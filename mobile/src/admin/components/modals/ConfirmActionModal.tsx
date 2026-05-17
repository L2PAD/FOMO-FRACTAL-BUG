/**
 * ConfirmActionModal — medium-friction governance action.
 *
 * Used for:
 *   * capability override (grant/revoke/clear)
 *   * mode change
 *   * console access toggle
 *   * blanket revoke
 *
 * Contract:
 *   * `reason` field is always shown; required iff `requireReason`
 *   * confirm is disabled until reason satisfies the requirement
 *   * onConfirm receives the trimmed reason; caller awaits mutation
 *     then triggers an authoritative refetch (no optimistic UI)
 *   * non-cancellable while busy
 */
import React, { useState } from 'react';
import {
  Modal, View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../../core/useColors';

export interface ConfirmActionModalProps {
  visible: boolean;
  title: string;
  body: React.ReactNode;
  confirmLabel?: string;
  severity?: 'info' | 'elevated' | 'critical';
  requireReason?: boolean;
  reasonPlaceholder?: string;
  onCancel: () => void;
  onConfirm: (reason: string) => Promise<void>;
}

export function ConfirmActionModal(props: ConfirmActionModalProps) {
  const colors = useColors();
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sevColor =
    props.severity === 'critical' ? colors.sell
    : props.severity === 'elevated' ? colors.accent
    : colors.textSecondary;

  const canConfirm = !busy && (!props.requireReason || reason.trim().length > 0);

  const close = () => {
    if (busy) return;
    setReason('');
    setError(null);
    props.onCancel();
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await props.onConfirm(reason.trim());
      setReason('');
      props.onCancel();
    } catch (e: any) {
      setError(e?.response?.data?.detail?.error || e?.message || 'Action failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal visible={props.visible} transparent animationType="fade" onRequestClose={close}>
      <View style={[styles.backdrop, { backgroundColor: 'rgba(0,0,0,0.55)' }]}>
        <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <View style={styles.head}>
            <View style={[styles.sevDot, { backgroundColor: sevColor }]} />
            <Text style={[styles.title, { color: colors.textPrimary }]}>{props.title}</Text>
          </View>

          <ScrollView style={styles.body}>
            <View>{props.body}</View>
            <Text style={[styles.label, { color: colors.textMuted, marginTop: 16 }]}>
              REASON {props.requireReason ? <Text style={{ color: colors.sell }}>*</Text> : null}
            </Text>
            <TextInput
              value={reason}
              onChangeText={setReason}
              placeholder={props.reasonPlaceholder || 'Operational justification…'}
              placeholderTextColor={colors.textMuted}
              multiline
              style={[
                styles.input,
                { color: colors.textPrimary, borderColor: colors.border, backgroundColor: colors.background },
              ]}
              editable={!busy}
            />
            {error && (
              <View style={[styles.err, { borderColor: colors.danger, backgroundColor: colors.badgeHighBg }]}>
                <Text style={[styles.errText, { color: colors.badgeHighText }]}>{error}</Text>
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
                  backgroundColor: canConfirm ? sevColor : colors.surfaceHover,
                  borderColor: canConfirm ? sevColor : colors.border,
                  opacity: canConfirm ? 1 : 0.5,
                },
              ]}
            >
              {busy ? (
                <ActivityIndicator color={colors.accentText} />
              ) : (
                <Text style={[styles.btnText, { color: colors.accentText, fontWeight: '700' }]}>
                  {props.confirmLabel || 'Confirm'}
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
  card: {
    width: '100%', maxWidth: 520,
    borderWidth: 1, borderRadius: 12, padding: 22,
    maxHeight: '90%',
  },
  head: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 12 },
  sevDot: { width: 10, height: 10, borderRadius: 5 },
  title: { fontSize: 16, fontWeight: '700' },
  body: { maxHeight: 380 },
  label: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2, marginBottom: 6 },
  input: {
    borderWidth: 1, borderRadius: 6, padding: 10, minHeight: 70,
    fontSize: 13, textAlignVertical: 'top',
  },
  err: { borderLeftWidth: 3, padding: 8, marginTop: 10, borderRadius: 4 },
  errText: { fontSize: 12 },
  foot: { flexDirection: 'row', justifyContent: 'flex-end', gap: 10, marginTop: 16 },
  btn: { paddingHorizontal: 16, paddingVertical: 10, borderRadius: 6, borderWidth: 1, minWidth: 100, alignItems: 'center' },
  btnConfirm: {},
  btnText: { fontSize: 13, fontWeight: '500' },
});
