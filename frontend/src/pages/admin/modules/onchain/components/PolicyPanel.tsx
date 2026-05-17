import React from 'react';
import { Card } from './Card';
import { OnchainGovPolicy, OnchainGovWeights, OnchainGovThresholds, OnchainGovGuardrails } from '../lib/onchainGovernanceApi';

interface PolicyPanelProps {
  policy: OnchainGovPolicy | null;
}

function WeightsTable({ weights }: { weights: OnchainGovWeights }) {
  const rows = [
    { key: 'exchangePressureWeight', label: 'Exchange Pressure' },
    { key: 'flowScoreWeight', label: 'Flow Score' },
    { key: 'whaleActivityWeight', label: 'Whale Activity' },
    { key: 'networkHeatWeight', label: 'Network Heat' },
    { key: 'velocityWeight', label: 'Velocity' },
    { key: 'distributionSkewWeight', label: 'Distribution Skew' },
  ];

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-slate-100">
          <th className="text-left py-2 text-slate-500 font-medium">Metric</th>
          <th className="text-right py-2 text-slate-500 font-medium">Weight</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(({ key, label }) => (
          <tr key={key} className="border-b border-slate-50">
            <td className="py-2 text-slate-700">{label}</td>
            <td className="py-2 text-right tabular-nums font-mono text-slate-800">
              {((weights as any)[key] * 100).toFixed(0)}%
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function KeyValueTable({ data, keys }: { data: Record<string, any>; keys: { key: string; label: string }[] }) {
  return (
    <table className="w-full text-sm">
      <tbody>
        {keys.map(({ key, label }) => (
          <tr key={key} className="border-b border-slate-50">
            <td className="py-2 text-slate-600">{label}</td>
            <td className="py-2 text-right tabular-nums font-mono text-slate-800">
              {typeof data[key] === 'boolean' 
                ? (data[key] ? 'true' : 'false')
                : typeof data[key] === 'number' 
                  ? data[key].toFixed(2)
                  : String(data[key] ?? 'N/A')
              }
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function PolicyPanel({ policy }: PolicyPanelProps) {
  if (!policy) {
    return (
      <Card title="Current Policy">
        <div className="text-slate-500 text-sm">No active policy</div>
      </Card>
    );
  }

  const thresholdKeys = [
    { key: 'minUsableConfidence', label: 'Min Usable Confidence' },
    { key: 'strongInflow', label: 'Strong Inflow' },
    { key: 'moderateInflow', label: 'Moderate Inflow' },
    { key: 'strongOutflow', label: 'Strong Outflow' },
    { key: 'moderateOutflow', label: 'Moderate Outflow' },
    { key: 'neutralZone', label: 'Neutral Zone' },
  ];

  const guardrailKeys = [
    { key: 'providerHealthyRequired', label: 'Provider Healthy Required' },
    { key: 'minSamples30d', label: 'Min Samples 30d' },
    { key: 'driftMaxPsi', label: 'Drift Max PSI' },
    { key: 'crisisBlock', label: 'Crisis Block' },
    { key: 'maxLatencyMs', label: 'Max Latency (ms)' },
    { key: 'requireManualApproval', label: 'Require Manual Approval' },
  ];

  return (
    <Card title={`Current Policy: ${policy.name}`}>
      <div className="space-y-6">
        <div className="flex items-center gap-4 text-xs text-slate-500">
          <span>ID: <code className="bg-slate-100 px-1.5 py-0.5 rounded">{policy.id}</code></span>
          <span>Version: <code className="bg-slate-100 px-1.5 py-0.5 rounded">{policy.version}</code></span>
          <span>Status: <code className="bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded">{policy.status}</code></span>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          <div>
            <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Weights</h4>
            <WeightsTable weights={policy.weights} />
          </div>
          
          <div>
            <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Thresholds</h4>
            <KeyValueTable data={policy.thresholds} keys={thresholdKeys} />
          </div>
          
          <div>
            <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Guardrails</h4>
            <KeyValueTable data={policy.guardrails} keys={guardrailKeys} />
          </div>
        </div>
      </div>
    </Card>
  );
}
