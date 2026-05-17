/**
 * Engine Decision View — Token-first UI
 * ========================================
 * 
 * PHASE 4, Block E2: Token decision card with search,
 * action display, evidence, reasons, and deep links.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Search,
  Loader2,
  TrendingUp,
  TrendingDown,
  Minus,
  Shield,
  AlertTriangle,
  Activity,
  Check,
  ArrowRight,
  RefreshCw,
  Gauge,
  Target,
  Info,
  Zap,
  ExternalLink,
} from 'lucide-react';
import { useOnchainChain } from '../context/OnchainChainContext';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

// ── Types ──

interface DecisionData {
  ok: boolean;
  action: 'BUY' | 'REDUCE' | 'NO_TRADE';
  confidence: number;
  score: number;
  riskCap: number;
  regime: string;
  reasons: string[];
  flags: { code: string; severity: string; detail?: string }[];
  evidence: {
    trades: number;
    spanHours: number;
    pricedShare: number;
    priceSource: string;
    poolScore: number | null;
    poolStatus: string | null;
    tvlUsd: number | null;
  } | null;
  modelFeatures: Record<string, any> | null;
  links: { signalsUrl: string; assetUrl: string };
  updatedAt: string;
  dataHealth: { blocked: boolean; blockers: string[] };
  target: { symbol?: string; address?: string };
  window: string;
}

interface Suggestion {
  symbol: string;
  name: string;
  verified: boolean;
  chainId: number;
  address: string;
}

// ── Action Styling ──

const ACTION_STYLE = {
  BUY: { bg: 'bg-emerald-500', text: 'text-white', icon: TrendingUp, label: 'BUY' },
  REDUCE: { bg: 'bg-red-500', text: 'text-white', icon: TrendingDown, label: 'REDUCE' },
  NO_TRADE: { bg: 'bg-gray-200', text: 'text-gray-700', icon: Minus, label: 'NO TRADE' },
};

const SEVERITY_STYLE: Record<string, string> = {
  CRITICAL: 'bg-red-50 text-red-700',
  WARN: 'bg-amber-50 text-amber-700',
  INFO: 'bg-blue-50 text-blue-700',
};

// ── Autocomplete ──

function TokenSearch({ onSelect }: { onSelect: (symbol: string) => void }) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (query.length < 1) { setSuggestions([]); return; }
    const t = setTimeout(async () => {
      try {
        const r = await fetch(`${API_BASE}/api/tokens/suggest?q=${encodeURIComponent(query)}&limit=7`);
        const d = await r.json();
        if (d.ok) { setSuggestions(d.data || []); setShowSuggestions(true); }
      } catch {}
    }, 200);
    return () => clearTimeout(t);
  }, [query]);

  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setShowSuggestions(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  return (
    <div ref={ref} className="relative">
      <div className="flex items-center gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && query.trim()) { setShowSuggestions(false); onSelect(query.trim()); } }}
            onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
            placeholder="Enter token symbol (LINK, UNI, AAVE...)"
            className="w-full pl-10 pr-4 py-3 rounded-xl bg-white text-gray-900 placeholder-gray-400 focus:outline-none text-sm"
            data-testid="engine-search-input"
          />
        </div>
        <button
          onClick={() => { if (query.trim()) { setShowSuggestions(false); onSelect(query.trim()); } }}
          className="px-5 py-3 rounded-xl bg-blue-600 text-white font-semibold hover:bg-blue-700 transition-colors text-sm"
          data-testid="engine-search-button"
        >
          Analyze
        </button>
      </div>
      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute z-50 w-full mt-1.5 bg-white rounded-xl max-h-64 overflow-y-auto">
          {suggestions.map(s => (
            <button
              key={`${s.chainId}-${s.address}`}
              onClick={() => { onSelect(s.symbol); setShowSuggestions(false); setQuery(s.symbol); }}
              className="w-full px-4 py-2.5 flex items-center gap-3 hover:bg-blue-50 text-left "
            >
              <div className="w-7 h-7 rounded-lg bg-blue-100 flex items-center justify-center">
                <span className="text-xs font-bold text-blue-600">{s.symbol?.charAt(0)}</span>
              </div>
              <div>
                <span className="text-sm font-bold text-gray-900">{s.symbol}</span>
                {s.verified && <Check className="inline w-3.5 h-3.5 text-emerald-500 ml-1" />}
                <span className="text-xs text-gray-500 ml-2">{s.name}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main Component ──

interface EngineDecisionViewProps {
  onNavigateTab?: (tab: string, params?: Record<string, string>) => void;
}

export function EngineDecisionView({ onNavigateTab }: EngineDecisionViewProps) {
  const { chainId } = useOnchainChain();
  const [data, setData] = useState<DecisionData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [symbol, setSymbol] = useState<string | null>(null);
  const [window, setWindow] = useState<'24h' | '7d'>('7d');

  const fetchDecision = useCallback(async (sym: string) => {
    setLoading(true);
    setError(null);
    setSymbol(sym);
    try {
      const res = await fetch(`${API_BASE}/api/v10/onchain-v2/engine/decision?chainId=${chainId}&window=${window}&symbol=${encodeURIComponent(sym)}`);
      const json = await res.json();
      if (json.ok !== undefined) {
        setData(json);
      } else {
        setError(json.message || 'Failed to compute decision');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Network error');
    } finally {
      setLoading(false);
    }
  }, [window]);

  // ── Empty State ──
  if (!symbol && !loading) {
    return (
      <div className="space-y-6" data-testid="engine-decision-view">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-gray-900">Engine Decision</h2>
            <p className="text-sm text-gray-500 mt-1">Get actionable decisions for any token</p>
          </div>
          <div className="flex items-center gap-1 p-1">
            {(['24h', '7d'] as const).map(w => (
              <button key={w} onClick={() => setWindow(w)}
                className={`px-3 py-1.5 text-xs font-bold transition-colors ${window === w ? 'text-gray-900' : 'text-gray-400'}`}
              >{w}</button>
            ))}
          </div>
        </div>
        <TokenSearch onSelect={fetchDecision} />
        <div className="p-16 text-center">
          <Target className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500 font-medium">Search for a token to get an Engine decision</p>
          <p className="text-gray-400 text-sm mt-1">BUY / REDUCE / NO TRADE — based on on-chain evidence</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5" data-testid="engine-decision-view">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Engine Decision</h2>
          <p className="text-sm text-gray-500 mt-1">Token-level actionable analysis</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 p-1">
            {(['24h', '7d'] as const).map(w => (
              <button key={w} onClick={() => { setWindow(w); if (symbol) fetchDecision(symbol); }}
                className={`px-3 py-1.5 text-xs font-bold transition-colors ${window === w ? 'text-gray-900' : 'text-gray-400'}`}
              >{w}</button>
            ))}
          </div>
        </div>
      </div>

      <TokenSearch onSelect={fetchDecision} />

      {loading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          <span className="ml-3 text-gray-500">Computing decision for {symbol}...</span>
        </div>
      )}

      {error && (
        <div className="rounded-xl bg-red-50 p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-600">{error}</p>
        </div>
      )}

      {data && !loading && (
        <DecisionCard data={data} onNavigateTab={onNavigateTab} onRefresh={() => symbol && fetchDecision(symbol)} />
      )}
    </div>
  );
}

// ── Decision Card ──

function DecisionCard({ data, onNavigateTab, onRefresh }: { 
  data: DecisionData; 
  onNavigateTab?: (tab: string, params?: Record<string, string>) => void;
  onRefresh: () => void;
}) {
  const actionStyle = ACTION_STYLE[data.action];
  const ActionIcon = actionStyle.icon;
  const blocked = data.dataHealth.blocked;

  return (
    <div className="space-y-4" data-testid="engine-decision-card">
      {/* Blocked banner */}
      {blocked && (
        <div className="flex items-center gap-3 px-4 py-3 bg-red-50 rounded-xl">
          <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <div>
            <p className="text-sm font-semibold text-red-800">Decision Blocked</p>
            <p className="text-xs text-red-600">{data.dataHealth.blockers.join(' · ')}</p>
          </div>
        </div>
      )}

      {/* Main Decision Card */}
      <div className="rounded-2xl bg-white p-6" data-testid="decision-action-card">
        <div className="flex items-start justify-between mb-6">
          {/* Token + Action */}
          <div className="flex items-center gap-4">
            <div className={`w-16 h-16 rounded-2xl ${actionStyle.bg} flex items-center justify-center`}>
              <ActionIcon className={`w-8 h-8 ${actionStyle.text}`} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-2xl font-bold text-gray-900">{data.target.symbol || data.target.address?.slice(0, 10)}</span>
                <span className={`px-3 py-1 rounded-lg text-sm font-bold ${actionStyle.bg} ${actionStyle.text}`}>{actionStyle.label}</span>
              </div>
              <p className="text-sm text-gray-500 mt-0.5">{data.window} window · {data.regime} regime</p>
            </div>
          </div>
          {/* Refresh */}
          <button onClick={onRefresh} className="p-2 rounded-lg hover:bg-gray-100" data-testid="decision-refresh">
            <RefreshCw className="w-4 h-4 text-gray-400" />
          </button>
        </div>

        {/* Metrics Row */}
        <div className="grid grid-cols-4 gap-3 mb-6">
          <MetricBox label="Score" value={data.score} suffix="/100" color={data.score >= 65 ? 'text-emerald-600' : data.score <= 35 ? 'text-red-600' : 'text-gray-900'} />
          <MetricBox label="Confidence" value={`${(data.confidence * 100).toFixed(0)}%`} color={data.confidence >= 0.55 ? 'text-emerald-600' : 'text-amber-600'} />
          <MetricBox label="Risk Cap" value={`${(data.riskCap * 100).toFixed(0)}%`} color="text-blue-600" />
          <MetricBox label="Regime" value={data.regime} color="text-gray-700" />
        </div>

        {/* Reasons (Why) */}
        <div className="mb-5">
          <h3 className="text-xs uppercase tracking-wider text-gray-400 font-bold mb-2">Why</h3>
          <div className="space-y-1.5">
            {data.reasons.map((r, i) => (
              <div key={i} className="flex items-start gap-2 text-sm text-gray-700" data-testid={`decision-reason-${i}`}>
                <ArrowRight className="w-3.5 h-3.5 text-gray-400 mt-0.5 flex-shrink-0" />
                <span>{r}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Flags */}
        {data.flags.length > 0 && (
          <div className="mb-5">
            <h3 className="text-xs uppercase tracking-wider text-gray-400 font-bold mb-2">Flags</h3>
            <div className="flex flex-wrap gap-1.5">
              {data.flags.map((f, i) => (
                <span key={i} className={`text-[10px] px-2 py-0.5 rounded font-medium ${SEVERITY_STYLE[f.severity] || ''}`} title={f.detail}>
                  {f.code}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Evidence */}
        {data.evidence && (
          <div className="mb-5">
            <h3 className="text-xs uppercase tracking-wider text-gray-400 font-bold mb-2">Evidence</h3>
            <div className="grid grid-cols-5 gap-2">
              <EvidenceBox label="Trades" value={data.evidence.trades.toLocaleString()} />
              <EvidenceBox label="Span" value={`${data.evidence.spanHours.toFixed(1)}h`} />
              <EvidenceBox label="Priced" value={`${(data.evidence.pricedShare * 100).toFixed(0)}%`} />
              <EvidenceBox label="Source" value={data.evidence.priceSource} />
              <EvidenceBox label="Pool" value={data.evidence.poolStatus || 'N/A'} />
            </div>
          </div>
        )}

        {/* Deep Links */}
        <div className="flex items-center gap-2 pt-4">
          <button
            onClick={() => onNavigateTab?.('signals', { token: data.target.symbol || '' })}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm transition-colors"
            data-testid="decision-link-signals"
          >
            <Zap className="w-3.5 h-3.5" /> Open in Signals
          </button>
          <button
            onClick={() => onNavigateTab?.('assets', { token: data.target.symbol || '' })}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm transition-colors"
            data-testid="decision-link-assets"
          >
            <Activity className="w-3.5 h-3.5" /> Open in Assets
          </button>
          <span className="ml-auto text-[10px] text-gray-400">
            Updated: {new Date(data.updatedAt).toLocaleTimeString()}
          </span>
        </div>
      </div>
    </div>
  );
}

function MetricBox({ label, value, suffix, color }: { label: string; value: string | number; suffix?: string; color?: string }) {
  return (
    <div className="p-3 text-center">
      <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-1">{label}</div>
      <div className={`text-xl font-bold ${color || 'text-gray-900'}`}>
        {value}{suffix && <span className="text-xs text-gray-400">{suffix}</span>}
      </div>
    </div>
  );
}

function EvidenceBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-2 text-center">
      <div className="text-[9px] uppercase text-gray-400">{label}</div>
      <div className="text-xs font-semibold text-gray-700">{value}</div>
    </div>
  );
}

export default EngineDecisionView;
