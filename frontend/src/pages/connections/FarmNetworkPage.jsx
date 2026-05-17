/**
 * Bot Detection — Decision Intelligence Engine v3
 * 
 * Product layer: What's happening → Why it matters → What to do.
 * Every @handle is clickable. Every metric is explained.
 */

import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { 
  RefreshCw, ZoomIn, ZoomOut, Maximize2, ExternalLink, X,
  AlertTriangle, TrendingUp, Shield, Eye, Activity, Target,
  ChevronRight, ArrowUpRight, Users, Info
} from 'lucide-react';
import { fetchFarmGraph } from '../../api/blocks15-28.api';

const FARM_PALETTE = ['#EF4444', '#F59E0B', '#8B5CF6', '#3B82F6', '#EC4899', '#10B981', '#F97316', '#6366F1'];
const DEFAULT_COLOR = '#6B7280';
const API = process.env.REACT_APP_BACKEND_URL;

const SIGNAL_ICONS = {
  COORDINATED_PUSH: TrendingUp,
  BOT_AMPLIFICATION: AlertTriangle,
  GHOST_ACCOUNTS: Eye,
  EXIT_RISK: Shield,
};
const SIGNAL_COLORS = { HIGH: 'text-red-500', MEDIUM: 'text-amber-500', LOW: 'text-gray-400' };
const SIGNAL_BG = { HIGH: 'bg-red-500/5', MEDIUM: 'bg-amber-500/5', LOW: 'bg-gray-50' };

const CLUSTER_TYPE_COLORS = {
  HIGH: { dot: '#EF4444', label: 'High risk — likely manipulation' },
  MEDIUM: { dot: '#F59E0B', label: 'Elevated — possible coordination' },
  LOW: { dot: '#10B981', label: 'Low risk — weak correlation' },
};

const RISK_COLORS = { HIGH: 'text-red-500', MEDIUM: 'text-amber-500', LOW: 'text-green-500', NONE: 'text-gray-400' };
const RISK_BG = { HIGH: 'bg-red-500/5', MEDIUM: 'bg-amber-500/5', LOW: 'bg-green-500/5', NONE: 'bg-gray-50' };

// ─── STATUS BADGE ───────────────────────────────────────
function ActorStatusBadge({ level }) {
  if (level === 'ELITE' || level === 'GOOD' || level === 'MODERATE' || level === 'RISKY')
    return <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/10 text-green-600 font-medium">Analyzed</span>;
  if (level === 'UNANALYZED')
    return <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-600 font-medium">Has data</span>;
  if (level === 'TARGET')
    return <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-200 text-gray-500 font-medium">Limited</span>;
  return null;
}

