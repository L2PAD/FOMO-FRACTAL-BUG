/**
 * Admin Signals Page — Unified hub with internal horizontal tabs.
 * Wrapped in AdminLayout (platform sidebar).
 *
 * Tabs: Сигналы | Настройки алертов | FOMO Алерты
 */
import React, { useState, useEffect, useCallback, lazy, Suspense } from 'react';
import { AdminLayout } from '../../components/admin/PlatformAdminLayout';
import {
  Zap, RefreshCw, AlertCircle, TrendingUp, TrendingDown, Minus,
  Activity, Brain, BarChart2, Wifi, WifiOff, Bell, Shield,
} from 'lucide-react';
import { api } from '../../api/client';

const AdminAlertsSettingsPage = lazy(() => import('./AdminAlertsSettingsPage'));
const FomoAlertsAdminPage = lazy(() => import('./FomoAlertsAdminPage'));

// ── Tab config ──────────────────────────────────────────────────
const TABS = [
  { id: 'signals', label: 'Сигналы', icon: Zap },
  { id: 'alerts', label: 'Настройки алертов', icon: Bell },
  { id: 'fomo', label: 'FOMO Алерты', icon: Shield },
];

// ── Color tokens ────────────────────────────────────────────────
const c = {
  text: '#0f172a',
  textSecondary: '#475569',
  accent: '#6366f1',
  surface: '#f8fafc',
};

