/**
 * Twitter Parser — Аккаунты
 * Управление Twitter-аккаунтами парсера
 */

import { useState, useEffect, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import AdminLayout from '../../components/admin/AdminLayout';
import {
  getTwitterAccounts,
  createTwitterAccount,
  updateTwitterAccount,
  enableTwitterAccount,
  disableTwitterAccount,
  deleteTwitterAccount,
} from '../../api/twitterParserAdmin.api';
import { Input } from '../../components/ui/input';
import { Button } from '../../components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../../components/ui/dialog';
import {
  Plus,
  RefreshCw,
  Download,
  Pencil,
  Trash2,
  Power,
  PowerOff,
  User,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Lock,
  LogIn,
  Loader2,
} from 'lucide-react';
import { toast } from 'sonner';

/* ── Status indicator (text only, no pill) ── */
const STATUS_CFG = {
  ACTIVE:      { label: 'Активен',        icon: CheckCircle, cls: 'text-emerald-700' },
  DISABLED:    { label: 'Отключён',       icon: PowerOff,    cls: 'text-slate-400' },
  SUSPENDED:   { label: 'Заблокирован',   icon: XCircle,     cls: 'text-red-500' },
  LOCKED:      { label: 'Заблокирован',   icon: Lock,        cls: 'text-red-500' },
  NEEDS_LOGIN: { label: 'Нужен вход',     icon: LogIn,       cls: 'text-amber-700' },
};

function StatusIndicator({ status }) {
  const c = STATUS_CFG[status] || STATUS_CFG.DISABLED;
  const Icon = c.icon;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium ${c.cls}`} data-testid={`status-${status}`}>
      <Icon className="w-3.5 h-3.5" />
      {c.label}
    </span>
  );
}

/* ── Account Form ── */
function AccountForm({ account, onSave, onCancel }) {
  const [username, setUsername] = useState(account?.username || '');
  const [displayName, setDisplayName] = useState(account?.displayName || '');
  const [notes, setNotes] = useState(account?.notes || '');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim()) { toast.error('Укажите username'); return; }
    setLoading(true);
    try {
      await onSave({
        username: username.trim().replace('@', ''),
        displayName: displayName.trim() || undefined,
        notes: notes.trim() || undefined,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="text-xs font-medium text-slate-500 block mb-1">Twitter Username *</label>
        <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="@cryptotrader" disabled={!!account} />
        {!!account && <p className="text-xs text-slate-500 mt-1">Username нельзя изменить</p>}
      </div>
      <div>
        <label className="text-xs font-medium text-slate-500 block mb-1">Отображаемое имя</label>
        <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="Основной аккаунт" />
      </div>
      <div>
        <label className="text-xs font-medium text-slate-500 block mb-1">Заметки</label>
        <Input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Для SOL-проектов" />
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" size="sm" onClick={onCancel}>Отмена</Button>
        <Button type="submit" size="sm" disabled={loading}>{loading ? 'Сохранение...' : (account ? 'Обновить' : 'Создать')}</Button>
      </DialogFooter>
    </form>
  );
}

export default function TwitterParserAccountsPage() {
  const navigate = useNavigate();

  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [showDialog, setShowDialog] = useState(false);
  const [editingAccount, setEditingAccount] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);

  const fetchAccounts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getTwitterAccounts();
      if (res.ok) setAccounts(res.data || []);
      else setError(res.error || 'Не удалось загрузить аккаунты');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAccounts();
  }, [fetchAccounts]);

  const handleCreate = async (data) => {
    const res = await createTwitterAccount(data);
    if (res.ok) { toast.success('Аккаунт создан'); setShowDialog(false); fetchAccounts(); }
    else toast.error(res.error || 'Ошибка создания');
  };

  const handleUpdate = async (data) => {
    const res = await updateTwitterAccount(editingAccount._id, data);
    if (res.ok) { toast.success('Аккаунт обновлён'); setShowDialog(false); setEditingAccount(null); fetchAccounts(); }
    else toast.error(res.error || 'Ошибка обновления');
  };

  const handleToggleStatus = async (account) => {
    const action = account.status === 'ACTIVE' ? disableTwitterAccount : enableTwitterAccount;
    const res = await action(account._id);
    if (res.ok) { toast.success(`Аккаунт ${account.status === 'ACTIVE' ? 'отключён' : 'включён'}`); fetchAccounts(); }
    else toast.error(res.error || 'Ошибка');
  };

  const handleDelete = async (id) => {
    const res = await deleteTwitterAccount(id);
    if (res.ok) { toast.success('Аккаунт удалён'); setConfirmDelete(null); fetchAccounts(); }
    else toast.error(res.error || 'Ошибка удаления');
  };

  const handleForceDownload = async () => {
    try {
      const backendUrl = process.env.REACT_APP_BACKEND_URL || '';
      const response = await fetch(`${backendUrl}/api/admin/twitter-parser/download-parser`);
      
      if (!response.ok) {
        toast.error('Ошибка загрузки файла');
        return;
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'twitter-parser-v2.zip';
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();
      
      setTimeout(() => {
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }, 100);
      
      toast.success('Скачивание началось');
    } catch (err) {
      toast.error('Ошибка: ' + err.message);
    }
  };

  if (loading && accounts.length === 0) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6 space-y-6" data-testid="admin-accounts-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-900" data-testid="accounts-page-title">Аккаунты</h1>
            <p className="text-sm text-slate-400 mt-0.5">Twitter-аккаунты для парсинга</p>
          </div>
          <div className="flex items-center gap-2">
            <a
              href={`${process.env.REACT_APP_BACKEND_URL || ''}/api/admin/twitter-parser/download-parser`}
              download="twitter-parser-v2.zip"
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded transition-colors border border-blue-200"
              data-testid="btn-download-parser"
            >
              <Download className="w-4 h-4" />
              Скачать парсер
            </a>
            <button onClick={fetchAccounts} disabled={loading} className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded transition-colors" data-testid="btn-refresh">
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Обновить
            </button>
            <button onClick={() => { setEditingAccount(null); setShowDialog(true); }} className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-semibold text-slate-800 bg-slate-100 hover:bg-slate-200 rounded transition-colors" data-testid="btn-add-account">
              <Plus className="w-4 h-4" />
              Добавить
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-1 bg-slate-100/80 p-1 rounded-lg w-fit" data-testid="parser-tabs">
          <Link to="/admin/twitter-parser/accounts" className="px-3 py-1.5 text-sm font-medium text-slate-900 bg-white rounded shadow-sm">Аккаунты</Link>
          <Link to="/admin/twitter-parser/sessions" className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800 rounded transition-colors">Сессии</Link>
          <Link to="/admin/twitter-parser/slots" className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800 rounded transition-colors">Слоты</Link>
          <Link to="/admin/twitter-parser/monitor" className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800 rounded transition-colors">Мониторинг</Link>
        </div>

        {/* Download Instructions */}
        <div className="p-4 rounded-lg bg-blue-50 border border-blue-200" data-testid="download-instructions">
          <div className="flex items-start gap-3">
            <Download className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-blue-900">Скачивание Twitter Parser v2</h3>
              <p className="text-xs text-blue-700 mt-1">
                Если кнопка "Скачать парсер" не работает, попробуйте альтернативный метод ниже или используйте прямую ссылку:
              </p>
              <div className="mt-3 flex items-center gap-3">
                <button
                  onClick={handleForceDownload}
                  className="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded transition-colors"
                  data-testid="btn-force-download"
                >
                  Принудительная загрузка (JS)
                </button>
                <a
                  href={`${process.env.REACT_APP_BACKEND_URL || ''}/api/admin/twitter-parser/download-parser`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-600 hover:text-blue-800 underline"
                  data-testid="link-direct"
                >
                  Открыть в новой вкладке
                </a>
                <code className="text-xs text-blue-800 bg-blue-100 px-2 py-1 rounded">
                  Размер: 62 KB
                </code>
              </div>
            </div>
          </div>
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
            <div className="text-2xl font-bold text-slate-900">{accounts.length}</div>
            <div className="text-xs text-slate-500 mt-1">Всего аккаунтов</div>
          </div>
          <div className="p-4 rounded-lg bg-emerald-50" data-testid="stat-active">
            <div className="text-2xl font-bold text-emerald-700">{accounts.filter(a => a.status === 'ACTIVE').length}</div>
            <div className="text-xs text-slate-500 mt-1">Активных</div>
          </div>
          <div className="p-4 rounded-lg bg-slate-100" data-testid="stat-disabled">
            <div className="text-2xl font-bold text-slate-500">{accounts.filter(a => a.status === 'DISABLED').length}</div>
            <div className="text-xs text-slate-500 mt-1">Отключённых</div>
          </div>
          <div className="p-4 rounded-lg bg-amber-50" data-testid="stat-issues">
            <div className="text-2xl font-bold text-amber-700">{accounts.filter(a => a.status === 'NEEDS_LOGIN' || a.status === 'LOCKED').length}</div>
            <div className="text-xs text-slate-500 mt-1">С проблемами</div>
          </div>
        </div>

        {/* Accounts List */}
        <div className="p-5 rounded-2xl bg-slate-50/60 space-y-4">
          <span className="text-sm font-semibold text-slate-800">Список аккаунтов</span>

          {loading ? (
            <div className="text-center py-12">
              <RefreshCw className="w-6 h-6 animate-spin text-slate-400 mx-auto" />
            </div>
          ) : accounts.length === 0 ? (
            <div className="text-center py-12 text-slate-400">
              <User className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm">Аккаунты не настроены</p>
              <button onClick={() => { setEditingAccount(null); setShowDialog(true); }} className="mt-3 text-sm text-slate-600 hover:text-slate-900 underline" data-testid="add-first-account">
                Добавить первый аккаунт
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              {accounts.map((account) => (
                <div key={account._id} className="flex items-center justify-between p-4 rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors" data-testid={`account-${account.username}`}>
                  <div className="flex items-center gap-4">
                    <div className="w-9 h-9 rounded-full bg-slate-100 text-slate-500 flex items-center justify-center">
                      <User className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-slate-800">@{account.username}</div>
                      {account.displayName && <div className="text-xs text-slate-500">{account.displayName}</div>}
                      {account.notes && <div className="text-xs text-slate-400">{account.notes}</div>}
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-xs text-slate-400">Лимит: {account.rateLimit || 200}/ч</span>
                    <StatusIndicator status={account.status} />
                    <div className="flex gap-1">
                      <button onClick={() => handleToggleStatus(account)} className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded transition-colors" data-testid={`toggle-${account.username}`}>
                        {account.status === 'ACTIVE' ? <PowerOff className="w-4 h-4" /> : <Power className="w-4 h-4" />}
                      </button>
                      <button onClick={() => { setEditingAccount(account); setShowDialog(true); }} className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded transition-colors" data-testid={`edit-${account.username}`}>
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button onClick={() => setConfirmDelete(account)} className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors" data-testid={`delete-${account.username}`}>
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Create/Edit Dialog */}
        <Dialog open={showDialog} onOpenChange={setShowDialog}>
          <DialogContent className="bg-white">
            <DialogHeader>
              <DialogTitle className="text-slate-900">{editingAccount ? 'Редактировать аккаунт' : 'Добавить аккаунт'}</DialogTitle>
            </DialogHeader>
            <AccountForm
              account={editingAccount}
              onSave={editingAccount ? handleUpdate : handleCreate}
              onCancel={() => { setShowDialog(false); setEditingAccount(null); }}
            />
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation */}
        <Dialog open={!!confirmDelete} onOpenChange={() => setConfirmDelete(null)}>
          <DialogContent className="bg-white">
            <DialogHeader>
              <DialogTitle className="text-slate-900">Удалить аккаунт?</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-slate-600">
              Вы уверены, что хотите удалить <strong>@{confirmDelete?.username}</strong>? Это действие необратимо.
            </p>
            <DialogFooter>
              <Button variant="outline" size="sm" onClick={() => setConfirmDelete(null)} data-testid="cancel-delete">Отмена</Button>
              <Button size="sm" className="bg-red-500 hover:bg-red-600 text-white" onClick={() => handleDelete(confirmDelete._id)} data-testid="confirm-delete">Удалить</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </AdminLayout>
  );
}
