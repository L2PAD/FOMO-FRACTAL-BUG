import { useEffect, useMemo, useRef, useState } from "react";
import * as LightweightCharts from "lightweight-charts";
import { useTerminal } from "../../../store/terminalStore";
import useMarketCandles from "../../../hooks/useMarketCandles";
import DecisionOverlay from "../overlays/DecisionOverlay";
import ExecutionReplayOverlay from "../overlays/ExecutionReplayOverlay";
import PositionPnlOverlay from "../overlays/PositionPnlOverlay";
import LiquidityHeatmapOverlay from "../overlays/LiquidityHeatmapOverlay";
import useExecutionHeatmap from "../../../hooks/useExecutionHeatmap";

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const timeframes = ["1h", "4h", "1d"];

export default function SmartChartPanel({ hideNoTradeOverlay = false }) {
  const { state } = useTerminal();
  const [timeframe, setTimeframe] = useState("4h");
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [fills, setFills] = useState([]);
  const [showHeatmap, setShowHeatmap] = useState(true);
  
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const priceLinesRef = useRef([]);
  const markLineRef = useRef(null);

  const { candles, loading } = useMarketCandles(state.selectedSymbol, timeframe);
  const heatmap = useExecutionHeatmap(state.selectedSymbol);

  // Fetch fills for selected symbol
  useEffect(() => {
    async function fetchFills() {
      try {
        const res = await fetch(`${API_URL}/api/exchange/fills`);
        const data = await res.json();
        if (data.ok) {
          const symbolFills = (data.fills || []).filter(
            f => f.symbol === state.selectedSymbol
          );
          setFills(symbolFills);
        }
      } catch (e) {
        console.error('Fills fetch error:', e);
      }
    }

    fetchFills();
    const interval = setInterval(fetchFills, 5000);
    return () => clearInterval(interval);
  }, [state.selectedSymbol]);

  const selectedDecision = useMemo(() => {
    const realDecision = state.allocator?.decisions?.find(
      (d) => d.symbol === state.selectedSymbol
    );
    
    // ONLY use real decisions from backend
    // Mock removed - no fake overlays in normal mode
    return realDecision || null;
  }, [state.allocator, state.selectedSymbol]);

  const selectedPosition = useMemo(() => {
    return (
      state.positions?.find((p) => p.symbol === state.selectedSymbol && p.status === "OPEN") || null
    );
  }, [state.positions, state.selectedSymbol]);

  const currentPrice = useMemo(() => {
    return candles?.length ? Number(candles[candles.length - 1]?.close || 0) : null;
  }, [candles]);

  // Create chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = LightweightCharts.createChart(chartContainerRef.current, {
      layout: {
        background: { color: "#ffffff" },
        textColor: "#111111",
      },
      grid: {
        vertLines: { color: "#f5f5f5" },
        horzLines: { color: "#f5f5f5" },
      },
      rightPriceScale: {
        borderColor: "#e5e5e5",
      },
      timeScale: {
        borderColor: "#e5e5e5",
        timeVisible: true,
      },
      crosshair: {
        mode: 0,
      },
    });

    const candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {
      upColor: "#111111",
      downColor: "#c44",
      borderDownColor: "#c44",
      borderUpColor: "#111111",
      wickDownColor: "#c44",
      wickUpColor: "#111111",
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;

    const resizeObserver = new ResizeObserver(() => {
      if (!chartContainerRef.current || !chartRef.current) return;
      chartRef.current.applyOptions({
        width: chartContainerRef.current.clientWidth,
        height: chartContainerRef.current.clientHeight,
      });
    });

    resizeObserver.observe(chartContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, []);

  // Update candles
  useEffect(() => {
    if (!candleSeriesRef.current) return;

    const mapped = (candles || []).map((c) => ({
      time: Math.floor((c.timestamp || c.time || Date.now()) / 1000),
      open: Number(c.open),
      high: Number(c.high),
      low: Number(c.low),
      close: Number(c.close),
    }));

    candleSeriesRef.current.setData(mapped);

    if (chartRef.current && mapped.length > 0) {
      chartRef.current.timeScale().fitContent();
    }
  }, [candles]);

  // Update chart markers and lines when case changes
  useEffect(() => {
    if (!candleSeriesRef.current || !state.selectedCase || !candles?.length) return;

    const caseData = state.selectedCase;
    const markers = [];

    // Entry markers
    if (caseData.entries) {
      caseData.entries.forEach((entry) => {
        markers.push({
          time: entry.time,
          position: 'belowBar',
          color: '#16a34a',
          shape: 'arrowUp',
          text: 'ENTRY'
        });
      });
    }

    // Add markers
    if (caseData.adds) {
      caseData.adds.forEach((add) => {
        markers.push({
          time: add.time,
          position: 'belowBar',
          color: '#2563eb',
          shape: 'circle',
          text: 'ADD'
        });
      });
    }

    // Partial exit markers
    if (caseData.partial_exits) {
      caseData.partial_exits.forEach((exit) => {
        markers.push({
          time: exit.time,
          position: 'aboveBar',
          color: '#f59e0b',
          shape: 'circle',
          text: 'PARTIAL'
        });
      });
    }

    // Full exit markers
    if (caseData.exits) {
      caseData.exits.forEach((exit) => {
        markers.push({
          time: exit.time,
          position: 'aboveBar',
          color: '#dc2626',
          shape: 'arrowDown',
          text: 'EXIT'
        });
      });
    }

    // Thesis change markers (⚡ → FLIP)
    if (caseData.switched_from) {
      // Add flip marker at first entry time
      const flipTime = caseData.entries?.[0]?.time || (Math.floor(Date.now() / 1000) - 86400 * 3);
      markers.push({
        time: flipTime - 3600, // 1 hour before entry
        position: 'belowBar', // Below bar чтобы не терялся
        color: '#a855f7', // Ярче purple
        shape: 'circle',
        text: 'FLIP'
      });
    }

    console.log('[Chart Intelligence] Setting markers:', markers);
    
    // Set markers
    if (typeof candleSeriesRef.current.setMarkers === 'function') {
      try {
        candleSeriesRef.current.setMarkers(markers);
      } catch (e) {
        console.error('[Chart Intelligence] Failed to set markers:', e);
      }
    }

    // Clear existing price lines
    priceLinesRef.current.forEach(line => {
      try {
        candleSeriesRef.current?.removePriceLine(line);
      } catch (e) {}
    });
    priceLinesRef.current = [];

    // Add Stop line (thinner, more transparent)
    if (caseData.stop && typeof candleSeriesRef.current.createPriceLine === 'function') {
      try {
        const stopPrice = parseFloat(caseData.stop.replace(/,/g, ''));
        priceLinesRef.current.push(
          candleSeriesRef.current.createPriceLine({
            price: stopPrice,
            color: 'rgba(220, 38, 38, 0.7)',
            lineWidth: 1,
            lineStyle: 2,
            axisLabelVisible: true,
            title: 'STOP'
          })
        );
      } catch (e) {
        console.error('[Chart Intelligence] Failed to create stop line:', e);
      }
    }

    // Add Target line (thinner)
    if (caseData.target && typeof candleSeriesRef.current.createPriceLine === 'function') {
      try {
        priceLinesRef.current.push(
          candleSeriesRef.current.createPriceLine({
            price: caseData.target,
            color: '#16a34a',
            lineWidth: 1,
            lineStyle: 2,
            axisLabelVisible: true,
            title: 'TARGET'
          })
        );
      } catch (e) {
        console.error('[Chart Intelligence] Failed to create target line:', e);
      }
    }

    // Add Position Zone (area series) - ENHANCED VISIBILITY
    if (caseData.avg_entry && caseData.status === 'ACTIVE' && chartRef.current && candles?.length > 0) {
      try {
        // Get current price from last candle
        const lastCandle = candles[candles.length - 1];
        const currentPrice = lastCandle?.close || lastCandle?.c || caseData.avg_entry;
        
        const isLong = caseData.direction === 'LONG';
        
        // Enhanced colors - MORE VISIBLE
        const zoneColor = isLong ? 
          { 
            top: 'rgba(34,197,94,0.22)',     // Increased from 0.12
            bottom: 'rgba(34,197,94,0.08)',  // Increased from 0.02
            line: 'rgba(34,197,94,0.6)',     // Increased from 0.3
            lineWidth: 2                     // Increased from 1
          } :
          { 
            top: 'rgba(239,68,68,0.22)', 
            bottom: 'rgba(239,68,68,0.08)', 
            line: 'rgba(239,68,68,0.6)',
            lineWidth: 2
          };

        const zoneSeries = chartRef.current.addAreaSeries({
          topColor: zoneColor.top,
          bottomColor: zoneColor.bottom,
          lineColor: zoneColor.line,
          lineWidth: zoneColor.lineWidth,
          priceLineVisible: false,
          lastValueVisible: false
        });

        const firstEntryTime = caseData.entries?.[0]?.time || (Math.floor(Date.now() / 1000) - 86400 * 3);
        const now = Math.floor(Date.now() / 1000);

        // Create REAL ZONE between entry and current price
        const zoneData = [];
        
        // Start from entry time with entry price
        zoneData.push({ time: firstEntryTime, value: caseData.avg_entry });
        
        // Add middle points to create smooth zone
        const midTime = firstEntryTime + Math.floor((now - firstEntryTime) / 2);
        zoneData.push({ time: midTime, value: currentPrice });
        
        // End at now with current price
        zoneData.push({ time: now, value: currentPrice });

        zoneSeries.setData(zoneData);

        // Store for cleanup
        if (!priceLinesRef.current.zoneSeries) {
          priceLinesRef.current.zoneSeries = zoneSeries;
        }
      } catch (e) {
        console.error('[Chart Intelligence] Failed to create position zone:', e);
      }
    }

    return () => {
      // Cleanup price lines on unmount
      priceLinesRef.current.forEach(line => {
        try {
          candleSeriesRef.current?.removePriceLine(line);
        } catch (e) {}
      });
      
      // Cleanup zone series
      if (priceLinesRef.current.zoneSeries && chartRef.current) {
        try {
          chartRef.current.removeSeries(priceLinesRef.current.zoneSeries);
        } catch (e) {}
      }
      
      priceLinesRef.current = [];
    };
  }, [state.selectedCase, candles]);

  // Update MARK line
  useEffect(() => {
    if (!candleSeriesRef.current || !currentPrice) return;

    if (markLineRef.current) {
      candleSeriesRef.current.removePriceLine(markLineRef.current);
      markLineRef.current = null;
    }

    markLineRef.current = candleSeriesRef.current.createPriceLine({
      price: Number(currentPrice),
      color: "#111111",
      lineWidth: 1,
      lineStyle: 1,
      axisLabelVisible: true,
      title: "MARK",
    });
  }, [currentPrice]);

  // Update price lines (entry/stop/target)
  useEffect(() => {
    if (!candleSeriesRef.current) return;

    // Clear old lines
    priceLinesRef.current.forEach(line => {
      candleSeriesRef.current.removePriceLine(line);
    });
    priceLinesRef.current = [];

    // Use decision for overlays (real or mock)
    const decision = selectedDecision;
    if (!decision) return;

    const entry = selectedPosition?.entry_price || decision.entry;
    const stop = selectedPosition?.stop_loss || decision.stop;
    const target = selectedPosition?.take_profit || decision.target;

    if (entry) {
      const line = candleSeriesRef.current.createPriceLine({
        price: Number(entry),
        color: '#2962FF',
        lineWidth: 2,
        lineStyle: 0,
        axisLabelVisible: true,
        title: 'ENTRY'
      });
      priceLinesRef.current.push(line);
    }

    if (stop) {
      const line = candleSeriesRef.current.createPriceLine({
        price: Number(stop),
        color: '#FF4D4F',
        lineWidth: 2,
        lineStyle: 2,
        axisLabelVisible: true,
        title: 'STOP'
      });
      priceLinesRef.current.push(line);
    }

    if (target) {
      const line = candleSeriesRef.current.createPriceLine({
        price: Number(target),
        color: '#00C853',
        lineWidth: 2,
        lineStyle: 2,
        axisLabelVisible: true,
        title: 'TARGET'
      });
      priceLinesRef.current.push(line);
    }
  }, [selectedDecision, selectedPosition]);

  // Calculate RR ratio
  const rrRatio = useMemo(() => {
    const decision = selectedDecision;
    if (!decision) return null;

    const entry = selectedPosition?.entry_price || decision.entry;
    const stop = selectedPosition?.stop_loss || decision.stop;
    const target = selectedPosition?.take_profit || decision.target;

    if (!entry || !stop || !target) return null;

    const risk = Math.abs(Number(entry) - Number(stop));
    const reward = Math.abs(Number(target) - Number(entry));

    return risk > 0 ? (reward / risk).toFixed(2) : null;
  }, [selectedDecision, selectedPosition]);

  // Calculate Y coordinates for risk/reward zones
  const zoneCoordinates = useMemo(() => {
    if (!chartRef.current) return null;

    const decision = selectedDecision;
    if (!decision) return null;

    const entry = selectedPosition?.entry_price || decision.entry;
    const stop = selectedPosition?.stop_loss || decision.stop;
    const target = selectedPosition?.take_profit || decision.target;

    if (!entry || !stop || !target) return null;

    try {
      const priceScale = chartRef.current.priceScale('right');
      const entryY = priceScale.priceToCoordinate(Number(entry));
      const stopY = priceScale.priceToCoordinate(Number(stop));
      const targetY = priceScale.priceToCoordinate(Number(target));

      return { entryY, stopY, targetY };
    } catch (e) {
      return null;
    }
  }, [selectedDecision, selectedPosition, candles]);

  return (
    <div className="h-full flex flex-col p-4 gap-3 relative" style={{ fontFamily: 'Gilroy, sans-serif' }}>
      {/* ─── Chart header ─────────────────────────────────────────────────
          Two stacked rows so primary identity and secondary context don't
          fight for space:
            Row 1 — symbol · status · RR
            Row 2 — Market structure · Execution mode · liquidity walls
          Controls (Heatmap toggle + Timeframe) live on the right and are
          two distinct groups, not a single ad-hoc row. */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1 min-w-0">
          {/* Row 1 */}
          <div className="flex items-center gap-3 flex-wrap">
            <div className="text-sm font-semibold text-gray-900">
              {state.selectedSymbol}
            </div>
            <div className="text-xs text-gray-500">
              {selectedPosition
                ? "Position active"
                : selectedDecision
                  ? "Decision ready"
                  : "No open position"}
            </div>
            {rrRatio && (
              <div className="text-xs font-semibold text-gray-700 px-2 py-0.5 rounded bg-gray-100">
                RR {rrRatio}
              </div>
            )}
          </div>

          {/* Row 2 — calm secondary context, no big shouting tags */}
          <div className="flex items-center gap-4 text-[11px] text-gray-500 flex-wrap">
            <span>
              <span className="text-gray-400">Market structure </span>
              <span className="text-gray-700 font-medium">Neutral</span>
            </span>
            <span>
              <span className="text-gray-400">Execution mode </span>
              <span className="text-gray-700 font-medium">Paper</span>
            </span>
            {heatmap?.summary && (
              <>
                <span aria-hidden className="text-gray-300">·</span>
                <span title="Top bid liquidity wall">
                  <span className="text-gray-400">Bid wall </span>
                  <span className="text-gray-700 tabular-nums">
                    {heatmap.summary.top_bid_wall?.toFixed(0) ?? "—"}
                  </span>
                </span>
                <span title="Top ask liquidity wall">
                  <span className="text-gray-400">Ask wall </span>
                  <span className="text-gray-700 tabular-nums">
                    {heatmap.summary.top_ask_wall?.toFixed(0) ?? "—"}
                  </span>
                </span>
              </>
            )}
          </div>
        </div>

        {/* ─── Controls: two distinct groups ───────────────────────────── */}
        <div className="flex items-center gap-3 flex-shrink-0">
          {/* Group 1 — Heatmap toggle */}
          <label className="flex items-center gap-2 text-xs text-gray-600 select-none">
            <span className="text-gray-500">Heatmap</span>
            <button
              type="button"
              role="switch"
              aria-checked={showHeatmap}
              onClick={() => setShowHeatmap((v) => !v)}
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                showHeatmap ? "bg-emerald-500" : "bg-gray-300"
              }`}
              data-testid="toggle-heatmap-btn"
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                  showHeatmap ? "translate-x-4" : "translate-x-0.5"
                }`}
              />
            </button>
          </label>

          {/* Group 2 — Timeframe (segmented control) */}
          <div
            role="tablist"
            aria-label="Timeframe"
            className="inline-flex items-center rounded-md bg-gray-100 p-0.5"
          >
            {timeframes.map((tf) => {
              const active = timeframe === tf;
              return (
                <button
                  key={tf}
                  role="tab"
                  aria-selected={active}
                  type="button"
                  onClick={() => setTimeframe(tf)}
                  className={`px-2.5 py-1 text-xs font-semibold rounded transition-colors ${
                    active
                      ? "bg-white text-gray-900 shadow-sm"
                      : "text-gray-600 hover:text-gray-900"
                  }`}
                  data-testid={`timeframe-${tf}`}
                >
                  {tf.toUpperCase()}
                </button>
              );
            })}
          </div>
        </div>
      </div>


      {/* Chart Container with Overlays */}
      <div className="flex-1 relative min-h-0">
        <div ref={chartContainerRef} className="absolute inset-0" />
        
        {/* Risk/Reward Zones Overlay */}
        {zoneCoordinates && (
          <div className="absolute inset-0 pointer-events-none">
            {/* Reward Zone (entry to target) */}
            <div
              style={{
                position: 'absolute',
                left: 0,
                right: 60,
                top: `${zoneCoordinates.targetY}px`,
                height: `${Math.abs(zoneCoordinates.entryY - zoneCoordinates.targetY)}px`,
                background: 'rgba(0, 200, 83, 0.12)',
                borderTop: '1px dashed rgba(0, 200, 83, 0.4)',
                borderBottom: '1px dashed rgba(0, 200, 83, 0.4)',
              }}
            />
            
            {/* Risk Zone (entry to stop) */}
            <div
              style={{
                position: 'absolute',
                left: 0,
                right: 60,
                top: `${zoneCoordinates.entryY}px`,
                height: `${Math.abs(zoneCoordinates.stopY - zoneCoordinates.entryY)}px`,
                background: 'rgba(255, 77, 79, 0.12)',
                borderTop: '1px dashed rgba(255, 77, 79, 0.4)',
                borderBottom: '1px dashed rgba(255, 77, 79, 0.4)',
              }}
            />
          </div>
        )}
        
        {/* Liquidity Heatmap Overlay */}
        {showHeatmap && chartRef.current && heatmap && (
          <LiquidityHeatmapOverlay chart={chartRef.current} heatmap={heatmap} />
        )}
        
        {/* Position PnL Overlay */}
        {chartRef.current && selectedPosition && (
          <PositionPnlOverlay
            chart={chartRef.current}
            position={selectedPosition}
            currentPrice={currentPrice}
          />
        )}
        
        {/* Decision Overlay */}
        {selectedDecision && chartRef.current && (
          <DecisionOverlay decision={selectedDecision} chart={chartRef.current} />
        )}
        
        {/* Execution Replay Overlay */}
        {fills.length > 0 && chartRef.current && (
          <ExecutionReplayOverlay fills={fills} chart={chartRef.current} />
        )}
        
        {/* Chart Empty State Overlay - with fade animation */}
        {!hideNoTradeOverlay && !selectedDecision && !loading && (
          <div 
            className="absolute inset-0 flex items-center justify-center pointer-events-none z-10 animate-fade-in"
            style={{ animation: 'fadeIn 300ms ease-out' }}
          >
            <div className="bg-white/80 backdrop-blur-md px-8 py-6 rounded-2xl border border-neutral-300 shadow-lg text-center max-w-md">
              <div className="text-xl font-bold text-neutral-900 mb-2">
                NO TRADE
              </div>
              <div className="text-sm text-neutral-700 mb-1">
                Market has no edge.
              </div>
              <div className="text-sm text-neutral-600">
                Wait for breakout or imbalance.
              </div>
              <div className="text-sm text-neutral-500 mt-3 font-medium">
                → Stay flat
              </div>
            </div>
          </div>
        )}
        
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center text-sm text-neutral-500 bg-white bg-opacity-80">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 border-2 border-neutral-300 border-t-neutral-600 rounded-full animate-spin" />
              <span>Loading chart...</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
