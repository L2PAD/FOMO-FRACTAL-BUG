/**
 * Network Combined Page — Clusters + Bot Detection
 */
import React, { useState, Suspense, lazy } from 'react';
import { Layers, ShieldAlert, Loader2 } from 'lucide-react';

const ClusterAttentionPage = lazy(() => import('../connections/ClusterAttentionPage'));
const FarmNetworkPage = lazy(() => import('../connections/FarmNetworkPage'));

const SUB_TABS = [
  { id: 'clusters', label: 'Clusters', icon: Layers },
  { id: 'bot-detection', label: 'Bot Detection', icon: ShieldAlert },
];

export default function NetworkCombinedPage() {
  const [active, setActive] = useState('clusters');

  return (
    <div data-testid="network-combined-page">
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
        {active === 'clusters' && <ClusterAttentionPage />}
        {active === 'bot-detection' && <FarmNetworkPage />}
      </Suspense>
    </div>
  );
}
