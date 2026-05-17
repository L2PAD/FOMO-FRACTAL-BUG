/**
 * TACompositionPanel — Active Technical Setup View
 * ==================================================
 * 
 * This is NOT structure markup.
 * This shows the CURRENT TECHNICAL SETUP:
 * - Active figure (pattern on price)
 * - Active fib context
 * - Relevant overlays
 * - Breakout/Invalidation logic
 */

import React from 'react';
import styled from 'styled-components';
import { 
  TrendingUp, TrendingDown, Target, AlertTriangle, 
  Layers, Activity, ArrowUpRight, ArrowDownRight,
  ChevronRight, Minus
} from 'lucide-react';

// ═══════════════════════════════════════════════════════════════
// STYLED COMPONENTS
// ═══════════════════════════════════════════════════════════════

const Container = styled.div`
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  border-radius: 12px;
  border: 1px solid rgba(99, 102, 241, 0.2);
  overflow: hidden;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: rgba(99, 102, 241, 0.1);
  border-bottom: 1px solid rgba(99, 102, 241, 0.15);
`;

const Title = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #e2e8f0;
`;

const QualityBadge = styled.span`
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  
  ${({ $quality }) => {
    switch ($quality) {
      case 'high':
        return 'background: rgba(34, 197, 94, 0.2); color: #22c55e;';
      case 'medium':
        return 'background: rgba(234, 179, 8, 0.2); color: #eab308;';
      case 'low':
        return 'background: rgba(239, 68, 68, 0.2); color: #ef4444;';
      default:
        return 'background: rgba(100, 116, 139, 0.2); color: #64748b;';
    }
  }}
`;

const Content = styled.div`
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
`;

const SetupSummary = styled.div`
  font-size: 14px;
  font-weight: 500;
  color: #f1f5f9;
  padding: 10px 12px;
  background: rgba(99, 102, 241, 0.08);
  border-radius: 8px;
  border-left: 3px solid #6366f1;
`;

const SectionTitle = styled.div`
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
`;

const FigureCard = styled.div`
  background: rgba(15, 23, 42, 0.6);
  border-radius: 8px;
  padding: 12px;
  border: 1px solid rgba(148, 163, 184, 0.1);
`;

const FigureHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
`;

const FigureName = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #e2e8f0;
`;

const DirectionIcon = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  
  ${({ $direction }) => {
    if ($direction === 'bullish') {
      return 'background: rgba(34, 197, 94, 0.2); color: #22c55e;';
    } else if ($direction === 'bearish') {
      return 'background: rgba(239, 68, 68, 0.2); color: #ef4444;';
    }
    return 'background: rgba(100, 116, 139, 0.2); color: #64748b;';
  }}
`;

const ConfidenceBar = styled.div`
  width: 60px;
  height: 4px;
  background: rgba(100, 116, 139, 0.3);
  border-radius: 2px;
  overflow: hidden;
`;

const ConfidenceFill = styled.div`
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
  
  ${({ $confidence }) => {
    const pct = Math.round($confidence * 100);
    const color = $confidence >= 0.7 ? '#22c55e' : $confidence >= 0.5 ? '#eab308' : '#ef4444';
    return `width: ${pct}%; background: ${color};`;
  }}
`;

const LevelRow = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 12px;
  
  &:not(:last-child) {
    border-bottom: 1px solid rgba(148, 163, 184, 0.08);
  }
`;

const LevelLabel = styled.span`
  color: #94a3b8;
  display: flex;
  align-items: center;
  gap: 4px;
`;

const LevelValue = styled.span`
  font-weight: 600;
  font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
  
  ${({ $type }) => {
    if ($type === 'breakout') return 'color: #22c55e;';
    if ($type === 'invalidation') return 'color: #ef4444;';
    return 'color: #e2e8f0;';
  }}
`;

const FibSection = styled.div`
  background: rgba(234, 179, 8, 0.05);
  border-radius: 8px;
  padding: 12px;
  border: 1px solid rgba(234, 179, 8, 0.15);
