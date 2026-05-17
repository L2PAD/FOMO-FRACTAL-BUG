/**
 * QuarantineBanner — Soft quarantine notice for the orphan Expo admin
 * surface at /admin/*.
 *
 * Quarantine contract (T10.2F):
 *   1. Display a deprecation banner on every /admin/* route, web only.
 *   2. Provide ONE explicit CTA to the canonical /api/panel/admin.
 *      No force redirect, no auto-navigation, no timed redirect.
 *   3. Apply noindex/nofollow so this orphan surface drops from search
 *      and link-graph discovery, without affecting accessibility.
 *   4. Visual downgrade (subdued palette, compatibility-mode framing)
 *      — but do NOT break functionality of the orphan tree underneath.
 *
 * Backend is untouched.  This is a pure UI quarantine layer.
 */
import React, { useEffect } from 'react';
import { Platform, Pressable, StyleSheet, Text, View } from 'react-native';

const CANONICAL_ADMIN_URL = '/api/panel/admin';

/**
 * Install <meta name="robots" content="noindex,nofollow"> for the
 * lifetime this banner is mounted.  Restore previous value on unmount
 * so leaving /admin/* doesn't poison the rest of the app.
 */
function useNoindexMeta() {
  useEffect(() => {
    if (Platform.OS !== 'web') return;
    if (typeof document === 'undefined') return;
    const name = 'robots';
    let el = document.querySelector(`meta[name="${name}"]`) as HTMLMetaElement | null;
    const previous = el ? el.getAttribute('content') : null;
    if (!el) {
      el = document.createElement('meta');
      el.setAttribute('name', name);
      document.head.appendChild(el);
    }
    el.setAttribute('content', 'noindex,nofollow');
    return () => {
      if (!el) return;
      if (previous === null) {
        el.parentElement?.removeChild(el);
      } else {
        el.setAttribute('content', previous);
      }
    };
  }, []);
}

function openCanonical() {
  if (Platform.OS !== 'web') return;
  if (typeof window === 'undefined') return;
  // Same-tab navigation — explicit CTA, NOT a redirect.  Users land on
  // the canonical FOMO Admin Console at /api/panel/admin (served by
  // backend, separate auth surface — that is the contract).
  window.location.assign(CANONICAL_ADMIN_URL);
}

export function QuarantineBanner() {
  useNoindexMeta();

  // Banner is web-only.  On native the parent layout already renders
  // NativeBlock instead of children, so this component never instantiates
  // there — but we keep an explicit guard for safety.
  if (Platform.OS !== 'web') return null;

  return (
    <View
      testID="orphan-admin-quarantine-banner"
      accessibilityRole="alert"
      style={styles.banner}
    >
      <View style={styles.content}>
        <View style={styles.textCol}>
          <Text style={styles.label}>Compatibility mode</Text>
          <Text style={styles.title}>
            Эта административная поверхность переведена в режим совместимости.
          </Text>
          <Text style={styles.body}>
            Каноническая FOMO Admin Console теперь доступна через{' '}
            <Text style={styles.code}>/api/panel/admin</Text>. Этот orphan
            surface остаётся operational как fallback, но не считается
            каноническим в reintegration-контракте.
          </Text>
        </View>
        <Pressable
          testID="orphan-admin-quarantine-cta"
          onPress={openCanonical}
          accessibilityRole="link"
          style={({ pressed }) => [styles.cta, pressed && styles.ctaPressed]}
        >
          <Text style={styles.ctaText}>Открыть FOMO Admin Console</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  // Subdued palette — slate/gray, NOT brand blue.  This is intentional
  // visual downgrade so the orphan surface stops feeling primary.
  banner: {
    width: '100%',
    backgroundColor: '#f1f5f9',
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0',
    paddingHorizontal: 20,
    paddingVertical: 12,
  },
  content: {
    width: '100%',
    maxWidth: 1280,
    marginHorizontal: 'auto' as any,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 16,
    flexWrap: 'wrap',
  },
  textCol: {
    flex: 1,
    minWidth: 280,
  },
  label: {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    color: '#64748b',
    marginBottom: 4,
  },
  title: {
    fontSize: 13,
    fontWeight: '700',
    color: '#1e293b',
    lineHeight: 18,
  },
  body: {
    fontSize: 12,
    color: '#475569',
    lineHeight: 17,
    marginTop: 3,
  },
  code: {
    fontFamily: Platform.select({ web: 'JetBrains Mono, ui-monospace, monospace' as any, default: 'Courier' }),
    fontSize: 11.5,
    color: '#0f172a',
    backgroundColor: '#e2e8f0',
    paddingHorizontal: 5,
    paddingVertical: 1,
    borderRadius: 4,
  },
  cta: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: '#cbd5e1',
    borderRadius: 8,
  },
  ctaPressed: {
    backgroundColor: '#f8fafc',
    borderColor: '#94a3b8',
  },
  ctaText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#334155',
  },
});

export default QuarantineBanner;
