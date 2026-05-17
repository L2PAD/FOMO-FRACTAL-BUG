/**
 * Trading Terminal — unified single-page workspace (PHASE 7.1).
 *
 *   ┌───────── Trading Terminal (single header) ──────────────────────────┐
 *   │  Icon + Title + Subtitle                                             │
 *   │                                                                      │
 *   │  [Analysis] [Action] [Prediction] [Ideas]  │  [Trade] [Positions]    │
 *   │                                              [Decisions] [Analytics] │
 *   └──────────────────────────────────────────────────────────────────────┘
 *   │                                                                      │
 *   │                      Full-page body (one active tab)                 │
 *   │                                                                      │
 *   └──────────────────────────────────────────────────────────────────────┘
 *
 * Design notes:
 *   • ONE unified header. 8 tabs split 4 | 4 by a thin vertical divider.
 *   • ONE full-width body (not a side-by-side split).
 *   • Both MarketProvider (Tech Analysis) and TerminalProvider (Trading)
 *     wrap the whole shell so tab switching is instantaneous and each
 *     workspace keeps its own context alive.
 *   • No existing component was rewritten — we reuse the views/workspaces
 *     and deliberately skip their own sub-headers (they don't render one
 *     themselves; the only one that did — TerminalModuleHeader — is
 *     bypassed because we render workspaces directly).
 */
import React, { useState, useCallback } from 'react';
import {
  Activity,
  BarChart2,
  Sparkles,
  Bookmark,
  Target,
  TrendingUp,
  GitBranch,
  Terminal as TerminalIcon,
} from 'lucide-react';

import { MarketProvider, useMarket } from '../../store/marketStore';
import { TerminalProvider } from '../../store/terminalStore';
import setupService from '../../services/setupService';

// Tech Analysis views
import ResearchView from '../../modules/cockpit/views/ResearchViewNew';
import IdeasView from '../../modules/cockpit/views/IdeasView';
import TAPredictionTab from '../../modules/cockpit/views/TAPredictionTab';

// Trading workspaces
import TradeWorkspace from '../../components/terminal/workspaces/TradeWorkspace';
import PositionsWorkspace from '../../components/terminal/workspaces/PositionsWorkspace';
import DecisionsWorkspace from '../../components/terminal/workspaces/DecisionsWorkspace';
import AnalyticsWorkspace from '../../components/terminal/workspaces/AnalyticsWorkspace';

// ════════════════════════════════════════════════════════════════════════
// TAB DEFINITIONS
// ════════════════════════════════════════════════════════════════════════
const LEFT_TABS = [
  { id: 'analysis',   label: 'Analysis',   icon: BarChart2, title: 'What is happening' },
  { id: 'action',     label: 'Action',     icon: Activity,  title: 'What to do' },
  { id: 'prediction', label: 'Prediction', icon: Sparkles,  title: 'TA forecasts' },
  { id: 'ideas',      label: 'Ideas',      icon: Bookmark,  title: 'Saved ideas' },
];

const RIGHT_TABS = [
  { id: 'trade',      label: 'Trade',      icon: Activity,   title: 'Execute' },
  { id: 'positions',  label: 'Positions',  icon: TrendingUp, title: 'Open positions' },
  { id: 'decisions',  label: 'Decisions',  icon: GitBranch,  title: 'Decision history' },
  { id: 'analytics',  label: 'Performance', icon: Target,    title: 'Realised performance & stats' },
];

const ALL_TAB_IDS = [...LEFT_TABS.map(t => t.id), ...RIGHT_TABS.map(t => t.id)];

