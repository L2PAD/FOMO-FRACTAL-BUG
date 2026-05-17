/**
 * On-chain Admin — Research (Advanced) Tab
 * Экспериментальный слой
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  FlaskConical, Loader2, Brain,
  BarChart3, Target, RefreshCw,
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

export default function ResearchTab() {
  const [observationData, setObservationData] = useState(null);
  const [mlStatus, setMlStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [trainingLoading, setTrainingLoading] = useState(false);

  const PLANNED_BANNER = (
    <div className="flex items-center gap-3 p-3 mb-6 rounded-lg bg-amber-50 border border-amber-200" data-testid="planned-module-banner">
      <FlaskConical className="w-5 h-5 text-amber-600 flex-shrink-0" />
      <div>
        <div className="text-sm font-semibold text-amber-800">Planned module</div>
        <div className="text-xs text-amber-600">Not connected to live pipeline. Observation model и ML training будут подключены после стабилизации индексера.</div>
      </div>
    </div>
  );

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, metricsRes, mlRes] = await Promise.allSettled([
        fetch(`${API_URL}/api/v6/observation/stats`).then(r => r.json()),
        fetch(`${API_URL}/api/v6/observation/metrics/summary`).then(r => r.json()),
        fetch(`${API_URL}/api/v6/observation/ml/status`).then(r => r.json()),
      ]);
      if (statsRes.status === 'fulfilled') {
        setObservationData(prev => ({ ...prev, stats: statsRes.value }));
      }
      if (metricsRes.status === 'fulfilled') {
        setObservationData(prev => ({ ...prev, metrics: metricsRes.value }));
      }
      if (mlRes.status === 'fulfilled') setMlStatus(mlRes.value);
    } catch (e) {
      console.error('Research fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const runTraining = async () => {
    setTrainingLoading(true);
    try {
      await fetch(`${API_URL}/api/v6/observation/ml/train`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      await fetchData();
    } catch (e) {
      console.error('Training error:', e);
    } finally {
      setTrainingLoading(false);
    }
  };

  const stats = observationData?.stats;
  const metrics = observationData?.metrics;
  const byDecision = stats?.byDecision || {};
  const total = stats?.total || 0;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-8" data-testid="onchain-research-tab">
      {PLANNED_BANNER}
      {/* Advanced badge */}
      <div className="flex items-center gap-3">
        <FlaskConical className="w-5 h-5 text-purple-600" />
        <span className="text-sm font-bold text-purple-600 bg-purple-50 px-2 py-0.5 rounded">Advanced</span>
        <span className="text-xs text-slate-400">Экспериментальные инструменты</span>
      </div>

      {/* Observation Model Stats */}
      <section>
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Модель наблюдения</h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="Всего наблюдений"
            value={total}
            status={total > 0 ? 'ok' : 'warn'}
          />
          <MetricCard
            label="USE Rate"
            value={total > 0 ? `${((byDecision.USE || 0) / total * 100).toFixed(1)}%` : '—'}
            sub={`${byDecision.USE || 0} сигналов`}
            status={byDecision.USE > 0 ? 'ok' : 'warn'}
          />
          <MetricCard
            label="MISS Rate"
            value={total > 0 ? `${((byDecision.MISS_ALERT || 0) / total * 100).toFixed(1)}%` : '—'}
            sub={`${byDecision.MISS_ALERT || 0} слепых зон`}
            status={(byDecision.MISS_ALERT || 0) / total > 0.1 ? 'warn' : 'ok'}
          />
          <MetricCard
            label="Ложная уверенность"
            value={metrics?.falseConfidenceRate != null ? `${metrics.falseConfidenceRate.toFixed(1)}%` : '—'}
            status={metrics?.falseConfidenceRate > 30 ? 'error' : 'ok'}
          />
        </div>
      </section>

      {/* ML Status */}
      <section>
        <h3 className="text-sm font-semibold text-slate-700 mb-3">ML Модель</h3>
        {mlStatus ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              label="Загружена"
              value={mlStatus.loaded ? 'Да' : 'Нет'}
              status={mlStatus.loaded ? 'ok' : 'warn'}
            />
            <MetricCard
              label="Версия"
              value={mlStatus.version || '—'}
            />
            <MetricCard
              label="Accuracy"
              value={mlStatus.accuracy != null ? `${(mlStatus.accuracy * 100).toFixed(1)}%` : '—'}
              status={mlStatus.accuracy > 0.7 ? 'ok' : mlStatus.accuracy > 0.5 ? 'warn' : 'error'}
            />
            <MetricCard
              label="Обучающих записей"
              value={mlStatus.trainingSamples ?? '—'}
            />
          </div>
        ) : (
          <div className="text-sm text-slate-400 p-4 bg-slate-50/70 rounded-lg">ML модель недоступна</div>
        )}

        <div className="mt-4">
          <Button
            variant="outline" size="sm"
            onClick={runTraining}
            disabled={trainingLoading}
            data-testid="btn-run-training"
          >
            {trainingLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Brain className="w-4 h-4 mr-2" />}
            Запустить обучение
          </Button>
        </div>
      </section>

      {/* Experiments */}
      <section>
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Эксперименты</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-5 rounded-lg bg-slate-50/70">
            <div className="flex items-center gap-2 mb-2">
              <BarChart3 className="w-4 h-4 text-slate-500" />
              <span className="text-sm font-semibold text-slate-700">Backtesting</span>
            </div>
            <p className="text-xs text-slate-400">
              Проверка on-chain сигналов на исторических данных. Оценка точности прогнозов.
            </p>
            <div className="mt-3 text-xs text-slate-400">Статус: —  |  Последний запуск: —  |  Ошибки: 0</div>
          </div>
          <div className="p-5 rounded-lg bg-slate-50/70">
            <div className="flex items-center gap-2 mb-2">
              <Target className="w-4 h-4 text-slate-500" />
              <span className="text-sm font-semibold text-slate-700">Scenario Testing</span>
            </div>
            <p className="text-xs text-slate-400">
              Моделирование поведения движка при различных рыночных сценариях.
            </p>
            <div className="mt-3 text-xs text-slate-400">Статус: —  |  Последний запуск: —  |  Ошибки: 0</div>
          </div>
        </div>
      </section>

      {/* Refresh */}
      <div>
        <Button variant="outline" size="sm" onClick={fetchData} data-testid="btn-refresh-research">
          <RefreshCw className="w-4 h-4 mr-2" /> Обновить
        </Button>
      </div>
    </div>
  );
}
