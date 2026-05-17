/**
 * Twitter Admin — Connections Tab
 * Twitter Adapter + Network (adapter health, latency, connection status)
 * Не ломаем Connections — только показываем статус адаптера
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Zap, Loader2, RefreshCw, Activity, ArrowRight,
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
    <div className={`p-4 rounded-lg ${bg}`}>
      <div className="text-xs text-slate-500 font-medium mb-1">{label}</div>
      <div className={`text-lg font-bold ${color}`}>{value ?? '—'}</div>
      {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
    </div>
  );
}

export default function TwitterConnectionsTab() {
  const [adapterStatus, setAdapterStatus] = useState(null);
  const [networkHealth, setNetworkHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [adapterRes, networkRes] = await Promise.allSettled([
        fetch(`${API_URL}/api/connections/admin/twitter-adapter/status`).then(r => r.json()),
        fetch(`${API_URL}/api/admin/connections/network-health`).then(r => r.json()),
      ]);
      if (adapterRes.status === 'fulfilled') setAdapterStatus(adapterRes.value);
      if (networkRes.status === 'fulfilled') setNetworkHealth(networkRes.value);
    } catch (e) {
      console.error('Connections fetch error:', e);
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

  const adapter = adapterStatus || {};
  const network = networkHealth || {};

  return (
    <div className="space-y-8" data-testid="twitter-connections-tab">
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-400">Twitter Adapter + Network</span>
        <button onClick={fetchData} className="text-slate-400 hover:text-slate-700 transition-colors">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Adapter Status */}
      <section>
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Twitter Adapter</h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="Режим"
            value={adapter.mode || '—'}
            status={adapter.mode === 'live' ? 'ok' : adapter.mode === 'mock' ? 'warn' : undefined}
          />
          <MetricCard
            label="Статус"
            value={adapter.enabled ? 'Включён' : 'Выключен'}
            status={adapter.enabled ? 'ok' : 'error'}
          />
          <MetricCard
            label="Источники"
            value={adapter.sources?.length ?? '—'}
            status={(adapter.sources?.length ?? 0) > 0 ? 'ok' : 'warn'}
          />
          <MetricCard
            label="Последний запуск"
            value={adapter.lastRun ? new Date(adapter.lastRun).toLocaleString('ru-RU') : '—'}
          />
        </div>
      </section>

      {/* Network Health */}
      <section>
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Network Health</h3>
        {network && Object.keys(network).length > 0 ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              label="Статус сети"
              value={network.status || '—'}
              status={network.status === 'healthy' ? 'ok' : 'warn'}
            />
            <MetricCard
              label="Задержка"
              value={network.latency ? `${network.latency}ms` : '—'}
              status={network.latency < 500 ? 'ok' : 'warn'}
            />
            <MetricCard
              label="Активные соединения"
              value={network.activeConnections ?? '—'}
            />
            <MetricCard
              label="Ошибки"
              value={network.errors ?? 0}
              status={(network.errors ?? 0) > 0 ? 'warn' : 'ok'}
            />
          </div>
        ) : (
          <div className="text-sm text-slate-400 p-4 bg-slate-50/70 rounded-lg">Данные недоступны</div>
        )}
      </section>

      {/* Link to full Connections admin */}
      <div>
        <Link
          to="/admin/connections"
          className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-800 transition-colors"
          data-testid="link-full-connections"
        >
          Полный Connections модуль <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  );
}
