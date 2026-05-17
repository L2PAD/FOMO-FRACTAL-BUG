/**
 * Sentiment API — Admin Console
 * ==============================
 * /admin/sentiment-api
 *
 * Blocks:
 *   1. Engine Status   — health, version, cache hit rate
 *   2. Test Analyzer   — interactive text → analyze
 *   3. Endpoint Docs   — endpoints, curl examples
 *   4. Metrics         — request counts, latency, label distribution
 */

import { useState, useEffect, useCallback } from 'react';
import AdminLayout from '../../components/admin/AdminLayout';
import { Button } from '../../components/ui/button';
import {
  Activity,
  CheckCircle,
  XCircle,
  RefreshCw,
  Play,
  Copy,
  Server,
  Zap,
  Database,
  FileText,
  BarChart3,
  Clock,
  Loader2,
  ChevronDown,
  ChevronRight,
  Download,
  Trash2,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

// ── Compact stat card ────────────────────────────────────

function Stat({ label, value, sub, color = 'slate' }) {
  const bg = {
    green: 'bg-emerald-50/70',
    blue: 'bg-blue-50/70',
    amber: 'bg-amber-50/70',
    red: 'bg-red-50/70',
    slate: 'bg-slate-50/70',
    violet: 'bg-violet-50/70',
  }[color] || 'bg-slate-50/70';

  return (
    <div data-testid={`stat-${label.toLowerCase().replace(/\s+/g, '-')}`} className={`p-4 rounded-lg ${bg}`}>
      <div className="text-xs text-slate-400 mb-1">{label}</div>
      <div className="text-lg font-semibold text-slate-900">{value}</div>
      {sub && <div className="text-xs text-slate-400 mt-0.5">{sub}</div>}
    </div>
  );
}

// ── Section wrapper ──────────────────────────────────────

function Section({ title, icon: Icon, children, testId }) {
  return (
    <div data-testid={testId} className="bg-white/60 rounded-xl p-5 mb-5">
      <div className="flex items-center gap-2 mb-4">
        {Icon && <Icon size={16} className="text-slate-400" />}
        <h2 className="text-base font-semibold text-slate-800">{title}</h2>
      </div>
      {children}
    </div>
  );
}

// ── Source select ────────────────────────────────────────

const SOURCES = ['twitter', 'news', 'telegram', 'article', 'headline', 'user'];

// ── Main Page ────────────────────────────────────────────

export default function AdminSentimentApiPage() {

  // Health
  const [health, setHealth] = useState(null);
  const [capabilities, setCaps] = useState(null);
  const [metricsData, setMetrics] = useState(null);
  const [loadingHealth, setLoadingHealth] = useState(false);

  // Test analyzer
  const [testText, setTestText] = useState('');
  const [testSource, setTestSource] = useState('twitter');
  const [testResult, setTestResult] = useState(null);
  const [testLoading, setTestLoading] = useState(false);

  // Docs expand
  const [expandedDoc, setExpandedDoc] = useState(null);

  // API Keys
  const [apiKeys, setApiKeys] = useState([]);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyResult, setNewKeyResult] = useState(null);
  const [keyLoading, setKeyLoading] = useState(false);

  // Server config
  const [serverMode, setServerMode] = useState('local');
  const [serverUrl, setServerUrl] = useState('http://localhost:8001');
  const [serverLive, setServerLive] = useState(null); // null=unknown, true=online, false=offline
  const [serverVersion, setServerVersion] = useState(null);
  const [configSaved, setConfigSaved] = useState(false);
  const [configLoading, setConfigLoading] = useState(false);
  const [editingServer, setEditingServer] = useState(false);
  const [editUrl, setEditUrl] = useState('');

  // ── Fetch data ───────────────────────────────────────────

  const fetchAll = useCallback(async () => {
    setLoadingHealth(true);
    try {
      const [hRes, cRes, mRes, kRes, cfgRes] = await Promise.all([
        fetch(`${API}/api/v1/sentiment/health`).then(r => r.json()),
        fetch(`${API}/api/v1/sentiment/capabilities`).then(r => r.json()),
        fetch(`${API}/api/v1/sentiment/metrics`).then(r => r.json()),
        fetch(`${API}/api/v1/sentiment/keys`).then(r => r.json()),
        fetch(`${API}/api/v1/sentiment/config`).then(r => r.json()),
      ]);
      if (hRes.ok) setHealth(hRes.data);
      if (cRes.ok) setCaps(cRes.data);
      if (mRes.ok) setMetrics(mRes.data);
      if (kRes.ok) setApiKeys(kRes.data);
      if (cfgRes.ok && cfgRes.data) {
        setServerMode(cfgRes.data.mode || 'local');
        setServerUrl(cfgRes.data.url || 'http://localhost:8005');
        setServerLive(cfgRes.data.live ?? null);
        setServerVersion(cfgRes.data.version || null);
      }
    } catch (e) {
      console.error('Fetch error:', e);
    } finally {
      setLoadingHealth(false);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) fetchAll();
  }, [isAuthenticated, fetchAll]);

  // Auto-refresh metrics every 30s
  useEffect(() => {
    if (!isAuthenticated) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API}/api/v1/sentiment/metrics`).then(r => r.json());
        if (res.ok) setMetrics(res.data);
      } catch {}
    }, 30000);
    return () => clearInterval(interval);
  }, [isAuthenticated]);

  // ── Test analyze ─────────────────────────────────────────

  const runTest = async () => {
    if (!testText.trim()) return;
    setTestLoading(true);
    setTestResult(null);
    try {
      const headers = { 'Content-Type': 'application/json', 'X-Internal-Service': 'admin-console' };
      // Attach API key if a freshly created key is available
      if (newKeyResult?.key) {
        headers['X-API-Key'] = newKeyResult.key;
      }
      const res = await fetch(`${API}/api/v1/sentiment/analyze`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ text: testText, source: testSource }),
      }).then(r => r.json());
      if (res.ok) setTestResult(res.data);
      else setTestResult({ error: res.error, message: res.message });
    } catch (e) {
      console.error('Test error:', e);
    } finally {
      setTestLoading(false);
    }
  };

  // ── Key management ──────────────────────────────────────

  const saveServerConfig = async (newUrl, newMode) => {
    const urlToSave = newUrl || serverUrl;
    const modeToSave = newMode || serverMode;
    setConfigLoading(true);
    setConfigSaved(false);

    try {
      const res = await fetch(`${API}/api/v1/sentiment/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: modeToSave, url: urlToSave }),
      });
      const json = await res.json();
      if (json.ok) {
        setServerUrl(urlToSave);
        setServerMode(modeToSave);
        setServerLive(true);
        setEditingServer(false);
        setConfigSaved(true);
        setTimeout(() => setConfigSaved(false), 3000);
        // Refresh full config to get version
        fetchAll();
      } else {
        alert(json.message || json.error || 'Ошибка');
      }
    } catch (e) {
      alert(`Сетевая ошибка: ${e.message}`);
    } finally {
      setConfigLoading(false);
    }
  };

  const createKey = async () => {
    if (!newKeyName.trim()) return;
    setKeyLoading(true);
    setNewKeyResult(null);
    try {
      const res = await fetch(`${API}/api/v1/sentiment/keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newKeyName }),
      });
      const json = await res.json();
      if (json.ok) {
        setNewKeyResult(json.data);
        setNewKeyName('');
        const kRes = await fetch(`${API}/api/v1/sentiment/keys`).then(r => r.json());
        if (kRes.ok) setApiKeys(kRes.data);
      } else {
        alert(`Ошибка: ${json.message || json.error || 'Unknown error'}`);
      }
    } catch (e) {
      alert(`Сетевая ошибка: ${e.message}`);
    } finally {
      setKeyLoading(false);
    }
  };

  const revokeKey = async (prefix) => {
    if (!window.confirm(`Отозвать ключ ${prefix}?`)) return;
    try {
      const res = await fetch(`${API}/api/v1/sentiment/keys`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prefix }),
      });
      const json = await res.json();
      if (!json.ok) {
        alert(`Ошибка: ${json.message || json.error}`);
      }
      const kRes = await fetch(`${API}/api/v1/sentiment/keys`).then(r => r.json());
      if (kRes.ok) setApiKeys(kRes.data);
    } catch (e) {
      alert(`Сетевая ошибка: ${e.message}`);
    }
  };

  const deleteKey = async (prefix) => {
    if (!window.confirm(`Удалить ключ ${prefix} навсегда?`)) return;
    try {
      await fetch(`${API}/api/v1/sentiment/keys`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prefix, permanent: true }),
      });
      setNewKeyResult(null);
      const kRes = await fetch(`${API}/api/v1/sentiment/keys`).then(r => r.json());
      if (kRes.ok) setApiKeys(kRes.data);
    } catch (e) {
      alert(`Сетевая ошибка: ${e.message}`);
    }
  };

  // ── Copy helper ──────────────────────────────────────────

  const [copied, setCopied] = useState(null);
  const copyText = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 1500);
  };

  // ── Render ───────────────────────────────────────────────

  if (authLoading) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="animate-spin text-slate-400" size={24} />
        </div>
      </AdminLayout>
    );
  }

  const labelColor = {
    POSITIVE: 'text-emerald-600',
    NEGATIVE: 'text-red-500',
    NEUTRAL: 'text-slate-500',
  };

  const labelBg = {
    POSITIVE: 'bg-emerald-50',
    NEGATIVE: 'bg-red-50',
    NEUTRAL: 'bg-slate-100',
  };

  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 data-testid="page-title" className="text-xl font-semibold text-slate-900">
              Sentiment API
            </h1>
            <p className="text-sm text-slate-400 mt-0.5">
              Управление движком анализа настроений
            </p>
          </div>
          <Button
            data-testid="download-sdk-btn"
            variant="outline"
            size="sm"
            className="gap-2"
            onClick={() => window.open(`${API}/api/v1/sentiment/sdk/zip`, '_blank')}
          >
            <Download size={14} />
            Скачать SDK
          </Button>
        </div>

        {/* ═══ Block 1: Engine Status ═══ */}
        <Section title="Статус движка" icon={Server} testId="engine-status-section">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Stat
              label="Статус"
              value={health?.status || '—'}
              color={health?.status === 'READY' ? 'green' : 'red'}
            />
            <Stat
              label="Uptime"
              value={health?.uptime ? `${Math.floor(health.uptime / 60)}m` : '—'}
              color="blue"
            />
            <Stat
              label="Cache"
              value={metricsData ? `${metricsData.cache.hitRate}%` : '—'}
              sub={metricsData ? `${metricsData.cache.size} / ${metricsData.cache.maxSize}` : ''}
              color="violet"
            />
            <Stat
              label="Avg Latency"
              value={metricsData ? `${metricsData.latency.avgMs} ms` : '—'}
              color="amber"
            />
          </div>

          <div className="flex items-center gap-2 mt-3">
            <Button
              data-testid="refresh-status-btn"
              variant="outline"
              size="sm"
              onClick={fetchAll}
              disabled={loadingHealth}
              className="text-xs"
            >
              {loadingHealth ? <Loader2 size={12} className="animate-spin mr-1" /> : <RefreshCw size={12} className="mr-1" />}
              Обновить
            </Button>
            {health?.status === 'READY' && (
              <span className="flex items-center gap-1 text-xs text-emerald-600">
                <CheckCircle size={12} /> Движок готов
              </span>
            )}
          </div>
        </Section>

        {/* ═══ Block 2: Server Configuration ═══ */}
        <Section title="Настройка сервера" icon={Server} testId="server-config-section">
          {/* Current active server */}
          <div className="p-4 rounded-lg bg-slate-50/80 mb-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className={`w-2.5 h-2.5 rounded-full ${serverLive === true ? 'bg-emerald-400 animate-pulse' : serverLive === false ? 'bg-red-400' : 'bg-slate-300'}`} />
                <span className="text-xs text-slate-400">
                  {serverLive === true ? 'Активен' : serverLive === false ? 'Недоступен' : 'Проверка...'}
                </span>
                <span className="text-xs px-2 py-0.5 rounded bg-slate-200 text-slate-500">{serverMode === 'local' ? 'Локальный' : serverMode === 'server' ? 'Сервер' : 'Домен'}</span>
              </div>
              <div className="flex items-center gap-1">
                {!editingServer && (
                  <>
                    <button
                      data-testid="copy-server-url-btn"
                      onClick={() => copyText(serverUrl, 'server-url')}
                      className="p-1.5 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100"
                      title="Копировать URL"
                    >
                      {copied === 'server-url' ? <CheckCircle size={14} className="text-emerald-500" /> : <Copy size={14} />}
                    </button>
                    <button
                      data-testid="edit-server-btn"
                      onClick={() => { setEditingServer(true); setEditUrl(serverUrl); }}
                      className="px-2 py-1 rounded-md text-xs text-slate-400 hover:text-slate-600 hover:bg-slate-100"
                    >
                      Изменить
                    </button>
                  </>
                )}
                {configSaved && <span className="text-xs text-emerald-600">Сохранено</span>}
              </div>
            </div>
            <div data-testid="current-server-url" className="font-mono text-sm text-slate-800 select-all">
              {serverUrl}
            </div>
          </div>

          {/* Edit mode */}
          {editingServer && (
            <div className="p-4 rounded-lg bg-blue-50/50 space-y-3">
              <div className="flex gap-2">
                {[
                  { id: 'local', label: 'Локальный', def: 'http://localhost:8005' },
                  { id: 'server', label: 'Сервер', def: '' },
                  { id: 'domain', label: 'Домен', def: '' },
                ].map((m) => (
                  <button
                    key={m.id}
                    data-testid={`mode-${m.id}`}
                    onClick={() => {
                      setServerMode(m.id);
                      if (m.def) setEditUrl(m.def);
                    }}
                    className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                      serverMode === m.id
                        ? 'bg-slate-900 text-white'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {m.label}
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-2">
                <input
                  data-testid="server-url-input"
                  className="flex-1 px-3 py-1.5 rounded-lg bg-white border-0 text-sm font-mono text-slate-700 placeholder-slate-400 focus:ring-2 focus:ring-blue-200 focus:outline-none"
                  placeholder={serverMode === 'local' ? 'http://localhost:8005' : serverMode === 'server' ? 'http://192.168.1.100:8005' : 'https://api.yourdomain.com'}
                  value={editUrl}
                  onChange={(e) => setEditUrl(e.target.value)}
                />
                <Button
                  data-testid="save-config-btn"
                  size="sm"
                  onClick={() => saveServerConfig(editUrl, serverMode)}
                  disabled={configLoading || !editUrl.trim()}
                  className="bg-slate-900 text-white hover:bg-slate-800"
                >
                  {configLoading ? <Loader2 size={14} className="animate-spin mr-1" /> : <CheckCircle size={14} className="mr-1" />}
                  Проверить и сохранить
                </Button>
                <button
                  onClick={() => setEditingServer(false)}
                  className="px-2 py-1.5 text-xs text-slate-400 hover:text-slate-600"
                >
                  Отмена
                </button>
              </div>

              <p className="text-xs text-slate-400">
                URL проверяется перед сохранением. Если сервер не ответит — сохранение не произойдёт.
              </p>
            </div>
          )}
        </Section>

        {/* ═══ Block 3: API Keys ═══ */}
        <Section title="API-ключи" icon={Zap} testId="api-keys-section">
          {/* Create new key */}
          <div className="flex items-center gap-2 mb-4">
            <input
              data-testid="new-key-name-input"
              className="flex-1 px-3 py-1.5 rounded-lg bg-slate-50 border-0 text-sm text-slate-700 placeholder-slate-400 focus:ring-2 focus:ring-blue-200 focus:outline-none"
              placeholder="Название ключа (например: my-project)"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && createKey()}
            />
            <Button
              data-testid="create-key-btn"
              size="sm"
              onClick={createKey}
              disabled={!newKeyName.trim() || keyLoading}
              className="bg-slate-900 text-white hover:bg-slate-800"
            >
              {keyLoading ? <Loader2 size={14} className="animate-spin mr-1" /> : <Zap size={14} className="mr-1" />}
              Создать ключ
            </Button>
          </div>

          {/* Key list */}
          {apiKeys.length > 0 ? (
            <div className="space-y-1">
              {apiKeys.map((k) => {
                const isNew = newKeyResult?.prefix === k.prefix;
                return (
                  <div key={k.prefix} className={`flex items-center gap-3 py-2.5 px-3 rounded-lg ${isNew ? 'bg-emerald-50/60' : 'hover:bg-slate-50/80'}`}>
                    <span className={`w-2 h-2 rounded-full ${k.active ? 'bg-emerald-400' : 'bg-slate-300'}`} />
                    <span className="text-sm font-medium text-slate-700">{k.name}</span>

                    {/* Show full key if just created, otherwise prefix */}
                    {isNew ? (
                      <code className="flex-1 text-xs font-mono text-emerald-700 bg-emerald-50 px-2 py-1 rounded select-all break-all">
                        {newKeyResult.key}
                      </code>
                    ) : (
                      <span className="flex-1 text-xs font-mono text-slate-400">{k.prefix}</span>
                    )}

                    {/* Copy */}
                    <button
                      data-testid={`copy-key-${k.prefix}`}
                      onClick={() => copyText(isNew ? newKeyResult.key : k.prefix, `key-${k.prefix}`)}
                      className="p-1 rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100"
                      title="Копировать"
                    >
                      {copied === `key-${k.prefix}` ? <CheckCircle size={14} className="text-emerald-500" /> : <Copy size={14} />}
                    </button>

                    <span className="text-xs text-slate-400 w-20 text-right">{k.requests || 0} запросов</span>

                    {/* Revoke or Delete */}
                    {k.active ? (
                      <button
                        data-testid={`revoke-key-${k.prefix}`}
                        onClick={() => revokeKey(k.prefix)}
                        className="text-xs text-red-400 hover:text-red-600 px-2 py-1 rounded hover:bg-red-50"
                      >
                        Отозвать
                      </button>
                    ) : (
                      <button
                        data-testid={`delete-key-${k.prefix}`}
                        onClick={() => deleteKey(k.prefix)}
                        className="p-1 rounded text-slate-300 hover:text-red-500 hover:bg-red-50"
                        title="Удалить навсегда"
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-sm text-slate-400">Нет ключей. Создайте первый для интеграции.</div>
          )}
        </Section>

        {/* ═══ Block 3: Test Analyzer ═══ */}
        <Section title="Тестовый анализатор" icon={Play} testId="test-analyzer-section">
          <div className="space-y-3">
            <textarea
              data-testid="test-text-input"
              className="w-full h-24 px-3 py-2 rounded-lg bg-slate-50 border-0 text-sm text-slate-800 placeholder-slate-400 focus:ring-2 focus:ring-blue-200 focus:outline-none resize-none"
              placeholder="Введите текст для анализа..."
              value={testText}
              onChange={(e) => setTestText(e.target.value)}
            />

            <div className="flex items-center gap-3">
              <select
                data-testid="test-source-select"
                className="px-3 py-1.5 rounded-lg bg-slate-50 text-sm text-slate-700 border-0 focus:ring-2 focus:ring-blue-200"
                value={testSource}
                onChange={(e) => setTestSource(e.target.value)}
              >
                {SOURCES.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>

              <Button
                data-testid="run-analyze-btn"
                size="sm"
                onClick={runTest}
                disabled={!testText.trim() || testLoading}
                className="bg-slate-900 text-white hover:bg-slate-800"
              >
                {testLoading ? <Loader2 size={14} className="animate-spin mr-1" /> : <Play size={14} className="mr-1" />}
                Анализировать
              </Button>
            </div>

            {/* Result */}
            {testResult && (
              <div data-testid="test-result" className="mt-3 p-4 rounded-lg bg-slate-50/80">
                <div className="flex items-center gap-4 mb-3">
                  <div className={`px-3 py-1 rounded-full text-sm font-semibold ${labelBg[testResult.label]} ${labelColor[testResult.label]}`}>
                    {testResult.label}
                  </div>
                  <div className="text-sm text-slate-600">
                    Score: <span className="font-mono font-semibold">{testResult.score}</span>
                  </div>
                  <div className="text-sm text-slate-600">
                    Confidence: <span className="font-mono font-semibold">{testResult.meta?.confidenceScore}</span>
                    <span className="text-xs text-slate-400 ml-1">({testResult.meta?.confidence})</span>
                  </div>
                  <div className="text-sm text-slate-400">
                    {testResult.meta?.processingTimeMs}ms
                    {testResult.meta?.cached && <span className="ml-1 text-violet-500">(cached)</span>}
                  </div>
                </div>

                {/* Detected words */}
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {testResult.meta?.detected?.positiveWords?.map(w => (
                    <span key={w} className="px-2 py-0.5 text-xs rounded bg-emerald-50 text-emerald-600">{w}</span>
                  ))}
                  {testResult.meta?.detected?.negativeWords?.map(w => (
                    <span key={w} className="px-2 py-0.5 text-xs rounded bg-red-50 text-red-500">{w}</span>
                  ))}
                  {testResult.meta?.detected?.neutralWords?.map(w => (
                    <span key={w} className="px-2 py-0.5 text-xs rounded bg-slate-100 text-slate-500">{w}</span>
                  ))}
                </div>

                {/* Breakdown */}
                {testResult.meta?.breakdown && (
                  <div className="grid grid-cols-3 gap-2 text-xs text-slate-500 font-mono">
                    <div>CNN: {testResult.meta.breakdown.cnnScore} ({testResult.meta.breakdown.cnnContribution})</div>
                    <div>Lex: {testResult.meta.breakdown.lexScoreNorm} ({testResult.meta.breakdown.lexContribution})</div>
                    <div>Rules: {testResult.meta.breakdown.rulesBias} ({testResult.meta.breakdown.rulesContribution})</div>
                  </div>
                )}

                {/* Rules applied */}
                {testResult.meta?.reasons?.length > 0 && (
                  <div className="mt-2 text-xs text-slate-400">
                    {testResult.meta.reasons.join(' | ')}
                  </div>
                )}
              </div>
            )}
          </div>
        </Section>

        {/* ═══ Block 3: Endpoint Docs ═══ */}
        <Section title="Документация API" icon={FileText} testId="endpoint-docs-section">
          <div className="space-y-1">
            {ENDPOINTS.map((ep) => (
              <EndpointDoc
                key={ep.id}
                ep={ep}
                expanded={expandedDoc === ep.id}
                onToggle={() => setExpandedDoc(expandedDoc === ep.id ? null : ep.id)}
                onCopy={copyText}
                copied={copied}
              />
            ))}
          </div>
        </Section>

        {/* ═══ Block 4: Metrics ═══ */}
        <Section title="Метрики" icon={BarChart3} testId="metrics-section">
          {metricsData ? (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-4">
                <Stat label="Всего запросов" value={metricsData.requests.total} color="blue" />
                <Stat label="analyze" value={metricsData.requests.analyze} color="slate" />
                <Stat label="batch" value={metricsData.requests.batch} color="slate" />
                <Stat label="normalize" value={metricsData.requests.normalize} color="slate" />
                <Stat label="Ошибки" value={metricsData.errors} color={metricsData.errors > 0 ? 'red' : 'green'} />
              </div>

              {/* Label distribution */}
              <div className="mb-4">
                <div className="text-xs text-slate-400 mb-2">Распределение меток</div>
                <LabelBar labels={metricsData.labels} />
              </div>

              {/* Source distribution */}
              {Object.keys(metricsData.sources).length > 0 && (
                <div>
                  <div className="text-xs text-slate-400 mb-2">Источники</div>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(metricsData.sources).map(([src, count]) => (
                      <div key={src} className="px-3 py-1.5 rounded-lg bg-slate-50 text-xs">
                        <span className="text-slate-600 font-medium">{src}</span>
                        <span className="text-slate-400 ml-1.5">{String(count)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="text-sm text-slate-400">Загрузка метрик...</div>
          )}
        </Section>
      </div>
    </AdminLayout>
  );
}

// ── Label distribution bar ───────────────────────────────

function LabelBar({ labels }) {
  const total = (labels.POSITIVE || 0) + (labels.NEUTRAL || 0) + (labels.NEGATIVE || 0);
  if (total === 0) return <div className="text-xs text-slate-400">Нет данных</div>;

  const pct = (v) => Math.round(((v || 0) / total) * 100);

  return (
    <div data-testid="label-distribution" className="flex items-center gap-1 h-6 rounded-lg overflow-hidden">
      {labels.POSITIVE > 0 && (
        <div
          className="h-full bg-emerald-400 flex items-center justify-center text-xs text-white font-medium"
          style={{ width: `${pct(labels.POSITIVE)}%`, minWidth: 32 }}
        >
          +{labels.POSITIVE}
        </div>
      )}
      {labels.NEUTRAL > 0 && (
        <div
          className="h-full bg-slate-300 flex items-center justify-center text-xs text-white font-medium"
          style={{ width: `${pct(labels.NEUTRAL)}%`, minWidth: 32 }}
        >
          ={labels.NEUTRAL}
        </div>
      )}
      {labels.NEGATIVE > 0 && (
        <div
          className="h-full bg-red-400 flex items-center justify-center text-xs text-white font-medium"
          style={{ width: `${pct(labels.NEGATIVE)}%`, minWidth: 32 }}
        >
          -{labels.NEGATIVE}
        </div>
      )}
    </div>
  );
}

// ── Endpoint doc item ────────────────────────────────────

function EndpointDoc({ ep, expanded, onToggle, onCopy, copied }) {
  const methodColor = ep.method === 'POST' ? 'text-blue-600 bg-blue-50' : 'text-emerald-600 bg-emerald-50';
  const fullUrl = `${API}${ep.path}`;
  const fullCurl = ep.curl.replace(/\{URL\}/g, API);

  return (
    <div data-testid={`endpoint-${ep.id}`} className="border-0">
      <div className="flex items-center gap-1 py-2.5 px-3 rounded-lg hover:bg-slate-50/80 group">
        <button
          className="flex items-center gap-3 flex-1 text-left"
          onClick={onToggle}
        >
          <span className={`px-2 py-0.5 text-xs font-mono font-semibold rounded ${methodColor}`}>
            {ep.method}
          </span>
          <span className="text-sm font-mono text-slate-700 flex-1">{ep.path}</span>
          <span className="text-xs text-slate-400">{ep.desc}</span>
          {expanded ? <ChevronDown size={14} className="text-slate-400" /> : <ChevronRight size={14} className="text-slate-400" />}
        </button>
        <button
          data-testid={`copy-path-${ep.id}`}
          onClick={(e) => { e.stopPropagation(); onCopy(fullUrl, `path-${ep.id}`); }}
          className="ml-2 p-1.5 rounded-md text-slate-300 hover:text-slate-600 hover:bg-slate-100 opacity-0 group-hover:opacity-100 transition-opacity"
          title="Копировать полный URL"
        >
          {copied === `path-${ep.id}` ? <CheckCircle size={14} className="text-emerald-500" /> : <Copy size={14} />}
        </button>
      </div>

      {expanded && (
        <div className="ml-3 mb-3 p-3 rounded-lg bg-slate-50/80 text-xs space-y-3">
          {/* curl */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-slate-400 font-medium">curl</span>
              <button
                data-testid={`copy-curl-${ep.id}`}
                onClick={() => onCopy(fullCurl, ep.id)}
                className="flex items-center gap-1 text-slate-400 hover:text-slate-600"
              >
                <Copy size={10} />
                {copied === ep.id ? 'Скопировано' : 'Копировать'}
              </button>
            </div>
            <pre className="p-2 rounded bg-slate-900 text-slate-200 overflow-x-auto whitespace-pre-wrap font-mono text-xs">{fullCurl}</pre>
          </div>

          {/* Response */}
          {ep.response && (
            <div>
              <span className="text-slate-400 font-medium">Ответ</span>
              <pre className="mt-1 p-2 rounded bg-slate-900 text-slate-200 overflow-x-auto whitespace-pre-wrap font-mono text-xs">{ep.response}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Endpoint definitions ─────────────────────────────────

const BASE = '/api/v1/sentiment';

const ENDPOINTS = [
  {
    id: 'analyze',
    method: 'POST',
    path: `${BASE}/analyze`,
    desc: 'Анализ текста',
    curl: `curl -X POST {URL}${BASE}/analyze \\
  -H "Content-Type: application/json" \\
  -d '{"text": "Bitcoin looks very strong today", "source": "twitter"}'`,
    response: `{
  "ok": true,
  "data": {
    "label": "POSITIVE",
    "score": 0.62,
    "source": "twitter",
    "meta": {
      "confidence": "HIGH",
      "confidenceScore": 0.71,
      "processingTimeMs": 0.3,
      "cached": false
    }
  }
}`,
  },
  {
    id: 'batch',
    method: 'POST',
    path: `${BASE}/batch`,
    desc: 'Пакетный анализ',
    curl: `curl -X POST {URL}${BASE}/batch \\
  -H "Content-Type: application/json" \\
  -d '{"source": "news", "items": [{"id": "1", "text": "BTC breakout"}, {"id": "2", "text": "Market crash"}]}'`,
    response: `{
  "ok": true,
  "data": {
    "results": [...],
    "meta": {
      "totalItems": 2,
      "successCount": 2,
      "errorCount": 0
    }
  }
}`,
  },
  {
    id: 'normalize',
    method: 'POST',
    path: `${BASE}/normalize`,
    desc: 'Нормализация текста',
    curl: `curl -X POST {URL}${BASE}/normalize \\
  -H "Content-Type: application/json" \\
  -d '{"text": "@user Bitcoin #BTC is pumping! https://t.co/xyz"}'`,
    response: `{
  "ok": true,
  "data": {
    "cleaned": "Bitcoin BTC is pumping",
    "tokens": ["bitcoin", "btc", "is", "pumping"],
    "lang": "en",
    "wordCount": 4
  }
}`,
  },
  {
    id: 'health',
    method: 'GET',
    path: `${BASE}/health`,
    desc: 'Статус движка',
    curl: `curl {URL}${BASE}/health`,
    response: `{
  "ok": true,
  "data": {
    "status": "READY",
    "cache": { "size": 42, "maxSize": 10000, "ttlHours": 24 }
  }
}`,
  },
  {
    id: 'capabilities',
    method: 'GET',
    path: `${BASE}/capabilities`,
    desc: 'Возможности движка',
    curl: `curl {URL}${BASE}/capabilities`,
    response: `{
  "ok": true,
  "data": {
    "type": "lexicon-rules-ensemble",
    "supportedSources": ["twitter", "news", "telegram", ...],
    "lexiconStats": { "positive": 58, "negative": 45, "neutral": 32 }
  }
}`,
  },
  {
    id: 'metrics',
    method: 'GET',
    path: `${BASE}/metrics`,
    desc: 'Метрики использования',
    curl: `curl {URL}${BASE}/metrics`,
    response: `{
  "ok": true,
  "data": {
    "requests": { "total": 150, "analyze": 120, "batch": 10 },
    "cache": { "hitRate": 72, "size": 85 },
    "latency": { "avgMs": 0.4 },
    "labels": { "POSITIVE": 60, "NEUTRAL": 50, "NEGATIVE": 40 }
  }
}`,
  },
];
