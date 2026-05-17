/**
 * Public Referral Landing Page — /ref/:code
 * 
 * Influencer shares this URL. The visitor sees the discount info,
 * the code is stored in localStorage, and on sign-up it auto-applies.
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Gift, ArrowRight, Check, Star, Loader2, Shield, Zap, Brain, BarChart3 } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

export default function ReferralLandingPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, login } = useAuth();
  const [promoData, setPromoData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [invalid, setInvalid] = useState(false);
  const [applied, setApplied] = useState(false);

  // Validate code on mount
  useEffect(() => {
    if (!code) { setInvalid(true); setLoading(false); return; }

    fetch(`${API}/api/billing/validate-promo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: code.toUpperCase() }),
    })
      .then(r => r.ok ? r.json() : { ok: false })
      .then(data => {
        if (data.ok) {
          setPromoData(data);
          localStorage.setItem('referral_code', code.toUpperCase());
        } else {
          setInvalid(true);
        }
      })
      .catch(() => setInvalid(true))
      .finally(() => setLoading(false));
  }, [code]);

  // If authenticated, auto-apply the referral
  useEffect(() => {
    if (!isAuthenticated || !promoData || applied) return;

    fetch(`${API}/api/billing/apply-referral`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: code.toUpperCase() }),
    })
      .then(r => r.ok ? r.json() : { ok: false })
      .then(data => {
        if (data.ok) {
          setApplied(true);
          localStorage.removeItem('referral_code');
          setTimeout(() => navigate('/settings?tab=billing'), 2000);
        }
      })
      .catch(console.error);
  }, [isAuthenticated, promoData, applied, code, navigate]);

  const handleSignUp = () => {
    localStorage.setItem('referral_code', code.toUpperCase());
    login();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center" style={{ fontFamily: "'Gilroy', sans-serif" }}>
        <Loader2 className="w-8 h-8 animate-spin text-[#D4AF37]" />
      </div>
    );
  }

  if (invalid) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center" style={{ fontFamily: "'Gilroy', sans-serif" }}>
        <div className="text-center">
          <div className="w-16 h-16 rounded-2xl bg-red-500/10 flex items-center justify-center mx-auto mb-4">
            <Shield className="w-8 h-8 text-red-400" />
          </div>
          <h1 className="text-xl font-semibold text-white mb-2">Invalid Referral Code</h1>
          <p className="text-sm text-zinc-500 mb-6">This referral link is invalid or has expired.</p>
          <button onClick={() => navigate('/info')}
            className="px-6 py-2.5 bg-white/10 text-white rounded-lg text-sm font-medium hover:bg-white/15 transition-colors">
            Go to Homepage
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center px-4" style={{ fontFamily: "'Gilroy', sans-serif" }}
      data-testid="referral-landing-page">

      {/* Background glow */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-[#D4AF37]/[0.03] rounded-full blur-[150px]" />
      </div>

      <div className="relative z-10 w-full max-w-lg">
        {/* Card */}
        <div className="rounded-2xl border border-white/[0.08] overflow-hidden" style={{ background: 'rgba(255,255,255,0.02)' }}>

          {/* Header */}
          <div className="px-8 pt-8 pb-6 text-center border-b border-white/[0.06]">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full mb-4"
              style={{ background: 'rgba(212,175,55,0.08)', border: '1px solid rgba(212,175,55,0.15)' }}>
              <Gift className="w-3.5 h-3.5 text-[#D4AF37]" />
              <span className="text-[10px] font-semibold tracking-[0.2em] text-[#D4AF37] uppercase">Referral Invite</span>
            </div>

            <h1 className="text-2xl font-semibold text-white mb-2">
              You've been invited
            </h1>
            <p className="text-sm text-zinc-500">
              {promoData.group_name && `from ${promoData.group_name} program`}
            </p>
          </div>

          {/* Discount display */}
          <div className="px-8 py-6 text-center border-b border-white/[0.06]">
            <div className="inline-flex items-baseline gap-1">
              <span className="text-5xl font-bold text-[#D4AF37]">{promoData.discount_percent}%</span>
              <span className="text-lg text-zinc-500">off</span>
            </div>
            <p className="text-xs text-zinc-600 mt-2">on your FOMO Intelligence PRO subscription</p>

            {/* Referral code display */}
            <div className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
              <span className="text-[10px] text-zinc-600 uppercase tracking-wider">Code:</span>
              <span className="font-mono text-sm font-bold text-white tracking-wider" data-testid="referral-code-display">{code.toUpperCase()}</span>
              <Check className="w-3.5 h-3.5 text-emerald-400" />
            </div>
          </div>

          {/* Features preview */}
          <div className="px-8 py-5 border-b border-white/[0.06]">
            <div className="grid grid-cols-2 gap-3">
              {[
                { icon: BarChart3, label: '40+ Exchange Indicators' },
                { icon: Brain, label: 'Meta Brain AI Synthesis' },
                { icon: Zap, label: 'Real-time Signal Alerts' },
                { icon: Star, label: 'Cross-Market Intel' },
              ].map((f, i) => (
                <div key={i} className="flex items-center gap-2 text-xs text-zinc-500">
                  <f.icon className="w-3.5 h-3.5 text-[#D4AF37]/50" strokeWidth={1.5} />
                  {f.label}
                </div>
              ))}
            </div>
          </div>

          {/* CTA */}
          <div className="px-8 py-6">
            {applied ? (
              <div className="text-center">
                <div className="inline-flex items-center gap-2 text-emerald-400">
                  <Check className="w-5 h-5" />
                  <span className="text-sm font-medium">Referral applied! Redirecting to checkout...</span>
                </div>
              </div>
            ) : isAuthenticated ? (
              <div className="text-center">
                <Loader2 className="w-5 h-5 animate-spin text-[#D4AF37] mx-auto mb-2" />
                <p className="text-xs text-zinc-500">Applying referral code...</p>
              </div>
            ) : (
              <>
                <button onClick={handleSignUp}
                  data-testid="referral-signup-btn"
                  className="w-full py-3.5 rounded-xl text-sm font-bold transition-all duration-300 hover:brightness-110 active:scale-[0.99] flex items-center justify-center gap-2"
                  style={{
                    background: 'linear-gradient(135deg, #D4AF37 0%, #C5A028 100%)',
                    color: '#0A0A0A',
                    boxShadow: '0 4px 24px rgba(212,175,55,0.2)',
                  }}>
                  Sign up & claim {promoData.discount_percent}% off
                  <ArrowRight className="w-4 h-4" />
                </button>
                <p className="text-[10px] text-zinc-700 text-center mt-3">
                  Free Google sign-in · No credit card required to start
                </p>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
