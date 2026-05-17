import { useState, useCallback } from 'react';

/**
 * useHoverState — hover tooltip state + positioning.
 * Does NOT know about graph modes, intelligence, or loading.
 * Only enriches node data from nodeDataMap and tracks mouse position.
 *
 * Contract:
 *   readonly: hoveredNode, position
 *   actions:  handleNodeHover, handleMouseMove
 */
export function useHoverState(nodeDataMap) {
  const [hoveredNode, setHoveredNode] = useState(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });

  const handleNodeHover = useCallback((node) => {
    if (node) {
      const fullData = nodeDataMap.get(node.id);
      setHoveredNode(fullData || { id: node.id, label: node.fullName || node.label, type: node.nodeType });
    } else {
      setHoveredNode(null);
    }
  }, [nodeDataMap]);

  const handleMouseMove = useCallback((e) => {
    setPosition({ x: e.clientX, y: e.clientY });
  }, []);

  return { hoveredNode, position, handleNodeHover, handleMouseMove };
}
