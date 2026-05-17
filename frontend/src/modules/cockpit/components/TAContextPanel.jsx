/**
 * TAContextPanel — Unified TA Context Display
 * =============================================
 * Shows how ALL TA sources contributed to the decision.
 * 
 * Displays:
 * - Aggregated bias/score/confidence
 * - Top drivers (key factors)
 * - All contributions grouped by source
 * - Hidden but used (invisible on chart, but in the brain)
 */

import React, { useState } from 'react';
import styled from 'styled-components';
import { Brain, ChevronDown, ChevronUp, Eye, EyeOff, Activity, TrendingUp, TrendingDown, Minus } from 'lucide-react';

const Panel = styled.div`
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  cursor: pointer;
  user-select: none;
  border-bottom: ${({ $expanded }) => $expanded ? '1px solid #f1f5f9' : 'none'};

  &:hover { background: #fafbfc; }
`;

const HeaderLeft = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
`;

const Title = styled.span`
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: 0.3px;
`;

const Badge = styled.span`
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 10px;
  background: ${({ $type }) => 
    $type === 'bullish' ? '#dcfce7' : 
    $type === 'bearish' ? '#fee2e2' : '#f1f5f9'};
  color: ${({ $type }) => 
    $type === 'bullish' ? '#16a34a' : 
    $type === 'bearish' ? '#dc2626' : '#64748b'};
  text-transform: uppercase;
`;

const SourceCount = styled.span`
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
`;

const Content = styled.div`
  padding: 14px 18px;
`;

const SummaryRow = styled.div`
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
`;

const SummaryStat = styled.div`
  text-align: center;
  padding: 10px 8px;
  background: #f8fafc;
  border-radius: 8px;

  .label { font-size: 10px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; }
  .value { font-size: 16px; font-weight: 800; margin-top: 4px; color: ${({ $color }) => $color || '#0f172a'}; }
`;

const SectionTitle = styled.div`
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  margin: 14px 0 8px 0;
  display: flex;
  align-items: center;
  gap: 6px;
`;

const DriverList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;
`;

const DriverRow = styled.div`
  display: grid;
  grid-template-columns: 24px 1fr 60px 60px 70px;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  background: ${({ $idx }) => $idx % 2 === 0 ? '#f8fafc' : '#ffffff'};
  font-size: 12px;

  .icon { display: flex; align-items: center; justify-content: center; }
  .name { font-weight: 600; color: #0f172a; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .signal { font-weight: 700; font-size: 11px; text-align: center; }
  .score { font-weight: 600; font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif; text-align: right; }
  .impact { font-weight: 700; font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif; text-align: right; }
`;

const ContribGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 6px;
`;

const ContribCard = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  background: #f8fafc;
  border-left: 3px solid ${({ $signal }) => 
    $signal === 'bullish' ? '#22c55e' : 
    $signal === 'bearish' ? '#ef4444' : '#cbd5e1'};
  font-size: 11px;

  .name { font-weight: 600; color: #334155; flex: 1; }
  .score { font-weight: 700; font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif; font-size: 10px;
    color: ${({ $signal }) => 
      $signal === 'bullish' ? '#16a34a' : 
      $signal === 'bearish' ? '#dc2626' : '#94a3b8'};
  }
`;

const HiddenList = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
`;

const HiddenTag = styled.span`
  font-size: 10px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 4px;
  background: #fef3c7;
  color: #92400e;
`;

const ToggleBtn = styled.button`
  font-size: 11px;
  font-weight: 600;
  color: #3b82f6;
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px 0;
  &:hover { text-decoration: underline; }
