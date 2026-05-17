/**
 * On-chain Admin — Validation Tab
 * Проверка корректности данных
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Loader2, Zap, RefreshCw, AlertTriangle,
} from 'lucide-react';
import { Button } from '../../../../components/ui/button';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

function StatusText({ ok, yes = 'Pass', no = 'Fail' }) {
  return (
    <span className={`text-xs font-bold ${ok ? 'text-emerald-600' : 'text-red-500'}`}>
      {ok ? yes : no}
    </span>
  );
}

function ago(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

export default function ValidationTab() {
  const [stats, setStats] = useState(null);
  const [contradictions, setContradictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [runningBatch, setRunningBatch] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, contradRes] = await Promise.allSettled([
        fetch(`${API_URL}/api/v7/validation/stats`).then(r => r.json()),
        fetch(`${API_URL}/api/v7/validation/contradictions?limit=20`).then(r => r.json()),
      ]);
      if (statsRes.status === 'fulfilled') setStats(statsRes.value);
      if (contradRes.status === 'fulfilled') setContradictions(contradRes.value?.contradictions || []);
    } catch (e) {
      console.error('Validation fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const runBatch = async () => {
    setRunningBatch(true);
    try {
      await fetch(`${API_URL}/api/v7/validation/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      await fetchData();
    } catch (e) {
      console.error('Batch validation error:', e);
    } finally {
      setRunningBatch(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
      </div>
    );
  }

  const validation = stats?.validation || {};
  const kpis = stats?.kpis || {};

  const checks = [
    {
      name: 'Консистентность снимков',
      status: validation.total > 0,
      lastRun: stats?.timestamp || stats?.lastRun,
      errors: validation.by_verdict?.NO_DATA || 0,
    },
    {
      name: 'Проверка сигналов',
      status: kpis.use_contradict_rate ? parseFloat(kpis.use_contradict_rate) < 30 : true,
      lastRun: stats?.timestamp || stats?.lastRun,
      errors: validation.by_verdict?.CONTRADICTS || 0,
    },
    {
      name: 'Пропущенные данные',
      status: (validation.by_verdict?.NO_DATA || 0) < 5,
      lastRun: stats?.timestamp || stats?.lastRun,
      errors: validation.by_verdict?.NO_DATA || 0,
    },
    {
      name: 'Ошибки валидации',
      status: (validation.by_impact?.STRONG_ALERT || 0) === 0,
      lastRun: stats?.timestamp || stats?.lastRun,
      errors: validation.by_impact?.STRONG_ALERT || 0,
    },
  ];

  return (
    <div className="space-y-8" data-testid="onchain-validation-tab">
      {/* Planned module banner */}
      <div className="flex items-center gap-3 p-3 mb-2 rounded-lg bg-amber-50 border border-amber-200" data-testid="planned-module-banner-validation">
        <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0" />
        <div>
          <div className="text-sm font-semibold text-amber-800">Planned module</div>
          <div className="text-xs text-amber-600">Not connected to live pipeline. Валидация будет подключена после стабилизации потоков данных индексера.</div>
        </div>
      </div>
      {/* Action bar */}
      <div className="flex items-center gap-3">
        <Button
          variant="outline" size="sm"
          onClick={runBatch}
          disabled={runningBatch}
          data-testid="btn-run-validation"
        >
          {runningBatch ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Zap className="w-4 h-4 mr-2" />}
          Запустить валидацию
        </Button>
        <Button variant="outline" size="sm" onClick={fetchData} data-testid="btn-refresh-validation">
          <RefreshCw className="w-4 h-4 mr-2" /> Обновить
        </Button>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-lg bg-emerald-50/70">
          <div className="text-xs text-slate-500 font-medium">Подтверждено</div>
          <div className="text-xl font-bold text-emerald-600 mt-1">{kpis.use_confirm_rate || '—'}</div>
        </div>
        <div className="p-4 rounded-lg bg-red-50/70">
          <div className="text-xs text-slate-500 font-medium">Опровергнуто</div>
          <div className="text-xl font-bold text-red-500 mt-1">{kpis.use_contradict_rate || '—'}</div>
        </div>
        <div className="p-4 rounded-lg bg-amber-50/70">
          <div className="text-xs text-slate-500 font-medium">MISS подтверждено</div>
          <div className="text-xl font-bold text-amber-600 mt-1">{kpis.miss_confirm_rate || '—'}</div>
        </div>
        <div className="p-4 rounded-lg bg-slate-50/70">
          <div className="text-xs text-slate-500 font-medium">Снижение уверенности</div>
          <div className="text-xl font-bold text-slate-700 mt-1">{kpis.false_positive_reduced || '—'}</div>
        </div>
      </div>

      {/* Validation Checks Table */}
      <section>
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Проверки</h3>
        <div className="overflow-x-auto bg-slate-50/50 rounded-lg">
          <table className="w-full text-sm" data-testid="validation-checks-table">
            <thead>
              <tr className="text-left text-xs text-slate-500">
                <th className="py-3 px-4">Проверка</th>
                <th className="py-3 px-4">Статус</th>
                <th className="py-3 px-4">Последний запуск</th>
                <th className="py-3 px-4">Ошибки</th>
              </tr>
            </thead>
            <tbody>
              {checks.map((check, i) => (
                <tr key={i} className="border-t border-slate-100">
                  <td className="py-3 px-4 text-slate-700 font-medium">{check.name}</td>
                  <td className="py-3 px-4"><StatusText ok={check.status} /></td>
                  <td className="py-3 px-4 text-slate-500">{ago(check.lastRun)}</td>
                  <td className="py-3 px-4">
                    <span className={check.errors > 0 ? 'text-red-500 font-bold' : 'text-slate-500'}>
                      {check.errors}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Contradictions list */}
      {contradictions.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-slate-700 mb-3">
            Противоречия — последние {contradictions.length}
          </h3>
          <div className="overflow-x-auto bg-slate-50/50 rounded-lg">
            <table className="w-full text-sm" data-testid="contradictions-table">
              <thead>
                <tr className="text-left text-xs text-slate-500">
                  <th className="py-3 px-4">Символ</th>
                  <th className="py-3 px-4">Вердикт</th>
                  <th className="py-3 px-4">Влияние</th>
                  <th className="py-3 px-4">Уверенность</th>
                  <th className="py-3 px-4">Время</th>
                </tr>
              </thead>
              <tbody>
                {contradictions.slice(0, 10).map((c, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    <td className="py-2.5 px-4 text-slate-700 font-medium">{c.symbol || '—'}</td>
                    <td className="py-2.5 px-4">
                      <span className={`text-xs font-bold ${c.verdict === 'CONTRADICTS' ? 'text-red-500' : 'text-emerald-600'}`}>
                        {c.verdict}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 text-slate-500">{c.impact || '—'}</td>
                    <td className="py-2.5 px-4 text-slate-500">{c.confidence ? `${(c.confidence * 100).toFixed(0)}%` : '—'}</td>
                    <td className="py-2.5 px-4 text-slate-400">{ago(c.timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
