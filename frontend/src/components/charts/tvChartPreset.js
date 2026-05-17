/**
 * TV Chart Factory - ЕДИНСТВЕННЫЙ способ создания графика
 * =======================================================
 * 
 * Используется во ВСЕХ вкладках:
 * - Forecast
 * - Exchange  
 * - On-chain
 * - Sentiment
 * 
 * Гарантирует:
 * - Одинаковый zoom на колесо мыши
 * - Drag для скролла
 * - Pinch для mobile
 * - Аккуратный стартовый масштаб
 * - Нет "огромных свечей"
 */

import { createChart, CandlestickSeries, LineSeries, AreaSeries, HistogramSeries, BaselineSeries, createSeriesMarkers } from 'lightweight-charts';

// V5 marker tracking — keeps references for cleanup
const _markerPrimitives = new WeakMap();

/**
 * V5-compatible setMarkers wrapper
 * Replaces series.setMarkers() which was removed in v5
 */
export function setSeriesMarkers(series, markers) {
  // Remove existing markers
  const existing = _markerPrimitives.get(series);
  if (existing && typeof existing.detach === 'function') {
    existing.detach();
  }
  // Create new markers
  if (markers && markers.length > 0) {
    const primitive = createSeriesMarkers(series, markers);
    _markerPrimitives.set(series, primitive);
  } else {
    _markerPrimitives.delete(series);
  }
}

export function createTvChart(container) {
  const chart = createChart(container, {
    layout: {
      background: { type: 'solid', color: '#ffffff' },
      textColor: '#111',
      fontFamily: "Inter, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
      fontSize: 12,
    },

    // Fix locale issue - use simple locale without posix suffix
    localization: {
      locale: 'en',
      dateFormat: 'yyyy-MM-dd',
    },

    grid: {
      vertLines: { color: 'rgba(17, 24, 39, 0.06)' },
      horzLines: { color: 'rgba(17, 24, 39, 0.06)' },
    },

    rightPriceScale: {
      borderVisible: false,
      scaleMargins: {
        top: 0.15,
        bottom: 0.15,
      },
    },

    timeScale: {
      rightOffset: 12,
      barSpacing: 4,  // V3.11: More compact - shows more candles
      minBarSpacing: 1,
      fixLeftEdge: false,
      fixRightEdge: false,
      rightBarStaysOnScroll: false,
      lockVisibleTimeRangeOnResize: false,
      timeVisible: true,
      secondsVisible: false,
      borderVisible: false,
      tickMarkFormatter: (time) => {
        const date = new Date(time * 1000);
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const month = months[date.getMonth()];
        const day = date.getDate();
        return `${month} ${day}`;
      },
    },

    handleScroll: {
      mouseWheel: true,
      pressedMouseMove: true,
      horzTouchDrag: true,
      vertTouchDrag: false,
    },

    handleScale: {
      mouseWheel: true,
      pinch: true,
      axisPressedMouseMove: true,
    },

    crosshair: {
      mode: 1,
    },
  });

  // V5 migration: addSeries(SeriesType, options) replaces addXxxSeries(options)
  chart.addCandlestickSeries = (opts) => chart.addSeries(CandlestickSeries, opts);
  chart.addLineSeries = (opts) => chart.addSeries(LineSeries, opts);
  chart.addAreaSeries = (opts) => chart.addSeries(AreaSeries, opts);
  chart.addHistogramSeries = (opts) => chart.addSeries(HistogramSeries, opts);
  chart.addBaselineSeries = (opts) => chart.addSeries(BaselineSeries, opts);

  return chart;
}

// Candle series options (one style for all)
export const TV_CANDLE_OPTIONS = {
  upColor: 'rgba(34, 197, 94, 0.80)',
  downColor: 'rgba(239, 68, 68, 0.80)',
  borderVisible: false,
  wickUpColor: 'rgba(34, 197, 94, 0.55)',
  wickDownColor: 'rgba(239, 68, 68, 0.55)',
  lastValueVisible: true,
  priceLineVisible: false,
};

// Volume series options
export const TV_VOLUME_OPTIONS = {
  priceFormat: { type: 'volume' },
  priceScaleId: '',
  scaleMargins: {
    top: 0.8,
    bottom: 0,
  },
  color: 'rgba(0, 0, 0, 0.08)',
};

// For backwards compatibility
export const TV_CHART_OPTIONS = null; // Use createTvChart() instead
