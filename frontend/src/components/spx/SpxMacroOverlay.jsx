/**
 * SPX MACRO OVERLAY CHART
 * 
 * Displays:
 * - Primary: Macro-Adjusted Hybrid (thick solid line)
 * - Secondary: Base Hybrid (dotted)
 * - Secondary: DXY Macro Influence (dotted, different color)
 * 
 * With legend showing all three sources
 */

import React, { useEffect, useState, useMemo } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
} from 'recharts';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

// ═══════════════════════════════════════════════════════════════
// HOOK
// ═══════════════════════════════════════════════════════════════

export function useSpxMacroOverlay(horizon) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    fetch(`${API_BASE}/api/spx/macro-overlay?horizon=${horizon}`)
      .then(res => res.json())
      .then(json => {
        if (json.ok) {
          setData(json);
        } else {
          setError(json.error || 'Failed to fetch macro overlay');
        }
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [horizon]);

  return { data, loading, error };
}

// ═══════════════════════════════════════════════════════════════
// MACRO INFO PANEL
// ═══════════════════════════════════════════════════════════════

export function SpxMacroInfoPanel({ meta }) {
  if (!meta) return null;

  return (
    <div className="bg-white rounded-xl p-6 mb-6" data-testid="spx-macro-info">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Macro Impact</h3>
      
      <div className="grid grid-cols-4 gap-4 mb-4">
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Base Hybrid</p>
          <p className={`text-xl font-bold ${meta.spxBaseP50 > 0 ? 'text-emerald-600' : meta.spxBaseP50 < 0 ? 'text-red-500' : 'text-gray-500'}`}>
            {meta.spxBaseP50 > 0 ? '+' : ''}{meta.spxBaseP50.toFixed(2)}%
          </p>
        </div>
        
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Macro Adjustment</p>
          <p className={`text-xl font-bold ${meta.adjustmentP50 > 0 ? 'text-emerald-600' : meta.adjustmentP50 < 0 ? 'text-red-500' : 'text-gray-500'}`}>
            {meta.adjustmentP50 > 0 ? '+' : ''}{meta.adjustmentP50.toFixed(2)}%
          </p>
        </div>
        
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Adjusted Total</p>
          <p className={`text-xl font-bold ${meta.adjustedP50 > 0 ? 'text-emerald-600' : meta.adjustedP50 < 0 ? 'text-red-500' : 'text-gray-500'}`}>
            {meta.adjustedP50 > 0 ? '+' : ''}{meta.adjustedP50.toFixed(2)}%
          </p>
        </div>
        
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Overlay Strength</p>
          <p className="text-xl font-bold text-gray-900">
            {(meta.overlayWeight * 100).toFixed(0)}%
          </p>
        </div>
      </div>
      
      <div className="grid grid-cols-3 gap-4 pt-4 border-t border-gray-100">
        <div>
          <p className="text-xs text-gray-400">DXY Expected</p>
          <p className={`font-medium ${meta.dxyDeltaP50 > 0 ? 'text-emerald-600' : meta.dxyDeltaP50 < 0 ? 'text-red-500' : 'text-gray-500'}`}>
            {meta.dxyDeltaP50 > 0 ? '+' : ''}{meta.dxyDeltaP50.toFixed(2)}%
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-400">Correlation</p>
          <p className="font-medium text-gray-700">{meta.corr.toFixed(2)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400">Beta (SPX/DXY)</p>
          <p className="font-medium text-gray-700">{meta.beta.toFixed(2)}</p>
        </div>
      </div>
      
      {!meta.overlayActive && (
        <div className="mt-4 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg">
          <p className="text-sm text-amber-700">
            <span className="font-medium">Macro overlay inactive:</span>{' '}
            {meta.reasonCodes.join(', ') || 'Insufficient signal strength'}
          </p>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// CHART COMPONENT
// ═══════════════════════════════════════════════════════════════

export function SpxMacroOverlayChart({ data }) {
  // Combine all series into unified chart data
  const chartData = useMemo(() => {
    if (!data) return [];
    
    const adjustedSeries = data.adjusted?.series || [];
    const baseSeries = data.baseHybrid?.series || [];
    const dxySeries = data.dxyMacro?.series || [];
    
    // Normalize DXY to SPX scale (for visual comparison)
    const baseStart = baseSeries[0]?.y || 100;
    const dxyStart = dxySeries[0]?.y || 100;
    
    const maxLen = Math.max(adjustedSeries.length, baseSeries.length, dxySeries.length);
    const result = [];
    
    for (let i = 0; i < maxLen; i++) {
      const adjusted = adjustedSeries[i];
      const base = baseSeries[i];
      const dxy = dxySeries[i];
      
      result.push({
        t: adjusted?.t || base?.t || dxy?.t || i,
        adjusted: adjusted?.y,
        base: base?.y,
        dxyNormalized: dxy ? baseStart * (dxy.y / dxyStart) : undefined,
      });
    }
    
    return result;
  }, [data]);

  if (!data || chartData.length === 0) {
    return (
      <div className="bg-white rounded-xl p-6 h-64 flex items-center justify-center">
        <p className="text-gray-400">No chart data available</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl p-6" data-testid="spx-macro-chart">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">
          Macro-Adjusted Projection
        </h3>
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1">
            <div className="w-4 h-0.5 bg-emerald-500" />
            <span className="text-gray-600">Adjusted</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-4 h-0.5 bg-blue-400 opacity-50" style={{ borderStyle: 'dashed' }} />
            <span className="text-gray-600">Base Hybrid</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-4 h-0.5 bg-amber-500 opacity-50" style={{ borderStyle: 'dashed' }} />
            <span className="text-gray-600">DXY Influence</span>
          </div>
        </div>
      </div>
      
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <XAxis 
            dataKey="t" 
            tick={{ fontSize: 10, fill: '#9CA3AF' }}
            tickFormatter={(val) => {
              if (typeof val === 'number' && val > 1000000000) {
                return new Date(val).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
              }
              return `D${val}`;
            }}
          />
          <YAxis 
            tick={{ fontSize: 10, fill: '#9CA3AF' }}
            domain={['auto', 'auto']}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              return (
                <div className="bg-gray-900 text-white text-xs p-2 rounded shadow-lg">
                  {payload.map((entry, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <span style={{ color: entry.color }}>{entry.name}:</span>
                      <span>{typeof entry.value === 'number' ? entry.value.toFixed(2) : 'N/A'}</span>
                    </div>
                  ))}
                </div>
              );
            }}
          />
          
          {/* DXY Influence (dotted, amber) */}
          <Line
            type="monotone"
            dataKey="dxyNormalized"
            name="DXY Influence"
            stroke="#F59E0B"
            strokeWidth={1.5}
            strokeDasharray="4 4"
            dot={false}
            opacity={0.6}
          />
          
          {/* Base Hybrid (dotted, blue) */}
          <Line
            type="monotone"
            dataKey="base"
            name="Base Hybrid"
            stroke="#60A5FA"
            strokeWidth={1.5}
            strokeDasharray="4 4"
            dot={false}
            opacity={0.6}
          />
          
          {/* Adjusted (solid, primary, thick) */}
          <Line
            type="monotone"
            dataKey="adjusted"
            name="Macro Adjusted"
            stroke="#10B981"
            strokeWidth={2.5}
            dot={false}
          />
          
          {/* Reference line at current price */}
          <ReferenceLine y={chartData[0]?.adjusted || 100} stroke="#E5E7EB" strokeDasharray="3 3" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// FULL MACRO VIEW
// ═══════════════════════════════════════════════════════════════

export function SpxMacroView({ horizon }) {
  const { data, loading, error } = useSpxMacroOverlay(horizon);

  if (loading) {
    return (
      <div className="animate-pulse">
        <div className="bg-gray-200 rounded-xl h-48 mb-6" />
        <div className="bg-gray-200 rounded-xl h-80" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-6">
        <p className="text-red-700">Failed to load macro overlay: {error}</p>
      </div>
    );
  }

  return (
    <div data-testid="spx-macro-view">
      <SpxMacroInfoPanel meta={data.meta} />
      <SpxMacroOverlayChart data={data} />
    </div>
  );
}

export default SpxMacroView;
