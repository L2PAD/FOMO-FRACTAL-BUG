/**
 * PatternActivationLayer Component
 * =================================
 * Shows detected elements below chart.
 * User clicks to toggle visibility on chart.
 */

import React from 'react';
import styled from 'styled-components';
import { Triangle, TrendingUp, Layers, Target, Activity, AlertCircle } from 'lucide-react';

// ============================================
// STYLED COMPONENTS
// ============================================

const Container = styled.div`
  background: #ffffff;
  border: 1px solid #eef1f5;
  border-radius: 12px;
  padding: 16px;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  
  .title {
    font-size: 13px;
    font-weight: 700;
    color: #0f172a;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  
  .count {
    font-size: 12px;
    color: #64748b;
  }
`;

const CategoryGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
`;

const Category = styled.div`
  .category-header {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    margin-bottom: 8px;
    
    svg {
      width: 14px;
      height: 14px;
    }
  }
`;

const ElementList = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
`;

const ElementTag = styled.button`
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: 6px;
  border: 1px solid ${({ $active, $color }) => $active ? $color : '#e2e8f0'};
  background: ${({ $active, $color }) => $active ? `${$color}10` : '#f8fafc'};
  color: ${({ $active, $color }) => $active ? $color : '#64748b'};
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  
  &:hover {
    border-color: ${({ $color }) => $color};
    background: ${({ $color }) => `${$color}08`};
  }
  
  .confidence {
    font-size: 10px;
    opacity: 0.8;
  }
`;

const DirectionDot = styled.span`
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: ${({ $direction }) => 
    $direction === 'bullish' ? '#05A584' : 
    $direction === 'bearish' ? '#ef4444' : 
    '#64748b'};
`;

const EmptyState = styled.div`
  font-size: 11px;
  color: #94a3b8;
  padding: 4px 0;
`;

// ============================================
// COLORS
// ============================================

const CATEGORY_COLORS = {
  patterns: '#3b82f6',
  indicators: '#8b5cf6',
  structure: '#f59e0b',
  levels: '#05A584',
  conflicts: '#ef4444',
};

// ============================================
// COMPONENT
// ============================================

const PatternActivationLayer = ({
  setup = null,
  activeElements = {},
  onToggleElement = () => {},
}) => {
  if (!setup) {
    return (
      <Container data-testid="pattern-activation-layer">
        <Header>
          <span className="title">Detected Elements</span>
        </Header>
        <EmptyState>No setup data available</EmptyState>
      </Container>
    );
  }

  const patterns = setup.patterns || [];
  const indicators = setup.indicators || [];
  const levels = setup.levels || [];
  const structure = setup.structure || [];
  const conflicts = setup.conflicts || [];

  const totalElements = patterns.length + indicators.length + levels.length + structure.length;

  return (
    <Container data-testid="pattern-activation-layer">
      <Header>
        <span className="title">Detected Elements</span>
        <span className="count">{totalElements} found</span>
      </Header>

      <CategoryGrid>
        {/* Patterns */}
        <Category>
          <div className="category-header">
            <Triangle /> Patterns
          </div>
          <ElementList>
            {patterns.length > 0 ? patterns.map((p, i) => (
              <ElementTag
                key={`pattern-${i}`}
                $active={activeElements[`pattern-${i}`]}
                $color={CATEGORY_COLORS.patterns}
                onClick={() => onToggleElement(`pattern-${i}`)}
                data-testid={`element-pattern-${i}`}
              >
                <DirectionDot $direction={p.direction} />
                {(p.type || 'Unknown').replace(/_/g, ' ')}
                <span className="confidence">{Math.round((p.confidence || 0) * 100)}%</span>
              </ElementTag>
            )) : <EmptyState>No patterns detected</EmptyState>}
          </ElementList>
        </Category>

        {/* Indicators */}
        <Category>
          <div className="category-header">
            <Activity /> Indicators
          </div>
          <ElementList>
            {indicators.length > 0 ? indicators.slice(0, 6).map((ind, i) => (
              <ElementTag
                key={`indicator-${i}`}
                $active={activeElements[`indicator-${i}`]}
                $color={CATEGORY_COLORS.indicators}
                onClick={() => onToggleElement(`indicator-${i}`)}
                data-testid={`element-indicator-${i}`}
              >
                <DirectionDot $direction={ind.direction} />
                {ind.name}
              </ElementTag>
            )) : <EmptyState>No indicator signals</EmptyState>}
          </ElementList>
        </Category>

        {/* Structure */}
        <Category>
          <div className="category-header">
            <TrendingUp /> Structure
          </div>
          <ElementList>
            {structure.length > 0 ? (
              // Group structure by type
              [...new Set(structure.map(s => s.type))].map((type, i) => {
                const count = structure.filter(s => s.type === type).length;
                const isBullish = ['HH', 'HL'].includes(type);
                return (
                  <ElementTag
                    key={`structure-${type}`}
                    $active={activeElements[`structure-${type}`]}
                    $color={CATEGORY_COLORS.structure}
                    onClick={() => onToggleElement(`structure-${type}`)}
                    data-testid={`element-structure-${type}`}
                  >
                    <DirectionDot $direction={isBullish ? 'bullish' : 'bearish'} />
                    {type}
                    <span className="confidence">×{count}</span>
                  </ElementTag>
                );
              })
            ) : <EmptyState>No structure data</EmptyState>}
          </ElementList>
        </Category>

        {/* Levels */}
        <Category>
          <div className="category-header">
            <Layers /> Levels
          </div>
          <ElementList>
            {levels.length > 0 ? (
              // Group levels by type
              [...new Set(levels.map(l => l.type))].map((type, i) => {
                const count = levels.filter(l => l.type === type).length;
                const isBullish = type === 'support';
                return (
                  <ElementTag
                    key={`level-${type}`}
                    $active={activeElements[`level-${type}`]}
                    $color={CATEGORY_COLORS.levels}
                    onClick={() => onToggleElement(`level-${type}`)}
                    data-testid={`element-level-${type}`}
                  >
                    <DirectionDot $direction={isBullish ? 'bullish' : 'bearish'} />
                    {(type || '').replace(/_/g, ' ')}
                    <span className="confidence">×{count}</span>
                  </ElementTag>
                );
              })
            ) : <EmptyState>No levels found</EmptyState>}
          </ElementList>
        </Category>

        {/* Conflicts */}
        {conflicts.length > 0 && (
          <Category>
            <div className="category-header">
              <AlertCircle /> Conflicts
            </div>
            <ElementList>
              {conflicts.map((c, i) => (
                <ElementTag
                  key={`conflict-${i}`}
                  $active={activeElements[`conflict-${i}`]}
                  $color={CATEGORY_COLORS.conflicts}
                  onClick={() => onToggleElement(`conflict-${i}`)}
                  data-testid={`element-conflict-${i}`}
                >
                  {c.name}
                  <span className="confidence">{c.severity}</span>
                </ElementTag>
              ))}
            </ElementList>
          </Category>
        )}
      </CategoryGrid>
    </Container>
  );
};

export default PatternActivationLayer;
