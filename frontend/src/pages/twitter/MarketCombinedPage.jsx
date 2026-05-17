/**
 * Market Combined Page — Altseason + Lifecycle + Narratives
 */
import React, { useState, Suspense, lazy } from 'react';
import { Flame, RotateCcw, Hash, Loader2 } from 'lucide-react';

const AltSeasonPage = lazy(() => import('../connections/AltSeasonPage'));
const LifecyclePage = lazy(() => import('../connections/LifecyclePage'));
const NarrativesPage = lazy(() => import('../connections/NarrativesPage'));

const SUB_TABS = [
  { id: 'altseason', label: 'Altseason', icon: Flame },
  { id: 'lifecycle', label: 'Lifecycle', icon: RotateCcw },
  { id: 'narratives', label: 'Narratives', icon: Hash },
];

export default function MarketCombinedPage() {
  const [active, setActive] = useState('altseason');

  return (
    <div data-testid="market-combined-page">
      <div className="sticky top-[73px] z-10 bg-white/80 backdrop-blur-xl border-b border-gray-100">
        <div className="max-w-[1600px] mx-auto px-6">
          <div className="flex items-center gap-1 py-2">
            {SUB_TABS.map(tab => {
              const Icon = tab.icon;
              const isActive = active === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActive(tab.id)}
                  data-testid={`subtab-${tab.id}`}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    isActive ? 'bg-gray-900 text-white' : 'text-gray-400 hover:text-gray-600'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>
      <Suspense fallback={<div className="flex items-center justify-center py-20"><Loader2 className="w-5 h-5 animate-spin text-gray-400" /></div>}>
        {active === 'altseason' && <AltSeasonPage />}
        {active === 'lifecycle' && <LifecyclePage />}
        {active === 'narratives' && <NarrativesPage />}
      </Suspense>
    </div>
  );
}
