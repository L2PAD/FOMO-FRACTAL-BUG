/**
 * Twitter Parser — Слоты
 * Управление Egress-слотами (Proxy / Railway / Mock)
 */

import { useState, useEffect, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import AdminLayout from '../../components/admin/AdminLayout';
import {
  getEgressSlots,
  createEgressSlot,
  updateEgressSlot,
  deleteEgressSlot,
  getTwitterAccounts,
  testSlotConnection,
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import {
  Plus,
  RefreshCw,
  Pencil,
  Trash2,
  Server,
  Globe,
  Zap,
  AlertTriangle,
  Link2,
  User,
  Wifi,
  Loader2,
  CheckCircle,
} from 'lucide-react';
import { toast } from 'sonner';

/* ── Type indicator (text only) ── */
const TYPE_CFG = {
  PROXY:         { label: 'Proxy',   icon: Globe,  cls: 'text-blue-700' },
  REMOTE_WORKER: { label: 'Railway', icon: Server, cls: 'text-purple-700' },
  MOCK:          { label: 'Mock',    icon: Zap,    cls: 'text-amber-700' },
};

function TypeIndicator({ type }) {
  const c = TYPE_CFG[type] || TYPE_CFG.MOCK;
  const Icon = c.icon;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium ${c.cls}`}>
      <Icon className="w-3.5 h-3.5" />
      {c.label}
    </span>
  );
}

/* ── Health indicator (text only) ── */
const HEALTH_CFG = {
  HEALTHY: { label: 'Здоров', cls: 'text-emerald-700' },
  DEGRADED: { label: 'Деградация', cls: 'text-amber-700' },
  ERROR:   { label: 'Ошибка', cls: 'text-red-500' },
  UNKNOWN: { label: 'Неизвестно', cls: 'text-slate-400' },
};

function HealthIndicator({ health }) {
  const c = HEALTH_CFG[health?.status] || HEALTH_CFG.UNKNOWN;
  return <span className={`text-xs font-medium ${c.cls}`}>{c.label}</span>;
}

/* ── Slot Form ── */
function SlotForm({ slot, accounts, onSave, onCancel }) {
  const [label, setLabel] = useState(slot?.label || '');
  const [type, setType] = useState(slot?.type || 'MOCK');
  const [baseUrl, setBaseUrl] = useState(slot?.worker?.baseUrl || '');
  const [proxyUrl, setProxyUrl] = useState(slot?.proxy?.url || '');
  const [accountId, setAccountId] = useState(slot?.boundAccountId || slot?.accountId || '');
  const [limitPerHour, setLimitPerHour] = useState(slot?.limits?.requestsPerHour || 200);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!label.trim()) { toast.error('Укажите название'); return; }
    setLoading(true);
    try {
      const data = {
        label: label.trim(),
        type,
        enabled: true,
        limits: { requestsPerHour: parseInt(limitPerHour) || 200 },
      };
      if (type === 'REMOTE_WORKER' && baseUrl) data.worker = { baseUrl: baseUrl.trim() };
      if (type === 'PROXY' && proxyUrl) data.proxy = { url: proxyUrl.trim() };
      if (accountId) data.boundAccountId = accountId;
      await onSave(data);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="text-xs font-medium text-slate-500 block mb-1">Название *</label>
        <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Railway-EU-01" />
      </div>
      <div>
        <label className="text-xs font-medium text-slate-500 block mb-1">Тип *</label>
        <Select value={type} onValueChange={setType}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="MOCK">Mock (Разработка)</SelectItem>
            <SelectItem value="PROXY">Proxy</SelectItem>
            <SelectItem value="REMOTE_WORKER">Railway / Remote Worker</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {type === 'REMOTE_WORKER' && (
        <div>
          <label className="text-xs font-medium text-slate-500 block mb-1">Base URL</label>
          <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://your-parser.up.railway.app" />
        </div>
      )}
      {type === 'PROXY' && (
        <div>
          <label className="text-xs font-medium text-slate-500 block mb-1">Proxy URL</label>
          <Input value={proxyUrl} onChange={(e) => setProxyUrl(e.target.value)} placeholder="http://proxy:port" />
        </div>
      )}
      <div>
        <label className="text-xs font-medium text-slate-500 block mb-1">Привязанный аккаунт</label>
        <Select value={accountId || 'none'} onValueChange={(val) => setAccountId(val === 'none' ? '' : val)}>
          <SelectTrigger><SelectValue placeholder="Нет" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="none">Нет</SelectItem>
            {accounts.map((a) => (
              <SelectItem key={a._id} value={a._id}>{a.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div>
        <label className="text-xs font-medium text-slate-500 block mb-1">Лимит в час</label>
        <Input type="number" value={limitPerHour} onChange={(e) => setLimitPerHour(e.target.value)} min={10} max={1000} />
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" size="sm" onClick={onCancel}>Отмена</Button>
        <Button type="submit" size="sm" disabled={loading}>{loading ? 'Сохранение...' : (slot ? 'Обновить' : 'Создать')}</Button>
      </DialogFooter>
    </form>
  );
}

export default function TwitterParserSlotsPage() {
  const navigate = useNavigate();

  const [slots, setSlots] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [showDialog, setShowDialog] = useState(false);
  const [editingSlot, setEditingSlot] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [testingSlot, setTestingSlot] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [slotsRes, accountsRes] = await Promise.all([
        getEgressSlots(),
        getTwitterAccounts(),
      ]);
      if (slotsRes.ok) setSlots(slotsRes.data || []);
      if (accountsRes.ok) setAccounts(accountsRes.data || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCreate = async (data) => {
    const res = await createEgressSlot(data);
    if (res.ok) { toast.success('Слот создан'); setShowDialog(false); fetchData(); }
    else toast.error(res.error || 'Ошибка создания');
  };

  const handleUpdate = async (data) => {
    const res = await updateEgressSlot(editingSlot._id, data);
    if (res.ok) { toast.success('Слот обновлён'); setShowDialog(false); setEditingSlot(null); fetchData(); }
    else toast.error(res.error || 'Ошибка обновления');
  };

  const handleDelete = async (id) => {
    const res = await deleteEgressSlot(id);
    if (res.ok) { toast.success('Слот удалён'); setConfirmDelete(null); fetchData(); }
    else toast.error(res.error || 'Ошибка удаления');
  };

  const handleTestConnection = async (slot) => {
    setTestingSlot(slot._id);
    try {
      const res = await testSlotConnection(slot._id);
      if (res.ok && res.data?.status?.ok) {
        toast.success(`Соединение OK! Статус: ${res.data.status.status || 'READY'}`);
      } else if (res.ok) {
        toast.warning(`Проблема: ${res.data?.status?.message || 'Неизвестный статус'}`);
      } else {
        toast.error(res.error || 'Тест соединения не пройден');
      }
      fetchData();
    } catch (err) {
      toast.error('Ошибка теста: ' + (err.message || 'Сетевая ошибка'));
    } finally {
      setTestingSlot(null);
    }
  };

  const getAccountLabel = (id) => {
    const acc = accounts.find(a => a._id === id);
    return acc?.label || 'Не привязан';
  };


  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6 space-y-6" data-testid="admin-slots-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-900" data-testid="slots-page-title">Слоты</h1>
            <p className="text-sm text-slate-400 mt-0.5">Egress-каналы: Proxy, Railway, Mock</p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={fetchData} disabled={loading} className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded transition-colors" data-testid="btn-refresh">
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Обновить
            </button>
            <button onClick={() => { setEditingSlot(null); setShowDialog(true); }} className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-semibold text-slate-800 bg-slate-100 hover:bg-slate-200 rounded transition-colors" data-testid="btn-add-slot">
              <Plus className="w-4 h-4" />
              Добавить
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-1 bg-slate-100/80 p-1 rounded-lg w-fit" data-testid="parser-tabs">
          <Link to="/admin/twitter-parser/accounts" className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800 rounded transition-colors">Аккаунты</Link>
          <Link to="/admin/twitter-parser/sessions" className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800 rounded transition-colors">Сессии</Link>
          <Link to="/admin/twitter-parser/slots" className="px-3 py-1.5 text-sm font-medium text-slate-900 bg-white rounded shadow-sm">Слоты</Link>
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
            <div className="text-2xl font-bold text-slate-900">{slots.length}</div>
            <div className="text-xs text-slate-500 mt-1">Всего слотов</div>
          </div>
          <div className="p-4 rounded-lg bg-purple-50" data-testid="stat-railway">
            <div className="text-2xl font-bold text-purple-700">{slots.filter(s => s.type === 'REMOTE_WORKER').length}</div>
            <div className="text-xs text-slate-500 mt-1">Railway</div>
          </div>
          <div className="p-4 rounded-lg bg-blue-50" data-testid="stat-proxy">
            <div className="text-2xl font-bold text-blue-700">{slots.filter(s => s.type === 'PROXY').length}</div>
            <div className="text-xs text-slate-500 mt-1">Proxy</div>
          </div>
          <div className="p-4 rounded-lg bg-amber-50" data-testid="stat-mock">
            <div className="text-2xl font-bold text-amber-700">{slots.filter(s => s.type === 'MOCK').length}</div>
            <div className="text-xs text-slate-500 mt-1">Mock</div>
          </div>
        </div>

        {/* Slots List */}
        <div className="p-5 rounded-2xl bg-slate-50/60 space-y-4">
          <span className="text-sm font-semibold text-slate-800">Настроенные слоты</span>

          {loading ? (
            <div className="text-center py-12">
              <RefreshCw className="w-6 h-6 animate-spin text-slate-400 mx-auto" />
            </div>
          ) : slots.length === 0 ? (
            <div className="text-center py-12 text-slate-400">
              <Server className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm">Слоты не настроены</p>
              <button onClick={() => { setEditingSlot(null); setShowDialog(true); }} className="mt-3 text-sm text-slate-600 hover:text-slate-900 underline" data-testid="add-first-slot">
                Добавить первый слот
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              {slots.map((slot) => (
                <div key={slot._id} className="p-4 rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors" data-testid={`slot-${slot.label}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-9 h-9 rounded-full bg-slate-100 text-slate-500 flex items-center justify-center">
                        {slot.type === 'REMOTE_WORKER' ? <Server className="w-4 h-4" /> :
                         slot.type === 'PROXY' ? <Globe className="w-4 h-4" /> :
                         <Zap className="w-4 h-4" />}
                      </div>
                      <div>
                        <div className="text-sm font-medium text-slate-800">{slot.label}</div>
                        <div className="text-xs text-slate-400">
                          {slot.type === 'REMOTE_WORKER' && slot.worker?.baseUrl && (
                            <span className="flex items-center gap-1"><Link2 className="w-3 h-3" />{slot.worker.baseUrl}</span>
                          )}
                          {slot.type === 'PROXY' && slot.proxy?.url && (
                            <span className="flex items-center gap-1"><Globe className="w-3 h-3" />{slot.proxy.url}</span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <TypeIndicator type={slot.type} />
                      <HealthIndicator health={slot.health} />
                      <span className="text-xs text-slate-400 flex items-center gap-1">
                        <User className="w-3 h-3" />
                        {getAccountLabel(slot.boundAccountId)}
                      </span>
                      <div className="flex gap-1">
                        <button
                          onClick={() => handleTestConnection(slot)}
                          disabled={testingSlot === slot._id}
                          className="flex items-center gap-1 px-2 py-1 text-xs text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded transition-colors"
                          data-testid={`test-slot-${slot.label}`}
                        >
                          <Wifi className={`w-3.5 h-3.5 ${testingSlot === slot._id ? 'animate-pulse' : ''}`} />
                          {testingSlot === slot._id ? '...' : 'Тест'}
                        </button>
                        <button onClick={() => { setEditingSlot(slot); setShowDialog(true); }} className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded transition-colors" data-testid={`edit-slot-${slot.label}`}>
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button onClick={() => setConfirmDelete(slot)} className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors" data-testid={`delete-slot-${slot.label}`}>
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                  {/* Usage */}
                  <div className="mt-3 pt-3">
                    <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
                      <span>Использование за час</span>
                      <span>{slot.usage?.usedInWindow || 0} / {slot.limits?.requestsPerHour || 200}</span>
                    </div>
                    <div className="h-1.5 bg-slate-200/60 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-slate-400 rounded-full transition-all"
                        style={{ width: `${((slot.usage?.usedInWindow || 0) / (slot.limits?.requestsPerHour || 200)) * 100}%` }}
                      />
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
              <DialogTitle className="text-slate-900">{editingSlot ? 'Редактировать слот' : 'Добавить слот'}</DialogTitle>
            </DialogHeader>
            <SlotForm
              slot={editingSlot}
              accounts={accounts}
              onSave={editingSlot ? handleUpdate : handleCreate}
              onCancel={() => { setShowDialog(false); setEditingSlot(null); }}
            />
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation */}
        <Dialog open={!!confirmDelete} onOpenChange={() => setConfirmDelete(null)}>
          <DialogContent className="bg-white">
            <DialogHeader>
              <DialogTitle className="text-slate-900">Удалить слот?</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-slate-600">
              Вы уверены, что хотите удалить «{confirmDelete?.label}»? Это действие необратимо.
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
