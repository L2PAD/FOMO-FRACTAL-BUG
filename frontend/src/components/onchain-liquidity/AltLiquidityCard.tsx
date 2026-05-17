/**
 * Alt Liquidity Card
 * ===================
 * 
 * PHASE 3: Hero block showing LiquidityScore, Regime, Confidence, Governance
 */

import React from 'react';
import { TrendingUp, TrendingDown, Activity, Shield, AlertTriangle, Lock, Unlock } from 'lucide-react';
import type { LiquidityLatest } from './types';
import { scoreColor, regimeColor, regimeLabel, guardrailColor } from './ui';

interface Props {
  latest: LiquidityLatest;
}

export function AltLiquidityCard({ latest }: Props) {
  const score = Math.round(latest.score);
  const confPct = Math.round((latest.confidence ?? 0) * 100);
  const regime = latest.regime;
  const govState = latest.governance?.guardrailState ?? 'HEALTHY';
  const govAction = latest.governance?.guardrailAction ?? 'NONE';
  const isBlocked = govAction === 'BLOCK_OUTPUT' || govState === 'CRITICAL';
  const isDownweighted = govAction === 'DOWNWEIGHT';

  // Gate info
  const gate = latest.gate;
  const riskCapPct = gate ? Math.round(gate.riskCap * 100) : 0;

  return (
    <div className="rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm p-5">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <Activity className="w-5 h-5 text-blue-400" />
        <span className="text-sm font-medium text-gray-300">Alt Liquidity Signal</span>
      </div>

      {/* Main Content */}
      <div className="flex flex-col lg:flex-row gap-6">
        {/* Score */}
        <div className="flex-shrink-0">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Liquidity Score</div>
          <div 
            className="text-5xl font-bold"
            style={{ color: scoreColor(score) }}
            data-testid="liquidity-score"
          >
            {score}
          </div>
          <div className="text-xs text-gray-500 mt-1">0–100 range</div>
        </div>

        {/* Regime & Confidence */}
        <div className="flex-1 grid grid-cols-2 gap-4">
          {/* Regime */}
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Regime</div>
            <div 
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium"
              style={{ 
                backgroundColor: `${regimeColor(regime)}20`,
                color: regimeColor(regime),
                border: `1px solid ${regimeColor(regime)}40`,
              }}
              data-testid="liquidity-regime"
            >
              {score >= 50 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
              {regimeLabel(regime)}
            </div>
          </div>

          {/* Confidence */}
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Confidence</div>
            <div className="flex items-center gap-3">
              <div className="flex-1 h-2 bg-white/10 rounded-full overflow-hidden">
                <div 
                  className="h-full rounded-full transition-all duration-500"
                  style={{ 
                    width: `${confPct}%`,
                    backgroundColor: confPct >= 60 ? '#22c55e' : confPct >= 30 ? '#eab308' : '#ef4444',
                  }}
                />
              </div>
              <span className="text-sm font-medium text-gray-300" data-testid="liquidity-confidence">
                {confPct}%
              </span>
            </div>
            {isDownweighted && (
              <div className="text-xs text-yellow-500 mt-1 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" />
                Downweighted
              </div>
            )}
          </div>

          {/* Guardrail */}
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Guardrail</div>
            <div 
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium"
              style={{ 
                backgroundColor: `${guardrailColor(govState)}20`,
                color: guardrailColor(govState),
                border: `1px solid ${guardrailColor(govState)}40`,
              }}
              data-testid="liquidity-guardrail"
            >
              <Shield className="w-4 h-4" />
              {govState}
            </div>
          </div>

          {/* Action */}
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Action</div>
            <div className="text-sm text-gray-400" data-testid="liquidity-action">
              {govAction === 'NONE' ? 'None (Pass-through)' : govAction}
            </div>
          </div>
        </div>
      </div>

      {/* Risk Gate (Context Layer Output) */}
      {gate && (
        <div className="mt-4 p-3 rounded-lg bg-white/5 border border-white/10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-gray-300">
              {gate.blockNewPositions ? (
                <Lock className="w-4 h-4 text-red-400" />
              ) : (
                <Unlock className="w-4 h-4 text-green-400" />
              )}
              <span className="font-medium">Risk Gate</span>
            </div>
            <div className="flex items-center gap-4 text-sm">
              <div className="flex items-center gap-2">
                <span className="text-gray-500">Risk Cap:</span>
                <span 
                  className={`font-medium ${riskCapPct >= 50 ? 'text-green-400' : riskCapPct >= 25 ? 'text-yellow-400' : 'text-red-400'}`}
                  data-testid="risk-cap"
                >
                  {riskCapPct}%
                </span>
              </div>
              {gate.allowAggressiveRisk && (
                <span className="px-2 py-0.5 rounded-full bg-green-500/20 text-green-400 text-xs">
                  Aggressive OK
                </span>
              )}
              {gate.blockNewPositions && (
                <span className="px-2 py-0.5 rounded-full bg-red-500/20 text-red-400 text-xs">
                  Blocked
                </span>
              )}
            </div>
          </div>
          <div className="mt-2 text-xs text-gray-500">
            {gate.reason}
          </div>
        </div>
      )}

      {/* Blocked Warning */}
      {isBlocked && (
        <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30">
          <div className="flex items-center gap-2 text-red-400 text-sm font-medium">
            <AlertTriangle className="w-4 h-4" />
            Output blocked by governance
          </div>
          {latest.governance?.reasons?.length > 0 && (
            <div className="mt-1 text-xs text-red-400/80">
              {latest.governance.reasons.join(', ')}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
