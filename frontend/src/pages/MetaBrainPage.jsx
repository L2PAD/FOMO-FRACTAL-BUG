/**
 * MetaBrainPage — Central Intelligence Page
 *
 * Layout:
 * - Sticky header with title + horizon + refresh
 * - Hero chart (65vh) — rolling forecast curve from real snapshots
 * - Below: Full-width Forecast Table (like Exchange prediction)
 *
 * Cards (Verdict/Position/Signals/Context) removed per user request.
 */
import React, { useState } from 'react';
import { RefreshCw } from 'lucide-react';
import MetaBrainChart from '../modules/meta-brain-ui/MetaBrainChart';
import MetaBrainForecastTable from '../modules/meta-brain-ui/MetaBrainForecastTable';

const HORIZONS = [1, 7, 30];

export default function MetaBrainPage() {
  const [horizon, setHorizon] = useState(7);
  const [refreshKey, setRefreshKey] = useState(0);
  const [loading, setLoading] = useState(false);

  return (
    <div className="min-h-screen bg-gray-50" data-testid="meta-brain-page">
      {/* STICKY HEADER */}
      <div className="sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-gray-100">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900" data-testid="meta-brain-title">Meta Brain</h1>
              <p className="text-sm text-gray-500">AI ensemble forecast — BTC</p>
            </div>

            <div className="flex items-center gap-4">
              {/* Horizon Selector */}
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-500">Horizon:</span>
                <div className="flex bg-white border border-gray-200 rounded-lg p-1">
                  {HORIZONS.map(h => (
                    <button
                      key={h}
                      onClick={() => setHorizon(h)}
                      data-testid={`horizon-${h}d`}
                      className={`px-3 py-1.5 text-sm font-medium rounded transition-colors ${
                        horizon === h
                          ? 'bg-emerald-500 text-white'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      {h}d
                    </button>
                  ))}
                </div>
              </div>

              {/* Refresh */}
              <button
                onClick={() => setRefreshKey(k => k + 1)}
                className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
                data-testid="refresh-btn"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* MAIN CONTENT */}
      <div className="max-w-6xl mx-auto px-6 py-6">

        {/* 1. BIG CHART */}
        <div className="mb-6">
          <MetaBrainChart
            key={refreshKey}
            asset="BTC"
            horizonDays={horizon}
          />
        </div>

        {/* 2. FORECAST TABLE — full width */}
        <MetaBrainForecastTable
          key={`table-${horizon}-${refreshKey}`}
          asset="BTC"
          horizonDays={horizon}
        />
      </div>
    </div>
  );
}
