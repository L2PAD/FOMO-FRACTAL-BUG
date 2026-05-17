/**
 * OnChain Forecast Chart V2
 * ==========================
 * 
 * BLOCK O9.5: Production-grade chart for OnChain Prediction UI
 * Uses governance-enriched /final/:symbol endpoint
 */

import { useEffect, useRef, useState, useMemo, useCallback } from "react";
import { createChart, ColorType, CrosshairMode, IChartApi, ISeriesApi } from "lightweight-charts";
import { OnchainFinalOutput, OnchainPoint, GuardrailState } from "../../lib/onchain/types";
import { formatGuardrailState, formatConfidence, biasLabel } from "../../lib/onchain/analytics";

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Map window selection to API format
const WINDOW_MAP: Record<string, string> = {
  '1D': '24h',
  '7D': '7d',
  '30D': '30d',
};

// Guardrail state colors
const GUARDRAIL_COLORS: Record<string, { line: string; bg: string }> = {
  HEALTHY: { line: '#10b981', bg: 'rgba(16, 185, 129, 0.1)' },
  WARN: { line: '#f59e0b', bg: 'rgba(245, 158, 11, 0.1)' },
  DEGRADED: { line: '#f97316', bg: 'rgba(249, 115, 22, 0.1)' },
  CRITICAL: { line: '#ef4444', bg: 'rgba(239, 68, 68, 0.1)' },
  FROZEN: { line: '#6b7280', bg: 'rgba(107, 114, 128, 0.1)' },
};

interface Props {
  symbol?: string;
  horizon?: string;
  height?: number;
}

