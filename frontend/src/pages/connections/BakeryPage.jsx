/**
 * BakeryPage v5 — WHO MOVES MONEY NOW + MARKET CONTROL
 *
 * Design: dark hero → white decisions → light table
 * New: MARKET CONTROL block, BAKER DNA preview in cards, TRUST badges
 */
import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { RefreshCw, Zap, TrendingUp, AlertTriangle } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const safeFetch = async (url) => {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const t = await res.text();
    return JSON.parse(t);
  } catch { return null; }
};

const PLAY_C = { ENTER: '#16a34a', FOLLOW: '#22c55e', WATCH: '#ca8a04', AVOID: '#6b7280', EXIT: '#ef4444' };
const ENTRY_C = { EARLY: 'text-green-600', MID: 'text-amber-600', LATE: 'text-red-500', EXIT: 'text-red-500' };
const SYNC_C = { HIGH: '#16a34a', MEDIUM: '#ca8a04', LOW: '#4b5563' };
const ALPHA_C = { EARLY: '#16a34a', MOMENTUM: '#ca8a04', EXIT: '#ef4444', NOISE: '#6b7280' };
const TRUST_C = { YES: '#16a34a', WEAK: '#ca8a04', NO: '#ef4444' };
const CONTROL_C = { controlled: '#16a34a', building: '#ca8a04', fragmented: '#6b7280', 'no leader': '#374151' };

const playVerb = (p) => (p || '').split(' ')[0];
const playColor = (p) => PLAY_C[playVerb(p)] || '#6b7280';

const FILTERS = [
  { value: '', label: 'ALL' },
  { value: 'FUND', label: 'FUNDS' },
  { value: 'PERSON', label: 'PEOPLE' },
  { value: 'MEDIA', label: 'MEDIA' },
];

/* ── Decision Card (on white bg) ─────────────────────── */
function DecisionCard({ d, rank }) {
  const dna = d.dna || {};
  return (
    <div className="py-3 border-b border-gray-50" data-testid={`decision-${d.slug}`}>
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-300 font-mono">#{rank}</span>
          <Link to={`/twitter?tab=credibility&baker=${d.slug}`} className="text-base font-semibold text-gray-900 hover:text-green-700 transition-colors">
            {d.name}
          </Link>
          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded" style={{ background: ALPHA_C[d.alphaType] + '15', color: ALPHA_C[d.alphaType] }}>
            {d.alphaType}
          </span>
          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded" style={{ background: TRUST_C[d.trustMode] + '15', color: TRUST_C[d.trustMode] }}>
            {d.trustMode}
          </span>
        </div>
        <span className="text-xs font-semibold" style={{ color: playColor(d.play) }}>{d.play}</span>
      </div>
      {/* DNA summary line */}
      <div className="text-[11px] text-gray-400 mb-1.5">
        {dna.style && <span>{dna.style}</span>}
        {dna.edge && <span className="text-gray-300 mx-1.5">|</span>}
        {dna.edge && <span>edge: <span className="text-gray-600">{dna.edge}</span></span>}
        {dna.weakness && <span className="text-gray-300 mx-1.5">|</span>}
        {dna.weakness && <span>weak: <span className="text-red-400">{dna.weakness}</span></span>}
      </div>
      {d.reasons && d.reasons.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {d.reasons.map((r, i) => (
            <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">{r}</span>
          ))}
        </div>
      )}
      <div className="flex items-center gap-4 text-xs text-gray-400">
        <span>Role <span className="text-gray-900 font-medium">{d.role}</span></span>
        <span>Edge <span className="text-gray-900 font-medium">{d.edgeLabel}</span></span>
        <span>Entry <span className={ENTRY_C[d.entry]}>{d.entry}</span></span>
        {d.lastMove && (
          <span>{d.lastMove.token} <span className={d.lastMove.return >= 0 ? 'text-green-600 font-medium' : 'text-red-500 font-medium'}>
            {d.lastMove.return >= 0 ? '+' : ''}{d.lastMove.return}%
          </span></span>
        )}
      </div>
    </div>
  );
}

