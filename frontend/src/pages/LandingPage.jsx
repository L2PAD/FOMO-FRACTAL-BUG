import { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence, useInView } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import {
  Shield, Zap, Radio, BarChart3, Globe2,
  Brain, Activity, ArrowRight, ChevronRight, Lock,
  Layers, Eye, Target, Star, TrendingUp,
  Network, Send, Bell, Cpu,
  LineChart, Crosshair, Terminal,
  Smartphone, Monitor, Bot, Workflow, Gauge, Clock, Database
} from 'lucide-react';

/* ═══════════════════════════════════════════════
   HOOKS & UTILITIES
   ═══════════════════════════════════════════════ */

/* Scramble text — "decryption" effect */
function useScrambleText(text, trigger, duration = 600) {
  const [display, setDisplay] = useState(text);
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*';

  useEffect(() => {
    if (!trigger) return;
    let frame = 0;
    const totalFrames = Math.ceil(duration / 30);
    const interval = setInterval(() => {
      frame++;
      const progress = frame / totalFrames;
      const revealed = Math.floor(progress * text.length);
      let result = '';
      for (let i = 0; i < text.length; i++) {
        if (text[i] === ' ') { result += ' '; continue; }
        result += i < revealed ? text[i] : chars[Math.floor(Math.random() * chars.length)];
      }
      setDisplay(result);
      if (frame >= totalFrames) { clearInterval(interval); setDisplay(text); }
    }, 30);
    return () => clearInterval(interval);
  }, [text, trigger]);

  return display;
}

/* Typewriter effect */
function Typewriter({ text, speed = 20, delay = 0, className = '' }) {
  const [displayed, setDisplayed] = useState('');
  const [started, setStarted] = useState(false);

  useEffect(() => {
    setDisplayed('');
    setStarted(false);
    const startTimer = setTimeout(() => setStarted(true), delay);
    return () => clearTimeout(startTimer);
  }, [text, delay]);

  useEffect(() => {
    if (!started) return;
    let i = 0;
    const interval = setInterval(() => {
      i++;
      setDisplayed(text.slice(0, i));
      if (i >= text.length) clearInterval(interval);
    }, speed);
    return () => clearInterval(interval);
  }, [started, text, speed]);

  return (
    <span className={className}>
      {displayed}
      {displayed.length < text.length && started && (
        <span className="inline-block w-[2px] h-[1em] bg-[#D4AF37] ml-0.5 animate-pulse align-middle" />
      )}
    </span>
  );
}

/* Running hex background */
function CodeStream({ className = '' }) {
  const lines = useRef(
    Array.from({ length: 12 }, () =>
      Array.from({ length: 80 }, () => '0123456789abcdef'[Math.floor(Math.random() * 16)]).join('')
    )
  );

  return (
    <div className={`absolute inset-0 overflow-hidden pointer-events-none select-none ${className}`}>
      <div className="animate-scroll-code font-mono text-[10px] leading-[18px] text-white/[0.015] whitespace-pre">
        {lines.current.map((l, i) => <div key={i}>{l}</div>)}
        {lines.current.map((l, i) => <div key={`d-${i}`}>{l}</div>)}
      </div>
      <style>{`
        @keyframes scrollCode { from { transform: translateY(0); } to { transform: translateY(-50%); } }
        .animate-scroll-code { animation: scrollCode 20s linear infinite; }
      `}</style>
    </div>
  );
}

/* Fade-in on scroll */
function Anim({ children, className = '', delay = 0 }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-40px' });
  return (
    <motion.div ref={ref}
      initial={{ opacity: 0, y: 16 }}
      animate={inView ? { opacity: 1, y: 0 } : { opacity: 0, y: 16 }}
      transition={{ delay: delay * 0.08, duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }}
      className={className}>
      {children}
    </motion.div>
  );
}

/* ═══════════════════════════════════════════════
   MODULE DATA
   ═══════════════════════════════════════════════ */
