/**
 * Evidence Panel
 * ===============
 * 

 */

import React from 'react';
import Card from '../Card';
import { ExchangeAdminSnapshot } from '../../types/exchangeAdmin.types';

interface EvidencePanelProps {
  snapshot: ExchangeAdminSnapshot;
}

const eventTypeColors: Record<string, string> = {
  guard_state_changed: 'bg-blue-100 text-blue-700',
  training_blocked: 'bg-red-100 text-red-700',
  baseline_created: 'bg-green-100 text-green-700',
  simulation_run_recorded: 'bg-purple-100 text-purple-700',
  freeze_blocked_action: 'bg-amber-100 text-amber-700',
  calibration_status_changed: 'bg-indigo-100 text-indigo-700',
  capital_health_computed: 'bg-emerald-100 text-emerald-700',
  drift_check_completed: 'bg-cyan-100 text-cyan-700',
};

export default function EvidencePanel({ snapshot }: EvidencePanelProps) {
  const events = snapshot.evidence ?? [];

  return (
    <Card 
      title="Evidence Log (Audit Trail)" 
      right={<span className="text-xs text-gray-500">Last 5 events</span>}
    >
      {events.length === 0 ? (
        <div className="text-sm text-gray-500 py-4 text-center">No events recorded</div>
      ) : (
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {events.slice(0, 5).map((e, i) => (
            <div key={i} className="flex items-start gap-3 py-2 ">
              <div className="text-xs text-gray-400 w-20 flex-shrink-0">
                {new Date(e.timestamp).toLocaleTimeString()}
              </div>
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                eventTypeColors[e.eventType] || 'bg-gray-100 text-gray-600'
              }`}>
                {e.eventType}
              </span>
              <div className="flex-1 text-xs text-gray-600 truncate">
                {e.payload ? JSON.stringify(e.payload).slice(0, 60) : '—'}
              </div>
              <div className="text-xs text-gray-400">
                {e.fieldsCount} fields
              </div>
            </div>
          ))}
        </div>
      )}
      
      <div className="mt-3 pt-3 text-xs text-gray-500">
        Append-only audit log • Events auto-refresh every 60s
      </div>
    </Card>
  );
}
