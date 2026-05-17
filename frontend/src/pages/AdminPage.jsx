/**
 * Admin UI (P3) — Editable Thresholds + Versioning + Freeze Mode
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Settings, Save, RotateCcw, Lock, Unlock, AlertTriangle, Check
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const THRESHOLD_GROUPS = [
  {
    key: 'signals',
    label: 'Signals',
    fields: [
      { key: 'executionThreshold', label: 'Execution threshold', tooltip: 'Min execution score for directional action', min: 0.1, max: 1, step: 0.05 },
      { key: 'lowActivityThreshold', label: 'Low activity threshold', tooltip: 'Below this, execution is LOW mode', min: 0.05, max: 0.5, step: 0.05 },
    ],
  },
  {
    key: 'decision',
    label: 'Decision',
    fields: [
      { key: 'holdThreshold', label: 'Hold threshold', tooltip: 'Min edge for HOLD action', min: 0.1, max: 0.5, step: 0.05 },
      { key: 'edgeMin', label: 'Edge minimum', tooltip: 'Below this, LOW_EDGE gate activates', min: 0.1, max: 0.5, step: 0.05 },
      { key: 'buyThreshold', label: 'Buy/Sell threshold', tooltip: 'Min direction for BUY/SELL action', min: 0.2, max: 0.8, step: 0.05 },
    ],
  },
  {
    key: 'macroGates',
    label: 'Macro Gates',
    danger: true,
    fields: [
      { key: 'riskOffBlockThreshold', label: 'Risk-Off block', tooltip: 'Above this, RISK_OFF gate blocks actions', min: 0.5, max: 0.95, step: 0.05 },
      { key: 'structuralRiskBlock', label: 'Structural risk block', tooltip: 'Above this, HIGH_STRUCTURAL_RISK gate', min: 50, max: 100, step: 5 },
      { key: 'extremeFearThreshold', label: 'Extreme fear F&G', tooltip: 'Below this, EXTREME_FEAR gate', min: 5, max: 30, step: 1 },
      { key: 'fearRecoveryTarget', label: 'Fear recovery target', tooltip: 'F&G target to clear fear gate', min: 20, max: 50, step: 5 },
    ],
  },
  {
    key: 'altOutlook',
    label: 'Alt Outlook',
    fields: [
      { key: 'bullishThreshold', label: 'Bullish threshold', tooltip: 'Above this altScore → ALT_BULLISH', min: 0.1, max: 0.6, step: 0.05 },
      { key: 'bearishThreshold', label: 'Bearish threshold', tooltip: 'Below this altScore → ALT_BEARISH', min: -0.6, max: -0.1, step: 0.05 },
    ],
  },
];

function SavedBadge({ show }) {
  if (!show) return null;
  return (
    <span className="inline-flex items-center gap-1 text-badge px-2 py-0.5 rounded-full animate-pulse"
      style={{ background: 'rgba(22,163,74,0.08)', color: '#16a34a' }}>
      <Check className="w-3 h-3" /> Saved
    </span>
  );
}

export default function AdminPage() {
  const [config, setConfig] = useState(null);
  const [defaults, setDefaults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [savedGroup, setSavedGroup] = useState(null);
  const [freezeReason, setFreezeReason] = useState('');

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/admin/config`);
      const json = await res.json();
      if (json.ok) {
        setConfig(json.config);
        setDefaults(json.defaults);
      }
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  const handleChange = (group, field, value) => {
    setConfig(prev => ({
      ...prev,
      [group]: { ...prev[group], [field]: parseFloat(value) },
    }));
  };

  const handleSave = async (groupKey) => {
    try {
      await fetch(`${API}/api/admin/config`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [groupKey]: config[groupKey] }),
      });
      setSavedGroup(groupKey);
      setTimeout(() => setSavedGroup(null), 1500);
    } catch {}
  };

  const handleReset = (groupKey) => {
    if (defaults?.[groupKey]) {
      setConfig(prev => ({ ...prev, [groupKey]: { ...defaults[groupKey] } }));
    }
  };

  const handleFreeze = async () => {
    await fetch(`${API}/api/admin/freeze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: freezeReason || 'Manual freeze' }),
    });
    fetchConfig();
  };

  const handleUnfreeze = async () => {
    await fetch(`${API}/api/admin/unfreeze`, { method: 'POST' });
    fetchConfig();
  };

  if (loading) return <div className="p-8 text-center text-hint">Loading config...</div>;
  if (!config) return <div className="p-8 text-center text-hint" style={{ color: '#dc2626' }}>Failed to load config</div>;

  return (
    <div className="max-w-3xl mx-auto px-6 py-6" data-testid="admin-page">
      <div className="flex items-center gap-3 mb-6">
        <Settings className="w-5 h-5" style={{ color: '#6366f1' }} />
        <h1 className="text-lg font-bold" style={{ color: '#0f172a' }}>System Administration</h1>
        <span className="text-badge px-2 py-0.5 rounded-full" style={{ background: '#f1f5f9', color: '#94a3b8' }}>
          {config.profile}
        </span>
      </div>

      {/* Freeze Mode */}
      <div className="rounded-2xl p-5 mb-6" data-testid="admin-freeze"
        style={{ background: config.frozen ? 'rgba(220,38,38,0.03)' : '#fff', border: `1px solid ${config.frozen ? '#fecaca' : '#e2e8f0'}` }}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            {config.frozen ? <Lock className="w-4 h-4" style={{ color: '#dc2626' }} /> : <Unlock className="w-4 h-4" style={{ color: '#16a34a' }} />}
            <span className="text-card-title">Freeze Mode</span>
            {config.frozen && <span className="text-badge px-2 py-0.5 rounded" style={{ background: 'rgba(220,38,38,0.08)', color: '#dc2626' }}>ACTIVE</span>}
          </div>
          {config.frozen ? (
            <button onClick={handleUnfreeze} data-testid="unfreeze-btn"
              className="px-3 py-1.5 rounded-lg text-hint font-bold transition-colors"
              style={{ background: 'rgba(22,163,74,0.08)', color: '#16a34a' }}>
              Unfreeze
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <input value={freezeReason} onChange={e => setFreezeReason(e.target.value)}
                placeholder="Reason..."
                className="px-2 py-1 rounded-lg text-hint w-40 outline-none"
                style={{ background: '#f8fafc', border: '1px solid #e2e8f0', color: '#475569' }} />
              <button onClick={handleFreeze} data-testid="freeze-btn"
                className="px-3 py-1.5 rounded-lg text-hint font-bold transition-colors"
                style={{ background: 'rgba(220,38,38,0.06)', color: '#dc2626' }}>
                Freeze
              </button>
            </div>
          )}
        </div>
        {config.frozen && (
          <div className="text-hint" style={{ color: '#64748b' }}>
            Frozen at: {config.frozenAt} | Reason: {config.frozenReason}
          </div>
        )}
        <div className="text-hint mt-1" style={{ color: '#94a3b8' }}>
          When frozen, all endpoints return the last cached snapshot. No recalculation.
        </div>
      </div>

      {/* Threshold Groups */}
      <div className="space-y-5">
        {THRESHOLD_GROUPS.map(group => (
          <div key={group.key} className="rounded-2xl p-5" data-testid={`admin-group-${group.key}`}
            style={{ background: '#fff', border: `1px solid ${group.danger ? '#fecaca' : '#e2e8f0'}` }}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="text-card-title">{group.label}</span>
                {group.danger && <AlertTriangle className="w-3 h-3" style={{ color: '#dc2626' }} />}
                <SavedBadge show={savedGroup === group.key} />
              </div>
              <div className="flex gap-2">
                <button onClick={() => handleReset(group.key)} data-testid={`reset-${group.key}`}
                  className="p-1.5 rounded-lg transition-colors"
                  onMouseEnter={e => e.currentTarget.style.background = '#f1f5f9'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  title="Reset to defaults">
                  <RotateCcw className="w-3.5 h-3.5" style={{ color: '#94a3b8' }} />
                </button>
                <button onClick={() => handleSave(group.key)} data-testid={`save-${group.key}`}
                  className="px-3 py-1 rounded-lg text-badge flex items-center gap-1 transition-colors"
                  style={{ background: 'rgba(99,102,241,0.08)', color: '#6366f1' }}>
                  <Save className="w-3 h-3" /> Save
                </button>
              </div>
            </div>
            <div className="space-y-4">
              {group.fields.map(field => {
                const val = config[group.key]?.[field.key] ?? 0;
                const defVal = defaults?.[group.key]?.[field.key];
                const isChanged = defVal !== undefined && Math.abs(val - defVal) > 0.001;
                return (
                  <div key={field.key}>
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className="text-hint font-medium" style={{ color: '#475569' }}>{field.label}</span>
                        {isChanged && <span className="w-1.5 h-1.5 rounded-full" style={{ background: '#f59e0b' }} title="Modified" />}
                      </div>
                      <div className="flex items-center gap-2">
                        <input type="number" value={val} step={field.step} min={field.min} max={field.max}
                          onChange={e => handleChange(group.key, field.key, e.target.value)}
                          className="w-[70px] text-right font-bold px-2 py-1 rounded-lg outline-none tabular-nums"
                          style={{ background: '#f8fafc', border: '1px solid #e2e8f0', color: '#0f172a', fontSize: 14 }} />
                        {defVal !== undefined && (
                          <span className="text-hint tabular-nums" style={{ color: '#cbd5e1' }}>def: {defVal}</span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <input type="range" value={val} step={field.step} min={field.min} max={field.max}
                        onChange={e => handleChange(group.key, field.key, e.target.value)}
                        className="flex-1 h-1 rounded-full appearance-none cursor-pointer"
                        style={{ background: '#e2e8f0', accentColor: group.danger ? '#dc2626' : '#6366f1' }} />
                    </div>
                    <div className="text-hint mt-0.5" style={{ color: '#cbd5e1' }}>{field.tooltip}</div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
