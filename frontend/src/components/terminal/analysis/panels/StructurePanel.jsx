/**
 * Structure Panel - Price structure analysis
 * Question: Как устроено движение цены?
 */

import React from 'react';
import { GridRow } from '../shared/GridRow';
import MetricBar from '../shared/MetricBar';

export default function StructurePanel({ data }) {
  if (!data) {
    return (
      <div className="text-center text-sm text-gray-500 py-8">
        No structure data available
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-400">
        Structure
      </h3>
      <div className="space-y-3">
        <GridRow label="Trend" value={data.trend_state} />
        <GridRow label="Phase" value={data.phase} />
        <GridRow label="Last BOS" value={data.last_bos} />
        <GridRow label="Last CHOCH" value={data.last_choch} />
        <GridRow label="Range" value={data.range_state} />
        <GridRow label="Compression" value={data.compression_state} />
        <GridRow label="Bias" value={data.structural_bias} />
        <MetricBar label="Structure Confidence" value={data.confidence} />
      </div>
    </div>
  );
}
