/**
 * Chart Highlight Layer - Shows current focus
 * ===========================================
 */

'use client'

import { useBinding } from './BindingProvider';

export default function ChartHighlightLayer() {
  const { hovered, selected, clearSelected } = useBinding();
  const active = selected || hovered;

  if (!active) return null;

  return (
    <div className="absolute right-3 top-3 z-[20] flex items-center gap-2 rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-200 backdrop-blur">
      <span>Focus: {active.label || active.type || active.id}</span>

      {selected && (
        <button
          type="button"
          onClick={clearSelected}
          className="pointer-events-auto rounded bg-white/10 px-2 py-1 text-[11px] text-white hover:bg-white/20"
        >
          Clear
        </button>
      )}
    </div>
  );
}
