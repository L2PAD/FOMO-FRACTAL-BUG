/**
 * Context Panel - Market environment context
 * Question: Что за среда рынка сейчас?
 */

import React from 'react';
import { PanelShell } from '../shared/PanelShell';
import { GridRow } from '../shared/GridRow';
import MetricBar from '../shared/MetricBar';

export default function ContextPanel({ data }) {
  if (!data) {
    return (
      <div className="text-center text-sm text-gray-500 py-8">
        No context data available
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-400">
        Market Context
      </h3>
      <div className="space-y-3">
        <GridRow label="Regime" value={data.market_regime} />
        <GridRow label="Volatility" value={data.volatility_state} />
        <GridRow label="Liquidity" value={data.liquidity_state} />
        <GridRow label="Macro Bias" value={data.macro_bias} />
        <GridRow label="Dominance" value={data.dominance_context} />
        <MetricBar label="Context Confidence" value={data.confidence} />
      </div>
    </div>
  );
}
