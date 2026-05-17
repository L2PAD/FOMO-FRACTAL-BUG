import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, TrendingDown, Activity, Zap, Target, Layers, 
  RefreshCw, Settings, Eye, EyeOff, ChevronDown 
} from 'lucide-react';
import {
  ChartLabLayout,
  ResearchStack,
  Panel,
  PanelHeader,
  PanelContent,
  StatusBadge,
  ProgressBar,
  Select,
  ToggleGroup,
  ToggleChip,
  Button
} from '../components/styles';
import CockpitAPI from '../services/api';

// Mock chart data
const generateMockCandles = (count = 100) => {
  const candles = [];
  let price = 67000 + Math.random() * 2000;
  const now = Date.now();
  
  for (let i = count; i >= 0; i--) {
    const open = price;
    const change = (Math.random() - 0.48) * 500;
    const close = price + change;
    const high = Math.max(open, close) + Math.random() * 200;
    const low = Math.min(open, close) - Math.random() * 200;
    
    candles.push({
      timestamp: now - i * 3600000,
      open,
      high,
      low,
      close,
      volume: Math.random() * 1000 + 500
    });
    
    price = close;
  }
  return candles;
};

const ChartLabPage = () => {
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [timeframe, setTimeframe] = useState('1h');
  const [preset, setPreset] = useState('trend');
  const [candles, setCandles] = useState(generateMockCandles());
  const [loading, setLoading] = useState(false);
  
  const [visibleIndicators, setVisibleIndicators] = useState(['EMA', 'RSI', 'Volume']);
  const [visibleObjects, setVisibleObjects] = useState(['trendlines', 'zones', 'targets']);
  
  const [researchData, setResearchData] = useState({
    regime: { regime: 'TRENDING_UP', confidence: 0.78, nextLikely: 'VOLATILE', transitionProb: 0.15 },
    capitalFlow: { bias: 'BULLISH', rotation: 'Risk-On', strength: 0.72 },
    fractal: { alignment: 'BULLISH', topMatch: 'Bull Flag 2024-Q1', similarity: 0.85 },
    microstructure: { pressureBias: 'BUY', vacuum: false, cascadeRisk: 0.12, impact: 'LOW' },
    explanation: {
      summary: 'Strong uptrend continuation with momentum confirmation',
      drivers: ['Volume breakout above 20-day avg', 'RSI divergence resolved', 'Support held at key level'],
      conflicts: ['Overbought on 4H timeframe'],
      confidence: { trend: 0.85, momentum: 0.78, volume: 0.82 }
    }
  });

  const presets = [
    { id: 'trend', label: 'Trend' },
    { id: 'range', label: 'Range' },
    { id: 'volatile', label: 'Volatile' },
    { id: 'breakout', label: 'Breakout' },
    { id: 'scalping', label: 'Scalping' },
    { id: 'research', label: 'Research' }
  ];
  
  const indicators = ['EMA', 'SMA', 'RSI', 'MACD', 'Bollinger', 'VWAP', 'ATR'];
  const objects = ['trendlines', 'zones', 'targets', 'fractals', 'hypotheses', 'liquidity'];
  const timeframes = ['5m', '15m', '1h', '4h', '1d', '1w'];
  const symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'];

  const toggleIndicator = (ind) => {
    setVisibleIndicators(prev => 
      prev.includes(ind) ? prev.filter(i => i !== ind) : [...prev, ind]
    );
  };
  
  const toggleObject = (obj) => {
    setVisibleObjects(prev =>
      prev.includes(obj) ? prev.filter(o => o !== obj) : [...prev, obj]
    );
  };

  const refreshChart = async () => {
    setLoading(true);
    try {
      const analysis = await CockpitAPI.analyzeTechnical(symbol.replace('USDT', ''), timeframe);
      if (analysis?.status === 'ok') {
        console.log('[ChartLab] Analysis:', analysis);
      }
      setCandles(generateMockCandles());
    } catch (err) {
      console.log('[ChartLab] Using mock data');
    }
    setLoading(false);
  };

  // Simple canvas chart rendering
  const renderChart = () => {
    const latest = candles[candles.length - 1];
    const high = Math.max(...candles.map(c => c.high));
    const low = Math.min(...candles.map(c => c.low));
    const priceChange = latest ? ((latest.close - candles[0].open) / candles[0].open * 100).toFixed(2) : 0;
    
    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        {/* Chart Header */}
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between',
          padding: '16px 20px',
          borderBottom: '1px solid #eef1f5'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <Select value={symbol} onChange={(e) => setSymbol(e.target.value)} data-testid="symbol-selector">
              {symbols.map(s => <option key={s} value={s}>{s}</option>)}
            </Select>
            
            <div style={{ display: 'flex', gap: 4 }}>
              {timeframes.map(tf => (
                <ToggleChip 
                  key={tf} 
                  $active={timeframe === tf}
                  onClick={() => setTimeframe(tf)}
                  data-testid={`tf-${tf}`}
                >
                  {tf}
                </ToggleChip>
              ))}
            </div>
            
            <Select value={preset} onChange={(e) => setPreset(e.target.value)} data-testid="preset-selector">
              {presets.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
            </Select>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {latest && (
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: 24, fontWeight: 700, color: '#0f172a' }}>
                  ${latest.close.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </div>
                <div style={{ 
                  fontSize: 14, 
                  color: priceChange >= 0 ? '#05A584' : '#ef4444',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  justifyContent: 'flex-end'
                }}>
                  {priceChange >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                  {priceChange >= 0 ? '+' : ''}{priceChange}%
                </div>
              </div>
            )}
            <Button onClick={refreshChart} disabled={loading} data-testid="refresh-chart">
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
              Refresh
            </Button>
          </div>
        </div>
        
        {/* Chart Area */}
        <div style={{ flex: 1, padding: 16, position: 'relative' }}>
          {/* Simple ASCII-style chart representation */}
          <div style={{ 
            height: '100%',
            background: 'linear-gradient(180deg, rgba(5, 165, 132, 0.04) 0%, #ffffff 50%, rgba(239, 68, 68, 0.04) 100%)',
            borderRadius: 12,
            padding: 20,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            border: '1px solid #eef1f5'
          }}>
            {/* Price levels */}
            <div style={{ display: 'flex', justifyContent: 'space-between', color: '#9CA3AF', fontSize: 12 }}>
              <span>High: ${high.toLocaleString()}</span>
              <span>Range: ${(high - low).toLocaleString()}</span>
            </div>
            
            {/* Mini bar chart visualization */}
            <div style={{ 
              display: 'flex', 
              alignItems: 'flex-end', 
              gap: 2, 
              height: 200,
              padding: '20px 0'
            }}>
              {candles.slice(-50).map((candle, i) => {
                const height = ((candle.close - low) / (high - low)) * 180;
                const isGreen = candle.close >= candle.open;
                return (
                  <div
                    key={i}
                    style={{
                      flex: 1,
                      height: Math.max(height, 2),
                      background: isGreen ? '#05A584' : '#ef4444',
                      borderRadius: 1,
                      opacity: 0.8,
                      transition: 'height 0.3s ease'
                    }}
                  />
                );
              })}
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'space-between', color: '#9CA3AF', fontSize: 12 }}>
              <span>Low: ${low.toLocaleString()}</span>
              <span>{candles.length} candles</span>
            </div>
          </div>
          
          {/* Chart Objects Legend */}
          <div style={{ 
            position: 'absolute', 
            top: 30, 
            left: 30, 
            background: '#ffffff',
            padding: 12,
            borderRadius: 10,
            border: '1px solid #eef1f5',
            boxShadow: '0 2px 8px rgba(0,0,0,0.06)'
          }}>
            <div style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Visible Objects</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {visibleObjects.map(obj => (
                <div key={obj} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: '#738094' }}>
                  <div style={{ width: 8, height: 8, borderRadius: 2, background: '#05A584' }} />
                  {obj}
                </div>
              ))}
            </div>
          </div>
        </div>
        
        {/* Indicators Toggle */}
        <div style={{ 
          padding: '12px 20px', 
          borderTop: '1px solid #eef1f5',
          display: 'flex',
          alignItems: 'center',
          gap: 16
        }}>
          <span style={{ fontSize: 13, color: '#9CA3AF' }}>Indicators:</span>
          <ToggleGroup>
            {indicators.map(ind => (
              <ToggleChip 
                key={ind}
                $active={visibleIndicators.includes(ind)}
                onClick={() => toggleIndicator(ind)}
              >
                {ind}
              </ToggleChip>
            ))}
          </ToggleGroup>
        </div>
        
        {/* Objects Toggle */}
        <div style={{ 
          padding: '12px 20px', 
          borderTop: '1px solid #eef1f5',
          display: 'flex',
          alignItems: 'center',
          gap: 16
        }}>
          <span style={{ fontSize: 13, color: '#9CA3AF' }}>Objects:</span>
          <ToggleGroup>
            {objects.map(obj => (
              <ToggleChip
                key={obj}
                $active={visibleObjects.includes(obj)}
                onClick={() => toggleObject(obj)}
              >
                {obj}
              </ToggleChip>
            ))}
          </ToggleGroup>
        </div>
      </div>
    );
  };

  return (
    <ChartLabLayout data-testid="chart-lab-page">
      {/* Main Chart Area */}
      <Panel style={{ display: 'flex', flexDirection: 'column' }}>
        {renderChart()}
      </Panel>
      
      {/* Research Stack */}
      <ResearchStack data-testid="research-stack">
        {/* Market Regime */}
        <Panel>
          <PanelHeader>
            <div className="title">Market Regime</div>
            <StatusBadge $status={researchData.regime.regime.includes('UP') ? 'BULLISH' : 'BEARISH'}>
              {researchData.regime.regime.replace('_', ' ')}
            </StatusBadge>
          </PanelHeader>
          <PanelContent>
            <div style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 13, color: '#738094' }}>Confidence</span>
                <span style={{ fontSize: 14, fontWeight: 600, color: '#0f172a' }}>{(researchData.regime.confidence * 100).toFixed(0)}%</span>
              </div>
              <ProgressBar $value={researchData.regime.confidence * 100} $color="#05A584">
                <div className="fill" />
              </ProgressBar>
            </div>
            <div style={{ fontSize: 13, color: '#738094' }}>
              Next likely: <span style={{ color: '#f59e0b', fontWeight: 500 }}>{researchData.regime.nextLikely}</span> ({(researchData.regime.transitionProb * 100).toFixed(0)}%)
            </div>
          </PanelContent>
        </Panel>
        
        {/* Capital Flow */}
        <Panel>
          <PanelHeader>
            <div className="title">Capital Flow</div>
            <StatusBadge $status={researchData.capitalFlow.bias}>{researchData.capitalFlow.bias}</StatusBadge>
          </PanelHeader>
          <PanelContent>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <div style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 4, textTransform: 'uppercase' }}>Rotation</div>
                <div style={{ fontSize: 15, fontWeight: 600, color: '#0f172a' }}>{researchData.capitalFlow.rotation}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 4, textTransform: 'uppercase' }}>Strength</div>
                <div style={{ fontSize: 15, fontWeight: 600, color: '#05A584' }}>{(researchData.capitalFlow.strength * 100).toFixed(0)}%</div>
              </div>
            </div>
          </PanelContent>
        </Panel>
        
        {/* Fractal Analysis */}
        <Panel>
          <PanelHeader>
            <div className="title">Fractal Match</div>
            <StatusBadge $status={researchData.fractal.alignment}>{researchData.fractal.alignment}</StatusBadge>
          </PanelHeader>
          <PanelContent>
            <div style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 12, color: '#9CA3AF', marginBottom: 4 }}>Top Match</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#0f172a' }}>{researchData.fractal.topMatch}</div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: 13, color: '#738094' }}>Similarity</span>
              <span style={{ fontSize: 14, fontWeight: 600, color: '#05A584' }}>{(researchData.fractal.similarity * 100).toFixed(0)}%</span>
            </div>
            <ProgressBar $value={researchData.fractal.similarity * 100} $color="#05A584">
              <div className="fill" />
            </ProgressBar>
          </PanelContent>
        </Panel>
        
        {/* Microstructure */}
        <Panel>
          <PanelHeader>
            <div className="title">Microstructure</div>
            <StatusBadge $status={researchData.microstructure.pressureBias}>{researchData.microstructure.pressureBias}</StatusBadge>
          </PanelHeader>
          <PanelContent>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <div style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 4, textTransform: 'uppercase' }}>Vacuum</div>
                <div style={{ fontSize: 15, fontWeight: 600, color: researchData.microstructure.vacuum ? '#ef4444' : '#05A584' }}>
                  {researchData.microstructure.vacuum ? 'Yes' : 'No'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 4, textTransform: 'uppercase' }}>Cascade Risk</div>
                <div style={{ fontSize: 15, fontWeight: 600, color: researchData.microstructure.cascadeRisk > 0.3 ? '#ef4444' : '#05A584' }}>
                  {(researchData.microstructure.cascadeRisk * 100).toFixed(0)}%
                </div>
              </div>
            </div>
          </PanelContent>
        </Panel>
        
        {/* Signal Explanation */}
        <Panel>
          <PanelHeader>
            <div className="title">Signal Explanation</div>
            <Zap size={16} style={{ color: '#05A584' }} />
          </PanelHeader>
          <PanelContent>
            <div style={{ fontSize: 14, color: '#0f172a', marginBottom: 12, lineHeight: 1.6 }}>
              {researchData.explanation.summary}
            </div>
            
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 12, color: '#05A584', marginBottom: 6, fontWeight: 600 }}>Drivers</div>
              {researchData.explanation.drivers.map((driver, i) => (
                <div key={i} style={{ fontSize: 13, color: '#738094', marginBottom: 4, paddingLeft: 12, borderLeft: '2px solid #05A584' }}>
                  {driver}
                </div>
              ))}
            </div>
            
            {researchData.explanation.conflicts.length > 0 && (
              <div>
                <div style={{ fontSize: 12, color: '#f59e0b', marginBottom: 6, fontWeight: 600 }}>Conflicts</div>
                {researchData.explanation.conflicts.map((conflict, i) => (
                  <div key={i} style={{ fontSize: 13, color: '#738094', marginBottom: 4, paddingLeft: 12, borderLeft: '2px solid #f59e0b' }}>
                    {conflict}
                  </div>
                ))}
              </div>
            )}
          </PanelContent>
        </Panel>
      </ResearchStack>
    </ChartLabLayout>
  );
};

export default ChartLabPage;
