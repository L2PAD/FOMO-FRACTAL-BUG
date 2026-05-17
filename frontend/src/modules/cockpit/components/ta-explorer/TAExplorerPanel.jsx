/**
 * TAExplorerPanel.jsx — Unified TA Analysis Panel
 * 
 * Redesigned for user-friendly experience:
 * - All patterns with clickable selection
 * - Clean layer visualization (no JSON)
 * - Trade setup clarity
 * - Full-width responsive layout
 */

import React, { useState } from 'react';
import styled from 'styled-components';
import { Activity, TrendingUp, TrendingDown, Target, Layers, 
         BarChart2, ChevronRight, CheckCircle, XCircle, AlertCircle } from 'lucide-react';

const Container = styled.div`
  display: flex;
  flex-direction: column;
  gap: 0;
  background: #0f172a;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  overflow: hidden;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(15, 23, 42, 0.8);
`;

const Title = styled.h3`
  font-size: 14px;
  font-weight: 700;
  color: #ffffff;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 10px;
`;

const Badge = styled.span`
  font-size: 9px;
  padding: 3px 8px;
  border-radius: 4px;
  background: ${props => props.$type === 'trade' ? 'rgba(34, 197, 94, 0.2)' : 'rgba(59, 130, 246, 0.2)'};
  color: ${props => props.$type === 'trade' ? '#22c55e' : '#60a5fa'};
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const Tabs = styled.div`
  display: flex;
  gap: 2px;
  background: rgba(255, 255, 255, 0.03);
  padding: 4px;
  border-radius: 8px;
`;

const Tab = styled.button`
  padding: 8px 16px;
  font-size: 12px;
  font-weight: 600;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  background: ${props => props.$active ? '#3b82f6' : 'transparent'};
  color: ${props => props.$active ? '#ffffff' : 'rgba(255, 255, 255, 0.6)'};
  display: flex;
  align-items: center;
  gap: 6px;
  
  &:hover {
    background: ${props => props.$active ? '#3b82f6' : 'rgba(255, 255, 255, 0.08)'};
    color: #ffffff;
  }
  
  .count {
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 10px;
    background: ${props => props.$active ? 'rgba(255, 255, 255, 0.2)' : 'rgba(255, 255, 255, 0.1)'};
  }
`;

const Content = styled.div`
  padding: 16px 20px;
  min-height: 180px;
`;

const NoData = styled.div`
  color: rgba(255, 255, 255, 0.4);
  font-size: 13px;
  text-align: center;
  padding: 40px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
`;

// ════════════════════════════════════════════════════════════════
// PATTERNS TAB
// ════════════════════════════════════════════════════════════════

const PatternsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
`;

const PatternCard = styled.div`
  background: ${props => props.$selected ? 'rgba(59, 130, 246, 0.15)' : 'rgba(255, 255, 255, 0.03)'};
  border: 1px solid ${props => props.$selected ? 'rgba(59, 130, 246, 0.4)' : 'rgba(255, 255, 255, 0.08)'};
  border-radius: 10px;
  padding: 14px 16px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    background: rgba(59, 130, 246, 0.1);
    border-color: rgba(59, 130, 246, 0.3);
  }
`;

const PatternHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
`;

const PatternName = styled.div`
  font-size: 14px;
  font-weight: 600;
  color: #ffffff;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const PatternRank = styled.span`
  font-size: 10px;
  color: rgba(255, 255, 255, 0.4);
  background: rgba(255, 255, 255, 0.05);
  padding: 2px 6px;
  border-radius: 4px;
`;

const ScoreBadge = styled.div`
  font-size: 16px;
  font-weight: 700;
  color: ${props => props.$score >= 70 ? '#22c55e' : props.$score >= 50 ? '#eab308' : '#ef4444'};
