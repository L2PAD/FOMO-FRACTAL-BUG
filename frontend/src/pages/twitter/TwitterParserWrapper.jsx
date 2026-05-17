/**
 * Twitter Parser Wrapper
 * 
 * Wraps ParserOverviewPage inside Twitter Intelligence module.
 * Adds: 
 * - "Setup Account" button (navigates to accounts tab)
 * - Check if parser is configured, if not → show setup prompt
 */

import React, { useState, useEffect, Suspense, lazy } from 'react';
import { Settings, UserPlus, Loader2, ChevronRight } from 'lucide-react';
import { getIntegrationStatus } from '../../api/twitterIntegration.api';

const ParserOverviewPage = lazy(() => import('../dashboard/parser/ParserOverviewPage'));
const TwitterIntegrationPage = lazy(() => import('../dashboard/twitter/TwitterIntegrationPage'));

export default function TwitterParserWrapper() {
  const [hasSession, setHasSession] = useState(null); // null = loading, true/false
  const [showAccounts, setShowAccounts] = useState(false);

  useEffect(() => {
    // Check if Twitter session is configured via the same API as TwitterIntegrationPage
    getIntegrationStatus()
      .then(d => {
        const sessions = d?.sessions || d?.data?.sessions || { ok: 0, stale: 0 };
        const totalSessions = (sessions.ok || 0) + (sessions.stale || 0);
        const consentAccepted = d?.details?.consentAccepted || d?.data?.details?.consentAccepted;
        setHasSession(consentAccepted && totalSessions > 0);
      })
      .catch(() => setHasSession(false));
  }, []);

  // New user → show setup prompt
  if (hasSession === false && !showAccounts) {
    return (
      <div className="p-6 max-w-2xl mx-auto" data-testid="parser-setup-prompt">
        <div className="bg-white border border-gray-200 rounded-2xl p-8 text-center shadow-sm">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-cyan-600 flex items-center justify-center mx-auto mb-4">
            <Settings className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">Setup Parser First</h2>
          <p className="text-sm text-gray-500 mb-6 max-w-md mx-auto">
            To start parsing Twitter data, you need to connect your account first. 
            This is a one-time secure setup.
          </p>
          <button
            onClick={() => setShowAccounts(true)}
            className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-medium transition-colors"
          >
            <UserPlus className="w-4 h-4" />
            Setup Account
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  // Show accounts setup page
  if (showAccounts) {
    return (
      <div data-testid="parser-accounts-setup">
        <div className="max-w-[1400px] mx-auto px-4 pt-3">
          <button
            onClick={() => setShowAccounts(false)}
            className="text-xs text-blue-500 hover:text-blue-600 font-medium mb-2 flex items-center gap-1"
          >
            ← Back to Parser
          </button>
        </div>
        <Suspense fallback={<div className="flex justify-center py-20"><Loader2 className="w-5 h-5 animate-spin text-gray-400" /></div>}>
          <TwitterIntegrationPage forceStep={1} />
        </Suspense>
      </div>
    );
  }

  // Main parser with Account button
  return (
    <div data-testid="parser-page">
      {/* Parser toolbar */}
      <div className="max-w-[1400px] mx-auto px-4 pt-3 flex items-center justify-end gap-2">
        <button
          onClick={() => setShowAccounts(true)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-xs font-medium transition-colors"
        >
          <UserPlus className="w-3.5 h-3.5" />
          Account Setup
        </button>
      </div>
      <Suspense fallback={<div className="flex justify-center py-20"><Loader2 className="w-5 h-5 animate-spin text-gray-400" /></div>}>
        <ParserOverviewPage />
      </Suspense>
    </div>
  );
}
