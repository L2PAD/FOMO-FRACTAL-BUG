/**
 * SPX VERDICT CARD — State-Oriented Research View
 * 
 * Unified with DXY philosophy:
 * - Market State: BULLISH / BEARISH / NEUTRAL
 * - Directional Bias: SPX ↑ / SPX ↓
 * - Expected Move (P50)
 * - Range (P10-P90)
 * - Position Size
 * 
 * NO BUY/SELL actions in main display
 */

import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

// Convert action/stats to market state
const getMarketState = (action, medianReturn) => {
  if (action === 'BUY' || medianReturn > 0.01) return 'BULLISH';
  if (action === 'SELL' || medianReturn < -0.01) return 'BEARISH';
  return 'NEUTRAL';
};

const getStateColor = (state) => {
  switch (state) {
    case 'BULLISH': return 'text-emerald-600';
    case 'BEARISH': return 'text-red-500';
    default: return 'text-gray-500';
  }
};

const getBiasArrow = (medianReturn) => {
  if (medianReturn > 0.005) return '↑';
  if (medianReturn < -0.005) return '↓';
  return '—';
};

const BiasIcon = ({ direction }) => {
  if (direction === 'up') return <TrendingUp className="w-5 h-5" />;
  if (direction === 'down') return <TrendingDown className="w-5 h-5" />;
  return <Minus className="w-5 h-5" />;
};

const SpxVerdictCard = ({ overlay, consensus, meta, focus }) => {
  if (!overlay?.stats) return null;
  
  const { stats } = overlay;
  const action = consensus?.resolved?.action || 'HOLD';
  const sizeMultiplier = consensus?.resolved?.sizeMultiplier || 1.0;
  
  // Calculate state-oriented values
  const marketState = getMarketState(action, stats.medianReturn);
  const biasArrow = getBiasArrow(stats.medianReturn);
  const biasDirection = stats.medianReturn > 0.005 ? 'up' : stats.medianReturn < -0.005 ? 'down' : 'neutral';
  
  // Format percentages
  const expectedP50 = (stats.medianReturn * 100).toFixed(2);
  const rangeP10 = (stats.p10Return * 100).toFixed(2);
  const rangeP90 = (stats.p90Return * 100).toFixed(2);
  
  // Invalidations / What would change view
  const invalidations = [];
  if (stats.hitRate < 0.5) invalidations.push('Hit rate below 50%');
  if (Math.abs(stats.medianReturn) < 0.01) invalidations.push('No clear directional edge');
  if (overlay.matches?.length < 5) invalidations.push('Limited historical sample');

  return (
    <div className="bg-white rounded-xl p-6 mb-6" data-testid="spx-verdict-card">
      <div className="flex items-center gap-3 mb-4">
        <h2 className="text-xl font-semibold text-gray-900">SPX Verdict</h2>
        <span className="text-sm font-medium text-gray-600">
          {focus?.toUpperCase() || '30D'}
        </span>
      </div>
      
      <div className="grid grid-cols-5 gap-6 mb-6">
        {/* Market State */}
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Market State</p>
          <p className={`text-2xl font-bold ${getStateColor(marketState)}`}>
            {marketState}
          </p>
        </div>
        
        {/* Directional Bias */}
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Directional Bias</p>
          <div className="flex items-center gap-2">
            <span className={`text-xl font-bold ${
              biasDirection === 'up' ? 'text-emerald-600' : 
              biasDirection === 'down' ? 'text-red-500' : 'text-gray-500'
            }`}>
              SPX {biasArrow}
            </span>
          </div>
        </div>
        
        {/* Expected Move */}
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Expected (P50)</p>
          <p className={`text-xl font-bold ${
            stats.medianReturn > 0 ? 'text-emerald-600' : 
            stats.medianReturn < 0 ? 'text-red-500' : 'text-gray-500'
          }`}>
            {stats.medianReturn > 0 ? '+' : ''}{expectedP50}%
          </p>
        </div>
        
        {/* Range */}
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Range (P10–P90)</p>
          <p className="text-sm font-medium text-gray-700">
            {rangeP10}% – {rangeP90}%
          </p>
        </div>
        
        {/* Position Size */}
        <div>
          <p className="text-xs text-gray-400 uppercase mb-1">Position Size</p>
          <p className="text-xl font-bold text-gray-900">{sizeMultiplier.toFixed(1)}×</p>
        </div>
      </div>
      
      {/* Invalidations */}
      {invalidations.length > 0 && (
        <div className="pt-4 border-t border-gray-100">
          <p className="text-xs text-gray-400 uppercase mb-2">What would change this view</p>
          <ul className="space-y-1">
            {invalidations.map((inv, idx) => (
              <li key={idx} className="text-sm text-gray-600 flex items-center gap-2">
                <span className="w-1 h-1 bg-amber-500 rounded-full" />
                {inv}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default SpxVerdictCard;