`;

const FibLevelChip = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  margin-right: 6px;
  margin-bottom: 4px;
  
  ${({ $status }) => {
    if ($status === 'testing') {
      return 'background: rgba(234, 179, 8, 0.2); color: #eab308; border: 1px solid rgba(234, 179, 8, 0.3);';
    } else if ($status === 'above') {
      return 'background: rgba(34, 197, 94, 0.1); color: #86efac;';
    }
    return 'background: rgba(239, 68, 68, 0.1); color: #fca5a5;';
  }}
`;

const OverlaysRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
`;

const OverlayChip = styled.div`
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 6px;
  font-size: 11px;
  color: #c7d2fe;
`;

const OverlayValue = styled.span`
  font-weight: 600;
  color: #e2e8f0;
  font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
`;

const BreakoutSection = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
`;

const BreakoutCard = styled.div`
  padding: 10px 12px;
  border-radius: 8px;
  
  ${({ $type }) => {
    if ($type === 'breakout') {
      return `
        background: rgba(34, 197, 94, 0.08);
        border: 1px solid rgba(34, 197, 94, 0.2);
      `;
    }
    return `
      background: rgba(239, 68, 68, 0.08);
      border: 1px solid rgba(239, 68, 68, 0.2);
    `;
  }}
`;

const BreakoutLabel = styled.div`
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  margin-bottom: 4px;
  
  ${({ $type }) => $type === 'breakout' ? 'color: #86efac;' : 'color: #fca5a5;'}
`;

const BreakoutPrice = styled.div`
  font-size: 16px;
  font-weight: 700;
  font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
  
  ${({ $type }) => $type === 'breakout' ? 'color: #22c55e;' : 'color: #ef4444;'}
`;

const ActiveZone = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(168, 85, 247, 0.1);
  border: 1px solid rgba(168, 85, 247, 0.2);
  border-radius: 6px;
  font-size: 12px;
  color: #d8b4fe;
`;

const NoSetupMessage = styled.div`
  text-align: center;
  padding: 24px;
  color: #64748b;
  font-size: 13px;
