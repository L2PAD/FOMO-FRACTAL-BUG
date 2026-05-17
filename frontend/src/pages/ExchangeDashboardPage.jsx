/**
 * Exchange Overview v2 — Profit-First War Room
 * =============================================
 * 
 * Answer in 10 seconds:
 * 1. Where is BTC going
 * 2. What alts are moving and why
 * 3. Which alts are next (Alt Radar)
 * 4. What risks are active
 */

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { 
  Activity, TrendingUp, TrendingDown, Minus, ArrowRight,
  Zap, Shield, BarChart3, Radar, FlaskConical, TestTubes, Globe,
  RefreshCw, Loader2, AlertTriangle, CheckCircle, XCircle,
  Crosshair
} from 'lucide-react';
import { api } from '@/api/client';

const API = process.env.REACT_APP_BACKEND_URL;

/* ═══════════════════════════════════════════════════════════
   HELPERS
═══════════════════════════════════════════════════════════ */
const fmtVol = (v) => {
  if (!v) return '$0';
  if (v >= 1e9) return `$${(v/1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v/1e6).toFixed(1)}M`;
  if (v >= 1e3) return `$${(v/1e3).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
};

const fmtPct = (v) => v ? `${v >= 0 ? '+' : ''}${v.toFixed(1)}%` : '—';

const biasFromRegime = (regime, pressure) => {
  if (regime === 'TRENDING' && pressure > 0) return { label: 'Risk-On', color: 'bg-emerald-100 text-emerald-700' };
  if (regime === 'DISTRIBUTION' || regime === 'SQUEEZE') return { label: 'Risk-Off', color: 'bg-red-100 text-red-700' };
  return { label: 'Neutral', color: 'bg-gray-100 text-gray-600' };
};

const directionFromPressure = (p) => {
  if (p > 0.15) return { label: 'Up', icon: TrendingUp, color: 'text-emerald-600' };
  if (p < -0.15) return { label: 'Down', icon: TrendingDown, color: 'text-red-600' };
  return { label: 'Range', icon: Minus, color: 'text-gray-500' };
};

const strengthLabel = (v) => {
  const abs = Math.abs(v || 0);
  if (abs > 0.4) return 'Strong';
  if (abs > 0.15) return 'Medium';
  return 'Weak';
};

/* ═══════════════════════════════════════════════════════════
   MAIN COMPONENT
═══════════════════════════════════════════════════════════ */
export default function ExchangeDashboardPage() {
  const [, setSearchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [markets, setMarkets] = useState([]);
  const [signals, setSignals] = useState(null);
  const [research, setResearch] = useState(null);
  const [radar, setRadar] = useState(null);
  const [tactical, setTactical] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    try {
      const [ovRes, uniRes, sigRes, resRes, radarRes, tactRes] = await Promise.all([
        api.get('/api/v10/exchange/overview').catch(() => ({ data: { ok: false } })),
        api.get('/api/v10/exchange/universe?status=INCLUDED').catch(() => ({ data: { ok: false, items: [] } })),
        api.get('/api/v10/exchange/signals/combined').catch(() => ({ data: null })),
        api.get('/api/v10/exchange/research/hypotheses').catch(() => ({ data: null })),
        fetch(`${API}/api/v10/exchange/alt-radar/state`).then(r => r.json()).catch(() => null),
        api.get('/api/tactical/1d?asset=BTC').catch(() => ({ data: null })),
      ]);
      if (ovRes.data?.ok) setData(ovRes.data.data);
      if (uniRes.data?.ok && uniRes.data.items) {
        setMarkets(uniRes.data.items.sort((a,b) => (b.scores?.universeScore||0)-(a.scores?.universeScore||0)));
      }
      if (sigRes.data) setSignals(sigRes.data);
      if (resRes.data) setResearch(resRes.data);
      if (radarRes) setRadar(radarRes);
      if (tactRes.data?.ok) setTactical(tactRes.data);
    } catch (e) {
      console.error('Overview fetch:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const iv = setInterval(fetchAll, 60000);
    return () => clearInterval(iv);
  }, [fetchAll]);

  const navigateTab = (tab) => setSearchParams({ tab }, { replace: true });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
      </div>
    );
  }

  const pressure = data?.aggressionRatio || 0;
  const bias = biasFromRegime(data?.regime, pressure);
  const dir = directionFromPressure(pressure);
  const confidence = Math.min(99, Math.round(Math.abs(pressure) * 200 + (data?.volatilityIndex || 0) * 0.3));
  const liqRisk = (data?.liquidationPressure || 0) > 50 ? 'High' : (data?.liquidationPressure || 0) > 20 ? 'Medium' : 'Low';
  const DirIcon = dir.icon;
  const altCondition = (data?.volatilityIndex || 0) > 40 ? 'Rotation' : pressure > 0.1 ? 'Alts allowed' : 'BTC-only';
  const riskCount = ((data?.liquidationPressure || 0) > 30 ? 1 : 0) + ((data?.volatilityIndex || 0) > 60 ? 1 : 0);

  // Drivers
  const drivers = [];
  if (Math.abs(pressure) > 0.1) drivers.push(pressure > 0 ? 'Exchange Pressure Up' : 'Exchange Pressure Down');
  if ((data?.volatilityIndex || 0) > 40) drivers.push('Volatility Elevated');
  if ((data?.liquidationPressure || 0) > 30) drivers.push('Liquidation Risk');
  if (!drivers.length) drivers.push('Low Activity');

  return (
    <div className="min-h-screen bg-[#F7F8FA]" data-testid="exchange-overview">
      <div className="max-w-[1400px] mx-auto px-6 py-5 space-y-6">

        {/* ══════════ 1. MARKET CONTROL BAR ══════════ */}
        <div className="flex items-center gap-3 flex-wrap" data-testid="market-control-bar">
          <span className={`px-3 py-1 rounded-full text-xs font-semibold ${bias.color}`}>{bias.label}</span>
          <span className={`flex items-center gap-1 text-sm font-medium ${dir.color}`}>
            <DirIcon className="w-4 h-4" /> BTC {dir.label}
          </span>
          <span className="text-xs text-gray-400">|</span>
          <span className="text-xs text-gray-500">Confidence <strong className="text-gray-700">{confidence}%</strong></span>
          <span className="text-xs text-gray-400">|</span>
          <span className="text-xs text-gray-500">{altCondition}</span>
          <span className="text-xs text-gray-400">|</span>
          {riskCount > 0 && (
            <span className="flex items-center gap-1 text-xs text-amber-600">
              <AlertTriangle className="w-3 h-3" /> {riskCount} risk{riskCount > 1 ? 's' : ''}
            </span>
          )}
          <span className="text-xs text-gray-400 ml-auto">Live</span>
          <button onClick={fetchAll} className="p-1 hover:bg-gray-200 rounded transition-colors">
            <RefreshCw className="w-3.5 h-3.5 text-gray-400" />
          </button>
        </div>

        {/* ══════════ 2. BTC OUTLOOK + RISK & POLICY ══════════ */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
          {/* BTC Outlook */}
          <div className="lg:col-span-3 bg-white rounded-2xl p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04)]" data-testid="btc-outlook">
            <h2 className="text-sm font-semibold text-gray-800 mb-4">BTC Outlook</h2>
            <div className="flex items-start gap-6">
              <div className="flex-shrink-0 text-center">
                <div className={`w-16 h-16 rounded-2xl flex items-center justify-center ${
                  dir.label === 'Up' ? 'bg-emerald-50' : dir.label === 'Down' ? 'bg-red-50' : 'bg-gray-50'
                }`}>
                  <DirIcon className={`w-8 h-8 ${dir.color}`} />
                </div>
                <p className={`text-lg font-bold mt-2 ${dir.color}`}>{dir.label}</p>
                <p className="text-xs text-gray-400">{strengthLabel(pressure)}</p>
              </div>
              <div className="flex-1 space-y-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500 w-24">Confidence</span>
                  <div className="flex-1 bg-gray-100 rounded-full h-1.5">
                    <div className="bg-blue-500 h-1.5 rounded-full transition-all" style={{width: `${confidence}%`}} />
                  </div>
                  <span className="text-xs font-medium text-gray-700 w-10 text-right">{confidence}%</span>
                </div>
                <p className="text-xs font-medium text-gray-500 mt-3">Drivers</p>
                <div className="flex flex-wrap gap-1.5">
                  {drivers.map((d, i) => (
                    <span key={i} className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full">{d}</span>
                  ))}
                </div>
                <button
                  onClick={() => navigateTab('signals')}
                  className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 mt-2 font-medium"
                >
                  Open Signals <ArrowRight className="w-3 h-3" />
                </button>
              </div>
            </div>
          </div>

          {/* Risk & Policy */}
          <div className="lg:col-span-2 bg-white rounded-2xl p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04)]" data-testid="risk-policy">
            <h2 className="text-sm font-semibold text-gray-800 mb-4">Risk & Policy</h2>
            <div className="space-y-3">
              <PolicyRow label="Leverage allowed" value={liqRisk === 'Low'} />
              <PolicyRow label="ALT exposure" value={altCondition !== 'BTC-only'} detail={altCondition === 'BTC-only' ? 'Reduce' : 'Normal'} />
              <PolicyRow label="Risk level" detail={liqRisk} isRisk={liqRisk !== 'Low'} />
              <PolicyRow label="Macro influence" detail={
                data?.regime === 'TRENDING' ? 'Trending' :
                data?.regime === 'SQUEEZE' ? 'Squeeze caution' :
                data?.regime === 'DISTRIBUTION' ? 'Distribution' : 'Low activity'
              } />
            </div>
            <button
              onClick={() => navigateTab('macro-regime')}
              className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 mt-4 font-medium"
            >
              Open Macro <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        </div>

        {/* ══════════ 2.5. TACTICAL CONDITIONS (1D) ══════════ */}
        <TacticalPanel data={tactical} />

        {/* ══════════ 3. TODAY'S MOVERS ══════════ */}
        <div className="bg-white rounded-2xl p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04)]" data-testid="todays-movers">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-800">Today's Markets</h2>
            <button
              onClick={() => navigateTab('markets')}
              className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
            >
              View all <ArrowRight className="w-3 h-3" />
            </button>
          </div>
          {markets.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-400 uppercase tracking-wider">
                    <th className="pb-3 font-medium">#</th>
                    <th className="pb-3 font-medium">Token</th>
                    <th className="pb-3 font-medium text-right">Universe</th>
                    <th className="pb-3 font-medium text-right">Liquidity</th>
                    <th className="pb-3 font-medium text-right">Derivatives</th>
                    <th className="pb-3 font-medium text-right">Whale</th>
                    <th className="pb-3 font-medium text-right">Volume 24h</th>
                  </tr>
                </thead>
                <tbody>
                  {markets.slice(0, 8).map((m, i) => {
                    const s = m.scores || {};
                    return (
                      <tr key={m.symbol} className="border-t border-gray-50 hover:bg-gray-50/50 transition-colors">
                        <td className="py-2.5 text-gray-400 text-xs">{i+1}</td>
                        <td className="py-2.5 font-semibold text-gray-900">{m.symbol}</td>
                        <td className="py-2.5 text-right">
                          <ScoreBar value={s.universeScore} />
                        </td>
                        <td className="py-2.5 text-right">
                          <ScoreBar value={s.liquidityScore} />
                        </td>
                        <td className="py-2.5 text-right">
                          <ScoreBar value={s.derivativeScore} />
                        </td>
                        <td className="py-2.5 text-right">
                          <ScoreBar value={s.whaleScore} color="purple" />
                        </td>
                        <td className="py-2.5 text-right text-gray-500">{fmtVol(m.raw?.volume24h)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState text="No market data available" />
          )}
        </div>

        {/* ══════════ 4. NEXT MOVERS (ALT RADAR) ══════════ */}
        <div className="bg-white rounded-2xl p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04)]" data-testid="next-movers">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-800">Next Movers — Alt Radar</h2>
            <button
              onClick={() => navigateTab('alt-radar')}
              className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
            >
              Open Alt Radar <ArrowRight className="w-3 h-3" />
            </button>
          </div>
          {radar?.opportunities?.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {radar.opportunities.slice(0, 6).map((opp, i) => (
                <div key={i} className="p-3 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-gray-900 text-sm">{opp.symbol || opp.token || `Opp #${i+1}`}</span>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                      (opp.score || 0) > 70 ? 'bg-emerald-100 text-emerald-700' :
                      (opp.score || 0) > 40 ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'
                    }`}>
                      {opp.score?.toFixed(0) || '—'}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500">{opp.setupType || opp.type || 'Pattern'} · {opp.timeHorizon || '24h'}</p>
                  {opp.reasons && <p className="text-xs text-gray-400 mt-1">{opp.reasons.slice(0,2).join(', ')}</p>}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState text="Waiting for patterns..." subtext="Alt Radar is scanning for opportunities" />
          )}
        </div>

        {/* ══════════ 5. SIGNAL SNAPSHOT ══════════ */}
        <div className="bg-white rounded-2xl p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04)]" data-testid="signal-snapshot">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-800">Signal Snapshot</h2>
            <button
              onClick={() => navigateTab('signals')}
              className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
            >
              Open Signals <ArrowRight className="w-3 h-3" />
            </button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <SignalCard 
              title="Exchange Pressure" 
              state={pressure > 0.1 ? 'Bullish' : pressure < -0.1 ? 'Bearish' : 'Neutral'}
              strength={Math.abs(pressure * 100)}
              meaning={pressure > 0.1 ? 'Buyers dominating' : pressure < -0.1 ? 'Sellers dominating' : 'Balanced flows'}
            />
            <SignalCard 
              title="Acc / Distribution"
              state={pressure > 0.05 ? 'Accumulation' : pressure < -0.05 ? 'Distribution' : 'Neutral'}
              strength={Math.abs(pressure * 80)}
              meaning={pressure > 0.05 ? 'Accumulation zones active' : 'No strong signal'}
            />
            <SignalCard 
              title="Liquidity"
              state={liqRisk === 'High' ? 'Thin' : 'Normal'}
              strength={data?.liquidationPressure || 0}
              meaning={liqRisk === 'High' ? 'Slippage risk elevated' : 'Adequate depth'}
            />
            <SignalCard 
              title="Derivatives"
              state={pressure > 0 ? 'Long bias' : pressure < 0 ? 'Short bias' : 'Balanced'}
              strength={Math.abs(pressure * 60)}
              meaning="Funding rate context"
            />
            <SignalCard 
              title="Whale Activity"
              state={markets.some(m => (m.scores?.whaleScore||0) > 0.6) ? 'Active' : 'Silent'}
              strength={Math.max(...markets.map(m => (m.scores?.whaleScore||0) * 100), 0)}
              meaning={markets.some(m => (m.scores?.whaleScore||0) > 0.6) ? 'Large wallet movement' : 'No significant whale activity'}
            />
            <SignalCard 
              title="Volatility"
              state={(data?.volatilityIndex||0) > 50 ? 'High' : (data?.volatilityIndex||0) > 25 ? 'Medium' : 'Low'}
              strength={data?.volatilityIndex || 0}
              meaning={(data?.volatilityIndex||0) > 50 ? 'Expect sharp moves' : 'Range compression'}
            />
          </div>
        </div>

        {/* ══════════ 6. RESEARCH SNAPSHOT ══════════ */}
        <div className="bg-white rounded-2xl p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04)]" data-testid="research-snapshot">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-800">Research</h2>
            <button
              onClick={() => navigateTab('research')}
              className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
            >
              Open Research <ArrowRight className="w-3 h-3" />
            </button>
          </div>
          {research?.hypotheses?.length > 0 ? (
            <div className="space-y-2">
              {research.hypotheses.slice(0, 3).map((h, i) => (
                <div key={i} className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
                  <span className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold ${
                    (h.confidence||0) > 70 ? 'bg-emerald-100 text-emerald-700' :
                    (h.confidence||0) > 40 ? 'bg-blue-100 text-blue-700' : 'bg-gray-200 text-gray-600'
                  }`}>{h.confidence || '?'}%</span>
                  <div className="flex-1">
                    <p className="text-sm text-gray-800">{h.title || h.hypothesis || `Hypothesis #${i+1}`}</p>
                    {h.narrative && <p className="text-xs text-gray-400 mt-0.5 line-clamp-1">{h.narrative}</p>}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">No active hypotheses. Market may be in low-activity mode.</p>
          )}
        </div>

        {/* ══════════ 7. QUICK ACCESS ══════════ */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3" data-testid="quick-access">
          <QuickTile icon={BarChart3} label="Markets" kpi={`${markets.length} active`} onClick={() => navigateTab('markets')} />
          <QuickTile icon={Zap} label="Signals" kpi={bias.label} onClick={() => navigateTab('signals')} />
          <QuickTile icon={Radar} label="Alt Radar" kpi={`${radar?.opportunities?.length || 0} setups`} onClick={() => navigateTab('alt-radar')} />
          <QuickTile icon={FlaskConical} label="Research" kpi={`${research?.hypotheses?.length || 0} hyp.`} onClick={() => navigateTab('research')} />
          <QuickTile icon={TestTubes} label="Labs" kpi={`${riskCount} risks`} onClick={() => navigateTab('labs')} />
          <QuickTile icon={Globe} label="Macro" kpi={data?.regime?.replace('_', ' ') || 'Unknown'} onClick={() => navigateTab('macro-regime')} />
        </div>

      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   SUB-COMPONENTS
═══════════════════════════════════════════════════════════ */

function PolicyRow({ label, value, detail, isRisk }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
      <span className="text-xs text-gray-500">{label}</span>
      <div className="flex items-center gap-1.5">
        {value !== undefined && (
          value 
            ? <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
            : <XCircle className="w-3.5 h-3.5 text-red-400" />
        )}
        {detail && (
          <span className={`text-xs font-medium ${
            isRisk ? 'text-amber-600' : 'text-gray-700'
          }`}>{detail}</span>
        )}
      </div>
    </div>
  );
}

