/**
 * Twitter Parser — Sessions
 * Управление cookie-сессиями парсера
 */

import { useState, useEffect, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import AdminLayout from '../../components/admin/AdminLayout';
import {
  getSessions,
  getWebhookInfo,
  testSession,
  deleteSession,
} from '../../api/twitterParserAdmin.api';
import { api } from '../../api/client';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../../components/ui/dialog';
import { Button } from '../../components/ui/button';
import {
  RefreshCw,
  Trash2,
  Cookie,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  Key,
  Copy,
  PlayCircle,
  Bell,
  HeartPulse,
  ShieldCheck,
  Timer,
  Activity,
  Download,
  Loader2,
} from 'lucide-react';
import { toast } from 'sonner';

/* ── Status indicator (no Badge, no pill) ── */
function StatusIndicator({ status }) {
  const cfg = {
    OK:      { label: 'Валидна', icon: CheckCircle, cls: 'text-emerald-700' },
    STALE:   { label: 'Устарела', icon: Clock,       cls: 'text-amber-700' },
    INVALID: { label: 'Невалидна', icon: XCircle,    cls: 'text-red-500' },
    EXPIRED: { label: 'Истекла', icon: XCircle,       cls: 'text-red-500' },
  };
  const c = cfg[status] || cfg.INVALID;
  const Icon = c.icon;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium ${c.cls}`} data-testid={`status-${status}`}>
      <Icon className="w-3.5 h-3.5" />
      {c.label}
    </span>
  );
}

/* ── Risk level (text only) ── */
function RiskLevel({ score }) {
  if (score == null) return null;
  const cls = score < 35 ? 'text-emerald-700' : score < 70 ? 'text-amber-700' : 'text-red-500';
  return (
    <span className={`text-xs font-medium ${cls}`}>
      <ShieldCheck className="w-3 h-3 inline mr-0.5" />
      Риск: {score}%
    </span>
  );
}

export default function TwitterParserSessionsPage() {
  const navigate = useNavigate();

  const [sessions, setSessions] = useState([]);
  const [stats, setStats] = useState({ total: 0, ok: 0, stale: 0, invalid: 0 });
  const [riskReport, setRiskReport] = useState(null);
  const [workerStatus, setWorkerStatus] = useState(null);
  const [webhookInfo, setWebhookInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [showWebhookDialog, setShowWebhookDialog] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [testingSession, setTestingSession] = useState(null);
  const [regenerating, setRegenerating] = useState(false);
  const platformUrl = typeof window !== 'undefined' ? window.location.origin : '';

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getSessions();
      if (res.ok) {
        setSessions(res.data || []);
        setStats(res.stats || { total: 0, ok: 0, stale: 0, invalid: 0 });
      } else {
        setError(res.error || 'Не удалось загрузить сессии');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchRiskReport = useCallback(async () => {
    try {
      const res = await api.get('/api/admin/twitter-parser/risk/report');
      if (res.data.ok) setRiskReport(res.data.data);
    } catch (err) {
      console.error('Failed to fetch risk report:', err);
    }
  }, []);

  const fetchWorkerStatus = useCallback(async () => {
    try {
      const res = await api.get('/api/admin/twitter-parser/worker/status');
      if (res.data.ok) setWorkerStatus(res.data.data);
    } catch (err) {
      console.error('Failed to fetch worker status:', err);
    }
  }, []);

  const fetchWebhookInfo = useCallback(async () => {
    try {
      const res = await getWebhookInfo();
      if (res.ok) setWebhookInfo(res.data);
    } catch (err) {
      console.error('Failed to fetch webhook info:', err);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
    fetchWebhookInfo();
    fetchRiskReport();
    fetchWorkerStatus();
  }, [fetchSessions, fetchWebhookInfo, fetchRiskReport, fetchWorkerStatus]);

  const handleTest = async (session) => {
    setTestingSession(session.sessionId);
    try {
      const res = await testSession(session.sessionId);
      if (res.ok) {
        res.valid
          ? toast.success(`Сессия ${session.sessionId} валидна (${res.cookieCount} cookies)`)
          : toast.error(`Сессия невалидна: ${res.reason}`);
        fetchSessions();
      } else {
        toast.error(res.error || 'Тест не пройден');
      }
    } catch (err) {
      toast.error(err.message);
    } finally {
      setTestingSession(null);
    }
  };

  const handleDelete = async (sessionId) => {
    const res = await deleteSession(sessionId);
    if (res.ok) {
      toast.success('Сессия удалена');
      setConfirmDelete(null);
      fetchSessions();
    } else {
      toast.error(res.error || 'Не удалось удалить');
    }
  };

  const handleHealthCheck = async () => {
    try {
      const res = await api.post('/api/admin/twitter-parser/sessions/health-check');
      if (res.data.ok) {
        toast.success(`Health check: ${res.data.checked} проверено, ${res.data.changed} изменено`);
        fetchSessions();
        fetchRiskReport();
      } else {
        toast.error(res.data.error || 'Health check failed');
      }
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleRiskRecalculate = async () => {
    try {
      const res = await api.post('/api/admin/twitter-parser/risk/recalculate');
      if (res.data.ok) {
        toast.success(`Риск пересчитан: ${res.data.checked} сессий, ${res.data.changed} изменений`);
        fetchSessions();
        fetchRiskReport();
      } else {
        toast.error(res.data.error || 'Ошибка пересчёта');
      }
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleTestNotification = async () => {
    try {
      const res = await api.post('/api/admin/twitter-parser/sessions/test-notification');
      if (res.data.ok) toast.success('Тест-уведомление отправлено в Telegram!');
      else toast.error(res.data.error || 'Не удалось отправить');
    } catch (err) {
      toast.error(err.response?.data?.error || err.message);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Скопировано');
  };

  const handleRegenerateKey = async () => {
    try {
      setRegenerating(true);
      const res = await api.post('/api/admin/twitter-parser/sessions/webhook/regenerate-key');
      if (res.data.ok) {
        toast.success('API-ключ перегенерирован');
        fetchWebhookInfo();
      } else {
        toast.error(res.data.error || 'Ошибка генерации');
      }
    } catch (err) {
      toast.error(err.message);
    } finally {
      setRegenerating(false);
    }
  };


  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6 space-y-6" data-testid="admin-sessions-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-900" data-testid="sessions-page-title">Сессии</h1>
            <p className="text-sm text-slate-400 mt-0.5">Управление cookie-сессиями парсера</p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={handleHealthCheck} className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded transition-colors" data-testid="btn-health-check">
              <HeartPulse className="w-4 h-4" />
              Проверка
            </button>
            <button onClick={handleTestNotification} className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded transition-colors" data-testid="btn-test-alert">
              <Bell className="w-4 h-4" />
              Тест алерта
            </button>
            <button onClick={fetchSessions} disabled={loading} className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded transition-colors" data-testid="btn-refresh">
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Обновить
            </button>
            <button onClick={() => setShowWebhookDialog(true)} className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded transition-colors" data-testid="btn-webhook">
              <Key className="w-4 h-4" />
              Webhook
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-1 bg-slate-100/80 p-1 rounded-lg w-fit" data-testid="parser-tabs">
          <Link to="/admin/twitter-parser/accounts" className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800 rounded transition-colors">Аккаунты</Link>
          <Link to="/admin/twitter-parser/sessions" className="px-3 py-1.5 text-sm font-medium text-slate-900 bg-white rounded shadow-sm">Сессии</Link>
          <Link to="/admin/twitter-parser/slots" className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800 rounded transition-colors">Слоты</Link>
          <Link to="/admin/twitter-parser/monitor" className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800 rounded transition-colors">Мониторинг</Link>
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-center gap-3 p-4 rounded-lg bg-red-50 text-red-700 text-sm" data-testid="error-banner">
            <AlertTriangle className="w-5 h-5 flex-shrink-0" />
            {error}
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4">
          <div className="p-4 rounded-lg bg-slate-100" data-testid="stat-total">
            <div className="text-2xl font-bold text-slate-900">{stats.total}</div>
            <div className="text-xs text-slate-500 mt-1">Всего сессий</div>
          </div>
          <div className="p-4 rounded-lg bg-emerald-50" data-testid="stat-valid">
            <div className="text-2xl font-bold text-emerald-700">{stats.ok}</div>
            <div className="text-xs text-slate-500 mt-1">Валидных</div>
          </div>
          <div className="p-4 rounded-lg bg-amber-50" data-testid="stat-stale">
            <div className="text-2xl font-bold text-amber-700">{stats.stale}</div>
            <div className="text-xs text-slate-500 mt-1">Устаревших</div>
          </div>
          <div className="p-4 rounded-lg bg-red-50" data-testid="stat-invalid">
            <div className="text-2xl font-bold text-red-500">{stats.invalid}</div>
            <div className="text-xs text-slate-500 mt-1">Невалидных</div>
          </div>
        </div>

        {/* Risk Engine */}
        {riskReport && (
          <div className="p-5 rounded-2xl bg-slate-50/60 space-y-4" data-testid="risk-engine-section">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-slate-500" />
              <span className="text-sm font-semibold text-slate-800">Здоровье сессий</span>
            </div>
            <div className="grid grid-cols-4 gap-4">
              <div className="p-4 rounded-lg bg-emerald-50">
                <div className="text-xl font-bold text-emerald-700">{riskReport.byRisk?.healthy || 0}</div>
                <div className="text-xs text-slate-500 mt-1">Здоровые (&lt;35)</div>
              </div>
              <div className="p-4 rounded-lg bg-amber-50">
                <div className="text-xl font-bold text-amber-700">{riskReport.byRisk?.warning || 0}</div>
                <div className="text-xs text-slate-500 mt-1">Внимание (35-70)</div>
              </div>
              <div className="p-4 rounded-lg bg-red-50">
                <div className="text-xl font-bold text-red-500">{riskReport.byRisk?.critical || 0}</div>
                <div className="text-xs text-slate-500 mt-1">Критические (70+)</div>
              </div>
              <div className="p-4 rounded-lg bg-slate-100">
                <div className="text-xl font-bold text-slate-700 flex items-center gap-1.5">
                  {workerStatus?.isRunning ? (
                    <><span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />Активен</>
                  ) : (
                    <><span className="w-2 h-2 bg-slate-400 rounded-full" />Остановлен</>
                  )}
                </div>
                <div className="text-xs text-slate-500 mt-1">Health Worker</div>
              </div>
            </div>
            <button onClick={handleRiskRecalculate} className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded transition-colors" data-testid="btn-recalculate-risk">
              <RefreshCw className="w-3.5 h-3.5" />
              Пересчитать риск
            </button>
          </div>
        )}

        {/* Extension Setup */}
        <div className="p-5 rounded-2xl bg-slate-50/60 space-y-5" data-testid="extension-setup-card">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-slate-500" />
            <span className="text-sm font-semibold text-slate-800">Настройка расширения</span>
          </div>

          <div className="space-y-5 pl-1">
            {/* Step 1 */}
            <div className="flex gap-4">
              <div className="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center flex-shrink-0">
                <span className="text-xs font-bold text-slate-600">1</span>
              </div>
              <div>
                <h4 className="text-sm font-medium text-slate-800 mb-1">Скачать расширение</h4>
                <p className="text-xs text-slate-400 mb-2">Chrome-расширение для синхронизации Twitter cookies.</p>
                <a
                  href={`${process.env.REACT_APP_BACKEND_URL || ''}/api/download/fomo-extension`}
                  download="fomo_extension_v1.3.0.zip"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-semibold text-slate-800 bg-slate-100 hover:bg-slate-200 rounded transition-colors"
                  data-testid="download-extension-btn"
                >
                  <Download className="w-3.5 h-3.5" />
                  Скачать (ZIP)
                </a>
                <p className="text-xs text-slate-500 mt-1.5">chrome://extensions → Режим разработчика → Загрузить распакованное</p>
              </div>
            </div>

            {/* Step 2 */}
            <div className="flex gap-4">
              <div className="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center flex-shrink-0">
                <span className="text-xs font-bold text-slate-600">2</span>
              </div>
              <div>
                <h4 className="text-sm font-medium text-slate-800 mb-1">API-ключ</h4>
                <p className="text-xs text-slate-400 mb-2">Используйте этот ключ в настройках расширения.</p>
                <div className="flex items-center gap-2 mb-2">
                  <code className="flex-1 p-2.5 bg-slate-100 rounded-lg text-sm font-mono break-all text-slate-700">
                    {webhookInfo?.apiKey || 'Загрузка...'}
                  </code>
                  <button onClick={() => copyToClipboard(webhookInfo?.apiKey)} disabled={!webhookInfo?.apiKey} className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded transition-colors" data-testid="copy-api-key">
                    <Copy className="w-4 h-4" />
                  </button>
                </div>
                <button onClick={handleRegenerateKey} disabled={regenerating} className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded transition-colors" data-testid="btn-regenerate-key">
                  {regenerating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Key className="w-3.5 h-3.5" />}
                  Перегенерировать ключ
                </button>
              </div>
            </div>

            {/* Step 3 */}
            <div className="flex gap-4">
              <div className="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center flex-shrink-0">
                <span className="text-xs font-bold text-slate-600">3</span>
              </div>
              <div>
                <h4 className="text-sm font-medium text-slate-800 mb-1">URL платформы</h4>
                <p className="text-xs text-slate-400 mb-2">Введите этот URL в расширении.</p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 p-2.5 bg-slate-100 rounded-lg text-sm font-mono break-all text-slate-700">
                    {platformUrl}
                  </code>
                  <button onClick={() => copyToClipboard(platformUrl)} className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded transition-colors" data-testid="copy-platform-url">
                    <Copy className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>

            {/* Step 4 */}
            <div className="flex gap-4">
              <div className="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center flex-shrink-0">
                <span className="text-xs font-bold text-slate-600">4</span>
              </div>
              <div>
                <h4 className="text-sm font-medium text-slate-800 mb-1">Синхронизация</h4>
                <p className="text-xs text-slate-400">Откройте расширение на Twitter (x.com), вставьте URL и ключ, нажмите «Sync Session».</p>
              </div>
            </div>
          </div>
        </div>

        {/* Sessions List */}
        <div className="p-5 rounded-2xl bg-slate-50/60 space-y-4">
          <span className="text-sm font-semibold text-slate-800">Список сессий</span>

          {loading ? (
            <div className="text-center py-12">
              <RefreshCw className="w-6 h-6 animate-spin text-slate-400 mx-auto" />
            </div>
          ) : sessions.length === 0 ? (
            <div className="text-center py-12 text-slate-400">
              <Cookie className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm">Сессии не настроены</p>
              <p className="text-xs mt-1">Используйте Webhook для загрузки cookies через расширение</p>
              <button onClick={() => setShowWebhookDialog(true)} className="mt-3 text-sm text-slate-600 hover:text-slate-900 underline" data-testid="show-webhook-empty">
                Показать Webhook
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              {sessions.map((session) => {
                const riskInfo = riskReport?.sessions?.find(s => s.sessionId === session.sessionId);
                return (
                  <div key={session._id} className="flex items-center justify-between p-4 rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors" data-testid={`session-${session.sessionId}`}>
                    <div className="flex items-center gap-4">
                      <div className="w-9 h-9 rounded-full bg-amber-50 text-amber-500 flex items-center justify-center">
                        <Cookie className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="text-sm font-medium text-slate-800">{session.sessionId}</div>
                        {session.accountId && (
                          <div className="text-xs text-slate-500">
                            Аккаунт: @{session.accountId.username || session.accountId}
                          </div>
                        )}
                        <div className="text-xs text-slate-400 mt-0.5">
                          {session.cookiesMeta?.count || 0} cookies
                          {session.cookiesMeta?.hasAuthToken ? ' · auth_token' : ''}
                          {session.cookiesMeta?.hasCt0 ? ' · ct0' : ''}
                        </div>
                        <div className="flex items-center gap-3 mt-1">
                          {riskInfo && (
                            <>
                              <RiskLevel score={riskInfo.riskScore} />
                              <span className="text-xs text-slate-400 flex items-center gap-0.5">
                                <Timer className="w-3 h-3" />
                                ~{riskInfo.lifetime}д
                              </span>
                            </>
                          )}
                          {session.lastSyncedAt && (
                            <span className="text-xs text-slate-400">
                              Синхр: {new Date(session.lastSyncedAt).toLocaleString()}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <StatusIndicator status={session.status} />
                      <div className="flex gap-1">
                        <button
                          onClick={() => handleTest(session)}
                          disabled={testingSession === session.sessionId}
                          className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded transition-colors"
                          data-testid={`test-session-${session.sessionId}`}
                        >
                          {testingSession === session.sessionId ? (
                            <RefreshCw className="w-4 h-4 animate-spin" />
                          ) : (
                            <PlayCircle className="w-4 h-4" />
                          )}
                        </button>
                        <button
                          onClick={() => setConfirmDelete(session)}
                          className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                          data-testid={`delete-session-${session.sessionId}`}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Webhook Dialog */}
        <Dialog open={showWebhookDialog} onOpenChange={setShowWebhookDialog}>
          <DialogContent className="bg-white max-w-lg">
            <DialogHeader>
              <DialogTitle className="text-slate-900">Webhook</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-slate-500 block mb-1">Webhook URL</label>
                <div className="flex gap-2">
                  <code className="flex-1 p-2 bg-slate-100 rounded text-sm break-all text-slate-700">{window.location.origin}{webhookInfo?.webhookUrl}</code>
                  <button onClick={() => copyToClipboard(`${window.location.origin}${webhookInfo?.webhookUrl}`)} className="p-2 text-slate-400 hover:text-slate-700 rounded"><Copy className="w-4 h-4" /></button>
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-slate-500 block mb-1">API-ключ</label>
                <div className="flex gap-2">
                  <code className="flex-1 p-2 bg-slate-100 rounded text-sm font-mono break-all text-slate-700">{webhookInfo?.apiKey}</code>
                  <button onClick={() => copyToClipboard(webhookInfo?.apiKey)} className="p-2 text-slate-400 hover:text-slate-700 rounded"><Copy className="w-4 h-4" /></button>
                </div>
              </div>
              <div className="p-3 rounded-lg bg-amber-50 text-xs text-amber-700">
                <strong>Безопасность:</strong> Храните API-ключ в секрете. Он используется для аутентификации запросов загрузки cookies.
              </div>
              <div>
                <label className="text-xs font-medium text-slate-500 block mb-2">Формат запроса</label>
                <pre className="p-3 bg-slate-50 rounded text-xs overflow-auto text-slate-600">
{`POST ${webhookInfo?.webhookUrl}
Content-Type: application/json

{
  "apiKey": "<ваш-ключ>",
  "sessionId": "имя_сессии",
  "cookies": [
    {"name": "auth_token", "value": "...", "domain": ".twitter.com"},
    {"name": "ct0", "value": "...", "domain": ".twitter.com"}
  ],
  "userAgent": "Mozilla/5.0...",
  "accountUsername": "twitter_handle"
}`}
                </pre>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" size="sm" onClick={() => setShowWebhookDialog(false)} data-testid="close-webhook-dialog">Закрыть</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation */}
        <Dialog open={!!confirmDelete} onOpenChange={() => setConfirmDelete(null)}>
          <DialogContent className="bg-white">
            <DialogHeader>
              <DialogTitle className="text-slate-900">Удалить сессию?</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-slate-600">
              Вы уверены, что хотите удалить сессию <strong>{confirmDelete?.sessionId}</strong>? Это действие необратимо.
            </p>
            <DialogFooter>
              <Button variant="outline" size="sm" onClick={() => setConfirmDelete(null)} data-testid="cancel-delete">Отмена</Button>
              <Button size="sm" className="bg-red-500 hover:bg-red-600 text-white" onClick={() => handleDelete(confirmDelete?.sessionId)} data-testid="confirm-delete">
                Удалить
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </AdminLayout>
  );
}