const MODULES = [
  {
    id: '01', cmd: 'FRACTAL_ANALYSIS', title: 'Fractal Analysis',
    icon: Layers, color: '#A78BFA',
    tagline: 'Multi-horizon market structure intelligence',
    output: [
      '> Initializing fractal engine...',
      '> Loading BTC Elliott Wave model (4H / 1D / 1W)',
      '> S&P 500 cycle correlation: mapping cross-asset divergence',
      '> DXY macro regime: STRONG_DOLLAR → BTC inverse pressure',
      '> Macro Brain: synthesizing 4 asset classes',
      '> Auto-detecting support & resistance clusters',
      '> Wave probability: continuation 67% | failure 18% | upgrade 15%',
      '> Fractal engine online. 3 horizons active.',
    ],
    features: ['BTC Elliott Wave detection across 4H, 1D, 1W timeframes', 'S&P 500 cycle analysis with real-time correlation mapping', 'DXY dollar index macro regime identification', 'Macro Brain: cross-asset divergence signal detection', 'Auto-detected support & resistance cluster mapping', 'Wave probability scoring — continuation, failure, upgrade'],
  },
  {
    id: '02', cmd: 'EXCHANGE_INTEL', title: 'Exchange Intelligence',
    icon: BarChart3, color: '#60A5FA',
    tagline: '40+ indicators. All exchanges. Real-time.',
    output: [
      '> Connecting to 12 exchanges...',
      '> Open Interest: +$840M (24h) — bullish divergence',
      '> Funding rate: 0.024% — moderately long-biased',
      '> Liquidation heatmap: $94,200 cluster (shorts)',
      '> Volume-weighted momentum: +2.4σ deviation',
      '> Order flow imbalance: 68% buy-side pressure',
      '> Capital flow: $120M migrated Binance → Bybit',
      '> Labs: Regime=TRENDING | Attribution=OI+Volume',
      '> 38/40 indicators aligned. Signal confidence: HIGH.',
    ],
    features: ['Open Interest, Funding Rate, Liquidation tracking', 'Volume-weighted price momentum analysis', 'Order flow imbalance detection across exchanges', 'Whale position tracking — CEX and DEX combined', 'Capital flow radar between major exchanges', 'Labs modules: Regime, Attribution, Pattern Risk, Whale Risk'],
  },
  {
    id: '03', cmd: 'ONCHAIN_INTEL', title: 'On-chain Intelligence',
    icon: Network, color: '#34D399',
    tagline: 'Full-spectrum blockchain analysis',
    output: [
      '> Scanning blockchain mempool...',
      '> SIGNAL: 3 wallets moved 12,400 BTC to cold storage',
      '> Smart Money entity "0x7a3..f2e" accumulating since $91K',
      '> Token neural network score: 0.84 (bullish)',
      '> Entity Graph: 847 connected wallets mapped',
      '> CEX Flow: -$240M net outflow (accumulation signal)',
      '> Event Radar: dormant wallet 0xb4c.. active after 2.3 years',
      '> Bridge: $18M USDC moved Ethereum → Arbitrum',
      '> On-chain engine online. Monitoring 14M+ addresses.',
    ],
    features: ['Signals Terminal: real-time transaction intelligence', 'Smart Money tracking with entity labeling', 'Token Intelligence with neural network scoring', 'Entity Graph: wallet relationship visualization', 'CEX Flow analysis with exchange attribution', 'Event Radar: dormant wallet activation, bridge flows, risk alerts'],
  },
  {
    id: '04', cmd: 'SENTIMENT_ENGINE', title: 'Sentiment Engine',
    icon: Activity, color: '#FBBF24',
    tagline: 'Social intelligence. Real-time parsing.',
    output: [
      '> Parsing Twitter/X firehose...',
      '> 24h tweet volume: 142K crypto-related',
      '> Bullish sentiment ratio: 78.3% (+4.2% vs 7d avg)',
      '> Top influencer consensus: 8/10 LONG bias',
      '> News impact: "ETF inflows hit $1.2B" — HIGH positive',
      '> Fear & Greed Index: 74 (Greed)',
      '> Sentiment shift detected: pre-move bullish acceleration',
      '> Historical correlation: 82% when sentiment > 75%',
    ],
    features: ['Twitter/X live parsing with real-time sentiment scoring', 'Influencer opinion tracking and consensus analysis', 'News aggregation with market impact classification', 'Fear & Greed Index integration', 'Sentiment shift detection before price moves', 'Historical sentiment-to-price correlation mapping'],
  },
  {
    id: '05', cmd: 'PREDICTION_MKT', title: 'Prediction Markets',
    icon: Crosshair, color: '#F87171',
    tagline: 'Polymarket & Kalshi alpha extraction',
    output: [
      '> Loading Polymarket + Kalshi feeds...',
      '> "BTC > $100K by Apr 15" — Poly: 0.71 | Kalshi: 0.68',
      '> Cross-market spread detected: +3.2% arbitrage',
      '> Volume spike: $2.4M in last hour (3x average)',
      '> ML confidence: 0.82 for YES outcome',
      '> Whale bet: $180K YES @ 0.72 (single order)',
      '> Analytics: 73.2% historical accuracy on similar setups',
      '> SIGNAL: High-conviction opportunity detected.',
    ],
    features: ['Live market overview with probability tracking', 'Signal detection: volume spikes, odds shifts, whale bets', 'Cross-market spread: Polymarket vs Kalshi arbitrage', 'ML-powered outcome probability scoring', 'Analytics: historical accuracy and P&L tracking', 'Smart alerts on high-conviction market movements'],
  },
  {
    id: '06', cmd: 'TELEGRAM_INTEL', title: 'Telegram Intelligence',
    icon: Send, color: '#22D3EE',
    tagline: 'Full influencer feed. Zero noise.',
    output: [
      '> Connecting to 100+ private channels...',
      '> Feed parsing: 2,400 messages/hour',
      '> @CryptoAlpha: "BTC breakout imminent, targets $102K"',
      '> @WhaleAlert: "500 BTC moved to Coinbase" (SELL signal)',
      '> Influencer accuracy ranking updated',
      '> Top 5 by hit rate: @trader_xyz (84%), @onchain_guru (79%)',
      '> Content filter: 34 alpha calls, 12 TA signals, 8 news',
      '> Cross-referencing with on-chain data... 6 signals confirmed.',
    ],
    features: ['Live feed from 100+ crypto Telegram channels', 'Influencer ranking by accuracy and signal quality', 'Content filtering: signals, analysis, alpha calls', 'Channel sentiment aggregation and trend detection', 'Cross-reference with on-chain and exchange data', 'Custom alert rules for specific channels or keywords'],
  },
  {
    id: '07', cmd: 'META_BRAIN', title: 'Alpha / Meta Brain',
    icon: Brain, color: '#D4AF37',
    tagline: 'Cross-layer synthesis. One unified score.',
    output: [
      '> Aggregating 10 intelligence layers...',
      '> Fractal: BULLISH (0.78) | Exchange: BULLISH (0.84)',
      '> On-chain: BULLISH (0.81) | Sentiment: BULLISH (0.76)',
      '> Prediction: BULLISH (0.82) | Telegram: NEUTRAL (0.54)',
      '> Cross-layer confidence: 0.87 — HIGH',
      '> Regime: TRENDING | Sector rotation: RISK-ON',
      '> BTC Dominance rising → altcoin rotation lag expected',
      '> FOMO AI: "Asymmetric long setup. Risk/reward 3.2:1"',
      '> META VERDICT: STRONG BUY | Position size: 2.8% portfolio',
    ],
    features: ['Aggregates all 10 intelligence layers into one verdict', 'Cross-layer confidence scoring with calibration', 'Sector rotation detection and bias calculation', 'BTC Dominance + Stablecoin flow analysis', 'FOMO AI: asset-specific deep analysis on any symbol', 'Lab Attribution: which layer drives the current signal'],
  },
  {
    id: '08', cmd: 'TECH_ANALYSIS_AI', title: 'Technical Analysis AI',
    icon: LineChart, color: '#F472B6',
    tagline: 'Auto-TA on any chart. Any timeframe.',
    output: [
      '> [COMING SOON] Initializing TA neural network...',
      '> Chart pattern recognition engine: training on 4M candles',
      '> Support/resistance auto-draw: multi-timeframe confluence',
      '> Trend line detection: probability zones calculated',
      '> Pattern: ascending triangle on BTC 4H (78% breakout prob)',
      '> AI report generated: 12 key levels, 3 scenarios',
      '> Predictive target: $103,200 (based on measured move)',
      '> Status: BETA — launching Q2 2026',
    ],
    features: ['AI-powered chart pattern recognition', 'Support/resistance auto-drawing on any timeframe', 'Trend line detection with probability zones', 'Multi-timeframe confluence scoring', 'AI-generated TA reports for any asset', 'Predictive price targets based on pattern completion'],
    soon: true,
  },
  {
    id: '09', cmd: 'SMART_ALERTS', title: 'Smart Alerts',
    icon: Bell, color: '#FB923C',
    tagline: 'Right signal. Right time. Right channel.',
    output: [
      '> Alert engine active. 47 rules configured.',
      '> TRIGGERED: "BTC OI > $20B AND Funding < 0.01%"',
      '> Delivering to Telegram @your_bot...',
      '> Alert includes: entry, targets, stop-loss, position size',
      '> Cross-layer alert: Exchange + On-chain + Sentiment aligned',
      '> Dormant wallet alert: 0xb4c.. moved $14M after 847 days',
      '> History: 23/31 alerts profitable (74.2% hit rate)',
      '> Next check: 14 seconds...',
    ],
    features: ['Telegram bot delivery for instant notifications', 'Custom alert rules with multi-condition logic', 'Cross-layer alerts (exchange + onchain + sentiment)', 'Dormant wallet activation alerts', 'Price target and breakout notifications', 'Alert history with outcome tracking'],
  },
  {
    id: '10', cmd: 'TRADING_TERMINAL', title: 'Trading Terminal',
    icon: Monitor, color: '#06B6D4',
    tagline: 'Auto-execute on intelligence. Binance, Bybit & more.',
    output: [
      '> Connecting exchange APIs...',
      '> Binance: authenticated | Bybit: authenticated',
      '> Portfolio sync: $24,800 across 3 exchanges',
      '> META BRAIN signal: STRONG BUY BTC @ $97,200',
      '> Auto-executing: LONG 0.08 BTC | SL: $95,100 | TP: $103,400',
      '> Position sizing: 2.8% portfolio (Kelly criterion)',
      '> Risk manager: max drawdown -5% | daily limit: 3 trades',
      '> Order filled. Monitoring PnL in real-time.',
    ],
    features: ['Connect Binance, Bybit, OKX and more via API keys', 'Auto-execution based on Meta Brain intelligence signals', 'Position sizing with Kelly criterion and risk parameters', 'Real-time PnL tracking across all connected exchanges', 'Stop-loss and take-profit automation', 'Portfolio dashboard with cross-exchange aggregation'],
    soon: true,
  },
];

