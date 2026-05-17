/**
 * Execution Overlay - ZONES with BINDING
 * =======================================
 * 
 * Renders execution as visual zones with bidirectional binding:
 * - Red zone (entry → stop) = risk area
 * - Green zone (entry → target) = reward area
 * - Highlights when validation issues or blockers are active
 */

import React, { useMemo } from 'react';
import { useBinding, isBoundActive, makeEntryZoneId, makeRiskZoneId, makeTargetZoneId } from '../../binding';

const ExecutionOverlay = ({ data, priceToY, width, height, symbol = 'BTCUSDT', timeframe = '4H' }) => {
  const { hovered, selected, setHovered, clearHovered, setSelected } = useBinding();

  const zones = useMemo(() => {
    if (!data || !priceToY) return null;
    const { entry, stop, target } = data;
    if (entry == null || stop == null || target == null) return null;

    const yEntry = priceToY(entry);
    const yStop = priceToY(stop);
    const yTarget = priceToY(target);

    if ([yEntry, yStop, yTarget].some(v => v == null)) return null;

    return {
      yEntry,
      yStop,
      yTarget,
    };
  }, [data, priceToY]);

  if (!zones || !width || !height) return null;

  const entryZoneId = makeEntryZoneId(symbol, timeframe);
  const riskZoneId = makeRiskZoneId(symbol, timeframe);
  const targetZoneId = makeTargetZoneId(symbol, timeframe);

  const entryActive = isBoundActive(entryZoneId, hovered, selected);
  const riskActive = isBoundActive(riskZoneId, hovered, selected);
  const targetActive = isBoundActive(targetZoneId, hovered, selected);

  const riskTop = Math.min(zones.yEntry, zones.yStop);
  const riskHeight = Math.abs(zones.yEntry - zones.yStop);

  const targetTop = Math.min(zones.yEntry, zones.yTarget);
  const targetHeight = Math.abs(zones.yEntry - zones.yTarget);

  return (
    <div className="pointer-events-none absolute inset-0 z-[2]" style={{ width, height }}>
      <svg width={width} height={height} className="absolute inset-0">
        {/* Risk Zone (red) */}
        <rect
          x={0}
          y={riskTop}
          width={width}
          height={riskHeight}
          fill={riskActive ? 'rgba(239,68,68,0.18)' : 'rgba(239,68,68,0.10)'}
        />
        
        {/* Target Zone (green) */}
        <rect
          x={0}
          y={targetTop}
          width={width}
          height={targetHeight}
          fill={targetActive ? 'rgba(34,197,94,0.18)' : 'rgba(34,197,94,0.10)'}
        />
        
        {/* Entry Line (blue) */}
        <line
          x1={0}
          y1={zones.yEntry}
          x2={width}
          y2={zones.yEntry}
          stroke={entryActive ? 'rgba(34,211,238,1)' : 'rgba(59,130,246,0.85)'}
          strokeWidth={entryActive ? 2.5 : 2}
          strokeDasharray="6 4"
        />
        
        {/* Stop Line (red) */}
        <line
          x1={0}
          y1={zones.yStop}
          x2={width}
          y2={zones.yStop}
          stroke="rgba(239,68,68,0.85)"
          strokeWidth="2"
          strokeDasharray="6 4"
        />
        
        {/* Target Line (green) */}
        <line
          x1={0}
          y1={zones.yTarget}
          x2={width}
          y2={zones.yTarget}
          stroke="rgba(34,197,94,0.85)"
          strokeWidth="2"
          strokeDasharray="6 4"
        />
      </svg>

      {/* Interactive overlay for binding */}
      <button
        type="button"
        className="absolute left-0 top-0 h-full w-full opacity-0 pointer-events-auto"
        onMouseEnter={() =>
          setHovered({
            id: entryZoneId,
            type: 'entry_zone',
            label: 'Entry Zone',
            relatedIds: [riskZoneId, targetZoneId],
          })
        }
        onMouseLeave={clearHovered}
        onClick={() =>
          setSelected({
            id: entryZoneId,
            type: 'entry_zone',
            label: 'Entry Zone',
            relatedIds: [riskZoneId, targetZoneId],
          })
        }
        aria-label="Entry execution zone"
      />
    </div>
  );
};

export default ExecutionOverlay;
