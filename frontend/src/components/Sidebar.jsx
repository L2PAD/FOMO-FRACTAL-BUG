/**
 * Sidebar Navigation — FOMO Intelligence
 *
 * - Collapsible, localStorage persistence
 * - Real auth state from AuthContext
 * - 3 user states: guest / free / pro
 */
import { Link, useLocation } from 'react-router-dom';
import {
  Crosshair, BarChart3, Link2, Activity, Send, Bell, Triangle,
  Settings, ChevronLeft, ChevronRight, LogOut, CreditCard, LineChart
} from 'lucide-react';
import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

const AlphaIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor" stroke="none">
    <rect x="2" y="16" width="3.5" height="5" rx="0.4" opacity="0.4" />
    <rect x="7" y="12" width="3.5" height="9" rx="0.4" opacity="0.55" />
    <rect x="12" y="8.5" width="3.5" height="12.5" rx="0.4" opacity="0.75" />
    <rect x="17" y="5" width="3.5" height="16" rx="0.4" />
  </svg>
);

const NAV_ITEMS = [
  { id: 'alpha', label: 'Alpha', icon: AlphaIcon, path: '/intelligence/price-expectation-v2' },
  { id: 'fractal', label: 'Fractal', icon: Triangle, path: '/fractal' },
  { id: 'exchange', label: 'Exchange', icon: BarChart3, path: '/exchange' },
  { id: 'onchain', label: 'On-chain', icon: Link2, path: '/intelligence/onchain-v3' },
  { id: 'sentiment', label: 'Sentiment', icon: Activity, path: '/twitter' },
  // RESTORED 2026-05-16: Tech Analysis was previously removed during refactor.
  // Backend integration (services/technical_analysis.py + /api/ta/basic/{symbol}) is live.
  { id: 'tech-analysis', label: 'Tech Analysis', icon: LineChart, path: '/tech-analysis' },
  { id: 'prediction', label: 'Prediction', icon: Crosshair, path: '/prediction-markets' },
  { id: 'telegram', label: 'Telegram', icon: Send, path: '/telegram' },
];

