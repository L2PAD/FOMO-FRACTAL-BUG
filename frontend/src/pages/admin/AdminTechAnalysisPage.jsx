/**
 * AdminTechAnalysisPage — Tech Analysis · Operator Console
 * ============================================================================
 * Канонический скоп (docs/07_UI_GUIDE.md → "Админ-страница /admin/tech-analysis"):
 *
 *   1. OBSERVABILITY — "Trustworthy?"
 *      R5..R10 read-only панели (Core7 / Calibration Quality / Integrity /
 *      Shadow Gate / Gate Evaluation / Gate Analytics).
 *
 *   2. MIRRORS — "Configured?"
 *      Read-only снимки прод-состояния (Trading Control / Risk Limits /
 *      Execution Config / Strategies / Audit). Никаких mutating-кнопок.
 *
 *   3. LIFECYCLE — "Operate"
 *      Operator write-поверхности: Calibration · MLOps · Exchange ML ·
 *      Auto-Retrain.
 *
 *   4. DIAGNOSTICS — "Engine internals"
 *      Operator-only аналитика и lab: Data Health · Risk R1/R2 ·
 *      Execution · Safety · Learning · Hypotheses Lab.
 *
 * Что было намеренно вычищено (см. docs/AUDIT_ADMIN_TA_2026-05-08.md):
 *   ❌ Analysis · Prediction  — был 1-в-1 дубликат user UI (PredictionPage)
 *   ❌ Analysis · Overview    — vague + дубликат /tech-analysis сводки
 *   ❌ Reserved-вкладки       — Root Cause / ML Readiness / Simulation /
 *                              Debug — без backend-контракта
 *   ❌ Mode "Analysis · BRAIN" — semantic drift, переименовано в Diagnostics
 *   ❌ <MarketProvider> global — теперь только локально вокруг Hypotheses
 *
 * UI-локализация: «smart bilingual»
 *   • Технические термины и API-эндпойнты — на английском (TA, ML, R5..R10,
 *     MLOps, Calibration, Shadow Gate, can_trade, kill-switch, …).
 *   • Описания, подсказки, empty-states, помощь — на русском.
 */
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import AdminLayout from '../../components/admin/AdminLayout';
import { useAdminAuth } from '../../context/AdminAuthContext';
import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../components/ui/tabs';
import { MarketProvider } from '../../store/marketStore';
import {
  // Header
  LineChart,
  // OBSERVABILITY
  Activity, ScanLine, Eye, CircleDot, Layers, TimerReset,
  // MIRRORS
  Settings, SlidersHorizontal, Cog, Target, FileText,
  // LIFECYCLE
  Gauge, Rocket, Database, GraduationCap,
  // DIAGNOSTICS
  HeartPulse, Shield, ShieldAlert, Radio, AlertOctagon, Brain as BrainIcon, Beaker,
  // Mode/status
  Bug, CheckCircle, AlertTriangle,
} from 'lucide-react';

// ─── Lifecycle write-поверхности (canonical) ──────────────────────
import {
  CalibrationStatusCard,
  CalibrationBuildPanel,
  CalibrationRunHistory,
  CalibrationAttackTests,
} from '../../components/calibration';
import MLOpsPage from '../mlops/MLOpsPage';
import AdminExchangeMLPage from './AdminExchangeMLPage';

// ─── Observability (R5..R10 · read-only) ──────────────────────────
import Core7ContextPanel        from '../../components/admin/observability/Core7ContextPanel';
import CalibrationQualityPanel  from '../../components/admin/observability/CalibrationQualityPanel';
import PredictionIntegrityPanel from '../../components/admin/observability/PredictionIntegrityPanel';
import ShadowGatePanel          from '../../components/admin/observability/ShadowGatePanel';
import GateEvaluationPanel      from '../../components/admin/observability/GateEvaluationPanel';
import GateAnalyticsPanel       from '../../components/admin/observability/GateAnalyticsPanel';
import DataHealthPanel          from '../../components/admin/observability/DataHealthPanel';

// ─── Diagnostics (engine-internal · operator-only) ────────────────
import HypothesesView from '../../modules/cockpit/views/HypothesesView';
import DynamicRiskAnalyticsPanel  from '../../components/terminal/analytics/DynamicRiskAnalyticsPanel';
import AdaptiveRiskAnalyticsPanel from '../../components/terminal/analytics/AdaptiveRiskAnalyticsPanel';
import ExecutionAnalyticsPanel    from '../../components/terminal/analytics/ExecutionAnalyticsPanel';
import SafetyAnalyticsPanel       from '../../components/terminal/analytics/SafetyAnalyticsPanel';
import LearningInsightsPanel      from '../../components/terminal/analytics/LearningInsightsPanel';
import useAdaptiveRiskAnalytics   from '../../hooks/analytics/useAdaptiveRiskAnalytics';

