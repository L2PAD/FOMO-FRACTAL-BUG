/**
 * MiniApp Admin Console v2 — Money Dashboard.
 * Goal: "за 3 секунды понять где теряются деньги"
 */
import { useState, useEffect, useCallback } from 'react';
import {
  Smartphone, BarChart3, Zap, TrendingUp,
  DollarSign, Target, Activity, Users,
  ArrowDown, RefreshCw, Loader2,
  Shield, AlertTriangle, Eye, MousePointer, CreditCard,
  Bell, Settings, ArrowUpDown, Check, X, Mail, Trash2,
} from 'lucide-react';
import { AdminLayout } from '../../components/admin/PlatformAdminLayout';

const API = process.env.REACT_APP_BACKEND_URL;

const TABS = [
  { id: 'overview', label: 'Обзор', icon: BarChart3 },
  { id: 'signals', label: 'Сигналы', icon: Zap },
  { id: 'edge', label: 'Эдж', icon: TrendingUp },
  { id: 'users', label: 'Users', icon: Users },
  { id: 'billing', label: 'Billing', icon: CreditCard },
  { id: 'alerts', label: 'Alerts', icon: Bell },
  { id: 'subscribers', label: 'Subscribers', icon: Mail },
  { id: 'settings', label: 'Settings', icon: Settings },
];

const c = {
  text: '#0f172a',
  textSecondary: '#475569',
  textMuted: '#94a3b8',
  accent: '#6366f1',
  surface: '#f8fafc',
  border: '#e2e8f0',
  green: '#10b981',
  red: '#ef4444',
  amber: '#f59e0b',
};

export default function MiniAppAdminPage() {
  const params = new URLSearchParams(window.location.search);
  const initialTab = params.get('tab') || 'overview';
  const [activeTab, setActiveTab] = useState(initialTab);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    const url = new URL(window.location);
    if (tab === 'overview') url.searchParams.delete('tab');
    else url.searchParams.set('tab', tab);
    window.history.replaceState({}, '', url);
  };

  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6" data-testid="miniapp-admin-page">
        <div className="mb-8">
          <h1 className="text-2xl font-bold flex items-center gap-3" style={{ color: c.text }}>
            <Smartphone size={28} style={{ color: c.accent }} />
            Мини-апка
          </h1>
          <p className="text-sm mt-1" style={{ color: c.textSecondary }}>
            Money Dashboard — управление прибылью
          </p>
        </div>

        <div className="flex gap-1 mb-8 p-1 rounded-xl overflow-x-auto" style={{ backgroundColor: c.surface }}>
          {TABS.map(tab => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                data-testid={`miniapp-tab-${tab.id}`}
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

        {activeTab === 'overview' && <OverviewTab />}
        {activeTab === 'signals' && <SignalsTab />}
        {activeTab === 'edge' && <EdgeTab />}
        {activeTab === 'users' && <UsersTab />}
        {activeTab === 'billing' && <BillingTab />}
        {activeTab === 'alerts' && <AlertsTab />}
        {activeTab === 'subscribers' && <SubscribersTab />}
        {activeTab === 'settings' && <SettingsTab />}
      </div>
    </AdminLayout>
  );
}


/* ═══════════════════════════════════════════════════
   KPI CARD
   ═══════════════════════════════════════════════════ */
