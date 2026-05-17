/**
 * Admin Backtesting Page
 * ML Quality Control Dashboard
 */
import { useState, useEffect } from 'react';
import AdminLayout from '../../components/admin/AdminLayout';
import { api } from '../../api/client';
import { 
  BarChart3, RefreshCw, Loader2, AlertTriangle, 
  CheckCircle, TrendingUp, Target, Activity,
} from 'lucide-react';

const NETWORKS = [
  { id: 'ethereum', name: 'Ethereum' },
  { id: 'arbitrum', name: 'Arbitrum' },
  { id: 'optimism', name: 'Optimism' },
  { id: 'base', name: 'Base' },
  { id: 'polygon', name: 'Polygon' },
];

const WINDOWS = [
  { value: '7', label: '7 дней' },
  { value: '14', label: '14 дней' },
  { value: '30', label: '30 дней' },
  { value: '60', label: '60 дней' },
];

function KPICard({ title, value, threshold, icon: Icon, format = 'percent' }) {
  const numValue = typeof value === 'number' ? value : 0;
  const displayValue = format === 'percent' 
    ? `${(numValue * 100).toFixed(1)}%`
    : numValue.toLocaleString();
  
  let color = 'text-slate-900';
  if (threshold) {
    if (numValue >= threshold.good) color = 'text-green-700';
    else if (numValue >= threshold.warning) color = 'text-amber-700';
    else color = 'text-red-700';
  }
  
  return (
    <div className="p-4 rounded-lg bg-gray-50/70" data-testid="kpi-card">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-500 uppercase tracking-wide">{title}</span>
        {Icon && <Icon className="w-4 h-4 text-gray-400" />}
      </div>
      <div className={`text-2xl font-bold ${color}`}>{displayValue}</div>
    </div>
  );
}

