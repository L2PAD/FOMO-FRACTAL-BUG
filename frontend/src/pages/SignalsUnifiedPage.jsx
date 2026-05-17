/**
 * Unified Signals Page — Tab-based view for all signal versions
 * 
 * V1.0: On-chain Whale/Exchange/Fund activity signals
 * D1:   Structural alerts from graph layer (corridors, density, regime changes)
 * 
 * Architecture audit result: V1.0 was hidden when SignalsPageD1 replaced it in App.js
 * This page restores both versions under a unified tab interface.
 */
import { useState, lazy, Suspense } from 'react';
import { Activity, Waypoints, Info } from 'lucide-react';

// Lazy load both signal page versions
const SignalsV1 = lazy(() => import('./SignalsPage'));
const SignalsD1 = lazy(() => import('./SignalsPageD1'));

const TAB_CONFIG = [
  {
    id: 'v1',
    label: 'V1.0 — On-Chain',
    icon: Activity,
    description: 'Whale, Exchange, Fund activity signals',
    badge: 'LEGACY',
    badgeColor: 'bg-amber-100 text-amber-700',
  },
  {
    id: 'd1',
    label: 'D1 — Structural',
    icon: Waypoints,
    description: 'Graph-based structural alerts + Telegram',
    badge: 'CURRENT',
    badgeColor: 'bg-emerald-100 text-emerald-700',
  },
];

function TabLoader() {
  return (
    <div className="flex items-center justify-center py-24">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-3 border-slate-200 border-t-slate-700 rounded-full animate-spin" />
        <span className="text-sm text-slate-500">Loading signals...</span>
      </div>
    </div>
  );
}

export default function SignalsUnifiedPage() {
  const [activeTab, setActiveTab] = useState('d1');

  return (
    <div className="min-h-screen bg-slate-50" data-testid="signals-unified-page">
      {/* Header with version tabs */}
      <div className="bg-white border-b border-slate-200">
        <div className="px-6 pt-4 pb-0">
          {/* Title row */}
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-xl font-bold text-slate-900">Signal Engine</h1>
              <p className="text-sm text-slate-500 mt-0.5">
                All signal versions in one view
              </p>
            </div>
            
            {/* Architecture info chip */}
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-500">
              <Info className="w-3.5 h-3.5" />
              <span>2 signal engines available</span>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-0" data-testid="signal-version-tabs">
            {TAB_CONFIG.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  data-testid={`signal-tab-${tab.id}`}
                  className={`
                    relative flex items-center gap-2.5 px-5 py-3 text-sm font-medium transition-all
                    border-b-2
                    ${isActive
                      ? 'border-slate-900 text-slate-900'
                      : 'border-transparent text-slate-400 hover:text-slate-600 hover:border-slate-300'
                    }
                  `}
                >
                  <Icon className="w-4 h-4" />
                  <span>{tab.label}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${tab.badgeColor}`}>
                    {tab.badge}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Tab description bar */}
      <div className="px-6 py-2 bg-slate-100/80 border-b border-slate-200">
        <p className="text-xs text-slate-500">
          {TAB_CONFIG.find(t => t.id === activeTab)?.description}
        </p>
      </div>

      {/* Content */}
      <Suspense fallback={<TabLoader />}>
        <div className={activeTab === 'v1' ? 'block' : 'hidden'}>
          <SignalsV1 layoutMode="embedded" />
        </div>
        <div className={activeTab === 'd1' ? 'block' : 'hidden'}>
          <SignalsD1 layoutMode="embedded" />
        </div>
      </Suspense>
    </div>
  );
}
