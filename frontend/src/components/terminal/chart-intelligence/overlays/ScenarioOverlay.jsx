/**
 * Scenario Overlay - TT-UI4.2
 * ============================
 * 
 * Renders scenario projections (primary/alternative paths)
 * with target/invalidation levels and probability
 */

import React from 'react';
import { useBinding } from '../../binding/BindingProvider';
import { isBoundActive } from '../../binding/bindingUtils';

function mapScenarioPoint(pt, timeToX, priceToY) {
  const x = timeToX?.(pt.time);
  const y = priceToY?.(pt.price);
  if (x == null || y == null) return null;
  return { x, y };
}

function renderArrowHead(x1, y1, x2, y2, color) {
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const size = 6;
  const a1 = angle - Math.PI / 7;
  const a2 = angle + Math.PI / 7;

  const x3 = x2 - size * Math.cos(a1);
  const y3 = y2 - size * Math.sin(a1);
  const x4 = x2 - size * Math.cos(a2);
  const y4 = y2 - size * Math.sin(a2);

  return (
    <>
      <line x1={x2} y1={y2} x2={x3} y2={y3} stroke={color} strokeWidth="2" />
      <line x1={x2} y1={y2} x2={x4} y2={y4} stroke={color} strokeWidth="2" />
    </>
  );
}

export default function ScenarioOverlay({
  scenarios,
  priceToY,
  timeToX,
  width,
  height,
}) {
  const { hovered, selected, setHovered, clearHovered, setSelected } = useBinding();

  if (!scenarios?.length) return null;

  return (
    <div className="pointer-events-none absolute inset-0 z-[16]">
      <svg width={width} height={height}>
        {scenarios.map((s) => {
          const entityId = `scenario-${s.id}`;
          const active = isBoundActive(entityId, hovered, selected);

          const pts = (s.path || [])
            .map((pt) => mapScenarioPoint(pt, timeToX, priceToY))
            .filter(Boolean);

          if (pts.length < 2) return null;

          const pointsStr = pts.map((p) => `${p.x},${p.y}`).join(' ');
          const first = pts[0];
          const last = pts[pts.length - 1];

          // Role-based visual dominance
          const isPrimary = s.role === 'PRIMARY';
          const baseOpacity = isPrimary ? 1 : 0.5;
          const baseWidth = isPrimary ? 3 : 1.5;

          // Probability influences strokeWidth (visual > text)
          const probability = s.probability || 0;
          const strokeWidth = baseWidth + probability * 2;

          const color =
            s.bias === 'BULLISH'
              ? active
                ? `rgba(34,197,94,${baseOpacity})`
                : `rgba(34,197,94,${baseOpacity * 0.88})`
              : active
              ? `rgba(239,68,68,${baseOpacity})`
              : `rgba(239,68,68,${baseOpacity * 0.88})`;

          return (
            <g key={s.id}>
              <polyline
                points={pointsStr}
                fill="none"
                stroke={color}
                strokeWidth={active ? strokeWidth + 1 : strokeWidth}
                strokeDasharray="6 4"
                className="pointer-events-auto cursor-pointer"
                onMouseEnter={() =>
                  setHovered({
                    id: entityId,
                    type: 'scenario',
                    label: s.label || s.type,
                    meta: s,
                  })
                }
                onMouseLeave={clearHovered}
                onClick={() =>
                  setSelected({
                    id: entityId,
                    type: 'scenario',
                    label: s.label || s.type,
                    meta: s,
                  })
                }
              />

              {renderArrowHead(
                pts[pts.length - 2].x,
                pts[pts.length - 2].y,
                last.x,
                last.y,
                color
              )}

              <text x={first.x} y={first.y - 8} fontSize="10" fill={color}>
                {(s.label || s.type) + ` (${Math.round((s.probability || 0) * 100)}%)`}
              </text>

              {/* Target line */}
              {s.target?.price != null &&
                (() => {
                  const y = priceToY?.(s.target.price);
                  if (y == null) return null;
                  return (
                    <line
                      x1={Math.max(0, first.x)}
                      y1={y}
                      x2={width}
                      y2={y}
                      stroke={color}
                      strokeDasharray="2 6"
                      strokeWidth="1"
                    />
                  );
                })()}

              {/* Invalidation line - CRITICAL LEVEL */}
              {s.invalidation?.price != null &&
                (() => {
                  const y = priceToY?.(s.invalidation.price);
                  if (y == null) return null;
                  return (
                    <>
                      <line
                        x1={Math.max(0, first.x)}
                        y1={y}
                        x2={width}
                        y2={y}
                        stroke="rgba(251,191,36,0.9)"
                        strokeDasharray="2 6"
                        strokeWidth="2"
                      />
                      <text
                        x={Math.max(0, first.x) + 4}
                        y={y - 4}
                        fontSize="9"
                        fill="rgba(251,191,36,1)"
                        fontWeight="600"
                      >
                        INVALID
                      </text>
                    </>
                  );
                })()}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
