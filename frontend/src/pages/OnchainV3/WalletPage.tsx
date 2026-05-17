import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft, Copy, ExternalLink, ArrowRight, ArrowUpRight, ArrowDownRight,
  Zap, Target, BarChart3, TrendingUp, Repeat2, PieChart, Radio, Activity,
  Shield, Link2, Users, Droplets, Lock, Play, Crosshair, Globe
} from 'lucide-react';
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '../../components/ui/tooltip';

const API = process.env.REACT_APP_BACKEND_URL || '';

/* ── Typography ───────────────────────────────────────────── */
const LBL = "text-[11px] font-semibold uppercase tracking-wider";

/* ── Cards ────────────────────────────────────────────────── */
const Dk = ({ children, className = '', id }: { children: React.ReactNode; className?: string; id?: string }) => (
  <div className={`rounded-2xl bg-gray-900 intelligence-dark p-5 h-full ${className}`} data-testid={id}>{children}</div>
);
const Wh = ({ children, className = '', id }: { children: React.ReactNode; className?: string; id?: string }) => (
  <div className={`rounded-2xl bg-white shadow-sm p-5 h-full ${className}`} data-testid={id}>{children}</div>
);

/* ── Section header with tooltip ─────────────────────────── */
const SH = ({ icon, title, tip, dark = true }: { icon: React.ReactNode; title: string; tip: string; dark?: boolean }) => (
  <div className="flex items-center gap-2 mb-4">
    {icon}
    <Tooltip delayDuration={200}>
      <TooltipTrigger asChild>
        <h4 className={`text-xs font-semibold uppercase tracking-wider cursor-default transition-colors ${dark ? 'text-gray-400 hover:text-gray-200' : 'text-gray-500 hover:text-gray-700'}`}>{title}</h4>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="max-w-[280px] text-xs leading-relaxed">{tip}</TooltipContent>
    </Tooltip>
  </div>
);

/* ── Metric rows ─────────────────────────────────────────── */
const DR = ({ label, value, vc = 'text-gray-100' }: { label: string; value: any; vc?: string }) => (
  <div className="flex items-center justify-between py-[3px]">
    <span className={`${LBL} text-gray-500`}>{label}</span>
    <span className={`text-xs font-semibold ${vc}`}>{value}</span>
  </div>
);
const WR = ({ label, value, vc = 'text-gray-900' }: { label: string; value: any; vc?: string }) => (
  <div className="flex items-center justify-between py-[3px]">
    <span className={`${LBL} text-gray-400`}>{label}</span>
    <span className={`text-xs font-semibold ${vc}`}>{value}</span>
  </div>
);