// ════════════════════════════════════════════════════════════════════════
// TAB BUTTON
// ════════════════════════════════════════════════════════════════════════
function TabButton({ tab, active, onClick }) {
  const Icon = tab.icon;
  return (
    <button
      type="button"
      onClick={onClick}
      title={tab.title}
      data-testid={`tab-${tab.id}`}
      className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-[13px] font-semibold transition-colors ${
        active
          ? 'bg-[#0f172a] text-white shadow-sm'
          : 'text-[#475569] hover:bg-[#f1f5f9] hover:text-[#0f172a]'
      }`}
      style={{ border: 'none', cursor: 'pointer' }}
    >
      <Icon className="w-[14px] h-[14px]" strokeWidth={1.75} />
      <span>{tab.label}</span>
    </button>
  );
}

// ════════════════════════════════════════════════════════════════════════
// INNER CONTENT (runs inside both providers)
// ════════════════════════════════════════════════════════════════════════
function TerminalContent() {
  const [activeTab, setActiveTab] = useState('analysis');
  const { symbol, timeframe } = useMarket();

  // Save-idea toast plumbing (from legacy TechAnalysisModule, kept working)
  const [savingIdea, setSavingIdea] = useState(false);
  const [ideaToast, setIdeaToast] = useState(null);

  // eslint-disable-next-line no-unused-vars
  const handleSaveIdea = useCallback(async () => {
    if (savingIdea) return;
    try {
      setSavingIdea(true);
      const result = await setupService.createIdea(symbol, timeframe || '4H');
      if (result.ok) {
        setIdeaToast(`Idea saved: ${result.idea.idea_id}`);
        setTimeout(() => setIdeaToast(null), 3000);
      }
    } catch (err) {
      console.error('Failed to save idea:', err);
      setIdeaToast('Failed to save idea');
      setTimeout(() => setIdeaToast(null), 3000);
    } finally {
      setSavingIdea(false);
    }
  }, [symbol, timeframe, savingIdea]);

  // Unsafe fallback if a bad tab id is somehow stored.
  const safeTab = ALL_TAB_IDS.includes(activeTab) ? activeTab : 'analysis';

  const renderBody = () => {
    switch (safeTab) {
      case 'analysis':
      case 'action':
        return <ResearchView activeMode={safeTab} />;
      case 'prediction':
        return <TAPredictionTab />;
      case 'ideas':
        return (
          <IdeasView
            onNavigateToChart={() => setActiveTab('analysis')}
          />
        );
      case 'trade':
        return <TradeWorkspace />;
      case 'positions':
        return <PositionsWorkspace />;
      case 'decisions':
        return <DecisionsWorkspace />;
      case 'analytics':
        return <AnalyticsWorkspace />;
      default:
        return <ResearchView activeMode="analysis" />;
    }
  };

  return (
    <div
      className="w-full h-full min-h-screen flex flex-col bg-[#f5f7fa] text-[#0f172a] terminal-scope"
      style={{ fontFamily: 'Gilroy, sans-serif' }}
      data-testid="terminal-workspace"
    >
      {/* ────────── UNIFIED HEADER ────────── */}
      <div
        className="shrink-0 bg-white border-b border-[#eef1f5] px-6 py-3 flex items-center justify-between gap-4"
        data-testid="terminal-header"
      >
        {/* Brand */}
        <div className="flex items-center gap-3 min-w-0">
          <TerminalIcon className="w-7 h-7 text-[#05A584] shrink-0" strokeWidth={1.75} />
          <div className="flex flex-col leading-tight min-w-0">
            <h1 className="text-[17px] font-bold text-[#0f172a] m-0 truncate">
              Trading Terminal
            </h1>
            <span className="text-[11px] text-[#94a3b8] mt-0.5 truncate">
              Analysis &amp; execution · single workspace
            </span>
          </div>
        </div>

        {/* Tabs — 4 | 4 with a thin vertical divider */}
        <nav
          className="flex items-center gap-1 flex-wrap justify-end"
          data-testid="terminal-tabs"
          aria-label="Workspace tabs"
        >
          {LEFT_TABS.map((tab) => (
            <TabButton
              key={tab.id}
              tab={tab}
              active={safeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
            />
          ))}

          {/* Divider between Analysis-zone and Execution-zone */}
          <div
            className="mx-2 h-6 w-px bg-[#e2e8f0]"
            aria-hidden="true"
            data-testid="terminal-tab-divider"
          />

          {RIGHT_TABS.map((tab) => (
            <TabButton
              key={tab.id}
              tab={tab}
              active={safeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
            />
          ))}
        </nav>
      </div>

      {/* ────────── FULL-WIDTH BODY ────────── */}
      <div
        className="flex-1 min-h-0 overflow-y-auto"
        data-testid="terminal-body"
      >
        {renderBody()}
      </div>

      {/* Toast */}
      {ideaToast && (
        <div
          className="fixed top-[84px] right-6 bg-[#0f172a] text-white px-4 py-2.5 rounded-lg text-[13px] shadow-lg z-[1000]"
          data-testid="terminal-toast"
        >
          {ideaToast}
        </div>
      )}
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════
// EXPORTED SHELL — wraps both stores
// ════════════════════════════════════════════════════════════════════════
export default function TerminalWorkspace() {
  return (
    <MarketProvider>
      <TerminalProvider>
        <TerminalContent />
      </TerminalProvider>
    </MarketProvider>
  );
}
