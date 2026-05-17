/**
 * Regime Panel - Market regime analysis
 * Question: В каком режиме это работает?
 */

import React from 'react';
import { GridRow } from '../shared/GridRow';
import { TagList } from '../shared/TagList';
import MetricBar from '../shared/MetricBar';

export default function RegimePanel({ data }) {
  if (!data) {
    return (
      <div className="text-center text-sm text-gray-500 py-8">
        No regime data available
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-400">
        Regime
      </h3>
      <div className="space-y-3">
        <GridRow label="Current" value={data.current} />
        <GridRow label="Allowed Activity" value={data.allowed_activity} />
        <MetricBar label="Regime Strength" value={data.strength} />
        <TagList
          title="Best Fit"
          items={data.best_fit}
          empty="No best-fit modes"
        />
        <TagList title="Avoid" items={data.avoid} empty="No avoid list" />
      </div>
    </div>
  );
}
