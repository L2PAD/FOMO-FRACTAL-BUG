/**
 * MetaBrainSignals — Module contribution breakdown
 * Shows each module's direction, weight, and impact on the final verdict
 */
import React from 'react';
import { TrendingUp, TrendingDown, Minus, Layers } from 'lucide-react';

const DIR_ICON = {
  LONG: { icon: TrendingUp, color: '#16a34a' },
  SHORT: { icon: TrendingDown, color: '#dc2626' },
  NEUTRAL: { icon: Minus, color: '#6b7280' },
};

const MODULE_LABELS = {
  fractal: 'Fractal',
  exchange: 'Exchange',
  onchain: 'On-Chain',
  sentiment: 'Sentiment',
  tech: 'TechAnalysis',
};

export default function MetaBrainSignals({ signals }) {
  if (!signals?.length) return null;

  // Sort by absolute impact
  const sorted = [...signals].sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact));

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5" data-testid="meta-brain-signals">
      <div className="flex items-center gap-2 mb-4">
        <Layers className="w-4 h-4 text-gray-400" />
        <p className="text-[10px] uppercase tracking-wider text-gray-400 font-medium">Module Signals</p>
      </div>

      <div className="space-y-2">
        {sorted.map(sig => {
          const dir = sig.direction || 'NEUTRAL';
          const cfg = DIR_ICON[dir] || DIR_ICON.NEUTRAL;
          const Icon = cfg.icon;
          const impactSign = sig.impact >= 0 ? '+' : '';
          const impactPct = (Math.abs(sig.impact) * 100).toFixed(1);

          return (
            <div key={sig.module} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0" data-testid={`signal-${sig.module}`}>
              <div className="flex items-center gap-2.5">
                <Icon className="w-3.5 h-3.5" style={{ color: cfg.color }} />
                <span className="text-sm font-medium text-gray-700">{MODULE_LABELS[sig.module] || sig.module}</span>
              </div>

              <div className="flex items-center gap-4">
                <span className="text-xs font-medium" style={{ color: cfg.color }}>{dir}</span>
                <div className="w-24">
                  <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${Math.min(Math.abs(sig.impact) / 0.5 * 100, 100)}%`,
                        backgroundColor: cfg.color,
                        opacity: 0.6,
                      }}
                    />
                  </div>
                </div>
                <span className="text-xs font-mono text-gray-500 w-16 text-right" data-testid={`impact-${sig.module}`}>
                  {impactSign}{sig.impact.toFixed(3)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
