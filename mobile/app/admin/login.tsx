/**
 * /admin/login — admin secret entry.
 *
 * The secret is validated against /api/admin/operator-access/list with a
 * cheap limit=1 probe.  On 200 it is stored in localStorage (web-only
 * deployment), and the inactivity timer starts.  On 401/403 we surface
 * the error without persisting anything.
 */
import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, KeyboardAvoidingView, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAdminAuth } from '../../src/admin/auth/AdminAuthContext';
import { useColors } from '../../src/core/useColors';

export default function AdminLoginScreen() {
  const colors = useColors();
  const { login } = useAdminAuth();
  const [secret, setSecret] = useState('');
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    setBusy(true);
    const res = await login(secret);
    setBusy(false);
    if (!res.ok) setError(res.error || 'Login failed');
    // navigation handled by AuthGuard
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      style={[styles.root, { backgroundColor: colors.background }]}
    >
      <View style={styles.center}>
        <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <View style={styles.brand}>
            <Ionicons name="shield-checkmark-outline" size={28} color={colors.accent} />
            <Text style={[styles.brandTitle, { color: colors.textPrimary }]}>
              FOMO · Operations
            </Text>
          </View>
          <Text style={[styles.subtitle, { color: colors.textSecondary }]}>
            Restricted governance console. Operator access only — capability
            overrides, live-authority grants and audit review.
          </Text>

          <Text style={[styles.label, { color: colors.textMuted }]}>ADMIN SECRET</Text>
          <View style={[styles.inputRow, { borderColor: colors.border, backgroundColor: colors.background }]}>
            <TextInput
              value={secret}
              onChangeText={setSecret}
              placeholder="paste admin secret"
              placeholderTextColor={colors.textMuted}
              secureTextEntry={!show}
              autoCapitalize="none"
              autoCorrect={false}
              style={[styles.input, { color: colors.textPrimary }]}
              onSubmitEditing={submit}
              testID="admin-secret-input"
            />
            <TouchableOpacity onPress={() => setShow(v => !v)} hitSlop={{top:10,bottom:10,left:10,right:10}}>
              <Ionicons
                name={show ? 'eye-off-outline' : 'eye-outline'}
                size={18}
                color={colors.textMuted}
              />
            </TouchableOpacity>
          </View>

          {error && (
            <View style={[styles.errBox, { borderColor: colors.danger, backgroundColor: colors.badgeHighBg }]}>
              <Text style={[styles.errText, { color: colors.badgeHighText }]}>{error}</Text>
            </View>
          )}

          <TouchableOpacity
            onPress={submit}
            disabled={busy || !secret.trim()}
            style={[
              styles.btn,
              {
                backgroundColor: busy || !secret.trim() ? colors.surfaceHover : colors.accent,
                opacity: busy || !secret.trim() ? 0.6 : 1,
              },
            ]}
            testID="admin-login-submit"
          >
            {busy ? (
              <ActivityIndicator color={colors.accentText} />
            ) : (
              <Text style={[styles.btnText, { color: colors.accentText }]}>
                Unlock console
              </Text>
            )}
          </TouchableOpacity>

          <Text style={[styles.fineprint, { color: colors.textMuted }]}>
            Session expires after 8 hours of inactivity. The secret never
            leaves this device and is not sent to the customer-app surface.
          </Text>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  card: {
    width: '100%', maxWidth: 480,
    borderWidth: 1, borderRadius: 14, padding: 28, gap: 12,
  },
  brand: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  brandTitle: { fontSize: 18, fontWeight: '800', letterSpacing: 0.2 },
  subtitle: { fontSize: 13, lineHeight: 19, marginTop: 4, marginBottom: 8 },
  label: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2, marginTop: 8 },
  inputRow: {
    flexDirection: 'row', alignItems: 'center',
    borderWidth: 1, borderRadius: 8, paddingHorizontal: 12,
  },
  input: { flex: 1, paddingVertical: 12, fontSize: 14 },
  errBox: { borderLeftWidth: 3, paddingHorizontal: 10, paddingVertical: 8, borderRadius: 4 },
  errText: { fontSize: 12, fontWeight: '500' },
  btn: { paddingVertical: 14, borderRadius: 8, alignItems: 'center', marginTop: 6 },
  btnText: { fontSize: 14, fontWeight: '700', letterSpacing: 0.4 },
  fineprint: { fontSize: 11, lineHeight: 16, marginTop: 8, textAlign: 'center' },
});
