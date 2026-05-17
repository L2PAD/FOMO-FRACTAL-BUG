/**
 * Alt Liquidity Flags
 * ====================
 * 
 * PHASE 3: Data quality flags display
 */

import React from 'react';
import { Flag, AlertTriangle, Info, AlertCircle } from 'lucide-react';
import type { LiquidityFlag, FlagSeverity } from './types';
import { severityColor } from './ui';

interface Props {
  flags: LiquidityFlag[];
}

function SeverityIcon({ severity }: { severity: FlagSeverity }) {
  const color = severityColor(severity);
  const className = "w-4 h-4";
  
  switch (severity) {
    case 'CRITICAL':
      return <AlertCircle className={className} style={{ color }} />;
    case 'DEGRADED':
      return <AlertTriangle className={className} style={{ color }} />;
    case 'WARN':
      return <AlertTriangle className={className} style={{ color }} />;
    default:
      return <Info className={className} style={{ color }} />;
  }
}

export function AltLiquidityFlags({ flags }: Props) {
  if (!flags || flags.length === 0) {
    return null;
  }

  // Sort by severity
  const sortedFlags = [...flags].sort((a, b) => {
    const order = { CRITICAL: 0, DEGRADED: 1, WARN: 2, INFO: 3 };
    return (order[a.severity] ?? 3) - (order[b.severity] ?? 3);
  });

  return (
    <div className="rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm p-5">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <Flag className="w-5 h-5 text-yellow-400" />
        <span className="text-sm font-medium text-gray-300">Data Quality Flags</span>
      </div>

      {/* Flags List */}
      <div className="space-y-2" data-testid="liquidity-flags">
        {sortedFlags.map((flag, i) => (
          <div 
            key={i}
            className="flex items-start gap-3 p-2 rounded-lg"
            style={{ 
              backgroundColor: `${severityColor(flag.severity)}10`,
              border: `1px solid ${severityColor(flag.severity)}30`,
            }}
          >
            <SeverityIcon severity={flag.severity} />
            <div className="flex-1">
              <div 
                className="text-sm font-medium"
                style={{ color: severityColor(flag.severity) }}
              >
                {flag.code}
              </div>
              {flag.message && (
                <div className="text-xs text-gray-500 mt-0.5">
                  {flag.message}
                </div>
              )}
            </div>
            <span 
              className="text-xs px-2 py-0.5 rounded-full"
              style={{ 
                backgroundColor: `${severityColor(flag.severity)}20`,
                color: severityColor(flag.severity),
              }}
            >
              {flag.severity}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
