/**
 * On-chain v3 — Main Page
 * ========================
 * 
 * 2-Level Navigation Architecture:
 * 
 * Level 1 (Sections):
 *   Overview | Market | Intelligence | Monitoring | [OS]
 * 
 * Level 2 (Sub-tabs per section):
 *   Market: Signals | Smart Money | CEX Flow | Token Intelligence | Wallet | Entities
 *   Intelligence: Graph | Engine
 *   Monitoring: Alerts | Timeline
 * 
 * URL Params:
 * ?tab=signals|assets|actors|entities|graph|cex-flow|engine|alerts|os
 * ?token=LINK (for Assets)
 * ?entity=0x... (for Signals/Actors)
 */

import React, { useEffect, useState, Suspense, lazy } from 'react';
import {
  Activity, Radio, Coins, Users, Building, Wallet, Network, Loader2,
  Shield, Building2, Link2, Zap, Cpu, BarChart3, Brain, Clock,
} from 'lucide-react';
import { OverviewTab } from './tabs/OverviewTab';
import { SignalsTerminal } from './tabs/SignalsTerminal';
import { TokenIntelligenceTab } from './tabs/assets/TokenIntelligenceTab';
import { ActorsTab } from './tabs/ActorsTab';
import { SystemStatusStrip } from './components/SystemStatusStrip';
import { OnchainChainProvider } from './context/OnchainChainContext';
import { NetworkSelector } from './components/NetworkSelector';

// Lazy load tabs for better performance
const EntitiesTab = lazy(() => import('./tabs/EntitiesTab'));
const GraphLegacyTab = lazy(() => import('./tabs/GraphLegacyTab'));
const EngineTab = lazy(() => import('./tabs/EngineTab'));
const CexFlowTab = lazy(() => import('./tabs/CexFlowTab'));
const AlertsTab = lazy(() => import('./tabs/AlertsTab'));
const AlertRulesTab = lazy(() => import('./tabs/AlertRulesTab'));
const OSTab = lazy(() => import('./tabs/OSTab'));
const WalletSearchContent = lazy(() => import('./WalletSearchPage'));
const WalletProfileContent = lazy(() => import('./WalletPage'));

type TabId = 'overview' | 'signals' | 'assets' | 'actors' | 'engine' | 'cex-flow' | 'entities' | 'wallet' | 'graph' | 'alerts' | 'alert-rules' | 'os';

type SectionId = 'overview' | 'market' | 'intelligence' | 'engine-section' | 'monitoring' | 'os';

interface Section {
  id: SectionId;
  label: string;
  icon: React.ElementType;
  tabs: { id: TabId; label: string; icon: React.ElementType }[];
  standalone?: boolean;
}

const SECTIONS: Section[] = [
  {
    id: 'overview',
    label: 'Overview',
    icon: Activity,
    tabs: [{ id: 'overview', label: 'Overview', icon: Activity }],
    standalone: true,
  },
  {
    id: 'market',
    label: 'Market',
    icon: BarChart3,
    tabs: [
      { id: 'signals', label: 'Signals Terminal', icon: Radio },
      { id: 'actors', label: 'Smart Money', icon: Users },
      { id: 'cex-flow', label: 'CEX Flow', icon: Building2 },
      { id: 'assets', label: 'Token Intelligence', icon: Coins },
      { id: 'wallet', label: 'Wallet', icon: Wallet },
      { id: 'entities', label: 'Entities', icon: Building },
    ],
  },
  {
    id: 'intelligence',
    label: 'Graph',
    icon: Network,
    tabs: [{ id: 'graph', label: 'Graph', icon: Network }],
    standalone: true,
  },
  {
    id: 'engine-section',
    label: 'Engine',
    icon: Shield,
    tabs: [{ id: 'engine', label: 'Engine', icon: Shield }],
    standalone: true,
  },
  {
    id: 'monitoring',
    label: 'Monitoring',
    icon: Zap,
    tabs: [
      { id: 'alerts', label: 'Event Radar', icon: Radio },
      { id: 'alert-rules', label: 'Alert Rules', icon: Shield },
    ],
  },
  {
    id: 'os',
    label: 'OS',
    icon: Cpu,
    tabs: [{ id: 'os', label: 'OS', icon: Cpu }],
    standalone: true,
  },
];

// Map tab → section
const TAB_TO_SECTION: Record<TabId, SectionId> = {} as any;
SECTIONS.forEach(s => s.tabs.forEach(t => { TAB_TO_SECTION[t.id] = s.id; }));

