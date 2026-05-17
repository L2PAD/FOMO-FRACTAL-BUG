/**
 * Execution Analytics Panel
 * Phase 4: Operational Analytics Layer
 * 
 * Operator-grade UI: answers "Доходят ли решения до fill?" in 2 seconds.
 * 
 * Priority hierarchy:
 * 1. FILLED vs FAILED (main success/failure signal)
 * 2. Fill Rate (quality metric)
 * 3. Queued / Submitted (pipeline context)
 */

import { useExecutionAnalytics } from '@/hooks/analytics/useExecutionAnalytics';
import { Card, CardHeader, CardContent } from '@/components/ui/card';

export default function ExecutionAnalyticsPanel() {
  const { data, loading, error } = useExecutionAnalytics();

  if (loading) {
    return (
      <Card data-testid="execution-panel">
        <CardHeader>
          <div className="text-sm font-semibold text-gray-300">EXECUTION</div>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-gray-500">Loading...</div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card data-testid="execution-panel">
        <CardHeader>
          <div className="text-sm font-semibold text-gray-300">EXECUTION</div>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-red-400">Error: {error}</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card data-testid="execution-panel">
      <CardHeader>
        <div className="text-sm font-semibold text-gray-300">EXECUTION</div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Pipeline Context: Queued & Submitted */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs text-gray-500 mb-1">QUEUED</div>
            <div className="text-lg font-semibold text-gray-300" style={{ fontVariantNumeric: 'tabular-nums' }}>
              {data.queued}
            </div>
          </div>
          
          <div>
            <div className="text-xs text-gray-500 mb-1">SUBMITTED</div>
            <div className="text-lg font-semibold text-gray-300" style={{ fontVariantNumeric: 'tabular-nums' }}>
              {data.submitted}
            </div>
          </div>
        </div>

        {/* Primary Metrics: FILLED vs FAILED */}
        <div className="border-t border-gray-800 pt-3">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-xs text-gray-500 mb-1">FILLED</div>
              <div className="text-2xl font-bold text-emerald-400" style={{ fontVariantNumeric: 'tabular-nums' }}>
                {data.filled}
              </div>
              <div className="w-8 h-1 bg-emerald-500 mt-1" />
            </div>
            
            <div>
              <div className="text-xs text-gray-500 mb-1">FAILED</div>
              <div className="text-2xl font-bold text-red-400" style={{ fontVariantNumeric: 'tabular-nums' }}>
                {data.failed}
              </div>
              {data.failed > 0 && <div className="w-8 h-1 bg-red-500 mt-1" />}
            </div>
          </div>
        </div>

        {/* Secondary Metric: Fill Rate */}
        <div className="border-t border-gray-800 pt-3">
          <div className="text-xs text-gray-500 mb-1">FILL RATE</div>
          <div className="text-xl font-bold text-gray-200" style={{ fontVariantNumeric: 'tabular-nums' }}>
            {data.fill_rate_pct.toFixed(1)}%
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
