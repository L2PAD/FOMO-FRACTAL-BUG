/**
 * Telegram Filter Drawer (UI-FREEZE-1 / ETAP 2)
 * Production-grade URL-driven filter system
 */
import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { X, RotateCcw, Shield, Rocket, Radio, Sprout } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';

const ACTIVITY_OPTIONS = [
  { value: '_all', label: 'All Activity' },
  { value: 'Very High', label: 'Very High' },
  { value: 'High', label: 'High' },
  { value: 'Medium', label: 'Medium' },
  { value: 'Low', label: 'Low' },
];

const LANGUAGE_OPTIONS = [
  { value: '_all', label: 'All Languages' },
  { value: 'EN', label: 'English' },
  { value: 'RU', label: 'Russian' },
  { value: 'UA', label: 'Ukrainian' },
];

const TYPE_OPTIONS = [
  { value: '_all', label: 'All Types' },
  { value: 'channel', label: 'Channel' },
  { value: 'group', label: 'Group' },
];

const SECTOR_OPTIONS = [
  { value: '_all', label: 'All Sectors' },
  { value: 'Crypto', label: 'Crypto' },
  { value: 'DeFi', label: 'DeFi' },
  { value: 'NFT', label: 'NFT' },
  { value: 'Trading', label: 'Trading' },
  { value: 'Gaming', label: 'Gaming' },
  { value: 'News', label: 'News' },
  { value: 'Education', label: 'Education' },
  { value: 'Community', label: 'Community' },
  { value: 'Airdrop', label: 'Airdrop' },
  { value: 'ICO', label: 'ICO' },
];

const SORT_OPTIONS = [
  { value: 'utility', label: 'FOMO Score' },
  { value: 'growth', label: 'Growth (7D)' },
  { value: 'members', label: 'Members' },
  { value: 'reach', label: 'Avg Reach' },
];

const PRESETS = [
  {
    id: 'fast-growing',
    label: 'Fast Growing',
    Icon: Rocket,
    filters: {
      minGrowth7: '10',
      activity: 'High',
      maxRedFlags: '2',
    },
  },
  {
    id: 'high-reach',
    label: 'High Reach Low Spam',
    Icon: Radio,
    filters: {
      minReach: '10000',
      maxRedFlags: '1',
    },
  },
  {
    id: 'low-risk',
    label: 'Low Risk Stable',
    Icon: Shield,
    filters: {
      maxRedFlags: '0',
      activity: '',
      minGrowth7: '0',
    },
  },
  {
    id: 'emerging',
    label: 'New Emerging',
    Icon: Sprout,
    filters: {
      minGrowth7: '5',
      lifecycle: 'EMERGING',
    },
  },
];

