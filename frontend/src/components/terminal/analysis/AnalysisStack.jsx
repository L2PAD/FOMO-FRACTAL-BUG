/**
 * Analysis Stack - FULL (11 panels)
 * ==================================
 * 
 * Complete analytical explanation layer
 */

import React, { useState } from 'react';
import ContextPanel from './panels/ContextPanel';
import StructurePanel from './panels/StructurePanel';
import PatternsPanel from './panels/PatternsPanel';
import ConfluencePanel from './panels/ConfluencePanel';
import PredictionPanel from './panels/PredictionPanel';
import EntryTimingPanel from './panels/EntryTimingPanel';
import MicrostructurePanel from './panels/MicrostructurePanel';
import ValidationPanel from './panels/ValidationPanel';
import AlphaPanel from './panels/AlphaPanel';
import RegimePanel from './panels/RegimePanel';
import ControlPanel from './panels/ControlPanel';

const tabs = [
  { id: 'context', label: 'Context' },
  { id: 'structure', label: 'Structure' },
  { id: 'patterns', label: 'Patterns' },
  { id: 'confluence', label: 'Confluence' },
  { id: 'prediction', label: 'Prediction' },
  { id: 'entry', label: 'Entry' },
  { id: 'micro', label: 'Micro' },
  { id: 'validation', label: 'Validation' },
  { id: 'alpha', label: 'Alpha' },
  { id: 'regime', label: 'Regime' },
  { id: 'control', label: 'Control' },
];

export default function AnalysisStack({ data, symbol = 'BTCUSDT', timeframe = '4H' }) {
  const [active, setActive] = useState('entry');

  if (!data) return null;

  return (
    <div className="rounded-xl border border-white/10 bg-[#0F141A]">
      {/* Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-white/10 p-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActive(tab.id)}
            className={`rounded px-3 py-1.5 text-xs font-medium uppercase tracking-wide transition-all ${
              active === tab.id
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                : 'text-gray-400 hover:bg-white/5 hover:text-white'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Panel Content */}
      <div className="p-4">
        {active === 'context' && <ContextPanel data={data.context} />}
        {active === 'structure' && <StructurePanel data={data.structure_analysis} />}
        {active === 'patterns' && <PatternsPanel data={data.patterns_analysis} />}
        {active === 'confluence' && <ConfluencePanel data={data.confluence} />}
        {active === 'prediction' && <PredictionPanel data={data.prediction} />}
        {active === 'entry' && (
          <EntryTimingPanel
            data={data.entry || data.decision}
            symbol={symbol}
            timeframe={timeframe}
          />
        )}
        {active === 'micro' && <MicrostructurePanel data={data.micro} />}
        {active === 'validation' && (
          <ValidationPanel
            data={data.validation}
            symbol={symbol}
            timeframe={timeframe}
          />
        )}
        {active === 'alpha' && <AlphaPanel data={data.alpha} />}
        {active === 'regime' && <RegimePanel data={data.regime} />}
        {active === 'control' && <ControlPanel data={data.control} fullData={data} />}
      </div>
    </div>
  );
}
