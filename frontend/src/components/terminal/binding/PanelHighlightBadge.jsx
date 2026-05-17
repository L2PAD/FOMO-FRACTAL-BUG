/**
 * Panel Highlight Badge - Highlights panel elements when bound
 * ============================================================
 */

'use client'

import { useBinding } from './BindingProvider';
import { isBoundActive } from './bindingUtils';

export default function PanelHighlightBadge({ entityId, children }) {
  const { hovered, selected } = useBinding();
  const active = isBoundActive(entityId, hovered, selected);

  return (
    <span
      className={
        active
          ? 'rounded bg-cyan-500/20 px-1.5 py-0.5 text-cyan-300 ring-1 ring-cyan-400/30'
          : ''
      }
    >
      {children}
    </span>
  );
}