`;

// ═══════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

const formatFigureType = (type) => {
  if (!type) return 'Unknown';
  return type
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
};

const formatPrice = (price) => {
  if (!price) return '—';
  if (price >= 10000) return price.toLocaleString('en-US', { maximumFractionDigits: 0 });
  if (price >= 100) return price.toLocaleString('en-US', { maximumFractionDigits: 1 });
  return price.toLocaleString('en-US', { maximumFractionDigits: 2 });
};

// ═══════════════════════════════════════════════════════════════
// COMPONENT
// ═══════════════════════════════════════════════════════════════

const TACompositionPanel = ({ composition }) => {
  if (!composition) {
    return (
      <Container data-testid="ta-composition-panel">
        <Header>
          <Title>
            <Layers size={14} />
            Technical Setup
          </Title>
        </Header>
        <NoSetupMessage>Loading composition...</NoSetupMessage>
      </Container>
    );
  }

  const {
    has_active_setup,
    setup_quality,
    active_figure,
    active_fib,
    relevant_overlays = [],
    breakout_logic,
    active_zone,
    setup_summary,
    structure_context,
  } = composition;

  if (!has_active_setup) {
    return (
      <Container data-testid="ta-composition-panel">
        <Header>
          <Title>
            <Layers size={14} />
            Technical Setup
          </Title>
          <QualityBadge $quality="none">No Setup</QualityBadge>
        </Header>
        <NoSetupMessage>
          <Minus size={24} style={{ marginBottom: 8, opacity: 0.5 }} />
          <div>No clear technical setup detected</div>
          <div style={{ fontSize: 11, marginTop: 4, color: '#475569' }}>
            Structure: {structure_context || 'neutral'}
          </div>
        </NoSetupMessage>
      </Container>
    );
  }

  return (
    <Container data-testid="ta-composition-panel">
      <Header>
        <Title>
          <Layers size={14} />
          Technical Setup
        </Title>
        <QualityBadge $quality={setup_quality}>{setup_quality}</QualityBadge>
      </Header>

      <Content>
        {/* Setup Summary */}
        {setup_summary && (
          <SetupSummary data-testid="setup-summary">
            {setup_summary}
          </SetupSummary>
        )}

        {/* Active Figure */}
        {active_figure && (
          <div>
            <SectionTitle>Active Figure</SectionTitle>
            <FigureCard data-testid="active-figure">
              <FigureHeader>
                <FigureName>
                  <DirectionIcon $direction={active_figure.direction}>
                    {active_figure.direction === 'bullish' ? (
                      <TrendingUp size={12} />
                    ) : active_figure.direction === 'bearish' ? (
                      <TrendingDown size={12} />
                    ) : (
                      <Minus size={12} />
                    )}
                  </DirectionIcon>
                  {formatFigureType(active_figure.type)}
                </FigureName>
                <ConfidenceBar title={`${Math.round(active_figure.confidence * 100)}%`}>
                  <ConfidenceFill $confidence={active_figure.confidence} />
                </ConfidenceBar>
              </FigureHeader>
              
              <LevelRow>
                <LevelLabel>
                  <ArrowUpRight size={12} />
                  Breakout
                </LevelLabel>
                <LevelValue $type="breakout">
                  {formatPrice(active_figure.breakout_level)}
                </LevelValue>
              </LevelRow>
              <LevelRow>
                <LevelLabel>
                  <AlertTriangle size={12} />
                  Invalidation
                </LevelLabel>
                <LevelValue $type="invalidation">
                  {formatPrice(active_figure.invalidation_level)}
                </LevelValue>
              </LevelRow>
            </FigureCard>
          </div>
        )}

        {/* Active Fib */}
        {active_fib && (
          <div>
            <SectionTitle>Fibonacci Context</SectionTitle>
            <FibSection data-testid="active-fib">
              <div style={{ fontSize: 12, color: '#fcd34d', marginBottom: 8 }}>
                {active_fib.swing_type?.replace(/_/g, ' ')} — {active_fib.current_position?.replace(/_/g, ' ')}
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap' }}>
                {active_fib.key_levels?.map((level, i) => (
                  <FibLevelChip key={i} $status={level.status}>
                    {level.level} @ {formatPrice(level.price)}
                  </FibLevelChip>
                ))}
              </div>
            </FibSection>
          </div>
        )}

        {/* Relevant Overlays */}
        {relevant_overlays.length > 0 && (
          <div>
            <SectionTitle>Supporting Indicators</SectionTitle>
            <OverlaysRow data-testid="relevant-overlays">
              {relevant_overlays.map((overlay, i) => (
                <OverlayChip key={i}>
                  <Activity size={12} />
                  {overlay.display_name}
                  <ChevronRight size={10} style={{ opacity: 0.5 }} />
                  <OverlayValue>{formatPrice(overlay.current_value)}</OverlayValue>
                </OverlayChip>
              ))}
            </OverlaysRow>
          </div>
        )}

        {/* Breakout Logic */}
        {breakout_logic && (
          <div>
            <SectionTitle>Trade Levels</SectionTitle>
            <BreakoutSection data-testid="breakout-logic">
              <BreakoutCard $type="breakout">
                <BreakoutLabel $type="breakout">
                  {breakout_logic.breakout_type?.replace(/_/g, ' ')}
                </BreakoutLabel>
                <BreakoutPrice $type="breakout">
                  {formatPrice(breakout_logic.breakout_level)}
                </BreakoutPrice>
              </BreakoutCard>
              <BreakoutCard $type="invalidation">
                <BreakoutLabel $type="invalidation">
                  Invalidation ({breakout_logic.risk_pct?.toFixed(1)}%)
                </BreakoutLabel>
                <BreakoutPrice $type="invalidation">
                  {formatPrice(breakout_logic.invalidation_level)}
                </BreakoutPrice>
              </BreakoutCard>
            </BreakoutSection>
          </div>
        )}

        {/* Active Zone */}
        {active_zone && (
          <ActiveZone data-testid="active-zone">
            <Target size={14} />
            <span>{active_zone.type?.replace(/_/g, ' ')}</span>
            <span style={{ fontWeight: 600 }}>
              {formatPrice(active_zone.lower)} — {formatPrice(active_zone.upper)}
            </span>
          </ActiveZone>
        )}
      </Content>
    </Container>
  );
};

export default TACompositionPanel;
