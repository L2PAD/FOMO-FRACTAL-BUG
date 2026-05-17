import React, { useState, useEffect, useCallback } from 'react';
import AdminLayout from '../../components/admin/AdminLayout';
import {
  Box, RefreshCw, AlertCircle, CheckCircle, Clock, XCircle, ArrowRight,
  Shield, Activity, GitBranch,
} from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { api } from '../../api/client';
import { Link } from 'react-router-dom';

const STATUS_CONFIG = {
  deployed:  { icon: CheckCircle, color: 'text-emerald-600', bg: 'bg-emerald-50', label: 'Deployed' },
  shadow:    { icon: Shield,      color: 'text-purple-600',  bg: 'bg-purple-50',  label: 'Shadow' },
  candidate: { icon: GitBranch,   color: 'text-blue-600',    bg: 'bg-blue-50',    label: 'Candidate' },
  retired:   { icon: XCircle,     color: 'text-gray-400',    bg: 'bg-gray-50',    label: 'Retired' },
  training:  { icon: Clock,       color: 'text-amber-600',   bg: 'bg-amber-50',   label: 'Training' },
};

export default function AdminModelRegistryPage() {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all');

  const loadModels = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get('/api/admin/ml/v3/models/shadow');
      const raw = res.data?.data?.models || res.data?.models || [];
      setModels(raw);
    } catch {
      setError('Не удалось загрузить реестр моделей');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadModels(); }, [loadModels]);

  const deployed = models.filter(m => m.status === 'deployed');
  const shadow = models.filter(m => m.status === 'shadow' || !m.status);
  const candidates = models.filter(m => m.status === 'candidate');

  const filtered = filter === 'all' ? models
    : filter === 'deployed' ? deployed
    : filter === 'shadow' ? shadow
    : candidates;

  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6 space-y-6">
        {/* Header — MetaBrain style */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Box className="w-5 h-5 text-blue-600" />
            <div>
              <h1 className="text-xl font-semibold text-slate-900">Реестр моделей</h1>
              <p className="text-xs text-gray-500">Управление жизненным циклом ML моделей</p>
            </div>
          </div>
          <button
            onClick={loadModels}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            data-testid="models-refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Обновить
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-3 p-4 bg-amber-50 rounded-lg">
            <AlertCircle className="w-5 h-5 text-amber-600" />
            <span className="text-sm text-amber-800">{error}</span>
          </div>
        )}

        {/* Filter tabs — identical to MetaBrain */}
        <Tabs value={filter} onValueChange={setFilter}>
          <TabsList className="bg-gray-100 flex-wrap h-auto gap-1 p-1" data-testid="models-tabs">
            {[
              { id: 'all', label: 'Все', count: models.length },
              { id: 'deployed', label: 'Deployed', count: deployed.length },
              { id: 'shadow', label: 'Shadow', count: shadow.length },
              { id: 'candidate', label: 'Кандидаты', count: candidates.length },
            ].map(f => (
              <TabsTrigger key={f.id} value={f.id}
                className="data-[state=active]:bg-white data-[state=active]:shadow-sm text-xs gap-1.5"
                data-testid={`models-filter-${f.id}`}>
                {f.label}
              </TabsTrigger>
            ))}
          </TabsList>

          {/* Content */}
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <RefreshCw className="w-6 h-6 text-gray-400 animate-spin" />
            </div>
          ) : models.length === 0 ? (
            <EmptyModels />
          ) : filtered.length === 0 ? (
            <div className="text-center py-12">
              <Box className="w-8 h-8 mx-auto mb-3 text-gray-300" />
              <p className="text-sm text-gray-500">Нет моделей в категории {filter}</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-2">
              {filtered.map(m => <ModelCard key={m._id || m.id} model={m} />)}
            </div>
          )}
        </Tabs>
      </div>
    </AdminLayout>
  );
}

function SummaryCard({ label, value, color }) {
  const colorCls = color === 'emerald' ? 'text-emerald-600'
    : color === 'purple' ? 'text-purple-600'
    : color === 'blue' ? 'text-blue-600'
    : 'text-gray-900';
  return (
    <div className="bg-gray-50/70 rounded-lg p-4">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={`text-2xl font-bold ${colorCls}`}>{value}</div>
    </div>
  );
}