/* ── Baker Table Row (light bg) ──────────────────────── */
function BakerRow({ b, i }) {
  const entryC = { EARLY: '#16a34a', MID: '#ca8a04', LATE: '#ef4444', EXIT: '#ef4444' };
  const edgeC = { HIGH: '#16a34a', MID: '#6b7280', LOW: '#ef4444' };
  return (
    <div className="flex items-center gap-3 px-3 py-2.5 border-b border-gray-50 transition-colors hover:bg-gray-50"
      data-testid={`baker-row-${i}`}>
      <span className="w-8 text-xs font-mono text-gray-300">{i + 1}</span>
      <Link to={`/twitter?tab=credibility&baker=${b.slug}`} className="flex-1 text-sm font-medium text-gray-900 hover:text-green-700 transition-colors no-underline"
        data-testid={`baker-name-${b.slug}`}>
        {b.name}
      </Link>
      <span className="w-20 text-[10px] font-bold text-center rounded px-1 py-0.5" style={{ background: ALPHA_C[b.alphaType] + '12', color: ALPHA_C[b.alphaType] }}>{b.alphaType}</span>
      <span className="w-12 text-[10px] font-bold text-center rounded px-1 py-0.5" style={{ background: TRUST_C[b.trustMode] + '12', color: TRUST_C[b.trustMode] }}>{b.trustMode}</span>
      <span className="w-16 text-xs text-right text-gray-500">{b.role}</span>
      <span className="w-12 text-xs text-right font-semibold" style={{ color: edgeC[b.edgeLabel] }}>{b.edgeLabel}</span>
      <span className="w-12 text-xs text-right font-semibold" style={{ color: entryC[b.entry] }}>{b.entry}</span>
      <span className="w-28 text-right text-xs">
        {b.lastMove ? (
          <>
            <span className="text-gray-500">{b.lastMove.token}</span>
            <span className="ml-1 font-semibold" style={{ color: b.lastMove.return >= 0 ? '#16a34a' : '#ef4444' }}>
              {b.lastMove.return >= 0 ? '+' : ''}{b.lastMove.return}%
            </span>
          </>
        ) : <span className="text-gray-300">—</span>}
      </span>
      <span className="w-28 text-right text-xs font-bold" style={{ color: playColor(b.play) }}>{b.play}</span>
    </div>
  );
}