export default function OnChainForecastChartV2({ 
  symbol = 'ETH', 
  horizon = '30D',
  height = 420 
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const scoreSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const confidenceSeriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const isDisposedRef = useRef(false);
  const prevSymbolRef = useRef<string>(symbol);

  const [data, setData] = useState<OnchainFinalOutput | null>(null);
  const [chartPoints, setChartPoints] = useState<OnchainPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chartKey, setChartKey] = useState(0);

  // Cleanup function
  const cleanupChart = useCallback(() => {
    isDisposedRef.current = true;
    if (chartRef.current) {
      try {
        chartRef.current.remove();
      } catch (e) {
        // Ignore cleanup errors
      }
      chartRef.current = null;
      scoreSeriesRef.current = null;
      confidenceSeriesRef.current = null;
    }
  }, []);

  // Reset chart when symbol changes
  useEffect(() => {
    if (prevSymbolRef.current !== symbol) {
      prevSymbolRef.current = symbol;
      setChartKey(k => k + 1);
      cleanupChart();
    }
  }, [symbol, cleanupChart]);

  // Fetch data
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setChartPoints([]); // Clear old data immediately

    const fetchData = async () => {
      try {
        const finalRes = await fetch(`${API_URL}/api/v10/onchain-v2/final/${symbol}`);
        if (!finalRes.ok) throw new Error('Failed to fetch OnChain data');
        const finalJson = await finalRes.json();
        
        if (cancelled) return;
        
        if (finalJson.ok) {
          setData(finalJson.output);
        } else {
          throw new Error(finalJson.error || 'Unknown error');
        }

        const window = WINDOW_MAP[horizon] || '30d';
        const chartRes = await fetch(`${API_URL}/api/v10/onchain-v2/chart/${symbol}?window=${window}`);
        if (chartRes.ok) {
          const chartJson = await chartRes.json();
          if (!cancelled && chartJson.ok && chartJson.series) {
            setChartPoints(chartJson.series);
          }
        }
        
        if (!cancelled) setLoading(false);
      } catch (err: any) {
        if (!cancelled) {
          console.error('[OnChainChartV2] Error:', err);
          setError(err.message);
          setLoading(false);
        }
      }
    };

    fetchData();
    
    return () => {
      cancelled = true;
    };
  }, [symbol, horizon]);

  // Initialize and update chart
  useEffect(() => {
    if (!containerRef.current || loading || !chartPoints.length) return;

    // Reset disposed flag
    isDisposedRef.current = false;

    // Clean up existing chart
    cleanupChart();
    isDisposedRef.current = false;

    const container = containerRef.current;
    
    const chart = createChart(container, {
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
      },
      rightPriceScale: {
        borderColor: '#e5e7eb',
        scaleMargins: { top: 0.1, bottom: 0.2 },
      },
      timeScale: {
        borderColor: '#e5e7eb',
        timeVisible: true,
        secondsVisible: false,
        tickMarkFormatter: (time: number) => {
          const date = new Date(time * 1000);
          return `${date.getMonth()+1}/${date.getDate()}`;
        },
      },
      localization: {
        timeFormatter: (time: number) => {
          const date = new Date(time * 1000);
          return `${date.getMonth()+1}/${date.getDate()} ${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}`;
        },
      },
      width: container.clientWidth,
      height: height - 60,
    });

    // Score line series
    const scoreSeries = chart.addLineSeries({
      color: '#FFB020',
      lineWidth: 2,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 4,
      priceFormat: {
        type: 'custom',
        formatter: (price: number) => `${(price * 100).toFixed(0)}%`,
      },
    });

    // Confidence band area
    const confidenceSeries = chart.addAreaSeries({
      topColor: 'rgba(255, 176, 32, 0.2)',
      bottomColor: 'rgba(255, 176, 32, 0.02)',
      lineColor: 'rgba(255, 176, 32, 0.3)',
      lineWidth: 1,
    });

    chartRef.current = chart;
    scoreSeriesRef.current = scoreSeries;
    confidenceSeriesRef.current = confidenceSeries;

    // Set data - MUST be sorted ascending by time AND deduplicated for lightweight-charts
    const sortedPoints = [...chartPoints].sort((a, b) => a.t - b.t);
    
    // Deduplicate by seconds (lightweight-charts uses seconds precision)
    const seenTimes = new Set<number>();
    const dedupedPoints = sortedPoints.filter(p => {
      const timeSec = Math.floor(p.t / 1000);
      if (seenTimes.has(timeSec)) return false;
      seenTimes.add(timeSec);
      return true;
    });
    
    const scoreData = dedupedPoints.map(p => ({
      time: Math.floor(p.t / 1000) as any,
      value: p.score,
    }));

    const confData = dedupedPoints.map(p => ({
      time: Math.floor(p.t / 1000) as any,
      value: p.score + (p.confidence * 0.2),
    }));

    scoreSeries.setData(scoreData);
    confidenceSeries.setData(confData);

    // Fit content
    chart.timeScale().fitContent();

    // Handle resize
    const handleResize = () => {
      if (!isDisposedRef.current && chartRef.current && container) {
        chartRef.current.applyOptions({ width: container.clientWidth });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      cleanupChart();
    };
  }, [loading, height, chartPoints, cleanupChart, chartKey]);

  // Get guardrail config
  const guardrailConfig = useMemo(() => {
    const state = data?.governance?.guardrailState || 'HEALTHY';
    return formatGuardrailState(state);
  }, [data]);

  // Get bias label from score
  const bias = useMemo(() => {
    return biasLabel(data?.finalScore || 0.5);
  }, [data]);

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6 flex items-center justify-center" style={{ height }}>
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-3 border-gray-200 border-t-amber-500 rounded-full animate-spin" />
          <span className="text-sm text-gray-500">Loading OnChain data...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6 flex items-center justify-center" style={{ height }}>
        <div className="text-center">
          <p className="text-red-600 font-medium">Error loading OnChain data</p>
          <p className="text-sm text-gray-500 mt-1">{error}</p>
        </div>
      </div>
    );
  }

  const governance = data?.governance;
  const isSafeMode = data?.finalState === 'SAFE';

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid="onchain-forecast-chart">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h3 className="font-semibold text-gray-900">{symbol} ONCHAIN FORECAST</h3>
          <span 
            className={`px-2 py-0.5 rounded-full text-xs font-medium ${guardrailConfig.color}`}
          >
            {guardrailConfig.label}
          </span>
          {isSafeMode && (
            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
              SAFE MODE
            </span>
          )}
        </div>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-gray-500">
            Bias: <span className={`font-medium ${
              bias === 'Accumulating' ? 'text-emerald-600' :
              bias === 'Distributing' ? 'text-red-600' : 'text-gray-600'
            }`}>
              {bias}
            </span>
          </span>
          <span className="text-gray-500">
            Conf: <span className="font-medium text-gray-900">
              {formatConfidence(data?.finalConfidence || 0)}
            </span>
          </span>
        </div>
      </div>

      {/* Chart */}
      <div key={chartKey} ref={containerRef} style={{ height: height - 60 }} />

      {/* Governance Footer */}
      {governance && (
        <div className="px-4 py-2 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-xs">
          <div className="flex items-center gap-4">
            <span className="text-slate-500">
              PSI: <span className={`font-medium ${
                governance.psi < 0.15 ? 'text-emerald-600' :
                governance.psi < 0.30 ? 'text-amber-600' : 'text-red-600'
              }`}>
                {governance.psi.toFixed(3)}
              </span>
            </span>
            <span className="text-slate-500">
              Samples: <span className="font-medium text-slate-700">
                {governance.sampleCount30d}
              </span>
            </span>
            {governance.emaApplied && (
              <span className="text-slate-400">EMA smoothed</span>
            )}
          </div>
          <span className="text-slate-400">
            Policy {governance.policyVersion}
          </span>
        </div>
      )}

      {/* SafeMode/Guardrail banner */}
      {data?.governance?.guardrailAction !== 'NONE' && (
        <div className={`px-4 py-2 border-t ${
          data.governance.guardrailAction === 'FORCE_SAFE' ? 'bg-amber-50 border-amber-200' :
          data.governance.guardrailAction === 'DOWNWEIGHT' ? 'bg-blue-50 border-blue-200' :
          'bg-red-50 border-red-200'
        }`}>
          <div className="flex items-center gap-2 text-sm">
            <span className={`w-2 h-2 rounded-full ${
              data.governance.guardrailAction === 'FORCE_SAFE' ? 'bg-amber-500' :
              data.governance.guardrailAction === 'DOWNWEIGHT' ? 'bg-blue-500' :
              'bg-red-500'
            }`} />
            <span className="font-medium">
              {data.governance.guardrailAction === 'FORCE_SAFE' ? 'SAFE MODE' :
               data.governance.guardrailAction === 'DOWNWEIGHT' ? 'DOWNWEIGHTED' :
               data.governance.guardrailAction}
            </span>
            <span className="text-gray-600">
              — {data.governance.guardrailActionReasons?.join(', ') || 'Guardrails active'}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
