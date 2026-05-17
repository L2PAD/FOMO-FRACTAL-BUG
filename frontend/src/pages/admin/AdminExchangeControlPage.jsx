/**
 * Exchange Admin Page
 * ====================
 * 
 * Unified admin control for Exchange module.
 * Tabs: Обзор, Провайдеры, Задания, Сеть, Надёжность, ML
 */

import { useState, useEffect, useCallback } from 'react';
import AdminLayout from '../../components/admin/AdminLayout';
import { Button } from '../../components/ui/button';
import { Switch } from '../../components/ui/switch';
import { Input } from '../../components/ui/input';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../../components/ui/tabs';
import {
  Server,
  RefreshCw,
  PlayCircle,
  StopCircle,
  TestTube,
  RotateCcw,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Activity,
  Loader2,
  Clock,
  Zap,
  Settings,
  TrendingUp,
  Globe,
  Wifi,
  WifiOff,
  Plus,
  Trash2,
  Shield,
} from 'lucide-react';
import api from '../../lib/api';
import ExchangeAdminDashboard from './modules/exchange/ExchangeAdminDashboard';
import ModelHealthPanel from '../../components/prediction/ModelHealthPanel';

// ═══════════════════════════════════════════════════════════════
// COMPONENTS
// ═══════════════════════════════════════════════════════════════

function HealthBadge({ status }) {
  const config = {
    UP: { cls: 'text-emerald-500', icon: CheckCircle, text: 'UP' },
    DEGRADED: { cls: 'text-amber-500', icon: AlertTriangle, text: 'DEGRADED' },
    DOWN: { cls: 'text-red-500', icon: XCircle, text: 'DOWN' },
  }[status] || { cls: 'text-slate-500', icon: Activity, text: status };
  
  const Icon = config.icon;
  
  return (
    <span className={`inline-flex items-center text-sm font-semibold ${config.cls}`}>
      <Icon className="w-3.5 h-3.5 mr-1" />
      {config.text}
    </span>
  );
}

function JobStatusBadge({ status, running }) {
  if (running) {
    return (
      <span className="inline-flex items-center text-sm font-semibold text-emerald-500">
        <Activity className="w-3.5 h-3.5 mr-1 animate-pulse" />
        RUNNING
      </span>
    );
  }
  
  const config = {
    IDLE: { cls: 'text-slate-400', text: 'IDLE' },
    STOPPED: { cls: 'text-slate-400', text: 'STOPPED' },
    ERROR: { cls: 'text-red-500', text: 'ERROR' },
  }[status] || { cls: 'text-slate-400', text: status };
  
  return (
    <span className={`inline-flex items-center text-sm font-semibold ${config.cls}`}>
      {config.text}
    </span>
  );
}

function ProviderCard({ provider, onToggle, onPriorityChange, onTest, onReset, testSymbol, loading }) {
  const [localPriority, setLocalPriority] = useState(provider.priority);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  
  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await onTest(provider.id, testSymbol);
      setTestResult(result);
    } finally {
      setTesting(false);
    }
  };
  
  const handlePriorityBlur = () => {
    if (localPriority !== provider.priority && localPriority >= 0) {
      onPriorityChange(provider.id, localPriority);
    }
  };
  
  return (
    <div 
      className={`p-4 rounded-lg transition-all ${
        provider.enabled 
          ? 'bg-white' 
          : 'bg-gray-50 opacity-60'
      }`}
      data-testid={`exchange-provider-${provider.id}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${provider.enabled ? 'bg-indigo-50' : 'bg-gray-100'}`}>
            <Server className={`w-5 h-5 ${provider.enabled ? 'text-indigo-500' : 'text-gray-400'}`} />
          </div>
          <div>
            <p className="font-semibold text-gray-800">{provider.id}</p>
            <p className="text-xs text-gray-500">Приоритет: {provider.priority}{provider.health?.lastOkAt ? ` · ${(() => {
              const sec = Math.round((Date.now() - new Date(provider.health.lastOkAt).getTime()) / 1000);
              return sec < 60 ? `${sec}s назад` : `${Math.round(sec / 60)}m назад`;
            })()}` : ''}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <HealthBadge status={provider.health?.status || 'UP'} />
          <Switch
            checked={provider.enabled}
            onCheckedChange={(checked) => onToggle(provider.id, checked)}
            disabled={loading}
            data-testid={`provider-toggle-${provider.id}`}
          />
        </div>
      </div>
      
      {/* Stats */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="p-2 bg-gray-50 rounded text-center">
          <p className="text-xs text-gray-500">Приоритет</p>
          <Input
            type="number"
            min={0}
            value={localPriority}
            onChange={(e) => setLocalPriority(Number(e.target.value))}
            onBlur={handlePriorityBlur}
            className="h-7 w-16 mx-auto text-center bg-white text-gray-800"
            data-testid={`provider-priority-${provider.id}`}
          />
        </div>
        <div className="p-2 bg-gray-50 rounded text-center">
          <p className="text-xs text-gray-500">Ошибки</p>
          <p className={`font-semibold ${provider.health?.errorCount > 0 ? 'text-red-500' : 'text-gray-700'}`}>
            {provider.health?.errorCount || 0}
          </p>
        </div>
        <div className="p-2 bg-gray-50 rounded text-center">
          <p className="text-xs text-gray-500">Последний OK</p>
          <p className="text-xs text-gray-600">
            {provider.health?.lastOkAt 
              ? new Date(provider.health.lastOkAt).toLocaleTimeString()
              : '—'}
          </p>
        </div>
      </div>
      
      {/* Last Error */}
      {provider.health?.lastError && (
        <div className="mb-3 p-2 bg-red-50 rounded text-xs text-red-600">
          <AlertTriangle className="w-3 h-3 inline mr-1" />
          {provider.health.lastError}
        </div>
      )}
      
      {/* Test Result */}
      {testResult && (
        <div className={`mb-3 p-2 rounded text-xs ${
          testResult.ok 
            ? 'bg-emerald-50 text-emerald-600'
            : 'bg-red-50 text-red-600'
        }`}>
          {testResult.ok ? (
            <>
              <CheckCircle className="w-3 h-3 inline mr-1" />
              Задержка: {testResult.latencyMs}мс | Цена: ${testResult.sample?.mid?.toFixed(2)}
            </>
          ) : (
            <>
              <XCircle className="w-3 h-3 inline mr-1" />
              {testResult.error}
            </>
          )}
        </div>
      )}
      
      {/* Actions */}
      <div className="flex gap-2 pt-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={handleTest}
          disabled={testing || loading}
          className="flex-1 bg-white text-gray-700 hover:bg-gray-50"
          data-testid={`provider-test-${provider.id}`}
        >
          {testing ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <TestTube className="w-3 h-3 mr-1" />}
          Тест
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onReset(provider.id)}
          disabled={loading}
          className="flex-1 bg-white text-gray-700 hover:bg-gray-50"
          data-testid={`provider-reset-${provider.id}`}
        >
          <RotateCcw className="w-3 h-3 mr-1" />
          Сброс
        </Button>
      </div>
    </div>
  );
}

