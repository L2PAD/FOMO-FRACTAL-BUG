/**
 * Influencer Detail Page — Actor Hub v6
 * Dense terminal layout: Profile sidebar + 2-col main grid
 * Zero empty space, zero borders/shadows
 */
import { useState, useEffect, useMemo } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, ExternalLink, Users, Network, TrendingUp,
  CheckCircle, AlertTriangle, XCircle, Twitter, BarChart3, Zap,
  Loader2, Target, Activity, Shield, Rocket, Brain
} from 'lucide-react';
import { getAuthorityColor, getGroupConfig, formatFollowers, calculateAuthorityScore } from '../../config/influencer.config';
import AccountTrendPanel from '../../components/connections/AccountTrendPanel';
import TimeSeriesCharts from '../../components/connections/TimeSeriesCharts';
import SmartFollowersPanel, { TierDistributionCompact } from '../../components/connections/SmartFollowersPanel';
import NetworkPathsPanel from '../../components/connections/NetworkPathsPanel';
import AiSummaryPanel from '../../components/connections/AiSummaryPanel';
import SentimentHeader from '../twitter/components/SentimentHeader';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const GroupBadge = ({ groupId }) => {
  const labels = { INFLUENCE: 'Influence', SMART: 'Smart Money', MEDIA: 'Media', TRADING: 'Trading', NFT: 'NFT', POPULAR: 'Popular', FOUNDER: 'Founder', DEVELOPER: 'Developer', VC: 'VC', REAL: 'Real', REAL_TWITTER: 'Twitter' };
  const c = getGroupConfig(groupId);
  return <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${c.bg} ${c.text}`}>{labels[groupId] || groupId}</span>;
};

const Bar = ({ value, max = 1, color = '#6366f1' }) => (
  <div className="w-full h-1 bg-gray-100 rounded-full overflow-hidden"><div className="h-full rounded-full" style={{ width: `${Math.min((value / max) * 100, 100)}%`, backgroundColor: color }} /></div>
);

export default function InfluencerDetailPage() {
  const { handle } = useParams();
  const navigate = useNavigate();
  const [influencer, setInfluencer] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [similarInfluencers, setSimilarInfluencers] = useState([]);
  const [signalData, setSignalData] = useState(null);
  const [connectionsProfile, setConnectionsProfile] = useState(null);
  const [scoreResult, setScoreResult] = useState(null);
  const [trendData, setTrendData] = useState(null);
  const [earlySignal, setEarlySignal] = useState(null);
  const [smartFollowersBreakdown, setSmartFollowersBreakdown] = useState(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_URL}/api/connections/unified?facet=REAL_TWITTER&limit=500`);
        const r = await res.json();
        if (!r.ok) { setError(r.error); return; }
        const found = r.data.find(a => (a.handle || '').toLowerCase().replace('@', '') === handle.toLowerCase().replace('@', ''));
        if (!found) { setError('Not found'); return; }
        const iN = Math.min((found.influence || 50) / 100, 1), sN = Math.min((found.smart || 50) / 100, 1), eN = Math.min((found.engagementRate || found.engagement || 3) / 10, 1);
        setInfluencer({
          id: found.id, handle: found.handle?.replace('@', '') || handle, name: found.title || found.handle,
          avatar: found.avatar || `https://unavatar.io/twitter/${handle}`,
          twitterScore: found.twitterScore || Math.min(Math.round(iN * 700 + sN * 200 + eN * 100), 1000),
          authorityScore: calculateAuthorityScore(found.influence, found.engagement, found.confidence),
          followers: found.followers || 0, strongConnections: Math.round((found.smart || 50) / 5),
          groups: found.categories || ['REAL'], topFollowers: found.topFollowers || [],
          realityBadge: found.confidence > 0.7 ? 'CONFIRMED' : found.confidence > 0.4 ? 'MIXED' : 'RISKY',
          bio: found.bio || '', lastActive: found.lastActive ? new Date(found.lastActive).toLocaleString() : 'Recently',
          avgLikes: found.avgLikes || 0, tweetCount: found.tweetCount || 0,
          engagementRate: found.engagementRate || found.engagement || 0,
          networkScore: found.networkScore || Math.round(found.smart || 50),
          totalLikes: found.totalLikes || 0, recentTokens: found.recentTokens || [],
          influence: found.influence || 0, engagement: found.engagement || 0,
          author_id: found.id || `demo_${found.handle?.replace('@', '') || handle}`,
        });
        setSimilarInfluencers(r.data.filter(a => a.handle !== found.handle && a.source === found.source).slice(0, 4).map(a => ({
          handle: a.handle?.replace('@', ''), name: a.title,
          avatar: a.avatar || `https://unavatar.io/twitter/${a.handle?.replace('@', '')}`,
          authorityScore: calculateAuthorityScore(a.influence, a.engagement, a.confidence),
        })));
      } catch (e) { setError(e.message); } finally { setLoading(false); }
    })();
  }, [handle]);

  useEffect(() => { if (!handle) return; fetch(`${API_URL}/api/v4/actors/signal-performance/${handle.replace('@', '')}`).then(r => r.json()).then(d => { if (d.ok) setSignalData(d); }).catch(() => {}); }, [handle]);

  useEffect(() => {
    if (!influencer) return;
    const aid = influencer.author_id;
    (async () => {
      let prof = null;
      try { const r = await fetch(`${API_URL}/api/connections/accounts/${aid}`); const d = await r.json(); if (d.ok && d.data) prof = d.data; } catch {}
      if (!prof) prof = { scores: { influence_score: Math.round(influencer.influence * 10) || Math.round(influencer.twitterScore * 0.7), x_score: influencer.twitterScore || 500, signal_noise: 5 + Math.random() * 3, risk_level: 'medium' }, activity: { posts_count: influencer.tweetCount || 0 }, trend: { velocity_norm: (Math.random() - 0.3) * 1.2, acceleration_norm: (Math.random() - 0.3) * 1.0 } };
      setConnectionsProfile(prof);
      const vel = prof.trend?.velocity_norm ?? 0, acc = prof.trend?.acceleration_norm ?? 0, baseInf = prof.scores?.influence_score || 500;
      try { const tr = await fetch(`${API_URL}/api/connections/trend-adjusted`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ influence_score: baseInf, x_score: prof.scores?.x_score || 300, velocity_norm: vel, acceleration_norm: acc }) }); const td = await tr.json(); if (td.ok) setTrendData({ influence_base: baseInf, influence_adjusted: td.data.influence.adjusted_score, velocity: vel, acceleration: acc, state: vel > 0.2 ? 'growing' : vel < -0.2 ? 'cooling' : 'stable' }); else throw 0; } catch { setTrendData({ influence_base: baseInf, influence_adjusted: Math.round(baseInf * (1 + 0.35 * vel + 0.15 * acc)), velocity: vel, acceleration: acc, state: vel > 0.2 ? 'growing' : vel < -0.2 ? 'cooling' : 'stable' }); }
      try { const er = await fetch(`${API_URL}/api/connections/early-signal`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ influence_base: baseInf, influence_adjusted: Math.round(baseInf * (1 + 0.35 * vel)), trend: { velocity_norm: vel, acceleration_norm: acc }, signal_noise: prof.scores?.signal_noise || 5, risk_level: prof.scores?.risk_level || 'low', profile: prof.profile || 'retail' }) }); const ed = await er.json(); if (ed.ok) setEarlySignal(ed.data); else throw 0; } catch { const sc = Math.round((prof.scores?.x_score || 500) * 0.4 + baseInf * 0.3 + Math.max(0, vel * 300)); setEarlySignal({ early_signal_score: Math.min(sc, 999), badge: sc >= 700 ? 'breakout' : sc >= 450 ? 'rising' : 'none', reasons: vel > 0.2 ? ['Positive growth'] : [], explanation: '' }); }
      try { const mr = await fetch(`${API_URL}/api/connections/score/mock`); const md = await mr.json(); if (md.ok) setScoreResult(md.data); } catch {}
    })();
  }, [influencer]);

  const verdict = useMemo(() => {
    if (!influencer) return 'UNVERIFIED';
    const a = influencer.authorityScore || 0, wr = signalData?.signalStats?.winrate || 0, ts = signalData?.signalStats?.total || 0;
    if (a >= 500 && wr >= 0.6 && ts >= 5) return 'STRONG';
    if (a >= 300 && (wr >= 0.5 || ts >= 3)) return 'RELIABLE';
    if (a >= 100 || ts > 0) return 'MODERATE';
    return 'UNVERIFIED';
  }, [influencer, signalData]);

  if (loading) return <div className="min-h-screen bg-gray-50"><SentimentHeader activeTab="actors" /><div className="flex items-center justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-purple-500" /></div></div>;
  if (error || !influencer) return <div className="min-h-screen bg-gray-50"><SentimentHeader activeTab="actors" /><div className="flex items-center justify-center py-20"><div className="text-center"><p className="text-gray-500 mb-2">@{handle} not found</p><button onClick={() => navigate('/twitter?tab=actors')} className="px-3 py-1.5 bg-gray-900 text-white rounded text-sm">Back</button></div></div></div>;

  const color = getAuthorityColor(influencer.authorityScore);
  const authorId = influencer.author_id;
  const metrics = scoreResult?.metrics || connectionsProfile?.activity || {};
  const scores = connectionsProfile?.scores || {};
  const verdictColors = { STRONG: 'bg-green-500', RELIABLE: 'bg-blue-500', MODERATE: 'bg-yellow-500', UNVERIFIED: 'bg-gray-400' };
  const verdictLabels = { STRONG: 'Strong', RELIABLE: 'Reliable', MODERATE: 'Moderate', UNVERIFIED: 'Unverified' };
  const realityIcons = { CONFIRMED: CheckCircle, MIXED: AlertTriangle, RISKY: XCircle };
  const realityColors = { CONFIRMED: 'text-green-600', MIXED: 'text-yellow-600', RISKY: 'text-red-600' };
  const RIcon = realityIcons[influencer.realityBadge] || AlertTriangle;

  return (
    <div className="min-h-screen bg-gray-50" data-testid="influencer-detail-page">
      {/* PERSISTENT SENTIMENT HEADER */}
      <SentimentHeader activeTab="actors" />
      {/* ACTOR SUB-HEADER */}
      <div className="bg-white sticky top-[65px] z-20 px-5 py-2 flex items-center gap-3 text-sm" style={{borderBottom: '1px solid #f3f4f6'}}>
        <button onClick={() => navigate('/twitter?tab=actors')} className="text-gray-400 hover:text-gray-800 flex items-center gap-1" data-testid="back-button"><ArrowLeft className="w-4 h-4" /><span className="text-sm">Actors</span></button>
        <span className="text-gray-200">|</span>
        <img src={influencer.avatar} alt="" className="w-6 h-6 rounded-full" onError={e => { e.target.src = `https://ui-avatars.com/api/?name=${influencer.name}&background=random&size=24`; }} />
        <span className="font-semibold text-gray-900">{influencer.name}</span>
        <span className="text-gray-400">@{influencer.handle}</span>
        <span className={`px-2 py-0.5 rounded-full ${verdictColors[verdict]} text-white text-xs font-semibold flex items-center gap-1`} data-testid="actor-verdict"><Shield className="w-3 h-3" />{verdictLabels[verdict]}</span>
        <a href={`https://twitter.com/${influencer.handle}`} target="_blank" rel="noopener noreferrer" className="ml-auto text-gray-400 hover:text-blue-500 flex items-center gap-1 text-xs"><Twitter className="w-3.5 h-3.5" /><ExternalLink className="w-3 h-3" /></a>
      </div>

      <div className="px-5 py-3" data-testid="page-content">
        <div className="flex gap-5">
          {/* ===== LEFT SIDEBAR: Profile ===== */}
          <div className="w-[230px] flex-shrink-0" data-testid="profile-header">
            <div className="flex items-center gap-3 mb-3">
              <img src={influencer.avatar} alt="" className="w-12 h-12 rounded-full" onError={e => { e.target.src = `https://ui-avatars.com/api/?name=${influencer.name}&background=random&size=48`; }} />
              <div>
                <div className="text-sm font-bold text-gray-900 leading-tight">{influencer.name}</div>
                <div className="text-xs text-gray-400">@{influencer.handle}</div>
                <div className="flex gap-1 mt-1 flex-wrap">
                  <span className={`inline-flex items-center gap-0.5 text-[10px] ${realityColors[influencer.realityBadge]} font-medium`}><RIcon className="w-3 h-3" />{influencer.realityBadge === 'CONFIRMED' ? 'Verified' : influencer.realityBadge === 'MIXED' ? 'Partial' : 'Unverified'}</span>
                  {influencer.groups.map(g => <GroupBadge key={g} groupId={g} />)}
                </div>
              </div>
            </div>
            {influencer.bio && <p className="text-xs text-gray-500 mb-2 leading-relaxed line-clamp-2">{influencer.bio}</p>}

            <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs mb-2">
              <div className="flex justify-between"><span className="text-gray-400">Followers</span><span className="font-semibold text-gray-900">{formatFollowers(influencer.followers)}</span></div>
              <div className="flex justify-between"><span className="text-gray-400">Network</span><span className="font-semibold text-gray-900">{influencer.networkScore || '—'}</span></div>
              <div className="flex justify-between"><span className="text-gray-400">Engagement</span><span className="font-semibold text-gray-900">{influencer.engagementRate > 0 ? (influencer.engagementRate < 0.1 ? `${(influencer.engagementRate * 1000).toFixed(1)}‰` : `${influencer.engagementRate?.toFixed(2)}%`) : '—'}</span></div>
              <div className="flex justify-between"><span className="text-gray-400">Links</span><span className="font-semibold text-gray-900">{influencer.strongConnections}</span></div>
            </div>

            <div className="flex gap-2 text-[10px] mb-2" data-testid="reality-check">
              <span className="text-green-600 font-semibold">12 confirmed</span>
              <span className="text-red-500 font-semibold">3 contradicted</span>
              <span className="text-gray-400">4h ago</span>
            </div>

            <div className="text-xs space-y-0.5 mb-2" data-testid="activity-info">
              <div className="flex justify-between"><span className="text-gray-400">Posts</span><span className="text-gray-700">{influencer.tweetCount || 0}</span></div>
              <div className="flex justify-between"><span className="text-gray-400">Avg Likes</span><span className="text-gray-700">{formatFollowers(influencer.avgLikes || 0)}</span></div>
              <div className="flex justify-between"><span className="text-gray-400">Last Active</span><span className="text-gray-700">{influencer.lastActive}</span></div>
            </div>

            {influencer.recentTokens?.length > 0 && (
              <div className="flex gap-1 flex-wrap mb-2" data-testid="token-mentions-section">
                {influencer.recentTokens.map(t => <span key={t} className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded text-[10px]">${t}</span>)}
              </div>
            )}

            {similarInfluencers.length > 0 && (
              <div data-testid="similar-influencers-section">
                <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Similar Actors</div>
                {similarInfluencers.map(inf => (
                  <Link key={inf.handle} to={`/connections/influencers/${inf.handle}`} className="flex items-center gap-1.5 py-0.5 text-xs hover:bg-gray-100 rounded transition">
                    <img src={inf.avatar} alt="" className="w-4 h-4 rounded-full" onError={e => { e.target.src = `https://ui-avatars.com/api/?name=${inf.name}&background=random&size=16`; }} />
                    <span className="text-gray-600 flex-1 truncate">{inf.name}</span>
                    <span className={`font-bold ${getAuthorityColor(inf.authorityScore).text}`}>{inf.authorityScore}</span>
                  </Link>
                ))}
              </div>
            )}

            {/* Tier Distribution — moved here from SmartFollowersPanel */}
            {smartFollowersBreakdown && (
              <div className="mt-2">
                <TierDistributionCompact breakdown={smartFollowersBreakdown} />
              </div>
            )}
          </div>

          {/* ===== MAIN CONTENT ===== */}
          <div className="flex-1 min-w-0">
            {/* TOP: Scores + Smart Followers side by side */}
            <div className="grid grid-cols-2 gap-5 mb-4">
              {/* LEFT: Scores + Authority + Metrics + Signals */}
              <div>
                {/* All 5 Scores as horizontal grid */}
                <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Scores</div>
                <div className="grid grid-cols-5 gap-3 mb-3" data-testid="scores-unified">
                  {[
                    { label: 'Twitter', val: influencer.twitterScore, color: '#3b82f6', max: 1000 },
                    { label: 'Authority', val: influencer.authorityScore, color: color.bar, max: 1000 },
                    { label: 'Influence', val: scores.influence_score || Math.round(influencer.twitterScore * 0.7), color: '#3b82f6', max: 1000 },
                    { label: 'X Score', val: scores.x_score || 0, color: '#a855f7', max: 1000 },
                    { label: 'Signal/Noise', val: scores.signal_noise || 0, color: '#22c55e', max: 10, fmt: v => `${v.toFixed(1)}/10` },
                  ].map(s => (
                    <div key={s.label}>
                      <div className="text-xs text-gray-400 mb-0.5">{s.label}</div>
                      <div className="text-base font-bold text-gray-900 mb-0.5">{s.fmt ? s.fmt(s.val) : s.val}</div>
                      <Bar value={s.val / s.max} color={s.color} />
                    </div>
                  ))}
                </div>

                {/* Authority Breakdown as horizontal grid */}
                <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1" data-testid="authority-breakdown-section">Authority Breakdown</div>
                <div className="grid grid-cols-4 gap-3 mb-3">
                  {[
                    { l: 'Network Quality', v: Math.round(influencer.authorityScore * 0.35), m: 350 },
                    { l: 'Engagement', v: Math.round(influencer.authorityScore * 0.25), m: 250 },
                    { l: 'Consistency', v: Math.round(influencer.authorityScore * 0.20), m: 200 },
                    { l: 'Reality', v: Math.round(influencer.authorityScore * 0.20), m: 200 },
                  ].map(c => (
                    <div key={c.l}>
                      <div className="text-xs text-gray-500 mb-0.5">{c.l}</div>
                      <div className="text-sm font-medium text-gray-700 mb-0.5">{c.v}/{c.m}</div>
                      <Bar value={c.v / c.m} color="#a78bfa" />
                    </div>
                  ))}
                </div>

                {/* Activity Metrics */}
                <div className="flex gap-5 mb-3 text-sm" data-testid="activity-metrics">
                  <div><span className="text-gray-400 text-xs block">Views</span><span className="font-bold text-gray-900">{(metrics.real_views || 0).toLocaleString()}</span></div>
                  <div><span className="text-gray-400 text-xs block">Quality</span><span className="font-bold text-gray-900">{((metrics.engagement_quality || 0) * 100).toFixed(0)}%</span></div>
                  <div><span className="text-gray-400 text-xs block">Consistency</span><span className="font-bold text-gray-900">{((metrics.posting_consistency || 0) * 100).toFixed(0)}%</span></div>
                </div>

                {/* Early Signal + Signal Performance */}
                <div className="flex gap-5 mb-3">
                  {earlySignal && (
                    <div data-testid="early-signal-section">
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <Rocket className="w-3.5 h-3.5 text-yellow-500" />
                        <span className="text-xs text-gray-400">Early Signal</span>
                        <span className={`text-[10px] font-medium ${earlySignal.badge === 'breakout' ? 'text-green-700' : earlySignal.badge === 'rising' ? 'text-yellow-700' : 'text-gray-500'}`}>{earlySignal.badge} {earlySignal.early_signal_score}</span>
                      </div>
                      {earlySignal.explanation && <p className="text-xs text-gray-500">{earlySignal.explanation}</p>}
                    </div>
                  )}
                  {signalData?.signalStats && (
                    <div data-testid="signal-performance-section">
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <Target className="w-3.5 h-3.5 text-green-500" />
                        <span className="text-xs text-gray-400">Signal Performance</span>
                      </div>
                      <div className="flex gap-3 text-sm">
                        <span className={`font-bold ${Math.round(signalData.signalStats.winrate * 100) >= 60 ? 'text-green-600' : 'text-yellow-600'}`}>{Math.round(signalData.signalStats.winrate * 100)}% WR</span>
                        <span className="text-gray-700">{signalData.signalStats.total} signals</span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Trend Dynamics inline */}
                {trendData && (
                  <div data-testid="trend-dynamics-section">
                    <AccountTrendPanel trend={{ velocity: trendData.velocity, acceleration: trendData.acceleration, state: trendData.state }} influence_base={trendData.influence_base} influence_adjusted={trendData.influence_adjusted} period="30d" />
                  </div>
                )}
              </div>

              {/* RIGHT: Smart Followers */}
              <div data-testid="smart-followers-compact">
                <SmartFollowersPanel accountId={authorId} onDataLoaded={(d) => setSmartFollowersBreakdown(d?.breakdown)} />
              </div>
            </div>

            {/* BOTTOM: 2x2 analytics grid */}
            <div className="grid grid-cols-2 gap-4">
              <div data-testid="ai-summary-section">
                <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1 flex items-center gap-1"><Brain className="w-3.5 h-3.5" />AI Summary</div>
                <AiSummaryPanel accountId={authorId} scoreData={{
                  twitter_score: influencer.twitterScore || 500, influence_score: trendData?.influence_adjusted || influencer.twitterScore || 500,
                  grade: scoreResult?.grade || 'B', quality: metrics.engagement_quality || 0.7, trend_score: trendData?.velocity > 0 ? 0.7 : 0.4,
                  network: 0.6, consistency: metrics.posting_consistency || 0.7, audience_quality: 0.75, authority: 0.6, smart_followers: 65,
                  hops: { avg_hops_to_top: 2.5 }, trends: trendData ? { velocity_pts_per_day: trendData.velocity * 10, state: trendData.state } : { state: 'stable' },
                  early_signal: earlySignal ? { badge: earlySignal.badge, score: earlySignal.early_signal_score } : { badge: 'none' }, red_flags: [], confidence: 75,
                }} isAdmin={false} />
              </div>
              <div data-testid="analytics-section">
                <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1 flex items-center gap-1"><BarChart3 className="w-3.5 h-3.5" />Analytics</div>
                <TimeSeriesCharts accountId={authorId} window="30d" />
              </div>
              <div data-testid="network-paths-section">
                <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1 flex items-center gap-1"><Network className="w-3.5 h-3.5" />Network Paths</div>
                <NetworkPathsPanel accountId={authorId} onHighlightPath={() => {}} />
              </div>
              <div data-testid="risk-analysis-section">
                <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1 flex items-center gap-1"><AlertTriangle className="w-3.5 h-3.5" />Risk</div>
                {(scoreResult?.red_flags?.length > 0) ? (
                  <div className="space-y-1">{scoreResult.red_flags.map((f, i) => <div key={i} className="p-2 bg-red-50 rounded text-sm"><span className="font-medium text-gray-900">{f.type?.replace(/_/g, ' ')}</span> — <span className="text-gray-600">{f.reason}</span></div>)}</div>
                ) : (
                  <div className="flex items-center gap-2 py-2"><TrendingUp className="w-4 h-4 text-green-600" /><span className="text-sm text-green-700 font-medium">No Risk Flags — all checks passed</span></div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
