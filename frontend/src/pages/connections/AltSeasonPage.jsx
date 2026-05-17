/**
 * Alt Season Monitor — "WHERE MONEY IS" Engine
 * Light theme, no borders, no shadows, no boxes
 */

import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, TrendingUp, AlertTriangle, Zap, Target, ChevronDown, ChevronUp, Activity } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const STATE_CONFIG = {
  FULL_ALT: { label: 'Full Altseason', color: 'text-green-600', barColor: '#16a34a' },
  ALTSEASON: { label: 'Altseason', color: 'text-emerald-600', barColor: '#059669' },
  EARLY_ALT: { label: 'Early Alt', color: 'text-yellow-600', barColor: '#ca8a04' },
  BTC_DOMINANCE: { label: 'BTC Dominance', color: 'text-orange-600', barColor: '#ea580c' },
};

const PHASE_COLORS = {
  EARLY: 'text-green-600',
  MOMENTUM: 'text-amber-600',
  LATE: 'text-red-600',
  NEUTRAL: 'text-gray-400',
};

const ACTION_CONFIG = {
  ACCUMULATE: { label: 'ACCUMULATE', color: 'text-green-600' },
  RIDE: { label: 'RIDE', color: 'text-amber-600' },
  EXIT: { label: 'EXIT', color: 'text-red-600' },
  WAIT: { label: 'WAIT', color: 'text-gray-400' },
};

function IndexGauge({ value, state }) {
  const cfg = STATE_CONFIG[state] || STATE_CONFIG.BTC_DOMINANCE;
  const rotation = (value / 100) * 180 - 90;
  return (
    <div className="flex flex-col items-center" data-testid="altseason-gauge">
      <div className="relative w-48 h-24 overflow-hidden">
        <div className="absolute inset-0">
          <svg viewBox="0 0 200 100" className="w-full h-full">
            <path d="M 10 95 A 85 85 0 0 1 190 95" fill="none" stroke="#1f2937" strokeWidth="12" strokeLinecap="round" />
            <path d="M 10 95 A 85 85 0 0 1 190 95" fill="none" stroke={cfg.barColor} strokeWidth="12" strokeLinecap="round"
              strokeDasharray={`${value * 2.67} 267`} />
          </svg>
        </div>
        <div className="absolute bottom-0 left-1/2 origin-bottom" style={{ transform: `translateX(-50%) rotate(${rotation}deg)` }}>
          <div className="w-0.5 h-16 rounded-full" style={{ background: '#d1d5db' }} />
        </div>
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1">
          <span className="text-4xl font-semibold" style={{ color: '#f9fafb' }}>{value}</span>
        </div>
      </div>
      <span className={`text-sm font-medium mt-2 ${cfg.color}`}>{cfg.label}</span>
    </div>
  );
}

function ComponentBars({ components }) {
  const items = [
    { key: 'outperformance', label: 'ALT > BTC', value: components.outperformance },
    { key: 'twitterShare', label: 'Twitter Share', value: components.twitterShare },
    { key: 'clusterStrength', label: 'Cluster Strength', value: components.clusterStrength },
    { key: 'breadth', label: 'Market Breadth', value: components.breadth },
    { key: 'marketBias', label: 'Market Bias', value: components.marketBias },
  ];
  return (
    <div className="space-y-2.5" data-testid="component-bars">
      {items.map(item => (
        <div key={item.key} className="flex items-center gap-3">
          <span className="text-xs w-28 text-right shrink-0" style={{ color: '#6b7280' }}>{item.label}</span>
          <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: '#1f2937' }}>
            <div className="h-full rounded-full transition-all duration-700"
              style={{ width: `${item.value * 100}%`, background: item.value > 0.7 ? '#16a34a' : item.value > 0.4 ? '#ca8a04' : '#dc2626' }} />
          </div>
          <span className="text-xs w-10 text-right font-mono" style={{ color: '#9ca3af' }}>{(item.value * 100).toFixed(0)}%</span>
        </div>
      ))}
    </div>
  );
}

