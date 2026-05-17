/**
 * Leaderboard Mode Tabs (U-2 + M-3 UI)
 * Toggle between Utility, Intel and Momentum views
 */
import { useSearchParams } from 'react-router-dom';
import { BarChart3, Zap, Activity } from 'lucide-react';

export default function LeaderboardModeTabs() {
  const [searchParams, setSearchParams] = useSearchParams();
  const mode = searchParams.get('mode') || 'utility';

  const setMode = (next) => {
    const p = new URLSearchParams(searchParams.toString());
    if (next === 'utility') {
      p.delete('mode'); // utility is default
    } else {
      p.set('mode', next);
    }
    p.delete('page');
    // Reset sort to mode-appropriate default
    p.delete('sort');
    setSearchParams(p);
  };

  const Tab = ({ value, label, icon: Icon, description }) => {
    const active = mode === value;
    return (
      <button
        onClick={() => setMode(value)}
        data-testid={`mode-tab-${value}`}
        title={description}
        className={`px-4 py-2 text-sm font-medium rounded-lg border transition-all flex items-center gap-2 ${
          active
            ? 'bg-gray-900 border-gray-900 text-white shadow-sm'
            : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50 hover:border-gray-300'
        }`}
      >
        <Icon className="w-4 h-4" />
        {label}
      </button>
    );
  };

  return (
    <div className="flex gap-2" data-testid="leaderboard-mode-tabs">
      <Tab 
        value="utility" 
        label="Utility" 
        icon={BarChart3}
        description="Objective metrics: Growth, Engagement, Stability"
      />
      <Tab 
        value="intel" 
        label="Advanced" 
        icon={Zap}
        description="Full intel score: Alpha, Credibility, Network"
      />
      <Tab 
        value="momentum" 
        label="Momentum" 
        icon={Activity}
        description="Growth velocity and acceleration"
      />
    </div>
  );
}
