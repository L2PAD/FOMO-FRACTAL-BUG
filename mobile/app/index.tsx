import React from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AppGate } from '../src/core/AppGate';

export default function App() {
  return (
    <SafeAreaProvider>
      <AppGate />
    </SafeAreaProvider>
  );
}
