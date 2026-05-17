/**
 * On-Chain Alert Rules Tab
 * ========================
 * Manage alert rules for on-chain entity intelligence signals.
 * CRUD: create, enable/disable, delete rules.
 * View alert history.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Bell, Plus, Trash2, ToggleLeft, ToggleRight,
  ChevronDown, ChevronUp, ExternalLink, Check,
  AlertTriangle, Layers, Activity, Zap,
  RefreshCw, Loader2, Clock, Shield,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const CHAIN_OPTIONS = [
  { id: 'ethereum', label: 'ETH' },
  { id: 'arbitrum', label: 'ARB' },
  { id: 'optimism', label: 'OP' },
  { id: 'base', label: 'BASE' },
];

const SIGNAL_TYPE_OPTIONS = [
  { id: 'CEX_INFLOW', label: 'CEX Inflow', category: 'exchange' },
  { id: 'CEX_OUTFLOW', label: 'CEX Outflow', category: 'exchange' },
  { id: 'EXCHANGE_ACTIVITY', label: 'Exchange Activity', category: 'exchange' },
  { id: 'WHALE_TRANSFER', label: 'Whale Transfer', category: 'whale' },
  { id: 'SMART_MONEY_ACTIVITY', label: 'Smart Money', category: 'entity' },
  { id: 'MM_ACTIVITY', label: 'MM Activity', category: 'entity' },
  { id: 'SETUP_CONFIRMATION', label: 'Setup Confirm', category: 'engine' },
  { id: 'FLOW_ACCELERATION', label: 'Flow Accel', category: 'engine' },
  { id: 'ACCUMULATION', label: 'Accumulation', category: 'engine' },
  { id: 'DISTRIBUTION', label: 'Distribution', category: 'engine' },
];

const SEV_COLORS: Record<string, string> = {
  EXTREME: 'text-red-400', STRONG: 'text-amber-400',
  WATCH: 'text-cyan-400', WEAK: 'text-gray-400',
};

function relTime(ts: string): string {
  if (!ts) return '';
  const m = Math.floor((Date.now() - new Date(ts).getTime()) / 60000);
  if (m < 1) return 'now';
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  return h < 24 ? `${h}h` : `${Math.floor(h / 24)}d`;
}

export function AlertRulesTab() {
  const [rules, setRules] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [view, setView] = useState<'rules' | 'history'>('rules');

  const load = useCallback(async () => {
    try {
      const [rulesRes, histRes, statsRes] = await Promise.all([
        fetch(`${API}/api/alerts/onchain/rules`),
        fetch(`${API}/api/alerts/onchain/history?limit=50`),
        fetch(`${API}/api/alerts/onchain/stats`),
      ]);
      const rJ = await rulesRes.json();
      const hJ = await histRes.json();
      const sJ = await statsRes.json();
      if (rJ.ok) setRules(rJ.rules || []);
      if (hJ.ok) setHistory(hJ.alerts || []);
      if (sJ.ok) setStats(sJ);
    } catch (e) { console.error('Alert load error:', e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggleRule = async (ruleId: string, enabled: boolean) => {
    await fetch(`${API}/api/alerts/onchain/rules/${ruleId}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: !enabled }),
    });
    load();
  };

  const deleteRule = async (ruleId: string) => {
    await fetch(`${API}/api/alerts/onchain/rules/${ruleId}`, { method: 'DELETE' });
    load();
  };

  const evaluateNow = async () => {
    setEvaluating(true);
    try {
      const res = await fetch(`${API}/api/alerts/onchain/evaluate`, { method: 'POST' });
      const j = await res.json();
      if (j.ok && j.count > 0) load();
    } catch (e) { console.error(e); }
    finally { setEvaluating(false); }
  };

  const acknowledgeAlert = async (dedupKey: string) => {
    await fetch(`${API}/api/alerts/onchain/acknowledge/${dedupKey}`, { method: 'POST' });
    load();
  };

  if (loading) return (
    <div className="flex items-center justify-center py-20" data-testid="alerts-loading">
      <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
    </div>
  );

  return (
    <div className="space-y-4 max-w-[1200px]" data-testid="alert-rules-tab">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3" data-testid="alerts-header">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center">
            <Bell className="w-5 h-5 text-amber-500" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-gray-900">Alert Rules</h2>
            <p className="text-xs text-gray-500">On-chain signal alerts with Telegram delivery</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {stats && (
            <div className="flex items-center gap-4 text-xs">
              <span className="text-gray-500">{stats.active_rules} active rules</span>
              <span className="text-amber-500 font-bold">{stats.unacknowledged} unack</span>
              <span className="text-gray-600">{stats.last_24h} / 24h</span>
            </div>
          )}
          <button onClick={evaluateNow} disabled={evaluating}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-amber-500 hover:text-amber-400 transition-colors"
            data-testid="evaluate-btn">
            {evaluating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
            Evaluate Now
          </button>
          <button onClick={() => setShowCreate(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-emerald-500 hover:text-emerald-400 transition-colors"
            data-testid="create-rule-btn">
            <Plus className="w-3 h-3" /> New Rule
          </button>
        </div>
      </div>

      {/* View Toggle */}
      <div className="flex gap-2" data-testid="view-toggle">
        <button onClick={() => setView('rules')}
          className={`px-3 py-1.5 text-[10px] font-bold rounded-lg transition-all ${
            view === 'rules' ? 'bg-[#0a0e14] text-white border border-gray-700' : 'bg-gray-800/30 text-gray-500 hover:bg-gray-800/50'
          }`} data-testid="view-rules-btn">
          Rules ({rules.length})
        </button>
        <button onClick={() => setView('history')}
          className={`px-3 py-1.5 text-[10px] font-bold rounded-lg transition-all ${
            view === 'history' ? 'bg-[#0a0e14] text-white border border-gray-700' : 'bg-gray-800/30 text-gray-500 hover:bg-gray-800/50'
          }`} data-testid="view-history-btn">
          History ({history.length})
        </button>
      </div>

      {/* Create Rule Modal */}
      {showCreate && <CreateRuleForm onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); load(); }} />}

      {/* Rules List */}
      {view === 'rules' && (
        <div className="space-y-2" data-testid="rules-list">
          {rules.length === 0 ? (
            <div className="text-center py-10 text-gray-600 text-xs">No alert rules configured</div>
          ) : rules.map(rule => (
            <RuleCard key={rule.id} rule={rule} onToggle={toggleRule} onDelete={deleteRule} />
          ))}
        </div>
      )}

      {/* Alert History */}
      {view === 'history' && (
        <div className="space-y-1.5" data-testid="alerts-history">
          {history.length === 0 ? (
            <div className="text-center py-10 text-gray-600 text-xs">No alerts fired yet</div>
          ) : history.map((alert, i) => (
            <AlertCard key={alert.dedup_key || i} alert={alert} onAcknowledge={acknowledgeAlert} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Rule Card ── */
function RuleCard({ rule, onToggle, onDelete }: { rule: any; onToggle: (id: string, en: boolean) => void; onDelete: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const cond = rule.conditions || {};

  return (
    <div className={`bg-[#0a0e14] intelligence-dark rounded-xl border ${rule.enabled ? 'border-gray-800/40' : 'border-gray-800/20 opacity-60'} overflow-hidden`} data-testid={`rule-${rule.id}`}>
      <div className="flex items-center gap-3 px-4 py-3 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <button onClick={(e) => { e.stopPropagation(); onToggle(rule.id, rule.enabled); }}
          className="shrink-0" data-testid={`rule-toggle-${rule.id}`}>
          {rule.enabled
            ? <ToggleRight className="w-5 h-5 text-emerald-400" />
            : <ToggleLeft className="w-5 h-5 text-gray-600" />}
        </button>

        <div className="flex-1 min-w-0">
          <span className="text-sm font-bold text-white">{rule.name}</span>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[9px] text-gray-500">Score &ge; {cond.min_score || 70}</span>
            <span className="text-[9px] text-gray-600">&middot;</span>
            <span className="text-[9px] text-gray-500">{cond.status || 'any'}</span>
            {(cond.signal_types || []).length > 0 && (
              <>
                <span className="text-[9px] text-gray-600">&middot;</span>
                <span className="text-[9px] text-cyan-400">{cond.signal_types.join(', ')}</span>
              </>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          {rule.fired_count > 0 && (
            <span className="text-[9px] text-amber-400">{rule.fired_count} fired</span>
          )}
          {rule.last_fired && (
            <span className="text-[8px] text-gray-600">{relTime(rule.last_fired)}</span>
          )}
          {expanded ? <ChevronUp className="w-3 h-3 text-gray-600" /> : <ChevronDown className="w-3 h-3 text-gray-600" />}
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-3 border-t border-gray-800/30 pt-2">
          <div className="grid grid-cols-3 gap-4 text-[9px]">
            <div>
              <span className="text-gray-600 uppercase font-bold">Chains</span>
              <div className="flex gap-1 mt-1 flex-wrap">
                {(cond.chains || []).map((c: string) => {
                  const label = { ethereum: 'ETH', arbitrum: 'ARB', optimism: 'OP', base: 'BASE' }[c] || c;
                  return <span key={c} className="px-1.5 py-0.5 rounded bg-gray-800/50 text-gray-400 font-bold">{label}</span>;
                })}
              </div>
            </div>
            <div>
              <span className="text-gray-600 uppercase font-bold">Min Amount</span>
              <p className="text-gray-300 mt-1">{cond.min_amount_eth > 0 ? `${cond.min_amount_eth} ETH` : 'Any'}</p>
            </div>
            <div>
              <span className="text-gray-600 uppercase font-bold">Notify</span>
              <div className="flex gap-2 mt-1">
                {rule.notify?.telegram && <span className="text-cyan-400">Telegram</span>}
                {rule.notify?.in_app && <span className="text-gray-400">In-app</span>}
              </div>
            </div>
          </div>
          <div className="flex justify-end mt-2">
            <button onClick={() => onDelete(rule.id)}
              className="flex items-center gap-1 px-2 py-1 text-[9px] text-red-400 hover:bg-red-500/10 rounded transition-colors"
              data-testid={`rule-delete-${rule.id}`}>
              <Trash2 className="w-3 h-3" /> Delete
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Alert Card ── */
function AlertCard({ alert, onAcknowledge }: { alert: any; onAcknowledge: (key: string) => void }) {
  const sevCls = SEV_COLORS[alert.severity] || SEV_COLORS.WATCH;

  return (
    <div className={`bg-[#0a0e14] intelligence-dark rounded-lg border border-gray-800/30 px-4 py-2.5 flex items-center gap-3 ${alert.acknowledged ? 'opacity-50' : ''}`}
      data-testid={`alert-${alert.dedup_key}`}>
      <div className="w-6 h-6 rounded flex items-center justify-center shrink-0">
        <AlertTriangle className={`w-3 h-3 ${sevCls}`} />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold text-white">{alert.signal_type?.replace(/_/g, ' ')}</span>
          <span className="text-[8px] font-bold text-gray-400">{alert.chain_label}</span>
          {alert.entity && (
            <span className="text-[9px] font-bold text-cyan-400">{alert.entity}</span>
          )}
          <span className={`text-[8px] font-bold ${sevCls}`}>{alert.score}</span>
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-[8px] text-gray-600">Rule: {alert.rule_name}</span>
          {alert.amount_eth > 0 && (
            <span className="text-[8px] text-amber-400">{alert.amount_eth >= 1000 ? `${(alert.amount_eth / 1000).toFixed(1)}k` : alert.amount_eth.toFixed(1)} ETH</span>
          )}
          {alert.detail && <span className="text-[8px] text-gray-500 truncate max-w-[300px]">{alert.detail}</span>}
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <span className="text-[8px] text-gray-600">{relTime(alert.fired_at)}</span>
        {alert.explorer_url && (
          <a href={alert.explorer_url} target="_blank" rel="noopener noreferrer"
            className="text-cyan-400 hover:text-cyan-300" data-testid={`alert-explorer-${alert.dedup_key}`}>
            <ExternalLink className="w-3 h-3" />
          </a>
        )}
        {!alert.acknowledged && (
          <button onClick={() => onAcknowledge(alert.dedup_key)}
            className="flex items-center gap-1 px-1.5 py-0.5 text-[8px] text-emerald-400 hover:bg-emerald-500/10 rounded transition-colors"
            data-testid={`alert-ack-${alert.dedup_key}`}>
            <Check className="w-2.5 h-2.5" /> Ack
          </button>
        )}
      </div>
    </div>
  );
}

/* ── Create Rule Form ── */
function CreateRuleForm({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState('');
  const [minScore, setMinScore] = useState(70);
  const [status, setStatus] = useState('confirmed');
  const [chains, setChains] = useState<string[]>(['ethereum', 'arbitrum', 'optimism', 'base']);
  const [signalTypes, setSignalTypes] = useState<string[]>([]);
  const [minAmountEth, setMinAmountEth] = useState(0);
  const [saving, setSaving] = useState(false);

  const toggleChain = (c: string) => setChains(prev => prev.includes(c) ? prev.filter(x => x !== c) : [...prev, c]);
  const toggleType = (t: string) => setSignalTypes(prev => prev.includes(t) ? prev.filter(x => x !== t) : [...prev, t]);

  const save = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/alerts/onchain/rules`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          enabled: true,
          conditions: {
            min_score: minScore,
            status,
            chains,
            signal_types: signalTypes,
            min_amount_eth: minAmountEth,
          },
          notify: { telegram: true, in_app: true },
        }),
      });
      const j = await res.json();
      if (j.ok) onCreated();
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  return (
    <div className="bg-[#0a0e14] intelligence-dark rounded-xl border border-gray-700 p-5 space-y-4" data-testid="create-rule-form">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-white">New Alert Rule</h3>
        <button onClick={onClose} className="text-gray-600 hover:text-gray-400 text-xs">&times; Close</button>
      </div>

      <div>
        <label className="text-[9px] text-gray-500 font-bold uppercase block mb-1">Rule Name</label>
        <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Large Binance Outflow"
          className="w-full bg-gray-900/50 border border-gray-800 rounded px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/40"
          data-testid="rule-name-input" />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="text-[9px] text-gray-500 font-bold uppercase block mb-1">Min Score</label>
          <input type="number" value={minScore} onChange={e => setMinScore(Number(e.target.value))} min={0} max={100}
            className="w-full bg-gray-900/50 border border-gray-800 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500/40"
            data-testid="rule-min-score" />
        </div>
        <div>
          <label className="text-[9px] text-gray-500 font-bold uppercase block mb-1">Status</label>
          <select value={status} onChange={e => setStatus(e.target.value)}
            className="w-full bg-gray-900/50 border border-gray-800 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500/40"
            data-testid="rule-status-select">
            <option value="confirmed">Confirmed</option>
            <option value="forming">Forming</option>
            <option value="">Any</option>
          </select>
        </div>
        <div>
          <label className="text-[9px] text-gray-500 font-bold uppercase block mb-1">Min Amount (ETH)</label>
          <input type="number" value={minAmountEth} onChange={e => setMinAmountEth(Number(e.target.value))} min={0}
            className="w-full bg-gray-900/50 border border-gray-800 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500/40"
            data-testid="rule-min-amount" />
        </div>
      </div>

      <div>
        <label className="text-[9px] text-gray-500 font-bold uppercase block mb-1">Chains</label>
        <div className="flex gap-2 flex-wrap">
          {CHAIN_OPTIONS.map(c => (
            <button key={c.id} onClick={() => toggleChain(c.id)}
              className={`px-2.5 py-1 text-[9px] font-bold rounded transition-all ${
                chains.includes(c.id) ? 'bg-cyan-500/15 text-cyan-400' : 'bg-gray-800/30 text-gray-500 hover:bg-gray-800/50'
              }`} data-testid={`rule-chain-${c.id}`}>
              {c.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="text-[9px] text-gray-500 font-bold uppercase block mb-1">Signal Types (empty = all)</label>
        <div className="flex gap-1.5 flex-wrap">
          {SIGNAL_TYPE_OPTIONS.map(t => (
            <button key={t.id} onClick={() => toggleType(t.id)}
              className={`px-2 py-1 text-[8px] font-bold rounded transition-all ${
                signalTypes.includes(t.id) ? 'bg-amber-500/15 text-amber-400' : 'bg-gray-800/30 text-gray-500 hover:bg-gray-800/50'
              }`} data-testid={`rule-type-${t.id}`}>
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex justify-end gap-3">
        <button onClick={onClose} className="px-4 py-2 text-xs text-gray-500 hover:text-gray-300 transition-colors">Cancel</button>
        <button onClick={save} disabled={saving || !name.trim()}
          className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/15 rounded-lg disabled:opacity-50 transition-colors"
          data-testid="rule-save-btn">
          {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
          Create Rule
        </button>
      </div>
    </div>
  );
}

export default AlertRulesTab;
