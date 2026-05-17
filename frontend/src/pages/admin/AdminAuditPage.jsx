/**
 * Audit Log — История действий администраторов
 */
import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminLayout from '../../components/admin/AdminLayout';
import { useAdminAuth } from '../../context/AdminAuthContext';
import { getAuditLog } from '../../api/admin.api';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import {
  FileText, RefreshCw, AlertTriangle, CheckCircle, XCircle,
  Loader2, Filter, Clock, User, ChevronLeft, ChevronRight,
} from 'lucide-react';

const displayText = (t) => (typeof t === 'string' ? t.replace(/_/g, ' ') : t);

const ACTION_COLORS = {
  LOGIN_SUCCESS: 'text-green-700',
  LOGIN_FAILED: 'text-red-700',
  ML_TOGGLE: 'text-purple-700',
  ML_POLICY_UPDATE: 'text-purple-700',
  ML_RELOAD: 'text-purple-700',
  ML_MODEL_TOGGLE: 'text-purple-700',
  PROVIDER_ADD: 'text-blue-700',
  PROVIDER_REMOVE: 'text-blue-700',
  PROVIDER_RESET: 'text-blue-700',
  PROVIDER_RESET_ALL: 'text-amber-700',
  CIRCUIT_BREAKER_RESET: 'text-amber-700',
  SETTINGS_UPDATE: 'text-blue-700',
  PASSWORD_CHANGE: 'text-orange-700',
};

const ACTION_TYPES = [
  { value: 'all', label: 'Все действия' },
  { value: 'LOGIN_SUCCESS', label: 'Успешный вход' },
  { value: 'LOGIN_FAILED', label: 'Неудачный вход' },
  { value: 'ML_TOGGLE', label: 'ML переключение' },
  { value: 'ML_POLICY_UPDATE', label: 'Обновление политики ML' },
  { value: 'ML_RELOAD', label: 'Перезагрузка ML' },
  { value: 'PROVIDER_ADD', label: 'Добавление провайдера' },
  { value: 'PROVIDER_REMOVE', label: 'Удаление провайдера' },
  { value: 'PROVIDER_RESET_ALL', label: 'Сброс всех провайдеров' },
  { value: 'CIRCUIT_BREAKER_RESET', label: 'Сброс Circuit Breaker' },
];

const PAGE_SIZE = 10;

