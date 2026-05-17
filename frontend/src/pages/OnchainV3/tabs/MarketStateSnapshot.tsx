/**
 * Market State Snapshot — On-chain v3 Overview
 * ==============================================
 * 
 * Migrated concept from legacy P0Dashboard (Exchange Pressure).
 * Shows aggregated market state: Net Flow Bias, Signal Coverage,
 * Conflict Rate, Contributing Factors, Confidence Calibration.
 * Uses /api/advanced/signals-attribution endpoint.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  Shield,
  AlertTriangle,
  RefreshCw,
  Loader2,
  TrendingUp,
  TrendingDown,
  Minus,
  Gauge,
  Zap,
  Target,
} from 'lucide-react';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

interface Coverage {
  activeSignals: number;
  coveragePercent: number;
  conflictRate: number;
}

interface ImpactSignal {
  signalType: string;
  direction: 'POSITIVE' | 'NEGATIVE';
  confidenceImpact: number;
}

interface Calibration {
  status: string;
  note?: string;
}

interface AttributionData {
  coverage: Coverage;
  topImpactSignals: ImpactSignal[];
  confidenceCalibration: Calibration;
}

const CALIBRATION_STYLE: Record<string, { bg: string; text: string; label: string }> = {
  OK: { bg: 'bg-emerald-50', text: 'text-emerald-700', label: 'Calibrated' },
  OVERCONFIDENT: { bg: 'bg-amber-50', text: 'text-amber-700', label: 'Overconfident' },
  UNDERCONFIDENT: { bg: 'bg-blue-50', text: 'text-blue-700', label: 'Underconfident' },
  INSUFFICIENT_DATA: { bg: 'bg-gray-50', text: 'text-gray-600', label: 'Insufficient Data' },
};

const SIGNAL_ICON: Record<string, React.ElementType> = {
  DEX_FLOW: Zap,
  WHALE_TX: Activity,
  CORRIDOR_SPIKE: Target,
};

export function MarketStateSnapshot() {
  const [data, setData] = useState<AttributionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async (isRefresh = false) => {
    try {
      if (!isRefresh) setLoading(true);
      setError(null);
      const res = await fetch(`${API_BASE}/api/advanced/signals-attribution`);
      if (!res.ok) throw new Error(`API ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div className="rounded-2xl bg-white p-6" data-testid="market-state-section">
        <div className="flex items-center gap-2 mb-4">
          <Gauge className="w-4 h-4 text-indigo-500" />
          <span className="text-sm font-semibold text-gray-700">Market State</span>
        </div>
        <div className="flex items-center justify-center py-10">
          <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-2xl bg-white p-6" data-testid="market-state-section">
        <div className="flex items-center gap-2 mb-4">
          <Gauge className="w-4 h-4 text-indigo-500" />
          <span className="text-sm font-semibold text-gray-700">Market State</span>
        </div>
        <div className="text-center py-8">
          <AlertTriangle className="w-8 h-8 text-gray-400 mx-auto mb-2" />
          <p className="text-sm text-gray-500">{error || 'No data'}</p>
          <button onClick={() => fetchData()} className="mt-3 text-sm text-blue-600 hover:underline" data-testid="market-state-retry">Retry</button>
        </div>
      </div>
    );
  }

  const { coverage, topImpactSignals, confidenceCalibration } = data;
  const conflictPct = ((coverage?.conflictRate || 0) * 100).toFixed(1);
  const calStyle = CALIBRATION_STYLE[confidenceCalibration?.status] || CALIBRATION_STYLE.INSUFFICIENT_DATA;

  return (
    <div className="rounded-2xl bg-white p-6" data-testid="market-state-section">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <Gauge className="w-4 h-4 text-indigo-500" />
          <span className="text-sm font-semibold text-gray-700">Market State</span>
        </div>
        <button
          onClick={() => fetchData(true)}
          className="p-1 rounded hover:bg-gray-100 transition-colors"
          data-testid="market-state-refresh"
        >
          <RefreshCw className="w-3.5 h-3.5 text-gray-400" />
        </button>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="rounded-xl bg-gray-50 p-3">
          <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Active Signals</div>
          <div className="text-2xl font-bold text-gray-900">{coverage?.activeSignals || 0}</div>
        </div>
        <div className="rounded-xl bg-gray-50 p-3">
          <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Coverage</div>
          <div className="text-2xl font-bold text-gray-900">{coverage?.coveragePercent || 0}%</div>
        </div>
        <div className="rounded-xl bg-gray-50 p-3">
          <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Conflict Rate</div>
          <div className={`text-2xl font-bold ${Number(conflictPct) > 20 ? 'text-red-600' : Number(conflictPct) > 10 ? 'text-amber-600' : 'text-gray-900'}`}>
            {conflictPct}%
          </div>
        </div>
      </div>

      {/* Contributing Factors */}
      {topImpactSignals && topImpactSignals.length > 0 && (
        <div className="mb-4">
          <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-2">Contributing Factors</div>
          <div className="space-y-1.5">
            {topImpactSignals.slice(0, 5).map((signal, idx) => {
              const Icon = SIGNAL_ICON[signal.signalType] || Activity;
              const isPositive = signal.direction === 'POSITIVE';
              return (
                <div key={idx} className="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-50" data-testid={`contributing-factor-${idx}`}>
                  <div className="flex items-center gap-2">
                    {isPositive ? (
                      <TrendingUp className="w-3.5 h-3.5 text-emerald-600" />
                    ) : (
                      <TrendingDown className="w-3.5 h-3.5 text-red-500" />
                    )}
                    <Icon className="w-3.5 h-3.5 text-gray-400" />
                    <span className="text-sm text-gray-700">{signal.signalType.replace(/_/g, ' ')}</span>
                  </div>
                  <span className={`text-sm font-semibold ${isPositive ? 'text-emerald-600' : 'text-red-500'}`}>
                    {signal.confidenceImpact > 0 ? '+' : ''}{signal.confidenceImpact}%
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Confidence Calibration */}
      <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${calStyle.bg}`}>
        <Shield className={`w-3.5 h-3.5 ${calStyle.text}`} />
        <span className="text-xs">
          <span className="font-medium">Calibration:</span>{' '}
          <span className={`font-semibold ${calStyle.text}`}>{calStyle.label}</span>
        </span>
        {confidenceCalibration?.note && (
          <span className={`text-[10px] ml-auto ${calStyle.text} opacity-70`}>
            {confidenceCalibration.note}
          </span>
        )}
      </div>
    </div>
  );
}

export default MarketStateSnapshot;
