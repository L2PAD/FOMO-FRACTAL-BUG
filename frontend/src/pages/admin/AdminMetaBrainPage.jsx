/**
 * Meta-Brain Admin Dashboard — ML Control Center
 * ================================================
 *
 * 7 tabs answering 3 core questions:
 *   - What did the model decide? (Overview, Decisions)
 *   - Why did it decide that? (Signals)
 *   - Is it working at all? (Engine, Drift, Dataset, Policy)
 *
 * TABS:
 * 1. Overview  — system status, verdict, coverage, active signals
 * 2. Engine    — providers, alignment, run pipeline
 * 3. Signals   — module signals + forecast + health + conflict
 * 4. Decisions — decision timeline + explainability
 * 5. Drift     — signal drift, correlation
 * 6. Dataset   — ML training runs, hit rate
 * 7. Policy    — weights, regime, thresholds
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminLayout from '../../components/admin/AdminLayout';
import { useAdminAuth } from '../../context/AdminAuthContext';
import { Button } from '../../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/card';
import { Progress } from '../../components/ui/progress';
import {
  Activity, RefreshCw, CheckCircle, XCircle, AlertTriangle,
  Brain, Zap, Loader2, Target, TrendingUp, Shield,
  ArrowUp, ArrowDown, Minus, Clock, Play, Radio,
  Database, GitBranch, Scale, Gauge, Eye, ChevronDown, ChevronUp,
  ToggleLeft, ToggleRight, Settings2,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

/* ───────────── Helpers ───────────── */
const fmt = (v, d = 1) => typeof v === 'number' ? v.toFixed(d) : '—';
const pct = (v) => typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : '—';
const ts = (v) => v ? new Date(v).toLocaleString() : '—';
const ago = (tsMs) => {
  if (!tsMs) return '—';
  const d = Date.now() - tsMs;
  if (d < 60000) return `${Math.round(d / 1000)}s`;
  if (d < 3600000) return `${Math.round(d / 60000)}m`;
  if (d < 86400000) return `${Math.round(d / 3600000)}h`;
  return `${Math.round(d / 86400000)}d`;
};
const dirIcon = (d) => d === 'LONG' || d === 'BULLISH' ? <ArrowUp className="w-3.5 h-3.5 text-green-600" /> :
  d === 'SHORT' || d === 'BEARISH' ? <ArrowDown className="w-3.5 h-3.5 text-red-600" /> :
  <Minus className="w-3.5 h-3.5 text-gray-400" />;
const dirColor = (d) => d === 'LONG' || d === 'BULLISH' ? 'text-green-700' :
  d === 'SHORT' || d === 'BEARISH' ? 'text-red-700' : 'text-gray-600';

const healthColor = (h) => h === 'OK' ? 'bg-green-500' : h === 'WARN' ? 'bg-yellow-500' : 'bg-red-500';
const healthBadge = (h) => h === 'OK' ? 'text-green-700' : h === 'WARN' ? 'text-yellow-700' : 'text-red-700';

/* Flat status text — replaces pill badges to eliminate all visual outlines */
const S = ({ className = '', children }) => (
  <span className={`text-xs font-bold uppercase ${className}`}>{children}</span>
);

const displayText = (text) => String(text || '').replace(/_/g, ' ');

const SCard = ({ children, className = '' }) => (
  <Card className={`bg-white shadow-none rounded-lg ${className}`}>{children}</Card>
);
const Loading = () => <div className="flex items-center justify-center h-48"><Loader2 className="w-6 h-6 text-indigo-400 animate-spin" /></div>;

/* Compute signal conflict: variance of direction scores */
const computeConflict = (signals) => {
  if (!signals?.length) return { score: 0, level: 'NONE' };
  const vals = signals.map(s => {
    if (s.direction === 'LONG' || s.direction === 'BULLISH') return 1;
    if (s.direction === 'SHORT' || s.direction === 'BEARISH') return -1;
    return 0;
  });
  const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
  const variance = vals.reduce((a, v) => a + (v - mean) ** 2, 0) / vals.length;
  const score = Math.sqrt(variance);
  return {
    score: score.toFixed(2),
    level: score < 0.3 ? 'LOW' : score < 0.6 ? 'MEDIUM' : 'HIGH',
  };
};

/* Compute system stability from coverage, drift, conflict, confidence */
const computeStability = (coverage, driftModules, conflict, confidence) => {
  let issues = 0;
  const details = [];

  const cov = coverage?.aligned || 0;
  const total = coverage?.total || 4;
  if (cov < 2) { issues += 2; details.push(`coverage ${cov}/${total}`); }
  else if (cov < total) { issues += 1; details.push(`coverage ${cov}/${total}`); }

  const maxDrift = Math.max(...(driftModules || []).map(m => m.driftScore || 0), 0);
  if (maxDrift > 0.4) { issues += 2; details.push(`drift ${maxDrift.toFixed(2)}`); }
  else if (maxDrift > 0.2) { issues += 1; details.push(`drift ${maxDrift.toFixed(2)}`); }

  const conflictNum = parseFloat(conflict?.score || 0);
  if (conflictNum > 0.6) { issues += 2; details.push('high conflict'); }
  else if (conflictNum > 0.3) { issues += 1; details.push('medium conflict'); }

  if (typeof confidence === 'number' && confidence < 0.3) { issues += 1; details.push(`low confidence`); }

  const level = issues === 0 ? 'STABLE' : issues <= 2 ? 'WARNING' : 'UNSTABLE';
  return { level, issues, details };
};

/* Auto-refresh intervals per tab (ms) */
const REFRESH_INTERVALS = {
  overview: 30000,
  engine: 30000,
  signals: 30000,
  decisions: 60000,
  drift: 120000,
  dataset: null, // manual only
  policy: null,  // no refresh
  modules: null, // manual only
};

