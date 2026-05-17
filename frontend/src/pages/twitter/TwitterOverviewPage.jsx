/**
 * Twitter Intelligence — Overview (Decision Terminal v2)
 *
 * OLD blocks preserved (borders removed):
 * A) System Status Bar
 * B) Market Pulse (4 KPI + CAS)
 * C) Live Signals (Signal Assets + Coordinated Tokens)
 * D) Actor Intel (Influencers + Rising Tokens + Top Clusters)
 * E) Risk Panel
 * F) Quick Access Grid
 *
 * NEW blocks added:
 * - What To Do Now (compact, between A and B)
 * - Top Signals + Dominant Narratives (2-col, after CAS chart)
 * - Capital Flow (compact, after Actor Intel)
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  TrendingUp, Users, Network, Shield, AlertTriangle,
  BarChart3, Activity, Eye, Zap, Radio,
  GitBranch, Target, Award, Bot, ChevronRight,
  RefreshCw,
  ArrowUpRight, ArrowDownRight
} from 'lucide-react';
import CASHistoryChart from './components/CASHistoryChart';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

export default function TwitterOverviewPage() {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    const results = {};
    const endpoints = [
      { key: 'stats', url: '/api/connections/stats' },
      { key: 'unifiedStats', url: '/api/connections/unified/stats' },
      { key: 'altSeason', url: '/api/connections/alt-season' },
      { key: 'clusters', url: '/api/connections/clusters' },
      { key: 'clusterMomentum', url: '/api/connections/cluster-momentum' },
      { key: 'clusterCredibility', url: '/api/connections/cluster-credibility' },
      { key: 'reality', url: '/api/connections/reality/leaderboard?limit=5' },
      { key: 'radar', url: '/api/connections/radar' },
      { key: 'narratives', url: '/api/connections/narratives' },
      { key: 'cas', url: '/api/connections/overview/cas' },
    ];
    await Promise.allSettled(
      endpoints.map(async ({ key, url }) => {
        try {
          const res = await fetch(`${API_BASE}${url}`);
          const json = await res.json();
          if (json.ok) results[key] = json;
        } catch {}
      })
    );
    setData(results);
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Auto-refresh every 60 seconds
  useEffect(() => {
    const interval = setInterval(fetchAll, 60000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const [lastUpdate, setLastUpdate] = useState(null);
  useEffect(() => {
    if (!loading && Object.keys(data).length > 0) setLastUpdate(new Date());
  }, [data, loading]);

  // Derived data
  const stats = data.stats?.stats || {};
  const altIdx = data.altSeason?.altSeasonIndex ?? 0;
  const altSignal = data.altSeason?.signal || 'unknown';
  const clusters = data.clusters?.data || [];
  const momentum = useMemo(() => data.clusterMomentum?.data || [], [data.clusterMomentum]);
  const credibility = useMemo(() => data.clusterCredibility?.data || [], [data.clusterCredibility]);
  const leaderboard = data.reality?.leaderboard || [];
  const radarBreakout = useMemo(() => data.radar?.data?.breakout || [], [data.radar]);
  const narratives = useMemo(() => data.narratives?.data || [], [data.narratives]);

  // CAS
  const casData = data.cas || {};
  const cas = casData.current ?? 0;
  const casEma = casData.ema6h ?? cas;
  const casEma24 = casData.ema24h ?? cas;
  const casTrend = casData.trend || 'stable';
  const casLabel = casData.label || 'Unknown';
  const casDelta = casData.delta24h ?? 0;
  const casFlags = casData.qualityFlags || [];
  const casHistory = casData.history || [];
  const casComponents = casData.components || {};
  const hasCasFlags = casFlags.length > 0;
  const casColor = casEma >= 80 ? 'red' : casEma >= 60 ? 'orange' : casEma >= 30 ? 'amber' : 'green';
  const casRising3 = casHistory.length >= 3 && casHistory.slice(-3).every((h, i, a) => i === 0 || h.value >= a[i - 1].value);
  const pumpTokens = momentum.filter(m => m.classification === 'PUMP_LIKE');
  const lowCredCount = casData.context?.lowCredClusters ?? credibility.filter(c => c.score < 0.5).length;
  const casContext = casData.context || {};
  const pumpTokenSet = useMemo(() => new Set(
    (casContext.topPumpTokens || []).concat(pumpTokens.map(m => m.token))
  ), [casContext.topPumpTokens, pumpTokens]);

  // Decision engine (nuanced: pump with strong signal + early = cautious enter)
  const decisions = useMemo(() => {
    const enter = [], watch = [], avoid = [];
    const processed = new Set();

    for (const t of radarBreakout) {
      const isPump = pumpTokenSet.has(t.token);
      const narrative = narratives.find(n => {
        const nName = (n.name || '').toLowerCase();
        const tk = t.token.toLowerCase();
        // Try token list first, fallback to name heuristic
        if ((n.tokens || []).includes(t.token)) return true;
        return nName.includes(tk) || tk.includes(nName.replace(/_/g, ''));
      });
      const narrativeName = narrative?.name?.replace(/_/g, ' ');
      const q = getSignalQuality(t);
      processed.add(t.token);

      if (isPump && t.strength > 0.8 && t.confidence > 0.6 && q.timing === 'EARLY') {
        // Pump but very early and strong — cautious enter
        enter.push({
          token: t.token,
          pct: t.priceChange24h,
          reason: `Early pump signal${narrativeName ? ` (${narrativeName})` : ''} — enter with caution`,
          quality: q,
        });
      } else if (isPump && t.strength > 0.7) {
        // Pump with moderate strength — watch closely
        watch.push({
          token: t.token,
          pct: t.priceChange24h,
          reason: `Pump-like but strong signal (${(t.strength * 100).toFixed(0)}%)`,
          quality: q,
        });
      } else if (isPump) {
        avoid.push({
          token: t.token,
          pct: t.priceChange24h,
          reason: `Coordinated pump · flagged by momentum`,
          quality: q,
        });
      } else if (t.strength > 0.7 && t.confidence > 0.5) {
        enter.push({
          token: t.token,
          pct: t.priceChange24h,
          reason: narrativeName || `Strong signal (${(t.strength * 100).toFixed(0)}%) + confidence ${(t.confidence * 100).toFixed(0)}%`,
          quality: q,
        });
      } else if (t.strength > 0.4) {
        watch.push({
          token: t.token,
          pct: t.priceChange24h,
          reason: t.confidence < 0.5 ? `Signal unconfirmed (${(t.confidence * 100).toFixed(0)}% conf)` : `Moderate strength (${(t.strength * 100).toFixed(0)}%)`,
          quality: q,
        });
      }
    }

    // Add remaining pump tokens not in radar
    for (const m of momentum) {
      if (m.classification === 'PUMP_LIKE' && !processed.has(m.token)) {
        avoid.push({
          token: m.token,
          reason: `Pump-like coordination · ${m.uniqueMentioners} mentioners`,
          quality: { timing: 'LATE', purity: 'NOISY' },
        });
      }
    }

    return { enter, watch, avoid };
  }, [radarBreakout, pumpTokenSet, narratives, momentum]);

  // Narrative dominance
  const narrativeDominance = useMemo(() => {
    const total = narratives.reduce((s, n) => s + (n.mentionCount || 0), 0) || 1;
    return narratives.map(n => ({ ...n, share: Math.round((n.mentionCount || 0) / total * 100) }))
      .sort((a, b) => b.mentionCount - a.mentionCount);
  }, [narratives]);

  // Capital flow — based on price action + narrative momentum
  const capitalFlow = useMemo(() => {
    const inflow = [], outflow = [];

    // Narrative-level: confidence + mention volume as proxy for capital attention
    for (const n of narratives) {
      const name = n.name.replace(/_/g, ' ');
      if (n.confidence > 0.7 && n.mentionCount > 5) {
        inflow.push({ name, confidence: n.confidence, mentions: n.mentionCount });
      } else if (n.confidence < 0.5) {
        outflow.push({ name, confidence: n.confidence, mentions: n.mentionCount });
      }
    }

    // Token-level: price action (>5% = strong inflow, <-5% = outflow)
    for (const t of radarBreakout) {
      if (t.priceChange24h > 0.05 && !pumpTokenSet.has(t.token)) {
        inflow.push({ name: t.token, confidence: t.confidence, mentions: t.mentionCount, pct: t.priceChange24h });
      } else if (t.priceChange24h < -0.05) {
        outflow.push({ name: t.token, confidence: t.confidence, mentions: t.mentionCount, pct: t.priceChange24h });
      }
    }

    return { inflow, outflow };
  }, [narratives, radarBreakout, pumpTokenSet]);

  // Cluster evaluation
  const clusterEval = useMemo(() => {
    return credibility.map(c => {
      const hasPump = momentum.some(m => m.classification === 'PUMP_LIKE' && m.cluster === c.clusterId);
      let status, risk;
      if (c.score < 0.4 || hasPump) { status = 'OVERHEATED'; risk = 'High'; }
      else if (c.score < 0.6) { status = 'MIXED'; risk = 'Medium'; }
      else { status = 'HEALTHY'; risk = 'Low'; }
      return { ...c, status, risk };
    }).sort((a, b) => a.score - b.score);
  }, [credibility, momentum]);

  return (
    <div className="p-5 max-w-[1500px] mx-auto space-y-5" data-testid="twitter-overview">

      {/* ═══ A: Status Bar ═══ */}
      <div className="flex items-center justify-between bg-gray-900 text-white px-5 py-3 rounded-t-2xl" data-testid="status-bar">
        <div className="flex items-center gap-6 text-xs">
          <StatusPill label="Accounts" value={stats.totalAccounts || 0} color="blue" />
          <StatusPill label="Verified" value={stats.verifiedAccounts || 0} color="green" />
          <StatusPill label="Clusters" value={clusters.length} color="purple" />
          <StatusPill label="Pump Tokens" value={pumpTokens.length} color={pumpTokens.length > 3 ? 'red' : 'gray'} />
          <StatusPill label="Narratives" value={narratives.length} color="cyan" />
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            <span className="text-gray-400">Live</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={fetchAll} className="p-1.5 hover:bg-gray-800 rounded-lg transition-colors" title="Refresh">
            <RefreshCw className={`w-3.5 h-3.5 text-gray-400 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* ═══ NEW: What To Do Now (compact) ═══ */}
      <div className="px-5 py-4 rounded-b-2xl" style={{ backgroundColor: '#0f172a' }} data-testid="decision-block">
        <p className="text-xs font-bold uppercase tracking-wider mb-3" style={{ color: '#94a3b8' }}>What to do now</p>
        <div className="grid grid-cols-3 gap-6">
          <div>
            <span className="text-[10px] font-bold uppercase" style={{ color: '#4ade80' }}>Enter</span>
            {decisions.enter.length > 0 ? decisions.enter.slice(0, 3).map(t => (
              <p key={t.token} className="text-xs mt-1" style={{ color: '#e2e8f0' }}>
                <strong>{t.token}</strong> <span style={{ color: '#64748b' }}>— {t.reason}</span>
              </p>
            )) : <p className="text-xs mt-1" style={{ color: '#475569' }}>No clear entries</p>}
          </div>
          <div>
            <span className="text-[10px] font-bold uppercase" style={{ color: '#fbbf24' }}>Watch</span>
            {decisions.watch.length > 0 ? decisions.watch.slice(0, 3).map(t => (
              <p key={t.token} className="text-xs mt-1" style={{ color: '#e2e8f0' }}>
                <strong>{t.token}</strong> <span style={{ color: '#64748b' }}>— {t.reason}</span>
              </p>
            )) : <p className="text-xs mt-1" style={{ color: '#475569' }}>Nothing to watch</p>}
          </div>
          <div>
            <span className="text-[10px] font-bold uppercase" style={{ color: '#f87171' }}>Avoid</span>
            {decisions.avoid.length > 0 ? decisions.avoid.slice(0, 3).map((t, i) => (
              <p key={t.token + i} className="text-xs mt-1" style={{ color: '#e2e8f0' }}>
                <strong>{t.token}</strong> <span style={{ color: '#64748b' }}>— {t.reason}</span>
              </p>
            )) : <p className="text-xs mt-1" style={{ color: '#475569' }}>No threats</p>}
          </div>
        </div>
      </div>

      {/* ═══ C: Live Signals ═══ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="live-signals">
        {/* Top Signal Assets */}
        <div className="bg-white overflow-hidden">
          <div className="px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Radio className="w-4 h-4 text-blue-500" />
              <span className="text-sm font-semibold text-gray-800">Top Signal Assets</span>
            </div>
            <TabLink tab="radar" label="Radar" />
          </div>
          <div>
            {radarBreakout.slice(0, 5).map(t => (
              <div key={t.token} className="flex items-center justify-between px-4 py-2.5" style={{ borderBottom: '1px solid #f5f5f5' }}>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-bold text-gray-900 w-12">{t.token}</span>
                  <span className="text-[10px] font-semibold" style={{
                    color: t.priceChange24h > 0 ? '#16a34a' : '#dc2626'
                  }}>{t.priceChange24h > 0 ? '+' : ''}{(t.priceChange24h * 100).toFixed(1)}%</span>
                </div>
                <div className="flex items-center gap-4 text-xs text-gray-500">
                  <span>Strength: <strong className="text-gray-700">{(t.strength * 100).toFixed(0)}%</strong></span>
                  <span>Conf: <strong className="text-gray-700">{(t.confidence * 100).toFixed(0)}%</strong></span>
                  <span>{t.mentionCount} mentions</span>
                </div>
              </div>
            ))}
            {radarBreakout.length === 0 && <div className="px-4 py-6 text-sm text-gray-400 text-center">No breakout signals</div>}
          </div>
        </div>

        {/* Coordinated Tokens */}
        <div className="bg-white overflow-hidden">
          <div className="px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-orange-500" />
              <span className="text-sm font-semibold text-gray-800">Coordinated Tokens</span>
            </div>
            <TabLink tab="clusters" label="Clusters" />
          </div>
          <div>
            {momentum.slice(0, 5).map(t => (
              <div key={t.token} className="flex items-center justify-between px-4 py-2.5" style={{ borderBottom: '1px solid #f5f5f5' }}>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-bold text-gray-900 w-12">{t.token}</span>
                  <span className="text-[10px] font-semibold" style={{
                    color: t.classification === 'PUMP_LIKE' ? '#dc2626' : '#d97706'
                  }}>{t.classification === 'PUMP_LIKE' ? 'PUMP' : t.classification}</span>
                </div>
                <div className="flex items-center gap-4 text-xs text-gray-500">
                  <span>Score: <strong className="text-gray-700">{(t.score * 100).toFixed(0)}%</strong></span>
                  <span>{t.uniqueMentioners} mentioners</span>
                </div>
              </div>
            ))}
            {momentum.length === 0 && <div className="px-4 py-6 text-sm text-gray-400 text-center">No coordinated activity</div>}
          </div>
        </div>
      </div>

      {/* ═══ Narratives + Cluster Intelligence (white cards) ═══ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="narratives-clusters">
        {/* Dominant Narratives */}
        <div className="bg-white overflow-hidden">
          <div className="px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-violet-500" />
              <span className="text-sm font-semibold text-gray-800">Dominant Narratives</span>
            </div>
            <TabLink tab="narratives" label="View all" />
          </div>
          <div>
            {narrativeDominance.slice(0, 6).map((n, i) => (
              <div key={n.name} className="flex items-center gap-3 px-4 py-2.5" style={{ borderBottom: '1px solid #f5f5f5' }}>
                <span className="text-[10px] font-bold text-gray-400 w-4">{i + 1}</span>
                <span className="text-xs font-medium text-gray-800 flex-1 truncate">{n.name.replace(/_/g, ' ')}</span>
                <div className="w-16 h-1 bg-gray-100 overflow-hidden">
                  <div className="h-full" style={{ width: `${n.share}%`, backgroundColor: '#8b5cf6' }} />
                </div>
                <span className="text-xs font-bold text-gray-600 w-8 text-right">{n.share}%</span>
                <span className="text-[10px] text-gray-400 w-12 text-right">{n.influencerCount} infl</span>
                <span className="text-[10px] font-medium" style={{
                  color: n.confidence > 0.8 ? '#16a34a' : n.confidence > 0.5 ? '#d97706' : '#94a3b8'
                }}>{(n.confidence * 100).toFixed(0)}%</span>
              </div>
            ))}
            {narrativeDominance.length === 0 && <div className="px-4 py-6 text-sm text-gray-400 text-center">No narrative data</div>}
          </div>
        </div>

        {/* Cluster Intelligence */}
        <div className="bg-white overflow-hidden">
          <div className="px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-green-500" />
              <span className="text-sm font-semibold text-gray-800">Cluster Intelligence</span>
            </div>
            <TabLink tab="clusters" label="View all" />
          </div>
          <div>
            {clusterEval.map(c => {
              const sc = c.status === 'OVERHEATED' ? '#dc2626' : c.status === 'MIXED' ? '#d97706' : '#16a34a';
              return (
                <div key={c.clusterId} className="flex items-center gap-3 px-4 py-2.5" style={{ borderBottom: '1px solid #f5f5f5' }}>
                  <span className="text-xs font-medium text-gray-700 flex-1 truncate">{c.clusterId}</span>
                  <span className="text-[10px] font-bold" style={{ color: sc }}>{c.status}</span>
                  <span className="text-[10px] text-gray-500">Score {(c.score * 100).toFixed(0)}%</span>
                  <span className="text-[10px] font-bold" style={{ color: sc }}>{c.risk}</span>
                  <span className="text-[10px] text-gray-400">{c.totalEvents} ev</span>
                </div>
              );
            })}
            {clusterEval.length === 0 && <div className="px-4 py-6 text-sm text-gray-400 text-center">No cluster data</div>}
          </div>
        </div>
      </div>

      {/* ═══ Capital Flow (expanded) ═══ */}
      <div className="p-6 rounded-2xl" style={{ backgroundColor: '#0f172a' }} data-testid="flow-block">
        <h3 className="text-xs font-bold uppercase tracking-wider mb-4" style={{ color: '#94a3b8' }}>Capital Flow</h3>
        <div className="grid grid-cols-2 gap-8">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <ArrowUpRight size={14} style={{ color: '#4ade80' }} />
              <span className="text-xs font-bold uppercase" style={{ color: '#4ade80' }}>Inflow</span>
            </div>
            {capitalFlow.inflow.length > 0 ? capitalFlow.inflow.map((item, i) => (
              <div key={item.name + i} className="flex items-center gap-2 mb-1.5">
                <span className="text-xs" style={{ color: '#4ade80' }}>-{'>'}</span>
                <span className="text-sm" style={{ color: '#e2e8f0' }}>{item.name}</span>
                {item.pct != null && <span className="text-[10px]" style={{ color: '#4ade80' }}>+{(item.pct * 100).toFixed(1)}%</span>}
                {item.confidence != null && <span className="text-[10px]" style={{ color: '#64748b' }}>{(item.confidence * 100).toFixed(0)}% conf</span>}
              </div>
            )) : <p className="text-xs" style={{ color: '#475569' }}>No clear inflows</p>}
          </div>
          <div>
            <div className="flex items-center gap-2 mb-2">
              <ArrowDownRight size={14} style={{ color: '#f87171' }} />
              <span className="text-xs font-bold uppercase" style={{ color: '#f87171' }}>Outflow</span>
            </div>
            {capitalFlow.outflow.length > 0 ? capitalFlow.outflow.map((item, i) => (
              <div key={item.name + i} className="flex items-center gap-2 mb-1.5">
                <span className="text-xs" style={{ color: '#f87171' }}>{'<'}-</span>
                <span className="text-sm" style={{ color: '#e2e8f0' }}>{item.name}</span>
                {item.pct != null && <span className="text-[10px]" style={{ color: '#f87171' }}>{(item.pct * 100).toFixed(1)}%</span>}
                {item.confidence != null && <span className="text-[10px]" style={{ color: '#64748b' }}>{(item.confidence * 100).toFixed(0)}% conf</span>}
              </div>
            )) : <p className="text-xs" style={{ color: '#475569' }}>No clear outflows</p>}
          </div>
        </div>
        <div className="mt-4 pt-3" style={{ borderTop: '1px solid #1e293b' }}>
          <div className="flex items-center gap-3 text-xs">
            <span style={{ color: '#64748b' }}>Altseason Index:</span>
            <span className="font-bold" style={{ color: altIdx > 0.6 ? '#4ade80' : altIdx > 0.4 ? '#fbbf24' : '#f87171' }}>
              {(altIdx * 100).toFixed(0)}%
            </span>
            <span style={{ color: '#64748b' }}>·</span>
            <span className="font-medium" style={{ color: altSignal === 'rotation' ? '#4ade80' : '#94a3b8' }}>{altSignal}</span>
          </div>
        </div>
      </div>

      {/* ═══ Risk Alert (expanded) ═══ */}
      <div className="p-6 rounded-2xl" style={{ backgroundColor: '#1c1017' }} data-testid="risk-panel">
        <div className="flex items-center gap-2 mb-4">
          <AlertTriangle className="w-4 h-4" style={{ color: '#f87171' }} />
          <span className="text-sm font-bold" style={{ color: '#f87171' }}>Risk Alert</span>
          <span className="text-xs ml-auto" style={{ color: '#64748b' }}>CAS: {cas}/100 ({casLabel})</span>
        </div>
        <div className="space-y-3">
          {pumpTokens.length > 0 && (
            <div className="flex items-start gap-3">
              <span className="text-xs mt-0.5 flex-shrink-0" style={{ color: '#f87171' }}>-</span>
              <p className="text-sm" style={{ color: '#fca5a5' }}>
                <strong>{pumpTokens.length} tokens</strong> pumped without organic support
                <span style={{ color: '#f87171' }}> ({pumpTokens.slice(0, 5).map(t => t.token).join(', ')})</span>
              </p>
            </div>
          )}
          {lowCredCount > 0 && (
            <div className="flex items-start gap-3">
              <span className="text-xs mt-0.5 flex-shrink-0" style={{ color: '#fbbf24' }}>-</span>
              <p className="text-sm" style={{ color: '#fde68a' }}>
                <strong>{lowCredCount} low-credibility clusters</strong> detected — possible fake coordination
              </p>
            </div>
          )}
          {(casComponents.mentionVelocity || 0) > 20 && (
            <div className="flex items-start gap-3">
              <span className="text-xs mt-0.5 flex-shrink-0" style={{ color: '#fbbf24' }}>-</span>
              <p className="text-sm" style={{ color: '#fde68a' }}>
                High mention velocity (<strong>{(casComponents.mentionVelocity).toFixed(0)}/h</strong>) without confirmed capital flow
              </p>
            </div>
          )}
          {(casComponents.botProbability || 0) > 0.3 && (
            <div className="flex items-start gap-3">
              <span className="text-xs mt-0.5 flex-shrink-0" style={{ color: '#f87171' }}>-</span>
              <p className="text-sm" style={{ color: '#fca5a5' }}>
                Bot probability: <strong>{((casComponents.botProbability) * 100).toFixed(0)}%</strong> — automated activity detected
              </p>
            </div>
          )}
          {pumpTokens.length === 0 && lowCredCount === 0 && (
            <p className="text-sm" style={{ color: '#4ade80' }}>No significant risks detected. Market looks clean.</p>
          )}
          <div className="pt-3 mt-1" style={{ borderTop: '1px solid #2d1a22' }}>
            <p className="text-xs font-bold" style={{
              color: cas >= 60 ? '#f87171' : cas >= 30 ? '#fbbf24' : '#4ade80'
            }}>
              {cas >= 60 ? 'High risk environment — trade with caution' :
               cas >= 30 ? 'Moderate risk — verify signals before entering' :
               'Low risk — market conditions are favorable'}
            </p>
          </div>
        </div>
      </div>

      {/* ═══ F: Quick Access (flat) ═══ */}
      <section className="pt-4" data-testid="quick-access">
        <div className="flex flex-wrap gap-2">
          {[
            { tab: 'feed', label: 'Feed' }, { tab: 'actors', label: 'Actors' },
            { tab: 'graph', label: 'Graph' }, { tab: 'network', label: 'Network' },
            { tab: 'market', label: 'Market' }, { tab: 'credibility', label: 'Credibility' },
            { tab: 'news', label: 'News' }, { tab: 'radar', label: 'Radar' },
            { tab: 'clusters', label: 'Clusters' }, { tab: 'bot-detection', label: 'Bot Detection' },
            { tab: 'altseason', label: 'Altseason' }, { tab: 'lifecycle', label: 'Lifecycle' },
            { tab: 'narratives', label: 'Narratives' }, { tab: 'reality', label: 'Reality' },
            { tab: 'backers', label: 'Backers' },
          ].map(q => (
            <button key={q.tab} onClick={() => { window.history.pushState({}, '', `/twitter?tab=${q.tab}`); window.dispatchEvent(new PopStateEvent('popstate')); }}
              className="px-4 py-2 text-xs font-medium transition-colors" style={{ color: '#64748b', backgroundColor: '#f8fafc' }}
              data-testid={`quick-${q.tab}`}>
              {q.label} <ChevronRight size={10} className="inline ml-0.5" />
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

// ═══ Helper Components ═══

function StatusPill({ label, value, color }) {
  const colors = { blue: 'text-blue-400', green: 'text-green-400', purple: 'text-purple-400', red: 'text-red-400', gray: 'text-gray-400', cyan: 'text-cyan-400' };
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-gray-500">{label}:</span>
      <span className={`font-bold ${colors[color] || colors.gray}`}>{value}</span>
    </div>
  );
}

function MiniButton({ icon: Icon, label, tab }) {
  return (
    <button onClick={() => { window.history.pushState({}, '', `/twitter?tab=${tab}`); window.dispatchEvent(new PopStateEvent('popstate')); }}
      className="flex items-center gap-1.5 px-2.5 py-1 bg-gray-800 hover:bg-gray-700 rounded-lg text-xs text-gray-300 transition-colors">
      <Icon className="w-3 h-3" /><span>{label}</span>
    </button>
  );
}

function TabLink({ tab, label }) {
  return (
    <button onClick={() => { window.history.pushState({}, '', `/twitter?tab=${tab}`); window.dispatchEvent(new PopStateEvent('popstate')); }}
      className="text-[10px] text-blue-500 hover:text-blue-600 font-medium flex items-center gap-0.5">
      {label} <ChevronRight className="w-3 h-3" />
    </button>
  );
}

function PulseCard({ title, value, label, color, icon: Icon, detail }) {
  const text = { green: '#16a34a', red: '#dc2626', amber: '#d97706', orange: '#ea580c', blue: '#2563eb', gray: '#64748b' };
  const c = text[color] || text.gray;
  return (
    <div className="bg-white p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-4 h-4" style={{ color: c }} />
        <span className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">{title}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span className="text-2xl font-bold" style={{ color: c }}>{value}</span>
      </div>
      <div className="flex items-center justify-between mt-2">
        <span className="text-[10px] font-semibold" style={{ color: c }}>{label}</span>
        <span className="text-[10px] text-gray-400">{detail}</span>
      </div>
    </div>
  );
}

function CASMiniChart({ data, color }) {
  if (!data || data.length < 2) return null;
  const values = data.map(d => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 200, h = 32, pad = 2;
  const points = values.map((v, i) => {
    const x = pad + (i / (values.length - 1)) * (w - pad * 2);
    const y = pad + (1 - (v - min) / range) * (h - pad * 2);
    return `${x},${y}`;
  });
  const strokeColor = color === 'red' ? '#ef4444' : color === 'orange' ? '#f97316' : color === 'amber' ? '#f59e0b' : '#22c55e';
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-8 mt-0.5" preserveAspectRatio="none" data-testid="cas-mini-chart">
      <defs>
        <linearGradient id="casGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={strokeColor} stopOpacity="0.15" />
          <stop offset="100%" stopColor={strokeColor} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`${pad},${h} ${points.join(' ')} ${w - pad},${h}`} fill="url(#casGrad)" />
      <polyline points={points.join(' ')} fill="none" stroke={strokeColor} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

function getSignalQuality(t) {
  const timing = t.mentionCount < 50 ? 'EARLY' : t.mentionCount < 150 ? 'MID' : 'LATE';
  const purity = t.confidence > 0.7 ? 'CLEAN' : t.confidence > 0.4 ? 'NOISY' : 'SUSPECT';
  return { timing, purity };
}

function QuickTile({ tab, icon: Icon, label, color }) {
  const iconColors = {
    purple: 'text-purple-500', blue: 'text-blue-500', cyan: 'text-cyan-500', green: 'text-green-500',
    red: 'text-red-500', orange: 'text-orange-500', emerald: 'text-emerald-500', indigo: 'text-indigo-500',
    violet: 'text-violet-500', amber: 'text-amber-500', teal: 'text-teal-500', gray: 'text-gray-500',
  };
  return (
    <button onClick={() => { window.history.pushState({}, '', `/twitter?tab=${tab}`); window.dispatchEvent(new PopStateEvent('popstate')); }}
      className="flex flex-col items-center gap-1.5 p-3 bg-white hover:bg-gray-50 transition-all">
      <Icon className={`w-4.5 h-4.5 ${iconColors[color]}`} />
      <span className="text-[10px] font-medium text-gray-600">{label}</span>
    </button>
  );
}
