/**
 * Admin Login Page
 */
import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAdminAuth } from '../../context/AdminAuthContext';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { AlertCircle, Shield, Loader2 } from 'lucide-react';

export default function AdminLoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnTo = searchParams.get('returnTo') || '/admin/system-overview';
  const { login, loading: authLoading, isAuthenticated } = useAdminAuth();
  
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (isAuthenticated && !authLoading) {
    navigate(returnTo, { replace: true });
    return null;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const result = await login(username, password);
      if (result.ok) {
        navigate(returnTo, { replace: true });
      } else {
        setError(result.error || 'Неверные учётные данные');
      }
    } catch {
      setError('Ошибка соединения. Попробуйте снова.');
    } finally {
      setLoading(false);
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white rounded-2xl p-8" data-testid="admin-login-card">
        <div className="text-center mb-6">
          <div className="flex justify-center mb-4">
            <div className="p-3 rounded-xl bg-blue-50">
              <Shield className="w-8 h-8 text-blue-600" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Admin Panel</h1>
          <p className="text-sm text-slate-500 mt-1">Администрирование платформы</p>
        </div>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50/70 text-red-700 text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
          
          <div className="space-y-2">
            <Label htmlFor="username" className="text-slate-700">Имя пользователя</Label>
            <Input
              id="username"
              data-testid="admin-login-username"
              type="text"
              placeholder="admin"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoComplete="username"
            />
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="password" className="text-slate-700">Пароль</Label>
            <Input
              id="password"
              data-testid="admin-login-password"
              type="password"
              placeholder="********"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>
          
          <Button
            type="submit"
            data-testid="admin-login-submit"
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium"
            disabled={loading}
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Вход...
              </>
            ) : (
              'Войти'
            )}
          </Button>
        </form>
        
        <div className="mt-6 pt-4">
          <p className="text-xs text-slate-500 text-center">
            Доступ ограничен авторизованным персоналом.
            <br />
            Все действия записываются.
          </p>
        </div>
      </div>
    </div>
  );
}
