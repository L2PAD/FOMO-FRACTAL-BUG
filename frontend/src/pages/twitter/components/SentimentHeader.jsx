/**
 * SentimentHeader — Persistent top nav for the Sentiment module
 * Reused in TwitterPage and all detail pages (InfluencerDetail, etc.)
 * so the header never disappears when navigating between sub-routes.
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity, Rss, Users, Network, TrendingUp,
  BarChart3, Share2, Newspaper, Flame
} from 'lucide-react';
import TwitterAlertsPanel from './TwitterAlertsPanel';

const TABS = [
  { id: 'overview', label: 'Overview', icon: Activity },
  { id: 'prediction', label: 'Prediction', icon: BarChart3 },
  { id: 'feed', label: 'Feed', icon: Rss },
  { id: 'actors', label: 'Actors', icon: Users },
  { id: 'graph', label: 'Graph', icon: Share2 },
  { id: 'network', label: 'Network', icon: Network },
  { id: 'market', label: 'Market', icon: TrendingUp },
  { id: 'credibility', label: 'Backers', icon: Users },
  { id: 'news', label: 'News', icon: Newspaper },
];

export default function SentimentHeader({ activeTab = 'overview', onTabChange }) {
  const navigate = useNavigate();

  const handleTab = (tabId) => {
    if (onTabChange) {
      onTabChange(tabId);
    } else {
      const url = tabId === 'overview' ? '/twitter' : `/twitter?tab=${tabId}`;
      navigate(url);
    }
  };

  return (
    <div className="border-b border-gray-200 bg-white/80 backdrop-blur-xl sticky top-0 z-30" data-testid="sentiment-header">
      <div className="max-w-[1600px] mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity className="w-6 h-6 text-gray-400" />
            <div>
              <h1 className="text-xl font-bold text-gray-900">Sentiment</h1>
              <p className="text-sm text-gray-500">Social signal & market sentiment analysis</p>
            </div>
            <TwitterAlertsPanel />
          </div>

          <div className="flex items-center gap-1">
            {TABS.map(tab => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => handleTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-gray-900 text-white'
                      : 'text-gray-400 hover:text-gray-700'
                  }`}
                  data-testid={`tab-${tab.id}`}
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
  );
}
