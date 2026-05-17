/**
 * MetaBrainVerdict — Shows the main AI signal verdict
 * Clean, confident display of direction + confidence + regime
 */
import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

const VERDICT_CONFIG = {
  LONG: { icon: TrendingUp, color: '#16a34a', bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', label: 'LONG' },
  SHORT: { icon: TrendingDown, color: '#dc2626', bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200', label: 'SHORT' },
  NEUTRAL: { icon: Minus, color: '#6b7280', bg: 'bg-gray-50', text: 'text-gray-600', border: 'border-gray-200', label: 'NEUTRAL' },
};

export default function MetaBrainVerdict({ data }) {
  if (!data) return null;
  const cfg = VERDICT_CONFIG[data.verdict] || VERDICT_CONFIG.NEUTRAL;
  const Icon = cfg.icon;
  const confPct = Math.round((data.metaConfidence || 0) * 100);

  return (
    <div className={`rounded-2xl border ${cfg.border} ${cfg.bg} p-5`} data-testid="meta-brain-verdict">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${cfg.bg}`} style={{ border: `1.5px solid ${cfg.color}20` }}>
            <Icon className="w-5 h-5" style={{ color: cfg.color }} />
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wider text-gray-400 font-medium">Meta Brain Signal</p>
            <p className={`text-xl font-bold ${cfg.text}`} data-testid="verdict-direction">{cfg.label}</p>
          </div>
        </div>

        <div className="text-right">
          <p className="text-[10px] uppercase tracking-wider text-gray-400 font-medium">Confidence</p>
          <p className="text-xl font-bold text-gray-900" data-testid="verdict-confidence">{confPct}%</p>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-gray-400 uppercase tracking-wider">Regime</span>
          <span className="text-xs font-semibold text-gray-700" data-testid="verdict-regime">{data.regime || '—'}</span>
        </div>
        {data.stability?.cooldownActive && (
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
            <span className="text-[10px] text-amber-600 font-medium">Cooldown active</span>
          </div>
        )}
        {data.stability?.applied && (
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-gray-400">Stability applied</span>
          </div>
        )}
      </div>
    </div>
  );
}
