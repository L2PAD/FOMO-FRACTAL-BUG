import React from 'react';
import GraphExplorer from './EntityGraphExplorer';

const GRAPH_COLORS = {
  token: '#f59e0b',
  project: '#3b82f6',
  protocol: '#8b5cf6',
  fund: '#10b981',
  person: '#ec4899',
  twitter_account: '#06b6d4',
  chain: '#6366f1',
  developer: '#14b8a6',
  wallet: '#6b7280',
  exchange: '#ef4444',
  background: '#0d0d14',
  text: '#e2e8f0',
  edge: '#1e293b',
  edgeHighlight: '#f59e0b',
};

export default function EntityGraphTab() {
  return (
    <div data-testid="entity-graph-tab" style={{ background: '#f8fafc' }}>
      <GraphExplorer colors={GRAPH_COLORS} />
    </div>
  );
}
