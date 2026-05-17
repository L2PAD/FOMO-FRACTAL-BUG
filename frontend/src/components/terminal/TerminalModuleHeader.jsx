import { useTerminal } from '../../store/terminalStore';
import { Activity, Target, TrendingUp, GitBranch } from 'lucide-react';

// OPERATOR TABS ONLY (admin tabs moved to /admin/trading)
const TABS = [
  { id: 'trade', label: 'Trade', icon: Activity, workspace: 'trade' },
  { id: 'positions', label: 'Positions', icon: TrendingUp, workspace: 'positions' },
  { id: 'decisions', label: 'Decisions', icon: GitBranch, workspace: 'decisions' },
  { id: 'analytics', label: 'Analytics', icon: Target, workspace: 'analytics' },
];

export default function TerminalModuleHeader() {
  const { state, dispatch } = useTerminal();

  const handleTabClick = (workspace) => {
    dispatch({ type: 'SET_WORKSPACE', payload: workspace });
  };

  return (
    <div className="shrink-0 border-b border-[#eef1f5] bg-white" style={{ fontFamily: 'Gilroy, sans-serif' }}>
      <div className="px-6 py-4 flex items-center justify-between">
        {/* LEFT: Title + Subtitle */}
        <div className="flex items-center gap-3">
          <Activity className="w-8 h-8 text-[#05A584]" />
          <div className="flex flex-col">
            <h1 className="text-[20px] font-bold text-[#0f172a] leading-tight m-0" data-testid="trading-title">
              Trading Terminal
            </h1>
            <span className="text-xs text-[#94a3b8] mt-0.5">Advanced execution & portfolio management</span>
          </div>
        </div>

        {/* RIGHT: Tabs */}
        <div className="flex items-center gap-[6px]" data-testid="trading-tabs">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = state.selectedWorkspace === tab.workspace;

            return (
              <button
                key={tab.id}
                onClick={() => handleTabClick(tab.workspace)}
                style={{
                  padding: '8px 16px',
                  borderRadius: '10px',
                  fontSize: '14px',
                  fontWeight: 500,
                  transition: 'all 0.15s',
                  border: 'none',
                  background: isActive ? '#0f172a' : 'transparent',
                  color: isActive ? '#ffffff' : '#64748b',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = '#f1f5f9';
                    e.currentTarget.style.color = '#0f172a';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = 'transparent';
                    e.currentTarget.style.color = '#64748b';
                  }
                }}
                data-testid={`tab-${tab.id}`}
              >
                <Icon style={{ width: '16px', height: '16px' }} />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