function KpiCard({ label, value, icon: Icon, color = '', large = false, sub = '' }) {
  return (
    <div className="border border-gray-200 rounded-lg p-4" data-testid={`kpi-${label.replace(/\s/g, '-').toLowerCase()}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium" style={{ color: c.textMuted }}>{label}</span>
        {Icon && <Icon size={14} className={color || 'text-gray-400'} />}
      </div>
      <div className={`font-bold ${large ? 'text-2xl' : 'text-xl'} ${color || ''}`} style={{ color: color ? undefined : c.text }}>
        {value ?? '—'}
      </div>
      {sub && <div className="text-xs mt-1" style={{ color: c.textMuted }}>{sub}</div>}
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
    </div>
  );
}


/* ═══════════════════════════════════════════════════
   OVERVIEW TAB v2 — Money Dashboard
   ═══════════════════════════════════════════════════ */
function OverviewTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    fetch(`${API}/api/admin/miniapp/overview`)
      .then(r => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading && !data) return <LoadingState />;
  const k = data || {};
  const f = k.funnel || {};

  return (
    <div className="space-y-8" data-testid="miniapp-overview">
      {/* Refresh */}
      <div className="flex justify-end">
        <button onClick={load} className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700">
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Обновить
        </button>
      </div>

      {/* BLOCK 1 — MONEY (top priority) */}
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: c.textMuted }}>
          Деньги
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard label="Доход" value={`$${k.revenue || 0}`} icon={DollarSign} color="text-emerald-600" large />
          <KpiCard label="Конверсия" value={`${k.conversion || 0}%`} icon={TrendingUp} color="text-blue-600" large />
          <KpiCard label="Платные" value={k.paid_users || 0} icon={CreditCard} color="text-emerald-600" large />
          <KpiCard label="$ / алерт" value={`$${k.revenue_per_alert || 0}`} icon={DollarSign} color="text-amber-600" large />
        </div>
      </div>

      {/* BLOCK 2 — FUNNEL (center, most important) */}
      <div className="border border-gray-200 rounded-xl p-6" data-testid="miniapp-funnel">
        <h3 className="text-sm font-semibold mb-5" style={{ color: c.text }}>Воронка конверсии</h3>
        <FunnelFlow funnel={f} />
      </div>

      {/* BLOCK 3 — A/B Testing */}
      {k.ab_stats && Object.keys(k.ab_stats).length > 0 && (
        <div className="border border-gray-200 rounded-xl p-6" data-testid="miniapp-ab-stats">
          <h3 className="text-sm font-semibold mb-4" style={{ color: c.text }}>A/B тестирование алертов</h3>
          <ABTable stats={k.ab_stats} />
        </div>
      )}

      {/* BLOCK 4 — MODEL */}
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: c.textMuted }}>
          Модель
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard label="Точность" value={k.accuracy ? `${k.accuracy}%` : '—'} icon={Target} color="text-blue-600" />
          <KpiCard label="Coverage" value={k.coverage ? `${k.coverage}%` : '—'} icon={Shield} />
          <KpiCard label="Catastrophic" value={k.catastrophic || 0} icon={AlertTriangle} color="text-red-500" />
          <KpiCard label="Активные эджи" value={k.active_edges || 0} icon={TrendingUp} color="text-emerald-600" />
        </div>
      </div>

      {/* Revenue chart */}
      <BarChartSimple title="Доход по дням" data={k.revenue_daily} color="#10b981" valueKey="revenue" prefix="$" />

      {/* Scheduler */}
      <SchedulerStatus />
    </div>
  );
}


/* ═══════════════════════════════════════════════════
   FUNNEL FLOW — horizontal visual with arrows
   ═══════════════════════════════════════════════════ */
function FunnelFlow({ funnel }) {
  const steps = [
    { key: 'alerts', label: 'Алерты', icon: Activity, color: '#6366f1' },
    { key: 'opened', label: 'Открытия', icon: Eye, color: '#818cf8' },
    { key: 'edge_viewed', label: 'Эдж', icon: TrendingUp, color: '#a78bfa' },
    { key: 'upgrade_clicked', label: 'Клик', icon: MousePointer, color: '#c084fc' },
    { key: 'paid', label: 'Оплата', icon: CreditCard, color: '#10b981' },
  ];

  const rates = funnel.rates || {};
  const rateKeys = ['open_rate', 'edge_rate', 'click_rate', 'pay_rate'];

  return (
    <div className="flex flex-col gap-3">
      {/* Desktop horizontal */}
      <div className="hidden md:flex items-stretch gap-0">
        {steps.map((step, i) => {
          const val = funnel[step.key] ?? 0;
          const Icon = step.icon;
          const rate = i > 0 ? (rates[rateKeys[i - 1]] || 0) : null;
          return (
            <div key={step.key} className="flex items-center" style={{ flex: 1 }}>
              {i > 0 && (
                <div className="flex flex-col items-center px-2 shrink-0" style={{ minWidth: '50px' }}>
                  <ArrowDown size={16} className="text-gray-300 rotate-[-90deg]" />
                  <span
                    className="text-xs font-bold mt-0.5"
                    data-testid={`funnel-rate-${rateKeys[i - 1]}`}
                    style={{ color: rate > 30 ? c.green : rate > 10 ? c.amber : c.red }}
                  >
                    {rate}%
                  </span>
                </div>
              )}
              <div
                data-testid={`funnel-step-${step.key}`}
                className="flex-1 rounded-xl p-4 text-center border"
                style={{ borderColor: step.color + '40', backgroundColor: step.color + '08' }}
              >
                <Icon size={18} style={{ color: step.color, margin: '0 auto 6px' }} />
                <div className="text-2xl font-bold" style={{ color: c.text }}>{val}</div>
                <div className="text-xs font-medium mt-1" style={{ color: c.textSecondary }}>{step.label}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Mobile vertical */}
      <div className="md:hidden flex flex-col gap-1">
        {steps.map((step, i) => {
          const val = funnel[step.key] ?? 0;
          const Icon = step.icon;
          const rate = i > 0 ? (rates[rateKeys[i - 1]] || 0) : null;
          return (
            <div key={step.key}>
              {i > 0 && (
                <div className="flex items-center justify-center gap-2 py-1">
                  <ArrowDown size={14} className="text-gray-300" />
                  <span
                    className="text-xs font-bold"
                    style={{ color: rate > 30 ? c.green : rate > 10 ? c.amber : c.red }}
                  >
                    {rate}%
                  </span>
                </div>
              )}
              <div
                className="flex items-center gap-4 rounded-lg p-3 border"
                style={{ borderColor: step.color + '30', backgroundColor: step.color + '06' }}
              >
                <Icon size={16} style={{ color: step.color }} />
                <div className="flex-1">
                  <div className="text-xs font-medium" style={{ color: c.textSecondary }}>{step.label}</div>
                </div>
                <div className="text-lg font-bold" style={{ color: c.text }}>{val}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════════════
   A/B TABLE — sorted by $/alert
   ═══════════════════════════════════════════════════ */
function ABTable({ stats }) {
  const variants = ['A', 'B', 'C', 'D'];
  const labels = { A: 'Urgency', B: 'Loss', C: 'Performance', D: 'Combo' };

  // Sort by revenue_per_alert descending
  const sorted = [...variants].sort((a, b) => {
    const ra = (stats[b] || {}).revenue_per_alert || 0;
    const rb = (stats[a] || {}).revenue_per_alert || 0;
    return ra - rb;
  });

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid="ab-table">
        <thead>
          <tr className="bg-gray-50">
            <th className="px-3 py-2.5 text-left text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>Вариант</th>
            <th className="px-3 py-2.5 text-right text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>Отправлено</th>
            <th className="px-3 py-2.5 text-right text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>Открыто</th>
            <th className="px-3 py-2.5 text-right text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>CTR</th>
            <th className="px-3 py-2.5 text-right text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>Эдж</th>
            <th className="px-3 py-2.5 text-right text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>Клик</th>
            <th className="px-3 py-2.5 text-right text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>Оплата</th>
            <th className="px-3 py-2.5 text-right text-xs font-medium uppercase tracking-wider" style={{ color: c.amber }}>$/алерт</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((v, i) => {
            const s = stats[v] || {};
            return (
              <tr key={v} className="border-t border-gray-100 hover:bg-gray-50" data-testid={`ab-row-${v}`}>
                <td className="px-3 py-3">
                  <span className="font-bold text-sm" style={{ color: c.accent }}>{v}</span>
                  <span className="text-xs text-gray-400 ml-2">{labels[v]}</span>
                </td>
                <td className="px-3 py-3 text-right font-mono text-xs">{s.sent || 0}</td>
                <td className="px-3 py-3 text-right font-mono text-xs">{s.opened || 0}</td>
                <td className="px-3 py-3 text-right font-mono text-xs font-medium" style={{ color: (s.ctr || 0) > 0 ? c.green : c.textMuted }}>
                  {s.ctr || 0}%
                </td>
                <td className="px-3 py-3 text-right font-mono text-xs">{s.edge_viewed || 0}</td>
                <td className="px-3 py-3 text-right font-mono text-xs">{s.clicks || 0}</td>
                <td className="px-3 py-3 text-right font-mono text-xs font-medium" style={{ color: (s.paid || 0) > 0 ? c.green : c.textMuted }}>
                  {s.paid || 0}
                </td>
                <td className="px-3 py-3 text-right font-mono text-xs font-bold" style={{ color: (s.revenue_per_alert || 0) > 0 ? c.green : c.textMuted }}>
                  ${(s.revenue_per_alert || 0).toFixed(4)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}


/* ═══════════════════════════════════════════════════
   SIGNALS TAB v2 — Money Connection
   ═══════════════════════════════════════════════════ */
function SignalsTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ asset: '', source: '', highOnly: false });

  const load = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filters.asset) params.set('asset', filters.asset);
    if (filters.source) params.set('source', filters.source);
    if (filters.highOnly) params.set('high_only', 'true');
    fetch(`${API}/api/admin/miniapp/signals?${params}`)
      .then(r => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  const k = data?.kpis || {};

  return (
    <div className="space-y-6" data-testid="miniapp-signals">
      {/* KPIs row 1 — counts */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <KpiCard label="Сигналы всего" value={k.total} icon={Zap} />
        <KpiCard label="Сильные" value={k.high_priority} icon={AlertTriangle} color="text-amber-600" />
        <KpiCard label="С эджем" value={k.with_edge} icon={TrendingUp} color="text-emerald-600" />
        <KpiCard label="С алертом" value={k.with_alert} icon={Activity} color="text-indigo-600" />
        <KpiCard label="С доходом" value={k.with_revenue} icon={DollarSign} color="text-emerald-600" />
      </div>

      {/* KPIs row 2 — money connection rates */}
      <div className="grid grid-cols-3 gap-4">
        <div className="border border-gray-200 rounded-lg p-4 text-center" data-testid="kpi-signal-edge-pct">
          <div className="text-xs font-medium mb-1" style={{ color: c.textMuted }}>Сигнал &rarr; Эдж</div>
          <div className="text-2xl font-bold" style={{ color: (k.edge_pct || 0) > 0 ? c.green : c.textMuted }}>{k.edge_pct || 0}%</div>
        </div>
        <div className="border border-gray-200 rounded-lg p-4 text-center" data-testid="kpi-signal-alert-pct">
          <div className="text-xs font-medium mb-1" style={{ color: c.textMuted }}>Сигнал &rarr; Алерт</div>
          <div className="text-2xl font-bold" style={{ color: (k.alert_pct || 0) > 0 ? c.amber : c.textMuted }}>{k.alert_pct || 0}%</div>
        </div>
        <div className="border border-gray-200 rounded-lg p-4 text-center" data-testid="kpi-signal-revenue-pct">
          <div className="text-xs font-medium mb-1" style={{ color: c.textMuted }}>Сигнал &rarr; Деньги</div>
          <div className="text-2xl font-bold" style={{ color: (k.revenue_pct || 0) > 0 ? c.green : c.textMuted }}>{k.revenue_pct || 0}%</div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 items-center flex-wrap">
        <select
          data-testid="signal-filter-asset"
          value={filters.asset}
          onChange={e => setFilters(f => ({ ...f, asset: e.target.value }))}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
          style={{ color: c.text }}
        >
          <option value="">Все активы</option>
          <option value="BTC">BTC</option>
          <option value="ETH">ETH</option>
          <option value="SOL">SOL</option>
        </select>
        <select
          data-testid="signal-filter-source"
          value={filters.source}
          onChange={e => setFilters(f => ({ ...f, source: e.target.value }))}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
          style={{ color: c.text }}
        >
          <option value="">Все источники</option>
          <option value="exchange">Exchange</option>
          <option value="onchain">On-chain</option>
          <option value="sentiment">Sentiment</option>
          <option value="twitter">Twitter</option>
          <option value="ml">ML</option>
        </select>
        <label className="flex items-center gap-2 text-sm" style={{ color: c.textSecondary }}>
          <input type="checkbox" checked={filters.highOnly} onChange={e => setFilters(f => ({ ...f, highOnly: e.target.checked }))} />
          Только сильные
        </label>
        <button onClick={load} className="ml-auto flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700">
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Обновить
        </button>
      </div>

      {/* Signals Table */}
      {loading && !data ? <LoadingState /> : (
        <div className="border border-gray-200 rounded-lg overflow-hidden" data-testid="signals-table">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left">
                <th className="px-4 py-3 font-medium text-xs uppercase tracking-wider" style={{ color: c.textMuted }}>Время</th>
                <th className="px-4 py-3 font-medium text-xs uppercase tracking-wider" style={{ color: c.textMuted }}>Актив</th>
                <th className="px-4 py-3 font-medium text-xs uppercase tracking-wider" style={{ color: c.textMuted }}>Источник</th>
                <th className="px-4 py-3 font-medium text-xs uppercase tracking-wider" style={{ color: c.textMuted }}>Тип</th>
                <th className="px-4 py-3 font-medium text-xs uppercase tracking-wider" style={{ color: c.textMuted }}>Направление</th>
                <th className="px-4 py-3 font-medium text-xs uppercase tracking-wider" style={{ color: c.textMuted }}>Сила</th>
                <th className="px-4 py-3 font-medium text-xs uppercase tracking-wider" style={{ color: c.textMuted }}>Эдж</th>
                <th className="px-4 py-3 font-medium text-xs uppercase tracking-wider" style={{ color: c.textMuted }}>Алерт</th>
                <th className="px-4 py-3 font-medium text-xs uppercase tracking-wider" style={{ color: c.amber }}>Деньги</th>
              </tr>
            </thead>
            <tbody>
              {(data?.signals || []).map((s, i) => (
                <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-3 text-xs font-mono" style={{ color: c.textMuted }}>{formatTime(s.timestamp)}</td>
                  <td className="px-4 py-3 font-medium" style={{ color: c.text }}>{s.asset}</td>
                  <td className="px-4 py-3"><SourceBadge source={s.source} /></td>
                  <td className="px-4 py-3 text-xs" style={{ color: c.textSecondary }}>{s.type || '—'}</td>
                  <td className="px-4 py-3"><DirectionBadge dir={s.direction} /></td>
                  <td className="px-4 py-3 text-xs font-mono" style={{ color: c.textSecondary }}>{s.strength || '—'}</td>
                  <td className="px-4 py-3">{s.has_edge ? <span className="text-emerald-600 text-xs font-medium">YES</span> : <span className="text-gray-300 text-xs">—</span>}</td>
                  <td className="px-4 py-3">{s.has_alert ? <span className="text-indigo-600 text-xs font-medium">YES</span> : <span className="text-gray-300 text-xs">—</span>}</td>
                  <td className="px-4 py-3">{s.has_revenue ? <span className="text-emerald-600 text-xs font-bold">$</span> : <span className="text-gray-300 text-xs">—</span>}</td>
                </tr>
              ))}
              {(!data?.signals || data.signals.length === 0) && (
                <tr><td colSpan={9} className="px-4 py-8 text-center text-sm" style={{ color: c.textMuted }}>Нет сигналов</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════════════
   EDGE TAB v2 — Money Integration
   ═══════════════════════════════════════════════════ */
function EdgeTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    fetch(`${API}/api/admin/miniapp/edges`)
      .then(r => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const k = data?.kpis || {};

  return (
    <div className="space-y-6" data-testid="miniapp-edge">
      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
        <KpiCard label="Активные" value={k.active} icon={TrendingUp} color="text-emerald-600" />
        <KpiCard label="ELITE" value={k.elite} icon={Target} color="text-red-500" />
        <KpiCard label="LIVE" value={k.live} icon={Activity} color="text-amber-600" />
        <KpiCard label="STRONG" value={k.strong} icon={Zap} color="text-blue-600" />
        <KpiCard label="Просмотры" value={k.total_views} icon={Eye} />
        <KpiCard label="Доход" value={`$${k.total_revenue || 0}`} icon={DollarSign} color="text-emerald-600" />
      </div>

      {/* Top Edges by Revenue */}
      {data?.top_by_revenue && data.top_by_revenue.length > 0 && (
        <div className="border border-gray-200 rounded-xl p-5" data-testid="top-edges-revenue">
          <h3 className="text-sm font-semibold mb-3" style={{ color: c.text }}>Топ эджи по доходу</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {data.top_by_revenue.map((e, i) => (
              <div key={i} className="border border-gray-100 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold text-sm" style={{ color: c.text }}>{e.asset}</span>
                  <PriorityBadge label={e.priorityLabel} />
                </div>
                <div className="text-xs truncate mb-2" style={{ color: c.textSecondary }}>{e.question}</div>
                <div className="flex gap-4 text-xs">
                  <div><span style={{ color: c.textMuted }}>Edge: </span><span className="font-bold" style={{ color: e.edge > 0 ? c.green : c.red }}>{(e.edge * 100).toFixed(1)}%</span></div>
                  <div><span style={{ color: c.textMuted }}>Views: </span><span className="font-medium">{e.views}</span></div>
                  <div><span style={{ color: c.textMuted }}>Rev: </span><span className="font-bold" style={{ color: c.green }}>${e.revenue}</span></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Refresh */}
      <div className="flex justify-end">
        <button onClick={load} className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700">
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Обновить
        </button>
      </div>

      {/* Edge Table with Money columns */}
      {loading && !data ? <LoadingState /> : (
        <div className="border border-gray-200 rounded-lg overflow-hidden" data-testid="edges-table">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left">
                <th className="px-3 py-3 font-medium text-xs uppercase tracking-wider" style={{ color: c.textMuted }}>Актив</th>
                <th className="px-3 py-3 font-medium text-xs uppercase tracking-wider" style={{ color: c.textMuted }}>Вопрос</th>
                <th className="px-3 py-3 font-medium text-xs uppercase tracking-wider" style={{ color: c.textMuted }}>Market</th>
                <th className="px-3 py-3 font-medium text-xs uppercase tracking-wider" style={{ color: c.textMuted }}>Model</th>
                <th className="px-3 py-3 font-medium text-xs uppercase tracking-wider" style={{ color: c.textMuted }}>Edge</th>
                <th className="px-3 py-3 font-medium text-xs uppercase tracking-wider" style={{ color: c.textMuted }}>Priority</th>
                <th className="px-3 py-3 font-medium text-xs uppercase tracking-wider" style={{ color: c.textMuted }}>Label</th>
                <th className="px-3 py-3 font-medium text-xs uppercase tracking-wider" style={{ color: c.textMuted }}>Просмотры</th>
                <th className="px-3 py-3 font-medium text-xs uppercase tracking-wider" style={{ color: c.textMuted }}>Клики</th>
                <th className="px-3 py-3 font-medium text-xs uppercase tracking-wider" style={{ color: c.textMuted }}>Оплаты</th>
                <th className="px-3 py-3 font-medium text-xs uppercase tracking-wider" style={{ color: c.amber }}>Доход</th>
              </tr>
            </thead>
            <tbody>
              {(data?.edges || []).map((e, i) => (
                <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-3 py-3 font-medium" style={{ color: c.text }}>{e.asset}</td>
                  <td className="px-3 py-3 text-xs max-w-[180px] truncate" style={{ color: c.textSecondary }}>{e.question}</td>
                  <td className="px-3 py-3 text-xs font-mono">{Math.round(e.marketProbability * 100)}%</td>
                  <td className="px-3 py-3 text-xs font-mono">{Math.round(e.modelProbability * 100)}%</td>
                  <td className="px-3 py-3 font-mono font-bold" style={{ color: e.edge > 0 ? '#10b981' : '#ef4444' }}>
                    {e.edge > 0 ? '+' : ''}{(e.edge * 100).toFixed(1)}%
                  </td>
                  <td className="px-3 py-3 text-xs font-mono font-medium" style={{ color: c.accent }}>{e.priorityScore?.toFixed(3)}</td>
                  <td className="px-3 py-3"><PriorityBadge label={e.priorityLabel} /></td>
                  <td className="px-3 py-3 text-xs font-mono">{e.views || 0}</td>
                  <td className="px-3 py-3 text-xs font-mono">{e.clicks || 0}</td>
                  <td className="px-3 py-3 text-xs font-mono font-medium" style={{ color: (e.payments || 0) > 0 ? c.green : c.textMuted }}>{e.payments || 0}</td>
                  <td className="px-3 py-3 text-xs font-mono font-bold" style={{ color: (e.revenue || 0) > 0 ? c.green : c.textMuted }}>${e.revenue || 0}</td>
                </tr>
              ))}
              {(!data?.edges || data.edges.length === 0) && (
                <tr><td colSpan={11} className="px-4 py-8 text-center text-sm" style={{ color: c.textMuted }}>Нет активных эджей</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Priority distribution */}
      {data?.priority_distribution && (
        <div className="border border-gray-200 rounded-lg p-5" data-testid="priority-dist">
          <h3 className="text-sm font-semibold mb-3" style={{ color: c.text }}>Распределение приоритетов</h3>
          <div className="flex items-end gap-1 h-16">
            {Object.entries(data.priority_distribution).map(([label, count]) => {
              const max = Math.max(...Object.values(data.priority_distribution), 1);
              const h = Math.max(count / max * 100, 8);
              const colors = {
                'ELITE EDGE': '#ef4444',
                'LIVE EDGE': '#f59e0b',
                'STRONG EDGE': '#6366f1',
                'WATCHING': '#94a3b8',
                'LOW PRIORITY': '#d1d5db',
              };
              return (
                <div key={label} className="flex-1 flex flex-col items-center gap-1">
                  <div className="w-full rounded-t" style={{ height: `${h}%`, backgroundColor: colors[label] || '#d1d5db' }} title={`${label}: ${count}`} />
                  <span className="text-[9px] font-medium text-center" style={{ color: c.textMuted }}>{label.split(' ')[0]}</span>
                  <span className="text-xs font-bold" style={{ color: c.text }}>{count}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════════════
   SMALL COMPONENTS
   ═══════════════════════════════════════════════════ */

function BarChartSimple({ title, data, color = '#6366f1', valueKey = 'value', prefix = '' }) {
  if (!data || data.length === 0) return null;
  return (
    <div className="border border-gray-200 rounded-lg p-5">
      <h3 className="text-sm font-semibold mb-3" style={{ color: c.text }}>{title}</h3>
      <div className="flex items-end gap-0.5 h-24">
        {data.map((d, i) => {
          const max = Math.max(...data.map(x => x[valueKey] || 0), 1);
          const h = Math.max((d[valueKey] || 0) / max * 100, 2);
          return (
            <div key={i} className="flex-1 rounded-t-sm opacity-80 hover:opacity-100 transition-opacity cursor-default"
                 style={{ height: `${h}%`, backgroundColor: color }} title={`${d.date || d.label}: ${prefix}${d[valueKey]}`} />
          );
        })}
      </div>
    </div>
  );
}

function SchedulerStatus() {
  const [status, setStatus] = useState(null);
  useEffect(() => {
    fetch(`${API}/api/miniapp/scheduler/status`)
      .then(r => r.json())
      .then(setStatus)
      .catch(() => {});
  }, []);

  if (!status) return null;
  return (
    <div className="border border-gray-200 rounded-lg p-4" data-testid="scheduler-status">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold" style={{ color: c.text }}>Scheduler</h3>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${status.running ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}`}>
          {status.running ? 'Active' : 'Stopped'}
        </span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3 text-xs" style={{ color: c.textSecondary }}>
        <div>Ingest: {status.ingestCount || 0} runs</div>
        <div>Digest: {status.digestCount || 0} runs</div>
        <div>Interval: {status.ingestIntervalMinutes}min</div>
        <div>Digest: {status.digestHourUtc}:00 UTC</div>
      </div>
      {status.lastIngest && <div className="text-xs mt-2" style={{ color: c.textMuted }}>Last ingest: {formatTime(status.lastIngest)}</div>}
    </div>
  );
}

