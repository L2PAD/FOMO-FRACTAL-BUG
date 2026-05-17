import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Star, Users, Tag, Bell, Shield, Copy, Check, ChevronRight, X, Settings } from 'lucide-react';
import { useMiniApp } from '../../../context/MiniAppContext';

export default function ProfileScreen() {
  const { profileData, fetchProfile, billingData, fetchBillingStatus, fetchPlans, telegramUser } = useMiniApp();

  useEffect(() => {
    if (!profileData) fetchProfile();
    fetchBillingStatus();
    fetchPlans();
  }, [profileData, fetchProfile, fetchBillingStatus, fetchPlans]);

  if (!profileData) return <ProfileLoading />;

  return (
    <div data-testid="profile-screen" style={{ flex: 1, overflowY: 'auto', paddingBottom: '80px' }}>
      <UserCard user={profileData.user} billing={billingData} telegramUser={telegramUser} />
      <PlanCard billing={billingData} />
      <PerformanceCard performance={profileData.performance} />
      <FavoritesCard favorites={profileData.favorites} />
      <ReferralCard referral={profileData.referral} />
      <PromoCard promo={profileData.promo} />
      <SettingsCard settings={profileData.settings} />
    </div>
  );
}


function UserCard({ user, billing, telegramUser }) {
  const displayName = telegramUser?.firstName
    ? `${telegramUser.firstName}${telegramUser.lastName ? ' ' + telegramUser.lastName : ''}`
    : (user.name || 'User');
  const displayUsername = telegramUser?.username || user.username || '';
  const photoUrl = telegramUser?.photoUrl || user.photoUrl || '';
  const initial = (displayName || 'U')[0].toUpperCase();
  const isActive = billing?.subscribed || user.planName === 'PRO';
  const planLabel = isActive ? 'PRO' : (billing?.planStatus === 'past_due' ? 'PAST DUE' : 'FREE');
  const planColor = isActive ? '#10b981' : (billing?.planStatus === 'past_due' ? '#f87171' : '#a1a1aa');

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      data-testid="user-card"
      style={{
        margin: '16px', padding: '20px',
        background: 'var(--ma-surface, #18181b)', borderRadius: '20px', border: '1px solid var(--ma-border, #27272a)',
        display: 'flex', alignItems: 'center', gap: '16px',
      }}
    >
      {photoUrl ? (
        <img
          src={photoUrl}
          alt={displayName}
          data-testid="user-avatar"
          style={{
            width: '48px', height: '48px', borderRadius: '14px',
            objectFit: 'cover', flexShrink: 0,
            border: isActive ? '2px solid #10b981' : '2px solid var(--ma-border)',
          }}
          onError={(e) => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'flex'; }}
        />
      ) : null}
      <div style={{
        width: '48px', height: '48px', borderRadius: '14px',
        background: isActive ? 'linear-gradient(135deg, #10b981, #059669)' : 'var(--ma-stat-bg)',
        display: photoUrl ? 'none' : 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '18px', fontWeight: 700, color: 'var(--ma-text, #fafafa)',
        fontFamily: "'JetBrains Mono', monospace", flexShrink: 0,
      }}>
        {initial}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--ma-text, #fafafa)', fontFamily: "'Manrope', sans-serif" }}>
          {displayName}
        </div>
        {displayUsername && (
          <div style={{ fontSize: '12px', color: 'var(--ma-secondary)', marginTop: '2px', fontFamily: "'JetBrains Mono', monospace" }}>
            @{displayUsername}
          </div>
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px' }}>
          <span data-testid="plan-badge" style={{
            fontSize: '10px', fontWeight: 700,
            color: planColor,
            background: `${planColor}15`,
            padding: '2px 8px', borderRadius: '20px',
            fontFamily: "'JetBrains Mono', monospace",
            textTransform: 'uppercase', letterSpacing: '0.1em',
          }}>
            {planLabel}
          </span>
          {user.linkedTelegram && (
            <span style={{ fontSize: '9px', color: 'var(--ma-muted, #52525b)', fontFamily: "'JetBrains Mono', monospace" }}>
              TG
            </span>
          )}
          {user.linkedGoogle && (
            <span style={{ fontSize: '9px', color: 'var(--ma-muted, #52525b)', fontFamily: "'JetBrains Mono', monospace" }}>
              G
            </span>
          )}
        </div>
      </div>
    </motion.div>
  );
}