/* ═══════════ Tab 1: OVERVIEW ═══════════ */
const OverviewTab = ({ state, status, signals, policy, drift, dataset, loading }) => {
  if (loading) return <Loading />;

  const s = state?.state || {};
  const rawSignals = signals?.signals || [];
  const dropped = signals?.aligned?.dropped || [];
  const coverage = signals?.aligned?.coverage || {};
  const conflict = computeConflict(rawSignals);
  const stability = computeStability(coverage, drift?.modules, conflict, s.lastScore);

  return (
    <div className="space-y-5" data-testid="overview-tab">
      {/* System Status Banner */}
      <div className="p-4 rounded-xl bg-gradient-to-r from-indigo-50 to-purple-50">
        <div className="grid grid-cols-2 md:grid-cols-7 gap-4">
          <div>
            <p className="text-xs text-gray-500 mb-1">Система</p>
            <div className="flex items-center gap-1.5">
              <span className={`w-2.5 h-2.5 rounded-full ${coverage.aligned >= 2 ? 'bg-green-500' : 'bg-red-500'}`} />
              <span className="text-sm font-semibold text-gray-900">
                {coverage.aligned >= 2 ? 'ONLINE' : 'ПРОБЛЕМЫ'}
              </span>
            </div>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1">Вердикт</p>
            <div className="flex items-center gap-1">
              {dirIcon(s.lastVerdict)}
              <span className="text-sm font-bold text-gray-900">{s.lastVerdict || '—'}</span>
            </div>
          </div>
          <div title="Совокупный скор модели — используется для определения направления">
            <p className="text-xs text-gray-500 mb-1">Скор</p>
            <span className="text-sm font-bold text-gray-900">{fmt(s.lastScore, 3)}</span>
          </div>
          <div title="Сколько модулей из общего числа дают сигнал в одном направлении">
            <p className="text-xs text-gray-500 mb-1">Покрытие</p>
            <span className="text-sm font-bold text-gray-900">{coverage.aligned || 0}/{coverage.total || 4}</span>
          </div>
          <div title="Текущий рыночный режим — определяет пороги и policy">
            <p className="text-xs text-gray-500 mb-1">Режим</p>
            <S className="text-purple-700">{policy?.regime || '—'}</S>
          </div>
          <div title="STABLE — система работает стабильно, WARNING — есть проблемы, UNSTABLE — критическая нестабильность">
            <p className="text-xs text-gray-500 mb-1">Стабильность</p>
            <S className={`${
              stability.level === 'STABLE' ? 'text-green-700' :
              stability.level === 'WARNING' ? 'text-yellow-700' :
              'text-red-700'
            }`}>{stability.level}</S>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1">Обновлено</p>
            <span className="text-xs font-medium text-gray-700">{ago(s.lastUpdatedTs)}</span>
          </div>
        </div>
      </div>

      {/* Decision Quality + Diagnostics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <SCard>
          <CardContent className="p-4 text-center" title="Точность прогнозов — процент верных решений">
            <p className="text-xs text-gray-500 mb-1">Hit Rate</p>
            <p className="text-2xl font-bold text-gray-900">{dataset?.hitRate ? pct(dataset.hitRate) : '—'}</p>
            <p className="text-xs text-gray-400 mt-0.5">{dataset?.evaluated || 0} оценено</p>
          </CardContent>
        </SCard>
        <SCard>
          <CardContent className="p-4 text-center" title="LOW — модули согласованы, MEDIUM — есть расхождения, HIGH — сильный конфликт">
            <p className="text-xs text-gray-500 mb-1">Конфликт</p>
            <S className={`${
              conflict.level === 'LOW' ? 'text-green-700' :
              conflict.level === 'MEDIUM' ? 'text-yellow-700' :
              'text-red-700'
            }`}>{conflict.level}</S>
            <p className="text-xs text-gray-400 mt-1">{conflict.score}</p>
          </CardContent>
        </SCard>
        <SCard>
          <CardContent className="p-4 text-center" title="Количество модулей, дающих сигнал в одном направлении">
            <p className="text-xs text-gray-500 mb-1">Покрытие</p>
            <p className="text-2xl font-bold text-gray-900">{coverage.aligned || 0}/{coverage.total || 4}</p>
          </CardContent>
        </SCard>
        <SCard>
          <CardContent className="p-4 text-center" title="Период ожидания между решениями. ACTIVE — новое решение временно заблокировано">
            <p className="text-xs text-gray-500 mb-1">Cooldown</p>
            <S className={`${s.cooldownUntilTs > Date.now() ? 'text-yellow-700' : 'text-green-700'}`}>
              {s.cooldownUntilTs > Date.now() ? 'ACTIVE' : 'NONE'}
            </S>
          </CardContent>
        </SCard>
      </div>

      {/* System Stability Details */}
      {stability.details.length > 0 && (
        <SCard className={stability.level === 'UNSTABLE' ? 'bg-red-50/70' : 'bg-yellow-50/70'}>
          <CardContent className="p-3 flex items-center gap-2">
            <AlertTriangle className={`w-4 h-4 ${stability.level === 'UNSTABLE' ? 'text-red-500' : 'text-yellow-500'}`} />
            <span className="text-sm text-gray-700">Проблемы стабильности: {stability.details.join(', ')}</span>
          </CardContent>
        </SCard>
      )}

      {/* Active Signals per module */}
      <SCard>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-700">Активные сигналы</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {rawSignals.map(s => (
              <div key={s.module} className="p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-800 capitalize">{s.module}</span>
                  <span className={`w-2 h-2 rounded-full ${healthColor(s.health)}`} />
                </div>
                <div className="flex items-center gap-1.5 mb-1">
                  {dirIcon(s.direction)}
                  <span className="font-semibold text-gray-900 text-sm">{s.direction}</span>
                </div>
                <div className="flex justify-between text-xs text-gray-500">
                  <span>conf: {pct(s.confidence)}</span>
                  <span>{ago(s.asOfTs)}</span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </SCard>

      {/* Dropped modules */}
      {dropped.length > 0 && (
        <SCard className="bg-orange-50/70">
          <CardContent className="p-4">
            <p className="text-xs text-orange-600 font-medium uppercase mb-2">Пропущенные сигналы ({dropped.length})</p>
            <div className="space-y-1.5">
              {dropped.map(d => (
                <div key={d.module} className="flex items-center gap-2 text-sm">
                  <XCircle className="w-3.5 h-3.5 text-orange-500" />
                  <span className="font-medium text-gray-800 capitalize">{d.module}</span>
                  <span className="text-gray-500">— {d.reason}: {d.detail}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </SCard>
      )}
    </div>
  );
};

/* ═══════════ Tab 2: ENGINE ═══════════ */
const EngineTab = ({ status, aligned, loading, onRun }) => {
  const [running, setRunning] = useState(false);
  const handleRun = async () => { setRunning(true); await onRun(); setRunning(false); };

  if (loading) return <Loading />;

  const providers = status?.providers || [];
  const cov = aligned?.coverage || {};

  return (
    <div className="space-y-5" data-testid="engine-tab">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-gray-900">Pipeline Engine</h2>
          <p className="text-sm text-gray-500">Запуск и состояние pipeline</p>
        </div>
        <Button onClick={handleRun} disabled={running} className="bg-indigo-600 hover:bg-indigo-700 text-white"
          data-testid="run-pipeline-btn">
          {running ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
          {running ? 'Запуск...' : 'Запустить Pipeline'}
        </Button>
      </div>

      {/* Providers */}
      <SCard>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-700 flex items-center gap-2">
            <Radio className="w-4 h-4 text-indigo-500" /> Провайдеры ({providers.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {providers.map(p => {
              const sig = (aligned?.aligned || []).find(a => a.module === p.key);
              const drop = (aligned?.dropped || []).find(d => d.module === p.key);
              const isAligned = !!sig;

              return (
                <div key={p.key} className={`p-3 rounded-lg ${isAligned ? 'bg-green-50/70' : 'bg-orange-50/70'}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`w-2.5 h-2.5 rounded-full ${isAligned ? 'bg-green-500' : 'bg-orange-500'}`} />
                    <span className="text-sm font-medium text-gray-800 capitalize">{p.key}</span>
                  </div>
                  {isAligned && (
                    <div className="text-xs text-gray-600 space-y-0.5">
                      <p>Здоровье: <S className={healthBadge(sig.health)}>{sig.health}</S></p>
                      <p>Свежесть: {ago(sig.asOfTs)}</p>
                    </div>
                  )}
                  {drop && (
                    <div className="text-xs text-orange-600 mt-1">
                      <p>{drop.reason}: {drop.detail}</p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </CardContent>
      </SCard>

      {/* Alignment & Coverage */}
      <SCard>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-700">Временная синхронизация</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500">Anchor Mode</p>
              <p className="text-sm font-medium text-gray-800">{status?.policy?.anchorMode || '—'}</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500">Coverage</p>
              <p className="text-sm font-bold text-gray-900">{cov.aligned || 0}/{cov.total || 4}</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500">Мин. требуется</p>
              <p className="text-sm font-medium text-gray-800">{status?.policy?.minModulesRequired || 2}</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg col-span-1">
              <p className="text-xs text-gray-500">Отброшено</p>
              <p className="text-sm font-bold text-orange-600">{cov.dropped || 0}</p>
            </div>
          </div>

          {status?.policy?.ttl && (
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="text-xs text-gray-500">TTL модулей:</span>
              {Object.entries(status.policy.ttl).map(([k, v]) => (
                <span key={k} className="text-xs text-gray-600">
                  {k}: {Math.round(v / 3600000)}ч
                </span>
              ))}
            </div>
          )}
        </CardContent>
      </SCard>
    </div>
  );
};

/* ═══════════ Tab 3: SIGNALS ═══════════ */
const SignalsTab = ({ signals, forecastTable, aligned, policy, loading }) => {
  if (loading) return <Loading />;

  const rawSignals = signals?.signals || [];
  const weights = policy?.policy?.weights || {};
  const forecast = forecastTable?.rows || [];
  const conflict = computeConflict(rawSignals);

  return (
    <div className="space-y-5" data-testid="signals-tab">
      <h2 className="text-base font-semibold text-gray-900">Сигналы и прогноз</h2>

      {/* Signal Diagnostics bar */}
      <div className="grid grid-cols-3 gap-3">
        <SCard>
          <CardContent className="p-3 text-center">
            <p className="text-xs text-gray-500">Конфликт</p>
            <S className={
              conflict.level === 'LOW' ? 'text-green-700' :
              conflict.level === 'MEDIUM' ? 'text-yellow-700' :
              'text-red-700'
            }>{conflict.level} ({conflict.score})</S>
          </CardContent>
        </SCard>
        <SCard>
          <CardContent className="p-3 text-center">
            <p className="text-xs text-gray-500">Покрытие</p>
            <p className="text-lg font-bold text-gray-900">{aligned?.coverage?.aligned || 0}/{aligned?.coverage?.total || 4}</p>
          </CardContent>
        </SCard>
        <SCard>
          <CardContent className="p-3 text-center">
            <p className="text-xs text-gray-500">Длительность</p>
            <p className="text-lg font-bold text-gray-900">{signals?.durationMs || 0}ms</p>
          </CardContent>
        </SCard>
      </div>

      {/* Module Signals Table */}
      <SCard>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-700">Вклад модулей</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs uppercase border-b border-gray-100">
                  <th className="text-left py-2 px-3">Модуль</th>
                  <th className="text-center py-2 px-3">Направление</th>
                  <th className="text-right py-2 px-3">Скор</th>
                  <th className="text-right py-2 px-3">Уверенность</th>
                  <th className="text-right py-2 px-3">Вес</th>
                  <th className="text-right py-2 px-3">Влияние</th>
                  <th className="text-center py-2 px-3">Здоровье</th>
                  <th className="text-right py-2 px-3">Свежесть</th>
                  <th className="text-left py-2 px-3">Причина</th>
                </tr>
              </thead>
              <tbody>
                {rawSignals.map(s => {
                  const w = weights[s.module] || 0;
                  const impact = s.score * w;
                  return (
                    <tr key={s.module} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="py-2.5 px-3 font-medium text-gray-800 capitalize">{s.module}</td>
                      <td className="py-2.5 px-3 text-center">
                        <span className={`inline-flex items-center gap-1 text-xs font-medium ${dirColor(s.direction)}`}>
                          {dirIcon(s.direction)} {s.direction}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right text-gray-700">{fmt(s.score, 3)}</td>
                      <td className="py-2.5 px-3 text-right text-gray-700">{pct(s.confidence)}</td>
                      <td className="py-2.5 px-3 text-right text-gray-500">{pct(w)}</td>
                      <td className={`py-2.5 px-3 text-right font-medium ${impact >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {impact >= 0 ? '+' : ''}{fmt(impact, 3)}
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        <S className={healthBadge(s.health)}>{s.health}</S>
                      </td>
                      <td className="py-2.5 px-3 text-right text-gray-500">{ago(s.asOfTs)}</td>
                      <td className="py-2.5 px-3 text-xs text-gray-400 max-w-[200px] truncate">
                        {s.reasons?.[0] || '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </SCard>

      {/* Signal Health */}
      <SCard>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-700">Здоровье сигналов</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {rawSignals.map(s => {
              const freshMs = Date.now() - s.asOfTs;
              const isFresh = freshMs < (s.ttlMs || 86400000);
              return (
                <div key={s.module} className="p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-800 capitalize">{s.module}</span>
                    <S className={isFresh ? healthBadge('OK') : healthBadge('WARN')}>
                      {isFresh ? 'LIVE' : 'STALE'}
                    </S>
                  </div>
                  <div className="space-y-1 text-xs text-gray-500">
                    <div className="flex justify-between">
                      <span>Свежесть</span>
                      <span className="font-medium text-gray-700">{ago(s.asOfTs)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>TTL</span>
                      <span className="font-medium text-gray-700">{Math.round((s.ttlMs || 0) / 3600000)}h</span>
                    </div>
                    {s.drift !== undefined && (
                      <div className="flex justify-between">
                        <span>Drift</span>
                        <span className="font-medium text-gray-700">{fmt(s.drift, 2)}</span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </SCard>

      {/* Forecast */}
      {forecast.length > 0 && (
        <SCard>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-700">Прогноз (7D)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs uppercase border-b border-gray-100">
                    <th className="text-left py-2 px-3">Дата</th>
                    <th className="text-center py-2 px-3">Направление</th>
                    <th className="text-right py-2 px-3">Цель</th>
                    <th className="text-right py-2 px-3">Уверенность</th>
                    <th className="text-left py-2 px-3">Статус</th>
                  </tr>
                </thead>
                <tbody>
                  {forecast.filter(r => r.hasData).map((r, i) => (
                    <tr key={i} className="border-b border-gray-50">
                      <td className="py-2 px-3 text-gray-700">
                        {r.dayLabel && <span className="text-xs text-indigo-600 mr-1">{r.dayLabel}</span>}
                        {r.date}
                      </td>
                      <td className="py-2 px-3 text-center">
                        {r.direction && <S className={dirColor(r.direction)}>{r.direction}</S>}
                      </td>
                      <td className="py-2 px-3 text-right text-gray-700">
                        {r.target ? `$${r.target.toLocaleString()}` : '—'}
                      </td>
                      <td className="py-2 px-3 text-right text-gray-700">
                        {r.confidence ? `${r.confidence}%` : '—'}
                      </td>
                      <td className="py-2 px-3">
                        <S className={`${
                          r.status === 'Pending' ? 'text-blue-600' :
                          r.status?.includes('Hit') ? 'text-green-600' :
                          'text-gray-500'
                        }`}>{r.status}</S>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </SCard>
      )}
    </div>
  );
};

/* ═══════════ Tab 4: DECISIONS ═══════════ */
const DecisionsTab = ({ snapshots, loading }) => {
  const [expanded, setExpanded] = useState(null);

  if (loading) return <Loading />;

  const snaps = snapshots?.data?.snapshots || [];

  return (
    <div className="space-y-5" data-testid="decisions-tab">
      <h2 className="text-base font-semibold text-gray-900">История решений</h2>

      {snaps.length === 0 ? (
        <SCard>
          <CardContent className="p-8 text-center">
            <Database className="w-10 h-10 text-gray-300 mx-auto mb-2" />
            <p className="text-gray-500 text-sm">Решения ещё не создавались.</p>
            <p className="text-gray-400 text-xs mt-1">Запустите pipeline на вкладке Engine.</p>
          </CardContent>
        </SCard>
      ) : (
        <SCard>
          <CardContent className="p-0">
            <div className="divide-y divide-gray-100">
              {snaps.map(s => {
                const isExpanded = expanded === s.snapshotId;
                return (
                  <div key={s.snapshotId} className="hover:bg-gray-50/50">
                    {/* Row */}
                    <div
                      className="flex items-center gap-3 p-3 cursor-pointer"
                      onClick={() => setExpanded(isExpanded ? null : s.snapshotId)}
                      data-testid={`decision-row-${s.snapshotId}`}
                    >
                      <div className="w-6 h-6 flex items-center justify-center rounded-full bg-gray-100">
                        {isExpanded ? <ChevronUp className="w-3.5 h-3.5 text-gray-500" /> : <ChevronDown className="w-3.5 h-3.5 text-gray-500" />}
                      </div>

                      <S className={`${dirColor(s.finalDecision?.action)} min-w-[55px]`}
                        title={s.finalDecision?.action === 'BUY' ? 'Рекомендация к покупке' : s.finalDecision?.action === 'SELL' ? 'Рекомендация к продаже' : 'Удержание позиции'}>
                        {s.finalDecision?.action}
                      </S>
                      <S className="text-gray-600"
                        title={s.finalDecision?.strength === 'WEAK' ? 'Слабый сигнал — низкая уверенность' : s.finalDecision?.strength === 'MODERATE' ? 'Умеренный сигнал' : 'Сильный сигнал — высокая уверенность'}>
                        {s.finalDecision?.strength}
                      </S>

                      <span className="text-sm text-gray-700" title="Уровень уверенности модели в решении">{pct(s.finalDecision?.confidence)}</span>

                      {s.finalDecision?.downgraded && (
                        <S className="text-yellow-700"
                          title="Сила сигнала понижена из-за макро-контекста или конфликта модулей">
                          DOWNGRADED
                        </S>
                      )}

                      <span className="text-xs text-gray-400 ml-auto">{ts(s.timestamp)}</span>
                    </div>

                    {/* Explainability Panel */}
                    {isExpanded && (
                      <div className="px-6 pb-4 pt-1 bg-gray-50/80 space-y-4" data-testid="decision-explainability">
                        {/* Input Signal */}
                        <div>
                          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2 font-medium">Входной сигнал</p>
                          <div className="flex gap-3">
                            <div className="p-2 bg-white rounded text-center min-w-[80px]">
                              <p className="text-xs text-gray-500">Направление</p>
                              <S className={`${dirColor(s.input?.direction)} mt-1`}>{s.input?.direction}</S>
                            </div>
                            <div className="p-2 bg-white rounded text-center min-w-[80px]">
                              <p className="text-xs text-gray-500">Уверенность</p>
                              <p className="text-sm font-bold text-gray-900">{pct(s.input?.confidence)}</p>
                            </div>
                            <div className="p-2 bg-white rounded text-center min-w-[80px]">
                              <p className="text-xs text-gray-500">Сила</p>
                              <p className="text-sm font-bold text-gray-900">{s.input?.strength}</p>
                            </div>
                          </div>
                        </div>

                        {/* Macro Context */}
                        <div>
                          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2 font-medium">Макро-контекст</p>
                          <div className="flex flex-wrap gap-3">
                            <div className="p-2">
                              <p className="text-xs text-gray-500">Режим</p>
                              <S className="text-purple-700">{s.macroContext?.regime}</S>
                            </div>
                            <div className="p-2">
                              <p className="text-xs text-gray-500">Риск</p>
                              <p className="text-sm font-medium text-gray-800">{s.macroContext?.riskLevel}</p>
                            </div>
                            <div className="p-2">
                              <p className="text-xs text-gray-500">Fear & Greed</p>
                              <p className="text-sm font-bold text-gray-900">{s.macroContext?.fearGreed}</p>
                            </div>
                            <div className="p-2">
                              <p className="text-xs text-gray-500">Множитель</p>
                              <p className="text-sm text-gray-800">{s.macroContext?.confidenceMultiplier}</p>
                            </div>
                            {s.macroContext?.blockedStrong && (
                              <S className="text-red-700 self-center">STRONG BLOCKED</S>
                            )}
                          </div>
                          {s.macroContext?.flags?.length > 0 && (
                            <div className="flex gap-1.5 mt-2">
                              {s.macroContext.flags.map(f => (
                                <S key={f} className="text-orange-600">{f}</S>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Invariant Check */}
                        <div>
                          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2 font-medium">Проверка инвариантов</p>
                          <div className="flex items-center gap-2">
                            {s.invariantCheck?.passed ? (
                              <S className="text-green-700 flex items-center gap-1">
                                <CheckCircle className="w-3 h-3" /> PASSED
                              </S>
                            ) : (
                              <S className="text-red-700 flex items-center gap-1">
                                <XCircle className="w-3 h-3" /> FAILED ({s.invariantCheck?.hardViolations} hard)
                              </S>
                            )}
                          </div>
                        </div>

                        {/* Final Decision */}
                        <div>
                          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2 font-medium">Финальное решение</p>
                          <div className="p-3 flex items-center gap-4">
                            <S className={`${dirColor(s.finalDecision?.action)} text-sm`}>
                              {s.finalDecision?.action} {s.finalDecision?.strength}
                            </S>
                            <span className="text-sm text-gray-700">Уверенность: <strong>{pct(s.finalDecision?.confidence)}</strong></span>
                            {s.finalDecision?.downgraded && (
                              <span className="text-xs text-yellow-600">понижено с {s.input?.strength}</span>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </SCard>
      )}
    </div>
  );
};

/* ═══════════ Tab 5: DRIFT ═══════════ */
const DriftTab = ({ drift, correlation, loading }) => {
  if (loading) return <Loading />;
  const modules = drift?.modules || [];

  return (
    <div className="space-y-5" data-testid="drift-tab">
      <h2 className="text-base font-semibold text-gray-900">Drift и корреляция</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {modules.map(m => (
          <SCard key={m.moduleId}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className={`w-2.5 h-2.5 rounded-full ${m.status === 'OK' ? 'bg-green-500' : m.status === 'WARN' ? 'bg-yellow-500' : 'bg-red-500'}`} />
                  <span className="text-sm font-medium text-gray-800 capitalize">{m.moduleId}</span>
                </div>
                <S className={`${
                  m.driftScore < 0.2 ? 'text-green-700' :
                  m.driftScore < 0.4 ? 'text-yellow-700' :
                  'text-red-700'
                }`} title={`Drift score: ${fmt(m.driftScore, 2)}. Ниже 0.2 — норма, 0.2-0.4 — предупреждение, выше 0.4 — критично`}>drift: {fmt(m.driftScore, 2)}</S>
              </div>

              <div className="grid grid-cols-3 gap-2 text-xs mb-3">
                <div className="p-2 bg-gray-50 rounded" title="Отклонение сигнала от нормы">
                  <p className="text-gray-500">Сигнал</p>
                  <p className="text-gray-800 font-medium">{fmt(m.signalDrift, 2)}</p>
                </div>
                <div className="p-2 bg-gray-50 rounded" title="Drift покрытия — насколько изменилось количество активных источников">
                  <p className="text-gray-500">Покрытие</p>
                  <p className="text-gray-800 font-medium">{fmt(m.coverageDrift, 2)}</p>
                </div>
                <div className="p-2 bg-gray-50 rounded" title="Штраф к весу модуля за drift">
                  <p className="text-gray-500">Штраф</p>
                  <p className="text-gray-800 font-medium">{fmt(m.penalty, 2)}</p>
                </div>
              </div>

              {m.explain?.length > 0 && (
                <div className="text-xs text-gray-500 space-y-1">
                  {m.explain.map((e, i) => (
                    <p key={i} className="flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3 text-yellow-500 flex-shrink-0" /> {e}
                    </p>
                  ))}
                </div>
              )}
            </CardContent>
          </SCard>
        ))}
      </div>

      {correlation?.pairs?.length > 0 && (
        <SCard>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-700 flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-indigo-500" /> Корреляция ({correlation.runsAnalyzed} запусков)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {correlation.pairs.map((p, i) => (
                <div key={i} className="flex items-center justify-between p-2.5 bg-gray-50 rounded text-sm">
                  <span className="text-gray-600 capitalize">{p.a} × {p.b}</span>
                  <span className={`font-medium ${
                    Math.abs(p.correlation) < 0.3 ? 'text-gray-500' :
                    p.correlation > 0 ? 'text-green-600' : 'text-red-600'
                  }`}>{fmt(p.correlation, 3)}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </SCard>
      )}
    </div>
  );
};

/* ═══════════ Tab 6: DATASET ═══════════ */
const DatasetTab = ({ dataset, runs, loading }) => {
  if (loading) return <Loading />;

  return (
    <div className="space-y-5" data-testid="dataset-tab">
      <h2 className="text-base font-semibold text-gray-900">ML Dataset</h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SCard className="bg-blue-50/70">
          <CardContent className="p-4">
            <p className="text-xs text-gray-500">Всего запусков</p>
            <p className="text-2xl font-bold text-gray-900">{dataset?.total || 0}</p>
          </CardContent>
        </SCard>
        <SCard className="bg-green-50/70">
          <CardContent className="p-4">
            <p className="text-xs text-gray-500">Оценено</p>
            <p className="text-2xl font-bold text-gray-900">{dataset?.evaluated || 0}</p>
          </CardContent>
        </SCard>
        <SCard className="bg-yellow-50/70">
          <CardContent className="p-4">
            <p className="text-xs text-gray-500">Ожидает</p>
            <p className="text-2xl font-bold text-gray-900">{dataset?.unevaluated || 0}</p>
          </CardContent>
        </SCard>
        <SCard className="bg-purple-50/70">
          <CardContent className="p-4">
            <p className="text-xs text-gray-500">Hit Rate</p>
            <p className="text-2xl font-bold text-gray-900">{dataset?.hitRate ? pct(dataset.hitRate) : '—'}</p>
          </CardContent>
        </SCard>
      </div>

      {dataset?.byHorizon?.length > 0 && (
        <SCard>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-700">По горизонту</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-3">
              {dataset.byHorizon.map(h => (
                <div key={h._id} className="p-3 bg-gray-50 rounded-lg text-center">
                  <p className="text-lg font-bold text-gray-900">{h._id}D</p>
                  <p className="text-xs text-gray-500">{h.count} запусков</p>
                </div>
              ))}
            </div>
          </CardContent>
        </SCard>
      )}

      {runs?.length > 0 && (
        <SCard>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-700">Последние оценённые запуски</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs uppercase border-b border-gray-100">
                    <th className="text-left py-2 px-2">Горизонт</th>
                    <th className="text-left py-2 px-2">Вердикт</th>
                    <th className="text-right py-2 px-2">Скор</th>
                    <th className="text-right py-2 px-2">Уверенность</th>
                    <th className="text-left py-2 px-2">Режим</th>
                    <th className="text-right py-2 px-2">Доходность</th>
                    <th className="text-center py-2 px-2">Попадание</th>
                    <th className="text-left py-2 px-2">Дата</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r, i) => (
                    <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="py-2 px-2 text-gray-700">{r.horizonDays}D</td>
                      <td className="py-2 px-2">
                        <S className={dirColor(r.metaFinalVerdict)}>{r.metaFinalVerdict}</S>
                      </td>
                      <td className="py-2 px-2 text-right text-gray-700">{fmt(r.metaRawScore, 3)}</td>
                      <td className="py-2 px-2 text-right text-gray-700">{pct(r.metaConfidence)}</td>
                      <td className="py-2 px-2">
                        <S className="text-purple-600">{r.regime}</S>
                      </td>
                      <td className={`py-2 px-2 text-right ${r.futureReturn > 0 ? 'text-green-600' : r.futureReturn < 0 ? 'text-red-600' : 'text-gray-500'}`}>
                        {r.futureReturn != null ? `${(r.futureReturn * 100).toFixed(2)}%` : '—'}
                      </td>
                      <td className="py-2 px-2 text-center">
                        {r.hit === true ? <CheckCircle className="w-4 h-4 text-green-500 mx-auto" /> :
                         r.hit === false ? <XCircle className="w-4 h-4 text-red-500 mx-auto" /> :
                         <span className="text-gray-400">—</span>}
                      </td>
                      <td className="py-2 px-2 text-xs text-gray-400">{ts(r.createdAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </SCard>
      )}
    </div>
  );
};

/* ═══════════ Tab 7: POLICY ═══════════ */
const PolicyTab = ({ active, all, loading }) => {
  if (loading) return <Loading />;
  const policies = all?.policies || {};

  return (
    <div className="space-y-5" data-testid="policy-tab">
      <h2 className="text-base font-semibold text-gray-900">Policy и режим</h2>

      {active?.ok && (
        <SCard>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-700 flex items-center gap-2">
              <Scale className="w-4 h-4 text-indigo-500" /> Активная Policy
              <S className="text-purple-700 ml-2">{active.regime}</S>
              <span className="text-xs text-gray-400 font-normal">источник: {active.regimeSource}</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
              {active.policy?.weights && Object.entries(active.policy.weights).map(([k, v]) => (
                <div key={k} className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-gray-500 capitalize">{k}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <Progress value={v * 100} className="h-2 flex-1" />
                    <span className="text-sm font-bold text-gray-800">{pct(v)}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-500">Порог входа</p>
                <p className="text-sm font-bold text-gray-900">{active.policy?.thresholds?.enter}</p>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-500">Порог выхода</p>
                <p className="text-sm font-bold text-gray-900">{active.policy?.thresholds?.exit}</p>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-500">Мин. покрытие</p>
                <p className="text-sm font-bold text-gray-900">{active.policy?.gates?.minCoverage} модулей</p>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-500">Блок при конфликте</p>
                <S className={active.policy?.gates?.blockIfConflicted ? 'text-red-700' : 'text-green-700'}>
                  {active.policy?.gates?.blockIfConflicted ? 'ДА' : 'НЕТ'}
                </S>
              </div>
            </div>

            {active.policy?.cooldown && (
              <div className="mt-3 flex gap-3">
                <span className="text-xs text-gray-600">
                  Cooldown: {Math.round((active.policy.cooldown.durationMs || 0) / 3600000)}ч
                </span>
                <span className="text-xs text-gray-600">
                  Penalty K: {active.policy.cooldown.averagePenaltyK}
                </span>
              </div>
            )}
          </CardContent>
        </SCard>
      )}

      {Object.keys(policies).length > 0 && (
        <SCard>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-700">Все Policy по режимам</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Object.entries(policies).map(([regime, p]) => (
                <div key={regime} className={`p-3 rounded-lg ${regime === active?.regime ? 'bg-indigo-50' : 'bg-gray-50'}`}>
                  <div className="flex items-center justify-between mb-2">
                    <S className="text-purple-700">{displayText(regime)}</S>
                    {regime === active?.regime && <S className="text-indigo-700">ACTIVE</S>}
                  </div>
                  <div className="flex flex-wrap gap-3 text-xs">
                    {p.weights && Object.entries(p.weights).map(([k, v]) => (
                      <span key={k} className="text-gray-500">
                        <span className="capitalize text-gray-700 font-medium">{k}</span>: {pct(v)}
                      </span>
                    ))}
                    <span className="text-gray-400 ml-4">
                      enter: {p.thresholds?.enter} / exit: {p.thresholds?.exit}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </SCard>
      )}
    </div>
  );
};

/* ═══════════ Tab 8: MODULES ═══════════ */
const MODE_OPTIONS = ['live', 'snapshot', 'off'];
const MODE_COLORS = {
  live: 'text-green-700',
  snapshot: 'text-amber-700',
  off: 'text-gray-500',
};
const MODE_DESC = {
  live: 'Полный real-time pipeline',
  snapshot: 'Использует последний кэш',
  off: 'Модуль отключён, вес = 0',
};

const ModulesTab = ({ modules, loading, onUpdate, onRefresh }) => {
  if (loading) return <Loading />;
  const mods = modules || [];

  const handleToggle = async (mod) => {
    if (mod.mode === 'off') {
      await onUpdate(mod.module, { enabled: true, mode: 'snapshot' });
    } else {
      await onUpdate(mod.module, { enabled: false, mode: 'off' });
    }
  };

  const handleModeChange = async (mod, newMode) => {
    await onUpdate(mod.module, {
      enabled: newMode !== 'off',
      mode: newMode,
    });
  };

  const handleWeightChange = async (mod, val) => {
    const num = parseFloat(val);
    await onUpdate(mod.module, { weightOverride: isNaN(num) ? null : num });
  };

  const handleStaleChange = async (mod, val) => {
    const num = parseInt(val, 10);
    if (!isNaN(num) && num > 0) {
      await onUpdate(mod.module, { maxSnapshotAgeHours: num });
    }
  };

  return (
    <div className="space-y-5" data-testid="modules-tab">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-900">Управление модулями</h2>
        <Button variant="ghost" size="sm" onClick={onRefresh} className="text-gray-600 hover:bg-gray-100 text-xs" data-testid="modules-refresh-btn">
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Обновить
        </Button>
      </div>

      {/* Summary Table */}
      <SCard>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-700 flex items-center gap-2">
            <Settings2 className="w-4 h-4 text-indigo-500" /> Реестр модулей
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="modules-table">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="py-2 text-left text-xs text-gray-500 font-medium">Модуль</th>
                  <th className="py-2 text-center text-xs text-gray-500 font-medium">Статус</th>
                  <th className="py-2 text-center text-xs text-gray-500 font-medium">Режим</th>
                  <th className="py-2 text-center text-xs text-gray-500 font-medium">Вес</th>
                  <th className="py-2 text-center text-xs text-gray-500 font-medium">Лимит устаревания</th>
                  <th className="py-2 text-right text-xs text-gray-500 font-medium">Обновлено</th>
                </tr>
              </thead>
              <tbody>
                {mods.map(mod => (
                  <tr key={mod.module} className="border-b border-gray-50 hover:bg-gray-50" data-testid={`module-row-${mod.module}`}>
                    <td className="py-3">
                      <span className="font-medium text-gray-900 capitalize">{mod.module}</span>
                    </td>
                    <td className="py-3 text-center">
                      <button
                        onClick={() => handleToggle(mod)}
                        className="inline-flex items-center gap-1 cursor-pointer"
                        data-testid={`toggle-${mod.module}`}
                      >
                        {mod.enabled && mod.mode !== 'off' ? (
                          <ToggleRight className="w-6 h-6 text-green-600" />
                        ) : (
                          <ToggleLeft className="w-6 h-6 text-gray-400" />
                        )}
                        <span className={`text-xs font-medium ${mod.enabled && mod.mode !== 'off' ? 'text-green-700' : 'text-gray-500'}`}>
                          {mod.enabled && mod.mode !== 'off' ? 'ON' : 'OFF'}
                        </span>
                      </button>
                    </td>
                    <td className="py-3 text-center">
                      <select
                        value={mod.mode}
                        onChange={e => handleModeChange(mod, e.target.value)}
                        className="text-xs px-2 py-1 rounded-md bg-gray-50 text-gray-700 focus:outline-none"
                        data-testid={`mode-select-${mod.module}`}
                      >
                        {MODE_OPTIONS.map(m => (
                          <option key={m} value={m}>{m.toUpperCase()}</option>
                        ))}
                      </select>
                    </td>
                    <td className="py-3 text-center">
                      <span className="text-xs font-bold text-gray-800">
                        {mod.weightOverride != null ? mod.weightOverride.toFixed(2) : mod.weight.toFixed(2)}
                      </span>
                      {mod.weightOverride != null && (
                        <span className="text-[10px] text-amber-600 ml-1">OVR</span>
                      )}
                    </td>
                    <td className="py-3 text-center">
                      <span className="text-xs text-gray-600">{mod.maxSnapshotAgeHours}h</span>
                    </td>
                    <td className="py-3 text-right">
                      <span className="text-xs text-gray-400">{ts(mod.lastUpdated)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </SCard>

      {/* Per-module detail cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {mods.map(mod => (
          <SCard key={mod.module}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-700 flex items-center justify-between">
                <span className="capitalize flex items-center gap-2">
                  {mod.module}
                  <S className={MODE_COLORS[mod.mode] || 'text-gray-500'}>
                    {mod.mode.toUpperCase()}
                  </S>
                </span>
                <button
                  onClick={() => handleToggle(mod)}
                  className="cursor-pointer"
                  data-testid={`card-toggle-${mod.module}`}
                >
                  {mod.enabled && mod.mode !== 'off' ? (
                    <ToggleRight className="w-5 h-5 text-green-600" />
                  ) : (
                    <ToggleLeft className="w-5 h-5 text-gray-400" />
                  )}
                </button>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-xs text-gray-500">{MODE_DESC[mod.mode]}</p>

              {/* Mode selector */}
              <div>
                <p className="text-[10px] text-gray-400 uppercase mb-1">Режим</p>
                <div className="flex gap-1">
                  {MODE_OPTIONS.map(m => (
                    <button
                      key={m}
                      onClick={() => handleModeChange(mod, m)}
                      className={`px-2.5 py-1 text-xs rounded-md transition-colors cursor-pointer ${
                        mod.mode === m
                          ? 'bg-indigo-600 text-white'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                      data-testid={`mode-btn-${mod.module}-${m}`}
                    >
                      {m.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>

              {/* Weight Override */}
              <div>
                <p className="text-[10px] text-gray-400 uppercase mb-1">Переопределение веса</p>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    placeholder={mod.weight.toFixed(2)}
                    defaultValue={mod.weightOverride ?? ''}
                    onBlur={e => handleWeightChange(mod, e.target.value)}
                    className="w-20 text-xs px-2 py-1 bg-gray-50 rounded-md focus:outline-none"
                    data-testid={`weight-input-${mod.module}`}
                  />
                  <span className="text-[10px] text-gray-400">по умолчанию: {mod.weight}</span>
                  {mod.weightOverride != null && (
                    <button
                      onClick={() => handleWeightChange(mod, '')}
                      className="text-[10px] text-red-500 cursor-pointer hover:text-red-700"
                      data-testid={`reset-weight-${mod.module}`}
                    >
                      Сброс
                    </button>
                  )}
                </div>
              </div>

              {/* Stale Limit */}
              {mod.mode === 'snapshot' && (
                <div>
                  <p className="text-[10px] text-gray-400 uppercase mb-1">Макс. возраст снимка (часы)</p>
                  <input
                    type="number"
                    min="1"
                    max="168"
                    defaultValue={mod.maxSnapshotAgeHours}
                    onBlur={e => handleStaleChange(mod, e.target.value)}
                    className="w-20 text-xs px-2 py-1 bg-gray-50 rounded-md focus:outline-none"
                    data-testid={`stale-input-${mod.module}`}
                  />
                </div>
              )}

              <div className="text-[10px] text-gray-400">
                Обновлено: {ts(mod.lastUpdated)}
              </div>
            </CardContent>
          </SCard>
        ))}
      </div>
    </div>
  );
};

/* ═══════════ MAIN ═══════════ */
export default function AdminMetaBrainPage() {
  const { isAuthenticated } = useAdminAuth();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [data, setData] = useState({});

  const fetchAll = useCallback(async () => {
    setLoading(true);
    const f = (url) => fetch(`${API_URL}${url}`).then(r => r.json()).catch(() => ({}));

    const [
      status, state, signals, signalsAligned,
      forecastTable, drift, correlation,
      datasetStats, datasetRuns, snapshots,
      policyActive, policyAll, modulesResp,
    ] = await Promise.all([
      f('/api/meta-brain-v2/status'),
      f('/api/meta-brain-v2/state'),
      f('/api/meta-brain-v2/signals'),
      f('/api/meta-brain-v2/signals/aligned'),
      f('/api/meta-brain-v2/forecast-table'),
      f('/api/meta-brain-v2/drift'),
      f('/api/meta-brain-v2/correlation'),
      f('/api/meta-brain-v2/dataset/stats'),
      f('/api/meta-brain-v2/dataset/runs?limit=20'),
      f('/api/v10/meta-brain/snapshots?limit=20'),
      f('/api/meta-brain-v2/policy'),
      f('/api/meta-brain-v2/policy/all'),
      f('/api/meta-brain-v2/modules'),
    ]);

    setData({
      status, state, signals, signalsAligned,
      forecastTable, drift, correlation,
      datasetStats, datasetRuns, snapshots,
      policyActive, policyAll,
      modules: modulesResp?.modules || [],
    });
    setLoading(false);
  }, []);

  const handleRunPipeline = async () => {
    try {
      await fetch(`${API_URL}/api/meta-brain-v2/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asset: 'BTC', horizonDays: 7 }),
      });
      await fetchAll();
    } catch (e) {
      console.error('Pipeline run failed:', e);
    }
  };

  const handleModuleUpdate = async (moduleName, patch) => {
    try {
      await fetch(`${API_URL}/api/meta-brain-v2/modules/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ module: moduleName, ...patch }),
      });
      await fetchAll();
    } catch (e) {
      console.error('Module update failed:', e);
    }
  };

  useEffect(() => {
    if (!isAuthenticated) { navigate('/admin/login'); return; }
    fetchAll();
  }, [isAuthenticated, navigate, fetchAll]);

  /* Auto-refresh based on active tab */
  useEffect(() => {
    const interval = REFRESH_INTERVALS[activeTab];
    if (!interval) return;
    const id = setInterval(fetchAll, interval);
    return () => clearInterval(id);
  }, [activeTab, fetchAll]);

  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6 space-y-5" data-testid="meta-brain-admin">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Brain className="w-5 h-5 text-purple-600" />
            <div>
              <h1 className="text-xl font-semibold text-slate-900">MetaBrain</h1>
              <p className="text-xs text-gray-500">Центр управления ML</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={fetchAll} disabled={loading}
            className="text-gray-600 hover:bg-gray-100" data-testid="refresh-all-btn">
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} /> Обновить
          </Button>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-gray-100 flex-wrap h-auto gap-1 p-1">
            {[
              { v: 'overview', icon: Activity, label: 'Обзор' },
              { v: 'engine', icon: Radio, label: 'Engine' },
              { v: 'signals', icon: Zap, label: 'Сигналы' },
              { v: 'decisions', icon: Eye, label: 'Решения' },
              { v: 'drift', icon: TrendingUp, label: 'Drift' },
              { v: 'dataset', icon: Database, label: 'Dataset' },
              { v: 'policy', icon: Scale, label: 'Policy' },
              { v: 'modules', icon: Settings2, label: 'Модули' },
            ].map(t => (
              <TabsTrigger key={t.v} value={t.v}
                className="data-[state=active]:bg-white data-[state=active]:shadow-sm text-xs gap-1.5">
                <t.icon className="w-3.5 h-3.5" /> {t.label}
              </TabsTrigger>
            ))}
          </TabsList>

          <TabsContent value="overview" className="mt-4">
            <OverviewTab state={data.state} status={data.status}
              signals={{ signals: data.signals?.signals, aligned: data.signalsAligned }}
              policy={data.policyActive} drift={data.drift} dataset={data.datasetStats} loading={loading} />
          </TabsContent>
          <TabsContent value="engine" className="mt-4">
            <EngineTab status={data.status} aligned={data.signalsAligned} loading={loading} onRun={handleRunPipeline} />
          </TabsContent>
          <TabsContent value="signals" className="mt-4">
            <SignalsTab signals={data.signals} forecastTable={data.forecastTable}
              aligned={data.signalsAligned} policy={data.policyActive} loading={loading} />
          </TabsContent>
          <TabsContent value="decisions" className="mt-4">
            <DecisionsTab snapshots={data.snapshots} loading={loading} />
          </TabsContent>
          <TabsContent value="drift" className="mt-4">
            <DriftTab drift={data.drift} correlation={data.correlation} loading={loading} />
          </TabsContent>
          <TabsContent value="dataset" className="mt-4">
            <DatasetTab dataset={data.datasetStats} runs={data.datasetRuns?.runs} loading={loading} />
          </TabsContent>
          <TabsContent value="policy" className="mt-4">
            <PolicyTab active={data.policyActive} all={data.policyAll} loading={loading} />
          </TabsContent>
          <TabsContent value="modules" className="mt-4">
            <ModulesTab modules={data.modules} loading={loading} onUpdate={handleModuleUpdate} onRefresh={fetchAll} />
          </TabsContent>
        </Tabs>
      </div>
    </AdminLayout>
  );
}
