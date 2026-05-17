/**
 * Feed Combined Page — Feed + Twitter AI + Account Setup under one roof
 * Left tabs: "Twitter Sentiment" | "Twitter AI"
 * Right: "Account Setup" — opens parser integration page inline
 */
import React, { useState, Suspense, lazy } from 'react';
import { AtSign, Sparkles, Loader2, UserPlus, ArrowLeft } from 'lucide-react';
import TwitterIntegrationPage from '../dashboard/twitter/TwitterIntegrationPage';

const TwitterSentimentPage = lazy(() => import('../TwitterSentimentPage'));
const TwitterAIPage = lazy(() => import('../TwitterAIPage'));

const SUB_TABS = [
  { id: 'feed', label: 'Twitter Sentiment', icon: AtSign },
  { id: 'twitter-ai', label: 'Twitter AI', icon: Sparkles },
];

export default function FeedCombinedPage() {
  const [active, setActive] = useState('feed');
  const [showSetup, setShowSetup] = useState(false);

  return (
    <div data-testid="feed-combined-page">
      {/* Sub-tab bar */}
      <div className="sticky top-[73px] z-10 bg-white/80 backdrop-blur-xl border-b border-gray-100">
        <div className="max-w-[1600px] mx-auto px-6">
          <div className="flex items-center justify-between py-2">
            {/* Left: sub-tabs */}
            <div className="flex items-center gap-1">
              {showSetup && (
                <button
                  onClick={() => setShowSetup(false)}
                  data-testid="back-to-feed-btn"
                  className="flex items-center gap-1 px-3 py-2 text-xs font-medium text-gray-500 hover:text-gray-800 rounded-lg transition-colors mr-1"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  Back
                </button>
              )}
              {SUB_TABS.map(tab => {
                const Icon = tab.icon;
                const isActive = !showSetup && active === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => { setActive(tab.id); setShowSetup(false); }}
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

            {/* Right: Account Setup */}
            <button
              onClick={() => setShowSetup(true)}
              data-testid="account-setup-btn"
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                showSetup
                  ? 'bg-gray-900 text-white'
                  : 'text-gray-400 hover:text-gray-600'
              }`}
            >
              <UserPlus className="w-4 h-4" />
              Account Setup
            </button>
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
        {showSetup ? (
          <TwitterIntegrationPage forceStep={1} />
        ) : (
          <>
            {active === 'feed' && <TwitterSentimentPage />}
            {active === 'twitter-ai' && <TwitterAIPage />}
          </>
        )}
      </Suspense>
    </div>
  );
}
