/**
 * MetaBrainContext — Market context and system parameters (PROD-GAP-1.8 repoint).
 *
 * If parent passes `data` prop, it's used as-is (legacy behaviour, fully backward compatible).
 * Otherwise the component self-fetches canonical verdict from /api/trading/verdict/{symbol}
 * and maps it to the same shape, so Coverage finally reads 4/5 (or whatever runtime returns),
 * never the stale 0/4 from legacy endpoints.
 */
import React, { useEffect, useState } from 'react';
import { Activity, BarChart3, Gauge, Shield } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

function entropyLabel(e) {
  if (e < 0.3) return 'Low';
  if (e < 0.7) return 'Medium';
  return 'High';
}

// ── Canonical adapter: trading verdict → MetaBrainContext shape ──────────
function adaptVerdictToContext(verdict) {
  if (!verdict) return null;
  const alignment = verdict.alignment || {};
  const active = Array.isArray(alignment.activeModules) ? alignment.activeModules : [];
  const total =
    alignment.totalModules ||
    ((Array.isArray(alignment.degradedModules) ? alignment.degradedModules.length : 0) +
      (Array.isArray(alignment.abstainedModules) ? alignment.abstainedModules.length : 0) +
      active.length) ||
    5;

  // Use longVotes / shortVotes / waitVotes to estimate disagreement
  const longV  = alignment.longVotes  || 0;
  const shortV = alignment.shortVotes || 0;
  const waitV  = alignment.waitVotes  || 0;
  const totalVotes = longV + shortV + waitV;
  const directionalVotes = longV + shortV;
  const disagreeRate = totalVotes > 0 ? Math.min(longV, shortV) / totalVotes : 0;
  const entropy = totalVotes > 0 ? 1 - (Math.max(longV, shortV, waitV) / totalVotes) : 0.5;

  return {
    regime: verdict.regime || (verdict.action === 'WAIT' ? 'neutral' : verdict.action?.toLowerCase()) || '—',
    coverage: {
      active: active.length,
      total,
      pct: total > 0 ? (active.length / total) * 100 : 0,
    },
    moduleSignals: active.map(m => ({ module: m, vote: alignment[m] || 'UNKNOWN' })),
    metaConfidenceDetail: {
      entropy,
      disagreeRate,
      confidence: verdict.confidence || 0,
    },
    // Pass-through for diagnostics
    _verdict: verdict,
  };
}

export default function MetaBrainContext({ data: dataProp, symbol = 'BTC' }) {
  const [data, setData] = useState(dataProp || null);
  const [loading, setLoading] = useState(!dataProp);

  useEffect(() => {
    if (dataProp) { setData(dataProp); return; }
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const r = await fetch(`${API}/api/trading/verdict/${symbol}`, { credentials: 'include' });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const verdict = await r.json();
        if (!cancelled) setData(adaptVerdictToContext(verdict));
      } catch (e) {
        if (!cancelled) setData(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [dataProp, symbol]);

  if (loading && !data) {
    return (
      <div className="rounded-2xl border border-gray-200 bg-white p-5 animate-pulse" data-testid="meta-brain-context-loading">
        <p className="text-[10px] uppercase tracking-wider text-gray-400 font-medium mb-4">Market Context</p>
        <div className="grid grid-cols-4 gap-3">
          {[1,2,3,4].map(i => <div key={i} className="h-12 bg-gray-100 rounded" />)}
        </div>
      </div>
    );
  }
  if (!data) return null;

  const mc = data.metaConfidenceDetail || {};
  const activeModules = data.moduleSignals?.length || data.coverage?.active || 0;
  const totalProviders = data.coverage?.total || 5;
  const covLabel = `${activeModules}/${totalProviders}`;

  const items = [
    { icon: Activity,  label: 'Regime',      value: data.regime || '—',                          testId: 'ctx-regime' },
    { icon: BarChart3, label: 'Coverage',    value: covLabel,                                    testId: 'ctx-coverage' },
    { icon: Gauge,     label: 'Entropy',     value: entropyLabel(mc.entropy || 0),
      sub: mc.entropy !== undefined ? mc.entropy.toFixed(2) : '',                                testId: 'ctx-entropy' },
    { icon: Shield,    label: 'Disagreement', value: mc.disagreeRate !== undefined ? `${(mc.disagreeRate * 100).toFixed(0)}%` : '—', testId: 'ctx-disagree' },
  ];

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5" data-testid="meta-brain-context">
      <p className="text-[10px] uppercase tracking-wider text-gray-400 font-medium mb-4">Market Context</p>
      <div className="grid grid-cols-4 gap-3">
        {items.map(item => {
          const Icon = item.icon;
          return (
            <div key={item.label} className="flex items-start gap-2">
              <Icon className="w-3.5 h-3.5 text-gray-300 mt-0.5 shrink-0" />
              <div>
                <p className="text-[9px] uppercase tracking-wider text-gray-400 mb-0.5">{item.label}</p>
                <p className="text-sm text-gray-900 font-medium tabular-nums" data-testid={item.testId}>{item.value}</p>
                {item.sub && <p className="text-[10px] text-gray-400 mt-0.5 tabular-nums">{item.sub}</p>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
