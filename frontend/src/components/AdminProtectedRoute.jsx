/**
 * Protected Route для админки
 * Проверяет авторизацию ОДИН РАЗ на входе в /admin
 * Внутренние страницы не требуют повторной проверки
 */

import { Navigate, Outlet } from 'react-router-dom';
import { useAdminAuth } from '../context/AdminAuthContext';
import { Loader2 } from 'lucide-react';

export default function AdminProtectedRoute() {
  const { isAuthenticated, loading } = useAdminAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/admin/login" replace />;
  }

  return <Outlet />;
}
