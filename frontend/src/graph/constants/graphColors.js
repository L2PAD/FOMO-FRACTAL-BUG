/**
 * Graph Colors (visual standard — FIXED, never changes)
 * 
 * Nodes: always grey
 * Edges: green = incoming, red = outgoing
 */

export const NODE_FILL = '#1a1f2e';
export const NODE_STROKE = '#3a3f4b';
export const NODE_RADIUS = 6;
export const MAIN_NODE_GLOW = '#3b82f6';

export const EDGE_COLOR_IN = '#43d18d';
export const EDGE_COLOR_OUT = '#ff6b6b';

export function getEdgeColor(direction) {
  return direction === 'in' ? EDGE_COLOR_IN : EDGE_COLOR_OUT;
}
