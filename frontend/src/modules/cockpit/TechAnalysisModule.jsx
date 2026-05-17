import React, { useState, useCallback } from 'react';
import { Activity, BarChart2, Sparkles, Bookmark } from 'lucide-react';
import styled from 'styled-components';
import { MarketProvider, useMarket } from '../../store/marketStore';
import setupService from '../../services/setupService';

/**
 * Tech Analysis Module — INPUT layer of the system.
 *
 * PHASE 6.3 (2026-05-01) — user-zone surface trimmed by 1 tab.
 *
 *   ✔ Analysis    — "что происходит" (ResearchViewNew)
 *   ✔ Action      — "что делать" (ResearchViewNew, mode=action)
 *   ✔ Prediction  — TA rolling forecasts + horizons
 *   ✔ Ideas       — saved ideas tracker
 *
 * Cut from user-zone (lives ONLY in /admin/tech-analysis):
 *   ❌ Hypotheses — strategy lab / backtest bench (research/lab
 *                   surface — admin-only).
 *
 * Same pattern as previous cuts: file NOT deleted. Admin page still
 * imports HypothesesView directly, so nothing gets lost.
 */

// ════════════════════════════════════════════════════════════════════
// STYLED COMPONENTS — Sentiment-like header (kept lightweight)
// ════════════════════════════════════════════════════════════════════

const PageContainer = styled.div`
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - 64px);
  background: #f5f7fa;
`;

const ModuleHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: #ffffff;
  border-bottom: 1px solid #eef1f5;
`;

const ModuleTitle = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;

  .icon {
    width: 28px;
    height: 28px;
    color: #05A584;
  }

  .text {
    display: flex;
    flex-direction: column;

    h1 {
      margin: 0;
      font-size: 18px;
      font-weight: 700;
      color: #0f172a;
    }

    span.description {
      font-size: 12px;
      color: #64748b;
      margin-top: 2px;
    }
  }
`;

const NotificationBtn = styled.button.attrs({ type: 'button' })`
  /* Deprecated in Phase 7 — bell removed per UX directive. Styled-component
     kept to avoid ripping out exports; no JSX reference to it remains. */
  display: none;
`;

const TabsNav = styled.div`
  display: flex;
  align-items: center;
  gap: 4px;
`;

const TabButton = styled.button`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: none;
  border-radius: 8px;
  background: ${({ $active }) => ($active ? '#0f172a' : 'transparent')};
  color: ${({ $active }) => ($active ? '#ffffff' : '#475569')};
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;

  &:hover {
    background: ${({ $active }) => ($active ? '#0f172a' : '#f1f5f9')};
    color: ${({ $active }) => ($active ? '#ffffff' : '#0f172a')};
  }

  svg {
    width: 14px;
    height: 14px;
    stroke-width: 1.75;
  }
`;

const MainContent = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
`;

const Toast = styled.div`
  position: fixed;
  top: 84px;
  right: 24px;
  background: #0f172a;
  color: #ffffff;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 13px;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.18);
  z-index: 1000;
`;

// ════════════════════════════════════════════════════════════════════
// TABS — only product surfaces here. Operator/research live elsewhere.
// ════════════════════════════════════════════════════════════════════
const MAIN_TABS = [
  { id: 'analysis',   label: 'Analysis',   icon: BarChart2, description: 'What is happening' },
  { id: 'action',     label: 'Action',     icon: Activity,  description: 'What to do' },
  { id: 'prediction', label: 'Prediction', icon: Sparkles,  description: 'TA forecasts' },
  { id: 'ideas',      label: 'Ideas',      icon: Bookmark,  description: 'Saved ideas' },
];

// ════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ════════════════════════════════════════════════════════════════════
const TechAnalysisInner = () => {
  const [activeTab, setActiveTab] = useState('analysis');
  const { symbol, timeframe } = useMarket();

  // Save Idea state (used by deep child components via setupService)
  // eslint-disable-next-line no-unused-vars
  const [savingIdea, setSavingIdea] = useState(false);
  // eslint-disable-next-line no-unused-vars
  const [savedIdea, setSavedIdea] = useState(null);
  const [ideaToast, setIdeaToast] = useState(null);

  // eslint-disable-next-line no-unused-vars
  const handleSaveIdea = useCallback(async () => {
    if (savingIdea) return;
    try {
      setSavingIdea(true);
      const result = await setupService.createIdea(symbol, timeframe || '4H');
      if (result.ok) {
        setSavedIdea(result.idea);
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

  return (
    <PageContainer data-testid="tech-analysis-module">
      <ModuleHeader data-testid="module-header">
        <ModuleTitle>
          <Activity className="icon" />
          <div className="text">
            <h1>Tech Analysis</h1>
            <span className="description">
              Pattern recognition &amp; market structure
            </span>
          </div>
        </ModuleTitle>

        <TabsNav data-testid="tabs-nav">
          {MAIN_TABS.map((tab) => (
            <TabButton
              key={tab.id}
              $active={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
              data-testid={`tab-${tab.id}`}
              title={tab.description}
            >
              <tab.icon />
              {tab.label}
            </TabButton>
          ))}
        </TabsNav>
      </ModuleHeader>

      <MainContent data-testid="main-content">
        {/* Analysis + Action share the unified ResearchViewNew layout. */}
        {(activeTab === 'analysis' || activeTab === 'action') && (
          <ResearchView activeMode={activeTab} />
        )}

        {/* Prediction — TA rolling forecasts / horizons */}
        {activeTab === 'prediction' && <TAPredictionTab />}

        {/* Ideas — text-only evolution tracker */}
        {activeTab === 'ideas' && (
          <IdeasView
            onNavigateToChart={() => {
              setActiveTab('analysis');
            }}
          />
        )}
      </MainContent>

      {ideaToast && <Toast>{ideaToast}</Toast>}
    </PageContainer>
  );
};

const TechAnalysisModule = () => {
  return (
    <MarketProvider>
      <TechAnalysisInner />
    </MarketProvider>
  );
};

// ════════════════════════════════════════════════════════════════════
// VIEW IMPORTS — user-zone product surface (PHASE 6.3).
// HypothesesView is NOT imported here — admin-only (research/lab).
// ════════════════════════════════════════════════════════════════════
import ResearchView from './views/ResearchViewNew';
import IdeasView from './views/IdeasView';
import TAPredictionTab from './views/TAPredictionTab';

export default TechAnalysisModule;