// ─── AUDIENCE COMPARE ───────────────────────────────────
function AudienceCompare({ onActorClick }) {
  const [actorA, setActorA] = useState('');
  const [actorB, setActorB] = useState('');
  const [actors, setActors] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [errorDetail, setErrorDetail] = useState(null);
  const [showA, setShowA] = useState(false);
  const [showB, setShowB] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/connections/network/actors-list`).then(r => r.json()).then(d => {
      if (d.ok) setActors(d.actors);
    }).catch(() => {});
  }, []);

  const cleanHandle = (val) => val.replace(/^@/, '').trim().toLowerCase();

  const doCompare = async () => {
    const a = cleanHandle(actorA);
    const b = cleanHandle(actorB);
    if (!a || !b) return;
    if (a === b) { setError('Cannot compare an account with itself'); return; }
    setLoading(true); setError(''); setErrorDetail(null); setResult(null);
    try {
      const resp = await fetch(`${API}/api/connections/network/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`);
      const data = await resp.json();
      if (data.ok) {
        setResult(data);
      } else {
        setError(data.error || 'Comparison failed');
        setErrorDetail(data);
      }
    } catch { setError('Network error'); }
    finally { setLoading(false); }
  };

  const handleKeyDown = (e) => { if (e.key === 'Enter') doCompare(); };

  const filteredA = actors.filter(a => {
    const q = cleanHandle(actorA);
    return q && a.actorId.toLowerCase().includes(q) && a.actorId !== cleanHandle(actorB);
  }).slice(0, 10);
  const filteredB = actors.filter(a => {
    const q = cleanHandle(actorB);
    return q && a.actorId.toLowerCase().includes(q) && a.actorId !== cleanHandle(actorA);
  }).slice(0, 10);

  return (
    <div className="mb-8" data-testid="audience-compare">
      <div className="flex items-center gap-3 mb-3">
        <span className="text-xs font-bold uppercase tracking-widest text-gray-400">Audience Compare</span>
        <span className="text-[10px] text-gray-300">any @handle</span>
      </div>

      {/* Input row */}
      <div className="flex items-end gap-3 mb-4">
        <div className="relative flex-1">
          <label className="text-xs text-gray-400 mb-1 block">Actor A</label>
          <input
            value={actorA}
            onChange={e => { setActorA(e.target.value); setShowA(true); setResult(null); setError(''); }}
            onFocus={() => setShowA(true)}
            onBlur={() => setTimeout(() => setShowA(false), 200)}
            onKeyDown={handleKeyDown}
            placeholder="type any @handle"
            className="w-full px-3 py-2 rounded-lg bg-gray-50 text-sm text-gray-900 focus:outline-none focus:ring-1 focus:ring-gray-300"
            data-testid="compare-input-a"
          />
          {showA && actorA && filteredA.length > 0 && (
            <div className="absolute z-30 top-full mt-1 w-full bg-white rounded-lg shadow-lg max-h-52 overflow-auto">
              {filteredA.map(a => (
                <button key={a.actorId} className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex items-center justify-between gap-2"
                  onMouseDown={() => { setActorA(a.actorId); setShowA(false); }}>
                  <span className="text-gray-900 truncate">@{a.actorId}</span>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <ActorStatusBadge level={a.level} />
                    {a.aqi > 0 && <span className="text-[10px] text-gray-400">AQI {a.aqi}</span>}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <span className="text-gray-300 text-sm pb-2 font-medium">vs</span>

        <div className="relative flex-1">
          <label className="text-xs text-gray-400 mb-1 block">Actor B</label>
          <input
            value={actorB}
            onChange={e => { setActorB(e.target.value); setShowB(true); setResult(null); setError(''); }}
            onFocus={() => setShowB(true)}
            onBlur={() => setTimeout(() => setShowB(false), 200)}
            onKeyDown={handleKeyDown}
            placeholder="type any @handle"
            className="w-full px-3 py-2 rounded-lg bg-gray-50 text-sm text-gray-900 focus:outline-none focus:ring-1 focus:ring-gray-300"
            data-testid="compare-input-b"
          />
          {showB && actorB && filteredB.length > 0 && (
            <div className="absolute z-30 top-full mt-1 w-full bg-white rounded-lg shadow-lg max-h-52 overflow-auto">
              {filteredB.map(a => (
                <button key={a.actorId} className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex items-center justify-between gap-2"
                  onMouseDown={() => { setActorB(a.actorId); setShowB(false); }}>
                  <span className="text-gray-900 truncate">@{a.actorId}</span>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <ActorStatusBadge level={a.level} />
                    {a.aqi > 0 && <span className="text-[10px] text-gray-400">AQI {a.aqi}</span>}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <button onClick={doCompare} disabled={loading || !actorA.trim() || !actorB.trim()}
          className="px-5 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
          data-testid="compare-btn">
          {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : 'Compare'}
        </button>
      </div>

      {/* Error with actionable detail */}
      {error && (
        <div className="mb-4 rounded-lg bg-red-50 p-3" data-testid="compare-error">
          <p className="text-sm text-red-600 font-medium">{error}</p>
          {errorDetail?.missingActors && (
            <p className="text-xs text-red-400 mt-1">
              {errorDetail.missingActors.map(h => `@${h}`).join(', ')} — no tweets collected yet. Only accounts with existing data can be compared.
            </p>
          )}
          {errorDetail?.suggestion && (
            <p className="text-xs text-gray-500 mt-1">{errorDetail.suggestion}</p>
          )}
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="flex items-center gap-2 mb-4 text-sm text-gray-400">
          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          <span>Analyzing behavioral patterns...</span>
        </div>
      )}

      {/* Results */}
      {result && <CompareResult result={result} onActorClick={onActorClick} />}
    </div>
  );
}

function DataStatusTag({ status }) {
  if (status === 'analyzed') return <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/10 text-green-600">Full analysis</span>;
  if (status === 'computed') return <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-600">Analyzed on-the-fly</span>;
  if (status === 'metadata_only') return <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-600">Limited data</span>;
  return null;
}

function CompareResult({ result, onActorClick }) {
  const o = result.overlap;
  const q = result.quality;
  const riskColor = RISK_COLORS[result.risk] || 'text-gray-500';
  const riskBg = RISK_BG[result.risk] || 'bg-gray-50';

  return (
    <div data-testid="compare-result">
      {/* Data quality notes */}
      {result.dataNotes && result.dataNotes.length > 0 && (
        <div className="flex items-start gap-2 mb-3 p-2.5 rounded-lg bg-blue-50/60">
          <Info className="w-3.5 h-3.5 text-blue-400 mt-0.5 shrink-0" />
          <div className="space-y-0.5">
            {result.dataNotes.map((note, i) => (
              <p key={i} className="text-xs text-blue-600">{note}</p>
            ))}
          </div>
        </div>
      )}

      {/* Classification banner */}
      <div className={`${riskBg} rounded-xl p-4 mb-4`}>
        <div className="flex items-center justify-between mb-1">
          <span className={`font-bold text-sm ${riskColor}`}>{result.classification}</span>
          <span className="text-xs text-gray-400">Relationship score: {(q.relationshipScore * 100).toFixed(0)}%</span>
        </div>
        <p className="text-sm text-gray-600">{result.howToUse}</p>
      </div>

      {/* Actors side by side */}
      <div className="grid grid-cols-5 gap-4 mb-4">
        <ActorSummaryCol actor={result.actorA} unique={o.uniqueA} label="A" onActorClick={onActorClick} />

        {/* Center — overlap visual */}
        <div className="col-span-1 flex flex-col items-center justify-center">
          <div className="relative w-24 h-24">
            <div className="absolute left-0 top-2 w-16 h-16 rounded-full border-2 border-blue-300 opacity-50" />
            <div className="absolute right-0 top-2 w-16 h-16 rounded-full border-2 border-purple-300 opacity-50" />
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-2xl font-bold text-gray-900">{(o.estimated * 100).toFixed(0)}%</span>
            </div>
          </div>
          <span className="text-xs text-gray-400 mt-1">Overlap</span>
        </div>

        <ActorSummaryCol actor={result.actorB} unique={o.uniqueB} label="B" onActorClick={onActorClick} />
      </div>

      {/* Breakdown grid */}
      <div className="grid grid-cols-4 gap-4 mb-4">
        <BreakdownItem label="Behavior Similarity" value={`${(o.behaviorSimilarity * 100).toFixed(0)}%`} high={o.behaviorSimilarity > 0.4} />
        <BreakdownItem label="Posting Time Sync" value={`${(o.timeSimilarity * 100).toFixed(0)}%`} high={o.timeSimilarity > 0.6} />
        <BreakdownItem label="Token Overlap" value={`${(o.tokenSimilarity * 100).toFixed(0)}%`} detail={o.sharedTokens.length > 0 ? o.sharedTokens.map(t => `$${t}`).join(' ') : '—'} />
        <BreakdownItem label="Bot Quality" value={`${(q.overlapBotRatio * 100).toFixed(0)}%`} high={q.overlapBotRatio > 0.25} />
      </div>

      {/* Interpretation */}
      <div className="space-y-1.5 mb-3">
        {result.interpretation.map((line, i) => (
          <p key={i} className="text-sm text-gray-700">{line}</p>
        ))}
      </div>

      {/* Shared cluster info */}
      {result.sharedCluster && (
        <div className="flex items-center gap-2 text-xs text-gray-500 pt-2 border-t border-gray-100">
          <Users className="w-3.5 h-3.5" />
          <span>Both in cluster: <strong className="text-gray-700">{result.sharedCluster.name}</strong></span>
          <span className={`font-bold ${RISK_COLORS[result.sharedCluster.riskLevel]}`}>{result.sharedCluster.riskLevel}</span>
        </div>
      )}
    </div>
  );
}

function ActorSummaryCol({ actor, unique, label, onActorClick }) {
  return (
    <div className="col-span-2 text-center">
      <div className="flex items-center justify-center gap-1.5 mb-1">
        <img src={`https://unavatar.io/twitter/${actor.id}`} alt="" className="w-6 h-6 rounded-full" onError={e => { e.target.src = `https://ui-avatars.com/api/?name=${actor.id}&size=24&background=random`; }} />
        <ActorLink handle={actor.id} onClick={onActorClick} className="text-sm font-semibold" />
      </div>
      <div className="flex items-center justify-center gap-1.5 mb-2">
        <DataStatusTag status={actor.dataStatus} />
      </div>
      <div className="flex justify-center gap-4 text-xs text-gray-500">
        <span>AQI {actor.aqi}</span>
        <span>Bot {actor.pctBot?.toFixed(0)}%</span>
        <span className="capitalize">{actor.category}</span>
      </div>
      <div className="mt-2">
        <span className="text-lg font-bold text-gray-900">{(unique * 100).toFixed(0)}%</span>
        <span className="text-xs text-gray-400 ml-1">unique</span>
      </div>
    </div>
  );
}

