/**
 * RestrictedEnvironmentScreen — Stage 0 capability landing.
 *
 *   What this screen IS:
 *     A semantic seal between the public intelligence surface and the
 *     restricted operational environment.  Renders inside Trading OS
 *     whenever the current user does NOT yet have `executionConsole`
 *     capability.
 *
 *   What this screen IS NOT:
 *     A paywall.  A subscription upsell.  A "VIP unlock" pitch.
 *
 *   Language rules (enforced):
 *     ALLOWED:  Operator Access · Restricted Environment ·
 *               Authorized Execution Layer · Capital Cognition
 *     FORBIDDEN: VIP · Elite · Premium · Alpha · Unlock · Upgrade ·
 *                Get rich · Profit · Win rate
 *
 *   Five states (rendered as one screen, language adapts):
 *     none           — first-time encounter, application not yet submitted
 *     invited        — explicit invitation, can accept terms
 *     pending_review — application submitted, awaiting authorization
 *     revoked        — access was revoked, contact admin
 *     approved-but-no-mode — edge case, treated as pending
 */
import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../../core/useColors';
import {
  useCapabilitiesStore,
  type OperatorAccess,
} from '../../../stores/capabilities.store';
import { softEntry, slowEmergence } from '../../../widgets/cognition/motion';
import Animated from 'react-native-reanimated';

// ─── Status → semantic copy ────────────────────────────────────────────
function copyForStatus(oa: OperatorAccess): {
  badge: string;
  badgeTone: 'neutral' | 'pending' | 'severe';
  title: string;
  body: string[];
  primaryCta: 'apply' | 'acknowledge-risk' | 'none';
  primaryCtaLabel: string;
} {
  if (oa.status === 'pending_review') {
    return {
      badge: 'OPERATOR REVIEW',
      badgeTone: 'pending',
      title: 'Operator access under review',
      body: [
        'Your application has been submitted.',
        'Operator access is granted manually after review.',
        'You will see the operational environment activate here once authorization completes.',
      ],
      primaryCta: 'none',
      primaryCtaLabel: '',
    };
  }
  if (oa.status === 'revoked') {
    return {
      badge: 'ACCESS REVOKED',
      badgeTone: 'severe',
      title: 'Operator access revoked',
      body: [
        'Your access to the restricted operational environment has been revoked.',
        'Contact the system operator for review.',
      ],
      primaryCta: 'none',
      primaryCtaLabel: '',
    };
  }
  if (oa.status === 'invited') {
    return {
      badge: 'INVITED',
      badgeTone: 'pending',
      title: 'You have been invited as an operator',
      body: [
        'This environment is restricted by design.',
        'Acknowledge the risk terms to activate paper operator mode.',
        'Live execution requires additional authorization.',
      ],
      primaryCta: 'acknowledge-risk',
      primaryCtaLabel: 'ACKNOWLEDGE RISK TERMS',
    };
  }
  if (oa.status === 'approved' && oa.mode === 'none') {
    return {
      badge: 'OPERATOR APPROVED',
      badgeTone: 'pending',
      title: 'Operator mode not assigned',
      body: [
        'Your operator access is approved but no operating mode has been assigned.',
        'The environment will activate once paper, shadow, or live mode is set.',
      ],
      primaryCta: 'none',
      primaryCtaLabel: '',
    };
  }
  // Default: status === 'none'  →  first encounter.
  return {
    badge: 'RESTRICTED ENVIRONMENT',
    badgeTone: 'neutral',
    title: 'Authorized execution layer',
    body: [
      'This is the restricted operational environment of the system.',
      'It contains the capital cognition layer — execution reasoning, suppression graph, parallel universes, attribution memory.',
      'Access is granted by review, not by subscription.',
      'No guaranteed outcome. Capital risk remains with the operator. The system provides advisory and execution-filtering infrastructure.',
    ],
    primaryCta: 'apply',
    primaryCtaLabel: 'APPLY FOR OPERATOR ACCESS',
  };
}

