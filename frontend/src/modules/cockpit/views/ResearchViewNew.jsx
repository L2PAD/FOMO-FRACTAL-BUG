/**
 * ResearchView — Technical Analysis Research Terminal
 * ====================================================
 * 
 * Uses Setup API to display:
 * 1. Full-width chart with patterns, levels, bias
 * 2. Pattern Activation Layer
 * 3. Deep Analysis Blocks
 * 4. Save Idea functionality
 */

import React, { useState, useEffect, useCallback } from 'react';
import styled from 'styled-components';
import { 
  Search, 
  RefreshCw, 
  Share2, 
  Camera, 
  Bookmark,
  Loader2,
  AlertTriangle,
  ChevronDown,
  BarChart2,
  LineChart,
  Eye,
  EyeOff,
  Settings2,
  Triangle,
  Layers,
  TrendingUp,
  Target,
  Check
} from 'lucide-react';

// ═══════════════════════════════════════════════════════════════
// UNIFIED TA STATE — single source of truth on the frontend
// ═══════════════════════════════════════════════════════════════
import useUnifiedTAState from '../hooks/useUnifiedTAState';
import MarketStateHeader from '../components/MarketStateHeader';

// ═══════════════════════════════════════════════════════════════
// TA VISUALIZATION — RenderPlan + Renderers (moved from Chart Lab)
// ═══════════════════════════════════════════════════════════════
import { useRenderPlan, useMarket } from '../../../store/marketStore';
import { RenderPlanOverlay } from '../renderers';

import ResearchChart from '../components/ResearchChart';
import PatternActivationLayer from '../components/PatternActivationLayer';
import DeepAnalysisBlocks from '../components/DeepAnalysisBlocks';
import MarketContextBar from '../components/MarketContextBar';
import ScenariosBlock from '../components/ScenariosBlock';
import PatternsBlock from '../components/PatternsBlock';
import TALayersPanel from '../components/TALayersPanel';
import { TAExplorerPanel } from '../components/ta-explorer';
import ConfidenceExplanation from '../components/ConfidenceExplanation';
import ExplanationPanel from '../components/ExplanationPanel';
import IndicatorPanes from '../components/IndicatorPanes';
import IndicatorControlBar from '../components/IndicatorControlBar';
import ConfluenceMatrix from '../components/ConfluenceMatrix';
import IndicatorSelector from '../components/IndicatorSelector';
import ViewModeSelector from '../components/ViewModeSelector';
import TAContextPanel from '../components/TAContextPanel';
import RenderPlanReasons from '../components/RenderPlanReasons';
import TACompositionPanel from '../components/TACompositionPanel';
import UnifiedSetupPanel from '../components/UnifiedSetupPanel';
import MTFHeaderPanel from '../components/MTFHeaderPanel';
import ExecutionPanel from '../components/ExecutionPanel';
import PatternHintCard from '../components/PatternHintCard';
import PatternIntelligenceCard from '../components/PatternIntelligenceCard';
import EntryCard from '../components/EntryCard';
import { 
  computeVisibility, 
  getLayerLimits, 
  applyLimits, 
  getLayerStyle,
  LAYER_PRIORITY,
  VISUAL_PRIORITY 
} from '../engine/GraphVisibilityEngine';
import setupService from '../../../services/setupService';
import { buildNarrative, NarrativeSummary } from '../../../components/chart-engine/narrative';
import StoryLine from '../components/StoryLine';

// ════════════════════════════════════════════════════════════════
// RESEARCH TABS — 2 unified views (after Pass 3 refactor)
// ════════════════════════════════════════════════════════════════
import { 
  OverviewTab, 
  StructureTab, 
  SignalsTab, 
  ExecutionTab, 
  DeepDiveTab,
  RESEARCH_TABS 
} from './research-tabs';
import AnalysisTab from './research-tabs/AnalysisTab';
import ActionTab from './research-tabs/ActionTab';

// ════════════════════════════════════════════════════════════════
// PATTERN V2 — New unified pattern detection system
// ════════════════════════════════════════════════════════════════
import { usePatternV2, PatternStateCard } from '../../ta/patterns';

// ════════════════════════════════════════════════════════════════
// CONFLUENCE ENGINE — TA Decision Logic (NEW!)
// ════════════════════════════════════════════════════════════════
import { buildConfluence, getLayerVisibility } from '../utils/confluenceEngine';
import { buildTradeSetup } from '../utils/setupGenerator';

// ============================================
// STYLED COMPONENTS
// ============================================

const Container = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f8fafc;
  overflow-y: auto;
  font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
  
  * {
    font-family: inherit;
  }
`;

const TopBar = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: #ffffff;
  border-bottom: 1px solid #eef1f5;
  flex-wrap: wrap;
  gap: 12px;
`;

// ════════════════════════════════════════════════════════════════
// RESEARCH TABS — 5 Cognitive Layers Navigation
// ════════════════════════════════════════════════════════════════
const ResearchTabsBar = styled.div`
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 20px 12px;
  background: #ffffff;
  border-bottom: 1px solid #e2e8f0;
`;

const ResearchTabBtn = styled.button`
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  
  background: ${p => p.$active ? '#0f172a' : 'transparent'};
  color: ${p => p.$active ? '#ffffff' : '#64748b'};
  
  &:hover {
    background: ${p => p.$active ? '#0f172a' : '#f1f5f9'};
    color: ${p => p.$active ? '#ffffff' : '#0f172a'};
  }
`;

const ControlsLeft = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
`;

const ControlsRight = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`;

const SearchWrapper = styled.div`
  position: relative;
`;

const SearchInput = styled.input`
  width: 160px;
  padding: 10px 14px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  letter-spacing: 0.5px;
  
  &:focus {
    outline: none;
    border-color: #05A584;
    background: #ffffff;
  }
  
  &::placeholder {
    color: #94a3b8;
    font-weight: 500;
  }
`;

const SymbolDropdown = styled.div`
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 4px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  z-index: 100;
  max-height: 200px;
  overflow-y: auto;
`;

const SymbolOption = styled.button`
  width: 100%;
  padding: 10px 12px;
  text-align: left;
  border: none;
  background: ${({ $active }) => $active ? '#f0f9ff' : 'transparent'};
  font-size: 13px;
  font-weight: 500;
  color: #0f172a;
  cursor: pointer;
  
  &:hover {
    background: #f8fafc;
  }
`;

const TfGroup = styled.div`
  display: flex;
  gap: 2px;
  background: #f1f5f9;
  padding: 3px;
  border-radius: 8px;
`;

const TfButton = styled.button`
  /* PHASE 5.2 polish — segmented text, not a card-pill row.
     Inactive: muted gray text. Active: dark ink + thin emerald
     underline. No shadows, no scale tricks, no hover backgrounds. */
  padding: 6px 10px;
  border-radius: 0;
  font-size: 12px;
  font-weight: ${({ $active }) => ($active ? 600 : 500)};
  border: none;
  background: transparent;
  color: ${({ $active }) => ($active ? '#0f172a' : '#94a3b8')};
  cursor: pointer;
  transition: color 0.15s ease;
  position: relative;

  &:hover {
    color: #0f172a;
  }

  /* Active indicator — thin underline, no scale-up */
  &::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 50%;
    transform: translateX(-50%) scaleX(${({ $active }) => ($active ? '1' : '0')});
    width: 18px;
    height: 2px;
    background: #05A584;
    border-radius: 1px;
    transition: transform 0.15s ease;
  }
`;

const ChartTypeGroup = styled.div`
  display: flex;
  gap: 2px;
  background: #f1f5f9;
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
  background: ${({ $active }) => $active ? '#ffffff' : 'transparent'};
  color: ${({ $active }) => $active ? '#0f172a' : '#64748b'};
  cursor: pointer;
  box-shadow: ${({ $active }) => $active ? '0 1px 3px rgba(0,0,0,0.08)' : 'none'};
  
  svg {
    width: 16px;
    height: 16px;
  }
  
  &:hover {
    color: #0f172a;
  }
`;

const ViewModeWrapper = styled.div`
  position: relative;
`;

const ViewModeButton = styled.button`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
  cursor: pointer;
  
  &:hover {
    border-color: #cbd5e1;
  }
  
  svg {
    width: 14px;
    height: 14px;
    color: #94a3b8;
  }
`;

const ViewModeDropdown = styled.div`
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 4px;
  min-width: 140px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  z-index: 50;
  overflow: hidden;
`;

const ViewModeOption = styled.button`
  display: block;
  width: 100%;
  padding: 10px 14px;
  background: ${({ $active }) => $active ? '#f8fafc' : '#ffffff'};
  border: none;
  text-align: left;
  font-size: 13px;
  font-weight: ${({ $active }) => $active ? '600' : '500'};
  color: #0f172a;
  cursor: pointer;
  
  &:hover {
    background: #f1f5f9;
  }
`;

const ActionBtn = styled.button`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  color: #64748b;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  
  svg {
    width: 14px;
    height: 14px;
  }
  
  &:hover {
    border-color: #3b82f6;
    color: #3b82f6;
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  &.primary {
    background: #3b82f6;
    border-color: #3b82f6;
    color: #ffffff;
    
    &:hover {
      background: #2563eb;
    }
  }
  
  &.loading svg {
    animation: spin 1s linear infinite;
  }
  
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
`;

// LayerToggles and LayerToggleBtn removed - using ViewModeSelector instead

const MainContent = styled.div`
  flex: 1;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
`;

const ChartSection = styled.div`
  background: #ffffff;
  border: 1px solid #eef1f5;
  border-radius: 12px;
  overflow: hidden;
`;

const ErrorBanner = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #dc2626;
  font-size: 13px;
  
  svg {
    flex-shrink: 0;
  }
