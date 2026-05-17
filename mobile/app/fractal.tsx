import React from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import FractalScreen from '../src/modules/trading/intelligence/FractalScreen';

/**
 * /fractal — Fractal intelligence dashboard for Mobile (Expo).
 */
export default function FractalRoute() {
  return (
    <SafeAreaProvider>
      <FractalScreen />
    </SafeAreaProvider>
  );
}
