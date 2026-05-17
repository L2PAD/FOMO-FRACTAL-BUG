import React from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { Tooltip, TooltipTrigger, TooltipContent } from '../../../../../components/ui/tooltip';
import { fmtUsd, fmtUsdSigned } from '../helpers';

export function SmartMoneyIndexCard({ score, confidence }: { score: number; confidence: number }) {
  const label = score >= 60 ? 'Bullish' : score >= 40 ? 'Neutral' : 'Bearish';
  const color = score >= 60 ? 'text-emerald-400' : score >= 40 ? 'text-amber-400' : 'text-red-400';
  const barColor = score >= 60 ? 'bg-emerald-400' : score >= 40 ? 'bg-amber-400' : 'bg-red-400';

  return (
    <div className="rounded-2xl bg-gray-900 intelligence-dark p-5 flex flex-col justify-between" data-testid="smi-card">
      <div>
        <Tooltip delayDuration={200}>
          <TooltipTrigger asChild>
            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider cursor-default">Smart Money Index</h4>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="max-w-[260px] text-xs leading-relaxed">
            Aggregated score based on buy/sell volume ratio weighted by entity significance. 100 = max bullish, 0 = max bearish.
          </TooltipContent>
        </Tooltip>
        <div className={`text-4xl font-bold mt-3 ${color}`} data-testid="smi-score">{score}</div>
        <div className={`text-sm font-semibold mt-1 ${color}`}>{label}</div>
      </div>
      <div className="mt-4">
        <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
          <div className={`h-full rounded-full ${barColor} transition-all duration-700`} style={{ width: `${score}%` }} />
        </div>
        <div className="flex justify-between mt-1.5">
          <span className="text-[10px] text-gray-500">0</span>
          <Tooltip delayDuration={200}>
            <TooltipTrigger asChild>
              <span className="text-[10px] text-gray-500 cursor-default">Confidence {confidence}%</span>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-[220px] text-xs">Based on total flow volume. Higher volume = higher confidence.</TooltipContent>
          </Tooltip>
          <span className="text-[10px] text-gray-500">100</span>
        </div>
      </div>
    </div>
  );
}

export function MarketPressureBlock({ totalBuy, totalSell, netFlow, isBullish, timeWindow }: {
  totalBuy: number; totalSell: number; netFlow: number; isBullish: boolean; timeWindow: string;
}) {
  const buyPct = totalBuy + Math.abs(totalSell) > 0
    ? (totalBuy / (totalBuy + Math.abs(totalSell))) * 100 : 50;

  return (
    <div className="rounded-2xl bg-gray-900 intelligence-dark p-6 text-white h-full" data-testid="market-pressure-block">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 flex items-center justify-center ${isBullish ? 'text-emerald-400' : 'text-red-400'}`}>
            {isBullish ? <TrendingUp className="w-5 h-5 text-emerald-400" /> : <TrendingDown className="w-5 h-5 text-red-400" />}
          </div>
          <div>
            <Tooltip delayDuration={200}>
              <TooltipTrigger asChild>
                <h3 className="text-lg font-bold cursor-default">Market Pressure</h3>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-[280px] text-xs leading-relaxed">
                Calculated from net smart money inflows vs outflows. Shows the buying/selling ratio of large wallets, protocols, and institutional entities.
              </TooltipContent>
            </Tooltip>
            <p className="text-xs text-gray-400">{timeWindow.toUpperCase()} window</p>
          </div>
        </div>
        <div className={`px-4 py-2 text-sm font-bold ${
          isBullish ? 'text-emerald-400' : 'text-red-400'
        }`} data-testid="market-signal">
          {isBullish ? 'BULLISH' : 'BEARISH'}
        </div>
      </div>

      <div className="mb-5">
        <div className="flex justify-between text-xs text-gray-400 mb-2">
          <span>Buying pressure</span><span>Selling pressure</span>
        </div>
        <div className="h-3 rounded-full bg-gray-800 overflow-hidden flex">
          <div className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 rounded-l-full transition-all duration-700" style={{ width: `${buyPct}%` }} />
          <div className="h-full bg-gradient-to-r from-red-400 to-red-500 rounded-r-full transition-all duration-700" style={{ width: `${100 - buyPct}%` }} />
        </div>
        <div className="flex justify-between text-xs mt-2">
          <span className="text-emerald-400 font-semibold">{buyPct.toFixed(0)}%</span>
          <span className="text-red-400 font-semibold">{(100 - buyPct).toFixed(0)}%</span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="p-3">
          <Tooltip delayDuration={200}>
            <TooltipTrigger asChild>
              <div className="text-[10px] text-gray-400 mb-1 cursor-default">Smart Money Buying</div>
            </TooltipTrigger>
            <TooltipContent className="text-xs">Sum of all positive net flows from tracked entities</TooltipContent>
          </Tooltip>
          <div className="text-xl font-bold text-emerald-400" data-testid="total-buying">+{fmtUsd(totalBuy)}</div>
        </div>
        <div className="p-3">
          <Tooltip delayDuration={200}>
            <TooltipTrigger asChild>
              <div className="text-[10px] text-gray-400 mb-1 cursor-default">Smart Money Selling</div>
            </TooltipTrigger>
            <TooltipContent className="text-xs">Sum of all negative net flows from tracked entities</TooltipContent>
          </Tooltip>
          <div className="text-xl font-bold text-red-400" data-testid="total-selling">-{fmtUsd(Math.abs(totalSell))}</div>
        </div>
        <div className="p-3">
          <Tooltip delayDuration={200}>
            <TooltipTrigger asChild>
              <div className="text-[10px] text-gray-400 mb-1 cursor-default">Net Smart Flow</div>
            </TooltipTrigger>
            <TooltipContent className="text-xs">Buying minus selling. Positive = net accumulation.</TooltipContent>
          </Tooltip>
          <div className={`text-xl font-bold ${isBullish ? 'text-emerald-400' : 'text-red-400'}`} data-testid="net-flow">{fmtUsdSigned(netFlow)}</div>
        </div>
      </div>
    </div>
  );
}