function SignalCard({ title, state, strength, meaning }) {
  const stateColor = 
    state === 'Bullish' || state === 'Accumulation' || state === 'Active' ? 'text-emerald-600' :
    state === 'Bearish' || state === 'Distribution' || state === 'Thin' || state === 'High' ? 'text-red-600' :
    'text-gray-500';
  
  return (
    <div className="p-3 bg-gray-50 rounded-xl">
      <p className="text-xs text-gray-400 mb-1">{title}</p>
      <p className={`text-sm font-semibold ${stateColor}`}>{state}</p>
      <div className="mt-1.5 bg-gray-200 rounded-full h-1">
        <div className={`h-1 rounded-full transition-all ${
          state.includes('Bullish') || state.includes('Accum') || state === 'Active' ? 'bg-emerald-400' :
          state.includes('Bearish') || state.includes('Dist') || state === 'Thin' || state === 'High' ? 'bg-red-400' :
          'bg-gray-400'
        }`} style={{width: `${Math.min(100, strength)}%`}} />
      </div>
      <p className="text-xs text-gray-400 mt-1.5">{meaning}</p>
    </div>
  );
}

function ScoreBar({ value, color = 'blue' }) {
  const pct = Math.round((value || 0) * 100);
  const colorClass = color === 'purple' ? 'bg-purple-400' : 'bg-blue-400';
  return (
    <div className="flex items-center justify-end gap-2">
      <div className="w-14 bg-gray-100 rounded-full h-1">
        <div className={`h-1 rounded-full ${colorClass}`} style={{width: `${pct}%`}} />
      </div>
      <span className="text-xs text-gray-500 w-8 text-right">{pct}%</span>
    </div>
  );
}

