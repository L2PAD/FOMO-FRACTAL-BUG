/**
 * Structure Tab — Market Geometry
 * ================================
 * 
 * Redesigned: All analysis in unified TA Explorer
 * 
 * Contains:
 * - Full Chart (shown in parent)
 * - Unified TA Explorer (full width) with:
 *   - Pattern selection
 *   - 10 Layers analysis (user-friendly)
 *   - Trade setup
 * - Pattern Lifecycle filter (clickable)
 */

import React, { useState } from 'react';
import styled from 'styled-components';
import { RefreshCw } from 'lucide-react';

// Import components
import ResearchChart from '../../components/ResearchChart';
import { TAExplorerPanel } from '../../components/ta-explorer';
import { RenderPlanOverlay } from '../../renderers';

const Container = styled.div`
  display: flex;
  flex-direction: column;
  gap: 16px;
`;

const ChartSection = styled.div`
  position: relative;
  height: 450px;
  background: #ffffff;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
`;

const LoadingOverlay = styled.div`
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.85);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  z-index: 10;
`;

// Full-width TA Explorer container
const ExplorerContainer = styled.div`
  width: 100%;
  border-radius: 12px;
  overflow: hidden;
`;

// Lifecycle integration at top of explorer
const LifecycleSection = styled.div`
  background: #0f172a;
  border-radius: 12px 12px 0 0;
  padding: 16px 20px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-bottom: none;
`;

const LifecycleHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
`;

const LifecycleTitle = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.7);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  
  svg {
    width: 14px;
    height: 14px;
  }
`;

const FilterHint = styled.span`
  font-size: 10px;
  color: rgba(255, 255, 255, 0.4);
  font-weight: 400;
  text-transform: none;
  letter-spacing: 0;
  margin-left: 8px;
`;

const PatternTypeBadge = styled.span`
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 6px;
  font-weight: 600;
  background: ${props => props.$bias === 'bullish' ? 'rgba(34, 197, 94, 0.15)' : 
                props.$bias === 'bearish' ? 'rgba(239, 68, 68, 0.15)' : 
                'rgba(59, 130, 246, 0.15)'};
  color: ${props => props.$bias === 'bullish' ? '#22c55e' : 
           props.$bias === 'bearish' ? '#ef4444' : '#60a5fa'};
`;

const LifecycleBar = styled.div`
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
`;

const LifecycleStage = styled.button`
  flex: 1;
  padding: 10px 12px;
  text-align: center;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  border: none;
  
  background: ${p => p.$active 
    ? p.$stage === 'confirmed' ? 'rgba(34, 197, 94, 0.2)' 
      : p.$stage === 'invalidated' ? 'rgba(239, 68, 68, 0.2)'
      : p.$stage === 'developing' ? 'rgba(234, 179, 8, 0.2)'
      : 'rgba(59, 130, 246, 0.2)'
    : p.$selected 
      ? 'rgba(255, 255, 255, 0.1)'
      : 'transparent'};
  
  color: ${p => p.$active 
    ? p.$stage === 'confirmed' ? '#22c55e' 
      : p.$stage === 'invalidated' ? '#ef4444'
      : p.$stage === 'developing' ? '#eab308'
      : '#3b82f6'
    : p.$selected
      ? '#ffffff'
      : 'rgba(255, 255, 255, 0.4)'};
    
  border: 1px solid ${p => p.$active 
    ? p.$stage === 'confirmed' ? 'rgba(34, 197, 94, 0.3)' 
      : p.$stage === 'invalidated' ? 'rgba(239, 68, 68, 0.3)'
      : p.$stage === 'developing' ? 'rgba(234, 179, 8, 0.3)'
      : 'rgba(59, 130, 246, 0.3)'
    : p.$selected
      ? 'rgba(255, 255, 255, 0.2)'
      : 'transparent'};
      
  &:hover {
    background: ${p => p.$active 
      ? p.$stage === 'confirmed' ? 'rgba(34, 197, 94, 0.25)' 
        : p.$stage === 'invalidated' ? 'rgba(239, 68, 68, 0.25)'
        : p.$stage === 'developing' ? 'rgba(234, 179, 8, 0.25)'
        : 'rgba(59, 130, 246, 0.25)'
      : 'rgba(255, 255, 255, 0.08)'};
    color: ${p => p.$active 
      ? p.$stage === 'confirmed' ? '#22c55e' 
        : p.$stage === 'invalidated' ? '#ef4444'
        : p.$stage === 'developing' ? '#eab308'
        : '#3b82f6'
      : '#ffffff'};
  }
    
  &::after {
    content: '→';
    position: absolute;
    right: -8px;
    color: rgba(255, 255, 255, 0.2);
    font-size: 10px;
  }
  
  &:last-child::after {
    display: none;
  }
`;

