/**
 * Structure Range Overlay - BOX (not lines)
 * ==========================================
 * 
 * Renders range as a semi-transparent rectangle
 */

import React from 'react';

const StructureRangeOverlay = ({ range, priceToY, width, height }) => {
  if (!range || !priceToY || !width || !height) return null;

  const yHigh = priceToY(range.high);
  const yLow = priceToY(range.low);

  if (yHigh == null || yLow == null) return null;

  const top = Math.min(yHigh, yLow);
  const boxHeight = Math.abs(yHigh - yLow);

  return (
    <div className="pointer-events-none absolute inset-0 z-[1]" style={{ width, height }}>
      <svg width={width} height={height} className="absolute inset-0">
        <rect
          x={0}
          y={top}
          width={width}
          height={boxHeight}
          fill="rgba(148,163,184,0.06)"
          stroke="rgba(148,163,184,0.30)"
          strokeWidth="1"
          strokeDasharray="4 4"
        />
      </svg>
    </div>
  );
};

export default StructureRangeOverlay;
