/**
 * PatternSVGOverlay.jsx — VISUAL MODE BASED RENDERING
 * 
 * PRINCIPLE: 1 SCREEN = 1 IDEA
 * 
 * Visual Mode dictates what CAN be rendered:
 * - range_only: box + R/S + triggers (NO swings, NO polyline)
 * - horizontal_pattern: polyline + neckline (NO range, NO swings)
 * - compression_pattern: trendlines only (NO range, NO swings)
 * - structure_only: HH/HL/LL only (NO patterns)
 * - none: nothing
 * 
 * Frontend OBEYS visual_mode from backend. No exceptions.
 */

import React, { useEffect, useState, useCallback } from 'react';

const PatternSVGOverlay = ({ chart, priceSeries, pattern, renderContract, data, renderStack, historyOverlay, mtfContext, externalHoveredIndex, externalSetHoveredIndex, selectedIndex, onPatternClick, lifecycle }) => {
  const [svgElements, setSvgElements] = useState([]);
  
  // ═══════════════════════════════════════════════════════════════
  // HOVER STATE — используем external если есть, иначе локальный
  // ═══════════════════════════════════════════════════════════════
  const [localHoveredIndex, setLocalHoveredIndex] = useState(null);
  const hoveredIndex = externalHoveredIndex !== undefined ? externalHoveredIndex : localHoveredIndex;
  const setHoveredIndex = externalSetHoveredIndex || setLocalHoveredIndex;
  
  const buildElements = useCallback(() => {
    if (!chart || !priceSeries) return [];
    
    try {
      const timeScale = chart.timeScale();
      if (!timeScale) return [];
      
      const visibleRange = timeScale.getVisibleRange();
      if (!visibleRange) return [];
      
      const elements = [];
      
      // ═══════════════════════════════════════════════════════════════
      // MTF CONTEXT — Higher TF range/levels FIRST (background)
      // ═══════════════════════════════════════════════════════════════
      if (mtfContext) {
        const mtfElements = renderMTFContext(mtfContext, chart, priceSeries, timeScale, visibleRange);
        elements.push(...mtfElements);
      }
      
      // ═══════════════════════════════════════════════════════════════
      // HISTORY OVERLAY — Ghost patterns (underneath current)
      // ═══════════════════════════════════════════════════════════════
      if (historyOverlay && historyOverlay.length > 0) {
        const ghostElements = renderHistoryOverlay(historyOverlay, chart, priceSeries, timeScale, visibleRange);
        elements.push(...ghostElements);
      }
      
      // ═══════════════════════════════════════════════════════════════
      // RENDER STACK MODE — Multi-pattern visualization with hover
      // ═══════════════════════════════════════════════════════════════
      if (renderStack && renderStack.length > 0) {
        const stackElements = renderStackElements(renderStack, chart, priceSeries, timeScale, visibleRange, hoveredIndex, setHoveredIndex, selectedIndex, onPatternClick, lifecycle);
        elements.push(...stackElements);
        return elements;
      }
      
      // ═══════════════════════════════════════════════════════════════
      // VISUAL MODE CHECK — CRITICAL!
      // ═══════════════════════════════════════════════════════════════
      const visualMode = data?.visual_mode || renderContract?.visual_mode;
      const mode = visualMode?.mode || 'structure_only';
      
      // Check what we're ALLOWED to render
      const allowed = visualMode?.allowed || [];
      const forbidden = visualMode?.forbidden || [];
      
      console.log('[PatternSVGOverlay] Visual Mode:', mode, 'Allowed:', allowed, 'Forbidden:', forbidden);
      
      // If mode is 'none', render nothing
      if (mode === 'none') {
        return [];
      }
      
      const normalizeTime = (t) => {
        if (!t) return null;
        return t > 9999999999 ? Math.floor(t / 1000) : t;
      };
      
      const toX = (time) => {
        const normalized = normalizeTime(time);
        if (!normalized) return null;
        const x = timeScale.timeToCoordinate(normalized);
        return Number.isFinite(x) ? x : null;
      };
      
      const toY = (price) => {
        if (price === null || price === undefined) return null;
        try {
          const y = priceSeries.priceToCoordinate(price);
          return Number.isFinite(y) ? y : null;
        } catch {
          return null;
        }
      };
      
      // ═══════════════════════════════════════════════════════════════
      // RENDER BASED ON VISUAL MODE
      // ═══════════════════════════════════════════════════════════════
      
      // RANGE_ONLY mode
      if (mode === 'range_only') {
        const activeRange = data?.active_range || data?.ta_layers?.active_range;
        const scenarios = data?.ta_layers?.scenarios;
        const probability = data?.ta_layers?.probability;
        
        if (activeRange && activeRange.top && activeRange.bottom) {
          return renderRange(activeRange, toX, toY, visibleRange, scenarios, probability);
        }
        
        // Fallback: render from renderContract if it's box mode
        if (renderContract?.box) {
          return renderUnifiedBox(renderContract, toX, toY, visibleRange);
        }
        
        return [];
      }
      
      // HORIZONTAL_PATTERN mode (double/triple top/bottom)
      if (mode === 'horizontal_pattern') {
        if (renderContract?.polyline) {
          return renderUnifiedPolyline(renderContract, toX, toY);
        }
        return [];
      }
      
      // COMPRESSION_PATTERN mode (triangle/wedge/channel)
      if (mode === 'compression_pattern') {
        if (renderContract?.lines) {
          return renderUnifiedTwoLines(renderContract, toX, toY);
        }
        return [];
      }
      
      // SWING_PATTERN mode (H&S)
      if (mode === 'swing_pattern') {
        if (renderContract?.polyline) {
          return renderUnifiedHS(renderContract, toX, toY);
        }
        return [];
      }
      
      // STRUCTURE_ONLY mode — minimal markers
      if (mode === 'structure_only') {
        // Don't render complex patterns, just structure markers if available
        return renderStructureMarkers(data, toX, toY);
      }
      
      // ═══════════════════════════════════════════════════════════════
      // FALLBACK: Legacy render (for backwards compatibility)
      // ═══════════════════════════════════════════════════════════════
      if (renderContract && renderContract.type && renderContract.render_mode) {
        const elements = renderUnifiedContract(renderContract, toX, toY, visibleRange);
        const triggerElements = renderTriggerLines(data?.v2_triggers, toX, toY, visibleRange);
        return [...elements, ...triggerElements];
      }
      
      return [];
      
    } catch (err) {
      console.error('[PatternSVGOverlay] Error:', err);
      return [];
    }
  }, [chart, priceSeries, renderContract, data, renderStack, hoveredIndex, selectedIndex, onPatternClick, lifecycle]);
  
  useEffect(() => {
    if (!chart || !priceSeries) {
      setSvgElements([]);
      return;
    }
    
    const update = () => setSvgElements(buildElements());
    update();
    
    const timeScale = chart.timeScale();
    if (timeScale) timeScale.subscribeVisibleTimeRangeChange(update);
    chart.subscribeCrosshairMove(update);
    
    return () => {
      if (timeScale) timeScale.unsubscribeVisibleTimeRangeChange(update);
      chart.unsubscribeCrosshairMove(update);
    };
  }, [chart, priceSeries, renderContract, data, buildElements, hoveredIndex]);
  
  if (!svgElements || svgElements.length === 0) return null;
  
  return (
    <svg
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',  // Allow chart interaction through SVG
        overflow: 'visible',
        zIndex: 50,
      }}
    >
      {svgElements}
    </svg>
  );
};

// ═══════════════════════════════════════════════════════════════
// PATTERN LEGEND — показывает какие паттерны на графике
// ═══════════════════════════════════════════════════════════════

// Helper: определить market state из stack (fallback)
const getMarketStateFromStack = (renderStack) => {
  const dominant = renderStack.find(p => p.role === 'dominant');
  const domType = dominant?.type?.toLowerCase() || '';
  
  if (domType.includes('rectangle') || domType.includes('range') || domType.includes('channel')) {
    return { state: 'COMPRESSION', color: '#fbbf24' };
  }
  if (domType.includes('triangle') || domType.includes('wedge')) {
    return { state: 'COMPRESSION', color: '#fbbf24' };
  }
  if (domType.includes('top') || domType.includes('head_shoulders')) {
    return { state: 'REVERSAL ↓', color: '#ef4444' };
  }
  if (domType.includes('bottom') || domType.includes('inverse')) {
    return { state: 'REVERSAL ↑', color: '#22c55e' };
  }
  if (renderStack.length > 1) {
    return { state: 'CONFLICTED', color: '#f97316' };
  }
  return { state: 'DEVELOPING', color: '#8b5cf6' };
};

