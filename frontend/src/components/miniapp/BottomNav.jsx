import { Home, Newspaper, TrendingUp, User } from 'lucide-react';
import { useMiniApp } from '../../context/MiniAppContext';

const TABS = [
  { id: 'home', label: 'Home', icon: Home },
  { id: 'feed', label: 'Feed', icon: Newspaper },
  { id: 'polymarket', label: 'Edge', icon: TrendingUp },
  { id: 'profile', label: 'Profile', icon: User },
];

export function BottomNav() {
  const { activeTab, setActiveTab, fetchFeed, fetchEdge, fetchProfile, trackEvent } = useMiniApp();

  const handleTab = (id) => {
    setActiveTab(id);
    if (id === 'feed') fetchFeed();
    if (id === 'polymarket') {
      fetchEdge();
      trackEvent('edge_viewed', { source: 'bottom_nav' });
    }
    if (id === 'profile') fetchProfile();
  };

  return (
    <nav
      data-testid="bottom-nav"
      style={{
        position: 'fixed', bottom: 0, left: 0, right: 0,
        display: 'flex',
        justifyContent: 'space-around',
        padding: '8px 0 16px',
        background: 'var(--ma-bg, #09090b)',
        borderTop: '1px solid var(--ma-border, #27272a)',
        zIndex: 9999,
      }}
    >
      {TABS.map(tab => {
        const Icon = tab.icon;
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            data-testid={`tab-${tab.id === 'polymarket' ? 'edge' : tab.id}`}
            onClick={() => handleTab(tab.id)}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '3px',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              padding: '4px 16px',
              transition: 'color 0.15s',
            }}
          >
            <Icon
              size={20}
              color={isActive ? 'var(--ma-text, #fafafa)' : 'var(--ma-muted, #52525b)'}
              strokeWidth={isActive ? 2.2 : 1.5}
            />
            <span style={{
              fontSize: '10px',
              fontWeight: isActive ? 700 : 500,
              fontFamily: "'Manrope', sans-serif",
              color: isActive ? 'var(--ma-text, #fafafa)' : 'var(--ma-muted, #52525b)',
            }}>
              {tab.label}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
