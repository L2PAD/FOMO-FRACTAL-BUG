/**
 * OnChain V2 — Guardrails Panel (O9.5 UI)
 * =========================================
 * 
 * Institutional-grade governance status display.
 * Uses /final/:symbol as single source of truth.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Card } from './Card';
import { CheckCircle, XCircle, AlertTriangle, Clock, Database, Activity, TrendingUp, Copy, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

interface FinalFlag {
  code: string;
  severity: 'CRITICAL' | 'WARN' | 'INFO';
  domain: 'DATA' | 'DRIFT' | 'MODEL' | 'GOV' | 'POST';
}

interface FinalOutput {
  symbol: string;
  t0: number;
  window: string;
  finalScore: number;
  finalConfidence: number;
  finalState: string;
  finalStateReason: string;
  dataState: string;
  drivers: string[];
  flags: FinalFlag[];
  governance: {
    policyVersion: string;
    guardrailState: string;
    guardrailAction: string;
    guardrailActionReasons: string[];
    psi: number;
    sampleCount30d: number;
    emaWindow: number;
    emaApplied: boolean;
    confidenceModifier: number;
    confidenceCapped: boolean;
  };
  raw: {
    score: number;
    confidence: number;
    state: string;
  };
  processedAt: number;
}

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

const STATE_COLORS: Record<string, string> = {
  HEALTHY: 'bg-emerald-500',
  WARN: 'bg-amber-500',
  DEGRADED: 'bg-orange-500',
  CRITICAL: 'bg-red-500',
  FROZEN: 'bg-slate-500',
};

const STATE_BG: Record<string, string> = {
  HEALTHY: 'bg-emerald-50 border-emerald-200',
  WARN: 'bg-amber-50 border-amber-200',
  DEGRADED: 'bg-orange-50 border-orange-200',
  CRITICAL: 'bg-red-50 border-red-200',
  FROZEN: 'bg-slate-50 border-slate-200',
};

const ACTION_LABELS: Record<string, { label: string; color: string }> = {
  NONE: { label: 'ALLOW', color: 'text-emerald-700 bg-emerald-100' },
  DOWNWEIGHT: { label: 'DOWNWEIGHT', color: 'text-amber-700 bg-amber-100' },
  FORCE_SAFE: { label: 'FORCE SAFE', color: 'text-red-700 bg-red-100' },
  BLOCK_OUTPUT: { label: 'BLOCKED', color: 'text-red-700 bg-red-200' },
  FREEZE: { label: 'FROZEN', color: 'text-slate-700 bg-slate-200' },
};

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: 'bg-red-100 text-red-700 border-red-200',
  WARN: 'bg-amber-100 text-amber-700 border-amber-200',
  INFO: 'bg-slate-100 text-slate-600 border-slate-200',
};

function formatAge(ms: number): string {
  const hours = Math.floor(ms / 3600000);
  if (hours < 1) return 'Fresh';
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h ago`;
}

// ═══════════════════════════════════════════════════════════════
// GATE ICON
// ═══════════════════════════════════════════════════════════════

function GateIcon({ ok, warning }: { ok: boolean; warning?: boolean }) {
  if (warning) {
    return <AlertTriangle className="w-4 h-4 text-amber-500" />;
  }
  return ok 
    ? <CheckCircle className="w-4 h-4 text-emerald-500" /> 
    : <XCircle className="w-4 h-4 text-red-500" />;
}

// ═══════════════════════════════════════════════════════════════
// COMPONENT
// ═══════════════════════════════════════════════════════════════

interface GuardrailsPanelV2Props {
  symbol?: string;
  onSymbolChange?: (symbol: string) => void;
}

export function GuardrailsPanelV2({ symbol = 'ETH', onSymbolChange }: GuardrailsPanelV2Props) {
  const [output, setOutput] = useState<FinalOutput | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState(symbol);

  const fetchFinal = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/v10/onchain-v2/final/${selectedSymbol}`);
      const data = await res.json();
      if (data.ok) {
        setOutput(data.output);
      } else {
        setError(data.error || 'Failed to fetch');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Network error');
    } finally {
      setLoading(false);
    }
  }, [selectedSymbol]);

  useEffect(() => {
    fetchFinal();
    const interval = setInterval(fetchFinal, 30000); // Auto-refresh every 30s
    return () => clearInterval(interval);
  }, [fetchFinal]);

  const handleCopyJson = () => {
    if (output) {
      navigator.clipboard.writeText(JSON.stringify(output, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleSymbolChange = (newSymbol: string) => {
    setSelectedSymbol(newSymbol.toUpperCase());
    onSymbolChange?.(newSymbol.toUpperCase());
  };

  // Render loading/error states
  if (loading && !output) {
    return (
      <Card title="Guardrails Status">
        <div className="flex items-center justify-center py-8 text-slate-400">
          <RefreshCw className="w-5 h-5 animate-spin mr-2" />
          Loading...
        </div>
      </Card>
    );
  }

  if (error && !output) {
    return (
      <Card title="Guardrails Status">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          {error}
          <button onClick={fetchFinal} className="ml-2 underline">Retry</button>
        </div>
      </Card>
    );
  }

  if (!output) return null;

  const { governance, flags, dataState, finalState, finalStateReason } = output;
  const dataAge = Date.now() - output.t0;
  const action = ACTION_LABELS[governance.guardrailAction] || ACTION_LABELS.NONE;

  // Compute gate statuses
  const providerOk = !flags.some(f => f.code === 'PROVIDER_UNHEALTHY');
  const freshnessOk = dataState === 'OK';
  const freshnessWarn = dataState === 'STALE';
  const samplesOk = governance.sampleCount30d >= 50;
  const samplesWarn = governance.sampleCount30d > 0 && governance.sampleCount30d < 50;
  const psiOk = governance.psi < 0.15;
  const psiWarn = governance.psi >= 0.15 && governance.psi < 0.30;
  const emaActive = governance.emaApplied;

  return (
    <Card 
      title="Guardrails Status"
      action={
        <div className="flex items-center gap-2">
          <select
            value={selectedSymbol}
            onChange={(e) => handleSymbolChange(e.target.value)}
            className="text-sm font-normal bg-slate-100 border border-slate-200 rounded px-2 py-1"
          >
            <option value="ETH">ETH</option>
            <option value="BTC">BTC</option>
            <option value="SOL">SOL</option>
            <option value="ARB">ARB</option>
          </select>
          <button
            onClick={fetchFinal}
            className="p-1.5 hover:bg-slate-100 rounded transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 text-slate-500 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={handleCopyJson}
            className="p-1.5 hover:bg-slate-100 rounded transition-colors"
            title="Copy JSON"
          >
            <Copy className={`w-4 h-4 ${copied ? 'text-emerald-500' : 'text-slate-500'}`} />
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        {/* Main State Banner */}
        <div className={`rounded-lg border p-4 ${STATE_BG[governance.guardrailState] || 'bg-slate-50 border-slate-200'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${STATE_COLORS[governance.guardrailState] || 'bg-slate-400'}`} />
              <div>
                <div className="font-semibold text-slate-800">
                  {governance.guardrailState}
                </div>
                <div className="text-xs text-slate-500">Module State</div>
              </div>
            </div>
            <div className={`px-3 py-1.5 rounded-full text-sm font-medium ${action.color}`}>
              {action.label}
            </div>
          </div>
          
          {/* Reason */}
          <div className="mt-3 text-sm text-slate-600">
            <span className="font-medium">Reason:</span>{' '}
            {finalStateReason.replace(/_/g, ' ')}
          </div>
        </div>

        {/* Key Gates Grid */}
        <div className="grid grid-cols-5 gap-2">
          {/* Provider */}
          <div className="p-2 rounded-lg bg-slate-50 border border-slate-100">
            <div className="flex items-center gap-1.5 mb-1">
              <GateIcon ok={providerOk} />
              <span className="text-xs text-slate-500">Provider</span>
            </div>
            <div className="text-sm font-medium text-slate-700">
              {providerOk ? 'Healthy' : 'Down'}
            </div>
          </div>

          {/* Freshness */}
          <div className="p-2 rounded-lg bg-slate-50 border border-slate-100">
            <div className="flex items-center gap-1.5 mb-1">
              <GateIcon ok={freshnessOk} warning={freshnessWarn} />
              <span className="text-xs text-slate-500">Freshness</span>
            </div>
            <div className="text-sm font-medium text-slate-700">
              {dataState === 'OK' ? 'Fresh' : dataState}
            </div>
            <div className="text-xs text-slate-400">{formatAge(dataAge)}</div>
          </div>

          {/* Samples */}
          <div className="p-2 rounded-lg bg-slate-50 border border-slate-100">
            <div className="flex items-center gap-1.5 mb-1">
              <GateIcon ok={samplesOk} warning={samplesWarn} />
              <span className="text-xs text-slate-500">Samples</span>
            </div>
            <div className="text-sm font-medium text-slate-700 tabular-nums">
              {governance.sampleCount30d.toLocaleString()}
            </div>
            {governance.confidenceCapped && (
              <div className="text-xs text-amber-600">capped</div>
            )}
          </div>

          {/* PSI Drift */}
          <div className="p-2 rounded-lg bg-slate-50 border border-slate-100">
            <div className="flex items-center gap-1.5 mb-1">
              <GateIcon ok={psiOk} warning={psiWarn} />
              <span className="text-xs text-slate-500">PSI Drift</span>
            </div>
            <div className="text-sm font-medium text-slate-700 tabular-nums">
              {governance.psi.toFixed(3)}
            </div>
            <div className="text-xs text-slate-400">
              {governance.psi < 0.15 ? 'OK' : governance.psi < 0.30 ? 'WARN' : 'HIGH'}
            </div>
          </div>

          {/* EMA */}
          <div className="p-2 rounded-lg bg-slate-50 border border-slate-100">
            <div className="flex items-center gap-1.5 mb-1">
              <Activity className={`w-4 h-4 ${emaActive ? 'text-emerald-500' : 'text-slate-400'}`} />
              <span className="text-xs text-slate-500">EMA</span>
            </div>
            <div className="text-sm font-medium text-slate-700">
              {emaActive ? 'Active' : 'Warmup'}
            </div>
            <div className="text-xs text-slate-400">×{governance.confidenceModifier}</div>
          </div>
        </div>

        {/* Flags */}
        {flags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {flags.map((flag, i) => (
              <span
                key={i}
                className={`text-xs px-2 py-0.5 rounded-full border ${SEVERITY_COLORS[flag.severity]}`}
              >
                {flag.code}
              </span>
            ))}
          </div>
        )}

        {/* Details Expander */}
        <button
          onClick={() => setDetailsOpen(!detailsOpen)}
          className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700"
        >
          {detailsOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          {detailsOpen ? 'Hide' : 'Show'} Details
        </button>

        {detailsOpen && (
          <div className="space-y-3 pt-2 border-t border-slate-100">
            {/* Action Reasons */}
            {governance.guardrailActionReasons.length > 0 && (
              <div>
                <div className="text-xs font-medium text-slate-500 mb-1">Action Reasons</div>
                <div className="flex flex-wrap gap-1">
                  {governance.guardrailActionReasons.map((reason, i) => (
                    <span key={i} className="text-xs bg-slate-100 px-2 py-0.5 rounded">
                      {reason}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Final Output */}
            <div className="grid grid-cols-3 gap-3">
              <div>
                <div className="text-xs font-medium text-slate-500 mb-1">Final Score</div>
                <div className="text-lg font-semibold text-slate-800 tabular-nums">
                  {output.finalScore.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-xs font-medium text-slate-500 mb-1">Final Confidence</div>
                <div className="text-lg font-semibold text-slate-800 tabular-nums">
                  {(output.finalConfidence * 100).toFixed(0)}%
                </div>
              </div>
              <div>
                <div className="text-xs font-medium text-slate-500 mb-1">Final State</div>
                <div className="text-lg font-semibold text-slate-800">
                  {finalState}
                </div>
              </div>
            </div>

            {/* Raw vs Final */}
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="bg-slate-50 rounded p-2">
                <div className="font-medium text-slate-500 mb-1">Raw</div>
                <div>Score: {output.raw.score.toFixed(2)}</div>
                <div>Conf: {(output.raw.confidence * 100).toFixed(0)}%</div>
                <div>State: {output.raw.state}</div>
              </div>
              <div className="bg-emerald-50 rounded p-2">
                <div className="font-medium text-slate-500 mb-1">Final</div>
                <div>Score: {output.finalScore.toFixed(2)}</div>
                <div>Conf: {(output.finalConfidence * 100).toFixed(0)}%</div>
                <div>State: {finalState}</div>
              </div>
            </div>

            {/* Drivers */}
            {output.drivers.length > 0 && (
              <div>
                <div className="text-xs font-medium text-slate-500 mb-1">Drivers</div>
                <div className="flex flex-wrap gap-1">
                  {output.drivers.map((d, i) => (
                    <span key={i} className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">
                      {d}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Meta */}
            <div className="text-xs text-slate-400 pt-2 border-t border-slate-100">
              Policy: {governance.policyVersion} • 
              Processed: {new Date(output.processedAt).toLocaleTimeString()}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
