/**
 * Labs Macro Regime Page
 * 
 * Full market regime analysis dashboard
 * Style: FomoAI Design System
 */

import { BarChart3, TrendingUp, RefreshCw, Activity, Zap, Globe } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { MarketRegimeGrid } from '../../components/macro/MarketRegimeGrid';
import { ActiveRegimeCard } from '../../components/macro/ActiveRegimeCard';
import { FearGreedHistoryChart } from '../../components/fomo-ai/FearGreedHistoryChart';
import { MacroContextPanel } from '../../components/fomo-ai/MacroContextPanel';
import { RegimeTransitionsHistory } from '../../components/macro/RegimeTransitionsHistory';

/* ═══════════════════════════════════════════════════════════════
   CSS-in-JS styles for animations (FomoAI style)
═══════════════════════════════════════════════════════════════ */
if (typeof document !== 'undefined' && !document.getElementById('macro-animations')) {
  const style = document.createElement('style');
  style.id = 'macro-animations';
  style.textContent = `
    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }
    @keyframes slideUp {
      from { opacity: 0; transform: translateY(12px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .card-hover { transition: all 0.2s ease; }
    .card-hover:hover { transform: translateY(-2px); box-shadow: 0 8px 25px -5px rgba(0,0,0,0.1); }
  `;
  document.head.appendChild(style);
}

export default function LabsMacroRegimePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-gray-50" style={{ animation: 'fadeIn 0.4s ease-out forwards' }}>
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Top Row: Active Regime + Context */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" style={{ animation: 'slideUp 0.5s ease-out forwards', animationDelay: '100ms' }}>
          <ActiveRegimeCard />
          <MacroContextPanel />
        </div>

        {/* Regime Grid */}
        <div style={{ animation: 'slideUp 0.5s ease-out forwards', animationDelay: '200ms' }}>
          <MarketRegimeGrid />
        </div>

        {/* Historical Data */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" style={{ animation: 'slideUp 0.5s ease-out forwards', animationDelay: '300ms' }}>
          <FearGreedHistoryChart days={14} />
          <RegimeTransitionsHistory limit={10} />
        </div>
        
        {/* Regime Explanation Card */}
        <div className="bg-white rounded-xl p-6 card-hover" style={{ animation: 'slideUp 0.5s ease-out forwards', animationDelay: '400ms' }}>
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-4 h-4 text-slate-600" />
            <h3 className="text-lg font-semibold text-gray-900">How Regime Detection Works</h3>
          </div>
          <div className="space-y-4 text-sm text-gray-600">
            <p>
              The Market Regime Engine analyzes four key signals to determine the current market state:
            </p>
            <ul className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <li className="flex items-start gap-3 p-3 bg-orange-50 rounded-xl ">
                <span className="text-orange-600 font-bold text-sm">&#8383;</span>
                <div>
                  <span className="font-semibold text-gray-900">BTC Dominance</span>
                  <p className="text-gray-500 text-xs mt-0.5">Capital concentration in Bitcoin vs altcoins</p>
                </div>
              </li>
              <li className="flex items-start gap-3 p-3 bg-green-50 rounded-xl ">
                <TrendingUp className="w-4 h-4 text-green-600" />
                <div>
                  <span className="font-semibold text-gray-900">BTC Price</span>
                  <p className="text-gray-500 text-xs mt-0.5">Direction of Bitcoin price over 24h</p>
                </div>
              </li>
              <li className="flex items-start gap-3 p-3 bg-blue-50 rounded-xl ">
                <BarChart3 className="w-4 h-4 text-blue-600" />
                <div>
                  <span className="font-semibold text-gray-900">Alt Market</span>
                  <p className="text-gray-500 text-xs mt-0.5">Proxy for altcoin market movement</p>
                </div>
              </li>
              <li className="flex items-start gap-3 p-3 bg-emerald-50 rounded-xl ">
                <Zap className="w-4 h-4 text-emerald-600" />
                <div>
                  <span className="font-semibold text-gray-900">Stablecoin Dominance</span>
                  <p className="text-gray-500 text-xs mt-0.5">Capital in stablecoins (USDT+USDC)</p>
                </div>
              </li>
            </ul>
            <div className="pt-4 border-t border-gray-200">
              <p className="text-gray-500 italic text-xs">
                Macro regime affects confidence multiplier and can block strong actions during extreme conditions.
                It never creates signals or changes direction — only context and caution.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
