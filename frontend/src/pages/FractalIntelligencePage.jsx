/**
 * Fractal Intelligence — Main Page
 * =================================
 * 
 * Single entry point for all Fractal analytics.
 * Internal header with tabs (like Exchange/Twitter pattern).
 * 
 * Tabs: Overview | Bitcoin | SPX | DXY | Macro Brain
 * URL: /fractal?tab=overview|btc|spx|dxy|brain
 */

import React from 'react';
import { useSearchParams, useLocation } from 'react-router-dom';
import {
  Triangle, Eye, TrendingUp, BarChart3, DollarSign, Brain, Loader2
} from 'lucide-react';

// Eagerly import tab pages — React 19 has known nested Suspense+lazy bugs
import OverviewPage from './OverviewPage';
import BtcFractalPage from './BtcFractalPage';
import SpxFractalPage from './SpxFractalPage';
import DxyFractalPage from './DxyFractalPage';
import BrainOverviewPage from './BrainOverviewPageV4';

const TABS = [
  { id: 'overview', label: 'Overview', icon: Eye },
  { id: 'btc', label: 'Bitcoin', icon: TrendingUp },
  { id: 'spx', label: 'SPX', icon: BarChart3 },
  { id: 'dxy', label: 'DXY', icon: DollarSign },
  { id: 'brain', label: 'Macro Brain', icon: Brain },
];

const TAB_COMPONENTS = {
  'overview': OverviewPage,
  'btc': BtcFractalPage,
  'spx': SpxFractalPage,
  'dxy': DxyFractalPage,
  'brain': BrainOverviewPage,
};

function LoadingFallback() {
  return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
    </div>
  );
}

// Map legacy paths to tab IDs
const PATH_TO_TAB = {
  '/fractal/btc': 'btc',
  '/fractal/spx': 'spx',
  '/fractal/dxy': 'dxy',
  '/brain': 'brain',
  '/overview': 'overview',
  '/fractal/overview': 'overview',
  '/bitcoin': 'btc',
};

export default function FractalIntelligencePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();

  // Resolve tab: URL param > legacy path > default
  const resolveTab = () => {
    const paramTab = searchParams.get('tab');
    if (paramTab && TAB_COMPONENTS[paramTab]) return paramTab;
    const pathTab = PATH_TO_TAB[location.pathname];
    if (pathTab) return pathTab;
    return 'overview';
  };

  const activeTab = resolveTab();

  const setTab = (tabId) => {
    setSearchParams({ tab: tabId }, { replace: true });
  };

  const ActiveComponent = TAB_COMPONENTS[activeTab] || OverviewPage;

  return (
    <div className="flex flex-col h-full bg-white" data-testid="fractal-page">
      {/* Header — matches Exchange/Twitter pattern exactly */}
      <div className="shrink-0 border-b border-gray-200 bg-white h-[71px]">
        <div className="px-6 h-full flex items-center">
          <div className="flex items-center justify-between w-full">
            {/* Title */}
            <div className="flex items-center gap-3">
              <Triangle className="w-5 h-5 text-gray-400" />
              <div>
                <h1 className="text-xl font-bold text-gray-900" data-testid="fractal-title">Fractal Intelligence</h1>
                <p className="text-sm text-gray-500">Historical pattern analysis engine</p>
              </div>
            </div>

            {/* Tabs — pill style like Exchange/Twitter */}
            <div className="flex items-center gap-1" data-testid="fractal-tabs">
              {TABS.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setTab(tab.id)}
                    data-testid={`fractal-tab-${tab.id}`}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      isActive
                        ? 'bg-gray-900 text-white'
                        : 'text-gray-500 hover:text-gray-900'
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
      </div>

      {/* Tab content — scrollable */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        <ActiveComponent />
      </div>
    </div>
  );
}
