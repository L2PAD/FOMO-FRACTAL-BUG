/**
 * Structure Event Overlay - WITH BINDING
 * =======================================
 * 
 * Renders BOS/CHOCH markers with bidirectional binding
 */

import React from 'react';
import { useBinding, isBoundActive, makeEventId, makeBlockerId } from '../../binding';

const StructureEventOverlay = ({ events, priceToY, width, height }) => {
  const { hovered, selected, setHovered, clearHovered, setSelected } = useBinding();

  if (!events?.length || !priceToY || !width || !height) return null;

  return (
    <div className="pointer-events-none absolute inset-0 z-[14]" style={{ width, height }}>
      {events.map((e, idx) => {
        const entityId = makeEventId(e);
        const relatedIds = [
          makeBlockerId('breakout-not-confirmed'),
          makeBlockerId('structure-conflict'),
        ];
        const active = isBoundActive(entityId, hovered, selected);

        const y = e.price != null ? priceToY(e.price) : 60 + idx * 28;
        
        const isBOS = e.type === 'BOS';
        const baseColor = isBOS
          ? 'text-blue-300 border-blue-500/40 bg-blue-500/10'
          : 'text-yellow-300 border-yellow-500/40 bg-yellow-500/10';

        const arrow = e.direction === 'UP' ? '↑' : '↓';

        return (
          <button
            key={entityId}
            type="button"
            onMouseEnter={() =>
              setHovered({
                id: entityId,
                type: 'structure_event',
                label: `${e.type} ${e.direction}`,
                relatedIds,
                meta: e,
              })
            }
            onMouseLeave={clearHovered}
            onClick={() =>
              setSelected({
                id: entityId,
                type: 'structure_event',
                label: `${e.type} ${e.direction}`,
                relatedIds,
                meta: e,
              })
            }
            className={`pointer-events-auto absolute rounded border px-2 py-1 text-[10px] font-semibold transition-all ${
              active
                ? 'scale-105 ring-2 ring-cyan-400/50 bg-cyan-500/20 text-cyan-200 border-cyan-400'
                : `${baseColor} hover:bg-white/10`
            }`}
            style={{
              left: `${20 + idx * 18}%`,
              top: `${y ?? 0}px`,
            }}
          >
            {e.type} {arrow}
          </button>
        );
      })}
    </div>
  );
};

export default StructureEventOverlay;
