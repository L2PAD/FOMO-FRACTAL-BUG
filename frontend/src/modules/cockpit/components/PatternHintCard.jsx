/**
 * PatternHintCard — Mini-visualization of detected pattern
 * =========================================================
 * 
 * PHASE 1: Instead of drawing broken lines on chart,
 * show pattern info in a clean card with:
 * - Pattern type name
 * - Confidence score
 * - State (forming/confirmed/invalidated)
 * - Mini SVG schematic of the pattern shape
 * - Time range when detected
 * 
 * This prevents broken geometry from polluting the main chart.
 */

import React from 'react';
import styled from 'styled-components';
import { Triangle, TrendingUp, TrendingDown, Activity } from 'lucide-react';

// ═══════════════════════════════════════════════════════════════
// STYLED COMPONENTS
// ═══════════════════════════════════════════════════════════════

const Card = styled.div`
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
`;

const Title = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`;

const PatternName = styled.span`
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  text-transform: capitalize;
`;

const PatternBadge = styled.span`
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  background: ${({ $bias }) => 
    $bias === 'bullish' ? 'rgba(5, 165, 132, 0.1)' :
    $bias === 'bearish' ? 'rgba(239, 68, 68, 0.1)' :
    'rgba(100, 116, 139, 0.1)'
  };
  color: ${({ $bias }) => 
    $bias === 'bullish' ? '#05A584' :
    $bias === 'bearish' ? '#EF4444' :
    '#64748b'
  };
`;

const ConfidenceBar = styled.div`
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
`;

const ConfidenceValue = styled.span`
  font-size: 18px;
  font-weight: 800;
  color: ${({ $value }) => 
    $value >= 70 ? '#05A584' :
    $value >= 50 ? '#F59E0B' :
    '#94a3b8'
  };
`;

const ConfidenceLabel = styled.span`
  font-size: 10px;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

// NEW: Visual confidence progress bar
const ProgressBarContainer = styled.div`
  width: 80px;
  height: 6px;
  background: #e2e8f0;
  border-radius: 3px;
  overflow: hidden;
`;

const ProgressBarFill = styled.div`
  height: 100%;
  width: ${({ $value }) => $value}%;
  background: ${({ $value }) => 
    $value >= 70 ? '#05A584' :
    $value >= 50 ? '#F59E0B' :
    '#94a3b8'
  };
  border-radius: 3px;
  transition: width 0.3s ease;
`;

// NEW: Mode badge (STRICT vs LOOSE visual difference)
const ModeBadge = styled.span`
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-left: 8px;
  
  ${({ $mode }) => $mode === 'strict' ? `
    background: rgba(59, 130, 246, 0.15);
    color: #3B82F6;
    border: 1px solid rgba(59, 130, 246, 0.3);
  ` : `
    background: rgba(148, 163, 184, 0.1);
    color: #64748b;
    border: 1px dashed rgba(148, 163, 184, 0.5);
  `}
`;

const Body = styled.div`
  display: flex;
  gap: 16px;
`;

const ShapeContainer = styled.div`
  width: 80px;
  height: 60px;
  flex-shrink: 0;
  background: #f8fafc;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
`;

const InfoContainer = styled.div`
  flex: 1;
`;

const InfoRow = styled.div`
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  
  &:last-child {
    margin-bottom: 0;
  }
`;

const InfoLabel = styled.span`
  font-size: 12px;
  color: #64748b;
`;

const InfoValue = styled.span`
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
`;

const StateBadge = styled.span`
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  background: ${({ $state }) => 
    $state === 'confirmed' ? 'rgba(5, 165, 132, 0.15)' :
    $state === 'forming' ? 'rgba(245, 158, 11, 0.15)' :
    $state === 'invalidated' ? 'rgba(239, 68, 68, 0.15)' :
    'rgba(100, 116, 139, 0.15)'
  };
  color: ${({ $state }) => 
    $state === 'confirmed' ? '#059669' :
    $state === 'forming' ? '#D97706' :
    $state === 'invalidated' ? '#DC2626' :
    '#64748b'
  };
`;

// ═══════════════════════════════════════════════════════════════
// PATTERN SHAPE SVGs (mini schematics)
// ═══════════════════════════════════════════════════════════════

