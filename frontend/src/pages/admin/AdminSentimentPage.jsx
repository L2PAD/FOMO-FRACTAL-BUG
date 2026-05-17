/**
 * Sentiment Admin — Operational Control Panel
 * =============================================
 * 
 * Control panel for Sentiment Engine.
 * Tabs: Обзор, Стек решений, Бустер, CNN-анализ, Тестирование, Датасет, Логи
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminLayout from '../../components/admin/AdminLayout';
import { useAdminAuth } from '../../context/AdminAuthContext';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Switch } from '../../components/ui/switch';
import { Label } from '../../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/card';
import { Progress } from '../../components/ui/progress';
import {
  Activity,
  Settings,
  Play,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Zap,
  Database,
  Server,
  Loader2,
  Sparkles,
  Shield,
  TrendingUp,
  Layers,
  Eye,
  FlaskConical,
  History,
  Lock,
  ArrowRight,
  ArrowDown,
  Info,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ============================================================
// Helper Components
// ============================================================

const HealthBadge = ({ health }) => {
  const cfg = {
    HEALTHY: { cls: 'text-emerald-600', icon: CheckCircle },
    DEGRADED: { cls: 'text-amber-600', icon: AlertTriangle },
    DISABLED: { cls: 'text-red-600', icon: XCircle },
  }[health] || { cls: 'text-slate-500', icon: Activity };
  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center text-sm font-semibold ${cfg.cls}`} data-testid="health-badge">
      <Icon className="w-3.5 h-3.5 mr-1" />
      {health}
    </span>
  );
};

const LabelBadge = ({ label }) => {
  const colors = {
    POSITIVE: 'text-emerald-600',
    NEUTRAL: 'text-amber-600',
    NEGATIVE: 'text-red-600',
  };
  return <span className={`text-sm font-semibold ${colors[label] || 'text-slate-500'}`}>{label}</span>;
};

const Tooltip = ({ text, children }) => (
  <div className="group relative inline-flex items-center">
    {children}
    <div className="hidden group-hover:block absolute z-20 bottom-full left-0 mb-2 p-2 bg-gray-900 text-white text-xs rounded-lg shadow-lg w-56 pointer-events-none">
      {text}
    </div>
  </div>
);

// ============================================================
// Main Component
// ============================================================

export default function AdminSentimentPage() {
  const navigate = useNavigate();
  const { isAuthenticated, loading: authLoading } = useAdminAuth();
  
  const [activeTab, setActiveTab] = useState('overview');
  const [actionLoading, setActionLoading] = useState(null);
  
  const [status, setStatus] = useState(null);
  const [shadowStatus, setShadowStatus] = useState(null);
  const [boosterStatus, setBoosterStatus] = useState(null);
  const [datasetStats, setDatasetStats] = useState(null);
  const [sessionStatus, setSessionStatus] = useState(null);
  
  const [testText, setTestText] = useState('');
  const [testResult, setTestResult] = useState(null);
  const [toggleHistory, setToggleHistory] = useState([]);
  const [mlData, setMlData] = useState(null);
  
  // ============================================================
  // Data Fetching
  // ============================================================
  
  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v4/admin/sentiment/status`);
      const data = await res.json();
      if (data.ok) setStatus(data.data);
    } catch (e) { console.error('Failed to fetch status:', e); }
  }, []);
  
  const fetchShadowStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v4/admin/sentiment/shadow/status`);
      const data = await res.json();
      if (data.ok) setShadowStatus(data.data);
    } catch (e) { console.error('Failed to fetch shadow status:', e); }
  }, []);
  
  const fetchBoosterStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v4/admin/sentiment/booster/status`);
      const data = await res.json();
      if (data.ok) setBoosterStatus(data.data);
    } catch (e) { console.error('Failed to fetch booster status:', e); }
  }, []);
  
  const fetchDatasetStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v4/admin/ml/retrain/stats`);
      const data = await res.json();
      if (data.ok) setDatasetStats(data.data);
    } catch (e) { console.error('Failed to fetch dataset stats:', e); }
  }, []);
  
  const fetchSessionStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v4/admin/ml/data-session/summary`);
      const data = await res.json();
      if (data.ok) setSessionStatus(data.data);
    } catch (e) { console.error('Failed to fetch session status:', e); }
  }, []);
  
  const fetchMlData = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/admin/data-accumulation`);
      const data = await res.json();
      if (data.ok) setMlData(data.data);
    } catch (e) { console.error('Failed to fetch ML data:', e); }
  }, []);
  
  const refreshAll = () => {
    fetchStatus(); fetchShadowStatus(); fetchBoosterStatus(); fetchDatasetStats(); fetchSessionStatus(); fetchMlData();
  };

  // ============================================================
  // Actions
  // ============================================================
  
  const toggleShadowMode = async (enabled) => {
    setActionLoading('shadow');
    try {
      await fetch(`${API_URL}/api/v4/admin/sentiment/shadow/toggle`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      });
      await fetchShadowStatus();
      addToggleHistory('shadow', enabled);
    } catch (e) { console.error('Failed to toggle shadow:', e); }
    finally { setActionLoading(null); }
  };
  
  const toggleBooster = async (enabled) => {
    setActionLoading('booster');
    try {
      await fetch(`${API_URL}/api/v4/admin/sentiment/booster/toggle`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      });
      await fetchBoosterStatus();
      addToggleHistory('booster', enabled);
    } catch (e) { console.error('Failed to toggle booster:', e); }
    finally { setActionLoading(null); }
  };
  
  const updateThreshold = async (threshold) => {
    setActionLoading('threshold');
    try {
      await fetch(`${API_URL}/api/v4/admin/sentiment/booster/threshold`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ threshold }),
      });
      await fetchBoosterStatus();
      addToggleHistory('threshold', threshold);
    } catch (e) { console.error('Failed to update threshold:', e); }
    finally { setActionLoading(null); }
  };
  
  const runTest = async () => {
    if (!testText.trim()) return;
    setActionLoading('test');
    setTestResult(null);
    try {
      const res = await fetch(`${API_URL}/api/v4/admin/sentiment/booster/test`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: testText }),
      });
      const data = await res.json();
      if (data.ok) setTestResult(data.data);
    } catch (e) { console.error('Failed to run test:', e); }
    finally { setActionLoading(null); }
  };
  
  const addToggleHistory = (type, value) => {
    setToggleHistory(prev => [{
      id: Date.now(), type, value, timestamp: new Date().toISOString(),
    }, ...prev.slice(0, 49)]);
  };
  
  // ============================================================
  // Effects
  // ============================================================
  
  useEffect(() => {
    if (!authLoading && !isAuthenticated) { navigate('/admin/login', { replace: true }); return; }
    if (isAuthenticated) refreshAll();
  }, [authLoading, isAuthenticated]);
  
  useEffect(() => {
    const interval = setInterval(() => { fetchStatus(); fetchShadowStatus(); fetchBoosterStatus(); }, 30000);
    return () => clearInterval(interval);
  }, [fetchStatus, fetchShadowStatus, fetchBoosterStatus]);
  
  // ============================================================
  // Render
  // ============================================================
  
  if (authLoading) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
        </div>
      </AdminLayout>
    );
  }

  const decisionSource = boosterStatus?.enabled ? 'HYBRID BOOST' : shadowStatus?.enabled ? 'SHADOW' : 'MOCK ONLY';
  const cnnThreshold = boosterStatus?.config?.cnnConfidenceThreshold ? Math.round(boosterStatus.config.cnnConfidenceThreshold * 100) : 70;

  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6 space-y-6" data-testid="admin-sentiment-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-50 rounded-lg">
              <Activity className="w-6 h-6 text-indigo-500" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-800">Sentiment</h1>
              <p className="text-sm text-gray-500">Управление движком, тестирование, логи</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {status && <HealthBadge health={status.health} />}
            <Button variant="outline" size="sm" onClick={refreshAll} className="bg-white border-gray-300 text-gray-700 hover:bg-gray-50" data-testid="sentiment-refresh-btn">
              <RefreshCw className="w-4 h-4 mr-2" />
              Обновить
            </Button>
          </div>
        </div>
        
        {/* Health Summary */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4" data-testid="sentiment-health-summary">
          <Tooltip text="Текущий режим работы движка. HEALTHY — всё в норме, DEGRADED — часть функций ограничена.">
            <div className="p-4 bg-white rounded-lg w-full">
              <div className="flex items-center gap-2 mb-2">
                <Server className="w-4 h-4 text-indigo-500" />
                <span className="text-xs text-gray-500 uppercase">Статус</span>
              </div>
              <div className="text-2xl font-bold text-gray-800">{status?.health || '—'}</div>
            </div>
          </Tooltip>
          
          <Tooltip text="Источник принятия решений: MOCK ONLY — правила, SHADOW — параллельная CNN, HYBRID BOOST — правила + CNN бустер.">
            <div className="p-4 bg-white rounded-lg w-full">
              <div className="flex items-center gap-2 mb-2">
                <Layers className="w-4 h-4 text-purple-500" />
                <span className="text-xs text-gray-500 uppercase">Решение</span>
              </div>
              <div className={`text-lg font-bold ${decisionSource === 'HYBRID BOOST' ? 'text-purple-600' : decisionSource === 'SHADOW' ? 'text-amber-500' : 'text-gray-600'}`}>
                {decisionSource}
              </div>
            </div>
          </Tooltip>
          
          <Tooltip text="Режим Shadow: CNN работает параллельно с правилами для сравнения результатов.">
            <div className="p-4 bg-white rounded-lg w-full">
              <div className="flex items-center gap-2 mb-2">
                <Eye className="w-4 h-4 text-cyan-500" />
                <span className="text-xs text-gray-500 uppercase">Shadow</span>
              </div>
              <div className={`text-2xl font-bold ${shadowStatus?.enabled ? 'text-emerald-500' : 'text-gray-400'}`}>
                {shadowStatus?.enabled ? 'ВКЛ' : 'ВЫКЛ'}
              </div>
            </div>
          </Tooltip>
          
          <Tooltip text="Количество сравнений между MOCK-правилами и CNN-моделью.">
            <div className="p-4 bg-white rounded-lg w-full">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-4 h-4 text-emerald-500" />
                <span className="text-xs text-gray-500 uppercase">Сравнения</span>
              </div>
              <div className="text-2xl font-bold text-gray-800">{shadowStatus?.stats?.totalComparisons || 0}</div>
            </div>
          </Tooltip>
          
          <Tooltip text="Процент совпадений меток между правилами (MOCK) и нейросетью (CNN).">
            <div className="p-4 bg-white rounded-lg w-full">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="w-4 h-4 text-emerald-500" />
                <span className="text-xs text-gray-500 uppercase">Совпадение</span>
              </div>
              <div className="text-2xl font-bold text-gray-800">
                {shadowStatus?.stats?.labelMatchRate ? `${Math.round(shadowStatus.stats.labelMatchRate * 100)}%` : '—'}
              </div>
            </div>
          </Tooltip>
          
          <Tooltip text="Средняя задержка обработки запроса через CNN-модель.">
            <div className="p-4 bg-white rounded-lg w-full">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-4 h-4 text-amber-500" />
                <span className="text-xs text-gray-500 uppercase">Задержка</span>
              </div>
              <div className="text-2xl font-bold text-gray-800">
                {shadowStatus?.stats?.avgLatencyMs ? `${Math.round(shadowStatus.stats.avgLatencyMs)}ms` : '—'}
              </div>
            </div>
          </Tooltip>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-gray-100 flex-wrap h-auto gap-1 p-1">
            <TabsTrigger value="overview" className="data-[state=active]:bg-white data-[state=active]:text-gray-800">
              <Activity className="w-4 h-4 mr-2" /> Обзор
            </TabsTrigger>
            <TabsTrigger value="decision-stack" className="data-[state=active]:bg-white data-[state=active]:text-gray-800">
              <Layers className="w-4 h-4 mr-2" /> Стек решений
            </TabsTrigger>
            <TabsTrigger value="booster" className="data-[state=active]:bg-white data-[state=active]:text-gray-800">
              <Sparkles className="w-4 h-4 mr-2" /> Бустер
            </TabsTrigger>
            <TabsTrigger value="bullish" className="data-[state=active]:bg-white data-[state=active]:text-gray-800">
              <TrendingUp className="w-4 h-4 mr-2" /> CNN-анализ
            </TabsTrigger>
            <TabsTrigger value="test" className="data-[state=active]:bg-white data-[state=active]:text-gray-800">
              <FlaskConical className="w-4 h-4 mr-2" /> Тестирование
            </TabsTrigger>
            <TabsTrigger value="dataset" className="data-[state=active]:bg-white data-[state=active]:text-gray-800">
              <Database className="w-4 h-4 mr-2" /> Датасет
            </TabsTrigger>
            <TabsTrigger value="logs" className="data-[state=active]:bg-white data-[state=active]:text-gray-800">
              <History className="w-4 h-4 mr-2" /> Логи
            </TabsTrigger>
            <TabsTrigger value="ml-data" className="data-[state=active]:bg-white data-[state=active]:text-gray-800">
              <Database className="w-4 h-4 mr-2" /> Данные ML
            </TabsTrigger>
          </TabsList>

          {/* ======================== TAB: Обзор ======================== */}
          <TabsContent value="overview" className="mt-6 space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Settings className="w-4 h-4" />
                  Быстрое управление
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-6">
                  <div className="flex items-center gap-3">
                    <Tooltip text="Включает параллельную работу CNN. Нейросеть анализирует текст одновременно с правилами, результаты сравниваются.">
                      <Label className="text-sm cursor-help">Shadow Mode</Label>
                    </Tooltip>
                    <Switch checked={shadowStatus?.enabled || false} onCheckedChange={toggleShadowMode} disabled={actionLoading === 'shadow'} data-testid="shadow-toggle" />
                  </div>
                  <div className="flex items-center gap-3">
                    <Tooltip text="Гибридный бустер повышает уверенность, когда CNN видит позитив, а правила — нейтраль. Метка не меняется.">
                      <Label className="text-sm cursor-help">Гибридный бустер (Hybrid Booster)</Label>
                    </Tooltip>
                    <Switch checked={boosterStatus?.enabled || false} onCheckedChange={toggleBooster} disabled={actionLoading === 'booster' || !shadowStatus?.enabled} data-testid="booster-toggle" />
                    {!shadowStatus?.enabled && (
                      <span className="text-xs text-amber-600">Сначала включите Shadow</span>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* ======================== TAB: Стек решений ======================== */}
          <TabsContent value="decision-stack" className="mt-6 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Layers className="w-5 h-5 text-indigo-600" />
                  Стек решений — как формируется результат
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {/* Step 1: MOCK */}
                  <div className="p-4 bg-blue-50 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="inline-flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-blue-600 rounded-full">1</span>
                      <span className="font-semibold text-blue-800">MOCK-правила (источник истины)</span>
                      <span className="text-emerald-700 font-medium text-sm ml-auto flex items-center gap-1">
                        <Lock className="w-3 h-3" /> Авторитет метки
                      </span>
                    </div>
                    <div className="text-sm text-blue-700 space-y-1">
                      <p>Правила на основе лексикона, грамматики и крипто-паттернов</p>
                      <p>Выход: Метка, Оценка (0-1), Уверенность, Причины, Флаги</p>
                      <p><strong>Эта метка — финальная.</strong> CNN не может её переопределить.</p>
                    </div>
                  </div>
                  
                  <div className="flex justify-center"><ArrowDown className="w-6 h-6 text-slate-400" /></div>
                  
                  {/* Step 2: CNN */}
                  <div className="p-4 bg-purple-50 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="inline-flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-purple-600 rounded-full">2</span>
                      <span className="font-semibold text-purple-800">CNN Shadow (наблюдатель)</span>
                      <span className="text-slate-500 font-medium text-sm ml-auto flex items-center gap-1">
                        <Eye className="w-3 h-3" /> Только чтение
                      </span>
                    </div>
                    <div className="text-sm text-purple-700 space-y-1">
                      <p>Нейросеть работает параллельно с правилами</p>
                      <p>Статус: {shadowStatus?.enabled ? <span className="text-emerald-600 font-semibold">ВКЛЮЧЁН</span> : <span className="text-slate-400">ВЫКЛЮЧЕН</span>}</p>
                      <p><strong>Не может изменить финальную метку</strong></p>
                    </div>
                  </div>
                  
                  <div className="flex justify-center"><ArrowDown className="w-6 h-6 text-slate-400" /></div>
                  
                  {/* Step 3: Hybrid */}
                  <div className="p-4 bg-amber-50 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="inline-flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-amber-600 rounded-full">3</span>
                      <span className="font-semibold text-amber-800">Гибридная логика (Booster)</span>
                      <span className={`text-sm font-medium ml-auto ${boosterStatus?.enabled ? 'text-emerald-600' : 'text-slate-500'}`}>
                        {boosterStatus?.enabled ? 'АКТИВЕН' : 'НЕАКТИВЕН'}
                      </span>
                    </div>
                    <div className="text-sm text-amber-700 space-y-1">
                      <p><strong>Условия для буста (все обязательны):</strong></p>
                      <div className="grid grid-cols-2 gap-2 mt-2">
                        <div className="flex items-center gap-1"><CheckCircle className="w-4 h-4 text-emerald-500" /><span>MOCK-метка = NEUTRAL</span></div>
                        <div className="flex items-center gap-1"><CheckCircle className="w-4 h-4 text-emerald-500" /><span>CNN-метка = POSITIVE</span></div>
                        <div className="flex items-center gap-1"><CheckCircle className="w-4 h-4 text-emerald-500" /><span>CNN уверенность &ge; {cnnThreshold}%</span></div>
                        <div className="flex items-center gap-1"><CheckCircle className="w-4 h-4 text-emerald-500" /><span>Нет конфликтных флагов</span></div>
                      </div>
                      <p className="mt-2"><strong>Эффект:</strong> Уверенность +15% (максимум 85%), метка не меняется</p>
                    </div>
                  </div>
                  
                  <div className="flex justify-center"><ArrowDown className="w-6 h-6 text-slate-400" /></div>
                  
                  {/* Step 4: Final */}
                  <div className="p-4 bg-emerald-50 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="inline-flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-emerald-600 rounded-full">4</span>
                      <span className="font-semibold text-emerald-800">Финальный результат</span>
                    </div>
                    <div className="text-sm text-emerald-700 space-y-1">
                      <p><strong>Метка:</strong> Всегда от MOCK (POSITIVE / NEUTRAL / NEGATIVE)</p>
                      <p><strong>Уверенность:</strong> MOCK + буст (если применён)</p>
                      <p><strong>Флаги:</strong> Включает cnn_positive_boost, если бустер сработал</p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* ======================== TAB: Бустер ======================== */}
          <TabsContent value="booster" className="mt-6 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-purple-600" />
                  Управление гибридным бустером
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 bg-slate-50 rounded-lg">
                    <div className="flex items-center justify-between">
                      <div>
                        <Label className="font-medium">CNN Shadow Mode</Label>
                        <p className="text-xs text-slate-500 mt-1">Параллельная обработка нейросетью</p>
                      </div>
                      <Switch checked={shadowStatus?.enabled || false} onCheckedChange={toggleShadowMode} disabled={actionLoading === 'shadow'} />
                    </div>
                  </div>
                  <div className="p-4 bg-slate-50 rounded-lg">
                    <div className="flex items-center justify-between">
                      <div>
                        <Label className="font-medium">Гибридный бустер</Label>
                        <p className="text-xs text-slate-500 mt-1">Повышение уверенности при совпадении условий</p>
                      </div>
                      <Switch checked={boosterStatus?.enabled || false} onCheckedChange={toggleBooster} disabled={actionLoading === 'booster' || !shadowStatus?.enabled} />
                    </div>
                    {!shadowStatus?.enabled && <p className="text-xs text-amber-600 mt-2">Сначала включите Shadow Mode</p>}
                  </div>
                </div>
                
                {/* Threshold */}
                <div className="p-4 bg-purple-50 rounded-lg">
                  <Tooltip text="Минимальная уверенность CNN для применения буста. Чем выше — тем строже условие.">
                    <Label className="font-medium text-purple-700 cursor-help">
                      Порог CNN уверенности (CNN Confidence Threshold): {cnnThreshold}%
                    </Label>
                  </Tooltip>
                  <input type="range" min="50" max="90" step="5"
                    value={cnnThreshold}
                    onChange={(e) => updateThreshold(parseInt(e.target.value) / 100)}
                    disabled={actionLoading === 'threshold'}
                    className="w-full h-2 bg-purple-200 rounded-lg appearance-none cursor-pointer accent-purple-600 mt-3"
                    data-testid="cnn-threshold-slider"
                  />
                  <div className="flex justify-between text-xs text-purple-600 mt-1">
                    <span>50%</span><span>60%</span><span>70%</span><span>80%</span><span>90%</span>
                  </div>
                </div>
                
                {boosterStatus && (
                  <div className="grid grid-cols-3 gap-4">
                    <div className="p-3 bg-white rounded text-center">
                      <p className="text-xs text-slate-500">Порог (Threshold)</p>
                      <p className="text-lg font-semibold">{Math.round((boosterStatus.config?.cnnConfidenceThreshold || 0.7) * 100)}%</p>
                    </div>
                    <div className="p-3 bg-white rounded text-center">
                      <p className="text-xs text-slate-500">Макс. буст (Max Boost)</p>
                      <p className="text-lg font-semibold">+{Math.round((boosterStatus.config?.maxBoost || 0.15) * 100)}%</p>
                    </div>
                    <div className="p-3 bg-white rounded text-center">
                      <p className="text-xs text-slate-500">Потолок (Confidence Cap)</p>
                      <p className="text-lg font-semibold">{Math.round((boosterStatus.config?.confidenceCap || 0.85) * 100)}%</p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ======================== TAB: CNN-анализ ======================== */}
          <TabsContent value="bullish" className="mt-6 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-emerald-600" />
                  CNN-анализ: бычьи сигналы
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="p-4 bg-blue-50 rounded-lg">
                  <div className="flex items-start gap-2">
                    <Info className="w-5 h-5 text-blue-600 mt-0.5" />
                    <div>
                      <p className="font-medium text-blue-800">Почему CNN более бычья</p>
                      <p className="text-sm text-blue-700 mt-1">
                        CNN обучена на общих данных настроений и видит позитивные сигналы в крипто-заголовках и сленге,
                        которые правила консервативно маркируют как NEUTRAL. Это не баг — это фича, которую мы используем через бустер.
                      </p>
                    </div>
                  </div>
                </div>
                
                {sessionStatus && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="p-4 bg-white rounded-lg">
                      <Tooltip text="Процент расхождений между MOCK и CNN метками.">
                        <p className="text-xs text-slate-500 cursor-help">Расхождение (Mismatch Rate)</p>
                      </Tooltip>
                      <p className="text-2xl font-bold text-amber-600">{sessionStatus.labels?.mismatchRate || 0}%</p>
                    </div>
                    <div className="p-4 bg-white rounded-lg">
                      <p className="text-xs text-slate-500">CNN POSITIVE</p>
                      <p className="text-2xl font-bold text-emerald-600">{sessionStatus.labels?.cnn?.POSITIVE || 0}</p>
                    </div>
                    <div className="p-4 bg-white rounded-lg">
                      <p className="text-xs text-slate-500">MOCK POSITIVE</p>
                      <p className="text-2xl font-bold text-blue-600">{sessionStatus.labels?.mock?.POSITIVE || 0}</p>
                    </div>
                    <div className="p-4 bg-white rounded-lg">
                      <Tooltip text="Случаи, когда MOCK = NEUTRAL, а CNN = POSITIVE. Кандидаты для буста.">
                        <p className="text-xs text-slate-500 cursor-help">Кандидаты на буст</p>
                      </Tooltip>
                      <p className="text-2xl font-bold text-purple-600">{datasetStats?.byMismatchType?.MOCK_NEUTRAL_CNN_POSITIVE || 0}</p>
                    </div>
                  </div>
                )}
                
                {/* Label Distribution */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Card>
                    <CardHeader className="pb-2"><CardTitle className="text-sm">Распределение MOCK-меток</CardTitle></CardHeader>
                    <CardContent>
                      {sessionStatus?.labels?.mock && (
                        <div className="space-y-2">
                          {['POSITIVE', 'NEUTRAL', 'NEGATIVE'].map(label => (
                            <div key={label} className="flex items-center gap-2">
                              <div className="w-20 text-xs">{label}</div>
                              <Progress value={(sessionStatus.labels.mock[label] || 0) / (sessionStatus.collection?.tweetsProcessed || 1) * 100} className="flex-1 h-2" />
                              <div className="w-8 text-xs text-right">{sessionStatus.labels.mock[label] || 0}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader className="pb-2"><CardTitle className="text-sm">Распределение CNN-меток</CardTitle></CardHeader>
                    <CardContent>
                      {sessionStatus?.labels?.cnn && (
                        <div className="space-y-2">
                          {['POSITIVE', 'NEUTRAL', 'NEGATIVE'].map(label => (
                            <div key={label} className="flex items-center gap-2">
                              <div className="w-20 text-xs">{label}</div>
                              <Progress value={(sessionStatus.labels.cnn[label] || 0) / (sessionStatus.collection?.tweetsProcessed || 1) * 100} className="flex-1 h-2" />
                              <div className="w-8 text-xs text-right">{sessionStatus.labels.cnn[label] || 0}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </div>
                
                {/* Main Mismatch Pattern */}
                <div className="p-4 bg-amber-50 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp className="w-5 h-5 text-amber-600" />
                    <span className="font-semibold text-amber-800">Основной паттерн расхождений</span>
                  </div>
                  <div className="flex items-center gap-4 mt-3">
                    <div className="p-3 bg-white rounded text-center">
                      <p className="text-xs text-slate-500">MOCK</p>
                      <LabelBadge label="NEUTRAL" />
                    </div>
                    <ArrowRight className="w-6 h-6 text-amber-500" />
                    <div className="p-3 bg-white rounded text-center">
                      <p className="text-xs text-slate-500">CNN</p>
                      <LabelBadge label="POSITIVE" />
                    </div>
                    <div className="flex-1 p-3 bg-white rounded">
                      <p className="text-xs text-slate-500">Количество</p>
                      <p className="text-xl font-bold text-amber-600">
                        {datasetStats?.byMismatchType?.MOCK_NEUTRAL_CNN_POSITIVE || 0} случаев
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* ======================== TAB: Тестирование ======================== */}
          <TabsContent value="test" className="mt-6 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FlaskConical className="w-5 h-5 text-indigo-600" />
                  Ручное тестирование
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label className="mb-2 block">Текст для анализа</Label>
                  <textarea value={testText} onChange={(e) => setTestText(e.target.value)}
                    placeholder="Вставьте твит, заголовок или любой текст для анализа..."
                    className="w-full h-32 p-3 rounded-lg resize-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    data-testid="test-harness-input"
                  />
                </div>
                <div className="flex gap-2">
                  <Button onClick={runTest} disabled={!testText.trim() || actionLoading === 'test'} className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white" data-testid="test-harness-run">
                    {actionLoading === 'test' ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
                    Запустить анализ
                  </Button>
                  <Button variant="outline" onClick={() => { setTestText(''); setTestResult(null); }}>Очистить</Button>
                </div>
                
                {testResult && (
                  <div className="space-y-4 mt-6">
                    <h3 className="font-semibold text-slate-700 flex items-center gap-2">
                      <CheckCircle className="w-5 h-5 text-emerald-600" />
                      Результаты анализа
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                      <div className="p-3 bg-blue-50 rounded-lg">
                        <p className="text-xs text-blue-600 font-medium mb-1">1. MOCK (Авторитет)</p>
                        <LabelBadge label={testResult.label} />
                        <p className="text-xs text-slate-500 mt-1">Оценка: {testResult.score?.toFixed(3)}</p>
                      </div>
                      <div className="p-3 bg-purple-50 rounded-lg">
                        <p className="text-xs text-purple-600 font-medium mb-1">2. CNN (Shadow)</p>
                        {testResult.hybridBooster?.cnnLabel ? (
                          <>
                            <LabelBadge label={testResult.hybridBooster.cnnLabel} />
                            <p className="text-xs text-slate-500 mt-1">Увер.: {Math.round((testResult.hybridBooster.cnnConfidence || 0) * 100)}%</p>
                          </>
                        ) : (
                          <span className="text-sm text-slate-500">Н/Д</span>
                        )}
                      </div>
                      <div className={`p-3 rounded-lg ${testResult.hybridBooster?.applied ? 'bg-emerald-50 border-emerald-200' : 'bg-slate-50 border-slate-200'}`}>
                        <p className="text-xs text-slate-600 font-medium mb-1">3. Бустер</p>
                        <span className={`text-sm font-medium ${testResult.hybridBooster?.applied ? 'text-emerald-600' : 'text-slate-500'}`}>
                          {testResult.hybridBooster?.applied ? 'ПРИМЕНЁН' : 'НЕ ПРИМЕНЁН'}
                        </span>
                        <p className="text-xs text-slate-500 mt-1">{testResult.hybridBooster?.reason}</p>
                      </div>
                      <div className="p-3 bg-emerald-50 rounded-lg">
                        <p className="text-xs text-emerald-600 font-medium mb-1">4. Финал</p>
                        <LabelBadge label={testResult.label} />
                        <p className="text-xs text-slate-500 mt-1">Увер.: {Math.round((testResult.confidence || 0) * 100)}%</p>
                      </div>
                    </div>
                    
                    {testResult.hybridBooster?.applied && (
                      <div className="p-3 bg-purple-50 rounded-lg">
                        <p className="text-sm font-medium text-purple-700">
                          Уверенность повышена: {Math.round((testResult.hybridBooster.originalConfidence || 0) * 100)}% &rarr; {Math.round((testResult.hybridBooster.boostedConfidence || 0) * 100)}%
                        </p>
                      </div>
                    )}
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {testResult.flags?.length > 0 && (
                        <div className="p-3 bg-white rounded-lg">
                          <p className="text-xs text-slate-500 mb-2">Флаги</p>
                          <div className="flex flex-wrap gap-1">
                            {testResult.flags.map((flag, i) => (
                              <span key={i} className="text-xs text-purple-600">{flag}</span>
                            ))}
                          </div>
                        </div>
                      )}
                      {testResult.reasons?.length > 0 && (
                        <div className="p-3 bg-white rounded-lg">
                          <p className="text-xs text-slate-500 mb-2">Причины</p>
                          <ul className="text-xs text-slate-600 space-y-1">
                            {testResult.reasons.map((reason, i) => <li key={i}>&bull; {reason}</li>)}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ======================== TAB: Датасет ======================== */}
          <TabsContent value="dataset" className="mt-6 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Database className="w-5 h-5 text-indigo-600" />
                  Датасет для переобучения (Retrain Dataset)
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {datasetStats && (
                  <>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className="p-4 bg-white rounded-lg">
                        <p className="text-xs text-slate-500">Всего собрано</p>
                        <p className="text-2xl font-bold">{datasetStats.total}</p>
                      </div>
                      <div className="p-4 bg-white rounded-lg">
                        <p className="text-xs text-slate-500">Валидных</p>
                        <p className="text-2xl font-bold text-emerald-600">{datasetStats.validForRetrain}</p>
                      </div>
                      <div className="p-4 bg-white rounded-lg">
                        <p className="text-xs text-slate-500">Цель</p>
                        <p className="text-2xl font-bold text-indigo-600">500+</p>
                      </div>
                      <div className="p-4 bg-white rounded-lg">
                        <p className="text-xs text-slate-500">Прогресс</p>
                        <p className="text-2xl font-bold">
                          {datasetStats.validForRetrain >= 500 ? <CheckCircle className="w-6 h-6 text-emerald-500 inline" /> : `${Math.round(datasetStats.validForRetrain / 500 * 100)}%`}
                        </p>
                      </div>
                    </div>
                    
                    <div className="p-4 bg-slate-50 rounded-lg">
                      <p className="text-sm font-medium mb-3">Баланс меток (Label Balance)</p>
                      <div className="grid grid-cols-3 gap-4">
                        {[
                          { key: 'positiveRatio', label: 'POSITIVE', color: 'text-emerald-600', target: '25-35%' },
                          { key: 'neutralRatio', label: 'NEUTRAL', color: 'text-amber-600', target: '35-45%' },
                          { key: 'negativeRatio', label: 'NEGATIVE', color: 'text-red-600', target: '25-35%' },
                        ].map(({ key, label, color, target }) => (
                          <div key={key} className="text-center">
                            <p className="text-xs text-slate-500">{label}</p>
                            <p className={`text-lg font-semibold ${color}`}>{Math.round((datasetStats.balance?.[key] || 0) * 100)}%</p>
                            <p className="text-xs text-slate-400">цель: {target}</p>
                          </div>
                        ))}
                      </div>
                      <div className="mt-3 text-center">
                        <span className={`text-sm font-medium ${datasetStats.balance?.isBalanced ? 'text-emerald-600' : 'text-amber-600'}`}>
                          {datasetStats.balance?.isBalanced ? 'СБАЛАНСИРОВАН' : 'ДИСБАЛАНС'}
                        </span>
                      </div>
                    </div>
                    
                    <div className="p-4 bg-blue-50 rounded-lg">
                      <p className="font-medium text-blue-800 mb-2">Готовность к переобучению (Retrain Readiness)</p>
                      <div className="space-y-2">
                        {[
                          { check: datasetStats.validForRetrain >= 500, text: 'Минимум сэмплов (500+)' },
                          { check: datasetStats.balance?.neutralRatio >= 0.3, text: 'NEUTRAL ratio >= 30%' },
                          { check: datasetStats.balance?.isBalanced, text: 'Баланс классов приемлем', warn: true },
                        ].map(({ check, text, warn }) => (
                          <div key={text} className="flex items-center gap-2">
                            {check ? <CheckCircle className="w-4 h-4 text-emerald-500" /> : warn ? <AlertTriangle className="w-4 h-4 text-amber-500" /> : <XCircle className="w-4 h-4 text-red-500" />}
                            <span className="text-sm">{text}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ======================== TAB: Логи ======================== */}
          <TabsContent value="logs" className="mt-6 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <History className="w-5 h-5 text-slate-600" />
                  История изменений
                </CardTitle>
              </CardHeader>
              <CardContent>
                {toggleHistory.length === 0 ? (
                  <p className="text-sm text-slate-500 text-center py-8">Нет изменений в этой сессии</p>
                ) : (
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {toggleHistory.map((entry) => (
                      <div key={entry.id} className="flex items-center justify-between p-2 bg-slate-50 rounded text-sm">
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-slate-600">{entry.type}</span>
                          <span className="text-slate-600">
                            {typeof entry.value === 'boolean' ? (entry.value ? 'ВКЛЮЧЁН' : 'ВЫКЛЮЧЕН') : entry.value}
                          </span>
                        </div>
                        <span className="text-xs text-slate-400">{new Date(entry.timestamp).toLocaleTimeString()}</span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Статистика Shadow-сравнений</CardTitle>
              </CardHeader>
              <CardContent>
                {shadowStatus?.stats && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div><p className="text-slate-500">Всего сравнений</p><p className="font-semibold">{shadowStatus.stats.totalComparisons}</p></div>
                    <div><p className="text-slate-500">Совпадение меток</p><p className="font-semibold">{shadowStatus.stats.labelMatchRate ? `${Math.round(shadowStatus.stats.labelMatchRate * 100)}%` : '—'}</p></div>
                    <div><p className="text-slate-500">Ср. разница оценки</p><p className="font-semibold">{shadowStatus.stats.avgScoreDiff?.toFixed(3) || '—'}</p></div>
                    <div><p className="text-slate-500">Процент ошибок</p><p className="font-semibold">{shadowStatus.stats.errorRate ? `${Math.round(shadowStatus.stats.errorRate * 100)}%` : '0%'}</p></div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ======================== TAB: Данные ML ======================== */}
          <TabsContent value="ml-data" className="mt-6 space-y-6">
            {/* ML Readiness Card */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-indigo-500" />
                  Готовность ML-модели
                </CardTitle>
              </CardHeader>
              <CardContent>
                {mlData?.mlReadiness ? (() => {
                  const r = mlData.mlReadiness;
                  const statusCfg = {
                    READY: { label: 'ГОТОВА К ОБУЧЕНИЮ', cls: 'text-emerald-600 bg-emerald-50', icon: CheckCircle },
                    MINIMUM_MET: { label: 'МИНИМУМ НАБРАН', cls: 'text-amber-600 bg-amber-50', icon: AlertTriangle },
                    NOT_READY: { label: 'НЕДОСТАТОЧНО ДАННЫХ', cls: 'text-red-600 bg-red-50', icon: XCircle },
                  }[r.status] || { label: r.status, cls: 'text-gray-600 bg-gray-50', icon: Activity };
                  const StatusIcon = statusCfg.icon;
                  return (
                    <div className="space-y-4">
                      {/* Status Badge */}
                      <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-semibold ${statusCfg.cls}`}>
                        <StatusIcon className="w-4 h-4" />
                        {statusCfg.label}
                      </div>
                      
                      {/* Progress Bar */}
                      <div>
                        <div className="flex justify-between text-xs text-slate-500 mb-1">
                          <span>Направленные сэмплы: {r.dirSamples}</span>
                          <span>Минимум: {r.minThreshold} / Оптимум: {r.goodThreshold}</span>
                        </div>
                        <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                          <div 
                            className={`h-full rounded-full transition-all duration-500 ${
                              r.progress >= 100 ? 'bg-emerald-500' : r.progress >= 70 ? 'bg-amber-500' : 'bg-red-400'
                            }`}
                            style={{ width: `${Math.min(100, r.progress)}%` }}
                          />
                        </div>
                        {r.dirSamples < r.goodThreshold && (
                          <p className="text-xs text-slate-400 mt-1">
                            До оптимума: ещё {r.goodThreshold - r.dirSamples} записей
                          </p>
                        )}
                      </div>
                      
                      {/* Key Metrics */}
                      <div className="grid grid-cols-2 gap-3 mt-3">
                        <div className="p-3 bg-gray-50 rounded-lg">
                          <p className="text-xs text-slate-500">Shadow ML решения</p>
                          <p className="text-xl font-bold text-slate-800">{r.shadowDecisions}</p>
                        </div>
                        <div className="p-3 bg-gray-50 rounded-lg">
                          <p className="text-xs text-slate-500">Направленные сэмплы</p>
                          <p className="text-xl font-bold text-slate-800">{r.dirSamples}</p>
                        </div>
                      </div>
                    </div>
                  );
                })() : (
                  <div className="flex items-center gap-2 text-slate-500">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="text-sm">Загрузка данных...</span>
                  </div>
                )}
              </CardContent>
            </Card>
            
            {/* Collections Table */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <Database className="w-4 h-4 text-indigo-500" />
                  Накопление данных по коллекциям
                </CardTitle>
              </CardHeader>
              <CardContent>
                {mlData?.collections ? (
                  <div className="space-y-2">
                    {Object.entries(mlData.collections)
                      .sort((a, b) => b[1].count - a[1].count)
                      .map(([key, val]) => (
                        <div key={key} className="flex items-center justify-between p-2.5 bg-gray-50/70 rounded-lg">
                          <div>
                            <span className="text-sm text-slate-700">{val.label}</span>
                            <span className="text-xs text-slate-400 ml-2">({key})</span>
                          </div>
                          <span className={`text-sm font-bold ${val.count > 0 ? 'text-slate-800' : 'text-slate-400'}`}>
                            {val.count.toLocaleString()}
                          </span>
                        </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-slate-500">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="text-sm">Загрузка...</span>
                  </div>
                )}
                {mlData?.timestamp && (
                  <p className="text-xs text-slate-400 mt-3">
                    Обновлено: {new Date(mlData.timestamp).toLocaleTimeString()}
                  </p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

        </Tabs>
      </div>
    </AdminLayout>
  );
}
