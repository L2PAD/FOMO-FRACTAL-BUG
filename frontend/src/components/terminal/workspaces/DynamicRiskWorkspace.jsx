// /app/frontend/src/components/terminal/workspaces/DynamicRiskWorkspace.jsx
import React, { useState, useEffect, useMemo } from "react";
import useDynamicRiskRecent from "@/hooks/dynamic_risk/useDynamicRiskRecent";
import useDynamicRiskStats from "@/hooks/dynamic_risk/useDynamicRiskStats";

import DynamicRiskStatsBar from "@/components/terminal/risk/DynamicRiskStatsBar";
import DynamicRiskRecentTable from "@/components/terminal/risk/DynamicRiskRecentTable";
import DynamicRiskExplainPanel from "@/components/terminal/risk/DynamicRiskExplainPanel";

// Stable key for selection matching
function getItemKey(item) {
  if (!item) return null;
  return `${item.symbol}-${item.timestamp}-${item.type}`;
}

export default function DynamicRiskWorkspace() {
  const { items, loading: recentLoading } = useDynamicRiskRecent();
  const { stats, loading: statsLoading } = useDynamicRiskStats();

  const [selectedKey, setSelectedKey] = useState(null);

  // Auto-select first item on initial load
  useEffect(() => {
    if (!selectedKey && items.length > 0) {
      setSelectedKey(getItemKey(items[0]));
    }
  }, [items, selectedKey]);

  // Find currently selected item
  const selected = useMemo(() => {
    if (!selectedKey || !items.length) return null;
    
    const found = items.find(item => getItemKey(item) === selectedKey);
    
    // If previously selected item disappeared, auto-select first
    if (!found && items.length > 0) {
      const firstKey = getItemKey(items[0]);
      setSelectedKey(firstKey);
      return items[0];
    }
    
    return found || null;
  }, [items, selectedKey]);

  const handleSelect = (item) => {
    setSelectedKey(getItemKey(item));
  };

  return (
    <div className="p-4 space-y-4" data-testid="dynamic-risk-workspace">
      {/* Stats Bar */}
      <DynamicRiskStatsBar stats={stats} loading={statsLoading} />

      {/* Main Grid: Table + Explain Panel */}
      <div className="grid grid-cols-12 gap-4">
        {/* Recent Decisions Table (8 cols) */}
        <div className="col-span-8">
          <DynamicRiskRecentTable
            items={items}
            loading={recentLoading}
            selected={selected}
            onSelect={handleSelect}
          />
        </div>

        {/* Explain Panel (4 cols) */}
        <div className="col-span-4">
          <DynamicRiskExplainPanel item={selected} />
        </div>
      </div>
    </div>
  );
}
