import React from 'react';
import { Card } from './Card';
import { StatusBadge } from './StatusBadge';
import { GuardrailsEvaluation } from '../lib/onchainGovernanceApi';

interface GuardrailsPanelProps {
  guardrails: GuardrailsEvaluation | null;
}

export function GuardrailsPanel({ guardrails }: GuardrailsPanelProps) {
  if (!guardrails) {
    return (
      <Card title="Guardrails Status">
        <div className="text-slate-500 text-sm">Loading...</div>
      </Card>
    );
  }

  const checks = [
    { 
      key: 'providerHealthy', 
      label: 'Provider Healthy', 
      value: guardrails.providerHealthy,
      display: guardrails.providerHealthy ? 'Yes' : 'No',
    },
    { 
      key: 'sampleCount30d', 
      label: 'Samples (30d)', 
      value: guardrails.sampleCount30d >= 200,
      display: guardrails.sampleCount30d.toLocaleString(),
    },
    { 
      key: 'driftPsi30d', 
      label: 'Drift PSI', 
      value: guardrails.driftPsi30d <= 0.20,
      display: guardrails.driftPsi30d.toFixed(3),
    },
    { 
      key: 'crisisFlag', 
      label: 'Crisis Flag', 
      value: !guardrails.crisisFlag,
      display: guardrails.crisisFlag ? 'ACTIVE' : 'Clear',
    },
  ];

  return (
    <Card 
      title="Guardrails Status"
      action={<StatusBadge status={guardrails.allPassed ? 'PASS' : 'BLOCK'} size="md" />}
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {checks.map(({ key, label, value, display }) => (
            <div 
              key={key} 
              className={`p-3 rounded-lg border ${
                value 
                  ? 'bg-emerald-50 border-emerald-100' 
                  : 'bg-amber-50 border-amber-100'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className={`w-2 h-2 rounded-full ${value ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                <span className="text-xs text-slate-600">{label}</span>
              </div>
              <div className={`text-sm font-semibold tabular-nums ${value ? 'text-emerald-700' : 'text-amber-700'}`}>
                {display}
              </div>
            </div>
          ))}
        </div>

        {guardrails.reasons && guardrails.reasons.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-100">
            {guardrails.reasons.map((reason, i) => (
              <span 
                key={i} 
                className="text-xs px-2.5 py-1 bg-amber-100 text-amber-700 rounded-full border border-amber-200"
              >
                {reason}
              </span>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}
