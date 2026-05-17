/**
 * Paywall Overlay — Blocks content for non-subscribers
 * Shows blur + upgrade CTA when user is not on PRO plan
 */
import { useAuth } from '../context/AuthContext';
import { Lock, CreditCard } from 'lucide-react';
import { Link } from 'react-router-dom';

export function Paywall({ children }) {
  const { isAuthenticated, isPro, login } = useAuth();

  // PRO users see content normally
  if (isPro) return children;

  return (
    <div className="relative">
      {/* Blurred content behind */}
      <div className="filter blur-sm opacity-40 pointer-events-none select-none">
        {children}
      </div>

      {/* Overlay */}
      <div className="absolute inset-0 flex items-center justify-center z-10" data-testid="paywall-overlay">
        <div className="bg-white rounded-2xl shadow-xl border border-gray-200 px-8 py-10 max-w-md text-center">
          <div className="w-14 h-14 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Lock className="w-6 h-6 text-gray-500" />
          </div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">Subscription Required</h2>
          <p className="text-sm text-gray-500 mb-6">
            Access FOMO Intelligence with a PRO subscription
          </p>
          {isAuthenticated ? (
            <Link to="/settings?tab=billing" data-testid="paywall-upgrade-btn"
              className="inline-flex items-center gap-2 px-6 py-3 bg-gray-900 text-white rounded-xl text-sm font-semibold hover:bg-gray-800 transition-colors">
              <CreditCard className="w-4 h-4" />
              Upgrade Now
            </Link>
          ) : (
            <button onClick={login} data-testid="paywall-signin-btn"
              className="inline-flex items-center gap-2 px-6 py-3 bg-gray-900 text-white rounded-xl text-sm font-semibold hover:bg-gray-800 transition-colors">
              Sign in to Subscribe
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