`;

const PatternMeta = styled.div`
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
`;

const MetaBadge = styled.span`
  font-size: 10px;
  padding: 3px 8px;
  border-radius: 4px;
  font-weight: 600;
  background: ${props => {
    if (props.$type === 'bullish') return 'rgba(34, 197, 94, 0.15)';
    if (props.$type === 'bearish') return 'rgba(239, 68, 68, 0.15)';
    if (props.$type === 'strict') return 'rgba(34, 197, 94, 0.15)';
    if (props.$type === 'regime') return 'rgba(59, 130, 246, 0.15)';
    return 'rgba(255, 255, 255, 0.08)';
  }};
  color: ${props => {
    if (props.$type === 'bullish') return '#22c55e';
    if (props.$type === 'bearish') return '#ef4444';
    if (props.$type === 'strict') return '#22c55e';
    if (props.$type === 'regime') return '#60a5fa';
    return 'rgba(255, 255, 255, 0.6)';
  }};
`;

// ════════════════════════════════════════════════════════════════
// LAYERS TAB - User Friendly Version
// ════════════════════════════════════════════════════════════════

const LayersGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
`;

const LayerCard = styled.div`
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
`;

const LayerHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const LayerLabel = styled.div`
  font-size: 10px;
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
`;

const LayerNum = styled.span`
  font-size: 9px;
  color: rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.05);
  padding: 2px 5px;
  border-radius: 3px;
`;

const LayerValue = styled.div`
  font-size: 14px;
  font-weight: 600;
  color: ${props => {
    if (props.$type === 'bullish') return '#22c55e';
    if (props.$type === 'bearish') return '#ef4444';
    return '#ffffff';
  }};
  display: flex;
  align-items: center;
  gap: 6px;
`;

const LayerDetail = styled.div`
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
`;

// ════════════════════════════════════════════════════════════════
// TRADE TAB
// ════════════════════════════════════════════════════════════════

const TradeCard = styled.div`
  background: ${props => props.$available ? 'rgba(34, 197, 94, 0.08)' : 'rgba(239, 68, 68, 0.08)'};
  border: 1px solid ${props => props.$available ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)'};
  border-radius: 12px;
  padding: 20px;
`;

const TradeStatus = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
`;

const TradeIcon = styled.div`
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: ${props => props.$available ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)'};
  color: ${props => props.$available ? '#22c55e' : '#ef4444'};
`;

const TradeTitle = styled.div`
  font-size: 18px;
  font-weight: 700;
  color: ${props => props.$available ? '#22c55e' : '#ef4444'};
`;

const TradeSubtitle = styled.div`
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  margin-top: 2px;
`;

const TradeLevels = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
`;

const LevelBox = styled.div`
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  padding: 12px;
  text-align: center;
`;

const LevelLabel = styled.div`
  font-size: 10px;
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
  margin-bottom: 4px;
`;

const LevelValue = styled.div`
  font-size: 15px;
  font-weight: 700;
  color: ${props => props.$type === 'entry' ? '#60a5fa' : props.$type === 'stop' ? '#ef4444' : '#22c55e'};
`;

// ════════════════════════════════════════════════════════════════
// LAYER CONFIG
// ════════════════════════════════════════════════════════════════

