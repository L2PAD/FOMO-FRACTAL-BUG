import React, { useState, useMemo, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Image,
  Platform,
  TextInput,
  KeyboardAvoidingView,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as WebBrowser from 'expo-web-browser';
import * as Google from 'expo-auth-session/providers/google';
import { signInWithGoogle, devLogin } from '../../services/auth.service';
import { useColors } from '../../core/useColors';
import { usePreferencesStore } from '../../stores/preferences.store';
import { useT } from '../../core/i18n';

WebBrowser.maybeCompleteAuthSession();

const IS_DEV = __DEV__;

const LOGO_DARK = require('../../../assets/branding/logo-dark.png');
const LOGO_LIGHT = require('../../../assets/images/logo-black.png');

const GOOGLE_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID || '';

export function WelcomeScreen() {
  const colors = useColors();
  const resolved = usePreferencesStore((s) => s.resolvedTheme);
  const t = useT();
  const styles = useMemo(() => makeStyles(colors), [colors]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showDevLogin, setShowDevLogin] = useState(false);
  const [devEmail, setDevEmail] = useState('dev@fomo.ai');
  const [devName, setDevName] = useState('FOMO Developer');

  const logoSource = resolved === 'light' ? LOGO_LIGHT : LOGO_DARK;

  // Google OAuth via expo-auth-session
  const [request, response, promptAsync] = Google.useIdTokenAuthRequest({
    clientId: GOOGLE_CLIENT_ID,
  });

  useEffect(() => {
    if (response?.type === 'success') {
      const idToken = response.params?.id_token;
      if (idToken) {
        setLoading(true);
        setError(null);
        signInWithGoogle(idToken)
          .catch((err: any) => {
            setError(err?.response?.data?.detail || err?.message || 'Google auth failed');
          })
          .finally(() => setLoading(false));
      }
    } else if (response?.type === 'error') {
      setError(response.error?.message || 'Google auth failed');
    }
  }, [response]);

  const handleGooglePress = async () => {
    setError(null);
    if (!GOOGLE_CLIENT_ID) {
      setError('Google Client ID not configured');
      return;
    }
    // Google OAuth is blocked inside iframes (web preview) — detect and show clear message
    if (Platform.OS === 'web') {
      try {
        const inIframe = typeof window !== 'undefined' && window.self !== window.top;
        if (inIframe) {
          setError(t('welcome.googleWebPreview'));
          return;
        }
      } catch { /* cross-origin iframe — also blocked */ 
        setError(t('welcome.googleWebPreview'));
        return;
      }
    }
    try {
      await promptAsync();
    } catch (err: any) {
      setError(err?.message || 'Google Sign-In not available');
    }
  };

  const handleDevLogin = async () => {
    setError(null);
    setLoading(true);
    try {
      await devLogin(devEmail, devName);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Login failed';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  // Google button colors depend on theme
  const googleBg = resolved === 'light' ? '#1F1F1F' : '#FFFFFF';
  const googleText = resolved === 'light' ? '#FFFFFF' : '#1F1F1F';
  const googleIcon = resolved === 'light' ? '#FFFFFF' : '#1F1F1F';

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <View style={[styles.glowTop, { backgroundColor: colors.accent }]} />

        <View style={styles.logoSection}>
          <Image source={logoSource} style={styles.logo} resizeMode="contain" />
          <Text style={[styles.tagline, { color: colors.textPrimary }]}>{t('welcome.tagline')}</Text>
          <Text style={[styles.subtitle, { color: colors.textSecondary }]}>{t('welcome.subtitle')}</Text>
        </View>

        <View style={styles.valueProps}>
          <ValuePropRow icon="flash" label="Decision" sub="BUY / SELL / WAIT" desc={t('welcome.decision')} colors={colors} />
          <ValuePropRow icon="layers" label="Context" desc={t('welcome.context')} colors={colors} />
          <ValuePropRow icon="time" label="Timing" desc={t('welcome.timing')} colors={colors} />
        </View>

        <View style={styles.authSection}>
          {error && (
            <View style={[styles.errorContainer, { backgroundColor: colors.sell + '15' }]}>
              <Ionicons name="alert-circle" size={16} color={colors.sell} />
              <Text style={[styles.errorText, { color: colors.sell }]}>{error}</Text>
            </View>
          )}

          <TouchableOpacity
            style={[styles.googleButton, { backgroundColor: googleBg }]}
            onPress={handleGooglePress}
            disabled={loading}
            activeOpacity={0.8}
          >
            {loading && !showDevLogin ? (
              <ActivityIndicator color={googleText} />
            ) : (
              <>
                <Ionicons name="logo-google" size={20} color={googleIcon} />
                <Text style={[styles.googleButtonText, { color: googleText }]}>{t('welcome.google')}</Text>
              </>
            )}
          </TouchableOpacity>

          {IS_DEV && (
            <View style={styles.devSection}>
              {!showDevLogin ? (
                <TouchableOpacity
                  style={[styles.devToggle, { borderColor: colors.accent + '30' }]}
                  onPress={() => setShowDevLogin(true)}
                  activeOpacity={0.7}
                >
                  <Ionicons name="code-slash" size={14} color={colors.accent} />
                  <Text style={[styles.devToggleText, { color: colors.accent }]}>{t('auth.devLogin')}</Text>
                </TouchableOpacity>
              ) : (
                <View style={[styles.devForm, { borderColor: colors.accent + '25', backgroundColor: colors.surface }]}>
                  <View style={styles.devHeader}>
                    <Text style={[styles.devTitle, { color: colors.accent }]}>{t('auth.devLogin')}</Text>
                    <TouchableOpacity onPress={() => setShowDevLogin(false)}>
                      <Ionicons name="close" size={18} color={colors.textMuted} />
                    </TouchableOpacity>
                  </View>
                  
                  <TextInput
                    style={[styles.devInput, { backgroundColor: colors.background, borderColor: colors.border, color: colors.textPrimary }]}
                    value={devEmail}
                    onChangeText={setDevEmail}
                    placeholder="Email"
                    placeholderTextColor={colors.textMuted}
                    keyboardType="email-address"
                    autoCapitalize="none"
                  />
                  <TextInput
                    style={[styles.devInput, { backgroundColor: colors.background, borderColor: colors.border, color: colors.textPrimary }]}
                    value={devName}
                    onChangeText={setDevName}
                    placeholder="Name"
                    placeholderTextColor={colors.textMuted}
                  />

                  <TouchableOpacity
                    style={[styles.devLoginButton, { backgroundColor: colors.accent }]}
                    onPress={handleDevLogin}
                    disabled={loading}
                    activeOpacity={0.8}
                  >
                    {loading ? (
                      <ActivityIndicator color="#FFF" size="small" />
                    ) : (
                      <>
                        <Ionicons name="log-in" size={18} color="#FFF" />
                        <Text style={styles.devLoginText}>Sign In (Dev)</Text>
                      </>
                    )}
                  </TouchableOpacity>
                </View>
              )}
            </View>
          )}

          <Text style={[styles.termsText, { color: colors.textMuted }]}>
            {t('welcome.terms')}
          </Text>
        </View>

        <Text style={[styles.versionText, { color: colors.textMuted }]}>v1.0.0</Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function ValuePropRow({ icon, label, sub, desc, colors }: { icon: keyof typeof Ionicons.glyphMap; label: string; sub?: string; desc: string; colors: any }) {
  return (
    <View style={vpStyles.row}>
      <View style={[vpStyles.icon, { backgroundColor: colors.accent + '15' }]}>
        <Ionicons name={icon} size={16} color={colors.accent} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={[vpStyles.label, { color: colors.textPrimary }]}>{label}{sub ? ` · ${sub}` : ''}</Text>
        <Text style={[vpStyles.desc, { color: colors.textSecondary }]}>{desc}</Text>
      </View>
    </View>
  );
}

const vpStyles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'flex-start', gap: 16 },
  icon: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center', marginTop: 2 },
  label: { fontSize: 14, fontWeight: '600' },
  desc: { fontSize: 12, marginTop: 2, lineHeight: 17 },
});

const makeStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    flexGrow: 1,
    alignItems: 'center',
    justifyContent: 'flex-start',
    paddingHorizontal: 24,
    paddingTop: 60,
    paddingBottom: 32,
  },
  glowTop: {
    position: 'absolute',
    top: -100,
    width: 300,
    height: 300,
    borderRadius: 150,
    opacity: 0.05,
  },
  logoSection: {
    alignItems: 'center',
    marginBottom: 24,
  },
  logo: {
    width: 180,
    height: 60,
    marginBottom: 16,
  },
  tagline: {
    fontSize: 18,
    fontWeight: '700',
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 13,
    textAlign: 'center',
    lineHeight: 19,
    marginTop: 8,
    paddingHorizontal: 8,
  },
  valueProps: {
    marginBottom: 32,
    gap: 16,
    width: '100%',
  },
  authSection: {
    width: '100%',
    alignItems: 'center',
  },
  errorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: 16,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 10,
    maxWidth: '100%',
  },
  errorText: {
    fontSize: 12,
    flex: 1,
  },
  googleButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderRadius: 10,
    width: '100%',
    gap: 8,
    minHeight: 48,
    ...Platform.select({
      ios: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.1,
        shadowRadius: 4,
      },
      android: { elevation: 3 },
      default: {},
    }),
  },
  googleButtonText: {
    fontSize: 14,
    fontWeight: '600',
  },
  devSection: {
    width: '100%',
    marginTop: 24,
    alignItems: 'center',
  },
  devToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 20,
    borderWidth: 1,
  },
  devToggleText: {
    fontSize: 12,
    fontWeight: '500',
  },
  devForm: {
    width: '100%',
    borderWidth: 1,
    borderRadius: 10,
    padding: 16,
  },
  devHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  devTitle: {
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  devInput: {
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    marginBottom: 8,
  },
  devLoginButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 8,
    gap: 8,
    marginTop: 4,
    minHeight: 48,
  },
  devLoginText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFF',
  },
  termsText: {
    fontSize: 11,
    textAlign: 'center',
    marginTop: 16,
    lineHeight: 16,
  },
  versionText: {
    fontSize: 11,
    marginTop: 16,
  },
});
