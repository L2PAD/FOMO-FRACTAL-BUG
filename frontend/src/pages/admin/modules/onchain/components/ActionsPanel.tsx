import React, { useState } from 'react';
import { Card } from './Card';
import { dryRun, proposePolicy, applyPolicy, DryRunResult } from '../lib/onchainGovernanceApi';

interface ActionsPanelProps {
  onRefresh: () => void;
}

const DEFAULT_DRAFT = {
  name: "New Policy",
  version: "1.1.0",
  description: "Policy draft",
  weights: {
    exchangePressureWeight: 0.35,
    flowScoreWeight: 0.25,
    whaleActivityWeight: 0.20,
    networkHeatWeight: 0.10,
    velocityWeight: 0.05,
    distributionSkewWeight: 0.05
  },
  thresholds: {
    minUsableConfidence: 0.40,
    strongInflow: 0.30,
    moderateInflow: 0.15,
    strongOutflow: -0.30,
    moderateOutflow: -0.15,
    neutralZone: 0.10
  },
  guardrails: {
    providerHealthyRequired: true,
    minSamples30d: 200,
    driftMaxPsi: 0.20,
    crisisBlock: true,
    maxLatencyMs: 5000,
    requireManualApproval: true
  }
};

export function ActionsPanel({ onRefresh }: ActionsPanelProps) {
  const [draft, setDraft] = useState(JSON.stringify(DEFAULT_DRAFT, null, 2));
  const [applyPolicyId, setApplyPolicyId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [dryRunResult, setDryRunResult] = useState<DryRunResult | null>(null);

  const parseDraft = () => {
    try {
      return JSON.parse(draft);
    } catch {
      throw new Error('Invalid JSON format');
    }
  };

  const handleDryRun = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);
    setDryRunResult(null);
    
    try {
      const parsed = parseDraft();
      const res = await dryRun({
        weights: parsed.weights,
        thresholds: parsed.thresholds,
        guardrails: parsed.guardrails,
      });
      
      if (res.ok) {
        setDryRunResult(res.result);
        setSuccess('Dry run completed');
      } else {
        setError('Dry run failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handlePropose = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);
    
    try {
      const parsed = parseDraft();
      const res = await proposePolicy(parsed);
      
      if (res.ok) {
        setSuccess(`Policy proposed: ${res.policy.id}`);
        setApplyPolicyId(res.policy.id);
        onRefresh();
      } else {
        setError('Propose failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleApply = async () => {
    if (!applyPolicyId.trim()) {
      setError('Enter policy ID');
      return;
    }
    
    setLoading(true);
    setError(null);
    setSuccess(null);
    
    try {
      const res = await applyPolicy(applyPolicyId.trim());
      
      if (res.ok) {
        setSuccess(res.message);
        setApplyPolicyId('');
        onRefresh();
      } else {
        setError('Apply failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="Policy Actions">
      <div className="space-y-4">
        {/* Draft Editor */}
        <div>
          <label className="text-xs font-medium text-slate-600 mb-2 block">Policy Draft (JSON)</label>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="w-full h-48 p-3 text-xs font-mono bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="{ weights: {}, thresholds: {}, guardrails: {} }"
          />
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2">
          <button
            onClick={handleDryRun}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition-colors disabled:opacity-50"
          >
            Dry Run
          </button>
          <button
            onClick={handlePropose}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium bg-blue-100 hover:bg-blue-200 text-blue-700 rounded-lg transition-colors disabled:opacity-50"
          >
            Propose
          </button>
        </div>

        {/* Apply Section */}
        <div className="pt-4 border-t border-slate-100">
          <label className="text-xs font-medium text-slate-600 mb-2 block">Apply Policy</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={applyPolicyId}
              onChange={(e) => setApplyPolicyId(e.target.value)}
              placeholder="pol_xxxxxxxx"
              className="flex-1 px-3 py-2 text-sm font-mono bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleApply}
              disabled={loading || !applyPolicyId.trim()}
              className="px-4 py-2 text-sm font-medium bg-emerald-100 hover:bg-emerald-200 text-emerald-700 rounded-lg transition-colors disabled:opacity-50"
            >
              Apply
            </button>
          </div>
        </div>

        {/* Status Messages */}
        {error && (
          <div className="p-3 bg-red-50 border border-red-100 rounded-lg text-sm text-red-700">
            {error}
          </div>
        )}
        
        {success && (
          <div className="p-3 bg-emerald-50 border border-emerald-100 rounded-lg text-sm text-emerald-700">
            {success}
          </div>
        )}

        {/* Dry Run Result */}
        {dryRunResult && (
          <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-slate-700">Dry Run Result</span>
              <span className={`text-xs px-2 py-0.5 rounded ${
                dryRunResult.wouldAllow 
                  ? 'bg-emerald-100 text-emerald-700' 
                  : 'bg-amber-100 text-amber-700'
              }`}>
                {dryRunResult.wouldAllow ? 'WOULD ALLOW' : 'WOULD BLOCK'}
              </span>
            </div>
            
            {dryRunResult.warnings.length > 0 && (
              <div className="mb-2">
                <span className="text-xs text-slate-500">Warnings:</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {dryRunResult.warnings.map((w, i) => (
                    <span key={i} className="text-xs px-2 py-0.5 bg-amber-100 text-amber-700 rounded">
                      {w}
                    </span>
                  ))}
                </div>
              </div>
            )}
            
            {Object.keys(dryRunResult.computedDeltas.weightsDelta).length > 0 && (
              <div className="text-xs text-slate-600">
                <span className="font-medium">Weight changes: </span>
                {Object.entries(dryRunResult.computedDeltas.weightsDelta).map(([k, v]) => (
                  <span key={k} className="mr-2">
                    {k}: {(v as number) > 0 ? '+' : ''}{((v as number) * 100).toFixed(0)}%
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
