/**
 * Confluence Panel - Signal confirmation analysis
 * Question: Насколько сигнал подтверждён?
 */

import React from 'react';
import { GridRow } from '../shared/GridRow';
import { TagList } from '../shared/TagList';
import MetricBar from '../shared/MetricBar';

export default function ConfluencePanel({ data }) {
  if (!data) {
    return (
      <div className="text-center text-sm text-gray-500 py-8">
        No confluence data available
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-400">
        Confluence
      </h3>
      <div className="space-y-3">
        <GridRow label="Status" value={data.status} />
        <MetricBar label="Confluence Score" value={data.score} />
        <TagList
          title="Bullish Factors"
          items={data.bullish_factors}
          empty="No bullish factors"
        />
        <TagList
          title="Bearish Factors"
          items={data.bearish_factors}
          empty="No bearish factors"
        />
        <TagList title="Conflicts" items={data.conflicts} empty="No conflicts" />
      </div>
    </div>
  );
}
