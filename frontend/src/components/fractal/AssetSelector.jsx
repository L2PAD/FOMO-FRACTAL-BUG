/**
 * ASSET SELECTOR — Product Switcher
 * 
 * Активы:
 * - BTC Terminal (Финальный)
 * - SPX Terminal (Финальный)
 * - DXY Macro (Финальный)
 * - Cross-Asset (Composite)
 */

import React from 'react';

const PRODUCTS = [
  {
    id: 'BTC',
    name: 'BTC',
    fullName: 'BTC Terminal',
    status: 'FINAL',
    description: 'Bitcoin Fractal Model',
    tooltip: 'Фрактальная модель Bitcoin: 56% hit rate, 15.7% avg error',
    color: 'bg-orange-500',
    available: true,
  },
  {
    id: 'SPX',
    name: 'SPX',
    fullName: 'SPX Terminal',
    status: 'FINAL',
    description: 'S&P 500 Fractal',
    tooltip: 'Фрактальная модель S&P 500: структурный анализ',
    color: 'bg-blue-500',
    available: true,
  },
  {
    id: 'DXY',
    name: 'DXY',
    fullName: 'DXY Macro',
    status: 'FINAL',
    description: 'Dollar Index Macro',
    tooltip: 'Макро-модель DXY: 71% hit rate, 1.9% avg error',
    color: 'bg-emerald-500',
    available: true,
  },
  {
    id: 'CROSS',
    name: 'Cross',
    fullName: 'Cross-Asset',
    status: 'FINAL',
    description: 'BTC×SPX×DXY Composite',
    tooltip: 'Composite модель: BTC 50% + SPX 30% + DXY 20%',
    color: 'bg-purple-500',
    available: true,
  },
];

export function AssetSelector({ currentAsset = 'BTC', onSelect, theme = 'light' }) {
  const isDark = theme === 'dark';
  
  return (
    <div className="flex items-center gap-2" data-testid="asset-selector">
      {PRODUCTS.map((product) => (
        <button
          key={product.id}
          onClick={() => product.available && onSelect?.(product.id)}
          disabled={!product.available}
          title={product.tooltip}
          className={`
            flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium
            transition-all duration-200
            ${currentAsset === product.id 
              ? `${product.color} text-white shadow-lg` 
              : product.available 
                ? isDark 
                  ? 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                : isDark
                  ? 'bg-slate-800 text-slate-500 cursor-not-allowed opacity-50'
                  : 'bg-gray-50 text-gray-400 cursor-not-allowed opacity-50'
            }
          `}
          data-testid={`asset-btn-${product.id}`}
        >
          <span className={`w-2 h-2 rounded-full ${
            product.status === 'FINAL' ? 'bg-emerald-400' : 'bg-amber-400 animate-pulse'
          }`}></span>
          <span>{product.name}</span>
        </button>
      ))}
    </div>
  );
}

export function AssetSelectorCard({ currentAsset = 'BTC', onSelect }) {
  const current = PRODUCTS.find(p => p.id === currentAsset) || PRODUCTS[0];
  
  return (
    <div className="bg-slate-900 rounded-xl p-4" data-testid="asset-selector-card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-white font-semibold">Select Terminal</h3>
        <span className={`px-2 py-0.5 rounded text-xs font-medium text-white ${
          current.status === 'FINAL' ? 'bg-emerald-500' : 'bg-amber-500'
        }`}>
          {current.status}
        </span>
      </div>
      
      <div className="grid grid-cols-3 gap-2">
        {PRODUCTS.map((product) => (
          <button
            key={product.id}
            onClick={() => product.available && onSelect?.(product.id)}
            disabled={!product.available}
            className={`
              flex flex-col items-center justify-center p-3 rounded-lg
              transition-all duration-200
              ${currentAsset === product.id 
                ? `${product.color} text-white` 
                : product.available 
                  ? 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  : 'bg-slate-800 text-slate-500 cursor-not-allowed'
              }
            `}
          >
            <span className="text-lg font-bold">{product.id}</span>
            <span className="text-xs opacity-75 mt-1">{product.description}</span>
          </button>
        ))}
      </div>
      
      <div className="mt-3 text-xs text-slate-500">
        {current.description} — {current.status === 'FINAL' ? 'Production Ready' : 'Under Construction'}
      </div>
    </div>
  );
}

export default AssetSelector;