export const PatternLegend = ({ renderStack, hoveredIndex, setHoveredIndex, interpretation, watchLevels, lifecycle, selectedIndex, onPatternClick, ...props }) => {
  if (!renderStack || renderStack.length === 0) return null;
  
  const formatType = (type) => {
    if (!type) return 'Pattern';
    return type.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  };
  
  // Используем interpretation из backend если есть
  const marketState = interpretation?.market_state 
    ? { 
        state: interpretation.market_state, 
        color: interpretation.market_state.includes('REVERSAL ↓') ? '#ef4444' 
             : interpretation.market_state.includes('REVERSAL ↑') ? '#22c55e'
             : interpretation.market_state === 'COMPRESSION' ? '#fbbf24'
             : interpretation.market_state === 'CONFLICTED' ? '#f97316'
             : '#8b5cf6'
      }
    : getMarketStateFromStack(renderStack);
  
  const dominant = renderStack.find(p => p.role === 'dominant');
  
  return (
    <div 
      className="absolute left-4 bottom-4 bg-black/90 backdrop-blur-sm rounded-lg border border-white/10 z-50"
      style={{ minWidth: '220px', maxWidth: '280px', fontFamily: "'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif" }}
    >
      {/* ═══════════════════════════════════════════════════════════════
          MARKET STATE BAR — главная информация сверху
          ═══════════════════════════════════════════════════════════════ */}
      <div 
        className="px-3 py-2 border-b border-white/10 flex items-center gap-2"
        style={{ backgroundColor: `${marketState.color}15` }}
      >
        <div 
          className="w-2 h-2 rounded-full animate-pulse"
          style={{ backgroundColor: marketState.color }}
        />
        <span className="text-xs font-bold uppercase" style={{ color: marketState.color }}>
          {marketState.state}
        </span>
        <span className="text-xs text-white/50 ml-auto">
          {formatType(dominant?.type)}
        </span>
      </div>
      
      {/* ═══════════════════════════════════════════════════════════════
          LIFECYCLE BADGE — forming / confirmed / invalidated
          ═══════════════════════════════════════════════════════════════ */}
      {lifecycle?.state && lifecycle.state !== 'forming' && (
        <div className="px-3 py-1.5 border-b border-white/5" data-testid="lifecycle-badge">
          <div className="flex items-center gap-2">
            <span style={{
              fontSize: '10px',
              fontWeight: '800',
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
              padding: '2px 8px',
              borderRadius: '3px',
              background: lifecycle.state === 'confirmed_up' ? 'rgba(34,197,94,0.2)' :
                lifecycle.state === 'confirmed_down' ? 'rgba(239,68,68,0.2)' :
                lifecycle.state === 'invalidated' ? 'rgba(100,116,139,0.2)' :
                'transparent',
              color: lifecycle.state === 'confirmed_up' ? '#22c55e' :
                lifecycle.state === 'confirmed_down' ? '#ef4444' :
                lifecycle.state === 'invalidated' ? '#64748b' :
                '#94a3b8',
            }}>
              {lifecycle.state === 'confirmed_up' ? 'BREAKOUT' :
               lifecycle.state === 'confirmed_down' ? 'BREAKDOWN' :
               lifecycle.state === 'invalidated' ? 'INVALIDATED' :
               lifecycle.state.toUpperCase()}
            </span>
            <span className="text-[10px] text-white/40">
              {lifecycle.label}
            </span>
          </div>
        </div>
      )}
      {lifecycle?.state === 'forming' && (
        <div className="px-3 py-1 border-b border-white/5" data-testid="lifecycle-badge">
          <span style={{
            fontSize: '9px',
            fontWeight: '600',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
            color: '#94a3b8',
          }}>
            {lifecycle.label || 'FORMING'}
          </span>
        </div>
      )}
      
      {/* ═══════════════════════════════════════════════════════════════
          INTERPRETATION — смысл паттернов (1-2 строки)
          ═══════════════════════════════════════════════════════════════ */}
      {interpretation && (interpretation.line1 || interpretation.line2) && (
        <div className="px-3 py-2 border-b border-white/5 bg-black/30">
          {interpretation.line1 && (
            <div className="text-xs text-white/80 leading-relaxed">
              {interpretation.line1}
            </div>
          )}
          {interpretation.line2 && (
            <div className="text-xs text-white/50 mt-1 leading-relaxed">
              {interpretation.line2}
            </div>
          )}
        </div>
      )}
      
      {/* ═══════════════════════════════════════════════════════════════
          WATCH LEVELS — "What to Watch" (breakout / breakdown)
          ═══════════════════════════════════════════════════════════════ */}
      {(() => {
        const wl = interpretation?.watch_levels || props?.watchLevels || [];
        return wl.length > 0 ? (
        <div className="px-3 py-2 border-b border-white/5" data-testid="watch-levels-section">
          <div className="text-[10px] text-white/40 uppercase tracking-wider mb-1.5">
            What to Watch
          </div>
          {wl.map((lvl, i) => (
            <div
              key={i}
              className="flex items-center gap-1.5 py-0.5"
              data-testid={`watch-level-${i}`}
            >
              <span style={{
                color: lvl.type === 'breakout_up' ? '#22c55e' : '#ef4444',
                fontSize: '11px',
                fontWeight: '700',
              }}>
                {lvl.type === 'breakout_up' ? '▲' : '▼'}
              </span>
              <span style={{
                color: lvl.type === 'breakout_up' ? '#22c55e' : '#ef4444',
                fontSize: '11px',
                fontWeight: '600',
                fontFamily: "'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif",
              }}>
                {typeof lvl.price === 'number' ? lvl.price.toLocaleString() : lvl.price}
              </span>
              <span className="text-[10px] text-white/40 ml-0.5">
                — {lvl.label}
              </span>
            </div>
          ))}
        </div>
        ) : null;
      })()}
      
      {/* PATTERNS LIST */}
      <div className="p-2">
        <div className="text-[10px] text-white/40 uppercase tracking-wider mb-1 px-1">
          Patterns
        </div>
        
        {renderStack.map((item, idx) => {
          const isDominant = item.role === 'dominant';
          const isActive = hoveredIndex === null || hoveredIndex === idx;
          const isHovered = hoveredIndex === idx;
          
          // Цвет по типу
          const typeColor = item.type?.includes('top') ? '#ef4444' 
            : item.type?.includes('bottom') ? '#22c55e' 
            : isDominant ? '#fbbf24' : '#00c8ff';
          
          // Confidence (пока фиксированный, потом можно брать из contract)
          const confidence = isDominant ? 42 : (38 - idx * 3);
          
          return (
            <div
              key={idx}
              className="flex items-center gap-2 py-1.5 px-2 rounded cursor-pointer transition-all duration-150 relative group"
              style={{
                opacity: isActive ? 1 : 0.3,
                backgroundColor: isHovered ? 'rgba(255,255,255,0.08)' : 'transparent',
              }}
              onMouseEnter={() => setHoveredIndex && setHoveredIndex(idx)}
              onMouseLeave={() => setHoveredIndex && setHoveredIndex(null)}
              onClick={() => onPatternClick && onPatternClick(idx)}
            >
              {/* Indicator */}
              <div 
                className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${isDominant ? 'ring-2 ring-offset-1 ring-offset-black' : ''}`}
                style={{ 
                  backgroundColor: typeColor,
                  ringColor: typeColor,
                }}
              />
              
              {/* Type name + lifecycle + confidence */}
              <div className="flex-1 flex items-center justify-between gap-1">
                <div className="flex items-center gap-1.5">
                  <span 
                    className="text-sm font-medium"
                    style={{ color: isDominant ? '#ffffff' : '#a0a0a0' }}
                  >
                    {formatType(item.type)}
                  </span>
                  {/* Lifecycle badge inline - ALWAYS show lifecycle state in legend */}
                  {isDominant && lifecycle?.state && (
                    <span style={{
                      fontSize: '9px',
                      fontWeight: '700',
                      textTransform: 'uppercase',
                      padding: '2px 5px',
                      borderRadius: '3px',
                      background: lifecycle.state === 'confirmed_up' ? 'rgba(34,197,94,0.2)' :
                        lifecycle.state === 'confirmed_down' ? 'rgba(239,68,68,0.2)' :
                        lifecycle.state === 'invalidated' ? 'rgba(100,116,139,0.2)' :
                        'rgba(148,163,184,0.15)',
                      color: lifecycle.state === 'confirmed_up' ? '#22c55e' :
                        lifecycle.state === 'confirmed_down' ? '#ef4444' :
                        lifecycle.state === 'invalidated' ? '#64748b' : '#94a3b8',
                    }}>
                      {lifecycle.state === 'confirmed_up' ? 'BREAKOUT' :
                       lifecycle.state === 'confirmed_down' ? 'BREAKDOWN' :
                       lifecycle.state === 'invalidated' ? 'INVALIDATED' :
                       'FORMING'}
                    </span>
                  )}
                </div>
                
                <span 
                  className="text-xs font-mono"
                  style={{ color: isDominant ? typeColor : '#666' }}
                >
                  {confidence}%
                </span>
              </div>
              
              {/* Role badge */}
              {isDominant && (
                <span 
                  className="text-[9px] px-1.5 py-0.5 rounded uppercase font-bold"
                  style={{ backgroundColor: `${typeColor}30`, color: typeColor }}
                >
                  main
                </span>
              )}
              
              {/* ═══════════════════════════════════════════════════════════════
                  TOOLTIP — появляется при hover
                  ═══════════════════════════════════════════════════════════════ */}
              {isHovered && (
                <div className="absolute left-full ml-2 top-0 bg-black/95 border border-white/20 rounded-lg p-3 min-w-[150px] z-50 shadow-xl">
                  <div className="text-sm font-bold text-white mb-1">
                    {formatType(item.type)}
                  </div>
                  <div className="text-xs text-white/60 space-y-1">
                    <div className="flex justify-between">
                      <span>Type:</span>
                      <span className="text-white/80">
                        {item.type?.includes('top') || item.type?.includes('head') ? 'Reversal ↓' :
                         item.type?.includes('bottom') || item.type?.includes('inverse') ? 'Reversal ↑' :
                         'Continuation'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Confidence:</span>
                      <span style={{ color: typeColor }}>{confidence}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Role:</span>
                      <span className={isDominant ? 'text-yellow-400' : 'text-white/50'}>
                        {isDominant ? 'DOMINANT' : 'Alternative'}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════
// 🟦 RANGE RENDERING — CLEAN MINIMAL UI
// ═══════════════════════════════════════════════════════════════
// PRINCIPLE: 1 screen = 1 idea
// Show ONLY: Range box + Support/Resistance + 2 Scenarios
// ═══════════════════════════════════════════════════════════════
function renderRange(range, toX, toY, visibleRange, scenarios, probability) {
  const elements = [];
  
  const top = range.top;
  const bottom = range.bottom;
  const startTime = range.start_time || range.left_boundary_time || range.left_time;
  
  let endTime = range.forward_time || range.end_time || range.right_time;
  if (visibleRange && endTime) {
    const visibleEnd = visibleRange.to;
    const extendedEnd = visibleEnd + (visibleEnd - visibleRange.from) * 0.5;
    if (endTime > extendedEnd) {
      endTime = extendedEnd;
    }
  }
  
  const left = toX(startTime);
  let right = toX(endTime);
  if (!right && visibleRange) {
    right = toX(visibleRange.to);
    if (!right) right = 1400;
  }
  
  const yTop = toY(top);
  const yBottom = toY(bottom);
  
  if (!yTop || !yBottom) return [];
  
  const effectiveLeft = Math.max(left || 0, 0);
  const effectiveRight = Math.max(right || 1400, effectiveLeft + 100);
  const width = Math.max(effectiveRight - effectiveLeft, 100);
  const rangeHeight = Math.abs(yBottom - yTop);
  const yStart = Math.min(yTop, yBottom);
  
  // Scenarios
  const breakUp = scenarios?.break_up;
  const breakDown = scenarios?.break_down;
  
  // ═══════════════════════════════════════════════════════════════
  // 1. RANGE BOX — subtle fill, clean
  // ═══════════════════════════════════════════════════════════════
  elements.push(
    <rect
      key="range-fill"
      x={effectiveLeft}
      y={yStart}
      width={width}
      height={rangeHeight}
      fill="rgba(100, 116, 139, 0.06)"
      stroke="none"
    />
  );
  
  // ═══════════════════════════════════════════════════════════════
  // 2. RESISTANCE LINE — clean solid line
  // ═══════════════════════════════════════════════════════════════
  elements.push(
    <line
      key="resistance"
      x1={effectiveLeft}
      y1={yTop}
      x2={effectiveRight}
      y2={yTop}
      stroke="#ef4444"
      strokeWidth={2}
    />
  );
  
  // Resistance label
  elements.push(
    <text
      key="resistance-label"
      x={effectiveRight - 80}
      y={yTop - 6}
      fill="#ef4444"
      fontSize="11"
      fontWeight="600"
    >
      R {top?.toFixed(0)}
    </text>
  );
  
  // ═══════════════════════════════════════════════════════════════
  // 3. SUPPORT LINE — clean solid line
  // ═══════════════════════════════════════════════════════════════
  elements.push(
    <line
      key="support"
      x1={effectiveLeft}
      y1={yBottom}
      x2={effectiveRight}
      y2={yBottom}
      stroke="#22c55e"
      strokeWidth={2}
    />
  );
  
  // Support label
  elements.push(
    <text
      key="support-label"
      x={effectiveRight - 80}
      y={yBottom + 14}
      fill="#22c55e"
      fontSize="11"
      fontWeight="600"
    >
      S {bottom?.toFixed(0)}
    </text>
  );
  
  // ═══════════════════════════════════════════════════════════════
  // 4. SCENARIOS — simple arrows at edge showing direction
  // ═══════════════════════════════════════════════════════════════
  const scenarioX = effectiveRight - 20;
  
  // Break UP scenario arrow
  if (breakUp?.target) {
    const arrowY = yTop - 25;
    elements.push(
      <g key="scenario-up">
        {/* Arrow pointing up */}
        <polygon
          points={`${scenarioX},${arrowY} ${scenarioX-6},${arrowY+10} ${scenarioX+6},${arrowY+10}`}
          fill="#22c55e"
        />
        {/* Target price */}
        <text
          x={scenarioX + 12}
          y={arrowY + 8}
          fill="#22c55e"
          fontSize="10"
          fontWeight="600"
        >
          → {breakUp.target?.toFixed(0)}
        </text>
      </g>
    );
  }
  
  // Break DOWN scenario arrow
  if (breakDown?.target) {
    const arrowY = yBottom + 25;
    elements.push(
      <g key="scenario-down">
        {/* Arrow pointing down */}
        <polygon
          points={`${scenarioX},${arrowY} ${scenarioX-6},${arrowY-10} ${scenarioX+6},${arrowY-10}`}
          fill="#ef4444"
        />
        {/* Target price */}
        <text
          x={scenarioX + 12}
          y={arrowY - 2}
          fill="#ef4444"
          fontSize="10"
          fontWeight="600"
        >
          → {breakDown.target?.toFixed(0)}
        </text>
      </g>
    );
  }
  
  return elements;
}

// ═══════════════════════════════════════════════════════════════
// 🔺 DOUBLE TOP/BOTTOM RENDERING
// ═══════════════════════════════════════════════════════════════
function renderDoublePattern(patternType, renderContract, meta, toX, toY) {
  const isTop = patternType === 'double_top';
  const anchors = renderContract?.anchors || {};
  
  let p1, valley, p2;
  let p2IsProjected = false;
  
  if (anchors.p1 && anchors.p2 && anchors.valley) {
    p1 = anchors.p1;
    p2 = anchors.p2;
    valley = anchors.valley;
  } else if (anchors.p1 && anchors.valley) {
    p1 = anchors.p1;
    valley = anchors.valley;
    const timeDiff = valley.time - p1.time;
    p2 = {
      time: valley.time + timeDiff,
      price: p1.price
    };
    p2IsProjected = true;
  } else {
    return [];
  }
  
  if (!p1 || !valley) return [];
  
  if (!p2) {
    const timeDiff = valley.time - p1.time;
    p2 = {
      time: valley.time + timeDiff,
      price: p1.price
    };
    p2IsProjected = true;
  }
  
  const peakPrice = (p1.price + p2.price) / 2;
  const necklinePrice = valley.price;
  const height = Math.abs(peakPrice - necklinePrice);
  const targetPrice = isTop ? necklinePrice - height : necklinePrice + height;
  
  const x1 = toX(p1.time);
  const y1 = toY(peakPrice);
  const xV = toX(valley.time);
  const yV = toY(necklinePrice);
  const x2 = toX(p2.time);
  const y2 = toY(peakPrice);
  const yTarget = toY(targetPrice);
  
  if (!x1 || !y1 || !xV || !yV || !x2 || !y2) {
    return [];
  }
  
  const elements = [];
  const mainColor = '#000000';
  const projectedColor = '#666666';
  
  // M-shape
  elements.push(
    <line
      key="left-side"
      x1={x1}
      y1={y1}
      x2={xV}
      y2={yV}
      stroke={mainColor}
      strokeWidth={2}
      strokeLinecap="round"
    />
  );
  
  elements.push(
    <line
      key="right-side"
      x1={xV}
      y1={yV}
      x2={x2}
      y2={y2}
      stroke={p2IsProjected ? projectedColor : mainColor}
      strokeWidth={2}
      strokeLinecap="round"
      strokeDasharray={p2IsProjected ? "4 3" : "none"}
    />
  );
  
  // Neckline
  elements.push(
    <line
      key="neckline"
      x1={x1}
      y1={yV}
      x2={x2 + 50}
      y2={yV}
      stroke="cyan"
      strokeWidth={1}
      strokeDasharray="4 2"
    />
  );
  
  // Target arrow
  if (yTarget) {
    const arrowStartX = x2 + 10;
    const arrowStartY = yV;
    const arrowEndX = x2 + 50;
    const arrowEndY = yTarget;
    
    elements.push(
      <line
        key="prediction"
        x1={arrowStartX}
        y1={arrowStartY}
        x2={arrowEndX}
        y2={arrowEndY}
        stroke={mainColor}
        strokeWidth={2}
      />
    );
    
    // Arrow head
    const angle = Math.atan2(arrowEndY - arrowStartY, arrowEndX - arrowStartX);
    const headLen = 8;
    const h1X = arrowEndX - headLen * Math.cos(angle - Math.PI / 6);
    const h1Y = arrowEndY - headLen * Math.sin(angle - Math.PI / 6);
    const h2X = arrowEndX - headLen * Math.cos(angle + Math.PI / 6);
    const h2Y = arrowEndY - headLen * Math.sin(angle + Math.PI / 6);
    
    elements.push(
      <polygon
        key="arrow-head"
        points={`${arrowEndX},${arrowEndY} ${h1X},${h1Y} ${h2X},${h2Y}`}
        fill={mainColor}
      />
    );
    
    elements.push(
      <text
        key="target"
        x={arrowEndX + 5}
        y={arrowEndY + 4}
        fill={mainColor}
        fontSize="11"
        fontWeight="bold"
      >
        {targetPrice.toFixed(0)}
      </text>
    );
  }
  
  // Points
  elements.push(<circle key="p1" cx={x1} cy={y1} r={4} fill={mainColor} />);
  elements.push(
    <text key="p1-label" x={x1} y={y1 - 8} fill={mainColor} fontSize="10" fontWeight="bold" textAnchor="middle">P1</text>
  );
  
  elements.push(
    <circle 
      key="p2" 
      cx={x2} 
      cy={y2} 
      r={4} 
      fill={p2IsProjected ? "none" : mainColor}
      stroke={mainColor}
      strokeWidth={p2IsProjected ? 2 : 0}
    />
  );
  elements.push(
    <text key="p2-label" x={x2} y={y2 - 8} fill={projectedColor} fontSize="10" fontWeight="bold" textAnchor="middle">
      P2{p2IsProjected ? "?" : ""}
    </text>
  );
  
  return elements;
}

// ═══════════════════════════════════════════════════════════════
// 🔺 TRIANGLE/WEDGE RENDERING
// ═══════════════════════════════════════════════════════════════
function renderTriangle(meta, toX, toY) {
  const boundaries = meta.boundaries || {};
  const upper = boundaries.upper;
  const lower = boundaries.lower;
  
  if (!upper || !lower) return [];
  
  const x1u = toX(upper.x1);
  const y1u = toY(upper.y1);
  const x2u = toX(upper.x2);
  const y2u = toY(upper.y2);
  const x1l = toX(lower.x1);
  const y1l = toY(lower.y1);
  const x2l = toX(lower.x2);
  const y2l = toY(lower.y2);
  
  if (!x1u || !y1u || !x2u || !y2u || !x1l || !y1l || !x2l || !y2l) {
    return [];
  }
  
  return [
    <line key="upper" x1={x1u} y1={y1u} x2={x2u} y2={y2u} stroke="#000000" strokeWidth={2} />,
    <line key="lower" x1={x1l} y1={y1l} x2={x2l} y2={y2l} stroke="#000000" strokeWidth={2} />
  ];
}

// ═══════════════════════════════════════════════════════════════
// 🆕 UNIFIED RENDER CONTRACT — NEW SYSTEM
// ═══════════════════════════════════════════════════════════════
// Handles render_contract from pattern_families/pattern_render_builder.py
// ═══════════════════════════════════════════════════════════════
function renderUnifiedContract(contract, toX, toY, visibleRange) {
  if (!contract || !contract.type) return [];
  
  const renderMode = contract.render_mode;
  
  switch (renderMode) {
    case 'box':
      return renderUnifiedBox(contract, toX, toY, visibleRange);
    case 'polyline':
      return renderUnifiedPolyline(contract, toX, toY);
    case 'two_lines':
      return renderUnifiedTwoLines(contract, toX, toY);
    case 'hs':
      return renderUnifiedHS(contract, toX, toY);
    default:
      console.log('[PatternSVGOverlay] Unknown render_mode:', renderMode);
      return [];
  }
}

// BOX render (range, rectangle)
function renderUnifiedBox(contract, toX, toY, visibleRange) {
  const elements = [];
  
  const box = contract.box;
  const window = contract.window;
  
  if (!box || !box.top || !box.bottom) return [];
  
  let x1 = toX(window?.start);
  let x2 = toX(window?.end);
  
  // Fallback to visible range
  if (!x1 && visibleRange) x1 = toX(visibleRange.from) || 50;
  if (!x2 && visibleRange) x2 = toX(visibleRange.to) || 1400;
  
  const yTop = toY(box.top);
  const yBottom = toY(box.bottom);
  
  if (!yTop || !yBottom) return [];
  
  const left = Math.min(x1, x2);
  const width = Math.abs(x2 - x1);
  const top = Math.min(yTop, yBottom);
  const height = Math.abs(yBottom - yTop);
  
  // Box fill
  elements.push(
    <rect
      key="box-fill"
      x={left}
      y={top}
      width={width}
      height={height}
      fill="rgba(56, 189, 248, 0.08)"
      stroke="none"
    />
  );
  
  // Resistance line
  elements.push(
    <line
      key="resistance"
      x1={left}
      y1={yTop}
      x2={left + width}
      y2={yTop}
      stroke="#ef4444"
      strokeWidth={2}
    />
  );
  
  // Support line
  elements.push(
    <line
      key="support"
      x1={left}
      y1={yBottom}
      x2={left + width}
      y2={yBottom}
      stroke="#22c55e"
      strokeWidth={2}
    />
  );
  
  // Labels
  contract.labels?.forEach((label, i) => {
    const y = toY(label.price);
    if (y == null) return;
    
    const color = label.kind === 'resistance' ? '#ef4444' : '#22c55e';
    elements.push(
      <text
        key={`label-${i}`}
        x={left + width + 6}
        y={y + 4}
        fill={color}
        fontSize="11"
        fontWeight="600"
      >
        {label.text}
      </text>
    );
  });
  
  return elements;
}

// POLYLINE render (double top/bottom, triple top/bottom)
function renderUnifiedPolyline(contract, toX, toY) {
  const elements = [];
  const polyline = contract.polyline || [];
  
  if (polyline.length < 2) return [];
  
  // Convert points to coordinates
  const coords = polyline.map(pt => ({
    x: toX(pt.time),
    y: toY(pt.price),
    label: pt.label,
    price: pt.price,
  })).filter(pt => pt.x != null && pt.y != null);
  
  if (coords.length < 2) return [];
  
  // Draw polyline
  const pathData = coords.map((pt, i) => `${i === 0 ? 'M' : 'L'} ${pt.x},${pt.y}`).join(' ');
  
  elements.push(
    <path
      key="polyline"
      d={pathData}
      fill="none"
      stroke="#ef4444"
      strokeWidth={2.5}
      strokeLinejoin="round"
      strokeLinecap="round"
    />
  );
  
  // Draw points and labels
  coords.forEach((pt, i) => {
    elements.push(
      <circle
        key={`point-${i}`}
        cx={pt.x}
        cy={pt.y}
        r={4}
        fill="#ef4444"
      />
    );
    
    if (pt.label) {
      elements.push(
        <text
          key={`label-${i}`}
          x={pt.x}
          y={pt.y - 10}
          fill="#fca5a5"
          fontSize="10"
          fontWeight="bold"
          textAnchor="middle"
        >
          {pt.label}
        </text>
      );
    }
  });
  
  // Draw levels (neckline, target)
  contract.levels?.forEach((level, i) => {
    if (!level || level.price == null) return;
    
    const y = toY(level.price);
    if (y == null) return;
    
    const xStart = Math.min(...coords.map(c => c.x));
    const xEnd = Math.max(...coords.map(c => c.x)) + 50;
    
    const color = level.kind === 'neckline' ? '#38bdf8' : '#a855f7';
    
    elements.push(
      <line
        key={`level-${i}`}
        x1={xStart}
        y1={y}
        x2={xEnd}
        y2={y}
        stroke={color}
        strokeWidth={2}
        strokeDasharray="6 4"
      />
    );
    
    elements.push(
      <text
        key={`level-label-${i}`}
        x={xEnd + 5}
        y={y + 4}
        fill={color}
        fontSize="10"
        fontWeight="600"
      >
        {level.kind} {level.price?.toFixed(0)}
      </text>
    );
  });
  
  return elements;
}

// TWO_LINES render (triangle, wedge, channel)
function renderUnifiedTwoLines(contract, toX, toY) {
  const elements = [];
  const lines = contract.lines || [];
  
  if (lines.length < 2) return [];
  
  // Draw lines
  lines.forEach((line, i) => {
    const from = line.from;
    const to = line.to;
    
    const x1 = toX(from?.time);
    const y1 = toY(from?.price);
    const x2 = toX(to?.time);
    const y2 = toY(to?.price);
    
    if (x1 == null || y1 == null || x2 == null || y2 == null) return;
    
    const color = line.kind === 'upper' ? '#f59e0b' : '#f59e0b';
    
    elements.push(
      <line
        key={`line-${i}`}
        x1={x1}
        y1={y1}
        x2={x2}
        y2={y2}
        stroke={color}
        strokeWidth={2.5}
        strokeLinecap="round"
      />
    );
  });
  
  // Draw pivot points
  contract.points?.forEach((pt, i) => {
    const x = toX(pt.time);
    const y = toY(pt.price);
    
    if (x == null || y == null) return;
    
    elements.push(
      <circle
        key={`point-${i}`}
        cx={x}
        cy={y}
        r={3}
        fill="#fbbf24"
      />
    );
  });
  
  return elements;
}

// H&S render (head & shoulders, inverse H&S)
function renderUnifiedHS(contract, toX, toY) {
  const elements = [];
  const polyline = contract.polyline || [];
  
  if (polyline.length < 3) return [];
  
  // Convert to coordinates
  const coords = polyline.map(pt => ({
    x: toX(pt.time),
    y: toY(pt.price),
    label: pt.label,
  })).filter(pt => pt.x != null && pt.y != null);
  
  if (coords.length < 3) return [];
  
  // Draw H&S shape
  const pathData = coords.map((pt, i) => `${i === 0 ? 'M' : 'L'} ${pt.x},${pt.y}`).join(' ');
  
  elements.push(
    <path
      key="hs-shape"
      d={pathData}
      fill="none"
      stroke="#22c55e"
      strokeWidth={2.5}
      strokeLinejoin="round"
      strokeLinecap="round"
    />
  );
  
  // Draw labels (LS, H, RS)
  coords.forEach((pt, i) => {
    elements.push(
      <circle
        key={`hs-point-${i}`}
        cx={pt.x}
        cy={pt.y}
        r={4}
        fill="#22c55e"
      />
    );
    
    if (pt.label) {
      elements.push(
        <text
          key={`hs-label-${i}`}
          x={pt.x}
          y={pt.y - 10}
          fill="#86efac"
          fontSize="10"
          fontWeight="bold"
          textAnchor="middle"
        >
          {pt.label}
        </text>
      );
    }
  });
  
  // Draw neckline
  contract.lines?.forEach((line, i) => {
    const from = line.from;
    const to = line.to;
    
    const x1 = toX(from?.time);
    const y1 = toY(from?.price);
    const x2 = toX(to?.time);
    const y2 = toY(to?.price);
    
    if (x1 == null || y1 == null || x2 == null || y2 == null) return;
    
    elements.push(
      <line
        key={`neckline-${i}`}
        x1={x1}
        y1={y1}
        x2={x2}
        y2={y2}
        stroke="#38bdf8"
        strokeWidth={2}
        strokeDasharray="6 4"
      />
    );
  });
  
  return elements;
}

// ═══════════════════════════════════════════════════════════════
// TRIGGER LINES — Breakout / Breakdown / Invalidation
// ═══════════════════════════════════════════════════════════════
function renderTriggerLines(triggers, toX, toY, visibleRange) {
  if (!triggers) return [];
  
  const elements = [];
  const xStart = toX(visibleRange?.from) || 0;
  const xEnd = toX(visibleRange?.to) || 1500;
  const lineWidth = Math.max(xEnd - xStart, 200);
  
  // Breakout UP line
  if (typeof triggers.up === 'number') {
    const y = toY(triggers.up);
    if (y != null) {
      elements.push(
        <line
          key="trigger-up"
          x1={xStart}
          y1={y}
          x2={xStart + lineWidth}
          y2={y}
          stroke="#22c55e"
          strokeWidth={1.5}
          strokeDasharray="8 4"
          opacity={0.8}
        />
      );
      elements.push(
        <text
          key="trigger-up-label"
          x={xStart + lineWidth - 4}
          y={y - 6}
          fill="#22c55e"
          fontSize="10"
          fontWeight="600"
          textAnchor="end"
        >
          Breakout {triggers.up.toLocaleString()}
        </text>
      );
    }
  }
  
  // Breakdown DOWN line
  if (typeof triggers.down === 'number') {
    const y = toY(triggers.down);
    if (y != null) {
      elements.push(
        <line
          key="trigger-down"
          x1={xStart}
          y1={y}
          x2={xStart + lineWidth}
          y2={y}
          stroke="#ef4444"
          strokeWidth={1.5}
          strokeDasharray="8 4"
          opacity={0.8}
        />
      );
      elements.push(
        <text
          key="trigger-down-label"
          x={xStart + lineWidth - 4}
          y={y + 14}
          fill="#ef4444"
          fontSize="10"
          fontWeight="600"
          textAnchor="end"
        >
          Breakdown {triggers.down.toLocaleString()}
        </text>
      );
    }
  }
  
  // Invalidation line
  if (typeof triggers.invalidation === 'number') {
    const y = toY(triggers.invalidation);
    if (y != null) {
      elements.push(
        <line
          key="trigger-invalidation"
          x1={xStart}
          y1={y}
          x2={xStart + lineWidth}
          y2={y}
          stroke="#f97316"
          strokeWidth={1}
          strokeDasharray="4 4"
          opacity={0.6}
        />
      );
      elements.push(
        <text
          key="trigger-invalidation-label"
          x={xStart + lineWidth - 4}
          y={y + 14}
          fill="#f97316"
          fontSize="9"
          fontWeight="600"
          textAnchor="end"
        >
          Invalidation {triggers.invalidation.toLocaleString()}
        </text>
      );
    }
  }
  
  return elements;
}

// ═══════════════════════════════════════════════════════════════
// STRUCTURE MARKERS — Minimal swing labels (for structure_only mode)
// ═══════════════════════════════════════════════════════════════
function renderStructureMarkers(data, toX, toY) {
  const elements = [];
  
  // Get structure from various sources
  const swings = data?.swings || data?.ta_layers?.swings || {};
  const recentHighs = swings.recent_highs || [];
  const recentLows = swings.recent_lows || [];
  
  // Render recent highs (limit to 3)
  recentHighs.slice(-3).forEach((swing, i) => {
    const x = toX(swing.timestamp);
    const y = toY(swing.price);
    
    if (x == null || y == null) return;
    
    elements.push(
      <circle
        key={`high-${i}`}
        cx={x}
        cy={y}
        r={3}
        fill="#ef4444"
        opacity={0.7}
      />
    );
    
    elements.push(
      <text
        key={`high-label-${i}`}
        x={x}
        y={y - 8}
        fill="#fca5a5"
        fontSize="9"
        fontWeight="600"
        textAnchor="middle"
      >
        {swing.type || 'H'}
      </text>
    );
  });
  
  // Render recent lows (limit to 3)
  recentLows.slice(-3).forEach((swing, i) => {
    const x = toX(swing.timestamp);
    const y = toY(swing.price);
    
    if (x == null || y == null) return;
    
    elements.push(
      <circle
        key={`low-${i}`}
        cx={x}
        cy={y}
        r={3}
        fill="#22c55e"
        opacity={0.7}
      />
    );
    
    elements.push(
      <text
        key={`low-label-${i}`}
        x={x}
        y={y + 14}
        fill="#86efac"
        fontSize="9"
        fontWeight="600"
        textAnchor="middle"
      >
        {swing.type || 'L'}
      </text>
    );
  });
  
  return elements;
}

// ═══════════════════════════════════════════════════════════════
// HISTORY OVERLAY — Ghost patterns from history
// ═══════════════════════════════════════════════════════════════
// Shows past confirmed/invalidated patterns as faint ghosts
// Rules:
// - Maximum 2 overlays
// - Dashed lines, low opacity
// - No labels, no hover, no click

function renderHistoryOverlay(historyItems, chart, priceSeries, timeScale, visibleRange) {
  const elements = [];
  
  if (!historyItems || historyItems.length === 0) return elements;
  
  const normalizeTime = (t) => {
    if (!t) return null;
    return t > 9999999999 ? Math.floor(t / 1000) : t;
  };
  
  const toX = (time) => {
    const normalized = normalizeTime(time);
    if (!normalized) return null;
    const x = timeScale.timeToCoordinate(normalized);
    return Number.isFinite(x) ? x : null;
  };
  
  const toY = (price) => {
    if (price === null || price === undefined) return null;
    try {
      const y = priceSeries.priceToCoordinate(price);
      return Number.isFinite(y) ? y : null;
    } catch {
      return null;
    }
  };
  
  // Ghost style config
  const ghostColor = '#64748b'; // Slate gray
  const ghostStrokeDash = '6 4';
  
  historyItems.forEach((item, idx) => {
    const { contract, opacity: itemOpacity, lifecycle } = item;
    if (!contract) return;
    
    const opacity = itemOpacity || (lifecycle === 'invalidated' ? 0.06 : 0.12);
    
    // Render range (rectangle)
    if (contract.range || (contract.start_time && contract.end_time && contract.top && contract.bottom)) {
      const range = contract.range || contract;
      const x1 = toX(range.start_time);
      const x2 = toX(range.end_time);
      const yTop = toY(range.top);
      const yBottom = toY(range.bottom);
      
      if (x1 !== null && x2 !== null && yTop !== null && yBottom !== null) {
        // Ghost box (no fill)
        elements.push(
          <rect
            key={`ghost-rect-${idx}`}
            x={Math.min(x1, x2)}
            y={Math.min(yTop, yBottom)}
            width={Math.abs(x2 - x1)}
            height={Math.abs(yBottom - yTop)}
            fill="transparent"
            stroke={ghostColor}
            strokeWidth={1}
            strokeDasharray={ghostStrokeDash}
            opacity={opacity}
          />
        );
        
        // Top line (resistance)
        elements.push(
          <line
            key={`ghost-top-${idx}`}
            x1={x1}
            x2={x2}
            y1={yTop}
            y2={yTop}
            stroke={ghostColor}
            strokeWidth={1}
            strokeDasharray={ghostStrokeDash}
            opacity={opacity}
          />
        );
        
        // Bottom line (support)
        elements.push(
          <line
            key={`ghost-bottom-${idx}`}
            x1={x1}
            x2={x2}
            y1={yBottom}
            y2={yBottom}
            stroke={ghostColor}
            strokeWidth={1}
            strokeDasharray={ghostStrokeDash}
            opacity={opacity}
          />
        );
      }
    }
    
    // Render polyline (for double top/bottom, etc.)
    if (contract.polyline?.points?.length > 0) {
      const pathData = contract.polyline.points
        .map((p, i) => {
          const x = toX(p.time || p.timestamp);
          const y = toY(p.price || p.value);
          if (x === null || y === null) return null;
          return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
        })
        .filter(Boolean)
        .join(' ');
      
      if (pathData) {
        elements.push(
          <path
            key={`ghost-polyline-${idx}`}
            d={pathData}
            stroke={ghostColor}
            strokeWidth={1}
            strokeDasharray={ghostStrokeDash}
            fill="none"
            opacity={opacity}
          />
        );
      }
    }
    
    // Render trendlines (for triangles, wedges)
    if (contract.trendlines) {
      contract.trendlines.forEach((tl, tlIdx) => {
        const x1 = toX(tl.start_time);
        const y1 = toY(tl.start_price);
        const x2 = toX(tl.end_time);
        const y2 = toY(tl.end_price);
        
        if (x1 !== null && y1 !== null && x2 !== null && y2 !== null) {
          elements.push(
            <line
              key={`ghost-tl-${idx}-${tlIdx}`}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke={ghostColor}
              strokeWidth={1}
              strokeDasharray={ghostStrokeDash}
              opacity={opacity}
            />
          );
        }
      });
    }
  });
  
  return elements;
}

// ═══════════════════════════════════════════════════════════════
// MTF CONTEXT — Higher timeframe range & levels
// ═══════════════════════════════════════════════════════════════
// Shows 1D context on 4H chart:
// - Range box (light blue, very transparent)
// - Key levels (dashed lines)
// NO patterns, NO polylines from HTF

function renderMTFContext(ctx, chart, priceSeries, timeScale, visibleRange) {
  const elements = [];
  
  if (!ctx) return elements;
  
  const normalizeTime = (t) => {
    if (!t) return null;
    return t > 9999999999 ? Math.floor(t / 1000) : t;
  };
  
  const toX = (time) => {
    const normalized = normalizeTime(time);
    if (!normalized) return null;
    const x = timeScale.timeToCoordinate(normalized);
    return Number.isFinite(x) ? x : null;
  };
  
  const toY = (price) => {
    if (price === null || price === undefined) return null;
    try {
      const y = priceSeries.priceToCoordinate(price);
      return Number.isFinite(y) ? y : null;
    } catch {
      return null;
    }
  };
  
  // MTF colors
  const mtfRangeColor = 'rgba(147, 197, 253, 0.06)'; // Light blue, very transparent
  const mtfRangeStroke = 'rgba(147, 197, 253, 0.2)';
  const mtfLevelColor = '#94a3b8';
  
  // 1. Render MTF Range (box)
  if (ctx.range && ctx.range.top && ctx.range.bottom) {
    const range = ctx.range;
    const x1 = toX(range.start_time);
    const x2 = toX(range.end_time);
    const yTop = toY(range.top);
    const yBottom = toY(range.bottom);
    
    // If no x coords, extend to full width
    const chartWidth = chart.timeScale().width();
    const finalX1 = x1 !== null ? x1 : 0;
    const finalX2 = x2 !== null ? x2 : chartWidth;
    
    if (yTop !== null && yBottom !== null) {
      // Range box
      elements.push(
        <rect
          key="mtf-range-box"
          x={finalX1}
          y={Math.min(yTop, yBottom)}
          width={Math.abs(finalX2 - finalX1)}
          height={Math.abs(yBottom - yTop)}
          fill={mtfRangeColor}
          stroke={mtfRangeStroke}
          strokeWidth={1}
          strokeDasharray="4 4"
        />
      );
      
      // Top line (resistance)
      elements.push(
        <line
          key="mtf-range-top"
          x1={0}
          x2={chartWidth}
          y1={yTop}
          y2={yTop}
          stroke={mtfRangeStroke}
          strokeWidth={1}
          strokeDasharray="6 4"
        />
      );
      
      // Bottom line (support)
      elements.push(
        <line
          key="mtf-range-bottom"
          x1={0}
          x2={chartWidth}
          y1={yBottom}
          y2={yBottom}
          stroke={mtfRangeStroke}
          strokeWidth={1}
          strokeDasharray="6 4"
        />
      );
    }
  }
  
  // 2. Render MTF Levels
  if (ctx.levels && ctx.levels.length > 0) {
    const chartWidth = chart.timeScale().width();
    
    ctx.levels.forEach((lvl, idx) => {
      const y = toY(lvl.price);
      if (y === null) return;
      
      elements.push(
        <line
          key={`mtf-level-${idx}`}
          x1={0}
          x2={chartWidth}
          y1={y}
          y2={y}
          stroke={mtfLevelColor}
          strokeWidth={1}
          strokeDasharray="2 4"
          opacity={0.4}
        />
      );
    });
  }
  
  return elements;
}

// ═══════════════════════════════════════════════════════════════
// RENDER STACK — Multi-pattern visualization with HOVER
// ═══════════════════════════════════════════════════════════════
// Shows 1 dominant + 2 secondary patterns
// Hover: подсвечивает активный, тушит остальные
// Иерархия: MAIN=1.0, ALT=0.25

const formatPatternType = (type) => {
  if (!type) return 'Pattern';
  return type.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
};

function renderStackElements(stack, chart, priceSeries, timeScale, visibleRange, hoveredIndex, setHoveredIndex, selectedIndex, onPatternClick, lifecycle) {
  const elements = [];
  
  console.log('[renderStack] Processing', stack.length, 'items:', stack.map(s => `${s.role}:${s.type}`).join(', '));
  
  const normalizeTime = (t) => {
    if (!t) return null;
    return t > 9999999999 ? Math.floor(t / 1000) : t;
  };
  
  const toX = (time) => {
    const normalized = normalizeTime(time);
    if (!normalized) return null;
    const x = timeScale.timeToCoordinate(normalized);
    return Number.isFinite(x) ? x : null;
  };
  
  const toY = (price) => {
    if (price === null || price === undefined) return null;
    try {
      const y = priceSeries.priceToCoordinate(price);
      return Number.isFinite(y) ? y : null;
    } catch {
      return null;
    }
  };
  
  // ═══════════════════════════════════════════════════════════════
  // ФИКС #5: Правильный порядок — secondary сначала, dominant поверх
  // ═══════════════════════════════════════════════════════════════
  const sortedStack = [...stack].sort((a, b) => {
    if (a.role === 'secondary' && b.role === 'dominant') return -1;
    if (a.role === 'dominant' && b.role === 'secondary') return 1;
    return 0;
  });
  
  sortedStack.forEach((item, idx) => {
    const { role, contract, type } = item;
    if (!contract) return;
    
    const isSecondary = role === 'secondary';
    
    // ═══════════════════════════════════════════════════════════════
    // ИЕРАРХИЯ: MAIN=1.0, ALT=0.25 (в дефолте)
    // При hover: активный=1.0, остальные=0.1
    // При click (selectedIndex): выбранный=1.0, остальные=0.1
    // Lifecycle: invalidated → 0.08, confirmed → 1.0 (glow)
    // ═══════════════════════════════════════════════════════════════
    const hasSelection = selectedIndex !== null && selectedIndex !== undefined;
    const isSelected = hasSelection && selectedIndex === idx;
    const isActive = hasSelection
      ? isSelected
      : (hoveredIndex === null || hoveredIndex === idx);
    
    // Lifecycle affects dominant pattern opacity
    const lcState = (idx === 0 && lifecycle?.state) || null;
    const isInvalidated = lcState === 'invalidated';
    const isConfirmed = lcState === 'confirmed_up' || lcState === 'confirmed_down';
    
    const baseOpacity = isInvalidated ? 0.08 : (isSecondary ? 0.25 : 1.0);
    const strokeOpacity = hasSelection
      ? (isSelected ? 1.0 : 0.1)
      : (hoveredIndex === null
        ? baseOpacity
        : (isActive ? 1.0 : 0.1));
    const lineWidth = isActive ? (isSecondary ? 2 : (isConfirmed ? 4 : 3.5)) : 1;
    
    // ═══════════════════════════════════════════════════════════════
    // Цвета: MAIN=желтый/красный/зелёный, ALT=голубой
    // ═══════════════════════════════════════════════════════════════
    const mainColor = type?.includes('top') ? '#ef4444' : 
                      type?.includes('bottom') ? '#22c55e' : '#fbbf24';
    const secondaryColor = '#00c8ff';
    const patternColor = isSecondary ? secondaryColor : mainColor;
    const topColor = type?.includes('top') ? '#ef4444' : (isSecondary ? secondaryColor : '#ef4444');
    const bottomColor = type?.includes('bottom') ? '#22c55e' : (isSecondary ? secondaryColor : '#22c55e');
    
    // Label для паттерна
    const labelText = isSecondary ? `ALT: ${formatPatternType(type)}` : `MAIN: ${formatPatternType(type)}`;
    
    // Hover handlers
    const handleMouseEnter = () => setHoveredIndex && setHoveredIndex(idx);
    const handleMouseLeave = () => setHoveredIndex && setHoveredIndex(null);
    // Click handler — select pattern for InsightPanel
    const handleClick = (e) => {
      e.stopPropagation();
      onPatternClick && onPatternClick(idx);
    };
    
    // Render based on contract type
    if (contract.type === 'range' || contract.render_mode === 'box') {
      const box = contract.box;
      if (!box) return;
      
      const startX = toX(contract.window?.start);
      const endX = toX(contract.window?.end);
      const topY = toY(box.top);
      const bottomY = toY(box.bottom);
      
      if (startX !== null && endX !== null && topY !== null && bottomY !== null) {
        // ═══════════════════════════════════════════════════════════════
        // HOVER WRAPPER с HITBOX для box/range
        // ═══════════════════════════════════════════════════════════════
        elements.push(
          <g 
            key={`stack-box-group-${idx}`}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
            onClick={handleClick}
            style={{ cursor: 'pointer' }}
          >
            {/* HITBOX — невидимая большая зона для hover */}
            <rect
              x={Math.min(startX, endX)}
              y={Math.min(topY, bottomY)}
              width={Math.abs(endX - startX)}
              height={Math.abs(bottomY - topY)}
              fill="transparent"
              stroke="transparent"
              strokeWidth={15}
            />
            
            {/* Box fill (только для dominant, очень прозрачный) */}
            {!isSecondary && (
              <rect
                x={Math.min(startX, endX)}
                y={Math.min(topY, bottomY)}
                width={Math.abs(endX - startX)}
                height={Math.abs(bottomY - topY)}
                fill={isActive ? "rgba(100, 150, 255, 0.04)" : "rgba(100, 150, 255, 0.01)"}
              />
            )}
            
            {/* Resistance line */}
            <line
              x1={startX}
              y1={topY}
              x2={endX}
              y2={topY}
              stroke={topColor}
              strokeWidth={lineWidth}
              opacity={strokeOpacity}
              strokeDasharray={isSecondary ? "6,3" : "none"}
            />
            
            {/* Support line */}
            <line
              x1={startX}
              y1={bottomY}
              x2={endX}
              y2={bottomY}
              stroke={bottomColor}
              strokeWidth={lineWidth}
              opacity={strokeOpacity}
              strokeDasharray={isSecondary ? "6,3" : "none"}
            />
            
            {/* Labels (only for dominant when active) */}
            {!isSecondary && isActive && contract.labels && contract.labels.map((label, labelIdx) => {
              const labelY = toY(label.price);
              if (labelY === null) return null;
              return (
                <text
                  key={`stack-label-${idx}-${labelIdx}`}
                  x={endX + 8}
                  y={labelY + 4}
                  fill={label.kind === 'resistance' ? '#ef4444' : '#22c55e'}
                  fontSize="12"
                  fontWeight="700"
                >
                  {label.text || `$${label.price?.toLocaleString()}`}
                </text>
              );
            })}
            
            {/* ═══════════════════════════════════════════════════════════════
                PATTERN LABEL НА ГРАФИКЕ — MAIN / ALT
                ═══════════════════════════════════════════════════════════════ */}
            <g opacity={strokeOpacity}>
              <rect
                x={startX + 10}
                y={topY - 28}
                width={isSecondary ? 90 : 110}
                height={20}
                rx={4}
                fill={isSecondary ? 'rgba(0,200,255,0.15)' : 'rgba(251,191,36,0.2)'}
                stroke={patternColor}
                strokeWidth={1}
              />
              <text
                x={startX + 15}
                y={topY - 14}
                fill={patternColor}
                fontSize="11"
                fontWeight="700"
              >
                {labelText}
              </text>
            </g>
          </g>
        );
      }
    }
    
    // Handle lines (for channels, triangles, flags)
    if (contract.lines && contract.lines.length > 0) {
      contract.lines.forEach((line, lineIdx) => {
        const x1 = toX(line.from?.time);
        const y1 = toY(line.from?.price);
        const x2 = toX(line.to?.time);
        const y2 = toY(line.to?.price);
        
        if (x1 !== null && y1 !== null && x2 !== null && y2 !== null) {
          const lineColor = isSecondary 
            ? '#00c8ff'
            : (line.kind === 'upper' ? '#ef4444' : 
               line.kind === 'lower' ? '#22c55e' : '#8b5cf6');
          
          // ═══════════════════════════════════════════════════════════════
          // HOVER WRAPPER для lines
          // ═══════════════════════════════════════════════════════════════
          elements.push(
            <g
              key={`stack-line-group-${idx}-${lineIdx}`}
              onMouseEnter={handleMouseEnter}
              onMouseLeave={handleMouseLeave}
              onClick={handleClick}
              style={{ cursor: 'pointer' }}
            >
              {/* HITBOX — толстая невидимая линия */}
              <line
                x1={x1} y1={y1} x2={x2} y2={y2}
                stroke="transparent"
                strokeWidth={15}
              />
              
              {/* Visible line */}
              <line
                x1={x1} y1={y1} x2={x2} y2={y2}
                stroke={lineColor}
                strokeWidth={lineWidth}
                opacity={strokeOpacity}
                strokeDasharray={isSecondary ? "8,4" : "none"}
              />
              
              {/* Точки на концах */}
              <circle cx={x1} cy={y1} r={isActive ? 4 : 2} fill={lineColor} opacity={strokeOpacity} />
              <circle cx={x2} cy={y2} r={isActive ? 4 : 2} fill={lineColor} opacity={strokeOpacity} />
            </g>
          );
        }
      });
    }
    
    // Handle polyline (for double/triple top/bottom)
    if (contract.polyline) {
      const polylineData = Array.isArray(contract.polyline) ? contract.polyline : contract.polyline.points;
      
      if (polylineData && polylineData.length >= 2) {
        // Build path from points
        const pathData = polylineData
          .map((p, i) => {
            const x = toX(p.time || p.t);
            const y = toY(p.price || p.p);
            if (x === null || y === null) return null;
            return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
          })
          .filter(Boolean)
          .join(' ');
        
        if (pathData) {
          const pathColor = isSecondary 
            ? (type?.includes('top') ? '#ff6b6b' : type?.includes('bottom') ? '#69db7c' : '#00c8ff')
            : (type?.includes('top') ? '#ef4444' : type?.includes('bottom') ? '#22c55e' : '#8b5cf6');
          
          // ═══════════════════════════════════════════════════════════════
          // HOVER WRAPPER для polyline с hitbox
          // ═══════════════════════════════════════════════════════════════
          elements.push(
            <g
              key={`stack-polyline-group-${idx}`}
              onMouseEnter={handleMouseEnter}
              onMouseLeave={handleMouseLeave}
              onClick={handleClick}
              style={{ cursor: 'pointer' }}
            >
              {/* HITBOX — толстый невидимый путь */}
              <path
                d={pathData}
                stroke="transparent"
                strokeWidth={15}
                fill="none"
              />
              
              {/* Visible path */}
              <path
                d={pathData}
                stroke={pathColor}
                strokeWidth={lineWidth}
                fill="none"
                opacity={strokeOpacity}
                strokeDasharray={isSecondary ? "8,4" : "none"}
              />
              
              {/* Точки на всех вершинах */}
              {polylineData.map((p, pointIdx) => {
                const x = toX(p.time || p.t);
                const y = toY(p.price || p.p);
                if (x === null || y === null) return null;
                
                const radius = isActive ? (isSecondary ? 5 : 7) : 3;
                
                return (
                  <circle
                    key={`stack-point-${idx}-${pointIdx}`}
                    cx={x}
                    cy={y}
                    r={radius}
                    fill={pathColor}
                    stroke="#ffffff"
                    strokeWidth={isActive ? 2 : 1}
                    opacity={strokeOpacity}
                  />
                );
              })}
              
              {/* Лейбл типа паттерна — MAIN / ALT */}
              {polylineData.length > 0 && (() => {
                const firstPoint = polylineData[0];
                const x = toX(firstPoint.time || firstPoint.t);
                const y = toY(firstPoint.price || firstPoint.p);
                if (x === null || y === null) return null;
                
                return (
                  <g opacity={strokeOpacity}>
                    <rect
                      x={x - 50}
                      y={y - 32}
                      width={isSecondary ? 90 : 110}
                      height={20}
                      rx={4}
                      fill={isSecondary ? 'rgba(0,200,255,0.15)' : `${pathColor}20`}
                      stroke={pathColor}
                      strokeWidth={1}
                    />
                    <text
                      x={x - 45}
                      y={y - 18}
                      fill={pathColor}
                      fontSize="11"
                      fontWeight="700"
                    >
                      {labelText}
                    </text>
                  </g>
                );
              })()}
            </g>
          );
        }
      }
    }
    
    // Handle pole (for flags/pennants) - support both formats
    if (contract.pole) {
      // Try new format (start_time/end_time) or old format (from/to)
      const poleStartTime = contract.pole.start_time || contract.pole.from?.time;
      const poleEndTime = contract.pole.end_time || contract.pole.to?.time;
      const poleStartPrice = contract.pole.start_price || contract.pole.from?.price;
      const poleEndPrice = contract.pole.end_price || contract.pole.to?.price;
      
      const x1 = toX(poleStartTime);
      const y1 = toY(poleStartPrice);
      const x2 = toX(poleEndTime);
      const y2 = toY(poleEndPrice);
      
      if (x1 !== null && y1 !== null && x2 !== null && y2 !== null) {
        // Pole line (dashed, yellow)
        elements.push(
          <line
            key={`stack-pole-${idx}`}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke="#fbbf24"
            strokeWidth={lineWidth + 1}
            strokeDasharray="8 4"
            opacity={strokeOpacity}
          />
        );
        
        // Pole strength indicator
        const poleStrength = contract.pole.strength || 'moderate';
        const strengthColor = poleStrength === 'strong' ? '#22c55e' : 
                             poleStrength === 'moderate' ? '#fbbf24' : '#94a3b8';
        
        // Arrow at pole end showing direction
        const direction = contract.pole.direction || (poleEndPrice > poleStartPrice ? 'up' : 'down');
        const arrowSize = 8;
        const arrowX = x2;
        const arrowY = y2;
        
        if (direction === 'up') {
          elements.push(
            <polygon
              key={`stack-pole-arrow-${idx}`}
              points={`${arrowX},${arrowY - arrowSize} ${arrowX - arrowSize/2},${arrowY} ${arrowX + arrowSize/2},${arrowY}`}
              fill={strengthColor}
              opacity={strokeOpacity}
            />
          );
        } else {
          elements.push(
            <polygon
              key={`stack-pole-arrow-${idx}`}
              points={`${arrowX},${arrowY + arrowSize} ${arrowX - arrowSize/2},${arrowY} ${arrowX + arrowSize/2},${arrowY}`}
              fill={strengthColor}
              opacity={strokeOpacity}
            />
          );
        }
      }
    }
  });
  
  console.log('[PatternSVGOverlay] Render stack:', stack.length, 'patterns rendered');
  return elements;
}

export default PatternSVGOverlay;
