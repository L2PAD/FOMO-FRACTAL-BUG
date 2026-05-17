/**
 * Prediction Panel - System prediction summary
 * Question: Что система ожидает дальше?
 */

import React from 'react';
import { GridRow } from '../shared/GridRow';
import MetricBar from '../shared/MetricBar';

export default function PredictionPanel({ data }) {
  if (!data) {
    return (
      <div className="text-center text-sm text-gray-500 py-8">
        No prediction data available
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-400">
        Prediction
      </h3>
      <div className="space-y-3">
        <GridRow label="Direction" value={data.direction} />
        <GridRow label="Horizon" value={data.horizon} />
        <MetricBar label="Prediction Confidence" value={data.confidence} />
        <GridRow label="Primary" value={data.primary_scenario} />
        <GridRow label="Alternative" value={data.alternative_scenario} />
        <GridRow label="Trigger" value={data.trigger} />
        <GridRow label="Invalidation" value={data.invalidation} />
      </div>
    </div>
  );
}
