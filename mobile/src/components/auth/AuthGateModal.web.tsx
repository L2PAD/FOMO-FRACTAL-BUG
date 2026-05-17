/**
 * P1 AuthGateModal — Web only.
 * 
 * Full-screen overlay that loads Google Identity Services, shows the
 * official Google Sign-In button, POSTs the id_token to
 * /api/unified/auth/google, stores JWT, refetches access preview,
 * merges guest funnel events, then closes and fires onSuccess.
 */
import React, { useEffect, useRef, useState } from 'react';
import { View, Text, Pressable, StyleSheet, ActivityIndicator } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { api } from '../../services/api/api-client';
import { useAccessStore } from '../../stores/access.store';

export interface AuthGateModalProps {
  open: boolean;
  onClose: () => void;
  surface?: string;
  blockKey?: string;
  onSuccess?: () => void;
}

function loadGoogleSDK(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined') return reject(new Error('no_window'));
    const w = window as any;
    if (w.google?.accounts?.id) return resolve();
    const s = document.createElement('script');
    s.src = 'https://accounts.google.com/gsi/client';
    s.async = true;
    s.defer = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error('google_sdk_failed'));
    document.head.appendChild(s);
  });
}

export default function AuthGateModal({ open, onClose, surface, blockKey, onSuccess }: AuthGateModalProps) {
  const [status, setStatus] = useState<string>('');
  const [isError, setIsError] = useState(false);
  const btnRef = useRef<any>(null);
  const fetchPreview = useAccessStore((s) => s.fetchPreview);
  const mergeGuestSession = useAccessStore((s) => s.mergeGuestSession);
  const trackEvent = useAccessStore((s) => s.trackEvent);

  useEffect(() => {
    if (!open || typeof window === 'undefined') return;
    setStatus('');
    setIsError(false);
    trackEvent('web_auth_prompt_shown', { surface, block_key: blockKey });

    let cancelled = false;
    (async () => {
      try {
        await loadGoogleSDK();
        if (cancelled) return;
        const w = window as any;
        const clientId =
          (process.env as any).EXPO_PUBLIC_GOOGLE_CLIENT_ID ||
          '539552820560-pso3qndegrntp46oneml9nr33t7rpi9j.apps.googleusercontent.com';
        w.google.accounts.id.initialize({
          client_id: clientId,
          callback: async (resp: any) => {
            setStatus('Signing you in…');
            setIsError(false);
            try {
              const r = await api.post('/api/unified/auth/google', {
                idToken: resp.credential,
                platform: 'web',
              });
              const body = r.data || {};
              const token = body.accessToken || body.access_token || body.token;
              if (token) {
                try { await AsyncStorage.setItem('auth_token', token); } catch {}
                try { await AsyncStorage.setItem('accessToken', token); } catch {}
              }
              if (body.refreshToken) {
                try { await AsyncStorage.setItem('refreshToken', body.refreshToken); } catch {}
              }
              await fetchPreview();
              await mergeGuestSession();
              trackEvent('web_auth_completed', { surface, block_key: blockKey });
              setStatus('Signed in.');
              onSuccess?.();
              setTimeout(onClose, 200);
            } catch (e: any) {
              setStatus('Sign-in failed. Please try again.');
              setIsError(true);
            }
          },
        });
        if (btnRef.current && !cancelled) {
          btnRef.current.innerHTML = '';
          w.google.accounts.id.renderButton(btnRef.current, {
            theme: 'filled_black',
            size: 'large',
            type: 'standard',
            shape: 'pill',
            text: 'continue_with',
            width: 320,
          });
        }
      } catch (e) {
        setStatus('Could not load Google sign-in. Refresh and try again.');
        setIsError(true);
      }
    })();
    return () => { cancelled = true; };
  }, [open, surface, blockKey, fetchPreview, mergeGuestSession, trackEvent, onClose, onSuccess]);

  if (!open) return null;

  return (
    <View style={styles.overlay}>
      <Pressable style={styles.backdrop} onPress={onClose} />
      <View style={styles.modal}>
        <View style={styles.topRow}>
          <Text style={styles.kicker}>SECURE CHECKOUT</Text>
          <Pressable onPress={onClose} hitSlop={10}>
            <Text style={styles.close}>×</Text>
          </Pressable>
        </View>
        <Text style={styles.title}>Sign in to continue</Text>
        <Text style={styles.sub}>
          Create your account before we take any money — your subscription is
          attached to you, not lost.
        </Text>
        <View
          ref={btnRef as any}
          // @ts-ignore — DOM attribute for web only
          nativeID="google-signin-btn"
          style={styles.googleBtnWrap}
        />
        <View style={styles.statusRow}>
          {status ? <Text style={[styles.status, isError && styles.statusErr]}>{status}</Text> : <ActivityIndicator size="small" color="#71717a" />}
        </View>
        <Text style={styles.fine}>By continuing you agree to our Terms & Privacy.</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    position: 'absolute',
    top: 0, left: 0, right: 0, bottom: 0,
    zIndex: 99999,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
    // @ts-ignore — web-only CSS
    ...({position: 'fixed'} as any),
  },
  backdrop: {
    position: 'absolute',
    top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.7)',
  },
  modal: {
    backgroundColor: '#0F141B',
    borderColor: '#16202B',
    borderWidth: 1,
    borderRadius: 16,
    padding: 24,
    maxWidth: 400,
    width: '100%',
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  kicker: {
    fontSize: 10,
    fontWeight: '800',
    color: '#a1a1aa',
    letterSpacing: 2,
  },
  close: { color: '#a1a1aa', fontSize: 22, width: 28, height: 28, textAlign: 'center', lineHeight: 24 },
  title: { fontSize: 22, fontWeight: '800', color: '#E6EDF3', marginBottom: 8 },
  sub: { fontSize: 14, color: '#a1a1aa', lineHeight: 20, marginBottom: 22 },
  googleBtnWrap: {
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  statusRow: { marginTop: 14, minHeight: 16, alignItems: 'center' },
  status: { fontSize: 12, color: '#a1a1aa' },
  statusErr: { color: '#FF6B6B' },
  fine: {
    marginTop: 18,
    paddingTop: 14,
    borderTopColor: '#16202B',
    borderTopWidth: 1,
    fontSize: 11,
    color: '#71717a',
    textAlign: 'center',
    lineHeight: 16,
  },
});
