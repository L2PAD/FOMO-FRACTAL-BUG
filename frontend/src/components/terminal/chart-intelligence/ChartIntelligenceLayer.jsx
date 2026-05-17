/**
 * Chart Intelligence Layer - Orchestrator with density control
 * =============================================================
 * 
 * Features:
 * - 4 independent toggles
 * - Density control (last 10 swings, last 3 events)
 * - Visual hierarchy (z-index layering)
 * - Extensible for future overlays
 */

import React, { useState, useMemo } from 'react';
import ChartToolbar from './ChartToolbar';
import ExecutionOverlay from './overlays/ExecutionOverlay';
import StructureRangeOverlay from './overlays/StructureRangeOverlay';
import StructureSwingOverlay from './overlays/StructureSwingOverlay';
import StructureEventOverlay from './overlays/StructureEventOverlay';
import PatternOverlay from './overlays/PatternOverlay';
import ScenarioOverlay from './overlays/ScenarioOverlay';

const ChartIntelligenceLayer = ({ chart, candleSeries, data }) => {
  // Separate toggles for each overlay type
  const [showExecution, setShowExecution] = useState(true);
  const [showRange, setShowRange] = useState(true);
  const [showSwings, setShowSwings] = useState(true);
  const [showEvents, setShowEvents] = useState(true);
  const [showPatterns, setShowPatterns] = useState(true);
  const [showScenario, setShowScenario] = useState(true);

  // Density control - limit data to prevent visual clutter
  const limitedStructure = useMemo(() => {
    if (!data?.structure) return null;
    return {
      ...data.structure,
      swings: (data.structure.swings || []).slice(-10), // Last 10 swings
      events: (data.structure.events || []).slice(-3),   // Last 3 events
    };
  }, [data]);

  // Helper to convert price to Y coordinate
  const priceToY = useMemo(() => {
    if (!candleSeries) return null;
    return (price) => {
      try {
        return candleSeries.priceToCoordinate(price);
      } catch (e) {
        return null;
      }
    };
  }, [candleSeries]);

  // Helper to convert time to X coordinate (MVP version)
  const timeToX = useMemo(() => {
    if (!chart) return null;
    // For MVP, use a simple approach: map timestamps to proportional positions
    // Production: Use chart's timeScale API for precise positioning
    return (timestamp) => {
      try {
        const logicalIndex = chart.timeScale().coordinateToLogical(timestamp);
        return chart.timeScale().logicalToCoordinate(logicalIndex);
      } catch (e) {
        // Fallback: return null, overlays will handle gracefully
        return null;
      }
    };
  }, [chart]);

  // Get chart dimensions
  const width = chart?.options()?.width || 800;
  const height = chart?.options()?.height || 450;

  if (!chart || !candleSeries || !data) return null;

  return (
    <>
      {/* Toolbar */}
      <ChartToolbar
        showExecution={showExecution}
        showRange={showRange}
        showSwings={showSwings}
        showEvents={showEvents}
        showPatterns={showPatterns}
        showScenario={showScenario}
        onToggleExecution={() => setShowExecution(v => !v)}
        onToggleRange={() => setShowRange(v => !v)}
        onToggleSwings={() => setShowSwings(v => !v)}
        onToggleEvents={() => setShowEvents(v => !v)}
        onTogglePatterns={() => setShowPatterns(v => !v)}
        onToggleScenario={() => setShowScenario(v => !v)}
      />

      {/* Overlays with visual hierarchy (z-index) */}
      
      {/* Level 1: Range (lowest) */}
      {showRange && limitedStructure?.range && (
        <StructureRangeOverlay
          range={limitedStructure.range}
          priceToY={priceToY}
          width={width}
          height={height}
        />
      )}

      {/* Level 2: Execution zones */}
      {showExecution && data.execution && (
        <ExecutionOverlay
          data={data.execution}
          priceToY={priceToY}
          width={width}
          height={height}
        />
      )}

      {/* Level 3: Swing labels */}
      {showSwings && limitedStructure?.swings && (
        <StructureSwingOverlay
          swings={limitedStructure.swings}
          priceToY={priceToY}
          width={width}
          height={height}
        />
      )}

      {/* Level 4: Event markers (highest) */}
      {showEvents && limitedStructure?.events && (
        <StructureEventOverlay
          events={limitedStructure.events}
          priceToY={priceToY}
          width={width}
          height={height}
        />
      )}

      {/* Level 5: Pattern overlays (TT-UI4.2) */}
      {showPatterns && data.chart_intelligence?.patterns && (
        <PatternOverlay
          patterns={data.chart_intelligence.patterns}
          priceToY={priceToY}
          timeToX={timeToX}
          width={width}
          height={height}
        />
      )}

      {/* Level 6: Scenario projections (highest - TT-UI4.2) */}
      {showScenario && data.chart_intelligence?.scenarios && (
        <ScenarioOverlay
          scenarios={data.chart_intelligence.scenarios}
          priceToY={priceToY}
          timeToX={timeToX}
          width={width}
          height={height}
        />
      )}
    </>
  );
};

export default ChartIntelligenceLayer;