/* ═══════════════════════════════════════════════
   HERO SECTION
   ═══════════════════════════════════════════════ */
function HeroLeft({ login }) {
  return (
    <div className="relative flex flex-col justify-center h-full px-8 sm:px-12 lg:px-16 py-12 lg:py-0">
      <div className="mb-12">
        <img src="/assets/logo-main.png" alt="FOMO" className="h-[53px] w-auto" data-testid="landing-logo" />
      </div>

      <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1, duration: 0.4 }}
        className="text-[11px] uppercase tracking-[0.3em] text-black/50 mb-5 font-medium">
        Prediction Intelligence OS
      </motion.p>

      <motion.h1 initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.5 }}
        className="text-4xl sm:text-5xl lg:text-[3.5rem] font-medium leading-[1.05] tracking-tight text-[#0A0A0A] mb-6">
        10 AI layers<br />analyze.<br />
        <span className="text-[#D4AF37]">You decide.</span>
      </motion.h1>

      <motion.p initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35, duration: 0.5 }}
        className="text-[15px] text-black/55 leading-relaxed max-w-md mb-10">
        10 intelligence layers. Auto-trading terminal. Two Telegram Mini Apps.
        Fractal analysis, on-chain neural networks, prediction markets, sentiment radar
        — unified into one decision engine.
        <span className="font-medium text-black/70"> From signal to execution. Zero noise.</span>
      </motion.p>

      {/* Google CTA */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5, duration: 0.5 }}>
        <button onClick={login} data-testid="hero-google-login-btn"
          className="w-full max-w-sm flex items-center justify-center gap-3 px-8 py-4 bg-[#0A0A0A] text-white text-[15px] font-medium tracking-tight rounded-xl hover:bg-black/85 hover:scale-[1.01] active:scale-[0.99] transition-all duration-200 group shadow-lg shadow-black/15">
          <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 24 24">
            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
            <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
          </svg>
          Continue with Google
          <ArrowRight className="w-4 h-4 ml-auto opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-200" />
        </button>
        <p className="text-[12px] text-black/40 mt-3 text-center max-w-sm font-medium">
          Free access to all intelligence layers. No credit card.
        </p>
      </motion.div>

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.7, duration: 0.5 }}
        className="mt-8 flex items-center gap-4 text-[10px] uppercase tracking-[0.15em] text-black/30 font-medium">
        <div className="flex items-center gap-1.5"><Lock className="w-3 h-3" /><span>Encrypted</span></div>
        <span className="text-black/10">|</span>
        <span>Real-time</span>
        <span className="text-black/10">|</span>
        <span>10 Layers</span>
      </motion.div>
    </div>
  );
}

