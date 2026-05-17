import React, { useState, useEffect, useMemo } from 'react';
import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Scatter
} from 'recharts';
import { 
  Layers, 
  TrendingUp, 
  Activity, 
  Calendar, 
  Triangle, 
  GitBranch 
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const Candlestick = (props) => {
  const { x, y, width, height, low, high, openClose } = props;
  const isGrowing = openClose[1] > openClose[0];
  const upColor = '#3A6B58';
  const downColor = '#C24A4A';
  const color = isGrowing ? upColor : downColor;
  const ratio = Math.abs(height / (openClose[1] - openClose[0]));

  return (
    <g>
      <line
        x1={x + width / 2}
        y1={y}
        x2={x + width / 2}
        y2={y + height}
        stroke={color}
        strokeWidth={1}
      />
      <rect
        x={x}
        y={y + (isGrowing ? (height - ratio * (openClose[1] - openClose[0])) : 0)}
        width={width}
        height={ratio * Math.abs(openClose[1] - openClose[0])}
        fill={color}
        stroke={color}
        strokeWidth={0}
      />
    </g>
  );
};

const TradingChart = ({ symbol = 'BTCUSDT', height = 500, lang = 'ru' }) => {
  const [candles, setCandles] = useState([]);
  const [loading, setLoading] = useState(true);
  
  const [showExecution, setShowExecution] = useState(false);
  const [showRange, setShowRange] = useState(false);
  const [showSwings, setShowSwings] = useState(false);
  const [showEvents, setShowEvents] = useState(false);
  const [showPatterns, setShowPatterns] = useState(false);
  const [showScenario, setShowScenario] = useState(false);

  const t = (ru, en) => (lang === 'ru' ? ru : en);

  useEffect(() => {
    fetchCandles();
  }, [symbol]);

  const fetchCandles = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_URL}/api/market/candles?symbol=${symbol}&date_range=7d`);
      const data = await res.json();
      
      if (data.ok && data.candles) {
        const transformed = data.candles.map(c => ({
          time: new Date(c.time * 1000).toLocaleDateString('ru-RU', { 
            day: '2-digit', 
            month: 'short' 
          }),
          timestamp: c.time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
          volume: c.volume,
          openClose: [c.open, c.close],
          highLow: [c.low, c.high],
        }));
        
        setCandles(transformed);
      }
    } catch (error) {
      console.error('Candles fetch error:', error);
    } finally {
      setLoading(false);
    }
  };

  const supportResistance = useMemo(() => {
    if (candles.length < 20) return { support: null, resistance: null };
    
    const recent = candles.slice(-20);
    const support = Math.min(...recent.map(c => c.low));
    const resistance = Math.max(...recent.map(c => c.high));
    
    return { support, resistance };
  }, [candles]);

  const swingPoints = useMemo(() => {
    if (!showSwings || candles.length < 5) return [];
    
    const swings = [];
    for (let i = 2; i < candles.length - 2; i++) {
      const c = candles[i];
      const prev = candles[i - 1];
      const next = candles[i + 1];
      
      if (c.high > prev.high && c.high > next.high) {
        swings.push({
          time: c.time,
          timestamp: c.timestamp,
          price: c.high,
          type: 'high'
        });
      }
      
      if (c.low < prev.low && c.low < next.low) {
        swings.push({
          time: c.time,
          timestamp: c.timestamp,
          price: c.low,
          type: 'low'
        });
      }
    }
    
    return swings;
  }, [candles, showSwings]);

  // LIMIT execution points to avoid clutter (FIX: "50,000 stops")
  const executionPoints = useMemo(() => {
    if (!showExecution || candles.length < 10) return [];
    
    // Only show 2-3 representative points, not all history
    return [
      { time: candles[Math.floor(candles.length * 0.3)]?.time, price: candles[Math.floor(candles.length * 0.3)]?.close, type: 'BUY' },
      { time: candles[Math.floor(candles.length * 0.7)]?.time, price: candles[Math.floor(candles.length * 0.7)]?.close, type: 'SELL' },
    ].filter(p => p.time);
  }, [candles, showExecution]);

  const controls = [
    { 
      id: 'execution', 
      label: t('Исполнение', 'Execution'), 
      icon: Layers, 
      active: showExecution, 
      toggle: () => setShowExecution(!showExecution) 
    },
    { 
      id: 'range', 
      label: t('Уровни', 'Range'), 
      icon: TrendingUp, 
      active: showRange, 
      toggle: () => setShowRange(!showRange) 
    },
    { 
      id: 'swings', 
      label: t('Свинги', 'Swings'), 
      icon: Activity, 
      active: showSwings, 
      toggle: () => setShowSwings(!showSwings) 
    },
    { 
      id: 'events', 
      label: t('События', 'Events'), 
      icon: Calendar, 
      active: showEvents, 
      toggle: () => setShowEvents(!showEvents) 
    },
    { 
      id: 'patterns', 
      label: t('Паттерны', 'Patterns'), 
      icon: Triangle, 
      active: showPatterns, 
      toggle: () => setShowPatterns(!showPatterns) 
    },
    { 
      id: 'scenario', 
      label: t('Сценарий', 'Scenario'), 
      icon: GitBranch, 
      active: showScenario, 
      toggle: () => setShowScenario(!showScenario) 
    },
  ];

  if (loading) {
    return (
      <div className="bg-[hsl(var(--surface))] rounded-[var(--radius)] p-6" style={{ height }} data-testid="trading-chart">
        <div className="flex items-center justify-center h-full">
          <div className="text-sm text-[hsl(var(--fg-3))]">{t('Загрузка графика...', 'Loading chart...')}</div>
        </div>
      </div>
    );
  }

  return (
    <div 
      className="bg-[hsl(var(--surface))] rounded-[var(--radius)] p-4" 
      data-testid="trading-chart-container"
    >
      {/* Controls */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        {controls.map(ctrl => {
          const Icon = ctrl.icon;
          return (
            <button
              key={ctrl.id}
              onClick={ctrl.toggle}
              className={`
                flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                transition-colors duration-150
                ${
                  ctrl.active 
                    ? 'bg-[hsl(var(--accent))] text-white' 
                    : 'bg-[hsl(var(--surface-2))] text-[hsl(var(--fg-2))] hover:bg-[hsl(var(--bg-2))]'
                }
              `}
              data-testid={`chart-control-${ctrl.id}`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{ctrl.label}</span>
            </button>
          );
        })}
        
        <div className="ml-auto text-xs text-[hsl(var(--fg-3))] mono">
          {symbol} • 1H
        </div>
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={height - 60}>
        <ComposedChart
          data={candles}
          margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
          
          <XAxis 
            dataKey="time" 
            tick={{ fontSize: 11, fill: 'hsl(var(--fg-3))' }}
            stroke="rgba(0,0,0,0.06)"
          />
          
          <YAxis 
            yAxisId="price"
            domain={['dataMin - 500', 'dataMax + 500']}
            tick={{ fontSize: 11, fill: 'hsl(var(--fg-3))' }}
            stroke="rgba(0,0,0,0.06)"
            orientation="right"
          />
          
          <YAxis 
            yAxisId="volume"
            orientation="left"
            tick={{ fontSize: 11, fill: 'hsl(var(--fg-3))' }}
            stroke="rgba(0,0,0,0.06)"
          />
          
          <Tooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--bg))',
              border: 'none',
              borderRadius: '8px',
              fontSize: '12px',
              padding: '8px 12px'
            }}
            formatter={(value, name) => {
              if (name === 'volume') return [value.toLocaleString(), t('Объём', 'Volume')];
              return [`$${value.toFixed(2)}`, name];
            }}
          />
          
          <Bar 
            yAxisId="volume"
            dataKey="volume" 
            fill="rgba(0,0,0,0.06)" 
            opacity={0.3}
            barSize={4}
          />
          
          <Scatter
            yAxisId="price"
            data={candles}
            shape={<Candlestick />}
          />
          
          {showRange && supportResistance.support && (
            <ReferenceLine
              yAxisId="price"
              y={supportResistance.support}
              stroke="#2E5B4A"
              strokeDasharray="5 5"
              strokeWidth={1.5}
              label={{ value: t('Поддержка', 'Support'), fontSize: 10, fill: '#2E5B4A', position: 'insideBottomRight' }}
            />
          )}
          
          {showRange && supportResistance.resistance && (
            <ReferenceLine
              yAxisId="price"
              y={supportResistance.resistance}
              stroke="#B23A3A"
              strokeDasharray="5 5"
              strokeWidth={1.5}
              label={{ value: t('Сопротивление', 'Resistance'), fontSize: 10, fill: '#B23A3A', position: 'insideTopRight' }}
            />
          )}
          
          {candles.length > 0 && (
            <ReferenceLine
              yAxisId="price"
              y={candles[candles.length - 1].close}
              stroke="hsl(var(--fg-3))"
              strokeDasharray="3 3"
              strokeWidth={1}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>

      {showExecution && executionPoints.length > 0 && (
        <div className="mt-2 flex gap-2 text-xs">
          {executionPoints.map((point, idx) => (
            <div 
              key={idx}
              className={`px-2 py-1 rounded ${
                point.type === 'BUY' 
                  ? 'bg-[hsl(var(--pos)/0.1)] text-[hsl(var(--pos))]' 
                  : 'bg-[hsl(var(--neg)/0.1)] text-[hsl(var(--neg))]'
              } mono`}
            >
              {point.type} @ ${point.price?.toFixed(2)}
            </div>
          ))}\n        </div>
      )}
      
      {showSwings && swingPoints.length > 0 && (
        <div className="mt-2 text-xs text-[hsl(var(--fg-3))]">
          {t('Свинги', 'Swing points')}: {swingPoints.length}
        </div>
      )}
    </div>
  );
};

export default TradingChart;
