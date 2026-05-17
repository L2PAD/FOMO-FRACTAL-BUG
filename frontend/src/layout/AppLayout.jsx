import { Outlet } from 'react-router-dom';
import { Suspense } from 'react';
import { Sidebar } from '../components/Sidebar';
import PaywallOverlay from '../components/PaywallOverlay';

function InlineLoader() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="w-6 h-6 border-2 border-gray-300 border-t-gray-900 rounded-full animate-spin" />
    </div>
  );
}

export default function AppLayout() {
  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      <Sidebar />

      <main className="flex-1 min-h-0 min-w-0 overflow-auto">
        <Suspense fallback={<InlineLoader />}>
          <Outlet />
        </Suspense>
      </main>

      <PaywallOverlay />
    </div>
  );
}
