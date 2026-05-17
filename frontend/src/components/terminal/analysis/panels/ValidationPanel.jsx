/**
 * Validation Panel - WITH BINDING
 * ================================
 * 
 * Shows truth layer metrics with bidirectional binding:
 * - Validation issues highlight execution zones when hovered
 */

import React from 'react';
import { useBinding, makeEntryZoneId, makeRiskZoneId, makeTargetZoneId } from '../../binding';
import { PanelShell } from '../shared/PanelShell';
import { GridRow } from '../shared/GridRow';
import { fmtPct, fmtNum } from '../shared/formatters';

export default function ValidationPanel({ data, symbol = 'BTCUSDT', timeframe = '4H' }) {
  const { setHovered, clearHovered, setSelected } = useBinding();

  if (!data) {
    return (
      <PanelShell title="Validation Truth">
        <div className="text-gray-500 text-sm">No validation data available</div>
      </PanelShell>
    );
  }

  const status = !data.is_valid
    ? 'CRITICAL'
    : (data.warning_count || 0) > 0
    ? 'WARNING'
    : 'VALID';

  const statusColor = status === 'CRITICAL' 
    ? 'text-red-400' 
    : status === 'WARNING' 
    ? 'text-yellow-400' 
    : 'text-green-400';

  return (
    <PanelShell title="Validation Truth">
      <GridRow 
        label="Status" 
        value={<span className={statusColor}>{status}</span>} 
      />
      <GridRow label="Critical" value={data.critical_count ?? 0} />
      <GridRow label="Warnings" value={data.warning_count ?? 0} />
      <GridRow label="Win Rate" value={fmtPct(data.metrics?.win_rate)} />
      <GridRow 
        label="Profit Factor" 
        value={data.metrics?.profit_factor != null ? fmtNum(data.metrics.profit_factor, 2) : '—'} 
      />
      <GridRow label="Expired" value={fmtPct(data.metrics?.expired_rate)} />
      <GridRow 
        label="Drift" 
        value={data.metrics?.avg_drift_bps != null ? `${fmtNum(data.metrics.avg_drift_bps, 1)} bps` : '—'} 
      />

      {/* Issues with binding */}
      <div>
        <div className="mb-2 text-xs uppercase tracking-wide text-gray-400">Issues</div>
        <div className="space-y-2">
          {data.issues?.length ? (
            data.issues.map((issue, i) => {
              const entityId = `validation-issue-${issue.type}-${i}`;

              return (
                <button
                  key={entityId}
                  type="button"
                  onMouseEnter={() =>
                    setHovered({
                      id: entityId,
                      type: 'validation_issue',
                      label: issue.type,
                      relatedIds: [
                        makeEntryZoneId(symbol, timeframe),
                        makeRiskZoneId(symbol, timeframe),
                        makeTargetZoneId(symbol, timeframe),
                      ],
                      meta: issue,
                    })
                  }
                  onMouseLeave={clearHovered}
                  onClick={() =>
                    setSelected({
                      id: entityId,
                      type: 'validation_issue',
                      label: issue.type,
                      relatedIds: [
                        makeEntryZoneId(symbol, timeframe),
                        makeRiskZoneId(symbol, timeframe),
                        makeTargetZoneId(symbol, timeframe),
                      ],
                      meta: issue,
                    })
                  }
                  className={`block w-full rounded-lg border px-3 py-2 text-left text-xs transition-all hover:bg-white/5 ${
                    issue.severity === 'critical'
                      ? 'bg-red-500/10 text-red-300 border-red-500/20'
                      : issue.severity === 'warning'
                      ? 'bg-yellow-500/10 text-yellow-300 border-yellow-500/20'
                      : 'bg-white/5 text-gray-300 border-white/10'
                  }`}
                >
                  <div className="font-medium">{issue.type}</div>
                  <div className="mt-0.5">{issue.message}</div>
                </button>
              );
            })
          ) : (
            <span className="text-xs text-gray-500">No validation issues</span>
          )}
        </div>
      </div>
    </PanelShell>
  );
}
