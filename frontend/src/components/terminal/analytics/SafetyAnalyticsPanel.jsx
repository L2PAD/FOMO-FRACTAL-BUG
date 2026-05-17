/**
 * Safety Analytics Panel
 * Phase 4: Operational Analytics Layer
 * 
 * Operator-grade UI: answers "Кто блокирует чаще: R1 или AutoSafety?" in 2 seconds.
 * 
 * Priority hierarchy:
 * 1. Total Blocks (main volume signal)
 * 2. R1 vs AutoSafety breakdown (diagnostic)
 * 3. Top Rule (actionable insight, red highlight)
 */

import { useSafetyAnalytics } from '@/hooks/analytics/useSafetyAnalytics';
import { Card, CardHeader, CardContent } from '@/components/ui/card';

export default function SafetyAnalyticsPanel() {
  const { data, loading, error } = useSafetyAnalytics();

  if (loading) {
    return (
      <Card data-testid="safety-panel">
        <CardHeader>
          <div className="text-sm font-semibold text-gray-300">SAFETY</div>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-gray-500">Loading...</div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card data-testid="safety-panel">
        <CardHeader>
          <div className="text-sm font-semibold text-gray-300">SAFETY</div>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-red-400">Error: {error}</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card data-testid="safety-panel">
      <CardHeader>
        <div className="text-sm font-semibold text-gray-300">SAFETY</div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Primary Metric: Total Blocks */}
        <div>
          <div className="text-xs text-gray-500 mb-1">TOTAL BLOCKS</div>
          <div className="text-2xl font-bold text-gray-200" style={{ fontVariantNumeric: 'tabular-nums' }}>
            {data.total_blocks}
          </div>
        </div>

        {/* Diagnostic: R1 vs AutoSafety breakdown */}
        <div className="border-t border-gray-800 pt-3">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-xs text-gray-500 mb-1">R1 BLOCKS</div>
              <div className="text-lg font-semibold text-gray-300" style={{ fontVariantNumeric: 'tabular-nums' }}>
                {data.dynamic_risk_block_count}
              </div>
            </div>
            
            <div>
              <div className="text-xs text-gray-500 mb-1">AUTO BLOCKS</div>
              <div className="text-lg font-semibold text-gray-300" style={{ fontVariantNumeric: 'tabular-nums' }}>
                {data.auto_block_count}
              </div>
            </div>
          </div>
        </div>

        {/* Actionable Insight: Top Rule */}
        <div className="border-t border-gray-800 pt-3">
          <div className="text-xs text-gray-500 mb-1">Top rule</div>
          <div className="flex items-center gap-2">
            <div className="text-sm text-red-400 bg-red-500/10 px-2 py-1 rounded border border-red-500/20" title={data.top_rule}>
              {String(data.top_rule || '—')
                .split(/[_\-.]+/)
                .filter(Boolean)
                .map((tok, idx) => (idx === 0 ? tok.charAt(0).toUpperCase() + tok.slice(1).toLowerCase() : tok.toLowerCase()))
                .join(' ')}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
