/**
 * Dynamic Risk Analytics Panel
 * Phase 4: Operational Analytics Layer
 * 
 * Operator-grade UI: answers "R1 душит или пропускает?" in 2 seconds.
 * 
 * Priority hierarchy:
 * 1. APPROVED vs BLOCKED (largest numbers, green/red)
 * 2. Approval Rate (secondary metric)
 * 3. Avg Multiplier / Notional (diagnostic)
 * 4. Clamp Rate (amber, separate concern)
 */

import { useDynamicRiskAnalytics } from '@/hooks/analytics/useDynamicRiskAnalytics';
import { Card, CardHeader, CardContent } from '@/components/ui/card';

export default function DynamicRiskAnalyticsPanel() {
  const { data, loading, error } = useDynamicRiskAnalytics();

  if (loading) {
    return (
      <Card data-testid="dynamic-risk-panel">
        <CardHeader>
          <div className="text-sm font-semibold text-gray-300">DYNAMIC RISK</div>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-gray-500">Loading...</div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card data-testid="dynamic-risk-panel">
        <CardHeader>
          <div className="text-sm font-semibold text-gray-300">DYNAMIC RISK</div>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-red-400">Error: {error}</div>
        </CardContent>
      </Card>
    );
  }

  // Honest display: show "—" if no data, not misleading 0
  const hasMultiplier = data.avg_multiplier > 0;
  const hasClamp = data.clamped_count > 0;

  return (
    <Card data-testid="dynamic-risk-panel">
      <CardHeader>
        <div className="text-sm font-semibold text-gray-300">DYNAMIC RISK</div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Primary Metrics: APPROVED vs BLOCKED */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs text-gray-500 mb-1">APPROVED</div>
            <div className="text-2xl font-bold text-emerald-400" style={{ fontVariantNumeric: 'tabular-nums' }}>
              {data.approved_count}
            </div>
            <div className="w-8 h-1 bg-emerald-500 mt-1" />
          </div>
          
          <div>
            <div className="text-xs text-gray-500 mb-1">BLOCKED</div>
            <div className="text-2xl font-bold text-red-400" style={{ fontVariantNumeric: 'tabular-nums' }}>
              {data.blocked_count}
            </div>
            <div className="w-8 h-1 bg-red-500 mt-1" />
          </div>
        </div>

        {/* Secondary Metric: Approval Rate */}
        <div className="border-t border-gray-800 pt-3">
          <div className="text-xs text-gray-500 mb-1">APPROVAL RATE</div>
          <div className="text-xl font-bold text-gray-200" style={{ fontVariantNumeric: 'tabular-nums' }}>
            {data.approval_rate_pct}%
          </div>
        </div>

        {/* Diagnostic Metrics */}
        <div className="border-t border-gray-800 pt-3">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-xs text-gray-500 mb-1">AVG MULTIPLIER</div>
              <div className="text-base font-semibold text-gray-300" style={{ fontVariantNumeric: 'tabular-nums' }}>
                {hasMultiplier ? `${data.avg_multiplier.toFixed(2)}x` : '—'}
              </div>
            </div>
            
            <div>
              <div className="text-xs text-gray-500 mb-1">AVG NOTIONAL</div>
              <div className="text-base font-semibold text-gray-300" style={{ fontVariantNumeric: 'tabular-nums' }}>
                ${data.avg_notional_usd.toFixed(0)}
              </div>
            </div>
          </div>
        </div>

        {/* Clamp Rate (separate concern, amber) */}
        <div className="border-t border-gray-800 pt-3">
          <div className="text-xs text-gray-500 mb-1">CLAMP RATE</div>
          <div className="flex items-center gap-2">
            <div className="text-base font-semibold text-amber-400" style={{ fontVariantNumeric: 'tabular-nums' }}>
              {hasClamp ? `${data.clamp_rate_pct.toFixed(1)}%` : '—'}
            </div>
            {hasClamp && <div className="w-6 h-1 bg-amber-500" />}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