function QuickTile({ icon: Icon, label, kpi, onClick }) {
  return (
    <button
      onClick={onClick}
      className="flex flex-col items-center gap-2 p-4 bg-white rounded-2xl shadow-[0_1px_3px_rgba(0,0,0,0.04)] hover:shadow-md transition-shadow cursor-pointer"
      data-testid={`quick-tile-${label.toLowerCase().replace(' ', '-')}`}
    >
      <Icon className="w-5 h-5 text-gray-400" />
      <span className="text-xs font-medium text-gray-700">{label}</span>
      <span className="text-xs text-gray-400">{kpi}</span>
    </button>
  );
}

function EmptyState({ text, subtext }) {
  return (
    <div className="text-center py-8">
      <Activity className="w-6 h-6 mx-auto mb-2 text-gray-300" />
      <p className="text-sm text-gray-400">{text}</p>
      {subtext && <p className="text-xs text-gray-300 mt-1">{subtext}</p>}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   TACTICAL PANEL — Block X.C — Decision Enhancer
   Shows tactical microstructure conditions AND what they change in execution
═══════════════════════════════════════════════════════════ */
const BIAS_CONFIG = {
  bearish: { color: 'text-red-600', bg: 'bg-red-50/80', border: 'border-red-200', label: 'BEARISH', icon: TrendingDown },
  bullish: { color: 'text-emerald-600', bg: 'bg-emerald-50/80', border: 'border-emerald-200', label: 'BULLISH', icon: TrendingUp },
  neutral: { color: 'text-slate-600', bg: 'bg-slate-50/80', border: 'border-slate-200', label: 'NEUTRAL', icon: Minus },
};

const ADVICE_CONFIG = {
  wait: { color: 'text-red-700 bg-red-100', label: 'WAIT', severity: 'critical' },
  reduced: { color: 'text-amber-700 bg-amber-100', label: 'REDUCE', severity: 'high' },
  avoid_aggressive: { color: 'text-orange-700 bg-orange-100', label: 'CAUTIOUS', severity: 'medium' },
  normal: { color: 'text-emerald-700 bg-emerald-100', label: 'NORMAL', severity: 'low' },
};

function TacticalPanel({ data }) {
  if (!data) return null;

  const bias = data.tacticalBias || 'neutral';
  const biasConf = BIAS_CONFIG[bias] || BIAS_CONFIG.neutral;
  const BiasIcon = biasConf.icon;
  const advice = data.executionAdvice || 'normal';
  const adviceConf = ADVICE_CONFIG[advice] || ADVICE_CONFIG.normal;
  const quality = data.tradeQuality || 'medium';
  const signals = data.signals || {};
  const impact = data.executionImpact || {};
  const strength = Math.round((data.signalStrength || 0) * 100);
  const sizePct = impact.sizePct || 100;

  // Collect active signal descriptions
  const activeSignals = [];
  if (signals.orderflow?.bearish) activeSignals.push({ label: 'Order Flow Imbalance', type: 'bearish' });
  if (signals.orderflow?.bullish) activeSignals.push({ label: 'Order Flow Bullish', type: 'bullish' });
  if (signals.liquidations?.forcedSelling) activeSignals.push({ label: 'Liquidation Pressure', type: 'bearish' });
  if (signals.liquidations?.forcedBuying) activeSignals.push({ label: 'Short Squeeze', type: 'bullish' });
  if (signals.funding?.crowdedLongs) activeSignals.push({ label: 'Funding Extreme (Longs)', type: 'bearish' });
  if (signals.funding?.crowdedShorts) activeSignals.push({ label: 'Funding Extreme (Shorts)', type: 'bullish' });
  if (signals.absorption?.sellerExhaustion) activeSignals.push({ label: 'Seller Exhaustion', type: 'bullish' });
  if (signals.absorption?.buyerExhaustion) activeSignals.push({ label: 'Buyer Exhaustion', type: 'bearish' });

  return (
    <div className={`rounded-2xl shadow-[0_1px_3px_rgba(0,0,0,0.06)] border ${biasConf.border} ${biasConf.bg}`} data-testid="tactical-panel">
      {/* Header */}
      <div className="flex items-center gap-2 px-5 pt-4 pb-3">
        <Crosshair className="w-4 h-4 text-slate-500" />
        <h2 className="text-sm font-semibold text-slate-800">Tactical Conditions</h2>
        <span className="text-[10px] tracking-wider text-slate-400 uppercase ml-auto">1D Decision Enhancer</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-0 md:gap-0">
        {/* ── Col 1: Bias + Confidence (3 cols) ── */}
        <div className="md:col-span-3 px-5 pb-4 md:border-r border-slate-200/60" data-testid="tactical-bias">
          <div className="flex items-center gap-3">
            <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${
              bias === 'bearish' ? 'bg-red-100' : bias === 'bullish' ? 'bg-emerald-100' : 'bg-slate-100'
            }`}>
              <BiasIcon className={`w-5 h-5 ${biasConf.color}`} />
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wider text-slate-400">Tactical Bias</p>
              <p className={`text-base font-bold tracking-tight ${biasConf.color}`}>{biasConf.label}</p>
            </div>
          </div>
          <div className="mt-3 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-slate-500">Confidence</span>
              <span className={`text-[11px] font-semibold ${strength > 50 ? 'text-slate-700' : 'text-slate-500'}`}>{strength}%</span>
            </div>
            <div className="w-full bg-slate-200/60 rounded-full h-1">
              <div className={`h-1 rounded-full transition-all ${
                bias === 'bearish' ? 'bg-red-400' : bias === 'bullish' ? 'bg-emerald-400' : 'bg-slate-400'
              }`} style={{ width: `${Math.max(strength, 3)}%` }} />
            </div>
            <div className="flex items-center gap-1.5 mt-2">
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${adviceConf.color}`}>
                {adviceConf.label}
              </span>
              <span className="text-[10px] text-slate-400 capitalize">{quality} quality</span>
            </div>
          </div>
        </div>

        {/* ── Col 2: Active Signals (3 cols) ── */}
        <div className="md:col-span-3 px-5 pb-4 md:border-r border-slate-200/60" data-testid="tactical-signals">
          <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-2">Signals</p>
          {activeSignals.length > 0 ? (
            <div className="space-y-1.5">
              {activeSignals.map((s, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                    s.type === 'bearish' ? 'bg-red-400' : 'bg-emerald-400'
                  }`} />
                  <span className="text-xs text-slate-700">{s.label}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-400">No strong signals</p>
          )}
        </div>

        {/* ── Col 3: Execution Impact (6 cols — largest, most important) ── */}
        <div className="md:col-span-6 px-5 pb-4" data-testid="tactical-impact">
          <div className="flex items-center justify-between mb-2">
            <p className="text-[10px] uppercase tracking-wider text-slate-400">Impact on Execution</p>
            {sizePct < 100 && (
              <span className="text-[10px] font-bold text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded">
                Size {sizePct}%
              </span>
            )}
          </div>
          <div className="space-y-1.5">
            {(impact.impacts || []).map((imp, i) => (
              <div key={i} className="flex items-start gap-1.5">
                <ArrowRight className={`w-3 h-3 mt-0.5 flex-shrink-0 ${
                  i === 0 ? 'text-slate-500' : 'text-slate-400'
                }`} />
                <span className={`text-xs ${i === 0 ? 'text-slate-700 font-medium' : 'text-slate-600'}`}>{imp}</span>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-slate-400 mt-3 pt-2 border-t border-slate-200/50">
            {impact.note || 'Enhances execution — does not override strategic forecast'}
          </p>
        </div>
      </div>
    </div>
  );
}
