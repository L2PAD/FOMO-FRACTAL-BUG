/**
 * SetupOverlay — TradingView-style Trade Setup Visualization
 * ===========================================================
 * 
 * Visual Terminal with:
 * - Entry Zone (semi-transparent band)
 * - Entry Line (solid)
 * - Stop Loss (red dashed)
 * - Take Profit Targets (green lines TP1/TP2)
 * - Risk/Reward visible on chart
 * - Setup Badge with full details
 * 
 * DESIGN: Gray theme like Fibonacci overlay, Gilroy font
 */

import React from 'react';
import styled from 'styled-components';

// ════════════════════════════════════════════════════════════════
// STYLED COMPONENTS — GRAY THEME (like Fibonacci)
// ════════════════════════════════════════════════════════════════

const OverlayContainer = styled.div`
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 100;
`;

const SetupBadge = styled.div`
  position: absolute;
  top: 12px;
  right: 12px;
  background: rgba(55, 65, 81, 0.95);
  color: white;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 12px;
  font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
  border: 1px solid rgba(100, 116, 139, 0.3);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  pointer-events: auto;
  min-width: 150px;
  backdrop-filter: blur(8px);
`;

const SetupTitle = styled.div`
  font-weight: 700;
  font-size: 15px;
  font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: ${props => props.$isLong ? '#4ade80' : props.$isShort ? '#f87171' : '#94a3b8'};
`;

const SetupRow = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
  opacity: 0.95;
  margin: 5px 0;
`;

const SetupLabel = styled.span`
  opacity: 0.7;
  color: #d1d5db;
  font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
`;

const SetupValue = styled.span`
  font-weight: 600;
  font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
`;

const RRBadge = styled.span`
  background: rgba(34, 197, 94, 0.25);
  color: #86efac;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  margin-left: 8px;
  font-weight: 600;
  font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
`;

const NoTradeBadge = styled(SetupBadge)`
  background: rgba(55, 65, 81, 0.9);
  border-color: rgba(100, 116, 139, 0.4);