function BreakdownItem({ label, value, detail, high }) {
  return (
    <div className="text-center">
      <span className="text-xs text-gray-400">{label}</span>
      <p className={`font-bold text-lg ${high ? 'text-amber-500' : 'text-gray-900'}`}>{value}</p>
      {detail && <span className="text-xs text-gray-400">{detail}</span>}
    </div>
  );
}
function ActorLink({ handle, onClick, className = '' }) {
  return (
    <button
      onClick={(e) => { e.stopPropagation(); onClick(handle); }}
      className={`text-gray-600 hover:text-gray-900 hover:underline underline-offset-2 transition-colors ${className}`}
      data-testid={`actor-link-${handle}`}
    >
      @{handle}
    </button>
  );
}

function ActorTwitterLink({ handle }) {
  return (
    <a
      href={`https://twitter.com/${handle}`}
      target="_blank"
      rel="noopener noreferrer"
      className="text-gray-300 hover:text-blue-500 transition-colors inline-flex"
      onClick={(e) => e.stopPropagation()}
    >
      <ExternalLink className="w-3 h-3" />
    </a>
  );
}

// ─── PARSE @HANDLES IN TEXT → CLICKABLE LINKS ───────────
function RichText({ text, onActorClick }) {
  if (!text) return null;
  const parts = text.split(/(@\w+)/g);
  return (
    <span>
      {parts.map((part, i) => {
        if (part.startsWith('@') && part.length > 1) {
          const handle = part.slice(1);
          return <ActorLink key={i} handle={handle} onClick={onActorClick} className="text-xs font-medium" />;
        }
        return <span key={i}>{part}</span>;
      })}
    </span>
  );
}