export function Sidebar() {
  const location = useLocation();
  const { user, isAuthenticated, isPro, login, logout } = useAuth();

  const [collapsed, setCollapsed] = useState(() => {
    const stored = localStorage.getItem('sidebar_collapsed');
    if (stored !== null) return stored === 'true';
    return window.innerWidth < 768;
  });

  useEffect(() => {
    localStorage.setItem('sidebar_collapsed', String(collapsed));
  }, [collapsed]);

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 768) setCollapsed(true);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const isActive = (path) => {
    const base = path.split('?')[0];
    if (location.pathname === base) return true;
    if (base !== '/' && location.pathname.startsWith(base + '/')) return true;
    return false;
  };

  const userState = !isAuthenticated ? 'guest' : isPro ? 'pro' : 'free';
  const userEmail = user?.email || '';

  return (
    <aside
      data-testid="sidebar"
      className={`${collapsed ? 'w-16' : 'w-56'} bg-gray-950 text-white min-h-screen flex flex-col transition-all duration-200 ease-in-out flex-shrink-0`}
    >
      {/* Logo + Collapse */}
      <div className={`${collapsed ? 'justify-center' : ''} px-3 py-4 border-b border-white/5`}>
        <div className={`flex items-center ${collapsed ? 'justify-center' : 'justify-between'}`}>
          {!collapsed && (
            <Link to="/" className="flex items-center gap-2" data-testid="sidebar-logo">
              <img src="/assets/logo.svg" alt="FOMO" className="h-9 w-auto" />
            </Link>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="p-1.5 rounded-md hover:bg-white/10 transition-colors text-gray-400 hover:text-white"
            data-testid="sidebar-collapse-toggle"
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>
        {!collapsed && (
          <p className="text-[10px] text-gray-500 mt-1 pl-0.5 tracking-wide">Prediction Intelligence</p>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 space-y-0.5">
        {NAV_ITEMS.map((item) => {
          const active = isActive(item.path);
          const Icon = item.icon;
          const className = `flex items-center gap-2.5 rounded-lg text-sm transition-all duration-150 ${
            collapsed ? 'justify-center px-2 py-2.5' : 'px-3 py-2'
          } ${active ? 'bg-white/10 text-white font-medium' : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'}`;
          // External (Expo bundle) navigation — full page load.
          if (item.external) {
            return (
              <a
                key={item.id}
                href={item.path}
                data-testid={`sidebar-nav-${item.id}`}
                title={collapsed ? item.label : undefined}
                className={className}
              >
                <Icon className="w-[18px] h-[18px] flex-shrink-0" />
                {!collapsed && <span>{item.label}</span>}
              </a>
            );
          }
          return (
            <Link
              key={item.id} to={item.path}
              data-testid={`sidebar-nav-${item.id}`}
              title={collapsed ? item.label : undefined}
              className={className}
            >
              <Icon className="w-[18px] h-[18px] flex-shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}

        <div className="pt-3 pb-1"><div className="h-px bg-white/5" /></div>

        <Link to="/notifications" data-testid="sidebar-nav-alerts" title={collapsed ? 'Alerts' : undefined}
          className={`flex items-center gap-2.5 rounded-lg text-sm transition-all duration-150 ${
            collapsed ? 'justify-center px-2 py-2.5' : 'px-3 py-2'
          } ${isActive('/notifications') ? 'bg-white/10 text-white font-medium' : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'}`}>
          <Bell className="w-[18px] h-[18px] flex-shrink-0" />
          {!collapsed && <span>Alerts</span>}
        </Link>

        <Link to="/settings" data-testid="sidebar-nav-settings" title={collapsed ? 'Settings' : undefined}
          className={`flex items-center gap-2.5 rounded-lg text-sm transition-all duration-150 ${
            collapsed ? 'justify-center px-2 py-2.5' : 'px-3 py-2'
          } ${isActive('/settings') ? 'bg-white/10 text-white font-medium' : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'}`}>
          <Settings className="w-[18px] h-[18px] flex-shrink-0" />
          {!collapsed && <span>Settings</span>}
        </Link>
      </nav>

      {/* User Block */}
      <div className="border-t border-white/5 p-3" data-testid="sidebar-user-block">
        {userState === 'guest' ? (
          <button onClick={login} data-testid="sidebar-signin-btn"
            className={`w-full flex items-center justify-center gap-2 rounded-lg text-sm font-medium transition-all ${
              collapsed ? 'p-2.5' : 'px-3 py-2.5'
            } bg-white/10 hover:bg-white/15 text-white`}>
            <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="currentColor">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            {!collapsed && <span>Sign in with Google</span>}
          </button>
        ) : (
          <div className={`${collapsed ? 'flex flex-col items-center gap-2' : 'space-y-2'}`}>
            <div className={`flex items-center ${collapsed ? 'justify-center' : 'gap-2.5'}`}>
              {user?.picture ? (
                <img src={user.picture} alt="" className="w-8 h-8 rounded-full flex-shrink-0" />
              ) : (
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                  {userEmail ? userEmail[0].toUpperCase() : 'U'}
                </div>
              )}
              {!collapsed && (
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-white font-medium truncate">{userEmail}</p>
                  <p className={`text-[10px] font-medium ${userState === 'pro' ? 'text-emerald-400' : 'text-gray-500'}`}>
                    Plan: {userState === 'pro' ? 'PRO' : 'Free'}
                  </p>
                </div>
              )}
            </div>
            {!collapsed && (
              <div className="space-y-1">
                {userState === 'free' ? (
                  <Link to="/settings?tab=billing" data-testid="sidebar-upgrade-btn"
                    className="flex items-center gap-2 w-full px-2.5 py-1.5 rounded-md text-xs font-medium bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 transition-colors">
                    <CreditCard className="w-3.5 h-3.5" /><span>Upgrade</span>
                  </Link>
                ) : (
                  <Link to="/settings?tab=billing" data-testid="sidebar-manage-btn"
                    className="flex items-center gap-2 w-full px-2.5 py-1.5 rounded-md text-xs text-gray-400 hover:bg-white/5 hover:text-gray-200 transition-colors">
                    <CreditCard className="w-3.5 h-3.5" /><span>Manage Plan</span>
                  </Link>
                )}
                <button onClick={logout} data-testid="sidebar-logout-btn"
                  className="flex items-center gap-2 w-full px-2.5 py-1.5 rounded-md text-xs text-gray-500 hover:bg-white/5 hover:text-gray-300 transition-colors">
                  <LogOut className="w-3.5 h-3.5" /><span>Logout</span>
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