function AuditLogEntry({ log }) {
  const colorClass = ACTION_COLORS[log.action] || 'text-gray-700';
  const isFailure = log.result === 'failure';

  return (
    <div className="flex items-start gap-3 p-3 rounded-lg bg-gray-50/70" data-testid="audit-log-entry">
      <div className="mt-0.5">
        {isFailure
          ? <XCircle className="w-4 h-4 text-red-500" />
          : <CheckCircle className="w-4 h-4 text-green-500" />
        }
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs font-bold uppercase ${colorClass}`}>{displayText(log.action)}</span>
          {log.resource && <span className="text-xs text-gray-400">{log.resource}</span>}
        </div>
        <div className="flex items-center gap-3 mt-1.5 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <User className="w-3 h-3" />
            {log.adminUsername || log.adminId?.substring(0, 8)}
          </span>
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {new Date(log.ts * 1000).toLocaleString()}
          </span>
          {log.ip && <span>IP: {log.ip}</span>}
        </div>
      </div>
    </div>
  );
}

export default function AdminAuditPage() {
  const navigate = useNavigate();
  const { isAdmin, isAuthenticated, loading: authLoading } = useAdminAuth();

  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionFilter, setActionFilter] = useState('all');
  const [page, setPage] = useState(1);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getAuditLog(200, actionFilter === 'all' ? null : actionFilter);
      if (result.ok) {
        setLogs(result.data.logs || []);
        setStats(result.data.stats || null);
        setError(null);
      }
    } catch (err) {
      if (err.message === 'UNAUTHORIZED') { navigate('/admin/login', { replace: true }); return; }
      setError(err.message);
    } finally { setLoading(false); }
  }, [navigate, actionFilter]);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) { navigate('/admin/login', { replace: true }); return; }
    if (!authLoading && isAuthenticated && !isAdmin) { navigate('/admin/system-overview', { replace: true }); return; }
    if (isAdmin) fetchLogs();
  }, [authLoading, isAuthenticated, isAdmin, navigate, fetchLogs]);

  useEffect(() => { setPage(1); }, [actionFilter]);

  const totalPages = Math.max(1, Math.ceil(logs.length / PAGE_SIZE));
  const pagedLogs = logs.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  if (authLoading || (loading && logs.length === 0)) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center h-32">
          <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className="space-y-6" data-testid="audit-log-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <FileText className="w-5 h-5 text-amber-600" />
            <div>
              <h1 className="text-xl font-semibold text-slate-900">Audit Log</h1>
              <p className="text-xs text-gray-500">История действий администраторов</p>
            </div>
          </div>
          <button onClick={fetchLogs} disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            data-testid="audit-refresh">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Обновить
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-3 p-4 bg-red-50/70 rounded-lg">
            <AlertTriangle className="w-5 h-5 text-red-600" />
            <span className="text-sm text-red-800">{error}</span>
          </div>
        )}

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3" data-testid="audit-stats">
            <div className="p-4 rounded-lg bg-gray-50/70 text-center">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Всего действий</p>
              <p className="text-2xl font-bold text-slate-900">{stats.totalActions || 0}</p>
            </div>
            <div className="p-4 rounded-lg bg-gray-50/70 text-center">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Ошибки</p>
              <p className="text-2xl font-bold text-red-600">{stats.failures || 0}</p>
            </div>
            <div className="p-4 rounded-lg bg-gray-50/70 text-center">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Активные админы</p>
              <p className="text-2xl font-bold text-slate-900">{Object.keys(stats.byAdmin || {}).length}</p>
            </div>
            <div className="p-4 rounded-lg bg-gray-50/70 text-center">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Типы действий</p>
              <p className="text-2xl font-bold text-slate-900">{Object.keys(stats.byAction || {}).length}</p>
            </div>
          </div>
        )}

        {/* Filter */}
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-500" />
            <Select value={actionFilter} onValueChange={setActionFilter}>
              <SelectTrigger className="w-[200px]" data-testid="audit-action-filter">
                <SelectValue placeholder="Фильтр" />
              </SelectTrigger>
              <SelectContent>
                {ACTION_TYPES.map(t => (
                  <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Logs */}
        <div data-testid="audit-logs-list">
          <p className="text-xs text-gray-400 mb-3">{logs.length} записей всего</p>
          {logs.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <FileText className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <p className="text-sm">Записей не найдено</p>
            </div>
          ) : (
            <div className="space-y-2">
              {pagedLogs.map((log, idx) => <AuditLogEntry key={`${log.ts}-${idx}`} log={log} />)}
            </div>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between pt-2" data-testid="audit-pagination">
            <span className="text-xs text-gray-400">
              Страница {page} из {totalPages}
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                data-testid="audit-page-prev"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                let pageNum;
                if (totalPages <= 7) {
                  pageNum = i + 1;
                } else if (page <= 4) {
                  pageNum = i + 1;
                } else if (page >= totalPages - 3) {
                  pageNum = totalPages - 6 + i;
                } else {
                  pageNum = page - 3 + i;
                }
                return (
                  <button
                    key={pageNum}
                    onClick={() => setPage(pageNum)}
                    className={`w-8 h-8 rounded-lg text-sm font-medium transition-colors ${
                      page === pageNum
                        ? 'bg-indigo-600 text-white'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                    data-testid={`audit-page-${pageNum}`}
                  >
                    {pageNum}
                  </button>
                );
              })}
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                data-testid="audit-page-next"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