// ─── Component ─────────────────────────────────────────────────────────
export function RestrictedEnvironmentScreen() {
  const colors = useColors();
  const oa = useCapabilitiesStore((s) => s.operatorAccess);
  const loaded = useCapabilitiesStore((s) => s.loaded);
  const applyForOperator = useCapabilitiesStore((s) => s.applyForOperator);
  const acknowledgeRisk = useCapabilitiesStore((s) => s.acknowledgeRisk);

  const [busy, setBusy] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const copy = copyForStatus(oa);

  const handleApply = useCallback(async () => {
    if (!termsAccepted) {
      setLocalError('Please accept the operational risk terms first.');
      return;
    }
    setLocalError(null);
    setBusy(true);
    try {
      await applyForOperator(true, null);
    } catch (e: any) {
      setLocalError(e?.message || 'Application failed');
    } finally {
      setBusy(false);
    }
  }, [termsAccepted, applyForOperator]);

  const handleAcknowledge = useCallback(async () => {
    setLocalError(null);
    setBusy(true);
    try {
      await acknowledgeRisk();
    } catch (e: any) {
      setLocalError(e?.message || 'Acknowledgement failed');
    } finally {
      setBusy(false);
    }
  }, [acknowledgeRisk]);

  if (!loaded) {
    return (
      <View style={[styles.loadingWrap, { backgroundColor: colors.background }]}>
        <ActivityIndicator size="small" color={colors.textMuted} />
        <Text style={[styles.loadingLabel, { color: colors.textMuted }]}>
          resolving environment capability
        </Text>
      </View>
    );
  }

  const badgeColor =
    copy.badgeTone === 'severe' ? colors.sell
    : copy.badgeTone === 'pending' ? colors.accent
    : colors.textMuted;

  return (
    <ScrollView
      testID="restricted-environment-screen"
      style={[styles.root, { backgroundColor: colors.background }]}
      contentContainerStyle={styles.content}
    >
      {/* Seal / badge */}
      <Animated.View entering={softEntry()} style={styles.sealRow}>
        <View style={[styles.seal, { borderColor: badgeColor + '60' }]}>
          <Ionicons name="lock-closed" size={14} color={badgeColor} />
          <Text style={[styles.sealLabel, { color: badgeColor }]}>
            {copy.badge}
          </Text>
        </View>
      </Animated.View>

      {/* Title */}
      <Animated.Text
        entering={slowEmergence(200)}
        style={[styles.title, { color: colors.textPrimary }]}
      >
        {copy.title}
      </Animated.Text>

      {/* Body — paragraphs */}
      <View style={styles.bodyWrap}>
        {copy.body.map((line, i) => (
          <Animated.Text
            key={i}
            entering={slowEmergence(400 + i * 220)}
            style={[styles.bodyLine, { color: colors.textSecondary || colors.textMuted }]}
          >
            {line}
          </Animated.Text>
        ))}
      </View>

      {/* Public surface reminder */}
      <Animated.View entering={slowEmergence(1400)} style={[styles.publicReminder, { borderColor: colors.border }]}>
        <Text style={[styles.publicReminderLabel, { color: colors.textMuted }]}>
          PUBLIC INTELLIGENCE REMAINS ACCESSIBLE
        </Text>
        <Text style={[styles.publicReminderBody, { color: colors.textSecondary || colors.textMuted }]}>
          Home · Feed · Signals · Edge continue to operate without restriction.
          {'\n'}
          Only the operational layer below is sealed.
        </Text>
      </Animated.View>

      {/* Application surface (only when applicable) */}
      {copy.primaryCta === 'apply' && (
        <Animated.View entering={slowEmergence(1700)} style={styles.applyWrap}>
          <TouchableOpacity
            testID="restricted-accept-terms"
            onPress={() => setTermsAccepted(!termsAccepted)}
            style={[styles.termsRow, { borderColor: colors.border }]}
            activeOpacity={0.7}
          >
            <View style={[
              styles.checkbox,
              { borderColor: termsAccepted ? colors.accent : colors.border },
              termsAccepted && { backgroundColor: colors.accent + '20' },
            ]}>
              {termsAccepted && <Ionicons name="checkmark" size={14} color={colors.accent} />}
            </View>
            <Text style={[styles.termsLabel, { color: colors.textSecondary || colors.textMuted }]}>
              I acknowledge this is advisory infrastructure with no guaranteed outcome,
              capital risk remains with me, and operator access is granted at the
              system operator's discretion.
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            testID="restricted-apply-cta"
            onPress={handleApply}
            disabled={busy || !termsAccepted}
            activeOpacity={0.8}
            style={[
              styles.primaryCta,
              { borderColor: colors.accent },
              (!termsAccepted || busy) && { opacity: 0.4 },
            ]}
          >
            {busy ? (
              <ActivityIndicator size="small" color={colors.accent} />
            ) : (
              <>
                <Text style={[styles.primaryCtaLabel, { color: colors.accent }]}>
                  {copy.primaryCtaLabel}
                </Text>
                <Ionicons name="arrow-forward" size={14} color={colors.accent} />
              </>
            )}
          </TouchableOpacity>
        </Animated.View>
      )}

      {/* Acknowledge-risk CTA (invited state) */}
      {copy.primaryCta === 'acknowledge-risk' && (
        <Animated.View entering={slowEmergence(1500)} style={styles.applyWrap}>
          <TouchableOpacity
            testID="restricted-ack-cta"
            onPress={handleAcknowledge}
            disabled={busy}
            activeOpacity={0.8}
            style={[styles.primaryCta, { borderColor: colors.accent }, busy && { opacity: 0.4 }]}
          >
            {busy ? (
              <ActivityIndicator size="small" color={colors.accent} />
            ) : (
              <>
                <Text style={[styles.primaryCtaLabel, { color: colors.accent }]}>
                  {copy.primaryCtaLabel}
                </Text>
                <Ionicons name="arrow-forward" size={14} color={colors.accent} />
              </>
            )}
          </TouchableOpacity>
        </Animated.View>
      )}

      {/* Local error */}
      {localError ? (
        <Text style={[styles.errorLine, { color: colors.sell }]}>
          {localError}
        </Text>
      ) : null}

      {/* Quiet legal footer */}
      <View style={styles.footer}>
        <Text style={[styles.footerLine, { color: colors.textMuted }]}>
          The system provides probabilistic market interpretation and execution
          filtering. All outputs are advisory and experimental.
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  content: { paddingHorizontal: 20, paddingTop: 32, paddingBottom: 80 },
  loadingWrap: {
    flex: 1, alignItems: 'center', justifyContent: 'center', gap: 10,
  },
  loadingLabel: { fontSize: 11, letterSpacing: 1, textTransform: 'uppercase' },
  sealRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 24 },
  seal: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 10, paddingVertical: 6,
    borderRadius: 999, borderWidth: 1,
  },
  sealLabel: { fontSize: 10, fontWeight: '800', letterSpacing: 1.2 },
  title: {
    fontSize: 26, fontWeight: '800', lineHeight: 32,
    marginBottom: 24,
  },
  bodyWrap: { gap: 14, marginBottom: 32 },
  bodyLine: { fontSize: 14, lineHeight: 21 },
  publicReminder: {
    borderWidth: 1, borderRadius: 12,
    paddingHorizontal: 14, paddingVertical: 12,
    marginBottom: 28,
  },
  publicReminderLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 1, marginBottom: 6 },
  publicReminderBody: { fontSize: 12, lineHeight: 18 },
  applyWrap: { gap: 14, marginBottom: 16 },
  termsRow: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 10,
    borderWidth: 1, borderRadius: 10,
    padding: 12,
  },
  checkbox: {
    width: 20, height: 20, borderRadius: 4, borderWidth: 1,
    alignItems: 'center', justifyContent: 'center',
  },
  termsLabel: { flex: 1, minWidth: 0, fontSize: 12, lineHeight: 18 },
  primaryCta: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    paddingVertical: 14, borderRadius: 12, borderWidth: 1,
  },
  primaryCtaLabel: { fontSize: 12, fontWeight: '800', letterSpacing: 1 },
  errorLine: { fontSize: 12, marginTop: 8, textAlign: 'center' },
  footer: { marginTop: 32 },
  footerLine: { fontSize: 10, lineHeight: 15, textAlign: 'left' },
});