`;

const LoadingOverlay = styled.div`
  position: absolute;
  inset: 0;
  background: rgba(255,255,255,0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  z-index: 10;
  
  svg {
    animation: spin 1s linear infinite;
  }
  
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
`;

const SuccessToast = styled.div`
  position: fixed;
  bottom: 24px;
  right: 24px;
  padding: 12px 20px;
  background: #05A584;
  color: #ffffff;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  box-shadow: 0 4px 12px rgba(5, 165, 132, 0.3);
  z-index: 1000;
  animation: slideIn 0.3s ease;
  
  @keyframes slideIn {
    from {
      opacity: 0;
      transform: translateY(20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
`;

const DebugPanel = styled.div`
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  padding: 16px 20px;
  margin: 16px 0;
  font-family: 'Gilroy', 'Inter', -apple-system, sans-serif;
  
  .debug-title {
    font-weight: 700;
    font-size: 11px;
    color: #64748b;
    margin-bottom: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
  }
  
  .debug-row {
    display: flex;
    gap: 32px;
    padding: 8px 0;
    border-bottom: 1px solid #f1f5f9;
    
    &:last-child {
      border-bottom: none;
    }
  }
  
  .debug-label {
    min-width: 100px;
    font-size: 12px;
    font-weight: 500;
    color: #94a3b8;
  }
  
  .debug-value {
    font-size: 13px;
    font-weight: 600;
    color: #0f172a;
    
    &.bullish { color: #05A584; }
    &.bearish { color: #ef4444; }
    &.neutral { color: #64748b; }
  }
`;

// New Decision Layer UI Components
const BottomGrid = styled.div`
  display: flex;
  gap: 12px;
  margin-top: 12px;
  
  & > * {
    flex: 1;
    min-width: 0;
  }
  
  @media (max-width: 900px) {
    flex-direction: column;
  }
`;

const SubChartControls = styled.div`
  display: flex;
  align-items: center;
  justify-content: flex-start;
  flex-wrap: wrap;           /* UI FIX 2026-04-30: allow graceful wrap to next row
                                on narrow viewports instead of shrinking children */
  row-gap: 6px;
  column-gap: 6px;
  padding: 8px 16px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin: 0 0 8px 0;
  
  /* Overlay toggle section */
  .overlay-section {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    background: #f8fafc;
    border-radius: 6px;
    flex-shrink: 0;           /* keep the overlay cluster together as one unit */
  }
  
  .section-label {
    font-size: 10px;
    font-weight: 600;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    margin-right: 4px;
    flex-shrink: 0;
    white-space: nowrap;
  }
`;

const ControlDivider = styled.div`
  width: 1px;
  height: 24px;
  background: #e2e8f0;
  margin: 0 8px;
  flex-shrink: 0;
`;

const CollapsibleButton = styled.button`
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  background: ${({ $active }) => $active ? '#0f172a' : '#f8fafc'};
  border: 1px solid ${({ $active }) => $active ? '#0f172a' : '#e2e8f0'};
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  color: ${({ $active }) => $active ? '#ffffff' : '#64748b'};
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;        /* UI FIX 2026-04-30: never break label across two lines */
  flex-shrink: 0;             /* UI FIX 2026-04-30: don't let flex parent squeeze buttons */
  
  &:hover {
    border-color: ${({ $active }) => $active ? '#1e293b' : '#cbd5e1'};
    background: ${({ $active }) => $active ? '#1e293b' : '#f1f5f9'};
  }
  
  svg {
    width: 13px;
    height: 13px;
    opacity: ${({ $active }) => $active ? 1 : 0.6};
    flex-shrink: 0;
  }
  
  /* Status indicator dot */
  &::after {
    content: '';
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: ${({ $active }) => $active ? '#22c55e' : 'transparent'};
    margin-left: 4px;
    flex-shrink: 0;
  }
`;

const BottomSection = styled.div`
  margin-top: 12px;
`;

// ============================================
// CONSTANTS
// ============================================

const SYMBOLS = [
  'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT',
  'ADAUSDT', 'DOGEUSDT', 'AVAXUSDT', 'DOTUSDT', 'MATICUSDT',
  'LINKUSDT', 'UNIUSDT', 'ATOMUSDT', 'LTCUSDT', 'ETCUSDT',
  'FILUSDT', 'APTUSDT', 'ARBUSDT', 'OPUSDT', 'NEARUSDT',
  'INJUSDT', 'SUIUSDT', 'AAVEUSDT', 'MKRUSDT', 'CRVUSDT',
  'TONUSDT', 'SEIUSDT', 'TIAUSDT', 'JUPUSDT', 'WIFUSDT'
];
const TIMEFRAMES = ['4H', '1D', '7D', '30D', '180D', '1Y'];
const MTF_TIMEFRAMES = ['1D', '4H', '1H']; // Available MTF timeframes

// TF Display Names — human-readable labels
const TF_DISPLAY_NAMES = {
  '4H': '4H',
  '1D': '1D',
  '7D': '7D',
  '30D': '1M',   // 30D → 1M for clarity
  '180D': '6M',  // 180D → 6M for clarity
  '1Y': '1Y',
};

// ============================================
// COMPONENT
// ============================================

const ResearchView = ({ activeMode = 'research' }) => {
  // ═══════════════════════════════════════════════════════════════
  // GLOBAL STATE — Use MarketProvider for symbol/timeframe (SINGLE SOURCE OF TRUTH)
  // ═══════════════════════════════════════════════════════════════
  const { 
    symbol: globalSymbol, 
    timeframe: globalTimeframe, 
    setSymbol: setGlobalSymbol, 
    setTimeframe: setGlobalTimeframe 
  } = useMarket();
  
  // Map global timeframe to TA timeframes (1h -> 4H, 1d -> 1D, etc)
  const TF_MAP = { '1h': '4H', '4h': '4H', '1d': '1D', '7d': '7D', '30d': '30D', '180d': '180D', '1y': '1Y' };
  
  // SINGLE TIMEFRAME — derived from global or default to 4H
  const selectedTF = TF_MAP[globalTimeframe?.toLowerCase()] || '4H';
  const setSelectedTF = useCallback((tf) => {
    // Reverse map: TA timeframe -> global timeframe
    const reverseMap = { '4H': '4h', '1D': '1d', '7D': '7d', '30D': '30d', '180D': '180d', '1Y': '1y' };
    setGlobalTimeframe(reverseMap[tf] || '4h');
  }, [setGlobalTimeframe]);
  
  // SINGLE SYMBOL — use global
  const symbol = globalSymbol || 'BTCUSDT';
  const setSymbol = useCallback((s) => {
    setGlobalSymbol(s.toUpperCase());
  }, [setGlobalSymbol]);
  
  const [chartType, setChartType] = useState('candles');
  const [viewMode, setViewMode] = useState('auto');
  const [showViewModeDropdown, setShowViewModeDropdown] = useState(false);
  
  // ═══════════════════════════════════════════════════════════════
  // Active mode from header tabs (research/structure/signals/execution/deep)
  // Graph is ALWAYS visible — only panel below changes
  // ═══════════════════════════════════════════════════════════════
  
  const [searchQuery, setSearchQuery] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);
  
  // ═══════════════════════════════════════════════════════════════
  // TA OVERLAY STATE — moved from Chart Lab (RESEARCH EXCLUSIVE)
  // ═══════════════════════════════════════════════════════════════
  const [showTAOverlay, setShowTAOverlay] = useState(false);  // OFF by default - reduces noise
  
  // Hook into global render plan store for TA visualization
  const { renderPlan: globalRenderPlan, loading: renderPlanLoading, refresh: refreshRenderPlan } = useRenderPlan();
  
  // Collapsible panels state — toggles overlay visibility on chart
  // ALL OFF by default to reduce visual noise - user clicks to enable
  const [showFibonacciOverlay, setShowFibonacciOverlay] = useState(false);
  const [showPatternOverlay, setShowPatternOverlay] = useState(true);  // V4: Default ON for anchor-based patterns
  const [showSetupOverlay, setShowSetupOverlay] = useState(false);
  
  // PATTERN VIEW MODE — isolates pattern for readability
  // When true: hide structure, levels, indicators — show only candles + pattern
  const [patternViewMode, setPatternViewMode] = useState(false);
  
  // Data - NEW: MTF data structure
  const [tfMap, setTfMap] = useState({});
  const [mtfContext, setMtfContext] = useState(null);
  const [setupData, setSetupData] = useState(null);
  const [candles, setCandles] = useState([]);
  
  // Active elements for pattern activation
  const [activeElements, setActiveElements] = useState({});
  
  // Active pattern for switching between primary/alternatives
  const [activePatternId, setActivePatternId] = useState('primary');
  
  // Pattern index for V4 render contract switching (0 = primary, 1+ = alternatives)
  const [patternIndex, setPatternIndex] = useState(0);
  
  // Layer visibility now controlled by viewMode through layerVisibilityComputed
  // Removed manual layerVisibility state to avoid duplication
  
  // Indicator selection state (max 2 overlays, max 2 panes)
  const [selectedOverlays, setSelectedOverlays] = useState(['ema_20', 'ema_50']);
  const [selectedPanes, setSelectedPanes] = useState(['rsi', 'macd']);
  
  // Active indicators toggle (for pane visibility)
  const [activeIndicators, setActiveIndicators] = useState({ rsi: false, macd: false });
  
  // ═══════════════════════════════════════════════════════════════
  // PATTERN V2 — Unified detection with render contract & triggers
  // ═══════════════════════════════════════════════════════════════
  const baseSymbol = symbol.replace('USDT', '');
  const { pattern: patternV2, loading: patternV2Loading } = usePatternV2(baseSymbol, selectedTF);
  
  const handleIndicatorToggle = useCallback((indicator) => {
    setActiveIndicators(prev => ({
      ...prev,
      [indicator]: !prev[indicator]
    }));
  }, []);

  // Fetch MTF data from per-timeframe pipeline
  // CRITICAL: Fetch ALL timeframes at once, not one by one
  const fetchSetup = useCallback(async () => {
    console.log('[MTF] Starting fetch for ALL timeframes...');
    setLoading(true);
    setError(null);
    
    try {
      // Extract base symbol (BTC from BTCUSDT)
      const baseSymbol = symbol.replace('USDT', '');
      
      // CRITICAL: Request ALL TIMEFRAMES at once (was MTF_TIMEFRAMES, now TIMEFRAMES)
      const allTFs = TIMEFRAMES.join(',');
      const url = `/api/ta-engine/mtf/${baseSymbol}?timeframes=${allTFs}`;
      console.log('[MTF] Fetching ALL TFs:', url);
      
      // Add timeout controller - increased to 35s for MTF endpoint
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 35000);
      
      // Fetch MTF data
      const response = await fetch(url, { signal: controller.signal });
      clearTimeout(timeoutId);
      
      console.log('[MTF] Response status:', response.status);
      
      if (!response.ok) {
        throw new Error('Failed to fetch MTF analysis');
      }
      
      const data = await response.json();
      const tfKeys = Object.keys(data.tf_map || {});
      console.log('[MTF] Data received, tf_map keys:', tfKeys);
      
      // Store ALL MTF data in cache
      setTfMap(data.tf_map || {});
      setMtfContext(data.mtf_context || null);
      
      // Set active TF data as setupData for compatibility
      const activeTFData = data.tf_map?.[selectedTF] || {};
      setSetupData(activeTFData);
      setCandles(activeTFData.candles || []);
      setActivePatternId('primary');
      
      // 🔥 CRITICAL LOG: Verify each TF has different render_plan
      tfKeys.forEach(tf => {
        const tfData = data.tf_map[tf];
        const rp = tfData?.render_plan;
        console.log(`[MTF] TF=${tf}: candles=${tfData?.candles?.length}, swings=${rp?.structure?.swings?.length}, levels=${rp?.levels?.length}`);
      });
      
    } catch (err) {
      if (err.name === 'AbortError') {
        console.error('[MTF] Fetch timeout');
        setError('Analysis timeout - please try again');
      } else {
        console.error('[MTF] Fetch error:', err);
        setError(err.message || 'Failed to load analysis');
      }
    } finally {
      setLoading(false);
      console.log('[MTF] Fetch complete');
    }
  }, [symbol, selectedTF]);

  // Update setupData when selectedTF changes — use cached data
  useEffect(() => {
    if (tfMap[selectedTF]) {
      // Data already cached — use it IMMEDIATELY
      const tfData = tfMap[selectedTF];
      setSetupData(tfData);
      setCandles(tfData.candles || []);
      
      // 🔥 CRITICAL LOG: Verify TF switch changes data
      const rp = tfData.render_plan;
      console.log('[MTF] ═══════════════════════════════════════');
      console.log('[MTF] TF SWITCHED TO:', selectedTF);
      console.log('[MTF] Candles:', tfData.candles?.length);
      console.log('[MTF] render_plan:', !!rp);
      if (rp) {
        console.log('[MTF] > Structure swings:', rp.structure?.swings?.length);
        console.log('[MTF] > Levels:', rp.levels?.length);
        console.log('[MTF] > Market state:', rp.market_state?.trend);
        console.log('[MTF] > Execution:', rp.execution?.status);
      }
      console.log('[MTF] ═══════════════════════════════════════');
    } else if (Object.keys(tfMap).length === 0) {
      // No data at all — need initial fetch
      console.log('[MTF] No cached data, will fetch on mount');
    } else {
      // Data for some TFs exists but not for selected one
      console.log('[MTF] TF not in cache:', selectedTF, 'available:', Object.keys(tfMap));
    }
  }, [selectedTF, tfMap]);

  // Initial load
  useEffect(() => {
    fetchSetup();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol]); // Only re-fetch when symbol changes

  // Handle symbol change
  const handleSymbolSelect = (s) => {
    setSymbol(s);
    setSearchQuery('');
    setShowDropdown(false);
  };

  // Handle search - filter and show first 5
  const filteredSymbols = searchQuery
    ? SYMBOLS.filter(s => 
        s.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.replace('USDT', '').toLowerCase().includes(searchQuery.toLowerCase())
      ).slice(0, 5)
    : SYMBOLS.slice(0, 5);

  // Toggle element visibility
  const handleToggleElement = (elementKey) => {
    setActiveElements(prev => ({
      ...prev,
      [elementKey]: !prev[elementKey]
    }));
  };

  // Save idea — 1 click, no forms, no friction
  // Saves current TA snapshot to Ideas tab
  const [ideaSaved, setIdeaSaved] = React.useState(false);
  const [savingIdea, setSavingIdea] = React.useState(false);
  
  const handleSaveIdea = async () => {
    if (savingIdea || ideaSaved) return;
    
    try {
      setSavingIdea(true);
      
      // Build snapshot from current TA data
      const snapshot = {
        pattern: renderContract?.pattern_type || primaryPattern?.type || 'unknown',
        lifecycle: primaryPattern?.lifecycle || 'forming',
        probability: {
          up: setupData?.decision?.bullish_prob || 0.5,
          down: setupData?.decision?.bearish_prob || 0.5,
        },
        levels: {
          top: levels?.resistance?.[0]?.price || renderContract?.upper_line?.end_price,
          bottom: levels?.support?.[0]?.price || renderContract?.lower_line?.end_price,
          start_time: renderContract?.start_time,
          end_time: renderContract?.end_time,
        },
        interpretation: autoInterpret(
          renderContract?.pattern_type || primaryPattern?.type,
          setupData?.structure_context?.market_state,
          primaryPattern?.lifecycle
        ),
        context: {
          market_state: setupData?.structure_context?.market_state,
          mtf_bias: setupData?.decision?.bias,
          volatility: setupData?.structure_context?.volatility,
          trend_strength: setupData?.structure_context?.trend_strength,
        },
        render_contract: renderContract,
      };
      
      const result = await setupService.createIdea(symbol, selectedTF, [], '', snapshot);
      
      if (result.ok) {
        setIdeaSaved(true);
        setToast('✔ Saved to Ideas');
        setTimeout(() => {
          setToast(null);
          setIdeaSaved(false);
        }, 3000);
      }
    } catch (err) {
      setError('Failed to save idea');
      console.error('Save idea error:', err);
    } finally {
      setSavingIdea(false);
    }
  };
  
  // Rule-based auto-interpretation (no LLM, fast & stable)
  const autoInterpret = (pattern, marketState, lifecycle) => {
    if (lifecycle === 'confirmed_up') return 'Breakout confirmed ↑';
    if (lifecycle === 'confirmed_down') return 'Breakdown confirmed ↓';
    if (marketState === 'compression' || marketState === 'consolidating') return 'Market was consolidating';
    if (marketState === 'trending_up') return 'Uptrend in progress';
    if (marketState === 'trending_down') return 'Downtrend in progress';
    if (pattern === 'triangle' || pattern === 'wedge') return 'Converging price action';
    if (pattern === 'rectangle' || pattern === 'range') return 'Horizontal consolidation';
    return 'Neutral structure';
  };

  // Share (placeholder)
  const handleShare = () => {
    if (navigator.share) {
      navigator.share({
        title: `${symbol} Technical Analysis`,
        text: `${setupData?.technical_bias?.toUpperCase()} bias with ${Math.round((setupData?.bias_confidence || 0) * 100)}% confidence`,
        url: window.location.href,
      });
    }
  };

  // Derived data - Map backend v2 format to component format
  // v2 returns: { primary_pattern, alternative_patterns, decision, scenarios, confidence_explanation, ... }
  
  // ═══════════════════════════════════════════════════════════════
  // PATTERN SOURCE PRIORITY (NEW GEOMETRY LAYER INTEGRATION)
  // ═══════════════════════════════════════════════════════════════
  // 1. final_analysis.ui.main_overlay (new geometry layer)
  // 2. pattern_render_contract (legacy V2 pipeline)
  // 3. primary_pattern (fallback)
  
  const finalAnalysis = setupData?.final_analysis;
  const mainOverlay = finalAnalysis?.ui?.main_overlay;
  const analysisMode = finalAnalysis?.analysis_mode;
  
  // Get pattern based on activePatternId
  // PRIORITY: Use final_analysis.ui.main_overlay if figure mode
  // BUG FIX 2026-04-30: wrap in useMemo so identity is stable; otherwise the
  // dependent useMemo at line ~1061 sees a fresh object every render and
  // recomputes primaryPattern unnecessarily.
  const renderContract = React.useMemo(() => (
    mainOverlay?.geometry ? {
      // Convert new geometry format to legacy render contract format
      type: mainOverlay.type,
      render_mode: mainOverlay.render_mode,
      geometry_contract: mainOverlay.geometry,
      boundaries: mainOverlay.geometry?.boundaries ? [
        { id: 'upper', ...mainOverlay.geometry.boundaries.upper },
        { id: 'lower', ...mainOverlay.geometry.boundaries.lower },
      ] : [],
      window: mainOverlay.geometry?.window,
      anchors: mainOverlay.geometry?.anchors,
      confidence: mainOverlay.geometry?.shape_metrics?.cleanliness || 0.6,
    } : setupData?.pattern_render_contract
  ), [mainOverlay, setupData?.pattern_render_contract]);
  
  const legacyPrimaryPattern = setupData?.primary_pattern;
  
  // V2: Get pattern from render_plan.patterns.primary (with forward extension for ranges)
  const renderPlanPattern = setupData?.render_plan?.patterns?.primary;
  
  // Build unified pattern object from render contract
  const primaryPattern = React.useMemo(() => {
    // PRIORITY 1: Use render_plan.patterns.primary
    if (renderPlanPattern) {
      console.log('[ResearchViewNew] Using render_plan pattern:', renderPlanPattern.type, renderPlanPattern);
      return {
        ...(legacyPrimaryPattern || {}),
        ...(renderContract || {}),
        // Use render_plan pattern data
        type: renderPlanPattern.type,
        is_active: renderPlanPattern.is_active,
        points: renderPlanPattern.points,
        forward_bars: renderPlanPattern.forward_bars,
        confidence: renderPlanPattern.confidence || renderPlanPattern.score,
        direction: renderPlanPattern.direction || renderPlanPattern.bias,
        breakout_level: renderPlanPattern.breakout_level,
        invalidation: renderPlanPattern.invalidation_level,
        lifecycle: renderPlanPattern.state || 'forming',
      };
    }
    
    // PRIORITY 2: Use anchor-based render contract
    if (renderContract) {
      // Use anchor-based pattern data - OVERRIDE legacy values
      return {
        // Legacy data as fallback
        ...(legacyPrimaryPattern || {}),
        // OVERRIDE with render contract values (anchor-based)
        type: renderContract.type,
        direction: renderContract.direction || renderContract.bias,
        confidence: renderContract.confidence,
        final_score: renderContract.confidence,
        touch_score: renderContract.touch_score,
        render_quality: renderContract.render_quality,
        breakout_level: renderContract.render?.levels?.[0]?.price,
        invalidation: null,
        anchor_points: renderContract.anchors,
        lifecycle: renderContract.state || 'forming',
      };
    }
    return legacyPrimaryPattern;
  }, [renderContract, legacyPrimaryPattern, renderPlanPattern]);
  
  // BUG FIX 2026-04-30: stabilise reference so dependent useMemo doesn't
  // recompute on every render due to a fresh `[]` literal.
  const alternativePatterns = React.useMemo(
    () => setupData?.alternative_patterns || [],
    [setupData?.alternative_patterns]
  );
  
  // CRITICAL: Memoize patternV2 to prevent infinite re-renders
  const patternV2Memoized = React.useMemo(() => ({
    primary_pattern: primaryPattern,
    alternative_patterns: alternativePatterns,
  }), [primaryPattern, alternativePatterns]);
  
  // Determine which pattern to display on chart
  const getActivePattern = () => {
    if (activePatternId === 'primary') return primaryPattern;
    const altIndex = parseInt(activePatternId.replace('alt-', ''));
    return alternativePatterns[altIndex] || primaryPattern;
  };
  
  const pattern = getActivePattern();
  
  // LEVELS — use from render_plan (max 5, ranked by strength)
  const levels = React.useMemo(() => {
    const rpLevels = setupData?.render_plan?.levels;
    if (rpLevels?.length) {
      // Convert to format ResearchChart expects
      return rpLevels.map(l => ({
        price: l.price,
        type: l.type, // support/resistance
        strength: l.strength,
        source: l.source,
      }));
    }
    return setupData?.levels || [];
  }, [setupData?.render_plan?.levels, setupData?.levels]);
  
  const structure = setupData?.structure;
  const setup = setupData?.setup;
  
  // New v2 data
  const decision = setupData?.decision;
  
  // BUILD scenarios from decision and structure
  const scenarios = React.useMemo(() => {
    if (!setupData) return [];
    
    const decisionData = setupData.decision;
    const structure = setupData.structure_context;
    const pattern = setupData.primary_pattern;
    const rp = setupData.render_plan;
    const currentPrice = setupData.current_price || rp?.market_state?.current_price;
    const levels = rp?.levels || [];
    
    const result = [];
    
    // Bullish scenario
    const resistances = levels.filter(l => l.type === 'resistance' && l.price > currentPrice);
    const nearestResistance = resistances.length > 0 ? resistances.reduce((a, b) => b.price < a.price ? b : a) : null;
    
    if (nearestResistance) {
      result.push({
        id: 'bullish',
        type: 'bullish',
        title: 'Bullish Breakout',
        description: `Break above ${nearestResistance.price?.toFixed(0)} triggers bullish continuation`,
        probability: decisionData?.bias === 'bullish' ? 0.6 : decisionData?.bias === 'neutral' ? 0.4 : 0.3,
        trigger_price: nearestResistance.price,
        target_price: nearestResistance.price * 1.03,
      });
    }
    
    // Bearish scenario
    const supports = levels.filter(l => l.type === 'support' && l.price < currentPrice);
    const nearestSupport = supports.length > 0 ? supports.reduce((a, b) => b.price > a.price ? b : a) : null;
    
    if (nearestSupport) {
      result.push({
        id: 'bearish',
        type: 'bearish',
        title: 'Bearish Breakdown',
        description: `Break below ${nearestSupport.price?.toFixed(0)} triggers bearish move`,
        probability: decisionData?.bias === 'bearish' ? 0.6 : decisionData?.bias === 'neutral' ? 0.4 : 0.3,
        trigger_price: nearestSupport.price,
        target_price: nearestSupport.price * 0.97,
      });
    }
    
    // Range scenario (if both levels exist)
    if (nearestResistance && nearestSupport) {
      result.push({
        id: 'range',
        type: 'neutral',
        title: 'Range Continuation',
        description: `Price consolidates between ${nearestSupport.price?.toFixed(0)} - ${nearestResistance.price?.toFixed(0)}`,
        probability: decisionData?.bias === 'neutral' ? 0.5 : 0.3,
        trigger_price: currentPrice,
        target_price: null,
      });
    }
    
    return result;
  }, [setupData]);
  
  // BUILD confidenceExplanation from REAL backend numbers ONLY (Pass 2 honesty).
  // No magic 0.5/0.6/0.65/0.8 placeholders — if backend didn't compute it,
  // we surface null and the UI handles it gracefully.
  const confidenceExplanation = React.useMemo(() => {
    if (!setupData?.decision) return null;

    const d = setupData.decision;
    const pattern = setupData.primary_pattern;

    // Real pattern-level scores
    if (pattern?.scores) {
      const scores = pattern.scores;
      const out = {};
      ['geometry', 'structure', 'level', 'recency', 'cleanliness'].forEach((k) => {
        if (typeof scores[k] === 'number' && Number.isFinite(scores[k])) {
          out[k] = Math.max(0, Math.min(1, scores[k]));
        }
      });
      if (Object.keys(out).length) return out;
    }

    // Real confidence_breakdown from decision
    const cb = d.confidence_breakdown;
    if (cb && typeof cb === 'object') {
      const out = {};
      Object.entries(cb).forEach(([k, v]) => {
        if (typeof v === 'number' && Number.isFinite(v)) {
          out[k] = Math.max(0, Math.min(1, v));
        }
      });
      if (Object.keys(out).length) return out;
    }

    // Nothing real — return null. UI must NOT synthesize.
    return null;
  }, [setupData]);
  
  // BUILD explanation from decision and pattern — format for ExplanationPanel
  const explanation = React.useMemo(() => {
    if (!setupData) return null;
    
    const d = setupData.decision;
    const pattern = setupData.primary_pattern;
    const levels = setupData.render_plan?.levels || [];
    const currentPrice = setupData.current_price;
    
    if (!d && !pattern) return null;
    
    // Build summary
    let summary = '';
    if (d?.summary) {
      summary = d.summary;
    } else if (pattern?.type) {
      summary = `${pattern.type.replace(/_/g, ' ')} pattern detected with ${pattern.direction || 'neutral'} bias.`;
    } else {
      summary = 'Market conditions being analyzed.';
    }
    
    // Build action
    let action = '';
    if (d?.bias === 'bullish' && d?.tradeability === 'high') {
      action = 'Look for long entries on pullbacks to support.';
    } else if (d?.bias === 'bearish' && d?.tradeability === 'high') {
      action = 'Look for short entries on rallies to resistance.';
    } else if (d?.tradeability === 'medium') {
      action = 'Wait for clearer setup before taking position.';
    } else {
      action = 'No clear action — observe and wait for better conditions.';
    }
    
    // Build risk
    let risk = '';
    const resistances = levels.filter(l => l.type === 'resistance' && l.price > currentPrice);
    const supports = levels.filter(l => l.type === 'support' && l.price < currentPrice);
    
    if (d?.bias === 'bullish' && supports.length > 0) {
      const nearestSupport = supports.reduce((a, b) => b.price > a.price ? b : a);
      risk = `Invalidation below ${nearestSupport.price?.toFixed(0)} support level.`;
    } else if (d?.bias === 'bearish' && resistances.length > 0) {
      const nearestResistance = resistances.reduce((a, b) => b.price < a.price ? b : a);
      risk = `Invalidation above ${nearestResistance.price?.toFixed(0)} resistance level.`;
    } else {
      risk = 'Define clear stop-loss before entering any position.';
    }
    
    // Confidence
    let confidence = 'medium';
    if (d?.confidence >= 0.7 || d?.tradeability === 'high') confidence = 'high';
    else if (d?.confidence <= 0.3 || d?.tradeability === 'low') confidence = 'low';
    
    return { summary, action, risk, confidence };
  }, [setupData]);
  
  // TRADE SETUP — Execution-ready entry/stop/targets
  const tradeSetup = setupData?.trade_setup || null;
  
  // BASE LAYER — always visible
  const baseLayer = setupData?.base_layer || null;
  
  // Structure context from V2 engine (rich data)
  const structureContext = setupData?.structure_context || null;
  
  // STRUCTURE VISUALIZATION — pivot points, BOS/CHOCH, trendlines
  const structureVisualization = setupData?.structure_visualization || null;
  
  // CHART STRUCTURE — build from render_plan.structure for chart rendering
  // Format: { labels: [{time, price, label, type}], breaks: [...], legs: [...] }
  const chartStructure = React.useMemo(() => {
    const rpStructure = setupData?.render_plan?.structure;
    if (!rpStructure?.swings?.length) return null;
    
    // Convert swings to labels format that ResearchChart expects
    const labels = rpStructure.swings.map(s => ({
      time: s.time,
      price: s.price,
      label: s.type, // HH/HL/LH/LL
      type: s.type?.includes('H') && s.type !== 'HL' ? 'high' : 'low',
    }));
    
    // Build breaks from BOS/CHOCH
    const breaks = [];
    if (rpStructure.bos) {
      breaks.push({
        time: rpStructure.bos.time,
        level: rpStructure.bos.price,
        type: 'bos',
        direction: rpStructure.bos.direction,
      });
    }
    if (rpStructure.choch) {
      breaks.push({
        time: rpStructure.choch.time,
        level: rpStructure.choch.price,
        type: 'choch',
        direction: rpStructure.choch.direction,
      });
    }
    
    return { labels, breaks, legs: [] };
  }, [setupData?.render_plan?.structure]);
  
  // TA CONTEXT — unified contributions from all TA sources
  // Transform backend format to TAContextPanel expected format
  const taContext = React.useMemo(() => {
    const rawContext = setupData?.ta_context;
    if (!rawContext) return null;
    
    const indicators = rawContext.indicators || {};
    const signals = indicators.signals || [];
    
    // Count bullish/bearish/neutral from signals
    let bullishCount = 0;
    let bearishCount = 0;
    let neutralCount = 0;
    let bullishScore = 0;
    let bearishScore = 0;
    
    const bullishSignals = [];
    const bearishSignals = [];
    const neutralSignals = [];
    
    signals.forEach(s => {
      const direction = s.direction?.toLowerCase();
      const strength = s.strength || 0;
      const item = {
        name: s.name,
        signal_type: s.signal_type,
        strength: strength,
        description: s.description,
        signal: direction,
        score: direction === 'bullish' ? strength : direction === 'bearish' ? -strength : 0,
        source: 'indicator',
        impact: strength / (signals.length || 1),
      };
      
      if (direction === 'bullish') {
        bullishCount++;
        bullishScore += strength;
        bullishSignals.push(item);
      } else if (direction === 'bearish') {
        bearishCount++;
        bearishScore += strength;
        bearishSignals.push(item);
      } else {
        neutralCount++;
        neutralSignals.push(item);
      }
    });
    
    // Calculate aggregated bias and score
    const totalScore = bullishScore - bearishScore;
    const maxPossibleScore = signals.length * 1; // max strength is 1
    const normalizedScore = maxPossibleScore > 0 ? totalScore / maxPossibleScore : 0;
    
    let aggregatedBias = 'neutral';
    if (normalizedScore > 0.1) aggregatedBias = 'bullish';
    else if (normalizedScore < -0.1) aggregatedBias = 'bearish';
    
    // Sort by strength for top_drivers
    const allContribs = [...bullishSignals, ...bearishSignals, ...neutralSignals]
      .sort((a, b) => Math.abs(b.strength) - Math.abs(a.strength));
    
    return {
      summary: {
        aggregated_bias: aggregatedBias,
        aggregated_score: normalizedScore,
        aggregated_confidence: Math.min(1, (bullishCount + bearishCount) / (signals.length || 1)),
        total_sources: signals.length,
        active_sources: bullishCount + bearishCount,
      },
      indicators: {
        bullish: bullishCount,
        bearish: bearishCount,
        neutral: neutralCount,
        total: signals.length,
      },
      top_drivers: allContribs.slice(0, 10),
      all_contributions: allContribs,
      hidden_but_used: [],
      rendered_default: [],
    };
  }, [setupData?.ta_context]);
  
  // RENDER PLAN — brain → chart mapping (from VisualMappingEngine)
  const renderPlan = setupData?.render_plan || null;
  
  // ════════════════════════════════════════════════════════════════
  // CONFLUENCE ENGINE — TA Decision Logic (NEW!)
  // Transforms raw data into actionable analysis
  // ════════════════════════════════════════════════════════════════
  const confluence = React.useMemo(() => {
    const result = buildConfluence(renderPlan);
    if (result) {
      console.log('[CONFLUENCE] ═══════════════════════════════════');
      console.log('[CONFLUENCE] TF:', selectedTF);
      console.log('[CONFLUENCE] Bias:', result.bias, '| Strength:', result.strength);
      console.log('[CONFLUENCE] Score:', result.score);
      console.log('[CONFLUENCE] Decision:', result.decision);
      console.log('[CONFLUENCE] Signals:', result.signals);
      console.log('[CONFLUENCE] ═══════════════════════════════════');
    }
    return result;
  }, [renderPlan, selectedTF]);
  
  // TRADE SETUP — generated from confluence analysis
  const generatedTradeSetup = React.useMemo(() => {
    return buildTradeSetup(renderPlan, confluence);
  }, [renderPlan, confluence]);
  
  // MODE-BASED LAYER VISIBILITY — Auto/Classic/Smart/Minimal
  const modeLayerVisibility = React.useMemo(() => {
    return getLayerVisibility(viewMode);
  }, [viewMode]);
  
  // TA COMPOSITION — complete technical setup view (BUILD FROM DATA!)
  const taComposition = React.useMemo(() => {
    if (!setupData) return null;
    
    const pattern = setupData.primary_pattern;
    const fib = setupData.fib;
    const rp = setupData.render_plan;
    const indicators = setupData.indicators;
    const decision = setupData.decision;
    
    // Если нет паттерна и нет данных — нет setup
    const hasPattern = pattern && pattern.type;
    const hasFib = fib && fib.levels?.length > 0;
    
    // Build active_figure from primary_pattern
    let active_figure = null;
    if (hasPattern) {
      active_figure = {
        type: pattern.type,
        direction: pattern.direction,
        confidence: pattern.confidence || 0.5,
        breakout_level: pattern.breakout_price || pattern.upper_line?.end_price,
        invalidation_level: pattern.invalidation_price || pattern.lower_line?.end_price,
      };
    }
    
    // Build active_fib from fib data
    let active_fib = null;
    if (hasFib) {
      const fibLevels = fib.levels || [];
      active_fib = {
        swing_type: fib.type || 'retracement',
        current_position: fib.current_zone || 'between_levels',
        key_levels: fibLevels.slice(0, 5).map(l => ({
          level: l.level,
          price: l.price,
          status: l.status || 'active',
        })),
      };
    }
    
    // Build relevant_overlays from indicators
    const relevant_overlays = [];
    if (indicators?.overlays) {
      indicators.overlays.slice(0, 3).forEach(o => {
        const lastValue = o.data?.[o.data.length - 1]?.value;
        if (lastValue) {
          relevant_overlays.push({
            display_name: o.name || o.id,
            current_value: lastValue,
          });
        }
      });
    }
    
    // Build breakout_logic from pattern or levels
    let breakout_logic = null;
    const levels = rp?.levels || setupData.levels || [];
    const currentPrice = setupData.current_price || rp?.market_state?.current_price;
    
    if (levels.length > 0 && currentPrice) {
      const resistances = levels.filter(l => l.type === 'resistance' && l.price > currentPrice);
      const supports = levels.filter(l => l.type === 'support' && l.price < currentPrice);
      
      const nearestResistance = resistances.length > 0 ? resistances.reduce((a, b) => b.price < a.price ? b : a) : null;
      const nearestSupport = supports.length > 0 ? supports.reduce((a, b) => b.price > a.price ? b : a) : null;
      
      if (nearestResistance || nearestSupport) {
        breakout_logic = {
          breakout_level: nearestResistance?.price,
          invalidation_level: nearestSupport?.price,
          breakout_type: 'resistance_break',
          risk_pct: currentPrice && nearestSupport ? ((currentPrice - nearestSupport.price) / currentPrice * 100) : null,
        };
      }
    }
    
    // Determine setup quality
    let setup_quality = 'low';
    if (hasPattern && pattern.confidence > 0.7) setup_quality = 'high';
    else if (hasPattern && pattern.confidence > 0.5) setup_quality = 'medium';
    else if (hasFib || levels.length > 0) setup_quality = 'medium';
    
    // Build setup_summary with lifecycle info
    let setup_summary = '';
    
    // Check for display_message from Display Gate (pattern rejected)
    const displayMessage = setupData?.display_message;
    
    if (displayMessage && !hasPattern) {
      // Display Gate rejected pattern - show fallback message
      setup_summary = displayMessage;
    } else if (hasPattern) {
      const lifecycle = pattern.lifecycle;
      const lifecycleStage = lifecycle?.stage || 'forming';
      const completion = lifecycle?.completion || 0;
      
      // Add lifecycle stage badge
      const stageBadges = {
        'forming': '🔄 Forming',
        'maturing': '⏳ Maturing',
        'confirmed': '✅ Confirmed',
        'broken': '❌ Broken',
        'invalidated': '⚠️ Invalidated',
      };
      const stageBadge = stageBadges[lifecycleStage] || lifecycleStage;
      
      setup_summary = `${pattern.label || pattern.type?.replace(/_/g, ' ')} — ${stageBadge}`;
      
      // Add completion percentage for forming/maturing
      if (lifecycleStage === 'forming' || lifecycleStage === 'maturing') {
        setup_summary += ` (${Math.round(completion * 100)}%)`;
      }
      
      // Add direction bias
      if (pattern.direction) {
        setup_summary += ` · ${pattern.direction.charAt(0).toUpperCase() + pattern.direction.slice(1)} bias`;
      }
      
      // Add state reason if available
      if (lifecycle?.state_reason) {
        setup_summary = lifecycle.state_reason;
      }
    } else if (decision?.summary) {
      setup_summary = decision.summary;
    } else {
      setup_summary = 'Analyzing market structure...';
    }
    
    return {
      has_active_setup: hasPattern || hasFib || levels.length > 0,
      setup_quality,
      setup_summary,
      active_figure,
      active_fib,
      relevant_overlays,
      breakout_logic,
      active_zone: null,
      structure_context: decision?.context || 'neutral',
    };
  }, [setupData]);
  
  // ═══════════════════════════════════════════════════════════════
  // MARKET MECHANICS — POI, Liquidity from render_plan
  // ═══════════════════════════════════════════════════════════════
  const poi = setupData?.poi || null;
  
  // LIQUIDITY — prioritize render_plan over raw data
  const liquidity = React.useMemo(() => {
    const rpLiquidity = setupData?.render_plan?.liquidity;
    if (rpLiquidity) {
      // Convert render_plan format to MarketMechanicsRenderer format
      const pools = [];
      
      // Add BSL (above price)
      (rpLiquidity.bsl || []).forEach(bsl => {
        const price = typeof bsl.price === 'number' ? bsl.price : parseFloat(bsl.price);
        pools.push({
          type: 'buy_side_liquidity',
          side: 'high',
          price: price,
          strength: bsl.strength,
          touches: bsl.touches,
          label: bsl.label || `BSL @ ${price ? Math.round(price) : 'N/A'}`,
          status: 'active',
        });
      });
      
      // Add SSL (below price)
      (rpLiquidity.ssl || []).forEach(ssl => {
        const price = typeof ssl.price === 'number' ? ssl.price : parseFloat(ssl.price);
        pools.push({
          type: 'sell_side_liquidity',
          side: 'low',
          price: price,
          strength: ssl.strength,
          touches: ssl.touches,
          label: ssl.label || `SSL @ ${price ? Math.round(price) : 'N/A'}`,
          status: 'active',
        });
      });
      
      return {
        pools,
        sweeps: rpLiquidity.sweeps || [],
        equal_highs: [],
        equal_lows: [],
      };
    }
    return setupData?.liquidity || null;
  }, [setupData?.render_plan?.liquidity, setupData?.liquidity]);
  
  const chochValidation = setupData?.choch_validation || null;
  const displacement = setupData?.displacement || null;
  
  // ═══════════════════════════════════════════════════════════════
  // EXECUTION — prioritize render_plan execution (always visible!)
  // ═══════════════════════════════════════════════════════════════
  const execution = React.useMemo(() => {
    const rpExecution = setupData?.render_plan?.execution;
    if (rpExecution) {
      return rpExecution;
    }
    return setupData?.execution || null;
  }, [setupData?.render_plan?.execution, setupData?.execution]);
  
  const chainMap = setupData?.chain_map || [];
  const unifiedSetupData = setupData?.unified_setup || null;
  const fib = setupData?.fib || null;
  
  // Handle pattern click (switch between primary/alternatives)
  const handlePatternClick = (patternId) => {
    setActivePatternId(patternId);
  };
  
  // Handle scenario click (highlight corresponding pattern)
  const handleScenarioClick = (scenario) => {
    // Map scenario to pattern
    if (scenario.pattern) {
      const altIndex = alternativePatterns.findIndex(p => p.type === scenario.pattern);
      if (altIndex >= 0) {
        setActivePatternId(`alt-${altIndex}`);
      } else if (primaryPattern?.type === scenario.pattern) {
        setActivePatternId('primary');
      }
    }
  };
  
  // Map structure to array format for PatternActivationLayer
  // BUG FIX 2026-04-30: memoise — dependent components compare references and
  // a fresh array each render forces unnecessary updates.
  const structureArray = React.useMemo(() => (
    structure ? [
      ...Array(structure.hh || 0).fill({ type: 'HH' }),
      ...Array(structure.hl || 0).fill({ type: 'HL' }),
      ...Array(structure.lh || 0).fill({ type: 'LH' }),
      ...Array(structure.ll || 0).fill({ type: 'LL' }),
    ] : []
  ), [structure]);
  
  // Build unified setup object for all components
  const unifiedSetup = React.useMemo(() => {
    // PRIORITY: Use backend unified_setup if available
    if (setupData?.unified_setup && setupData.unified_setup.direction) {
      return {
        ...setupData.unified_setup,
        // Ensure required fields exist
        valid: setupData.unified_setup.valid ?? false,
        direction: setupData.unified_setup.direction || 'no_trade',
        confidence: setupData.unified_setup.confidence || setupData?.decision?.confidence || 0,
        narrative: setupData.unified_setup.narrative || '',
        chain: setupData.unified_setup.chain || [],
        conflicts: setupData.unified_setup.conflicts || [],
      };
    }
    
    if (!setupData) return null;
    
    const d = setupData.decision;
    const rp = setupData.render_plan;
    const indicators = setupData.indicator_result || setupData.ta_context?.indicators?.signals || [];
    const structureState = setupData.structure_state || setupData.structure_context;
    
    // Build structure array from structure_state swings or render_plan structure
    const buildStructureArray = () => {
      const swings = rp?.structure?.swings || [];
      if (swings.length > 0) {
        return swings.map(s => ({ type: s.type, time: s.time, price: s.price }));
      }
      // Fallback to structure_state counts
      if (structureState) {
        const arr = [];
        for (let i = 0; i < (structureState.hh_count || 0); i++) arr.push({ type: 'HH' });
        for (let i = 0; i < (structureState.hl_count || 0); i++) arr.push({ type: 'HL' });
        for (let i = 0; i < (structureState.lh_count || 0); i++) arr.push({ type: 'LH' });
        for (let i = 0; i < (structureState.ll_count || 0); i++) arr.push({ type: 'LL' });
        return arr;
      }
      return structureArray;
    };
    
    // Build indicators array from indicator_result
    const buildIndicatorsArray = () => {
      if (Array.isArray(indicators) && indicators.length > 0) {
        return indicators.map(ind => ({
          name: ind.name,
          direction: ind.direction?.toLowerCase(),
          signal_type: ind.signal_type,
          strength: ind.strength,
          description: ind.description,
        }));
      }
      return [];
    };
    
    // Derive bias and confidence from decision
    const derivedBias = d?.bias || (pattern?.direction) || 'neutral';
    const derivedConfidence = d?.confidence || pattern?.confidence || 0;
    const derivedSetupType = pattern?.type || (rp?.market_state?.trend_direction) || 'analysis';
    
    // Convert bias to direction for UnifiedSetupPanel
    const getDirection = (bias) => {
      if (bias === 'bullish' || bias === 'lean_bullish') return 'long';
      if (bias === 'bearish' || bias === 'lean_bearish') return 'short';
      return 'no_trade';
    };
    
    // Determine if setup is valid
    const isValid = derivedBias !== 'neutral' && derivedConfidence > 0.4;
    
    return {
      // Pattern as array (for PatternActivationLayer)
      patterns: pattern ? [{
        type: pattern.type,
        confidence: pattern.confidence,
        direction: pattern.direction || derivedBias,
        points: pattern.points,
      }] : [],
      
      // Single pattern object (for ResearchChart)
      pattern: pattern,
      
      // Levels array - from render_plan or computed levels
      levels: levels,
      
      // Structure as array with actual data
      structure: buildStructureArray(),
      
      // Setup details from decision
      setup_type: derivedSetupType,
      direction: getDirection(derivedBias),
      valid: isValid,
      confidence: derivedConfidence,
      confluence_score: d?.confidence || 0,
      narrative: d?.summary || `${pattern?.type || 'Pattern'} detected with ${derivedBias} bias`,
      trigger: setup?.trigger,
      invalidation: setup?.invalidation,
      targets: setup?.targets || [],
      
      // Indicators from API
      indicators: buildIndicatorsArray(),
      
      // Conflicts/risks
      conflicts: [],
      
      // Market context from decision and render_plan
      market_regime: rp?.market_state?.trend_direction || structureState?.regime || d?.context || 'neutral',
      asset: symbol,
      timeframe: selectedTF,
      current_price: setupData.current_price,
      
      // Additional fields for DeepAnalysisBlocks
      primary_confluence: d ? {
        score: d.confidence,
        components: [d.bias, d.strength].filter(Boolean),
      } : null,
      explanation: d?.summary,
    };
  }, [setupData, pattern, levels, structureArray, setup, symbol, selectedTF]);
  
  const technicalBias = unifiedSetup?.direction || 'neutral';
  const biasConfidence = unifiedSetup?.confidence || 0;

  // ═══════════════════════════════════════════════════════════════
  // 🧠 UNIFIED TA STATE — single source of truth (Pass 3 refactor)
  // Every UI block must read bias / confidence / tradeability from here.
  // No local recomputation, no magic numbers.
  // ═══════════════════════════════════════════════════════════════
  const unified = useUnifiedTAState(setupData, selectedTF);

  // ═══════════════════════════════════════════════════════════════
  // GRAPH VISIBILITY ENGINE — Intelligent layer prioritization
  // ═══════════════════════════════════════════════════════════════
  const currentPrice = candles?.length > 0 ? candles[candles.length - 1]?.close : null;
  
  // Get pattern from render_plan.patterns.primary (v2) OR legacy primary_pattern
  const rpPatternPrimary = setupData?.render_plan?.patterns?.primary;
  const effectivePattern = rpPatternPrimary || setupData?.primary_pattern;
  
  const visibilityContext = {
    setup: setupData?.setup,
    pattern_primary: effectivePattern,  // Use v2 pattern from render_plan
    pattern_alternative: setupData?.alternative_patterns?.[0],
    poi: poi,
    liquidity: liquidity,
    fib: setupData?.fibonacci,
    indicators: setupData?.indicators,
    choch: chochValidation,
    displacement: displacement,
    structure_context: structureContext || structure,
    current_price: currentPrice,
  };
  
  const layerVisibilityComputed = computeVisibility(visibilityContext, viewMode, renderPlan);
  console.log('[Visibility] viewMode:', viewMode, 'renderPlan:', renderPlan);
  console.log('[Visibility] computed:', layerVisibilityComputed);
  console.log('[Visibility] context keys with data:', Object.keys(visibilityContext).filter(k => visibilityContext[k]));
  const limits = getLayerLimits(viewMode);
  
  // Apply limits to data with price-based prioritization
  const limitedPOI = poi ? {
    ...poi,
    zones: applyLimits(poi.zones, 'poi_zones', limits, currentPrice),
  } : null;
  
  const limitedLiquidity = liquidity ? {
    ...liquidity,
    equal_highs: applyLimits(liquidity.equal_highs, 'liquidity_levels', limits, currentPrice),
    equal_lows: applyLimits(liquidity.equal_lows, 'liquidity_levels', limits, currentPrice),
  } : null;

  // Get visual styles for layers
  const poiStyle = getLayerStyle('poi');
  const liquidityStyle = getLayerStyle('liquidity');
  const patternStyle = getLayerStyle('pattern_primary');
  const fibStyle = getLayerStyle('fib');

  // ═══════════════════════════════════════════════════════════════
  // PATTERN VIEW MODE — isolates pattern for readability
  // When active: hide structure, levels, indicators, liquidity
  // Keep: candles + active pattern + breakout/neckline
  // ═══════════════════════════════════════════════════════════════
  
  // Determine what to show based on view mode
  // PATTERN VIEW MODE overrides normal visibility settings
  const showPatterns = viewMode !== 'clean' && layerVisibilityComputed.patterns;
  const showLevels = patternViewMode ? false : (layerVisibilityComputed.levels !== false);
  const showStructure = patternViewMode ? false : layerVisibilityComputed.structure;
  const showIndicators = patternViewMode ? false : (viewMode === 'manual');
  const showBaseLayer = patternViewMode ? true : (viewMode !== 'minimal');
  
  // Additional visibility controls for Pattern View mode
  const showMarketMechanicsComputed = patternViewMode ? false : (viewMode !== 'classic');
  const showLiquidityComputed = patternViewMode ? false : layerVisibilityComputed.liquidity;
  const showPOIComputed = patternViewMode ? false : layerVisibilityComputed.poi;
  const showSweepsComputed = patternViewMode ? false : layerVisibilityComputed.liquidity;
  const showCHOCHComputed = patternViewMode ? false : layerVisibilityComputed.structure;

  return (
    <Container data-testid="research-view">
      {/* Top Control Bar */}
      <TopBar>
        <ControlsLeft>
          {/* Search Asset */}
          <SearchWrapper>
            <SearchInput
              type="text"
              placeholder="Search symbol (BTC, ETH…)"
              value={showDropdown ? searchQuery : (searchQuery || '')}
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

          {/* MTF Timeframe Selector — ALL TIMEFRAMES */}
          <TfGroup>
            {TIMEFRAMES.map(tf => (
              <TfButton
                key={tf}
                $active={selectedTF === tf}
                onClick={() => setSelectedTF(tf)}
                data-testid={`tf-${tf}`}
              >
                {TF_DISPLAY_NAMES[tf] || tf}
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

          {/* Layer Toggles removed - using ViewModeSelector below chart instead */}
        </ControlsLeft>
      </TopBar>

      {/* ════════════════════════════════════════════════════════════════ */}
      {/* CHART CONTROLS — PHASE 5 (2026-04-30) cleanup                  */}
      {/* Was: View(4) + Indicators + Overlays(5+) + Save + Trade        */}
      {/*       = 22 toggles in one row.                                 */}
      {/* Now: Indicators ▾ · Layers ▾ · Save Idea · Trade This          */}
      {/* ViewMode state remains 'auto' (default) — selector hidden.    */}
      {/* ════════════════════════════════════════════════════════════════ */}
      {!loading && (
        <SubChartControls data-testid="sub-chart-controls">
          {/* Indicators — already a dropdown component */}
          <span className="section-label">Indicators</span>
          <IndicatorSelector
            selectedOverlays={selectedOverlays}
            selectedPanes={selectedPanes}
            onOverlaysChange={setSelectedOverlays}
            onPanesChange={setSelectedPanes}
          />

          <ControlDivider />

          {/* Layers — single details/summary collapser containing the
              5 chart-overlay toggles + pattern-isolation view + pattern
              switcher. Closed by default → no shouting strip. */}
          <span className="section-label">Layers</span>
          <details
            data-testid="layers-dropdown"
            style={{
              position: 'relative',
              flexShrink: 0,
            }}
          >
            <summary
              style={{
                listStyle: 'none',
                cursor: 'pointer',
                userSelect: 'none',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '5px 10px',
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 500,
                color: '#334155',
                whiteSpace: 'nowrap',
              }}
            >
              <Layers size={13} />
              {(() => {
                const n =
                  (showFibonacciOverlay ? 1 : 0) +
                  (showPatternOverlay   ? 1 : 0) +
                  (showSetupOverlay     ? 1 : 0) +
                  (showTAOverlay        ? 1 : 0);
                return n > 0 ? `Layers (${n})` : 'Layers';
              })()}
            </summary>
            <div
              style={{
                position: 'absolute',
                top: 'calc(100% + 4px)',
                left: 0,
                zIndex: 30,
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: '8px',
                boxShadow: '0 8px 24px rgba(15, 23, 42, 0.08)',
                padding: '8px',
                minWidth: '200px',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
              }}
            >
              {/* PHASE 5.2 polish — header so the dropdown reads as a list,
                  not a stack of buttons. */}
              <div
                style={{
                  fontSize: '10px',
                  fontWeight: 600,
                  color: '#94a3b8',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  padding: '4px 8px 6px',
                  borderBottom: '1px solid #f1f5f9',
                  marginBottom: '4px',
                }}
              >
                Layers
              </div>
              <CollapsibleButton
                $active={showFibonacciOverlay}
                onClick={() => setShowFibonacciOverlay(!showFibonacciOverlay)}
                data-testid="overlay-fib"
                title="Show Fibonacci retracement levels on chart"
              >
                <RefreshCw size={13} />
                Fibonacci
              </CollapsibleButton>
              <CollapsibleButton
                $active={showPatternOverlay}
                onClick={() => setShowPatternOverlay(!showPatternOverlay)}
                data-testid="overlay-pattern"
                title="Show detected pattern info card on chart"
              >
                <Triangle size={13} />
                Patterns
              </CollapsibleButton>
              {showPatternOverlay && (
                <CollapsibleButton
                  $active={patternViewMode}
                  onClick={() => setPatternViewMode(!patternViewMode)}
                  data-testid="overlay-view"
                  title="Pattern View Mode — isolates pattern, hides structure/levels"
                >
                  <Eye size={13} />
                  Isolate pattern
                </CollapsibleButton>
              )}
              {showPatternOverlay &&
                setupData?.alternative_render_contracts?.length > 0 && (
                  <button
                    data-testid="pattern-switcher-btn"
                    onClick={() => {
                      const totalPatterns =
                        1 + (setupData?.alternative_render_contracts?.length || 0);
                      setPatternIndex((patternIndex + 1) % totalPatterns);
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '6px 10px',
                      background: '#f8fafc',
                      border: '1px solid #e2e8f0',
                      borderRadius: '6px',
                      color: '#334155',
                      fontSize: '12px',
                      fontWeight: '500',
                      cursor: 'pointer',
                      textAlign: 'left',
                    }}
                    title="Switch between detected patterns"
                  >
                    Switch pattern{' '}
                    {patternIndex + 1}/
                    {1 + (setupData?.alternative_render_contracts?.length || 0)}
                  </button>
                )}
              <CollapsibleButton
                $active={showSetupOverlay}
                onClick={() => setShowSetupOverlay(!showSetupOverlay)}
                data-testid="overlay-setup"
                title="Show trade setup info card on chart"
              >
                <Target size={13} />
                Setup
              </CollapsibleButton>
              <CollapsibleButton
                $active={showTAOverlay}
                onClick={() => setShowTAOverlay(!showTAOverlay)}
                data-testid="overlay-ta"
                title="Show full TA analysis overlay on chart"
              >
                <Layers size={13} />
                TA composite
              </CollapsibleButton>
            </div>
          </details>

          <ControlDivider />

          {/* SAVE IDEA — secondary action (outline). */}
          <button
            data-testid="save-idea-btn"
            onClick={handleSaveIdea}
            disabled={savingIdea || ideaSaved || !setupData}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              background: ideaSaved ? '#10b981' : '#ffffff',
              border: ideaSaved ? '1px solid #10b981' : '1px solid #e2e8f0',
              borderRadius: '6px',
              color: ideaSaved ? '#ffffff' : '#334155',
              fontSize: '12px',
              fontWeight: 600,
              cursor: savingIdea || ideaSaved ? 'default' : 'pointer',
              transition: 'all 0.15s ease',
              opacity: !setupData ? 0.5 : 1,
              whiteSpace: 'nowrap',
              flexShrink: 0,
            }}
            title="Save current analysis as Idea"
          >
            {ideaSaved ? (
              <>
                <Check size={14} />
                Saved
              </>
            ) : savingIdea ? (
              <>
                <RefreshCw size={14} style={{ animation: 'spin 1s linear infinite' }} />
                Saving...
              </>
            ) : (
              <>
                <Bookmark size={14} />
                Save Idea
              </>
            )}
          </button>

          {/* Trade This — TA → Trading Decision Bridge */}
          <TradeThisButton setupData={setupData} />
        </SubChartControls>
      )}

      {/* Main Content — Graph (always visible) + Dynamic Panel */}
      <MainContent>
        {/* ════════════════════════════════════════════════════════════════ */}
        {/* GRAPH — ALWAYS VISIBLE (center of the system) */}
        {/* Height is auto-calculated, no fixed height to avoid empty space */}
        {/* ════════════════════════════════════════════════════════════════ */}
        <div style={{ position: 'relative', marginBottom: '0' }} data-testid="graph-section">
          <ResearchChart
            candles={candles}
            data={setupData}
            symbol={symbol}
            timeframe={selectedTF}
            chartType={chartType}
            levels={levels}
            structure={structure}
            showLevels={showLevels}
            showStructure={showStructure}
            showLiquidity={showLiquidityComputed}
            showSweeps={showSweepsComputed}
            showCHOCH={showCHOCHComputed}
            showNarrative={patternViewMode ? false : (viewMode !== 'minimal')}
            decision={decision}
            indicatorOverlays={
              patternViewMode ? [] : (
                layerVisibilityComputed.indicators_overlay
                  ? (setupData?.indicators?.overlays || [])
                      .filter(o => selectedOverlays.includes(o.id))
                      .slice(0, limits.overlays)
                  : []
              )
            }
            patternV2={patternV2Memoized}
            patternGeometry={setupData?.pattern_geometry}
            fibonacci={fib || setupData?.fibonacci}
            showFibonacciOverlay={patternViewMode ? false : showFibonacciOverlay}
            showPatternOverlay={showPatternOverlay}
            patternViewMode={patternViewMode}
            patternWindow={patternV2?.renderContract?.window || setupData?.pattern_render_contract?.window}
            renderPlan={setupData?.render_plan}
          />
          
          {/* Render Plan Overlay */}
          {showTAOverlay && (globalRenderPlan || renderPlan) && (
            <RenderPlanOverlay 
              renderPlan={globalRenderPlan || renderPlan}
              onChainStepClick={(step) => console.log('[Research] Step clicked:', step)}
            />
          )}
          
          {/* Loading overlay */}
          {loading && (
            <div style={{
              position: 'absolute',
              inset: 0,
              background: 'rgba(255,255,255,0.85)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '10px',
              zIndex: 10,
            }}>
              <RefreshCw size={24} color="#3b82f6" style={{ animation: 'spin 1s linear infinite' }} />
              <span style={{ color: '#64748b', fontSize: 13 }}>Analyzing {symbol}...</span>
            </div>
          )}
        </div>

        {/* ════════════════════════════════════════════════════════════════ */}
        {/* COMPACT INFO PANELS — Only show if overlay is active, no empty space */}
        {/* ════════════════════════════════════════════════════════════════ */}
        {(showPatternOverlay || showSetupOverlay || showFibonacciOverlay) && (
          <div style={{ 
            display: 'flex', 
            gap: '12px', 
            marginTop: '8px',
            marginBottom: '8px',
            flexWrap: 'wrap',
          }}>
            {/* PATTERN INFO PANEL — Shows detected pattern below chart */}
            {/* Hide on Structure tab - TA Explorer shows patterns there */}
            {/* PHASE 5.2 polish — light theme, product language. */}
            {showPatternOverlay && primaryPattern && primaryPattern.type && activeMode !== 'structure' && (
              <div
                data-testid="pattern-card"
                style={{
                flex: '1 1 280px',
                maxWidth: '380px',
                background: '#ffffff',
                borderRadius: '10px',
                padding: '14px 16px',
                border: '1px solid #e2e8f0',
                boxShadow: 'inset 3px 0 0 ' + (
                  primaryPattern.direction === 'bullish' ? '#10b981'
                  : primaryPattern.direction === 'bearish' ? '#ef4444'
                  : '#94a3b8'
                ),
              }}>
                {/* Title — pattern name only, no shouty caps. */}
                <div style={{
                  fontSize: '15px',
                  fontWeight: 600,
                  color: '#0f172a',
                  letterSpacing: '-0.01em',
                }}>
                  {primaryPattern.type
                    ?.split('_')
                    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
                    .join(' ')}
                </div>

                {/* Subline — direction + strength, secondary tone. */}
                <div style={{
                  marginTop: '4px',
                  fontSize: '13px',
                  color: '#475569',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  flexWrap: 'wrap',
                }}>
                  <span style={{
                    color:
                      primaryPattern.direction === 'bullish' ? '#059669'
                    : primaryPattern.direction === 'bearish' ? '#dc2626'
                    : '#64748b',
                    fontWeight: 500,
                  }}>
                    {primaryPattern.direction === 'bullish' ? 'Bullish pattern'
                    : primaryPattern.direction === 'bearish' ? 'Bearish pattern'
                    : 'Neutral pattern'}
                  </span>
                  <span style={{ color: '#cbd5e1' }}>·</span>
                  <span>
                    <span style={{ color: '#94a3b8' }}>Strength </span>
                    <span style={{ color: '#0f172a', fontWeight: 600 }}>
                      {Math.round((primaryPattern.confidence || primaryPattern.final_score || 0) * 100)}%
                    </span>
                  </span>
                  {(primaryPattern.lifecycle || primaryPattern.is_active) && (
                    <>
                      <span style={{ color: '#cbd5e1' }}>·</span>
                      <span style={{ color: '#94a3b8' }}>Active</span>
                    </>
                  )}
                </div>

                {/* Optional break level — kept as quiet secondary line. */}
                {primaryPattern.breakout_level && (
                  <div style={{
                    marginTop: '6px',
                    fontSize: '12px',
                    color: '#64748b',
                  }}>
                    Break <span style={{ color: '#0f172a', fontWeight: 600 }}>
                      ${Number(primaryPattern.breakout_level).toLocaleString()}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* SETUP INFO PANEL — Shows trade setup below chart */}
            {showSetupOverlay && (
              <div style={{
                flex: '1 1 280px',
                maxWidth: '360px',
              }}>
                <UnifiedSetupPanel setup={unifiedSetup} />
              </div>
            )}
            
            {/* FIBONACCI INFO PANEL — Shows Fib levels below chart */}
            {showFibonacciOverlay && (fib?.fib_set || setupData?.fibonacci?.fib_set) && (
              <div style={{
                flex: '1 1 280px',
                maxWidth: '360px',
                background: '#0f172a',
                borderRadius: '10px',
                padding: '12px 14px',
                border: '1px solid rgba(245, 158, 11, 0.3)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
                  <div style={{ 
                    width: '24px', 
                    height: '24px', 
                    borderRadius: '5px',
                    background: 'rgba(245, 158, 11, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}>
                    <span style={{ color: '#f59e0b', fontSize: '12px', fontWeight: '700' }}>Φ</span>
                  </div>
                  <span style={{ color: '#f1f5f9', fontSize: '14px', fontWeight: '600' }}>Fibonacci Levels</span>
                  <span style={{ 
                    marginLeft: 'auto',
                    padding: '2px 6px', 
                    borderRadius: '4px', 
                    background: (fib?.fib_set?.direction || setupData?.fibonacci?.fib_set?.direction) === 'bullish' 
                      ? 'rgba(5,165,132,0.2)' : 'rgba(239,68,68,0.2)',
                    color: (fib?.fib_set?.direction || setupData?.fibonacci?.fib_set?.direction) === 'bullish' 
                      ? '#05A584' : '#ef4444',
                    fontSize: '11px',
                    fontWeight: '600',
                    textTransform: 'uppercase',
                  }}>
                    {(fib?.fib_set?.direction || setupData?.fibonacci?.fib_set?.direction) === 'bullish' ? '↗ BULLISH' : '↘ BEARISH'}
                  </span>
                </div>
                {/* Swing High/Low */}
                <div style={{ display: 'flex', gap: '16px', fontSize: '11px', marginBottom: '8px', paddingBottom: '8px', borderBottom: '1px solid rgba(245, 158, 11, 0.1)' }}>
                  <div>
                    <span style={{ color: '#64748b' }}>High: </span>
                    <span style={{ color: '#f1f5f9', fontWeight: '600' }}>
                      ${Number(fib?.fib_set?.swing_high?.price || setupData?.fibonacci?.fib_set?.swing_high?.price || 0).toLocaleString()}
                    </span>
                  </div>
                  <div>
                    <span style={{ color: '#64748b' }}>Low: </span>
                    <span style={{ color: '#f1f5f9', fontWeight: '600' }}>
                      ${Number(fib?.fib_set?.swing_low?.price || setupData?.fibonacci?.fib_set?.swing_low?.price || 0).toLocaleString()}
                    </span>
                  </div>
                </div>
                {/* Retracement Levels */}
                <div style={{ marginBottom: '6px' }}>
                  <span style={{ color: '#64748b', fontSize: '9px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Retracement</span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', fontSize: '10px' }}>
                  {(fib?.fib_set?.retracement_levels || setupData?.fibonacci?.fib_set?.retracement_levels || []).slice(0, 5).map((level, i) => (
                    <div key={i} style={{ 
                      padding: '3px 8px', 
                      borderRadius: '4px', 
                      background: level.is_key_level ? 'rgba(245, 158, 11, 0.15)' : '#1e293b',
                      border: level.is_key_level ? '1px solid rgba(245, 158, 11, 0.3)' : 'none',
                    }}>
                      <span style={{ color: level.is_key_level ? '#f59e0b' : '#64748b', fontWeight: level.is_key_level ? '600' : '400' }}>{level.label}: </span>
                      <span style={{ color: level.is_key_level ? '#f59e0b' : '#f1f5f9', fontWeight: '600' }}>
                        ${Number(level.price).toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ════════════════════════════════════════════════════════════════ */}
        {/* MARKET STATE HEADER — always-on truth bar (Pass 3 refactor) */}
        {/* ════════════════════════════════════════════════════════════════ */}
        {unified && (
          <MarketStateHeader unified={unified} mtfContext={mtfContext} />
        )}

        {/* ════════════════════════════════════════════════════════════════ */}
        {/* DYNAMIC PANEL — 2 unified views (Pass 3 refactor) */}
        {/* analysis  = state · geometry · evidence · detail  (was 4 tabs)    */}
        {/* action    = trade plan with honest WAIT-banner    (was Execution) */}
        {/* ════════════════════════════════════════════════════════════════ */}

        {/* MODE: ANALYSIS */}
        {activeMode === 'analysis' && (
          <AnalysisTab
            unified={unified}
            setupData={setupData}
            mtfContext={mtfContext}
            symbol={symbol}
            selectedTF={selectedTF}
            chartType={chartType}
            overviewProps={{
              setupData,
              mtfContext,
              primaryPattern,
              decision,
              levels,
              selectedTF,
              contextFit: setupData?.summary?.context_fit || setupData?.context_fit,
              context: setupData?.summary?.context || setupData?.context,
              historical: setupData?.summary?.historical || setupData?.historical,
              probabilityV3: setupData?.summary?.probability_v3 || setupData?.probability_v3,
              regimeDrift: setupData?.summary?.regime_drift || setupData?.regime_drift,
            }}
            structureProps={{
              symbol,
              selectedTF,
              chartType,
              levels,
              structure,
              decision,
              primaryPattern,
              alternativePatterns,
              activePatternId,
              onPatternClick: handlePatternClick,
              patternV2,
              setupData,
              showLevels,
              showStructure,
              showLiquidity: showLiquidityComputed,
              showSweeps: showSweepsComputed,
              showCHOCH: showCHOCHComputed,
              showNarrative: false,
              indicatorOverlays: [],
              fibonacci: fib || setupData?.fibonacci,
              showFibonacciOverlay: false,
              showPatternOverlay,
              patternViewMode,
              patternWindow: patternV2?.renderContract?.window || setupData?.pattern_render_contract?.window,
              showTAOverlay: false,
              renderPlan: null,
              loading,
              analysisMode,
              hideChart: true,
            }}
            signalsProps={{
              setupData,
              taContext,
              decision,
              activeIndicators,
              onIndicatorToggle: handleIndicatorToggle,
              confidenceExplanation,
            }}
            deepProps={{
              setupData,
              decision,
              primaryPattern,
              symbol,
              selectedTF,
              explanation,
              unifiedSetup,
              technicalBias,
              biasConfidence,
              activeElements,
              onToggleElement: handleToggleElement,
              liquidity,
              displacement,
              chochValidation,
              poi,
              tradeSetup,
              renderPlan,
            }}
          />
        )}

        {/* MODE: ACTION */}
        {activeMode === 'action' && (
          <ActionTab
            unified={unified}
            setupData={setupData}
            decision={decision}
            levels={levels}
            primaryPattern={primaryPattern}
            scenarios={scenarios}
            onScenarioClick={handleScenarioClick}
            taComposition={taComposition}
            contextFit={setupData?.summary?.context_fit || setupData?.context_fit}
            tradeable={setupData?.summary?.tradeable ?? true}
            historical={setupData?.summary?.historical || setupData?.historical}
            executionPlan={setupData?.summary?.execution_plan || setupData?.execution_plan}
            probabilityV3={setupData?.summary?.probability_v3 || setupData?.probability_v3}
            regimeDrift={setupData?.summary?.regime_drift || setupData?.regime_drift}
          />
        )}
      </MainContent>

      {/* Toast */}
      {toast && <SuccessToast>{toast}</SuccessToast>}
    </Container>
  );
};


// ═══════════════════════════════════════════════════════════
// Sprint 3: Trade This Button — TA → Trading Decision Bridge
// ═══════════════════════════════════════════════════════════
function TradeThisButton({ setupData }) {
  const [status, setStatus] = useState('idle'); // idle | loading | success | error
  const API_URL = process.env.REACT_APP_BACKEND_URL || '';
  
  const handleTradeThis = async () => {
    if (!setupData) return;
    
    setStatus('loading');
    try {
      const setup = setupData.setup || {};
      const pattern = setupData.pattern || {};
      const symbol = setupData.symbol || 'BTCUSDT';
      const direction = setup.direction || pattern.direction || 'bullish';
      const side = direction === 'bullish' ? 'BUY' : 'SELL';
      
      const targets = setup.targets || [];
      const entryPrice = setup.trigger || setupData.candles?.[setupData.candles?.length - 1]?.close || 0;
      const stopPrice = setup.invalidation || entryPrice * (side === 'BUY' ? 0.97 : 1.03);
      const targetPrice = targets[0]?.price || entryPrice * (side === 'BUY' ? 1.03 : 0.97);
      
      const res = await fetch(`${API_URL}/api/trade-this`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol,
          side,
          entry_price: entryPrice,
          stop_price: stopPrice,
          target_price: targetPrice,
          strategy: pattern.type || 'MANUAL_FROM_TA',
          confidence: (pattern.confidence || 0.5),
          timeframe: setupData.timeframe || '1D',
          thesis: `TA Pattern: ${pattern.type || 'manual'} (${(pattern.confidence || 0) * 100}%)`,
        }),
      });
      
      const data = await res.json();
      if (data.ok) {
        setStatus('success');
        setTimeout(() => setStatus('idle'), 3000);
      } else {
        setStatus('error');
        setTimeout(() => setStatus('idle'), 3000);
      }
    } catch (err) {
      console.error('Trade This failed:', err);
      setStatus('error');
      setTimeout(() => setStatus('idle'), 3000);
    }
  };
  
  const buttonStyle = {
    /* PHASE 5.2 polish — primary CTA, no orange/dev fill. */
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '6px 14px',
    background:
      status === 'success' ? '#10b981'
    : status === 'error'   ? '#ef4444'
    : status === 'loading' ? '#475569'
    : '#0f172a',
    border: 'none',
    borderRadius: '6px',
    color: '#ffffff',
    fontSize: '12px',
    fontWeight: 600,
    cursor: status === 'idle' ? 'pointer' : 'default',
    transition: 'all 0.15s ease',
    opacity: !setupData ? 0.4 : 1,
    whiteSpace: 'nowrap',
    flexShrink: 0,
  };
  
  return (
    <button
      data-testid="trade-this-btn"
      onClick={handleTradeThis}
      disabled={!setupData || status !== 'idle'}
      style={buttonStyle}
      title="Create trading decision from current TA setup"
    >
      {status === 'success' ? 'Decision Created' : 
       status === 'error' ? 'Failed' :
       status === 'loading' ? 'Creating...' : 
       'Trade Setup'}
    </button>
  );
}

export default ResearchView; 
