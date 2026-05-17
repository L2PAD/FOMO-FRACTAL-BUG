/**
 * Chart Toolbar - Split toggles for precise control
 * ==================================================
 * 
 * Toggles:
 * - Execution (zones + lines)
 * - Range (box)
 * - Swings (HH/HL/LH/LL labels)
 * - Events (BOS/CHOCH markers)
 * - Patterns (triangle, wedge, channel, box) - TT-UI4.2
 * - Scenario (projection paths) - TT-UI4.2
 */

import React from 'react';
import { Layers, TrendingUp, Square, Target, Triangle, TrendingDown } from 'lucide-react';

const ChartToolbar = ({ 
  showExecution, 
  showRange, 
  showSwings, 
  showEvents,
  showPatterns,
  showScenario,
  onToggleExecution,
  onToggleRange,
  onToggleSwings,
  onToggleEvents,
  onTogglePatterns,
  onToggleScenario
}) => {
  return (
    <div className="absolute top-4 left-4 z-10 flex flex-wrap gap-2 rounded-lg border border-white/10 bg-[#11161D]/95 p-2 backdrop-blur">
      <Toggle 
        label="Execution" 
        active={showExecution} 
        onClick={onToggleExecution}
        icon={<Layers size={14} />}
      />
      <Toggle 
        label="Range" 
        active={showRange} 
        onClick={onToggleRange}
        icon={<Square size={14} />}
      />
      <Toggle 
        label="Swings" 
        active={showSwings} 
        onClick={onToggleSwings}
        icon={<TrendingUp size={14} />}
      />
      <Toggle 
        label="Events" 
        active={showEvents} 
        onClick={onToggleEvents}
        icon={<Target size={14} />}
      />
      <Toggle 
        label="Patterns" 
        active={showPatterns} 
        onClick={onTogglePatterns}
        icon={<Triangle size={14} />}
      />
      <Toggle 
        label="Scenario" 
        active={showScenario} 
        onClick={onToggleScenario}
        icon={<TrendingDown size={14} />}
      />
    </div>
  );
};

const Toggle = ({ label, active, onClick, icon }) => {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-all ${
        active
          ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
          : 'bg-white/5 text-gray-300 hover:bg-white/10 hover:text-white'
      }`}
      title={`Toggle ${label}`}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
};

export default ChartToolbar;
