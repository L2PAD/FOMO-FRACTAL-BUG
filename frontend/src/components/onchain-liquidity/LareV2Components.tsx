/**
 * LARE v2 Components Breakdown
 * =============================
 * 
 * PHASE 4: 4 uniform cards for Market, Flow, Bridge, Stables
 * - Одинаковая высота
 * - Без "/ 100"
 * - Без лишнего текста
 */

import React from 'react';
import { TrendingUp, TrendingDown, Minus, BarChart3, Waves, GitBranch, DollarSign } from 'lucide-react';
import type { LareV2Component } from './useLareV2';

interface Props {
  components: LareV2Component[];
}

const COMPONENT_CONFIG: Record<string, { icon: any; label: string }> = {
  'market': { icon: BarChart3, label: 'Market' },
  'flow': { icon: Waves, label: 'Flow' },
  'bridge': { icon: GitBranch, label: 'Bridge' },
  'stables': { icon: DollarSign, label: 'Stables' },
};

function ComponentCard({ component }: { component: LareV2Component }) {
  const config = COMPONENT_CONFIG[component.key] || { icon: BarChart3, label: component.key };
  const Icon = config.icon;
  
  const score = Math.round(component.score);
  const confPct = Math.round(component.confidence * 100);
  
  // Direction
  const DirectionIcon = component.direction === 1 ? TrendingUp : 
                        component.direction === -1 ? TrendingDown : Minus;
  
  // Colors
  const scoreColor = score >= 60 ? '#4ade80' : 
                     score >= 40 ? '#fbbf24' : '#f87171';
  
  const dirColor = component.direction === 1 ? '#4ade80' : 
                   component.direction === -1 ? '#f87171' : '#6b7280';
  
  const confColor = confPct >= 50 ? '#4ade80' : confPct >= 30 ? '#fbbf24' : '#f87171';

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-gray-400" />
          <span className="text-sm font-medium text-gray-200">{config.label}</span>
        </div>
        <DirectionIcon className="w-4 h-4" style={{ color: dirColor }} />
      </div>

      {/* Score — крупно, без /100 */}
      <div 
        className="text-3xl font-bold tabular-nums mb-3"
        style={{ color: scoreColor }}
      >
        {score}
      </div>

      {/* Confidence bar — толще */}
      <div className="flex items-center gap-2 mb-3">
        <div className="flex-1 h-2 bg-white/10 rounded-full overflow-hidden">
          <div 
            className="h-full rounded-full transition-all"
            style={{ width: `${confPct}%`, backgroundColor: confColor }}
          />
        </div>
        <span className="text-xs font-medium tabular-nums" style={{ color: confColor }}>
          {confPct}%
        </span>
      </div>

      {/* Driver — только если есть, в конец */}
      {component.drivers.length > 0 && (
        <div className="mt-auto text-xs text-gray-400 line-clamp-2">
          {component.drivers[0]}
        </div>
      )}
    </div>
  );
}

export function LareV2Components({ components }: Props) {
  // Если нет компонентов — не рендерим
  if (!components || components.length === 0) return null;
  
  // Порядок: market, flow, bridge, stables
  const order = ['market', 'flow', 'bridge', 'stables'];
  const sorted = [...components].sort((a, b) => 
    order.indexOf(a.key) - order.indexOf(b.key)
  );

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4" data-testid="lare-v2-components">
      {sorted.map(c => (
        <ComponentCard key={c.key} component={c} />
      ))}
    </div>
  );
}
