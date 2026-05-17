import { useState, useEffect, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { createCheckout, createCryptoCheckout, getPlans } from '../api/billing.api';
import { Check, CreditCard, Zap, ArrowLeft, Shield, Lock, Loader2 } from 'lucide-react';

const BG_IMG = 'https://static.prod-images.emergentagent.com/jobs/df7924bb-3513-434f-9ac1-a36539ed9016/images/cd908b9f645ee69f597f94f389a3d897dcd812d2e4fb0fcab448e8ff0511af75.png';

const PRO_FEATURES = [
  'Fractal Analysis Engine',
  'Exchange Intelligence (Real-time)',
  'On-chain Data & Analytics',
  'Sentiment Analysis',
  'Prediction Engine (Polymarket Alpha)',
  'Telegram Signal Alerts',
  'Tech Analysis (Coming Soon)',
];

export default function CheckoutPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const method = params.get('method') || 'card';
  const interval = params.get('interval') || 'month';
  const [plans, setPlans] = useState(null);
  const [loading, setLoading] = useState(false);
  const [redirecting, setRedirecting] = useState(false);
  const [countdown, setCountdown] = useState(null);
  const hasStarted = useRef(false);

  useEffect(() => {
    getPlans().then(d => { if (d.ok) setPlans(d.plans); });
  }, []);

  const currentPlan = plans ? (interval === 'year' ? plans.yearly : plans.monthly) : null;
  const monthly = plans?.monthly;
  const yearly = plans?.yearly;
  const billingMode = plans?.billing_mode || 'paid';
  const freeTrialDays = plans?.free_trial_days || 3;
  const isFreeTrial = billingMode === 'free_trial';

  const handleCheckout = async () => {
    if (hasStarted.current) return;
    hasStarted.current = true;
    setLoading(true);

    try {
      const origin = window.location.origin;
      let data;
      if (method === 'crypto') {
        data = await createCryptoCheckout(origin, interval);
      } else {
        data = await createCheckout(origin, interval);
      }
      if (data?.ok && data?.url) {
        setRedirecting(true);
        setCountdown(3);
        // Countdown then redirect
        let c = 3;
        const timer = setInterval(() => {
          c--;
          setCountdown(c);
          if (c <= 0) {
            clearInterval(timer);
            window.location.href = data.url;
          }
        }, 700);
      }
    } catch (e) {
      console.error('Checkout error:', e);
      hasStarted.current = false;
    } finally {
      if (!redirecting) setLoading(false);
    }
  };

  if (!user) {
    navigate('/settings?tab=billing');
    return null;
  }

  const price = currentPlan?.card_price?.toFixed(2) || '0.00';
  const cryptoPrice = currentPlan?.crypto_price?.toFixed(2) || '0.00';
  const displayPrice = isFreeTrial ? '0.00' : (method === 'crypto' ? cryptoPrice : price);
  const productName = plans?.product_name || 'FOMO Intelligence PRO';
  const savings = monthly && yearly ? ((monthly.card_price * 12) - yearly.card_price).toFixed(2) : '0';

  return (
    <div className="min-h-screen relative" style={{ background: '#030303' }}>
      {/* Background */}
      <div className="absolute inset-0 opacity-20"
        style={{ backgroundImage: `url(${BG_IMG})`, backgroundSize: 'cover', backgroundPosition: 'center' }} />
      <div className="absolute inset-0" style={{ background: 'radial-gradient(ellipse at 30% 50%, rgba(212,175,55,0.06) 0%, transparent 60%)' }} />

      {/* Top bar */}
      <div className="relative z-10 border-b border-white/5" style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(24px)' }}>
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <button onClick={() => navigate('/settings?tab=billing')} data-testid="checkout-back-btn"
            className="flex items-center gap-2 text-white/50 hover:text-white transition-colors text-sm">
            <ArrowLeft className="w-4 h-4" /> Back to Plans
          </button>
          <div className="flex items-center gap-2 text-white/40 text-xs">
            <Lock className="w-3.5 h-3.5" />
            <span>Secured by Stripe</span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="relative z-10 max-w-4xl mx-auto px-6 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">

          {/* Left — Order Summary (3/5) */}
          <div className="lg:col-span-3">
            <div className="rounded-2xl overflow-hidden" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
              <div className="p-8">
                <p className="text-[10px] uppercase tracking-[0.2em] text-amber-400/80 mb-3">Order Summary</p>
                <h1 className="text-2xl font-bold text-white mb-1" style={{ fontFamily: "'Unbounded', sans-serif" }}>
                  {productName}
                </h1>
                <p className="text-sm text-white/40 mb-8">
                  {isFreeTrial
                    ? `Free Trial — ${freeTrialDays} Days`
                    : (interval === 'year' ? 'Annual Subscription' : 'Monthly Subscription')
                  }
                </p>

                {/* Features */}
                <div className="space-y-3 mb-8">
                  {PRO_FEATURES.map((f, i) => (
                    <div key={i} className="flex items-center gap-3" style={{ animationDelay: `${i * 80}ms` }}>
                      <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0"
                        style={{ background: 'rgba(212,175,55,0.15)' }}>
                        <Check className="w-3 h-3 text-amber-400" />
                      </div>
                      <span className="text-sm text-white/70">{f}</span>
                    </div>
                  ))}
                </div>

                {/* Pricing breakdown */}
                <div className="border-t border-white/8 pt-6 space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-white/50">
                      {productName} ({isFreeTrial ? `Trial ${freeTrialDays}d` : (interval === 'year' ? 'Annual' : 'Monthly')})
                    </span>
                    <span className="text-white">${displayPrice}</span>
                  </div>
                  {isFreeTrial && (
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-emerald-400/80">Free trial discount</span>
                      <span className="text-emerald-400">-${price}</span>
                    </div>
                  )}
                  {!isFreeTrial && interval === 'year' && (
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-emerald-400/80">Annual savings</span>
                      <span className="text-emerald-400">-${savings}</span>
                    </div>
                  )}
                  <div className="border-t border-white/8 pt-3 flex items-center justify-between">
                    <span className="text-white font-medium">Total due today</span>
                    <div className="text-right">
                      <span className="text-xl font-bold text-white" style={{ fontFamily: "'Unbounded', sans-serif" }}>
                        ${displayPrice}
                      </span>
                      <span className="text-white/40 text-xs ml-1">
                        {method === 'crypto' ? 'USDC' : 'USD'}
                      </span>
                    </div>
                  </div>
                  {isFreeTrial && (
                    <p className="text-[11px] text-amber-400/70">
                      After {freeTrialDays} days: ${price}/mo will be charged automatically
                    </p>
                  )}
                  {!isFreeTrial && interval === 'year' && monthly && (
                    <p className="text-[11px] text-white/30">
                      Equivalent to ${yearly?.monthly_equivalent?.toFixed(2)}/mo — Save {yearly?.discount_percent}% vs monthly
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Right — Payment Action (2/5) */}
          <div className="lg:col-span-2 flex flex-col gap-6">
            <div className="rounded-2xl p-8" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
              <div className="text-center mb-6">
                {method === 'crypto' ? (
                  <div className="w-14 h-14 rounded-full mx-auto mb-4 flex items-center justify-center"
                    style={{ background: 'rgba(39,117,202,0.2)', border: '1px solid rgba(39,117,202,0.4)' }}>
                    <Zap className="w-6 h-6 text-blue-400" />
                  </div>
                ) : (
                  <div className="w-14 h-14 rounded-full mx-auto mb-4 flex items-center justify-center"
                    style={{ background: 'rgba(212,175,55,0.15)', border: '1px solid rgba(212,175,55,0.3)' }}>
                    <CreditCard className="w-6 h-6 text-amber-400" />
                  </div>
                )}
                <h2 className="text-lg font-semibold text-white mb-1">
                  {isFreeTrial ? 'Start Free Trial' : (method === 'crypto' ? 'Crypto Payment' : 'Card Payment')}
                </h2>
                <p className="text-xs text-white/40">
                  {isFreeTrial
                    ? `Link your card — ${freeTrialDays} days free, cancel anytime`
                    : (method === 'crypto'
                      ? 'USDC on Ethereum, Polygon, Solana & more'
                      : 'Visa, Mastercard, Amex & more')}
                </p>
              </div>

              {/* CTA Button */}
              {!redirecting ? (
                <button onClick={handleCheckout} disabled={loading || !plans}
                  data-testid="checkout-pay-btn"
                  className="w-full py-4 rounded-xl text-sm font-bold transition-all hover:brightness-110 active:scale-[0.98] disabled:opacity-50 flex items-center justify-center gap-2"
                  style={method === 'crypto'
                    ? { background: 'rgba(39,117,202,0.3)', border: '1px solid rgba(39,117,202,0.5)', color: '#fff' }
                    : { background: '#D4AF37', color: '#000' }
                  }>
                  {loading ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Preparing...</>
                  ) : isFreeTrial ? (
                    <><CreditCard className="w-4 h-4" /> Start Free Trial — $0.00</>
                  ) : (
                    <>{method === 'crypto' ? <Zap className="w-4 h-4" /> : <CreditCard className="w-4 h-4" />}
                      Pay ${displayPrice} {method === 'crypto' ? 'USDC' : ''}</>
                  )}
                </button>
              ) : (
                <div className="text-center py-4">
                  <Loader2 className="w-8 h-8 animate-spin text-amber-400 mx-auto mb-3" />
                  <p className="text-sm text-white/60">
                    Redirecting to secure payment...
                  </p>
                  <p className="text-2xl font-bold text-white mt-2" style={{ fontFamily: "'Unbounded', sans-serif" }}>
                    {countdown}
                  </p>
                </div>
              )}
            </div>

            {/* Trust signals */}
            <div className="rounded-xl p-5" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
              <div className="flex items-center gap-3 mb-3">
                <Shield className="w-4 h-4 text-emerald-400" />
                <span className="text-xs font-medium text-white/60">Secure Checkout</span>
              </div>
              <ul className="space-y-2">
                <li className="text-[11px] text-white/40 flex items-center gap-2">
                  <div className="w-1 h-1 rounded-full bg-emerald-400/50" />
                  256-bit SSL encryption
                </li>
                <li className="text-[11px] text-white/40 flex items-center gap-2">
                  <div className="w-1 h-1 rounded-full bg-emerald-400/50" />
                  PCI-DSS Level 1 compliant
                </li>
                <li className="text-[11px] text-white/40 flex items-center gap-2">
                  <div className="w-1 h-1 rounded-full bg-emerald-400/50" />
                  Cancel anytime from your dashboard
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
