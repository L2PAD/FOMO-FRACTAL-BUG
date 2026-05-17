/**
 * LIVE PREDICTION CHART — Production-ready TradingView-like
 * 
 * Built with lightweight-charts for professional trading experience.
 * 
 * Features:
 * - Real OHLC candles + volume
 * - Active prediction overlay
 * - Archived predictions (gray, trimmed by next.asOf)
 * - Zoom/scroll/crosshair
 * - NO vertical NOW line
 * - Horizon controls timescale (not TF selector)
 */

import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { createChart, CrosshairMode, CandlestickSeries, HistogramSeries, LineSeries } from 'lightweight-charts';
import { Eye, EyeOff, RefreshCw, TrendingUp, TrendingDown, Minus } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function isoToUnixSeconds(iso) {
  return Math.floor(new Date(iso).getTime() / 1000);
}

function dateToUnix(dateStr) {
  // Handle both ISO and YYYY-MM-DD formats
  // Return as string 'YYYY-MM-DD' for lightweight-charts
  if (dateStr.includes('T')) {
    return dateStr.split('T')[0];
  }
  return dateStr;
}

function mapSeries(series) {
  if (!series || !Array.isArray(series)) return [];
  return series
    .map(p => ({
      time: dateToUnix(p.t),
      value: p.v
    }))
    .filter(p => p.time && isFinite(p.value))
    .sort((a, b) => a.time.localeCompare(b.time));
}

function trimByNextAsOf(points, nextAsOfIso) {
  if (!nextAsOfIso || !points.length) return points;
  const cutoff = dateToUnix(nextAsOfIso);
  return points.filter(p => p.time <= cutoff);
}

// Horizon to lookback days mapping (E1 spec: for short horizons show more context)
// lookbackDays = max(90, horizonDays * 3)
const HORIZON_LOOKBACK = {
  7: 90,    // 7d horizon → show 90 days history
  14: 90,   // 14d horizon → show 90 days history
  30: 90,   // 30d horizon → show 90 days history
  90: 270,  // 90d horizon → show 270 days history
  180: 540, // 180d horizon → show 540 days history
  365: 1095 // 365d horizon → show ~3 years history
};

// Helper to calculate visible range dates
function getVisibleRange(horizonDays, candles) {
  if (!candles || candles.length === 0) return null;
  
  const lookbackDays = HORIZON_LOOKBACK[horizonDays] || Math.max(90, horizonDays * 3);
  const lastCandleDate = candles[candles.length - 1]?.time;
  
  if (!lastCandleDate) return null;
  
  // Calculate start date
  const endDate = new Date(lastCandleDate);
  const startDate = new Date(endDate);
  startDate.setDate(startDate.getDate() - lookbackDays);
  
  // Calculate forecast end (anchor + horizon)
  const forecastEnd = new Date(endDate);
  forecastEnd.setDate(forecastEnd.getDate() + horizonDays + 5); // +5 for padding
  
  return {
    from: startDate.toISOString().split('T')[0],
    to: forecastEnd.toISOString().split('T')[0]
  };
}

// ═══════════════════════════════════════════════════════════════
// CHART COMPONENT
// ═══════════════════════════════════════════════════════════════

