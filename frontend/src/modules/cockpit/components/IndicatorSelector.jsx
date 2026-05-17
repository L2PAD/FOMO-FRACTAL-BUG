/**
 * IndicatorSelector Component
 * ===========================
 * Toggle overlays and panes on/off.
 * 
 * Rules:
 * - Max 2 overlays at a time
 * - Max 2 lower panes at a time
 * - Default presets: Trend, Momentum, Volatility
 */

import React, { useState, useCallback } from 'react';
import styled from 'styled-components';
import { ChevronDown, ChevronUp, TrendingUp, Activity, BarChart3, Layers } from 'lucide-react';

// ============================================
// STYLED COMPONENTS
// ============================================

const SelectorContainer = styled.div`
  position: relative;
`;

const ToggleButton = styled.button`
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 10px;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: #64748b;
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;      /* UI FIX 2026-04-30: "Indicators (4)" must stay on one line */
  flex-shrink: 0;           /* UI FIX 2026-04-30 */
  
  &:hover {
    color: #0f172a;
    background: rgba(15, 23, 42, 0.05);
  }
  
  svg {
    width: 13px;
    height: 13px;
    flex-shrink: 0;
  }
`;

const Dropdown = styled.div`
  position: absolute;
  bottom: 100%;
  left: 0;
  margin-bottom: 8px;
  width: 320px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 -10px 40px rgba(0, 0, 0, 0.15);
  z-index: 1000;
  overflow: hidden;
`;

const Section = styled.div`
  padding: 12px 16px;
  border-bottom: 1px solid #eef1f5;
  
  &:last-child {
    border-bottom: none;
  }
  
  .section-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
    
    svg {
      width: 16px;
      height: 16px;
      color: #64748b;
    }
    
    .title {
      font-size: 11px;
      font-weight: 600;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    
    .count {
      margin-left: auto;
      font-size: 10px;
      background: rgba(100, 116, 139, 0.1);
      padding: 2px 6px;
      border-radius: 4px;
      color: #64748b;
    }
    
    .limit-warning {
      margin-left: auto;
      font-size: 10px;
      background: rgba(239, 68, 68, 0.1);
      padding: 2px 6px;
      border-radius: 4px;
      color: #ef4444;
    }
  }
`;

const OptionGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
`;

const Option = styled.button`
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 8px 6px;
  background: ${({ $active }) => $active ? 'rgba(59, 130, 246, 0.1)' : '#f8fafc'};
  border: 1px solid ${({ $active }) => $active ? '#3b82f6' : '#e2e8f0'};
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover:not(:disabled) {
    background: rgba(59, 130, 246, 0.05);
    border-color: #94a3b8;
  }
  
  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  
  .name {
    font-size: 10px;
    font-weight: 600;
    color: ${({ $active }) => $active ? '#3b82f6' : '#475569'};
  }
  
  .indicator {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: ${({ $active }) => $active ? '#3b82f6' : 'transparent'};
  }
`;

const PresetBar = styled.div`
  display: flex;
  gap: 6px;
  padding: 12px 16px;
  background: #f8fafc;
  border-bottom: 1px solid #eef1f5;
`;

const PresetButton = styled.button`
  flex: 1;
  padding: 6px 10px;
  background: ${({ $active }) => $active ? '#3b82f6' : '#ffffff'};
  border: 1px solid ${({ $active }) => $active ? '#3b82f6' : '#e2e8f0'};
  border-radius: 6px;
  font-size: 10px;
  font-weight: 600;
  color: ${({ $active }) => $active ? '#ffffff' : '#475569'};
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    background: ${({ $active }) => $active ? '#2563eb' : '#f1f5f9'};
  }