const PatternShapes = {
  falling_wedge: (
    <svg width="60" height="40" viewBox="0 0 60 40">
      <line x1="5" y1="5" x2="55" y2="20" stroke="#3B82F6" strokeWidth="2" />
      <line x1="5" y1="35" x2="55" y2="25" stroke="#3B82F6" strokeWidth="2" />
      <circle cx="55" cy="22" r="3" fill="#22C55E" />
    </svg>
  ),
  rising_wedge: (
    <svg width="60" height="40" viewBox="0 0 60 40">
      <line x1="5" y1="35" x2="55" y2="15" stroke="#EF4444" strokeWidth="2" />
      <line x1="5" y1="5" x2="55" y2="20" stroke="#EF4444" strokeWidth="2" />
      <circle cx="55" cy="17" r="3" fill="#EF4444" />
    </svg>
  ),
  symmetrical_triangle: (
    <svg width="60" height="40" viewBox="0 0 60 40">
      <line x1="5" y1="5" x2="55" y2="18" stroke="#3B82F6" strokeWidth="2" />
      <line x1="5" y1="35" x2="55" y2="22" stroke="#3B82F6" strokeWidth="2" />
      <circle cx="55" cy="20" r="3" fill="#F59E0B" />
    </svg>
  ),
  ascending_triangle: (
    <svg width="60" height="40" viewBox="0 0 60 40">
      <line x1="5" y1="10" x2="55" y2="10" stroke="#22C55E" strokeWidth="2" />
      <line x1="5" y1="35" x2="55" y2="15" stroke="#22C55E" strokeWidth="2" />
      <circle cx="55" cy="10" r="3" fill="#22C55E" />
    </svg>
  ),
  descending_triangle: (
    <svg width="60" height="40" viewBox="0 0 60 40">
      <line x1="5" y1="30" x2="55" y2="30" stroke="#EF4444" strokeWidth="2" />
      <line x1="5" y1="5" x2="55" y2="25" stroke="#EF4444" strokeWidth="2" />
      <circle cx="55" cy="30" r="3" fill="#EF4444" />
    </svg>
  ),
  channel: (
    <svg width="60" height="40" viewBox="0 0 60 40">
      <line x1="5" y1="10" x2="55" y2="10" stroke="#8B5CF6" strokeWidth="2" />
      <line x1="5" y1="30" x2="55" y2="30" stroke="#8B5CF6" strokeWidth="2" />
    </svg>
  ),
  double_top: (
    <svg width="60" height="40" viewBox="0 0 60 40">
      <polyline points="5,30 15,10 25,25 35,10 45,30 55,35" fill="none" stroke="#EF4444" strokeWidth="2" />
    </svg>
  ),
  double_bottom: (
    <svg width="60" height="40" viewBox="0 0 60 40">
      <polyline points="5,10 15,30 25,15 35,30 45,10 55,5" fill="none" stroke="#22C55E" strokeWidth="2" />
    </svg>
  ),
  head_shoulders: (
    <svg width="60" height="40" viewBox="0 0 60 40">
      <polyline points="5,25 12,15 20,25 30,5 40,25 48,15 55,25" fill="none" stroke="#EF4444" strokeWidth="2" />
      <line x1="5" y1="25" x2="55" y2="25" stroke="#EF4444" strokeWidth="1" strokeDasharray="2,2" />
    </svg>
  ),
  // NEW: Loose patterns (dashed style)
  loose_range: (
    <svg width="60" height="40" viewBox="0 0 60 40">
      <line x1="5" y1="12" x2="55" y2="12" stroke="#64748B" strokeWidth="1.5" strokeDasharray="4,3" />
      <line x1="5" y1="28" x2="55" y2="28" stroke="#64748B" strokeWidth="1.5" strokeDasharray="4,3" />
      <rect x="5" y="12" width="50" height="16" fill="rgba(100,116,139,0.08)" />
    </svg>
  ),
  loose_wedge: (
    <svg width="60" height="40" viewBox="0 0 60 40">
      <line x1="5" y1="5" x2="55" y2="18" stroke="#64748B" strokeWidth="1.5" strokeDasharray="4,3" />
      <line x1="5" y1="35" x2="55" y2="22" stroke="#64748B" strokeWidth="1.5" strokeDasharray="4,3" />
    </svg>
  ),
  loose_triangle: (
    <svg width="60" height="40" viewBox="0 0 60 40">
      <line x1="5" y1="5" x2="55" y2="18" stroke="#64748B" strokeWidth="1.5" strokeDasharray="4,3" />
      <line x1="5" y1="35" x2="55" y2="22" stroke="#64748B" strokeWidth="1.5" strokeDasharray="4,3" />
    </svg>
  ),
  structure: (
    <svg width="60" height="40" viewBox="0 0 60 40">
      <polyline points="5,30 15,15 25,25 35,10 45,20 55,15" fill="none" stroke="#64748B" strokeWidth="2" />
      <circle cx="15" cy="15" r="2" fill="#64748B" />
      <circle cx="35" cy="10" r="2" fill="#64748B" />
    </svg>
  ),
};

