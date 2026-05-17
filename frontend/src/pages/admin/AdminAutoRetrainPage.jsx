/**
 * Admin Auto-Retrain Policies Page
 * 
 * Настройка политик автоматического переобучения моделей
 */

import { useState, useEffect, useCallback } from 'react';
import AdminLayout from '../../components/admin/AdminLayout';
import { 
  Settings, RefreshCw, Loader2, CheckCircle, XCircle,
  Cpu, Zap, Shield, Clock, TrendingDown, Activity,
  ChevronDown, ChevronUp, Play, AlertTriangle, HelpCircle,
  Layers, Scissors, Scale
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Switch } from '../../components/ui/switch';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../../components/ui/tooltip';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../../components/ui/dialog';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../../components/ui/tabs';

const API_BASE = process.env.REACT_APP_BACKEND_URL;

// ============ HELPERS ============
function InfoTip({ text }) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button className="text-gray-400 hover:text-gray-600 ml-1">
            <HelpCircle className="w-3.5 h-3.5" />
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs bg-white text-slate-900 border-gray-200">
          <p className="text-xs">{text}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// ============ POLICY CARD ============
function PolicyCard({ policy, onEdit, onDryRun, onTrigger, loading }) {
  const [expanded, setExpanded] = useState(false);
  const mlVersion = policy.mlVersion || 'v2.1';
  
  return (
    <div className={`bg-gray-50/70 rounded-xl ${!policy.enabled ? 'opacity-60' : ''} overflow-hidden`}>
      {/* Header */}
      <div className="p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${policy.enabled ? 'bg-green-50' : 'bg-slate-100/50'}`}>
            <Cpu className={`w-5 h-5 ${policy.enabled ? 'text-green-600' : 'text-slate-500'}`} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-900">{policy.task}</span>
              <span className="text-slate-600">/</span>
              <span className="text-slate-700">{policy.network}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className={`text-xs font-bold ${policy.enabled ? 'text-green-600' : 'text-slate-500'}`}>
                {policy.enabled ? 'Активна' : 'Выключена'}
              </span>
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDryRun(policy)}
            disabled={loading}
            className="text-slate-600 hover:text-slate-900"
          >
            <Play className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onEdit(policy)}
            className="text-slate-600 hover:text-slate-900"
          >
            <Settings className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setExpanded(!expanded)}
            className="text-slate-600 hover:text-slate-900"
          >
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </Button>
        </div>
      </div>
      
      {/* Expanded Content */}
      {expanded && (
        <div className="px-4 pb-4 pt-4">
          <div className="grid grid-cols-2 gap-4">
            {/* Triggers */}
            <div>
              <h4 className="text-xs font-medium text-slate-500 uppercase mb-2">Триггеры</h4>
              <div className="space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">Accuracy</span>
                  <span className={policy.triggers?.accuracy?.enabled ? 'text-green-600' : 'text-slate-500'}>
                    {policy.triggers?.accuracy?.enabled ? `< ${(policy.triggers.accuracy.minAccuracy7d * 100).toFixed(0)}%` : 'Выкл'}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">Drift</span>
                  <span className={policy.triggers?.drift?.enabled ? 'text-amber-600' : 'text-slate-500'}>
                    {policy.triggers?.drift?.enabled ? policy.triggers.drift.minLevel : 'Выкл'}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">Время</span>
                  <span className={policy.triggers?.time?.enabled ? 'text-blue-600' : 'text-slate-500'}>
                    {policy.triggers?.time?.enabled ? `> ${policy.triggers.time.maxHoursSinceRetrain}ч` : 'Выкл'}
                  </span>
                </div>
              </div>
            </div>
            
            {/* Guards */}
            <div>
              <h4 className="text-xs font-medium text-slate-500 uppercase mb-2">Ограничения</h4>
              <div className="space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">Cooldown</span>
                  <span className="text-slate-700">{policy.guards?.cooldownMinutes}мин</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">Макс/день</span>
                  <span className="text-slate-700">{policy.guards?.maxJobsPerDay}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">Мин строк</span>
                  <span className="text-slate-700">{policy.guards?.minRows}</span>
                </div>
              </div>
            </div>
          </div>
          
          {/* v2.3 Config */}
          {mlVersion === 'v2.3' && policy.v23Config && (
            <div className="mt-4 p-3 bg-purple-50/70 rounded-lg">
              <h4 className="text-xs font-medium text-purple-600 uppercase mb-2 flex items-center gap-1">
                <Scissors className="w-3 h-3" />
                Расширенные настройки
              </h4>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-600">Pruning</span>
                  <span className="text-purple-700">{policy.v23Config.pruningMode}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-600">Weighting</span>
                  <span className="text-purple-700">{policy.v23Config.weightingMode}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-600">Мин признаков</span>
                  <span className="text-purple-700">{policy.v23Config.minFeatures}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-600">Макс. удаление %</span>
                  <span className="text-purple-700">{policy.v23Config.maxFeatureDropPct}%</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============ EDIT MODAL ============
function PolicyEditModal({ policy, open, onClose, onSave, loading }) {
  const [form, setForm] = useState({
    enabled: false,
    mlVersion: 'v2.1',
    triggers: {
      accuracy: { enabled: false, minAccuracy7d: 0.55 },
      drift: { enabled: false, minLevel: 'HIGH' },
      time: { enabled: false, maxHoursSinceRetrain: 48 }
    },
    guards: {
      cooldownMinutes: 360,
      maxJobsPerDay: 2,
      minRows: 500
    },
    v23Config: {
      pruningMode: 'FULL',
      weightingMode: 'FULL',
      minFeatures: 5,
      maxFeatureDropPct: 40
    }
  });

  useEffect(() => {
    if (policy) {
      setForm({
        enabled: policy.enabled || false,
        mlVersion: policy.mlVersion || 'v2.1',
        triggers: {
          accuracy: policy.triggers?.accuracy || { enabled: false, minAccuracy7d: 0.55 },
          drift: policy.triggers?.drift || { enabled: false, minLevel: 'HIGH' },
          time: policy.triggers?.time || { enabled: false, maxHoursSinceRetrain: 48 }
        },
        guards: {
          cooldownMinutes: policy.guards?.cooldownMinutes || 360,
          maxJobsPerDay: policy.guards?.maxJobsPerDay || 2,
          minRows: policy.guards?.minRows || 500
        },
        v23Config: policy.v23Config || {
          pruningMode: 'FULL',
          weightingMode: 'FULL',
          minFeatures: 5,
          maxFeatureDropPct: 40
        }
      });
    }
  }, [policy]);

  const handleSave = () => {
    onSave(form);
  };

  if (!policy) return null;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="bg-white text-slate-900 max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-blue-600" />
            Редактирование: {policy.task}/{policy.network}
          </DialogTitle>
          <DialogDescription className="text-slate-600">
            Настройка триггеров, ограничений и версии ML
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="general" className="mt-4">
          <TabsList className="bg-gray-100">
            <TabsTrigger value="general" className="data-[state=active]:bg-white">Общие</TabsTrigger>
            <TabsTrigger value="triggers" className="data-[state=active]:bg-white">Триггеры</TabsTrigger>
            <TabsTrigger value="guards" className="data-[state=active]:bg-white">Ограничения</TabsTrigger>
            <TabsTrigger value="ml" className="data-[state=active]:bg-white">ML Версия</TabsTrigger>
          </TabsList>

          {/* General */}
          <TabsContent value="general" className="mt-4 space-y-4">
            <div className="flex items-center justify-between p-4 bg-white rounded-lg">
              <div>
                <Label className="text-slate-900">Политика включена</Label>
                <p className="text-xs text-slate-600 mt-1">Включить Auto-Retrain для этой задачи/сети</p>
              </div>
              <Switch
                checked={form.enabled}
                onCheckedChange={(checked) => setForm({ ...form, enabled: checked })}
              />
            </div>
          </TabsContent>

          {/* Triggers */}
          <TabsContent value="triggers" className="mt-4 space-y-4">
            {/* Accuracy Trigger */}
            <div className="p-4 bg-white rounded-lg">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <TrendingDown className="w-4 h-4 text-red-600" />
                  <Label className="text-slate-900">Accuracy Drop</Label>
                  <InfoTip text="Запуск переобучения при снижении accuracy за 7 дней ниже порога" />
                </div>
                <Switch
                  checked={form.triggers.accuracy.enabled}
                  onCheckedChange={(checked) => setForm({
                    ...form,
                    triggers: { ...form.triggers, accuracy: { ...form.triggers.accuracy, enabled: checked } }
                  })}
                />
              </div>
              {form.triggers.accuracy.enabled && (
                <div className="flex items-center gap-2">
                  <Label className="text-slate-600 text-sm">Порог:</Label>
                  <Input
                    type="number"
                    value={(form.triggers.accuracy.minAccuracy7d * 100).toFixed(0)}
                    onChange={(e) => setForm({
                      ...form,
                      triggers: { ...form.triggers, accuracy: { ...form.triggers.accuracy, minAccuracy7d: parseFloat(e.target.value) / 100 } }
                    })}
                    className="w-20 bg-slate-100 border-slate-300 text-slate-900"
                    min={0}
                    max={100}
                  />
                  <span className="text-slate-600">%</span>
                </div>
              )}
            </div>

            {/* Drift Trigger */}
            <div className="p-4 bg-white rounded-lg">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-amber-600" />
                  <Label className="text-slate-900">Drift Level</Label>
                  <InfoTip text="Запуск переобучения при достижении указанного уровня дрифта" />
                </div>
                <Switch
                  checked={form.triggers.drift.enabled}
                  onCheckedChange={(checked) => setForm({
                    ...form,
                    triggers: { ...form.triggers, drift: { ...form.triggers.drift, enabled: checked } }
                  })}
                />
              </div>
              {form.triggers.drift.enabled && (
                <Select
                  value={form.triggers.drift.minLevel}
                  onValueChange={(value) => setForm({
                    ...form,
                    triggers: { ...form.triggers, drift: { ...form.triggers.drift, minLevel: value } }
                  })}
                >
                  <SelectTrigger className="w-32 bg-slate-100 border-slate-300 text-slate-900">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-white">
                    <SelectItem value="LOW">LOW</SelectItem>
                    <SelectItem value="MEDIUM">MEDIUM</SelectItem>
                    <SelectItem value="HIGH">HIGH</SelectItem>
                  </SelectContent>
                </Select>
              )}
            </div>

            {/* Time Trigger */}
            <div className="p-4 bg-white rounded-lg">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-blue-600" />
                  <Label className="text-slate-900">Time Elapsed</Label>
                  <InfoTip text="Запуск переобучения после указанного количества часов с последнего обучения" />
                </div>
                <Switch
                  checked={form.triggers.time.enabled}
                  onCheckedChange={(checked) => setForm({
                    ...form,
                    triggers: { ...form.triggers, time: { ...form.triggers.time, enabled: checked } }
                  })}
                />
              </div>
              {form.triggers.time.enabled && (
                <div className="flex items-center gap-2">
                  <Label className="text-slate-600 text-sm">Макс часов:</Label>
                  <Input
                    type="number"
                    value={form.triggers.time.maxHoursSinceRetrain}
                    onChange={(e) => setForm({
                      ...form,
                      triggers: { ...form.triggers, time: { ...form.triggers.time, maxHoursSinceRetrain: parseInt(e.target.value) } }
                    })}
                    className="w-20 bg-slate-100 border-slate-300 text-slate-900"
                    min={1}
                  />
                  <span className="text-slate-600">часов</span>
                </div>
              )}
            </div>
          </TabsContent>

          {/* Guards */}
          <TabsContent value="guards" className="mt-4 space-y-4">
            <div className="p-4 bg-white rounded-lg space-y-4">
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-green-600" />
                <Label className="text-slate-900">Safety Guards</Label>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <Label className="text-slate-600 text-sm">Cooldown (мин)</Label>
                  <Input
                    type="number"
                    value={form.guards.cooldownMinutes}
                    onChange={(e) => setForm({
                      ...form,
                      guards: { ...form.guards, cooldownMinutes: parseInt(e.target.value) }
                    })}
                    className="mt-1 bg-slate-100 border-slate-300 text-slate-900"
                    min={1}
                  />
                </div>
                <div>
                  <Label className="text-slate-600 text-sm">Макс задач/день</Label>
                  <Input
                    type="number"
                    value={form.guards.maxJobsPerDay}
                    onChange={(e) => setForm({
                      ...form,
                      guards: { ...form.guards, maxJobsPerDay: parseInt(e.target.value) }
                    })}
                    className="mt-1 bg-slate-100 border-slate-300 text-slate-900"
                    min={1}
                  />
                </div>
                <div>
                  <Label className="text-slate-600 text-sm">Мин строк</Label>
                  <Input
                    type="number"
                    value={form.guards.minRows}
                    onChange={(e) => setForm({
                      ...form,
                      guards: { ...form.guards, minRows: parseInt(e.target.value) }
                    })}
                    className="mt-1 bg-slate-100 border-slate-300 text-slate-900"
                    min={1}
                  />
                </div>
              </div>
            </div>
          </TabsContent>

          {/* ML Version */}
          <TabsContent value="ml" className="mt-4 space-y-4">
            {/* Version Selection */}
            <div className="p-4 bg-white rounded-lg">
              <div className="flex items-center gap-2 mb-4">
                <Layers className="w-4 h-4 text-purple-600" />
                <Label className="text-slate-900">ML Training Version</Label>
                <InfoTip text="Classic — стандартное обучение. Advanced — с pruning и weighting признаков" />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <button
                  onClick={() => setForm({ ...form, mlVersion: 'v2.1' })}
                  className={`p-4 rounded-lg text-left transition-all ${
                    form.mlVersion === 'v2.1'
                      ? 'bg-blue-50/70 ring-2 ring-blue-400'
                      : 'bg-gray-50/70 hover:bg-gray-100/70'
                  }`}
                >
                  <div className="font-semibold text-slate-900">Classic</div>
                  <div className="text-xs text-slate-600 mt-1">Стандартное обучение без манипуляции признаками</div>
                </button>
                <button
                  onClick={() => setForm({ ...form, mlVersion: 'v2.3' })}
                  className={`p-4 rounded-lg text-left transition-all ${
                    form.mlVersion === 'v2.3'
                      ? 'bg-purple-50/70 ring-2 ring-purple-400'
                      : 'bg-gray-50/70 hover:bg-gray-100/70'
                  }`}
                >
                  <div className="font-semibold text-slate-900 flex items-center gap-2">
                    Advanced
                    <span className="text-xs font-bold text-purple-700">NEW</span>
                  </div>
                  <div className="text-xs text-slate-600 mt-1">Feature pruning + sample weighting</div>
                </button>
              </div>
            </div>

            {/* v2.3 Config */}
            {form.mlVersion === 'v2.3' && (
              <div className="p-4 bg-purple-50/70 rounded-lg">
                <div className="flex items-center gap-2 mb-4">
                  <Scissors className="w-4 h-4 text-purple-600" />
                  <Label className="text-slate-900">Расширенные настройки</Label>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  {/* Pruning Mode */}
                  <div>
                    <Label className="text-slate-600 text-sm flex items-center gap-1">
                      Pruning Mode
                      <InfoTip text="OFF = без pruning, FULL = variance + correlation + importance" />
                    </Label>
                    <Select
                      value={form.v23Config.pruningMode}
                      onValueChange={(value) => setForm({
                        ...form,
                        v23Config: { ...form.v23Config, pruningMode: value }
                      })}
                    >
                      <SelectTrigger className="mt-1 bg-slate-100 border-slate-300 text-slate-900">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-white">
                        <SelectItem value="OFF">OFF</SelectItem>
                        <SelectItem value="BASIC">BASIC (variance only)</SelectItem>
                        <SelectItem value="CORRELATION">CORRELATION</SelectItem>
                        <SelectItem value="IMPORTANCE">IMPORTANCE</SelectItem>
                        <SelectItem value="FULL">FULL (all)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Weighting Mode */}
                  <div>
                    <Label className="text-slate-600 text-sm flex items-center gap-1">
                      Weighting Mode
                      <InfoTip text="OFF = равные веса, FULL = time decay + strong boost + class balance" />
                    </Label>
                    <Select
                      value={form.v23Config.weightingMode}
                      onValueChange={(value) => setForm({
                        ...form,
                        v23Config: { ...form.v23Config, weightingMode: value }
                      })}
                    >
                      <SelectTrigger className="mt-1 bg-slate-100 border-slate-300 text-slate-900">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-white">
                        <SelectItem value="OFF">OFF</SelectItem>
                        <SelectItem value="TIME_DECAY">TIME_DECAY</SelectItem>
                        <SelectItem value="CLASS_WEIGHT">CLASS_WEIGHT</SelectItem>
                        <SelectItem value="FULL">FULL (all)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Safety Guards */}
                  <div>
                    <Label className="text-slate-600 text-sm flex items-center gap-1">
                      Min Features
                      <InfoTip text="Минимальное количество признаков после pruning (предохранитель)" />
                    </Label>
                    <Input
                      type="number"
                      value={form.v23Config.minFeatures}
                      onChange={(e) => setForm({
                        ...form,
                        v23Config: { ...form.v23Config, minFeatures: parseInt(e.target.value) }
                      })}
                      className="mt-1 bg-slate-100 border-slate-300 text-slate-900"
                      min={1}
                    />
                  </div>

                  <div>
                    <Label className="text-slate-600 text-sm flex items-center gap-1">
                      Max Drop %
                      <InfoTip text="Максимальный процент признаков, которые могут быть удалены (предохранитель)" />
                    </Label>
                    <Input
                      type="number"
                      value={form.v23Config.maxFeatureDropPct}
                      onChange={(e) => setForm({
                        ...form,
                        v23Config: { ...form.v23Config, maxFeatureDropPct: parseInt(e.target.value) }
                      })}
                      className="mt-1 bg-slate-100 border-slate-300 text-slate-900"
                      min={0}
                      max={100}
                    />
                  </div>
                </div>
              </div>
            )}
          </TabsContent>
        </Tabs>

        <DialogFooter className="mt-6">
          <Button variant="ghost" onClick={onClose} className="text-slate-700 hover:bg-gray-100">
            Отмена
          </Button>
          <Button onClick={handleSave} disabled={loading} className="bg-blue-600 hover:bg-blue-700">
            {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            Сохранить
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ============ MAIN PAGE ============
export default function AdminAutoRetrainPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [policies, setPolicies] = useState([]);
  const [summary, setSummary] = useState({ total: 0, enabled: 0, disabled: 0 });
  const [editPolicy, setEditPolicy] = useState(null);
  const [dryRunResult, setDryRunResult] = useState(null);

  // Fetch policies
  const fetchPolicies = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem('admin_token');
      if (!token) { setError('Необходима авторизация'); setLoading(false); return; }
      const res = await fetch(`${API_BASE}/api/admin/auto-retrain/policies`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) { setError(`Ошибка сервера: ${res.status}`); setLoading(false); return; }
      const data = await res.json();
      if (data.ok) {
        setPolicies(data.policies || []);
        setSummary(data.summary || { total: 0, enabled: 0, disabled: 0 });
      } else {
        setError(data.error || 'Не удалось загрузить политики');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPolicies();
  }, [fetchPolicies]);

  // Save policy
  const handleSavePolicy = async (form) => {
    if (!editPolicy) return;
    setSaving(true);
    setError(null);
    try {
      const token = localStorage.getItem('admin_token');
      const res = await fetch(`${API_BASE}/api/admin/auto-retrain/policies/${editPolicy.task}/${editPolicy.network}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(form)
      });
      const data = await res.json();
      if (data.ok) {
        setSuccess(`Политика ${editPolicy.task}/${editPolicy.network} обновлена`);
        setEditPolicy(null);
        fetchPolicies();
      } else {
        setError(data.error || 'Не удалось сохранить политику');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  // Dry run
  const handleDryRun = async (policy) => {
    try {
      const token = localStorage.getItem('admin_token');
      const res = await fetch(`${API_BASE}/api/admin/auto-retrain/dry-run/${policy.task}/${policy.network}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      setDryRunResult({
        task: policy.task,
        network: policy.network,
        ...data
      });
    } catch (err) {
      setError(err.message);
    }
  };

  // Manual trigger
  const handleTrigger = async (policy) => {
    try {
      const token = localStorage.getItem('admin_token');
      const res = await fetch(`${API_BASE}/api/admin/auto-retrain/run/${policy.task}/${policy.network}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.ok && data.enqueued) {
        setSuccess(`Retrain запущен для ${policy.task}/${policy.network}`);
        fetchPolicies();
      } else {
        setError(data.reason || data.reasons?.join(', ') || 'Запуск пропущен');
      }
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className="space-y-6" data-testid="admin-auto-retrain-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <Zap className="w-5 h-5 text-purple-600" />
              <h1 className="text-xl font-semibold text-slate-900">Auto-Retrain Policies</h1>
            </div>
            <p className="text-sm text-gray-500 mt-1 ml-8">
              Автоматическое переобучение моделей с оптимизацией признаков
            </p>
          </div>
          <Button
            variant="ghost"
            onClick={fetchPolicies}
            disabled={loading}
            className="text-slate-700 hover:bg-gray-100"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Обновить
          </Button>
        </div>

        {/* Messages */}
        {error && (
          <div className="p-4 bg-red-50/70 rounded-lg flex items-center gap-2 text-red-600">
            <AlertTriangle className="w-5 h-5" />
            {error}
            <button onClick={() => setError(null)} className="ml-auto text-red-600 hover:text-red-300">✕</button>
          </div>
        )}
        {success && (
          <div className="p-4 bg-green-50/70 rounded-lg flex items-center gap-2 text-green-600">
            <CheckCircle className="w-5 h-5" />
            {success}
            <button onClick={() => setSuccess(null)} className="ml-auto text-green-600 hover:text-green-300">✕</button>
          </div>
        )}

        {/* Summary */}
        <div className="grid grid-cols-3 gap-4">
          <div className="p-4 bg-gray-50/70 rounded-lg text-center">
            <p className="text-xs text-slate-500 uppercase">Всего политик</p>
            <p className="text-2xl font-bold text-slate-900">{summary.total}</p>
          </div>
          <div className="p-4 bg-green-50/70 rounded-lg text-center">
            <p className="text-xs text-green-600 uppercase">Активные</p>
            <p className="text-2xl font-bold text-green-600">{summary.enabled}</p>
          </div>
          <div className="p-4 bg-gray-50/70 rounded-lg text-center">
            <p className="text-xs text-slate-500 uppercase">Выключенные</p>
            <p className="text-2xl font-bold text-slate-600">{summary.disabled}</p>
          </div>
        </div>

        {/* Dry Run Result */}
        {dryRunResult && (
          <div className={`p-4 rounded-lg ${dryRunResult.wouldEnqueue ? 'bg-amber-50/70' : 'bg-gray-50/70'}`}>
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-slate-900">Dry Run: {dryRunResult.task}/{dryRunResult.network}</h3>
                <p className="text-sm text-slate-600 mt-1">
                  Будет запущено: <span className={dryRunResult.wouldEnqueue ? 'text-amber-600' : 'text-slate-500'}>
                    {dryRunResult.wouldEnqueue ? 'ДА' : 'НЕТ'}
                  </span>
                  {dryRunResult.reason && ` — ${dryRunResult.reason}`}
                  {dryRunResult.reasons && ` — ${dryRunResult.reasons.join(', ')}`}
                </p>
                {dryRunResult.mlVersion && (
                  <p className="text-sm text-purple-600 mt-1">ML Version: {dryRunResult.mlVersion}</p>
                )}
              </div>
              <button onClick={() => setDryRunResult(null)} className="text-slate-600 hover:text-slate-900">✕</button>
            </div>
          </div>
        )}

        {/* Policies Grid */}
        <div className="grid gap-4 md:grid-cols-2">
          {policies.map((policy) => (
            <PolicyCard
              key={`${policy.task}-${policy.network}`}
              policy={policy}
              onEdit={setEditPolicy}
              onDryRun={handleDryRun}
              onTrigger={handleTrigger}
              loading={loading}
            />
          ))}
        </div>

        {/* Edit Modal */}
        <PolicyEditModal
          policy={editPolicy}
          open={!!editPolicy}
          onClose={() => setEditPolicy(null)}
          onSave={handleSavePolicy}
          loading={saving}
        />
      </div>
    </AdminLayout>
  );
}
