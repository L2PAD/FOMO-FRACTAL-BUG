import React from 'react';
import { useAppMode } from '../../stores/app-mode.store';
import { IntelligenceShell } from './IntelligenceShell';
import { TradingShell } from './TradingShell';

export function AppShell() {
  const mode = useAppMode((s) => s.mode);

  if (mode === 'TRADING') {
    return <TradingShell />;
  }

  return <IntelligenceShell />;
}