const LAYER_CONFIG = {
  layer_1_structure: { 
    name: 'Market Structure', 
    icon: TrendingUp,
    getValue: (d) => d?.trend || '-',
    getDetail: (d) => d?.swing_status || null,
    getType: (d) => d?.trend?.toLowerCase()?.includes('bullish') ? 'bullish' : 
                    d?.trend?.toLowerCase()?.includes('bearish') ? 'bearish' : 'neutral'
  },
  layer_2_impulse: { 
    name: 'Impulse', 
    icon: Activity,
    getValue: (d) => d?.direction || '-',
    getDetail: (d) => {
      if (!d?.strength) return null;
      // Handle string or number strength values
      if (typeof d.strength === 'string') return `Strength: ${d.strength}`;
      if (typeof d.strength === 'number' && !isNaN(d.strength)) {
        return `Strength: ${(d.strength * 100).toFixed(0)}%`;
      }
      return null;
    },
    getType: (d) => d?.direction?.toLowerCase()?.includes('bullish') ? 'bullish' : 
                    d?.direction?.toLowerCase()?.includes('bearish') ? 'bearish' : 'neutral'
  },
  layer_3_regime: { 
    name: 'Market Regime', 
    icon: BarChart2,
    getValue: (d) => d?.regime || '-',
    getDetail: (d) => d?.volatility ? `Volatility: ${d.volatility}` : null,
    getType: () => 'neutral'
  },
  layer_4_range: { 
    name: 'Range Status', 
    icon: Layers,
    getValue: (d) => {
      if (!d) return 'Trending';
      return d?.status || (d?.in_range ? 'In Range' : 'Trending');
    },
    getDetail: (d) => {
      if (!d || !d?.range_width) return null;
      return `Width: $${Number(d.range_width).toLocaleString()}`;
    },
    getType: () => 'neutral'
  },
  layer_5_pattern: { 
    name: 'Pattern', 
    icon: Target,
    getValue: (d) => {
      const type = d?.type;
      if (!type) return '-';
      return type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    },
    getDetail: (d) => d?.confidence ? `Confidence: ${(d.confidence * 100).toFixed(0)}%` : null,
    getType: (d) => d?.direction?.toLowerCase()?.includes('bullish') ? 'bullish' : 
                    d?.direction?.toLowerCase()?.includes('bearish') ? 'bearish' : 'neutral'
  },
  layer_6_confluence: { 
    name: 'Confluence', 
    icon: Layers,
    getValue: (d) => d?.count !== undefined ? `${d.count} Factors` : '-',
    getDetail: (d) => d?.factors?.slice(0, 2).join(', ') || null,
    getType: (d) => d?.count >= 3 ? 'bullish' : 'neutral'
  },
  layer_7_probability: { 
    name: 'Probability', 
    icon: BarChart2,
    getValue: (d) => {
      if (!d) return '-';
      // Show bullish/bearish percentage
      const bullish = d?.bullish;
      const bearish = d?.bearish;
      if (typeof bullish === 'number') return `${bullish}%`;
      if (d?.win_rate) return `${((d.win_rate) * 100).toFixed(0)}%`;
      return '-';
    },
    getDetail: (d) => d?.dominant_bias || null,
    getType: (d) => d?.dominant_bias?.toLowerCase()?.includes('bullish') ? 'bullish' : 
                    d?.dominant_bias?.toLowerCase()?.includes('bearish') ? 'bearish' : 'neutral'
  },
  layer_8_scenarios: { 
    name: 'Scenarios', 
    icon: Target,
    getValue: (d) => {
      const up = d?.break_up?.target;
      const down = d?.break_down?.target;
      if (up && down) return `↑$${up.toFixed(0)} / ↓$${down.toFixed(0)}`;
      return '-';
    },
    getDetail: () => null,
    getType: () => 'neutral'
  },
  layer_9_timing: { 
    name: 'Timing', 
    icon: Activity,
    getValue: (d) => {
      if (!d) return '-';
      const phase = d?.phase || d?.market_phase;
      if (!phase || phase === 'unknown') return 'Waiting';
      return phase.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    },
    getDetail: (d) => {
      if (d?.compression) return 'Compression detected';
      return d?.recommendation || null;
    },
    getType: () => 'neutral'
  },
  layer_10_narrative: { 
    name: 'Narrative', 
    icon: Activity,
    getValue: (d) => {
      // Handle string or object narrative
      if (typeof d === 'string') {
        return d.length > 50 ? d.substring(0, 50) + '...' : d;
      }
      return d?.short || d?.headline || '-';
    },
    getDetail: (d) => {
      if (typeof d === 'string' && d.length > 50) return d;
      return null;
    },
    getType: () => 'neutral'
  },
};

// ════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ════════════════════════════════════════════════════════════════

