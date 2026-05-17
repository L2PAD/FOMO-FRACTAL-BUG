/**
 * Actors Combined Page — Influencers + Radar under one roof
 * Sub-tabs: "Influencers" | "Radar"
 */
import React, { useState, Suspense, lazy } from 'react';
import { Users, Radio, Loader2 } from 'lucide-react';

const ConnectionsInfluencersPage = lazy(() => import('../connections/ConnectionsInfluencersPage'));
const ConnectionsEarlySignalPage = lazy(() => import('../connections/ConnectionsEarlySignalPage'));

const SUB_TABS = [
  { id: 'influencers', label: 'Influencers', icon: Users },
  { id: 'radar', label: 'Radar', icon: Radio },
];

export default function ActorsCombinedPage() {
  const [active, setActive] = useState('influencers');

  return (
    <div data-testid="actors-combined-page">
      {/* Sub-tab bar */}
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
                    isActive
                      ? 'bg-gray-900 text-white'
                      : 'text-gray-400 hover:text-gray-600'
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

      {/* Content */}
      <Suspense
        fallback={
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
          </div>
        }
      >
        {active === 'influencers' && <ConnectionsInfluencersPage />}
        {active === 'radar' && <ConnectionsEarlySignalPage />}
      </Suspense>
    </div>
  );
}
