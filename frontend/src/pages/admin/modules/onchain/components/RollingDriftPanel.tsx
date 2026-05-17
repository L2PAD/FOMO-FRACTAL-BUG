/**
 * OnChain V2 — Rolling & Drift Panel (O9.5 UI)
 * ==============================================
 * 
 * Institutional-grade stability monitoring.
 * Two side-by-side cards: Rolling 30d + PSI Drift
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Card } from './Card';
import { RefreshCw, Plus, AlertTriangle, CheckCircle, TrendingUp, Database } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

interface RollingStats {
  symbol: string;
  window: string;
  sampleCount: number;
  score: {
    avg: number;
    std: number;
    min: number;
    max: number;
    median: number;
  };
  confidence: {
    avg: number;
    std: number;
    min: number;
    max: number;
  };
  stateDistribution: Record<string, number>;
  computedAt: number;
  health: {
    sufficientSamples: boolean;
    stableVariance: boolean;
    recentActivity: boolean;
  };
}

interface DriftResult {
  symbol: string;
  psi: number;
  level: string;
  hasBaseline: boolean;
  sampleCount: number;
  bucketComparison: Array<{
    bucket: number;
    expected: number;
    actual: number;
    contribution: number;
  }>;
  thresholds: {
    warn: number;
    degraded: number;
    critical: number;
  };
}

interface BaselineInfo {
  symbol: string;
  metric: string;
  version: number;
  createdAt: number;
  sampleCount: number;
  avgScore: number;
}

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

const LEVEL_COLORS: Record<string, string> = {
  OK: 'bg-emerald-100 text-emerald-700',
  WARN: 'bg-amber-100 text-amber-700',
  DEGRADED: 'bg-orange-100 text-orange-700',
  CRITICAL: 'bg-red-100 text-red-700',
};

function formatAgo(ts: number): string {
  const hours = Math.floor((Date.now() - ts) / 3600000);
  if (hours < 1) return 'just now';
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

// ═══════════════════════════════════════════════════════════════
// ROLLING PANEL
// ═══════════════════════════════════════════════════════════════

interface RollingPanelProps {
  symbol: string;
}

function RollingPanel({ symbol }: RollingPanelProps) {
  const [rolling, setRolling] = useState<RollingStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [computing, setComputing] = useState(false);

  const fetchRolling = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v10/onchain-v2/governance/rolling?symbol=${symbol}`);
      const data = await res.json();
      if (data.ok && data.rolling) {
        setRolling(data.rolling);
      } else {
        setRolling(null);
      }
    } catch {
      setRolling(null);
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    fetchRolling();
  }, [fetchRolling]);

  const handleRecompute = async () => {
    setComputing(true);
    try {
      await fetch(`${API_URL}/api/v10/onchain-v2/governance/compute-rolling`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, window: '30d' }),
      });
      await fetchRolling();
    } finally {
      setComputing(false);
    }
  };

  if (loading) {
    return (
      <Card title="Rolling 30d" className="flex-1">
        <div className="flex items-center justify-center py-6 text-slate-400">
          <RefreshCw className="w-4 h-4 animate-spin mr-2" />
          Loading...
        </div>
      </Card>
    );
  }

  if (!rolling || rolling.sampleCount === 0) {
    return (
      <Card title="Rolling 30d" className="flex-1">
        <div className="text-center py-4">
          <Database className="w-8 h-8 text-slate-300 mx-auto mb-2" />
          <div className="text-sm text-slate-500 mb-3">No rolling data</div>
          <button
            onClick={handleRecompute}
            disabled={computing}
            className="px-3 py-1.5 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
          >
            {computing ? 'Computing...' : 'Compute Rolling'}
          </button>
        </div>
      </Card>
    );
  }

  // State distribution - top 2, convert counts to percentages
  const totalStates = Object.values(rolling.stateDistribution || {}).reduce((a, b) => a + b, 0);
  const states = Object.entries(rolling.stateDistribution || {})
    .filter(([_, count]) => count > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([state, count]) => [state, totalStates > 0 ? (count / totalStates) : 0] as [string, number]);

  const lowSamples = rolling.sampleCount < 50;

  return (
    <Card title="Rolling 30d" className="flex-1">
      <div className="space-y-3">
        {/* Top metrics line */}
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-1">
            <span className="text-slate-500">Samples:</span>
            <span className={`font-semibold tabular-nums ${lowSamples ? 'text-amber-600' : 'text-slate-800'}`}>
              {rolling.sampleCount}
            </span>
            {lowSamples && (
              <span className="text-xs px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded">LOW</span>
            )}
          </div>
          <div className="text-slate-300">|</div>
          <div>
            <span className="text-slate-500">μ:</span>
            <span className="font-semibold tabular-nums ml-1">{(rolling.score?.avg ?? 0).toFixed(2)}</span>
          </div>
          <div>
            <span className="text-slate-500">σ:</span>
            <span className="font-semibold tabular-nums ml-1">{(rolling.score?.std ?? 0).toFixed(2)}</span>
          </div>
          <div>
            <span className="text-slate-500">Conf μ:</span>
            <span className="font-semibold tabular-nums ml-1">{(rolling.confidence?.avg ?? 0).toFixed(2)}</span>
          </div>
        </div>

        {/* State distribution */}
        {states.length > 0 && (
          <div className="flex items-center gap-2 text-xs">
            {states.map(([state, pct]) => (
              <span
                key={state}
                className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded"
              >
                {state} {(pct * 100).toFixed(0)}%
              </span>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between pt-2 border-t border-slate-100">
          <span className="text-xs text-slate-400">
            Computed: {formatAgo(rolling.computedAt)}
          </span>
          <button
            onClick={handleRecompute}
            disabled={computing}
            className="flex items-center gap-1 px-2 py-1 text-xs text-slate-500 hover:text-slate-700 hover:bg-slate-50 rounded"
          >
            <RefreshCw className={`w-3 h-3 ${computing ? 'animate-spin' : ''}`} />
            Recompute
          </button>
        </div>
      </div>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════
// DRIFT PANEL
// ═══════════════════════════════════════════════════════════════

interface DriftPanelProps {
  symbol: string;
}

function DriftPanel({ symbol }: DriftPanelProps) {
  const [drift, setDrift] = useState<DriftResult | null>(null);
  const [baseline, setBaseline] = useState<BaselineInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const fetchDrift = useCallback(async () => {
    try {
      const [driftRes, baselineRes] = await Promise.all([
        fetch(`${API_URL}/api/v10/onchain-v2/governance/drift?symbol=${symbol}`),
        fetch(`${API_URL}/api/v10/onchain-v2/governance/baseline?symbol=${symbol}`),
      ]);
      
      const driftData = await driftRes.json();
      const baselineData = await baselineRes.json();
      
      if (driftData.ok) {
        setDrift(driftData.drift);
      }
      if (baselineData.ok && baselineData.baseline) {
        setBaseline(baselineData.baseline);
      } else {
        setBaseline(null);
      }
    } catch {
      setDrift(null);
      setBaseline(null);
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    fetchDrift();
  }, [fetchDrift]);

  const handleCreateBaseline = async () => {
    setCreating(true);
    try {
      await fetch(`${API_URL}/api/v10/onchain-v2/governance/create-baseline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, metric: 'score' }),
      });
      await fetchDrift();
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return (
      <Card title="PSI Drift" className="flex-1">
        <div className="flex items-center justify-center py-6 text-slate-400">
          <RefreshCw className="w-4 h-4 animate-spin mr-2" />
          Loading...
        </div>
      </Card>
    );
  }

  // No baseline state
  if (!baseline || !drift?.hasBaseline) {
    return (
      <Card title="PSI Drift" className="flex-1">
        <div className="text-center py-4">
          <AlertTriangle className="w-8 h-8 text-amber-400 mx-auto mb-2" />
          <div className="text-sm text-slate-600 mb-1">No active baseline</div>
          <div className="text-xs text-slate-400 mb-3">Create baseline to enable drift monitoring</div>
          <button
            onClick={handleCreateBaseline}
            disabled={creating}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 mx-auto"
          >
            <Plus className="w-3 h-3" />
            {creating ? 'Creating...' : 'Create Baseline'}
          </button>
        </div>
      </Card>
    );
  }

  // Top 2 bucket contributions
  const topBuckets = (drift.bucketComparison || [])
    .filter(b => b.contribution > 0.001)
    .sort((a, b) => b.contribution - a.contribution)
    .slice(0, 2);

  const levelColor = LEVEL_COLORS[drift.level] || LEVEL_COLORS.OK;

  return (
    <Card title="PSI Drift" className="flex-1">
      <div className="space-y-3">
        {/* PSI + Level */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-slate-500 text-sm">PSI:</span>
            <span className="text-lg font-semibold tabular-nums">{drift.psi.toFixed(3)}</span>
          </div>
          <span className={`px-2 py-0.5 text-xs font-medium rounded ${levelColor}`}>
            {drift.level}
          </span>
        </div>

        {/* Baseline info */}
        <div className="text-xs text-slate-500">
          Baseline: v{baseline.version} ({formatAgo(baseline.createdAt)}) • {baseline.sampleCount} samples
        </div>

        {/* Top bucket shifts */}
        {topBuckets.length > 0 && drift.psi > 0 && (
          <div className="text-xs text-slate-600 space-y-1">
            <div className="text-slate-400">Top shifts:</div>
            {topBuckets.map((b) => (
              <div key={b.bucket} className="flex items-center gap-2">
                <span className="w-14">Bucket {b.bucket}:</span>
                <span className={`tabular-nums ${b.contribution > 0.05 ? 'text-amber-600' : ''}`}>
                  +{b.contribution.toFixed(3)}
                </span>
                <span className="text-slate-400">
                  ({(b.expected * 100).toFixed(0)}% → {(b.actual * 100).toFixed(0)}%)
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-2 pt-2 border-t border-slate-100">
          <button
            onClick={fetchDrift}
            className="flex items-center gap-1 px-2 py-1 text-xs text-slate-500 hover:text-slate-700 hover:bg-slate-50 rounded"
          >
            <RefreshCw className="w-3 h-3" />
            Refresh
          </button>
          <button
            onClick={handleCreateBaseline}
            disabled={creating}
            className="flex items-center gap-1 px-2 py-1 text-xs text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded disabled:opacity-50"
          >
            <Plus className="w-3 h-3" />
            {creating ? 'Creating...' : 'New Baseline'}
          </button>
        </div>
      </div>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════
// COMBINED COMPONENT
// ═══════════════════════════════════════════════════════════════

interface RollingDriftPanelProps {
  symbol?: string;
}

export function RollingDriftPanel({ symbol = 'ETH' }: RollingDriftPanelProps) {
  return (
    <div className="grid md:grid-cols-2 gap-4">
      <RollingPanel symbol={symbol} />
      <DriftPanel symbol={symbol} />
    </div>
  );
}