const getPatternShape = (type) => {
  const normalized = type?.toLowerCase().replace(/ /g, '_');
  return PatternShapes[normalized] || PatternShapes.structure;
};

// ═══════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════

const PatternHintCard = ({ 
  pattern = null,
  analysisMode = 'structure',
  summary = null,
}) => {
  // Don't render if no pattern and not in figure mode
  if (!pattern && analysisMode !== 'figure') {
    return null;
  }
  
  // Structure mode - show structure card
  if (analysisMode === 'structure' || !pattern) {
    return (
      <Card data-testid="pattern-hint-card-structure">
        <Header>
          <Title>
            <Activity size={16} color="#64748b" />
            <PatternName>Structure Developing</PatternName>
          </Title>
          <PatternBadge $bias="neutral">Neutral</PatternBadge>
        </Header>
        <Body>
          <ShapeContainer>
            {getPatternShape('structure')}
          </ShapeContainer>
          <InfoContainer>
            <InfoRow>
              <InfoLabel>Status</InfoLabel>
              <StateBadge $state="forming">In Transition</StateBadge>
            </InfoRow>
            <InfoRow>
              <InfoLabel>Summary</InfoLabel>
              <InfoValue>{summary?.text || 'No dominant pattern detected'}</InfoValue>
            </InfoRow>
          </InfoContainer>
        </Body>
      </Card>
    );
  }
  
  // Figure mode - show pattern card
  const patternType = pattern.type || 'unknown';
  const confidence = Math.round((pattern.confidence || pattern.render_quality || 0.5) * 100);
  const state = pattern.state || pattern.status || 'forming';
  const mode = pattern.mode || 'loose'; // STRICT vs LOOSE
  const bias = patternType.includes('falling') || patternType.includes('ascending') || patternType.includes('bottom')
    ? 'bullish'
    : patternType.includes('rising') || patternType.includes('descending') || patternType.includes('top')
    ? 'bearish'
    : 'neutral';
    
  const windowInfo = pattern.window;
  const formatTime = (ts) => {
    if (!ts) return '-';
    const date = new Date(ts * 1000);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  return (
    <Card data-testid="pattern-hint-card">
      <Header>
        <Title>
          {bias === 'bullish' ? <TrendingUp size={16} color="#05A584" /> :
           bias === 'bearish' ? <TrendingDown size={16} color="#EF4444" /> :
           <Triangle size={16} color="#3B82F6" />}
          <PatternName>{patternType.replace(/_/g, ' ')}</PatternName>
          <ModeBadge $mode={mode}>{mode}</ModeBadge>
        </Title>
        <ConfidenceBar>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <ConfidenceValue $value={confidence}>{confidence}%</ConfidenceValue>
            <ConfidenceLabel>conf</ConfidenceLabel>
          </div>
          <ProgressBarContainer>
            <ProgressBarFill $value={confidence} />
          </ProgressBarContainer>
        </ConfidenceBar>
      </Header>
      <Body>
        <ShapeContainer>
          {getPatternShape(patternType)}
        </ShapeContainer>
        <InfoContainer>
          <InfoRow>
            <InfoLabel>State</InfoLabel>
            <StateBadge $state={state}>{state}</StateBadge>
          </InfoRow>
          <InfoRow>
            <InfoLabel>Bias</InfoLabel>
            <PatternBadge $bias={bias}>{bias}</PatternBadge>
          </InfoRow>
          {windowInfo && (
            <InfoRow>
              <InfoLabel>Detected</InfoLabel>
              <InfoValue>{formatTime(windowInfo.start)} → {formatTime(windowInfo.end)}</InfoValue>
            </InfoRow>
          )}
        </InfoContainer>
      </Body>
    </Card>
  );
};

export default PatternHintCard;