// ============================================================================
//   ─ COMMON PRIMITIVES ─
// ============================================================================
const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

function useAdminEndpoint(path, { interval = 0 } = {}) {
  const [state, setState] = useState({
    loading: true,
    error: null,
    data: null,
    status: null, // 'ok' | 'not_connected' | 'error'
  });

  const fetcher = useCallback(async () => {
    if (!path) return;
    try {
      const res = await axios.get(`${API_BASE}${path}`, { timeout: 8000 });
      setState({ loading: false, error: null, data: res.data, status: 'ok' });
    } catch (e) {
      const code = e?.response?.status;
      const isMissing = code === 404 || code === 501;
      setState({
        loading: false,
        error: e?.message || 'request_failed',
        data: null,
        status: isMissing ? 'not_connected' : 'error',
      });
    }
  }, [path]);

  useEffect(() => {
    fetcher();
    if (interval > 0) {
      const id = setInterval(fetcher, interval);
      return () => clearInterval(id);
    }
  }, [fetcher, interval]);

  return state;
}

function StatusPill({ tone = 'gray', children, testid }) {
  const map = {
    gray:    'bg-gray-100 text-gray-700 border-gray-200',
    amber:   'bg-amber-50 text-amber-700 border-amber-200',
    sky:     'bg-sky-50 text-sky-700 border-sky-200',
    rose:    'bg-rose-50 text-rose-700 border-rose-200',
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    indigo:  'bg-indigo-50 text-indigo-700 border-indigo-200',
  };
  return (
    <Badge variant="outline" className={map[tone] || map.gray} data-testid={testid}>
      {children}
    </Badge>
  );
}

