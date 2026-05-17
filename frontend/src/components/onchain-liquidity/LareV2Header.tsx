/**
 * LARE v2 Header
 * ===============
 * 
 * BLOCK 8: 4-card header layout
 * Score | Regime | Confidence | Risk Cap
 */

import React from 'react';
import { TrendingUp, TrendingDown, Minus, Lock } from 'lucide-react';
import type { LareV2Data } from './useLareV2';

interface Props {
  data: LareV2Data;
}

// Regime colors — контрастные, НЕ серые
const REGIME_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  'RISK_ON_ALTS': { color: '#4ade80', bg: '#22c55e25', label: 'Risk On Alts' },
  'MODERATE_RISK_ON': { color: '#a3e635', bg: '#84cc1625', label: 'Moderate Risk On' },
  'NEUTRAL': { color: '#60a5fa', bg: '#3b82f625', label: 'Neutral' },
  'MODERATE_RISK_OFF': { color: '#fb923c', bg: '#f9731625', label: 'Moderate Risk Off' },
  'RISK_OFF': { color: '#f87171', bg: '#ef444425', label: 'Risk Off' },
};

export function LareV2Header({ data }: Props) {
  const score = Math.round(data.score);
  const confPct = Math.round(data.confidence * 100);
  const riskCapPct = Math.round(data.gate.riskCap * 100);
  const regimeConfig = REGIME_CONFIG[data.regime] || REGIME_CONFIG['NEUTRAL'];

  // Score color based on value
  const scoreColor = score >= 65 ? '#22c55e' : 
                     score >= 55 ? '#84cc16' : 
                     score >= 45 ? '#eab308' : 
                     score >= 35 ? '#f97316' : '#ef4444';

  // Confidence bar color
  const confColor = confPct >= 50 ? '#22c55e' : confPct >= 30 ? '#eab308' : '#ef4444';

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4" data-testid="lare-v2-header">
      {/* Card 1: Score — главный визуальный якорь */}
      <div className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
        <div className="text-xs text-gray-400 uppercase tracking-wider mb-3 font-medium">Liquidity Score</div>
        <div 
          className="text-5xl font-bold tabular-nums leading-none"
          style={{ color: scoreColor }}
          data-testid="lare-score"
        >
          {score}
        </div>
      </div>

      {/* Card 2: Regime — контрастный badge */}
      <div className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
        <div className="text-xs text-gray-400 uppercase tracking-wider mb-3 font-medium">Regime</div>
        <div 
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold"
          style={{ 
            backgroundColor: regimeConfig.bg,
            color: regimeConfig.color,
            border: `1px solid ${regimeConfig.color}50`,
          }}
          data-testid="lare-regime"
        >
          {score >= 50 ? <TrendingUp className="w-4 h-4" /> : 
           score < 45 ? <TrendingDown className="w-4 h-4" /> : 
           <Minus className="w-4 h-4" />}
          {regimeConfig.label}
        </div>
      </div>

      {/* Card 3: Confidence — толстый bar */}
      <div className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
        <div className="text-xs text-gray-400 uppercase tracking-wider mb-3 font-medium">Confidence</div>
        <div className="flex items-center gap-4">
          <div className="flex-1 h-3 bg-white/10 rounded-full overflow-hidden">
            <div 
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${confPct}%`, backgroundColor: confColor }}
            />
          </div>
          <span 
            className="text-xl font-bold tabular-nums"
            style={{ color: confColor }}
            data-testid="lare-confidence"
          >
            {confPct}%
          </span>
        </div>
      </div>

      {/* Card 4: Risk Cap — заметный badge */}
      <div className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
        <div className="text-xs text-gray-400 uppercase tracking-wider mb-3 font-medium">Risk Cap</div>
        {data.gate.blockNewPositions ? (
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/20 border border-red-500/30">
            <Lock className="w-5 h-5 text-red-400" />
            <span className="text-red-400 font-semibold">Positions Blocked</span>
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <div 
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg font-bold text-xl ${
                riskCapPct >= 20 ? 'bg-green-500/20 border border-green-500/30 text-green-400' : 
                riskCapPct >= 10 ? 'bg-yellow-500/20 border border-yellow-500/30 text-yellow-400' : 
                'bg-red-500/20 border border-red-500/30 text-red-400'
              }`}
              data-testid="lare-risk-cap"
            >
              <Lock className="w-4 h-4" />
              {riskCapPct}%
            </div>
            {data.gate.allowAggressiveRisk && (
              <span className="px-2 py-1 rounded bg-green-500/20 text-green-400 text-xs font-medium">
                AGG
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
