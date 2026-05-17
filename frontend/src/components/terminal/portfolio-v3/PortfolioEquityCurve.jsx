import { useEffect, useRef } from 'react';
import * as LightweightCharts from 'lightweight-charts';

export default function PortfolioEquityCurve({ data }) {
  const chartContainerRef = useRef();
  const chartRef = useRef();
  const seriesRef = useRef();

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create chart — Bloomberg style (контраст = читаемость)
    const chart = LightweightCharts.createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 480,
      layout: {
        background: { color: '#FFFFFF' },
        textColor: '#111827'
      },
      grid: {
        vertLines: { color: 'rgba(0,0,0,0.03)' },
        horzLines: { color: 'rgba(0,0,0,0.03)' }
      },
      timeScale: {
        borderColor: 'rgba(0,0,0,0.06)',
        timeVisible: true,
        secondsVisible: false
      },
      rightPriceScale: {
        borderColor: 'rgba(0,0,0,0.06)'
      },
      crosshair: {
        mode: 1,
        vertLine: {
          color: '#6b7280',
          width: 1,
          style: 1,
          labelBackgroundColor: '#111827'
        },
        horzLine: {
          color: '#6b7280',
          width: 1,
          style: 1,
          labelBackgroundColor: '#111827'
        }
      }
    });

    // Bloomberg style: почти чёрный, НЕ зелёный!
    const areaSeries = chart.addSeries(LightweightCharts.AreaSeries, {
      lineColor: '#111827',
      lineWidth: 2.5,
      topColor: 'rgba(17,24,39,0.08)',
      bottomColor: 'rgba(17,24,39,0.01)',
      priceLineVisible: false
    });

    areaSeries.setData(data);

    chartRef.current = chart;
    seriesRef.current = areaSeries;

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
      }
    };
  }, [data]);

  return (
    <div className="rounded-[var(--radius)] bg-[hsl(var(--surface))] overflow-hidden" data-testid="portfolio-equity-curve">
      {/* NO HEADER — данные → смысл → структура */}
      <div ref={chartContainerRef} className="w-full" />
    </div>
  );
}
