import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  Star, Zap, Shield, Brain, BarChart3, Radio, Globe2,
  Layers, ChevronRight, Lock, ArrowRight, Tag, Loader2, Check,
  CreditCard, Terminal, Activity, Eye
} from 'lucide-react';
import {
  createCheckout, createCryptoCheckout, getPlans,
} from '../api/billing.api';

const API = process.env.REACT_APP_BACKEND_URL;

/* ── Animated terminal lines in background ── */
function TerminalBg() {
  const lines = [
    '> fractal.analyze --market=BTC --depth=9',
    '  [OK] regime_detection: bull_continuation',
    '  [OK] confidence_score: 0.87',
    '> exchange.scan --pairs=142 --interval=1m',
    '  funding_rate: +0.0023%  oi_delta: +2.4M',
    '> onchain.whale_flow --threshold=100k',
    '  net_flow: -4,200 BTC (exchange_outflow)',
    '> sentinel.check --layer=safety',
    '  [PASS] position_sizing: conservative',
    '  [PASS] drawdown_limit: within_bounds',
    '> meta_brain.synthesize --layers=all',
    '  cross_correlation: 0.92  signal: LONG',
    '> alert.dispatch --channel=telegram',
    '  [SENT] signal_id: SIG-2026-0401-07',
    '> prediction.backtest --window=30d',
    '  win_rate: 68.4%  sharpe: 2.1',
  ];

  return (
    <div className="absolute inset-0 overflow-hidden opacity-[0.04] pointer-events-none select-none" aria-hidden="true">
      <div className="font-mono text-[11px] leading-[1.8] text-white whitespace-pre p-8">
        {lines.map((l, i) => (
          <div key={i} style={{ animationDelay: `${i * 0.15}s` }}
            className="animate-fadeInTerminal">{l}</div>
        ))}
      </div>
    </div>
  );
}

/* ── Glow orb decorative element ── */
function GlowOrb({ className }) {
  return (
    <div className={`absolute rounded-full blur-[120px] pointer-events-none ${className}`} />
  );
}