`;

const SignalIcon = ({ signal, size = 14 }) => {
  if (signal === 'bullish') return <TrendingUp size={size} color="#16a34a" />;
  if (signal === 'bearish') return <TrendingDown size={size} color="#dc2626" />;
  return <Minus size={size} color="#94a3b8" />;
};

const TAContextPanel = ({ taContext }) => {
  const [expanded, setExpanded] = useState(false);
  const [showAll, setShowAll] = useState(false);

  if (!taContext) return null;

  const { summary, indicators, top_drivers = [], all_contributions = [], hidden_but_used = [], rendered_default = [] } = taContext;
  if (!summary) return null;

  const scoreColor = summary.aggregated_bias === 'bullish' ? '#16a34a' : summary.aggregated_bias === 'bearish' ? '#dc2626' : '#64748b';

  // Group contributions by source
  const grouped = {};
  all_contributions.forEach(c => {
    const src = c.source;
    if (!grouped[src]) grouped[src] = [];
    grouped[src].push(c);
  });

  const visibleContribs = showAll ? all_contributions : all_contributions.filter(c => c.score !== 0);

  return (
    <Panel data-testid="ta-context-panel">
      <Header $expanded={expanded} onClick={() => setExpanded(!expanded)}>
        <HeaderLeft>
          <Brain size={16} color="#6366f1" />
          <Title>TA Brain</Title>
          <Badge $type={summary.aggregated_bias} data-testid="ta-bias-badge">{summary.aggregated_bias}</Badge>
          <SourceCount>{summary.total_sources} sources | {summary.active_sources} active</SourceCount>
        </HeaderLeft>
        {expanded ? <ChevronUp size={16} color="#94a3b8" /> : <ChevronDown size={16} color="#94a3b8" />}
      </Header>

      {expanded && (
        <Content>
          {/* Summary stats */}
          <SummaryRow>
            <SummaryStat $color={scoreColor}>
              <div className="label">Score</div>
              <div className="value" data-testid="ta-score">{summary.aggregated_score > 0 ? '+' : ''}{summary.aggregated_score.toFixed(3)}</div>
            </SummaryStat>
            <SummaryStat>
              <div className="label">Confidence</div>
              <div className="value" data-testid="ta-confidence">{(summary.aggregated_confidence * 100).toFixed(0)}%</div>
            </SummaryStat>
            <SummaryStat $color="#16a34a">
              <div className="label">Bullish</div>
              <div className="value">{indicators?.bullish || 0}</div>
            </SummaryStat>
            <SummaryStat $color="#dc2626">
              <div className="label">Bearish</div>
              <div className="value">{indicators?.bearish || 0}</div>
            </SummaryStat>
          </SummaryRow>

          {/* Top Drivers */}
          <SectionTitle><Activity size={12} /> Top Drivers</SectionTitle>
          <DriverList data-testid="ta-top-drivers">
            {top_drivers.slice(0, 7).map((d, i) => (
              <DriverRow key={i} $idx={i}>
                <div className="icon"><SignalIcon signal={d.signal} size={12} /></div>
                <div className="name">{d.name}</div>
                <div className="signal" style={{ color: d.signal === 'bullish' ? '#16a34a' : d.signal === 'bearish' ? '#dc2626' : '#94a3b8' }}>{d.signal}</div>
                <div className="score" style={{ color: d.score > 0 ? '#16a34a' : d.score < 0 ? '#dc2626' : '#94a3b8' }}>{d.score > 0 ? '+' : ''}{d.score.toFixed(3)}</div>
                <div className="impact" style={{ color: '#6366f1' }}>{(d.impact * 100).toFixed(1)}%</div>
              </DriverRow>
            ))}
          </DriverList>

          {/* All Contributions */}
          <SectionTitle>
            <Eye size={12} /> All Contributions ({all_contributions.length})
            <ToggleBtn onClick={() => setShowAll(!showAll)}>
              {showAll ? 'Active only' : 'Show all'}
            </ToggleBtn>
          </SectionTitle>
          <ContribGrid data-testid="ta-all-contributions">
            {visibleContribs.map((c, i) => (
              <ContribCard key={i} $signal={c.signal}>
                <span className="name">{c.name}</span>
                <span className="score">{c.score > 0 ? '+' : ''}{c.score.toFixed(2)}</span>
              </ContribCard>
            ))}
          </ContribGrid>

          {/* Hidden but used */}
          {hidden_but_used.length > 0 && (
            <>
              <SectionTitle><EyeOff size={12} /> Hidden But Used ({hidden_but_used.length})</SectionTitle>
              <HiddenList data-testid="ta-hidden-but-used">
                {hidden_but_used.map((id, i) => (
                  <HiddenTag key={i}>{id}</HiddenTag>
                ))}
              </HiddenList>
            </>
          )}
        </Content>
      )}
    </Panel>
  );
};

export default TAContextPanel;
