import React from 'react';
import { Card } from './Card';
import { OnchainAuditEntry } from '../lib/onchainGovernanceApi';

interface AuditPanelProps {
  entries: OnchainAuditEntry[];
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const ACTION_COLORS: Record<string, string> = {
  POLICY_ACTIVATED: 'bg-emerald-100 text-emerald-700',
  POLICY_PROPOSED: 'bg-blue-100 text-blue-700',
  POLICY_ARCHIVED: 'bg-slate-100 text-slate-600',
  GUARDRAILS_VIOLATION: 'bg-amber-100 text-amber-700',
  DECISION_MADE: 'bg-purple-100 text-purple-700',
  MANUAL_OVERRIDE: 'bg-red-100 text-red-700',
  PROVIDER_RESET: 'bg-slate-100 text-slate-600',
};

export function AuditPanel({ entries }: AuditPanelProps) {
  return (
    <Card title="Audit Log">
      {entries.length === 0 ? (
        <div className="text-slate-500 text-sm">No audit entries</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100">
                <th className="text-left py-2 px-2 text-slate-500 font-medium">Time</th>
                <th className="text-left py-2 px-2 text-slate-500 font-medium">Actor</th>
                <th className="text-left py-2 px-2 text-slate-500 font-medium">Action</th>
                <th className="text-left py-2 px-2 text-slate-500 font-medium">Policy</th>
                <th className="text-left py-2 px-2 text-slate-500 font-medium">Notes</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id} className="border-b border-slate-50 hover:bg-slate-50">
                  <td className="py-2 px-2 text-slate-600 tabular-nums whitespace-nowrap">
                    {formatTime(entry.timestamp)}
                  </td>
                  <td className="py-2 px-2 text-slate-700 font-mono text-xs">
                    {entry.actor}
                  </td>
                  <td className="py-2 px-2">
                    <span className={`text-xs px-2 py-0.5 rounded ${ACTION_COLORS[entry.action] || 'bg-slate-100 text-slate-600'}`}>
                      {entry.action}
                    </span>
                  </td>
                  <td className="py-2 px-2 text-slate-600 font-mono text-xs">
                    {entry.policyId || '-'}
                  </td>
                  <td className="py-2 px-2 text-slate-500 text-xs max-w-xs truncate">
                    {entry.notes || (entry.details ? JSON.stringify(entry.details).slice(0, 50) : '-')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
