/**
 * Alt Liquidity Panel
 * ====================
 * 
 * PHASE 3 + BLOCK 3.6: Main container for Alt Liquidity Signal
 */

import React, { useState } from 'react';
import { Loader2, RefreshCw, AlertCircle } from 'lucide-react';
import { useAltLiquidity } from './useAltLiquidity';
import { useAltFlow } from './useAltFlow';
import { AltLiquidityCard } from './AltLiquidityCard';
import { AltLiquidityChart } from './AltLiquidityChart';
import { AltLiquidityDrivers } from './AltLiquidityDrivers';
import { AltLiquidityFlags } from './AltLiquidityFlags';
import { AltLiquidityInputs } from './AltLiquidityInputs';
import { AltFlowTable } from './AltFlowTable';

export function AltLiquidityPanel() {
  const { loading, error, latest, series, refresh } = useAltLiquidity({ window: '30d' });
  const [flowWindow, setFlowWindow] = useState<'24h' | '7d'>('24h');
  const altFlow = useAltFlow(flowWindow);

  // Loading state
  if (loading && !latest) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
        <span className="ml-3 text-gray-400">Loading liquidity data...</span>
      </div>
    );
  }

  // Error state
  if (error && !latest) {
    return (
      <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-6">
        <div className="flex items-center gap-3 text-red-400">
          <AlertCircle className="w-6 h-6" />
          <div>
            <div className="font-medium">Failed to load liquidity data</div>
            <div className="text-sm text-red-400/80 mt-1">{error}</div>
          </div>
        </div>
        <button 
          onClick={refresh}
          className="mt-4 flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-400 text-sm transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Retry
        </button>
      </div>
    );
  }

  if (!latest) {
    return (
      <div className="text-center py-12 text-gray-500">
        No liquidity data available
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="alt-liquidity-panel">
      {/* Header with refresh */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-200">Alt Liquidity Signal</h2>
        <button 
          onClick={refresh}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 text-sm transition-colors disabled:opacity-50"
          data-testid="refresh-button"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Hero Card */}
      <AltLiquidityCard latest={latest} />

      {/* Chart */}
      {series?.series && series.series.length > 0 && (
        <AltLiquidityChart points={series.series} />
      )}

      {/* Two column layout for details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Drivers */}
        <AltLiquidityDrivers drivers={latest.drivers} />

        {/* Inputs */}
        <AltLiquidityInputs inputs={latest.inputs} />
      </div>

      {/* Flags (only if present) */}
      {latest.flags && latest.flags.length > 0 && (
        <AltLiquidityFlags flags={latest.flags} />
      )}

      {/* Alt Flow Activity Section */}
      <div className="mt-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-gray-200">Alt Flow Activity</h3>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setFlowWindow('24h')}
              className={`px-3 py-1 rounded-lg text-sm transition-colors ${
                flowWindow === '24h' 
                  ? 'bg-blue-500/20 text-blue-400 border border-blue-500/40' 
                  : 'bg-white/5 text-gray-400 hover:bg-white/10'
              }`}
            >
              24h
            </button>
            <button
              onClick={() => setFlowWindow('7d')}
              className={`px-3 py-1 rounded-lg text-sm transition-colors ${
                flowWindow === '7d' 
                  ? 'bg-blue-500/20 text-blue-400 border border-blue-500/40' 
                  : 'bg-white/5 text-gray-400 hover:bg-white/10'
              }`}
            >
              7d
            </button>
            <button
              onClick={() => altFlow.refresh(true)}
              disabled={altFlow.loading}
              className="ml-2 p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 transition-colors disabled:opacity-50"
              title="Refresh alt flow"
            >
              <RefreshCw className={`w-4 h-4 ${altFlow.loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {altFlow.loading && !altFlow.data ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 text-blue-400 animate-spin" />
            <span className="ml-2 text-gray-400">Loading alt flow...</span>
          </div>
        ) : altFlow.error && !altFlow.data ? (
          <div className="text-center py-8 text-red-400">
            {altFlow.error}
          </div>
        ) : altFlow.data ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <AltFlowTable 
              title="Strong Accumulation" 
              rows={altFlow.data.topAccumulation} 
              type="accumulation"
            />
            <AltFlowTable 
              title="Strong Distribution" 
              rows={altFlow.data.topDistribution} 
              type="distribution"
            />
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            No alt flow data available
          </div>
        )}

        {altFlow.data && (
          <div className="mt-2 text-xs text-gray-600 text-right">
            {altFlow.data.totalTokens} tokens analyzed • Updated {new Date(altFlow.data.generatedAt).toLocaleTimeString()}
          </div>
        )}
      </div>

      {/* Timestamp */}
      <div className="text-xs text-gray-600 text-right">
        Last updated: {new Date(latest.t).toLocaleString()}
      </div>
    </div>
  );
}