function HeroRight() {
  return (
    <div className="relative h-full bg-[#0A0A0A] overflow-hidden flex flex-col justify-center p-8 sm:p-12 lg:p-16">
      <CodeStream />
      <div className="absolute top-0 left-0 w-px h-full bg-gradient-to-b from-transparent via-[#D4AF37]/30 to-transparent" />

      <div className="relative z-10">
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5, duration: 0.8 }}>
          <div className="flex items-center gap-2 mb-6">
            <div className="w-2 h-2 rounded-full bg-[#D4AF37] animate-pulse" />
            <span className="text-[11px] uppercase tracking-[0.2em] text-zinc-500 font-medium">Live Intelligence Feed</span>
          </div>

          <div className="border border-white/10 rounded-xl overflow-hidden mb-8 bg-[#0D0D0D]">
            <div className="border-b border-white/10 px-4 py-2.5 flex items-center gap-2 bg-white/[0.02]">
              <div className="w-2 h-2 rounded-full bg-emerald-400/80" />
              <div className="w-2 h-2 rounded-full bg-zinc-600" />
              <div className="w-2 h-2 rounded-full bg-zinc-600" />
              <span className="text-[10px] text-zinc-500 ml-2 font-medium">fomo://terminal/live</span>
            </div>
            <div className="p-4 space-y-2.5 text-[13px] font-mono">
              <TLine d={0.7} c="text-[#D4AF37]" t="[FRACTAL] BTC H4 wave 3 extension → target $102,400" />
              <TLine d={1.0} c="text-blue-400" t="[EXCHANGE] OI surge +$840M | Funding 0.024% | 38/40 aligned" />
              <TLine d={1.3} c="text-emerald-400" t="[ONCHAIN] Whale accumulation: 12,400 BTC to cold storage" />
              <TLine d={1.6} c="text-yellow-400" t="[SENTIMENT] Twitter bullish 78% | Influencer consensus: LONG" />
              <TLine d={1.9} c="text-red-400" t="[PREDICTION] BTC >$100K Apr 15 — Poly 0.71 → 0.78 (+9.8%)" />
              <TLine d={2.2} c="text-[#D4AF37]/80" t="[META BRAIN] Cross-layer confidence: 0.87 | Regime: TRENDING" />
              <TLine d={2.5} c="text-purple-400" t="[ALPHA] SPX decorrelation → BTC decoupling signal active" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {[
              { l: 'Intelligence Layers', v: '10', icon: Layers, color: 'text-[#D4AF37]' },
              { l: 'Directional Accuracy', v: '82%', icon: Target, color: 'text-emerald-400' },
              { l: 'Data Points / Day', v: '14M+', icon: Database, color: 'text-purple-400' },
              { l: 'Signal Latency', v: '<2s', icon: Zap, color: 'text-amber-400' },
            ].map((s, i) => (
              <motion.div key={s.l} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.9 + i * 0.12, duration: 0.4 }}
                className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-4">
                <s.icon className={`w-4 h-4 ${s.color} mb-2`} strokeWidth={1.5} />
                <p className="text-xl font-medium text-white tracking-tight">{s.v}</p>
                <p className="text-[9px] uppercase tracking-[0.15em] text-zinc-500 mt-1 font-medium">{s.l}</p>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
}

function TLine({ d, c, t }) {
  return (
    <motion.div initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
      transition={{ delay: d, duration: 0.3 }} className={`${c} truncate`}>{t}</motion.div>
  );
}

/* ═══════════════════════════════════════════════
   INTELLIGENCE TERMINAL — Interactive Split-Screen
   ═══════════════════════════════════════════════ */