function JobCard({ job, onStart, onStop, onRunOnce, loading }) {
  const [running, setRunning] = useState(false);
  
  const handleRunOnce = async () => {
    setRunning(true);
    try {
      await onRunOnce(job.id);
    } finally {
      setRunning(false);
    }
  };
  
  return (
    <div 
      className="p-4 bg-white rounded-lg"
      data-testid={`exchange-job-${job.id}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${job.running ? 'bg-emerald-50' : 'bg-gray-100'}`}>
            <Zap className={`w-5 h-5 ${job.running ? 'text-emerald-500' : 'text-gray-400'}`} />
          </div>
          <div>
            <p className="font-semibold text-gray-800">{job.displayName || job.id}</p>
            <p className="text-xs text-gray-500">
              Интервал: {(job.scheduleMs / 1000).toFixed(0)}с
            </p>
          </div>
        </div>
        <JobStatusBadge status={job.status} running={job.running} />
      </div>
      
      {/* Stats */}
      <div className="grid grid-cols-2 gap-2 mb-3">
        <div className="p-2 bg-gray-50 rounded text-center">
          <p className="text-xs text-gray-500">Последний запуск</p>
          <p className="text-xs text-gray-600">
            {job.lastRunAt 
              ? new Date(job.lastRunAt).toLocaleTimeString()
              : '—'}
          </p>
        </div>
        <div className="p-2 bg-gray-50 rounded text-center">
          <p className="text-xs text-gray-500">Результат</p>
          <p className={`text-xs font-semibold ${
            job.lastRunStatus === 'OK' ? 'text-emerald-500' : 
            job.lastRunStatus === 'ERROR' ? 'text-red-500' : 'text-gray-500'
          }`}>
            {job.lastRunStatus || '—'}
          </p>
        </div>
      </div>
      
      {/* Symbols */}
      {job.config?.trackedSymbols && (
        <div className="mb-3 flex flex-wrap gap-1">
          {job.config.trackedSymbols.slice(0, 5).map(s => (
            <span key={s} className="text-xs text-gray-700">
              {s}
            </span>
          ))}
          {job.config.trackedSymbols.length > 5 && (
            <span className="text-xs text-gray-500">
              +{job.config.trackedSymbols.length - 5} ещё
            </span>
          )}
        </div>
      )}
      
      {/* Error */}
      {job.lastError && (
        <div className="mb-3 p-2 bg-red-50 rounded text-xs text-red-600">
          <AlertTriangle className="w-3 h-3 inline mr-1" />
          {job.lastError}
        </div>
      )}
      
      {/* Actions */}
      <div className="flex gap-2 pt-2">
        {job.running ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onStop(job.id)}
            disabled={loading}
            className="flex-1 bg-red-50 text-red-600 hover:bg-red-100"
            data-testid={`job-stop-${job.id}`}
          >
            <StopCircle className="w-3 h-3 mr-1" />
            Стоп
          </Button>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onStart(job.id)}
            disabled={loading}
            className="flex-1 bg-emerald-50 text-emerald-600 hover:bg-emerald-100"
            data-testid={`job-start-${job.id}`}
          >
            <PlayCircle className="w-3 h-3 mr-1" />
            Старт
          </Button>
        )}
        <Button
          variant="ghost"
          size="sm"
          onClick={handleRunOnce}
          disabled={running || loading}
          className="flex-1 bg-white text-gray-700 hover:bg-gray-50"
          data-testid={`job-run-once-${job.id}`}
        >
          {running ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Zap className="w-3 h-3 mr-1" />}
          Запустить разово
        </Button>
      </div>
    </div>
  );
}