// ── Loading fallback ────────────────────────────────────────────
function TabLoader() {
  return (
    <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
      <RefreshCw className="w-4 h-4 animate-spin mr-2" /> Загрузка...
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════════════════════════
export default function AdminSignalsPage() {
  const params = new URLSearchParams(window.location.search);
  const initialTab = params.get('tab') || 'signals';
  const [activeTab, setActiveTab] = useState(initialTab);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    const url = new URL(window.location);
    if (tab === 'signals') {
      url.searchParams.delete('tab');
    } else {
      url.searchParams.set('tab', tab);
    }
    window.history.replaceState({}, '', url);
  };

  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6" data-testid="signals-admin-page">
        {/* Page Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold flex items-center gap-3" style={{ color: c.text }}>
            <Zap size={28} style={{ color: c.accent }} />
            Signals & Alerts
          </h1>
          <p className="text-sm mt-1" style={{ color: c.textSecondary }}>
            Реестр сигналов, настройки алертов и FOMO уведомлений
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
                data-testid={`signals-tab-${tab.id}`}
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
        {activeTab === 'signals' && <SignalsContent />}
        {activeTab === 'alerts' && (
          <Suspense fallback={<TabLoader />}>
            <div className="[&>div]:min-h-0 [&>div]:p-0 [&>div]:bg-transparent">
              <AdminAlertsSettingsPage />
            </div>
          </Suspense>
        )}
        {activeTab === 'fomo' && (
          <Suspense fallback={<TabLoader />}>
            <div className="[&>div]:min-h-0 [&>div]:p-0 [&>div]:bg-transparent">
              <FomoAlertsAdminPage />
            </div>
          </Suspense>
        )}
      </div>
    </AdminLayout>
  );
}


/* ══════════════════════════════════════════════════════════════════
   SIGNALS CONTENT (previously the full page)
   ══════════════════════════════════════════════════════════════════ */
const MODULE_META = {
  fractal:   { label: 'Fractal Engine',    color: 'text-violet-600',  bg: 'bg-violet-50/70',  icon: Activity },
  exchange:  { label: 'Exchange',           color: 'text-blue-600',    bg: 'bg-blue-50/70',    icon: BarChart2 },
  onchain:   { label: 'On-Chain',           color: 'text-emerald-600', bg: 'bg-emerald-50/70', icon: Zap },
  sentiment: { label: 'Sentiment',          color: 'text-amber-600',   bg: 'bg-amber-50/70',   icon: Brain },
};

function SignalsContent() {
  const [modules, setModules] = useState([]);
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedModule, setSelectedModule] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [modRes, sigRes] = await Promise.all([
        api.get('/api/meta-brain-v2/modules'),
        api.get('/api/meta-brain-v2/signals'),
      ]);
      setModules(modRes.data?.modules || []);
      setSignals(sigRes.data?.signals || []);
    } catch {
      setError('Не удалось загрузить данные сигналов');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const activeSignals = selectedModule
    ? signals.filter(s => s.module === selectedModule)
    : signals;

  const totalWeight = modules.reduce((s, m) => s + (m.enabled ? m.weight : 0), 0);

  return (
    <div className="space-y-6" data-testid="signals-content">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <Zap className="w-5 h-5 text-blue-600" />
            <h2 className="text-xl font-semibold text-slate-900">Реестр сигналов</h2>
          </div>
          <p className="text-sm text-gray-500 mt-1 ml-8">
            Активные источники сигналов для MetaBrain
          </p>
        </div>
        <button
          onClick={loadData}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          data-testid="signals-refresh"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Обновить
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-3 p-4 bg-amber-50 rounded-lg">
          <AlertCircle className="w-5 h-5 text-amber-600" />
          <span className="text-sm text-amber-800">{error}</span>
        </div>
      )}

      {/* Module cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4" data-testid="signals-modules">
        {modules.map(m => {
          const meta = MODULE_META[m.module] || { label: m.module, color: 'text-gray-600', bg: 'bg-gray-50', icon: Activity };
          const Icon = meta.icon;
          const sigCount = signals.filter(s => s.module === m.module).length;
          const isSelected = selectedModule === m.module;
          const weightPct = totalWeight > 0 ? (m.weight / totalWeight * 100).toFixed(0) : 0;

          return (
            <button
              key={m.module}
              onClick={() => setSelectedModule(isSelected ? null : m.module)}
              className={`text-left p-4 rounded-lg transition-all ${
                isSelected ? 'bg-blue-50/70' : 'bg-gray-50/70 hover:bg-gray-100/70'
              }`}
              data-testid={`signals-module-${m.module}`}
            >
              <div className="flex items-center justify-between mb-3">
                <div className={`p-2 rounded-lg ${meta.bg}`}>
                  <Icon className={`w-4 h-4 ${meta.color}`} />
                </div>
                {m.enabled
                  ? <Wifi className="w-3.5 h-3.5 text-emerald-500" />
                  : <WifiOff className="w-3.5 h-3.5 text-gray-300" />
                }
              </div>
              <div className="text-sm font-medium text-gray-900 mb-1">{meta.label}</div>
              <div className="flex items-center gap-3 text-xs text-gray-500">
                <span>{sigCount} сигнал{sigCount !== 1 ? 'ов' : ''}</span>
                <span className="text-gray-300">|</span>
                <span>Вес {weightPct}%</span>
                <span className="text-gray-300">|</span>
                <span className="capitalize">{m.mode}</span>
              </div>
              <div className="h-1 bg-gray-100 rounded-full mt-3 overflow-hidden">
                <div
                  className={`h-full rounded-full ${m.enabled ? 'bg-blue-500' : 'bg-gray-300'}`}
                  style={{ width: `${m.weight * 100}%` }}
                />
              </div>
            </button>
          );
        })}
      </div>

      {/* Signals table */}
      <div className="bg-gray-50/70 rounded-lg overflow-hidden" data-testid="signals-table">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-gray-700">
              {selectedModule
                ? `Сигналы ${MODULE_META[selectedModule]?.label || selectedModule}`
                : 'Все сигналы'
              }
            </span>
            <span className="text-xs text-gray-400">{activeSignals.length} активных</span>
          </div>
          {selectedModule && (
            <button
              onClick={() => setSelectedModule(null)}
              className="text-xs text-blue-600 hover:text-blue-700"
            >
              Показать все
            </button>
          )}
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-5 h-5 text-gray-400 animate-spin" />
          </div>
        ) : activeSignals.length === 0 ? (
          <div className="text-center py-12">
            <Zap className="w-8 h-8 mx-auto mb-3 text-gray-300" />
            <p className="text-sm text-gray-500">Нет активных сигналов</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-50">
            {activeSignals.map((sig, i) => {
              const meta = MODULE_META[sig.module] || { label: sig.module, color: 'text-gray-600', bg: 'bg-gray-50' };
              const DirIcon = sig.direction === 'LONG' || sig.direction === 'BULLISH'
                ? TrendingUp
                : sig.direction === 'SHORT' || sig.direction === 'BEARISH'
                  ? TrendingDown
                  : Minus;
              const dirColor = sig.direction === 'LONG' || sig.direction === 'BULLISH'
                ? 'text-emerald-600'
                : sig.direction === 'SHORT' || sig.direction === 'BEARISH'
                  ? 'text-red-600'
                  : 'text-gray-400';
              const dirLabel = sig.direction === 'LONG' || sig.direction === 'BULLISH'
                ? 'Bullish'
                : sig.direction === 'SHORT' || sig.direction === 'BEARISH'
                  ? 'Bearish'
                  : 'HOLD';

              const modWeight = modules.find(m => m.module === sig.module)?.weight || 0;
              const age = sig.asOfTs ? Math.round((Date.now() - sig.asOfTs) / 60000) : null;

              return (
                <div key={`${sig.module}-${i}`} className="px-4 py-3 hover:bg-gray-50 transition-colors" data-testid={`signal-row-${sig.module}`}>
                  <div className="flex items-center gap-4">
                    <div className={`text-xs font-medium ${meta.color}`}>
                      {meta.label}
                    </div>
                    <div className="flex items-center gap-1.5 min-w-[80px]">
                      <DirIcon className={`w-4 h-4 ${dirColor}`} />
                      <span className={`text-sm font-bold ${dirColor}`}>{dirLabel}</span>
                    </div>
                    <div className="min-w-[60px]">
                      <div className="text-xs text-gray-400">Скор</div>
                      <div className="text-sm font-medium text-gray-800">{sig.score?.toFixed(3)}</div>
                    </div>
                    <div className="min-w-[80px]">
                      <div className="text-xs text-gray-400">Уверенность</div>
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-16 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full bg-blue-500"
                            style={{ width: `${(sig.confidence || 0) * 100}%` }}
                          />
                        </div>
                        <span className="text-sm font-medium text-gray-800">{((sig.confidence || 0) * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                    <div className="min-w-[60px]">
                      <div className="text-xs text-gray-400">Вес</div>
                      <div className="text-sm font-medium text-gray-800">{(modWeight * 100).toFixed(0)}%</div>
                    </div>
                    <div className="min-w-[80px]">
                      <div className="text-xs text-gray-400">Прогноз</div>
                      <div className={`text-sm font-medium ${
                        (sig.expectedMovePct || 0) > 0 ? 'text-emerald-600'
                          : (sig.expectedMovePct || 0) < 0 ? 'text-red-600'
                          : 'text-gray-500'
                      }`}>
                        {(sig.expectedMovePct || 0) > 0 ? '+' : ''}{((sig.expectedMovePct || 0) * 100).toFixed(2)}%
                      </div>
                    </div>
                    <div className="ml-auto text-right">
                      <div className="text-xs text-gray-400">Возраст</div>
                      <div className="text-sm text-gray-500">
                        {age !== null ? (age < 60 ? `${age}m` : `${Math.round(age / 60)}h`) : '-'}
                      </div>
                    </div>
                  </div>
                  <div className="mt-1.5 text-[11px] text-gray-400 truncate">
                    {sig.sourceId || '-'}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Aggregation summary */}
      {signals.length > 0 && (
        <div className="bg-gray-50/70 rounded-lg p-4" data-testid="signals-summary">
          <div className="text-sm font-medium text-gray-700 mb-3">Агрегация MetaBrain</div>
          <div className="flex items-center gap-6">
            <div>
              <div className="text-xs text-gray-400">Взвешенный скор</div>
              <div className="text-lg font-bold text-gray-900">
                {signals.reduce((sum, s) => {
                  const w = modules.find(m => m.module === s.module)?.weight || 0;
                  return sum + s.score * w;
                }, 0).toFixed(4)}
              </div>
            </div>
            <div className="h-8 w-px bg-gray-200" />
            <div>
              <div className="text-xs text-gray-400">Активные модули</div>
              <div className="text-lg font-bold text-gray-900">{modules.filter(m => m.enabled).length}/{modules.length}</div>
            </div>
            <div className="h-8 w-px bg-gray-200" />
            <div>
              <div className="text-xs text-gray-400">Всего сигналов</div>
              <div className="text-lg font-bold text-gray-900">{signals.length}</div>
            </div>
            <div className="h-8 w-px bg-gray-200" />
            <div>
              <div className="text-xs text-gray-400">Средняя уверенность</div>
              <div className="text-lg font-bold text-gray-900">
                {signals.length > 0
                  ? (signals.reduce((s, sig) => s + (sig.confidence || 0), 0) / signals.length * 100).toFixed(0)
                  : 0
                }%
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
