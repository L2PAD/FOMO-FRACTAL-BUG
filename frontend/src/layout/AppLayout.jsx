import { Outlet, useLocation } from 'react-router-dom';
import { Suspense } from 'react';
import { Sidebar } from '../components/Sidebar';
import PaywallOverlay from '../components/PaywallOverlay';
import ErrorBoundary from '../components/ErrorBoundary';

function InlineLoader() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="w-6 h-6 border-2 border-gray-300 border-t-gray-900 rounded-full animate-spin" />
    </div>
  );
}

export default function AppLayout() {
  const location = useLocation();
  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      <Sidebar />

      <main className="flex-1 min-h-0 min-w-0 overflow-auto">
        <Suspense fallback={<InlineLoader />}>
          {/* Re-mount the boundary on every route change so a contained
              error on one page does not block navigation to another page. */}
          <ErrorBoundary key={location.pathname} scope={`page:${location.pathname}`}>
            <Outlet />
          </ErrorBoundary>
        </Suspense>
      </main>

      <PaywallOverlay />
    </div>
  );
}
