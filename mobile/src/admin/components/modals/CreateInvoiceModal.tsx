/**
 * CreateInvoiceModal — TIER-4B.1
 *
 * Issues a commercial invoice intent.  Strictly constrained:
 *   * userId
 *   * productCode (PRO | TRADER)
 *   * optional price override
 *
 * Wording invariant: NEVER use "grant" or "trader access" — this is a
 * commercial product issuance.  Operational authority is governed in
 * /admin/operators only.
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  Modal, View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, ScrollView, Pressable,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../../core/useColors';

interface Product {
  code: 'PRO' | 'TRADER';
  title: string;
  subtitle: string;
  tier: string;
  priceUsd: number;
  grants: string[];
  doesNotGrant: string[];
}

export interface CreateInvoiceModalProps {
  visible: boolean;
  products: Product[];
  prefillUserId?: string;
  onCancel: () => void;
  onConfirm: (args: {
    userId: string;
    productCode: 'PRO' | 'TRADER';
    priceUsdOverride: number | null;
  }) => Promise<void>;
}

export function CreateInvoiceModal(props: CreateInvoiceModalProps) {
  const colors = useColors();
  const [userId, setUserId] = useState('');
  const [productCode, setProductCode] = useState<'PRO' | 'TRADER'>('PRO');
  const [override, setOverride] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (props.visible) {
      setUserId(props.prefillUserId || '');
      setProductCode('PRO');
      setOverride('');
      setError(null);
    }
  }, [props.visible, props.prefillUserId]);

  const selected = useMemo(
    () => props.products.find(p => p.code === productCode),
    [props.products, productCode],
  );

  const overrideNum = override.trim() === '' ? null : Number(override);
  const overrideValid = override.trim() === '' || (isFinite(overrideNum as number) && (overrideNum as number) >= 0);
  const userIdOk = userId.trim().length > 0;
  const canConfirm = !busy && userIdOk && overrideValid;

  const close = () => {
    if (busy) return;
    props.onCancel();
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await props.onConfirm({
        userId: userId.trim().toLowerCase(),
        productCode,
        priceUsdOverride: overrideNum,
      });
      props.onCancel();
    } catch (e: any) {
      const code = e?.response?.data?.detail?.error;
      setError(code || e?.message || 'Invoice creation failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal visible={props.visible} transparent animationType="fade" onRequestClose={close}>
      <View style={styles.backdrop}>
        <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <View style={styles.head}>
            <Ionicons name="document-text-outline" size={20} color={colors.accent} />
            <Text style={[styles.title, { color: colors.textPrimary }]}>Issue commercial invoice</Text>
          </View>
          <Text style={[styles.sub, { color: colors.textMuted }]}>
            Creates a pending invoice intent. Entitlement activates on confirm.
            Operational authority is governed separately under <Text style={{ color: colors.textSecondary, fontWeight: '700' }}>/admin/operators</Text>.
          </Text>

          <ScrollView style={styles.body}>
            <Text style={[styles.label, { color: colors.textMuted, marginTop: 14 }]}>
              CUSTOMER USER ID <Text style={{ color: colors.sell }}>*</Text>
            </Text>
            <TextInput
              value={userId}
              onChangeText={setUserId}
              placeholder="e.g. ops_alice"
              placeholderTextColor={colors.textMuted}
              autoCapitalize="none"
              autoCorrect={false}
              style={[
                styles.input,
                { color: colors.textPrimary, borderColor: colors.border, backgroundColor: colors.background },
              ]}
              editable={!busy}
              testID="create-invoice-userid"
            />

            <Text style={[styles.label, { color: colors.textMuted, marginTop: 16 }]}>
              COMMERCIAL PRODUCT <Text style={{ color: colors.sell }}>*</Text>
            </Text>
            <View style={styles.productGrid}>
              {props.products.map(p => {
                const active = p.code === productCode;
                return (
                  <Pressable
                    key={p.code}
                    onPress={() => !busy && setProductCode(p.code)}
                    style={({ hovered }: any) => [
                      styles.productCard,
                      {
                        borderColor: active ? colors.accent : colors.border,
                        backgroundColor: active ? colors.surfaceHover : colors.background,
                      },
                      hovered && !active && { borderColor: colors.textSecondary },
                    ]}
                  >
                    <View style={styles.productHead}>
                      <Text style={[styles.productCode, { color: colors.textPrimary }]}>{p.code}</Text>
                      <Text style={[styles.productPrice, { color: colors.textSecondary }]}>
                        ${p.priceUsd.toFixed(2)}
                      </Text>
                    </View>
                    <Text style={[styles.productTitle, { color: colors.textSecondary }]}>{p.subtitle}</Text>
                    <Text style={[styles.productTier, { color: colors.textMuted }]}>activates tier: {p.tier}</Text>
                  </Pressable>
                );
              })}
            </View>

            <Text style={[styles.label, { color: colors.textMuted, marginTop: 16 }]}>
              PRICE OVERRIDE (optional, USD)
            </Text>
            <TextInput
              value={override}
              onChangeText={setOverride}
              placeholder={selected ? `default ${selected.priceUsd.toFixed(2)}` : ''}
              placeholderTextColor={colors.textMuted}
              keyboardType="decimal-pad"
              style={[
                styles.input,
                {
                  color: colors.textPrimary,
                  borderColor: overrideValid ? colors.border : colors.danger,
                  backgroundColor: colors.background,
                },
              ]}
              editable={!busy}
              testID="create-invoice-override"
            />

            {selected && (
              <View style={[styles.snapshotBox, { borderColor: colors.border }]}>
                <Text style={[styles.snapshotTitle, { color: colors.textMuted }]}>
                  FROZEN PRODUCT SNAPSHOT AT ISSUANCE
                </Text>
                <View style={styles.grantRow}>
                  <Text style={[styles.grantLabel, { color: colors.buy }]}>GRANTS</Text>
                  <View style={styles.grantPills}>
                    {selected.grants.map(g => (
                      <View key={g} style={[styles.gp, { backgroundColor: colors.badgeLowBg || colors.surfaceHover }]}>
                        <Text style={[styles.gpText, { color: colors.badgeLowText || colors.buy }]}>{g}</Text>
                      </View>
                    ))}
                  </View>
                </View>
                <View style={styles.grantRow}>
                  <Text style={[styles.grantLabel, { color: colors.textMuted }]}>DOES NOT GRANT</Text>
                  <View style={styles.grantPills}>
                    {selected.doesNotGrant.map(g => (
                      <View key={g} style={[styles.gp, { backgroundColor: colors.surfaceHover, borderColor: colors.border, borderWidth: 1 }]}>
                        <Text style={[styles.gpTextMuted, { color: colors.textMuted, textDecorationLine: 'line-through' }]}>{g}</Text>
                      </View>
                    ))}
                  </View>
                </View>
              </View>
            )}

            {error && (
              <View style={[styles.err, { borderColor: colors.danger, backgroundColor: colors.badgeHighBg }]}>
                <Text style={[styles.errText, { color: colors.badgeHighText }]}>
                  {error === 'UNKNOWN_PRODUCT_CODE' ? 'Unknown product code.'
                  : error === 'TARGET_MISMATCH' ? 'Backend rejected: target mismatch.'
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
                styles.btn,
                {
                  backgroundColor: canConfirm ? colors.accent : colors.surfaceHover,
                  borderColor: canConfirm ? colors.accent : colors.border,
                  opacity: canConfirm ? 1 : 0.5,
                },
              ]}
              testID="create-invoice-submit"
            >
              {busy
                ? <ActivityIndicator color={colors.accentText} />
                : <Text style={[styles.btnText, { color: colors.accentText, fontWeight: '700' }]}>Create invoice</Text>}
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1, alignItems: 'center', justifyContent: 'center',
    padding: 24, backgroundColor: 'rgba(0,0,0,0.65)',
  },
  card: { width: '100%', maxWidth: 580, borderWidth: 1, borderRadius: 12, padding: 22, maxHeight: '92%' },
  head: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  title: { fontSize: 16, fontWeight: '800' },
  sub: { fontSize: 12, marginTop: 6, lineHeight: 18 },
  body: { marginTop: 10, maxHeight: 460 },
  label: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2, marginBottom: 6 },
  input: { borderWidth: 1, borderRadius: 6, padding: 10, fontSize: 13 },
  productGrid: { flexDirection: 'row', gap: 10 },
  productCard: { flex: 1, borderWidth: 1, borderRadius: 8, padding: 12, gap: 4 },
  productHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  productCode: { fontSize: 14, fontWeight: '800', letterSpacing: 0.4 },
  productPrice: { fontSize: 12, fontWeight: '700', fontFamily: 'monospace' },
  productTitle: { fontSize: 11, lineHeight: 15 },
  productTier: { fontSize: 10, marginTop: 2, letterSpacing: 0.2 },
  snapshotBox: { borderWidth: 1, borderRadius: 6, padding: 10, marginTop: 16, gap: 8 },
  snapshotTitle: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2 },
  grantRow: { gap: 4 },
  grantLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 1 },
  grantPills: { flexDirection: 'row', flexWrap: 'wrap', gap: 4 },
  gp: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4 },
  gpText: { fontSize: 10, fontWeight: '700' },
  gpTextMuted: { fontSize: 10, fontWeight: '500' },
  err: { borderLeftWidth: 3, padding: 8, marginTop: 14, borderRadius: 4 },
  errText: { fontSize: 12 },
  foot: { flexDirection: 'row', justifyContent: 'flex-end', gap: 10, marginTop: 16 },
  btn: { paddingHorizontal: 16, paddingVertical: 10, borderRadius: 6, borderWidth: 1, minWidth: 110, alignItems: 'center' },
  btnText: { fontSize: 13, fontWeight: '500' },
});
