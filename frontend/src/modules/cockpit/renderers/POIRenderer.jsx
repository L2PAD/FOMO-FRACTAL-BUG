/**
 * POIRenderer
 * ===========
 * Renders Point of Interest zones (only 1, closest to price)
 */

import React from 'react';
import styled from 'styled-components';

const POIBadge = styled.div`
  position: absolute;
  bottom: 50px;
  left: 12px;
  padding: 8px 12px;
  background: rgba(139, 92, 246, 0.9);
  border-radius: 6px;
  font-size: 11px;
  color: #fff;
  z-index: 5;
  backdrop-filter: blur(4px);
  
  .label { font-weight: 700; text-transform: uppercase; }
  .range { font-size: 10px; opacity: 0.9; margin-top: 2px; }
`;

export const POIRenderer = ({ zones }) => {
  if (!zones || zones.length === 0) return null;

  // Only show closest zone (already filtered by backend)
  const zone = zones[0];
  const low = zone.price_low || zone.lower;
  const high = zone.price_high || zone.upper;
  const type = zone.type || 'POI';

  return (
    <POIBadge data-testid="poi-renderer">
      <div className="label">{type.replace(/_/g, ' ')}</div>
      {low && high && (
        <div className="range">${low.toFixed(2)} - ${high.toFixed(2)}</div>
      )}
    </POIBadge>
  );
};

export default POIRenderer;