function NotConnectedCard({ title, reason }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-semibold">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-start gap-3 text-sm">
          <AlertOctagon className="w-4 h-4 text-gray-400 mt-0.5" strokeWidth={1.75} />
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <StatusPill tone="gray">Not connected</StatusPill>
              <span className="text-xs text-gray-500">read-only · нет backend-контракта</span>
            </div>
            <p className="text-xs text-gray-500 max-w-prose">{reason}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function KVRow({ label, value, hint, testid }) {
  const display = value === null || value === undefined || value === '' ? '—' : value;
  return (
    <div className="flex items-center justify-between py-2" data-testid={testid}>
      <div>
        <span className="text-sm text-gray-700">{label}</span>
        {hint && <p className="text-[11px] text-gray-400 leading-tight">{hint}</p>}
      </div>
      <span className="text-sm text-gray-900 font-medium tabular-nums">{display}</span>
    </div>
  );
}

function TabHead({ title, description }) {
  return (
    <div className="mb-4">
      <h2 className="text-xl font-semibold mb-1 text-gray-900">{title}</h2>
      {description && <p className="text-sm text-gray-500">{description}</p>}
    </div>
  );
}

// ============================================================================
//   ─ OBSERVABILITY (R5..R10 · read-only) ─
//   Single source of truth: «насколько система trustworthy прямо сейчас?»
// ============================================================================
//
// Каждая панель сама знает свой endpoint и сама обрабатывает empty-state /
// INSUFFICIENT_SAMPLE / DEGRADED / UNRELIABLE. Здесь — только тонкие обёртки,
// прибивающие пилотный символ-таймфрейм (BTCUSDT/1d) для R5..R7. Не вытягивают
// глобальный <MarketProvider> — admin не должен зависеть от user-market-context.
function Core7ContextWrap()        { return <Core7ContextPanel        symbol="BTCUSDT" tf="1d" />; }
function CalibrationQualityWrap()  { return <CalibrationQualityPanel  symbol="BTCUSDT" tf="1d" />; }
function PredictionIntegrityWrap() { return <PredictionIntegrityPanel symbol="BTCUSDT" tf="1d" />; }
function ShadowGateWrap()          { return <ShadowGatePanel />; }
function GateEvaluationWrap()      { return <GateEvaluationPanel />; }
function GateAnalyticsWrap()       { return <GateAnalyticsPanel />; }

// ============================================================================
//   ─ MIRRORS (raw read-only state) ─
//   «Что operationally configured прямо сейчас?»
//   Дизайн — компактный: KV-сетка, без графиков, без аналитической обвязки.
// ============================================================================

function TradingControlTab() {
  const canTrade  = useAdminEndpoint('/api/control/can-trade',  { interval: 15000 });
  const dashboard = useAdminEndpoint('/api/dashboard/strategy', { interval: 15000 });

  const ctrl = dashboard.data?.data?.controls || {};
  const ct   = canTrade.data?.data || {};

  const renderState = (label, val, testid) => {
    let tone = 'gray';
    let text = '—';
    if (val === true)  { tone = 'emerald'; text = 'true'; }
    if (val === false) { tone = 'rose';    text = 'false'; }
    return (
      <div className="flex items-center justify-between py-2" data-testid={testid}>
        <span className="text-sm text-gray-700">{label}</span>
        <StatusPill tone={tone}>{text}</StatusPill>
      </div>
    );
  };

  return (
    <div className="p-6 space-y-6" data-testid="ta-tab-trading-control-content">
      <TabHead
        title="Trading Control"
        description="Read-only зеркало /api/control/* и /api/dashboard/strategy. Mutating-кнопки отключены по дизайну."
      />

      <div className="flex items-center gap-2 text-xs text-gray-500">
        <StatusPill tone="amber" testid="trading-control-mode-pill">Mutations · disabled</StatusPill>
        <span>Поверхность только наблюдательная — execution-mode не управляется отсюда.</span>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">Trading authority · live state</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          {canTrade.status === 'not_connected' ? (
            <p className="text-sm text-gray-500">Endpoint /api/control/can-trade не зарегистрирован.</p>
          ) : canTrade.status === 'error' ? (
            <p className="text-sm text-rose-600">Не удалось прочитать /api/control/can-trade — {canTrade.error}</p>
          ) : (
            <>
              {renderState('can_trade',            ct.can_trade,            'kv-can-trade')}
              {renderState('can_open_entry',       ct.can_open_entry,       'kv-can-open-entry')}
              {renderState('can_manage_positions', ct.can_manage_positions, 'kv-can-manage-positions')}
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">Strategy controls · live state</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          {dashboard.status === 'not_connected' ? (
            <p className="text-sm text-gray-500">Endpoint /api/dashboard/strategy не зарегистрирован.</p>
          ) : dashboard.status === 'error' ? (
            <p className="text-sm text-rose-600">Не удалось прочитать /api/dashboard/strategy — {dashboard.error}</p>
          ) : (
            <>
              {renderState('tradingPaused',    ctrl.tradingPaused,    'kv-trading-paused')}
              {renderState('killSwitchActive', ctrl.killSwitchActive, 'kv-kill-switch')}
              <KVRow label="health"          value={dashboard.data?.data?.health}            testid="kv-strategy-health" />
              <KVRow label="activeStrategy"  value={dashboard.data?.data?.selectedStrategy}  testid="kv-active-strategy" />
              <KVRow label="activeProfile"   value={dashboard.data?.data?.activeProfile}     testid="kv-active-profile" />
            </>
          )}
        </CardContent>
      </Card>

      <NotConnectedCard
        title="Mode switch · paper / live"
        reason="Admin endpoint для переключения execution-mode из UI не привязан. EXCHANGE_MODE контролируется ops через .env, в UI намеренно не зеркалируется."
      />
    </div>
  );
}

