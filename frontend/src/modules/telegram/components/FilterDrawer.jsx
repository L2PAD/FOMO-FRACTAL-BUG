/**
 * Filter Drawer UI (Light Terminal Look)
 */
import React from 'react';
import { X, RotateCcw } from 'lucide-react';

function Field({ label, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-xs text-gray-500 font-semibold uppercase tracking-wide">{label}</div>
      {children}
    </div>
  );
}

function Input(props) {
  return (
    <input
      {...props}
      className="h-9 rounded-xl border border-gray-200 px-3 text-sm outline-none focus:border-gray-400 bg-white"
    />
  );
}

function Select({ value, onChange, children }) {
  return (
    <select
      value={value}
      onChange={onChange}
      className="h-9 rounded-xl border border-gray-200 px-2.5 text-sm outline-none focus:border-gray-400 bg-white"
    >
      {children}
    </select>
  );
}

function TogglePill({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`h-8 px-3 rounded-full text-xs font-bold border transition-all ${
        active
          ? 'bg-gray-900 text-white border-gray-900'
          : 'bg-white text-gray-700 border-gray-200 hover:border-gray-400'
      }`}
    >
      {label}
    </button>
  );
}

export function FilterDrawer({ open, onClose, value, onChange, onApply, onReset }) {
  if (!open) return null;

  const set = (patch) => onChange({ ...value, ...patch, page: 1 });

  const toggleInArr = (key, item) => {
    const curr = value[key] || [];
    const next = curr.includes(item) ? curr.filter((x) => x !== item) : [...curr, item];
    set({ [key]: next });
  };

  return (
    <div
      className="fixed inset-0 bg-black/25 z-50"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="absolute right-4 top-4 bottom-4 w-[420px] bg-white rounded-2xl border border-gray-200 shadow-2xl p-4 flex flex-col gap-4 overflow-y-auto"
      >
        {/* Header */}
        <div className="flex justify-between items-center">
          <div className="text-sm font-black text-gray-900">Filters</div>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded-lg">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Range Inputs Grid */}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Members (min)">
            <Input
              type="number"
              value={value.minMembers ?? ''}
              onChange={(e) => set({ minMembers: e.target.value ? Number(e.target.value) : null })}
              placeholder="1000"
            />
          </Field>
          <Field label="Members (max)">
            <Input
              type="number"
              value={value.maxMembers ?? ''}
              onChange={(e) => set({ maxMembers: e.target.value ? Number(e.target.value) : null })}
              placeholder="500000"
            />
          </Field>

          <Field label="Avg Reach (min)">
            <Input
              type="number"
              value={value.minReach ?? ''}
              onChange={(e) => set({ minReach: e.target.value ? Number(e.target.value) : null })}
              placeholder="500"
            />
          </Field>
          <Field label="Avg Reach (max)">
            <Input
              type="number"
              value={value.maxReach ?? ''}
              onChange={(e) => set({ maxReach: e.target.value ? Number(e.target.value) : null })}
              placeholder="200000"
            />
          </Field>

          <Field label="Growth 7D (min, 0.10=10%)">
            <Input
              type="number"
              step="0.01"
              value={value.minGrowth7 ?? ''}
              onChange={(e) => set({ minGrowth7: e.target.value ? Number(e.target.value) : null })}
              placeholder="0.10"
            />
          </Field>
          <Field label="Growth 7D (max)">
            <Input
              type="number"
              step="0.01"
              value={value.maxGrowth7 ?? ''}
              onChange={(e) => set({ maxGrowth7: e.target.value ? Number(e.target.value) : null })}
              placeholder="0.80"
            />
          </Field>

          <Field label="Posts/day (min)">
            <Input
              type="number"
              step="0.1"
              value={value.minPostsPerDay ?? ''}
              onChange={(e) => set({ minPostsPerDay: e.target.value ? Number(e.target.value) : null })}
              placeholder="0.2"
            />
          </Field>
          <Field label="Posts/day (max)">
            <Input
              type="number"
              step="0.1"
              value={value.maxPostsPerDay ?? ''}
              onChange={(e) => set({ maxPostsPerDay: e.target.value ? Number(e.target.value) : null })}
              placeholder="20"
            />
          </Field>

          <Field label="Max Fraud (0..1)">
            <Input
              type="number"
              step="0.05"
              value={value.maxFraud ?? ''}
              onChange={(e) => set({ maxFraud: e.target.value ? Number(e.target.value) : null })}
              placeholder="0.45"
            />
          </Field>
          <Field label="Min Crypto (0..1)">
            <Input
              type="number"
              step="0.01"
              value={value.minCrypto ?? ''}
              onChange={(e) => set({ minCrypto: e.target.value ? Number(e.target.value) : null })}
              placeholder="0.08"
            />
          </Field>

          <Field label="Sort">
            <Select value={value.sort ?? 'utility'} onChange={(e) => set({ sort: e.target.value })}>
              <option value="utility">Utility</option>
              <option value="growth7">Growth 7D</option>
              <option value="reach">Avg Reach</option>
              <option value="members">Members</option>
              <option value="fraud">Fraud</option>
              <option value="fresh">Fresh</option>
            </Select>
          </Field>
          <Field label="Order">
            <Select value={value.order ?? 'desc'} onChange={(e) => set({ order: e.target.value })}>
              <option value="desc">Desc</option>
              <option value="asc">Asc</option>
            </Select>
          </Field>
        </div>

        {/* Language Pills */}
        <Field label="Language">
          <div className="flex gap-2 flex-wrap">
            <TogglePill label="RU" active={(value.lang || []).includes('ru')} onClick={() => toggleInArr('lang', 'ru')} />
            <TogglePill label="UK" active={(value.lang || []).includes('uk')} onClick={() => toggleInArr('lang', 'uk')} />
            <TogglePill label="Mixed" active={(value.lang || []).includes('mixed')} onClick={() => toggleInArr('lang', 'mixed')} />
          </div>
        </Field>

        {/* Tier Pills */}
        <Field label="Tier">
          <div className="flex gap-2 flex-wrap">
            {['A+', 'A', 'B', 'C', 'D'].map((t) => (
              <TogglePill key={t} label={t} active={(value.tier || []).includes(t)} onClick={() => toggleInArr('tier', t)} />
            ))}
          </div>
        </Field>

        {/* Footer Buttons */}
        <div className="mt-auto flex gap-3 pt-4 border-t border-gray-100">
          <button
            onClick={onReset}
            className="flex-1 h-10 rounded-xl border border-gray-200 bg-white font-bold text-sm hover:bg-gray-50 flex items-center justify-center gap-2"
          >
            <RotateCcw className="w-4 h-4" />
            Reset
          </button>
          <button
            onClick={onApply}
            className="flex-1 h-10 rounded-xl bg-gray-900 text-white font-bold text-sm hover:bg-gray-800"
          >
            Apply Filters
          </button>
        </div>
      </div>
    </div>
  );
}
