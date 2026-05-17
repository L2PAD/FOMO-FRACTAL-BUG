/**
 * SentimentMiniEquityChart — BLOCK P2.2
 * ======================================
 * 
 * Mini equity curve showing paper performance
 * Simplified version without chart library
 */

import React, { useEffect, useState } from 'react';
import { TrendingUp, TrendingDown, Activity } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function SentimentMiniEquityChart({ symbol, period = '90d', height = 160 }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch equity data
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);

    fetch(`${API_URL}/api/market/sentiment/equity-v2?symbol=${symbol}&period=${period}`)
      .then(r => r.json())
      .then(res => {
        if (!alive) return;
        if (res.ok) {
          setData(res);
        } else {
          setError(res.error || 'Failed to load equity data');
        }
        setLoading(false);
      })
      .catch(err => {
        if (!alive) return;
        setError(err.message);
        setLoading(false);
      });

    return () => { alive = false; };
  }, [symbol, period]);

  const formatPct = (x) => (x * 100).toFixed(2);
  const formatNum = (x) => x.toFixed(2);

  if (loading) {
    return (
      <div 
        className="bg-white rounded-xl border border-gray-200 p-4"
        style={{ minHeight: height }}
        data-testid="sentiment-equity-loading"
      >
        <div className="text-sm text-gray-500">Loading equity data...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div 
        className="bg-white rounded-xl border border-gray-200 p-4"
        style={{ minHeight: height }}
        data-testid="sentiment-equity-error"
      >
        <div className="text-sm text-gray-500">{error || 'No equity data'}</div>
      </div>
    );
  }

  const { stats, points } = data;
  const isPositive = stats.totalReturn >= 0;

  // Simple SVG sparkline
  const sparklineWidth = 400;
  const sparklineHeight = 80;
  
  // Get min/max for scaling
  const values = points.map(p => p.equity);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const range = maxVal - minVal || 1;

  // Sample points for sparkline (every Nth point)
  const step = Math.max(1, Math.floor(points.length / 100));
  const sampledPoints = points.filter((_, i) => i % step === 0);

  // Generate SVG path
  const pathPoints = sampledPoints.map((p, i) => {
    const x = (i / (sampledPoints.length - 1)) * sparklineWidth;
    const y = sparklineHeight - ((p.equity - minVal) / range) * sparklineHeight;
    return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
  }).join(' ');

  return (
    <div 
      className="bg-white rounded-xl border border-gray-200 overflow-hidden"
      data-testid="sentiment-mini-equity-chart"
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-gray-400" />
          <span className="text-sm font-medium text-gray-700">Paper Performance</span>
          <span className="text-xs text-gray-400">{period}</span>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1">
            <span className="text-gray-500">Return:</span>
            <span className={`font-semibold ${isPositive ? 'text-emerald-600' : 'text-red-600'}`}>
              {isPositive ? '+' : ''}{formatPct(stats.totalReturn)}%
            </span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-gray-500">MaxDD:</span>
            <span className="font-medium text-gray-700">{formatPct(stats.maxDD)}%</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-gray-500">Trades:</span>
            <span className="font-medium text-gray-700">{stats.trades}</span>
          </div>
        </div>
      </div>

      {/* Sparkline Chart */}
      <div className="px-4 py-4" style={{ height: height - 80 }}>
        <svg 
          width="100%" 
          height="100%" 
          viewBox={`0 0 ${sparklineWidth} ${sparklineHeight}`}
          preserveAspectRatio="none"
        >
          {/* Baseline at 1.0 */}
          <line 
            x1="0" 
            y1={sparklineHeight - ((1 - minVal) / range) * sparklineHeight}
            x2={sparklineWidth}
            y2={sparklineHeight - ((1 - minVal) / range) * sparklineHeight}
            stroke="#e5e7eb"
            strokeWidth="1"
            strokeDasharray="4 2"
          />
          {/* Equity line */}
          <path
            d={pathPoints}
            fill="none"
            stroke={isPositive ? '#10b981' : '#ef4444'}
            strokeWidth="2"
          />
          {/* Area under curve */}
          <path
            d={`${pathPoints} L ${sparklineWidth} ${sparklineHeight} L 0 ${sparklineHeight} Z`}
            fill={isPositive ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)'}
          />
        </svg>
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-gray-100 flex items-center justify-between text-xs text-gray-400">
        <span>Simulated paper trading performance</span>
        <span>Sharpe: {formatNum(stats.sharpe)}</span>
      </div>
    </div>
  );
}
