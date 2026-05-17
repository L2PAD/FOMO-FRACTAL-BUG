/**
 * Twitter Admin — Overview Tab
 * Операционный центр: статус парсера, здоровье, сводка
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity, Server, Database, Users, Clock, AlertTriangle,
  CheckCircle, XCircle, Loader2, Key, Zap, RefreshCw,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

function MetricCard({ label, value, sub, status }) {
  const color =
    status === 'ok' ? 'text-emerald-600'
    : status === 'warn' ? 'text-amber-600'
    : status === 'error' ? 'text-red-500'
    : 'text-slate-700';
  const bg =
    status === 'ok' ? 'bg-emerald-50/70'
    : status === 'warn' ? 'bg-amber-50/70'
    : status === 'error' ? 'bg-red-50/70'
    : 'bg-slate-50/70';
  return (
    <div className={`p-4 rounded-lg ${bg}`} data-testid={`tw-metric-${label.replace(/\s/g, '-').toLowerCase()}`}>
      <div className="text-xs text-slate-500 font-medium mb-1">{label}</div>
      <div className={`text-lg font-bold ${color}`}>{value ?? '—'}</div>
      {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
    </div>
  );
}

function StatusDot({ ok }) {
  return <span className={`inline-block w-2.5 h-2.5 rounded-full ${ok ? 'bg-emerald-500' : 'bg-red-500'}`} />;
}

export default function TwitterOverviewTab() {
  const [parserHealth, setParserHealth] = useState(null);
  const [systemOverview, setSystemOverview] = useState(null);
  const [runtimeStatus, setRuntimeStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [healthRes, overviewRes, runtimeRes] = await Promise.allSettled([
        fetch(`${API_URL}/api/v4/admin/system/health`).then(r => r.json()),
        fetch(`${API_URL}/api/v4/admin/twitter/system/overview`).then(r => r.json()),
        fetch(`${API_URL}/api/v4/admin/runtime/twitter`).then(r => r.json()),
      ]);
      if (healthRes.status === 'fulfilled' && healthRes.value?.ok) setParserHealth(healthRes.value.data);
      if (overviewRes.status === 'fulfilled' && overviewRes.value?.ok) setSystemOverview(overviewRes.value.data);
      if (runtimeRes.status === 'fulfilled' && runtimeRes.value?.ok) setRuntimeStatus(runtimeRes.value.data);
    } catch (e) {
      console.error('Twitter overview fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
      </div>
    );
  }

  const parser = parserHealth?.parser || {};
  const browser = parserHealth?.browser || {};
  const sessions = parserHealth?.sessions || {};
  const limiter = parserHealth?.limiter || {};
  const overview = systemOverview || {};
  const runtime = runtimeStatus || {};

  const parserOk = parser.status === 'UP' || parser.status === 'ONLINE';
  const browserOk = browser.status === 'UP' || browser.status === 'ONLINE';
  const systemOk = parserOk && browserOk;

  return (
    <div className="space-y-8" data-testid="twitter-overview-tab">
      {/* System Health banner */}
      <div className="flex items-center gap-3">
        <StatusDot ok={systemOk} />
        <span className={`text-lg font-bold ${systemOk ? 'text-emerald-600' : 'text-red-500'}`}>
          {systemOk ? 'HEALTHY' : parserOk ? 'DEGRADED' : 'DOWN'}
        </span>
        <button onClick={fetchData} className="ml-auto text-slate-400 hover:text-slate-700 transition-colors">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Parser Status */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Parser Service"
          value={parser.status || '—'}
          sub={parser.url || undefined}
          status={parserOk ? 'ok' : 'error'}
        />
        <MetricCard
          label="Browser"
          value={browser.status || '—'}
          status={browserOk ? 'ok' : 'error'}
        />
        <MetricCard
          label="Активные сессии"
          value={sessions.total ?? '—'}
          sub={sessions.valid != null ? `Валидных: ${sessions.valid}` : undefined}
          status={sessions.valid > 0 ? 'ok' : sessions.total > 0 ? 'warn' : 'error'}
        />
        <MetricCard
          label="Stale / Invalid"
          value={`${sessions.stale ?? 0} / ${sessions.invalid ?? 0}`}
          status={(sessions.stale ?? 0) + (sessions.invalid ?? 0) > 0 ? 'warn' : 'ok'}
        />
      </div>

      {/* Runtime & ML */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Парсер (Runtime)"
          value={runtime.parser?.status || '—'}
          status={runtime.parser?.status === 'RUNNING' ? 'ok' : 'warn'}
        />
        <MetricCard
          label="Sentiment Pipeline"
          value={runtime.sentiment?.status || '—'}
          status={runtime.sentiment?.status === 'RUNNING' ? 'ok' : 'warn'}
        />
        <MetricCard
          label="Юзеры отслеживаются"
          value={overview.totalUsers ?? '—'}
          status={(overview.totalUsers ?? 0) > 0 ? 'ok' : 'warn'}
        />
        <MetricCard
          label="Здоровые / Проблемные"
          value={`${overview.healthyUsers ?? 0} / ${overview.warningUsers ?? 0}`}
          status={(overview.warningUsers ?? 0) === 0 ? 'ok' : 'warn'}
        />
      </div>

      {/* Rate Limiter */}
      {limiter && (
        <div>
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Rate Limiter</h3>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            {Object.entries(limiter).map(([key, val]) => (
              <div key={key} className="p-3 rounded-lg bg-slate-50/70">
                <div className="text-xs text-slate-500 font-medium">{key}</div>
                <div className="text-sm font-bold text-slate-700 mt-1">{typeof val === 'object' ? JSON.stringify(val) : String(val)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
