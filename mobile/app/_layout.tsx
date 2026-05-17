// Root layout: pre-loads icon fonts to prevent the
// `fontfaceobserver: 6000ms timeout exceeded` Uncaught Error overlay that
// surfaced on Expo Web/iOS when @expo/vector-icons loaded the Ionicons.ttf
// font lazily. We also globally ignore the residual log/rejection so the
// dev RedBox doesn't appear on slow networks. This is purely additive —
// it does NOT change app routing or AppGate behaviour (existing screens
// like /index, /info, /exchange, /terminal continue to render unchanged).

import React, { useEffect } from 'react';
import { LogBox, Platform } from 'react-native';
import { Stack } from 'expo-router';
import { useFonts } from 'expo-font';
import * as SplashScreen from 'expo-splash-screen';
import Ionicons from '@expo/vector-icons/Ionicons';

// Suppress the noisy fontfaceobserver timeout in dev RedBox.
LogBox.ignoreLogs([
  '6000ms timeout exceeded',
  'fontfaceobserver',
  'fontFamily',
]);

// Web: swallow unhandled rejections coming from fontfaceobserver so the
// Expo dev error overlay doesn't appear. We never want a font timeout to
// crash the app or block UX.
if (Platform.OS === 'web' && typeof window !== 'undefined') {
  window.addEventListener('unhandledrejection', (ev: any) => {
    const msg = String(ev?.reason?.message || ev?.reason || '');
    if (msg.includes('timeout exceeded') || msg.includes('fontfaceobserver')) {
      ev.preventDefault?.();
    }
  });
}

SplashScreen.preventAutoHideAsync().catch(() => {});

export default function RootLayout() {
  const [loaded, error] = useFonts({
    ...Ionicons.font,
  });

  useEffect(() => {
    if (loaded || error) {
      SplashScreen.hideAsync().catch(() => {});
    }
  }, [loaded, error]);

  // Render the stack regardless of font-loader outcome — icons gracefully
  // fall back to system glyphs if the font failed to load.
  return <Stack screenOptions={{ headerShown: false }} />;
}
