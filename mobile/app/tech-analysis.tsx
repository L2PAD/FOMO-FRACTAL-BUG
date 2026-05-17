import React from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import TechAnalysisScreen from '../src/modules/trading/intelligence/TechAnalysisScreen';

export default function TechAnalysisRoute() {
  return (
    <SafeAreaProvider>
      <TechAnalysisScreen />
    </SafeAreaProvider>
  );
}
