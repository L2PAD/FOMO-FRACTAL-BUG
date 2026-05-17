/**
 * Admin Billing Console — Unified page with internal horizontal tabs.
 * Wrapped in AdminLayout (platform sidebar).
 *
 * Tabs: Overview | Subscribers | Payments | Subscriptions | Events | Access
 */
import { useState, useEffect, useCallback } from 'react';
import {
  DollarSign, Users, CreditCard, Activity, Shield, RefreshCw,
  Search, Eye, Clock, Wallet, ArrowUpRight,
  TrendingUp, TrendingDown, AlertTriangle, CheckCircle2,
  XCircle, BarChart3, Settings2, Save, Key, Loader2, Info,
} from 'lucide-react';
import { AdminLayout } from '../../components/admin/PlatformAdminLayout';

const API = process.env.REACT_APP_BACKEND_URL;

// ── Tab config ──────────────────────────────────────────────────
const TABS = [
  { id: 'overview', label: 'Обзор', icon: BarChart3 },
  { id: 'crypto', label: 'Crypto Payments', icon: Wallet },
  { id: 'pricing', label: 'Тарифы', icon: Settings2 },
  { id: 'promos', label: 'Промокоды', icon: Activity },
  { id: 'subscribers', label: 'Подписчики', icon: Users },
  { id: 'payments', label: 'Платежи', icon: CreditCard },
  { id: 'subscriptions', label: 'Подписки', icon: Wallet },
  { id: 'events', label: 'События', icon: Activity },
  { id: 'access', label: 'Доступ', icon: Shield },
];

// ── Color tokens ────────────────────────────────────────────────
const c = {
  text: '#0f172a',
  textSecondary: '#475569',
  textMuted: '#94a3b8',
  accent: '#6366f1',
  surface: '#f8fafc',
  border: '#e2e8f0',
};

// ═══════════════════════════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════════════════════════
export default function BillingAdminPage() {
  const params = new URLSearchParams(window.location.search);
  const initialTab = params.get('tab') || 'overview';
  const [activeTab, setActiveTab] = useState(initialTab);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    const url = new URL(window.location);
    if (tab === 'overview') {
      url.searchParams.delete('tab');
    } else {
      url.searchParams.set('tab', tab);
    }
    window.history.replaceState({}, '', url);
  };

  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6" data-testid="billing-admin-page">
        {/* Page Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold flex items-center gap-3" style={{ color: c.text }}>
            <DollarSign size={28} style={{ color: c.accent }} />
            Billing Console
          </h1>
          <p className="text-sm mt-1" style={{ color: c.textSecondary }}>
            Управление подписками, платежами и доступом пользователей
          </p>
        </div>

        {/* Horizontal Tab Navigation */}
        <div className="flex gap-1 mb-8 p-1 rounded-xl" style={{ backgroundColor: c.surface }}>
          {TABS.map(tab => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                data-testid={`billing-tab-${tab.id}`}
                onClick={() => handleTabChange(tab.id)}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all"
                style={{
                  backgroundColor: isActive ? 'white' : 'transparent',
                  color: isActive ? c.accent : c.textSecondary,
                  boxShadow: isActive ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                }}
              >
                <Icon size={16} />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab Content */}
        {activeTab === 'overview' && <OverviewTab />}
        {activeTab === 'crypto' && <CryptoPaymentsTab />}
        {activeTab === 'pricing' && <PricingTab />}
        {activeTab === 'promos' && <PromosTab />}
        {activeTab === 'subscribers' && <SubscribersTab />}
        {activeTab === 'payments' && <PaymentsTab />}
        {activeTab === 'subscriptions' && <SubscriptionsTab />}
        {activeTab === 'events' && <EventsTab />}
        {activeTab === 'access' && <AccessTab />}
      </div>
    </AdminLayout>
  );
}


/* ══════════════════════════════════════════════════════════════════
   OVERVIEW TAB
   ══════════════════════════════════════════════════════════════════ */
function OverviewTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    // Fetch crypto stats instead of Stripe
    fetch(`${API}/api/admin/billing/crypto/stats`).then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(setData).finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading && !data) return <LoadingState />;

  const k = {
    total_users: (data?.proUsers || 0),
    active_subscribers: data?.proUsers || 0,
    mrr: data?.mrr || 0,
    revenue_30d: data?.last30Days?.revenue || 0,
    total_payments: data?.totalPayments || 0,
    total_revenue: data?.totalRevenue || 0,
  };

  return (
    <div className="space-y-8" data-testid="billing-overview">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="kpi-cards">
        <KpiCard label="PRO Пользователи" value={k.active_subscribers} icon={Users} color="text-emerald-600" />
        <KpiCard label="Всего платежей" value={k.total_payments} icon={CreditCard} color="text-blue-600" />
        <KpiCard label="MRR" value={`$${k.mrr}`} icon={DollarSign} color="text-emerald-600" />
        <KpiCard label="Выручка 30д" value={`$${k.revenue_30d}`} icon={TrendingUp} color="text-purple-600" />
      </div>

      {/* Revenue Summary */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h3 className="text-lg font-bold mb-4 text-gray-900">
          Статистика Crypto Payments (NOWPayments)
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
          <div>
            <div className="text-sm text-gray-500 mb-1">Всего выручка</div>
            <div className="text-2xl font-bold text-emerald-600">${k.total_revenue}</div>
          </div>
          <div>
            <div className="text-sm text-gray-500 mb-1">Платежей за 30 дней</div>
            <div className="text-2xl font-bold text-blue-600">{data?.last30Days?.payments || 0}</div>
          </div>
          <div>
            <div className="text-sm text-gray-500 mb-1">Новых PRO за 30 дней</div>
            <div className="text-2xl font-bold text-purple-600">{data?.last30Days?.newPro || 0}</div>
          </div>
        </div>
      </div>

      {/* Info Block */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <Info className="text-blue-600 mt-0.5" size={20} />
          <div>
            <h4 className="text-sm font-semibold text-blue-900 mb-1">Crypto Billing System</h4>
            <p className="text-sm text-blue-700">
              Платежная система на базе NOWPayments. Все платежи обрабатываются через crypto (BTC, USDT, ETH и др.). 
              Перейдите на вкладку "Crypto Payments" для детальной информации и управления транзакциями.
            </p>
          </div>
        </div>
      </div>

      {/* Payment Methods */}
        <div className="border border-gray-200 rounded-lg p-5" data-testid="payment-methods">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Методы оплаты</h3>
          {data?.charts?.payment_methods && (
            <div className="space-y-3">
              {Object.entries(data.charts.payment_methods).map(([method, count]) => (
                <div key={method} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {method === 'crypto' ? <Wallet className="w-4 h-4 text-blue-500" /> : <CreditCard className="w-4 h-4 text-gray-500" />}
                    <span className="text-sm text-gray-700">{method === 'crypto' ? 'Крипто (USDC)' : 'Карта'}</span>
                  </div>
                  <span className="text-sm font-medium text-gray-900">{count}</span>
                </div>
              ))}
            </div>
          )}
        </div>

      {/* Tables Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Recent Payments */}
        <div className="border border-gray-200 rounded-lg p-5" data-testid="recent-payments">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Последние платежи</h3>
          {(data?.recent_payments || []).length === 0 ? (
            <p className="text-xs text-gray-400 py-4 text-center">Платежей пока нет</p>
          ) : (
            <div className="space-y-2">
              {data.recent_payments.slice(0, 8).map((p, i) => (
                <div key={i} className="flex items-center justify-between text-xs py-1.5 border-b border-gray-50">
                  <div className="flex items-center gap-2">
                    <StatusDot status={p.payment_status} />
                    <span className="text-gray-600 truncate max-w-[150px]">{p.email || p.user_id}</span>
                  </div>
                  <div className="flex items-center gap-3 text-gray-500">
                    <span className={p.payment_method === 'crypto' ? 'text-blue-600' : ''}>{p.payment_method === 'crypto' ? 'USDC' : 'Карта'}</span>
                    <span className="font-medium text-gray-700">${p.amount || '--'}</span>
                    <span className="text-gray-400">{p.created_at ? new Date(p.created_at).toLocaleDateString() : ''}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* At-Risk Users */}
        <div className="border border-gray-200 rounded-lg p-5" data-testid="at-risk-users">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Подписки в зоне риска</h3>
          {(data?.at_risk || []).length === 0 ? (
            <p className="text-xs text-gray-400 py-4 text-center">Нет проблемных подписок</p>
          ) : (
            <div className="space-y-2">
              {data.at_risk.map((r, i) => (
                <div key={i} className="flex items-center justify-between text-xs py-1.5 border-b border-gray-50">
                  <span className="text-gray-600">{r.user?.email || r.user_id}</span>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={r.status} />
                    <span className="text-gray-400">{r.current_period_end ? new Date(r.current_period_end).toLocaleDateString() : ''}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════════
   PRICING TAB - Настройка тарифов
   ══════════════════════════════════════════════════════════════════ */
function PricingTab() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(null);
  const [error, setError] = useState(null);

  // Form state
  const [billingMode, setBillingMode] = useState('paid');
  const [freeTrialDays, setFreeTrialDays] = useState('3');
  const [monthlyCard, setMonthlyCard] = useState('');
  const [yearlyCard, setYearlyCard] = useState('');
  const [monthlyCrypto, setMonthlyCrypto] = useState('');
  const [yearlyCrypto, setYearlyCrypto] = useState('');
  const [discountPct, setDiscountPct] = useState('15');
  const [freeEnabled, setFreeEnabled] = useState(false);
  const [paywallEnabled, setPaywallEnabled] = useState(true);
  const [productName, setProductName] = useState('');

  const load = useCallback(() => {
    setLoading(true);
    fetch(`${API}/api/admin/billing/pricing`).then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(data => {
        const p = data.pricing || {};
        setConfig(p);
        setBillingMode(p.billing_mode || 'paid');
        setFreeTrialDays(String(p.free_trial_days || 3));
        setMonthlyCard(((p.monthly_card_cents || 100) / 100).toFixed(2));
        setYearlyCard(((p.yearly_card_cents || 1000) / 100).toFixed(2));
        setMonthlyCrypto((p.monthly_crypto_dollars || 1).toFixed(2));
        setYearlyCrypto((p.yearly_crypto_dollars || 10).toFixed(2));
        setDiscountPct(String(p.yearly_discount_percent || 15));
        setFreeEnabled(p.free_access_enabled || false);
        setProductName(p.product_name || 'FOMO Intelligence PRO');
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    setError(null); setSuccess(null);
    const mCard = Math.round(parseFloat(monthlyCard) * 100);
    const yCard = Math.round(parseFloat(yearlyCard) * 100);
    if (billingMode === 'paid' && (isNaN(mCard) || mCard < 50)) { setError('Мин. месячная цена карты — $0.50'); return; }
    if (billingMode === 'paid' && (isNaN(yCard) || yCard < 50)) { setError('Мин. годовая цена карты — $0.50'); return; }

    setSaving(true);
    try {
      const res = await fetch(`${API}/api/admin/billing/pricing`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          billing_mode: billingMode,
          free_trial_days: parseInt(freeTrialDays) || 3,
          monthly_card_cents: mCard,
          yearly_card_cents: yCard,
          monthly_crypto_dollars: parseFloat(monthlyCrypto),
          yearly_crypto_dollars: parseFloat(yearlyCrypto),
          yearly_discount_percent: parseInt(discountPct) || 15,
          free_access_enabled: freeEnabled,
          paywall_enabled: paywallEnabled,
          product_name: productName,
        }),
      });
      const data = await res.json();
      if (data.ok) {
        setSuccess('Тарифы обновлены');
        setConfig(data.pricing);
        setTimeout(() => setSuccess(null), 3000);
      } else { setError(data.detail || 'Ошибка'); }
    } catch { setError('Ошибка сети'); }
    finally { setSaving(false); }
  };

  if (loading) return <LoadingState />;

  return (
    <div className="space-y-6" data-testid="pricing-tab">
      {/* Billing Mode Toggle */}
      <div className="border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-3">Режим биллинга</h3>
        <div className="flex gap-3">
          <button onClick={() => setBillingMode('free_trial')}
            className={`flex-1 p-4 rounded-lg border-2 transition-all text-left ${
              billingMode === 'free_trial' ? 'border-emerald-500 bg-emerald-50' : 'border-gray-200 hover:border-gray-300'
            }`}>
            <p className="text-sm font-bold text-gray-900">Free Trial</p>
            <p className="text-xs text-gray-500 mt-1">$0 — привязка карты, доступ на N дней</p>
          </button>
          <button onClick={() => setBillingMode('paid')}
            className={`flex-1 p-4 rounded-lg border-2 transition-all text-left ${
              billingMode === 'paid' ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200 hover:border-gray-300'
            }`}>
            <p className="text-sm font-bold text-gray-900">Paid</p>
            <p className="text-xs text-gray-500 mt-1">Оплата за Card/Crypto сразу</p>
          </button>
        </div>

        {billingMode === 'free_trial' && (
          <div className="mt-4 p-3 bg-emerald-50 rounded-lg">
            <label className="text-xs text-emerald-700 font-medium">Дней бесплатного доступа</label>
            <input type="number" min="1" max="30" value={freeTrialDays}
              onChange={e => setFreeTrialDays(e.target.value)}
              className="mt-1 w-20 border border-emerald-300 rounded-lg px-3 py-1.5 text-sm font-bold text-emerald-800 focus:outline-none" />
            <p className="text-[10px] text-emerald-600 mt-1">Бесплатный пробный период для новых пользователей.</p>
          </div>
        )}
      </div>

      {/* Free Access & Paywall Toggles */}
      <div className="border border-gray-200 rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Бесплатный доступ для всех</h3>
            <p className="text-xs text-gray-500 mt-0.5">Все пользователи получают полный доступ без оплаты</p>
          </div>
          <button onClick={() => setFreeEnabled(!freeEnabled)}
            className={`relative w-12 h-6 rounded-full transition-colors ${freeEnabled ? 'bg-emerald-500' : 'bg-gray-300'}`}>
            <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform shadow-sm ${freeEnabled ? 'translate-x-6' : ''}`} />
          </button>
        </div>
        <div className="flex items-center justify-between pt-4 border-t border-gray-100">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Paywall (блокировка доступа)</h3>
            <p className="text-xs text-gray-500 mt-0.5">Блокирует приложение для неоплативших пользователей</p>
          </div>
          <button onClick={() => setPaywallEnabled(!paywallEnabled)}
            className={`relative w-12 h-6 rounded-full transition-colors ${paywallEnabled ? 'bg-red-500' : 'bg-gray-300'}`}>
            <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform shadow-sm ${paywallEnabled ? 'translate-x-6' : ''}`} />
          </button>
        </div>
      </div>

      {/* Monthly/Yearly Pricing */}
      <div className="border border-gray-200 rounded-lg p-5 space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Месячная подписка</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-gray-500">Карта (USD/мес)</label>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-lg font-bold text-gray-400">$</span>
              <input type="number" step="0.01" min="0.50" value={monthlyCard}
                onChange={e => setMonthlyCard(e.target.value)}
                className="w-32 border border-gray-200 rounded-lg px-3 py-2 text-lg font-bold text-gray-900 focus:outline-none focus:border-indigo-400" />
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-500">Крипто (USD/мес)</label>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-lg font-bold text-blue-500">$</span>
              <input type="number" step="0.01" min="0" value={monthlyCrypto}
                onChange={e => setMonthlyCrypto(e.target.value)}
                className="w-32 border border-gray-200 rounded-lg px-3 py-2 text-lg font-bold text-gray-900 focus:outline-none focus:border-indigo-400" />
            </div>
          </div>
        </div>
      </div>

      <div className="border border-gray-200 rounded-lg p-5 space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Годовая подписка</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="text-xs text-gray-500">Карта (USD/год)</label>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-lg font-bold text-gray-400">$</span>
              <input type="number" step="0.01" min="0.50" value={yearlyCard}
                onChange={e => setYearlyCard(e.target.value)}
                className="w-32 border border-gray-200 rounded-lg px-3 py-2 text-lg font-bold text-gray-900 focus:outline-none focus:border-indigo-400" />
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-500">Крипто (USD/год)</label>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-lg font-bold text-blue-500">$</span>
              <input type="number" step="0.01" min="0" value={yearlyCrypto}
                onChange={e => setYearlyCrypto(e.target.value)}
                className="w-32 border border-gray-200 rounded-lg px-3 py-2 text-lg font-bold text-gray-900 focus:outline-none focus:border-indigo-400" />
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-500">Скидка (%)</label>
            <input type="number" min="0" max="90" value={discountPct}
              onChange={e => setDiscountPct(e.target.value)}
              className="mt-1 w-20 border border-gray-200 rounded-lg px-3 py-2 text-lg font-bold text-emerald-600 focus:outline-none" />
          </div>
        </div>
      </div>

      {/* Messages */}
      {error && <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700"><AlertTriangle className="w-4 h-4" /> {error}</div>}
      {success && <div className="flex items-center gap-2 p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700"><CheckCircle2 className="w-4 h-4" /> {success}</div>}

      {/* Save */}
      <div className="flex items-center gap-4">
        <button onClick={handleSave} disabled={saving}
          className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
          <Save className="w-4 h-4" /> {saving ? 'Сохранение...' : 'Сохранить тарифы'}
        </button>
        <span className="text-xs text-gray-400">Изменения применяются к крипто-платежам</span>
      </div>
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════════
   PAYMENTS TAB
   ══════════════════════════════════════════════════════════════════ */
function PaymentsTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [methodFilter, setMethodFilter] = useState('all');

  const load = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams({ status: statusFilter, method: methodFilter, limit: '50' });
    fetch(`${API}/api/admin/billing/payments?${params}`).then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(setData).finally(() => setLoading(false));
  }, [statusFilter, methodFilter]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4" data-testid="payments-tab">
      <div className="flex items-center gap-3 flex-wrap">
        {[['all','Все'],['paid','Оплачено'],['failed','Ошибка']].map(([f,l]) => (
          <button key={f} onClick={() => setStatusFilter(f)}
            className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-all ${statusFilter === f ? 'bg-indigo-600 text-white' : 'text-gray-500 hover:bg-gray-100'}`}>{l}</button>
        ))}
        <div className="w-px h-4 bg-gray-200" />
        {[['all','Все методы'],['card','Карта'],['crypto','Крипто']].map(([f,l]) => (
          <button key={f} onClick={() => setMethodFilter(f)}
            className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-all ${methodFilter === f ? 'bg-indigo-600 text-white' : 'text-gray-500 hover:bg-gray-100'}`}>{l}</button>
        ))}
        <span className="text-xs text-gray-400 ml-auto">{data?.total || 0} платежей</span>
      </div>
      {loading && !data ? <LoadingState /> : (
        <div className="overflow-x-auto border border-gray-200 rounded-lg">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-400 border-b border-gray-100 bg-gray-50">
                <th className="py-2.5 px-4 font-medium">Дата</th>
                <th className="py-2.5 px-3 font-medium">Пользователь</th>
                <th className="py-2.5 px-3 font-medium">Сумма</th>
                <th className="py-2.5 px-3 font-medium">Метод</th>
                <th className="py-2.5 px-3 font-medium">Статус</th>
              </tr>
            </thead>
            <tbody>
              {(data?.payments || []).map((p, i) => (
                <tr key={i} className="border-b border-gray-50 hover:bg-gray-50/50">
                  <td className="py-2.5 px-4 text-xs text-gray-600">{p.created_at ? new Date(p.created_at).toLocaleString() : '--'}</td>
                  <td className="py-2.5 px-3 text-xs text-gray-700">{p.email || p.user_id}</td>
                  <td className="py-2.5 px-3 text-sm font-medium text-gray-900">${p.amount || '--'}</td>
                  <td className="py-2.5 px-3">
                    {p.payment_method === 'crypto'
                      ? <span className="text-[10px] font-bold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">CRYPTO</span>
                      : <span className="text-[10px] text-gray-500">Карта</span>}
                  </td>
                  <td className="py-2.5 px-3"><StatusBadge status={p.payment_status} /></td>
                </tr>
              ))}
              {(data?.payments || []).length === 0 && (
                <tr><td colSpan={5} className="py-8 text-center text-sm text-gray-400">Платежи не найдены</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════════
   SUBSCRIPTIONS TAB
   ══════════════════════════════════════════════════════════════════ */
function SubscriptionsTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');

  const load = useCallback(() => {
    setLoading(true);
    fetch(`${API}/api/admin/billing/subscriptions?status=${filter}&limit=50`).then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(setData).finally(() => setLoading(false));
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4" data-testid="subscriptions-tab">
      <div className="flex items-center gap-3">
        {[['all','Все'],['active','Активные'],['canceled','Отменено']].map(([f,l]) => (
          <button key={f} onClick={() => setFilter(f)}
            className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-all ${filter === f ? 'bg-indigo-600 text-white' : 'text-gray-500 hover:bg-gray-100'}`}>{l}</button>
        ))}
        <span className="text-xs text-gray-400 ml-auto">{data?.total || 0} подписок</span>
      </div>
      {loading && !data ? <LoadingState /> : (
        <div className="overflow-x-auto border border-gray-200 rounded-lg">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-400 border-b border-gray-100 bg-gray-50">
                <th className="py-2.5 px-4 font-medium">Пользователь</th>
                <th className="py-2.5 px-3 font-medium">Статус</th>
                <th className="py-2.5 px-3 font-medium">Сумма</th>
                <th className="py-2.5 px-3 font-medium">Метод</th>
                <th className="py-2.5 px-3 font-medium">Окончание</th>
              </tr>
            </thead>
            <tbody>
              {(data?.subscriptions || []).map((s, i) => (
                <tr key={i} className="border-b border-gray-50 hover:bg-gray-50/50">
                  <td className="py-2.5 px-4 text-sm text-gray-700">{s.user?.email || s.user_id}</td>
                  <td className="py-2.5 px-3"><StatusBadge status={s.status} /></td>
                  <td className="py-2.5 px-3 text-gray-600">{s.amount != null ? `$${s.amount}` : '--'}</td>
                  <td className="py-2.5 px-3 text-xs text-gray-500">{s.payment_method || 'карта'}</td>
                  <td className="py-2.5 px-3 text-xs text-gray-500">{s.expires_at ? new Date(s.expires_at).toLocaleDateString() : '--'}</td>
                </tr>
              ))}
              {(data?.subscriptions || []).length === 0 && (
                <tr><td colSpan={5} className="py-8 text-center text-sm text-gray-400">Подписки не найдены</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════════
   EVENTS TAB
   ══════════════════════════════════════════════════════════════════ */
function EventsTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API}/api/admin/billing/events?limit=50`).then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(setData).finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4" data-testid="events-tab">
      <p className="text-xs text-gray-400">Журнал всех webhook-событий крипто-платежей и действий администратора.</p>
      {loading && !data ? <LoadingState /> : (
        <div className="overflow-x-auto border border-gray-200 rounded-lg">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-400 border-b border-gray-100 bg-gray-50">
                <th className="py-2.5 px-4 font-medium">Время</th>
                <th className="py-2.5 px-3 font-medium">Источник</th>
                <th className="py-2.5 px-3 font-medium">Тип</th>
                <th className="py-2.5 px-3 font-medium">Пользователь</th>
                <th className="py-2.5 px-3 font-medium">Обработано</th>
              </tr>
            </thead>
            <tbody>
              {(data?.events || []).map((e, i) => (
                <tr key={i} className="border-b border-gray-50 hover:bg-gray-50/50">
                  <td className="py-2.5 px-4 text-xs text-gray-600">{e.created_at ? new Date(e.created_at).toLocaleString() : '--'}</td>
                  <td className="py-2.5 px-3">
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${e.source === 'admin' ? 'text-purple-600 bg-purple-50' : 'text-blue-600 bg-blue-50'}`}>
                      {e.source === 'admin' ? 'Админ' : 'Crypto'}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-xs text-gray-700">{e.type}</td>
                  <td className="py-2.5 px-3 text-xs text-gray-500">{e.user_id || '--'}</td>
                  <td className="py-2.5 px-3">
                    {e.processed ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> : <XCircle className="w-3.5 h-3.5 text-red-400" />}
                  </td>
                </tr>
              ))}
              {(data?.events || []).length === 0 && (
                <tr><td colSpan={5} className="py-8 text-center text-sm text-gray-400">Событий пока нет</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}




/* ══════════════════════════════════════════════════════════════════
   SUBSCRIBERS TAB
   ══════════════════════════════════════════════════════════════════ */

/* ══════════════════════════════════════════════════════════════════
   PRICING TAB
   ══════════════════════════════════════════════════════════════════ */
function ReferralGroupEditor({ group, onSaved }) {
  const [reward, setReward] = useState(String(group.referral_reward_percent || 10));
  const [discount, setDiscount] = useState(String(group.discount_percent || 0));
  const [saving, setSaving] = useState(false);
  const [assignEmail, setAssignEmail] = useState('');
  const [assignResult, setAssignResult] = useState(null);

  const handleSave = async () => {
    setSaving(true);
    try {
      await fetch(`${API}/api/admin/billing/promos/groups/${group.group_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          referral_reward_percent: parseInt(reward) || 0,
          discount_percent: parseInt(discount) || 0,
        }),
      });
      onSaved();
    } catch { }
    finally { setSaving(false); }
  };

  const handleAssign = async () => {
    if (!assignEmail.trim()) return;
    setAssignResult(null);
    try {
      const res = await fetch(`${API}/api/admin/billing/promos/groups/${group.group_id}/assign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_email: assignEmail }),
      });
      const data = await res.json();
      setAssignResult(data.ok ? { ok: true, code: data.code } : { ok: false, error: data.detail || 'Error' });
      if (data.ok) setAssignEmail('');
    } catch (e) { setAssignResult({ ok: false, error: e.message }); }
  };

  return (
    <div className="border-t border-gray-100 bg-blue-50 p-5 space-y-4" data-testid={`referral-editor-${group.group_id}`}>
      <p className="text-xs font-semibold text-blue-800">Настройки реферальной системы</p>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div>
          <label className="text-xs text-gray-600 font-medium">Скидка для приглашённого %</label>
          <select value={discount} onChange={e => setDiscount(e.target.value)}
            className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
            {[0,5,10,15,20,25,30,40,50,75,95,100].map(v => (
              <option key={v} value={v}>{v}%</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-600 font-medium">Вознаграждение рефереру %</label>
          <select value={reward} onChange={e => setReward(e.target.value)}
            className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
            {[5,10,15,20,25,30,40,50].map(v => (
              <option key={v} value={v}>{v}%</option>
            ))}
          </select>
        </div>
        <div className="flex items-end">
          <button onClick={handleSave} disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-xs font-medium hover:bg-blue-700 disabled:opacity-50">
            {saving ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      </div>

      {/* Assign code to influencer */}
      <div className="border-t border-blue-200 pt-4">
        <p className="text-xs font-medium text-gray-600 mb-2">Назначить код пользователю (инфлюенсер / блогер)</p>
        <div className="flex gap-2">
          <input type="email" placeholder="email@example.com" value={assignEmail}
            onChange={e => setAssignEmail(e.target.value)}
            style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '8px 12px', outline: 'none' }}
            className="flex-1 text-sm" />
          <button onClick={handleAssign}
            data-testid="assign-referral-btn"
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-medium hover:bg-indigo-700">
            Назначить
          </button>
        </div>
        {assignResult?.ok && (
          <p className="text-xs text-emerald-600 mt-2">Код <span className="font-mono font-bold">{assignResult.code}</span> назначен</p>
        )}
        {assignResult && !assignResult.ok && (
          <p className="text-xs text-red-500 mt-2">{assignResult.error}</p>
        )}
      </div>
    </div>
  );
}



/* ══════════════════════════════════════════════════════════════════
   PROMOS TAB
   ══════════════════════════════════════════════════════════════════ */
function PromosTab() {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [expandedGroup, setExpandedGroup] = useState(null);
  const [groupCodes, setGroupCodes] = useState({});

  // Create form
  const [newName, setNewName] = useState('');
  const [newDiscount, setNewDiscount] = useState('50');
  const [newCount, setNewCount] = useState('10');
  const [newPrefix, setNewPrefix] = useState('');
  const [newReferralEnabled, setNewReferralEnabled] = useState(false);
  const [newReferralReward, setNewReferralReward] = useState('10');
  const [showCreate, setShowCreate] = useState(false);
  const [editGroup, setEditGroup] = useState(null);

  const loadGroups = useCallback(() => {
    setLoading(true);
    fetch(`${API}/api/admin/billing/promos/groups`).then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(d => setGroups(d.groups || []))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadGroups(); }, [loadGroups]);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const res = await fetch(`${API}/api/admin/billing/promos/groups`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newName,
          discount_percent: parseInt(newDiscount) || 0,
          count: parseInt(newCount) || 10,
          prefix: newPrefix,
          referral_enabled: newReferralEnabled,
          referral_reward_percent: newReferralEnabled ? (parseInt(newReferralReward) || 0) : 0,
        }),
      });
      const data = await res.json();
      if (data.ok) {
        setNewName(''); setNewDiscount('50'); setNewCount('10'); setNewPrefix('');
        setNewReferralEnabled(false); setNewReferralReward('10');
        setShowCreate(false);
        loadGroups();
      }
    } catch { }
    finally { setCreating(false); }
  };

  const handleDelete = async (groupId) => {
    if (!window.confirm('Удалить группу и все её коды?')) return;
    await fetch(`${API}/api/admin/billing/promos/groups/${groupId}`, { method: 'DELETE' });
    loadGroups();
  };

  const loadCodes = async (groupId) => {
    if (expandedGroup === groupId) { setExpandedGroup(null); return; }
    setExpandedGroup(groupId);
    const res = await fetch(`${API}/api/admin/billing/promos/groups/${groupId}/codes`);
    const data = await res.json();
    setGroupCodes(prev => ({ ...prev, [groupId]: data.codes || [] }));
  };

  if (loading) return <LoadingState />;

  return (
    <div className="space-y-6" data-testid="promos-tab">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">Промокоды</h3>
          <p className="text-xs text-gray-500 mt-0.5">Создавайте группы промокодов с разными скидками</p>
        </div>
        <button onClick={() => setShowCreate(!showCreate)}
          data-testid="create-promo-group-btn"
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-medium hover:bg-indigo-700 transition-colors">
          + Создать группу
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="border border-indigo-200 bg-indigo-50 rounded-lg p-5 space-y-4" data-testid="create-promo-form">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label className="text-xs text-gray-600 font-medium">Название группы</label>
              <input type="text" placeholder="VIP 50%" value={newName}
                onChange={e => setNewName(e.target.value)}
                className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none" />
            </div>
            <div>
              <label className="text-xs text-gray-600 font-medium">Скидка %</label>
              <select value={newDiscount} onChange={e => setNewDiscount(e.target.value)}
                className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
                <option value="0">0% (без скидки)</option>
                <option value="15">15%</option>
                <option value="25">25%</option>
                <option value="50">50%</option>
                <option value="75">75%</option>
                <option value="95">95%</option>
                <option value="100">100% (бесплатный доступ)</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-600 font-medium">Кол-во кодов</label>
              <input type="number" min="1" max="500" value={newCount}
                onChange={e => setNewCount(e.target.value)}
                className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none" />
            </div>
            <div>
              <label className="text-xs text-gray-600 font-medium">Префикс (опц.)</label>
              <input type="text" placeholder="VIP" value={newPrefix}
                onChange={e => setNewPrefix(e.target.value.toUpperCase())}
                className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none" />
            </div>
          </div>

          {/* Referral settings */}
          <div className="border-t border-indigo-200 pt-4">
            <div className="flex items-center gap-3 mb-3">
              <button onClick={() => setNewReferralEnabled(!newReferralEnabled)}
                data-testid="referral-toggle-create"
                className={`relative w-10 h-5 rounded-full transition-colors ${newReferralEnabled ? 'bg-indigo-500' : 'bg-gray-300'}`}>
                <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform shadow-sm ${newReferralEnabled ? 'translate-x-5' : ''}`} />
              </button>
              <span className="text-xs font-medium text-gray-700">Реферальная система</span>
            </div>
            {newReferralEnabled && (
              <div className="grid grid-cols-2 gap-4 ml-13">
                <div>
                  <label className="text-xs text-gray-600 font-medium">Вознаграждение реферера %</label>
                  <select value={newReferralReward} onChange={e => setNewReferralReward(e.target.value)}
                    data-testid="referral-reward-select"
                    className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
                    <option value="5">5%</option>
                    <option value="10">10%</option>
                    <option value="15">15%</option>
                    <option value="20">20%</option>
                    <option value="25">25%</option>
                    <option value="30">30%</option>
                    <option value="40">40%</option>
                    <option value="50">50%</option>
                  </select>
                  <p className="text-[10px] text-gray-400 mt-1">Процент от оплаты, который получает реферер</p>
                </div>
              </div>
            )}
          </div>

          <button onClick={handleCreate} disabled={creating || !newName.trim()}
            data-testid="submit-promo-group-btn"
            className="px-5 py-2 bg-indigo-600 text-white rounded-lg text-xs font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors">
            {creating ? 'Создание...' : 'Сгенерировать коды'}
          </button>
        </div>
      )}

      {/* Groups list */}
      {groups.length === 0 ? (
        <div className="text-center py-8 text-sm text-gray-400">Нет промокодов</div>
      ) : (
        <div className="space-y-3">
          {groups.map(g => (
            <div key={g.group_id} className="border border-gray-200 rounded-lg overflow-hidden">
              <div className="px-5 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors">
                <div className="flex items-center gap-4">
                  <div className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                    g.discount_percent === 100 ? 'bg-purple-100 text-purple-700'
                    : g.discount_percent >= 50 ? 'bg-emerald-100 text-emerald-700'
                    : 'bg-gray-100 text-gray-700'
                  }`}>
                    {g.discount_percent === 100 ? 'FREE' : `-${g.discount_percent}%`}
                  </div>
                  {g.referral_enabled && (
                    <div className="px-2.5 py-1 rounded-full text-xs font-bold bg-blue-100 text-blue-700" data-testid={`referral-badge-${g.group_id}`}>
                      REF {g.referral_reward_percent}%
                    </div>
                  )}
                  <div>
                    <p className="text-sm font-medium text-gray-900">{g.name}</p>
                    <p className="text-xs text-gray-400">
                      {g.used_codes}/{g.total_codes} used
                      {g.referral_enabled && g.referral_conversions > 0 && ` · ${g.referral_conversions} conversions`}
                      {' · Created '}
                      {new Date(g.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {g.referral_enabled && (
                    <button onClick={() => setEditGroup(editGroup === g.group_id ? null : g.group_id)}
                      className="px-3 py-1.5 text-xs font-medium text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-50 transition-colors">
                      {editGroup === g.group_id ? 'Скрыть' : 'Настройки'}
                    </button>
                  )}
                  <button onClick={() => loadCodes(g.group_id)}
                    className="px-3 py-1.5 text-xs font-medium text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-100 transition-colors">
                    {expandedGroup === g.group_id ? 'Скрыть' : 'Коды'}
                  </button>
                  <button onClick={() => handleDelete(g.group_id)}
                    className="px-3 py-1.5 text-xs font-medium text-red-500 border border-red-200 rounded-lg hover:bg-red-50 transition-colors">
                    Удалить
                  </button>
                </div>
              </div>

              {/* Referral settings inline editor */}
              {editGroup === g.group_id && g.referral_enabled && (
                <ReferralGroupEditor group={g} onSaved={() => { setEditGroup(null); loadGroups(); }} />
              )}

              {/* Expanded codes */}
              {expandedGroup === g.group_id && groupCodes[g.group_id] && (
                <div className="border-t border-gray-100 bg-gray-50 p-4 max-h-60 overflow-y-auto">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                    {groupCodes[g.group_id].map(c => (
                      <div key={c.code}
                        className={`font-mono text-xs px-3 py-2 rounded-lg border ${
                          c.used_by
                            ? 'bg-red-50 border-red-200 text-red-500 line-through'
                            : c.referrer_user_id
                              ? 'bg-blue-50 border-blue-200 text-blue-700'
                              : 'bg-white border-gray-200 text-gray-700'
                        }`}>
                        {c.code}
                        {c.used_by && <span className="text-[9px] ml-1 no-underline">(used)</span>}
                        {c.referrer_user_id && !c.used_by && <span className="text-[9px] ml-1 text-blue-500">(assigned)</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


/* StripeKeysTab removed - using Crypto Payments only */

function SubscribersTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams({ status: filter, limit: '50' });
    if (search) params.set('search', search);
    fetch(`${API}/api/admin/billing/subscribers?${params}`).then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(setData).finally(() => setLoading(false));
  }, [filter, search]);

  useEffect(() => { load(); }, [load]);

  const loadDetail = async (userId) => {
    setSelected(userId);
    const res = await fetch(`${API}/api/admin/billing/subscribers/${userId}`);
    setDetail(await res.json());
  };

  if (selected && detail) {
    return <SubscriberDetail data={detail} onBack={() => { setSelected(null); setDetail(null); }} onRefresh={() => loadDetail(selected)} />;
  }

  return (
    <div className="space-y-4" data-testid="subscribers-tab">
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input type="text" placeholder="Поиск по email или имени..."
            value={search} onChange={e => setSearch(e.target.value)}
            className="pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-gray-400 w-64"
            data-testid="subscriber-search" />
        </div>
        {[['all','Все'],['active','Активные'],['free','Бесплатные'],['past_due','Просрочено'],['canceled','Отменено']].map(([f,l]) => (
          <button key={f} onClick={() => setFilter(f)}
            data-testid={`filter-${f}`}
            className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-all ${filter === f ? 'bg-indigo-600 text-white' : 'text-gray-500 hover:bg-gray-100'}`}>
            {l}
          </button>
        ))}
        <span className="text-xs text-gray-400 ml-auto">{data?.total || 0} пользователей</span>
      </div>

      {loading && !data ? <LoadingState /> : (
        <div className="overflow-x-auto border border-gray-200 rounded-lg" data-testid="subscribers-table">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-400 border-b border-gray-100 bg-gray-50">
                <th className="py-2.5 px-4 font-medium">Пользователь</th>
                <th className="py-2.5 px-3 font-medium">Статус</th>
                <th className="py-2.5 px-3 font-medium">Сумма</th>
                <th className="py-2.5 px-3 font-medium">Метод</th>
                <th className="py-2.5 px-3 font-medium">Продление</th>
                <th className="py-2.5 px-3 font-medium">Последний платёж</th>
                <th className="py-2.5 px-3 font-medium">Регистрация</th>
                <th className="py-2.5 px-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {(data?.subscribers || []).map(s => (
                <tr key={s.user_id} className="border-b border-gray-50 hover:bg-gray-50/50 transition-colors">
                  <td className="py-2.5 px-4">
                    <div className="flex items-center gap-2">
                      {s.picture
                        ? <img src={s.picture} alt="" className="w-6 h-6 rounded-full" />
                        : <div className="w-6 h-6 rounded-full bg-gray-200 flex items-center justify-center text-[10px] font-bold text-gray-500">{(s.email || '?')[0].toUpperCase()}</div>}
                      <div>
                        <span className="text-sm text-gray-900">{s.email}</span>
                        {s.name && <span className="text-xs text-gray-400 ml-2">{s.name}</span>}
                      </div>
                    </div>
                  </td>
                  <td className="py-2.5 px-3"><StatusBadge status={s.plan_status} /></td>
                  <td className="py-2.5 px-3 text-gray-600 tabular-nums">{s.subscription?.amount != null ? `$${s.subscription.amount}` : '--'}</td>
                  <td className="py-2.5 px-3">
                    {s.last_payment?.payment_method === 'crypto'
                      ? <span className="text-[10px] font-bold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">USDC</span>
                      : s.last_payment ? <span className="text-[10px] text-gray-500">Карта</span> : <span className="text-gray-300">--</span>}
                  </td>
                  <td className="py-2.5 px-3 text-xs text-gray-500">{s.subscription?.current_period_end ? new Date(s.subscription.current_period_end).toLocaleDateString() : '--'}</td>
                  <td className="py-2.5 px-3 text-xs text-gray-500">{s.last_payment?.created_at ? new Date(s.last_payment.created_at).toLocaleDateString() : '--'}</td>
                  <td className="py-2.5 px-3 text-xs text-gray-400">{s.created_at ? new Date(s.created_at).toLocaleDateString() : '--'}</td>
                  <td className="py-2.5 px-3">
                    <button onClick={() => loadDetail(s.user_id)} data-testid={`view-subscriber-${s.user_id}`}
                      className="p-1 rounded hover:bg-gray-100 transition-colors"><Eye className="w-3.5 h-3.5 text-gray-400" /></button>
                  </td>
                </tr>
              ))}
              {(data?.subscribers || []).length === 0 && (
                <tr><td colSpan={8} className="py-8 text-center text-sm text-gray-400">Подписчики не найдены</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


/* ── Subscriber Detail ── */
function SubscriberDetail({ data, onBack, onRefresh }) {
  const [grantDays, setGrantDays] = useState(30);
  const [grantReason, setGrantReason] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const user = data?.user || {};
  const sub = data?.subscription;
  const payments = data?.payments || [];
  const events = data?.events || [];
  const access = data?.access || {};

  const doAction = async (action) => {
    setActionLoading(true);
    try {
      await fetch(`${API}/api/admin/billing/access/${user.user_id}/${action}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: grantReason || `Admin ${action}`, days: grantDays }),
      });
      onRefresh();
    } catch (e) { console.error(e); }
    setActionLoading(false);
  };

  return (
    <div className="space-y-6" data-testid="subscriber-detail">
      <button onClick={onBack} className="text-sm text-gray-500 hover:text-gray-700" data-testid="back-to-subscribers">← Назад к подписчикам</button>
      <div className="border border-gray-200 rounded-lg p-5 flex items-center gap-4">
        {user.picture
          ? <img src={user.picture} alt="" className="w-12 h-12 rounded-full" />
          : <div className="w-12 h-12 rounded-full bg-gray-200 flex items-center justify-center text-lg font-bold text-gray-500">{(user.email || '?')[0].toUpperCase()}</div>}
        <div className="flex-1">
          <h2 className="text-lg font-semibold text-gray-900">{user.name || user.email}</h2>
          <p className="text-sm text-gray-500">{user.email}</p>
          <div className="flex items-center gap-3 mt-1 text-[10px] text-gray-400">
            <span>Auth: {user.auth_provider || 'google'}</span>
            <span>Регистрация: {user.created_at ? new Date(user.created_at).toLocaleDateString() : '--'}</span>
            {user.stripe_customer_id && <span>Stripe: {user.stripe_customer_id}</span>}
          </div>
        </div>
        <StatusBadge status={user.plan_status} />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="border border-gray-200 rounded-lg p-5 space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Подписка</h3>
          {sub ? (
            <div className="space-y-1.5 text-xs">
              <InfoRow label="Статус" value={<StatusBadge status={sub.status} />} />
              <InfoRow label="Сумма" value={sub.amount != null ? `$${sub.amount}/мес` : '--'} />
              <InfoRow label="Метод" value={sub.payment_method || 'карта'} />
              <InfoRow label="Окончание периода" value={sub.current_period_end ? new Date(sub.current_period_end).toLocaleDateString() : '--'} />
              <InfoRow label="Stripe Sub ID" value={sub.stripe_subscription_id || '--'} />
              {sub.cancel_at_period_end && <InfoRow label="Отмена" value="В конце периода" />}
            </div>
          ) : <p className="text-xs text-gray-400">Нет подписки</p>}
        </div>
        <div className="border border-gray-200 rounded-lg p-5 space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Управление доступом</h3>
          <div className="space-y-1.5 text-xs">
            <InfoRow label="Доступ" value={access.has_access ? <span className="text-emerald-600 font-bold">ДА</span> : <span className="text-red-500 font-bold">НЕТ</span>} />
            <InfoRow label="План" value={access.plan_status || 'free'} />
            {access.override_status && <InfoRow label="Переопределение" value={access.override_status} />}
            {access.override_reason && <InfoRow label="Причина" value={access.override_reason} />}
          </div>
          <div className="pt-2 border-t border-gray-100 space-y-2">
            <div className="flex items-center gap-2">
              <input type="number" value={grantDays} onChange={e => setGrantDays(Number(e.target.value))} className="w-16 text-xs border border-gray-200 rounded px-2 py-1" />
              <span className="text-xs text-gray-400">дней</span>
              <input type="text" placeholder="Причина..." value={grantReason} onChange={e => setGrantReason(e.target.value)} className="flex-1 text-xs border border-gray-200 rounded px-2 py-1" />
            </div>
            <div className="flex gap-2">
              <button onClick={() => doAction('grant')} disabled={actionLoading} data-testid="grant-access-btn"
                className="text-xs px-3 py-1.5 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50">Выдать доступ</button>
              <button onClick={() => doAction('revoke')} disabled={actionLoading} data-testid="revoke-access-btn"
                className="text-xs px-3 py-1.5 bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:opacity-50">Отозвать доступ</button>
            </div>
          </div>
        </div>
      </div>
      <div className="border border-gray-200 rounded-lg p-5 space-y-3">
        <h3 className="text-sm font-semibold text-gray-900">История платежей</h3>
        {payments.length === 0 ? <p className="text-xs text-gray-400">Нет платежей</p> : (
          <div className="space-y-1">
            {payments.map((p, i) => (
              <div key={i} className="flex items-center justify-between text-xs py-1.5 border-b border-gray-50">
                <div className="flex items-center gap-2">
                  <StatusDot status={p.payment_status} />
                  <span className="text-gray-600">{p.payment_status}</span>
                  <span className={p.payment_method === 'crypto' ? 'text-blue-600 font-bold' : 'text-gray-400'}>{p.payment_method === 'crypto' ? 'USDC' : 'Карта'}</span>
                </div>
                <div className="flex items-center gap-3 text-gray-500">
                  <span className="font-medium">${p.amount || '--'}</span>
                  <span>{p.created_at ? new Date(p.created_at).toLocaleDateString() : ''}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      {events.length > 0 && (
        <div className="border border-gray-200 rounded-lg p-5 space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Биллинг-события</h3>
          <div className="space-y-1">
            {events.map((e, i) => (
              <div key={i} className="flex items-center justify-between text-xs py-1.5 border-b border-gray-50">
                <div className="flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full ${e.processed ? 'bg-emerald-400' : 'bg-red-400'}`} />
                  <span className="text-gray-700 font-mono">{e.type}</span>
                  <span className="text-gray-400">{e.source}</span>
                </div>
                <span className="text-gray-400">{e.created_at ? new Date(e.created_at).toLocaleString() : ''}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════════
   PAYMENTS TAB
   ══════════════════════════════════════════════════════════════════ */
function AccessTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    fetch(`${API}/api/admin/billing/subscribers?limit=100`)
      .then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(setData)
      .catch(e => console.error('AccessTab load error:', e))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4" data-testid="access-tab">
      <p className="text-xs text-gray-400">Ручное управление доступом. Все действия логируются во вкладке «События».</p>
      {loading && !data ? <LoadingState /> : (
        <div className="overflow-x-auto border border-gray-200 rounded-lg">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-400 border-b border-gray-100 bg-gray-50">
                <th className="py-2.5 px-4 font-medium">Пользователь</th>
                <th className="py-2.5 px-3 font-medium">План</th>
                <th className="py-2.5 px-3 font-medium">Доступ</th>
                <th className="py-2.5 px-3 font-medium">Действия</th>
              </tr>
            </thead>
            <tbody>
              {(data?.subscribers || []).map(s => (
                <tr key={s.user_id} className="border-b border-gray-50">
                  <td className="py-2.5 px-4 text-sm text-gray-700">{s.email}</td>
                  <td className="py-2.5 px-3"><StatusBadge status={s.plan_status} /></td>
                  <td className="py-2.5 px-3">
                    {s.plan_status === 'active'
                      ? <span className="text-emerald-600 text-xs font-bold">АКТИВЕН</span>
                      : <span className="text-gray-400 text-xs">НЕТ</span>}
                  </td>
                  <td className="py-2.5 px-3">
                    <div className="flex gap-1.5">
                      <AccessButton userId={s.user_id} action="grant" label="Выдать" color="emerald" onDone={load} />
                      <AccessButton userId={s.user_id} action="revoke" label="Отозвать" color="red" onDone={load} />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function AccessButton({ userId, action, label, color, onDone }) {
  const [loading, setLoading] = useState(false);
  const click = async () => {
    setLoading(true);
    await fetch(`${API}/api/admin/billing/access/${userId}/${action}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: `Admin ${action}`, days: 30 }),
    });
    onDone();
    setLoading(false);
  };
  const colors = color === 'emerald' ? 'text-emerald-600 border-emerald-200 hover:bg-emerald-50' : 'text-red-500 border-red-200 hover:bg-red-50';
  return (
    <button onClick={click} disabled={loading}
      className={`text-[10px] font-medium px-2 py-1 rounded border transition-all disabled:opacity-50 ${colors}`}>{label}</button>
  );
}


/* ── Shared Components ── */
function KpiCard({ label, value, icon: Icon, color = 'text-gray-900', large }) {
  return (
    <div className="border border-gray-200 rounded-lg p-4" data-testid={`kpi-${label.toLowerCase().replace(/\s+/g, '-')}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] text-gray-400 uppercase tracking-wider">{label}</p>
          <p className={`${large ? 'text-2xl' : 'text-lg'} font-bold ${color} mt-0.5`}>{value ?? '--'}</p>
        </div>
        {Icon && <Icon className="w-4 h-4 text-gray-300" />}
      </div>
    </div>
  );
}

function StatusBadge({ status }) {
  const styles = { active: 'text-emerald-600 bg-emerald-50', free: 'text-gray-500 bg-gray-100', past_due: 'text-amber-600 bg-amber-50', canceled: 'text-red-500 bg-red-50', paid: 'text-emerald-600 bg-emerald-50', succeeded: 'text-emerald-600 bg-emerald-50', failed: 'text-red-500 bg-red-50', initiated: 'text-gray-500 bg-gray-100' };
  const labels = { active: 'Активен', free: 'Бесплатный', past_due: 'Просрочен', canceled: 'Отменён', paid: 'Оплачено', succeeded: 'Успех', failed: 'Ошибка', initiated: 'Инициировано' };
  return <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${styles[status] || 'text-gray-500 bg-gray-100'}`} data-testid={`status-${status}`}>{labels[status] || status || 'free'}</span>;
}


// ═══════════════════════════════════════════════════════════════
// CRYPTO PAYMENTS TAB (NOWPayments)
// ═══════════════════════════════════════════════════════════════
function CryptoPaymentsTab() {
  const [stats, setStats] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [settings, setSettings] = useState({
    apiKey: '',
    ipnSecret: '',
    webhookUrl: ''
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchCryptoStats();
    fetchCryptoTransactions();
    fetchCryptoSettings();
  }, []);

  const fetchCryptoStats = async () => {
    try {
      const res = await fetch(`${API}/api/admin/billing/crypto/stats`);
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (e) {
      console.error('Failed to fetch crypto stats:', e);
    }
  };

  const fetchCryptoTransactions = async () => {
    try {
      const res = await fetch(`${API}/api/admin/billing/crypto/transactions`);
      if (res.ok) {
        const data = await res.json();
        setTransactions(data.transactions || []);
      }
    } catch (e) {
      console.error('Failed to fetch crypto transactions:', e);
    } finally {
      setLoading(false);
    }
  };

  const fetchCryptoSettings = async () => {
    try {
      const res = await fetch(`${API}/api/admin/billing/crypto/settings`);
      if (res.ok) {
        const data = await res.json();
        setSettings(data);
      }
    } catch (e) {
      console.error('Failed to fetch crypto settings:', e);
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/admin/billing/crypto/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      if (res.ok) {
        alert('✅ Настройки сохранены');
      } else {
        alert('❌ Ошибка сохранения');
      }
    } catch (e) {
      alert('❌ Ошибка сохранения: ' + e.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingState />;

  return (
    <div className="space-y-8">
      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard icon={DollarSign} label="Total Revenue" value={`$${stats?.totalRevenue || 0}`} color="#10b981" />
        <StatCard icon={CreditCard} label="Payments" value={stats?.totalPayments || 0} color="#6366f1" />
        <StatCard icon={Users} label="PRO Users" value={stats?.proUsers || 0} color="#f59e0b" />
        <StatCard icon={TrendingUp} label="MRR" value={`$${stats?.mrr || 0}`} color="#8b5cf6" />
      </div>

      {/* API Keys Settings */}
      <div className="bg-white border rounded-xl p-6" style={{ borderColor: c.border }}>
        <h3 className="text-lg font-bold mb-4 flex items-center gap-2" style={{ color: c.text }}>
          <Key size={20} style={{ color: c.accent }} />
          NOWPayments API Settings
        </h3>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: c.textSecondary }}>API Key</label>
            <input
              type="password"
              value={settings.apiKey}
              onChange={(e) => setSettings({ ...settings, apiKey: e.target.value })}
              placeholder="S5T82FH-NQD466D-..."
              className="w-full px-3 py-2 border rounded-lg text-sm"
              style={{ borderColor: c.border }}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: c.textSecondary }}>IPN Secret</label>
            <input
              type="password"
              value={settings.ipnSecret}
              onChange={(e) => setSettings({ ...settings, ipnSecret: e.target.value })}
              placeholder="cefc9da9-1774-..."
              className="w-full px-3 py-2 border rounded-lg text-sm"
              style={{ borderColor: c.border }}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: c.textSecondary }}>Webhook URL</label>
            <input
              type="text"
              value={settings.webhookUrl}
              onChange={(e) => setSettings({ ...settings, webhookUrl: e.target.value })}
              placeholder="https://your-domain.com/api/payments/webhook-wallet"
              className="w-full px-3 py-2 border rounded-lg text-sm"
              style={{ borderColor: c.border }}
            />
            <p className="text-xs mt-1" style={{ color: c.textMuted }}>
              Настройте этот URL в NOWPayments dashboard → Settings → IPN
            </p>
          </div>

          <button
            onClick={saveSettings}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-white text-sm font-medium transition-all"
            style={{ backgroundColor: saving ? c.textMuted : c.accent }}
          >
            {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            {saving ? 'Сохранение...' : 'Сохранить настройки'}
          </button>
        </div>
      </div>

      {/* Recent Transactions */}
      <div className="bg-white border rounded-xl p-6" style={{ borderColor: c.border }}>
        <h3 className="text-lg font-bold mb-4 flex items-center gap-2" style={{ color: c.text }}>
          <CreditCard size={20} style={{ color: c.accent }} />
          Recent Crypto Payments
        </h3>

        {transactions.length === 0 ? (
          <div className="text-center py-12 text-sm" style={{ color: c.textMuted }}>
            Нет платежей
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: `1px solid ${c.border}` }}>
                  <th className="text-left py-3 px-2" style={{ color: c.textSecondary }}>Payment ID</th>
                  <th className="text-left py-3 px-2" style={{ color: c.textSecondary }}>User</th>
                  <th className="text-left py-3 px-2" style={{ color: c.textSecondary }}>Amount</th>
                  <th className="text-left py-3 px-2" style={{ color: c.textSecondary }}>Currency</th>
                  <th className="text-left py-3 px-2" style={{ color: c.textSecondary }}>Status</th>
                  <th className="text-left py-3 px-2" style={{ color: c.textSecondary }}>Date</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((tx) => (
                  <tr key={tx.payment_id} style={{ borderBottom: `1px solid ${c.border}` }}>
                    <td className="py-3 px-2 font-mono text-xs" style={{ color: c.text }}>{tx.payment_id}</td>
                    <td className="py-3 px-2" style={{ color: c.text }}>{tx.order_id}</td>
                    <td className="py-3 px-2 font-bold" style={{ color: c.text }}>${tx.amount}</td>
                    <td className="py-3 px-2 uppercase" style={{ color: c.textSecondary }}>{tx.currency}</td>
                    <td className="py-3 px-2">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        tx.status === 'finished' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                      }`}>
                        {tx.status}
                      </span>
                    </td>
                    <td className="py-3 px-2 text-xs" style={{ color: c.textMuted }}>
                      {new Date(tx.processed_at).toLocaleDateString('ru-RU')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}


function StatusDot({ status }) {
  const color = ['paid', 'succeeded'].includes(status) ? 'bg-emerald-400' : status === 'failed' ? 'bg-red-400' : 'bg-gray-300';
  return <span className={`w-1.5 h-1.5 rounded-full ${color}`} />;
}

function InfoRow({ label, value }) {
  return <div className="flex items-center justify-between py-1"><span className="text-gray-400">{label}</span><span className="text-gray-700">{value}</span></div>;
}

function LoadingState() {
  return <div className="flex items-center justify-center h-32 text-gray-400 text-sm"><RefreshCw className="w-4 h-4 animate-spin mr-2" /> Загрузка...</div>;
}


function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-500 uppercase tracking-wide">{label}</span>
        <Icon size={16} style={{ color }} />
      </div>
      <div className="text-2xl font-bold" style={{ color }}>{value}</div>
    </div>
  );
}
