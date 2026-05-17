/**
 * BLOCK 50 + P6 — Admin Dashboard with Tabs
 * 
 * Institutional control panel for Fractal v2.0-stable
 * Tabs: Обзор | Жизненный цикл | Дрифт | Здоровье | Управление | История
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { GovernanceCard } from './GovernanceCard';
import { HealthCard } from './HealthCard';
import { ReliabilityCard } from './ReliabilityCard';
import { PerformanceCard } from './PerformanceCard';
import { GuardCard } from './GuardCard';
import { PlaybookCard } from './PlaybookCard';
import { TailRiskCard } from './TailRiskCard';
import { SnapshotTimeline } from './SnapshotTimeline';
import { WeeklyCronCard } from './WeeklyCronCard';
import { ShadowDivergencePanel } from './shadow';
import VolatilityTab from './VolatilityTab';
import AlertsTab from './AlertsTab';
import AttributionTab from './AttributionTab';
import GovernanceTab from './GovernanceTab';
import BackfillProgressPanel from './BackfillProgressPanel';
import DriftTab from './DriftTab';
import OpsTab from './OpsTab';
import IntelTab from './IntelTab';
import SpxAdminTab from './SpxAdminTab';
import SpxAttributionTab from './SpxAttributionTab';
import SpxCalibrationTab from './SpxCalibrationTab';
import SpxDriftTab from './SpxDriftTab';
import SpxRulesTab from './SpxRulesTab';
import SpxCrisisTab from './SpxCrisisTab';
import SpxDecadeTrackerTab from './SpxDecadeTrackerTab';
import SpxRegimesTab from './SpxRegimesTab';
import SpxConstitutionTab from './SpxConstitutionTab';
import SpxGovernanceTab from './SpxGovernanceTab';
import LifecycleTab from './LifecycleTab';
import HealthTab from './HealthTab';
import TimelineTab from './TimelineTab';
import { ModelQualityCard } from './ModelQualityCard';
import { BootstrapProgressCard, RollbackCard } from './BootstrapProgressCard';
import { AssetSelector } from '../AssetSelector';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

// Check if system is in PROD/FROZEN mode
const isProdMode = () => {
  return process.env.REACT_APP_PROD_MODE === 'true' || 
         process.env.NODE_ENV === 'production';
};

// Asset product info for different terminals
const ASSET_INFO = {
  BTC: { name: 'BTC Terminal', status: 'FINAL', color: 'orange', available: true },
  SPX: { name: 'SPX Terminal', status: 'FINAL', color: 'blue', available: true },
  DXY: { name: 'DXY Macro', status: 'FINAL', color: 'green', available: true },
  CROSS: { name: 'Cross-Asset', status: 'FINAL', color: 'purple', available: true },
};

// Storage key for seed toggle
const SEED_TOGGLE_KEY = 'admin_include_seed';

// ═══════════════════════════════════════════════════════════════
// ФИНАЛЬНЫЕ ТАБЫ — Только актуальные для продакшена
// ═══════════════════════════════════════════════════════════════

// Табы для BTC (финальная версия)
const BTC_TABS = [
  { id: 'overview', label: 'Обзор', tooltip: 'Главная панель с ключевыми метриками модели' },
  { id: 'lifecycle', label: 'Жизненный цикл', tooltip: 'Версионирование и история изменений модели' },
  { id: 'drift', label: 'Дрифт', tooltip: 'Анализ отклонения модели: by-horizon, rolling, by-regime' },
  { id: 'health', label: 'Здоровье', tooltip: 'Статус модели: HEALTHY / DEGRADED / CRITICAL' },
  { id: 'governance', label: 'Управление', tooltip: 'Freeze/Unfreeze, promote, rollback' },
  { id: 'timeline', label: 'История', tooltip: 'Хронология всех событий модели' },
];

// Табы для SPX
const SPX_TABS = [
  { id: 'overview', label: 'Обзор', tooltip: 'Главная панель SPX модели' },
  { id: 'lifecycle', label: 'Жизненный цикл', tooltip: 'Версионирование SPX' },
  { id: 'drift', label: 'Дрифт', tooltip: 'Анализ отклонения SPX модели' },
  { id: 'health', label: 'Здоровье', tooltip: 'Статус SPX модели' },
  { id: 'governance', label: 'Управление', tooltip: 'Governance SPX' },
  { id: 'timeline', label: 'История', tooltip: 'Timeline SPX' },
];

// Табы для DXY
const DXY_TABS = [
  { id: 'overview', label: 'Обзор', tooltip: 'Главная панель DXY макро-модели' },
  { id: 'lifecycle', label: 'Жизненный цикл', tooltip: 'Версионирование DXY' },
  { id: 'drift', label: 'Дрифт', tooltip: 'Анализ отклонения DXY (67% hit rate)' },
  { id: 'health', label: 'Здоровье', tooltip: 'Статус DXY модели' },
  { id: 'governance', label: 'Управление', tooltip: 'Governance DXY' },
  { id: 'timeline', label: 'История', tooltip: 'Timeline DXY' },
];

// Табы для CROSS-ASSET
const CROSS_TABS = [
  { id: 'overview', label: 'Обзор', tooltip: 'Composite модель: BTC + SPX + DXY' },
  { id: 'weights', label: 'Веса', tooltip: 'Веса компонент: BTC 50%, SPX 30%, DXY 20%' },
  { id: 'drift', label: 'Дрифт', tooltip: 'Сравнение composite vs parents' },
  { id: 'health', label: 'Здоровье', tooltip: 'Статус composite модели' },
  { id: 'timeline', label: 'История', tooltip: 'Timeline composite' },
];

// Get tabs based on asset
function getTabsForAsset(asset) {
  switch (asset) {
    case 'SPX': return SPX_TABS;
    case 'DXY': return DXY_TABS;
    case 'CROSS': return CROSS_TABS;
    case 'BTC':
    default: return BTC_TABS;
  }
}

export function AdminDashboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const activeTab = searchParams.get('tab') || 'overview';
  const currentAsset = searchParams.get('asset') || 'BTC';

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [freezeStatus, setFreezeStatus] = useState(null);
  
  // SEED TOGGLE: Include seed_backtest data in metrics
  const [includeSeed, setIncludeSeed] = useState(() => {
    // В PROD режиме seed всегда выключен
    if (isProdMode()) return false;
    try {
      return localStorage.getItem(SEED_TOGGLE_KEY) === 'true';
    } catch {
      return false;
    }
  });
  
  // Fetch freeze status
  useEffect(() => {
    async function checkFreezeStatus() {
      try {
        const res = await fetch(`${API_BASE}/api/admin/freeze-status`);
        const data = await res.json();
        setFreezeStatus(data);
      } catch (err) {
        console.error('Failed to fetch freeze status:', err);
      }
    }
    checkFreezeStatus();
  }, []);
  
  const toggleSeed = useCallback(() => {
    setIncludeSeed(prev => {
      const newVal = !prev;
      try {
        localStorage.setItem(SEED_TOGGLE_KEY, String(newVal));
      } catch {}
      return newVal;
    });
  }, []);
  
  // Handle asset selection
  const handleAssetSelect = (assetId) => {
    const params = new URLSearchParams(searchParams);
    params.set('asset', assetId);
    setSearchParams(params, { replace: true });
    // Force refresh data
    setLoading(true);
  };
  
  const setActiveTab = (tabId) => {
    const params = new URLSearchParams(searchParams);
    params.set('tab', tabId);
    // Reset shadow params when switching away
    if (tabId !== 'shadow') {
      params.delete('preset');
      params.delete('h');
      params.delete('role');
    }
    setSearchParams(params, { replace: true });
  };

  const fetchData = useCallback(async () => {
    try {
      // Use unified dashboard aggregator endpoint
      const scopeMap = {
        'BTC': 'btc',
        'SPX': 'spx',
        'DXY': 'dxy',
        'COMBINED': 'btc', // Default to BTC for combined view
      };
      const scope = scopeMap[currentAsset] || 'btc';
      
      // Add includeSeed param if enabled
      const seedParam = includeSeed ? '?includeSeed=true' : '';
      const response = await fetch(`${API_BASE}/api/admin/${scope}/dashboard${seedParam}`);
      if (!response.ok) throw new Error('Failed to fetch admin dashboard');
      const result = await response.json();
      
      if (result.ok) {
        // Transform unified dashboard to existing data structure
        const dashboard = result.data;
        
        // Determine governance mode based on health state
        let mode = 'NORMAL';
        if (dashboard.health.frozen) mode = 'FREEZE';
        else if (dashboard.health.grade === 'CRITICAL') mode = 'CONSERVATIVE';
        else if (dashboard.health.grade === 'DEGRADED') mode = 'CONSERVATIVE';
        
        setData({
          governance: {
            mode: mode,
            freeze: {
              isFrozen: dashboard.health.frozen,
              reason: dashboard.health.reasons?.[0] || null,
            },
            guardrails: {
              state: dashboard.health.grade === 'CRITICAL' ? 'ACTIVE' : 'OFF',
            },
            config: {
              windowLen: dashboard.governance.windowLen,
              topK: dashboard.governance.topK,
              consensusThreshold: dashboard.governance.consensusThreshold,
              minGapDays: dashboard.governance.minGapDays,
            },
          },
          health: {
            state: dashboard.health.grade === 'UNKNOWN' ? 'HEALTHY' : dashboard.health.grade,
            score: dashboard.health.hitRate ?? 0,
            hitRate: dashboard.health.hitRate ?? 0,
            avgAbsError: dashboard.health.avgAbsError ?? 0,
            sampleCount: dashboard.health.sampleCount ?? 0,
            modifier: dashboard.health.modifier ?? 1,
            frozen: dashboard.health.frozen,
            reasons: dashboard.health.reasons,
            headline: dashboard.health.sampleCount === 0 
              ? 'Система запущена. Ожидается накопление данных для расчета метрик.' 
              : null,
          },
          guard: {
            state: dashboard.health.frozen ? 'ALERT' : 'OK',
            degenerationScore: 0,
            frozen: dashboard.health.frozen,
            drift: dashboard.drift.trend,
            subscores: {},
          },
          model: {
            hitRate: dashboard.health.hitRate,
            avgAbsError: dashboard.health.avgAbsError,
            sampleCount: dashboard.health.sampleCount,
          },
          performance: {
            snapshotsTotal: dashboard.snapshots.total,
            snapshotsResolved: dashboard.snapshots.resolved,
            snapshotsPending: dashboard.snapshots.pending,
          },
          version: dashboard.version,
          confidenceMeta: dashboard.confidenceMeta,
          lastEvents: dashboard.lastEvents,
          meta: dashboard.meta,
        });
        setLastUpdate(new Date());
        setError(null);
      } else {
        throw new Error(result.error || 'Dashboard fetch failed');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [currentAsset, includeSeed]);
  
  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);
  
  // Refetch when seed toggle changes
  useEffect(() => {
    if (!loading) {
      fetchData();
    }
  }, [includeSeed]); // eslint-disable-line react-hooks/exhaustive-deps
  
  const handleApplyPlaybook = async (playbookType) => {
    try {
      const response = await fetch(`${API_BASE}/api/fractal/v2.1/admin/playbook/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: playbookType,
          confirm: true,
          actor: 'ADMIN',
          reason: 'Applied from Admin Dashboard',
        }),
      });
      
      if (!response.ok) throw new Error('Failed to apply playbook');
      await fetchData();
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  };
  
  // Loading state - only for Overview tab
  if (loading && activeTab === 'overview') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600">Загрузка панели управления...</p>
        </div>
      </div>
    );
  }
  
  const assetInfo = ASSET_INFO[currentAsset] || ASSET_INFO.BTC;
  
  return (
    <div className="min-h-screen bg-gray-50">
      {/* PROD LOCKED Banner */}
      {freezeStatus?.frozen && (
        <div className="bg-slate-900 text-white py-2 px-4 text-center text-sm font-medium">
          <span className="inline-flex items-center gap-2">
            <svg className="w-4 h-4 text-emerald-400" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
            </svg>
            PROD LOCKED ({freezeStatus?.env?.FREEZE_VERSION || 'v2.0'}) — Система заморожена. Мутационные операции заблокированы.
          </span>
        </div>
      )}
      
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div>
                <div className="flex items-center gap-3">
                  <h1 className="text-xl font-bold text-gray-900">
                    {assetInfo.name}
                  </h1>
                  {/* MODEL STATUS Badge */}
                  <span className={`px-2.5 py-1 text-xs font-bold rounded-full ${
                    freezeStatus?.frozen 
                      ? 'bg-emerald-100 text-emerald-800 border border-emerald-300' 
                      : 'bg-amber-100 text-amber-800 border border-amber-300'
                  }`} data-testid="model-status-badge">
                    {freezeStatus?.frozen ? 'PROD LOCKED' : 'DEV MODE'}
                  </span>
                </div>
                <p className="text-sm text-gray-500 mt-0.5">
                  Панель управления моделью
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-4">
              {/* Asset Selector */}
              <AssetSelector 
                currentAsset={currentAsset} 
                onSelect={handleAssetSelect}
              />
              
              {/* SEED TOGGLE — скрыт в PROD режиме */}
              {!freezeStatus?.frozen && (
                <button
                  onClick={toggleSeed}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    includeSeed 
                      ? 'bg-purple-100 text-purple-800 border border-purple-300' 
                      : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                  }`}
                  title={includeSeed ? 'Показываются тестовые и реальные данные' : 'Нажмите чтобы включить тестовые данные'}
                  data-testid="seed-toggle-btn"
                >
                  <div className={`w-2 h-2 rounded-full ${includeSeed ? 'bg-purple-500' : 'bg-gray-400'}`}></div>
                  {includeSeed ? 'Тест. данные вкл.' : 'Тест. данные выкл.'}
                </button>
              )}
              
              <span className="text-xs text-gray-400">
                Обновлено: {lastUpdate?.toLocaleTimeString('ru-RU') || '—'}
              </span>
              <button
                onClick={fetchData}
                className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                title="Обновить данные"
                data-testid="refresh-btn"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 mt-4 border-b border-gray-200 -mb-px">
            {getTabsForAsset(currentAsset).map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                title={tab.tooltip}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
                data-testid={`tab-${tab.id}`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </header>
      
      {/* Tab Content — Universal Renderer */}
      <TabContent 
        activeTab={activeTab} 
        currentAsset={currentAsset}
        data={data}
        error={error}
        fetchData={fetchData}
        handleApplyPlaybook={handleApplyPlaybook}
      />
      
      {/* Footer */}
      <footer className="border-t border-gray-200 bg-white mt-8">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span>Fractal Platform</span>
            <span>Панель управления моделями</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

/**
 * Universal Tab Content Renderer
 * Поддерживает все активы: BTC, SPX, DXY, CROSS
 */
function TabContent({ activeTab, currentAsset, data, error, fetchData, handleApplyPlaybook }) {
  // Универсальные табы (работают для всех активов)
  const universalTabs = {
    overview: (
      <OverviewTab 
        data={data} 
        error={error} 
        fetchData={fetchData}
        handleApplyPlaybook={handleApplyPlaybook}
        asset={currentAsset}
      />
    ),
    lifecycle: <LifecycleTab asset={currentAsset} />,
    drift: <DriftTab asset={currentAsset} />,
    health: (
      <div className="max-w-7xl mx-auto px-4 py-6">
        <HealthTab asset={currentAsset} />
      </div>
    ),
    governance: <GovernanceTab asset={currentAsset} />,
    timeline: (
      <div className="max-w-7xl mx-auto px-4 py-6">
        <TimelineTab asset={currentAsset} />
      </div>
    ),
    weights: (
      <div className="max-w-7xl mx-auto px-4 py-6">
        <WeightsTab />
      </div>
    ),
  };
  
  // Проверяем универсальный таб
  if (universalTabs[activeTab]) {
    return universalTabs[activeTab];
  }
  
  // Fallback: Overview
  return universalTabs.overview;
}

/**
 * Weights Tab for Cross-Asset
 */
function WeightsTab() {
  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  
  React.useEffect(() => {
    async function fetchWeights() {
      try {
        const res = await fetch(`${API_BASE}/api/cross-asset/admin/drift/weights?includeSeed=true`);
        const json = await res.json();
        setData(json);
      } catch (err) {
        console.error('Error fetching weights:', err);
      } finally {
        setLoading(false);
      }
    }
    fetchWeights();
  }, []);
  
  if (loading) {
    return <div className="text-center py-8 text-gray-500">Загрузка весов...</div>;
  }
  
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6" data-testid="weights-tab">
      <h2 className="text-xl font-bold text-gray-900 mb-4">Веса компонент Cross-Asset</h2>
      <p className="text-gray-500 mb-6">
        Composite модель использует взвешенное усреднение сигналов от трёх базовых моделей.
      </p>
      
      <div className="grid grid-cols-3 gap-6">
        <div className="bg-orange-50 rounded-xl p-4 border border-orange-200">
          <div className="text-3xl font-bold text-orange-600 mb-2">50%</div>
          <div className="text-sm font-medium text-gray-700">BTC</div>
          <div className="text-xs text-gray-500 mt-1">Bitcoin Fractal Model</div>
        </div>
        
        <div className="bg-blue-50 rounded-xl p-4 border border-blue-200">
          <div className="text-3xl font-bold text-blue-600 mb-2">30%</div>
          <div className="text-sm font-medium text-gray-700">SPX</div>
          <div className="text-xs text-gray-500 mt-1">S&P 500 Structure</div>
        </div>
        
        <div className="bg-emerald-50 rounded-xl p-4 border border-emerald-200">
          <div className="text-3xl font-bold text-emerald-600 mb-2">20%</div>
          <div className="text-sm font-medium text-gray-700">DXY</div>
          <div className="text-xs text-gray-500 mt-1">Dollar Macro Factor</div>
        </div>
      </div>
      
      {data?.diagnostics && (
        <div className="mt-6 p-4 bg-gray-50 rounded-lg">
          <h3 className="text-sm font-medium text-gray-700 mb-2">Диагностика</h3>
          <pre className="text-xs text-gray-600">{JSON.stringify(data.diagnostics, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

/**
 * Overview Tab (Original Admin Dashboard content)
 */
function OverviewTab({ data, error, fetchData, handleApplyPlaybook, asset = 'BTC' }) {
  if (error) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center p-6 bg-red-50 rounded-xl border border-red-200 max-w-md">
          <p className="text-red-600 font-medium mb-2">Ошибка загрузки</p>
          <p className="text-red-500 text-sm">{error}</p>
          <button 
            onClick={fetchData}
            className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg text-sm hover:bg-red-700"
          >
            Повторить
          </button>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600">Загрузка...</p>
        </div>
      </div>
    );
  }

  // Rollback handler
  const handleRollback = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/admin/jobs/run?job=rollback&scope=${asset}`, {
        method: 'POST'
      });
      const result = await res.json();
      if (result.ok) {
        fetchData();
      }
    } catch (err) {
      console.error('Rollback failed:', err);
    }
  };

  return (
    <main className="max-w-7xl mx-auto px-4 py-6">
      {/* Rollback Warning (for CRITICAL/DEGRADED) */}
      <RollbackCard health={data?.health} onRollback={handleRollback} />
      
      {/* Top Row - Critical Status */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6 mt-4">
        <GovernanceCard governance={data?.governance} />
        <HealthCard health={data?.health} />
        <GuardCard guard={data?.guard} />
        <ModelQualityCard asset={asset} />
      </div>
      
      {/* Bootstrap Progress (if not enough samples) */}
      {data?.health?.sampleCount < 30 && (
        <div className="mb-6">
          <BootstrapProgressCard 
            sampleCount={data?.health?.sampleCount || 0} 
            minSamples={30} 
          />
        </div>
      )}
      
      {/* Middle Row - Model Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <ReliabilityCard model={data?.model} />
        <TailRiskCard model={data?.model} />
        <PerformanceCard performance={data?.performance} />
      </div>
      
      {/* Bottom Row - Actions & History */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <PlaybookCard 
          recommendation={data?.recommendation} 
          onApply={handleApplyPlaybook}
        />
        <SnapshotTimeline recent={data?.recent} />
      </div>
      
      {/* BLOCK 76.2.2: Weekly Cron Control */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <WeeklyCronCard />
      </div>
    </main>
  );
}

export default AdminDashboard;
