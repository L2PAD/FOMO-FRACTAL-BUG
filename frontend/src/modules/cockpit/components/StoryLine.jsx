/**
 * StoryLine — Market Narrative Chain
 * ===================================
 * 
 * Connects graph and analysis through a narrative chain:
 * Liquidity sweep → impulsive move → loss of momentum → range formation
 * 
 * NOT decorative — the CORE linking element.
 */

import React from 'react';
import styled from 'styled-components';
import { ArrowRight, Zap, TrendingUp, TrendingDown, Minus, AlertCircle } from 'lucide-react';

// ============================================
// STYLED COMPONENTS
// ============================================

const Container = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  background: linear-gradient(135deg, #f0f9ff 0%, #f8fafc 100%);
  border: 1px solid #e0f2fe;
  border-radius: 10px;
  margin: 8px 0;
  overflow-x: auto;
  
  &::-webkit-scrollbar {
    display: none;
  }
`;

const Label = styled.span`
  font-size: 10px;
  font-weight: 700;
  color: #0369a1;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
  margin-right: 8px;
`;

const ChainStep = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  background: ${({ $color }) => $color ? `${$color}15` : '#ffffff'};
  border: 1px solid ${({ $color }) => $color ? `${$color}40` : '#e2e8f0'};
  border-radius: 6px;
  white-space: nowrap;
  flex-shrink: 0;
  
  svg {
    width: 12px;
    height: 12px;
    color: ${({ $color }) => $color || '#64748b'};
  }
`;

const StepText = styled.span`
  font-size: 11px;
  font-weight: 600;
  color: #0f172a;
`;

const Arrow = styled.span`
  color: #cbd5e1;
  font-size: 14px;
  flex-shrink: 0;
`;

const PhaseTag = styled.span`
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: ${({ $phase }) => 
    $phase === 'trending' ? '#dcfce7' :
    $phase === 'range' ? '#fef3c7' :
    $phase === 'transition' ? '#e0e7ff' :
    '#f1f5f9'
  };
  border-radius: 12px;
  font-size: 10px;
  font-weight: 700;
  color: ${({ $phase }) => 
    $phase === 'trending' ? '#16a34a' :
    $phase === 'range' ? '#d97706' :
    $phase === 'transition' ? '#4f46e5' :
    '#64748b'
  };
  text-transform: uppercase;
  flex-shrink: 0;
  margin-left: auto;
`;

// ============================================
// HELPER — Build narrative from data
// ============================================

const buildNarrativeChain = (data) => {
  const { 
    liquidity, 
    displacement, 
    chochValidation, 
    structure,
    decision,
    pattern
  } = data || {};
  
  const chain = [];
  
  // 1. Liquidity event
  if (liquidity?.recent_sweeps?.length > 0) {
    const sweep = liquidity.recent_sweeps[0];
    const type = sweep.type?.toLowerCase();
    if (type === 'ssl' || type === 'bsl') {
      chain.push({
        text: `${type.toUpperCase()} Sweep`,
        icon: Zap,
        color: type === 'ssl' ? '#ef4444' : '#16a34a',
      });
    }
  }
  
  // 2. Displacement / Impulse
  if (displacement?.detected) {
    const direction = displacement.direction === 'bullish' ? 'up' : 'down';
    chain.push({
      text: `Impulse ${direction}`,
      icon: direction === 'up' ? TrendingUp : TrendingDown,
      color: direction === 'up' ? '#16a34a' : '#ef4444',
    });
  }
  
  // 3. CHOCH / Structure break
  if (chochValidation?.detected || structure?.choch) {
    const dir = chochValidation?.direction || structure?.choch?.direction || 'neutral';
    chain.push({
      text: 'CHOCH',
      icon: AlertCircle,
      color: dir === 'bullish' ? '#16a34a' : dir === 'bearish' ? '#ef4444' : '#6366f1',
    });
  } else if (structure?.bos) {
    const dir = structure.bos.direction;
    chain.push({
      text: 'BOS',
      icon: AlertCircle,
      color: dir === 'bullish' ? '#16a34a' : '#ef4444',
    });
  }
  
  // 4. Pattern formation (if any)
  if (pattern?.type) {
    chain.push({
      text: pattern.type.replace(/_/g, ' '),
      icon: Minus,
      color: '#6366f1',
    });
  }
  
  // 5. Current state from decision
  if (decision?.regime) {
    const regime = decision.regime.toLowerCase();
    if (regime.includes('range')) {
      chain.push({
        text: 'Range response',
        icon: Minus,
        color: '#f59e0b',
      });
    } else if (regime.includes('trend')) {
      chain.push({
        text: 'Trending',
        icon: TrendingUp,
        color: '#16a34a',
      });
    }
  }
  
  // If chain is empty, add generic
  if (chain.length === 0) {
    chain.push({
      text: 'Analyzing structure',
      icon: Minus,
      color: '#64748b',
    });
  }
  
  return chain;
};

const getCurrentPhase = (decision, structure) => {
  const regime = decision?.regime?.toLowerCase() || '';
  const bias = decision?.technical_bias?.toLowerCase() || '';
  
  if (regime.includes('range') || regime.includes('consolidat')) {
    return 'range';
  }
  if (regime.includes('trend') || bias === 'bullish' || bias === 'bearish') {
    return 'trending';
  }
  if (structure?.choch || structure?.bos) {
    return 'transition';
  }
  return 'developing';
};

// ============================================
// MAIN COMPONENT
// ============================================

const StoryLine = ({ 
  liquidity,
  displacement,
  chochValidation,
  structure,
  decision,
  pattern
}) => {
  const chain = buildNarrativeChain({
    liquidity,
    displacement,
    chochValidation,
    structure,
    decision,
    pattern
  });
  
  const phase = getCurrentPhase(decision, structure);

  return (
    <Container data-testid="story-line">
      <Label>Market Story</Label>
      
      {chain.map((step, idx) => (
        <React.Fragment key={idx}>
          {idx > 0 && <Arrow>→</Arrow>}
          <ChainStep $color={step.color}>
            <step.icon />
            <StepText>{step.text}</StepText>
          </ChainStep>
        </React.Fragment>
      ))}
      
      <PhaseTag $phase={phase}>
        Phase: {phase}
      </PhaseTag>
    </Container>
  );
};

export default StoryLine;