function PlanCard({ billing }) {
  const { plansData, createCryptoInvoice, checkPaymentStatus, openBillingPortal, trackEvent } = useMiniApp();
  const [loading, setLoading] = useState(false);
  const [polling, setPolling] = useState(false);

  const isSubscribed = billing?.subscribed;
  const planStatus = billing?.planStatus || 'free';
  const sub = billing?.subscription;
  const renewDate = sub?.currentPeriodEnd ? new Date(sub.currentPeriodEnd).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : null;

  const price = plansData?.monthly?.price;

  // Poll for PRO activation after payment
  useEffect(() => {
    if (!polling) return;
    
    let attempts = 0;
    const maxAttempts = 60; // 5 minutes
    
    const interval = setInterval(async () => {
      attempts++;
      const status = await checkPaymentStatus();
      
      if (status.plan === 'PRO') {
        clearInterval(interval);
        setPolling(false);
        
        // ✅ POST-PAYMENT UX: Step 2 - Show "PRO Activated" with VALUE
        if (window.Telegram?.WebApp?.showAlert) {
          window.Telegram.WebApp.showAlert(
            "PRO Activated!\n\nYou now have full access to:\n• Full signal reasoning\n• Real-time market drivers\n• Hidden opportunities (Edge)\n• Deep market intelligence\n\nCheck the Home tab to see unlocked content!"
          );
        } else {
          alert("PRO Activated! Full access unlocked.");
        }
        
        // Reload to show unlocked content
        setTimeout(() => window.location.reload(), 1500);
      }
      
      if (attempts >= maxAttempts) {
        clearInterval(interval);
        setPolling(false);
        alert("Payment is still processing. Access will unlock automatically once confirmed.");
      }
    }, 5000);
    
    return () => clearInterval(interval);
  }, [polling, checkPaymentStatus]);

  const handleUpgradeCrypto = async () => {
    setLoading(true);
    trackEvent('upgrade_crypto_clicked', { source: 'profile_plan_card' });
    
    const result = await createCryptoInvoice();
    setLoading(false);
    
    if (result?.ok && result?.invoice_url) {
      // Open payment page
      if (window.Telegram?.WebApp?.openLink) {
        window.Telegram.WebApp.openLink(result.invoice_url);
      } else {
        window.open(result.invoice_url, '_blank');
      }
      
      // ✅ POST-PAYMENT UX: Step 1 - Show "Processing"
      if (window.Telegram?.WebApp?.showAlert) {
        window.Telegram.WebApp.showAlert(
          "We're unlocking your access. This usually takes 10-30 seconds. Stay in the app - you'll see a notification when ready."
        );
      } else {
        alert("Processing payment... Access will unlock in 10-30 seconds.");
      }
      
      // Start polling
      setPolling(true);
    } else {
      alert("Failed to create payment. Please try again.");
    }
  };

  const handleManage = async () => {
    setLoading(true);
    const result = await openBillingPortal();
    setLoading(false);
    if (result?.success && result?.url) {
      if (window.Telegram?.WebApp?.openLink) {
        window.Telegram.WebApp.openLink(result.url);
      } else {
        window.open(result.url, '_blank');
      }
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.05 }}
      data-testid="plan-card"
      style={{
        margin: '0 16px 12px', padding: '16px',
        background: isSubscribed
          ? 'radial-gradient(ellipse at top left, rgba(16,185,129,0.08), var(--ma-surface) 70%)'
          : 'var(--ma-surface)',
        borderRadius: '16px',
        border: `1px solid ${isSubscribed ? 'rgba(16,185,129,0.2)' : 'var(--ma-border)'}`,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
        <Shield size={14} color={isSubscribed ? '#10b981' : '#a1a1aa'} />
        <span style={{
          fontSize: '10px', fontWeight: 700, letterSpacing: '0.15em',
          color: 'var(--ma-muted, #52525b)', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif",
        }}>
          Plan & Billing
        </span>
      </div>

      {isSubscribed ? (
        // Active subscription
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span style={{
              fontSize: '16px', fontWeight: 700, color: '#10b981',
              fontFamily: "'Oswald', sans-serif", textTransform: 'uppercase', letterSpacing: '0.08em',
            }}>
              PRO Active
            </span>
            {sub?.status === 'trialing' && (
              <span style={{
                fontSize: '9px', fontWeight: 600, color: '#eab308',
                background: 'rgba(234,179,8,0.1)', padding: '2px 6px', borderRadius: '20px',
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                TRIAL
              </span>
            )}
          </div>
          {renewDate && (
            <div style={{ fontSize: '11px', color: 'var(--ma-muted, #52525b)', fontFamily: "'JetBrains Mono', monospace", marginBottom: '12px' }}>
              Renews {renewDate}
            </div>
          )}
          <button
            data-testid="manage-billing-btn"
            onClick={handleManage}
            disabled={loading}
            style={{
              width: '100%', padding: '10px',
              borderRadius: '10px', background: 'var(--ma-stat-bg)',
              border: '1px solid var(--ma-border)', color: 'var(--ma-secondary)',
              fontSize: '12px', fontWeight: 600, fontFamily: "'Manrope', sans-serif",
              cursor: 'pointer',
            }}
          >
            {loading ? 'Opening...' : 'Manage Billing'}
          </button>
        </div>
      ) : planStatus === 'past_due' ? (
        // Past due / payment issue
        <div>
          <div style={{ fontSize: '13px', fontWeight: 600, color: '#f87171', fontFamily: "'Manrope', sans-serif", marginBottom: '8px' }}>
            Payment issue — please update your billing
          </div>
          <button
            data-testid="fix-billing-btn"
            onClick={handleManage}
            disabled={loading}
            style={{
              width: '100%', padding: '10px',
              borderRadius: '10px', background: 'rgba(248,113,113,0.1)',
              border: '1px solid rgba(248,113,113,0.2)', color: '#f87171',
              fontSize: '12px', fontWeight: 700, fontFamily: "'Manrope', sans-serif",
              cursor: 'pointer',
            }}
          >
            {loading ? 'Opening...' : 'Fix Billing'}
          </button>
        </div>
      ) : (
        // Free plan
        <div>
          <div style={{ fontSize: '13px', color: 'var(--ma-secondary, #a1a1aa)', fontFamily: "'Manrope', sans-serif", marginBottom: '4px' }}>
            Unlock full intelligence
          </div>
          <div style={{ fontSize: '11px', color: 'var(--ma-muted, #52525b)', fontFamily: "'Manrope', sans-serif", marginBottom: '12px' }}>
            $19/month — Decision Engine, Edge Alerts, Whale Signals
          </div>
          <button
            data-testid="upgrade-pro-btn"
            onClick={handleUpgradeCrypto}
            disabled={loading || polling}
            style={{
              width: '100%', padding: '12px',
              borderRadius: '12px',
              background: polling ? 'var(--ma-stat-bg)' : 'linear-gradient(135deg, #10b981, #059669)',
              border: 'none', color: 'var(--ma-text, #fafafa)',
              fontSize: '13px', fontWeight: 700, fontFamily: "'Manrope', sans-serif",
              cursor: polling ? 'not-allowed' : 'pointer', textTransform: 'uppercase', letterSpacing: '0.06em',
            }}
          >
            {loading ? 'Opening Payment...' : polling ? 'Waiting for payment...' : 'Pay with Crypto'}
          </button>
        </div>
      )}
    </motion.div>
  );
}



function PerformanceCard({ performance }) {
  if (!performance || performance.totalDecisions === 0) return null;

  const accuracy = Math.round(performance.accuracy * 100);
  const bestAcc = Math.round(performance.bestTypeAccuracy * 100);
  const worstAcc = Math.round(performance.worstTypeAccuracy * 100);
  const coverage = performance.coverage ? Math.round(performance.coverage * 100) : null;
  const dirTotal = performance.directionalTotal || 0;
  const dirCorrect = performance.directionalCorrect || 0;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.1 }}
      data-testid="performance-card"
      style={{
        margin: '0 16px 12px', padding: '16px',
        background: 'var(--ma-surface, #18181b)', borderRadius: '16px', border: '1px solid var(--ma-border, #27272a)',
      }}
    >
      <div style={{
        fontSize: '10px', fontWeight: 700, letterSpacing: '0.15em',
        color: 'var(--ma-muted, #52525b)', textTransform: 'uppercase',
        fontFamily: "'Manrope', sans-serif", marginBottom: '12px',
      }}>
        Your Edge
      </div>

      {/* Directional Accuracy — the hero metric */}
      <div style={{
        padding: '14px', marginBottom: '12px',
        background: accuracy >= 60 ? 'rgba(74,222,128,0.06)' : 'rgba(250,250,250,0.03)',
        borderRadius: '12px',
        border: `1px solid ${accuracy >= 60 ? 'rgba(74,222,128,0.15)' : 'var(--ma-border)'}`,
        textAlign: 'center',
      }}>
        <div style={{ fontSize: '10px', color: 'var(--ma-muted)', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif", marginBottom: '4px' }}>
          Directional Accuracy
        </div>
        <div data-testid="perf-accuracy" style={{
          fontSize: '32px', fontWeight: 700,
          color: accuracy >= 60 ? '#4ade80' : accuracy >= 40 ? '#facc15' : '#f87171',
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          {accuracy}%
        </div>
        <div style={{ fontSize: '10px', color: 'var(--ma-muted, #52525b)', fontFamily: "'JetBrains Mono', monospace", marginTop: '2px' }}>
          {dirCorrect} / {dirTotal} directional calls correct
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', marginBottom: '12px' }}>
        <StatBox label="Total" value={performance.totalDecisions} testId="perf-total" />
        <StatBox label="Evaluated" value={performance.evaluated} testId="perf-evaluated" />
        <StatBox label="Coverage" value={coverage !== null ? `${coverage}%` : '—'} testId="perf-coverage" />
      </div>

      <div style={{ display: 'flex', gap: '8px' }}>
        <TypeBadge label={`Best: ${performance.bestType}`} value={`${bestAcc}%`} color="#4ade80" />
        <TypeBadge label={`Worst: ${performance.worstType}`} value={`${worstAcc}%`} color="#f87171" />
      </div>
    </motion.div>
  );
}

function StatBox({ label, value, color, testId }) {
  return (
    <div data-testid={testId} style={{
      padding: '10px', background: 'var(--ma-stat-bg)', borderRadius: '10px',
    }}>
      <div style={{ fontSize: '10px', color: 'var(--ma-muted)', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif", marginBottom: '2px' }}>
        {label}
      </div>
      <div style={{ fontSize: '18px', fontWeight: 700, color: color || 'var(--ma-text)', fontFamily: "'JetBrains Mono', monospace" }}>
        {value}
      </div>
    </div>
  );
}

function TypeBadge({ label, value, color }) {
  return (
    <div style={{
      flex: 1, padding: '8px 10px', background: `${color}10`,
      borderRadius: '10px', border: `1px solid ${color}20`,
    }}>
      <div style={{ fontSize: '10px', color: 'var(--ma-muted)', fontFamily: "'Manrope', sans-serif", marginBottom: '2px' }}>{label}</div>
      <div style={{ fontSize: '14px', fontWeight: 700, color, fontFamily: "'JetBrains Mono', monospace" }}>{value}</div>
    </div>
  );
}


function FavoritesCard({ favorites }) {
  const { addFavorite, removeFavorite, setSelectedAsset, setActiveTab } = useMiniApp();
  const DECISION_COLORS = { BUY: '#4ade80', SELL: '#f87171', WAIT: '#facc15', AVOID: '#71717a' };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.15 }}
      data-testid="favorites-card"
      style={{
        margin: '0 16px 12px', padding: '14px 16px',
        background: 'var(--ma-surface, #18181b)', borderRadius: '16px', border: '1px solid var(--ma-border, #27272a)',
      }}
    >
      <div style={{
        fontSize: '10px', fontWeight: 700, letterSpacing: '0.15em',
        color: 'var(--ma-muted, #52525b)', textTransform: 'uppercase',
        fontFamily: "'Manrope', sans-serif", marginBottom: '10px',
      }}>
        Favorites
      </div>
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {favorites.map(f => {
          const decColor = DECISION_COLORS[f.decision] || '#52525b';
          return (
            <button
              key={f.asset}
              data-testid={`fav-${f.asset}`}
              onClick={() => { setSelectedAsset(f.asset); setActiveTab('home'); }}
              style={{
                padding: '8px 14px', background: 'var(--ma-stat-bg)', borderRadius: '12px',
                border: '1px solid var(--ma-border)', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '8px',
              }}
            >
              <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--ma-text, #fafafa)', fontFamily: "'JetBrains Mono', monospace" }}>
                {f.asset}
              </span>
              {f.decision && (
                <span style={{ fontSize: '9px', fontWeight: 700, color: decColor, fontFamily: "'JetBrains Mono', monospace", textTransform: 'uppercase' }}>
                  {f.decision}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </motion.div>
  );
}


function ReferralCard({ referral }) {
  const [copied, setCopied] = useState(false);

  const copyLink = () => {
    navigator.clipboard.writeText(referral.inviteLink).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {});
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.2 }}
      data-testid="referral-card"
      style={{
        margin: '0 16px 12px', padding: '14px 16px',
        background: 'var(--ma-surface, #18181b)', borderRadius: '16px', border: '1px solid var(--ma-border, #27272a)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
        <Users size={14} color="var(--ma-secondary)" />
        <span style={{
          fontSize: '10px', fontWeight: 700, letterSpacing: '0.15em',
          color: 'var(--ma-muted, #52525b)', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif",
        }}>
          Referral
        </span>
      </div>

      <div style={{ fontSize: '13px', color: 'var(--ma-secondary)', fontFamily: "'Manrope', sans-serif", marginBottom: '10px' }}>
        {referral.rewardText}
      </div>

      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px',
        padding: '10px 12px', background: 'var(--ma-stat-bg)', borderRadius: '10px',
      }}>
        <span style={{
          flex: 1, fontSize: '11px', color: 'var(--ma-secondary, #a1a1aa)',
          fontFamily: "'JetBrains Mono', monospace",
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {referral.code}
        </span>
        <button
          data-testid="copy-referral"
          onClick={copyLink}
          style={{
            padding: '4px 10px', borderRadius: '8px',
            background: copied ? 'rgba(16,185,129,0.15)' : 'var(--ma-stat-bg)',
            border: 'none', cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: '4px',
          }}
        >
          {copied
            ? <Check size={12} color="#4ade80" />
            : <Copy size={12} color="var(--ma-secondary)" />
          }
          <span style={{ fontSize: '10px', fontWeight: 600, color: copied ? '#4ade80' : 'var(--ma-secondary)', fontFamily: "'Manrope', sans-serif" }}>
            {copied ? 'Copied' : 'Copy'}
          </span>
        </button>
      </div>

      <div style={{ fontSize: '11px', color: 'var(--ma-muted)', fontFamily: "'JetBrains Mono', monospace", marginTop: '6px' }}>
        Invites: {referral.invites} / 3
      </div>
    </motion.div>
  );
}


function PromoCard({ promo }) {
  const { applyPromo } = useMiniApp();
  const [code, setCode] = useState('');
  const [status, setStatus] = useState(null); // { type: 'success'|'error', message }
  const [loading, setLoading] = useState(false);

  const handleApply = async () => {
    if (!code.trim()) return;
    setLoading(true);
    setStatus(null);
    const result = await applyPromo(code.trim());
    setLoading(false);
    if (result?.success || result?.ok) {
      setStatus({ type: 'success', message: result.message || 'Promo applied' });
      setCode('');
    } else {
      setStatus({ type: 'error', message: result?.message || 'Invalid code' });
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.25 }}
      data-testid="promo-card"
      style={{
        margin: '0 16px 12px', padding: '14px 16px',
        background: 'var(--ma-surface, #18181b)', borderRadius: '16px', border: '1px solid var(--ma-border, #27272a)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
        <Tag size={14} color="var(--ma-secondary)" />
        <span style={{
          fontSize: '10px', fontWeight: 700, letterSpacing: '0.15em',
          color: 'var(--ma-muted, #52525b)', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif",
        }}>
          Promo Code
        </span>
      </div>

      {promo.activeCode ? (
        <div style={{
          padding: '10px 12px', background: 'rgba(16,185,129,0.1)',
          borderRadius: '10px', border: '1px solid rgba(16,185,129,0.2)',
        }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: '#4ade80', fontFamily: "'JetBrains Mono', monospace" }}>
            {promo.activeCode}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--ma-muted)', fontFamily: "'Manrope', sans-serif", marginTop: '2px' }}>
            {promo.discountText}
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', gap: '8px' }}>
          <input
            data-testid="promo-input"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Enter code"
            style={{
              flex: 1, padding: '10px 12px',
              background: 'var(--ma-stat-bg)', borderRadius: '10px',
              border: '1px solid var(--ma-border)', color: 'var(--ma-text)',
              fontSize: '12px', fontFamily: "'JetBrains Mono', monospace",
              outline: 'none',
            }}
            onKeyDown={(e) => { if (e.key === 'Enter') handleApply(); }}
          />
          <button
            data-testid="promo-apply"
            onClick={handleApply}
            disabled={loading || !code.trim()}
            style={{
              padding: '10px 16px', borderRadius: '10px',
              background: code.trim() ? 'var(--ma-text)' : 'var(--ma-stat-bg)',
              color: code.trim() ? 'var(--ma-bg)' : 'var(--ma-muted)',
              border: 'none', cursor: code.trim() ? 'pointer' : 'default',
              fontSize: '12px', fontWeight: 700, fontFamily: "'Manrope', sans-serif",
            }}
          >
            {loading ? '...' : 'Apply'}
          </button>
        </div>
      )}

      {status && (
        <div style={{
          marginTop: '8px', fontSize: '11px',
          color: status.type === 'success' ? '#4ade80' : '#f87171',
          fontFamily: "'Manrope', sans-serif",
        }}>
          {status.message}
        </div>
      )}
    </motion.div>
  );
}


function SettingsCard({ settings }) {
  const { updateSettings, theme, toggleTheme } = useMiniApp();
  const [local, setLocal] = useState(settings);

  const toggle = (key) => {
    const next = { ...local, [key]: !local[key] };
    setLocal(next);
    updateSettings(next);
  };

  const items = [
    { key: 'alertsEnabled', label: 'Alerts', desc: 'Receive signal alerts' },
    { key: 'telegramDelivery', label: 'Telegram Delivery', desc: 'Send to Telegram DM' },
    { key: 'highConvictionOnly', label: 'High Conviction Only', desc: 'Skip normal signals' },
    { key: 'favoritesOnly', label: 'Favorites Only', desc: 'Alerts for favorite assets only' },
  ];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.3 }}
      data-testid="settings-card"
      style={{
        margin: '0 16px 12px', padding: '14px 16px',
        background: 'var(--ma-surface, #18181b)', borderRadius: '16px', border: '1px solid var(--ma-border, #27272a)',
      }}
    >
      {/* Theme Toggle */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
        <Settings size={14} color="var(--ma-secondary, #a1a1aa)" />
        <span style={{
          fontSize: '10px', fontWeight: 700, letterSpacing: '0.15em',
          color: 'var(--ma-muted, #52525b)', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif",
        }}>
          Appearance
        </span>
      </div>
      <button
        data-testid="theme-toggle"
        onClick={toggleTheme}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          width: '100%', padding: '10px 0',
          background: 'transparent', border: 'none', cursor: 'pointer',
          borderBottom: '1px solid var(--ma-border, rgba(39,39,42,0.4))',
          marginBottom: '12px',
        }}
      >
        <div style={{ textAlign: 'left' }}>
          <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--ma-text, #fafafa)', fontFamily: "'Manrope', sans-serif" }}>
            {theme === 'dark' ? 'Dark Mode' : 'Light Mode'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--ma-muted, #52525b)', fontFamily: "'Manrope', sans-serif" }}>
            Switch to {theme === 'dark' ? 'light' : 'dark'} theme
          </div>
        </div>
        <ToggleSwitch active={theme === 'light'} />
      </button>

      {/* Notification Settings */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
        <Bell size={14} color="var(--ma-secondary, #a1a1aa)" />
        <span style={{
          fontSize: '10px', fontWeight: 700, letterSpacing: '0.15em',
          color: 'var(--ma-muted, #52525b)', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif",
        }}>
          Notification Settings
        </span>
      </div>

      {items.map((item, i) => (
        <button
          key={item.key}
          data-testid={`setting-${item.key}`}
          onClick={() => toggle(item.key)}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            width: '100%', padding: '10px 0',
            background: 'transparent', border: 'none', cursor: 'pointer',
            borderBottom: i < items.length - 1 ? '1px solid var(--ma-border, rgba(39,39,42,0.4))' : 'none',
          }}
        >
          <div style={{ textAlign: 'left' }}>
            <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--ma-text, #fafafa)', fontFamily: "'Manrope', sans-serif" }}>
              {item.label}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--ma-muted, #52525b)', fontFamily: "'Manrope', sans-serif" }}>
              {item.desc}
            </div>
          </div>
          <ToggleSwitch active={local[item.key]} />
        </button>
      ))}
    </motion.div>
  );
}


function ToggleSwitch({ active }) {
  return (
    <div style={{
      width: '38px', height: '22px', borderRadius: '11px',
      background: active ? '#10b981' : 'var(--ma-stat-bg)',
      transition: 'background 0.2s',
      position: 'relative', flexShrink: 0,
    }}>
      <div style={{
        width: '18px', height: '18px', borderRadius: '50%',
        background: 'var(--ma-text)', position: 'absolute',
        top: '2px', left: active ? '18px' : '2px',
        transition: 'left 0.2s',
      }} />
    </div>
  );
}


function ProfileLoading() {
  return (
    <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {[100, 120, 60, 80, 60, 100].map((_, i) => (
        <div key={i} style={{
          height: i === 0 ? '90px' : i === 1 ? '160px' : '80px',
          background: 'var(--ma-surface)', borderRadius: '16px',
          animation: 'pulse 1.5s ease infinite',
        }} />
      ))}
      <style>{`@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }`}</style>
    </div>
  );
}
