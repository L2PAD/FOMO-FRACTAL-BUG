/**
 * Engine Projects View — Phase B4
 * =================================
 * Ranked token table with multi-signal scoring:
 *   DEX Net | CEX Net | Smart Money | Liquidity | Score | Action
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  TrendingUp,
  TrendingDown,
  Minus,
  Loader2,
  Filter,
  Clock,
  AlertTriangle,
} from 'lucide-react';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';
const WINDOWS = ['24h', '7d'] as const;
type SortField = 'score' | 'dexNetUsd' | 'cexNetUsd' | 'smartMoneyNet' | 'liquidityScore';
type FilterAction = 'ALL' | 'BUY' | 'SELL' | 'NEUTRAL';

interface ProjectPoint {
  symbol: string;
  tokenAddress: string | null;
  dexNetUsd: number;
  cexNetUsd: number;
  smartMoneyNet: number;
  liquidityScore: number;
  components: { dex: number; cex: number; smartMoney: number; liquidity: number };
  score: number;
  action: 'BUY' | 'SELL' | 'NEUTRAL';
  confidence: number;
  evidence: {
    dexTrades: number;
    cexTransfers: number;
    pricedShare: number;
    poolScore: number | null;
    poolStatus: string | null;
  };
}

function fmt(n: number): string {
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
  if (Math.abs(n) < 0.01) return '$0';
  return `$${n.toFixed(0)}`;
}

function fmtSigned(n: number): string {
  const s = fmt(Math.abs(n));
  return n >= 0 ? `+${s}` : `-${s}`;
}

const ACTION_COLORS: Record<string, string> = {
  BUY: 'bg-emerald-100 text-emerald-700',
  SELL: 'bg-red-100 text-red-700',
  NEUTRAL: 'bg-gray-100 text-gray-600',
};

const ACTION_ICONS: Record<string, React.ReactNode> = {
  BUY: <TrendingUp className="w-3 h-3" />,
  SELL: <TrendingDown className="w-3 h-3" />,
  NEUTRAL: <Minus className="w-3 h-3" />,
};

interface Props {
  onNavigateTab?: (tab: string, params?: Record<string, string>) => void;
}

export function EngineProjectsView({ onNavigateTab }: Props) {
  const [projects, setProjects] = useState<ProjectPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [window, setWindow] = useState<typeof WINDOWS[number]>('7d');
  const [sortField, setSortField] = useState<SortField>('score');
  const [sortDesc, setSortDesc] = useState(true);
  const [filterAction, setFilterAction] = useState<FilterAction>('ALL');
  const [totalTokens, setTotalTokens] = useState(0);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const url = `${API_BASE}/api/v10/onchain-v2/engine/projects?window=${window}&limit=100`;
      const r = await fetch(url);
      const d = await r.json();
      if (d.ok) {
        setProjects(d.projects || []);
        setTotalTokens(d.totalTokens || 0);
        setGeneratedAt(d.generatedAt || null);
      }
    } finally {
      setLoading(false);
    }
  }, [window]);

  useEffect(() => { load(); }, [load]);

  // Sort & filter
  const sorted = [...projects]
    .filter(p => filterAction === 'ALL' || p.action === filterAction)
    .sort((a, b) => {
      const av = a[sortField];
      const bv = b[sortField];
      if (sortField === 'score') {
        return sortDesc
          ? Math.abs(bv as number) - Math.abs(av as number)
          : Math.abs(av as number) - Math.abs(bv as number);
      }
      return sortDesc ? (bv as number) - (av as number) : (av as number) - (bv as number);
    });

  const toggleSort = (field: SortField) => {
    if (sortField === field) setSortDesc(!sortDesc);
    else { setSortField(field); setSortDesc(true); }
  };

  const SortHeader = ({ field, label, className = '' }: { field: SortField; label: string; className?: string }) => (
    <button
      onClick={() => toggleSort(field)}
      className={`flex items-center gap-1 text-xs font-medium text-gray-500 hover:text-gray-700 transition-colors ${className}`}
      data-testid={`sort-${field}`}
    >
      {label}
      {sortField === field ? (
        sortDesc ? <ArrowDown className="w-3 h-3" /> : <ArrowUp className="w-3 h-3" />
      ) : (
        <ArrowUpDown className="w-3 h-3 opacity-30" />
      )}
    </button>
  );

  // Counts
  const buyCount = projects.filter(p => p.action === 'BUY').length;
  const sellCount = projects.filter(p => p.action === 'SELL').length;
  const neutralCount = projects.filter(p => p.action === 'NEUTRAL').length;

  return (
    <div className="space-y-4" data-testid="engine-projects">
      {/* Header controls */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        {/* Window toggle */}
        <div className="flex items-center gap-1 bg-gray-100 p-0.5 rounded-lg">
          {WINDOWS.map(w => (
            <button
              key={w}
              onClick={() => setWindow(w)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                window === w ? 'bg-white text-gray-900' : 'text-gray-500 hover:text-gray-700'
              }`}
              data-testid={`window-${w}`}
            >
              {w}
            </button>
          ))}
        </div>

        {/* Action filter */}
        <div className="flex items-center gap-1" data-testid="action-filter">
          <Filter className="w-3.5 h-3.5 text-gray-400" />
          {(['ALL', 'BUY', 'SELL', 'NEUTRAL'] as FilterAction[]).map(a => (
            <button
              key={a}
              onClick={() => setFilterAction(a)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                filterAction === a
                  ? a === 'BUY' ? 'bg-emerald-100 text-emerald-700'
                    : a === 'SELL' ? 'bg-red-100 text-red-700'
                    : a === 'NEUTRAL' ? 'bg-gray-200 text-gray-700'
                    : 'bg-blue-100 text-blue-700'
                  : 'text-gray-400 hover:text-gray-600'
              }`}
              data-testid={`filter-${a.toLowerCase()}`}
            >
              {a === 'ALL' ? `All (${totalTokens})` :
               a === 'BUY' ? `BUY (${buyCount})` :
               a === 'SELL' ? `SELL (${sellCount})` :
               `NEUTRAL (${neutralCount})`}
            </button>
          ))}
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
        </div>
      )}

      {/* Empty state */}
      {!loading && sorted.length === 0 && (
        <div className="flex flex-col items-center py-12 text-gray-400" data-testid="projects-empty">
          <AlertTriangle className="w-8 h-8 mb-2" />
          <p className="text-sm">No project data for {window} window</p>
          <p className="text-xs mt-1">Engine may need more data to produce rankings</p>
        </div>
      )}

      {/* Table */}
      {!loading && sorted.length > 0 && (
        <div className="bg-white rounded-xl overflow-hidden">
          {/* Table header */}
          <div className="grid grid-cols-[1fr_120px_110px_110px_80px_70px_70px] gap-2 px-4 py-3 bg-gray-50">
            <span className="text-xs font-medium text-gray-500">Token</span>
            <SortHeader field="dexNetUsd" label="DEX Net" />
            <SortHeader field="cexNetUsd" label="CEX Net" />
            <SortHeader field="smartMoneyNet" label="Smart Money" />
            <SortHeader field="liquidityScore" label="Liquidity" />
            <SortHeader field="score" label="Score" />
            <span className="text-xs font-medium text-gray-500 text-center">Action</span>
          </div>

          {/* Table rows */}
          <div className="divide-y divide-gray-50">
            {sorted.map((p, i) => (
              <button
                key={p.symbol}
                onClick={() => {
                  if (p.tokenAddress) {
                    onNavigateTab?.('assets', { token: p.tokenAddress });
                  }
                }}
                className="grid grid-cols-[1fr_120px_110px_110px_80px_70px_70px] gap-2 px-4 py-3 hover:bg-gray-50 transition-colors w-full text-left"
                data-testid={`project-row-${p.symbol}`}
              >
                {/* Token */}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400 w-5 tabular-nums">{i + 1}</span>
                  <span className="font-medium text-gray-900 text-sm">{p.symbol}</span>
                  <span className="text-xs text-gray-400">{p.evidence.dexTrades}tx</span>
                </div>

                {/* DEX Net */}
                <div className="flex items-center">
                  <span className={`text-sm tabular-nums font-medium ${
                    p.dexNetUsd > 0 ? 'text-emerald-600' : p.dexNetUsd < 0 ? 'text-red-500' : 'text-gray-400'
                  }`}>
                    {fmtSigned(p.dexNetUsd)}
                  </span>
                </div>

                {/* CEX Net */}
                <div className="flex items-center">
                  <span className={`text-sm tabular-nums font-medium ${
                    p.cexNetUsd < 0 ? 'text-emerald-600' : p.cexNetUsd > 0 ? 'text-red-500' : 'text-gray-400'
                  }`}>
                    {p.cexNetUsd !== 0 ? fmtSigned(p.cexNetUsd) : '-'}
                  </span>
                </div>

                {/* Smart Money */}
                <div className="flex items-center">
                  <span className={`text-sm tabular-nums font-medium ${
                    p.smartMoneyNet > 0 ? 'text-emerald-600' : p.smartMoneyNet < 0 ? 'text-red-500' : 'text-gray-400'
                  }`}>
                    {p.smartMoneyNet !== 0 ? fmtSigned(p.smartMoneyNet) : '-'}
                  </span>
                </div>

                {/* Liquidity */}
                <div className="flex items-center">
                  <div className="flex items-center gap-1.5">
                    <div className="w-12 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500 rounded-full"
                        style={{ width: `${Math.round(p.liquidityScore * 100)}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-500 tabular-nums">{(p.liquidityScore * 100).toFixed(0)}</span>
                  </div>
                </div>

                {/* Score */}
                <div className="flex items-center">
                  <span className={`text-sm font-semibold tabular-nums ${
                    p.score > 0.3 ? 'text-emerald-600' : p.score < -0.3 ? 'text-red-500' : 'text-gray-600'
                  }`}>
                    {p.score > 0 ? '+' : ''}{p.score.toFixed(2)}
                  </span>
                </div>

                {/* Action badge */}
                <div className="flex items-center justify-center">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold ${ACTION_COLORS[p.action]}`}>
                    {ACTION_ICONS[p.action]}
                    {p.action}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Formula explanation + timestamp */}
      {!loading && sorted.length > 0 && (
        <div className="flex items-center justify-between text-xs text-gray-400 px-1">
          <span>
            Score = 0.35 DEX + 0.25 SmartMoney + 0.20 Liquidity + 0.20 (-CEX)
            {' '}| BUY &ge; 0.6 | SELL &le; -0.6
          </span>
          {generatedAt && (
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {new Date(generatedAt).toLocaleTimeString()}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