function OpportunityCard({ opp, rank }) {
  const phaseColor = PHASE_COLORS[opp.phase] || PHASE_COLORS.NEUTRAL;
  const action = ACTION_CONFIG[opp.action] || ACTION_CONFIG.WAIT;

  return (
    <div className="py-3" data-testid={`opportunity-${opp.symbol}`}>
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-300 font-mono">#{rank}</span>
          <span className="text-base font-semibold text-gray-900">${opp.symbol}</span>
          <span className={`text-[10px] font-medium uppercase ${phaseColor}`}>{opp.phase}</span>
        </div>
        <span className={`text-xs font-medium ${action.color}`}>{action.label}</span>
      </div>
      <div className="flex flex-wrap gap-1.5 mb-2">
        {(opp.signal || []).map((s, i) => (
          <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">{s}</span>
        ))}
      </div>
      <div className="flex items-center gap-4 text-xs text-gray-400">
        <span>Score <span className="text-gray-900 font-medium">{(opp.score * 100).toFixed(0)}</span></span>
        <span>24h <span className={opp.priceChange24h > 0 ? 'text-green-600 font-medium' : 'text-red-500 font-medium'}>
          {opp.priceChange24h > 0 ? '+' : ''}{opp.priceChange24h?.toFixed(1)}%
        </span></span>
        {opp.mentions > 0 && <span>Mentions <span className="text-gray-900 font-medium">{opp.mentions}</span></span>}
        {opp.uniqueAuthors > 0 && <span>Authors <span className="text-gray-900 font-medium">{opp.uniqueAuthors}</span></span>}
        {opp.price > 0 && <span className="text-gray-300">${opp.price}</span>}
      </div>
    </div>
  );
}

function MomentumTable({ tokens }) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? tokens : tokens.slice(0, 10);
  return (
    <div data-testid="momentum-table">
      <div className="space-y-0">
        <div className="flex items-center gap-3 px-3 py-1.5 text-[10px] uppercase tracking-wider" style={{ color: '#4b5563' }}>
          <span className="w-8">#</span>
          <span className="flex-1">Token</span>
          <span className="w-20 text-right">Momentum</span>
          <span className="w-16 text-right">24h</span>
          <span className="w-14 text-right">Mentions</span>
          <span className="w-16 text-right">Phase</span>
        </div>
        {visible.map((t, i) => {
          const phaseColor = PHASE_COLORS[t.phase] || PHASE_COLORS.NEUTRAL;
          return (
            <div key={t.symbol} className="flex items-center gap-3 px-3 py-2 transition-colors" style={{ borderRadius: 4 }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.03)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
              <span className="w-8 text-xs font-mono" style={{ color: '#4b5563' }}>{i + 1}</span>
              <span className="flex-1 text-sm font-medium" style={{ color: '#d1d5db' }}>${t.symbol}</span>
              <div className="w-20 flex items-center justify-end gap-1.5">
                <div className="w-12 h-1 rounded-full overflow-hidden" style={{ background: '#1f2937' }}>
                  <div className="h-full bg-blue-500 rounded-full" style={{ width: `${t.momentum * 100}%` }} />
                </div>
                <span className="text-xs font-mono" style={{ color: '#9ca3af' }}>{(t.momentum * 100).toFixed(0)}</span>
              </div>
              <span className={`w-16 text-right text-xs font-medium ${t.priceChange24h > 0 ? 'text-green-500' : 'text-red-500'}`}>
                {t.priceChange24h > 0 ? '+' : ''}{t.priceChange24h?.toFixed(1)}%
              </span>
              <span className="w-14 text-right text-xs" style={{ color: '#6b7280' }}>{t.mentions || '\u2014'}</span>
              <span className={`w-16 text-right text-[10px] font-medium ${phaseColor}`}>{t.phase}</span>
            </div>
          );
        })}
      </div>
      {tokens.length > 10 && (
        <button onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 mx-auto mt-2 text-xs hover:text-gray-400 transition-colors" style={{ color: '#6b7280' }}>
          {expanded ? <><ChevronUp className="w-3 h-3" /> Show less</> : <><ChevronDown className="w-3 h-3" /> Show all {tokens.length}</>}
        </button>
      )}
    </div>
  );
}

function StatCard({ label, value, sub, color }) {
  return (
    <div className="py-2">
      <div className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: '#6b7280' }}>{label}</div>
      <div className="flex items-baseline gap-1">
        <span className={`text-xl font-semibold ${color}`}>{value}</span>
        <span className="text-[10px]" style={{ color: '#4b5563' }}>{sub}</span>
      </div>
    </div>
  );
}

