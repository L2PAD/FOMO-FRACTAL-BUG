import { useState } from 'react';
import PortfolioHero from '../portfolio-fund/PortfolioHero';
import PortfolioChart from '../portfolio-fund/PortfolioChart';
import PortfolioSidebar from '../portfolio-fund/PortfolioSidebar';
import PortfolioAssets from '../portfolio-fund/PortfolioAssets';
import PortfolioActivePositions from '../portfolio-fund/PortfolioActivePositions';
import PortfolioClosedPositions from '../portfolio-fund/PortfolioClosedPositions';
import SystemIntelligencePanel from '../portfolio-fund/SystemIntelligencePanel';
import PortfolioPnlTimeline from '../portfolio-fund/PortfolioPnlTimeline';
import PortfolioContributionMini from '../portfolio-fund/PortfolioContributionMini';
import PortfolioModeMini from '../portfolio-fund/PortfolioModeMini';
import PortfolioRiskSnapshot from '../portfolio-fund/PortfolioRiskSnapshot';
import PortfolioMiniCharts from '../portfolio-fund/PortfolioMiniCharts';
import PortfolioNarrative from '../portfolio-fund/PortfolioNarrative';
import { usePortfolioSummary } from '../../../hooks/portfolio/usePortfolioSummary';
import { usePortfolioAllocations } from '../../../hooks/portfolio/usePortfolioAllocations';
import { usePortfolioAssets } from '../../../hooks/portfolio/usePortfolioAssets';
import { usePortfolioActivePositions } from '../../../hooks/portfolio/usePortfolioActivePositions';
import { usePortfolioClosedPositions } from '../../../hooks/portfolio/usePortfolioClosedPositions';

export default function PortfolioWorkspace() {
  const [selectedRange, setSelectedRange] = useState('ALL');
  const [focusAsset, setFocusAsset] = useState(null);
  
  // Real data hooks
  const { summary, loading: summaryLoading, isConnected, error } = usePortfolioSummary();
  const { allocations, loading: allocationsLoading } = usePortfolioAllocations();
  const { assets, loading: assetsLoading } = usePortfolioAssets();
  const { positions: activePositions, loading: activeLoading } = usePortfolioActivePositions();
  const { positions: closedPositions, loading: closedLoading } = usePortfolioClosedPositions();

  return (
    <div className="min-h-screen bg-white" style={{ fontFamily: 'Gilroy, sans-serif' }}>
      <div className="max-w-[1440px] mx-auto px-6 py-3">
        {/* HERO SUMMARY */}
        <PortfolioHero summary={summary} loading={summaryLoading} isConnected={isConnected} error={error} />

        {/* MAIN ANALYTICS GRID */}
        <div className="grid grid-cols-12 gap-3 mt-4">
          {/* LEFT COLUMN (8 cols): Chart + Assets + Active Positions + System State + Risk */}
          <div className="col-span-8 space-y-3">
            <PortfolioChart
              selectedRange={selectedRange}
              onRangeChange={setSelectedRange}
              focusAsset={focusAsset}
            />
            {/* Assets and Active Positions side by side */}
            <div className="grid grid-cols-2 gap-3">
              <PortfolioAssets assets={assets} loading={assetsLoading} />
              <PortfolioActivePositions positions={activePositions} loading={activeLoading} />
            </div>
            {/* System State and Risk Snapshot side by side */}
            <div className="grid grid-cols-2 gap-3">
              <PortfolioModeMini />
              <PortfolioRiskSnapshot />
            </div>
          </div>

          {/* RIGHT COLUMN (4 cols): Allocation + Intelligence */}
          <div className="col-span-4 flex flex-col gap-3">
            <PortfolioSidebar
              allocations={allocations}
              summary={summary}
              loading={allocationsLoading || summaryLoading}
            />
            <SystemIntelligencePanel />
          </div>
        </div>

        {/* PERFORMANCE & CONTRIBUTION ROW */}
        <div className="grid grid-cols-12 gap-3 mt-4">
          {/* LEFT: Asset Performance (8 cols) */}
          <div className="col-span-8">
            <PortfolioMiniCharts />
          </div>
          
          {/* RIGHT: Contribution (4 cols) */}
          <div className="col-span-4">
            <PortfolioContributionMini onFocusAsset={setFocusAsset} />
          </div>
        </div>

        {/* NARRATIVE & CLOSED POSITIONS ROW */}
        <div className="grid grid-cols-12 gap-3 mt-4">
          {/* LEFT: System Insight (8 cols) */}
          <div className="col-span-8">
            <PortfolioNarrative />
          </div>
          
          {/* RIGHT: Closed Positions (4 cols) */}
          <div className="col-span-4">
            <PortfolioClosedPositions positions={closedPositions} loading={closedLoading} />
          </div>
        </div>
      </div>
    </div>
  );
}
