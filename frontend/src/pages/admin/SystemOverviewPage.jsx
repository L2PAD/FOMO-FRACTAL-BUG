/**
 * System — Инфраструктурный обзор платформы
 * Показывает: System Health, Runtime, Networks, Pipeline Timestamps
 * БЕЗ Sentiment (он в ML Intelligence)
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import AdminLayout from '../../components/admin/AdminLayout';
import { useAdminAuth } from '../../context/AdminAuthContext';
import { getSystemOverview } from '../../api/admin.api';
import {
  Activity, Server, RefreshCw, Zap, Globe, Clock,
  CheckCircle, AlertTriangle, XCircle, Loader2,
  Cpu, HardDrive, Gauge,
} from 'lucide-react';

const S = ({ className = '', children }) => (
  <span className={`text-xs font-bold uppercase ${className}`}>
    {typeof children === 'string' ? children.replace(/_/g, ' ') : children}
  </span>
);

const statusColor = (s) => ({
  OK: 'text-green-700', DEGRADED: 'text-yellow-700', RATE_LIMITED: 'text-yellow-700',
  OFFLINE: 'text-red-700', FAILED: 'text-red-700',
}[s] || 'text-red-700');

const statusIcon = (s) => ({
  OK: <CheckCircle className="w-4 h-4 text-green-600" />,
  DEGRADED: <AlertTriangle className="w-4 h-4 text-yellow-600" />,
  RATE_LIMITED: <AlertTriangle className="w-4 h-4 text-yellow-600" />,
}[s] || <XCircle className="w-4 h-4 text-red-600" />);

export default function SystemOverviewPage() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [resources, setResources] = useState(null);
  const [verdictStatus, setVerdictStatus] = useState(null);
  const [standbyStatus, setStandbyStatus] = useState(null);

  const API_URL = process.env.REACT_APP_BACKEND_URL || '';

  const fetchResources = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/admin/resources`);
      const json = await res.json();
      if (json.ok) setResources(json.data);
    } catch {}
  }, [API_URL]);

  const fetchVerdictStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v10/exchange/cache/admin`);
      const json = await res.json();
      if (json.ok && json.data?.job) setVerdictStatus(json.data.job);
    } catch {}
  }, [API_URL]);

  const fetchStandby = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v4/admin/system/standby`);
      const json = await res.json();
      if (json.ok) setStandbyStatus(json.data);
    } catch {}
  }, [API_URL]);

  const fetchData = useCallback(async () => {
    try {
      const result = await getSystemOverview();
      if (result.ok) { setData(result.data); setError(null); }
    } catch (err) {
      if (err.message === 'UNAUTHORIZED') { navigate('/admin/login', { replace: true }); return; }
      setError(err.message);
    } finally { setLoading(false); }
  }, [navigate]);

  useEffect(() => {
    fetchData();
    fetchResources();
    fetchVerdictStatus();
    fetchStandby();
    const i = setInterval(() => { fetchData(); fetchResources(); fetchVerdictStatus(); fetchStandby(); }, 30000);
    return () => clearInterval(i);
  }, [fetchData, fetchResources, fetchVerdictStatus, fetchStandby]);

  if (loading) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center h-32">
          <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
        </div>
      </AdminLayout>
    );
  }

  const { system, runtime, networks, timestamps } = data || {};

  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6 space-y-6" data-testid="system-overview-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity className="w-5 h-5 text-blue-600" />
            <div>
              <h1 className="text-xl font-semibold text-slate-900">System</h1>
              <p className="text-xs text-gray-500">Состояние инфраструктуры платформы</p>
            </div>
          </div>
          <button onClick={fetchData} disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            data-testid="system-refresh">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Обновить
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-3 p-4 bg-red-50/70 rounded-lg">
            <AlertTriangle className="w-5 h-5 text-red-600" />
            <span className="text-sm text-red-800">{error}</span>
          </div>
        )}

        {/* System Health */}
        <div data-testid="system-health-section">
          <div className="flex items-center gap-2 mb-3">
            <Server className="w-4 h-4 text-gray-600" />
            <span className="text-sm font-semibold text-slate-900"
              title="Состояние всех сервисов платформы. OK = работает, DEGRADED = частичные проблемы, OFFLINE = недоступен">
              Здоровье системы
            </span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { key: 'backend', label: 'Backend', tip: 'Node.js API сервер' },
              { key: 'mlService', label: 'ML Service', tip: 'Python ML сервис предсказаний' },
              { key: 'priceService', label: 'Price Service', tip: 'Поставщик рыночных данных' },
              { key: 'providerPool', label: 'Provider Pool', tip: 'Пул провайдеров данных' },
            ].map(({ key, label, tip }) => {
              const svc = system?.[key];
              const status = svc?.status || 'OFFLINE';
              return (
                <div key={key} className="p-4 rounded-lg bg-white border border-gray-100 shadow-sm hover:shadow-md transition-shadow" title={tip}>
                  <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">{label}</p>
                  <div className="flex items-center gap-2">
                    {statusIcon(status)}
                    <S className={statusColor(status)}>{status}</S>
                  </div>
                  {svc?.latencyMs && <p className="text-xs text-gray-400 mt-1">{svc.latencyMs}ms</p>}
                  {key === 'providerPool' && svc && (
                    <p className="text-xs text-gray-400 mt-1">{svc.healthyCount || 0}/{svc.totalCount || 0} healthy</p>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* ═══ Resources Monitor ═══ */}
        {resources && (
          <div data-testid="resources-section">
            <div className="flex items-center gap-2 mb-3">
              <Gauge className="w-4 h-4 text-orange-600" />
              <span className="text-sm font-semibold text-slate-900">Ресурсы системы</span>
              {resources.health && (
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                  resources.health === 'OK' ? 'bg-emerald-50 text-emerald-700' :
                  resources.health === 'WARNING' ? 'bg-amber-50 text-amber-700' :
                  'bg-red-50 text-red-700'
                }`}>{resources.health === 'OK' ? 'НОРМА' : resources.health === 'WARNING' ? 'ВНИМАНИЕ' : 'КРИТИЧНО'}</span>
              )}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {/* CPU */}
              <div className="p-4 rounded-lg bg-white border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-blue-500" />
                    <span className="text-xs text-gray-500 uppercase">CPU</span>
                  </div>
                  <span className={`text-sm font-bold ${
                    resources.cpu.loadPercent >= 70 ? 'text-red-600' :
                    resources.cpu.loadPercent >= 50 ? 'text-amber-600' : 'text-slate-800'
                  }`}>{resources.cpu.loadPercent}%</span>
                </div>
                <div className="h-2 bg-gray-200 rounded-full overflow-hidden mb-2">
                  <div className={`h-full rounded-full transition-all ${
                    resources.cpu.loadPercent >= 70 ? 'bg-red-500' :
                    resources.cpu.loadPercent >= 50 ? 'bg-amber-500' : 'bg-blue-500'
                  }`} style={{ width: `${Math.min(100, resources.cpu.loadPercent)}%` }} />
                </div>
                <div className="flex justify-between text-xs text-gray-400">
                  <span>{resources.cpu.cores} ядер</span>
                  <span>Load: {resources.cpu.loadAvg[0]} / {resources.cpu.loadAvg[1]} / {resources.cpu.loadAvg[2]}</span>
                </div>
              </div>
              
              {/* Memory */}
              <div className="p-4 rounded-lg bg-white border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <HardDrive className="w-4 h-4 text-purple-500" />
                    <span className="text-xs text-gray-500 uppercase">Память</span>
                  </div>
                  <span className={`text-sm font-bold ${
                    resources.memory.percent >= 80 ? 'text-red-600' :
                    resources.memory.percent >= 65 ? 'text-amber-600' : 'text-slate-800'
                  }`}>{resources.memory.percent}%</span>
                </div>
                <div className="h-2 bg-gray-200 rounded-full overflow-hidden mb-2">
                  <div className={`h-full rounded-full transition-all ${
                    resources.memory.percent >= 80 ? 'bg-red-500' :
                    resources.memory.percent >= 65 ? 'bg-amber-500' : 'bg-purple-500'
                  }`} style={{ width: `${resources.memory.percent}%` }} />
                </div>
                <div className="flex justify-between text-xs text-gray-400">
                  <span>{Math.round(resources.memory.usedMB / 1024 * 10) / 10} / {Math.round(resources.memory.totalMB / 1024 * 10) / 10} GB</span>
                  <span>Свободно: {Math.round(resources.memory.availableMB / 1024 * 10) / 10} GB</span>
                </div>
              </div>
              
              {/* Parsers Health */}
              <div className="p-4 rounded-lg bg-white border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-center gap-2 mb-2">
                  <Activity className="w-4 h-4 text-cyan-500" />
                  <span className="text-xs text-gray-500 uppercase">Парсеры</span>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-slate-600">Twitter</span>
                    {standbyStatus ? (
                      <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${
                        standbyStatus.state === 'ACTIVE' ? 'bg-emerald-50 text-emerald-700' :
                        standbyStatus.state === 'STANDBY' ? 'bg-amber-50 text-amber-700' : 'bg-gray-100 text-gray-500'
                      }`}>
                        {standbyStatus.state === 'ACTIVE' ? 'АКТИВЕН' : standbyStatus.state === 'STANDBY' ? 'ОЖИДАНИЕ' : 'Н/Д'}
                        {standbyStatus.okSessions > 0 && ` (${standbyStatus.okSessions}/${standbyStatus.totalSessions})`}
                      </span>
                    ) : <span className="text-xs text-gray-400">—</span>}
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-slate-600">Verdict Extended</span>
                    {verdictStatus?.extended ? (
                      <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${
                        verdictStatus.extended.paused ? 'bg-amber-50 text-amber-700' :
                        verdictStatus.extended.enabled ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-500'
                      }`}>
                        {verdictStatus.extended.paused ? 'ПАУЗА' : verdictStatus.extended.enabled ? 'АКТИВЕН' : 'ВЫКЛ'}
                      </span>
                    ) : <span className="text-xs text-gray-400">—</span>}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Runtime */}
        <div data-testid="runtime-section">
          <div className="flex items-center gap-2 mb-3">
            <Zap className="w-4 h-4 text-amber-600" />
            <span className="text-sm font-semibold text-slate-900"
              title="Текущий режим работы системы">
              Среда исполнения
            </span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-4 rounded-lg bg-white border border-gray-100 shadow-sm hover:shadow-md transition-shadow"
              title="RULES_ONLY = алгоритмический. ADVISORY = ML предлагает. INFLUENCE = ML корректирует уверенность">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Режим решений</p>
              <S className="text-blue-700">{runtime?.decisionMode || 'RULES_ONLY'}</S>
            </div>
            <div className="p-4 rounded-lg bg-white border border-gray-100 shadow-sm hover:shadow-md transition-shadow"
              title="ON = ML модель корректирует confidence. OFF = только правила">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">ML влияние</p>
              <S className={runtime?.mlInfluence ? 'text-green-700' : 'text-gray-500'}>
                {runtime?.mlInfluence ? 'ON' : 'OFF'}
              </S>
            </div>
            <div className="p-4 rounded-lg bg-white border border-gray-100 shadow-sm hover:shadow-md transition-shadow"
              title="Экстренная остановка. ARMED = готов к активации">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Kill Switch</p>
              <S className={runtime?.killSwitch ? 'text-red-700' : 'text-green-700'}>
                {runtime?.killSwitch ? 'ARMED' : 'DISARMED'}
              </S>
            </div>
            <div className="p-4 rounded-lg bg-white border border-gray-100 shadow-sm hover:shadow-md transition-shadow"
              title="LOW = стабильно. MEDIUM = мониторить. HIGH = требуется вмешательство">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Уровень дрифта</p>
              <S className={
                runtime?.driftLevel === 'HIGH' ? 'text-red-700' :
                runtime?.driftLevel === 'MEDIUM' ? 'text-yellow-700' : 'text-green-700'
              }>{runtime?.driftLevel || 'LOW'}</S>
            </div>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          {/* Networks */}
          <div data-testid="networks-section">
            <div className="flex items-center gap-2 mb-3">
              <Globe className="w-4 h-4 text-purple-600" />
              <span className="text-sm font-semibold text-slate-900">Сети</span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {networks && Object.entries(networks).map(([name, enabled]) => (
                <div key={name} className={`flex items-center gap-2 px-3 py-2 rounded-lg ${
                  enabled ? 'bg-white border border-gray-100 shadow-sm hover:shadow-md transition-shadow' : 'bg-gray-50/40 opacity-50'
                }`}>
                  <div className={`w-2 h-2 rounded-full ${enabled ? 'bg-green-500' : 'bg-gray-300'}`} />
                  <span className="text-sm font-medium text-slate-700 capitalize">{name}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Pipeline Timestamps */}
          <div data-testid="timestamps-section">
            <div className="flex items-center gap-2 mb-3">
              <Clock className="w-4 h-4 text-gray-600" />
              <span className="text-sm font-semibold text-slate-900">Временные метки</span>
            </div>
            <div className="space-y-2">
              {[
                { label: 'Сборка фичей', key: 'lastFeatureBuild' },
                { label: 'Разметка', key: 'lastLabeling' },
                { label: 'Сборка датасета', key: 'lastDatasetBuild' },
                { label: 'ML Inference', key: 'lastMLInference' },
              ].map(({ label, key }) => (
                <div key={key} className="flex items-center justify-between p-2.5 bg-white border border-gray-100 shadow-sm hover:shadow-md transition-shadow rounded-lg">
                  <span className="text-sm text-gray-600">{label}</span>
                  <span className="text-sm font-medium text-slate-900">
                    {timestamps?.[key] ? new Date(timestamps[key]).toLocaleTimeString() : '—'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