// ─── ACTOR DETAIL MODAL (built for our data) ────────────
function ActorDetailModal({ isOpen, actor, loading, onClose, onActorClick, edges, farmColorMap, clusters }) {
  if (!isOpen) return null;

  const aq = actor?.audienceQuality || {};
  const breakdown = aq.breakdown || {};
  const engagement = aq.engagement || {};
  const connections = (edges || []).filter(e => {
    const s = typeof e.source === 'object' ? e.source.id : e.source;
    const t = typeof e.target === 'object' ? e.target.id : e.target;
    return s === actor?.id || t === actor?.id;
  });
  const cluster = (clusters || []).find(c => (c.members || []).includes(actor?.id));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" data-testid="actor-detail-modal">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-2xl max-w-xl w-full max-h-[85vh] overflow-hidden" style={{ fontFamily: 'Gilroy, system-ui, sans-serif' }} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src={`https://unavatar.io/twitter/${actor?.id}`} alt="" className="w-10 h-10 rounded-full bg-gray-100" onError={e => { e.target.src = `https://ui-avatars.com/api/?name=${actor?.id}&size=40&background=random`; }} />
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-gray-900">@{actor?.id || '...'}</span>
                <a href={`https://twitter.com/${actor?.id}`} target="_blank" rel="noopener noreferrer" className="text-gray-300 hover:text-blue-500"><ExternalLink className="w-3.5 h-3.5" /></a>
              </div>
              <div className="flex items-center gap-2 text-xs text-gray-400">
                {aq.category && <span className="capitalize">{aq.category}</span>}
                {aq.followers > 0 && <span>{(aq.followers / 1000).toFixed(0)}K followers</span>}
                {aq.tweetCount > 0 && <span>{aq.tweetCount} tweets analyzed</span>}
              </div>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-full transition-colors"><X className="w-4 h-4 text-gray-400" /></button>
        </div>

        <div className="px-6 pb-6 overflow-y-auto max-h-[calc(85vh-72px)] space-y-5">
          {loading ? (
            <div className="flex items-center justify-center py-12"><RefreshCw className="w-5 h-5 animate-spin text-gray-300" /></div>
          ) : (
            <>
              {/* Bot Influence Summary */}
              <div>
                <span className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-2 block">Audience Quality</span>
                <div className="grid grid-cols-4 gap-3">
                  <MetricBlock label="Bot Influence" value={`${aq.pctBot?.toFixed(0) || 0}%`} sub={aq.pctBot > 20 ? 'Suspicious audience detected' : 'Audience looks mostly organic'} color={aq.pctBot > 30 ? 'text-red-500' : aq.pctBot > 15 ? 'text-amber-500' : 'text-green-600'} />
                  <MetricBlock label="Human" value={`${aq.pctHuman?.toFixed(0) || 0}%`} sub="Real accounts" color="text-gray-900" />
                  <MetricBlock label="AQI Score" value={`${aq.aqi || 0}`} sub={aq.level || 'N/A'} color="text-gray-900" />
                  <MetricBlock label="Suspicious" value={`${aq.pctSuspicious?.toFixed(0) || 0}%`} sub="Needs monitoring" color="text-amber-500" />
                </div>
              </div>

              {/* What this means */}
              <div>
                <span className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-2 block">What this means</span>
                <div className="space-y-1.5 text-sm text-gray-700">
                  {aq.pctBot > 30 ? (
                    <p>This account has a significant suspicious audience ({aq.pctBot?.toFixed(0)}%). Engagement metrics from this actor should NOT be trusted at face value. Likes and views may be artificially inflated.</p>
                  ) : aq.pctBot > 10 ? (
                    <p>Some signs of inorganic activity detected ({aq.pctBot?.toFixed(0)}% suspicious). Not critical, but engagement should be cross-referenced with on-chain activity.</p>
                  ) : (
                    <p>Audience appears mostly organic ({aq.pctHuman?.toFixed(0)}% human). Engagement metrics can be considered reliable for signal analysis.</p>
                  )}
                </div>
              </div>

              {/* Engagement breakdown */}
              {(engagement.avgLikes > 0 || engagement.avgViews > 0) && (
                <div>
                  <span className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-2 block">Engagement Pattern</span>
                  <div className="grid grid-cols-3 gap-3">
                    <MetricBlock label="Avg Likes" value={engagement.avgLikes?.toFixed(0) || '0'} sub="per tweet" color="text-gray-900" />
                    <MetricBlock label="Avg Views" value={engagement.avgViews?.toFixed(0) || '0'} sub="per tweet" color="text-gray-900" />
                    <MetricBlock label="Zero Engagement" value={`${(engagement.zeroEngagementRatio * 100)?.toFixed(0) || 0}%`} sub={engagement.zeroEngagementRatio > 0.5 ? 'Ghost activity!' : 'Normal'} color={engagement.zeroEngagementRatio > 0.5 ? 'text-red-500' : 'text-gray-900'} />
                  </div>
                  {engagement.ghostScore > 0.3 && (
                    <p className="text-xs text-amber-600 mt-2">Ghost score elevated: high followers but low real engagement. Possible purchased followers.</p>
                  )}
                </div>
              )}

              {/* Cluster membership */}
              {cluster && (
                <div>
                  <span className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-2 block">Cluster Membership</span>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: farmColorMap[cluster.farmId] || DEFAULT_COLOR }} />
                    <span className="text-sm font-semibold text-gray-900">{cluster.name}</span>
                    <span className={`text-xs font-bold ${cluster.riskLevel === 'HIGH' ? 'text-red-500' : cluster.riskLevel === 'MEDIUM' ? 'text-amber-500' : 'text-green-500'}`}>{cluster.riskLevel}</span>
                  </div>
                  <p className="text-xs text-gray-500">{(cluster.interpretation || [])[0]}</p>
                </div>
              )}

              {/* Connected actors */}
              {connections.length > 0 && (
                <div>
                  <span className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-2 block">Connections ({connections.length})</span>
                  <div className="space-y-1.5">
                    {connections.slice(0, 8).map((edge, i) => {
                      const s = typeof edge.source === 'object' ? edge.source.id : edge.source;
                      const t = typeof edge.target === 'object' ? edge.target.id : edge.target;
                      const other = s === actor?.id ? t : s;
                      return (
                        <div key={i} className="flex items-center justify-between text-sm">
                          <div className="flex items-center gap-2">
                            <ActorLink handle={other} onClick={onActorClick} className="text-sm font-medium" />
                            <ActorTwitterLink handle={other} />
                          </div>
                          <div className="flex items-center gap-3 text-xs text-gray-400">
                            <span>Score {(edge.score * 100).toFixed(0)}%</span>
                            {(edge.sharedTokens || []).length > 0 && (
                              <span>{edge.sharedTokens.map(t => `$${t}`).join(' ')}</span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function MetricBlock({ label, value, sub, color = 'text-gray-900' }) {
  return (
    <div>
      <span className="text-xs text-gray-400">{label}</span>
      <p className={`font-bold text-lg ${color}`}>{value}</p>
      {sub && <span className="text-xs text-gray-400">{sub}</span>}
    </div>
  );
}

// ─── SIGNAL CARD ────────────────────────────────────────
function SignalCard({ signal, onActorClick }) {
  const Icon = SIGNAL_ICONS[signal.type] || Activity;
  const color = SIGNAL_COLORS[signal.severity] || 'text-gray-500';
  const bg = SIGNAL_BG[signal.severity] || 'bg-gray-50';
  
  return (
    <div className={`${bg} rounded-xl p-5 transition-all hover:scale-[1.005]`} data-testid={`signal-${signal.type}`}>
      <div className="flex items-start gap-3">
        <Icon className={`w-5 h-5 mt-0.5 ${color} shrink-0`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs font-bold uppercase tracking-wider ${color}`}>{signal.severity}</span>
            <span className="text-xs text-gray-400">confidence {(signal.confidence * 100).toFixed(0)}%</span>
          </div>
          <p className="font-semibold text-gray-900 text-sm leading-snug">{signal.title}</p>
          <p className="text-xs text-gray-500 mt-1">{signal.description}</p>
          {signal.detail && (
            <p className="text-xs text-gray-400 mt-1">
              <RichText text={signal.detail} onActorClick={onActorClick} />
            </p>
          )}
          <div className="mt-3 pt-2 border-t border-gray-200/50">
            <div className="flex items-center gap-1.5">
              <Target className="w-3.5 h-3.5 text-gray-400 shrink-0" />
              <span className="text-xs font-medium text-gray-700">{signal.action}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── PRIMARY CLUSTER HERO ───────────────────────────────
function PrimaryClusterHero({ cluster, color, onActorClick }) {
  if (!cluster) return null;
  const members = cluster.members || [];
  const tokens = (cluster.topTokens || []).map(t => `$${t.token}`).join(' & ');
  const howToUse = cluster.howToUse || [];
  
  return (
    <div className="mb-8" data-testid="primary-cluster">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: color }} />
        <span className="text-xs font-bold uppercase tracking-widest text-gray-400">Main Signal</span>
      </div>
      
      <div className="grid grid-cols-12 gap-6">
        {/* Left — identity */}
        <div className="col-span-4">
          <h2 className="text-2xl font-bold text-gray-900 mb-1">{cluster.name}</h2>
          <p className="text-sm text-gray-500 mb-4">
            {members.length} accounts coordinating around {tokens || 'multiple tokens'}
          </p>
          
          {/* Clickable members */}
          <div className="flex flex-wrap gap-x-3 gap-y-1 mb-4">
            {members.map(m => (
              <div key={m} className="flex items-center gap-1">
                <ActorLink handle={m} onClick={onActorClick} className="text-sm" />
                <ActorTwitterLink handle={m} />
              </div>
            ))}
          </div>

          {/* Metrics with explanations */}
          <div className="space-y-2">
            <MetricRow label="Bot Influence" value={`${(cluster.avgBotScore * 100).toFixed(0)}%`} explain={cluster.metricExplanations?.botScore} danger={cluster.avgBotScore > 0.3} />
            <MetricRow label="Coordination" value={`${(cluster.density * 100).toFixed(0)}%`} explain={cluster.metricExplanations?.density} danger={cluster.density > 0.7} />
            <MetricRow label="Confidence" value={`${(cluster.confidence * 100).toFixed(0)}%`} explain={cluster.metricExplanations?.confidence} />
            <MetricRow label="Risk" value={cluster.riskLevel} danger={cluster.riskLevel === 'HIGH'} warn={cluster.riskLevel === 'MEDIUM'} />
          </div>
        </div>

        {/* Center — Interpretation */}
        <div className="col-span-4">
          <span className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-3 block">What this means</span>
          <div className="space-y-2.5">
            {(cluster.interpretation || []).map((line, i) => (
              <p key={i} className="text-sm text-gray-700 leading-relaxed">{line}</p>
            ))}
          </div>
          {(cluster.evidence || []).length > 0 && (
            <div className="mt-3 space-y-1">
              {cluster.evidence.map((ev, i) => (
                <p key={i} className="text-xs text-gray-400">{ev}</p>
              ))}
            </div>
          )}
        </div>

        {/* Right — How to Use */}
        <div className="col-span-4">
          <span className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-3 block">How to use</span>
          <p className="text-sm text-gray-800 font-medium leading-relaxed mb-3">{cluster.action}</p>
          <div className="space-y-2">
            {howToUse.map((line, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-gray-600">
                <div className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${i === 0 ? 'bg-green-400' : i === 1 ? 'bg-amber-400' : 'bg-red-400'}`} />
                <span>{line}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricRow({ label, value, explain, danger, warn }) {
  const [showTip, setShowTip] = useState(false);
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="text-gray-400 w-28 shrink-0">{label}</span>
      <span className={`font-bold ${danger ? 'text-red-500' : warn ? 'text-amber-500' : 'text-gray-900'}`}>{value}</span>
      {explain && (
        <div className="relative">
          <button onMouseEnter={() => setShowTip(true)} onMouseLeave={() => setShowTip(false)} className="text-gray-300 hover:text-gray-500"><Info className="w-3 h-3" /></button>
          {showTip && (
            <div className="absolute left-4 bottom-0 z-50 w-64 p-2 bg-gray-900 text-white text-xs rounded-lg shadow-xl">
              {explain}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── CLUSTER CARD ───────────────────────────────────────
function ClusterCard({ cluster, color, onClick, onActorClick }) {
  const tokens = (cluster.topTokens || []).map(t => `$${t.token}`).join(', ');
  return (
    <div className="p-4 rounded-xl bg-gray-50/50 hover:bg-gray-100/50 transition-colors cursor-pointer" onClick={onClick} data-testid={`cluster-${cluster.farmId}`}>
      <div className="flex items-center gap-2 mb-2">
        <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
        <span className="font-semibold text-sm text-gray-900">{cluster.name}</span>
        <span className={`ml-auto text-xs font-bold ${cluster.riskLevel === 'HIGH' ? 'text-red-500' : cluster.riskLevel === 'MEDIUM' ? 'text-amber-500' : 'text-gray-400'}`}>{cluster.riskLevel}</span>
      </div>
      <div className="flex gap-4 text-xs text-gray-500 mb-2">
        <span>{cluster.memberCount || cluster.members?.length} members</span>
        <span>Bot {(cluster.clusterBotScore * 100).toFixed(0)}%</span>
        <span>Coordination {(cluster.density * 100).toFixed(0)}%</span>
      </div>
      <div className="flex flex-wrap gap-x-2 gap-y-0.5 mb-2">
        {(cluster.members || []).map(m => (
          <ActorLink key={m} handle={m} onClick={onActorClick} className="text-xs" />
        ))}
      </div>
      {tokens && <p className="text-xs text-gray-400">{tokens}</p>}
      <p className="text-xs text-gray-600 mt-1 line-clamp-2">{(cluster.interpretation || [])[0]}</p>
    </div>
  );
}

// ─── MAIN PAGE ──────────────────────────────────────────
export default function FarmNetworkPage() {
  const graphRef = useRef();
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [intel, setIntel] = useState({ primary: null, signals: [], clusters: [], stats: {} });
  const [loading, setLoading] = useState(true);
  const [minScore, setMinScore] = useState(0.25);
  const [selectedNode, setSelectedNode] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalActor, setModalActor] = useState(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [highlightFarm, setHighlightFarm] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);

  const farmColorMap = useMemo(() => {
    const map = {};
    const ids = new Set();
    intel.clusters.forEach(c => ids.add(c.farmId));
    graphData.nodes.forEach(n => { if (n.farmId) ids.add(n.farmId); });
    [...ids].sort().forEach((id, i) => { map[id] = FARM_PALETTE[i % FARM_PALETTE.length]; });
    return map;
  }, [intel.clusters, graphData.nodes]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [graphResp, intelResp] = await Promise.all([
        fetchFarmGraph(minScore, 200),
        fetch(`${API}/api/connections/network/intelligence`).then(r => r.json()),
      ]);

      const nodes = (graphResp.nodes || []).map(node => ({
        id: node.id, label: node.id, farmId: node.farmId || '',
        botScore: node.botScore || 0, pctBot: node.pctBot || 0,
        audienceQuality: node.audienceQuality || 50, level: node.level || 'UNKNOWN',
        risk: node.risk || 'low',
        connections: (graphResp.edges || []).filter(e => e.a === node.id || e.b === node.id).length,
      }));

      const edges = (graphResp.edges || []).map(edge => ({
        source: edge.a, target: edge.b,
        score: edge.edgeScore || edge.overlapScore || 0.5,
        behaviorSimilarity: edge.behaviorSimilarity || 0,
        tokenSimilarity: edge.tokenSimilarity || 0,
        sharedTokens: edge.sharedTokens || [],
        shared: edge.sharedSuspects || 0,
        evidence: edge.evidence || [],
        farmId: edge.farmId || '',
      }));

      setGraphData({ nodes, edges });
      if (intelResp.ok) setIntel(intelResp);
    } catch (err) {
      console.error('Load error:', err);
    } finally {
      setLoading(false);
    }
  }, [minScore]);

  useEffect(() => { loadData(); }, [loadData]);

  // Click actor → open modal with real data
  const openActorModal = useCallback(async (handleOrNode) => {
    const handle = typeof handleOrNode === 'string' ? handleOrNode : handleOrNode?.id;
    if (!handle) return;

    setModalLoading(true);
    setModalOpen(true);
    setModalActor({ id: handle });

    try {
      const resp = await fetch(`${API}/api/connections/network/actor/${encodeURIComponent(handle)}`);
      if (resp.ok) {
        const data = await resp.json();
        setModalActor({ id: handle, ...data.data });
      } else {
        // Fallback: use node data from graph
        const node = graphData.nodes.find(n => n.id === handle);
        setModalActor({ id: handle, audienceQuality: node ? { pctBot: node.pctBot, pctHuman: 100 - node.pctBot, aqi: node.audienceQuality, level: node.level } : {} });
      }
    } catch {
      setModalActor({ id: handle, audienceQuality: {} });
    } finally {
      setModalLoading(false);
    }
  }, [graphData.nodes]);

  const closeModal = useCallback(() => { setModalOpen(false); setModalActor(null); }, []);

  useEffect(() => {
    if (intel.primary && !highlightFarm) setHighlightFarm(intel.primary.farmId);
  }, [intel.primary, highlightFarm]);

  const primaryMembers = useMemo(() => new Set(intel.primary?.members || []), [intel.primary]);

  // ─── GRAPH RENDERING ─────────────────────────────────
  const paintNode = useCallback((node, ctx, globalScale) => {
    const isPrimary = primaryMembers.has(node.id);
    const isHighlighted = highlightFarm && node.farmId === highlightFarm;
    const isHovered = hoveredNode?.id === node.id;

    const base = isPrimary ? 5 : 3;
    const bonus = Math.min((node.connections || 0) * 0.4, 2);
    const radius = base + bonus + (isHovered ? 2 : 0);
    const alpha = (!highlightFarm || isHighlighted || isHovered) ? 1 : 0.15;

    ctx.beginPath();
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
    const fill = farmColorMap[node.farmId] || DEFAULT_COLOR;
    ctx.fillStyle = isHovered ? '#111827' : fill;
    ctx.globalAlpha = alpha;
    ctx.fill();

    if (isPrimary && !isHovered) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, radius + 3, 0, 2 * Math.PI);
      ctx.strokeStyle = fill;
      ctx.lineWidth = 1.5 / globalScale;
      ctx.globalAlpha = alpha * 0.3;
      ctx.stroke();
    }

    ctx.globalAlpha = alpha;
    const fontSize = Math.max(isPrimary ? 5 : 3.5, (isPrimary ? 6 : 4.5) / globalScale);
    ctx.font = `${isPrimary ? 600 : 400} ${fontSize}px Gilroy, system-ui, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillStyle = '#374151';
    ctx.fillText(`@${(node.id || '').slice(0, 14)}`, node.x, node.y + radius + 2);
    ctx.globalAlpha = 1;
  }, [hoveredNode, highlightFarm, farmColorMap, primaryMembers]);

  const linkColorFn = useCallback((link) => {
    const fId = link.farmId || '';
    const c = farmColorMap[fId] || DEFAULT_COLOR;
    const hi = !highlightFarm || link.farmId === highlightFarm;
    const r = parseInt(c.slice(1, 3), 16), g = parseInt(c.slice(3, 5), 16), b = parseInt(c.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${hi ? 0.4 + link.score * 0.4 : 0.05})`;
  }, [highlightFarm, farmColorMap]);

  const linkWidthFn = useCallback((link) => 0.3 + link.score * 2, []);

  const forceGraphData = useMemo(() => ({ nodes: graphData.nodes, links: graphData.edges }), [graphData]);

  // ─── RENDER ───────────────────────────────────────────
  if (loading) {
    return <div className="flex items-center justify-center py-32"><RefreshCw className="w-6 h-6 animate-spin text-gray-400" /></div>;
  }

  const hasClusters = intel.clusters.length > 0;
  const secondaryClusters = intel.clusters.slice(1);

  return (
    <div className="px-6 py-6 max-w-[1600px] mx-auto" data-testid="bot-detection-page" style={{ fontFamily: 'Gilroy, system-ui, sans-serif' }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Bot Detection</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            Coordinated manipulation intelligence — {intel.stats?.totalActors || 0} actors, {intel.stats?.totalEdges || 0} connections
          </p>
        </div>
        <button onClick={loadData} className="flex items-center gap-1.5 px-4 py-2 text-sm text-gray-600 hover:text-gray-900 rounded-lg hover:bg-gray-100 transition-colors" data-testid="refresh-btn">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* How to read this */}
      <div className="mb-6 text-sm text-gray-500 leading-relaxed" data-testid="how-to-read">
        <p>
          Clusters show groups of accounts acting together. <strong className="text-gray-700">High coordination</strong> = possible manipulation. <strong className="text-gray-700">High bot %</strong> = fake engagement. Click any <span className="text-gray-700 underline underline-offset-2">@account</span> to see full analysis.
        </p>
      </div>

      {/* Audience Compare */}
      <AudienceCompare onActorClick={openActorModal} />

      {!hasClusters && (
        <div className="text-center py-20 text-gray-400">
          <Shield className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No coordinated clusters detected</p>
        </div>
      )}

      {hasClusters && (
        <>
          {/* Signals */}
          {intel.signals.length > 0 && (
            <div className="mb-8" data-testid="signals-section">
              <span className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-3 block">Active Signals</span>
              <div className="grid grid-cols-2 gap-3">
                {intel.signals.map((s, i) => <SignalCard key={i} signal={s} onActorClick={openActorModal} />)}
              </div>
            </div>
          )}

          {/* Primary Cluster */}
          <PrimaryClusterHero cluster={intel.primary} color={farmColorMap[intel.primary?.farmId] || FARM_PALETTE[0]} onActorClick={openActorModal} />

          {/* Secondary Clusters */}
          {secondaryClusters.length > 0 && (
            <div className="mb-8">
              <span className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-3 block">Other Clusters</span>
              <div className="grid grid-cols-3 gap-3">
                {secondaryClusters.map(c => (
                  <ClusterCard key={c.farmId} cluster={c} color={farmColorMap[c.farmId] || DEFAULT_COLOR}
                    onClick={() => setHighlightFarm(highlightFarm === c.farmId ? intel.primary?.farmId : c.farmId)}
                    onActorClick={openActorModal}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Graph */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold uppercase tracking-widest text-gray-400">Network Graph</span>
              <div className="flex items-center gap-3">
                {/* Risk-based legend */}
                {Object.entries(CLUSTER_TYPE_COLORS).map(([risk, cfg]) => {
                  const count = intel.clusters.filter(c => c.riskLevel === risk).length;
                  if (!count) return null;
                  return (
                    <span key={risk} className="flex items-center gap-1.5 text-xs text-gray-400">
                      <div className="w-2 h-2 rounded-full" style={{ backgroundColor: cfg.dot }} />
                      {cfg.label} ({count})
                    </span>
                  );
                })}
                <div className="w-px h-4 bg-gray-200" />
                {/* Cluster legend */}
                {Object.entries(farmColorMap).map(([fid, clr]) => {
                  const farm = intel.clusters.find(c => c.farmId === fid);
                  return (
                    <button key={fid} onClick={() => setHighlightFarm(highlightFarm === fid ? null : fid)}
                      className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-lg transition-colors ${highlightFarm === fid ? 'bg-gray-200 text-gray-900' : 'text-gray-400 hover:text-gray-600'}`}>
                      <div className="w-2 h-2 rounded-full" style={{ backgroundColor: clr }} />
                      {farm?.name || fid}
                    </button>
                  );
                })}
                <div className="w-px h-4 bg-gray-200" />
                <div className="flex gap-1">
                  <button onClick={() => graphRef.current?.zoom(graphRef.current.zoom() * 1.5, 300)} className="p-1.5 rounded hover:bg-gray-100 transition text-gray-400"><ZoomIn className="w-3.5 h-3.5" /></button>
                  <button onClick={() => graphRef.current?.zoom(graphRef.current.zoom() / 1.5, 300)} className="p-1.5 rounded hover:bg-gray-100 transition text-gray-400"><ZoomOut className="w-3.5 h-3.5" /></button>
                  <button onClick={() => graphRef.current?.zoomToFit(400, 50)} className="p-1.5 rounded hover:bg-gray-100 transition text-gray-400"><Maximize2 className="w-3.5 h-3.5" /></button>
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-400">
                  <span>Threshold</span>
                  <input type="range" min="0.1" max="0.9" step="0.05" value={minScore} onChange={e => setMinScore(Number(e.target.value))} className="w-20 accent-gray-400" />
                  <span className="font-medium text-gray-600 w-8">{minScore.toFixed(2)}</span>
                </div>
              </div>
            </div>

            <div className="rounded-xl overflow-hidden bg-white" data-testid="graph-container">
              {graphData.nodes.length === 0 ? (
                <div className="h-[450px] flex items-center justify-center text-gray-400 text-sm">No connections above threshold</div>
              ) : (
                <ForceGraph2D
                  ref={graphRef}
                  graphData={forceGraphData}
                  width={Math.min(1560, typeof window !== 'undefined' ? window.innerWidth - 80 : 1200)}
                  height={450}
                  nodeCanvasObject={paintNode}
                  linkColor={linkColorFn}
                  linkWidth={linkWidthFn}
                  linkDirectionalParticles={1}
                  linkDirectionalParticleWidth={(link) => link.score > 0.35 ? 2 : 0}
                  onNodeClick={openActorModal}
                  onNodeHover={setHoveredNode}
                  cooldownTicks={80}
                  d3AlphaDecay={0.03}
                  d3VelocityDecay={0.35}
                  enableNodeDrag={true}
                  enableZoomPanInteraction={true}
                  backgroundColor="transparent"
                />
              )}
            </div>
            <div className="flex gap-4 mt-2 text-xs text-gray-300">
              <span>Node size = influence</span>
              <span>Node color = cluster</span>
              <span>Line thickness = coordination strength</span>
              <span>Glow = primary cluster</span>
            </div>
          </div>

          {/* Connections Table */}
          {graphData.edges.length > 0 && (
            <div className="mb-6">
              <span className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-3 block">Connections ({graphData.edges.length})</span>
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="connections-table">
                  <thead>
                    <tr className="text-xs text-gray-400 uppercase tracking-wider">
                      <th className="text-left py-2 font-medium">Pair</th>
                      <th className="text-center py-2 font-medium">Score</th>
                      <th className="text-center py-2 font-medium">Behavior</th>
                      <th className="text-center py-2 font-medium">Tokens</th>
                      <th className="text-left py-2 font-medium">Evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {graphData.edges.sort((a, b) => b.score - a.score).map((edge, idx) => {
                      const src = typeof edge.source === 'object' ? edge.source.id : edge.source;
                      const tgt = typeof edge.target === 'object' ? edge.target.id : edge.target;
                      const farmColor = farmColorMap[edge.farmId] || DEFAULT_COLOR;
                      return (
                        <tr key={idx} className="border-t border-gray-100 hover:bg-gray-50/50 transition-colors">
                          <td className="py-2.5">
                            <div className="flex items-center gap-2">
                              <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: farmColor }} />
                              <ActorLink handle={src} onClick={openActorModal} className="text-sm font-medium" />
                              <ChevronRight className="w-3 h-3 text-gray-300" />
                              <ActorLink handle={tgt} onClick={openActorModal} className="text-sm font-medium" />
                            </div>
                          </td>
                          <td className="text-center py-2.5"><span className="font-bold text-gray-900">{(edge.score * 100).toFixed(0)}%</span></td>
                          <td className="text-center py-2.5 text-gray-500">{(edge.behaviorSimilarity * 100).toFixed(0)}%</td>
                          <td className="text-center py-2.5">
                            {(edge.sharedTokens || []).length > 0 ? (
                              <span className="text-xs text-gray-500">{edge.sharedTokens.map(t => `$${t}`).join(' ')}</span>
                            ) : <span className="text-gray-300">—</span>}
                          </td>
                          <td className="py-2.5">
                            {(edge.evidence || []).length > 0 ? (
                              <span className="text-xs text-gray-500 line-clamp-1">{edge.evidence[0]}</span>
                            ) : <span className="text-gray-300 text-xs">—</span>}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Hovered node tooltip */}
          {hoveredNode && !modalOpen && (
            <div className="fixed bottom-6 right-6 bg-white rounded-xl shadow-xl p-4 w-72 z-40" data-testid="node-tooltip" style={{ fontFamily: 'Gilroy, system-ui, sans-serif' }}>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: farmColorMap[hoveredNode.farmId] || DEFAULT_COLOR }} />
                <span className="font-bold text-gray-900 text-sm">@{hoveredNode.id}</span>
                <a href={`https://twitter.com/${hoveredNode.id}`} target="_blank" rel="noopener noreferrer" className="ml-auto text-gray-400 hover:text-blue-500"><ExternalLink className="w-3.5 h-3.5" /></a>
              </div>
              <div className="grid grid-cols-3 gap-2 text-xs mb-3">
                <div><span className="text-gray-400">Bot</span><p className="font-bold text-gray-900">{hoveredNode.pctBot?.toFixed(0) || 0}%</p></div>
                <div><span className="text-gray-400">AQI</span><p className="font-bold text-gray-900">{hoveredNode.audienceQuality || 0}</p></div>
                <div><span className="text-gray-400">Links</span><p className="font-bold text-gray-900">{hoveredNode.connections || 0}</p></div>
              </div>
              <button onClick={() => openActorModal(hoveredNode)} className="w-full text-xs text-center py-1.5 text-gray-500 hover:text-gray-900 hover:bg-gray-50 rounded transition-colors">
                Click node for full analysis
              </button>
            </div>
          )}
        </>
      )}

      {/* Actor Detail Modal */}
      <ActorDetailModal
        isOpen={modalOpen}
        actor={modalActor}
        loading={modalLoading}
        onClose={closeModal}
        onActorClick={(handle) => { closeModal(); setTimeout(() => openActorModal(handle), 100); }}
        edges={graphData.edges}
        farmColorMap={farmColorMap}
        clusters={intel.clusters}
      />
    </div>
  );
}