function IntelligenceTerminal() {
  const [activeIdx, setActiveIdx] = useState(0);
  const [key, setKey] = useState(0);
  const sectionRef = useRef(null);
  const inView = useInView(sectionRef, { once: true, margin: '-100px' });

  const active = MODULES[activeIdx];

  const handleSelect = useCallback((i) => {
    setActiveIdx(i);
    setKey(k => k + 1);
  }, []);

  // Auto-rotate
  useEffect(() => {
    if (!inView) return;
    const timer = setInterval(() => {
      setActiveIdx(prev => {
        const next = (prev + 1) % MODULES.length;
        setKey(k => k + 1);
        return next;
      });
    }, 8000);
    return () => clearInterval(timer);
  }, [inView]);

  return (
    <section ref={sectionRef} className="bg-[#0A0A0A] relative overflow-hidden" data-testid="intelligence-terminal-section">
      <CodeStream className="opacity-50" />
      <div className="relative z-10 max-w-7xl mx-auto px-6 sm:px-12 lg:px-16 py-24">
        <Anim>
          <p className="text-[11px] uppercase tracking-[0.3em] text-[#D4AF37]/70 mb-3 font-medium">Intelligence Stack</p>
          <h2 className="text-3xl sm:text-4xl font-medium tracking-tight text-white mb-2">
            10 layers of intelligence.
          </h2>
          <p className="text-base text-zinc-400 mb-12 max-w-xl">
            Each module runs independently. Together, they form the most comprehensive
            crypto decision engine available to retail traders.
          </p>
        </Anim>

        {/* Terminal UI */}
        <div className="border border-white/10 rounded-xl overflow-hidden bg-[#0D0D0D]" data-testid="terminal-container">
          {/* Terminal Title Bar */}
          <div className="border-b border-white/10 px-5 py-3 flex items-center gap-2 bg-white/[0.02]">
            <div className="w-2 h-2 rounded-full bg-emerald-400/80" />
            <div className="w-2 h-2 rounded-full bg-yellow-400/60" />
            <div className="w-2 h-2 rounded-full bg-zinc-600" />
            <span className="text-[10px] text-zinc-500 ml-3 font-mono font-medium">
              fomo://intelligence/{active.cmd.toLowerCase()}
            </span>
            <div className="ml-auto flex items-center gap-1.5">
              <Terminal className="w-3 h-3 text-zinc-600" />
              <span className="text-[9px] text-zinc-600 font-mono">v2.4.1</span>
            </div>
          </div>

          {/* Split Content */}
          <div className="grid grid-cols-1 lg:grid-cols-12 min-h-[520px]">
            {/* Left: Module Directory */}
            <div className="lg:col-span-4 border-r border-white/[0.06] bg-[#0A0A0A]" data-testid="terminal-menu-list">
              <div className="p-3 border-b border-white/[0.06]">
                <span className="text-[9px] font-mono text-zinc-600 uppercase tracking-wider">// MODULE DIRECTORY</span>
              </div>
              <div className="py-1">
                {MODULES.map((m, i) => (
                  <button key={m.id}
                    onClick={() => handleSelect(i)}
                    data-testid={`module-select-button-${m.id}`}
                    className={`w-full text-left px-4 py-3 flex items-center gap-3 transition-all duration-150 group border-l-2 ${
                      i === activeIdx
                        ? 'border-[#D4AF37] bg-white/[0.04]'
                        : 'border-transparent hover:bg-white/[0.02] hover:border-white/10'
                    }`}>
                    <span className={`text-[10px] font-mono ${i === activeIdx ? 'text-[#D4AF37]' : 'text-zinc-600'}`}>
                      {m.id}
                    </span>
                    <m.icon className={`w-3.5 h-3.5 flex-shrink-0 ${i === activeIdx ? 'text-[#D4AF37]' : 'text-zinc-600 group-hover:text-zinc-400'}`}
                      strokeWidth={1.5} />
                    <div className="flex-1 min-w-0">
                      <span className={`text-[12px] font-mono truncate block ${
                        i === activeIdx ? 'text-white' : 'text-zinc-400 group-hover:text-zinc-300'
                      }`}>
                        {m.cmd}
                        {m.soon && <span className="text-pink-400/60 text-[9px] ml-1.5">[BETA]</span>}
                      </span>
                    </div>
                    {i === activeIdx && (
                      <motion.div layoutId="active-dot"
                        className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                        style={{ backgroundColor: m.color }} />
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Right: Execution Canvas */}
            <div className="lg:col-span-8 relative" data-testid="terminal-display-area">
              <AnimatePresence mode="wait">
                <motion.div key={key}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="p-6 sm:p-8 h-full">

                  {/* Header */}
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: active.color }} />
                    <ScrambleTitle text={active.title} color={active.color} />
                    {active.soon && (
                      <span className="px-2 py-0.5 bg-pink-500/10 text-pink-400 text-[9px] uppercase tracking-wider font-mono rounded-md">Coming Soon</span>
                    )}
                  </div>
                  <p className="text-sm text-zinc-400 mb-6 font-medium">{active.tagline}</p>

                  {/* Terminal Output */}
                  <div className="bg-[#0A0A0A] border border-white/[0.06] rounded-lg p-4 mb-6 font-mono" data-testid="terminal-output-content">
                    <div className="text-[10px] text-zinc-600 mb-3 flex items-center gap-2">
                      <span>$</span>
                      <Typewriter text={`./run ${active.cmd.toLowerCase()}.exe`} speed={25} className="text-[#D4AF37]" />
                    </div>
                    <div className="space-y-1.5">
                      {active.output.map((line, li) => (
                        <motion.div key={li}
                          initial={{ opacity: 0, x: -4 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: 0.3 + li * 0.15, duration: 0.2 }}
                          className={`text-[11px] leading-relaxed ${
                            line.includes('online') || line.includes('SIGNAL') || line.includes('VERDICT') || line.includes('HIGH')
                              ? 'text-emerald-400'
                              : line.includes('COMING SOON') || line.includes('BETA')
                                ? 'text-pink-400/60'
                                : 'text-zinc-400'
                          }`}>
                          {line}
                        </motion.div>
                      ))}
                    </div>
                  </div>

                  {/* Features */}
                  <div>
                    <p className="text-[9px] font-mono text-zinc-600 uppercase tracking-wider mb-3">// CAPABILITIES</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2">
                      {active.features.map((f, fi) => (
                        <motion.div key={fi}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ delay: 0.8 + fi * 0.1, duration: 0.2 }}
                          className="flex items-start gap-2 text-[12px] text-zinc-300 leading-relaxed">
                          <ChevronRight className="w-3 h-3 mt-0.5 flex-shrink-0" style={{ color: active.color + '80' }} />
                          {f}
                        </motion.div>
                      ))}
                    </div>
                  </div>
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function ScrambleTitle({ text, color }) {
  const display = useScrambleText(text, true, 500);
  return (
    <h3 className="text-xl font-medium font-mono tracking-tight" style={{ color }} data-testid="module-title-scramble">
      {display}
    </h3>
  );
}

/* ═══════════════════════════════════════════════
   PRODUCT ECOSYSTEM — What We Build
   ═══════════════════════════════════════════════ */
function ProductEcosystem() {
  const products = [
    {
      icon: Globe2,
      badge: 'LIVE',
      badgeColor: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
      title: 'Web Terminal',
      desc: 'Full-featured intelligence dashboard. 10 AI layers, real-time signals, portfolio analytics, and cross-market research — in your browser.',
      stats: [
        { label: 'Intelligence Layers', value: '10' },
        { label: 'Exchange Indicators', value: '40+' },
        { label: 'Markets Tracked', value: '2,400+' },
      ],
      color: '#D4AF37',
    },
    {
      icon: Bot,
      badge: 'LIVE',
      badgeColor: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
      title: 'Prediction Mini App',
      desc: 'Telegram-native intelligence. Edge Priority alerts, prediction market signals, and A/B optimized notifications — right in your messenger.',
      stats: [
        { label: 'Edge Alerts', value: '24/7' },
        { label: 'Prediction Markets', value: 'Poly + Kalshi' },
        { label: 'Alert Accuracy', value: '82%' },
      ],
      color: '#60A5FA',
    },
    {
      icon: Monitor,
      badge: 'COMING Q3',
      badgeColor: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/20',
      title: 'Trading Terminal Mini App',
      desc: 'Monitor positions, track PnL, and manage auto-trades from Telegram. Connected to Binance, Bybit, OKX — powered by our intelligence signals.',
      stats: [
        { label: 'Exchanges', value: 'Binance, Bybit, OKX' },
        { label: 'Auto-execution', value: 'Signal-based' },
        { label: 'Risk Management', value: 'Built-in' },
      ],
      color: '#06B6D4',
    },
    {
      icon: Smartphone,
      badge: 'ROADMAP',
      badgeColor: 'bg-purple-500/15 text-purple-400 border-purple-500/20',
      title: 'iOS & Android App',
      desc: 'Full Prediction OS in your pocket. Extended intelligence, trading, signals, and portfolio management — native mobile experience.',
      stats: [
        { label: 'Platforms', value: 'iOS + Android' },
        { label: 'Features', value: 'Full Terminal' },
        { label: 'Push Alerts', value: 'Real-time' },
      ],
      color: '#A78BFA',
    },
  ];

  return (
    <section className="bg-[#0A0A0A] border-y border-white/[0.06] px-6 sm:px-12 lg:px-16 py-24" data-testid="product-ecosystem-section">
      <div className="max-w-6xl mx-auto">
        <Anim>
          <p className="text-[11px] uppercase tracking-[0.3em] text-[#D4AF37]/70 mb-3 font-medium">Product Ecosystem</p>
          <h2 className="text-3xl sm:text-4xl font-medium tracking-tight text-white mb-3">
            One brain. <span className="text-[#D4AF37]">Four surfaces.</span>
          </h2>
          <p className="text-[15px] text-zinc-400 max-w-xl leading-relaxed mb-14">
            The same 10-layer intelligence engine powers every product.
            Web, Telegram, mobile — choose your interface, get the same edge.
          </p>
        </Anim>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {products.map((p, i) => (
            <Anim key={p.title} delay={i}>
              <div className="h-full p-6 bg-white/[0.02] border border-white/[0.06] rounded-xl hover:border-white/[0.12] transition-all duration-300 group">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-lg flex items-center justify-center"
                    style={{ backgroundColor: p.color + '12', border: `1px solid ${p.color}25` }}>
                    <p.icon className="w-5 h-5" style={{ color: p.color }} strokeWidth={1.5} />
                  </div>
                  <div>
                    <h3 className="text-base font-medium text-white tracking-tight">{p.title}</h3>
                  </div>
                  <span className={`ml-auto px-2.5 py-1 text-[9px] uppercase tracking-[0.15em] font-mono border rounded-full ${p.badgeColor}`}>
                    {p.badge}
                  </span>
                </div>
                <p className="text-[13px] text-zinc-400 leading-relaxed mb-5">{p.desc}</p>
                <div className="flex flex-wrap gap-x-6 gap-y-2 pt-4 border-t border-white/[0.06]">
                  {p.stats.map(s => (
                    <div key={s.label}>
                      <p className="text-sm font-medium text-white">{s.value}</p>
                      <p className="text-[9px] uppercase tracking-[0.15em] text-zinc-500 font-medium">{s.label}</p>
                    </div>
                  ))}
                </div>
              </div>
            </Anim>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════
   ARCHITECTURE — How the System Decides
   ═══════════════════════════════════════════════ */
function ArchitectureSection() {
  return (
    <section className="bg-[#0A0A0A] relative overflow-hidden py-24 px-6 sm:px-12 lg:px-16" data-testid="architecture-section">
      <div className="max-w-6xl mx-auto relative z-10">
        <Anim>
          <p className="text-[11px] uppercase tracking-[0.3em] text-[#D4AF37]/70 mb-3 font-medium">Core Architecture</p>
          <h2 className="text-3xl sm:text-4xl font-medium tracking-tight text-white mb-6">
            How the system<br /><span className="text-[#D4AF37]">makes decisions</span>
          </h2>
          <p className="text-[15px] text-zinc-400 max-w-lg leading-relaxed mb-14">
            Every signal passes through a multi-layer validation pipeline.
            No single indicator. No gut feelings. <span className="text-white font-medium">Pure systematic edge.</span>
          </p>
        </Anim>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { n: '01', title: 'Ingest', desc: '40+ exchange metrics, on-chain transactions, social feeds, prediction market odds — ingested in real time.', icon: Radio },
            { n: '02', title: 'Analyze', desc: 'Each intelligence layer processes independently. Fractal patterns, sentiment shifts, whale movements, ML scoring.', icon: Brain },
            { n: '03', title: 'Synthesize', desc: 'Meta Brain aggregates all layers. Cross-validates signals. Calculates unified confidence with regime context.', icon: Cpu },
            { n: '04', title: 'Deliver', desc: 'High-confidence signals via Telegram. Position sizing, entry/exit targets, and risk parameters included.', icon: Zap },
          ].map((step, i) => (
            <Anim key={step.n} delay={i}>
              <div className="p-6 h-full bg-white/[0.02] border border-white/[0.06] rounded-xl hover:border-[#D4AF37]/20 transition-all duration-300"
                data-testid={`step-${step.n}`}>
                <span className="text-3xl font-extralight text-white/[0.06] block mb-3 leading-none">{step.n}</span>
                <step.icon className="w-4 h-4 text-[#D4AF37]/50 mb-3" strokeWidth={1.5} />
                <h3 className="text-base font-medium text-white mb-2 tracking-tight">{step.title}</h3>
                <p className="text-[13px] text-zinc-500 leading-relaxed">{step.desc}</p>
              </div>
            </Anim>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════
   PRO TEASER
   ═══════════════════════════════════════════════ */
function PricingTeaser({ login }) {
  return (
    <section className="px-6 sm:px-12 lg:px-16 py-24 bg-[#111111]" data-testid="pricing-section">
      <div className="max-w-2xl mx-auto">
        <Anim>
          <div className="border border-[#D4AF37]/20 bg-[#0D0D0D] rounded-2xl p-10 sm:p-14 text-center relative overflow-hidden">
            <div className="absolute top-0 left-0 w-10 h-px bg-[#D4AF37]/40" />
            <div className="absolute top-0 left-0 w-px h-10 bg-[#D4AF37]/40" />
            <div className="absolute bottom-0 right-0 w-10 h-px bg-[#D4AF37]/40" />
            <div className="absolute bottom-0 right-0 w-px h-10 bg-[#D4AF37]/40" />

            <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-[#D4AF37]/10 text-[#D4AF37] text-[10px] uppercase tracking-[0.2em] border border-[#D4AF37]/20 rounded-full mb-6 font-medium">
              <Star className="w-3 h-3" /> PRO
            </div>

            <h2 className="text-3xl sm:text-4xl font-medium tracking-tight text-white mb-4">
              Unlock the full terminal
            </h2>
            <p className="text-[15px] text-zinc-400 leading-relaxed mb-8 max-w-md mx-auto">
              Priority Telegram alerts, ML confidence scores, position sizing,
              cross-market arbitrage scanner, auto-trading terminal, and all 10 intelligence layers unlocked.
            </p>

            <button onClick={login} data-testid="pricing-cta-btn"
              className="inline-flex items-center gap-2 px-8 py-4 bg-[#D4AF37] text-[#0A0A0A] text-[15px] font-semibold tracking-tight rounded-xl hover:bg-[#C5A032] transition-all duration-200 group shadow-lg shadow-[#D4AF37]/20">
              Get Started Free
              <ChevronRight className="w-4 h-4 opacity-60 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all duration-200" />
            </button>
          </div>
        </Anim>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════
   FOOTER — Premium Terminal Style
   ═══════════════════════════════════════════════ */
function Footer({ login }) {
  const [email, setEmail] = useState('');
  const [subscribed, setSubscribed] = useState(false);
  const [footerCfg, setFooterCfg] = useState(null);

  useEffect(() => {
    fetch(`${process.env.REACT_APP_BACKEND_URL}/api/footer/config`)
      .then(r => r.json())
      .then(d => { if (d.ok) setFooterCfg(d); })
      .catch(() => {});
  }, []);

  const social = footerCfg?.social_links || {};

  const handleSubscribe = async (e) => {
    e.preventDefault();
    const trimmed = email.trim();
    if (!trimmed) return;
    try {
      const r = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/newsletter/subscribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: trimmed, source: 'footer' }),
      });
      const d = await r.json();
      if (d.ok) { setSubscribed(true); setEmail(''); }
    } catch {
      setSubscribed(true); setEmail('');
    }
  };

  const moduleLinks = [
    'Fractal Analysis', 'Exchange Intelligence', 'On-chain Intelligence',
    'Sentiment Engine', 'Prediction Markets', 'Telegram Intelligence',
    'Alpha / Meta Brain', 'Technical Analysis AI', 'Smart Alerts', 'Trading Terminal',
  ];

  return (
    <footer className="bg-[#0A0A0A] border-t border-white/[0.06] relative overflow-hidden" data-testid="footer-section">
      <CodeStream className="opacity-30" />

      <div className="relative z-10 w-full px-6 sm:px-10 lg:px-14 py-20">
        {/* Main Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-y-12 gap-x-6">

          {/* Col 1: Brand + Newsletter */}
          <div className="lg:col-span-4" data-testid="footer-brand-column">
            <img src="/assets/logo-white.png" alt="FOMO" className="h-14 w-auto mb-5" data-testid="footer-logo" />
            <p className="text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-500 mb-2">Prediction OS</p>
            <p className="text-sm text-zinc-400 leading-relaxed mb-6 max-w-xs">
              Cross-market crypto intelligence. 10 layers of analysis. One terminal.
            </p>

            {/* Newsletter — single clean input */}
            <p className="text-[10px] font-mono text-zinc-600 uppercase tracking-wider mb-2">// Subscribe to signals</p>
            {!subscribed ? (
              <form onSubmit={handleSubscribe} className="flex items-center gap-0" data-testid="footer-newsletter-form">
                <span className="text-[#D4AF37] text-xs font-mono pr-2 flex-shrink-0 select-none">&gt;_</span>
                <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                  placeholder="your@email.com"
                  data-testid="footer-newsletter-input"
                  className="flex-1 bg-transparent text-sm text-[#D4AF37] font-mono focus:outline-none placeholder:text-zinc-600 min-w-0 py-2 border-b border-white/10 focus:border-[#D4AF37]/50 transition-colors" />
                <button type="submit" data-testid="footer-newsletter-submit"
                  className="ml-3 text-[#D4AF37] text-xs font-mono hover:text-[#D4AF37]/80 transition-colors flex-shrink-0">
                  Send
                </button>
              </form>
            ) : (
              <p className="text-emerald-400 text-xs font-mono py-2">&gt; Subscribed. Signals incoming.</p>
            )}
          </div>

          {/* Cols 2+3: Modules + Platform — side by side on mobile */}
          <div className="lg:col-span-5 grid grid-cols-2 gap-x-6">
            <div data-testid="footer-modules-column">
              <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500 mb-5">Modules</p>
              <nav className="space-y-0.5">
                {moduleLinks.map(m => (
                  <a key={m} href="#" data-testid={`footer-link-${m.toLowerCase().replace(/[\s\/]/g, '-')}`}
                    className="text-[13px] text-zinc-400 hover:text-zinc-100 hover:translate-x-1 transition-all duration-200 block py-1 w-fit">
                    {m}
                  </a>
                ))}
              </nav>
            </div>

            <div data-testid="footer-platform-column">
              <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500 mb-5">Platform</p>
              <nav className="space-y-0.5">
                {[
                  { label: 'Dashboard', href: '/' },
                  { label: 'Settings', href: '/settings' },
                  { label: 'Billing', href: '/settings?tab=billing' },
                  { label: 'Sign In', href: '#', onClick: login },
                ].map(l => (
                  <a key={l.label} href={l.href}
                    onClick={l.onClick ? (e) => { e.preventDefault(); l.onClick(); } : undefined}
                    data-testid={`footer-link-${l.label.toLowerCase().replace(/\s/g, '-')}`}
                    className="text-[13px] text-zinc-400 hover:text-zinc-100 hover:translate-x-1 transition-all duration-200 block py-1 w-fit">
                    {l.label}
                  </a>
                ))}
              </nav>
            </div>
          </div>

          {/* Col 4: Connect */}
          <div className="lg:col-span-3" data-testid="footer-connect-column">
            <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500 mb-5">Connect</p>
            <nav className="space-y-1.5">
              {[
                { label: 'X / Twitter', icon: 'X', url: social.twitter },
                { label: 'Discord', icon: 'D', url: social.discord },
                { label: 'Telegram', icon: 'T', url: social.telegram },
              ].map(l => (
                <a key={l.label}
                  href={l.url || '#'}
                  target={l.url ? '_blank' : undefined}
                  rel={l.url ? 'noopener noreferrer' : undefined}
                  data-testid={`footer-link-${l.label.toLowerCase().replace(/[\s\/]/g, '-')}`}
                  className="flex items-center gap-3 text-[13px] text-zinc-400 hover:text-zinc-100 transition-all duration-200 py-1 w-fit group">
                  <span className="w-7 h-7 rounded-lg bg-white/[0.04] border border-white/[0.06] flex items-center justify-center text-[10px] font-mono text-zinc-500 group-hover:text-white group-hover:border-white/10 transition-all">
                    {l.icon}
                  </span>
                  {l.label}
                </a>
              ))}
            </nav>

            <div className="mt-8 pt-5 border-t border-white/[0.06]">
              <p className="text-[10px] font-mono text-zinc-600 uppercase tracking-wider mb-2">// Built for</p>
              <p className="text-sm text-zinc-400 italic leading-relaxed">
                Traders who think in<br />probabilities, not predictions.
              </p>
            </div>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="mt-16 pt-6 border-t border-white/[0.06] flex flex-col md:flex-row justify-between items-center gap-4" data-testid="footer-bottom-bar">
          <p className="text-xs font-mono text-zinc-600">
            &copy; {new Date().getFullYear()} FOMO Intelligence. Let's Predict.
          </p>
          <div className="flex items-center gap-6 text-xs font-mono text-zinc-500">
            <a href="/legal/terms" className="hover:text-zinc-300 transition-colors" data-testid="footer-link-terms">Terms</a>
            <a href="/legal/privacy" className="hover:text-zinc-300 transition-colors" data-testid="footer-link-privacy">Privacy</a>
          </div>
          <div className="flex items-center gap-2 text-xs font-mono text-zinc-500" data-testid="footer-system-status">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
            </span>
            Systems Operational
          </div>
        </div>
      </div>
    </footer>
  );
}

/* ═══════════════════════════════════════════════
   LANDING PAGE — Main Export
   ═══════════════════════════════════════════════ */
export default function LandingPage() {
  const { login } = useAuth();

  return (
    <div className="min-h-screen bg-[#0A0A0A]" data-testid="landing-page" style={{ fontFamily: "'Gilroy', sans-serif" }}>
      {/* Hero — white left, dark right */}
      <section className="grid grid-cols-1 lg:grid-cols-2 min-h-screen" data-testid="hero-section">
        <div className="bg-white">
          <HeroLeft login={login} />
        </div>
        <HeroRight />
      </section>

      {/* Product Ecosystem */}
      <ProductEcosystem />

      {/* Interactive Intelligence Terminal */}
      <IntelligenceTerminal />

      {/* Architecture Pipeline */}
      <ArchitectureSection />

      {/* PRO */}
      <PricingTeaser login={login} />

      {/* Footer */}
      <Footer login={login} />
    </div>
  );
}
