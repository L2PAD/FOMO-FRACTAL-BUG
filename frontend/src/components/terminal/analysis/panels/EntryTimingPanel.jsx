/**
 * Entry Timing Panel - WITH BINDING
 * ==================================
 * 
 * Shows WHY entry is allowed/blocked with bidirectional binding:
 * - Blockers highlight related chart elements when hovered
 * - Chart elements highlight blockers when hovered
 */

import React from 'react';
import { useBinding, PanelHighlightBadge, makeBlockerId, makeEntryZoneId, slugify } from '../../binding';
import { PanelShell } from '../shared/PanelShell';
import { GridRow } from '../shared/GridRow';
import { TagList } from '../shared/TagList';
import { fmtPct } from '../shared/formatters';

export default function EntryTimingPanel({ data, symbol = 'BTCUSDT', timeframe = '4H' }) {
  const { setHovered, clearHovered, setSelected } = useBinding();

  if (!data) {
    return (
      <PanelShell title="Entry Timing">
        <div className="text-gray-500 text-sm">No entry timing data available</div>
      </PanelShell>
    );
  }

  return (
    <PanelShell title="Entry Timing">
      <GridRow label="Mode" value={data.mode || data.decision?.mode} />
      <GridRow label="Decision" value={data.decision?.action || data.action} />
      <GridRow label="Quality" value={fmtPct(data.quality_score)} />
      <GridRow label="MTF" value={data.mtf_alignment?.status || '—'} />
      <GridRow label="Trigger" value={data.selected_trigger || '—'} />

      {/* Blockers with binding */}
      <div>
        <div className="mb-2 text-xs uppercase tracking-wide text-gray-400">Blockers</div>
        <div className="flex flex-wrap gap-2">
          {data.blockers?.length ? (
            data.blockers.map((blocker, idx) => {
              const slug = slugify(blocker);
              const entityId = makeBlockerId(slug);

              return (
                <button
                  key={`${entityId}-${idx}`}
                  type="button"
                  onMouseEnter={() =>
                    setHovered({
                      id: entityId,
                      type: 'entry_blocker',
                      label: blocker,
                      relatedIds: [makeEntryZoneId(symbol, timeframe)],
                    })
                  }
                  onMouseLeave={clearHovered}
                  onClick={() =>
                    setSelected({
                      id: entityId,
                      type: 'entry_blocker',
                      label: blocker,
                      relatedIds: [makeEntryZoneId(symbol, timeframe)],
                    })
                  }
                  className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-xs text-gray-300 hover:bg-white/10 transition-all"
                >
                  <PanelHighlightBadge entityId={entityId}>
                    {blocker}
                  </PanelHighlightBadge>
                </button>
              );
            })
          ) : (
            <span className="text-xs text-gray-500">No blockers</span>
          )}
        </div>
      </div>

      <TagList 
        title="Reasons" 
        items={data.reasons || data.decision?.reasons} 
        empty="No reasons" 
      />
    </PanelShell>
  );
}