// MIRRORS · Risk Limits — RAW config only (interpretive аналитика → Diagnostics)
function RiskLimitsTab() {
  const r1cfg = useAdminEndpoint('/api/dynamic-risk/config', { interval: 30000 });
  const cfg = r1cfg.data?.config || {};

  return (
    <div className="p-6 space-y-6" data-testid="ta-tab-risk-limits-content">
      <TabHead
        title="Risk Limits · Config"
        description="Read-only зеркало /api/dynamic-risk/config. Только сырые значения конфигурации; поведенческая аналитика — в Diagnostics → Risk R1/R2."
      />

      <div className="flex items-center gap-2 text-xs text-gray-500">
        <StatusPill tone="amber">Read-only</StatusPill>
        <span>Mutations не привязаны · последний снимок server-truth.</span>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">Dynamic Risk · /api/dynamic-risk/config</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          {r1cfg.status === 'not_connected' ? (
            <p className="text-sm text-gray-500">Endpoint /api/dynamic-risk/config не зарегистрирован.</p>
          ) : r1cfg.status === 'error' ? (
            <p className="text-sm text-rose-600">Ошибка: {r1cfg.error}</p>
          ) : (
            <>
              <KVRow label="enabled"                       value={String(cfg.enabled ?? '')}      testid="kv-r1-enabled" />
              <KVRow label="base_notional_usd"             value={cfg.base_notional_usd}          testid="kv-r1-base-notional" />
              <KVRow label="min_confidence"                value={cfg.min_confidence}             testid="kv-r1-min-conf" />
              <KVRow label="max_confidence"                value={cfg.max_confidence}             testid="kv-r1-max-conf" />
              <KVRow label="min_size_multiplier"           value={cfg.min_size_multiplier}        testid="kv-r1-min-mult" />
              <KVRow label="max_size_multiplier"           value={cfg.max_size_multiplier}        testid="kv-r1-max-mult" />
              <KVRow label="max_symbol_notional_usd"       value={cfg.max_symbol_notional_usd}    testid="kv-r1-max-symbol" />
              <KVRow label="max_portfolio_exposure_pct"    value={cfg.max_portfolio_exposure_pct} testid="kv-r1-max-portfolio" />
            </>
          )}
        </CardContent>
      </Card>

      <NotConnectedCard
        title="Adaptive Risk (R2) · конфиг"
        reason="Admin endpoint для конфигурации R2 не привязан. Поведенческая интерпретация R2 (activation rate / multiplier breakdown) — в Diagnostics → Risk R2."
      />
    </div>
  );
}

// MIRRORS · Execution Config — RAW state only
function ExecutionConfigTab() {
  return (
    <div className="p-6 space-y-6" data-testid="ta-tab-execution-config-content">
      <TabHead
        title="Execution Config"
        description="Read-only снимок execution-конфигурации. Аналитика fill / latency — в Diagnostics → Execution."
      />

      <div className="flex items-center gap-2 text-xs text-gray-500">
        <StatusPill tone="amber">Provider · not connected</StatusPill>
        <StatusPill tone="gray">Credentials · not displayed</StatusPill>
        <span>UI никогда не читает и не показывает API-ключи.</span>
      </div>

      <NotConnectedCard
        title="Execution Provider · credentials"
        reason="Admin endpoint, отдающий идентификатор провайдера / маску API-ключа / баланс счёта, для этой поверхности не привязан. Конфигурация провайдера — на стороне ops через .env (EXCHANGE_MODE), в UI не зеркалируется."
      />

      <NotConnectedCard
        title="Execution Limits · max order size / max slippage"
        reason="Admin endpoint, отдающий значения лимитов исполнения, не привязан. Лимиты применяются внутри execution-engine и наружу в UI не возвращаются."
      />
    </div>
  );
}

// MIRRORS · Strategies — raw registry counters
function StrategiesTab() {
  const dash = useAdminEndpoint('/api/dashboard/strategy', { interval: 15000 });
  const d = dash.data?.data || {};
  const strat = d.strategies || {};

  return (
    <div className="p-6 space-y-6" data-testid="ta-tab-strategies-content">
      <TabHead
        title="Strategies"
        description="Read-only зеркало /api/dashboard/strategy. Поверхности управления стратегиями для admin не привязаны."
      />

      <div className="flex items-center gap-2 text-xs text-gray-500">
        <StatusPill tone="amber">Read-only</StatusPill>
        <span>Контроллеры стратегий не привязаны.</span>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">Registry counters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          {dash.status === 'not_connected' ? (
            <p className="text-sm text-gray-500">Endpoint /api/dashboard/strategy не зарегистрирован.</p>
          ) : dash.status === 'error' ? (
            <p className="text-sm text-rose-600">Ошибка: {dash.error}</p>
          ) : (
            <>
              <KVRow label="strategies.available"  value={strat.available}    testid="kv-strat-available" />
              <KVRow label="strategies.active"     value={strat.active}       testid="kv-strat-active" />
              <KVRow label="activeProfile"         value={d.activeProfile}    testid="kv-strat-profile" />
              <KVRow label="activeConfig"          value={d.activeConfig}     testid="kv-strat-config" />
              <KVRow label="selectedStrategy"      value={d.selectedStrategy} testid="kv-strat-selected" />
              <KVRow label="recentSwitches"        value={d.recentSwitches}   testid="kv-strat-switches" />
              <KVRow label="health"                value={d.health}           testid="kv-strat-health" />
            </>
          )}
        </CardContent>
      </Card>

      <NotConnectedCard
        title="Strategy registry list"
        reason="Admin endpoint, отдающий полный реестр стратегий (id / weight / status / version), не привязан. Имена / бейджи намеренно не показываются — чтобы не рисовать fake state."
      />
    </div>
  );
}

