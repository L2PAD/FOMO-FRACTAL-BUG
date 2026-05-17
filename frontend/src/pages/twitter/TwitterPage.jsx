/**
 * Sentiment — Main Page
 * ==================================================
 * Header styled like OnChain: dark pill for active, plain text for inactive.
 * All groups use combined pages with internal sub-tabs.
 */

import React, { useState, useEffect, Suspense, lazy } from 'react';
import { Loader2 } from 'lucide-react';
import SentimentHeader from './components/SentimentHeader';

// Lazy-load combined tab pages
const TwitterOverviewPage = lazy(() => import('./TwitterOverviewPage'));
const FeedCombinedPage = lazy(() => import('./FeedCombinedPage'));
const ActorsCombinedPage = lazy(() => import('./ActorsCombinedPage'));
const NetworkCombinedPage = lazy(() => import('./NetworkCombinedPage'));
const MarketCombinedPage = lazy(() => import('./MarketCombinedPage'));
const CredibilityCombinedPage = lazy(() => import('./CredibilityCombinedPage'));
const ParserWrapper = lazy(() => import('./TwitterParserWrapper'));
const EntityGraphTab = lazy(() => import('./EntityGraphTab'));
const NewsTab = lazy(() => import('./NewsTab'));
const PredictionTab = lazy(() => import('./PredictionTab'));

const TAB_IDS = ['overview', 'prediction', 'feed', 'actors', 'graph', 'network', 'market', 'credibility', 'news'];

// Backward compat redirects
const REDIRECTS = {
  'sentiment-ai': 'feed',
  'influencers': 'actors',
  'radar': 'actors',
  'clusters': 'network',
  'bot-detection': 'network',
  'altseason': 'market',
  'lifecycle': 'market',
  'narratives': 'market',
  'reality': 'credibility',
  'backers': 'credibility',
};

const ALL_VALID = [...TAB_IDS, ...Object.keys(REDIRECTS), 'parser', 'accounts'];

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

export default function TwitterPage() {
  const getTabFromUrl = () => {
    const params = new URLSearchParams(window.location.search);
    const tab = params.get('tab');
    if (REDIRECTS[tab]) return REDIRECTS[tab];
    return ALL_VALID.includes(tab) ? tab : 'overview';
  };

  const [activeTab, setActiveTab] = useState(getTabFromUrl);

  useEffect(() => {
    const handlePop = () => setActiveTab(getTabFromUrl());
    window.addEventListener('popstate', handlePop);
    return () => window.removeEventListener('popstate', handlePop);
  }, []);

  const changeTab = (tabId) => {
    setActiveTab(tabId);
    const params = new URLSearchParams(window.location.search);
    if (tabId === 'overview') params.delete('tab');
    else params.set('tab', tabId);
    const url = params.toString() ? `${window.location.pathname}?${params}` : window.location.pathname;
    window.history.pushState({}, '', url);
  };

  return (
    <div className="min-h-screen bg-gray-50/50">
      {/* Header — shared persistent component */}
      <SentimentHeader activeTab={activeTab} onTabChange={changeTab} />

      {/* Content */}
      <div className="">
        <Suspense fallback={<TabLoadingFallback />}>
          {activeTab === 'overview' && <TwitterOverviewPage />}
          {activeTab === 'prediction' && <PredictionTab />}
          {activeTab === 'feed' && <FeedCombinedPage />}
          {activeTab === 'actors' && <ActorsCombinedPage />}
          {activeTab === 'graph' && <EntityGraphTab />}
          {activeTab === 'network' && <NetworkCombinedPage />}
          {activeTab === 'market' && <MarketCombinedPage />}
          {activeTab === 'credibility' && <CredibilityCombinedPage />}
          {activeTab === 'parser' && <ParserWrapper />}
          {activeTab === 'accounts' && <ParserWrapper />}
          {activeTab === 'news' && <NewsTab />}
        </Suspense>
      </div>
    </div>
  );
}