function AlertCard({ alert }) {
  const config = {
    ERROR: { bg: 'bg-red-50', text: 'text-red-600', icon: XCircle },
    WARN: { bg: 'bg-amber-50', text: 'text-amber-600', icon: AlertTriangle },
    INFO: { bg: 'bg-blue-50', text: 'text-blue-600', icon: Activity },
  }[alert.level] || { bg: 'bg-gray-50', text: 'text-gray-600', icon: Activity };
  
  const Icon = config.icon;
  
  return (
    <div className={`p-3 rounded-lg ${config.bg}`}>
      <div className="flex items-start gap-2">
        <Icon className={`w-4 h-4 mt-0.5 ${config.text}`} />
        <div className="flex-1">
          <p className={`text-sm font-medium ${config.text}`}>{alert.code}</p>
          <p className="text-xs text-gray-500 mt-0.5">{alert.message}</p>
        </div>
        <span className="text-xs text-gray-400">
          {new Date(alert.timestamp).toLocaleTimeString()}
        </span>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// NETWORK TAB COMPONENT
// ═══════════════════════════════════════════════════════════════

function NetworkTab({ onRefresh }) {
  const [networkConfig, setNetworkConfig] = useState(null);
  const [networkHealth, setNetworkHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  
  // Proxy form fields (local state for immediate UI updates)
  const [proxyType, setProxyType] = useState('http');
  const [proxyIp, setProxyIp] = useState('');
  const [proxyPort, setProxyPort] = useState('');
  const [proxyUsername, setProxyUsername] = useState('');
  const [proxyPassword, setProxyPassword] = useState('');
  const [proxyTimeout, setProxyTimeout] = useState(8000);
  
  // New proxy form for pool
  const [newProxyId, setNewProxyId] = useState('');
  const [newProxyUrl, setNewProxyUrl] = useState('');
  
  const fetchNetworkData = useCallback(async () => {
    try {
      setLoading(true);
      const [configRes, healthRes] = await Promise.all([
        api.get('/v10/admin/network/config'),
        api.get('/v10/admin/network/health'),
      ]);
      const config = configRes.data.config;
      setNetworkConfig(config);
      setNetworkHealth(healthRes.data.health);
      
      // Populate form fields from config
      if (config.proxy) {
        setProxyType(config.proxy.type || 'http');
        setProxyIp(config.proxy.ip || '');
        setProxyPort(config.proxy.port || '');
        setProxyUsername(config.proxy.username || '');
        setProxyPassword(config.proxy.password || '');
        setProxyTimeout(config.proxy.timeoutMs || 8000);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);
  
  useEffect(() => {
    fetchNetworkData();
  }, [fetchNetworkData]);
  
  const handleTestConnectivity = async () => {
    setTesting(true);
    try {
      const res = await api.post('/v10/admin/network/test');
      // Refresh health after test
      const healthRes = await api.get('/v10/admin/network/health');
      setNetworkHealth(healthRes.data.health);
      alert(`Test complete: ${res.data.summary.ok}/${res.data.summary.total} providers OK`);
    } catch (err) {
      setError(err.message);
    } finally {
      setTesting(false);
    }
  };
  
  const handleUpdateEgressMode = async (mode) => {
    setSaving(true);
    try {
      const res = await api.patch('/v10/admin/network/config', { egressMode: mode });
      setNetworkConfig(res.data.config);
      onRefresh?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };
  
  const handleUpdateProxy = async () => {
    setSaving(true);
    setSaveSuccess(false);
    setError(null);
    
    try {
      // Build URL from separate fields
      let proxyUrl = `${proxyType}://`;
      if (proxyUsername && proxyPassword) {
        proxyUrl += `${proxyUsername}:${proxyPassword}@`;
      } else if (proxyUsername) {
        proxyUrl += `${proxyUsername}@`;
      }
      proxyUrl += `${proxyIp}:${proxyPort}`;
      
      // Save proxy config
      const res = await api.patch('/v10/admin/network/config', {
        proxy: {
          url: proxyUrl,
          type: proxyType,
          ip: proxyIp,
          port: proxyPort,
          username: proxyUsername || '',
          password: proxyPassword || '',
          timeoutMs: proxyTimeout,
          enabled: true,
        },
      });
      setNetworkConfig(res.data.config);
      setSaveSuccess(true);
      
      // Automatically test connectivity after saving
      setTesting(true);
      try {
        await api.post('/v10/admin/network/test');
        const healthRes = await api.get('/v10/admin/network/health');
        setNetworkHealth(healthRes.data.health);
      } catch (testErr) {
        console.error('Test failed:', testErr);
      } finally {
        setTesting(false);
      }
      
      onRefresh?.();
    } catch (err) {
      setError(err.message);
      setSaveSuccess(false);
    } finally {
      setSaving(false);
    }
  };
  
  const handleAddProxy = async () => {
    if (!newProxyId || !newProxyUrl) return;
    
    setSaving(true);
    try {
      await api.post('/v10/admin/network/proxy/add', {
        id: newProxyId,
        url: newProxyUrl,
        weight: 1,
      });
      setNewProxyId('');
      setNewProxyUrl('');
      await fetchNetworkData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };
  
  const handleRemoveProxy = async (id) => {
    if (!confirm(`Remove proxy "${id}"?`)) return;
    
    try {
      await api.delete(`/v10/admin/network/proxy/${id}`);
      await fetchNetworkData();
    } catch (err) {
      setError(err.message);
    }
  };
  
  const handleResetProxy = async (id) => {
    try {
      await api.post(`/v10/admin/network/proxy/${id}/reset`);
      await fetchNetworkData();
    } catch (err) {
      setError(err.message);
    }
  };
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
      </div>
    );
  }
  
  const probes = networkHealth?.probes || [];
  
  return (
    <div className="space-y-6">
      {error && (
        <div className="p-3 bg-red-50 rounded-lg flex items-center gap-2 text-red-600 text-sm">
          <AlertTriangle className="w-4 h-4" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto text-xs hover:underline">Dismiss</button>
        </div>
      )}
      
      {/* Connectivity Status */}
      <div className="p-4 bg-white rounded-lg">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Globe className="w-5 h-5 text-indigo-500" />
            <h3 className="font-semibold text-gray-800">Подключение провайдеров</h3>
          </div>
          <Button 
            variant="ghost" 
            size="sm"
            onClick={handleTestConnectivity}
            disabled={testing}
            className="bg-white text-gray-700 hover:bg-gray-50"
            data-testid="network-test-btn"
          >
            {testing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <TestTube className="w-4 h-4 mr-2" />}
            Тест всех
          </Button>
        </div>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {probes.map(probe => (
            <div 
              key={probe.provider}
              className={`p-3 rounded-lg ${
                probe.ok 
                  ? 'bg-emerald-50' 
                  : 'bg-red-50'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                {probe.ok ? (
                  <Wifi className="w-4 h-4 text-emerald-500" />
                ) : (
                  <WifiOff className="w-4 h-4 text-red-500" />
                )}
                <span className={`text-sm font-medium ${probe.ok ? 'text-emerald-700' : 'text-red-700'}`}>
                  {probe.provider}
                </span>
              </div>
              <div className="text-xs text-gray-500">
                {probe.ok ? `${probe.latencyMs}ms` : probe.reason || 'DOWN'}
              </div>
            </div>
          ))}
        </div>
      </div>
      
      {/* Egress Mode */}
      <div className="p-4 bg-white rounded-lg">
        <div className="flex items-center gap-2 mb-4">
          <Shield className="w-5 h-5 text-purple-500" />
          <h3 className="font-semibold text-gray-800">Режим выхода</h3>
        </div>
        
        <div className="grid grid-cols-3 gap-3">
          {['direct', 'proxy', 'proxy_pool'].map(mode => (
            <button
              key={mode}
              onClick={() => handleUpdateEgressMode(mode)}
              disabled={saving}
              className={`p-4 rounded-lg text-center transition-colors ${
                networkConfig?.egressMode === mode
                  ? 'bg-indigo-50 text-indigo-700'
                  : 'bg-gray-50 text-gray-600 hover:bg-gray-100'
              }`}
              data-testid={`egress-mode-${mode}`}
            >
              <div className="font-semibold uppercase">{mode.replace('_', ' ')}</div>
              <div className="text-xs mt-1 text-gray-500">
                {mode === 'direct' && 'Прямое подключение'}
                {mode === 'proxy' && 'Один прокси'}
                {mode === 'proxy_pool' && 'Ротация прокси'}
              </div>
            </button>
          ))}
        </div>
      </div>
      
      {/* Single Proxy Config */}
      {networkConfig?.egressMode === 'proxy' && (
        <div className="p-4 bg-white rounded-lg">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-800">Настройка прокси</h3>
            {/* Proxy Status */}
            {networkConfig.proxy?.ip && (
              <div className={`text-xs font-medium ${
                probes.some(p => p.ok && p.provider !== 'COINBASE') 
                  ? 'text-emerald-600' 
                  : 'text-amber-600'
              }`}>
                {probes.some(p => p.ok && p.provider !== 'COINBASE') 
                  ? '● Подключён' 
                  : '○ Не подключён'}
              </div>
            )}
          </div>
          
          <div className="space-y-4">
            {/* Success/Error Messages */}
            {saveSuccess && (
              <div className="p-3 bg-emerald-50 rounded-lg flex items-center gap-2 text-emerald-600 text-sm">
                <CheckCircle className="w-4 h-4" />
                Прокси сохранён! Тестирование подключения...
              </div>
            )}
            
            {/* Proxy Type */}
            <div>
              <label className="text-xs text-gray-500 block mb-2">Тип прокси</label>
              <div className="flex gap-3">
                {['http', 'socks5'].map(type => (
                  <button
                    key={type}
                    onClick={() => setProxyType(type)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      proxyType === type
                        ? 'bg-indigo-50 text-indigo-700'
                        : 'bg-gray-50 text-gray-600 hover:bg-gray-100'
                    }`}
                    data-testid={`proxy-type-${type}`}
                  >
                    {type.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
            
            {/* IP and Port */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-gray-500 block mb-1">IP адрес</label>
                <Input
                  type="text"
                  value={proxyIp}
                  onChange={(e) => setProxyIp(e.target.value)}
                  placeholder="192.168.1.100"
                  className="bg-white text-gray-800"
                  data-testid="proxy-ip-input"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-1">Порт</label>
                <Input
                  type="text"
                  value={proxyPort}
                  onChange={(e) => setProxyPort(e.target.value)}
                  placeholder="8080"
                  className="bg-white text-gray-800"
                  data-testid="proxy-port-input"
                />
              </div>
            </div>
            
            {/* Login and Password */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-gray-500 block mb-1">Логин</label>
                <Input
                  type="text"
                  value={proxyUsername}
                  onChange={(e) => setProxyUsername(e.target.value)}
                  placeholder="username"
                  className="bg-white text-gray-800"
                  data-testid="proxy-username-input"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-1">Пароль</label>
                <Input
                  type="password"
                  value={proxyPassword}
                  onChange={(e) => setProxyPassword(e.target.value)}
                  placeholder="••••••••"
                  className="bg-white text-gray-800"
                  data-testid="proxy-password-input"
                />
              </div>
            </div>
            
            {/* Timeout */}
            <div>
              <label className="text-xs text-gray-500 block mb-1">Timeout (ms)</label>
              <Input
                type="number"
                value={proxyTimeout}
                onChange={(e) => setProxyTimeout(parseInt(e.target.value) || 8000)}
                className="bg-white text-gray-800 w-32"
              />
            </div>
            
            {/* Preview */}
            {proxyIp && proxyPort && (
              <div className="p-3 bg-gray-50 rounded-lg">
                <label className="text-xs text-gray-500 block mb-1">Generated URL</label>
                <code className="text-sm text-gray-700">
                  {proxyType}://
                  {proxyUsername ? `${proxyUsername}:***@` : ''}
                  {proxyIp}:{proxyPort}
                </code>
              </div>
            )}
            
            {/* Save Button */}
            <Button 
              onClick={handleUpdateProxy}
              disabled={saving || testing || !proxyIp || !proxyPort}
              className="bg-indigo-600 hover:bg-indigo-700 text-white"
              data-testid="save-proxy-btn"
            >
              {saving ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : testing ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Testing...
                </>
              ) : (
                'Save & Test Proxy'
              )}
            </Button>
          </div>
        </div>
      )}
      
      {/* Proxy Pool */}
      {networkConfig?.egressMode === 'proxy_pool' && (
        <div className="p-4 bg-white rounded-lg">
          <h3 className="font-semibold text-gray-800 mb-4">Пул прокси</h3>
          
          {/* Existing proxies */}
          {networkConfig.proxyPool?.length > 0 ? (
            <div className="space-y-2 mb-4">
              {networkConfig.proxyPool.map(proxy => (
                <div 
                  key={proxy.id}
                  className={`p-3 rounded-lg flex items-center justify-between ${
                    proxy.enabled 
                      ? 'bg-gray-50' 
                      : 'bg-red-50'
                  }`}
                >
                  <div>
                    <span className="font-medium text-gray-800">{proxy.id}</span>
                    <span className="text-xs text-gray-500 ml-2">{proxy.url}</span>
                    {proxy.errorCount > 0 && (
                      <span className="text-xs text-red-500 ml-2">({proxy.errorCount} errors)</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <Button 
                      variant="ghost" 
                      size="sm"
                      onClick={() => handleResetProxy(proxy.id)}
                      className="text-gray-500 hover:text-gray-700"
                    >
                      <RotateCcw className="w-4 h-4" />
                    </Button>
                    <Button 
                      variant="ghost" 
                      size="sm"
                      onClick={() => handleRemoveProxy(proxy.id)}
                      className="text-red-500 hover:text-red-700"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm mb-4">Нет прокси в пуле</p>
          )}
          
          {/* Add new proxy */}
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <label className="text-xs text-gray-500 block mb-1">Proxy ID</label>
              <Input
                value={newProxyId}
                onChange={(e) => setNewProxyId(e.target.value)}
                placeholder="proxy-1"
                className="bg-white text-gray-800"
              />
            </div>
            <div className="flex-[2]">
              <label className="text-xs text-gray-500 block mb-1">Proxy URL</label>
              <Input
                value={newProxyUrl}
                onChange={(e) => setNewProxyUrl(e.target.value)}
                placeholder="http://user:pass@ip:port"
                className="bg-white text-gray-800"
              />
            </div>
            <Button 
              onClick={handleAddProxy}
              disabled={saving || !newProxyId || !newProxyUrl}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
              data-testid="add-proxy-btn"
            >
              <Plus className="w-4 h-4 mr-1" />
              Add
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════════════════════════

export default function AdminExchangeControlPage() {
  const [providers, setProviders] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [testSymbol, setTestSymbol] = useState('BTCUSDT');
  
  // ─────────────────────────────────────────────────────────────
  // DATA FETCHING
  // ─────────────────────────────────────────────────────────────
  
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      const [providersRes, jobsRes, healthRes] = await Promise.all([
        api.get('/v10/exchange/admin/providers'),
        api.get('/v10/exchange/admin/jobs'),
        api.get('/v10/exchange/admin/health'),
      ]);
      
      setProviders(providersRes.data?.providers || []);
      setJobs(jobsRes.data?.jobs || []);
      setHealth(healthRes.data);
    } catch (err) {
      setError(err.message || 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  }, []);
  
  useEffect(() => {
    fetchData();
    
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);
  
  // ─────────────────────────────────────────────────────────────
  // PROVIDER ACTIONS
  // ─────────────────────────────────────────────────────────────
  
  const handleToggleProvider = async (id, enabled) => {
    try {
      await api.patch(`/v10/exchange/admin/providers/${id}`, { enabled });
      await fetchData();
    } catch (err) {
      setError(err.message);
    }
  };
  
  const handlePriorityChange = async (id, priority) => {
    try {
      await api.patch(`/v10/exchange/admin/providers/${id}`, { priority });
      await fetchData();
    } catch (err) {
      setError(err.message);
    }
  };
  
  const handleTestProvider = async (id, symbol) => {
    try {
      const res = await api.post(`/v10/exchange/admin/providers/${id}/test`, { symbol });
      return res.data;
    } catch (err) {
      return { ok: false, error: err.message };
    }
  };
  
  const handleResetProvider = async (id) => {
    try {
      await api.post(`/v10/exchange/admin/providers/${id}/reset`);
      await fetchData();
    } catch (err) {
      setError(err.message);
    }
  };
  
  // ─────────────────────────────────────────────────────────────
  // JOB ACTIONS
  // ─────────────────────────────────────────────────────────────
  
  const handleStartJob = async (id) => {
    try {
      await api.post(`/v10/exchange/admin/jobs/${id}/start`);
      await fetchData();
    } catch (err) {
      setError(err.message);
    }
  };
  
  const handleStopJob = async (id) => {
    try {
      await api.post(`/v10/exchange/admin/jobs/${id}/stop`);
      await fetchData();
    } catch (err) {
      setError(err.message);
    }
  };
  
  const handleRunOnce = async (id) => {
    try {
      await api.post(`/v10/exchange/admin/jobs/${id}/run-once`, { symbol: testSymbol });
      await fetchData();
    } catch (err) {
      setError(err.message);
    }
  };
  
  // ─────────────────────────────────────────────────────────────
  // RENDER
  // ─────────────────────────────────────────────────────────────
  
  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-50 rounded-lg">
              <Settings className="w-6 h-6 text-indigo-500" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-800">Exchange</h1>
              <p className="text-sm text-gray-500">Управление провайдерами, заданиями и сетью</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button 
              variant="ghost" 
              onClick={fetchData} 
              disabled={loading}
              className="bg-white text-gray-700 hover:bg-gray-50"
              data-testid="exchange-refresh-btn"
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Обновить
            </Button>
          </div>
        </div>
        
        {/* Error */}
        {error && (
          <div className="p-4 bg-red-50 rounded-lg flex items-center gap-2 text-red-600">
            <AlertTriangle className="w-5 h-5" />
            {error}
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => setError(null)}
              className="ml-auto text-red-600 hover:bg-red-100"
            >
              Закрыть
            </Button>
          </div>
        )}
        
        {/* Health Summary */}
        {health && (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4" data-testid="exchange-health-summary">
            <div className="p-4 bg-white rounded-lg group relative" data-testid="providers-summary-card">
              <div className="flex items-center gap-2 mb-2">
                <Server className="w-4 h-4 text-indigo-500" />
                <span className="text-xs text-gray-500 uppercase">Провайдеры</span>
              </div>
              <div className="hidden group-hover:block absolute z-10 bottom-full left-0 mb-2 p-2 bg-gray-900 text-white text-xs rounded-lg shadow-lg w-56">
                Активные источники биржевых данных. Показывает сколько из подключённых провайдеров работает.
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold text-gray-800">{health.providers?.up || 0}</span>
                <span className="text-sm text-gray-500">/ {health.providers?.total || 0}</span>
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {health.providers?.degraded > 0 && (
                  <span className="text-amber-500">{health.providers.degraded} degraded</span>
                )}
                {health.providers?.down > 0 && (
                  <span className="text-red-500 ml-2">{health.providers.down} down</span>
                )}
              </div>
            </div>
            
            <div className="p-4 bg-white rounded-lg group relative">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-4 h-4 text-emerald-500" />
                <span className="text-xs text-gray-500 uppercase">Задания</span>
              </div>
              <div className="hidden group-hover:block absolute z-10 bottom-full left-0 mb-2 p-2 bg-gray-900 text-white text-xs rounded-lg shadow-lg w-56">
                Фоновые задачи сбора данных. Показывает сколько заданий выполняется в данный момент.
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold text-gray-800">{health.jobs?.running || 0}</span>
                <span className="text-sm text-gray-500">/ {health.jobs?.total || 0}</span>
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {health.jobs?.error > 0 && (
                  <span className="text-red-500">{health.jobs.error} с ошибками</span>
                )}
              </div>
            </div>
            
            <div className="p-4 bg-white rounded-lg group relative">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="w-4 h-4 text-purple-500" />
                <span className="text-xs text-gray-500 uppercase">Режим данных</span>
              </div>
              <div className="hidden group-hover:block absolute z-10 bottom-full left-0 mb-2 p-2 bg-gray-900 text-white text-xs rounded-lg shadow-lg w-56">
                Текущий режим получения данных. LIVE — реальные данные с бирж. MOCK — тестовые данные. MIXED — комбинация.
              </div>
              <div className="flex items-baseline gap-2">
                <span className={`text-xl font-bold ${
                  health.dataStatus?.mode === 'LIVE' ? 'text-emerald-500' :
                  health.dataStatus?.mode === 'MOCK' ? 'text-amber-500' : 'text-gray-600'
                }`}>
                  {health.dataStatus?.mode || 'UNKNOWN'}
                </span>
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {health.dataStatus?.activeSymbols || 0} активных символов
              </div>
            </div>
            
            <div className="p-4 bg-white rounded-lg group relative" data-testid="data-freshness-card">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-4 h-4 text-cyan-500" />
                <span className="text-xs text-gray-500 uppercase">Свежесть данных</span>
              </div>
              <div className="hidden group-hover:block absolute z-10 bottom-full left-0 mb-2 p-2 bg-gray-900 text-white text-xs rounded-lg shadow-lg w-56">
                Время с последнего успешного получения данных. Зелёный — до 30с, жёлтый — до 2мин, красный — более 5мин.
              </div>
              {(() => {
                const lastUpdate = providers.reduce((latest, p) => {
                  const t = p.health?.lastOkAt ? new Date(p.health.lastOkAt).getTime() : 0;
                  return t > latest ? t : latest;
                }, 0);
                const ageSec = lastUpdate ? Math.round((Date.now() - lastUpdate) / 1000) : null;
                const color = ageSec === null ? 'text-gray-400' : ageSec < 30 ? 'text-emerald-500' : ageSec < 120 ? 'text-amber-500' : 'text-red-500';
                return (
                  <>
                    <div className="flex items-baseline gap-1">
                      <span className={`text-2xl font-bold ${color}`}>
                        {ageSec === null ? '—' : ageSec < 60 ? `${ageSec}s` : `${Math.round(ageSec / 60)}m`}
                      </span>
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      {ageSec === null ? 'Нет данных' : ageSec < 30 ? 'Данные актуальны' : ageSec < 120 ? 'Небольшая задержка' : 'Данные устарели'}
                    </div>
                  </>
                );
              })()}
            </div>
            
            <div className="p-4 bg-white rounded-lg group relative" data-testid="circuit-breaker-card">
              <div className="flex items-center gap-2 mb-2">
                <Shield className="w-4 h-4 text-orange-500" />
                <span className="text-xs text-gray-500 uppercase">Circuit Breaker</span>
              </div>
              <div className="hidden group-hover:block absolute z-10 bottom-full left-0 mb-2 p-2 bg-gray-900 text-white text-xs rounded-lg shadow-lg w-56">
                Автоматическая защита от сбоев. Если провайдер выдаёт слишком много ошибок — он блокируется автоматически.
              </div>
              {(() => {
                const tripped = providers.some(p => p.health?.circuitBreaker === 'OPEN' || p.health?.circuitBreakerTripped);
                return (
                  <>
                    <div className="flex items-baseline gap-1">
                      <span className={`text-xl font-bold ${tripped ? 'text-red-500' : 'text-emerald-500'}`}>
                        {tripped ? 'СРАБОТАЛ' : 'ВЫКЛ'}
                      </span>
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      {tripped ? 'Провайдер заблокирован' : 'Все провайдеры активны'}
                    </div>
                  </>
                );
              })()}
            </div>
            
            <div className="p-4 bg-white rounded-lg group relative">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="w-4 h-4 text-amber-500" />
                <span className="text-xs text-gray-500 uppercase">Алерты</span>
              </div>
              <div className="hidden group-hover:block absolute z-10 bottom-full left-0 mb-2 p-2 bg-gray-900 text-white text-xs rounded-lg shadow-lg w-56">
                Активные предупреждения системы. Показывает проблемы, требующие внимания администратора.
              </div>
              <div className="flex items-baseline gap-2">
                <span className={`text-2xl font-bold ${
                  (health.alerts?.length || 0) > 0 ? 'text-amber-500' : 'text-gray-600'
                }`}>
                  {health.alerts?.length || 0}
                </span>
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {(health.alerts?.length || 0) === 0 ? 'Системы в норме' : 'Требуется внимание'}
              </div>
            </div>
          </div>
        )}
        
        {/* Tabs */}
        <Tabs defaultValue="providers" className="w-full">
          <TabsList className="bg-gray-100">
            <TabsTrigger value="providers" className="data-[state=active]:bg-white data-[state=active]:text-gray-800">
              <Server className="w-4 h-4 mr-2" />
              Провайдеры ({providers.length})
            </TabsTrigger>
            <TabsTrigger value="jobs" className="data-[state=active]:bg-white data-[state=active]:text-gray-800">
              <Zap className="w-4 h-4 mr-2" />
              Задания ({jobs.length})
            </TabsTrigger>
            <TabsTrigger value="network" className="data-[state=active]:bg-white data-[state=active]:text-gray-800" data-testid="network-tab">
              <Globe className="w-4 h-4 mr-2" />
              Сеть
            </TabsTrigger>
            <TabsTrigger value="alerts" className="data-[state=active]:bg-white data-[state=active]:text-gray-800">
              <AlertTriangle className="w-4 h-4 mr-2" />
              Алерты ({health?.alerts?.length || 0})
            </TabsTrigger>
            <TabsTrigger value="reliability" className="data-[state=active]:bg-white data-[state=active]:text-gray-800" data-testid="reliability-tab">
              <Shield className="w-4 h-4 mr-2" />
              Надёжность
            </TabsTrigger>
            <TabsTrigger value="ml-health" className="data-[state=active]:bg-white data-[state=active]:text-gray-800" data-testid="ml-health-tab">
              <TrendingUp className="w-4 h-4 mr-2" />
              ML
            </TabsTrigger>
          </TabsList>
          
          {/* Providers Tab */}
          <TabsContent value="providers" className="mt-4">
            {loading ? (
              <div className="flex items-center justify-center h-64">
                <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
              </div>
            ) : providers.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <Server className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>No providers configured</p>
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {providers
                  .sort((a, b) => b.priority - a.priority)
                  .map(provider => (
                    <ProviderCard
                      key={provider.id}
                      provider={provider}
                      onToggle={handleToggleProvider}
                      onPriorityChange={handlePriorityChange}
                      onTest={handleTestProvider}
                      onReset={handleResetProvider}
                      testSymbol={testSymbol}
                      loading={loading}
                    />
                  ))}
              </div>
            )}
          </TabsContent>
          
          {/* Jobs Tab */}
          <TabsContent value="jobs" className="mt-4">
            {loading ? (
              <div className="flex items-center justify-center h-64">
                <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
              </div>
            ) : jobs.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <Zap className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>No jobs configured</p>
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {jobs.map(job => (
                  <JobCard
                    key={job.id}
                    job={job}
                    onStart={handleStartJob}
                    onStop={handleStopJob}
                    onRunOnce={handleRunOnce}
                    loading={loading}
                  />
                ))}
              </div>
            )}
          </TabsContent>
          
          {/* Network Tab */}
          <TabsContent value="network" className="mt-4">
            <NetworkTab onRefresh={fetchData} />
          </TabsContent>
          
          {/* Alerts Tab */}
          <TabsContent value="alerts" className="mt-4">
            {!health?.alerts || health.alerts.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <CheckCircle className="w-12 h-12 mx-auto mb-3 text-emerald-400" />
                <p className="text-emerald-600">Все системы в норме</p>
              </div>
            ) : (
              <div className="space-y-3">
                {health.alerts.map((alert, idx) => (
                  <AlertCard key={idx} alert={alert} />
                ))}
              </div>
            )}
          </TabsContent>
          
          {/* Reliability Tab */}
          <TabsContent value="reliability" className="mt-4" data-testid="reliability-content">
            <ExchangeAdminDashboard />
          </TabsContent>
          
          {/* ML Health Tab */}
          <TabsContent value="ml-health" className="mt-4" data-testid="ml-health-content">
            <ModelHealthPanel asset="BTC" />
          </TabsContent>
        </Tabs>
      </div>
    </AdminLayout>
  );
}