const CountBadge = styled.span`
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.15);
  color: rgba(255, 255, 255, 0.7);
  margin-left: 4px;
`;

const TAExplorerWrapper = styled.div`
  border-radius: ${props => props.$hasLifecycle ? '0 0 12px 12px' : '12px'};
  overflow: hidden;
  
  > div {
    border-radius: ${props => props.$hasLifecycle ? '0 0 12px 12px' : '12px'};
    border-top: ${props => props.$hasLifecycle ? 'none' : '1px solid rgba(255, 255, 255, 0.1)'};
  }
`;

const StructureTab = ({
  // Chart props
  symbol,
  selectedTF,
  chartType,
  levels,
  structure,
  decision,
  primaryPattern,
  alternativePatterns,
  activePatternId,
  onPatternClick,
  patternV2,
  setupData,
  // Visibility props
  showLevels,
  showStructure,
  showLiquidity,
  showSweeps,
  showCHOCH,
  showNarrative,
  // Indicator overlays
  indicatorOverlays,
  // Fibonacci
  fibonacci,
  showFibonacciOverlay,
  showPatternOverlay,
  patternViewMode,
  patternWindow,
  // Render plan overlay
  showTAOverlay,
  renderPlan,
  // Loading state
  loading,
  // Analysis mode
  analysisMode,
  // Hide chart flag (graph is now always visible in parent)
  hideChart = false,
}) => {
  const [lifecycleFilter, setLifecycleFilter] = useState(null); // null = show all, or 'forming'|'developing'|'confirmed'|'invalidated'
  
  const lifecycle = primaryPattern?.lifecycle || primaryPattern?.stage || 'forming';
  const lifecycleStages = ['forming', 'developing', 'confirmed', 'invalidated'];
  const patternType = primaryPattern?.type?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || 'Analyzing...';
  const patternBias = primaryPattern?.bias || primaryPattern?.direction || 'neutral';
  
  // Check if we have pattern or lifecycle info to show
  const hasLifecycleData = primaryPattern?.type || setupData?.ta_explorer?.dominant?.type;
  
  // Count patterns by lifecycle stage
  const patterns = setupData?.ta_explorer?.patterns_all || [];
  const lifecycleCounts = lifecycleStages.reduce((acc, stage) => {
    acc[stage] = patterns.filter(p => (p.lifecycle || p.stage || 'forming') === stage).length;
    return acc;
  }, {});
  
  // Filter patterns based on lifecycle filter
  const getFilteredPatterns = () => {
    if (!lifecycleFilter) return patterns;
    return patterns.filter(p => (p.lifecycle || p.stage || 'forming') === lifecycleFilter);
  };
  
  const handleLifecycleClick = (stage) => {
    // Toggle filter: if clicking same stage, clear filter; otherwise set filter
    setLifecycleFilter(prev => prev === stage ? null : stage);
  };
  
  return (
    <Container data-testid="structure-tab">
      {/* Main Chart — Only show if NOT hidden */}
      {!hideChart && (
        <ChartSection data-testid="structure-chart">
          <ResearchChart
            symbol={symbol}
            timeframe={selectedTF}
            chartType={chartType}
            levels={levels}
            structure={structure}
            showLevels={showLevels}
            showStructure={showStructure}
            showLiquidity={showLiquidity}
            showSweeps={showSweeps}
            showCHOCH={showCHOCH}
            showNarrative={showNarrative}
            decision={decision}
            indicatorOverlays={indicatorOverlays}
            patternV2={{ primary_pattern: primaryPattern, alternative_patterns: alternativePatterns }}
            patternGeometry={setupData?.pattern_geometry}
            fibonacci={fibonacci}
            showFibonacciOverlay={showFibonacciOverlay}
            showPatternOverlay={showPatternOverlay}
            patternViewMode={patternViewMode}
            patternWindow={patternWindow}
          />
          
          {loading && (
            <LoadingOverlay>
              <RefreshCw size={24} color="#3b82f6" style={{ animation: 'spin 1s linear infinite' }} />
              <span style={{ color: '#64748b', fontSize: 13 }}>Loading chart...</span>
            </LoadingOverlay>
          )}
          
          {/* Render Plan Overlay */}
          {showTAOverlay && renderPlan && (
            <RenderPlanOverlay 
              renderPlan={renderPlan}
              onChainStepClick={(step) => console.log('[Structure] Step clicked:', step)}
            />
          )}
        </ChartSection>
      )}
      
      {/* Unified Full-Width TA Explorer */}
      <ExplorerContainer>
        {/* Pattern Lifecycle - Now clickable as filter */}
        {hasLifecycleData && (
          <LifecycleSection data-testid="pattern-lifecycle">
            <LifecycleHeader>
              <LifecycleTitle>
                <RefreshCw />
                Pattern Lifecycle
                <FilterHint>
                  {lifecycleFilter ? `Filtering: ${lifecycleFilter}` : 'Click to filter'}
                </FilterHint>
              </LifecycleTitle>
              <PatternTypeBadge $bias={patternBias}>
                {patternType}
              </PatternTypeBadge>
            </LifecycleHeader>
            <LifecycleBar>
              {lifecycleStages.map(stage => {
                const isCurrentLifecycle = lifecycle === stage || 
                  (lifecycle === 'confirmed_up' && stage === 'confirmed') ||
                  (lifecycle === 'confirmed_down' && stage === 'confirmed') ||
                  (lifecycle === 'active' && stage === 'developing');
                const isSelected = lifecycleFilter === stage;
                const count = lifecycleCounts[stage] || 0;
                
                return (
                  <LifecycleStage 
                    key={stage}
                    $active={isCurrentLifecycle}
                    $selected={isSelected}
                    $stage={stage}
                    onClick={() => handleLifecycleClick(stage)}
                    data-testid={`lifecycle-${stage}`}
                  >
                    {stage}
                    {count > 0 && <CountBadge>{count}</CountBadge>}
                  </LifecycleStage>
                );
              })}
            </LifecycleBar>
          </LifecycleSection>
        )}
        
        {/* TA Explorer Panel */}
        <TAExplorerWrapper $hasLifecycle={hasLifecycleData}>
          {setupData?.ta_explorer ? (
            <TAExplorerPanel 
              data={{
                ...setupData.ta_explorer,
                // Apply lifecycle filter if set
                patterns_all: lifecycleFilter 
                  ? getFilteredPatterns()
                  : setupData.ta_explorer.patterns_all
              }}
              onPatternSelect={(pattern, index) => {
                console.log('[StructureTab] Pattern selected:', pattern.type, index);
                if (onPatternClick) {
                  onPatternClick(pattern.id || index);
                }
              }}
              selectedPatternIndex={activePatternId || 0}
              lifecycleFilter={lifecycleFilter}
            />
          ) : (
            <TAExplorerPanel data={null} />
          )}
        </TAExplorerWrapper>
      </ExplorerContainer>
    </Container>
  );
};

export default StructureTab;