function SourceBadge({ source }) {
  const colors = {
    exchange: 'bg-blue-50 text-blue-700',
    onchain: 'bg-emerald-50 text-emerald-700',
    sentiment: 'bg-purple-50 text-purple-700',
    twitter: 'bg-cyan-50 text-cyan-700',
    ml: 'bg-amber-50 text-amber-700',
  };
  return <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${colors[source] || 'bg-gray-50 text-gray-600'}`}>{source}</span>;
}

function DirectionBadge({ dir }) {
  if (!dir) return <span className="text-xs text-gray-300">—</span>;
  const up = dir.toUpperCase().includes('BULL') || dir.toUpperCase() === 'BUY';
  const down = dir.toUpperCase().includes('BEAR') || dir.toUpperCase() === 'SELL';
  const color = up ? 'text-emerald-600' : down ? 'text-red-500' : 'text-gray-500';
  return <span className={`text-xs font-medium ${color}`}>{dir}</span>;
}

function PriorityBadge({ label }) {
  const colors = {
    'ELITE EDGE': 'bg-red-50 text-red-700',
    'LIVE EDGE': 'bg-amber-50 text-amber-700',
    'STRONG EDGE': 'bg-indigo-50 text-indigo-700',
    'WATCHING': 'bg-gray-50 text-gray-600',
    'LOW PRIORITY': 'bg-gray-50 text-gray-400',
  };
  return <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${colors[label] || 'bg-gray-50 text-gray-500'}`}>{label}</span>;
}

