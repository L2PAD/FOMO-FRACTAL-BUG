/**
 * Exchange Intelligence — Main Page
 * ==================================
 * 6 tabs: Overview | Prediction | Market | Alpha | Insights | Engine
 * Active tab = dark bg. Inactive = plain text.
 * 
 * Insights = Labs | Research with shared Global/Universe/Asset mode
 * Engine = Core Engine | Capital Flow with prominent switcher
 * Alpha = single page (Radar with Signals in control bar)
 */

import React, { useState, useEffect, useRef, Suspense, lazy } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Activity, BarChart3, Target, Loader2, Crosshair, Brain, Settings2,
  Globe, Search, X, TestTubes, FlaskConical, Cpu, TrendingUp,
} from 'lucide-react';

const ExchangeOverviewPage = lazy(() => import('./OverviewV2Page'));
const ExchangeMarketBoard = lazy(() => import('./ExchangeMarketBoard'));
const AltRadarPage = lazy(() => import('./ExchangeRadarTab'));
const LabsPageV3 = lazy(() => import('./LabsPageNew'));
const ExchangeResearchPage = lazy(() => import('./ExchangeResearchPage'));
const MacroV2Page = lazy(() => import('./MacroV2Page'));
const CoreEnginePage = lazy(() => import('./CoreEnginePage'));
const PredictionPage = lazy(() => import('./PredictionPage'));

const TABS = [
  { id: 'overview', label: 'Overview', icon: Activity },
  { id: 'prediction', label: 'Prediction', icon: Target },
  { id: 'market-board', label: 'Market', icon: BarChart3 },
  { id: 'alpha', label: 'Alpha', icon: Crosshair },
  { id: 'insights', label: 'Insights', icon: Brain },
  { id: 'engine', label: 'Engine', icon: Settings2 },
];

const TAB_COMPONENTS = {
  'overview': ExchangeOverviewPage,
  'prediction': PredictionPage,
  'market-board': ExchangeMarketBoard,
  'alpha': AltRadarPage,
  'insights:labs': LabsPageV3,
  'insights:research': ExchangeResearchPage,
  'engine:core': CoreEnginePage,
  'engine:capital': MacroV2Page,
};

const LEGACY_MAP = {
  'signals': { tab: 'alpha' },
  'alt-radar': { tab: 'alpha' },
  'research': { tab: 'insights', sub: 'research' },
  'labs': { tab: 'insights', sub: 'labs' },
  'macro-v2': { tab: 'engine', sub: 'capital' },
  'core-engine': { tab: 'engine', sub: 'core' },
};

function LoadingFallback() {
  return <div className="flex items-center justify-center h-64"><Loader2 className="w-6 h-6 animate-spin text-gray-400" /></div>;
}

/* ═══ INSIGHTS BAR — Labs|Research ... Global|Universe|Asset ═══ */