// MIRRORS · Audit
function AuditTab() {
  const summary   = useAdminEndpoint('/api/audit/summary',                 { interval: 30000 });
  const decisions = useAdminEndpoint('/api/audit/decisions?limit=10',      { interval: 30000 });
  const exec      = useAdminEndpoint('/api/audit/execution?limit=10',      { interval: 30000 });
  const strat     = useAdminEndpoint('/api/audit/strategies?limit=10',     { interval: 30000 });
  const learn     = useAdminEndpoint('/api/audit/learning?limit=10',       { interval: 30000 });

  const sum = summary.data?.summary || {};

  const renderList = (state, items, kind) => {
    if (state.status === 'not_connected') {
      return <p className="text-sm text-gray-500">Endpoint аудита для «{kind}» не зарегистрирован.</p>;
    }
    if (state.status === 'error') {
      return <p className="text-sm text-rose-600">Ошибка: {state.error}</p>;
    }
    if (state.loading) {
      return <p className="text-sm text-gray-400">Загрузка…</p>;
    }
    if (!items || items.length === 0) {
      return (
        <p className="text-sm text-gray-500" data-testid={`audit-empty-${kind}`}>
          Аудит-событий по <code className="text-xs">{kind}</code> пока нет.
        </p>
      );
    }
    return (
      <ul className="space-y-2">
        {items.slice(0, 10).map((it, i) => {
          const ts = it.created_at || it.timestamp || it.ts || it.at || null;
          const tsLabel = ts ? new Date(ts).toLocaleString('ru-RU') : '—';
          const rawLabel = it.event_type || it.type || it.action || it.kind || kind;
          const label = String(rawLabel)
            .split(/[_\-.]+/)
            .filter(Boolean)
            .map((tok, idx) => (idx === 0 ? tok.charAt(0).toUpperCase() + tok.slice(1).toLowerCase() : tok.toLowerCase()))
            .join(' ');
          return (
            <li key={i} className="flex items-start gap-3 py-1.5 border-b text-sm last:border-b-0" data-testid={`audit-${kind}-row-${i}`}>
              <CheckCircle className="w-4 h-4 text-gray-400 mt-0.5" strokeWidth={1.75} />
              <div className="flex-1">
                <p className="font-medium text-gray-800 text-sm">{label}</p>
                <p className="text-xs text-gray-500 tabular-nums">{tsLabel}</p>
              </div>
            </li>
          );
        })}
      </ul>
    );
  };

  return (
    <div className="p-6 space-y-6" data-testid="ta-tab-audit-content">
      <TabHead
        title="Audit"
        description="Read-only зеркало /api/audit/* — decisions / execution / strategies / learning. Operator-action audit не привязан (чтобы не рисовать fake timestamps)."
      />

      <div className="flex items-center gap-2 text-xs text-gray-500">
        <StatusPill tone="amber">Read-only</StatusPill>
        <span>Пустые списки — это honest empty state, синтетических timestamps не рендерим.</span>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">Audit summary · /api/audit/summary</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          {summary.status === 'not_connected' ? (
            <p className="text-sm text-gray-500">Endpoint /api/audit/summary не зарегистрирован.</p>
          ) : (
            <>
              <KVRow label="execution_events" value={sum.execution_events} testid="audit-sum-execution" />
              <KVRow label="decisions"        value={sum.decisions}        testid="audit-sum-decisions" />
              <KVRow label="strategy_actions" value={sum.strategy_actions} testid="audit-sum-strategies" />
              <KVRow label="learning_cycles"  value={sum.learning_cycles}  testid="audit-sum-learning" />
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">Decisions · последние 10</CardTitle>
        </CardHeader>
        <CardContent>{renderList(decisions, decisions.data?.decisions, 'decisions')}</CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">Execution events · последние 10</CardTitle>
        </CardHeader>
        <CardContent>{renderList(exec, exec.data?.execution_events, 'execution')}</CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">Strategy actions · последние 10</CardTitle>
        </CardHeader>
        <CardContent>{renderList(strat, strat.data?.strategy_actions, 'strategies')}</CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">Learning cycles · последние 10</CardTitle>
        </CardHeader>
        <CardContent>{renderList(learn, learn.data?.learning_cycles, 'learning')}</CardContent>
      </Card>
    </div>
  );
}

// ============================================================================
//   ─ LIFECYCLE (operator write surfaces) ─
//   «Что оператор может запускать / обновлять?»
// ============================================================================

