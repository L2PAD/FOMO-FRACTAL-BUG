/**
 * TopBar — Minimal header
 * P0: Page title + Notification Bell only
 */
import { useLocation } from 'react-router-dom';
import NotificationBell from '../components/NotificationBell';

const PAGE_TITLES = {
  '/intelligence/price-expectation-v2': 'Prediction',
  '/exchange': 'Exchange',
  '/intelligence/onchain-v3': 'On-chain',
  '/twitter': 'Sentiment',
  '/telegram': 'Telegram',
  '/notifications': 'Alerts',
  '/settings': 'Settings',
  '/admin': 'Admin',
};

function getPageTitle(pathname) {
  // Exact match first
  if (PAGE_TITLES[pathname]) return PAGE_TITLES[pathname];
  // Prefix match
  for (const [path, title] of Object.entries(PAGE_TITLES)) {
    if (path !== '/' && pathname.startsWith(path)) return title;
  }
  return 'Dashboard';
}

export default function TopBar() {
  const location = useLocation();
  const title = getPageTitle(location.pathname);

  return (
    <div className="bg-white border-b border-gray-100 px-6 py-3 flex items-center justify-between" data-testid="topbar">
      <h1 className="text-base font-semibold text-gray-900" data-testid="topbar-title">
        {title}
      </h1>

      <div className="flex items-center">
        <NotificationBell />
      </div>
    </div>
  );
}
