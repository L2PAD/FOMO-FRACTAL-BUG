/**
 * BakerDetailPage v5 — Behavioral Model
 *
 * Design: dark hero → white 2-col → dark bottom
 * New blocks: BAKER DNA, HOW TO COPY, ALPHA TYPE, WHERE HE MAKES MONEY, TRUST MODE
 */
import { useState, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, RefreshCw } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const PLAY_C = { ENTER: '#16a34a', FOLLOW: '#22c55e', WATCH: '#ca8a04', AVOID: '#6b7280', EXIT: '#ef4444' };
const EDGE_C = { HIGH: '#16a34a', MID: '#6b7280', LOW: '#ef4444' };
const ENTRY_C = { EARLY: '#16a34a', MID: '#ca8a04', LATE: '#ef4444', EXIT: '#ef4444' };
const SIG_C = { STRONG: '#16a34a', MEDIUM: '#ca8a04', WEAK: '#6b7280' };
const ALPHA_C = { EARLY: '#16a34a', MOMENTUM: '#ca8a04', EXIT: '#ef4444', NOISE: '#6b7280' };
const TRUST_C = { YES: '#16a34a', WEAK: '#ca8a04', NO: '#ef4444' };
const TRUST_DESC = { YES: 'signals are working now', WEAK: 'not his market right now', NO: 'better to ignore now' };

const playColor = (p) => PLAY_C[(p || '').split(' ')[0]] || '#6b7280';

const safeFetch = async (url) => {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const t = await res.text();
    return JSON.parse(t);
  } catch { return null; }
};