`;

// ════════════════════════════════════════════════════════════════
// HELPER: Normalize price to chart percentage
// ════════════════════════════════════════════════════════════════

function normalize(price, candles) {
  if (!candles?.length || !price) return 50;
  
  const highs = candles.map(c => c.high);
  const lows = candles.map(c => c.low);
  const min = Math.min(...lows);
  const max = Math.max(...highs);
  
  if (max === min) return 50;
  
  // Return percentage from bottom (0% = min, 100% = max)
  return ((price - min) / (max - min)) * 100;
}

// ════════════════════════════════════════════════════════════════
// COMPONENT: Line (ENTRY, STOP, TP lines)
// ════════════════════════════════════════════════════════════════

function Line({ candles, price, color, label, dashed, thick }) {
  const bottomPct = normalize(price, candles);
  
  // Skip if out of visible range
  if (bottomPct < -20 || bottomPct > 120) return null;
  
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: `${bottomPct}%`,
        borderTop: `${thick ? 2 : 1}px ${dashed ? 'dashed' : 'solid'} ${color}`,
        pointerEvents: 'none',
      }}
    >
      <span
        style={{
          position: 'absolute',
          right: 8,
          top: '50%',
          transform: 'translateY(-50%)',
          color: color,
          background: 'rgba(55, 65, 81, 0.85)',
          padding: '2px 8px',
          borderRadius: '3px',
          fontSize: '10px',
          fontWeight: 600,
          fontFamily: "'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif",
          whiteSpace: 'nowrap',
          backdropFilter: 'blur(4px)',
        }}
      >
        {label} ${price?.toFixed(0)}
      </span>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════
// COMPONENT: Zone (Entry Zone Band)
// ════════════════════════════════════════════════════════════════

function Zone({ candles, low, high, color }) {
  const bottomPct = normalize(low, candles);
  const topPct = normalize(high, candles);
  const heightPct = Math.max(0.5, topPct - bottomPct);
  
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: `${bottomPct}%`,
        height: `${heightPct}%`,
        background: color,
        pointerEvents: 'none',
      }}
    >
      {/* Entry Zone Label */}
      <span
        style={{
          position: 'absolute',
          left: 8,
          top: '50%',
          transform: 'translateY(-50%)',
          color: 'rgba(255,255,255,0.7)',
          background: 'rgba(0,0,0,0.5)',
          padding: '2px 8px',
          borderRadius: '3px',
          fontSize: '9px',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
        }}
      >
        Entry Zone
      </span>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ════════════════════════════════════════════════════════════════

export default function SetupOverlay({ candles, setup }) {
  // No setup data or invalid setup — don't show anything
  // NO TRADE is now shown via unified NoTradeIndicator in RenderPlanOverlay
  if (!setup || !setup.valid) return null;
  
  // Valid setup — full TradingView-style visualization
  const isLong = setup.type === 'LONG';
  
  const entry = setup.entry;
  const stop = setup.stop;
  const tp1 = setup.tp1;
  const tp2 = setup.tp2;
  
  // Entry zone: +/- 0.3% around entry
  const zoneLow = setup.entryZone?.low ?? entry * 0.997;
  const zoneHigh = setup.entryZone?.high ?? entry * 1.003;
  
  // Calculate Risk/Reward ratios
  const risk = Math.abs(entry - stop);
  const reward1 = Math.abs(tp1 - entry);
  const reward2 = Math.abs(tp2 - entry);
  const rr1 = risk > 0 ? (reward1 / risk).toFixed(1) : '—';
  const rr2 = risk > 0 ? (reward2 / risk).toFixed(1) : '—';
  
  return (
    <OverlayContainer>
      {/* ENTRY ZONE */}
      <Zone
        candles={candles}
        low={zoneLow}
        high={zoneHigh}
        color={isLong ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)'}
      />
      
      {/* ENTRY LINE */}
      <Line
        candles={candles}
        price={entry}
        color={isLong ? '#22c55e' : '#ef4444'}
        label="ENTRY"
        thick={true}
      />
      
      {/* STOP LINE */}
      <Line
        candles={candles}
        price={stop}
        color="#ef4444"
        label="STOP"
        dashed={true}
        thick={true}
      />
      
      {/* TP1 LINE */}
      <Line
        candles={candles}
        price={tp1}
        color="#22c55e"
        label="TP1"
      />
      
      {/* TP2 LINE */}
      <Line
        candles={candles}
        price={tp2}
        color="#16a34a"
        label="TP2"
      />
      
      {/* SETUP BADGE */}
      <SetupBadge>
        <SetupTitle $isLong={isLong} $isShort={!isLong}>
          <span style={{ fontSize: '16px' }}>{isLong ? '↑' : '↓'}</span>
          {setup.type}
        </SetupTitle>
        
        <SetupRow>
          <SetupLabel>Entry:</SetupLabel>
          <SetupValue style={{ color: isLong ? '#86efac' : '#fca5a5' }}>
            ${entry?.toFixed(0)}
          </SetupValue>
        </SetupRow>
        
        <SetupRow>
          <SetupLabel>Stop:</SetupLabel>
          <SetupValue style={{ color: '#fca5a5' }}>
            ${stop?.toFixed(0)}
          </SetupValue>
        </SetupRow>
        
        <SetupRow>
          <SetupLabel>TP1:</SetupLabel>
          <SetupValue style={{ color: '#86efac' }}>
            ${tp1?.toFixed(0)}
            <RRBadge>{rr1}R</RRBadge>
          </SetupValue>
        </SetupRow>
        
        <SetupRow>
          <SetupLabel>TP2:</SetupLabel>
          <SetupValue style={{ color: '#4ade80' }}>
            ${tp2?.toFixed(0)}
            <RRBadge>{rr2}R</RRBadge>
          </SetupValue>
        </SetupRow>
        
        {/* Pattern/Reason if available */}
        {setup.pattern && (
          <SetupRow style={{ marginTop: '8px', borderTop: '1px solid #374151', paddingTop: '8px' }}>
            <SetupLabel>Pattern:</SetupLabel>
            <SetupValue style={{ color: '#a5b4fc', fontSize: '10px' }}>
              {setup.pattern}
            </SetupValue>
          </SetupRow>
        )}
        
        {/* Confidence if available */}
        {setup.confidence && (
          <SetupRow>
            <SetupLabel>Confidence:</SetupLabel>
            <SetupValue style={{ color: '#fbbf24' }}>
              {setup.confidence}%
            </SetupValue>
          </SetupRow>
        )}
      </SetupBadge>
    </OverlayContainer>
  );
}
