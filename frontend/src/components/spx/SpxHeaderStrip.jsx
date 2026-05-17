/**
 * SPX HEADER STRIP — Intelligence Summary (State-Oriented)
 * 
 * Unified with DXY philosophy:
 * - BULLISH SPX / BEARISH SPX / NEUTRAL (not BUY/SELL)
 * - Confidence
 * - Risk
 * - Market Phase
 * 
 * NO TRADE moved to Execution block
 */

import React, { useEffect, useState } from 'react';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

// Convert action/consensus to market state
const getMarketState = (action, consensusIndex, direction) => {
  if (direction === 'BULL' || action === 'BUY' || consensusIndex > 60) return 'BULLISH';
  if (direction === 'BEAR' || action === 'SELL' || consensusIndex < 40) return 'BEARISH';
  return 'NEUTRAL';
};

const getStateColor = (state) => {
  switch (state) {
    case 'BULLISH': return 'text-emerald-600';
    case 'BEARISH': return 'text-red-500';
    default: return 'text-gray-500';
  }
};

const getRiskColor = (risk) => {
  if (!risk) return 'text-gray-600';
  const r = risk.toUpperCase();
  if (r === 'STRESS' || r === 'HIGH') return 'text-red-600';
  if (r === 'ELEVATED' || r === 'MEDIUM') return 'text-amber-600';
  if (r === 'LOW') return 'text-emerald-600';
  return 'text-gray-600';
};

const getPhaseLabel = (phase) => {
  if (!phase) return 'Unknown';
  const phaseMap = {
    'BULL_EXPANSION': 'Markup',
    'BULL_COOLDOWN': 'Distribution',
    'BEAR_DRAWDOWN': 'Markdown',
    'BEAR_RALLY': 'Accumulation',
    'SIDEWAYS_RANGE': 'Ranging',
    'MARKUP': 'Markup',
    'MARKDOWN': 'Markdown',
    'DISTRIBUTION': 'Distribution',
    'ACCUMULATION': 'Accumulation',
  };
  return phaseMap[phase] || phase.replace(/_/g, ' ');
};

const SpxHeaderStrip = ({ pack, consensus }) => {
  const [guardrails, setGuardrails] = useState(null);
  
  useEffect(() => {
    fetch(`${API_BASE}/api/spx/v2.1/guardrails/summary`)
      .then(res => res.json())
      .then(json => {
        if (json.ok) setGuardrails(json.data);
      })
      .catch(err => console.error('[SpxHeaderStrip] Guardrails fetch error:', err));
  }, []);
  
  if (!pack && !consensus) {
    return (
      <div className="bg-white border-b border-gray-200 px-6 py-3">
        <span className="text-gray-400 text-sm">Loading intelligence...</span>
      </div>
    );
  }

  const phase = pack?.phase?.phase || pack?.phaseIdAtNow?.phase || 'NEUTRAL';
  const phaseStrength = pack?.phase?.strength || pack?.phaseIdAtNow?.strength || 0.5;
  
  // Consensus data
  const consensusIndex = consensus?.consensusIndex || Math.round((pack?.overlay?.stats?.hitRate || 0.5) * 100);
  const direction = consensus?.direction || (pack?.overlay?.stats?.medianReturn > 0 ? 'BULL' : pack?.overlay?.stats?.medianReturn < 0 ? 'BEAR' : 'NEUTRAL');
  const action = consensus?.resolved?.action || 'HOLD';
  
  // Calculate market state (state-oriented, not action-oriented)
  const marketState = getMarketState(action, consensusIndex, direction);
  const stateLabel = marketState === 'BULLISH' ? 'BULLISH SPX' : 
                     marketState === 'BEARISH' ? 'BEARISH SPX' : 'NEUTRAL';
  
  // Risk level
  const riskLevel = guardrails?.globalStatus === 'BLOCK' ? 'STRESS' : 
                    guardrails?.globalStatus === 'CAUTION' ? 'ELEVATED' : 'NORMAL';

  return (
    <div 
      className="bg-white border-b border-gray-200 px-6 py-3"
      data-testid="spx-header-strip"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-6">
          {/* Market State */}
          <span className={`text-sm font-semibold ${getStateColor(marketState)}`} data-testid="spx-market-state">
            {stateLabel}
          </span>
          
          {/* Confidence */}
          <div className="text-sm">
            <span className="text-gray-400">Confidence:</span>
            <span className="ml-1 font-medium text-gray-900">{consensusIndex}%</span>
          </div>
          
          {/* Risk */}
          <div className="text-sm">
            <span className="text-gray-400">Risk:</span>
            <span className={`ml-1 text-xs font-medium ${getRiskColor(riskLevel)}`}>
              {riskLevel}
            </span>
          </div>
          
          {/* Phase */}
          <div className="text-sm">
            <span className="text-gray-400">Phase:</span>
            <span className="ml-1 font-medium text-gray-900">{getPhaseLabel(phase)}</span>
            <span className="ml-1 text-gray-400 text-xs">({Math.round(phaseStrength * 100)}%)</span>
          </div>
        </div>
        
        <div className="flex items-center gap-4 text-xs text-gray-500">
          <span className="text-emerald-700 text-xs font-medium">
            REAL
          </span>
        </div>
      </div>
    </div>
  );
};

export default SpxHeaderStrip;