export const LivePredictionChart = ({
  asset = 'BTC',
  horizonDays = 180,
  view = 'hybrid',
  viewMode = 'candle',
  onDataLoad = null
}) => {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const closeLineSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const activePredRef = useRef(null);
  const archivedRefs = useRef([]);
  const bandRef = useRef(null);
  const rawCandlesRef = useRef([]);
  
  const [showHistory, setShowHistory] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hoverData, setHoverData] = useState(null);
  const [activeSnapshotInfo, setActiveSnapshotInfo] = useState(null);
  
  // Fetch candles - use full history endpoint
  const fetchCandles = useCallback(async () => {
    // Use /api/ui/candles for full history (2 years)
    const url = `${API_URL}/api/ui/candles?asset=${asset}&years=2`;
    
    try {
      const res = await fetch(url);
      const data = await res.json();
      
      if (data.ok && data.candles) {
        return data.candles.map(c => {
          // Convert ISO date to YYYY-MM-DD for lightweight-charts
          let time = c.t;
          if (time && time.includes('T')) {
            time = time.split('T')[0];
          }
          return {
            time,
            open: c.o,
            high: c.h,
            low: c.l,
            close: c.c,
            volume: c.v || 0
          };
        }).filter(c => c.time).sort((a, b) => a.time.localeCompare(b.time));
      }
      return [];
    } catch (e) {
      console.error('[LiveChart] Candles fetch error:', e);
      return [];
    }
  }, [asset]);
  
  // Fetch snapshots
  const fetchSnapshots = useCallback(async () => {
    const url = `${API_URL}/api/prediction/snapshots?asset=${asset}&view=${view}&horizon=${horizonDays}&limit=20`;
    
    try {
      const res = await fetch(url);
      const data = await res.json();
      
      if (data.ok && data.snapshots) {
        return data.snapshots;
      }
      return [];
    } catch (e) {
      console.error('[LiveChart] Snapshots fetch error:', e);
      return [];
    }
  }, [asset, view, horizonDays]);
  
  // Initialize chart
  useEffect(() => {
    if (!containerRef.current) return;
    
    const chart = createChart(containerRef.current, {
      height: containerRef.current.clientHeight || 520,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333333',
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif"
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' }
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { labelVisible: true },
        horzLine: { labelVisible: true }
      },
      rightPriceScale: {
        borderColor: '#e5e5e5',
        scaleMargins: { top: 0.1, bottom: 0.2 }
      },
      timeScale: {
        borderColor: '#e5e5e5',
        rightOffset: 5,
        barSpacing: 4,
        fixLeftEdge: true,
        timeVisible: false,
        secondsVisible: false
      },
      localization: {
        locale: 'en-US',
        dateFormat: 'yyyy-MM-dd'
      },
      handleScale: { axisPressedMouseMove: true },
      handleScroll: { pressedMouseMove: true }
    });
    
    // Candlestick series (v5 API)
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#16a34a',
      downColor: '#dc2626',
      borderUpColor: '#16a34a',
      borderDownColor: '#dc2626',
      wickUpColor: '#16a34a',
      wickDownColor: '#dc2626'
    });
    
    // Close-price line series (for line viewMode)
    const closeLineSeries = chart.addSeries(LineSeries, {
      color: '#2563eb',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: true,
      visible: false,
    });
    
    // Volume series (v5 API)
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: '',
      scaleMargins: { top: 0.85, bottom: 0 }
    });
    
    // Active prediction line (v5 API)
    const activePred = chart.addSeries(LineSeries, {
      color: '#111827',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: true
    });
    
    // Subscribe to crosshair
    chart.subscribeCrosshairMove(param => {
      if (!param || !param.time) {
        setHoverData(null);
        return;
      }
      
      const candleData = param.seriesData.get(candleSeries);
      const predData = param.seriesData.get(activePred);
      
      setHoverData({
        time: param.time,
        candle: candleData,
        prediction: predData?.value
      });
    });
    
    // Resize observer
    const ro = new ResizeObserver(() => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight
        });
      }
    });
    ro.observe(containerRef.current);
    
    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    closeLineSeriesRef.current = closeLineSeries;
    volumeSeriesRef.current = volumeSeries;
    activePredRef.current = activePred;
    
    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      closeLineSeriesRef.current = null;
      volumeSeriesRef.current = null;
      activePredRef.current = null;
      archivedRefs.current = [];
    };
  }, []);
  
  // Load data
  useEffect(() => {
    let cancelled = false;
    
    async function loadData() {
      if (!chartRef.current || !candleSeriesRef.current || !volumeSeriesRef.current || !activePredRef.current) {
        return;
      }
      
      setLoading(true);
      setError(null);
      
      // Clear archived series
      for (const s of archivedRefs.current) {
        try {
          chartRef.current.removeSeries(s);
        } catch (e) {}
      }
      archivedRefs.current = [];
      
      // Clear band if exists
      if (bandRef.current) {
        try {
          chartRef.current.removeSeries(bandRef.current);
        } catch (e) {}
        bandRef.current = null;
      }
      
      try {
        const [candles, snapshots] = await Promise.all([
          fetchCandles(),
          fetchSnapshots()
        ]);
        
        if (cancelled) return;
        
        if (candles.length === 0) {
          setError('No candle data available');
          setLoading(false);
          return;
        }
        
        // Set candles (use string dates for lightweight-charts)
        candleSeriesRef.current.setData(candles.map(c => ({
          time: c.time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close
        })));
        
        // Set close-price line data (for line viewMode)
        if (closeLineSeriesRef.current) {
          closeLineSeriesRef.current.setData(candles.map(c => ({
            time: c.time,
            value: c.close,
          })));
        }
        rawCandlesRef.current = candles;
        
        // Set volume
        volumeSeriesRef.current.setData(
          candles.map(c => ({
            time: c.time,
            value: c.volume || 0,
            color: c.close >= c.open ? 'rgba(22,163,74,0.2)' : 'rgba(220,38,38,0.2)'
          }))
        );
        
        // Sort snapshots by asOf ascending
        const sortedSnapshots = [...snapshots].sort(
          (a, b) => isoToUnixSeconds(a.asOf) - isoToUnixSeconds(b.asOf)
        );
        
        let activeSnapshot = sortedSnapshots.at(-1);
        
        // FALLBACK: If no snapshots available, fetch from /api/ui/overview
        if (!activeSnapshot || !activeSnapshot.series) {
          console.log(`[LiveChart] No snapshots for ${asset}/${view}/${horizonDays}d, falling back to overview`);
          try {
            const overviewRes = await fetch(`${API_URL}/api/ui/overview?asset=${asset}&horizon=${horizonDays}`);
            const overviewData = await overviewRes.json();
            
            if (overviewData.ok && overviewData.charts) {
              // Build series from overview charts (actual + predicted)
              const actualSeries = (overviewData.charts.actual || []).map(p => ({
                t: p.t,
                v: p.v
              }));
              const predictedSeries = (overviewData.charts.predicted || []).map(p => ({
                t: p.t,
                v: p.v
              }));
              
              // Combine: full actual + predicted (excluding duplicate anchor)
              const combinedSeries = [...actualSeries];
              if (predictedSeries.length > 0) {
                // Skip first predicted if it matches last actual
                const startIdx = actualSeries.length > 0 && 
                  predictedSeries[0]?.t === actualSeries[actualSeries.length - 1]?.t ? 1 : 0;
                combinedSeries.push(...predictedSeries.slice(startIdx));
              }
              
              activeSnapshot = {
                series: combinedSeries,
                metadata: {
                  stance: overviewData.verdict?.stance || 'HOLD',
                  confidence: (overviewData.verdict?.confidencePct || 50) / 100
                },
                asOf: overviewData.asOf,
                _source: 'overview_fallback'
              };
              
              console.log(`[LiveChart] Overview fallback loaded: ${combinedSeries.length} points`);
            }
          } catch (e) {
            console.error('[LiveChart] Overview fallback error:', e);
          }
        }
        
        // Set active prediction
        if (activeSnapshot?.series) {
          const predSeries = mapSeries(activeSnapshot.series);
          activePredRef.current.setData(predSeries);
          
          // Set active snapshot info for display
          setActiveSnapshotInfo({
            stance: activeSnapshot.metadata?.stance || 'HOLD',
            confidence: activeSnapshot.metadata?.confidence || 0.5,
            asOf: activeSnapshot.asOf,
            createdAt: activeSnapshot.createdAt
          });
          
          // Notify parent
          if (onDataLoad) {
            onDataLoad({
              stance: activeSnapshot.metadata?.stance,
              confidence: activeSnapshot.metadata?.confidence,
              asOf: activeSnapshot.asOf
            });
          }
          
          // Add confidence band if available
          if (activeSnapshot.band?.p10 && activeSnapshot.band?.p90) {
            // For bands we'd need area series - simplified for now
          }
        } else {
          activePredRef.current.setData([]);
          setActiveSnapshotInfo(null);
        }
        
        // Add archived predictions
        if (showHistory && sortedSnapshots.length > 1) {
          for (let i = 0; i < sortedSnapshots.length - 1; i++) {
            const snap = sortedSnapshots[i];
            const nextSnap = sortedSnapshots[i + 1];
            
            if (!snap.series) continue;
            
            const trimmedSeries = trimByNextAsOf(
              mapSeries(snap.series),
              nextSnap.asOf
            );
            
            if (trimmedSeries.length < 2) continue;
            
            const archivedLine = chartRef.current.addSeries(LineSeries, {
              color: 'rgba(107,114,128,0.35)',
              lineWidth: 1,
              lineStyle: 2, // Dashed
              priceLineVisible: false,
              lastValueVisible: false,
              crosshairMarkerVisible: false
            });
            
            archivedLine.setData(trimmedSeries);
            archivedRefs.current.push(archivedLine);
          }
        }
        
        // Set visible range based on horizon (E1 spec: zoom for short horizons)
        // Data is always full history, but visible range changes with horizon
        const visibleRange = getVisibleRange(horizonDays, candles);

        // Apply viewMode visibility
        const isLine = viewMode === 'line';
        if (candleSeriesRef.current) candleSeriesRef.current.applyOptions({ visible: !isLine });
        if (closeLineSeriesRef.current) closeLineSeriesRef.current.applyOptions({ visible: isLine });
        if (volumeSeriesRef.current) volumeSeriesRef.current.applyOptions({ visible: !isLine });

        if (visibleRange) {
          chartRef.current.timeScale().setVisibleRange({
            from: visibleRange.from,
            to: visibleRange.to
          });
          console.log(`[LiveChart] Set visible range for ${horizonDays}d: ${visibleRange.from} to ${visibleRange.to}`);
        } else {
          // Fallback to fit all content
          chartRef.current.timeScale().fitContent();
        }
        
      } catch (e) {
        if (!cancelled) {
          setError(e.message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    
    loadData();
    
    return () => {
      cancelled = true;
    };
  }, [asset, horizonDays, view, showHistory, fetchCandles, fetchSnapshots, onDataLoad]);
  
  // Toggle candle/line view mode
  useEffect(() => {
    if (!candleSeriesRef.current || !closeLineSeriesRef.current) return;
    const isLine = viewMode === 'line';
    candleSeriesRef.current.applyOptions({ visible: !isLine });
    closeLineSeriesRef.current.applyOptions({ visible: isLine });
    if (volumeSeriesRef.current) {
      volumeSeriesRef.current.applyOptions({ visible: !isLine });
    }
  }, [viewMode]);
  
  // Stance icon
  const StanceIcon = useMemo(() => {
    if (!activeSnapshotInfo) return Minus;
    switch (activeSnapshotInfo.stance) {
      case 'BULLISH': return TrendingUp;
      case 'BEARISH': return TrendingDown;
      default: return Minus;
    }
  }, [activeSnapshotInfo]);
  
  const stanceColor = useMemo(() => {
    if (!activeSnapshotInfo) return 'text-gray-500';
    switch (activeSnapshotInfo.stance) {
      case 'BULLISH': return 'text-emerald-600';
      case 'BEARISH': return 'text-red-600';
      default: return 'text-gray-600';
    }
  }, [activeSnapshotInfo]);
  
  return (
    <div className="relative w-full" data-testid="live-prediction-chart">
      {/* Chart Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-gray-600" data-testid="fractal-title">Fractal</span>
          {activeSnapshotInfo && (
            <>
              <StanceIcon className={`w-4 h-4 ${stanceColor}`} />
              <span
                className={`text-sm font-bold ${stanceColor}`}
                data-testid="fractal-stance"
              >
                {activeSnapshotInfo.stance === 'BULLISH' ? 'Bullish'
                  : activeSnapshotInfo.stance === 'BEARISH' ? 'Bearish'
                  : 'HOLD'}
              </span>
              <span className="text-sm font-medium text-gray-500" data-testid="fractal-confidence">
                {Math.round(activeSnapshotInfo.confidence * 100)}%
              </span>
            </>
          )}
        </div>
        
        <div className="flex items-center gap-2">
          {/* History Toggle */}
          <button
            onClick={() => setShowHistory(v => !v)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg transition-all ${
              showHistory 
                ? 'bg-gray-900 text-white' 
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
            data-testid="history-toggle"
          >
            {showHistory ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            History
          </button>
          
          {/* Refresh */}
          <button
            onClick={() => window.location.reload()}
            className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>
      
      {/* Error State */}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-10 rounded-2xl">
          <div className="text-center">
            <p className="text-red-600 mb-2">{error}</p>
            <button 
              onClick={() => window.location.reload()}
              className="text-sm text-gray-600 hover:text-gray-800"
            >
              Try again
            </button>
          </div>
        </div>
      )}
      
      {/* Loading Overlay */}
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/60 z-10 rounded-2xl">
          <RefreshCw className="w-8 h-8 text-gray-400 animate-spin" />
        </div>
      )}
      
      {/* Hover Tooltip */}
      {hoverData?.candle && (
        <div 
          className="absolute top-12 left-4 bg-white border border-gray-100 rounded-xl shadow-lg p-3 z-20 min-w-[160px]"
          style={{ pointerEvents: 'none' }}
        >
          <div className="text-xs text-gray-500 mb-2">
            {typeof hoverData.time === 'string' ? hoverData.time : new Date(hoverData.time * 1000).toISOString().split('T')[0]}
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <span className="text-gray-400">O</span>
            <span className="font-medium text-right">{hoverData.candle.open?.toLocaleString('en-US')}</span>
            <span className="text-gray-400">H</span>
            <span className="font-medium text-right">{hoverData.candle.high?.toLocaleString('en-US')}</span>
            <span className="text-gray-400">L</span>
            <span className="font-medium text-right">{hoverData.candle.low?.toLocaleString('en-US')}</span>
            <span className="text-gray-400">C</span>
            <span className="font-medium text-right">{hoverData.candle.close?.toLocaleString('en-US')}</span>
          </div>
          {hoverData.prediction && (
            <div className="mt-2 pt-2 border-t border-gray-100">
              <span className="text-gray-400 text-xs">Prediction: </span>
              <span className="font-medium text-xs">{hoverData.prediction.toLocaleString('en-US')}</span>
            </div>
          )}
        </div>
      )}
      
      {/* Chart Container */}
      <div 
        ref={containerRef} 
        className="w-full rounded-2xl border border-gray-100 overflow-hidden"
        style={{ height: '65vh', minHeight: '400px' }}
      />
      
      {/* Legend */}
      <div className="flex items-center gap-6 mt-3 text-xs text-gray-500">
        <div className="flex items-center gap-2">
          <div className="w-4 h-0.5 bg-gray-900"></div>
          <span>Active Prediction</span>
        </div>
        {showHistory && (
          <div className="flex items-center gap-2">
            <div className="w-4 h-0.5 bg-gray-400/50" style={{ borderTop: '1px dashed' }}></div>
            <span>History (not corrected)</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default LivePredictionChart;
