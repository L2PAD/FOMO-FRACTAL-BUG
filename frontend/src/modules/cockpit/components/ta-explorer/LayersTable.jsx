/**
 * LayersTable.jsx — Shows all 10 TA layers with expandable details
 */

import React, { useState } from 'react';
import styled from 'styled-components';

const Card = styled.div`
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 8px;
  padding: 12px;
`;

const Header = styled.div`
  font-size: 12px;
  font-weight: 600;
  color: #f1f5f9;
  margin-bottom: 12px;
`;

const LayerRow = styled.details`
  margin-bottom: 4px;
  border-radius: 4px;
  overflow: hidden;
  
  &[open] {
    background: rgba(15, 23, 42, 0.5);
  }
`;

const Summary = styled.summary`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 11px;
  color: #f1f5f9;
  background: rgba(148, 163, 184, 0.05);
  border-radius: 4px;
  
  &:hover {
    background: rgba(148, 163, 184, 0.1);
  }
  
  &::marker {
    display: none;
  }
  
  &::-webkit-details-marker {
    display: none;
  }
`;

const LayerNum = styled.span`
  font-size: 10px;
  color: #64748b;
  width: 24px;
`;

const LayerName = styled.span`
  flex: 1;
  font-weight: 500;
`;

const LayerValue = styled.span`
  font-size: 10px;
  color: ${props => 
    props.$type === 'bullish' ? '#22c55e' : 
    props.$type === 'bearish' ? '#ef4444' : 
    '#94a3b8'
  };
  font-weight: 500;
`;

const ExpandIcon = styled.span`
  font-size: 10px;
  color: #64748b;
  transition: transform 0.2s;
  
  details[open] & {
    transform: rotate(90deg);
  }
`;

const Content = styled.div`
  padding: 8px 12px;
  font-size: 10px;
  color: #94a3b8;
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
`;

const LAYER_CONFIG = {
  layer_1_structure: { name: 'Structure', valueKey: 'trend' },
  layer_2_impulse: { name: 'Impulse', valueKey: 'direction' },
  layer_3_regime: { name: 'Regime', valueKey: 'regime' },
  layer_4_range: { name: 'Range', valueKey: 'status' },
  layer_5_pattern: { name: 'Pattern', valueKey: 'type' },
  layer_6_confluence: { name: 'Confluence', valueKey: 'count' },
  layer_7_probability: { name: 'Probability', valueKey: 'dominant_bias' },
  layer_8_scenarios: { name: 'Scenarios', valueKey: null },
  layer_9_timing: { name: 'Timing', valueKey: 'phase' },
  layer_10_narrative: { name: 'Narrative', valueKey: 'short' },
};

export default function LayersTable({ layers }) {
  if (!layers || Object.keys(layers).length === 0) {
    return (
      <Card>
        <Header>10 TA Layers</Header>
        <div style={{ color: '#64748b', fontSize: 11, padding: 16, textAlign: 'center' }}>
          No layer data available
        </div>
      </Card>
    );
  }
  
  const getLayerValue = (layerKey, layerData) => {
    if (!layerData) return '-';
    
    const config = LAYER_CONFIG[layerKey];
    if (!config) return '-';
    
    if (config.valueKey === null) {
      // Special handling for scenarios
      if (layerKey === 'layer_8_scenarios') {
        const up = layerData.break_up?.target;
        const down = layerData.break_down?.target;
        if (up && down) return `↑${up.toFixed(0)} ↓${down.toFixed(0)}`;
        return '-';
      }
      return '-';
    }
    
    const value = layerData[config.valueKey];
    if (value === undefined || value === null) return '-';
    
    if (typeof value === 'number') {
      return config.valueKey === 'count' ? value.toString() : value.toFixed(0);
    }
    
    return value;
  };
  
  const getValueType = (layerKey, layerData) => {
    if (!layerData) return 'neutral';
    
    const value = getLayerValue(layerKey, layerData);
    if (value === '-') return 'neutral';
    
    const str = value.toString().toLowerCase();
    if (str.includes('bullish') || str.includes('up')) return 'bullish';
    if (str.includes('bearish') || str.includes('down')) return 'bearish';
    return 'neutral';
  };
  
  const sortedLayers = Object.entries(layers).sort(([a], [b]) => {
    const numA = parseInt(a.split('_')[1]) || 0;
    const numB = parseInt(b.split('_')[1]) || 0;
    return numA - numB;
  });
  
  return (
    <Card data-testid="layers-table">
      <Header>10 TA Layers</Header>
      
      {sortedLayers.map(([key, data]) => {
        const config = LAYER_CONFIG[key];
        const layerNum = key.split('_')[1];
        const value = getLayerValue(key, data);
        const valueType = getValueType(key, data);
        
        return (
          <LayerRow key={key}>
            <Summary>
              <LayerNum>L{layerNum}</LayerNum>
              <LayerName>{config?.name || key}</LayerName>
              <LayerValue $type={valueType}>{value}</LayerValue>
              <ExpandIcon>›</ExpandIcon>
            </Summary>
            <Content>
              {JSON.stringify(data, null, 2)}
            </Content>
          </LayerRow>
        );
      })}
    </Card>
  );
}