function CalibrationTab() {
  const [refreshKey, setRefreshKey] = useState(0);
  const handleRefresh = () => setRefreshKey(k => k + 1);
  return (
    <div className="p-6 space-y-6" data-testid="ta-tab-calibration-content">
      <TabHead
        title="Calibration"
        description="Калибровка вероятностных моделей · Build · Simulate · Apply · History · Attack tests."
      />
      <CalibrationStatusCard key={`status-${refreshKey}`} window="7d" onRefresh={handleRefresh} />
      <CalibrationBuildPanel onBuildComplete={handleRefresh} />
      <CalibrationRunHistory key={`history-${refreshKey}`} window={null} limit={10} />
      <CalibrationAttackTests />
    </div>
  );
}

function MLOpsTab() {
  return (
    <div data-testid="ta-tab-mlops-content">
      <MLOpsPage />
    </div>
  );
}

function ExchangeMLTab() {
  return (
    <div data-testid="ta-tab-exchange-ml-content">
      <AdminExchangeMLPage />
    </div>
  );
}

function AutoRetrainTab() {
  const navigate = useNavigate();
  return (
    <div className="p-6 space-y-4">
      <TabHead
        title="Auto-Retrain"
        description="Управление переобучением моделей TA · shadow ML pipeline."
      />
      <Card>
        <CardContent className="py-10">
          <div className="flex flex-col items-center text-center gap-4">
            <GraduationCap className="w-7 h-7 text-indigo-500" strokeWidth={1.75} />
            <div>
              <p className="text-sm font-medium text-gray-900">Auto-Retrain Console</p>
              <p className="text-xs text-gray-500 mt-1 max-w-md">
                Полный pipeline обучения, политики переобучения и история запусков —
                в выделенной операторской консоли.
              </p>
            </div>
            <Button
              size="sm"
              onClick={() => navigate('/admin/auto-retrain')}
              data-testid="open-auto-retrain"
            >
              Открыть Auto-Retrain
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ============================================================================
//   ─ DIAGNOSTICS (engine-internal · operator-only) ─
//   «Что происходит внутри engines прямо сейчас?»
//   Это interpretive слой. Raw-конфиг тех же эндпойнтов живёт в Mirrors.
// ============================================================================

function DataHealthTab() {
  // Полная панель data-health observability (admin canonical).
  return <DataHealthPanel />;
}

function RiskR1Tab() {
  return (
    <div className="p-6 space-y-4">
      <TabHead
        title="Risk R1 · Analytics"
        description="Поведение Dynamic Risk engine: approve / block rate, средний multiplier, clamp rate. Сырая конфигурация R1 — в Mirrors → Risk Limits."
      />
      <DynamicRiskAnalyticsPanel />
    </div>
  );
}

function RiskR2Tab() {
  const { data, loading } = useAdaptiveRiskAnalytics();
  return (
    <div className="p-6 space-y-4">
      <TabHead
        title="Risk R2 · Analytics"
        description="Поведение Adaptive Risk engine: activation rate, средний multiplier, drawdown / loss-streak components."
      />
      <AdaptiveRiskAnalyticsPanel data={data} loading={loading} />
    </div>
  );
}

function ExecutionTab() {
  return (
    <div className="p-6 space-y-4">
      <TabHead
        title="Execution · Analytics"
        description="«Доходят ли решения до fill?» — queued / submitted / filled / failed / fill-rate."
      />
      <ExecutionAnalyticsPanel />
    </div>
  );
}

function SafetyTab() {
  return (
    <div className="p-6 space-y-4">
      <TabHead
        title="Safety · Analytics"
        description="«Кто блокирует чаще: R1 или AutoSafety?» — top rules, breakdown по причинам."
      />
      <SafetyAnalyticsPanel />
    </div>
  );
}

function LearningTab() {
  return (
    <div className="p-6 space-y-4">
      <TabHead
        title="Learning · Insights"
        description="ML feedback loop: качество фич, цикл обучения модели."
      />
      <LearningInsightsPanel />
    </div>
  );
}

// HypothesesView — единственная панель, опирающаяся на user-store (useMarket).
// Чтобы не тащить <MarketProvider> на весь admin — оборачиваем локально.
function HypothesesTab() {
  return (
    <MarketProvider>
      <div className="p-6">
        <TabHead
          title="Hypotheses · Lab"
          description="Strategy lab · бэктест-движок · profit factor / win-rate / drawdown. Research-поверхность, не торговля."
        />
        <HypothesesView />
      </div>
    </MarketProvider>
  );
}

// ============================================================================
//   ─ NAV REGISTRY (canonical 4-mode IA) ─
// ============================================================================
const NAV_GROUPS = [
  {
    id: 'observability',
    label: 'Observability',
    sublabel: 'R5..R10 · live',
    items: [
      { id: 'core7-context',        label: 'Core7 Context',        icon: Layers,     render: Core7ContextWrap        },
      { id: 'calibration-quality',  label: 'Calibration Quality',  icon: Activity,   render: CalibrationQualityWrap  },
      { id: 'prediction-integrity', label: 'Prediction Integrity', icon: ScanLine,   render: PredictionIntegrityWrap },
      { id: 'shadow-gate',          label: 'Shadow Gate',          icon: Eye,        render: ShadowGateWrap          },
      { id: 'gate-evaluation',      label: 'Gate Evaluation',      icon: CircleDot,  render: GateEvaluationWrap      },
      { id: 'gate-analytics',       label: 'Gate Analytics',       icon: TimerReset, render: GateAnalyticsWrap       },
    ],
  },
  {
    id: 'mirrors',
    label: 'Mirrors',
    sublabel: 'Read-only · prod state',
    items: [
      { id: 'trading-control',  label: 'Trading Control',  icon: Settings,          render: TradingControlTab  },
      { id: 'risk-limits',      label: 'Risk Limits',      icon: SlidersHorizontal, render: RiskLimitsTab      },
      { id: 'execution-config', label: 'Execution Config', icon: Cog,               render: ExecutionConfigTab },
      { id: 'strategies',       label: 'Strategies',       icon: Target,            render: StrategiesTab      },
      { id: 'audit',            label: 'Audit',            icon: FileText,          render: AuditTab           },
    ],
  },
  {
    id: 'lifecycle',
    label: 'Lifecycle',
    sublabel: 'Operator write surfaces',
    items: [
      { id: 'calibration',   label: 'Calibration',   icon: Gauge,         render: CalibrationTab   },
      { id: 'mlops',         label: 'MLOps',         icon: Rocket,        render: MLOpsTab         },
      { id: 'exchange-ml',   label: 'Exchange ML',   icon: Database,      render: ExchangeMLTab    },
      { id: 'auto-retrain',  label: 'Auto-Retrain',  icon: GraduationCap, render: AutoRetrainTab   },
    ],
  },
  {
    id: 'diagnostics',
    label: 'Diagnostics',
    sublabel: 'Engine internals',
    items: [
      { id: 'data-health',   label: 'Data Health',   icon: HeartPulse,   render: DataHealthTab },
      { id: 'risk-r1',       label: 'Risk R1',       icon: Shield,       render: RiskR1Tab     },
      { id: 'risk-r2',       label: 'Risk R2',       icon: ShieldAlert,  render: RiskR2Tab     },
      { id: 'execution',     label: 'Execution',     icon: Radio,        render: ExecutionTab  },
      { id: 'safety',        label: 'Safety',        icon: AlertOctagon, render: SafetyTab     },
      { id: 'learning',      label: 'Learning',      icon: BrainIcon,    render: LearningTab   },
      { id: 'hypotheses',    label: 'Hypotheses',    icon: Beaker,       render: HypothesesTab },
    ],
  },
];

// Mode metadata · mental model верхнего уровня.
const MODE_META = {
  observability: { label: 'Observability', sublabel: 'Trustworthy?',     icon: Activity, tone: 'sky'     },
  mirrors:       { label: 'Mirrors',       sublabel: 'Configured?',      icon: Layers,   tone: 'indigo'  },
  lifecycle:     { label: 'Lifecycle',     sublabel: 'Operate',          icon: Gauge,    tone: 'emerald' },
  diagnostics:   { label: 'Diagnostics',   sublabel: 'Engine internals', icon: Bug,      tone: 'red'     },
};

const MODE_TONE_CLASSES = {
  sky: {
    active: 'bg-sky-600 text-white border-sky-600 shadow-sm',
    idle:   'bg-white text-gray-700 hover:bg-sky-50 border-gray-200',
  },
  indigo: {
    active: 'bg-indigo-600 text-white border-indigo-600 shadow-sm',
    idle:   'bg-white text-gray-700 hover:bg-indigo-50 border-gray-200',
  },
  emerald: {
    active: 'bg-emerald-600 text-white border-emerald-600 shadow-sm',
    idle:   'bg-white text-gray-700 hover:bg-emerald-50 border-gray-200',
  },
  red: {
    active: 'bg-red-600 text-white border-red-600 shadow-sm',
    idle:   'bg-white text-gray-700 hover:bg-red-50 border-gray-200',
  },
};

// ============================================================================
//   ─ MAIN COMPONENT ─
// ============================================================================
export default function AdminTechAnalysisPage() {
  const navigate = useNavigate();
  const { isAuthenticated, loading: authLoading } = useAdminAuth();
  // По умолчанию открываем Observability — главная мысль страницы:
  // «насколько система trustworthy прямо сейчас».
  const [mode, setMode] = useState('observability');
  const [activeTabId, setActiveTabId] = useState('core7-context');

  React.useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      navigate('/admin/login', { replace: true });
    }
  }, [isAuthenticated, authLoading, navigate]);

  if (authLoading || !isAuthenticated) {
    return null;
  }

  const currentGroup = NAV_GROUPS.find(g => g.id === mode) || NAV_GROUPS[0];
  const currentItems = currentGroup.items;
  const activeItem = currentItems.find(it => it.id === activeTabId) || currentItems[0];

  const handleModeChange = (nextMode) => {
    if (nextMode === mode) return;
    setMode(nextMode);
    const nextGroup = NAV_GROUPS.find(g => g.id === nextMode);
    if (nextGroup && nextGroup.items.length) {
      setActiveTabId(nextGroup.items[0].id);
    }
  };

  return (
    <AdminLayout>
      <div className="p-6 space-y-5" data-testid="admin-tech-analysis-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <LineChart className="w-5 h-5 text-indigo-600" strokeWidth={1.75} />
            <div>
              <h1 className="text-xl font-semibold text-slate-900">
                Tech Analysis · Operator Console
              </h1>
              <p className="text-xs text-gray-500">
                Operator-grade консоль · Observability → Mirrors → Lifecycle → Diagnostics.
              </p>
            </div>
          </div>
          <Badge
            variant="outline"
            className="bg-indigo-50 text-indigo-700 border-indigo-200"
            data-testid="ta-current-mode-badge"
          >
            {MODE_META[mode].label}
          </Badge>
        </div>

        {/* Level 1 — Mode switch */}
        <div
          className="flex flex-wrap gap-2"
          role="tablist"
          aria-label="Tech Analysis admin modes"
          data-testid="ta-mode-switch"
        >
          {Object.entries(MODE_META).map(([modeId, meta]) => {
            const Icon = meta.icon;
            const isActive = modeId === mode;
            const cls = MODE_TONE_CLASSES[meta.tone];
            const groupLen = NAV_GROUPS.find(g => g.id === modeId)?.items?.length ?? 0;
            return (
              <button
                key={modeId}
                type="button"
                onClick={() => handleModeChange(modeId)}
                role="tab"
                aria-selected={isActive}
                data-testid={`ta-mode-${modeId}`}
                className={`flex items-center gap-2.5 px-4 py-2.5 rounded-lg border text-sm font-semibold transition-colors ${
                  isActive ? cls.active : cls.idle
                }`}
              >
                <Icon className="w-4 h-4" strokeWidth={1.75} />
                <div className="flex flex-col items-start leading-tight">
                  <span>{meta.label}</span>
                  <span className={`text-[10px] font-normal uppercase tracking-wider ${
                    isActive ? 'text-white/80' : 'text-gray-400'
                  }`}>
                    {meta.sublabel} · {groupLen}
                  </span>
                </div>
              </button>
            );
          })}
        </div>

        {/* Level 2 — Tabs of the active mode */}
        <Tabs value={activeItem.id} onValueChange={setActiveTabId}>
          <TabsList
            className="bg-gray-100 flex-wrap h-auto gap-1 p-1 justify-start w-full"
            data-testid="ta-tabs-bar"
          >
            {currentItems.map(item => {
              const Icon = item.icon;
              return (
                <TabsTrigger
                  key={item.id}
                  value={item.id}
                  data-testid={`ta-tab-${item.id}`}
                  className="data-[state=active]:bg-white data-[state=active]:shadow-sm text-xs gap-1.5 px-2.5 py-1.5"
                >
                  <Icon className="w-3.5 h-3.5" strokeWidth={1.75} />
                  <span>{item.label}</span>
                </TabsTrigger>
              );
            })}
          </TabsList>

          {currentItems.map(item => {
            const Render = item.render;
            return (
              <TabsContent key={item.id} value={item.id} className="mt-4">
                <Render />
              </TabsContent>
            );
          })}
        </Tabs>
      </div>
    </AdminLayout>
  );
}