`;

// ============================================
// CONSTANTS
// ============================================

const OVERLAY_OPTIONS = [
  { id: 'ema_20', name: 'EMA 20', group: 'ema' },
  { id: 'ema_50', name: 'EMA 50', group: 'ema' },
  { id: 'ema_200', name: 'EMA 200', group: 'ema' },
  { id: 'bollinger_bands', name: 'BB', group: 'bb' },
  { id: 'vwap', name: 'VWAP', group: 'vwap' },
];

const PANE_OPTIONS = [
  { id: 'rsi', name: 'RSI', group: 'oscillator' },
  { id: 'macd', name: 'MACD', group: 'momentum' },
  { id: 'stochastic', name: 'Stoch', group: 'oscillator' },
  { id: 'obv', name: 'OBV', group: 'volume' },
  { id: 'atr', name: 'ATR', group: 'volatility' },
  { id: 'adx', name: 'ADX', group: 'trend' },
  { id: 'volume', name: 'Volume', group: 'volume' },
];

const PRESETS = {
  trend: {
    name: 'Trend',
    overlays: ['ema_20', 'ema_50'],
    panes: ['adx', 'volume'],
  },
  momentum: {
    name: 'Momentum',
    overlays: ['ema_20', 'bollinger_bands'],
    panes: ['rsi', 'macd'],
  },
  volatility: {
    name: 'Volatility',
    overlays: ['bollinger_bands', 'vwap'],
    panes: ['atr', 'stochastic'],
  },
};

const MAX_OVERLAYS = 2;
const MAX_PANES = 2;

// ============================================
// COMPONENT
// ============================================

const IndicatorSelector = ({ 
  selectedOverlays = ['ema_20', 'ema_50'],
  selectedPanes = ['rsi', 'macd'],
  onOverlaysChange,
  onPanesChange,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [activePreset, setActivePreset] = useState(null);
  
  const handleOverlayToggle = useCallback((id) => {
    const newOverlays = selectedOverlays.includes(id)
      ? selectedOverlays.filter(o => o !== id)
      : [...selectedOverlays, id].slice(-MAX_OVERLAYS);
    
    onOverlaysChange?.(newOverlays);
    setActivePreset(null);
  }, [selectedOverlays, onOverlaysChange]);
  
  const handlePaneToggle = useCallback((id) => {
    const newPanes = selectedPanes.includes(id)
      ? selectedPanes.filter(p => p !== id)
      : [...selectedPanes, id].slice(-MAX_PANES);
    
    onPanesChange?.(newPanes);
    setActivePreset(null);
  }, [selectedPanes, onPanesChange]);
  
  const handlePresetSelect = useCallback((presetKey) => {
    const preset = PRESETS[presetKey];
    if (preset) {
      onOverlaysChange?.(preset.overlays);
      onPanesChange?.(preset.panes);
      setActivePreset(presetKey);
    }
  }, [onOverlaysChange, onPanesChange]);
  
  const totalSelected = selectedOverlays.length + selectedPanes.length;
  
  return (
    <SelectorContainer data-testid="indicator-selector">
      <ToggleButton onClick={() => setIsOpen(!isOpen)}>
        <Layers />
        Indicators ({totalSelected})
        {isOpen ? <ChevronUp /> : <ChevronDown />}
      </ToggleButton>
      
      {isOpen && (
        <Dropdown>
          {/* Presets */}
          <PresetBar>
            {Object.entries(PRESETS).map(([key, preset]) => (
              <PresetButton
                key={key}
                $active={activePreset === key}
                onClick={() => handlePresetSelect(key)}
              >
                {preset.name}
              </PresetButton>
            ))}
          </PresetBar>
          
          {/* Overlays */}
          <Section>
            <div className="section-header">
              <TrendingUp />
              <span className="title">Overlays</span>
              {selectedOverlays.length >= MAX_OVERLAYS ? (
                <span className="limit-warning">Max {MAX_OVERLAYS}</span>
              ) : (
                <span className="count">{selectedOverlays.length}/{MAX_OVERLAYS}</span>
              )}
            </div>
            <OptionGrid>
              {OVERLAY_OPTIONS.map(opt => (
                <Option
                  key={opt.id}
                  $active={selectedOverlays.includes(opt.id)}
                  onClick={() => handleOverlayToggle(opt.id)}
                  disabled={!selectedOverlays.includes(opt.id) && selectedOverlays.length >= MAX_OVERLAYS}
                >
                  <span className="name">{opt.name}</span>
                  <span className="indicator" />
                </Option>
              ))}
            </OptionGrid>
          </Section>
          
          {/* Panes */}
          <Section>
            <div className="section-header">
              <BarChart3 />
              <span className="title">Lower Panes</span>
              {selectedPanes.length >= MAX_PANES ? (
                <span className="limit-warning">Max {MAX_PANES}</span>
              ) : (
                <span className="count">{selectedPanes.length}/{MAX_PANES}</span>
              )}
            </div>
            <OptionGrid>
              {PANE_OPTIONS.map(opt => (
                <Option
                  key={opt.id}
                  $active={selectedPanes.includes(opt.id)}
                  onClick={() => handlePaneToggle(opt.id)}
                  disabled={!selectedPanes.includes(opt.id) && selectedPanes.length >= MAX_PANES}
                >
                  <span className="name">{opt.name}</span>
                  <span className="indicator" />
                </Option>
              ))}
            </OptionGrid>
          </Section>
        </Dropdown>
      )}
    </SelectorContainer>
  );
};

export default IndicatorSelector;