export default function BakerDetailPage({ slugOverride }) {
  const params = useParams();
  const slug = slugOverride || params.slug;
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const goBack = () => navigate('/twitter?tab=credibility');

  const fetchData = useCallback(async () => {
    if (!slug) return;
    setLoading(true);
    setError(null);
    const result = await safeFetch(`${API}/api/backers/${slug}`);
    if (result?.ok) setData(result);
    else setError(result?.error || 'Baker not found');
    setLoading(false);
  }, [slug]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) return (
    <div className="min-h-screen" data-testid="baker-detail-page">
      <div className="max-w-[1600px] mx-auto px-6 py-6">
        <button onClick={goBack} className="text-sm text-gray-400 hover:text-gray-900 flex items-center gap-1 mb-4" data-testid="back-to-bakery">
          <ArrowLeft className="w-4 h-4" /> Back to Backers
        </button>
        <div className="h-8 w-48 bg-gray-100 rounded animate-pulse mb-4" />
        <div className="rounded-xl mb-6 animate-pulse" style={{ background: '#0a0a0a', padding: '24px' }}>
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-4 py-2 space-y-3">
              <div className="h-3 w-20 rounded bg-gray-700" />
              <div className="h-10 w-16 rounded bg-gray-800" />
              <div className="h-10 w-16 rounded bg-gray-800" />
            </div>
            <div className="col-span-4 py-2 space-y-3">
              <div className="h-3 w-20 rounded bg-gray-700" />
              <div className="h-4 w-full rounded bg-gray-800" />
              <div className="h-4 w-full rounded bg-gray-800" />
              <div className="h-4 w-full rounded bg-gray-800" />
            </div>
            <div className="col-span-4 py-2 space-y-3">
              <div className="h-3 w-28 rounded bg-gray-700" />
              <div className="h-10 w-20 rounded bg-gray-800" />
              <div className="h-4 w-full rounded bg-gray-800" />
            </div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-8">
          <div className="space-y-2">
            <div className="h-3 w-40 bg-gray-100 rounded animate-pulse" />
            <div className="h-4 w-full bg-gray-50 rounded animate-pulse" />
            <div className="h-4 w-3/4 bg-gray-50 rounded animate-pulse" />
          </div>
          <div className="space-y-2">
            <div className="h-3 w-40 bg-gray-100 rounded animate-pulse" />
            <div className="h-4 w-full bg-gray-50 rounded animate-pulse" />
            <div className="h-4 w-3/4 bg-gray-50 rounded animate-pulse" />
          </div>
        </div>
      </div>
    </div>
  );

  if (error || !data) return (
    <div className="min-h-screen px-6 py-6">
      <div className="max-w-[1600px] mx-auto">
        <button onClick={goBack} className="text-sm text-gray-400 hover:text-gray-900 flex items-center gap-4 mb-6" data-testid="back-to-bakery">
          <ArrowLeft className="w-4 h-4" /> Back to Backers
        </button>
        <p className="text-red-500">{error || 'Not found'}</p>
      </div>
    </div>
  );

  const b = data.baker;
  const dna = b.dna || {};
  const profile = data.signalProfile || {};
  const howToTrade = data.howToTrade || [];
  const copyStrategy = data.copyStrategy || [];
  const frontRun = data.frontRun || [];
  const whyWorks = data.whyWorks || [];
  const whyFails = data.whyFails || [];
  const money = data.moneyTrack || {};
  const connections = data.connections || [];
  const sectorPerf = b.sectorPerformance || {};
  const sectorEntries = Object.entries(sectorPerf).sort((a, b) => b[1] - a[1]);

  return (
    <div className="min-h-screen" data-testid="baker-detail-page">
      <div className="max-w-[1600px] mx-auto px-6 py-6">

        {/* Back + Title */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <button onClick={goBack} className="text-sm text-gray-400 hover:text-gray-900 flex items-center gap-1 mb-2" data-testid="back-to-bakery">
              <ArrowLeft className="w-4 h-4" /> Back to Backers
            </button>
            <div className="flex items-center gap-4">
              <h1 className="text-2xl font-semibold tracking-tight text-gray-900" data-testid="baker-header">{b.name}</h1>
              <span className="text-xs font-bold px-2 py-0.5 rounded" style={{ background: ALPHA_C[b.alphaType] + '20', color: ALPHA_C[b.alphaType] }} data-testid="alpha-type">
                {b.alphaType} ALPHA
              </span>
              <span className="text-xs font-bold px-2 py-0.5 rounded" style={{ background: TRUST_C[b.trustMode] + '20', color: TRUST_C[b.trustMode] }} data-testid="trust-mode">
                TRUST: {b.trustMode}
              </span>
            </div>
            <div className="flex gap-3 mt-1 text-sm text-gray-400">
              <span>{b.role}</span>
              <span className="text-gray-200">|</span>
              <span>{b.sector}</span>
              {b.rank > 0 && <><span className="text-gray-200">|</span><span>#{b.rank}</span></>}
            </div>
          </div>
          <button onClick={fetchData} disabled={loading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-900 text-sm text-white hover:bg-gray-800 disabled:opacity-50 transition-colors">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* ── DARK HERO: Score + TRUST + DNA ────────────────── */}
        <div className="rounded-xl mb-6" style={{ background: '#0a0a0a', padding: '24px' }} data-testid="baker-score">
          <div className="grid grid-cols-12 gap-6">

            {/* Score — left */}
            <div className="col-span-4 py-2">
              <span className="text-[10px] font-medium uppercase tracking-widest block mb-3" style={{ color: '#9ca3af' }}>Score</span>
              <div className="grid grid-cols-2 gap-x-6 gap-y-3">
                <div>
                  <div className="text-[10px] uppercase" style={{ color: '#9ca3af' }}>Power</div>
                  <div className="text-3xl font-semibold" style={{ color: '#f9fafb' }}>{b.power}</div>
                </div>
                <div>
                  <div className="text-[10px] uppercase" style={{ color: '#9ca3af' }}>Edge</div>
                  <div className="text-3xl font-semibold" style={{ color: EDGE_C[b.edgeLabel] }}>{b.edgeLabel}</div>
                </div>
                <div>
                  <div className="text-[10px] uppercase" style={{ color: '#9ca3af' }}>Entry</div>
                  <div className="text-3xl font-semibold" style={{ color: ENTRY_C[b.entry] }}>{b.entry}</div>
                </div>
                <div>
                  <div className="text-[10px] uppercase" style={{ color: '#9ca3af' }}>Play</div>
                  <div className="text-xl font-bold mt-1" style={{ color: playColor(b.play) }}>{b.play}</div>
                </div>
              </div>
            </div>

            {/* BAKER DNA — center */}
            <div className="col-span-4 py-2" data-testid="baker-dna">
              <span className="text-[10px] font-medium uppercase tracking-widest block mb-3" style={{ color: '#9ca3af' }}>Baker DNA</span>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span style={{ color: '#9ca3af' }}>Style</span>
                  <span style={{ color: '#f9fafb', fontWeight: 600 }}>{dna.style || '—'}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span style={{ color: '#9ca3af' }}>Market Role</span>
                  <span style={{ color: '#f9fafb', fontWeight: 600 }}>{dna.marketRole || '—'}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span style={{ color: '#9ca3af' }}>Primary Edge</span>
                  <span style={{ color: '#16a34a', fontWeight: 600 }}>{dna.edge || '—'}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span style={{ color: '#9ca3af' }}>Weak Side</span>
                  <span style={{ color: '#ef4444', fontWeight: 600 }}>{dna.weakness || '—'}</span>
                </div>
              </div>
            </div>

            {/* Performance + Trust — right */}
            <div className="col-span-4 py-2">
              <span className="text-[10px] font-medium uppercase tracking-widest block mb-3" style={{ color: '#9ca3af' }}>Can You Trust Him Now?</span>
              <div className="flex items-center gap-3 mb-4">
                <span className="text-3xl font-bold" style={{ color: TRUST_C[b.trustMode] }}>{b.trustMode}</span>
                <span className="text-xs" style={{ color: '#9ca3af' }}>{TRUST_DESC[b.trustMode]}</span>
              </div>
              <div className="space-y-1.5">
                <div className="flex justify-between text-sm">
                  <span style={{ color: '#9ca3af' }}>Hit rate</span>
                  <span style={{ color: '#f9fafb', fontWeight: 600 }}>{b.hitRate}%</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span style={{ color: '#9ca3af' }}>Avg return</span>
                  <span style={{ color: b.avgReturn >= 0 ? '#16a34a' : '#ef4444', fontWeight: 600 }}>{b.avgReturn >= 0 ? '+' : ''}{b.avgReturn}%</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span style={{ color: '#9ca3af' }}>Calls tracked</span>
                  <span style={{ color: '#f9fafb', fontWeight: 600 }}>{b.callsTracked}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span style={{ color: '#9ca3af' }}>Signal</span>
                  <span style={{ color: SIG_C[b.signal], fontWeight: 600 }}>{b.signal}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── WHITE SECTION: HOW TO COPY + WHERE HE MAKES MONEY ── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-6">
          {/* HOW TO COPY — left */}
          <div data-testid="copy-strategy">
            <div className="text-[10px] font-medium uppercase tracking-widest text-green-600 mb-3">How To Copy This Baker</div>
            <div className="space-y-2">
              {copyStrategy.map((step, i) => (
                <div key={i} className="flex gap-3 items-start">
                  <span className="text-green-600 font-mono text-xs mt-0.5">-{'>'}</span>
                  <span className="text-sm text-gray-700">{step}</span>
                </div>
              ))}
              {copyStrategy.length === 0 && <span className="text-sm text-gray-300">No strategy available</span>}
            </div>
          </div>

          {/* WHERE HE MAKES MONEY — right */}
          <div data-testid="sector-performance">
            <div className="text-[10px] font-medium uppercase tracking-widest text-amber-600 mb-3">Where He Makes Money</div>
            {sectorEntries.length > 0 ? (
              <div className="space-y-2">
                {sectorEntries.map(([sec, avg]) => (
                  <div key={sec} className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-700">{sec}</span>
                    <div className="flex items-center gap-3">
                      <div className="w-32 h-2 rounded-full bg-gray-100 overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{
                            width: `${Math.min(100, Math.max(5, Math.abs(avg) * 3))}%`,
                            background: avg >= 0 ? '#16a34a' : '#ef4444',
                          }}
                        />
                      </div>
                      <span className="text-sm font-semibold min-w-[50px] text-right" style={{ color: avg >= 0 ? '#16a34a' : '#ef4444' }}>
                        {avg >= 0 ? '+' : ''}{avg}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <span className="text-sm text-gray-300">No sector data</span>
            )}

            {/* Alpha type inline */}
            <div className="mt-4 pt-3 border-t border-gray-100">
              <div className="flex items-center gap-3">
                <span className="text-[10px] uppercase tracking-widest text-gray-400">Alpha Type</span>
                <span className="text-sm font-bold" style={{ color: ALPHA_C[b.alphaType] }}>
                  {b.alphaType === 'EARLY' ? 'EARLY ALPHA — before the move' :
                   b.alphaType === 'MOMENTUM' ? 'MOMENTUM — during the move' :
                   b.alphaType === 'EXIT' ? 'EXIT SIGNAL — time to leave' :
                   'NOISE — unreliable signal'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* ── WHITE: HOW TO TRADE + FRONT-RUN ─────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-6">
          <div>
            <div className="text-[10px] font-medium uppercase tracking-widest text-gray-900 mb-3">How To Trade</div>
            {howToTrade.map((s, i) => (
              <div key={i} className="flex gap-2 mb-2">
                <span className="text-xs text-gray-300 font-mono mt-0.5">{i + 1}.</span>
                <span className="text-sm text-gray-700">{s}</span>
              </div>
            ))}
          </div>
          <div>
            <div className="text-[10px] font-medium uppercase tracking-widest text-gray-900 mb-3">How To Front-Run</div>
            {frontRun.map((s, i) => (
              <div key={i} className="flex gap-2 mb-2">
                <span className="text-xs text-gray-300 font-mono mt-0.5">{i + 1}.</span>
                <span className="text-sm text-gray-700">{s}</span>
              </div>
            ))}
          </div>
        </div>

        {/* WHY WORKS / FAILS (white bg) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-6" data-testid="why-works-fails">
          <div>
            <div className="text-[10px] font-medium uppercase tracking-widest text-green-600 mb-2">Why This Works</div>
            {whyWorks.map((w, i) => (
              <div key={i} className="text-sm text-gray-600 mb-1">{w}</div>
            ))}
            {whyWorks.length === 0 && <div className="text-sm text-gray-300">—</div>}
          </div>
          <div>
            <div className="text-[10px] font-medium uppercase tracking-widest text-red-500 mb-2">Why This Fails</div>
            {whyFails.map((w, i) => (
              <div key={i} className="text-sm text-gray-500 mb-1">{w}</div>
            ))}
            {whyFails.length === 0 && <div className="text-sm text-gray-300">—</div>}
          </div>
        </div>

        {/* ── DARK BLOCK: MONEY TRACK + CONNECTIONS ────────── */}
        <div className="rounded-xl" style={{ background: '#0a0a0a', padding: '20px 24px' }} data-testid="money-track">
          <div className="grid grid-cols-12 gap-6">

            {/* Money Track */}
            <div className="col-span-8 py-2">
              <span className="text-sm font-medium" style={{ color: '#ca8a04' }}>MONEY TRACK</span>
              <div className="grid grid-cols-2 gap-8 mt-3">
                <div>
                  <div className="text-[10px] uppercase tracking-wider mb-2" style={{ color: '#16a34a' }}>Best Plays</div>
                  {(money.best || []).map((p, i) => (
                    <div key={i} className="flex justify-between text-sm mb-1">
                      <span style={{ color: '#d1d5db' }}>{p.token}</span>
                      <span style={{ color: '#16a34a', fontWeight: 600 }}>+{p.return}%</span>
                    </div>
                  ))}
                  {(!money.best || money.best.length === 0) && <div style={{ color: '#374151', fontSize: 13 }}>—</div>}
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wider mb-2" style={{ color: '#ef4444' }}>Worst</div>
                  {(money.worst || []).map((p, i) => (
                    <div key={i} className="flex justify-between text-sm mb-1">
                      <span style={{ color: '#9ca3af' }}>{p.token}</span>
                      <span style={{ color: '#ef4444', fontWeight: 600 }}>{p.return}%</span>
                    </div>
                  ))}
                  {(!money.worst || money.worst.length === 0) && <div style={{ color: '#374151', fontSize: 13 }}>—</div>}
                </div>
              </div>
            </div>

            {/* Connections */}
            <div className="col-span-4 py-2">
              <span className="text-[10px] font-medium uppercase tracking-widest block mb-3" style={{ color: '#9ca3af' }}>Top Connections</span>
              {connections.map((c, i) => (
                <Link key={i} to={`/twitter?tab=credibility&baker=${c.slug}`}
                  className="flex justify-between py-1.5 hover:opacity-80 transition-opacity" style={{ textDecoration: 'none', borderBottom: '1px solid #1f2937' }}>
                  <span className="text-sm font-medium" style={{ color: '#d1d5db' }}>{c.name}</span>
                  <span className="text-xs" style={{ color: '#9ca3af' }}>{c.role}</span>
                </Link>
              ))}
              {connections.length === 0 && <div style={{ color: '#374151', fontSize: 13 }}>—</div>}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
