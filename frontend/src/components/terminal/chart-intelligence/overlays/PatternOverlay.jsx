/**
 * Pattern Overlay - TT-UI4.2
 * ===========================
 * 
 * Renders chart patterns (triangle, wedge, channel, consolidation box)
 * with full binding support
 */

import React from 'react';
import { useBinding } from '../../binding/BindingProvider';
import { isBoundActive } from '../../binding/bindingUtils';

function mapPoint(pt, timeToX, priceToY) {
  const x = timeToX?.(pt.time);
  const y = priceToY?.(pt.price);
  if (x == null || y == null) return null;
  return { x, y };
}

function renderPolygon(pattern, geometry, timeToX, priceToY, active, handlers) {
  const points = (geometry.points || [])
    .map((pt) => mapPoint(pt, timeToX, priceToY))
    .filter(Boolean);

  if (points.length < 3) return null;

  const pointsStr = points.map((p) => `${p.x},${p.y}`).join(' ');
  const first = points[0];

  return (
    <g key={pattern.id}>
      <polygon
        points={pointsStr}
        fill={active ? 'rgba(56,189,248,0.16)' : 'rgba(148,163,184,0.08)'}
        stroke={active ? 'rgba(34,211,238,0.95)' : 'rgba(148,163,184,0.45)'}
        strokeWidth={active ? 2 : 1}
        className="pointer-events-auto cursor-pointer"
        {...handlers}
      />
      <text
        x={first.x}
        y={first.y - 8}
        fontSize="10"
        fill={active ? '#22d3ee' : '#94a3b8'}
      >
        {pattern.label || pattern.type}
      </text>
    </g>
  );
}

function renderChannel(pattern, geometry, timeToX, priceToY, active, handlers) {
  const upper = (geometry.upper || []).map((pt) => mapPoint(pt, timeToX, priceToY)).filter(Boolean);
  const lower = (geometry.lower || []).map((pt) => mapPoint(pt, timeToX, priceToY)).filter(Boolean);

  if (upper.length < 2 || lower.length < 2) return null;

  const poly = [...upper, ...lower.slice().reverse()];
  const polyStr = poly.map((p) => `${p.x},${p.y}`).join(' ');

  return (
    <g key={pattern.id}>
      <polygon
        points={polyStr}
        fill={active ? 'rgba(56,189,248,0.14)' : 'rgba(148,163,184,0.06)'}
        stroke={active ? 'rgba(34,211,238,0.95)' : 'rgba(148,163,184,0.40)'}
        strokeWidth={active ? 2 : 1}
        className="pointer-events-auto cursor-pointer"
        {...handlers}
      />
      <polyline
        points={upper.map((p) => `${p.x},${p.y}`).join(' ')}
        fill="none"
        stroke={active ? 'rgba(34,211,238,0.95)' : 'rgba(148,163,184,0.50)'}
        strokeWidth={1}
      />
      <polyline
        points={lower.map((p) => `${p.x},${p.y}`).join(' ')}
        fill="none"
        stroke={active ? 'rgba(34,211,238,0.95)' : 'rgba(148,163,184,0.50)'}
        strokeWidth={1}
      />
      <text
        x={upper[0].x}
        y={upper[0].y - 8}
        fontSize="10"
        fill={active ? '#22d3ee' : '#94a3b8'}
      >
        {pattern.label || pattern.type}
      </text>
    </g>
  );
}

function renderBox(pattern, geometry, timeToX, priceToY, active, handlers, width) {
  const yHigh = priceToY?.(geometry.high);
  const yLow = priceToY?.(geometry.low);
  if (yHigh == null || yLow == null) return null;

  const x1 = timeToX?.(geometry.startTime) ?? width * 0.35;
  const x2 = timeToX?.(geometry.endTime) ?? width * 0.75;

  const top = Math.min(yHigh, yLow);
  const h = Math.abs(yHigh - yLow);

  return (
    <g key={pattern.id}>
      <rect
        x={x1}
        y={top}
        width={Math.max(8, x2 - x1)}
        height={h}
        fill={active ? 'rgba(56,189,248,0.14)' : 'rgba(148,163,184,0.06)'}
        stroke={active ? 'rgba(34,211,238,0.95)' : 'rgba(148,163,184,0.40)'}
        strokeDasharray="4 4"
        strokeWidth={active ? 2 : 1}
        className="pointer-events-auto cursor-pointer"
        {...handlers}
      />
      <text
        x={x1}
        y={top - 8}
        fontSize="10"
        fill={active ? '#22d3ee' : '#94a3b8'}
      >
        {pattern.label || pattern.type}
      </text>
    </g>
  );
}

export default function PatternOverlay({
  patterns,
  priceToY,
  timeToX,
  width,
  height,
}) {
  const { hovered, selected, setHovered, clearHovered, setSelected } = useBinding();

  if (!patterns?.length) return null;

  return (
    <div className="pointer-events-none absolute inset-0 z-[11]">
      <svg width={width} height={height}>
        {patterns.map((p) => {
          const entityId = `pattern-${p.id}`;
          const active = isBoundActive(entityId, hovered, selected);

          const handlers = {
            onMouseEnter: () =>
              setHovered({
                id: entityId,
                type: 'pattern',
                label: p.label || p.type,
                meta: p,
              }),
            onMouseLeave: clearHovered,
            onClick: () =>
              setSelected({
                id: entityId,
                type: 'pattern',
                label: p.label || p.type,
                meta: p,
              }),
          };

          const g = p.geometry || {};
          if (g.kind === 'polygon') {
            return renderPolygon(p, g, timeToX, priceToY, active, handlers);
          }
          if (g.kind === 'channel') {
            return renderChannel(p, g, timeToX, priceToY, active, handlers);
          }
          if (g.kind === 'box') {
            return renderBox(p, g, timeToX, priceToY, active, handlers, width);
          }
          return null;
        })}
      </svg>
    </div>
  );
}
