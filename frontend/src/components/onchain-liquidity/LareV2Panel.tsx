/**
 * LARE v2 Panel
 * ==============
 * 
 * BLOCK 8 UI Discipline: Main OnChain tab layout
 * 
 * PHASE 1: UI Cleanup — NO version, NO points, NO debug text
 * PHASE 2: Strong Header hierarchy
 */

import React, { useState } from 'react';
import { Loader2, RefreshCw, AlertCircle, Activity } from 'lucide-react';
import { useLareV2 } from './useLareV2';
import { useAltFlow } from './useAltFlow';
import { LareV2Header } from './LareV2Header';
import { LareV2DataFlag } from './LareV2DataFlag';
import { LareV2Drivers } from './LareV2Drivers';
import { LareV2Chart } from './LareV2Chart';
import { LareV2Components } from './LareV2Components';
import { AltFlowTable } from './AltFlowTable';

export function LareV2Panel() {
  const [historyRange, setHistoryRange] = useState<'1d' | '7d' | '30d'>('30d');
  const { loading, error, latest, series, refresh } = useLareV2('24h'); // snapshot always 24h
  const [flowWindow, setFlowWindow] = useState<'24h' | '7d'>('24h');
  const altFlow = useAltFlow(flowWindow);

  // Loading state — clean, без dev текста
  if (loading && !latest) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="w-6 h-6 text-blue-400 animate-spin" />
      </div>
    );
  }

  // Error state — компактный
  if (error && !latest) {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-5">
        <div className="flex items-center gap-3 text-red-400">
          <AlertCircle className="w-5 h-5" />
          <span className="font-medium">Connection Error</span>
        </div>
        <button 
          onClick={refresh}
          className="mt-3 flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-gray-300 text-sm transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Retry
        </button>
      </div>
    );
  }

  // Нет данных — блок не рендерится (без placeholder)
  if (!latest) {
    return null;
  }

  return (
    <div className="space-y-5" data-testid="lare-v2-panel">
      {/* Header: Liquidity Context — активный, не серый */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Activity className="w-5 h-5 text-blue-400" />
          <h2 className="text-lg font-semibold text-gray-100">Liquidity Context</h2>
        </div>
        <button 
          onClick={refresh}
          disabled={loading}
          className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 transition-colors disabled:opacity-50"
          data-testid="refresh-button"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* 1. Header Cards — главный визуальный блок */}
      <LareV2Header data={latest} />

      {/* 2. Guardrail — компактный alert под header */}
      <LareV2DataFlag flags={latest.flags} confidence={latest.confidence} />

      {/* 3. Why this regime? — drivers */}
      <LareV2Drivers regime={latest.regime} drivers={latest.drivers} />

      {/* 4. Score History с таймфреймами */}
      {series.length > 1 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium text-gray-300">Score History</span>
            <div className="flex items-center gap-1 bg-white/5 rounded-lg p-0.5">
              {(['1d', '7d', '30d'] as const).map(range => (
                <button
                  key={range}
                  onClick={() => setHistoryRange(range)}
                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                    historyRange === range 
                      ? 'bg-blue-500/20 text-blue-400' 
                      : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  {range.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <LareV2Chart series={series} range={historyRange} />
        </div>
      )}

      {/* 5. Signal Breakdown — 4 карточки */}
      {latest.components && latest.components.length > 0 && (
        <div>
          <div className="text-sm font-medium text-gray-300 mb-3">Signal Breakdown</div>
          <LareV2Components components={latest.components} />
        </div>
      )}

      {/* 6. Alt Flow — только если есть данные */}
      {altFlow.data && altFlow.data.totalTokens > 0 && (
        <div className="pt-4 border-t border-white/5">
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm font-medium text-gray-300">Alt Flow Activity</span>
            <div className="flex items-center gap-2">
              {(['24h', '7d'] as const).map(w => (
                <button
                  key={w}
                  onClick={() => setFlowWindow(w)}
                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                    flowWindow === w 
                      ? 'bg-blue-500/20 text-blue-400' 
                      : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  {w.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <AltFlowTable 
              title="Accumulation" 
              rows={altFlow.data.topAccumulation} 
              type="accumulation"
            />
            <AltFlowTable 
              title="Distribution" 
              rows={altFlow.data.topDistribution} 
              type="distribution"
            />
          </div>
        </div>
      )}
    </div>
  );
}