export default function TAExplorerPanel({ data, onPatternSelect, selectedPatternIndex = 0 }) {
  const [activeTab, setActiveTab] = useState('patterns');
  const [localSelectedPattern, setLocalSelectedPattern] = useState(selectedPatternIndex);
  
  if (!data) {
    return (
      <Container data-testid="ta-explorer-panel">
        <Header>
          <Title>
            <Activity size={16} />
            TA Explorer
          </Title>
        </Header>
        <NoData>
          <Activity size={32} color="rgba(255, 255, 255, 0.3)" />
          Loading analysis...
        </NoData>
      </Container>
    );
  }
  
  const { dominant, patterns_all, patterns_rejected, ta_layers, trade_setup } = data;
  const isTradeAvailable = trade_setup?.available === true;
  
  const handlePatternClick = (index) => {
    setLocalSelectedPattern(index);
    if (onPatternSelect) {
      onPatternSelect(patterns_all[index], index);
    }
  };
  
  const formatType = (type) => {
    if (!type) return '-';
    return type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  };
  
  // ════════════════════════════════════════════════════════════════
  // RENDER PATTERNS TAB
  // ════════════════════════════════════════════════════════════════
  const renderPatternsTab = () => {
    if (!patterns_all?.length) {
      return (
        <NoData>
          <Target size={32} color="rgba(255, 255, 255, 0.3)" />
          No patterns detected
        </NoData>
      );
    }
    
    return (
      <PatternsGrid>
        {patterns_all.map((pattern, index) => {
          const score = pattern.final_score ?? (pattern.score <= 1 ? pattern.score * 100 : pattern.score);
          const isSelected = localSelectedPattern === index;
          
          return (
            <PatternCard 
              key={index} 
              $selected={isSelected}
              onClick={() => handlePatternClick(index)}
              data-testid={`pattern-card-${index}`}
            >
              <PatternHeader>
                <PatternName>
                  <PatternRank>#{index + 1}</PatternRank>
                  {formatType(pattern.type)}
                </PatternName>
                <ScoreBadge $score={score}>{score.toFixed(0)}%</ScoreBadge>
              </PatternHeader>
              
              <PatternMeta>
                <MetaBadge $type={pattern.bias}>{pattern.bias || 'neutral'}</MetaBadge>
                <MetaBadge $type={pattern.mode}>{pattern.mode || 'standard'}</MetaBadge>
                <MetaBadge>{pattern.stage || 'forming'}</MetaBadge>
              </PatternMeta>
            </PatternCard>
          );
        })}
      </PatternsGrid>
    );
  };
  
  // ════════════════════════════════════════════════════════════════
  // RENDER LAYERS TAB
  // ════════════════════════════════════════════════════════════════
  const renderLayersTab = () => {
    if (!ta_layers || Object.keys(ta_layers).length === 0) {
      return (
        <NoData>
          <Layers size={32} color="rgba(255, 255, 255, 0.3)" />
          No layer data available
        </NoData>
      );
    }
    
    const sortedLayers = Object.entries(ta_layers).sort(([a], [b]) => {
      const numA = parseInt(a.split('_')[1]) || 0;
      const numB = parseInt(b.split('_')[1]) || 0;
      return numA - numB;
    });
    
    return (
      <LayersGrid>
        {sortedLayers.map(([key, layerData]) => {
          const config = LAYER_CONFIG[key];
          if (!config) return null;
          
          const layerNum = key.split('_')[1];
          const value = config.getValue(layerData);
          const detail = config.getDetail(layerData);
          const valueType = config.getType(layerData);
          const Icon = config.icon;
          
          // Extract just the number from layer key (e.g., "layer_1_structure" -> "1")
          const layerNumber = key.match(/layer_(\d+)/)?.[1] || layerNum;
          
          return (
            <LayerCard key={key} data-testid={`layer-${layerNumber}`}>
              <LayerHeader>
                <LayerLabel>{config.name}</LayerLabel>
                <LayerNum>L{layerNum}</LayerNum>
              </LayerHeader>
              <LayerValue $type={valueType}>
                <Icon size={14} />
                {value}
              </LayerValue>
              {detail && <LayerDetail>{detail}</LayerDetail>}
            </LayerCard>
          );
        })}
      </LayersGrid>
    );
  };
  
  // ════════════════════════════════════════════════════════════════
  // RENDER TRADE TAB
  // ════════════════════════════════════════════════════════════════
  const renderTradeTab = () => {
    return (
      <TradeCard $available={isTradeAvailable} data-testid="trade-card">
        <TradeStatus>
          <TradeIcon $available={isTradeAvailable}>
            {isTradeAvailable ? <CheckCircle size={24} /> : <XCircle size={24} />}
          </TradeIcon>
          <div>
            <TradeTitle $available={isTradeAvailable}>
              {isTradeAvailable ? 'TRADE AVAILABLE' : 'NO TRADE'}
            </TradeTitle>
            <TradeSubtitle>
              {trade_setup?.reason || (isTradeAvailable ? 'Setup conditions met' : 'Waiting for valid setup')}
            </TradeSubtitle>
          </div>
        </TradeStatus>
        
        {isTradeAvailable && trade_setup?.levels && (
          <TradeLevels>
            <LevelBox>
              <LevelLabel>Entry</LevelLabel>
              <LevelValue $type="entry">
                ${Number(trade_setup.levels.entry || 0).toLocaleString()}
              </LevelValue>
            </LevelBox>
            <LevelBox>
              <LevelLabel>Stop Loss</LevelLabel>
              <LevelValue $type="stop">
                ${Number(trade_setup.levels.stop || 0).toLocaleString()}
              </LevelValue>
            </LevelBox>
            <LevelBox>
              <LevelLabel>Target</LevelLabel>
              <LevelValue $type="target">
                ${Number(trade_setup.levels.target || 0).toLocaleString()}
              </LevelValue>
            </LevelBox>
          </TradeLevels>
        )}
        
        {!isTradeAvailable && (
          <div style={{ 
            marginTop: 16, 
            padding: 12, 
            background: 'rgba(255, 255, 255, 0.03)', 
            borderRadius: 8,
            fontSize: 12,
            color: 'rgba(255, 255, 255, 0.6)',
            display: 'flex',
            alignItems: 'center',
            gap: 8
          }}>
            <AlertCircle size={16} />
            {trade_setup?.narrative || 'Market conditions do not meet trade criteria'}
          </div>
        )}
      </TradeCard>
    );
  };
  
  // ════════════════════════════════════════════════════════════════
  // RENDER CONTENT BY TAB
  // ════════════════════════════════════════════════════════════════
  const renderContent = () => {
    switch (activeTab) {
      case 'patterns':
        return renderPatternsTab();
      case 'layers':
        return renderLayersTab();
      case 'trade':
        return renderTradeTab();
      default:
        return null;
    }
  };
  
  return (
    <Container data-testid="ta-explorer-panel">
      <Header>
        <Title>
          <Activity size={16} />
          TA Explorer
          {isTradeAvailable && <Badge $type="trade">TRADE</Badge>}
        </Title>
        
        <Tabs>
          <Tab 
            $active={activeTab === 'patterns'} 
            onClick={() => setActiveTab('patterns')}
            data-testid="tab-patterns"
          >
            Patterns
            <span className="count">{patterns_all?.length || 0}</span>
          </Tab>
          <Tab 
            $active={activeTab === 'layers'} 
            onClick={() => setActiveTab('layers')}
            data-testid="tab-layers"
          >
            Analysis
            <span className="count">10</span>
          </Tab>
          <Tab 
            $active={activeTab === 'trade'} 
            onClick={() => setActiveTab('trade')}
            data-testid="tab-trade"
            style={{ 
              color: isTradeAvailable ? '#22c55e' : undefined,
            }}
          >
            {isTradeAvailable ? 'Trade' : 'No Trade'}
          </Tab>
        </Tabs>
      </Header>
      
      <Content>
        {renderContent()}
      </Content>
    </Container>
  );
}
