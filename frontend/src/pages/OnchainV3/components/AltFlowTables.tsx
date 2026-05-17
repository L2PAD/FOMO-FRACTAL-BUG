/**
 * AltFlow Tables — On-chain v3
 * =============================
 * 
 * STEP 3: Confidence-based dimming + light theme
 */

import React from 'react';
import { ArrowUpRight, ArrowDownRight, AlertTriangle, Info } from 'lucide-react';
import type { AltFlowItem, AltFlowFlag } from '../api/altflowApi';

// =====================
// Helpers
// =====================

function formatUsd(val: number | undefined): string {
  if (val === undefined || val === null) return '—';
  const abs = Math.abs(val);
  if (abs >= 1_000_000) return `$${(val / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `$${(val / 1_000).toFixed(0)}K`;
  return `$${val.toFixed(0)}`;
}

function formatPercent(val: number | undefined): string {
  if (val === undefined || val === null) return '—';
  return `${Math.round(val * 100)}%`;
}

// STEP 3: Confidence-based row styling
function getConfidenceTone(conf: number, threshold: number): 'normal' | 'soft' | 'dim' {
  if (conf >= 0.7) return 'normal';
  if (conf >= threshold) return 'soft';
  return 'dim';
}

function getRowClasses(conf: number, threshold: number): string {
  const tone = getConfidenceTone(conf, threshold);
  switch (tone) {
    case 'normal':
      return 'bg-white hover:bg-gray-50';
    case 'soft':
      return 'bg-white hover:bg-gray-50 opacity-90';
    case 'dim':
      return 'bg-gray-50/50 hover:bg-gray-50 opacity-75';
    default:
      return 'bg-white hover:bg-gray-50';
  }
}

// Get flag icon/color
function getFlagDisplay(flags: (string | AltFlowFlag)[]): { hasWarning: boolean; hasInfo: boolean } {
  let hasWarning = false;
  let hasInfo = false;
  
  for (const f of flags) {
    const severity = typeof f === 'string' ? 'INFO' : f.severity;
    if (severity === 'WARN' || severity === 'CRITICAL') hasWarning = true;
    else hasInfo = true;
  }
  
  return { hasWarning, hasInfo };
}

// =====================
// Table Component
// =====================

interface AltFlowTableProps {
  title: string;
  type: 'accumulation' | 'distribution';
  items: AltFlowItem[];
  onItemClick: (item: AltFlowItem) => void;
  confThreshold?: number;
}

export function AltFlowTable({ title, type, items, onItemClick, confThreshold = 0.55 }: AltFlowTableProps) {
  const isAccum = type === 'accumulation';
  const Icon = isAccum ? ArrowUpRight : ArrowDownRight;
  const accentColor = isAccum ? 'text-emerald-600' : 'text-rose-600';
  const bgAccent = isAccum ? 'bg-emerald-50' : 'bg-rose-50';

  return (
    <div className={`rounded-xl ${bgAccent} overflow-hidden`} data-testid={`altflow-table-${type}`}>
      {/* Header */}
      <div className="px-5 py-3">
        <div className="flex items-center gap-2">
          <Icon className={`w-5 h-5 ${accentColor}`} />
          <h3 className={`font-semibold ${accentColor}`}>{title}</h3>
          <span className="text-sm text-gray-500 ml-auto">
            {items.length} {items.length === 1 ? 'token' : 'tokens'}
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white">
        {items.length === 0 ? (
          <div className="px-5 py-8 text-center text-gray-500 text-sm">
            No {type} signals
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-gray-500 text-left">
                <th className="px-4 py-3 font-medium">Token</th>
                <th className="px-4 py-3 font-medium text-right">Score</th>
                <th className="px-4 py-3 font-medium text-right">Conf</th>
                <th className="px-4 py-3 font-medium text-right">Net Flow</th>
                <th className="px-4 py-3 font-medium text-center w-10"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, idx) => {
                const conf = item.confidence ?? 0;
                const rowClasses = getRowClasses(conf, confThreshold);
                const { hasWarning, hasInfo } = getFlagDisplay(item.flags || []);
                const isLowConf = conf < confThreshold;
                
                return (
                  <tr
                    key={item.address || item.symbol || idx}
                    className={`border-b cursor-pointer transition-colors ${rowClasses}`}
                    onClick={() => onItemClick(item)}
                    data-testid={`altflow-row-${item.symbol}`}
                  >
                    {/* Token */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-gray-900">
                          {item.symbol || 'UNKNOWN'}
                        </span>
                        {isLowConf && (
                          <span className="px-1.5 py-0.5 text-xs rounded bg-gray-200 text-gray-600">
                            Low conf
                          </span>
                        )}
                      </div>
                    </td>
                    
                    {/* Score */}
                    <td className="px-4 py-3 text-right">
                      <span className={`font-mono font-medium ${accentColor}`}>
                        {item.score?.toFixed(0) ?? '—'}
                      </span>
                    </td>
                    
                    {/* Confidence */}
                    <td className="px-4 py-3 text-right">
                      <span className={`font-mono ${conf >= 0.7 ? 'text-gray-900' : conf >= confThreshold ? 'text-gray-600' : 'text-gray-400'}`}>
                        {formatPercent(conf)}
                      </span>
                    </td>
                    
                    {/* Net Flow */}
                    <td className="px-4 py-3 text-right">
                      <span className="font-mono text-gray-700">
                        {formatUsd(item.components?.dexNetUsd)}
                      </span>
                    </td>
                    
                    {/* Flags indicator */}
                    <td className="px-4 py-3 text-center">
                      {hasWarning && <AlertTriangle className="w-4 h-4 text-amber-500 inline" />}
                      {!hasWarning && hasInfo && <Info className="w-4 h-4 text-blue-400 inline" />}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