function parseUrlQuery() {
  const params = new URLSearchParams(window.location.search);
  return {
    tab: params.get('tab'),
    token: params.get('token'),
    entity: params.get('entity'),
    wallet: params.get('wallet'),
  };
}

function buildUrl(overrides: Record<string, string | null>) {
  const params = new URLSearchParams(window.location.search);
  for (const [key, val] of Object.entries(overrides)) {
    if (val == null) params.delete(key);
    else params.set(key, val);
  }
  return `${window.location.pathname}?${params.toString()}`;
}

// Loading fallback for lazy tabs
function TabLoadingFallback() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="flex items-center gap-3 text-gray-400">
        <Loader2 className="w-5 h-5 animate-spin" />
        <span className="text-sm">Loading module...</span>
      </div>
    </div>
  );
}

export default function OnchainV3Page() {
  return (
    <OnchainChainProvider>
      <OnchainV3Content />
    </OnchainChainProvider>
  );
}

function OnchainV3Content() {
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [urlToken, setUrlToken] = useState<string | null>(null);
  const [urlEntity, setUrlEntity] = useState<string | null>(null);
  const [urlWallet, setUrlWallet] = useState<string | null>(null);

  const validTabs: TabId[] = ['overview', 'signals', 'assets', 'actors', 'engine', 'cex-flow', 'entities', 'wallet', 'graph', 'alerts', 'alert-rules', 'os'];

  // Parse URL on mount
  useEffect(() => {
    const q = parseUrlQuery();
    if (q.tab && validTabs.includes(q.tab as TabId)) {
      setActiveTab(q.tab as TabId);
    }
    if (q.token) setUrlToken(q.token);
    if (q.entity) setUrlEntity(q.entity);
    if (q.wallet) setUrlWallet(q.wallet);
  }, []);

  // Derived: active section
  const activeSection = TAB_TO_SECTION[activeTab] || 'overview';
  const currentSection = SECTIONS.find(s => s.id === activeSection)!;
  const showSubNav = currentSection && !currentSection.standalone && currentSection.tabs.length > 1;

  function changeTab(tab: TabId) {
    setActiveTab(tab);
    pushState({ tab });
  }

  function changeSection(section: SectionId) {
    const sec = SECTIONS.find(s => s.id === section)!;
    const firstTab = sec.tabs[0].id;
    changeTab(firstTab);
  }

  function pushState(overrides: Record<string, string | null>) {
    const url = buildUrl(overrides);
    window.history.pushState({}, '', url);
  }

  // Embedded navigation callbacks for legacy tabs
  const embeddedNav = {
    onOpenWallet: (addr: string) => {
      setUrlWallet(addr);
      setActiveTab('wallet');
      pushState({ tab: 'wallet', wallet: addr });
    },
    onOpenEntity: (entityId: string) => {
      setUrlEntity(entityId);
      setActiveTab('entities');
      pushState({ tab: 'entities', entity: entityId });
    },
    onOpenGraph: (address: string) => {
      setUrlWallet(address);
      setActiveTab('graph');
      pushState({ tab: 'graph', wallet: address });
    },
    onOpenToken: (token: string) => {
      setUrlToken(token);
      setActiveTab('assets');
      pushState({ tab: 'assets', token });
    },
    onOpenSignals: (entity: string) => {
      setUrlEntity(entity);
      setActiveTab('signals');
      pushState({ tab: 'signals', entity });
    },
  };

  // Navigation helper for tabs that support onNavigateTab
  const navigateTab = (tab: string, params?: Record<string, string>) => {
    const tabId = tab as TabId;
    if (validTabs.includes(tabId)) {
      setActiveTab(tabId);
      const token = params?.token || null;
      if (token) setUrlToken(token);
      pushState({ tab, token });
    }
  };

  return (
    <div className="flex flex-col h-full min-w-0 bg-gray-50/50">
      {/* Header — FIXED, never scrolls, isolated from content */}
      <div className="flex-shrink-0 min-w-0 overflow-visible bg-white border-b border-gray-200/60 z-20 h-[71px]">
        <div className="px-6 h-full flex items-center">
          <div className="flex items-center justify-between w-full">
            {/* Title */}
            <div className="flex items-center gap-3">
              <Link2 className="w-5 h-5 text-gray-400" />
              <div>
                <h1 className="text-xl font-bold text-gray-900">On-chain Intelligence</h1>
                <p className="text-sm text-gray-500">Whale flows & smart money tracking</p>
              </div>
              <div className="ml-2">
                <NetworkSelector />
              </div>
            </div>

            {/* Level 1: Section buttons */}
            <div className="flex items-center gap-1" data-testid="nav-sections">
              {SECTIONS.filter(s => s.id !== 'os').map(section => {
                const Icon = section.icon;
                const isActive = activeSection === section.id;
                return (
                  <button
                    key={section.id}
                    onClick={() => changeSection(section.id)}
                    className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg transition-all ${
                      isActive
                        ? 'bg-gray-900 text-white'
                        : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                    }`}
                    data-testid={`section-${section.id}`}
                  >
                    <Icon className="w-4 h-4" />
                    {section.label}
                  </button>
                );
              })}
              {/* OS — highlighted separate */}
              <div className="w-px h-6 bg-gray-200 mx-2" />
              <button
                onClick={() => changeSection('os')}
                className={`flex items-center gap-1.5 px-4 py-2 text-sm font-bold rounded-lg transition-all ${
                  activeSection === 'os'
                    ? 'bg-cyan-500 text-white'
                    : 'text-cyan-600 hover:bg-cyan-50 border border-cyan-200'
                }`}
                data-testid="section-os"
              >
                <Cpu className="w-4 h-4" />
                OS
              </button>
            </div>
          </div>
        </div>

        {/* Level 2: Sub-navigation */}
        {showSubNav && (
          <div className="border-t border-gray-100">
            <div className="px-6">
              <div className="flex items-center gap-1 py-1.5" data-testid="nav-subtabs">
                {currentSection.tabs.map(tab => {
                  const Icon = tab.icon;
                  const isActive = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => changeTab(tab.id)}
                      className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                        isActive
                          ? 'text-gray-900 bg-gray-100'
                          : 'text-gray-400 hover:text-gray-600 hover:bg-gray-50'
                      }`}
                      data-testid={`tab-${tab.id}`}
                    >
                      <Icon className="w-3.5 h-3.5" />
                      {tab.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Content — scrolls independently, completely isolated from header */}
      <div className="flex-1 min-h-0 min-w-0 overflow-y-auto overflow-x-hidden">
        <div className="px-6 py-6">
        {/* V2 Tabs */}
        {activeTab === 'overview' && <OverviewTab onNavigate={changeTab} />}
        {activeTab === 'signals' && (
          <SignalsTerminal />
        )}
        {activeTab === 'assets' && (
          <TokenIntelligenceTab onNavigateTab={navigateTab} />
        )}
        {activeTab === 'actors' && (
          <ActorsTab
            externalEntity={urlEntity}
            onEntityConsumed={() => {
              setUrlEntity(null);
              pushState({ entity: null });
            }}
            onOpenWallet={(addr: string) => {
              setUrlWallet(addr);
              setActiveTab('wallet');
              pushState({ tab: 'wallet', wallet: addr });
            }}
          />
        )}

        {/* Lazy-loaded V2 + Legacy tabs */}
        <Suspense fallback={<TabLoadingFallback />}>
          {activeTab === 'engine' && (
            <EngineTab onNavigateTab={navigateTab} />
          )}
          {activeTab === 'cex-flow' && (
            <CexFlowTab onNavigateTab={navigateTab} />
          )}
          {activeTab === 'alerts' && (
            <AlertsTab />
          )}
          {activeTab === 'alert-rules' && (
            <AlertRulesTab />
          )}
          {activeTab === 'os' && (
            <OSTab />
          )}
          {activeTab === 'entities' && (
            <EntitiesTab 
              nav={embeddedNav} 
              selectedEntity={urlEntity}
            />
          )}
          {activeTab === 'graph' && (
            <GraphLegacyTab 
              nav={embeddedNav} 
              selectedAddress={urlWallet}
            />
          )}
          {activeTab === 'wallet' && !urlWallet && (
            <WalletSearchContent onOpenWallet={(addr: string) => {
              setUrlWallet(addr);
              pushState({ tab: 'wallet', wallet: addr });
            }} />
          )}
          {activeTab === 'wallet' && urlWallet && (
            <WalletProfileContent walletAddress={urlWallet} onBack={() => {
              setUrlWallet(null);
              pushState({ tab: 'wallet', wallet: null });
            }} />
          )}
        </Suspense>
        </div>
      </div>
    </div>
  );
}