export default function AltSeasonPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const resp = await fetch(`${API}/api/altseason`);
      const d = await resp.json();
      if (d.ok) setData(d);
      else setError(d.error || 'Failed to load');
    } catch { setError('Network error'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const earlyOpps = data?.top_opportunities?.filter(o => o.phase === 'EARLY') || [];
  const momentumOpps = data?.top_opportunities?.filter(o => o.phase === 'MOMENTUM') || [];
  const neutralOpps = data?.top_opportunities?.filter(o => o.phase === 'NEUTRAL' && o.score > 0.1) || [];

  return (
    <div className="min-h-screen" data-testid="alt-season-page">
      <div className="max-w-[1600px] mx-auto px-6 py-6">

        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-gray-900">Alt Alpha Engine</h1>
            <p className="text-sm text-gray-400 mt-0.5">Real-time alpha detection from market + social + clusters</p>
          </div>
          <button onClick={fetchData} disabled={loading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-900 text-sm text-white hover:bg-gray-800 disabled:opacity-50 transition-colors"
            data-testid="refresh-btn">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {error && <div className="text-sm text-red-500 mb-4">{error}</div>}

        {data && (
          <>
            <div className="rounded-xl mb-6" style={{ background: '#0a0a0a', padding: '24px' }}>
              <div className="grid grid-cols-12 gap-6">
              <div className="col-span-4 flex flex-col items-center justify-center py-4" data-testid="index-section">
                <IndexGauge value={data.index} state={data.state} />
                <div className="flex items-center gap-2 mt-3 text-xs" style={{ color: '#6b7280' }}>
                  <span>Confidence: {(data.confidence * 100).toFixed(0)}%</span>
                  <span style={{ color: '#374151' }}>|</span>
                  <span>{data.meta?.totalTokens} tokens tracked</span>
                </div>
              </div>
              <div className="col-span-4 py-4">
                <span className="text-[10px] font-medium uppercase tracking-widest mb-3 block" style={{ color: '#6b7280' }}>Index Components</span>
                <ComponentBars components={data.components} />
              </div>
              <div className="col-span-4 py-4">
                <span className="text-[10px] font-medium uppercase tracking-widest mb-3 block" style={{ color: '#6b7280' }}>Market Snapshot</span>
                <div className="grid grid-cols-2 gap-x-6 gap-y-2">
                  <StatCard label="Early Signals" value={earlyOpps.length} sub="tokens" color="text-green-500" />
                  <StatCard label="In Momentum" value={momentumOpps.length} sub="tokens" color="text-amber-500" />
                  <StatCard label="Social Volume" value={data.meta?.totalTweets || 0} sub="tweets" color="text-blue-500" />
                  <StatCard label="Clusters Active" value={data.meta?.totalClusters || 0} sub="groups" color="text-purple-500" />
                </div>
              </div>
              </div>
            </div>

            <div className="mb-10">
              {earlyOpps.length > 0 && (
                <div className="mb-8">
                  <div className="flex items-center gap-2 mb-1">
                    <Zap className="w-4 h-4 text-green-600" />
                    <span className="text-sm font-medium text-green-600">TOP ALPHA</span>
                    <span className="text-[10px] text-gray-400">Early attention, price hasn't moved</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-8">
                    {earlyOpps.map((o, i) => <OpportunityCard key={o.symbol} opp={o} rank={i + 1} />)}
                  </div>
                </div>
              )}
              {momentumOpps.length > 0 && (
                <div className="mb-8">
                  <div className="flex items-center gap-2 mb-1">
                    <TrendingUp className="w-4 h-4 text-amber-600" />
                    <span className="text-sm font-medium text-amber-600">RUNNING</span>
                    <span className="text-[10px] text-gray-400">Active momentum, ride the wave</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-8">
                    {momentumOpps.map((o, i) => <OpportunityCard key={o.symbol} opp={o} rank={earlyOpps.length + i + 1} />)}
                  </div>
                </div>
              )}
              {neutralOpps.length > 0 && (
                <div className="mb-8">
                  <div className="flex items-center gap-2 mb-1">
                    <Target className="w-4 h-4 text-gray-400" />
                    <span className="text-sm font-medium text-gray-400">ON RADAR</span>
                    <span className="text-[10px] text-gray-300">Waiting for confirmation</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-8">
                    {neutralOpps.map((o, i) => <OpportunityCard key={o.symbol} opp={o} rank={earlyOpps.length + momentumOpps.length + i + 1} />)}
                  </div>
                </div>
              )}
              {!earlyOpps.length && !momentumOpps.length && !neutralOpps.length && (
                <div className="text-center py-12 text-gray-300">
                  <Target className="w-8 h-8 mx-auto mb-3 opacity-30" />
                  <p className="text-sm">No opportunities detected right now</p>
                </div>
              )}
            </div>

            {data.token_momentum?.length > 0 && (
              <div className="rounded-xl" style={{ background: '#0a0a0a', padding: '20px 24px' }}>
                <div className="flex items-center gap-2 mb-2">
                  <Activity className="w-4 h-4 text-blue-500" />
                  <span className="text-sm font-medium text-blue-500">TOKEN MOMENTUM</span>
                  <span className="text-[10px]" style={{ color: '#6b7280' }}>Combined social + price + volume signal</span>
                </div>
                <MomentumTable tokens={data.token_momentum} />
              </div>
            )}
          </>
        )}

        {loading && !data && (
          <div className="flex items-center justify-center py-20">
            <RefreshCw className="w-5 h-5 animate-spin text-gray-300" />
          </div>
        )}
      </div>
    </div>
  );
}
