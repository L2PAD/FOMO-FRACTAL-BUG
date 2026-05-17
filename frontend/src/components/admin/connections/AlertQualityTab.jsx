/**
 * Alert Quality Model (AQM) Admin Tab - Phase 5.A.3
 * 
 * Features:
 * - Distribution: HIGH/MEDIUM/LOW/NOISE
 * - Weights editor
 * - Fatigue controls
 * - Dry-run tester
 */
import { useState, useEffect, useCallback } from 'react';
import { 
  Brain, 
  RefreshCw, 
  Settings, 
  Play, 
  AlertTriangle,
  CheckCircle,
  TrendingUp,
  BarChart3,
  Sliders,
  TestTube
} from 'lucide-react';
import { Button } from '../../ui/button';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

// Stat Card
const StatCard = ({ label, value, color = 'gray', icon: Icon }) => {
  const colors = {
    green: 'bg-emerald-50/70 text-emerald-600',
    yellow: 'bg-amber-50/70 text-amber-600',
    orange: 'bg-orange-50/70 text-orange-600',
    red: 'bg-red-50/70 text-red-500',
    blue: 'bg-blue-50/70 text-blue-600',
    purple: 'bg-purple-50/70 text-purple-600',
    gray: 'bg-slate-50 text-slate-600 ',
  };
  
  return (
    <div className={`rounded-lg p-4 ${colors[color]}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium opacity-75">{label}</span>
        {Icon && <Icon className="w-4 h-4 opacity-50" />}
      </div>
      <span className="text-2xl font-bold">{value}</span>
    </div>
  );
};

// Section Card
const SectionCard = ({ title, icon: Icon, children, action }) => (
  <div className="">
    <div className="flex items-center justify-between">
      <h3 className="text-sm font-medium text-slate-700 flex items-center gap-2">
        {Icon && <Icon className="w-4 h-4 text-slate-400" />}
        {title}
      </h3>
      {action}
    </div>
    <div className="mt-4">{children}</div>
  </div>
);

// Weight Slider
const WeightSlider = ({ label, value, onChange, min = 0, max = 1, step = 0.05, disabled }) => (
  <div className="space-y-1">
    <div className="flex justify-between text-xs">
      <span className="font-medium text-slate-700">{label}</span>
      <span className="text-slate-500">{(value * 100).toFixed(0)}%</span>
    </div>
    <input
      type="range"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => onChange(parseFloat(e.target.value))}
      disabled={disabled}
      className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-purple-500"
    />
  </div>
);

export default function AlertQualityTab({ token }) {
  const [config, setConfig] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [toast, setToast] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [configRes, statsRes] = await Promise.all([
        fetch(`${BACKEND_URL}/api/admin/connections/ml/quality/config`, {
          headers: { 'Authorization': `Bearer ${token}` },
        }),
        fetch(`${BACKEND_URL}/api/admin/connections/ml/quality/stats`, {
          headers: { 'Authorization': `Bearer ${token}` },
        }),
      ]);
      
      const [configData, statsData] = await Promise.all([
        configRes.json(),
        statsRes.json(),
      ]);
      
      if (configData.ok) setConfig(configData.data);
      if (statsData.ok) setStats(statsData.data);
    } catch (err) {
      setToast({ message: 'Не удалось загрузить данные AQM', type: 'error' });
    }
    setLoading(false);
  }, [token]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const updateConfig = async (updates) => {
    setSaving(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/admin/connections/ml/quality/config`, {
        method: 'PATCH',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(updates),
      });
      const data = await res.json();
      if (data.ok) {
        setToast({ message: 'AQM config updated', type: 'success' });
        setConfig(data.data);
      } else {
        setToast({ message: data.message || 'Update failed', type: 'error' });
      }
    } catch (err) {
      setToast({ message: 'Failed to update config', type: 'error' });
    }
    setSaving(false);
  };

  const runDryTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await fetch(`${BACKEND_URL}/api/connections/ml/quality/evaluate`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          alert_type: 'РАННИЙ_ПРОБОЙ',
          scores: { twitter_score: 750, influence: 60, quality: 70, trend: 55, network: 65, consistency: 50 },
          confidence: { score: 72, level: 'HIGH' },
          early_signal: { score: 25, velocity: 2.5, acceleration: 0.3 },
          network: { authority: 0.7, hops_to_elite: 2, elite_exposure_pct: 15 },
          audience: { smart_followers_pct: 35, purity_score: 75 },
          temporal: { last_alert_hours_ago: 48, alert_count_24h: 2 },
          meta: { mode: 'MOCK', pilot_account: false },
        }),
      });
      const data = await res.json();
      if (data.ok) {
        setTestResult(data.data);
      }
    } catch (err) {
      setToast({ message: 'Test failed', type: 'error' });
    }
    setTesting(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="w-6 h-6 animate-spin text-slate-400" />
        <span className="ml-2 text-slate-500">Загрузка AQM...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {toast && (
        <div className={`fixed bottom-4 right-4 px-4 py-3 rounded-lg  text-white z-50 ${
          toast.type === 'success' ? 'bg-green-500' : 'bg-red-500'
        }`}>
          {toast.message}
        </div>
      )}

      {/* Header */}
      <div className="p-4 rounded-lg bg-purple-50/70">
        <div className="flex items-start gap-3">
          <Brain className="w-6 h-6 text-purple-500 mt-0.5" />
          <div>
            <h3 className="font-semibold text-purple-900">Модель качества алертов (AQM)</h3>
            <p className="text-sm text-purple-700 mt-1">
              Оценка полезности алертов. Высокий балл = отправка, Шум = подавление.
            </p>
          </div>
          <div className="ml-auto">
            <span className={`text-sm font-medium ${
              config?.enabled ? 'text-emerald-600' : 'text-slate-500'
            }`}>
              {config?.enabled ? 'Включён' : 'Отключён'}
            </span>
          </div>
        </div>
      </div>

      {/* Distribution Stats */}
      <SectionCard title="Распределение меток (24ч)" icon={BarChart3}>
        <div className="grid grid-cols-4 gap-4">
          <StatCard 
            label="ВЫСОКИЙ" 
            value={stats?.distribution?.HIGH || 0} 
            color="green"
            icon={CheckCircle}
          />
          <StatCard 
            label="СРЕДНИЙ" 
            value={stats?.distribution?.MEDIUM || 0} 
            color="yellow"
            icon={TrendingUp}
          />
          <StatCard 
            label="НИЗКИЙ" 
            value={stats?.distribution?.LOW || 0} 
            color="orange"
            icon={AlertTriangle}
          />
          <StatCard 
            label="ШУМ" 
            value={stats?.distribution?.NOISE || 0} 
            color="red"
            icon={AlertTriangle}
          />
        </div>
        <div className="mt-4 text-sm text-slate-500">
          <span className="font-medium">Подавлено:</span> {stats?.suppressed_count || 0} алертов заблокировано AQM
        </div>
      </SectionCard>

      {/* Weights Editor */}
      <SectionCard 
        title="Веса скоринга" 
        icon={Sliders}
        action={
          <span className="text-xs text-slate-400">v{config?.version || '1.0.0'}</span>
        }
      >
        <div className="grid grid-cols-2 gap-6">
          <div className="space-y-4">
            <WeightSlider
              label="Ранний сигнал"
              value={config?.weights?.early_signal || 0.30}
              onChange={(v) => updateConfig({ weights: { ...config.weights, early_signal: v }})}
              disabled={saving}
            />
            <WeightSlider
              label="Уверенность"
              value={config?.weights?.confidence || 0.25}
              onChange={(v) => updateConfig({ weights: { ...config.weights, confidence: v }})}
              disabled={saving}
            />
            <WeightSlider
              label="Умные подписчики"
              value={config?.weights?.smart_followers || 0.20}
              onChange={(v) => updateConfig({ weights: { ...config.weights, smart_followers: v }})}
              disabled={saving}
            />
          </div>
          <div className="space-y-4">
            <WeightSlider
              label="Авторитетность"
              value={config?.weights?.authority || 0.15}
              onChange={(v) => updateConfig({ weights: { ...config.weights, authority: v }})}
              disabled={saving}
            />
            <WeightSlider
              label="Усталость алертов"
              value={config?.weights?.alert_fatigue || 0.10}
              onChange={(v) => updateConfig({ weights: { ...config.weights, alert_fatigue: v }})}
              disabled={saving}
            />
            <div className="text-xs text-yellow-600 flex items-center gap-1 mt-2">
              <AlertTriangle className="w-3 h-3" />
              Веса должны давать в сумме 1.0 (исключая усталость)
            </div>
          </div>
        </div>
      </SectionCard>

      {/* Thresholds */}
      <SectionCard title="Пороги" icon={Settings}>
        <div className="grid grid-cols-4 gap-4">
          <div className="p-3 bg-green-50 rounded-lg border border-green-100">
            <div className="text-xs text-green-600 mb-1">Порог HIGH</div>
            <div className="text-xl font-bold text-green-700">
              ≥{((config?.thresholds?.high || 0.75) * 100).toFixed(0)}%
            </div>
            <div className="text-xs text-green-500">→ SEND</div>
          </div>
          <div className="p-3 bg-yellow-50 rounded-lg border border-yellow-100">
            <div className="text-xs text-yellow-600 mb-1">Порог MEDIUM</div>
            <div className="text-xl font-bold text-yellow-700">
              ≥{((config?.thresholds?.medium || 0.55) * 100).toFixed(0)}%
            </div>
            <div className="text-xs text-yellow-500">→ SEND</div>
          </div>
          <div className="p-3 bg-orange-50 rounded-lg border border-orange-100">
            <div className="text-xs text-orange-600 mb-1">Порог LOW</div>
            <div className="text-xl font-bold text-orange-700">
              ≥{((config?.thresholds?.low || 0.40) * 100).toFixed(0)}%
            </div>
            <div className="text-xs text-orange-500">→ SEND_LOW_PRIORITY</div>
          </div>
          <div className="p-3 bg-red-50 rounded-lg border border-red-100">
            <div className="text-xs text-red-600 mb-1">Порог NOISE</div>
            <div className="text-xl font-bold text-red-700">
              &lt;{((config?.thresholds?.low || 0.40) * 100).toFixed(0)}%
            </div>
            <div className="text-xs text-red-500">→ SUPPRESS</div>
          </div>
        </div>
      </SectionCard>

      {/* Dry-Run Tester */}
      <SectionCard 
        title="Тестер (Dry-Run)" 
        icon={TestTube}
        action={
          <Button size="sm" onClick={runDryTest} disabled={testing} data-testid="run-aqm-test">
            {testing ? <RefreshCw className="w-4 h-4 animate-spin mr-1" /> : <Play className="w-4 h-4 mr-1" />}
            Run Test
          </Button>
        }
      >
        <p className="text-sm text-slate-600 mb-4">
          Test AQM with a sample alert context to see the evaluation result.
        </p>
        
        {testResult && (
          <div className="bg-slate-50 rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-700">Result:</span>
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                testResult.label === 'HIGH' ? 'text-emerald-600' :
                testResult.label === 'MEDIUM' ? 'text-amber-600' :
                testResult.label === 'LOW' ? 'text-orange-600' :
                'text-red-500'
              }`}>
                {testResult.label} ({(testResult.probability * 100).toFixed(0)}%)
              </span>
            </div>
            <div className="text-sm">
              <span className="font-medium text-slate-700">Recommendation:</span>
              <span className={`ml-2 ${
                testResult.recommendation === 'SEND' ? 'text-green-600' :
                testResult.recommendation === 'SEND_LOW_PRIORITY' ? 'text-yellow-600' :
                'text-red-600'
              }`}>
                {testResult.recommendation}
              </span>
            </div>
            {testResult.explain && (
              <div className="text-sm space-y-1">
                <div className="text-slate-700 font-medium">Explanation:</div>
                <div className="text-green-600">
                  ✓ {testResult.explain.top_positive_factors?.slice(0, 2).join(', ') || 'N/A'}
                </div>
                <div className="text-red-600">
                  ✗ {testResult.explain.top_negative_factors?.slice(0, 2).join(', ') || 'N/A'}
                </div>
              </div>
            )}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
