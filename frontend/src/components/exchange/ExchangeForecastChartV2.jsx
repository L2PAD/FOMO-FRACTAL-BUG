/**
 * Exchange Forecast Chart V2
 * ===========================
 * 
 * BLOCK E2: Production-grade chart for Exchange UI
 * 
 * Features:
 * - Real Binance candlesticks (green/red)
 * - Future forecast candles (blue/purple, after NOW)
 * - NOW vertical divider
 * - Projection line (entry → target)
 * - Reliability markers
 */

import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, CrosshairMode, LineSeries, CandlestickSeries, HistogramSeries, AreaSeries, createSeriesMarkers } from "lightweight-charts";

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const chartOptions = {
  layout: {
    background: { type: ColorType.Solid, color: '#ffffff' },
    textColor: '#1f2937',
  },
  grid: {
    vertLines: { color: '#f3f4f6' },
    horzLines: { color: '#f3f4f6' },
  },
  crosshair: {
    mode: CrosshairMode.Normal,
    vertLine: { color: '#9ca3af', width: 1, style: 2 },
    horzLine: { color: '#9ca3af', width: 1, style: 2 },
  },
  rightPriceScale: {
    borderColor: '#e5e7eb',
    scaleMargins: { top: 0.1, bottom: 0.2 },
  },
  timeScale: {
    borderColor: '#e5e7eb',
    timeVisible: true,
    secondsVisible: false,
  },
};

