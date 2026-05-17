/**
 * Settings Page — Account, Billing (Unified Checkout Design), Notifications.
 * Billing: single-screen checkout-style with order summary, promo codes, pricing.
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Settings, CreditCard, Bell, Loader2, ExternalLink, Check, Zap, Shield, Star, ArrowRight, Lock, Tag, Camera, User, KeyRound, ShieldCheck, Copy, Eye, EyeOff, Users, Gift, TrendingUp, Award } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import {
  createCheckout, createCryptoCheckout,
  getBillingStatus, openPortal, getPlans,
} from '../api/billing.api';

const API = process.env.REACT_APP_BACKEND_URL;

const TABS = [
  { id: 'account', label: 'Account', icon: Settings },
  { id: 'billing', label: 'Billing', icon: CreditCard },
  { id: 'referrals', label: 'Referrals', icon: Users },
  { id: 'notifications', label: 'Alerts', icon: Bell },
];

const PRO_FEATURES = [
  'Fractal Analysis Engine',
  'Exchange Intelligence (Real-time)',
  'On-chain Data & Analytics',
  'Sentiment Analysis',
  'Prediction Engine (Polymarket Alpha)',
  'Telegram Signal Alerts',
  'Tech Analysis (Coming Soon)',
];

const BG_IMG = 'https://static.prod-images.emergentagent.com/jobs/df7924bb-3513-434f-9ac1-a36539ed9016/images/cd908b9f645ee69f597f94f389a3d897dcd812d2e4fb0fcab448e8ff0511af75.png';

export default function SettingsPage() {
  const { user, isAuthenticated, isPro, login, logout } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get('tab') || 'account';

  // Billing state
  const [billing, setBilling] = useState(null);
  const [billingLoading, setBillingLoading] = useState(false);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [cryptoLoading, setCryptoLoading] = useState(false);

  // Plans
  const [plans, setPlans] = useState(null);
  const [billingCycle, setBillingCycle] = useState('monthly');

  // Promo
  const [promoCode, setPromoCode] = useState('');
  const [promoStatus, setPromoStatus] = useState(null); // {ok, discount_percent, error}
  const [promoLoading, setPromoLoading] = useState(false);

  useEffect(() => {
    if (isAuthenticated && activeTab === 'billing') {
      setBillingLoading(true);
      getBillingStatus().then(setBilling).finally(() => setBillingLoading(false));
    }
  }, [isAuthenticated, activeTab]);

  useEffect(() => {
    let active = true;
    getPlans().then(data => { if (active && data.ok) setPlans(data.plans); });
    return () => { active = false; };
  }, []);

  const handleUpgrade = async () => {
    setCheckoutLoading(true);
    try {
      const interval = billingCycle === 'yearly' ? 'year' : 'month';
      const res = await createCheckout(interval, promoStatus?.ok ? promoCode : '');
      if (res.ok && res.url) window.location.href = res.url;
    } catch (e) { console.error(e); }
    finally { setCheckoutLoading(false); }
  };

  const handleCryptoUpgrade = async () => {
    setCryptoLoading(true);
    try {
      const interval = billingCycle === 'yearly' ? 'year' : 'month';
      const res = await createCryptoCheckout(interval);
      if (res.ok && res.url) window.location.href = res.url;
    } catch (e) { console.error(e); }
    finally { setCryptoLoading(false); }
  };

  const handlePortal = async () => {
    try {
      const res = await openPortal();
      if (res.ok && res.url) window.open(res.url, '_blank');
    } catch (e) { console.error(e); }
  };

  const handleValidatePromo = async () => {
    if (!promoCode.trim()) return;
    setPromoLoading(true);
    try {
      const res = await fetch(`${API}/api/billing/validate-promo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ code: promoCode }),
      });
      const data = await res.json();
      setPromoStatus(data);
    } catch { setPromoStatus({ ok: false, error: 'Network error' }); }
    finally { setPromoLoading(false); }
  };

  // Compute prices
  const monthly = plans?.monthly || { card_price: 1, crypto_price: 1 };
  const yearly = plans?.yearly || { card_price: 10, crypto_price: 10, discount_percent: 15, monthly_equivalent: 0.83 };
  const currentPlan = billingCycle === 'yearly' ? yearly : monthly;
  const freeAccess = plans?.free_access_enabled;
  const billingMode = plans?.billing_mode || 'paid';
  const freeTrialDays = plans?.free_trial_days || 3;
  const isFreeTrial = billingMode === 'free_trial';
  const productName = plans?.product_name || 'FOMO Intelligence PRO';

  // Promo discount
  const promoDiscount = promoStatus?.ok ? promoStatus.discount_percent : 0;
  const basePrice = currentPlan.card_price || 0;
  const discountedPrice = promoDiscount === 100 ? 0 : (basePrice * (1 - promoDiscount / 100));
  const displayPrice = isFreeTrial ? 0 : discountedPrice;
  const savings = monthly && yearly ? ((monthly.card_price * 12) - yearly.card_price) : 0;

  return (
    <div data-testid="settings-page">
      {/* Header */}
      <div className="border-b border-gray-200 bg-white h-[71px]">
        <div className="px-6 h-full flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Settings className="w-5 h-5 text-gray-600" />
            <span className="text-lg font-semibold text-gray-900">Settings</span>
          </div>
          {isAuthenticated && (
            <button onClick={logout} className="text-sm text-red-500 hover:text-red-600 font-medium transition-colors">Sign Out</button>
          )}
        </div>
      </div>

      {/* Tab Nav */}
      <div className="border-b border-gray-200 bg-white">
        <div className="px-6 flex gap-0.5">
          {TABS.map(t => {
            const Icon = t.icon;
            const active = activeTab === t.id;
            return (
              <button key={t.id} onClick={() => setSearchParams({ tab: t.id })}
                data-testid={`settings-${t.id}-tab`}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  active ? 'border-gray-900 text-gray-900' : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}>
                <Icon className="w-4 h-4" /> {t.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Content */}
      <div className="min-h-[calc(100vh-130px)]">
        {/* Account Tab */}
        {activeTab === 'account' && (
          <AccountTab user={user} isAuthenticated={isAuthenticated} isPro={isPro} login={login} freeAccess={freeAccess} />
        )}

        {/* Billing Tab — Unified Checkout Design */}
        {activeTab === 'billing' && (
          <div data-testid="settings-billing-content">
            {!isAuthenticated ? (
              <div className="text-center py-12">
                <p className="text-gray-500 mb-4">Sign in to manage your subscription</p>
                <button onClick={login} className="px-6 py-2.5 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-gray-800 transition-colors">
                  Sign in with Google
                </button>
              </div>
            ) : billingLoading ? (
              <div className="flex justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-gray-400" /></div>
            ) : billing?.subscribed ? (
              /* Active subscription */
              <div className="p-6 max-w-xl">
                <div className="border border-emerald-200 bg-emerald-50 rounded-lg p-6">
                  <div className="flex items-center gap-2 mb-3">
                    <Shield className="w-5 h-5 text-emerald-600" />
                    <span className="font-semibold text-emerald-800">PRO Active</span>
                  </div>
                  <p className="text-sm text-emerald-700 mb-4">Full access to all intelligence modules.</p>
                  <button onClick={handlePortal} data-testid="manage-subscription-btn"
                    className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 transition-colors">
                    <ExternalLink className="w-4 h-4" /> Manage Subscription
                  </button>
                </div>
              </div>
            ) : freeAccess ? (
              /* Free access enabled */
              <div className="p-6 max-w-xl">
                <div className="border border-blue-200 bg-blue-50 rounded-lg p-6">
                  <div className="flex items-center gap-2 mb-3">
                    <Star className="w-5 h-5 text-blue-600" />
                    <span className="font-semibold text-blue-800">Free Access</span>
                  </div>
                  <p className="text-sm text-blue-700">Full access enabled by admin. No payment required.</p>
                </div>
              </div>
            ) : (
              /* ═══ UNIFIED CHECKOUT DESIGN ═══ */
              <div className="relative min-h-[calc(100vh-130px)]" style={{ background: '#030303' }}>
                {/* BG */}
                <div className="absolute inset-0 opacity-20"
                  style={{ backgroundImage: `url(${BG_IMG})`, backgroundSize: 'cover', backgroundPosition: 'center' }} />
                <div className="absolute inset-0"
                  style={{ background: 'radial-gradient(ellipse at 30% 50%, rgba(212,175,55,0.06) 0%, transparent 60%)' }} />

                {/* Top bar */}
                <div className="relative z-10 border-b border-white/5"
                  style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(24px)' }}>
                  <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between">
                    {/* Promo banner */}
                    <div className="flex items-center gap-3">
                      <Star className="w-4 h-4 text-amber-400" />
                      <span className="text-sm text-white/80">
                        {isFreeTrial
                          ? <>Start your <span className="font-bold text-amber-400">{freeTrialDays}-day free trial</span></>
                          : <>Save <span className="font-bold text-amber-400">{yearly.discount_percent || 15}%</span> with annual billing</>
                        }
                      </span>
                      {!isFreeTrial && billingCycle !== 'yearly' && (
                        <button onClick={() => setBillingCycle('yearly')}
                          className="text-xs font-medium text-amber-400 hover:text-amber-300 flex items-center gap-1 transition-colors">
                          Switch to yearly <ArrowRight className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-white/40 text-xs">
                      <Lock className="w-3.5 h-3.5" /><span>Secured by Stripe</span>
                    </div>
                  </div>
                </div>

                {/* Main content */}
                <div className="relative z-10 max-w-5xl mx-auto px-6 py-10">
                  <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">

                    {/* LEFT — Order Summary (3/5) */}
                    <div className="lg:col-span-3">
                      <div className="rounded-2xl overflow-hidden"
                        style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
                        <div className="p-8">
                          <p className="text-[10px] uppercase tracking-[0.2em] text-amber-400/80 mb-3">Order Summary</p>
                          <h1 className="text-2xl font-bold text-white mb-1" style={{ fontFamily: "'Unbounded', sans-serif" }}>
                            {productName}
                          </h1>
                          <p className="text-sm text-white/40 mb-8">
                            {isFreeTrial
                              ? `Free Trial — ${freeTrialDays} Days`
                              : (billingCycle === 'yearly' ? 'Annual Subscription' : 'Monthly Subscription')
                            }
                          </p>

                          {/* Features */}
                          <div className="space-y-3 mb-8">
                            {PRO_FEATURES.map((f, i) => (
                              <div key={i} className="flex items-center gap-3">
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
                                {productName} ({isFreeTrial ? 'Trial' : (billingCycle === 'yearly' ? 'Annual' : 'Monthly')})
                              </span>
                              <span className="text-white">
                                {isFreeTrial ? '$0.00' : `$${basePrice.toFixed(2)}`}
                              </span>
                            </div>

                            {/* Promo discount line */}
                            {promoDiscount > 0 && !isFreeTrial && (
                              <div className="flex items-center justify-between text-sm">
                                <span className="text-emerald-400/80">Promo -{promoDiscount}%</span>
                                <span className="text-emerald-400">
                                  -${(basePrice * promoDiscount / 100).toFixed(2)}
                                </span>
                              </div>
                            )}

                            {/* Yearly savings */}
                            {!isFreeTrial && billingCycle === 'yearly' && (
                              <div className="flex items-center justify-between text-sm">
                                <span className="text-emerald-400/80">Annual savings vs monthly</span>
                                <span className="text-emerald-400">-${savings.toFixed(2)}</span>
                              </div>
                            )}

                            {isFreeTrial && (
                              <div className="flex items-center justify-between text-sm">
                                <span className="text-emerald-400/80">Free trial discount</span>
                                <span className="text-emerald-400">-${monthly.card_price?.toFixed(2)}</span>
                              </div>
                            )}

                            <div className="border-t border-white/8 pt-3 flex items-center justify-between">
                              <span className="text-white font-medium">Total due today</span>
                              <div className="text-right">
                                <span className="text-xl font-bold text-white" style={{ fontFamily: "'Unbounded', sans-serif" }}>
                                  ${displayPrice.toFixed(2)}
                                </span>
                                <span className="text-white/40 text-xs ml-1">USD</span>
                              </div>
                            </div>

                            {isFreeTrial && (
                              <p className="text-[11px] text-amber-400/70">
                                After {freeTrialDays} days: ${monthly.card_price?.toFixed(2)}/mo charged automatically
                              </p>
                            )}

                            {!isFreeTrial && billingCycle === 'yearly' && (
                              <p className="text-[11px] text-white/30">
                                ${yearly.monthly_equivalent?.toFixed(2)}/mo — Save {yearly.discount_percent}% vs monthly
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* RIGHT — Payment (2/5) */}
                    <div className="lg:col-span-2 flex flex-col gap-5">

                      {/* Monthly/Yearly toggle */}
                      {!isFreeTrial && (
                        <div className="rounded-xl p-4"
                          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
                          <p className="text-[10px] uppercase tracking-wider text-white/30 mb-3">Billing Interval</p>
                          <div className="flex rounded-xl p-1" style={{ background: 'rgba(255,255,255,0.08)' }}
                            data-testid="monthly-yearly-toggle">
                            <button onClick={() => setBillingCycle('monthly')}
                              className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                                billingCycle === 'monthly'
                                  ? 'bg-white text-gray-900 shadow-lg'
                                  : 'text-white/60 hover:text-white/80'
                              }`}>Monthly</button>
                            <button onClick={() => setBillingCycle('yearly')}
                              className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2 ${
                                billingCycle === 'yearly'
                                  ? 'bg-white text-gray-900 shadow-lg'
                                  : 'text-white/60 hover:text-white/80'
                              }`}>
                              Yearly
                              <span className="text-[10px] font-bold bg-emerald-500 text-white px-1.5 py-0.5 rounded-full">
                                -{yearly.discount_percent || 15}%
                              </span>
                            </button>
                          </div>
                        </div>
                      )}

                      {/* Promo Code */}
                      {!isFreeTrial && (
                        <div className="rounded-xl p-4"
                          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}
                          data-testid="promo-code-section">
                          <p className="text-[10px] uppercase tracking-wider text-white/30 mb-3">Promo Code</p>
                          <div className="flex gap-2">
                            <input type="text" placeholder="Enter code..." value={promoCode}
                              onChange={e => { setPromoCode(e.target.value.toUpperCase()); setPromoStatus(null); }}
                              data-testid="promo-code-input"
                              className="flex-1 text-sm text-white placeholder-zinc-500 font-mono tracking-wider"
                              style={{ fontFamily: "'Gilroy', sans-serif", background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '8px', padding: '8px 12px', outline: 'none', boxShadow: 'none' }} />
                            <button onClick={handleValidatePromo} disabled={promoLoading || !promoCode.trim()}
                              data-testid="apply-promo-btn"
                              className="px-4 py-2 rounded-lg text-xs font-medium transition-all disabled:opacity-40"
                              style={{ background: 'rgba(212,175,55,0.15)', border: '1px solid rgba(212,175,55,0.25)', color: '#D4AF37' }}>
                              {promoLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Apply'}
                            </button>
                          </div>
                          {promoStatus?.ok && (
                            <p className="text-xs text-emerald-400 mt-2 flex items-center gap-1">
                              <Check className="w-3 h-3" />
                              {promoStatus.discount_percent === 100
                                ? 'Free access unlocked!'
                                : `${promoStatus.discount_percent}% discount applied`
                              }
                              {promoStatus.group_name && <span className="text-white/30">— {promoStatus.group_name}</span>}
                            </p>
                          )}
                          {promoStatus && !promoStatus.ok && (
                            <p className="text-xs text-red-400 mt-2">{promoStatus.error}</p>
                          )}
                        </div>
                      )}

                      {/* Payment Buttons */}
                      <div className="rounded-xl p-6"
                        style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>

                        {isFreeTrial ? (
                          <>
                            <div className="text-center mb-5">
                              <div className="w-12 h-12 rounded-full mx-auto mb-3 flex items-center justify-center"
                                style={{ background: 'rgba(212,175,55,0.15)', border: '1px solid rgba(212,175,55,0.3)' }}>
                                <CreditCard className="w-5 h-5 text-amber-400" />
                              </div>
                              <h2 className="text-base font-semibold text-white mb-1">Start Free Trial</h2>
                              <p className="text-xs text-white/40">Link your card — {freeTrialDays} days free</p>
                            </div>

                            <button onClick={handleUpgrade} disabled={checkoutLoading}
                              data-testid="upgrade-card-button"
                              className="w-full py-3.5 rounded-xl text-sm font-bold transition-all hover:brightness-110 active:scale-[0.98] disabled:opacity-50 flex items-center justify-center gap-2"
                              style={{ background: '#D4AF37', color: '#000' }}>
                              {checkoutLoading
                                ? <><Loader2 className="w-4 h-4 animate-spin" /> Preparing...</>
                                : <><CreditCard className="w-4 h-4" /> Start Free Trial — $0.00</>
                              }
                            </button>
                            <p className="text-[10px] text-white/30 mt-3 text-center">
                              No charge for {freeTrialDays} days. Cancel anytime.
                            </p>
                          </>
                        ) : (
                          <>
                            {/* Card */}
                            <button onClick={handleUpgrade} disabled={checkoutLoading || cryptoLoading}
                              data-testid="upgrade-card-button"
                              className="w-full py-3.5 rounded-xl text-sm font-bold transition-all hover:brightness-110 active:scale-[0.98] disabled:opacity-50 mb-3 flex items-center justify-center gap-2"
                              style={{ background: '#D4AF37', color: '#000' }}>
                              {checkoutLoading
                                ? <><Loader2 className="w-4 h-4 animate-spin" /> Redirecting...</>
                                : <><CreditCard className="w-4 h-4" /> Pay ${displayPrice.toFixed(2)} — Card</>
                              }
                            </button>

                            {/* Crypto */}
                            <button onClick={handleCryptoUpgrade} disabled={cryptoLoading || checkoutLoading}
                              data-testid="pay-crypto-button"
                              className="w-full py-3.5 rounded-xl text-sm font-bold transition-all hover:brightness-110 active:scale-[0.98] disabled:opacity-50 flex items-center justify-center gap-2"
                              style={{ background: 'rgba(39,117,202,0.15)', border: '1px solid rgba(39,117,202,0.4)', color: '#fff' }}>
                              {cryptoLoading
                                ? <><Loader2 className="w-4 h-4 animate-spin" /> Redirecting...</>
                                : <><Zap className="w-4 h-4" /> Pay ${currentPlan.crypto_price?.toFixed(2)} USDC</>
                              }
                            </button>

                            <p className="text-[10px] text-white/30 mt-3 text-center">
                              USDC on Ethereum, Polygon, Solana & more
                            </p>
                          </>
                        )}
                      </div>

                      {/* Trust signals */}
                      <div className="rounded-xl p-4"
                        style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
                        <div className="flex items-center gap-2 mb-2">
                          <Shield className="w-3.5 h-3.5 text-emerald-400" />
                          <span className="text-[10px] font-medium text-white/50">Secure Checkout</span>
                        </div>
                        <div className="space-y-1.5">
                          {['256-bit SSL encryption', 'PCI-DSS Level 1 compliant', 'Cancel anytime from dashboard'].map((t, i) => (
                            <p key={i} className="text-[10px] text-white/30 flex items-center gap-2">
                              <span className="w-1 h-1 rounded-full bg-emerald-400/50" />{t}
                            </p>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Referrals Tab */}
        {activeTab === 'referrals' && (
          <ReferralsTab user={user} isAuthenticated={isAuthenticated} login={login} />
        )}

        {/* Notifications Tab */}
        {activeTab === 'notifications' && (
          <div className="p-6 max-w-xl">
            <div className="border border-gray-200 rounded-lg p-6 text-center">
              <Bell className="w-8 h-8 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500 text-sm">Alert preferences coming soon.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


/* ══════════════════════════════════════════════════════
   Account Tab Component — Avatar, Nickname, 2FA
   ══════════════════════════════════════════════════════ */
function AccountTab({ user, isAuthenticated, isPro, login, freeAccess }) {
  const { refreshUser } = useAuth();
  const fileInputRef = useRef(null);

  // Profile state
  const [profile, setProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [nickname, setNickname] = useState('');
  const [nickSaving, setNickSaving] = useState(false);
  const [nickSuccess, setNickSuccess] = useState(false);

  // Avatar
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [avatarPreview, setAvatarPreview] = useState(null);

  // 2FA
  const [twoFASetup, setTwoFASetup] = useState(null);
  const [twoFACode, setTwoFACode] = useState('');
  const [twoFALoading, setTwoFALoading] = useState(false);
  const [twoFAError, setTwoFAError] = useState('');
  const [showSecret, setShowSecret] = useState(false);
  const [disableCode, setDisableCode] = useState('');
  const [disableLoading, setDisableLoading] = useState(false);
  const [disableError, setDisableError] = useState('');

  useEffect(() => {
    if (isAuthenticated) loadProfile();
  }, [isAuthenticated]);

  const loadProfile = async () => {
    setProfileLoading(true);
    try {
      const res = await fetch(`${API}/api/user/profile`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setProfile(data.profile);
        setNickname(data.profile.nickname || data.profile.name || '');
      }
    } catch (e) { console.error('Profile load error:', e); }
    finally { setProfileLoading(false); }
  };

  const handleNicknameSave = async () => {
    if (!nickname.trim()) return;
    setNickSaving(true);
    setNickSuccess(false);
    try {
      const res = await fetch(`${API}/api/user/profile`, {
        method: 'PUT', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nickname: nickname.trim() }),
      });
      if (res.ok) {
        setNickSuccess(true);
        refreshUser();
        setTimeout(() => setNickSuccess(false), 2000);
      }
    } catch (e) { console.error(e); }
    finally { setNickSaving(false); }
  };

  const handleAvatarUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Preview
    const reader = new FileReader();
    reader.onload = (ev) => setAvatarPreview(ev.target.result);
    reader.readAsDataURL(file);

    setAvatarUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch(`${API}/api/user/avatar`, {
        method: 'POST', credentials: 'include', body: fd,
      });
      if (res.ok) {
        await loadProfile();
        refreshUser();
      }
    } catch (e) { console.error(e); }
    finally { setAvatarUploading(false); }
  };

  const handleSetup2FA = async () => {
    setTwoFALoading(true);
    setTwoFAError('');
    try {
      const res = await fetch(`${API}/api/user/2fa/setup`, {
        method: 'POST', credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        setTwoFASetup(data);
      } else {
        const err = await res.json();
        setTwoFAError(err.detail || 'Setup failed');
      }
    } catch (e) { setTwoFAError('Network error'); }
    finally { setTwoFALoading(false); }
  };

  const handleVerify2FA = async () => {
    if (!twoFACode.trim()) return;
    setTwoFALoading(true);
    setTwoFAError('');
    try {
      const res = await fetch(`${API}/api/user/2fa/verify`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: twoFACode.trim() }),
      });
      if (res.ok) {
        setTwoFASetup(null);
        setTwoFACode('');
        await loadProfile();
      } else {
        const err = await res.json();
        setTwoFAError(err.detail || 'Invalid code');
      }
    } catch (e) { setTwoFAError('Network error'); }
    finally { setTwoFALoading(false); }
  };

  const handleDisable2FA = async () => {
    if (!disableCode.trim()) return;
    setDisableLoading(true);
    setDisableError('');
    try {
      const res = await fetch(`${API}/api/user/2fa/disable`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: disableCode.trim() }),
      });
      if (res.ok) {
        setDisableCode('');
        await loadProfile();
      } else {
        const err = await res.json();
        setDisableError(err.detail || 'Invalid code');
      }
    } catch (e) { setDisableError('Network error'); }
    finally { setDisableLoading(false); }
  };

  if (!isAuthenticated) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 mb-4">Sign in to manage your account</p>
        <button onClick={login} data-testid="settings-login-btn"
          className="px-6 py-2.5 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-gray-800 transition-colors">
          Sign in with Google
        </button>
      </div>
    );
  }

  if (profileLoading && !profile) {
    return <div className="flex justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-gray-400" /></div>;
  }

  const avatarSrc = avatarPreview
    || (profile?.avatar_url ? `${API}${profile.avatar_url}?t=${Date.now()}` : null)
    || profile?.picture
    || null;

  return (
    <div className="p-6 max-w-2xl" data-testid="account-tab-content" style={{ fontFamily: "'Gilroy', sans-serif" }}>
      <div className="space-y-6">

        {/* ── Profile Card ── */}
        <div className="border border-gray-200 rounded-xl p-6" data-testid="profile-card">
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-5">Profile</h3>
          <div className="flex items-start gap-6">
            {/* Avatar */}
            <div className="relative group" data-testid="avatar-section">
              <div className="w-20 h-20 rounded-full overflow-hidden bg-gray-100 flex items-center justify-center ring-2 ring-gray-200">
                {avatarSrc ? (
                  <img src={avatarSrc} alt="" className="w-full h-full object-cover" />
                ) : (
                  <User className="w-8 h-8 text-gray-400" />
                )}
              </div>
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={avatarUploading}
                data-testid="upload-avatar-btn"
                className="absolute -bottom-1 -right-1 w-7 h-7 rounded-full bg-gray-900 text-white flex items-center justify-center hover:bg-gray-700 transition-colors shadow-lg"
              >
                {avatarUploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Camera className="w-3.5 h-3.5" />}
              </button>
              <input ref={fileInputRef} type="file" accept="image/*" onChange={handleAvatarUpload} className="hidden" />
            </div>

            {/* Info */}
            <div className="flex-1 space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5">Display Name</label>
                <div className="flex gap-2">
                  <input type="text" value={nickname} onChange={e => setNickname(e.target.value)}
                    data-testid="nickname-input" maxLength={50}
                    className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-gray-900/10 focus:border-gray-400 transition-all"
                    style={{ fontFamily: "'Gilroy', sans-serif" }}
                    placeholder="Your display name" />
                  <button onClick={handleNicknameSave} disabled={nickSaving || !nickname.trim()}
                    data-testid="save-nickname-btn"
                    className="px-4 py-2 text-sm font-medium rounded-lg transition-all disabled:opacity-40 bg-gray-900 text-white hover:bg-gray-800">
                    {nickSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : nickSuccess ? <Check className="w-4 h-4" /> : 'Save'}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5">Email</label>
                <div className="flex items-center gap-2">
                  <div className="flex-1 px-3 py-2 border border-gray-100 rounded-lg text-sm text-gray-500 bg-gray-50"
                    data-testid="email-display">
                    {profile?.email || user?.email || '—'}
                  </div>
                  <span className="text-[10px] font-medium text-gray-400 bg-gray-100 px-2 py-1 rounded-md whitespace-nowrap">
                    via Google
                  </span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5">Plan</label>
                <div className="flex items-center gap-2" data-testid="plan-display">
                  <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${
                    isPro
                      ? 'bg-amber-50 text-amber-700 ring-1 ring-amber-200'
                      : freeAccess
                        ? 'bg-blue-50 text-blue-700 ring-1 ring-blue-200'
                        : 'bg-gray-100 text-gray-600'
                  }`}>
                    {isPro && <Star className="w-3 h-3" />}
                    {isPro ? 'PRO' : freeAccess ? 'Free Access' : 'Free'}
                  </span>
                </div>
              </div>

              {profile?.created_at && (
                <p className="text-xs text-gray-400">
                  Member since {new Date(profile.created_at).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* ── Two-Factor Authentication ── */}
        <div className="border border-gray-200 rounded-xl p-6" data-testid="2fa-section">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-gray-600" />
              <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Two-Factor Auth (2FA)</h3>
            </div>
            {profile?.totp_enabled && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200"
                data-testid="2fa-enabled-badge">
                <Check className="w-3 h-3" /> Enabled
              </span>
            )}
          </div>

          {!profile?.totp_enabled && !twoFASetup && (
            <div>
              <p className="text-sm text-gray-500 mb-4">
                Add an extra layer of security. Use an authenticator app (Google Authenticator, Authy, etc.) to generate login codes.
              </p>
              <button onClick={handleSetup2FA} disabled={twoFALoading}
                data-testid="enable-2fa-btn"
                className="inline-flex items-center gap-2 px-4 py-2.5 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-gray-800 transition-colors disabled:opacity-50">
                {twoFALoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
                Enable 2FA
              </button>
              {twoFAError && <p className="text-xs text-red-500 mt-2">{twoFAError}</p>}
            </div>
          )}

          {twoFASetup && !profile?.totp_enabled && (
            <div className="space-y-4" data-testid="2fa-setup-form">
              <p className="text-sm text-gray-600">Scan the QR code with your authenticator app, then enter the 6-digit code below.</p>
              <div className="flex flex-col sm:flex-row gap-6">
                <div className="flex-shrink-0">
                  <div className="bg-white border border-gray-100 rounded-xl p-3 shadow-sm inline-block">
                    <img src={twoFASetup.qr_code} alt="2FA QR Code" className="w-40 h-40" data-testid="2fa-qr-code" />
                  </div>
                </div>
                <div className="flex-1 space-y-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">Manual Key</label>
                    <div className="flex items-center gap-2">
                      <code className="flex-1 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs font-mono text-gray-700 break-all" data-testid="2fa-secret-key">
                        {showSecret ? twoFASetup.secret : '••••••••••••••••'}
                      </code>
                      <button onClick={() => setShowSecret(!showSecret)} className="p-1.5 text-gray-400 hover:text-gray-600">
                        {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                      <button onClick={() => { navigator.clipboard.writeText(twoFASetup.secret); }}
                        data-testid="copy-secret-btn" className="p-1.5 text-gray-400 hover:text-gray-600">
                        <Copy className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">Verification Code</label>
                    <div className="flex gap-2">
                      <input type="text" value={twoFACode}
                        onChange={e => { setTwoFACode(e.target.value.replace(/\D/g, '').slice(0, 6)); setTwoFAError(''); }}
                        data-testid="2fa-code-input" placeholder="000000" maxLength={6}
                        className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 text-center font-mono tracking-widest focus:outline-none focus:ring-2 focus:ring-gray-900/10 focus:border-gray-400"
                        style={{ fontFamily: "'Gilroy', monospace", letterSpacing: '0.3em' }} />
                      <button onClick={handleVerify2FA} disabled={twoFALoading || twoFACode.length < 6}
                        data-testid="verify-2fa-btn"
                        className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 transition-colors disabled:opacity-40">
                        {twoFALoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Verify'}
                      </button>
                    </div>
                    {twoFAError && <p className="text-xs text-red-500 mt-1" data-testid="2fa-error">{twoFAError}</p>}
                  </div>
                  <button onClick={() => { setTwoFASetup(null); setTwoFACode(''); setTwoFAError(''); }}
                    className="text-xs text-gray-400 hover:text-gray-600 transition-colors">Cancel</button>
                </div>
              </div>
            </div>
          )}

          {profile?.totp_enabled && (
            <div data-testid="2fa-disable-section">
              <p className="text-sm text-gray-500 mb-4">
                Two-factor authentication is active. Enter your current authenticator code to disable it.
              </p>
              <div className="flex gap-2 max-w-xs">
                <input type="text" value={disableCode}
                  onChange={e => { setDisableCode(e.target.value.replace(/\D/g, '').slice(0, 6)); setDisableError(''); }}
                  data-testid="disable-2fa-code-input" placeholder="000000" maxLength={6}
                  className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 text-center font-mono tracking-widest focus:outline-none focus:ring-2 focus:ring-gray-900/10 focus:border-gray-400" />
                <button onClick={handleDisable2FA} disabled={disableLoading || disableCode.length < 6}
                  data-testid="disable-2fa-btn"
                  className="px-4 py-2 bg-red-50 text-red-600 border border-red-200 rounded-lg text-sm font-medium hover:bg-red-100 transition-colors disabled:opacity-40">
                  {disableLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Disable'}
                </button>
              </div>
              {disableError && <p className="text-xs text-red-500 mt-1" data-testid="disable-2fa-error">{disableError}</p>}
            </div>
          )}
        </div>

        {/* ── Auth Method ── */}
        <div className="border border-gray-200 rounded-xl p-6" data-testid="auth-method-section">
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Authentication</h3>
          <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
            <div className="w-8 h-8 rounded-full bg-white shadow-sm flex items-center justify-center">
              <svg className="w-4 h-4" viewBox="0 0 24 24">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
              </svg>
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-900">Google Account</p>
              <p className="text-xs text-gray-500">{profile?.email || user?.email}</p>
            </div>
            <Lock className="w-4 h-4 text-gray-300" />
          </div>
          <p className="text-xs text-gray-400 mt-3">
            Your account is secured via Google OAuth. Password management is handled by Google.
          </p>
        </div>
      </div>
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════
   REFERRALS TAB — User-facing referral dashboard
   ══════════════════════════════════════════════════════════════ */
function ReferralsTab({ user, isAuthenticated, login }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [copiedCode, setCopiedCode] = useState(null);

  useEffect(() => {
    if (!isAuthenticated) { setLoading(false); return; }
    fetch(`${API}/api/user/referrals`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : { ok: false })
      .then(d => { if (d.ok) setData(d); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [isAuthenticated]);

  const handleCopy = (code) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  if (!isAuthenticated) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 mb-4">Sign in to view your referrals</p>
        <button onClick={login} className="px-6 py-2.5 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-gray-800 transition-colors">
          Sign in with Google
        </button>
      </div>
    );
  }

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-gray-400" /></div>;

  const stats = data?.stats || { total_codes: 0, used_codes: 0, total_conversions: 0, total_earned: 0 };
  const codes = data?.codes || [];
  const conversions = data?.conversions || [];

  if (codes.length === 0) {
    return (
      <div className="px-4 py-12" data-testid="referrals-empty">
        <div className="max-w-md mx-auto text-center">
          <div className="w-16 h-16 bg-gray-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Gift className="w-8 h-8 text-gray-300" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">No referral codes yet</h3>
          <p className="text-sm text-gray-500">
            Referral codes are assigned by the platform admin. Once you receive a code, you can share it with others and earn rewards for each successful subscription.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="px-4 py-6 space-y-6" data-testid="referrals-dashboard">
      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="border border-gray-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Tag className="w-4 h-4 text-indigo-500" />
            <span className="text-xs text-gray-500 uppercase tracking-wider">My Codes</span>
          </div>
          <p className="text-2xl font-bold text-gray-900" data-testid="ref-stat-codes">{stats.total_codes}</p>
        </div>
        <div className="border border-gray-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Users className="w-4 h-4 text-blue-500" />
            <span className="text-xs text-gray-500 uppercase tracking-wider">Used</span>
          </div>
          <p className="text-2xl font-bold text-gray-900" data-testid="ref-stat-used">{stats.used_codes}</p>
        </div>
        <div className="border border-gray-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <TrendingUp className="w-4 h-4 text-emerald-500" />
            <span className="text-xs text-gray-500 uppercase tracking-wider">Conversions</span>
          </div>
          <p className="text-2xl font-bold text-gray-900" data-testid="ref-stat-conversions">{stats.total_conversions}</p>
        </div>
        <div className="border border-gray-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Gift className="w-4 h-4 text-amber-500" />
            <span className="text-xs text-gray-500 uppercase tracking-wider">Earned</span>
          </div>
          <p className="text-2xl font-bold text-gray-900" data-testid="ref-stat-earned">${stats.total_earned.toFixed(2)}</p>
        </div>
      </div>

      {/* My referral codes */}
      <div className="border border-gray-200 rounded-xl overflow-hidden">
        <div className="px-5 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900">My Referral Codes</h3>
          <span className="text-xs text-gray-400">{codes.length} code{codes.length !== 1 && 's'}</span>
        </div>
        <div className="divide-y divide-gray-100">
          {codes.map(c => (
            <div key={c.code} className="px-5 py-3.5 flex items-center justify-between" data-testid={`ref-code-${c.code}`}>
              <div className="flex items-center gap-3">
                <span className={`font-mono text-sm font-semibold ${c.used_by ? 'text-gray-400 line-through' : 'text-gray-900'}`}>
                  {c.code}
                </span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600 font-medium">
                  {c.group_name}
                </span>
                <span className="text-xs text-gray-400">
                  Discount: {c.discount_percent}% · Reward: {c.referral_reward_percent}%
                </span>
              </div>
              <div className="flex items-center gap-2">
                {c.used_by ? (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-red-50 text-red-500 font-medium">Used</span>
                ) : (
                  <>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-600 font-medium">Active</span>
                    <button onClick={() => handleCopy(c.code)}
                      data-testid={`copy-code-${c.code}`}
                      className="p-1.5 text-gray-400 hover:text-gray-700 border border-gray-200 rounded-lg transition-colors">
                      {copiedCode === c.code ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Conversion history */}
      {conversions.length > 0 && (
        <div className="border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-5 py-3 bg-gray-50 border-b border-gray-200">
            <h3 className="text-sm font-semibold text-gray-900">Conversion History</h3>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
                <th className="py-2.5 px-5 font-medium">Referred User</th>
                <th className="py-2.5 px-3 font-medium">Code</th>
                <th className="py-2.5 px-3 font-medium">Payment</th>
                <th className="py-2.5 px-3 font-medium">Your Reward</th>
                <th className="py-2.5 px-3 font-medium">Status</th>
                <th className="py-2.5 px-3 font-medium">Date</th>
              </tr>
            </thead>
            <tbody>
              {conversions.map((c, i) => (
                <tr key={i} className="border-b border-gray-50">
                  <td className="py-2.5 px-5 text-gray-700 text-xs">{c.referred_user_id || '—'}</td>
                  <td className="py-2.5 px-3 font-mono text-xs text-gray-500">{c.code}</td>
                  <td className="py-2.5 px-3">${c.payment_amount || 0}</td>
                  <td className="py-2.5 px-3 text-emerald-600 font-semibold">${(c.reward_amount || 0).toFixed(2)}</td>
                  <td className="py-2.5 px-3">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      c.status === 'paid' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                    }`}>
                      {c.status === 'paid' ? 'PAID' : 'PENDING'}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-xs text-gray-400">{c.created_at ? new Date(c.created_at).toLocaleDateString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