export default function PaywallOverlay() {
  const { user, isPro, isAuthenticated } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const [plans, setPlans] = useState(null);
  const [interval, setInterval_] = useState('month');
  const [promoCode, setPromoCode] = useState('');
  const [promoStatus, setPromoStatus] = useState(null);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [cryptoLoading, setCryptoLoading] = useState(false);
  const [freeAccess, setFreeAccess] = useState(false);
  const [paywallEnabled, setPaywallEnabled] = useState(true);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    getPlans().then(data => {
      if (data.ok) {
        setPlans(data.plans);
        setFreeAccess(data.plans?.free_access_enabled || data.plans?.billing_mode === 'free_trial');
        setPaywallEnabled(data.plans?.paywall_enabled !== false);
      }
    });
  }, []);

  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 50);
    return () => clearTimeout(t);
  }, []);

  // Don't show if not authenticated, or is PRO, or free access, or paywall disabled, or on settings/admin page
  const isSettingsPage = location.pathname.startsWith('/settings');
  const isAdminPage = location.pathname.startsWith('/admin');
  if (!isAuthenticated || isPro || freeAccess || !paywallEnabled || isSettingsPage || isAdminPage) return null;

  const plan = plans;
  const monthlyPrice = plan?.monthly_price || plan?.monthly?.card_price || 0;
  const yearlyPrice = plan?.yearly_price || plan?.yearly?.card_price || 0;
  const price = interval === 'month' ? monthlyPrice : yearlyPrice;
  const yearlyDiscount = plan?.yearly?.discount_percent || 20;

  const handlePromoValidate = async () => {
    if (!promoCode.trim()) return;
    try {
      const res = await fetch(`${API}/api/billing/validate-promo`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: promoCode }),
      });
      const data = await res.json();
      setPromoStatus(data.ok ? { valid: true, discount: data.discount_percent } : { valid: false });
    } catch { setPromoStatus({ valid: false }); }
  };

  const handleCheckout = async () => {
    setCheckoutLoading(true);
    try {
      const data = await createCheckout(interval, promoStatus?.valid ? promoCode : '');
      if (data.url) window.location.href = data.url;
    } catch (e) { console.error(e); }
    finally { setCheckoutLoading(false); }
  };

  const handleCryptoCheckout = async () => {
    setCryptoLoading(true);
    try {
      const data = await createCryptoCheckout(interval);
      if (data.url) window.location.href = data.url;
    } catch (e) { console.error(e); }
    finally { setCryptoLoading(false); }
  };

  // Discounted price
  const discountedPrice = promoStatus?.valid
    ? (price * (1 - promoStatus.discount / 100))
    : price;

  const features = [
    { icon: Layers, label: '9 Intelligence Layers', desc: 'Full access to every analytical module' },
    { icon: BarChart3, label: '40+ Exchange Indicators', desc: 'Real-time data from major exchanges' },
    { icon: Brain, label: 'Meta Brain Synthesis', desc: 'AI cross-layer signal correlation' },
    { icon: Globe2, label: 'Cross-Market Intel', desc: 'Polymarket + Kalshi arbitrage' },
    { icon: Radio, label: 'Telegram Alerts', desc: 'Instant signal delivery to your phone' },
    { icon: Shield, label: 'ML Safety Layer', desc: 'Position sizing & drawdown protection' },
  ];

  return (
    <div className="fixed inset-0 z-[100]" data-testid="paywall-overlay">
      {/* Dark blur backdrop */}
      <div className="absolute inset-0 backdrop-blur-xl bg-black/75" />

      {/* Overlay content with scroll */}
      <div
        className={`absolute inset-0 overflow-y-auto transition-all duration-700 ${
          mounted ? 'opacity-100' : 'opacity-0'
        }`}
        style={{ fontFamily: "'Gilroy', sans-serif" }}
      >
        <div className="min-h-full flex items-center justify-center px-4 py-10">
          <div
            className={`w-full max-w-[960px] transition-all duration-700 ${
              mounted ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'
            }`}
            data-testid="paywall-card"
          >
            {/* ═══ Main Card ═══ */}
            <div className="relative rounded-2xl overflow-hidden border border-white/[0.08] shadow-2xl shadow-black/50"
              style={{ background: '#0A0A0A' }}>

              {/* Background effects */}
              <TerminalBg />
              <GlowOrb className="w-[500px] h-[500px] -top-40 -right-40 bg-[#D4AF37]/[0.04]" />
              <GlowOrb className="w-[300px] h-[300px] -bottom-20 -left-20 bg-[#D4AF37]/[0.03]" />

              {/* ── Top Header ── */}
              <div className="relative z-10 px-8 sm:px-10 pt-8 pb-6 border-b border-white/[0.06]">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <img src="/assets/logo-white.png" alt="FOMO" className="h-7 w-auto" />
                    <div className="h-5 w-px bg-white/10" />
                    <span className="text-[10px] font-mono uppercase tracking-[0.25em] text-zinc-500">
                      Intelligence Terminal
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 px-3 py-1 rounded-full"
                    style={{ background: 'rgba(212,175,55,0.08)', border: '1px solid rgba(212,175,55,0.15)' }}>
                    <Star className="w-3 h-3 text-[#D4AF37]" />
                    <span className="text-[10px] font-semibold tracking-[0.2em] text-[#D4AF37] uppercase">Pro</span>
                  </div>
                </div>

                <div className="mt-6">
                  <h1 className="text-2xl sm:text-3xl font-semibold text-white tracking-tight leading-tight">
                    Unlock the full terminal
                  </h1>
                  <p className="text-sm text-zinc-500 mt-2">
                    Signed in as <span className="text-zinc-300">{user?.email}</span>
                    <span className="mx-2 text-zinc-700">|</span>
                    <span className="text-zinc-600">Free tier</span>
                  </p>
                </div>
              </div>

              {/* ── Two Column Layout ── */}
              <div className="relative z-10 grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-white/[0.06]">

                {/* ── Left: What You Get ── */}
                <div className="p-8 sm:p-10">
                  <p className="text-[10px] font-mono uppercase tracking-[0.25em] text-[#D4AF37]/60 mb-6">
                    What you get
                  </p>

                  <div className="space-y-4">
                    {features.map((f, i) => (
                      <div key={i} className="flex items-start gap-3.5 group" data-testid={`paywall-feature-${i}`}>
                        <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5 transition-colors duration-300"
                          style={{
                            background: 'rgba(212,175,55,0.06)',
                            border: '1px solid rgba(212,175,55,0.12)'
                          }}>
                          <f.icon className="w-4 h-4 text-[#D4AF37]/60 group-hover:text-[#D4AF37] transition-colors" strokeWidth={1.5} />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-zinc-200 leading-snug">{f.label}</p>
                          <p className="text-xs text-zinc-600 mt-0.5">{f.desc}</p>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Current status box */}
                  <div className="mt-8 p-3.5 rounded-xl" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)' }}>
                    <div className="flex items-center gap-2">
                      <Lock className="w-3.5 h-3.5 text-zinc-600" />
                      <span className="text-xs text-zinc-600">Free tier — dashboards are view-only with limited data</span>
                    </div>
                  </div>
                </div>

                {/* ── Right: Checkout ── */}
                <div className="p-8 sm:p-10">
                  <p className="text-[10px] font-mono uppercase tracking-[0.25em] text-[#D4AF37]/60 mb-6">
                    Select your plan
                  </p>

                  {/* Interval toggle */}
                  <div className="flex gap-2 mb-7">
                    {['month', 'year'].map(int => (
                      <button key={int} onClick={() => setInterval_(int)}
                        data-testid={`paywall-interval-${int}`}
                        className={`flex-1 py-2.5 text-sm rounded-xl font-medium transition-all duration-300 ${
                          interval === int
                            ? 'bg-white/[0.08] text-white border border-white/[0.15] shadow-sm'
                            : 'text-zinc-600 border border-white/[0.04] hover:border-white/[0.08] hover:text-zinc-400'
                        }`}>
                        {int === 'month' ? 'Monthly' : (
                          <span className="flex items-center justify-center gap-1.5">
                            Yearly
                            <span className="text-[10px] font-bold text-emerald-400 bg-emerald-400/10 px-1.5 py-0.5 rounded-full">
                              -{yearlyDiscount}%
                            </span>
                          </span>
                        )}
                      </button>
                    ))}
                  </div>

                  {/* Price display — fixed height to prevent layout jump */}
                  {plan && (
                    <div className="mb-7" data-testid="paywall-price">
                      <div className="flex items-baseline gap-1.5">
                        <span className="text-[42px] font-semibold text-white leading-none tracking-tight">
                          ${promoStatus?.valid ? discountedPrice.toFixed(0) : price}
                        </span>
                        <div className="flex flex-col ml-1">
                          <span className="text-sm text-zinc-500">/{interval === 'month' ? 'mo' : 'yr'}</span>
                        </div>
                      </div>
                      {/* Always reserve one line of subtext to prevent height change */}
                      <p className={`text-[11px] mt-1.5 transition-opacity duration-200 ${
                        promoStatus?.valid ? 'text-emerald-400 flex items-center gap-1 opacity-100'
                        : interval === 'year' ? 'text-zinc-600 opacity-100'
                        : 'text-zinc-600 opacity-0 pointer-events-none'
                      }`}>
                        {promoStatus?.valid ? (
                          <>
                            <Check className="w-3 h-3" />
                            {promoStatus.discount}% discount applied
                            <span className="text-zinc-600 line-through ml-1">${price}</span>
                          </>
                        ) : interval === 'year' ? (
                          <>${(yearlyPrice / 12).toFixed(2)}/mo equivalent</>
                        ) : (
                          /* Invisible placeholder to keep height stable */
                          <>&nbsp;</>
                        )}
                      </p>
                    </div>
                  )}

                  {/* Promo code */}
                  <div className="mb-6">
                    <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-600 mb-2.5">
                      Promo code
                    </p>
                    <div className="flex gap-2">
                      <div className="flex-1 flex items-center rounded-lg overflow-hidden"
                        style={{ border: '1px solid rgba(255,255,255,0.10)', background: 'rgba(255,255,255,0.05)' }}>
                        <Tag className="w-3.5 h-3.5 text-zinc-600 ml-3 flex-shrink-0" />
                        <input type="text" value={promoCode}
                          onChange={e => { setPromoCode(e.target.value.toUpperCase()); setPromoStatus(null); }}
                          placeholder="ENTER CODE"
                          data-testid="paywall-promo-input"
                          className="flex-1 text-sm text-white placeholder:text-zinc-600 font-mono tracking-wider"
                          style={{ background: 'transparent', border: 'none', borderRadius: 0, padding: '10px 10px', outline: 'none', boxShadow: 'none' }} />
                      </div>
                      <button onClick={handlePromoValidate}
                        data-testid="paywall-promo-apply"
                        className="px-4 py-2.5 text-xs font-mono text-zinc-400 rounded-lg transition-all duration-200 hover:text-white hover:bg-white/[0.06]"
                        style={{ border: '1px solid rgba(255,255,255,0.10)', background: 'rgba(255,255,255,0.05)' }}>
                        Apply
                      </button>
                    </div>
                    {promoStatus && !promoStatus.valid && (
                      <p className="text-xs text-red-400/80 mt-2">Invalid or expired code</p>
                    )}
                    {promoStatus?.valid && (
                      <p className="text-xs text-emerald-400 mt-2 flex items-center gap-1">
                        <Check className="w-3 h-3" /> {promoStatus.discount}% discount active
                      </p>
                    )}
                  </div>

                  {/* Primary CTA — Card Payment */}
                  <button onClick={handleCheckout} disabled={checkoutLoading || cryptoLoading}
                    data-testid="paywall-checkout-btn"
                    className="w-full py-3.5 rounded-xl text-sm font-bold transition-all duration-300 hover:brightness-110 active:scale-[0.99] disabled:opacity-50 flex items-center justify-center gap-2"
                    style={{
                      background: 'linear-gradient(135deg, #D4AF37 0%, #C5A028 100%)',
                      color: '#0A0A0A',
                      boxShadow: '0 4px 24px rgba(212,175,55,0.2), 0 1px 3px rgba(212,175,55,0.3)',
                    }}>
                    {checkoutLoading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <>
                        <CreditCard className="w-4 h-4" />
                        Upgrade to PRO — ${promoStatus?.valid ? discountedPrice.toFixed(2) : price}
                      </>
                    )}
                  </button>

                  {/* Secondary CTA — Crypto */}
                  <button onClick={handleCryptoCheckout} disabled={cryptoLoading || checkoutLoading}
                    data-testid="paywall-crypto-btn"
                    className="w-full mt-2.5 py-3 rounded-xl text-sm font-medium transition-all duration-200 flex items-center justify-center gap-2 hover:bg-white/[0.06]"
                    style={{ border: '1px solid rgba(255,255,255,0.06)', color: '#A1A1AA' }}>
                    {cryptoLoading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <>
                        <Zap className="w-4 h-4" />
                        Pay with USDC
                      </>
                    )}
                  </button>

                  {/* Trust badges */}
                  <div className="flex items-center justify-center gap-4 mt-5 text-[10px] text-zinc-700">
                    <span className="flex items-center gap-1">
                      <Lock className="w-3 h-3" /> SSL Encrypted
                    </span>
                    <span className="w-px h-3 bg-zinc-800" />
                    <span className="flex items-center gap-1">
                      <Shield className="w-3 h-3" /> Stripe Secured
                    </span>
                    <span className="w-px h-3 bg-zinc-800" />
                    <span>Cancel anytime</span>
                  </div>

                  {/* Link to billing settings */}
                  <div className="mt-6 pt-5 border-t border-white/[0.04]">
                    <button onClick={() => navigate('/settings?tab=billing')}
                      data-testid="paywall-settings-link"
                      className="w-full text-xs text-zinc-600 hover:text-zinc-400 transition-colors flex items-center justify-center gap-1.5">
                      Manage billing in settings
                      <ChevronRight className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* CSS for terminal animation */}
      <style>{`
        @keyframes fadeInTerminal {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fadeInTerminal {
          animation: fadeInTerminal 0.4s ease-out forwards;
          opacity: 0;
        }
      `}</style>
    </div>
  );
}
