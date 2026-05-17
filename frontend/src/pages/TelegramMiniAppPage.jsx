import { useState, useEffect } from 'react';
import { MiniAppProvider, useMiniApp } from '../context/MiniAppContext';
import { HomeScreen } from '../components/miniapp/home/HomeScreen';
import { FeedScreen } from '../components/miniapp/feed/FeedScreen';
import { EdgeScreen } from '../components/miniapp/edge/EdgeScreen';
import ProfileScreen from '../components/miniapp/profile/ProfileScreen';
import { BottomNav } from '../components/miniapp/BottomNav';
import { WelcomeScreen } from '../components/miniapp/WelcomeScreen';

const ONBOARDING_KEY = 'fomo_onboarding_completed';

const THEMES = {
  dark: {
    '--ma-bg': '#09090b',
    '--ma-surface': '#18181b',
    '--ma-text': '#fafafa',
    '--ma-secondary': '#a1a1aa',
    '--ma-muted': '#52525b',
    '--ma-border': '#27272a',
    '--ma-border-active': '#52525b',
    '--ma-hover': 'rgba(39,39,42,0.5)',
    '--ma-card': '#18181b',
    '--ma-accent': '#6366f1',
    '--ma-divider': 'rgba(39,39,42,0.5)',
    '--ma-stat-bg': 'rgba(39,39,42,0.4)',
    '--ma-bar-bg': 'rgba(255,255,255,0.06)',
  },
  light: {
    '--ma-bg': '#f0f0f3',
    '--ma-surface': '#ffffff',
    '--ma-text': '#0f172a',
    '--ma-secondary': '#334155',
    '--ma-muted': '#64748b',
    '--ma-border': '#cbd5e1',
    '--ma-border-active': '#94a3b8',
    '--ma-hover': 'rgba(0,0,0,0.05)',
    '--ma-card': '#ffffff',
    '--ma-accent': '#6366f1',
    '--ma-divider': 'rgba(203,213,225,0.6)',
    '--ma-stat-bg': 'rgba(0,0,0,0.04)',
    '--ma-bar-bg': 'rgba(0,0,0,0.06)',
  },
};

export default function TelegramMiniAppPage() {
  return (
    <MiniAppProvider>
      <MiniAppShell />
    </MiniAppProvider>
  );
}

function MiniAppShell() {
  const { activeTab, theme } = useMiniApp();
  const themeVars = THEMES[theme] || THEMES.dark;
  const logo = theme === 'dark' ? '/assets/logo-white.png' : '/assets/logo-main.png';

  const [showWelcome, setShowWelcome] = useState(() => {
    try { return !localStorage.getItem(ONBOARDING_KEY); } catch { return true; }
  });

  const handleOnboardingComplete = () => {
    try { localStorage.setItem(ONBOARDING_KEY, 'true'); } catch {}
    setShowWelcome(false);
  };

  return (
    <div
      data-testid="miniapp-shell"
      style={{
        position: 'fixed', inset: 0,
        backgroundColor: themeVars['--ma-bg'],
        color: themeVars['--ma-text'],
        fontFamily: "'Manrope', sans-serif",
        display: 'flex', flexDirection: 'column',
        overflow: 'hidden',
        ...themeVars,
      }}
    >
      {showWelcome && <WelcomeScreen onComplete={handleOnboardingComplete} />}

      {/* Logo Header */}
      <div style={{
        padding: '10px 16px 4px',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <img
          src={logo}
          alt="FOMO"
          data-testid="miniapp-logo"
          style={{ height: '38px', objectFit: 'contain' }}
        />
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', paddingBottom: '72px' }}>
        {activeTab === 'home' && <HomeScreen />}
        {activeTab === 'feed' && <FeedScreen />}
        {activeTab === 'polymarket' && <EdgeScreen />}
        {activeTab === 'profile' && <ProfileScreen />}
      </div>

      {/* Bottom Navigation */}
      <BottomNav />
    </div>
  );
}