/* ── MAIN ────────────────────────────────────────────── */
export default function BakeryPage() {
  const [bakers, setBakers] = useState([]);
  const [whyNow, setWhyNow] = useState([]);
  const [flows, setFlows] = useState([]);
  const [sync, setSync] = useState({});
  const [marketControl, setMarketControl] = useState({});
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    const p = new URLSearchParams();
    if (typeFilter) p.set('type', typeFilter);
    p.set('limit', '50');
    const [lb, flowData] = await Promise.all([
      safeFetch(`${API}/api/backers?${p}`),
      safeFetch(`${API}/api/backers/active`),
    ]);
    if (lb?.ok) {
      setBakers(lb.bakers || []);
      setWhyNow(lb.whyNow || []);
      setSync(lb.sync || {});
      setMarketControl(lb.marketControl || {});
      setStats(lb.stats || null);
    }
    if (flowData?.ok) setFlows(flowData.flows || []);
    setLoading(false);
  }, [typeFilter]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const enterBakers = bakers.filter(b => playVerb(b.play) === 'ENTER' || playVerb(b.play) === 'FOLLOW');
  const watchBakers = bakers.filter(b => playVerb(b.play) === 'WATCH');
  const avoidBakers = bakers.filter(b => playVerb(b.play) === 'AVOID' || playVerb(b.play) === 'EXIT');

  const syncEntries = Object.entries(sync || {}).filter(([, v]) => v.count >= 2).sort((a, b) => b[1].count - a[1].count);
  const mcEntries = Object.entries(marketControl || {}).filter(([, v]) => v.bakerCount > 0);

  return (
    <div className="min-h-screen" data-testid="bakery-page">
      <div className="max-w-[1600px] mx-auto px-6 py-6">

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-gray-900">Backers</h1>
            <p className="text-sm text-gray-400 mt-0.5">Who moves money — and how to use them for profit</p>
          </div>
          <button onClick={() => fetchData()} disabled={loading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-900 text-sm text-white hover:bg-gray-800 disabled:opacity-50 transition-colors"
            data-testid="refresh-btn">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {loading && !bakers.length ? (
          <div className="flex items-center justify-center py-20">
            <RefreshCw className="w-5 h-5 animate-spin text-gray-300" />
          </div>
        ) : (
          <>
            {/* ── DARK HERO: WHY NOW + FLOW + MARKET CONTROL ───── */}
            <div className="rounded-xl mb-6" style={{ background: '#0a0a0a', padding: '24px' }} data-testid="hero-block">
              <div className="grid grid-cols-12 gap-6">

                {/* WHY NOW — left */}
                <div className="col-span-4 py-2">
                  <span className="text-[10px] font-medium uppercase tracking-widest block mb-3" style={{ color: '#9ca3af' }}>Who Moves Money Now</span>
                  {(whyNow || []).filter(w => w.play && !w.play.startsWith('AVOID')).slice(0, 4).map((w, i) => (
                    <div key={i} className="mb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold" style={{ color: playColor(w.play) }}>{w.play}</span>
                        {w.sync && w.sync !== 'LOW' && (
                          <span className="text-[10px] font-semibold" style={{ color: SYNC_C[w.sync] }}>SYNC {w.syncCount}</span>
                        )}
                      </div>
                      <Link to={`/twitter?tab=credibility&baker=${w.topBaker?.slug}`} className="text-sm font-medium block mt-0.5" style={{ color: '#f9fafb', textDecoration: 'none' }}>
                        {w.topBaker?.name} <span style={{ color: '#9ca3af', fontSize: 11 }}>{w.topBaker?.role}</span>
                      </Link>
                      {w.reasons?.length > 0 && (
                        <span className="text-[10px] block mt-0.5" style={{ color: '#9ca3af' }}>{w.reasons.join(' · ')}</span>
                      )}
                    </div>
                  ))}
                </div>

                {/* MONEY FLOW — mid */}
                <div className="col-span-4 py-2">
                  <span className="text-[10px] font-medium uppercase tracking-widest block mb-3" style={{ color: '#9ca3af' }}>Active Money Flow</span>
                  {(flows || []).slice(0, 5).map((f, i) => (
                    <div key={i} className="mb-2">
                      <Link to={`/twitter?tab=credibility&baker=${f.slug}`} className="text-sm font-medium" style={{ color: '#f9fafb', textDecoration: 'none' }}>
                        {f.name}
                      </Link>
                      <span className="text-[10px] ml-2" style={{ color: '#9ca3af' }}>{f.role}</span>
                      <div className="text-xs mt-0.5" style={{ color: '#ca8a04' }}>{f.context}</div>
                    </div>
                  ))}
                </div>

                {/* MARKET CONTROL — right */}
                <div className="col-span-4 py-2" data-testid="market-control">
                  <span className="text-[10px] font-medium uppercase tracking-widest block mb-3" style={{ color: '#9ca3af' }}>Market Control</span>
                  {mcEntries.length > 0 ? mcEntries.map(([sec, mc]) => (
                    <div key={sec} className="mb-2.5">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold" style={{ color: '#f9fafb' }}>{sec}</span>
                        <span className="text-[10px] font-bold" style={{ color: CONTROL_C[mc.status] }}>{mc.status}</span>
                      </div>
                      <div className="text-xs mt-0.5" style={{ color: '#9ca3af' }}>
                        {mc.leader ? (
                          <>
                            <Link to={`/twitter?tab=credibility&baker=${mc.leader.slug}`} style={{ color: '#d1d5db', textDecoration: 'none' }}>
                              {mc.leader.name}
                            </Link>
                            {mc.topBakers?.length > 1 && (
                              <span> + {mc.topBakers.slice(1).map(b => b.name).join(', ')}</span>
                            )}
                          </>
                        ) : 'no leader'}
                      </div>
                    </div>
                  )) : (
                    <div style={{ color: '#374151', fontSize: 13 }}>No sector data</div>
                  )}

                  {/* SYNC below market control */}
                  {syncEntries.length > 0 && (
                    <div className="mt-3 pt-3" style={{ borderTop: '1px solid #1f2937' }}>
                      <div className="text-[10px] uppercase tracking-wider mb-1.5" style={{ color: '#9ca3af' }}>Sync</div>
                      {syncEntries.map(([sec, v]) => (
                        <div key={sec} className="text-xs mb-0.5">
                          <span className="font-semibold" style={{ color: SYNC_C[v.label] }}>{v.count}</span>
                          <span style={{ color: '#d1d5db' }}> bakers on </span>
                          <span style={{ color: '#f9fafb' }}>{sec}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Overview stats row inside hero */}
              {stats && (
                <div className="flex gap-8 mt-4 pt-4" style={{ borderTop: '1px solid #1f2937' }}>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase" style={{ color: '#9ca3af' }}>Enter/Follow</span>
                    <span className="text-lg font-semibold text-green-500">{stats.enter}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase" style={{ color: '#9ca3af' }}>Watch</span>
                    <span className="text-lg font-semibold text-amber-500">{stats.watch}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase" style={{ color: '#9ca3af' }}>Avoid</span>
                    <span className="text-lg font-semibold" style={{ color: '#6b7280' }}>{stats.avoid}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase" style={{ color: '#9ca3af' }}>Total</span>
                    <span className="text-lg font-semibold" style={{ color: '#9ca3af' }}>{stats.total}</span>
                  </div>
                </div>
              )}
            </div>

            {/* ── WHITE SECTION: DECISIONS AS CARDS ──────────── */}
            <div className="mb-8">
              {enterBakers.length > 0 && (
                <div className="mb-6">
                  <div className="flex items-center gap-2 mb-2">
                    <Zap className="w-4 h-4 text-green-600" />
                    <span className="text-sm font-medium text-green-600">ENTER / FOLLOW</span>
                    <span className="text-[10px] text-gray-400">Strong signal, act now</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8">
                    {enterBakers.map((b, i) => <DecisionCard key={b.slug} d={b} rank={i + 1} />)}
                  </div>
                </div>
              )}
              {watchBakers.length > 0 && (
                <div className="mb-6">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp className="w-4 h-4 text-amber-600" />
                    <span className="text-sm font-medium text-amber-600">WATCH</span>
                    <span className="text-[10px] text-gray-400">Building signal, not yet confirmed</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8">
                    {watchBakers.map((b, i) => <DecisionCard key={b.slug} d={b} rank={enterBakers.length + i + 1} />)}
                  </div>
                </div>
              )}
              {avoidBakers.length > 0 && (
                <div className="mb-6">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangle className="w-4 h-4 text-gray-400" />
                    <span className="text-sm font-medium text-gray-400">AVOID / EXIT</span>
                    <span className="text-[10px] text-gray-300">No edge or late signal</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8">
                    {avoidBakers.map((b, i) => <DecisionCard key={b.slug} d={b} rank={enterBakers.length + watchBakers.length + i + 1} />)}
                  </div>
                </div>
              )}
            </div>

            {/* ── LIGHT TABLE: ALL BACKERS ────────────────────── */}
            <div className="mb-6" data-testid="baker-table">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-900">ALL BACKERS</span>
                <div className="flex gap-1">
                  {FILTERS.map(f => (
                    <button key={f.value} onClick={() => setTypeFilter(f.value)}
                      className="px-3 py-1 text-[11px] font-semibold rounded transition-colors"
                      style={{ background: typeFilter === f.value ? '#111827' : '#f3f4f6', color: typeFilter === f.value ? '#f9fafb' : '#6b7280' }}
                      data-testid={`filter-${f.value || 'all'}`}>
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Table header */}
              <div className="flex items-center gap-3 px-3 py-2 text-[10px] uppercase tracking-wider text-gray-400 border-b border-gray-200">
                <span className="w-8">#</span>
                <span className="flex-1">Name</span>
                <span className="w-20 text-center">Alpha</span>
                <span className="w-12 text-center">Trust</span>
                <span className="w-16 text-right">Role</span>
                <span className="w-12 text-right">Edge</span>
                <span className="w-12 text-right">Entry</span>
                <span className="w-28 text-right">Last Move</span>
                <span className="w-28 text-right">Play</span>
              </div>
              {bakers.map((b, i) => <BakerRow key={b.slug} b={b} i={i} />)}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
