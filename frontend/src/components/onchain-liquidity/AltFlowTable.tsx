/**
 * Alt Flow Table
 * ===============
 * 
 * PHASE 4: Alt token flow ranking display
 * - Если нет данных — не рендерить (без placeholder)
 * - Компактный, без лишнего текста
 */

import React from 'react';
import { TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight } from 'lucide-react';

export interface AltFlowRow {
  symbol: string;
  score: number;
  confidence: number;
  drivers: string[];
  flags: string[];
  cexNetUsd: number;
  dexNetUsd: number;
  whaleUsd: number;
}

interface Props {
  title: string;
  rows: AltFlowRow[];
  type: 'accumulation' | 'distribution';
}

function formatUsd(x: number): string {
  const abs = Math.abs(x || 0);
  const sign = x >= 0 ? '+' : '-';
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(0)}K`;
  return `${sign}$${abs.toFixed(0)}`;
}

function ScoreBadge({ score, type }: { score: number; type: 'accumulation' | 'distribution' }) {
  const pct = Math.round(score * 100);
  const isPositive = type === 'accumulation';
  const bgColor = isPositive ? 'bg-green-500/20' : 'bg-red-500/20';
  const textColor = isPositive ? 'text-green-400' : 'text-red-400';
  const Icon = isPositive ? TrendingUp : TrendingDown;

  return (
    <div className={`flex items-center gap-1 px-2 py-0.5 rounded ${bgColor} ${textColor} text-xs font-medium`}>
      <Icon className="w-3 h-3" />
      <span>{pct > 0 ? '+' : ''}{pct}</span>
    </div>
  );
}

export function AltFlowTable({ title, rows, type }: Props) {
  // Нет данных — не рендерим (без placeholder)
  if (!rows || rows.length === 0) return null;

  const Icon = type === 'accumulation' ? ArrowUpRight : ArrowDownRight;
  const iconColor = type === 'accumulation' ? 'text-green-400' : 'text-red-400';

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4" data-testid={`altflow-${type}`}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <Icon className={`w-4 h-4 ${iconColor}`} />
        <span className="text-sm font-medium text-gray-200">{title}</span>
      </div>

      {/* Rows */}
      <div className="space-y-1.5">
        {rows.map((row, i) => (
          <div 
            key={row.symbol}
            className="flex items-center justify-between rounded-lg bg-white/[0.03] px-3 py-2 hover:bg-white/[0.06] transition-colors"
          >
            {/* Left: Symbol + Flow */}
            <div className="flex items-center gap-3">
              <span className="w-4 text-xs text-gray-500 font-medium">{i + 1}</span>
              <span className="w-14 text-sm font-semibold text-gray-100">{row.symbol}</span>
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <span>DEX {formatUsd(row.dexNetUsd)}</span>
                <span>CEX {formatUsd(row.cexNetUsd)}</span>
              </div>
            </div>

            {/* Right: Score */}
            <ScoreBadge score={row.score} type={type} />
          </div>
        ))}
      </div>
    </div>
  );
}
