import React from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import ExchangeScreen from '../src/modules/trading/intelligence/ExchangeScreen';

/**
 * /exchange-board — CEX intelligence dashboard for Mobile.
 * (We can't use /exchange because that path is the Google OAuth callback shim.)
 */
export default function ExchangeBoardRoute() {
  return (
    <SafeAreaProvider>
      <ExchangeScreen />
    </SafeAreaProvider>
  );
}