function formatTime(ts) {
  if (!ts) return '—';
  try {
    const d = new Date(ts);
    return d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch {
    return ts;
  }
}


/* ═══════════════════════════════════════════════════
   USERS TAB — Who brings money?
   ═══════════════════════════════════════════════════ */
function UsersTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ status: '', variant: '', active_only: '', has_revenue: '' });
  const [sortBy, setSortBy] = useState('revenue');
  const [sortDir, setSortDir] = useState('desc');

  const load = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filters.status) params.set('status', filters.status);
    if (filters.variant) params.set('variant', filters.variant);
    if (filters.active_only) params.set('active_only', 'true');
    if (filters.has_revenue) params.set('has_revenue', 'true');
    params.set('sort_by', sortBy);
    params.set('sort_dir', sortDir);
    fetch(`${API}/api/admin/miniapp/users?${params}`)
      .then(r => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [filters, sortBy, sortDir]);

  useEffect(() => { load(); }, [load]);

  const k = data?.kpis || {};

  const toggleSort = (field) => {
    if (sortBy === field) setSortDir(d => d === 'desc' ? 'asc' : 'desc');
    else { setSortBy(field); setSortDir('desc'); }
  };

  const SortHeader = ({ field, label }) => (
    <th className="px-3 py-2.5 text-right text-xs font-medium uppercase tracking-wider cursor-pointer hover:text-indigo-500"
      style={{ color: sortBy === field ? c.accent : c.textMuted }}
      onClick={() => toggleSort(field)}
    >
      <span className="flex items-center justify-end gap-1">
        {label} <ArrowUpDown size={10} />
      </span>
    </th>
  );

  return (
    <div className="space-y-6" data-testid="miniapp-users">
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
        <KpiCard label="Всего" value={k.total} icon={Users} />
        <KpiCard label="Активные 24ч" value={k.active_24h} icon={Activity} color="text-blue-600" />
        <KpiCard label="Платные" value={k.paid} icon={CreditCard} color="text-emerald-600" />
        <KpiCard label="Конверсия" value={`${k.conversion || 0}%`} icon={TrendingUp} color="text-blue-600" />
        <KpiCard label="Google Linked" value={`${k.linked_pct || 0}%`} icon={Shield} color="text-emerald-600" />
        <KpiCard label="TG Only" value={`${k.tg_only_pct || 0}%`} icon={AlertTriangle} color="text-amber-600" />
      </div>

      {/* Filters */}
      <div className="flex gap-3 items-center flex-wrap">
        <select data-testid="users-filter-status" value={filters.status} onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm" style={{ color: c.text }}>
          <option value="">Все статусы</option>
          <option value="paid">Paid</option>
          <option value="linked">Linked</option>
          <option value="telegram">Telegram</option>
        </select>
        <select data-testid="users-filter-variant" value={filters.variant} onChange={e => setFilters(f => ({ ...f, variant: e.target.value }))}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm" style={{ color: c.text }}>
          <option value="">Все варианты</option>
          <option value="A">A — Urgency</option>
          <option value="B">B — Loss</option>
          <option value="C">C — Performance</option>
          <option value="D">D — Combo</option>
        </select>
        <label className="flex items-center gap-2 text-sm" style={{ color: c.textSecondary }}>
          <input type="checkbox" checked={!!filters.active_only} onChange={e => setFilters(f => ({ ...f, active_only: e.target.checked ? 'true' : '' }))} />
          Active 24h
        </label>
        <label className="flex items-center gap-2 text-sm" style={{ color: c.textSecondary }}>
          <input type="checkbox" checked={!!filters.has_revenue} onChange={e => setFilters(f => ({ ...f, has_revenue: e.target.checked ? 'true' : '' }))} />
          Has Revenue
        </label>
        <button onClick={load} className="ml-auto flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700">
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Обновить
        </button>
      </div>

      {/* Table */}
      {loading && !data ? <LoadingState /> : (
        <div className="border border-gray-200 rounded-lg overflow-x-auto" data-testid="users-table">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="px-3 py-2.5 text-left text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>User</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>Статус</th>
                <th className="px-3 py-2.5 text-center text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>A/B</th>
                <SortHeader field="alerts_received" label="Алерты" />
                <SortHeader field="alerts_opened" label="Открыто" />
                <SortHeader field="edge_views" label="Эдж" />
                <SortHeader field="clicks" label="Клики" />
                <SortHeader field="payments" label="Оплаты" />
                <SortHeader field="revenue" label="Доход" />
              </tr>
            </thead>
            <tbody>
              {(data?.users || []).map((u, i) => (
                <tr key={i} className="border-t border-gray-100 hover:bg-gray-50" data-testid={`user-row-${i}`}>
                  <td className="px-3 py-3">
                    <div className="font-medium text-sm" style={{ color: c.text }}>{u.user}</div>
                    <div className="text-xs" style={{ color: c.textMuted }}>{u.email || u.telegram_id}</div>
                  </td>
                  <td className="px-3 py-3"><StatusBadge status={u.status} /></td>
                  <td className="px-3 py-3 text-center font-bold text-xs" style={{ color: c.accent }}>{u.variant}</td>
                  <td className="px-3 py-3 text-right font-mono text-xs">{u.alerts_received}</td>
                  <td className="px-3 py-3 text-right font-mono text-xs">{u.alerts_opened}</td>
                  <td className="px-3 py-3 text-right font-mono text-xs">{u.edge_views}</td>
                  <td className="px-3 py-3 text-right font-mono text-xs">{u.clicks}</td>
                  <td className="px-3 py-3 text-right font-mono text-xs" style={{ color: u.payments > 0 ? c.green : c.textMuted }}>{u.payments}</td>
                  <td className="px-3 py-3 text-right font-mono text-xs font-bold" style={{ color: u.revenue > 0 ? c.green : c.textMuted }}>${u.revenue}</td>
                </tr>
              ))}
              {(!data?.users || data.users.length === 0) && (
                <tr><td colSpan={9} className="px-4 py-8 text-center text-sm" style={{ color: c.textMuted }}>Нет пользователей</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════════════
   BILLING TAB — Where does money come from?
   ═══════════════════════════════════════════════════ */
function BillingTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    fetch(`${API}/api/admin/miniapp/billing`)
      .then(r => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const k = data?.kpis || {};

  return (
    <div className="space-y-6" data-testid="miniapp-billing">
      <div className="flex justify-end">
        <button onClick={load} className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700">
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Обновить
        </button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
        <KpiCard label="Mini App" value={`$${k.revenue_miniapp || 0}`} icon={DollarSign} color="text-emerald-600" large />
        <KpiCard label="Web" value={`$${k.revenue_web || 0}`} icon={DollarSign} />
        <KpiCard label="Direct" value={`$${k.revenue_direct || 0}`} icon={DollarSign} />
        <KpiCard label="Mini App %" value={`${k.miniapp_pct || 0}%`} icon={TrendingUp} color="text-blue-600" />
        <KpiCard label="Конверсия" value={`${k.conversion || 0}%`} icon={Target} color="text-blue-600" />
        <KpiCard label="Средний чек" value={`$${k.avg_check || 0}`} icon={CreditCard} color="text-amber-600" />
      </div>

      {/* Revenue by Source (stacked bar) */}
      {data?.daily && data.daily.length > 0 && (
        <div className="border border-gray-200 rounded-xl p-5" data-testid="billing-chart">
          <h3 className="text-sm font-semibold mb-3" style={{ color: c.text }}>Доход по источникам</h3>
          <StackedBarChart data={data.daily} />
        </div>
      )}

      {/* Transactions Table */}
      {loading && !data ? <LoadingState /> : (
        <div className="border border-gray-200 rounded-lg overflow-hidden" data-testid="billing-table">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>User</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>Сумма</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>Статус</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>Источник</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>Дата</th>
              </tr>
            </thead>
            <tbody>
              {(data?.transactions || []).map((t, i) => (
                <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-sm" style={{ color: c.text }}>{t.user}</td>
                  <td className="px-4 py-3 text-right font-mono text-sm font-bold" style={{ color: c.green }}>${t.amount}</td>
                  <td className="px-4 py-3"><span className="text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700">{t.status}</span></td>
                  <td className="px-4 py-3"><SourceBadge source={t.source} /></td>
                  <td className="px-4 py-3 text-xs font-mono" style={{ color: c.textMuted }}>{formatTime(t.date)}</td>
                </tr>
              ))}
              {(!data?.transactions || data.transactions.length === 0) && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-sm" style={{ color: c.textMuted }}>Нет транзакций</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════════════
   ALERTS TAB — What sells?
   ═══════════════════════════════════════════════════ */
function AlertsTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    fetch(`${API}/api/admin/miniapp/alerts`)
      .then(r => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const k = data?.kpis || {};

  return (
    <div className="space-y-6" data-testid="miniapp-alerts-tab">
      <div className="flex justify-end">
        <button onClick={load} className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700">
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Обновить
        </button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-7 gap-4">
        <KpiCard label="Alerts Sent" value={k.alerts_sent} icon={Bell} />
        <KpiCard label="Opened" value={k.alerts_opened} icon={Eye} color="text-blue-600" />
        <KpiCard label="CTR" value={`${k.ctr || 0}%`} icon={Target} color="text-blue-600" />
        <KpiCard label="Edge Views" value={k.edge_views} icon={TrendingUp} />
        <KpiCard label="Clicks" value={k.clicks} icon={MousePointer} />
        <KpiCard label="Payments" value={k.payments} icon={CreditCard} color="text-emerald-600" />
        <KpiCard label="$ / alert" value={`$${k.revenue_per_alert || 0}`} icon={DollarSign} color="text-amber-600" />
      </div>

      {/* A/B Table (expanded) */}
      {data?.ab_stats && Object.keys(data.ab_stats).length > 0 && (
        <div className="border border-gray-200 rounded-xl p-5" data-testid="alerts-ab-table">
          <h3 className="text-sm font-semibold mb-3" style={{ color: c.text }}>A/B Тестирование алертов</h3>
          <ABTable stats={data.ab_stats} />
        </div>
      )}

      {/* CTR Over Time Chart */}
      {data?.ctr_over_time && data.ctr_over_time.length > 0 && (
        <div className="border border-gray-200 rounded-xl p-5" data-testid="alerts-ctr-chart">
          <h3 className="text-sm font-semibold mb-3" style={{ color: c.text }}>CTR по вариантам (7 дней)</h3>
          <CTRChart data={data.ctr_over_time} />
        </div>
      )}

      {/* Recent Alerts */}
      {loading && !data ? <LoadingState /> : (
        <div data-testid="recent-alerts">
          <h3 className="text-sm font-semibold mb-3" style={{ color: c.text }}>Последние алерты</h3>
          <div className="border border-gray-200 rounded-lg overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50">
                  <th className="px-3 py-2.5 text-left text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>Время</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>User</th>
                  <th className="px-3 py-2.5 text-center text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>A/B</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>Asset</th>
                  <th className="px-3 py-2.5 text-center text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>Opened</th>
                  <th className="px-3 py-2.5 text-center text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>Clicked</th>
                  <th className="px-3 py-2.5 text-center text-xs font-medium uppercase tracking-wider" style={{ color: c.textMuted }}>Paid</th>
                </tr>
              </thead>
              <tbody>
                {(data?.recent_alerts || []).map((a, i) => (
                  <tr key={i} className="border-t border-gray-100 hover:bg-gray-50" data-testid={`alert-row-${i}`}>
                    <td className="px-3 py-3 text-xs font-mono" style={{ color: c.textMuted }}>{formatTime(a.time)}</td>
                    <td className="px-3 py-3 text-xs font-medium" style={{ color: c.text }}>{a.user}</td>
                    <td className="px-3 py-3 text-center font-bold text-xs" style={{ color: c.accent }}>{a.variant}</td>
                    <td className="px-3 py-3 text-xs font-medium" style={{ color: c.text }}>{a.asset}</td>
                    <td className="px-3 py-3 text-center">{a.opened ? <Check size={14} className="text-emerald-500 mx-auto" /> : <X size={14} className="text-gray-300 mx-auto" />}</td>
                    <td className="px-3 py-3 text-center">{a.clicked ? <Check size={14} className="text-emerald-500 mx-auto" /> : <X size={14} className="text-gray-300 mx-auto" />}</td>
                    <td className="px-3 py-3 text-center">{a.paid ? <Check size={14} className="text-emerald-500 mx-auto" /> : <X size={14} className="text-gray-300 mx-auto" />}</td>
                  </tr>
                ))}
                {(!data?.recent_alerts || data.recent_alerts.length === 0) && (
                  <tr><td colSpan={7} className="px-4 py-8 text-center text-sm" style={{ color: c.textMuted }}>Нет алертов</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}



/* ═══════════════════════════════════════════════════
   SUBSCRIBERS TAB — Newsletter subscribers
   ═══════════════════════════════════════════════════ */
function SubscribersTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/admin/newsletter/subscribers`, { credentials: 'include' });
      const d = await r.json();
      if (d.ok) setData(d);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleRemove = async (email) => {
    if (!window.confirm(`Remove ${email}?`)) return;
    try {
      await fetch(`${API}/api/admin/newsletter/subscribers/${encodeURIComponent(email)}`, {
        method: 'DELETE', credentials: 'include',
      });
      load();
    } catch {}
  };

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="animate-spin" size={28} style={{ color: c.accent }} /></div>;

  const subs = data?.subscribers || [];

  return (
    <div className="space-y-6" data-testid="subscribers-tab">
      {/* KPIs */}
      <div className="grid grid-cols-2 gap-4">
        <div className="p-5 rounded-xl border" style={{ borderColor: c.border, backgroundColor: 'white' }}>
          <p className="text-xs font-medium uppercase tracking-wider mb-1" style={{ color: c.textMuted }}>Total Subscribers</p>
          <p className="text-3xl font-bold" style={{ color: c.text }}>{data?.total || 0}</p>
        </div>
        <div className="p-5 rounded-xl border" style={{ borderColor: c.border, backgroundColor: 'white' }}>
          <p className="text-xs font-medium uppercase tracking-wider mb-1" style={{ color: c.textMuted }}>Active</p>
          <p className="text-3xl font-bold" style={{ color: c.green }}>{data?.active || 0}</p>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border overflow-hidden" style={{ borderColor: c.border, backgroundColor: 'white' }}>
        <div className="p-4 border-b flex items-center justify-between" style={{ borderColor: c.border }}>
          <h3 className="font-semibold flex items-center gap-2" style={{ color: c.text }}>
            <Mail size={16} style={{ color: c.accent }} /> Newsletter Subscribers
          </h3>
          <button onClick={load} className="p-1.5 rounded-md hover:bg-gray-100 transition-colors" data-testid="subscribers-refresh">
            <RefreshCw size={14} style={{ color: c.textMuted }} />
          </button>
        </div>

        {subs.length === 0 ? (
          <div className="p-8 text-center" style={{ color: c.textMuted }}>
            <Mail size={32} className="mx-auto mb-2 opacity-40" />
            <p className="text-sm">No subscribers yet</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b" style={{ borderColor: c.border, backgroundColor: c.surface }}>
                  <th className="text-left py-3 px-4 font-medium" style={{ color: c.textMuted }}>Email</th>
                  <th className="text-left py-3 px-4 font-medium" style={{ color: c.textMuted }}>Source</th>
                  <th className="text-left py-3 px-4 font-medium" style={{ color: c.textMuted }}>Subscribed</th>
                  <th className="text-left py-3 px-4 font-medium" style={{ color: c.textMuted }}>Status</th>
                  <th className="text-right py-3 px-4 font-medium" style={{ color: c.textMuted }}></th>
                </tr>
              </thead>
              <tbody>
                {subs.map(s => (
                  <tr key={s.email} className="border-b last:border-0 hover:bg-gray-50 transition-colors" style={{ borderColor: c.border }} data-testid={`subscriber-row-${s.email}`}>
                    <td className="py-3 px-4 font-medium" style={{ color: c.text }}>{s.email}</td>
                    <td className="py-3 px-4" style={{ color: c.textSecondary }}>{s.source || 'footer'}</td>
                    <td className="py-3 px-4" style={{ color: c.textSecondary }}>
                      {s.subscribed_at ? new Date(s.subscribed_at).toLocaleDateString() : '—'}
                    </td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
                        style={{ backgroundColor: s.active ? '#dcfce7' : '#fee2e2', color: s.active ? c.green : c.red }}>
                        {s.active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button onClick={() => handleRemove(s.email)}
                        className="p-1 rounded hover:bg-red-50 transition-colors" data-testid={`subscriber-remove-${s.email}`}>
                        <Trash2 size={14} style={{ color: c.red }} />
                      </button>
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


/* ═══════════════════════════════════════════════════
   SETTINGS TAB — What to control?
   ═══════════════════════════════════════════════════ */
function SettingsTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    fetch(`${API}/api/admin/miniapp/settings`)
      .then(r => r.json())
      .then(d => { setData(d.settings); setDirty(false); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const update = (section, key, value) => {
    setData(prev => ({
      ...prev,
      [section]: { ...prev[section], [key]: value },
    }));
    setDirty(true);
  };

  const save = () => {
    setSaving(true);
    fetch(`${API}/api/admin/miniapp/settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ settings: data }),
    })
      .then(r => r.json())
      .then(() => setDirty(false))
      .catch(() => {})
      .finally(() => setSaving(false));
  };

  if (loading && !data) return <LoadingState />;
  const s = data || {};

  return (
    <div className="space-y-6" data-testid="miniapp-settings">
      <div className="flex justify-between items-center">
        <h3 className="text-sm font-semibold" style={{ color: c.text }}>Настройки Mini App</h3>
        <div className="flex gap-2">
          <button onClick={load} className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700">
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Сбросить
          </button>
          <button
            data-testid="settings-save"
            onClick={save}
            disabled={!dirty || saving}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium transition-all ${dirty ? 'bg-indigo-600 text-white hover:bg-indigo-700' : 'bg-gray-100 text-gray-400'}`}
          >
            {saving ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
            Сохранить
          </button>
        </div>
      </div>

      {/* Block 1 — Alerts */}
      <div className="border border-gray-200 rounded-xl p-5" data-testid="settings-alerts">
        <h4 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: c.textMuted }}>Алерты</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <SettingField label="Edge Threshold" value={s.alerts?.edge_threshold} type="number" step="0.01"
            onChange={v => update('alerts', 'edge_threshold', parseFloat(v))} sub="Мин. edge для алерта (0.05 - 0.30)" />
          <SettingField label="Priority Threshold" value={s.alerts?.priority_threshold} type="number" step="0.01"
            onChange={v => update('alerts', 'priority_threshold', parseFloat(v))} sub="Мин. priorityScore (0.50 - 0.90)" />
          <SettingField label="Daily Limit" value={s.alerts?.daily_limit} type="number" step="1"
            onChange={v => update('alerts', 'daily_limit', parseInt(v))} sub="Макс. алертов в день на юзера" />
          <SettingToggle label="EXTREME Bypass" value={s.alerts?.extreme_bypass}
            onChange={v => update('alerts', 'extreme_bypass', v)} sub="Пропускать лимиты для EXTREME сигналов" />
        </div>
      </div>

      {/* Block 2 — Scheduler */}
      <div className="border border-gray-200 rounded-xl p-5" data-testid="settings-scheduler">
        <h4 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: c.textMuted }}>Scheduler</h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <SettingField label="Ingest Interval" value={s.scheduler?.ingest_interval} type="number" step="5"
            onChange={v => update('scheduler', 'ingest_interval', parseInt(v))} sub="Минуты между Polymarket ingest" />
          <SettingField label="Digest Hour (UTC)" value={s.scheduler?.digest_hour} type="number" step="1"
            onChange={v => update('scheduler', 'digest_hour', parseInt(v))} sub="Час ежедневного дайджеста" />
          <SettingToggle label="Digest Enabled" value={s.scheduler?.digest_enabled}
            onChange={v => update('scheduler', 'digest_enabled', v)} sub="Отправка ежедневного дайджеста" />
        </div>
      </div>

      {/* Block 3 — Alert Boost */}
      <div className="border border-amber-200 rounded-xl p-5 bg-amber-50/30" data-testid="settings-boost">
        <h4 className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: '#d97706' }}>Alert Boost</h4>
        <div className="text-xs mb-4" style={{ color: c.textMuted }}>Включать ТОЛЬКО после анализа A/B данных</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <SettingToggle label="Resend Enabled" value={s.boost?.resend_enabled}
            onChange={v => update('boost', 'resend_enabled', v)} sub="Повтор алерта если edge &gt; 20% и не открыт через 45 мин" />
          <SettingToggle label="Accuracy Enabled" value={s.boost?.accuracy_enabled}
            onChange={v => update('boost', 'accuracy_enabled', v)} sub="Добавить 'Model accuracy: 82%' в текст алерта" />
        </div>
      </div>

      {/* Block 4 — Monetization */}
      <div className="border border-gray-200 rounded-xl p-5" data-testid="settings-monetization">
        <h4 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: c.textMuted }}>Монетизация</h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <SettingField label="Free Edge Limit" value={s.monetization?.free_edge_limit} type="number" step="1"
            onChange={v => update('monetization', 'free_edge_limit', parseInt(v))} sub="Макс. бесплатных эджей" />
          <SettingToggle label="Paywall Enabled" value={s.monetization?.paywall_enabled}
            onChange={v => update('monetization', 'paywall_enabled', v)} sub="Показ paywall после лимита" />
          <SettingToggle label="Teaser Mode" value={s.monetization?.teaser_mode}
            onChange={v => update('monetization', 'teaser_mode', v)} sub="Показ размытого контента для FREE" />
        </div>
      </div>
    </div>
  );
}

function SettingField({ label, value, type = 'number', step = '1', onChange, sub }) {
  return (
    <div>
      <label className="block text-xs font-medium mb-1" style={{ color: c.textSecondary }}>{label}</label>
      <input
        type={type}
        value={value ?? ''}
        step={step}
        onChange={e => onChange(e.target.value)}
        className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-200"
        style={{ color: c.text }}
      />
      {sub && <div className="text-xs mt-1" style={{ color: c.textMuted }}>{sub}</div>}
    </div>
  );
}

function SettingToggle({ label, value, onChange, sub }) {
  return (
    <div>
      <div className="flex items-center justify-between">
        <label className="text-xs font-medium" style={{ color: c.textSecondary }}>{label}</label>
        <button
          onClick={() => onChange(!value)}
          className="relative w-10 h-5 rounded-full transition-colors"
          style={{ backgroundColor: value ? '#10b981' : '#d1d5db' }}
        >
          <div className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all shadow-sm"
            style={{ left: value ? '22px' : '2px' }}
          />
        </button>
      </div>
      {sub && <div className="text-xs mt-1" style={{ color: c.textMuted }}>{sub}</div>}
    </div>
  );
}


/* ═══════════════════════════════════════════════════
   SPRINT 2 HELPER COMPONENTS
   ═══════════════════════════════════════════════════ */

function StatusBadge({ status }) {
  const colors = {
    paid: 'bg-emerald-50 text-emerald-700',
    linked: 'bg-blue-50 text-blue-700',
    telegram: 'bg-gray-100 text-gray-600',
    guest: 'bg-gray-50 text-gray-400',
  };
  return <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${colors[status] || 'bg-gray-50 text-gray-500'}`}>{status}</span>;
}

function StackedBarChart({ data }) {
  const max = Math.max(...data.map(d => d.miniapp + d.web + d.direct), 1);
  const colors = { miniapp: '#10b981', web: '#6366f1', direct: '#f59e0b' };

  return (
    <div>
      <div className="flex items-end gap-1 h-28">
        {data.map((d, i) => {
          const total = d.miniapp + d.web + d.direct;
          const h = total / max * 100;
          return (
            <div key={i} className="flex-1 flex flex-col" style={{ height: `${Math.max(h, 2)}%` }}
              title={`${d.date}: Mini App $${d.miniapp}, Web $${d.web}, Direct $${d.direct}`}>
              {d.miniapp > 0 && <div style={{ flex: d.miniapp, backgroundColor: colors.miniapp, borderRadius: '2px 2px 0 0' }} />}
              {d.web > 0 && <div style={{ flex: d.web, backgroundColor: colors.web }} />}
              {d.direct > 0 && <div style={{ flex: d.direct, backgroundColor: colors.direct, borderRadius: '0 0 2px 2px' }} />}
              {total === 0 && <div style={{ flex: 1, backgroundColor: '#e5e7eb', borderRadius: '2px', minHeight: '2px' }} />}
            </div>
          );
        })}
      </div>
      <div className="flex gap-4 mt-3">
        {Object.entries(colors).map(([key, color]) => (
          <div key={key} className="flex items-center gap-1.5 text-xs" style={{ color: c.textMuted }}>
            <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: color }} />
            {key === 'miniapp' ? 'Mini App' : key === 'web' ? 'Web' : 'Direct'}
          </div>
        ))}
      </div>
    </div>
  );
}

function CTRChart({ data }) {
  const variants = ['A', 'B', 'C', 'D'];
  const colors = { A: '#ef4444', B: '#f59e0b', C: '#6366f1', D: '#10b981' };
  const labels = { A: 'Urgency', B: 'Loss', C: 'Performance', D: 'Combo' };
  const max = Math.max(...data.flatMap(d => variants.map(v => d[v] || 0)), 1);

  return (
    <div>
      <div className="flex items-end gap-0.5 h-24">
        {data.map((d, i) => (
          <div key={i} className="flex-1 flex items-end gap-px">
            {variants.map(v => {
              const val = d[v] || 0;
              const h = Math.max(val / max * 100, 1);
              return (
                <div key={v} className="flex-1 rounded-t-sm transition-all hover:opacity-80"
                  style={{ height: `${h}%`, backgroundColor: colors[v], minHeight: '1px' }}
                  title={`${d.date} ${v}(${labels[v]}): ${val}%`}
                />
              );
            })}
          </div>
        ))}
      </div>
      <div className="flex gap-4 mt-3">
        {variants.map(v => (
          <div key={v} className="flex items-center gap-1.5 text-xs" style={{ color: c.textMuted }}>
            <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: colors[v] }} />
            {v} — {labels[v]}
          </div>
        ))}
      </div>
    </div>
  );
}
