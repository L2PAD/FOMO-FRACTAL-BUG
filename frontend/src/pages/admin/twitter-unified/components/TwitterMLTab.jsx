/**
 * Twitter Admin — ML Tab
 * Pipeline статус, runtime flags, data quality
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Zap, Loader2, RefreshCw, AlertTriangle, CheckCircle,
  Activity, Database, Settings,
} from 'lucide-react';
import { Button } from '../../../../components/ui/button';

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

function FlagToggle({ label, enabled, onToggle, loading }) {
  return (
    <div className="flex items-center justify-between p-3 rounded-lg bg-slate-50/70">
      <span className="text-sm text-slate-700">{label}</span>
      <button
        onClick={onToggle}
        disabled={loading}
        className={`px-3 py-1 text-xs font-bold rounded transition-colors ${enabled ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200' : 'bg-slate-200 text-slate-500 hover:bg-slate-300'}`}
        data-testid={`flag-${label.toLowerCase().replace(/\s/g, '-')}`}
      >
        {loading ? '...' : enabled ? 'ON' : 'OFF'}
      </button>
    </div>
  );
}

export default function TwitterMLTab() {
  const [runtimeStatus, setRuntimeStatus] = useState(null);
  const [dataQuality, setDataQuality] = useState(null);
  const [loading, setLoading] = useState(true);
  const [flagLoading, setFlagLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [runtimeRes, qualityRes] = await Promise.allSettled([
        fetch(`${API_URL}/api/v4/admin/runtime/twitter`).then(r => r.json()),
        fetch(`${API_URL}/api/v4/admin/sentiment/twitter/data-quality`).then(r => r.json()),
      ]);
      if (runtimeRes.status === 'fulfilled' && runtimeRes.value?.ok) setRuntimeStatus(runtimeRes.value.data);
      if (qualityRes.status === 'fulfilled' && qualityRes.value?.ok) setDataQuality(qualityRes.value.data);
    } catch (e) {
      console.error('ML fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleFlagToggle = async (flag) => {
    setFlagLoading(true);
    try {
      const body = {};
      const currentVal = runtimeStatus?.[flag]?.status === 'RUNNING';
      body[flag] = !currentVal;
      await fetch(`${API_URL}/api/v4/admin/runtime/twitter/flags`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      await fetchData();
    } catch (e) {
      console.error('Flag toggle error:', e);
    } finally {
      setFlagLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
      </div>
    );
  }

  const runtime = runtimeStatus || {};
  const quality = dataQuality || {};

  return (
    <div className="space-y-8" data-testid="twitter-ml-tab">
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-400">ML pipeline, runtime flags, качество данных</span>
        <button onClick={fetchData} className="text-slate-400 hover:text-slate-700 transition-colors">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Pipeline Status */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <MetricCard
          label="Парсер"
          value={runtime.parser?.status || '—'}
          sub={runtime.parser?.lastRun ? `Последний запуск: ${new Date(runtime.parser.lastRun).toLocaleString('ru-RU')}` : undefined}
          status={runtime.parser?.status === 'RUNNING' ? 'ok' : runtime.parser?.status === 'DISABLED' ? 'warn' : 'error'}
        />
        <MetricCard
          label="Sentiment"
          value={runtime.sentiment?.status || '—'}
          sub={runtime.sentiment?.lastRun ? `Последний запуск: ${new Date(runtime.sentiment.lastRun).toLocaleString('ru-RU')}` : undefined}
          status={runtime.sentiment?.status === 'RUNNING' ? 'ok' : 'warn'}
        />
        <MetricCard
          label="Price Pipeline"
          value={runtime.price?.status || '—'}
          status={runtime.price?.status === 'RUNNING' ? 'ok' : 'warn'}
        />
      </div>

      {/* Runtime Flags */}
      <section>
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Runtime Flags</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <FlagToggle
            label="Parser"
            enabled={runtime.parser?.status === 'RUNNING'}
            onToggle={() => handleFlagToggle('parser')}
            loading={flagLoading}
          />
          <FlagToggle
            label="Sentiment"
            enabled={runtime.sentiment?.status === 'RUNNING'}
            onToggle={() => handleFlagToggle('sentiment')}
            loading={flagLoading}
          />
          <FlagToggle
            label="Price"
            enabled={runtime.price?.status === 'RUNNING'}
            onToggle={() => handleFlagToggle('price')}
            loading={flagLoading}
          />
        </div>
      </section>

      {/* Data Quality */}
      {quality && Object.keys(quality).length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Качество данных</h3>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {quality.completeness != null && (
              <div className="p-3 rounded-lg bg-slate-50/70">
                <div className="text-xs text-slate-500 font-medium">Полнота</div>
                <div className="text-sm font-bold text-slate-700 mt-1">{(quality.completeness * 100).toFixed(1)}%</div>
              </div>
            )}
            {quality.freshness != null && (
              <div className="p-3 rounded-lg bg-slate-50/70">
                <div className="text-xs text-slate-500 font-medium">Свежесть</div>
                <div className="text-sm font-bold text-slate-700 mt-1">{quality.freshness}</div>
              </div>
            )}
            {quality.accuracy != null && (
              <div className="p-3 rounded-lg bg-slate-50/70">
                <div className="text-xs text-slate-500 font-medium">Точность</div>
                <div className="text-sm font-bold text-slate-700 mt-1">{(quality.accuracy * 100).toFixed(1)}%</div>
              </div>
            )}
            {quality.totalTweets != null && (
              <div className="p-3 rounded-lg bg-slate-50/70">
                <div className="text-xs text-slate-500 font-medium">Всего твитов</div>
                <div className="text-sm font-bold text-slate-700 mt-1">{quality.totalTweets.toLocaleString()}</div>
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
