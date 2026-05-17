/**
 * ML Overview Admin Page
 * Единая точка входа для управления ML системой.
 * Панели: Health, Safety, RAM, Modules, System Health, Data Freshness, System Metrics
 */

import React, { useState, useEffect, useCallback } from 'react';
import AdminLayout from '../../components/admin/AdminLayout';
import { Button } from '../../components/ui/button';
import {
  AlertCircle, CheckCircle, AlertTriangle, Power, PowerOff,
  Activity, Database, Cpu, Server, Loader2, BarChart3, RefreshCw,
  Clock, Wifi, WifiOff, HardDrive, Gauge, Timer,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

/* ─── helpers ─── */
const fmt = (v) => (v == null ? '—' : v);

const freshnessColor = (status) => ({
  fresh: 'text-green-600',
  stale: 'text-yellow-600',
  outdated: 'text-red-600',
  unknown: 'text-gray-400',
  error: 'text-red-400',
}[status] || 'text-gray-400');

const freshnessLabel = (status) => ({
  fresh: 'Актуально',
  stale: 'Устарело',
  outdated: 'Очень старое',
  unknown: 'Нет данных',
  error: 'Ошибка',
}[status] || 'Неизвестно');

const ageText = (minutes) => {
  if (minutes == null) return '—';
  if (minutes < 60) return `${minutes} мин назад`;
  if (minutes < 1440) return `${Math.round(minutes / 60)} ч назад`;
  return `${Math.round(minutes / 1440)} дн назад`;
};

/* ─── Section Card ─── */
const SectionCard = ({ icon: Icon, iconColor, title, tooltip, children, testId }) => (
  <div className="p-4 rounded-lg bg-gray-50/70" title={tooltip} data-testid={testId}>
    <div className="flex items-center gap-2 mb-3">
      {Icon && <Icon className={`w-4 h-4 ${iconColor || 'text-gray-600'}`} />}
      <span className="text-sm font-semibold text-slate-900">{title}</span>
    </div>
    {children}
  </div>
);

export default function AdminMLOverviewPage() {
  const [overview, setOverview] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchOverview = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v4/admin/runtime/overview`);
      const data = await res.json();
      if (data.ok) {
        setOverview(data.data);
        setError(null);
      } else {
        setError(data.error || 'Failed to fetch overview');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchMetrics = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v4/admin/runtime/system-metrics`);
      const data = await res.json();
      if (data.ok) setMetrics(data.data);
    } catch {
      /* silent — metrics are supplementary */
    }
  }, []);

  useEffect(() => {
    fetchOverview();
    fetchMetrics();
    const i1 = setInterval(fetchOverview, 5000);
    const i2 = setInterval(fetchMetrics, 15000);
    return () => { clearInterval(i1); clearInterval(i2); };
  }, [fetchOverview, fetchMetrics]);

  const handleKillSwitch = async (activate) => {
    setActionLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/v4/admin/runtime/kill-switch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ activate }),
      });
      const data = await res.json();
      if (data.ok) fetchOverview();
    } catch (err) {
      console.error('Kill switch error:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleSoftStop = async (activate) => {
    setActionLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/v4/admin/runtime/soft-stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ activate }),
      });
      const data = await res.json();
      if (data.ok) fetchOverview();
    } catch (err) {
      console.error('Soft stop error:', err);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <AdminLayout>
        <div className="px-4 py-5 lg:px-6 space-y-6">
          <div className="flex items-center gap-3">
            <BarChart3 className="w-5 h-5 text-blue-600" />
            <h1 className="text-xl font-semibold text-slate-900">Обзор ML</h1>
          </div>
          <div className="flex items-center justify-center h-32">
            <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
          </div>
        </div>
      </AdminLayout>
    );
  }

  if (error) {
    return (
      <AdminLayout>
        <div className="px-4 py-5 lg:px-6 space-y-6">
          <div className="flex items-center gap-3">
            <BarChart3 className="w-5 h-5 text-blue-600" />
            <h1 className="text-xl font-semibold text-slate-900">Обзор ML</h1>
          </div>
          <div className="flex items-center gap-3 p-4 bg-red-50/70 rounded-lg">
            <AlertCircle className="w-5 h-5 text-red-600" />
            <span className="text-sm text-red-800">{error}</span>
          </div>
        </div>
      </AdminLayout>
    );
  }

  const { health = {}, ram = {}, modules: _modules = {}, killSwitch = {} } = overview || {};
  const modules = {
    sentiment: _modules.sentiment || { status: '—', mode: '—', enabled: false },
    twitter: _modules.twitter || { status: '—', parserEnabled: false, sentimentEnabled: false },
    automation: _modules.automation || { status: '—', enabled: false, queueDepth: 0 },
    ..._modules,
  };

  const getHealthIcon = (status) => {
    switch (status) {
      case 'OK': return <CheckCircle className="h-5 w-5 text-green-600" />;
      case 'DEGRADED': return <AlertTriangle className="h-5 w-5 text-yellow-600" />;
      case 'CRITICAL': return <AlertCircle className="h-5 w-5 text-red-600" />;
      default: return null;
    }
  };

  const getHealthBg = (status) => {
    switch (status) {
      case 'OK': return 'bg-green-50/70';
      case 'DEGRADED': return 'bg-yellow-50/70';
      case 'CRITICAL': return 'bg-red-50/70';
      default: return 'bg-gray-50/70';
    }
  };

  const getModuleStatusColor = (status) => ({
    'RUNNING': 'text-green-700',
    'IDLE': 'text-gray-700',
    'DISABLED': 'text-gray-500',
    'STOPPED': 'text-red-700',
    'STOPPING': 'text-yellow-700',
  }[status] || 'text-gray-700');

  return (
    <AdminLayout>
      <div className="space-y-6" data-testid="ml-overview-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <BarChart3 className="w-5 h-5 text-blue-600" />
              <h1 className="text-xl font-semibold text-slate-900">Обзор ML</h1>
            </div>
            <p className="text-sm text-gray-500 mt-1 ml-8">
              Состояние системы и управление модулями
            </p>
          </div>
          <button
            onClick={() => { fetchOverview(); fetchMetrics(); }}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            data-testid="overview-refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Обновить
          </button>
        </div>

        {/* Health Status */}
        <div
          className={`p-4 rounded-lg ${getHealthBg(health.status)}`}
          title="Общий статус ML системы: OK, DEGRADED или CRITICAL"
          data-testid="health-status-card"
        >
          <div className="flex items-center gap-3">
            {getHealthIcon(health.status)}
            <div>
              <span className="text-sm font-semibold text-slate-900">
                Статус системы: {health.status}
              </span>
              <p className="text-xs text-gray-500 mt-0.5">{(health.reasons || []).join(' · ')}</p>
            </div>
          </div>
        </div>

        {/* ═══ NEW: System Health + Data Freshness + System Metrics ═══ */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

          {/* ── System Health ── */}
          <SectionCard
            icon={Activity}
            iconColor="text-green-600"
            title="System Health"
            tooltip="Состояние сервисов и подключений к БД"
            testId="system-health-card"
          >
            {metrics?.services ? (
              <div className="space-y-2">
                {Object.entries(metrics.services).map(([key, svc]) => (
                  <div key={key} className="flex items-center justify-between p-2.5 bg-white/60 rounded-lg text-sm">
                    <div className="flex items-center gap-2">
                      {svc.status === 'connected' || svc.status === 'running'
                        ? <Wifi className="w-3.5 h-3.5 text-green-500" />
                        : <WifiOff className="w-3.5 h-3.5 text-red-500" />
                      }
                      <span className="text-gray-700">{svc.label}</span>
                    </div>
                    <span className={`text-xs font-bold ${
                      svc.status === 'connected' || svc.status === 'running'
                        ? 'text-green-700' : 'text-red-700'
                    }`}>
                      {svc.status === 'connected' || svc.status === 'running' ? 'OK' : 'DOWN'}
                    </span>
                  </div>
                ))}
                {metrics.services.mongodb?.storageMB != null && (
                  <div className="flex justify-between text-xs text-gray-500 pt-1">
                    <span>Хранилище: {metrics.services.mongodb.storageMB} MB</span>
                    <span>Коллекции: {metrics.services.mongodb.collections}</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-xs text-gray-400">Загрузка...</div>
            )}
          </SectionCard>

          {/* ── Data Freshness ── */}
          <SectionCard
            icon={Clock}
            iconColor="text-blue-600"
            title="Data Freshness"
            tooltip="Актуальность данных из различных источников"
            testId="data-freshness-card"
          >
            {metrics?.dataFreshness && !metrics.dataFreshness.error ? (
              <div className="space-y-1.5">
                {Object.entries(metrics.dataFreshness).map(([key, src]) => (
                  <div key={key} className="flex items-center justify-between p-2 bg-white/60 rounded text-sm">
                    <span className="text-gray-600 text-xs">{src.label}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-400">{ageText(src.ageMinutes)}</span>
                      <span className={`text-[10px] font-bold uppercase ${freshnessColor(src.status)}`}>
                        {freshnessLabel(src.status)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-gray-400">
                {metrics?.dataFreshness?.error || 'Загрузка...'}
              </div>
            )}
          </SectionCard>

          {/* ── System Metrics ── */}
          <SectionCard
            icon={Gauge}
            iconColor="text-purple-600"
            title="System Metrics"
            tooltip="Производительность: CPU, RAM, время работы"
            testId="system-metrics-card"
          >
            {metrics?.system ? (
              <div className="space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2.5 bg-white/60 rounded-lg">
                    <div className="text-[10px] text-gray-400 uppercase tracking-wide">CPU Load (1m)</div>
                    <div className="text-lg font-bold text-slate-900 mt-0.5">{metrics.system.loadAvg1m}</div>
                    <div className="text-[10px] text-gray-400">{metrics.system.cpuCount} ядер</div>
                  </div>
                  <div className="p-2.5 bg-white/60 rounded-lg">
                    <div className="text-[10px] text-gray-400 uppercase tracking-wide">Uptime</div>
                    <div className="text-lg font-bold text-slate-900 mt-0.5">{metrics.system.uptimeHours}ч</div>
                    <div className="text-[10px] text-gray-400">{metrics.system.platform}</div>
                  </div>
                </div>
                {metrics.process && (
                  <div className="flex justify-between text-xs text-gray-500 px-1">
                    <span>Node {metrics.process.nodeVersion}</span>
                    <span>Heap: {metrics.process.memoryMB}/{metrics.process.heapTotalMB} MB</span>
                  </div>
                )}
                {metrics.system.loadAvg5m && (
                  <div className="flex justify-between text-xs text-gray-500 px-1">
                    <span>Load 5m: {metrics.system.loadAvg5m}</span>
                    <span>Load 15m: {metrics.system.loadAvg15m}</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-xs text-gray-400">Загрузка...</div>
            )}
          </SectionCard>
        </div>

        {/* Safety Controls */}
        <div
          className="p-4 rounded-lg bg-red-50/70"
          title="Экстренное управление: остановка всех модулей одной кнопкой"
          data-testid="safety-controls-card"
        >
          <div className="flex items-center gap-2 mb-4">
            <Power className="w-4 h-4 text-red-600" />
            <span className="text-sm font-semibold text-slate-900">Управление безопасностью</span>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-white/60 rounded-lg">
              <div>
                <div className="flex items-center gap-2">
                  <PowerOff className="w-4 h-4 text-red-500" />
                  <span className="text-sm font-medium text-slate-900">Global Kill Switch</span>
                </div>
                <p className="text-xs text-gray-500 mt-0.5 ml-6">Немедленная остановка всех модулей</p>
              </div>
              <Button
                variant={killSwitch.global ? "destructive" : "ghost"}
                size="sm"
                onClick={() => handleKillSwitch(!killSwitch.global)}
                disabled={actionLoading}
                data-testid="kill-switch-btn"
              >
                {killSwitch.global ? 'Деактивировать' : 'Активировать'}
              </Button>
            </div>

            <div className="flex items-center justify-between p-3 bg-white/60 rounded-lg">
              <div>
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-yellow-500" />
                  <span className="text-sm font-medium text-slate-900">Soft Stop</span>
                </div>
                <p className="text-xs text-gray-500 mt-0.5 ml-6">Завершить текущий batch, остановить приём новых</p>
              </div>
              <Button
                variant={killSwitch.softStop ? "secondary" : "ghost"}
                size="sm"
                onClick={() => handleSoftStop(!killSwitch.softStop)}
                disabled={actionLoading || killSwitch.global}
                data-testid="soft-stop-btn"
              >
                {killSwitch.softStop ? 'Возобновить' : 'Мягкая остановка'}
              </Button>
            </div>
          </div>

          {killSwitch.lastActivation && (
            <p className="text-xs text-gray-400 mt-3">
              Последнее включение: {new Date(killSwitch.lastActivation).toLocaleString()}
            </p>
          )}
        </div>

        {/* RAM Status */}
        <SectionCard
          icon={Database}
          iconColor="text-gray-600"
          title="Память"
          tooltip="Использование оперативной памяти. Для ML нужен достаточный объём RAM"
          testId="ram-status-card"
        >
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Используется</span>
              <span className="font-medium text-slate-900">{ram.usedMB} MB ({ram.usedPercent}%)</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all ${
                  ram.usedPercent > 90 ? 'bg-red-500' :
                  ram.usedPercent > 75 ? 'bg-yellow-500' : 'bg-green-500'
                }`}
                style={{ width: `${ram.usedPercent}%` }}
              />
            </div>
            <div className="flex justify-between text-xs text-gray-400">
              <span>Свободно: {ram.freeMB} MB</span>
              <span>Всего: {ram.totalMB} MB</span>
            </div>
            <div className="pt-2">
              {ram.canEnableRealML ? (
                <span className="inline-flex items-center gap-1.5 text-xs font-medium text-green-700">
                  <CheckCircle className="w-3 h-3" />
                  Достаточно RAM для ML
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 text-xs font-medium text-red-700">
                  <AlertCircle className="w-3 h-3" />
                  Недостаточно RAM для ML
                </span>
              )}
            </div>
          </div>
        </SectionCard>

        {/* Module Status Grid */}
        <div title="Состояние основных модулей платформы">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-sm font-semibold text-slate-900">Модули</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Sentiment Module */}
            <div className="p-4 rounded-lg bg-gray-50/70" data-testid="sentiment-module-card">
              <div className="flex items-center gap-2 mb-3">
                <Cpu className="w-4 h-4 text-gray-600" />
                <span className="text-sm font-medium text-slate-900">Sentiment Engine</span>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between items-center text-sm">
                  <span className="text-gray-500">Статус</span>
                  <span className={`text-xs font-bold ${getModuleStatusColor(modules.sentiment.status)}`}>
                    {modules.sentiment.status}
                  </span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-gray-500">Режим</span>
                  <span className="text-xs font-medium text-gray-700">{modules.sentiment.mode}</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-gray-500">Включён</span>
                  <span className={modules.sentiment.enabled ? 'text-green-600 text-xs font-medium' : 'text-red-600 text-xs font-medium'}>
                    {modules.sentiment.enabled ? 'Да' : 'Нет'}
                  </span>
                </div>
              </div>
            </div>

            {/* Twitter Module */}
            <div className="p-4 rounded-lg bg-gray-50/70" data-testid="twitter-module-card">
              <div className="flex items-center gap-2 mb-3">
                <Activity className="w-4 h-4 text-gray-600" />
                <span className="text-sm font-medium text-slate-900">Twitter Parser</span>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between items-center text-sm">
                  <span className="text-gray-500">Статус</span>
                  <span className={`text-xs font-bold ${getModuleStatusColor(modules.twitter.status)}`}>
                    {modules.twitter.status}
                  </span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-gray-500">Parser</span>
                  <span className={modules.twitter.parserEnabled ? 'text-green-600 text-xs font-medium' : 'text-red-600 text-xs font-medium'}>
                    {modules.twitter.parserEnabled ? 'Да' : 'Нет'}
                  </span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-gray-500">Sentiment</span>
                  <span className={modules.twitter.sentimentEnabled ? 'text-green-600 text-xs font-medium' : 'text-red-600 text-xs font-medium'}>
                    {modules.twitter.sentimentEnabled ? 'Да' : 'Нет'}
                  </span>
                </div>
              </div>
            </div>

            {/* Automation Module */}
            <div className="p-4 rounded-lg bg-gray-50/70" data-testid="automation-module-card">
              <div className="flex items-center gap-2 mb-3">
                <Server className="w-4 h-4 text-gray-600" />
                <span className="text-sm font-medium text-slate-900">Automation</span>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between items-center text-sm">
                  <span className="text-gray-500">Статус</span>
                  <span className={`text-xs font-bold ${getModuleStatusColor(modules.automation.status)}`}>
                    {modules.automation.status}
                  </span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-gray-500">Включён</span>
                  <span className={modules.automation.enabled ? 'text-green-600 text-xs font-medium' : 'text-red-600 text-xs font-medium'}>
                    {modules.automation.enabled ? 'Да' : 'Нет'}
                  </span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-gray-500">Работает</span>
                  <span className={modules.automation.running ? 'text-green-600 text-xs font-medium' : 'text-gray-400 text-xs font-medium'}>
                    {modules.automation.running ? 'Активен' : 'Простаивает'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Quick Links */}
        <div className="p-4 rounded-lg bg-gray-50/70">
          <span className="text-sm font-semibold text-slate-900">Управление модулями</span>
          <div className="flex gap-4 flex-wrap mt-3">
            <a href="/admin/ml/sentiment" className="text-sm text-blue-600 hover:text-blue-700 font-medium transition-colors">
              Sentiment Admin
            </a>
            <a href="/admin/ml/twitter-control" className="text-sm text-blue-600 hover:text-blue-700 font-medium transition-colors">
              Twitter Admin
            </a>
            <a href="/admin/ml/automation" className="text-sm text-blue-600 hover:text-blue-700 font-medium transition-colors">
              Automation Admin
            </a>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
