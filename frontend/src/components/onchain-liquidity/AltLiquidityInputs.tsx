/**
 * Alt Liquidity Inputs
 * =====================
 * 
 * PHASE 3: Raw market inputs display
 */

import React from 'react';
import { Database, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import type { LiquidityInputs } from './types';
import { formatNumber, formatDelta } from './ui';

interface Props {
  inputs?: LiquidityInputs;
}

interface MetricRowProps {
  label: string;
  value: number;
  delta7d: number | null;
  unit?: string;
  format?: 'number' | 'percent' | 'ratio';
}

function MetricRow({ label, value, delta7d, unit = '', format = 'number' }: MetricRowProps) {
  const formattedValue = format === 'percent' 
    ? `${value.toFixed(2)}%`
    : format === 'ratio'
    ? value.toFixed(4)
    : formatNumber(value);

  const DeltaIcon = delta7d === null 
    ? Minus 
    : delta7d >= 0 
    ? TrendingUp 
    : TrendingDown;

  const deltaColor = delta7d === null 
    ? 'text-gray-500' 
    : delta7d >= 0 
    ? 'text-green-400' 
    : 'text-red-400';

  return (
    <div className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
      <span className="text-sm text-gray-400">{label}</span>
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-gray-200">
          {formattedValue}{unit}
        </span>
        <div className={`flex items-center gap-1 text-xs ${deltaColor}`}>
          <DeltaIcon className="w-3 h-3" />
          <span>{formatDelta(delta7d)}</span>
        </div>
      </div>
    </div>
  );
}

export function AltLiquidityInputs({ inputs }: Props) {
  if (!inputs) {
    return null;
  }

  return (
    <div className="rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm p-5">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <Database className="w-5 h-5 text-blue-400" />
        <span className="text-sm font-medium text-gray-300">Market Inputs</span>
        <span className="text-xs text-gray-500 ml-auto">7d Change</span>
      </div>

      {/* Metrics */}
      <div data-testid="liquidity-inputs">
        <MetricRow 
          label="Pure Alt Cap" 
          value={inputs.pureAltCap.now} 
          delta7d={inputs.pureAltCap.delta7d} 
        />
        <MetricRow 
          label="Stable Supply" 
          value={inputs.stableSupply.now} 
          delta7d={inputs.stableSupply.delta7d} 
        />
        <MetricRow 
          label="Stable Dominance" 
          value={inputs.stableDom.now} 
          delta7d={inputs.stableDom.delta7d}
          format="percent"
        />
        <MetricRow 
          label="BTC Dominance" 
          value={inputs.btcDom.now} 
          delta7d={inputs.btcDom.delta7d}
          format="percent"
        />
        <MetricRow 
          label="ETH/BTC Ratio" 
          value={inputs.ethbtc.now} 
          delta7d={inputs.ethbtc.delta7d}
          format="ratio"
        />
      </div>
    </div>
  );
}