export default function ExchangeForecastChartV2({ symbol = 'BTC', horizon = '7D' }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch data
  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`${API_URL}/api/market/chart/exchange-v2?symbol=${symbol}&horizon=${horizon}`)
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch chart data');
        return res.json();
      })
      .then(d => { setData(d); setLoading(false); })
      .catch(err => { setError(err.message); setLoading(false); });
  }, [symbol, horizon]);

  // Render chart
  useEffect(() => {
    if (!containerRef.current || loading || !data) return;

    // Clean up
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }
    // Remove old overlays
    containerRef.current.querySelectorAll('[data-overlay]').forEach(el => el.remove());

    const chart = createChart(containerRef.current, {
      ...chartOptions,
      width: containerRef.current.clientWidth,
      height: 420,
      localization: { locale: 'en-US' },
    });
    chartRef.current = chart;

    const { chart: chartData, forecast } = data;
    const allCandles = chartData?.candles || [];
    const nowSec = Math.floor(Date.now() / 1000);

    // Split candles: real (before NOW) and future (after NOW)
    const realCandles = allCandles.filter(c => c.time <= nowSec);
    const futureCandles = allCandles.filter(c => c.time > nowSec);

    // Real candles series (green/red)
    const realSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#16a34a',
      downColor: '#dc2626',
      borderVisible: false,
      wickUpColor: '#16a34a',
      wickDownColor: '#dc2626',
    });
    if (realCandles.length) realSeries.setData(realCandles);

    // Future candles series (blue tones)
    if (futureCandles.length) {
      const futureSeries = chart.addSeries(CandlestickSeries, {
        upColor: '#3b82f6',
        downColor: '#8b5cf6',
        borderVisible: false,
        wickUpColor: '#3b82f6',
        wickDownColor: '#8b5cf6',
      });
      futureSeries.setData(futureCandles);
    }

    // Projection line (entry → target, dashed blue)
    if (chartData?.projectionLine?.length) {
      const projSeries = chart.addSeries(LineSeries, {
        color: '#2563eb',
        lineWidth: 2,
        lineStyle: 2,
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
      });
      projSeries.setData(chartData.projectionLine.map(p => ({ time: p.time, value: p.value })));
    }

    // Target price line
    if (forecast?.targetFinal && realSeries) {
      realSeries.createPriceLine({
        price: forecast.targetFinal,
        color: '#2563eb',
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: 'Target',
      });
    }

    // Markers
    if (chartData?.markers?.length && realCandles.length) {
      const markers = chartData.markers.map(m => ({
        time: m.time,
        position: 'aboveBar',
        color: m.type === 'SAFE_MODE' ? '#f59e0b' :
               m.type === 'URI_ADJUSTMENT' ? '#3b82f6' : '#6b7280',
        shape: 'circle',
        text: m.text,
      }));
      createSeriesMarkers(realSeries, markers);
    }

    chart.timeScale().fitContent();

    // NOW vertical overlay
    const container = containerRef.current;
    const nowLine = document.createElement('div');
    nowLine.setAttribute('data-overlay', 'now-line');
    Object.assign(nowLine.style, {
      position: 'absolute', top: '0', bottom: '30px', width: '2px',
      background: '#7c3aed', opacity: '0.6', pointerEvents: 'none', zIndex: '10',
      display: 'none',
    });
    container.appendChild(nowLine);

    const nowLabel = document.createElement('div');
    nowLabel.setAttribute('data-overlay', 'now-label');
    Object.assign(nowLabel.style, {
      position: 'absolute', bottom: '32px', fontSize: '9px', fontWeight: '700',
      color: '#7c3aed', pointerEvents: 'none', zIndex: '11', display: 'none',
    });
    nowLabel.textContent = 'NOW';
    container.appendChild(nowLabel);

    // Sync NOW position
    let rafId;
    const syncNow = () => {
      const x = chart.timeScale().timeToCoordinate(nowSec);
      if (x !== null && x >= 0) {
        nowLine.style.left = `${x}px`;
        nowLine.style.display = '';
        nowLabel.style.left = `${x - 10}px`;
        nowLabel.style.display = '';
      } else {
        nowLine.style.display = 'none';
        nowLabel.style.display = 'none';
      }
      rafId = requestAnimationFrame(syncNow);
    };
    rafId = requestAnimationFrame(syncNow);

    // Resize
    const ro = new ResizeObserver(entries => {
      if (entries.length > 0) {
        const { width } = entries[0].contentRect;
        chart.applyOptions({ width });
      }
    });
    ro.observe(container);

    return () => {
      if (rafId) cancelAnimationFrame(rafId);
      ro.disconnect();
      container.querySelectorAll('[data-overlay]').forEach(el => el.remove());
      chart.remove();
      chartRef.current = null;
    };
  }, [data, loading]);

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6 h-[420px] flex items-center justify-center">
        <div className="w-8 h-8 border-3 border-gray-200 border-t-blue-600 rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6 h-[420px] flex items-center justify-center">
        <p className="text-red-600 font-medium">Error loading chart</p>
        <p className="text-sm text-gray-500 mt-1">{error}</p>
      </div>
    );
  }

  const direction = data?.forecast?.direction || 'NEUTRAL';
  const dirColor = direction === 'LONG' ? '#16a34a' : direction === 'SHORT' ? '#dc2626' : '#6b7280';
  const confidence = Math.round((data?.reliability?.finalConfidence || 0) * 100);
  const source = data?.explain?.core?.notes?.[0] || '';

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h3 className="font-semibold text-gray-900" data-testid="exchange-chart-title">
            {symbol} Exchange Forecast
          </h3>
          <span
            className="text-xs font-medium"
            style={{ color: dirColor }}
            data-testid="exchange-chart-direction"
          >
            {direction}
          </span>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-gray-500">
            Confidence: <span className="font-medium text-gray-900" data-testid="exchange-chart-confidence">{confidence}%</span>
          </span>
          <span className="text-gray-500">
            Horizon: <span className="font-medium text-gray-900">{horizon}</span>
          </span>
          {source.startsWith('Source:') && (
            <span className="text-[10px] text-gray-400">{source}</span>
          )}
        </div>
      </div>
      <div ref={containerRef} style={{ height: 420, position: 'relative' }} data-testid="exchange-chart-container" />
      {data?.meta?.safeMode && (
        <div className="px-4 py-2 bg-amber-50 border-t border-amber-200">
          <div className="flex items-center gap-2 text-amber-800 text-sm">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            <span className="font-medium">SAFE MODE</span>
            <span className="text-amber-600">— Signal voided due to low reliability</span>
          </div>
        </div>
      )}
    </div>
  );
}
