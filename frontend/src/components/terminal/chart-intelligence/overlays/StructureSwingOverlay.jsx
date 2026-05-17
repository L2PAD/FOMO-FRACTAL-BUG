/**
 * Structure Swing Overlay - WITH BINDING
 * =======================================
 * 
 * Renders swing labels with bidirectional binding:
 * - Hover/click on swing → highlights related blockers in EntryTimingPanel
 * - Hover on blocker → highlights this swing
 */

import React from 'react';
import { useBinding, isBoundActive, makeSwingId, makeBlockerId } from '../../binding';

const StructureSwingOverlay = ({ swings, priceToY, width, height }) => {
  const { hovered, selected, setHovered, clearHovered, setSelected } = useBinding();

  if (!swings?.length || !priceToY || !width || !height) return null;

  return (
    <div className="pointer-events-none absolute inset-0 z-[13]" style={{ width, height }}>
      {swings.map((s, idx) => {
        const y = priceToY(s.price);
        if (y == null) return null;

        const entityId = makeSwingId(s);
        const relatedIds = [
          makeBlockerId(`structure-${String(s.type).toLowerCase()}`),
        ];
        const active = isBoundActive(entityId, hovered, selected);

        const isHigh = s.type.startsWith('H');
        const baseColor = isHigh 
          ? 'text-green-300 bg-green-500/20 border-green-500/40' 
          : 'text-red-300 bg-red-500/20 border-red-500/40';

        return (
          <button
            key={entityId}
            type="button"
            onMouseEnter={() =>
              setHovered({
                id: entityId,
                type: 'swing',
                label: s.type,
                relatedIds,
                meta: s,
              })
            }
            onMouseLeave={clearHovered}
            onClick={() =>
              setSelected({
                id: entityId,
                type: 'swing',
                label: s.type,
                relatedIds,
                meta: s,
              })
            }
            className={`pointer-events-auto absolute -translate-x-1/2 -translate-y-1/2 rounded border px-1.5 py-0.5 text-[10px] font-semibold transition-all ${baseColor} ${
              active
                ? 'ring-2 ring-cyan-400/60 scale-110 bg-cyan-500/30 text-cyan-200 border-cyan-400'
                : 'hover:bg-white/10'
            }`}
            style={{
              left: `${((idx + 1) / (swings.length + 1)) * 100}%`,
              top: `${y}px`,
            }}
          >
            {s.type}
          </button>
        );
      })}
    </div>
  );
};

export default StructureSwingOverlay;
