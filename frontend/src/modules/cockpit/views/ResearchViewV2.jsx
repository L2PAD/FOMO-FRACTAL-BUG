/**
 * ResearchView V2 — Unified Chart Objects Architecture
 * =====================================================
 * 
 * Uses /api/ta/research endpoint which returns:
 * - candles[]
 * - objects[] (unified chart objects with type, category, priority)
 * - summary (bias, confidence, regime)
 * 
 * Frontend renders ONLY from objects[].
 * NO manual pattern drawing.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import styled from 'styled-components';
import { createChart, CandlestickSeries, LineSeries } from 'lightweight-charts';
import { 
  Loader2,
  AlertTriangle,
  ChevronDown,
  BarChart2,
  LineChart,
} from 'lucide-react';

import { 
  ObjectCategory,
  filterByLayers,
  sortByPriority,
} from '../utils/chartObjects';

import { renderChartObjects, clearChartObjects } from '../utils/objectRenderer';

// ============================================
// STYLED COMPONENTS
// ============================================

const Container = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #0B0F14;
  overflow-y: auto;
`;

const TopBar = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: #111820;
  border-bottom: 1px solid #1e2730;
  flex-wrap: wrap;
  gap: 12px;
`;

const ControlsLeft = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
`;

const SearchWrapper = styled.div`
  position: relative;
`;

const SearchInput = styled.input`
  width: 140px;
  padding: 10px 14px;
  background: #1a2332;
  border: 1px solid #2d3748;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #e2e8f0;
  letter-spacing: 0.5px;
  
  &:focus {
    outline: none;
    border-color: #3B82F6;
    background: #1e293b;
  }
  
  &::placeholder {
    color: #64748b;
  }
`;

const SymbolDropdown = styled.div`
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 4px;
  background: #1a2332;
  border: 1px solid #2d3748;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.4);
  z-index: 100;
  max-height: 200px;
  overflow-y: auto;
`;

const SymbolOption = styled.button`
  width: 100%;
  padding: 10px 12px;
  text-align: left;
  border: none;
  background: ${({ $active }) => $active ? '#2d3748' : 'transparent'};
  font-size: 13px;
  font-weight: 500;
  color: #e2e8f0;
  cursor: pointer;
  
  &:hover {
    background: #2d3748;
  }
`;

const TfGroup = styled.div`
  display: flex;
  gap: 2px;
  background: #1a2332;
  padding: 3px;
  border-radius: 8px;
`;

const TfButton = styled.button`
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  border: none;
  background: ${({ $active }) => $active ? '#3B82F6' : 'transparent'};
  color: ${({ $active }) => $active ? '#ffffff' : '#64748b'};
  cursor: pointer;
  transition: all 0.15s ease;
  
  &:hover {
    color: ${({ $active }) => $active ? '#ffffff' : '#e2e8f0'};
  }
`;

const ChartTypeGroup = styled.div`
  display: flex;
  gap: 2px;
  background: #1a2332;
  padding: 3px;
  border-radius: 8px;
`;

const ChartTypeBtn = styled.button`
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6px 10px;
  border-radius: 6px;
  border: none;
  background: ${({ $active }) => $active ? '#3B82F6' : 'transparent'};
  color: ${({ $active }) => $active ? '#ffffff' : '#64748b'};
  cursor: pointer;
  
  svg {
    width: 16px;
    height: 16px;
  }
  
  &:hover {
    color: ${({ $active }) => $active ? '#ffffff' : '#e2e8f0'};
  }
`;

const ModeGroup = styled.div`
  display: flex;
  gap: 2px;
  background: #1a2332;
  padding: 3px;
  border-radius: 8px;
`;

const ModeButton = styled.button`
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border: none;
  background: ${({ $active }) => $active ? '#3B82F6' : 'transparent'};
  color: ${({ $active }) => $active ? '#ffffff' : '#64748b'};
  cursor: pointer;
  transition: all 0.15s ease;
  
  &:hover {
    color: ${({ $active }) => $active ? '#ffffff' : '#e2e8f0'};
  }
`;

const LayerToggles = styled.div`
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px;
  background: #1a2332;
  border-radius: 8px;
`;

const LayerToggleBtn = styled.button`
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  border: none;
  background: ${({ $active }) => $active ? '#1e293b' : 'transparent'};
  color: ${({ $active, $color }) => $active ? $color : '#4b5563'};
  cursor: pointer;
  transition: all 0.15s ease;
  
  &:hover {
    color: ${({ $color }) => $color};
  }
  
  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: ${({ $active, $color }) => $active ? $color : '#374151'};
  }
`;

const MainContent = styled.div`
  flex: 1;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
`;

const ChartSection = styled.div`
  background: #111820;
  border: 1px solid #1e2730;
  border-radius: 12px;
  overflow: hidden;
  position: relative;
`;

const ChartContainer = styled.div`
  width: 100%;
  height: 600px;
`;

const BiasOverlay = styled.div`
  position: absolute;
  top: 16px;
  left: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: ${({ $direction }) => 
    $direction === 'bullish' ? 'rgba(34, 197, 94, 0.9)' : 
    $direction === 'bearish' ? 'rgba(239, 68, 68, 0.9)' : 
    'rgba(100, 116, 139, 0.9)'};
  color: #ffffff;
  border-radius: 8px;
  font-weight: 700;
  font-size: 14px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  z-index: 10;
  
  .arrow { font-size: 16px; }
  .confidence { font-size: 12px; opacity: 0.85; margin-left: 4px; }
`;

const PatternLabel = styled.div`
  position: absolute;
  top: 16px;
  right: 16px;
  padding: 10px 14px;
  background: rgba(59, 130, 246, 0.9);
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  color: #ffffff;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
  z-index: 10;
  text-transform: capitalize;
  
  .confidence { margin-left: 8px; opacity: 0.85; }
`;

const RegimeLabel = styled.div`
  position: absolute;
  top: 60px;
  left: 16px;
  padding: 6px 12px;
  background: rgba(30, 41, 59, 0.9);
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  z-index: 10;
`;

const ErrorBanner = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #1c1f26;
  border: 1px solid #ef4444;
  border-radius: 8px;
  color: #ef4444;
  font-size: 13px;
  
  svg {
    flex-shrink: 0;
  }
`;

const LoadingOverlay = styled.div`
  position: absolute;
  inset: 0;
  background: rgba(11, 15, 20, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  z-index: 20;
  
  svg {
    animation: spin 1s linear infinite;
    color: #3B82F6;
  }
  
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
`;

const NoSetupMessage = styled.div`
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  padding: 20px 30px;
  background: rgba(30, 41, 59, 0.95);
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
  color: #94a3b8;
  text-align: center;
  z-index: 10;
`;

const SummaryPanel = styled.div`
  background: #111820;
  border: 1px solid #1e2730;
  border-radius: 12px;
  padding: 16px 20px;
  
  .title {
    font-size: 11px;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 12px;
  }
  
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 16px;
  }
  
  .item {
    .label {
      font-size: 11px;
      font-weight: 500;
      color: #64748b;
      margin-bottom: 4px;
    }
    .value {
      font-size: 14px;
      font-weight: 700;
      color: #e2e8f0;
      
      &.bullish { color: #22c55e; }
      &.bearish { color: #ef4444; }
    }
  }
`;

// ============================================
// CONSTANTS
// ============================================

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT'];
const TIMEFRAMES = ['4h', '1d', '7d', '30d'];
const MODES = ['research', 'hypothesis', 'trading'];

// ============================================
// COMPONENT
// ============================================

const ResearchViewV2 = () => {
  // State
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [timeframe, setTimeframe] = useState('1d');
  const [chartType, setChartType] = useState('candles');
  const [mode, setMode] = useState('research');
  
  const [searchQuery, setSearchQuery] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Data from API
  const [candles, setCandles] = useState([]);
  const [objects, setObjects] = useState([]);
  const [summary, setSummary] = useState(null);
  
  // Layer visibility
  const [layers, setLayers] = useState({
    patterns: true,
    levels: true,
    structure: true,
    hypothesis: true,
    trading: false,
  });
  
  // Chart refs
  const chartRef = useRef(null);
  const chartInstanceRef = useRef(null);
  const renderedSeriesRef = useRef([]);

  // Fetch data from unified endpoint
  const fetchResearchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(
        `${process.env.REACT_APP_BACKEND_URL}/api/ta/research?symbol=${symbol}&tf=${timeframe}&mode=${mode}`
      );
      
      if (!response.ok) {
        throw new Error('Failed to fetch research data');
      }
      
      const data = await response.json();
      
      setCandles(data.candles || []);
      setObjects(data.objects || []);
      setSummary(data.summary || null);
      
    } catch (err) {
      setError(err.message || 'Failed to load analysis');
      setCandles([]);
      setObjects([]);
      setSummary(null);
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe, mode]);

  // Initial load
  useEffect(() => {
    fetchResearchData();
  }, [fetchResearchData]);

  // Render chart with objects
  useEffect(() => {
    if (!chartRef.current || candles.length === 0) return;

    // Cleanup previous chart
    if (chartInstanceRef.current) {
      clearChartObjects(chartInstanceRef.current, renderedSeriesRef.current);
      chartInstanceRef.current.remove();
      chartInstanceRef.current = null;
      renderedSeriesRef.current = [];
    }

    // Create chart
    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: 600,
      layout: {
        background: { type: 'solid', color: '#0B0F14' },
        textColor: '#64748b',
        fontFamily: "'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: '#1e2730' },
        horzLines: { color: '#1e2730' },
      },
      crosshair: {
        mode: 1,
        vertLine: { color: '#3B82F6', style: 2, width: 1 },
        horzLine: { color: '#3B82F6', style: 2, width: 1 },
      },
      rightPriceScale: {
        borderColor: '#1e2730',
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: '#1e2730',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 50,
      },
    });

    chartInstanceRef.current = chart;

    // Add price series
    let priceSeries;
    if (chartType === 'line') {
      priceSeries = chart.addSeries(LineSeries, {
        color: '#3B82F6',
        lineWidth: 2,
        lastValueVisible: true,
        priceLineVisible: true,
      });
    } else {
      priceSeries = chart.addSeries(CandlestickSeries, {
        upColor: '#22c55e',
        downColor: '#ef4444',
        borderUpColor: '#22c55e',
        borderDownColor: '#ef4444',
        wickUpColor: '#22c55e',
        wickDownColor: '#ef4444',
        lastValueVisible: true,
        priceLineVisible: true,
      });
    }

    // Format candle data
    const seen = new Set();
    const mapped = candles
      .map(c => ({
        time: c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        value: c.close,
      }))
      .filter(c => c.time > 0)
      .sort((a, b) => a.time - b.time)
      .filter(c => {
        if (seen.has(c.time)) return false;
        seen.add(c.time);
        return true;
      });

    priceSeries.setData(mapped);

    // RENDER CHART OBJECTS
    // 1. Filter by layer visibility
    const filteredObjects = filterByLayers(objects, layers);
    
    // 2. Sort by priority
    const sortedObjects = sortByPriority(filteredObjects);
    
    // 3. Render
    const renderedSeries = renderChartObjects(chart, sortedObjects);
    renderedSeriesRef.current = renderedSeries;

    // Fit content
    chart.timeScale().fitContent();

    // Resize observer
    const ro = new ResizeObserver(() => {
      if (chartRef.current && chartInstanceRef.current) {
        const w = chartRef.current.clientWidth;
        if (w > 0) {
          chartInstanceRef.current.applyOptions({ width: w });
        }
      }
    });
    ro.observe(chartRef.current);

    return () => {
      ro.disconnect();
      if (chartInstanceRef.current) {
        chartInstanceRef.current.remove();
        chartInstanceRef.current = null;
      }
    };
  }, [candles, objects, chartType, layers]);

  // Handle symbol select
  const handleSymbolSelect = (s) => {
    setSymbol(s);
    setSearchQuery('');
    setShowDropdown(false);
  };

  // Toggle layer
  const toggleLayer = (layer) => {
    setLayers(prev => ({ ...prev, [layer]: !prev[layer] }));
  };

  // Filter symbols
  const filteredSymbols = searchQuery
    ? SYMBOLS.filter(s => 
        s.toLowerCase().includes(searchQuery.toLowerCase())
      ).slice(0, 5)
    : SYMBOLS;

  // Derived values
  const hasValidSetup = summary && summary.confidence > 0.4;
  const patternCount = objects.filter(o => o.category === ObjectCategory.PATTERN).length;
  const levelCount = objects.filter(o => o.category === ObjectCategory.LEVEL).length;

  return (
    <Container data-testid="research-view-v2">
      {/* Top Control Bar */}
      <TopBar>
        <ControlsLeft>
          {/* Search Asset */}
          <SearchWrapper>
            <SearchInput
              type="text"
              placeholder="Search"
              value={showDropdown ? searchQuery : symbol.replace('USDT', '')}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setShowDropdown(true);
              }}
              onFocus={() => setShowDropdown(true)}
              onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
              data-testid="asset-search"
            />
            {showDropdown && filteredSymbols.length > 0 && (
              <SymbolDropdown>
                {filteredSymbols.map(s => (
                  <SymbolOption
                    key={s}
                    $active={s === symbol}
                    onMouseDown={() => handleSymbolSelect(s)}
                  >
                    {s.replace('USDT', '')}
                  </SymbolOption>
                ))}
              </SymbolDropdown>
            )}
          </SearchWrapper>

          {/* Timeframe */}
          <TfGroup>
            {TIMEFRAMES.map(tf => (
              <TfButton
                key={tf}
                $active={timeframe === tf}
                onClick={() => setTimeframe(tf)}
                data-testid={`tf-${tf}`}
              >
                {tf.toUpperCase()}
              </TfButton>
            ))}
          </TfGroup>

          {/* Chart Type */}
          <ChartTypeGroup>
            <ChartTypeBtn
              $active={chartType === 'candles'}
              onClick={() => setChartType('candles')}
              title="Candles"
            >
              <BarChart2 />
            </ChartTypeBtn>
            <ChartTypeBtn
              $active={chartType === 'line'}
              onClick={() => setChartType('line')}
              title="Line"
            >
              <LineChart />
            </ChartTypeBtn>
          </ChartTypeGroup>

          {/* Mode */}
          <ModeGroup>
            {MODES.map(m => (
              <ModeButton
                key={m}
                $active={mode === m}
                onClick={() => setMode(m)}
              >
                {m}
              </ModeButton>
            ))}
          </ModeGroup>

          {/* Layer Toggles */}
          <LayerToggles>
            <LayerToggleBtn 
              $active={layers.patterns} 
              $color="#3B82F6"
              onClick={() => toggleLayer('patterns')}
            >
              <span className="dot" /> Patterns
            </LayerToggleBtn>
            <LayerToggleBtn 
              $active={layers.levels} 
              $color="#22c55e"
              onClick={() => toggleLayer('levels')}
            >
              <span className="dot" /> Levels
            </LayerToggleBtn>
            <LayerToggleBtn 
              $active={layers.structure} 
              $color="#f59e0b"
              onClick={() => toggleLayer('structure')}
            >
              <span className="dot" /> Structure
            </LayerToggleBtn>
            <LayerToggleBtn 
              $active={layers.hypothesis} 
              $color="#a855f7"
              onClick={() => toggleLayer('hypothesis')}
            >
              <span className="dot" /> Hypothesis
            </LayerToggleBtn>
            <LayerToggleBtn 
              $active={layers.trading} 
              $color="#ef4444"
              onClick={() => toggleLayer('trading')}
            >
              <span className="dot" /> Trading
            </LayerToggleBtn>
          </LayerToggles>
        </ControlsLeft>
      </TopBar>

      {/* Main Content */}
      <MainContent>
        {/* Error Banner */}
        {error && (
          <ErrorBanner>
            <AlertTriangle size={18} />
            {error}
          </ErrorBanner>
        )}

        {/* Chart Section */}
        <ChartSection>
          <ChartContainer 
            ref={chartRef} 
            key={`chart-${JSON.stringify(layers)}-${chartType}`}
          />
          
          {loading && (
            <LoadingOverlay>
              <Loader2 size={24} />
              <span style={{ color: '#64748b', fontSize: 13 }}>Analyzing {symbol}...</span>
            </LoadingOverlay>
          )}
          
          {!loading && summary && (
            <>
              <BiasOverlay $direction={summary.bias}>
                <span className="arrow">
                  {summary.bias === 'bullish' ? '↑' : summary.bias === 'bearish' ? '↓' : '→'}
                </span>
                {summary.bias.toUpperCase()}
                <span className="confidence">{Math.round(summary.confidence * 100)}%</span>
              </BiasOverlay>
              
              {summary.pattern_type && summary.pattern_type !== 'range' && (
                <PatternLabel>
                  {summary.pattern_type.replace(/_/g, ' ')}
                </PatternLabel>
              )}
              
              <RegimeLabel>
                {summary.regime?.replace(/_/g, ' ')}
              </RegimeLabel>
            </>
          )}
          
          {!loading && !hasValidSetup && objects.length === 0 && (
            <NoSetupMessage>
              No clear setup detected
            </NoSetupMessage>
          )}
        </ChartSection>

        {/* Summary Panel */}
        {summary && (
          <SummaryPanel>
            <div className="title">Analysis Summary</div>
            <div className="grid">
              <div className="item">
                <div className="label">Direction</div>
                <div className={`value ${summary.bias}`}>
                  {summary.bias?.charAt(0).toUpperCase() + summary.bias?.slice(1)}
                </div>
              </div>
              <div className="item">
                <div className="label">Confidence</div>
                <div className="value">{Math.round(summary.confidence * 100)}%</div>
              </div>
              <div className="item">
                <div className="label">Regime</div>
                <div className="value">{summary.regime?.replace(/_/g, ' ')}</div>
              </div>
              <div className="item">
                <div className="label">Pattern</div>
                <div className="value">{summary.pattern_type?.replace(/_/g, ' ') || 'None'}</div>
              </div>
              <div className="item">
                <div className="label">Structure</div>
                <div className="value">{summary.structure_trend || 'Unknown'}</div>
              </div>
              <div className="item">
                <div className="label">Objects</div>
                <div className="value">{objects.length} ({patternCount}P / {levelCount}L)</div>
              </div>
            </div>
          </SummaryPanel>
        )}
      </MainContent>
    </Container>
  );
};

export default ResearchViewV2;
