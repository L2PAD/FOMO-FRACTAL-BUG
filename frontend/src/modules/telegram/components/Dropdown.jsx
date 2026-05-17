/**
 * Dropdown Component (Multi-select)
 */
import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, X } from 'lucide-react';

export function Dropdown({ label, value = [], options, onChange, multi = true }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  function toggle(x) {
    if (!multi) return onChange([x]);
    const next = value.includes(x) ? value.filter((a) => a !== x) : [...value, x];
    onChange(next);
  }

  function clear() {
    onChange([]);
  }

  const summary = value.length ? `${label}: ${value.length}` : label;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((s) => !s)}
        className="h-9 px-3 rounded-xl border border-gray-200 bg-white text-xs font-bold flex items-center gap-1.5 hover:border-gray-400 transition-colors"
      >
        {summary}
        <ChevronDown className="w-4 h-4 text-gray-400" />
      </button>

      {open && (
        <div className="absolute top-11 left-0 w-64 bg-white border border-gray-200 rounded-2xl shadow-2xl p-3 z-30">
          <div className="flex justify-between items-center mb-3">
            <div className="text-xs font-black text-gray-900">{label}</div>
            <button
              onClick={clear}
              className="text-xs font-bold text-gray-500 hover:text-gray-900"
            >
              Clear
            </button>
          </div>

          <div className="flex flex-col gap-2 max-h-72 overflow-y-auto">
            {options.map((o) => {
              const active = value.includes(o.value);
              return (
                <button
                  key={o.value}
                  onClick={() => toggle(o.value)}
                  className={`flex items-center justify-between h-9 rounded-xl border px-3 text-xs font-bold transition-all ${
                    active
                      ? 'bg-gray-900 text-white border-gray-900'
                      : 'bg-white text-gray-700 border-gray-200 hover:border-gray-400'
                  }`}
                >
                  <span>{o.label}</span>
                  {active && <span>✓</span>}
                </button>
              );
            })}
          </div>

          <div className="flex justify-end mt-3 pt-3 border-t border-gray-100">
            <button
              onClick={() => setOpen(false)}
              className="h-8 px-3 rounded-xl border border-gray-200 bg-white text-xs font-bold hover:bg-gray-50"
            >
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
