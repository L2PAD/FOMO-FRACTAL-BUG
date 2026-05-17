/**
 * P2 — Market V2: Execution Intelligence Board
 * ================================================
 * Where to trade NOW. Not a list of metrics — a decision board.
 *
 * Blocks:
 *   1. Market Pulse (aggregate context)
 *   2. Action Now (execution-ready)
 *   3. Early Build (pre-breakout compression)
 *   4. Structural Shift (regime changes)
 *   5. Risk Events (avoid)
 */
import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Loader2 } from 'lucide-react';
import MarketPulse from '../components/market/MarketPulse';
import MarketSection from '../components/market/MarketSection';
import RadarExplainDrawer from '../components/exchange/RadarExplainDrawer';
import { fetchMarketBoard } from '../api/marketBoard.api';

export default function ExchangeMarketBoard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [universe, setUniverse] = useState('alpha');
  const [selectedRow, setSelectedRow] = useState(null);

  const load = useCallback(async (showSpinner = false) => {
    if (showSpinner) setRefreshing(true);
    try {
      const result = await fetchMarketBoard(universe);
      setData(result);
    } catch (err) {
      console.error('Market board fetch error:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [universe]);

  useEffect(() => { load(true); }, [load]);

  // Auto-refresh every 60s
  useEffect(() => {
    const iv = setInterval(() => load(false), 60000);
    return () => clearInterval(iv);
  }, [load]);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-5 h-5 animate-spin" style={{ color: '#94a3b8' }} />
      </div>
    );
  }

  return (
    <div data-testid="market-board" className="max-w-[1400px] mx-auto px-6 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-[22px] font-bold tracking-tight" style={{ color: '#0f172a' }}>Execution Board</h2>
          <p className="text-[13px] mt-0.5" style={{ color: '#94a3b8' }}>
            {data?.summary?.totalScanned || 0} assets scanned &middot; {data?.latencyMs || 0}ms
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Universe toggle */}
          <div className="flex items-center gap-0.5 p-0.5 rounded-lg" style={{ background: 'rgba(15,23,42,0.04)' }}>
            {['alpha', 'main'].map(u => (
              <button
                key={u}
                data-testid={`market-universe-${u}`}
                onClick={() => setUniverse(u)}
                className="px-3 py-1.5 rounded-md text-[12px] font-semibold transition-all"
                style={{
                  background: universe === u ? '#fff' : 'transparent',
                  color: universe === u ? '#0f172a' : '#94a3b8',
                  boxShadow: universe === u ? '0 1px 3px rgba(0,0,0,0.06)' : 'none',
                }}
              >
                {u.charAt(0).toUpperCase() + u.slice(1)}
              </button>
            ))}
          </div>

          <button
            onClick={() => load(true)}
            disabled={refreshing}
            data-testid="market-refresh"
            className="p-2 rounded-lg transition-colors"
            style={{ color: '#94a3b8' }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(15,23,42,0.04)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Pulse */}
      <MarketPulse pulse={data?.pulse} />

      {/* Sections */}
      <div className="mt-10 space-y-10">
        <MarketSection
          title="Action Now"
          description="Execution-ready setups with high conviction & clean structure"
          rows={data?.actionNow}
          sectionType="action"
          onRowClick={setSelectedRow}
        />

        <MarketSection
          title="Early Build"
          description="Compression & participation building — pre-breakout candidates"
          rows={data?.earlyBuild}
          sectionType="early"
          onRowClick={setSelectedRow}
        />

        <MarketSection
          title="Structural Shift"
          description="Regime, funding, or positioning changes"
          rows={data?.structuralShift}
          sectionType="shift"
          onRowClick={setSelectedRow}
        />

        <MarketSection
          title="Risk Events"
          description="Avoid — unstable, stale data, or extreme conditions"
          rows={data?.riskEvents}
          variant="risk"
          sectionType="risk"
          onRowClick={setSelectedRow}
        />
      </div>

      {/* Empty state */}
      {data && !data.actionNow?.length && !data.earlyBuild?.length && !data.structuralShift?.length && !data.riskEvents?.length && (
        <div className="text-center py-16">
          <div className="text-[15px] font-medium" style={{ color: '#94a3b8' }}>No actionable setups right now</div>
          <div className="text-[12px] mt-1" style={{ color: '#cbd5e1' }}>Market is quiet. Check back later.</div>
        </div>
      )}

      {/* Explain Drawer (reuse from Radar) */}
      <RadarExplainDrawer row={selectedRow} open={!!selectedRow} onClose={() => setSelectedRow(null)} />
    </div>
  );
}
