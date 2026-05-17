/**
 * AltFlow Details Drawer
 * =======================
 * 
 * STEP 3: Enhanced with quality/evidence breakdown + light theme
 */

import React, { useState } from 'react';
import { X, Copy, Check, TrendingUp, TrendingDown, Minus, AlertTriangle, Info, Database, BarChart2 } from 'lucide-react';
import type { AltFlowItem, AltFlowFlag } from '../api/altflowApi';

// =====================
// Helpers
// =====================

function formatUsd(n: number | undefined): string {
  if (n === undefined || n === null) return '—';
  const abs = Math.abs(n);
  const sign = n >= 0 ? '+' : '-';
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(1)}K`;
  return `${sign}$${abs.toFixed(0)}`;
}

function getScoreColor(score: number): string {
  if (score >= 70) return 'text-emerald-600';
  if (score >= 50) return 'text-emerald-500';
  if (score >= 30) return 'text-amber-500';
  return 'text-rose-500';
}

function getFlagColor(severity: string): string {
  switch (severity) {
    case 'CRITICAL': return 'bg-red-100 text-red-700';
    case 'WARN': return 'bg-amber-100 text-amber-700';
    default: return 'bg-blue-100 text-blue-700';
  }
}

// =====================
// Drawer Component
// =====================

interface AltFlowDetailsDrawerProps {
  item: AltFlowItem | null;
  onClose: () => void;
}

export function AltFlowDetailsDrawer({ item, onClose }: AltFlowDetailsDrawerProps) {
  const [copied, setCopied] = useState(false);

  if (!item) return null;

  const handleCopyJson = async () => {
    const json = JSON.stringify(item, null, 2);
    await navigator.clipboard.writeText(json);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const scoreColor = getScoreColor(item.score);
  const confidence = item.confidence ?? 0;
  
  const SideIcon = item.side === 'ACCUMULATION' ? TrendingUp 
    : item.side === 'DISTRIBUTION' ? TrendingDown 
    : Minus;
  
  const sideBg = item.side === 'ACCUMULATION' ? 'bg-emerald-100 text-emerald-700'
    : item.side === 'DISTRIBUTION' ? 'bg-rose-100 text-rose-700'
    : 'bg-gray-100 text-gray-700';

  // Parse flags
  const flags = (item.flags || []).map(f => 
    typeof f === 'string' ? { code: f, severity: 'INFO' as const } : f
  );

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/30 z-40"
        onClick={onClose}
      />
      
      {/* Drawer */}
      <div 
        className="fixed right-0 top-0 h-full w-[440px] bg-white z-50 overflow-y-auto"
        data-testid="altflow-details-drawer"
      >
        {/* Header */}
        <div className="sticky top-0 bg-white p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xl font-bold text-gray-900">{item.symbol}</span>
            <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${sideBg}`}>
              <SideIcon className="w-3 h-3" />
              {item.side}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
            data-testid="drawer-close-btn"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>
        
        <div className="p-4 space-y-5">
          {/* Score & Confidence */}
          <div className="rounded-xl bg-gray-50 p-4">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Signal Score</div>
                <div className={`text-4xl font-bold tabular-nums ${scoreColor}`}>
                  {item.score?.toFixed(0) ?? '—'}
                </div>
              </div>
              <div className="text-right">
                <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Confidence</div>
                <div className={`text-2xl font-bold tabular-nums ${confidence >= 0.7 ? 'text-gray-900' : confidence >= 0.55 ? 'text-gray-600' : 'text-gray-400'}`}>
                  {Math.round(confidence * 100)}%
                </div>
              </div>
            </div>
            
            {/* Confidence bar */}
            <div className="mt-3">
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div 
                  className={`h-full rounded-full ${confidence >= 0.7 ? 'bg-emerald-500' : confidence >= 0.55 ? 'bg-blue-500' : 'bg-gray-400'}`}
                  style={{ width: `${confidence * 100}%` }}
                />
              </div>
            </div>
          </div>

          {/* STEP 3: Quality Section */}
          {item.quality && (
            <div className="rounded-xl p-4">
              <div className="flex items-center gap-2 text-xs text-gray-500 uppercase tracking-wider mb-3">
                <Database className="w-4 h-4" />
                Data Quality
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <div className="text-gray-500">Price Source</div>
                  <div className={`font-medium ${
                    item.quality.priceSource === 'CHAINLINK' ? 'text-emerald-600' :
                    item.quality.priceSource === 'TWAP' ? 'text-blue-600' :
                    item.quality.priceSource === 'DEX_VWAP' ? 'text-amber-600' :
                    'text-gray-400'
                  }`}>
                    {item.quality.priceSource}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">Pool Status</div>
                  <div className={`font-medium ${
                    item.quality.poolStatus === 'ACTIVE' ? 'text-emerald-600' :
                    item.quality.poolStatus === 'DEGRADED' ? 'text-amber-600' :
                    'text-gray-400'
                  }`}>
                    {item.quality.poolStatus}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">Pool Score</div>
                  <div className="font-medium text-gray-900">{item.quality.poolScore}</div>
                </div>
                {item.quality.priceConfidence != null && (
                  <div>
                    <div className="text-gray-500">Price Conf</div>
                    <div className="font-medium text-gray-900">{Math.round(item.quality.priceConfidence * 100)}%</div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* STEP 3: Evidence Section */}
          {item.evidence && (
            <div className="rounded-xl p-4">
              <div className="flex items-center gap-2 text-xs text-gray-500 uppercase tracking-wider mb-3">
                <BarChart2 className="w-4 h-4" />
                Evidence
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <div className="text-gray-500">Trades</div>
                  <div className="font-medium text-gray-900">{item.evidence.trades}</div>
                </div>
                <div>
                  <div className="text-gray-500">Unique Pools</div>
                  <div className="font-medium text-gray-900">{item.evidence.uniquePools}</div>
                </div>
                <div>
                  <div className="text-gray-500">Time Span</div>
                  <div className="font-medium text-gray-900">{item.evidence.spanHours.toFixed(1)}h</div>
                </div>
                <div>
                  <div className="text-gray-500">Priced Share</div>
                  <div className="font-medium text-gray-900">{Math.round(item.evidence.pricedShare * 100)}%</div>
                </div>
              </div>
            </div>
          )}
          
          {/* Flow Components */}
          <div className="rounded-xl p-4">
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-3">Flow Components</div>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">DEX Net</span>
                <span className={`font-mono font-medium ${(item.components?.dexNetUsd ?? 0) > 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                  {formatUsd(item.components?.dexNetUsd)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">CEX Net</span>
                <span className={`font-mono font-medium ${(item.components?.cexNetUsd ?? 0) < 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                  {formatUsd(item.components?.cexNetUsd)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Whale</span>
                <span className="font-mono font-medium text-purple-600">
                  {formatUsd(item.components?.whaleUsd)}
                </span>
              </div>
            </div>
          </div>
          
          {/* Drivers */}
          {item.drivers && item.drivers.length > 0 && (
            <div className="rounded-xl p-4">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-3">Drivers</div>
              <ul className="space-y-2">
                {item.drivers.map((d, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                    <span className="text-blue-500 mt-0.5">•</span>
                    {d}
                  </li>
                ))}
              </ul>
            </div>
          )}
          
          {/* Flags */}
          {flags.length > 0 && (
            <div className="rounded-xl bg-amber-50 p-4">
              <div className="flex items-center gap-2 text-xs text-amber-700 uppercase tracking-wider mb-3">
                <AlertTriangle className="w-4 h-4" />
                Flags ({flags.length})
              </div>
              <div className="flex flex-wrap gap-2">
                {flags.map((f, i) => (
                  <span 
                    key={i} 
                    className={`px-2 py-1 rounded text-xs font-medium ${getFlagColor(f.severity)}`}
                    title={f.detail || undefined}
                  >
                    {f.code.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            </div>
          )}
          
          {/* Address */}
          {item.address && (
            <div className="rounded-xl p-4">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Contract Address</div>
              <code className="text-xs text-gray-600 break-all font-mono">{item.address}</code>
            </div>
          )}
          
          {/* Copy JSON */}
          <button
            onClick={handleCopyJson}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-gray-50 hover:bg-gray-100 text-gray-700 transition-colors"
            data-testid="copy-json-btn"
          >
            {copied ? (
              <>
                <Check className="w-4 h-4 text-emerald-600" />
                <span className="text-emerald-600 font-medium">Copied!</span>
              </>
            ) : (
              <>
                <Copy className="w-4 h-4" />
                <span>Copy JSON</span>
              </>
            )}
          </button>
        </div>
      </div>
    </>
  );
}
