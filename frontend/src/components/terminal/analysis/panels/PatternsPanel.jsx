/**
 * Patterns Panel - Chart patterns summary
 * Question: Какая форма рынка доминирует?
 */

import React from 'react';
import { GridRow } from '../shared/GridRow';
import { TagList } from '../shared/TagList';
import { fmtPct } from '../shared/formatters';

export default function PatternsPanel({ data }) {
  if (!data) {
    return (
      <div className="text-center text-sm text-gray-500 py-8">
        No patterns data available
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-400">
        Patterns
      </h3>
      <div className="space-y-3">
        <GridRow label="Dominant" value={data.dominant?.label || '—'} />
        <GridRow label="Type" value={data.dominant?.type || '—'} />
        <GridRow label="State" value={data.dominant?.state || '—'} />
        <GridRow label="Bias" value={data.dominant?.bias || '—'} />
        <GridRow label="Confidence" value={fmtPct(data.dominant?.confidence)} />
        <GridRow label="Trigger" value={data.trigger || '—'} />
        <GridRow label="Invalidation" value={data.invalidation || '—'} />
        <TagList
          title="Alternatives"
          items={(data.alternatives || []).map(
            (x) => `${x.label} (${Math.round((x.confidence || 0) * 100)}%)`
          )}
          empty="No alternatives"
        />
      </div>
    </div>
  );
}