function ConfusionMatrix({ data }) {
  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="p-6 rounded-lg bg-gray-50/70">
        <h3 className="text-sm font-semibold text-slate-900 mb-4 flex items-center gap-2">
          <Target className="w-4 h-4 text-blue-600" />
          Матрица ошибок
        </h3>
        <div className="text-center py-8 text-gray-400 text-sm">Нет данных</div>
      </div>
    );
  }
  
  const classes = ['BUY', 'SELL', 'NEUTRAL'];
  const totals = {};
  classes.forEach(actual => {
    totals[actual] = classes.reduce((sum, pred) => sum + (data[actual]?.[pred] || 0), 0);
  });
  
  const getColor = (actual, predicted, value) => {
    const total = totals[actual] || 1;
    const pct = value / total;
    if (actual === predicted) {
      return pct >= 0.6 ? 'text-green-700 font-bold' : pct >= 0.4 ? 'text-green-600' : 'text-amber-600';
    }
    return pct >= 0.3 ? 'text-red-700' : 'text-gray-500';
  };
  
  return (
    <div className="p-6 rounded-lg bg-gray-50/70">
      <h3 className="text-sm font-semibold text-slate-900 mb-3 flex items-center gap-2">
        <Target className="w-4 h-4 text-blue-600" />
        Матрица ошибок
      </h3>
      <p className="text-xs text-gray-400 mb-3">Строки = Факт, Столбцы = Прогноз</p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className="p-2 text-left text-gray-400 text-xs"></th>
              <th className="p-2 text-center text-gray-500 text-xs" colSpan={3}>Прогноз</th>
            </tr>
            <tr>
              <th className="p-2 text-left text-gray-400 text-xs"></th>
              {classes.map(cls => (
                <th key={cls} className="p-2 text-center text-slate-700 text-xs font-medium">{cls}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {classes.map((actual) => (
              <tr key={actual}>
                <td className="p-2 text-slate-600 text-xs font-medium">{actual}</td>
                {classes.map(predicted => {
                  const value = data[actual]?.[predicted] || 0;
                  const total = totals[actual] || 1;
                  const pct = ((value / total) * 100).toFixed(0);
                  return (
                    <td key={predicted} className={`p-3 text-center ${getColor(actual, predicted, value)}`}>
                      <div className="font-bold">{value}</div>
                      <div className="text-xs opacity-60">{pct}%</div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AccuracyChart({ data }) {
  if (!data || data.length === 0) {
    return (
      <div className="p-6 rounded-lg bg-gray-50/70">
        <h3 className="text-sm font-semibold text-slate-900 mb-4 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-blue-600" />
          Точность по времени
        </h3>
        <div className="text-center py-8 text-gray-400 text-sm">Нет исторических данных</div>
      </div>
    );
  }
  
  const maxAcc = Math.max(...data.map(d => d.accuracy), 0.8);
  const minAcc = Math.min(...data.map(d => d.accuracy), 0.3);
  const range = maxAcc - minAcc || 0.1;
  
  return (
    <div className="p-6 rounded-lg bg-gray-50/70">
      <h3 className="text-sm font-semibold text-slate-900 mb-4 flex items-center gap-2">
        <TrendingUp className="w-4 h-4 text-blue-600" />
        Точность по времени
      </h3>
      <div className="h-48 flex items-end gap-1">
        {data.slice(-30).map((d, i) => {
          const height = ((d.accuracy - minAcc) / range) * 100;
          const color = d.accuracy >= 0.6 ? 'bg-green-500' : d.accuracy >= 0.5 ? 'bg-amber-500' : 'bg-red-500';
          return (
            <div key={i} className="flex-1 min-w-[8px] group relative">
              <div className={`w-full rounded-t ${color}`} style={{ height: `${Math.max(height, 5)}%` }} />
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block bg-slate-800 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-10">
                {d.date}: {(d.accuracy * 100).toFixed(1)}%
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function AdminBacktestingPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [network, setNetwork] = useState('ethereum');
  const [windowDays, setWindowDays] = useState('30');
  const [modelVersion, setModelVersion] = useState('ALL');
  const [availableModels, setAvailableModels] = useState([]);
  const [backtest, setBacktest] = useState(null);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    const fetchModels = async () => {
      try {
        const token = localStorage.getItem('admin_token');
        if (!token) return;
        const res = await api.get(`/api/admin/backtest/models?network=${network}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (res.data.ok) setAvailableModels(res.data.data.versions || []);
      } catch {}
    };
    fetchModels();
  }, [network]);

  const runBacktest = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem('admin_token');
      if (!token) { setError('Необходима авторизация'); setLoading(false); return; }
      const headers = { Authorization: `Bearer ${token}` };
      const [backtestRes, historyRes] = await Promise.all([
        api.get(`/api/admin/backtest/market?network=${network}&windowDays=${windowDays}`, { headers }),
        api.get(`/api/admin/backtest/history?network=${network}&limit=30&modelVersion=${modelVersion}`, { headers }),
      ]);
      if (backtestRes.data.ok) setBacktest(backtestRes.data.data);
      if (historyRes.data.ok) setHistory(historyRes.data.data || []);
    } catch (err) {
      setError(err.response?.data?.message || 'Ошибка выполнения');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { runBacktest(); }, []);

  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6 space-y-6" data-testid="backtesting-page">
        {/* Header */}
        <div className="flex items-center gap-3">
          <BarChart3 className="w-5 h-5 text-blue-600" />
          <div>
            <h1 className="text-xl font-semibold text-slate-900">Backtesting</h1>
            <p className="text-xs text-gray-500">Контроль качества ML-моделей</p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-end gap-4 p-5 rounded-lg bg-gray-50/70">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Сеть</label>
            <select value={network} onChange={e => setNetwork(e.target.value)}
              className="px-3 py-2 rounded-lg text-sm bg-gray-50/70 outline-none appearance-none cursor-pointer" data-testid="network-select">
              {NETWORKS.map(n => <option key={n.id} value={n.id}>{n.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Период</label>
            <select value={windowDays} onChange={e => setWindowDays(e.target.value)}
              className="px-3 py-2 rounded-lg text-sm bg-gray-50/70 outline-none appearance-none cursor-pointer" data-testid="window-select">
              {WINDOWS.map(w => <option key={w.value} value={w.value}>{w.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Версия модели</label>
            <select value={modelVersion} onChange={e => setModelVersion(e.target.value)}
              className="px-3 py-2 rounded-lg text-sm bg-gray-50/70 outline-none appearance-none cursor-pointer" data-testid="model-select">
              <option value="ALL">Все версии</option>
              {availableModels.map(v => <option key={v} value={v}>{v}</option>)}
            </select>
          </div>
          <button onClick={runBacktest} disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 transition-colors disabled:opacity-50"
            data-testid="run-backtest-btn">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            Запустить
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-3 p-4 bg-red-50/70 rounded-lg">
            <AlertTriangle className="w-5 h-5 text-red-600" />
            <span className="text-sm text-red-800">{error}</span>
          </div>
        )}

        {/* KPI Summary */}
        {backtest && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KPICard title="Общая точность" value={backtest.summary.accuracy}
              threshold={{ good: 0.6, warning: 0.5 }} icon={Target} />
            <KPICard title="Precision BUY" value={backtest.summary.precisionBuy}
              threshold={{ good: 0.6, warning: 0.5 }} icon={TrendingUp} />
            <KPICard title="Precision SELL" value={backtest.summary.precisionSell}
              threshold={{ good: 0.6, warning: 0.5 }} icon={Activity} />
            <KPICard title="Сэмплы" value={backtest.summary.samples} format="number" icon={BarChart3} />
          </div>
        )}

        {backtest?.summary && (
          <div className="flex items-center gap-4 text-sm text-gray-500">
            <span>Model: <span className="font-bold text-slate-700">{backtest.summary.modelVersion || 'N/A'}</span></span>
            <span>Window: <span className="font-bold text-slate-700">{backtest.summary.window || windowDays + 'd'}</span></span>
            {backtest.note && (
              <span className="text-amber-600 flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" /> {backtest.note}
              </span>
            )}
          </div>
        )}

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <ConfusionMatrix data={backtest?.confusionMatrix} />
          <AccuracyChart data={history} />
        </div>

        {/* Decision Guide */}
        <div className="p-5 rounded-lg bg-gray-50/70">
          <h3 className="text-sm font-semibold text-slate-900 mb-3 flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-blue-600" />
            Руководство по решениям
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div className="flex items-start gap-2">
              <div className="w-1.5 h-1.5 mt-1.5 bg-green-500 rounded-full flex-shrink-0" />
              <div>
                <div className="font-medium text-slate-900">Точность 60%+</div>
                <div className="text-gray-500">ML надёжен. Включить ADVISORY режим.</div>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <div className="w-1.5 h-1.5 mt-1.5 bg-amber-500 rounded-full flex-shrink-0" />
              <div>
                <div className="font-medium text-slate-900">Точность 50-60%</div>
                <div className="text-gray-500">ML маргинален. Наблюдательный режим.</div>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <div className="w-1.5 h-1.5 mt-1.5 bg-red-500 rounded-full flex-shrink-0" />
              <div>
                <div className="font-medium text-slate-900">Точность ниже 50%</div>
                <div className="text-gray-500">ML вреден. Отключить или переобучить.</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