function InsightsBar({ activeSub, onSubChange, mode, onModeChange, symbol, symbols, onSymbolSelect }) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const searchRef = useRef(null);

  useEffect(() => {
    if (!searchOpen) return;
    const handler = (e) => { if (searchRef.current && !searchRef.current.contains(e.target)) { setSearchOpen(false); setSearchQuery(''); } };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [searchOpen]);

  const filtered = searchQuery
    ? symbols.filter(s => s.replace('USDT', '').toLowerCase().includes(searchQuery.toLowerCase())).slice(0, 20)
    : symbols.slice(0, 20);

  const tabStyle = (active) => `flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
    active ? 'bg-gray-900 text-white' : 'text-gray-500 hover:text-gray-700'
  }`;

  return (
    <div>
      <div className="px-6">
        <div className="flex items-center justify-between py-3" data-testid="insights-bar">
          {/* Left: Labs / Research */}
          <div className="flex items-center gap-1">
            {[
              { id: 'labs', label: 'Labs', icon: TestTubes },
              { id: 'research', label: 'Research', icon: FlaskConical },
            ].map(sub => {
              const Icon = sub.icon;
              const isActive = activeSub === sub.id;
              return (
                <button key={sub.id} onClick={() => onSubChange(sub.id)}
                  data-testid={`insights-sub-${sub.id}`}
                  className={tabStyle(isActive)}>
                  <Icon className="w-4 h-4" />
                  {sub.label}
                </button>
              );
            })}
          </div>

          {/* Right: Global / Universe / Asset */}
          <div className="flex items-center gap-1">
            {[
              { id: 'global', label: 'Global', icon: Globe },
              { id: 'universe', label: 'Universe', icon: BarChart3 },
            ].map(m => {
              const Icon = m.icon;
              const isActive = mode === m.id;
              return (
                <button key={m.id} onClick={() => onModeChange(m.id)}
                  data-testid={`insights-mode-${m.id}`}
                  className={tabStyle(isActive)}>
                  <Icon className="w-4 h-4" />
                  {m.label}
                </button>
              );
            })}

            <div className="relative" ref={searchRef}>
              <button onClick={() => setSearchOpen(!searchOpen)}
                data-testid="insights-mode-asset"
                className={tabStyle(mode === 'asset')}>
                <Search className="w-3.5 h-3.5" />
                {mode === 'asset' ? symbol.replace('USDT', '') : 'Asset'}
              </button>
              {searchOpen && (
                <div className="absolute right-0 top-full mt-2 z-50 w-72 rounded-xl overflow-hidden bg-white"
                  style={{ boxShadow: '0 16px 48px rgba(0,0,0,0.12)' }}>
                  <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100">
                    <Search className="w-4 h-4 flex-shrink-0 text-gray-400" />
                    <input autoFocus value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
                      placeholder="Search asset..." className="flex-1 text-[14px] outline-none bg-transparent font-medium text-gray-900" />
                    {searchQuery && <button onClick={() => setSearchQuery('')}><X className="w-3.5 h-3.5 text-gray-400" /></button>}
                  </div>
                  <div className="max-h-64 overflow-y-auto py-1">
                    {filtered.length === 0 && <div className="px-4 py-3 text-[13px] text-gray-400">No results</div>}
                    {filtered.map(s => (
                      <button key={s} onClick={() => { onSymbolSelect(s); setSearchOpen(false); setSearchQuery(''); }}
                        className="w-full text-left px-4 py-2 text-[13px] font-semibold hover:bg-gray-50 transition-colors text-gray-900">
                        {s.replace('USDT', '')}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══ ENGINE BAR — Core Engine | Capital Flow ═══ */

function EngineBar({ activeSub, onSubChange }) {
  return (
    <div>
      <div className="px-6">
        <div className="flex items-center py-3" data-testid="engine-bar">
          <div className="flex items-center gap-1">
            {[
              { id: 'core', label: 'Core Engine', icon: Cpu },
              { id: 'capital', label: 'Capital Flow', icon: TrendingUp },
            ].map(sub => {
              const Icon = sub.icon;
              const isActive = activeSub === sub.id;
              return (
                <button key={sub.id} onClick={() => onSubChange(sub.id)}
                  data-testid={`engine-sub-${sub.id}`}
                  className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    isActive ? 'bg-gray-900 text-white' : 'text-gray-500 hover:text-gray-700'
                  }`}>
                  <Icon className="w-4 h-4" />
                  {sub.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══ MAIN PAGE ═══ */

export default function ExchangePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const API = process.env.REACT_APP_BACKEND_URL;

  // Insights mode state
  const [insightsMode, setInsightsMode] = useState('global');
  const [insightsSymbol, setInsightsSymbol] = useState('BTCUSDT');
  const [insightsSymbols, setInsightsSymbols] = useState([]);

  useEffect(() => {
    fetch(`${API}/api/exchange/labs/symbols`)
      .then(r => r.json())
      .then(d => setInsightsSymbols(d.symbols || []))
      .catch(() => {});
  }, [API]);

  const resolveState = () => {
    let tab = searchParams.get('tab') || 'overview';
    let sub = searchParams.get('sub') || null;

    if (LEGACY_MAP[tab]) {
      const mapped = LEGACY_MAP[tab];
      tab = mapped.tab;
      sub = mapped.sub || sub;
    }
    if (!TABS.find(t => t.id === tab)) tab = 'overview';
    if (tab === 'insights' && !sub) sub = 'labs';
    if (tab === 'engine' && !sub) sub = 'core';
    return { tab, sub };
  };

  const { tab: activeTab, sub: activeSub } = resolveState();

  const setTab = (tabId) => {
    const newParams = { tab: tabId };
    if (tabId === 'insights') newParams.sub = 'labs';
    else if (tabId === 'engine') newParams.sub = 'core';
    setSearchParams(newParams, { replace: true });
  };

  const setSub = (subId) => {
    setSearchParams({ tab: activeTab, sub: subId }, { replace: true });
  };

  const handleInsightsSymbolSelect = (sym) => {
    setInsightsSymbol(sym);
    setInsightsMode('asset');
  };

  const getComponent = () => {
    if (activeTab === 'insights') return TAB_COMPONENTS[`insights:${activeSub}`];
    if (activeTab === 'engine') return TAB_COMPONENTS[`engine:${activeSub}`];
    return TAB_COMPONENTS[activeTab];
  };

  const ActiveComponent = getComponent() || ExchangeOverviewPage;

  const insightsProps = activeTab === 'insights' ? {
    externalMode: insightsMode,
    externalSymbol: insightsSymbol,
  } : {};

  return (
    <div className="flex flex-col h-full bg-white" data-testid="exchange-page">
      {/* Header */}
      <div className="shrink-0 border-b border-gray-200 bg-white h-[71px]">
        <div className="px-6 h-full flex items-center">
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-3">
              <BarChart3 className="w-5 h-5 text-gray-400" />
              <div>
                <h1 className="text-xl font-bold text-gray-900" data-testid="exchange-title">Exchange Intelligence</h1>
                <p className="text-sm text-gray-500">Market analytics & signals</p>
              </div>
            </div>

            <div className="flex items-center gap-1" data-testid="exchange-tabs">
              {TABS.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                return (
                  <button key={tab.id} onClick={() => setTab(tab.id)}
                    data-testid={`exchange-tab-${tab.id}`}
                    className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      isActive ? 'bg-gray-900 text-white' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                    }`}>
                    <Icon className="w-4 h-4" />
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Insights bar */}
        {activeTab === 'insights' && (
          <InsightsBar
            activeSub={activeSub}
            onSubChange={setSub}
            mode={insightsMode}
            onModeChange={setInsightsMode}
            symbol={insightsSymbol}
            symbols={insightsSymbols}
            onSymbolSelect={handleInsightsSymbolSelect}
          />
        )}

        {/* Engine bar */}
        {activeTab === 'engine' && (
          <EngineBar activeSub={activeSub} onSubChange={setSub} />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        <Suspense fallback={<LoadingFallback />}>
          <ActiveComponent {...insightsProps} />
        </Suspense>
      </div>
    </div>
  );
}