export default function TelegramFilterDrawer({ open, onClose }) {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  
  const [filters, setFilters] = useState({
    type: '',
    sector: '',
    minMembers: '',
    maxMembers: '',
    minReach: '',
    maxReach: '',
    minGrowth7: '',
    maxGrowth7: '',
    activity: '',
    maxRedFlags: '',
    lifecycle: '',
    language: '',
    sort: 'utility',
  });

  useEffect(() => {
    if (open) {
      setFilters({
        type: searchParams.get('type') || '',
        sector: searchParams.get('sector') || '',
        minMembers: searchParams.get('minMembers') || '',
        maxMembers: searchParams.get('maxMembers') || '',
        minReach: searchParams.get('minReach') || '',
        maxReach: searchParams.get('maxReach') || '',
        minGrowth7: searchParams.get('minGrowth7') || '',
        maxGrowth7: searchParams.get('maxGrowth7') || '',
        activity: searchParams.get('activity') || '',
        maxRedFlags: searchParams.get('maxRedFlags') || '',
        lifecycle: searchParams.get('lifecycle') || '',
        language: searchParams.get('language') || '',
        sort: searchParams.get('sort') || 'utility',
      });
    }
  }, [open, searchParams]);

  const updateFilter = (key, value) => {
    const clean = value === '_all' ? '' : value;
    setFilters(prev => ({ ...prev, [key]: clean }));
  };

  const applyFilters = () => {
    const params = new URLSearchParams();
    const q = searchParams.get('q');
    if (q) params.set('q', q);
    
    Object.entries(filters).forEach(([key, value]) => {
      if (value && value !== '' && value !== 'utility') {
        params.set(key, value);
      }
    });
    
    if (filters.sort && filters.sort !== 'utility') {
      params.set('sort', filters.sort);
    }
    
    params.set('page', '1');
    navigate(`/telegram?${params.toString()}`);
    onClose();
  };

  const resetFilters = () => {
    navigate('/telegram');
    onClose();
  };

  const applyPreset = (preset) => {
    setFilters(prev => ({
      ...prev,
      type: '',
      sector: '',
      minMembers: '',
      maxMembers: '',
      minReach: '',
      maxReach: '',
      minGrowth7: '',
      maxGrowth7: '',
      activity: '',
      maxRedFlags: '',
      lifecycle: '',
      language: '',
      ...preset.filters,
    }));
  };

  const activeCount = Object.entries(filters).filter(
    ([key, value]) => value && value !== '' && key !== 'sort'
  ).length;

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} />
      
      <div className="fixed right-0 top-0 h-full w-[420px] bg-white shadow-xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-gray-900">Filters</h2>
            {activeCount > 0 && (
              <span className="px-2 py-0.5 bg-teal-100 text-teal-700 text-xs font-medium rounded-full">
                {activeCount} active
              </span>
            )}
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100 transition-colors">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
          {/* Quick Presets */}
          <div>
            <label className="text-sm font-medium text-gray-700 mb-3 block">Quick Presets</label>
            <div className="grid grid-cols-2 gap-2">
              {PRESETS.map(preset => {
                const IconComponent = preset.Icon;
                return (
                  <button
                    key={preset.id}
                    onClick={() => applyPreset(preset)}
                    className="flex items-center gap-2.5 px-3 py-2.5 border border-gray-200 rounded-lg text-sm hover:bg-gray-50 hover:border-teal-300 transition-all text-left"
                    data-testid={`preset-${preset.id}`}
                  >
                    <IconComponent className="w-4 h-4 text-gray-500" />
                    <span className="text-gray-700">{preset.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="border-t border-gray-200" />

          {/* Type */}
          <FilterSelect
            label="Type"
            value={filters.type || '_all'}
            onChange={(v) => updateFilter('type', v)}
            options={TYPE_OPTIONS}
          />

          {/* Activity */}
          <FilterSelect
            label="Activity Level"
            value={filters.activity || '_all'}
            onChange={(v) => updateFilter('activity', v)}
            options={ACTIVITY_OPTIONS}
          />

          {/* Language */}
          <FilterSelect
            label="Language"
            value={filters.language || '_all'}
            onChange={(v) => updateFilter('language', v)}
            options={LANGUAGE_OPTIONS}
            testId="filter-language"
          />

          {/* Sector */}
          <FilterSelect
            label="Sector"
            value={filters.sector || '_all'}
            onChange={(v) => updateFilter('sector', v)}
            options={SECTOR_OPTIONS}
            testId="filter-sector"
          />

          {/* Members Range */}
          <FilterRange
            label="Members"
            minValue={filters.minMembers}
            maxValue={filters.maxMembers}
            onMinChange={(v) => updateFilter('minMembers', v)}
            onMaxChange={(v) => updateFilter('maxMembers', v)}
            placeholder={{ min: 'Min (e.g. 1000)', max: 'Max (e.g. 100000)' }}
          />

          {/* Avg Reach Range */}
          <FilterRange
            label="Average Reach"
            minValue={filters.minReach}
            maxValue={filters.maxReach}
            onMinChange={(v) => updateFilter('minReach', v)}
            onMaxChange={(v) => updateFilter('maxReach', v)}
            placeholder={{ min: 'Min reach', max: 'Max reach' }}
          />

          {/* Growth 7D Range */}
          <FilterRange
            label="Growth (7D %)"
            minValue={filters.minGrowth7}
            maxValue={filters.maxGrowth7}
            onMinChange={(v) => updateFilter('minGrowth7', v)}
            onMaxChange={(v) => updateFilter('maxGrowth7', v)}
            placeholder={{ min: 'Min % (e.g. 5)', max: 'Max %' }}
          />

          {/* Max Red Flags */}
          <div>
            <label className="text-sm font-medium text-gray-700 mb-2 block">Max Red Flags</label>
            <input
              type="number"
              value={filters.maxRedFlags}
              onChange={(e) => updateFilter('maxRedFlags', e.target.value)}
              placeholder="0-10"
              min="0"
              max="10"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-100 focus:border-teal-400"
            />
          </div>

          {/* Sort By */}
          <FilterSelect
            label="Sort By"
            value={filters.sort || 'utility'}
            onChange={(v) => updateFilter('sort', v)}
            options={SORT_OPTIONS}
          />
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200 bg-gray-50 relative z-[60]">
          <button
            onClick={resetFilters}
            className="flex items-center gap-2 px-4 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            Reset All
          </button>
          <button
            onClick={applyFilters}
            className="px-6 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 transition-colors"
            data-testid="apply-filters-btn"
          >
            Apply Filters
          </button>
        </div>
      </div>
    </>
  );
}

function FilterSelect({ label, value, onChange, options, testId }) {
  return (
    <div>
      <label className="text-sm font-medium text-gray-700 mb-2 block">{label}</label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger 
          className="w-full border-gray-200 bg-white rounded-lg h-10 text-sm hover:border-teal-300 transition-colors"
          data-testid={testId}
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent className="rounded-lg border-gray-200 bg-white shadow-lg">
          {options.map(opt => (
            <SelectItem 
              key={opt.value} 
              value={opt.value}
              className="text-sm cursor-pointer rounded-md hover:bg-teal-50 focus:bg-teal-50 focus:text-teal-900"
            >
              {opt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function FilterRange({ label, minValue, maxValue, onMinChange, onMaxChange, placeholder }) {
  return (
    <div>
      <label className="text-sm font-medium text-gray-700 mb-2 block">{label}</label>
      <div className="flex gap-2">
        <input
          type="number"
          value={minValue}
          onChange={(e) => onMinChange(e.target.value)}
          placeholder={placeholder.min}
          className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-100 focus:border-teal-400"
        />
        <span className="text-gray-400 self-center">—</span>
        <input
          type="number"
          value={maxValue}
          onChange={(e) => onMaxChange(e.target.value)}
          placeholder={placeholder.max}
          className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-100 focus:border-teal-400"
        />
      </div>
    </div>
  );
}