function ModelCard({ model }) {
  const status = model.status || 'shadow';
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.shadow;
  const Icon = cfg.icon;

  return (
    <div className="bg-gray-50/70 rounded-lg p-4 hover:bg-gray-100/70 transition-colors" data-testid={`model-card-${model._id || model.id}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className={`flex items-center gap-1.5`}>
          <Icon className={`w-3.5 h-3.5 ${cfg.color}`} />
          <span className={`text-xs font-medium ${cfg.color}`}>{cfg.label}</span>
        </div>
        <span className="text-xs text-gray-400">{(model._id || model.id || '').slice(-8)}</span>
      </div>

      {/* Info */}
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-gray-400">Сеть</span>
          <span className="font-medium text-gray-700 capitalize">{model.network || '-'}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Задача</span>
          <span className="font-medium text-gray-700">{model.task || '-'}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Признаки</span>
          <span className="font-medium text-gray-700">{model.featureCount || model.features?.length || '-'}</span>
        </div>
        {model.version && (
          <div className="flex justify-between">
            <span className="text-gray-400">Версия</span>
            <span className="font-medium text-gray-700">{model.version}</span>
          </div>
        )}
      </div>

      {/* Metrics */}
      {model.metrics && (
        <div className="mt-3 pt-3 border-t border-gray-50 grid grid-cols-3 gap-2">
          <MetricCell label="F1" value={model.metrics.f1} />
          <MetricCell label="Accuracy" value={model.metrics.accuracy} />
          <MetricCell label="Recall" value={model.metrics.recall} />
        </div>
      )}

      {/* Created */}
      {model.createdAt && (
        <div className="mt-3 text-[11px] text-gray-400">
          Создано {new Date(model.createdAt).toLocaleDateString()}
        </div>
      )}
    </div>
  );
}

function MetricCell({ label, value }) {
  return (
    <div className="text-center p-1.5 bg-gray-50 rounded">
      <div className="font-medium text-sm text-gray-800">{value != null ? value.toFixed(3) : '-'}</div>
      <div className="text-[10px] text-gray-400">{label}</div>
    </div>
  );
}

function EmptyModels() {
  return (
    <div className="text-center py-16" data-testid="models-empty">
      <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gray-50 flex items-center justify-center">
        <Box className="w-8 h-8 text-gray-300" />
      </div>
      <p className="text-sm font-medium text-gray-600 mb-1">Модели не зарегистрированы</p>
      <p className="text-sm text-gray-400 mb-6">
        Training pipeline неактивен. Настройте Auto-Retrain для создания моделей.
      </p>
      <div className="flex items-center justify-center gap-4">
        <Link
          to="/admin/auto-retrain"
          className="inline-flex items-center gap-1.5 px-4 py-2 text-sm text-purple-600 hover:bg-purple-50 font-medium rounded-lg transition-colors"
        >
          Retrain Policies <ArrowRight className="w-3.5 h-3.5" />
        </Link>
        <Link
          to="/admin/ml/research"
          className="inline-flex items-center gap-1.5 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 font-medium rounded-lg transition-colors"
        >
          <Activity className="w-3.5 h-3.5" />
          Лаборатория
        </Link>
      </div>

      {/* ML Lifecycle diagram */}
      <div className="mt-8 mx-auto max-w-lg">
        <div className="text-xs text-gray-400 mb-3">Жизненный цикл ML</div>
        <div className="flex items-center justify-center gap-2 text-xs">
          <Step label="Dataset" active={false} />
          <Arrow />
          <Step label="Training" active={false} />
          <Arrow />
          <Step label="Shadow" active={false} />
          <Arrow />
          <Step label="Evaluation" active={false} />
          <Arrow />
          <Step label="Deploy" active={false} />
        </div>
      </div>
    </div>
  );
}

function Step({ label, active }) {
  return (
    <div className={`text-sm font-medium ${
      active ? 'text-blue-700' : 'text-gray-400'
    }`}>
      {label}
    </div>
  );
}

function Arrow() {
  return <div className="text-gray-300">&#8594;</div>;
}