/* ── Progress bar ────────────────────────────────────────── */
const Bar = ({ value, color = 'bg-emerald-500', dark = true }: { value: number; color?: string; dark?: boolean }) => (
  <div className={`h-1.5 ${dark ? 'bg-gray-800' : 'bg-gray-200'} rounded-full overflow-hidden`}>
    <div className={`h-full rounded-full ${color} transition-all duration-500`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
  </div>
);

/* ── Color maps ──────────────────────────────────────────── */
const LC: Record<string, string> = { high: 'text-emerald-500', medium: 'text-amber-500', low: 'text-rose-500', High: 'text-emerald-400', Medium: 'text-amber-400', Low: 'text-rose-400' };
const STC: Record<string, string> = {
  early_accumulator: 'text-emerald-400', momentum_trader: 'text-blue-400',
  rotation_trader: 'text-violet-400', distribution_wallet: 'text-rose-400',
  active_trader: 'text-amber-400', liquidity_provider: 'text-cyan-400',
};
const SIGC: Record<string, string> = { accumulation: 'text-emerald-500', distribution: 'text-rose-500', rotation: 'text-blue-500', momentum: 'text-violet-500', weakening: 'text-amber-500', cluster_activity: 'text-cyan-500' };
const SIGD: Record<string, string> = { accumulation: 'bg-emerald-500', distribution: 'bg-rose-500', rotation: 'bg-blue-500', momentum: 'bg-violet-500', weakening: 'bg-amber-500', cluster_activity: 'bg-cyan-500' };

export default function WalletPage({ walletAddress, onBack }: { walletAddress?: string; onBack?: () => void }) {
  const { address: routeAddr } = useParams<{ address: string }>();
  const nav = useNavigate();
  const [searchParams] = useSearchParams();
  const navFrom = searchParams.get('from') || searchParams.get('src');
  const navToken = searchParams.get('token');
  const address = walletAddress || routeAddr;
  const [d, setD] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const goBack = () => { if (onBack) onBack(); else nav(-1); };
  const copyAddr = () => { navigator.clipboard.writeText(address || ''); setCopied(true); setTimeout(() => setCopied(false), 1500); };

  useEffect(() => {
    if (!address) return;
    setLoading(true); setErr(null);
    fetch(`${API}/api/onchain/smart-money/wallet/${encodeURIComponent(address)}/context?chainId=1&window=24h`)
      .then(r => r.json()).then(j => { if (j.ok) setD(j); else setErr(j.error || 'Failed'); })
      .catch(e => setErr(e.message)).finally(() => setLoading(false));
  }, [address]);

  if (loading) return <div className="flex items-center justify-center py-20" data-testid="wallet-loading"><div className="animate-spin w-6 h-6 border-2 border-gray-300 border-t-gray-900 rounded-full" /></div>;
  if (err || !d) return <div className="flex items-center justify-center py-20" data-testid="wallet-error"><p className="text-sm text-gray-400">{err || 'No data'}</p></div>;

  const w = d.wallet, perf = d.performance, beh = d.behavior, ins = d.insight;
  const tim = d.timing || {}, inf = d.influence || {}, cred = d.credibility || {};
  const alpha = d.alpha_score || {}, rank = d.wallet_rank || {}, tq = d.trade_quality || {};
  const rot = d.capital_rotation || {}, cp = d.copy_potential || {}, stab = d.strategy_stability || {};
  const liq = d.liquidity_impact || {}, sigrel = d.signal_reliability || {}, pi = d.portfolio_interpretation || {};
  const we = d.wallet_edge || {}, tr = d.trade_replay || {}, cs = d.copy_signal || {};
  const signals = d.signals || [], tokens = d.tokens || [], trades = d.trades || {};
  const related = d.related_wallets || [], counters = d.counterparties || [];
  const sc = alpha.score || 0;
  const scC = sc >= 70 ? 'text-emerald-400' : sc >= 40 ? 'text-amber-400' : 'text-rose-400';
  const scB = sc >= 70 ? 'bg-emerald-500' : sc >= 40 ? 'bg-amber-500' : 'bg-rose-500';

  return (
    <TooltipProvider>
      <div data-testid="wallet-page" className="max-w-[1600px] mx-auto space-y-4">
        <button onClick={goBack} className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-700 transition-colors" data-testid="wallet-nav-back">
          <ArrowLeft className="w-3.5 h-3.5" />Back
        </button>

        {navFrom && (
          <div className="flex items-center gap-2 text-[11px] text-gray-400" data-testid="nav-context">
            <span className="uppercase font-semibold tracking-wider">Viewed from</span>
            <ArrowRight className="w-3 h-3" />
            <span className="font-semibold text-gray-600 capitalize">{navFrom.replace(/_/g, ' ')}</span>
            {navToken && (
              <>
                <ArrowRight className="w-3 h-3" />
                <span className="font-bold text-gray-700">{navToken}</span>
              </>
            )}
          </div>
        )}

        {/* ═══ ROW 0 — ACTOR IDENTITY (WHITE) ════════════════════════ */}
        <Wh id="actor-header" className="!p-6">
          <div className="flex items-start justify-between gap-6">
            <div>
              <div className="flex items-center gap-3 mb-1.5 flex-wrap">
                <h2 className="text-xl font-bold text-gray-900 tracking-tight break-words" data-testid="wallet-name">{w.name?.replace(/_/g, ' ')}</h2>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-gray-100 text-gray-500">{w.actor_category?.replace(/_/g, ' ')}</span>
              </div>
              <div className="flex items-center gap-2.5 mb-5 flex-wrap">
                <span className="text-xs text-gray-500 break-all" data-testid="wallet-address">{address}</span>
                <Tooltip delayDuration={100}>
                  <TooltipTrigger asChild>
                    <button onClick={copyAddr} className="text-gray-400 hover:text-gray-900 transition-colors flex-shrink-0" data-testid="wallet-copy"><Copy className="w-3.5 h-3.5" /></button>
                  </TooltipTrigger>
                  <TooltipContent className="text-xs">{copied ? 'Copied!' : 'Copy address'}</TooltipContent>
                </Tooltip>
                <Tooltip delayDuration={100}>
                  <TooltipTrigger asChild>
                    <a href={`https://etherscan.io/address/${address}`} target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-blue-600 transition-colors flex-shrink-0" data-testid="wallet-explorer"><ExternalLink className="w-3.5 h-3.5" /></a>
                  </TooltipTrigger>
                  <TooltipContent className="text-xs">Etherscan</TooltipContent>
                </Tooltip>
              </div>
              <div className="grid grid-cols-3 md:grid-cols-6 gap-x-8 gap-y-3">
                {[
                  ['Actor Type', w.actor_type, 'text-gray-900'],
                  ['Behavior', w.actor_behavior, STC[w.strategy] || 'text-gray-900'],
                  ['Credibility', cred.score, LC[cred.score] || 'text-gray-900'],
                  ['Activity', w.activity, LC[w.activity] || 'text-gray-900'],
                  ['Alignment', ins.signal_alignment, ins.signal_alignment === 'bullish' ? 'text-emerald-600' : ins.signal_alignment === 'bearish' ? 'text-rose-600' : 'text-gray-500'],
                  ['Networks', (w.networks || []).join(' / '), 'text-gray-900'],
                ].map(([lbl, val, cls]) => (
                  <div key={lbl as string}>
                    <div className={`${LBL} text-gray-400`}>{lbl}</div>
                    <div className={`text-sm font-bold mt-1 capitalize ${cls}`}>{val}</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="text-center flex-shrink-0 min-w-[120px]">
              <Tooltip delayDuration={200}>
                <TooltipTrigger asChild><div className={`${LBL} text-gray-400 cursor-default`}>Alpha Score</div></TooltipTrigger>
                <TooltipContent side="left" className="max-w-[220px] text-xs">Composite intelligence score: PnL, timing, signal accuracy, consistency.</TooltipContent>
              </Tooltip>
              <div className={`text-4xl font-bold mt-1 tracking-tight ${scC}`} data-testid="wallet-alpha-score">{sc}</div>
              <div className="w-20 mx-auto mt-2"><Bar value={sc} color={scB} dark={false} /></div>
              <div className="text-xs font-bold text-gray-500 mt-2">{rank.label}</div>
              <div className="text-[10px] text-gray-400">Rank #{rank.rank?.toLocaleString()} / {rank.total?.toLocaleString()}</div>
            </div>
          </div>
        </Wh>

        {/* ═══ ROW 1 — AI SUMMARY (DARK) ═════════════════════════════ */}
        <Dk id="wallet-insight" className="!p-6">
          <SH icon={<Zap className="w-4 h-4 text-emerald-400" />} title="Actor Summary" tip="AI-generated behavioral profile: strategy, position, recent patterns." />
          <p className="text-sm text-gray-300 leading-relaxed mb-4">{ins.summary ? ins.summary.replace(/\n\n/g, ' ').replace(/_/g, ' ') : 'No summary available.'}</p>
          <div className="flex items-center gap-3 mb-4">
            <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider bg-gray-800 text-gray-200`} data-testid="alignment-badge">{ins.signal_alignment}</span>
            <span className="text-[10px] text-gray-600">confidence {ins.strategy_confidence}</span>
          </div>
          <div className="grid grid-cols-4 gap-4 pt-4 border-t border-gray-800">
            {Object.entries(cred.breakdown || {}).map(([k, v]: [string, any]) => (
              <div key={k}>
                <div className="text-[10px] text-gray-500 capitalize mb-1">{k.replace(/_/g, ' ')}</div>
                <div className={`text-xs font-bold capitalize ${LC[v] || 'text-gray-400'}`}>{v}</div>
              </div>
            ))}
          </div>
        </Dk>

        {/* ═══ ROW 2 — ANALYTICS (ALL DARK) ══════════════════════════ */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Alpha Score */}
          <Dk id="alpha-score">
            <SH icon={<Target className="w-4 h-4 text-amber-400" />} title="Alpha Score" tip="Composite: PnL quality, timing, signal accuracy, consistency, risk control." />
            <div className="flex items-baseline gap-3 mb-4">
              <span className={`text-3xl font-bold tracking-tight ${scC}`}>{sc}</span>
              <span className="text-xs text-gray-500">{rank.label}</span>
              <span className="text-[10px] text-gray-600">#{rank.rank?.toLocaleString()} / {rank.total?.toLocaleString()}</span>
            </div>
            <div className="space-y-2.5">
              {Object.entries(alpha.breakdown || {}).map(([k, v]: [string, any]) => (
                <div key={k}>
                  <div className="flex justify-between mb-1">
                    <span className="text-[10px] text-gray-500 capitalize">{k.replace(/_/g, ' ')}</span>
                    <span className="text-[10px] text-gray-400">{v}</span>
                  </div>
                  <Bar value={v} color={v >= 70 ? 'bg-emerald-500' : v >= 40 ? 'bg-amber-500' : 'bg-rose-500'} />
                </div>
              ))}
            </div>
          </Dk>

          {/* Strategy Fingerprint */}
          <Dk id="strategy-fingerprint">
            <SH icon={<BarChart3 className="w-4 h-4 text-violet-400" />} title="Strategy Fingerprint" tip="DNA profile: entry style, holding, execution, portfolio management." />
            <div className={`text-sm font-bold mb-4 ${STC[beh.strategy] || 'text-gray-100'}`}>{beh.strategy_label}</div>
            <DR label="Entry Style" value={beh.entry_style} vc="text-gray-100 capitalize" />
            <DR label="Holding" value={beh.holding_style?.replace('_', ' ')} vc="text-gray-100 capitalize" />
            <DR label="Execution" value={beh.execution_style?.toUpperCase()} />
            <DR label="Portfolio" value={beh.token_behavior} vc="text-gray-100 capitalize" />
            <DR label="Risk Profile" value={(alpha.breakdown?.risk_control || 0) > 60 ? 'Conservative' : 'Aggressive'} vc={(alpha.breakdown?.risk_control || 0) > 60 ? 'text-emerald-400' : 'text-rose-400'} />
            <DR label="Rotation" value={rot.frequency} />
            {beh.traits?.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-4 pt-4 border-t border-gray-800">
                {beh.traits.map((t: string, i: number) => <span key={i} className="px-2 py-0.5 rounded-full bg-gray-800 text-[10px] text-gray-400">{t}</span>)}
              </div>
            )}
          </Dk>

          {/* Market Timing */}
          <Dk id="market-timing">
            <SH icon={<TrendingUp className="w-4 h-4 text-emerald-400" />} title="Market Timing" tip="Does the actor enter before or after market momentum?" />
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div><div className={`${LBL} text-gray-500`}>Early entries</div><div className="text-xl font-bold text-emerald-400 mt-1">{((tim.early_entry_ratio || 0) * 100).toFixed(0)}%</div></div>
              <div><div className={`${LBL} text-gray-500`}>Late entries</div><div className="text-xl font-bold text-rose-400 mt-1">{((tim.late_entry_ratio || 0) * 100).toFixed(0)}%</div></div>
              <div><div className={`${LBL} text-gray-500`}>Lead time</div><div className="text-lg font-bold text-gray-100 mt-1">{tim.avg_lead_time || 'N/A'}</div></div>
              <div><div className={`${LBL} text-gray-500`}>Signal align.</div><div className="text-lg font-bold text-gray-100 mt-1">{((tim.signal_alignment || 0) * 100).toFixed(0)}%</div></div>
            </div>
            {tim.verdict && <p className="text-xs text-gray-500 leading-relaxed pt-3 border-t border-gray-800">{tim.verdict}</p>}
          </Dk>
        </div>

        {/* ═══ ROW 3 — METRICS (ALL WHITE) ═══════════════════════════ */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Wh id="performance">
            <SH icon={<BarChart3 className="w-4 h-4 text-blue-600" />} title="Performance" tip="Realized PnL, win rate, volume, trade execution quality." dark={false} />
            <WR label="Realized PnL" value={`${perf.pnl >= 0 ? '+' : ''}${perf.pnl_fmt}`} vc={perf.pnl >= 0 ? 'text-emerald-600' : 'text-rose-600'} />
            <WR label="Win Rate" value={`${(perf.win_rate * 100).toFixed(0)}%`} />
            <WR label="Volume" value={perf.total_volume_fmt} />
            <WR label="Avg Trade" value={perf.avg_trade_fmt} />
            <WR label="Trades" value={trades.total} />
            <div className="mt-4 pt-4 border-t border-gray-100">
              <div className={`${LBL} text-gray-400 mb-2`}>Trade Quality</div>
              <WR label="Entry Quality" value={tq.entry_quality} />
              <WR label="Profit Capture" value={`${tq.profit_capture}%`} />
              <WR label="Execution" value={tq.execution_efficiency} />
            </div>
          </Wh>

          <Wh id="capital-flow">
            <SH icon={<Repeat2 className="w-4 h-4 text-cyan-600" />} title="Capital Flow" tip="Accumulation, distribution and rotation patterns." dark={false} />
            <div className="grid grid-cols-3 gap-2 mb-4">
              {[['Accum', rot.accumulation_pct, 'text-emerald-600'], ['Distrib', rot.distribution_pct, 'text-rose-600'], ['Rotation', rot.rotation_pct, 'text-blue-600']].map(([l, v, c]) => (
                <div key={l as string} className="text-center py-2.5 rounded-lg bg-gray-50">
                  <div className={`${LBL} text-gray-400`}>{l}</div>
                  <div className={`text-sm font-bold ${c} mt-0.5`}>{v}%</div>
                </div>
              ))}
            </div>
            {rot.rotations?.length > 0 && rot.rotations.map((r: any, i: number) => (
              <div key={i} className="flex items-center gap-2 py-1">
                <span className="text-xs font-bold text-rose-600">{r.from}</span>
                <ArrowRight className="w-3 h-3 text-gray-300" />
                <span className="text-xs font-bold text-emerald-600">{r.to}</span>
              </div>
            ))}
          </Wh>

          <Wh id="positioning">
            <SH icon={<PieChart className="w-4 h-4 text-amber-600" />} title="Positioning" tip="Current portfolio allocation and exposure interpretation." dark={false} />
            {tokens.length > 0 ? (
              <div className="space-y-2.5">
                {tokens.slice(0, 5).map((t: any, i: number) => (
                  <div key={t.symbol} className="flex items-center gap-2" data-testid={`token-${i}`}>
                    <span className="text-xs font-bold text-gray-900 w-12">{t.symbol}</span>
                    <div className="flex-1"><Bar value={t.allocation * 100} color={t.direction === 'buy' ? 'bg-emerald-500' : 'bg-rose-500'} dark={false} /></div>
                    <span className="text-[11px] text-gray-500 w-10 text-right">{t.allocation_pct}</span>
                    {t.direction === 'buy' ? <ArrowUpRight className="w-3 h-3 text-emerald-600" /> : <ArrowDownRight className="w-3 h-3 text-rose-600" />}
                  </div>
                ))}
              </div>
            ) : <p className="text-xs text-gray-400">No token data</p>}
            {pi.text && <p className="text-[11px] text-gray-500 mt-4 pt-4 border-t border-gray-100 leading-relaxed">{pi.text}</p>}
          </Wh>
        </div>

        {/* ═══ ROW 4 — SIGNALS (ALL DARK) ════════════════════════════ */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Dk id="signals">
            <SH icon={<Radio className="w-4 h-4 text-violet-400" />} title="Signals" tip="On-chain signals triggered by this actor." />
            {signals.length > 0 ? (
              <div className="space-y-2">
                {signals.map((s: any, i: number) => (
                  <div key={i} className="flex items-center gap-2" data-testid={`signal-${i}`}>
                    <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${SIGD[s.type] || 'bg-gray-600'}`} />
                    <span className={`text-xs font-bold uppercase ${SIGC[s.type] || 'text-gray-400'}`}>{s.type?.replace('_', ' ')}</span>
                    <span className="text-xs font-semibold text-gray-100">{s.token}</span>
                    <span className="ml-auto text-sm font-bold text-gray-100">{s.conviction}%</span>
                  </div>
                ))}
                <div className="pt-3 border-t border-gray-800">
                  <DR label="Contribution" value={`${inf.signal_contribution} signals`} />
                  <DR label="Cluster overlap" value={`${inf.cluster_overlap} wallets`} />
                </div>
              </div>
            ) : <p className="text-xs text-gray-600">No signals triggered</p>}
          </Dk>

          <Dk id="activity">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-cyan-400" />
                <Tooltip delayDuration={200}><TooltipTrigger asChild><h4 className="text-xs font-semibold uppercase tracking-wider cursor-default text-gray-400 hover:text-gray-200 transition-colors">Activity</h4></TooltipTrigger><TooltipContent side="bottom" className="max-w-[260px] text-xs">Recent trading activity: DEX vs CEX ratio and latest transactions.</TooltipContent></Tooltip>
              </div>
              <span className="text-[10px] text-gray-500">{trades.total} trades</span>
            </div>
            {trades.total > 0 && (
              <div className="mb-4">
                <div className="flex justify-between text-[10px] text-gray-500 mb-1"><span>DEX {(trades.dex_share * 100).toFixed(0)}%</span><span>CEX {(trades.cex_share * 100).toFixed(0)}%</span></div>
                <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden flex">
                  <div className="h-full bg-blue-500 rounded-l-full" style={{ width: `${trades.dex_share * 100}%` }} />
                  <div className="h-full bg-amber-500 rounded-r-full" style={{ width: `${trades.cex_share * 100}%` }} />
                </div>
              </div>
            )}
            {trades.recent?.length > 0 ? (
              <div className="space-y-2">
                {trades.recent.slice(0, 6).map((t: any, i: number) => (
                  <div key={i} className="flex items-center gap-2" data-testid={`trade-${i}`}>
                    <span className={`text-xs font-bold w-6 ${t.side === 'Buy' ? 'text-emerald-400' : 'text-rose-400'}`}>{t.side}</span>
                    <span className="text-xs font-semibold text-gray-100">{t.token}</span>
                    <span className="ml-auto text-xs text-gray-400">{t.amount_fmt}</span>
                    <span className="text-[10px] text-gray-600 uppercase">{t.venue}</span>
                  </div>
                ))}
              </div>
            ) : <p className="text-xs text-gray-600">No recent trades</p>}
          </Dk>

          <Dk id="signal-reliability">
            <SH icon={<Shield className="w-4 h-4 text-emerald-400" />} title="Signal Reliability" tip="Historical accuracy and copy-trading potential." />
            <DR label="Signals triggered" value={sigrel.signals_triggered} />
            <DR label="Profitable" value={sigrel.profitable_signals} vc="text-emerald-400" />
            <DR label="Accuracy" value={`${sigrel.accuracy}%`} />
            {sigrel.best_signals?.length > 0 && (
              <div className="mt-3 pt-3 border-t border-gray-800">
                <div className={`${LBL} text-gray-500 mb-2`}>Best signals</div>
                {sigrel.best_signals.map((s: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 py-0.5">
                    <span className={`w-1.5 h-1.5 rounded-full ${SIGD[s.type] || 'bg-gray-600'}`} />
                    <span className={`text-xs font-semibold ${SIGC[s.type] || 'text-gray-400'}`}>{s.token}</span>
                    <span className="ml-auto text-xs text-gray-400">{s.conviction}%</span>
                  </div>
                ))}
              </div>
            )}
            <div className="mt-4 pt-4 border-t border-gray-800">
              <div className={`${LBL} text-gray-500 mb-2`}>Copy Potential</div>
              <div className="flex items-baseline gap-2 mb-2">
                <span className={`text-2xl font-bold ${cp.rating === 'A' ? 'text-emerald-400' : cp.rating?.startsWith('B') ? 'text-amber-400' : 'text-rose-400'}`}>{cp.rating}</span>
                <span className="text-xs text-gray-500">score {cp.composite}</span>
              </div>
              <DR label="Stability" value={`${stab.stable_pct}%`} />
              <DR label="Reliability" value={`${cp.signal_reliability}%`} />
            </div>
          </Dk>
        </div>

        {/* ═══ ROW 5 — TRADING TOOLS (ALL DARK) ═════════════════════ */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Trade Replay */}
          <Dk id="trade-replay">
            <SH icon={<Play className="w-4 h-4 text-blue-400" />} title="Trade Replay" tip="Step-by-step strategy timeline: what the wallet did and why." />
            {tr.timeline?.length > 0 ? (
              <div className="space-y-1.5 mb-4">
                {tr.timeline.map((t: any) => (
                  <div key={t.step} className="flex items-center gap-2">
                    <span className="text-[10px] text-gray-600 w-4">{t.step}.</span>
                    <span className={`text-xs font-bold w-6 ${t.action === 'Buy' ? 'text-emerald-400' : 'text-rose-400'}`}>{t.action}</span>
                    <span className="text-xs font-semibold text-gray-100">{t.token}</span>
                    <span className="ml-auto text-xs text-gray-400">{t.amount}</span>
                  </div>
                ))}
              </div>
            ) : <p className="text-xs text-gray-600 mb-4">No trade data</p>}
            {tr.strategy_steps?.length > 0 && (
              <div className="pt-3 border-t border-gray-800">
                <div className={`${LBL} text-gray-500 mb-2`}>Strategy Steps</div>
                {tr.strategy_steps.map((s: string, i: number) => (
                  <div key={i} className="flex items-start gap-2 py-0.5">
                    <span className="text-[10px] text-gray-600 mt-0.5">{i + 1}.</span>
                    <span className="text-xs text-gray-300">{s}</span>
                  </div>
                ))}
              </div>
            )}
          </Dk>

          {/* Wallet Edge */}
          <Dk id="wallet-edge">
            <SH icon={<Crosshair className="w-4 h-4 text-amber-400" />} title="Wallet Edge" tip="What makes this wallet strong: timing, execution, discovery, risk." />
            <DR label="Timing Edge" value={we.timing_edge} vc={LC[we.timing_edge] || 'text-gray-100'} />
            <DR label="Execution Speed" value={we.execution_speed} vc={LC[we.execution_speed] || 'text-gray-100'} />
            <DR label="Token Discovery" value={we.token_discovery} vc={LC[we.token_discovery] || 'text-gray-100'} />
            <DR label="Risk Discipline" value={we.risk_discipline} vc={LC[we.risk_discipline] || 'text-gray-100'} />
            {we.interpretation && <p className="text-xs text-gray-500 leading-relaxed mt-4 pt-4 border-t border-gray-800">{we.interpretation}</p>}
          </Dk>

          {/* Copy Signal */}
          <Dk id="copy-signal">
            <SH icon={<Crosshair className="w-4 h-4 text-cyan-400" />} title="Copy Signal" tip="Current position interpretation for copy-trading." />
            <div className={`${LBL} text-gray-500 mb-1`}>Current Position</div>
            <div className="flex items-baseline gap-2 mb-3">
              <span className="text-lg font-bold text-gray-100">{cs.current_token}</span>
              <span className={`text-xs font-bold uppercase ${SIGC[cs.signal_type?.toLowerCase()] || 'text-gray-400'}`}>{cs.signal_type}</span>
            </div>
            <DR label="Confidence" value={`${cs.confidence}%`} vc={cs.confidence >= 60 ? 'text-emerald-400' : 'text-amber-400'} />
            <DR label="Direction" value={cs.direction} vc="text-gray-100 capitalize" />
            <div className="mt-4 pt-4 border-t border-gray-800">
              <div className={`${LBL} text-gray-500 mb-1`}>Wallet Bias</div>
              <div className={`text-sm font-bold capitalize ${cs.bias === 'bullish' ? 'text-emerald-400' : cs.bias === 'bearish' ? 'text-rose-400' : 'text-gray-400'}`}>{cs.bias}</div>
            </div>
            <div className="mt-3 pt-3 border-t border-gray-800">
              <DR label="Copy Rating" value={cs.rating} vc={cs.rating === 'A' ? 'text-emerald-400' : cs.rating?.startsWith('B') ? 'text-amber-400' : 'text-rose-400'} />
              <DR label="Composite" value={cs.composite} />
            </div>
          </Dk>
        </div>

        {/* ═══ ROW 6 — NETWORK (ALL WHITE) ═══════════════════════════ */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Wh id="counterparties">
            <SH icon={<Link2 className="w-4 h-4 text-blue-600" />} title="Counterparties" tip="Entities and protocols this actor interacts with." dark={false} />
            {counters.length > 0 ? (
              <div className="space-y-2.5">
                {counters.map((c: any, i: number) => (
                  <div key={i} className="flex items-center gap-2" data-testid={`cp-${i}`}>
                    <span className={`w-2 h-2 rounded-full flex-shrink-0 ${{ dex: 'bg-blue-500', cex: 'bg-amber-500', bridge: 'bg-cyan-500' }[c.type] || 'bg-gray-300'}`} />
                    <span className="text-xs font-semibold text-gray-900 flex-1">{c.name?.replace(/_/g, ' ')}</span>
                    <span className="text-xs font-bold text-gray-900">{c.volume_fmt}</span>
                    <span className="text-[10px] text-gray-400 w-8 text-right">{(c.share * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            ) : <p className="text-xs text-gray-400">No counterparties</p>}
          </Wh>

          <Wh id="related-actors">
            <SH icon={<Users className="w-4 h-4 text-violet-600" />} title="Related Actors" tip="Wallets with similar behavior or shared clusters." dark={false} />
            {related.length > 0 ? (
              <div className="space-y-1.5">
                {related.slice(0, 5).map((r: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 rounded-lg px-2 -mx-2 py-1.5 transition-colors"
                       onClick={() => { if (!onBack) nav(`/wallet/${encodeURIComponent(r.address)}?src=actor`); }}
                       data-testid={`related-${i}`}>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-semibold text-gray-900">{r.is_wallet ? `${r.address.slice(0, 6)}...${r.address.slice(-4)}` : r.name?.replace(/_/g, ' ')}</div>
                      <div className="text-[10px] text-gray-400 capitalize">{r.relation?.replace(/_/g, ' ')}</div>
                    </div>
                    <span className="text-xs font-bold text-gray-900">{r.similarity}%</span>
                    {r.is_wallet && <ArrowRight className="w-3 h-3 text-gray-300" />}
                  </div>
                ))}
              </div>
            ) : <p className="text-xs text-gray-400">No related actors</p>}
          </Wh>

          <Wh id="liquidity-impact">
            <SH icon={<Droplets className="w-4 h-4 text-cyan-600" />} title="Liquidity Impact" tip="Trade size impact on pool depth, slippage, and market influence." dark={false} />
            <WR label="Avg Trade Size" value={liq.avg_trade_size} />
            <WR label="Pool Impact" value={liq.pool_impact} />
            <WR label="Slippage" value={liq.slippage} />
            <div className="mt-4 pt-4 border-t border-gray-100">
              <div className={`${LBL} text-gray-400 mb-1`}>Market Influence</div>
              <div className={`text-lg font-bold ${liq.market_influence === 'High' ? 'text-rose-600' : liq.market_influence === 'Moderate' ? 'text-amber-600' : 'text-gray-500'}`}>{liq.market_influence}</div>
            </div>
            <div className="mt-4 pt-4 border-t border-gray-100">
              <div className={`${LBL} text-gray-400 mb-2`}>Strategy Stability</div>
              <WR label="Primary Strategy" value={stab.primary_strategy} />
              <WR label="Stable" value={`${stab.stable_pct}%`} />
              <WR label="Changes" value={stab.strategy_changes} />
              <WR label="Consistency" value={stab.consistency_score} />
            </div>
          </Wh>
        </div>
      </div>
    </TooltipProvider>
  );
}
