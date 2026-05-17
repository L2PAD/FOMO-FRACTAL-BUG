/**
 * NarrativeSummary — Display market story as text chain
 * ======================================================
 * 
 * Shows: BSL Swept → Bearish Impulse → VALID CHOCH → Supply Zone → SHORT Setup
 */

import React from 'react';
import styled from 'styled-components';

// Helper to check valid chain
function hasValidNarrativeChain(events) {
  const hasSweep = events.some(e => e.type === 'liquidity_sweep');
  const hasDisplacement = events.some(e => e.type === 'displacement');
  const hasCHOCH = events.some(e => e.type === 'choch' && e.isValid);
  const hasPOI = events.some(e => e.type === 'poi');
  return hasSweep && (hasDisplacement || hasCHOCH) && hasPOI;
}

const Container = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: #0f172a;
  border-radius: 8px;
  font-size: 12px;
  margin-top: 8px;
`;

const Label = styled.span`
  color: #64748b;
  font-weight: 500;
  font-size: 11px;
`;

const Chain = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
`;

const Event = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
  color: ${props => props.$color || '#94a3b8'};
`;

const Arrow = styled.span`
  color: #475569;
  font-size: 10px;
`;

const Direction = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 4px;
  font-weight: 600;
  font-size: 11px;
  margin-left: auto;
  background: ${props => props.$bearish ? 'rgba(239, 68, 68, 0.15)' : 'rgba(34, 197, 94, 0.15)'};
  color: ${props => props.$bearish ? '#f87171' : '#4ade80'};
`;

const EVENT_STYLES = {
  liquidity_sweep: { color: '#fb923c' },
  displacement: { color: '#c084fc' },
  choch: { color: '#4ade80' },
  choch_weak: { color: '#fbbf24' },
  choch_fake: { color: '#6b7280' },
  poi: { color: '#60a5fa' },
  entry: { color: '#f87171' },
  entry_long: { color: '#4ade80' },
};

const NarrativeSummary = ({ narrative, decision }) => {
  // Handle both array (from buildNarrative) and object (from renderNarrative)
  const events = Array.isArray(narrative) ? narrative : narrative?.events || [];
  
  if (!events || events.length === 0) {
    return null;
  }

  const hasChain = narrative?.hasChain ?? hasValidNarrativeChain(events);
  const bias = decision?.bias || 'neutral';
  const isBearish = bias === 'bearish';

  const getEventStyle = (event) => {
    if (event.type === 'choch') {
      if (!event.isValid) {
        return event.score >= 0.45 ? EVENT_STYLES.choch_weak : EVENT_STYLES.choch_fake;
      }
    }
    if (event.type === 'entry') {
      return event.subtype === 'long' ? EVENT_STYLES.entry_long : EVENT_STYLES.entry;
    }
    return EVENT_STYLES[event.type] || {};
  };

  const getShortLabel = (event) => {
    switch (event.type) {
      case 'liquidity_sweep':
        return event.subtype === 'buy_side_sweep' ? 'BSL Swept' : 'SSL Swept';
      case 'displacement':
        return event.direction === 'bearish' ? 'Bearish Impulse' : 'Bullish Impulse';
      case 'choch':
        if (event.isValid) return 'VALID CHOCH';
        return event.score >= 0.45 ? 'WEAK CHOCH' : 'FAKE CHOCH';
      case 'poi':
        return event.subtype === 'supply' ? 'Supply Zone' : 'Demand Zone';
      case 'entry':
        return event.subtype === 'short' ? 'SHORT Setup' : 'LONG Setup';
      default:
        return event.label;
    }
  };

  return (
    <Container>
      <Label>Story:</Label>
      <Chain>
        {events.map((event, idx) => {
          const style = getEventStyle(event);
          return (
            <React.Fragment key={idx}>
              <Event $bg={style.bg} $color={style.color}>
                {getShortLabel(event)}
              </Event>
              {idx < events.length - 1 && <Arrow>→</Arrow>}
            </React.Fragment>
          );
        })}
      </Chain>
      <Direction $bearish={isBearish}>
        {isBearish ? '↓ BEARISH' : '↑ BULLISH'}
      </Direction>
    </Container>
  );
};

export default NarrativeSummary;
