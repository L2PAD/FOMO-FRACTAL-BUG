import { useState } from 'react';

/**
 * useIntelligenceView — UI state for intelligence panel.
 * Does NOT filter signals (that's the registry's job).
 * Only manages expandable wallet panel state.
 *
 * Contract:
 *   readonly: expandedWalletSignal
 *   actions:  setExpandedWalletSignal
 */
export function useIntelligenceView() {
  const [expandedWalletSignal, setExpandedWalletSignal] = useState(null);

  return { expandedWalletSignal, setExpandedWalletSignal };
}
