import React from 'react';
import { OnchainChartLatest } from './onchainApi';

interface OnchainContextCardProps {
  latest: OnchainChartLatest | null;
  policyVersion: string | null;
  provider: string;
  loading?: boolean;
}

const STATE_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  ACCUMULATION: { label: 'Accumulation', color: 'text-emerald-700', bg: 'bg-emerald-100' },
  DISTRIBUTION: { label: 'Distribution', color: 'text-rose-700', bg: 'bg-rose-100' },
  NEUTRAL: { label: 'Neutral', color: 'text-slate-700', bg: 'bg-slate-100' },
  LOW_CONF: { label: 'Low Confidence', color: 'text-amber-700', bg: 'bg-amber-100' },
  NO_DATA: { label: 'No Data', color: 'text-slate-500', bg: 'bg-slate-100' },
};

function getConfidenceBadge(confidence: number): { label: string; color: string } {
  if (confidence < 0.40) return { label: 'LOW', color: 'text-amber-600 bg-amber-50 border-amber-200' };
  if (confidence < 0.70) return { label: 'OK', color: 'text-slate-600 bg-slate-50 border-slate-200' };
  return { label: 'HIGH', color: 'text-emerald-600 bg-emerald-50 border-emerald-200' };
}

export function OnchainContextCard({ latest, policyVersion, provider, loading }: OnchainContextCardProps) {
  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-4 animate-pulse">
        <div className="h-4 bg-slate-200 rounded w-24 mb-3" />
        <div className="h-8 bg-slate-100 rounded w-32" />
      </div>
    );
  }

  if (!latest) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <div className="text-xs font-medium text-slate-500 mb-2">On-Chain Context</div>
        <div className="text-sm text-slate-400">Data not available</div>
      </div>
    );
  }

  const confidencePercent = Math.round(latest.confidence * 100);
  const scorePercent = Math.round(latest.score * 100);
  const confidenceBadge = getConfidenceBadge(latest.confidence);
  
  const hasNoData = latest.flags.includes('NO_DATA');
  const isMock = latest.flags.includes('MOCK_DATA');
  const isStale = latest.flags.includes('STALE');
  const isLowConfidence = latest.flags.includes('LOW_CONFIDENCE');
  
  // Determine effective state for display
  // NO_DATA takes precedence, then LOW_CONF if confidence is low
  const effectiveState = hasNoData ? 'NO_DATA' : 
                         isLowConfidence ? 'LOW_CONF' : 
                         latest.state;
  const stateConfig = STATE_CONFIG[effectiveState] || STATE_CONFIG.NO_DATA;
  
  // Should show metrics grayed out?
  const isDataIncomplete = hasNoData || isMock || isLowConfidence;

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-800">On-Chain Context</span>
          <span className="text-xs text-slate-400">(30d)</span>
        </div>
        <div className="flex items-center gap-2">
          {isMock && (
            <span className="text-xs px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded">MOCK</span>
          )}
          {isStale && (
            <span className="text-xs px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded">STALE</span>
          )}
          {policyVersion && (
            <span className="text-xs text-slate-400">v{policyVersion}</span>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="p-4">
        {/* Main State Badge - Always Visible */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <span className={`inline-flex px-3 py-1 rounded-full text-sm font-medium ${stateConfig.bg} ${stateConfig.color}`}>
              {stateConfig.label}
            </span>
          </div>
          
          {/* Score - grayed if incomplete */}
          <div className="text-right" title={isDataIncomplete ? 'Derived from mock / incomplete data' : undefined}>
            <div className={`text-2xl font-bold tabular-nums ${isDataIncomplete ? 'text-slate-400' : 'text-slate-800'}`}>
              {scorePercent}
            </div>
            <div className="text-xs text-slate-500">Score</div>
          </div>
        </div>

        {/* Confidence Bar with Badge */}
        <div className="mb-4">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-slate-500">Confidence</span>
            <div className="flex items-center gap-2">
              <span className={`text-xs px-1.5 py-0.5 rounded border ${confidenceBadge.color}`}>
                {confidenceBadge.label}
              </span>
              <span 
                className={`text-xs font-medium tabular-nums ${isDataIncomplete ? 'text-slate-400' : 'text-slate-700'}`}
                title={isDataIncomplete ? 'Derived from mock / incomplete data' : undefined}
              >
                {confidencePercent}%
              </span>
            </div>
          </div>
          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
            <div 
              className={`h-full rounded-full transition-all ${
                confidencePercent < 40 ? 'bg-amber-400' : 
                confidencePercent < 70 ? 'bg-slate-400' : 'bg-emerald-500'
              }`}
              style={{ width: `${confidencePercent}%` }}
            />
          </div>
        </div>

        {/* Drivers - only show if we have some data */}
        {latest.drivers.length > 0 && !hasNoData && (
          <div>
            <div className="text-xs text-slate-500 mb-2">Key Drivers</div>
            <div className="flex flex-wrap gap-1.5">
              {latest.drivers.map((driver, i) => (
                <span 
                  key={i}
                  className="text-xs px-2 py-1 bg-slate-50 text-slate-600 rounded border border-slate-100"
                >
                  {driver}
                </span>
              ))}
            </div>
          </div>
        )}
        
        {/* No Data Message */}
        {hasNoData && (
          <div className="text-center py-2 mt-2 bg-slate-50 rounded-lg">
            <div className="text-xs text-slate-500">Waiting for observations to accumulate</div>
          </div>
        )}
      </div>
    </div>
  );
}
