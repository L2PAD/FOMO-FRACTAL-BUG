import React, { useState, useEffect, useCallback } from 'react';
import AdminLayout from '../../components/admin/AdminLayout';
import { 
  Activity, AlertCircle, AlertTriangle, BarChart2, BarChart3, BookOpen, Box,
  CheckCircle, ChevronDown, ChevronRight, ChevronUp, Clock, Database, DollarSign,
  ExternalLink, Eye, FileText, Globe, HelpCircle, Key, Layers, Network, Newspaper,
  Play, Plus, Radio, RefreshCw, RotateCcw, Rss, Search, Server, Settings, Shield,
  Target, Terminal, Trash2, TrendingUp, Wifi, X, XCircle, Zap, UserCog
} from 'lucide-react';
const colors = {
  background: '#ffffff',
  surface: '#f8fafc',
  border: '#e2e8f0',
  text: '#0f172a',
  textSecondary: '#475569',
  textMuted: '#94a3b8',
  accent: '#6366f1',
  accentSoft: '#eef2ff',
  accentHover: '#4f46e5',
  success: '#10b981',
  successSoft: '#ecfdf5',
  warning: '#f59e0b',
  warningSoft: '#fffbeb',
  error: '#ef4444',
  errorSoft: '#fef2f2',
  bullish: '#10b981',
  bearish: '#ef4444',
  neutral: '#6b7280'
};

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function AdminPage() {
  // Parser state
  const [parserRunning, setParserRunning] = useState(false);
  const [parserResult, setParserResult] = useState(null);
  
  // Proxy state
  const [proxyStatus, setProxyStatus] = useState(null);
  const [proxyLoading, setProxyLoading] = useState(false);
  const [newProxy, setNewProxy] = useState({ 
    host: '', port: '', type: 'http', username: '', password: '', priority: 1 
  });
  const [testResults, setTestResults] = useState(null);
  const [typeDropdownOpen, setTypeDropdownOpen] = useState(false);
  
  const proxyTypes = [
    { value: 'http', label: 'HTTP' },
    { value: 'https', label: 'HTTPS' },
    { value: 'socks5', label: 'SOCKS5' },
  ];
  
  // Fetch proxy status
  const fetchProxyStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/intel/admin/proxy/status`);
      const data = await res.json();
      setProxyStatus(data);
    } catch (err) {
      console.error('Failed to fetch proxy status:', err);
    }
  }, []);
  
  const buildProxyServer = () => {
    if (!newProxy.host || !newProxy.port) return '';
    return `${newProxy.type}://${newProxy.host}:${newProxy.port}`;
  };
  
  const addProxy = async () => {
    const server = buildProxyServer();
    if (!server) return;
    setProxyLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/intel/admin/proxy/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          server,
          username: newProxy.username || null,
          password: newProxy.password || null,
          priority: newProxy.priority
        })
      });
      await res.json();
      setNewProxy({ host: '', port: '', type: 'http', username: '', password: '', priority: 1 });
      await fetchProxyStatus();
    } catch (err) {
      console.error('Failed to add proxy:', err);
    }
    setProxyLoading(false);
  };
  
  const removeProxy = async (proxyId) => {
    setProxyLoading(true);
    try {
      await fetch(`${API_URL}/api/intel/admin/proxy/${proxyId}`, { method: 'DELETE' });
      await fetchProxyStatus();
    } catch (err) {
      console.error('Failed to remove proxy:', err);
    }
    setProxyLoading(false);
  };
  
  const toggleProxy = async (proxyId, enabled) => {
    setProxyLoading(true);
    try {
      await fetch(`${API_URL}/api/intel/admin/proxy/${proxyId}/toggle?enabled=${enabled}`, { method: 'POST' });
      await fetchProxyStatus();
    } catch (err) {
      console.error('Failed to toggle proxy:', err);
    }
    setProxyLoading(false);
  };
  
  const testProxy = async (proxyId) => {
    setTestResults(prev => ({ ...prev, [proxyId]: { loading: true } }));
    try {
      const res = await fetch(`${API_URL}/api/intel/admin/proxy/${proxyId}/test`, { method: 'POST' });
      const data = await res.json();
      setTestResults(prev => ({ ...prev, [proxyId]: data }));
      await fetchProxyStatus();
    } catch (err) {
      setTestResults(prev => ({ ...prev, [proxyId]: { ok: false, error: err.message } }));
    }
  };

  const clearAllProxies = async () => {
    if (!window.confirm('Clear all proxies? Exchanges will use direct connection.')) return;
    setProxyLoading(true);
    try {
      await fetch(`${API_URL}/api/intel/admin/proxy/clear`, { method: 'POST' });
      await fetchProxyStatus();
    } catch (err) {
      console.error('Failed to clear proxies:', err);
    }
    setProxyLoading(false);
  };
  
  const setProxyPriority = async (proxyId, priority) => {
    try {
      await fetch(`${API_URL}/api/intel/admin/proxy/${proxyId}/priority?priority=${priority}`, { method: 'POST' });
      await fetchProxyStatus();
    } catch (err) {
      console.error('Failed to set priority:', err);
    }
  };
  
  const [apiKeysData, setApiKeysData] = useState({ keys: [], services: [], summary: {} });
  const [apiKeysLoading, setApiKeysLoading] = useState(false);
  const [newApiKey, setNewApiKey] = useState({ service: '', api_key: '', name: '', is_pro: false, proxy_id: null });
  const [apiKeyServiceDropdown, setApiKeyServiceDropdown] = useState(false);
  const [adminSubTab, setAdminSubTab] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('tab') || 'proxy';
  }); // 'proxy', 'api-keys', 'llm-keys', 'sentiment-keys', 'providers', 'health', 'discovery', 'webhooks', 'merge', 'profile'
  const [apiKeyServiceFilter, setApiKeyServiceFilter] = useState(null); // null = show all, or 'coingecko', 'coinmarketcap', 'messari'
  
  // Merge Candidates State
  const [mergeCandidates, setMergeCandidates] = useState([]);
  const [mergeLoading, setMergeLoading] = useState(false);
  const [mergeStats, setMergeStats] = useState(null);
  
  // LLM Keys State
  const [llmKeys, setLlmKeys] = useState([]);
  const [llmProviders, setLlmProviders] = useState([]);
  const [llmKeysSummary, setLlmKeysSummary] = useState(null);
  const [llmKeysLoading, setLlmKeysLoading] = useState(false);
  const [showAddLlmKey, setShowAddLlmKey] = useState(false);
  const [newLlmKey, setNewLlmKey] = useState({ provider: 'openai', api_key: '', name: '', capabilities: ['text'], is_default: false });
  
  // Sentiment Keys State
  const [sentimentKeys, setSentimentKeys] = useState([]);
  const [sentimentProviders, setSentimentProviders] = useState([]);
  const [sentimentSummary, setSentimentSummary] = useState(null);
  const [sentimentHeatmapData, setSentimentHeatmapData] = useState([{ total: 0 }]);
  const [sentimentKeysLoading, setSentimentKeysLoading] = useState(false);
  const [showAddSentimentKey, setShowAddSentimentKey] = useState(false);
  const [newSentimentKey, setNewSentimentKey] = useState({ provider: 'openai', api_key: '', name: '', model: '', endpoint_url: '', is_default: false });
  
  // Fetch sentiment providers
  const fetchSentimentProviders = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/sentiment/providers`);
      const data = await res.json();
      setSentimentProviders(data.providers || []);
    } catch (e) {
      console.error('Failed to fetch sentiment providers:', e);
    }
  }, []);
  
  // Webhooks State
  const [webhooks, setWebhooks] = useState([]);
  const [webhookEvents, setWebhookEvents] = useState([]);
  const [webhooksLoading, setWebhooksLoading] = useState(false);
  const [showAddWebhook, setShowAddWebhook] = useState(false);
  const [newWebhook, setNewWebhook] = useState({ url: '', name: '', events: [], secret: '', filters: { assets: [], projects: [] } });
  const [webhookEventTypes, setWebhookEventTypes] = useState([]);
  const [testWebhookResult, setTestWebhookResult] = useState(null);
  const [editingWebhook, setEditingWebhook] = useState(null); // For editing existing webhooks
  const [webhookRetryStats, setWebhookRetryStats] = useState({ pending: 0, failed: 0, success: 0 });
  const [pendingRetries, setPendingRetries] = useState([]);
  const [failedDeliveries, setFailedDeliveries] = useState([]);
  const [webhookAnalytics, setWebhookAnalytics] = useState(null);
  const [analyticsPeriod, setAnalyticsPeriod] = useState('24h');
  const [deliveryLogs, setDeliveryLogs] = useState([]);
  const [deliveryStats, setDeliveryStats] = useState({ success: 0, failed: 0, total: 0, success_rate: 100 });
  const [showDeliveryLogs, setShowDeliveryLogs] = useState(false);
  const [deliveryLogFilter, setDeliveryLogFilter] = useState({ subscription_id: '', status: '' });
  
  // Health Monitor State
  const [sourcesHealth, setSourcesHealth] = useState({ sources: [], summary: {} });
  const [healthLoading, setHealthLoading] = useState(false);
  const [graphHealth, setGraphHealth] = useState(null);
  const [graphHealthLoading, setGraphHealthLoading] = useState(false);
  
  // Fetch Graph Health
  const fetchGraphHealth = useCallback(async () => {
    setGraphHealthLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/graph/health`);
      const data = await res.json();
      setGraphHealth(data);
    } catch (err) {
      console.error('Failed to fetch graph health:', err);
    }
    setGraphHealthLoading(false);
  }, []);
  
  // LLM Analytics State
  const [llmAnalytics, setLlmAnalytics] = useState(null);
  const [llmAnalyticsByProvider, setLlmAnalyticsByProvider] = useState([]);
  const [llmHourlyData, setLlmHourlyData] = useState([]);
  
  // Discovery Dashboard State
  const [discoveryDashboard, setDiscoveryDashboard] = useState(null);
  const [discoveryDashboardLoading, setDiscoveryDashboardLoading] = useState(false);
  
  const fetchDiscoveryDashboard = useCallback(async () => {
    setDiscoveryDashboardLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/intel/admin/discovery/dashboard`);
      const data = await res.json();
      setDiscoveryDashboard(data);
    } catch (err) {
      console.error('Failed to fetch discovery dashboard:', err);
    }
    setDiscoveryDashboardLoading(false);
  }, []);
  
  // === Merge Candidates ===
  const fetchMergeCandidates = useCallback(async () => {
    setMergeLoading(true);
    try {
      const [candidatesRes, statsRes] = await Promise.all([
        fetch(`${API_URL}/api/graph/merge/find-candidates?limit=50`),
        fetch(`${API_URL}/api/graph/merge/stats`)
      ]);
      const candidates = await candidatesRes.json();
      const stats = await statsRes.json();
      setMergeCandidates(candidates.candidates || []);
      setMergeStats(stats);
    } catch (err) {
      console.error('Failed to fetch merge candidates:', err);
    }
    setMergeLoading(false);
  }, []);
  
  const executeMerge = async (sourceId, targetId) => {
    try {
      const res = await fetch(`${API_URL}/api/graph/merge/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_entity_id: sourceId, target_entity_id: targetId })
      });
      const result = await res.json();
      if (result.success) {
        fetchMergeCandidates(); // Refresh list
      }
      return result;
    } catch (err) {
      console.error('Failed to execute merge:', err);
      return { success: false, error: err.message };
    }
  };
  
  const dismissMergeCandidate = async (candidateId) => {
    try {
      await fetch(`${API_URL}/api/graph/merge/dismiss/${candidateId}`, { method: 'POST' });
      setMergeCandidates(prev => prev.filter(c => c.id !== candidateId));
    } catch (err) {
      console.error('Failed to dismiss candidate:', err);
    }
  };

  // Trigger manual discovery
  const triggerManualDiscovery = async (domain = null) => {
    try {
      const url = domain 
        ? `${API_URL}/api/intel/admin/discovery/trigger/discovery?domain=${encodeURIComponent(domain)}`
        : `${API_URL}/api/intel/admin/discovery/trigger/discovery`;
      await fetch(url, { method: 'POST' });
      fetchDiscoveryDashboard();
    } catch (err) {
      console.error('Failed to trigger discovery:', err);
    }
  };
  
  // Trigger drift check
  const triggerDriftCheck = async (domain = null) => {
    try {
      const url = domain 
        ? `${API_URL}/api/intel/admin/discovery/trigger/drift-check?domain=${encodeURIComponent(domain)}`
        : `${API_URL}/api/intel/admin/discovery/trigger/drift-check`;
      await fetch(url, { method: 'POST' });
      fetchDiscoveryDashboard();
    } catch (err) {
      console.error('Failed to trigger drift check:', err);
    }
  };
  
  // Trigger scoring
  const triggerScoring = async (domain = null) => {
    try {
      const url = domain 
        ? `${API_URL}/api/intel/admin/discovery/trigger/scoring?domain=${encodeURIComponent(domain)}`
        : `${API_URL}/api/intel/admin/discovery/trigger/scoring`;
      await fetch(url, { method: 'POST' });
      fetchDiscoveryDashboard();
    } catch (err) {
      console.error('Failed to trigger scoring:', err);
    }
  };
  
  const fetchSourcesHealth = useCallback(async () => {
    setHealthLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/intel/admin/health/sources`);
      const data = await res.json();
      setSourcesHealth({
        sources: data.sources || [],
        summary: data.summary || {}
      });
    } catch (err) {
      console.error('Failed to fetch health:', err);
    }
    setHealthLoading(false);
    // Also fetch graph health
    fetchGraphHealth();
  }, [fetchGraphHealth]);
  
  // News Sources State (full list with categories)
  const [newsSources, setNewsSources] = useState({ sources: [], stats: {} });
  const [newsSourcesLoading, setNewsSourcesLoading] = useState(false);
  const [newsSourcesFilter, setNewsSourcesFilter] = useState({ tier: null, language: null, category: null });
  const [newsSourcesSearch, setNewsSourcesSearch] = useState('');
  
  const fetchNewsSources = useCallback(async () => {
    setNewsSourcesLoading(true);
    try {
      let url = `${API_URL}/api/intel/admin/sources-registry`;
      const params = [];
      if (newsSourcesFilter.tier) params.push(`tier=${newsSourcesFilter.tier}`);
      if (newsSourcesFilter.language) params.push(`language=${newsSourcesFilter.language}`);
      if (newsSourcesFilter.category) params.push(`category=${newsSourcesFilter.category}`);
      if (params.length > 0) url += `?${params.join('&')}`;
      
      const res = await fetch(url);
      const data = await res.json();
      setNewsSources({
        sources: data.sources || [],
        stats: data.stats || {}
      });
    } catch (err) {
      console.error('Failed to fetch news sources:', err);
    }
    setNewsSourcesLoading(false);
  }, [newsSourcesFilter]);
  
  const handleUnpauseSource = async (sourceId) => {
    try {
      await fetch(`${API_URL}/api/intel/admin/health/unpause/${sourceId}`, { method: 'POST' });
      fetchSourcesHealth();
    } catch (err) {
      console.error('Failed to unpause:', err);
    }
  };
  
  const fetchApiKeys = useCallback(async () => {
    setApiKeysLoading(true);
    try {
      const [keysRes, servicesRes, summaryRes] = await Promise.all([
        fetch(`${API_URL}/api/admin/api-keys`),
        fetch(`${API_URL}/api/admin/api-keys/services`),
        fetch(`${API_URL}/api/admin/api-keys/summary`)
      ]);
      const [keys, services, summary] = await Promise.all([
        keysRes.json(),
        servicesRes.json(),
        summaryRes.json()
      ]);
      setApiKeysData({ 
        keys: keys.keys || [], 
        services: services.services || [],
        summary: summary.summary || {}
      });
    } catch (err) {
      console.error('Failed to fetch API keys:', err);
    }
    setApiKeysLoading(false);
  }, []);
  
  // LLM Keys Functions
  const fetchLlmKeys = useCallback(async () => {
    setLlmKeysLoading(true);
    try {
      const [keysRes, providersRes, summaryRes] = await Promise.all([
        fetch(`${API_URL}/api/admin/llm-keys`),
        fetch(`${API_URL}/api/admin/llm-keys/providers`),
        fetch(`${API_URL}/api/admin/llm-keys/summary`)
      ]);
      const [keys, providers, summary] = await Promise.all([
        keysRes.json(),
        providersRes.json(),
        summaryRes.json()
      ]);
      setLlmKeys(keys.keys || []);
      setLlmProviders(providers.providers || []);
      setLlmKeysSummary(summary);
    } catch (err) {
      console.error('Failed to fetch LLM keys:', err);
    }
    setLlmKeysLoading(false);
  }, []);
  
  const addLlmKey = async () => {
    if (!newLlmKey.api_key) return;
    setLlmKeysLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/llm-keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newLlmKey)
      });
      const data = await res.json();
      if (data.ok) {
        setNewLlmKey({ provider: 'openai', api_key: '', name: '', capabilities: ['text'], is_default: false });
        setShowAddLlmKey(false);
        await fetchLlmKeys();
      }
    } catch (err) {
      console.error('Failed to add LLM key:', err);
    }
    setLlmKeysLoading(false);
  };
  
  const removeLlmKey = async (keyId) => {
    setLlmKeysLoading(true);
    try {
      await fetch(`${API_URL}/api/admin/llm-keys/${keyId}`, { method: 'DELETE' });
      await fetchLlmKeys();
    } catch (err) {
      console.error('Failed to remove LLM key:', err);
    }
    setLlmKeysLoading(false);
  };
  
  const toggleLlmKey = async (keyId, enabled) => {
    try {
      await fetch(`${API_URL}/api/admin/llm-keys/${keyId}/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      });
      await fetchLlmKeys();
    } catch (err) {
      console.error('Failed to toggle LLM key:', err);
    }
  };
  
  const testLlmKey = async (keyId) => {
    try {
      const res = await fetch(`${API_URL}/api/admin/llm-keys/${keyId}/test`, { method: 'POST' });
      const data = await res.json();
      await fetchLlmKeys();
      return data;
    } catch (err) {
      console.error('Failed to test LLM key:', err);
    }
  };
  
  const setLlmKeyDefault = async (keyId, capability) => {
    try {
      await fetch(`${API_URL}/api/admin/llm-keys/${keyId}/set-default`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ capability })
      });
      await fetchLlmKeys();
    } catch (err) {
      console.error('Failed to set default:', err);
    }
  };
  
  // Fetch LLM Analytics
  const fetchLlmAnalytics = useCallback(async () => {
    try {
      const [overviewRes, byProviderRes, hourlyRes] = await Promise.all([
        fetch(`${API_URL}/api/admin/llm-keys/analytics/overview?hours=24`),
        fetch(`${API_URL}/api/admin/llm-keys/analytics/by-provider?hours=24`),
        fetch(`${API_URL}/api/admin/llm-keys/analytics/hourly?hours=24`)
      ]);
      const [overview, byProvider, hourly] = await Promise.all([
        overviewRes.json(),
        byProviderRes.json(),
        hourlyRes.json()
      ]);
      setLlmAnalytics(overview);
      setLlmAnalyticsByProvider(byProvider.providers || []);
      setLlmHourlyData(hourly.data || []);
    } catch (err) {
      console.error('Failed to fetch LLM analytics:', err);
    }
  }, []);
  
  const resetKeyHealth = async (keyId) => {
    try {
      await fetch(`${API_URL}/api/admin/llm-keys/${keyId}/reset-health`, { method: 'POST' });
      await fetchLlmKeys();
    } catch (err) {
      console.error('Failed to reset key health:', err);
    }
  };
  
  // Sentiment Keys Functions
  const fetchSentimentKeys = useCallback(async () => {
    setSentimentKeysLoading(true);
    try {
      const [keysRes, summaryRes] = await Promise.all([
        fetch(`${API_URL}/api/admin/sentiment-keys`),
        fetch(`${API_URL}/api/admin/sentiment-keys/summary`)
      ]);
      const [keys, summary] = await Promise.all([
        keysRes.json(),
        summaryRes.json()
      ]);
      setSentimentKeys(keys.keys || []);
      setSentimentSummary(summary);
    } catch (err) {
      console.error('Failed to fetch sentiment keys:', err);
    }
    setSentimentKeysLoading(false);
  }, []);
  
  const addSentimentKey = async () => {
    setSentimentKeysLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/sentiment-keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newSentimentKey)
      });
      const data = await res.json();
      if (data.ok) {
        setNewSentimentKey({ provider: 'internal', api_key: '', name: '', model: '', endpoint_url: '', is_default: false });
        setShowAddSentimentKey(false);
        await fetchSentimentKeys();
      }
    } catch (err) {
      console.error('Failed to add sentiment key:', err);
    }
    setSentimentKeysLoading(false);
  };
  
  const removeSentimentKey = async (keyId) => {
    setSentimentKeysLoading(true);
    try {
      await fetch(`${API_URL}/api/admin/sentiment-keys/${keyId}`, { method: 'DELETE' });
      await fetchSentimentKeys();
    } catch (err) {
      console.error('Failed to remove sentiment key:', err);
    }
    setSentimentKeysLoading(false);
  };
  
  const toggleSentimentKey = async (keyId, enabled) => {
    try {
      await fetch(`${API_URL}/api/admin/sentiment-keys/${keyId}/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      });
      await fetchSentimentKeys();
    } catch (err) {
      console.error('Failed to toggle sentiment key:', err);
    }
  };
  
  // Webhook Functions
  const fetchWebhooks = useCallback(async () => {
    setWebhooksLoading(true);
    try {
      const [subsRes, eventsRes, typesRes, statsRes, pendingRes, failedRes] = await Promise.all([
        fetch(`${API_URL}/api/webhooks/subscriptions`),
        fetch(`${API_URL}/api/webhooks/events?limit=20`),
        fetch(`${API_URL}/api/webhooks/event-types`),
        fetch(`${API_URL}/api/webhooks/retries/stats`),
        fetch(`${API_URL}/api/webhooks/retries/pending?limit=10`),
        fetch(`${API_URL}/api/webhooks/retries/failed?limit=10`)
      ]);
      const [subs, events, types, stats, pending, failed] = await Promise.all([
        subsRes.json(),
        eventsRes.json(),
        typesRes.json(),
        statsRes.json(),
        pendingRes.json(),
        failedRes.json()
      ]);
      setWebhooks(subs.subscriptions || []);
      setWebhookEvents(events.events || []);
      setWebhookEventTypes(types.event_types || []);
      setWebhookRetryStats(stats);
      setPendingRetries(pending.retries || []);
      setFailedDeliveries(failed.failed || []);
      
      // Also fetch analytics with current period
      const analyticsRes = await fetch(`${API_URL}/api/webhooks/analytics?period=${analyticsPeriod}`);
      const analyticsData = await analyticsRes.json();
      setWebhookAnalytics(analyticsData);
    } catch (err) {
      console.error('Failed to fetch webhooks:', err);
    }
    setWebhooksLoading(false);
  }, [analyticsPeriod]);
  
  const fetchWebhookAnalytics = useCallback(async (period) => {
    try {
      const res = await fetch(`${API_URL}/api/webhooks/analytics?period=${period}`);
      const data = await res.json();
      setWebhookAnalytics(data);
      setAnalyticsPeriod(period);
    } catch (err) {
      console.error('Failed to fetch analytics:', err);
    }
  }, []);
  
  const fetchDeliveryLogs = useCallback(async (filters = {}) => {
    try {
      const params = new URLSearchParams();
      if (filters.subscription_id) params.append('subscription_id', filters.subscription_id);
      if (filters.status) params.append('status', filters.status);
      params.append('limit', '30');
      
      const [logsRes, statsRes] = await Promise.all([
        fetch(`${API_URL}/api/webhooks/delivery-logs?${params}`),
        fetch(`${API_URL}/api/webhooks/delivery-stats${filters.subscription_id ? `?subscription_id=${filters.subscription_id}` : ''}`)
      ]);
      
      const [logsData, statsData] = await Promise.all([logsRes.json(), statsRes.json()]);
      
      setDeliveryLogs(logsData.logs || []);
      setDeliveryStats(statsData);
    } catch (err) {
      console.error('Failed to fetch delivery logs:', err);
    }
  }, []);
  
  const addWebhook = async () => {
    if (!newWebhook.url || newWebhook.events.length === 0) return;
    setWebhooksLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/webhooks/subscriptions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newWebhook)
      });
      const data = await res.json();
      if (data.ok) {
        setNewWebhook({ url: '', name: '', events: [], secret: '', filters: { assets: [], projects: [] } });
        setShowAddWebhook(false);
        await fetchWebhooks();
      }
    } catch (err) {
      console.error('Failed to add webhook:', err);
    }
    setWebhooksLoading(false);
  };
  
  const deleteWebhook = async (webhookId) => {
    setWebhooksLoading(true);
    try {
      await fetch(`${API_URL}/api/webhooks/subscriptions/${webhookId}`, { method: 'DELETE' });
      await fetchWebhooks();
    } catch (err) {
      console.error('Failed to delete webhook:', err);
    }
    setWebhooksLoading(false);
  };
  
  const testWebhook = async (url) => {
    setTestWebhookResult(null);
    try {
      const res = await fetch(`${API_URL}/api/webhooks/test?url=${encodeURIComponent(url)}`, { method: 'POST' });
      const data = await res.json();
      setTestWebhookResult(data);
    } catch (err) {
      setTestWebhookResult({ ok: false, error: err.message });
    }
  };
  
  const checkAllWebhookEvents = async () => {
    setWebhooksLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/webhooks/check-all`, { method: 'POST' });
      const data = await res.json();
      await fetchWebhooks();
      return data;
    } catch (err) {
      console.error('Failed to check webhook events:', err);
    }
    setWebhooksLoading(false);
  };
  
  const toggleWebhookEvent = (eventType) => {
    setNewWebhook(prev => {
      const events = prev.events.includes(eventType)
        ? prev.events.filter(e => e !== eventType)
        : [...prev.events, eventType];
      return { ...prev, events };
    });
  };
  
  const toggleEditWebhookEvent = (eventType) => {
    setEditingWebhook(prev => {
      if (!prev) return null;
      const events = prev.events.includes(eventType)
        ? prev.events.filter(e => e !== eventType)
        : [...prev.events, eventType];
      return { ...prev, events };
    });
  };
  
  const startEditWebhook = (webhook) => {
    setEditingWebhook({
      ...webhook,
      events: webhook.events || []
    });
    setTestWebhookResult(null);
  };
  
  const cancelEditWebhook = () => {
    setEditingWebhook(null);
    setTestWebhookResult(null);
  };
  
  const updateWebhook = async () => {
    if (!editingWebhook || !editingWebhook.url || editingWebhook.events.length === 0) return;
    setWebhooksLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/webhooks/subscriptions/${editingWebhook.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: editingWebhook.url,
          name: editingWebhook.name,
          events: editingWebhook.events,
          secret: editingWebhook.secret || undefined,
          enabled: editingWebhook.enabled
        })
      });
      const data = await res.json();
      if (data.ok) {
        setEditingWebhook(null);
        await fetchWebhooks();
      }
    } catch (err) {
      console.error('Failed to update webhook:', err);
    }
    setWebhooksLoading(false);
  };
  
  const toggleWebhookEnabled = async (webhookId, enabled) => {
    setWebhooksLoading(true);
    try {
      await fetch(`${API_URL}/api/webhooks/subscriptions/${webhookId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      });
      await fetchWebhooks();
    } catch (err) {
      console.error('Failed to toggle webhook:', err);
    }
    setWebhooksLoading(false);
  };
  
  const processRetries = async () => {
    setWebhooksLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/webhooks/retries/process`, { method: 'POST' });
      const data = await res.json();
      await fetchWebhooks();
      return data;
    } catch (err) {
      console.error('Failed to process retries:', err);
    }
    setWebhooksLoading(false);
  };
  
  const retryFailedDelivery = async (retryId) => {
    setWebhooksLoading(true);
    try {
      await fetch(`${API_URL}/api/webhooks/retries/${retryId}/retry`, { method: 'POST' });
      await fetchWebhooks();
    } catch (err) {
      console.error('Failed to retry delivery:', err);
    }
    setWebhooksLoading(false);
  };
  
  const addApiKey = async () => {
    if (!newApiKey.api_key || !newApiKey.service) return;
    setApiKeysLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/api-keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newApiKey)
      });
      const data = await res.json();
      if (data.ok) {
        setNewApiKey({ service: '', api_key: '', name: '', is_pro: false, proxy_id: null });
        await fetchApiKeys();
      }
    } catch (err) {
      console.error('Failed to add API key:', err);
    }
    setApiKeysLoading(false);
  };
  
  const removeApiKey = async (keyId) => {
    setApiKeysLoading(true);
    try {
      await fetch(`${API_URL}/api/admin/api-keys/${keyId}`, { method: 'DELETE' });
      await fetchApiKeys();
    } catch (err) {
      console.error('Failed to remove API key:', err);
    }
    setApiKeysLoading(false);
  };
  
  const toggleApiKey = async (keyId, enabled) => {
    try {
      await fetch(`${API_URL}/api/admin/api-keys/${keyId}/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      });
      await fetchApiKeys();
    } catch (err) {
      console.error('Failed to toggle API key:', err);
    }
  };
  
  const checkApiKeyHealth = async (keyId) => {
    try {
      const res = await fetch(`${API_URL}/api/admin/api-keys/${keyId}/health`, { method: 'POST' });
      const data = await res.json();
      // Refresh to show updated health status
      await fetchApiKeys();
      return data;
    } catch (err) {
      console.error('Failed to check key health:', err);
    }
  };
  
  const checkAllKeysHealth = async () => {
    setApiKeysLoading(true);
    try {
      await fetch(`${API_URL}/api/admin/api-keys/health/all`, { method: 'POST' });
      await fetchApiKeys();
    } catch (err) {
      console.error('Failed to check all keys health:', err);
    }
    setApiKeysLoading(false);
  };

  // Start parser/sync
  const startParser = async (proxyId = null) => {
    setParserRunning(true);
    setParserResult(null);
    try {
      const url = proxyId 
        ? `${API_URL}/api/admin/parser/sync?proxy_id=${proxyId}`
        : `${API_URL}/api/admin/parser/sync`;
      const res = await fetch(url, { method: 'POST' });
      const data = await res.json();
      setParserResult(data);
    } catch (err) {
      console.error('Failed to start parser:', err);
      setParserResult({ ok: false, error: err.message });
    }
    setParserRunning(false);
  };
  
  // Load data on mount (AdminPage is only rendered when admin tab is active)
  useEffect(() => {
    fetchProxyStatus();
    fetchApiKeys();
    fetchProviderPool();
    fetchSourcesHealth();
    fetchDiscoveryDashboard();
    fetchSentimentProviders();
  }, []);
  
  // Auto-refresh discovery dashboard every 30 seconds when on discovery sub-tab
  useEffect(() => {
    if (adminSubTab === 'discovery') {
      const interval = setInterval(fetchDiscoveryDashboard, 30000);
      return () => clearInterval(interval);
    }
  }, [adminSubTab, fetchDiscoveryDashboard]);
  
  // Fetch provider pool status
  const [providerPool, setProviderPool] = useState({ providers: [], bindings: [] });
  
  const fetchProviderPool = async () => {
    try {
      // Get providers from new Provider Gateway
      const gatewayRes = await fetch(`${API_URL}/api/providers`);
      const gatewayData = await gatewayRes.json();
      
      // Get exchange providers health
      const healthRes = await fetch(`${API_URL}/api/exchange/providers/health`);
      const healthData = await healthRes.json();
      
      // Build unified provider list
      const providers = [];
      
      // Add providers from gateway
      if (gatewayData.providers) {
        gatewayData.providers.forEach(p => {
          providers.push({
            id: p.id,
            name: p.name,
            type: p.requires_api_key ? 'api' : 'public',
            category: p.category,
            status: p.status,
            endpoint: p.endpoint,
            capabilities: p.capabilities || [],
            rate_limit: p.rate_limit,
            requires_api_key: p.requires_api_key,
            website: p.website,
            description: p.description,
            is_new: p.is_new || false,
            discovered_at: p.discovered_at,
            proxy: null
          });
        });
      }
      
      // Add exchange providers with health data
      if (healthData.providers) {
        Object.entries(healthData.providers).forEach(([name, data]) => {
          // Check if already exists
          const existing = providers.find(p => p.id === name.toLowerCase());
          if (existing) {
            existing.latency = data.latency_ms;
            existing.health_status = data.status;
            existing.error = data.error;
          } else {
            providers.push({
              id: name.toLowerCase(),
              name: name,
              type: 'exchange',
              category: 'exchange',
              status: data.status,
              latency: data.latency_ms,
              error: data.error,
              proxy: null
            });
          }
        });
      }
      
      // Get gateway stats
      const statsRes = await fetch(`${API_URL}/api/providers/stats`);
      const statsData = await statsRes.json();
      
      setProviderPool({ 
        providers,
        stats: statsData,
        categories: statsData.providers_by_category || {},
        capabilities: statsData.capabilities_count || {}
      });
    } catch (err) {
      console.error('Failed to fetch provider pool:', err);
    }
  };
  // LLM Keys Admin Section
  const renderLlmKeysAdmin = () => (
    <div className="space-y-6" data-testid="llm-keys-admin">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2" style={{ color: colors.text }}>
            <Zap size={24} style={{ color: '#8b5cf6' }} />
            LLM Keys Management
          </h2>
          <p className="text-sm" style={{ color: colors.textSecondary }}>
            Manage API keys for text and image generation (OpenAI, Anthropic, Google, Emergent)
          </p>
        </div>
        <button
          onClick={() => setShowAddLlmKey(true)}
          data-testid="add-llm-key-btn"
          className="flex items-center gap-2 px-4 py-2 rounded-xl font-medium transition-all"
          style={{ backgroundColor: '#8b5cf6', color: 'white' }}
        >
          <Plus size={18} />
          Add LLM Key
        </button>
      </div>
      
      {/* Summary Cards */}
      {llmKeysSummary && (
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-gradient-to-br from-purple-50 to-violet-50 rounded-2xl p-4 border" style={{ borderColor: '#e9d5ff' }}>
            <p className="text-sm font-medium" style={{ color: '#7c3aed' }}>Всего ключей</p>
            <p className="text-2xl font-bold" style={{ color: '#5b21b6' }}>{llmKeysSummary.total_keys || 0}</p>
          </div>
          <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-2xl p-4 border" style={{ borderColor: '#bbf7d0' }}>
            <p className="text-sm font-medium" style={{ color: '#059669' }}>Покрытие текста</p>
            <p className="text-2xl font-bold" style={{ color: '#047857' }}>
              {llmKeysSummary.capabilities_coverage?.text || 0} keys
            </p>
          </div>
          <div className="bg-gradient-to-br from-blue-50 to-cyan-50 rounded-2xl p-4 border" style={{ borderColor: '#bae6fd' }}>
            <p className="text-sm font-medium" style={{ color: '#0891b2' }}>Покрытие изображений</p>
            <p className="text-2xl font-bold" style={{ color: '#0e7490' }}>
              {llmKeysSummary.capabilities_coverage?.image || 0} keys
            </p>
          </div>
          <div className="bg-gradient-to-br from-orange-50 to-amber-50 rounded-2xl p-4 border" style={{ borderColor: '#fed7aa' }}>
            <p className="text-sm font-medium" style={{ color: '#d97706' }}>
              {llmKeysSummary.emergent_key_configured ? 'Emergent Key активен<' : 'Нет Emergent Key'}
            </p>
            <p className="text-2xl font-bold" style={{ color: '#b45309' }}>
              {llmKeysSummary.emergent_key_configured ? '✓' : '—'}
            </p>
          </div>
        </div>
      )}
      
      {/* Analytics Section */}
      <div className="bg-white rounded-2xl border p-6" style={{ borderColor: colors.border }}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center gap-2" style={{ color: colors.text }}>
            <BarChart2 size={20} style={{ color: '#8b5cf6' }} />
            Usage Analytics (24h)
          </h3>
          <button
            onClick={fetchLlmAnalytics}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm"
            style={{ backgroundColor: '#f3e8ff', color: '#7c3aed' }}
          >
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>
        
        {llmAnalytics ? (
          <div className="space-y-4">
            {/* Overview Stats */}
            <div className="grid grid-cols-5 gap-3">
              <div className="bg-gray-50 rounded-xl p-3 text-center">
                <p className="text-2xl font-bold" style={{ color: colors.text }}>{llmAnalytics.total_requests || 0}</p>
                <p className="text-xs" style={{ color: colors.textMuted }}>Total Requests</p>
              </div>
              <div className="bg-green-50 rounded-xl p-3 text-center">
                <p className="text-2xl font-bold" style={{ color: '#16a34a' }}>{llmAnalytics.success_count || 0}</p>
                <p className="text-xs" style={{ color: colors.textMuted }}>Success</p>
              </div>
              <div className="bg-red-50 rounded-xl p-3 text-center">
                <p className="text-2xl font-bold" style={{ color: '#dc2626' }}>{llmAnalytics.error_count || 0}</p>
                <p className="text-xs" style={{ color: colors.textMuted }}>Errors</p>
              </div>
              <div className="bg-blue-50 rounded-xl p-3 text-center">
                <p className="text-2xl font-bold" style={{ color: '#2563eb' }}>
                  {((llmAnalytics.success_rate || 0) * 100).toFixed(1)}%
                </p>
                <p className="text-xs" style={{ color: colors.textMuted }}>Success Rate</p>
              </div>
              <div className="bg-purple-50 rounded-xl p-3 text-center">
                <p className="text-2xl font-bold" style={{ color: '#7c3aed' }}>
                  {(llmAnalytics.total_tokens || 0).toLocaleString()}
                </p>
                <p className="text-xs" style={{ color: colors.textMuted }}>Tokens Used</p>
              </div>
            </div>
            
            {/* By Provider */}
            {llmAnalyticsByProvider.length > 0 && (
              <div>
                <p className="text-sm font-medium mb-2" style={{ color: colors.textSecondary }}>By Provider</p>
                <div className="grid grid-cols-4 gap-2">
                  {llmAnalyticsByProvider.map(p => (
                    <div key={p.provider} className="bg-gray-50 rounded-xl p-3">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium capitalize" style={{ color: colors.text }}>{p.provider}</span>
                        <span className="text-xs px-1.5 py-0.5 rounded" 
                          style={{ 
                            backgroundColor: p.success_rate > 0.9 ? '#dcfce7' : p.success_rate > 0.7 ? '#fef9c3' : '#fee2e2',
                            color: p.success_rate > 0.9 ? '#16a34a' : p.success_rate > 0.7 ? '#ca8a04' : '#dc2626'
                          }}>
                          {(p.success_rate * 100).toFixed(0)}%
                        </span>
                      </div>
                      <p className="text-xs" style={{ color: colors.textMuted }}>
                        {p.total_requests} requests • {p.avg_latency_ms}ms avg
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Hourly Chart (Simple bar visualization) */}
            {llmHourlyData.length > 0 && (
              <div>
                <p className="text-sm font-medium mb-2" style={{ color: colors.textSecondary }}>Hourly Activity</p>
                <div className="flex items-end gap-1 h-20">
                  {llmHourlyData.slice(-24).map((h, i) => {
                    const maxReq = Math.max(...llmHourlyData.map(d => d.requests)) || 1;
                    const height = (h.requests / maxReq) * 100;
                    return (
                      <div 
                        key={i}
                        className="flex-1 rounded-t transition-all hover:opacity-80"
                        style={{ 
                          height: `${Math.max(4, height)}%`,
                          backgroundColor: h.success_rate > 0.9 ? '#86efac' : h.success_rate > 0.5 ? '#fde047' : '#fca5a5'
                        }}
                        title={`${h.hour}: ${h.requests} requests (${(h.success_rate * 100).toFixed(0)}% success)`}
                      />
                    );
                  })}
                </div>
                <div className="flex justify-between mt-1">
                  <span className="text-xs" style={{ color: colors.textMuted }}>24h ago</span>
                  <span className="text-xs" style={{ color: colors.textMuted }}>Now</span>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-8">
            <BarChart2 size={32} className="mx-auto mb-2" style={{ color: colors.textMuted }} />
            <p className="text-sm" style={{ color: colors.textSecondary }}>No analytics data yet</p>
            <button
              onClick={fetchLlmAnalytics}
              className="mt-2 text-sm px-4 py-2 rounded-lg"
              style={{ backgroundColor: '#f3e8ff', color: '#7c3aed' }}
            >
              Load Analytics
            </button>
          </div>
        )}
      </div>
      
      {/* Add Key Modal */}
      {showAddLlmKey && (
        <div className="bg-white rounded-2xl border p-6 shadow-xl" style={{ borderColor: colors.border }}>
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-bold" style={{ color: colors.text }}>Add LLM API Key</h3>
            <button 
              onClick={() => setShowAddLlmKey(false)}
              className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <X size={20} style={{ color: colors.textMuted }} />
            </button>
          </div>
          
          <div className="space-y-5">
            {/* Provider Selection - Custom White Dropdown */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: colors.textSecondary }}>Provider</label>
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setNewLlmKey(prev => ({ ...prev, _dropdownOpen: !prev._dropdownOpen }))}
                    className="w-full px-4 py-3 rounded-xl border bg-white text-left flex items-center justify-between hover:border-violet-400 transition-colors"
                    style={{ borderColor: colors.border }}
                  >
                    <span className="flex items-center gap-2" style={{ color: colors.text }}>
                      {newLlmKey.provider === 'openai' && <Zap size={16} style={{ color: '#10a37f' }} />}
                      {newLlmKey.provider === 'anthropic' && <Shield size={16} style={{ color: '#d97706' }} />}
                      {newLlmKey.provider === 'google' && <Globe size={16} style={{ color: '#4285f4' }} />}
                      {newLlmKey.provider === 'emergent' && <Activity size={16} style={{ color: '#8b5cf6' }} />}
                      {llmProviders.find(p => p.id === newLlmKey.provider)?.name || 'Select Provider'}
                    </span>
                    <ChevronDown size={18} style={{ color: colors.textMuted }} />
                  </button>
                  
                  {/* Custom Dropdown Menu */}
                  {newLlmKey._dropdownOpen && (
                    <div 
                      className="absolute top-full left-0 right-0 mt-2 bg-white rounded-xl border shadow-lg z-50 overflow-hidden"
                      style={{ borderColor: colors.border }}
                    >
                      {llmProviders.map(p => (
                        <button
                          key={p.id}
                          type="button"
                          onClick={() => {
                            setNewLlmKey(prev => ({ 
                              ...prev, 
                              provider: p.id, 
                              capabilities: p.capabilities || ['text'],
                              _dropdownOpen: false 
                            }));
                          }}
                          className="w-full px-4 py-3 text-left hover:bg-violet-50 transition-colors flex items-center justify-between"
                          style={{ 
                            backgroundColor: newLlmKey.provider === p.id ? '#f5f3ff' : 'white',
                            color: colors.text
                          }}
                        >
                          <span className="flex items-center gap-2">
                            {p.id === 'openai' && <Zap size={16} style={{ color: '#10a37f' }} />}
                            {p.id === 'anthropic' && <Shield size={16} style={{ color: '#d97706' }} />}
                            {p.id === 'google' && <Globe size={16} style={{ color: '#4285f4' }} />}
                            {p.id === 'emergent' && <Activity size={16} style={{ color: '#8b5cf6' }} />}
                            {p.name}
                          </span>
                          {newLlmKey.provider === p.id && (
                            <CheckCircle size={18} style={{ color: '#8b5cf6' }} />
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: colors.textSecondary }}>Name (optional)</label>
                <input
                  type="text"
                  value={newLlmKey.name}
                  onChange={(e) => setNewLlmKey({ ...newLlmKey, name: e.target.value })}
                  placeholder="My OpenAI Key"
                  className="w-full px-4 py-3 rounded-xl border bg-white hover:border-violet-400 focus:border-violet-500 focus:ring-2 focus:ring-violet-200 transition-all outline-none"
                  style={{ borderColor: colors.border }}
                />
              </div>
            </div>
            
            {/* API Key Input */}
            <div>
              <label className="block text-sm font-medium mb-2" style={{ color: colors.textSecondary }}>API Key</label>
              <input
                type="password"
                value={newLlmKey.api_key}
                onChange={(e) => setNewLlmKey({ ...newLlmKey, api_key: e.target.value })}
                placeholder="sk-..."
                className="w-full px-4 py-3 rounded-xl border font-mono bg-white hover:border-violet-400 focus:border-violet-500 focus:ring-2 focus:ring-violet-200 transition-all outline-none"
                style={{ borderColor: colors.border }}
              />
            </div>
            
            {/* Capabilities - Updated with Sentiment */}
            <div>
              <label className="block text-sm font-medium mb-3" style={{ color: colors.textSecondary }}>
                Capabilities
                <span className="ml-2 text-xs font-normal" style={{ color: colors.textMuted }}>
                  Select what this key can be used for
                </span>
              </label>
              <div className="flex gap-3 flex-wrap">
                {['text', 'image', 'audio', 'video', 'sentiment'].map(cap => (
                  <label 
                    key={cap} 
                    className={`flex items-center gap-2 px-4 py-2.5 rounded-xl border cursor-pointer transition-all ${
                      newLlmKey.capabilities.includes(cap) 
                        ? 'bg-violet-50 border-violet-400' 
                        : 'bg-white hover:border-violet-300'
                    }`}
                    style={{ borderColor: newLlmKey.capabilities.includes(cap) ? '#a78bfa' : colors.border }}
                  >
                    <input
                      type="checkbox"
                      checked={newLlmKey.capabilities.includes(cap)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setNewLlmKey({ ...newLlmKey, capabilities: [...newLlmKey.capabilities, cap] });
                        } else {
                          setNewLlmKey({ ...newLlmKey, capabilities: newLlmKey.capabilities.filter(c => c !== cap) });
                        }
                      }}
                      className="sr-only"
                    />
                    <span 
                      className={`w-5 h-5 rounded-md flex items-center justify-center border ${
                        newLlmKey.capabilities.includes(cap) 
                          ? 'bg-violet-500 border-violet-500' 
                          : 'bg-white border-gray-300'
                      }`}
                    >
                      {newLlmKey.capabilities.includes(cap) && (
                        <CheckCircle size={14} style={{ color: 'white' }} />
                      )}
                    </span>
                    <span className={`text-sm font-medium capitalize ${
                      newLlmKey.capabilities.includes(cap) ? 'text-violet-700' : ''
                    }`} style={{ color: newLlmKey.capabilities.includes(cap) ? '#6d28d9' : colors.text }}>
                      {cap === 'sentiment' ? 'Sentiment Analysis' : cap}
                    </span>
                  </label>
                ))}
              </div>
              <p className="text-xs mt-2" style={{ color: colors.textMuted }}>
                OpenAI keys can handle multiple capabilities: news analysis, image generation, and sentiment analysis
              </p>
            </div>
            
            {/* Set as Default */}
            <div className="flex items-center pt-2">
              <label className="flex items-center gap-3 cursor-pointer">
                <div className="relative">
                  <input
                    type="checkbox"
                    checked={newLlmKey.is_default}
                    onChange={(e) => setNewLlmKey({ ...newLlmKey, is_default: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 rounded-full peer peer-checked:bg-violet-500 transition-colors"></div>
                  <div className="absolute left-1 top-1 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-5 shadow-sm"></div>
                </div>
                <span className="text-sm font-medium" style={{ color: colors.text }}>Set as default provider</span>
              </label>
            </div>
          </div>
          
          {/* Action Buttons */}
          <div className="flex justify-end gap-3 mt-6 pt-4 border-t" style={{ borderColor: colors.border }}>
            <button
              onClick={() => setShowAddLlmKey(false)}
              className="px-5 py-2.5 rounded-xl font-medium transition-all hover:bg-gray-100"
              style={{ backgroundColor: colors.surface, color: colors.textSecondary }}
            >
              Cancel
            </button>
            <button
              onClick={addLlmKey}
              disabled={!newLlmKey.api_key}
              className="px-5 py-2.5 rounded-xl font-medium transition-all"
              style={{ 
                backgroundColor: newLlmKey.api_key ? '#8b5cf6' : '#d1d5db', 
                color: 'white',
                cursor: newLlmKey.api_key ? 'pointer' : 'not-allowed'
              }}
            >
              Add Key
            </button>
          </div>
        </div>
      )}
      
      {/* Keys List */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold flex items-center gap-2" style={{ color: colors.text }}>
          Configured LLM Keys ({llmKeys.length})
        </h3>
        
        {llmKeysLoading ? (
          <div className="flex items-center justify-center h-32">
            <RefreshCw className="animate-spin" size={24} style={{ color: colors.accent }} />
          </div>
        ) : llmKeys.length === 0 ? (
          <div className="bg-gradient-to-br from-purple-50 to-violet-50 rounded-2xl p-8 text-center border" style={{ borderColor: '#e9d5ff' }}>
            <Zap size={48} className="mx-auto mb-4" style={{ color: '#8b5cf6' }} />
            <p className="font-medium" style={{ color: '#5b21b6' }}>No LLM Keys Configured</p>
            <p className="text-sm mt-1" style={{ color: '#7c3aed' }}>
              Add OpenAI, Anthropic, or Google keys to enable text/image generation
            </p>
            <p className="text-xs mt-2" style={{ color: '#a78bfa' }}>
              Currently using Emergent Universal Key as fallback
            </p>
          </div>
        ) : (
          llmKeys.map((key, i) => (
            <div 
              key={key.id || i}
              data-testid={`llm-key-${key.id}`}
              className="bg-white rounded-2xl border p-4 transition-all hover:shadow-md"
              style={{ borderColor: colors.border }}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div 
                    className="w-12 h-12 rounded-xl flex items-center justify-center"
                    style={{ 
                      backgroundColor: key.healthy ? '#f0fdf4' : '#fef2f2',
                      color: key.healthy ? '#16a34a' : '#dc2626'
                    }}
                  >
                    {key.provider === 'openai' && <Zap size={24} />}
                    {key.provider === 'anthropic' && <Terminal size={24} />}
                    {key.provider === 'google' && <Globe size={24} />}
                    {key.provider === 'emergent' && <Shield size={24} />}
                  </div>
                  <div>
                    <p className="font-medium flex items-center gap-2" style={{ color: colors.text }}>
                      {key.name}
                      <span className="px-2 py-0.5 rounded text-xs font-medium capitalize"
                        style={{ backgroundColor: '#f3e8ff', color: '#7c3aed' }}>
                        {key.provider}
                      </span>
                      {key.is_default && (
                        <span className="px-2 py-0.5 rounded text-xs font-medium"
                          style={{ backgroundColor: '#dbeafe', color: '#2563eb' }}>
                          Default
                        </span>
                      )}
                      {!key.enabled && (
                        <span className="px-2 py-0.5 rounded text-xs font-medium"
                          style={{ backgroundColor: '#f3f4f6', color: '#6b7280' }}>
                          Disabled
                        </span>
                      )}
                    </p>
                    <p className="text-sm flex items-center gap-2 flex-wrap" style={{ color: colors.textSecondary }}>
                      Key: {key.api_key_masked} • 
                      <span className="flex gap-1">
                        {key.capabilities?.map(cap => (
                          <span 
                            key={cap}
                            className="px-1.5 py-0.5 rounded text-xs font-medium capitalize"
                            style={{ 
                              backgroundColor: cap === 'sentiment' ? '#fef3c7' : '#ecfdf5',
                              color: cap === 'sentiment' ? '#92400e' : '#059669'
                            }}
                          >
                            {cap === 'sentiment' ? 'Sentiment' : cap}
                          </span>
                        ))}
                      </span>
                      • Requests: {key.requests_total || 0}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => testLlmKey(key.id)}
                    className="p-2 rounded-lg transition-all hover:bg-purple-50"
                    title="Проверить"
                  >
                    <Activity size={18} style={{ color: '#8b5cf6' }} />
                  </button>
                  {!key.healthy && (
                    <button
                      onClick={() => resetKeyHealth(key.id)}
                      className="p-2 rounded-lg transition-all hover:bg-green-50"
                      title="Reset health status"
                    >
                      <RotateCcw size={18} style={{ color: '#16a34a' }} />
                    </button>
                  )}
                  <button
                    onClick={() => toggleLlmKey(key.id, !key.enabled)}
                    className="p-2 rounded-lg transition-all hover:bg-gray-100"
                    title={key.enabled ? 'Disable' : 'Enable'}
                  >
                    {key.enabled ? (
                      <CheckCircle size={18} style={{ color: colors.success }} />
                    ) : (
                      <XCircle size={18} style={{ color: colors.textMuted }} />
                    )}
                  </button>
                  <button
                    onClick={() => removeLlmKey(key.id)}
                    className="p-2 rounded-lg transition-all hover:bg-red-50"
                    title="Удалить ключ"
                  >
                    <Trash2 size={18} style={{ color: colors.error }} />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
      
      {/* Provider Info */}
      <div className="mt-8">
        <h3 className="text-lg font-semibold mb-4" style={{ color: colors.text }}>Supported Providers</h3>
        <div className="grid grid-cols-2 gap-4">
          {llmProviders.map(provider => (
            <div 
              key={provider.id}
              className="bg-white rounded-2xl border p-4"
              style={{ borderColor: colors.border }}
            >
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: '#f3e8ff' }}>
                  {provider.id === 'openai' && <Zap size={20} style={{ color: '#8b5cf6' }} />}
                  {provider.id === 'anthropic' && <Terminal size={20} style={{ color: '#8b5cf6' }} />}
                  {provider.id === 'google' && <Globe size={20} style={{ color: '#8b5cf6' }} />}
                  {provider.id === 'emergent' && <Shield size={20} style={{ color: '#8b5cf6' }} />}
                </div>
                <div>
                  <p className="font-medium" style={{ color: colors.text }}>{provider.name}</p>
                  <p className="text-xs" style={{ color: colors.textSecondary }}>{provider.description}</p>
                </div>
              </div>
              <div className="flex flex-wrap gap-1 mb-2">
                {provider.capabilities?.map(cap => (
                  <span key={cap} className="px-2 py-0.5 rounded text-xs capitalize"
                    style={{ backgroundColor: '#f0fdf4', color: '#16a34a' }}>
                    {cap}
                  </span>
                ))}
              </div>
              <p className="text-xs" style={{ color: colors.textMuted }}>
                Key format: {provider.key_format}
              </p>
              {provider.docs_url && (
                <a href={provider.docs_url} target="_blank" rel="noopener noreferrer"
                  className="text-xs flex items-center gap-1 mt-1" style={{ color: colors.accent }}>
                  Get API Key <ExternalLink size={12} />
                </a>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  // Sentiment Keys Admin Section
  const renderSentimentKeysAdmin = () => {
    // Check provider status from loaded sentimentProviders
    const fomoProvider = sentimentProviders.find(p => p.id === 'fomo');
    const openaiProvider = sentimentProviders.find(p => p.id === 'openai');
    
    // Use available field from API response
    const fomoActive = fomoProvider?.available === true;
    const openaiActive = openaiProvider?.available === true;
    const bothActive = fomoActive && openaiActive;
    
    return (
    <div className="space-y-6" data-testid="sentiment-keys-admin">
      {/* Header with Add Button */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2" style={{ color: colors.text }}>
            <BarChart2 size={24} style={{ color: '#7c3aed' }} />
            Sentiment Analysis
          </h2>
          <p className="text-sm" style={{ color: colors.textSecondary }}>
            Multi-provider sentiment engine configuration
          </p>
        </div>
        <button
          onClick={() => setShowAddSentimentKey(true)}
          data-testid="add-sentiment-key-btn"
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl font-medium transition-all hover:shadow-md"
          style={{ backgroundColor: '#7c3aed', color: 'white' }}
        >
          <Plus size={18} />
          Add Custom Key
        </button>
      </div>
      
      {/* Add Custom Sentiment Key Modal */}
      {showAddSentimentKey && (
        <div className="bg-white rounded-2xl border p-6 shadow-xl" style={{ borderColor: colors.border }}>
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-bold" style={{ color: colors.text }}>Add Custom Sentiment Key</h3>
            <button 
              onClick={() => setShowAddSentimentKey(false)}
              className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <X size={20} style={{ color: colors.textMuted }} />
            </button>
          </div>
          
          <div className="space-y-5">
            {/* Provider Type */}
            <div>
              <label className="block text-sm font-medium mb-2" style={{ color: colors.textSecondary }}>Provider Type</label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setNewSentimentKey({ ...newSentimentKey, provider: 'openai' })}
                  className={`p-4 rounded-xl border-2 text-left transition-all ${
                    newSentimentKey.provider === 'openai' ? 'border-violet-500 bg-violet-50' : 'border-gray-200 hover:border-violet-300'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: '#10a37f20' }}>
                      <Zap size={20} style={{ color: '#10a37f' }} />
                    </div>
                    <div>
                      <p className="font-semibold" style={{ color: colors.text }}>OpenAI</p>
                      <p className="text-xs" style={{ color: colors.textMuted }}>GPT-4o for sentiment</p>
                    </div>
                  </div>
                </button>
                
                <button
                  type="button"
                  onClick={() => setNewSentimentKey({ ...newSentimentKey, provider: 'custom' })}
                  className={`p-4 rounded-xl border-2 text-left transition-all ${
                    newSentimentKey.provider === 'custom' ? 'border-violet-500 bg-violet-50' : 'border-gray-200 hover:border-violet-300'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: '#8b5cf620' }}>
                      <Server size={20} style={{ color: '#8b5cf6' }} />
                    </div>
                    <div>
                      <p className="font-semibold" style={{ color: colors.text }}>Custom API</p>
                      <p className="text-xs" style={{ color: colors.textMuted }}>Your own sentiment API</p>
                    </div>
                  </div>
                </button>
              </div>
            </div>
            
            {/* Name */}
            <div>
              <label className="block text-sm font-medium mb-2" style={{ color: colors.textSecondary }}>Name</label>
              <input
                type="text"
                value={newSentimentKey.name}
                onChange={(e) => setNewSentimentKey({ ...newSentimentKey, name: e.target.value })}
                placeholder="My Sentiment Key"
                className="w-full px-4 py-3 rounded-xl border bg-white hover:border-violet-400 focus:border-violet-500 focus:ring-2 focus:ring-violet-200 transition-all outline-none"
                style={{ borderColor: colors.border }}
              />
            </div>
            
            {/* API Key */}
            <div>
              <label className="block text-sm font-medium mb-2" style={{ color: colors.textSecondary }}>API Key</label>
              <input
                type="password"
                value={newSentimentKey.api_key}
                onChange={(e) => setNewSentimentKey({ ...newSentimentKey, api_key: e.target.value })}
                placeholder={newSentimentKey.provider === 'openai' ? 'sk-...' : 'your-api-key'}
                className="w-full px-4 py-3 rounded-xl border font-mono bg-white hover:border-violet-400 focus:border-violet-500 focus:ring-2 focus:ring-violet-200 transition-all outline-none"
                style={{ borderColor: colors.border }}
              />
            </div>
            
            {/* Custom Endpoint URL (only for custom provider) */}
            {newSentimentKey.provider === 'custom' && (
              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: colors.textSecondary }}>
                  Endpoint URL <span className="text-red-500">*</span>
                </label>
                <input
                  type="url"
                  value={newSentimentKey.endpoint_url || ''}
                  onChange={(e) => setNewSentimentKey({ ...newSentimentKey, endpoint_url: e.target.value })}
                  placeholder="https://api.yourservice.com/sentiment"
                  className="w-full px-4 py-3 rounded-xl border font-mono bg-white hover:border-violet-400 focus:border-violet-500 focus:ring-2 focus:ring-violet-200 transition-all outline-none"
                  style={{ borderColor: colors.border }}
                />
                <p className="text-xs mt-2" style={{ color: colors.textMuted }}>
                  Your custom sentiment API endpoint. Should accept POST with {"{"}"text": "..."{"}"}
                </p>
              </div>
            )}
            
            {/* Set as Default */}
            <div className="flex items-center pt-2">
              <label className="flex items-center gap-3 cursor-pointer">
                <div className="relative">
                  <input
                    type="checkbox"
                    checked={newSentimentKey.is_default}
                    onChange={(e) => setNewSentimentKey({ ...newSentimentKey, is_default: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 rounded-full peer peer-checked:bg-violet-500 transition-colors"></div>
                  <div className="absolute left-1 top-1 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-5 shadow-sm"></div>
                </div>
                <span className="text-sm font-medium" style={{ color: colors.text }}>Set as default sentiment provider</span>
              </label>
            </div>
          </div>
          
          {/* Action Buttons */}
          <div className="flex justify-end gap-3 mt-6 pt-4 border-t" style={{ borderColor: colors.border }}>
            <button
              onClick={() => setShowAddSentimentKey(false)}
              className="px-5 py-2.5 rounded-xl font-medium transition-all hover:bg-gray-100"
              style={{ backgroundColor: colors.surface, color: colors.textSecondary }}
            >
              Cancel
            </button>
            <button
              onClick={addSentimentKey}
              disabled={!newSentimentKey.api_key || (newSentimentKey.provider === 'custom' && !newSentimentKey.endpoint_url)}
              className="px-5 py-2.5 rounded-xl font-medium transition-all"
              style={{ 
                backgroundColor: (newSentimentKey.api_key && (newSentimentKey.provider !== 'custom' || newSentimentKey.endpoint_url)) ? '#7c3aed' : '#d1d5db', 
                color: 'white',
                cursor: (newSentimentKey.api_key && (newSentimentKey.provider !== 'custom' || newSentimentKey.endpoint_url)) ? 'pointer' : 'not-allowed'
              }}
            >
              Add Key
            </button>
          </div>
        </div>
      )}
      
      {/* System Status Alert */}
      {!openaiActive && (
        <div 
          className="flex items-center gap-3 p-4 rounded-xl border"
          style={{ 
            backgroundColor: '#fef3c7', 
            borderColor: '#fcd34d',
            color: '#92400e'
          }}
        >
          <AlertTriangle size={20} />
          <div>
            <p className="font-medium">OpenAI API Key Not Configured</p>
            <p className="text-sm opacity-80">
              Multi-provider consensus is limited. Only FOMO keyword-based analysis is active.
              Add OpenAI key below for full AI-powered sentiment analysis.
            </p>
          </div>
        </div>
      )}
      
      {/* Provider Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* FOMO Provider Card - Internal Engine (NO API KEY REQUIRED) */}
        <div 
          className={`rounded-2xl p-5 border-2 transition-all ${fomoActive ? 'shadow-md' : 'opacity-60'}`}
          style={{ 
            backgroundColor: fomoActive ? '#fefce8' : '#f9fafb',
            borderColor: fomoActive ? '#facc15' : '#e5e7eb'
          }}
          data-testid="fomo-provider-card"
        >
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div 
                className="w-10 h-10 rounded-xl flex items-center justify-center"
                style={{ backgroundColor: fomoActive ? '#fef08a' : '#e5e7eb' }}
              >
                <Zap size={20} style={{ color: fomoActive ? '#ca8a04' : '#9ca3af' }} />
              </div>
              <div>
                <p className="font-semibold" style={{ color: fomoActive ? '#854d0e' : '#6b7280' }}>FOMO</p>
                <p className="text-xs" style={{ color: fomoActive ? '#a16207' : '#9ca3af' }}>Внутренний движок / Internal</p>
              </div>
            </div>
            <div 
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: fomoActive ? '#22c55e' : '#d1d5db' }}
            />
          </div>
          <p className="text-xs mb-2" style={{ color: fomoActive ? '#92400e' : '#6b7280' }}>
            Встроенный анализатор на основе ключевых слов крипто-тематики
          </p>
          <p className="text-[10px] mb-3 px-2 py-1 rounded-lg inline-block" style={{ backgroundColor: '#e0f2fe', color: '#0369a1' }}>
            🔓 API ключ НЕ требуется
          </p>
          <div className="flex items-center justify-between text-xs">
            <span style={{ color: fomoActive ? '#a16207' : '#9ca3af' }}>Weight: 1.5x</span>
            <span 
              className="px-2 py-0.5 rounded-full font-medium"
              style={{ 
                backgroundColor: fomoActive ? '#dcfce7' : '#f3f4f6',
                color: fomoActive ? '#16a34a' : '#9ca3af'
              }}
            >
              {fomoActive ? 'ВСЕГДА АКТИВЕН' : 'INACTIVE'}
            </span>
          </div>
        </div>
        
        {/* OpenAI Provider Card - External API (REQUIRES API KEY) */}
        <div 
          className={`rounded-2xl p-5 border-2 transition-all ${openaiActive ? 'shadow-md' : 'opacity-60'}`}
          style={{ 
            backgroundColor: openaiActive ? '#f0fdf4' : '#f9fafb',
            borderColor: openaiActive ? '#22c55e' : '#e5e7eb'
          }}
          data-testid="openai-provider-card"
        >
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div 
                className="w-10 h-10 rounded-xl flex items-center justify-center"
                style={{ backgroundColor: openaiActive ? '#bbf7d0' : '#e5e7eb' }}
              >
                <Globe size={20} style={{ color: openaiActive ? '#16a34a' : '#9ca3af' }} />
              </div>
              <div>
                <p className="font-semibold" style={{ color: openaiActive ? '#166534' : '#6b7280' }}>OpenAI</p>
                <p className="text-xs" style={{ color: openaiActive ? '#15803d' : '#9ca3af' }}>Внешний API / GPT-4o</p>
              </div>
            </div>
            <div 
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: openaiActive ? '#22c55e' : '#d1d5db' }}
            />
          </div>
          <p className="text-xs mb-2" style={{ color: openaiActive ? '#166534' : '#6b7280' }}>
            AI-анализ с глубоким пониманием контекста
          </p>
          <p className="text-[10px] mb-3 px-2 py-1 rounded-lg inline-block" style={{ backgroundColor: openaiActive ? '#dcfce7' : '#fef3c7', color: openaiActive ? '#166534' : '#92400e' }}>
            {openaiActive ? '🔑 API ключ настроен' : '🔑 Требуется API ключ'}
          </p>
          <div className="flex items-center justify-between text-xs">
            <span style={{ color: openaiActive ? '#15803d' : '#9ca3af' }}>Weight: 1.0x</span>
            <span 
              className="px-2 py-0.5 rounded-full font-medium"
              style={{ 
                backgroundColor: openaiActive ? '#dcfce7' : '#fee2e2',
                color: openaiActive ? '#16a34a' : '#dc2626'
              }}
            >
              {openaiActive ? 'АКТИВЕН' : 'НУЖЕН КЛЮЧ'}
            </span>
          </div>
        </div>
        
        {/* Consensus Card */}
        <div 
          className={`rounded-2xl p-5 border-2 transition-all ${bothActive ? 'shadow-md' : 'opacity-60'}`}
          style={{ 
            backgroundColor: bothActive ? '#f5f3ff' : '#f9fafb',
            borderColor: bothActive ? '#8b5cf6' : '#e5e7eb'
          }}
        >
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div 
                className="w-10 h-10 rounded-xl flex items-center justify-center"
                style={{ backgroundColor: bothActive ? '#ddd6fe' : '#e5e7eb' }}
              >
                <Activity size={20} style={{ color: bothActive ? '#7c3aed' : '#9ca3af' }} />
              </div>
              <div>
                <p className="font-semibold" style={{ color: bothActive ? '#5b21b6' : '#6b7280' }}>Consensus</p>
                <p className="text-xs" style={{ color: bothActive ? '#6d28d9' : '#9ca3af' }}>FOMO + OpenAI</p>
              </div>
            </div>
            <div 
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: bothActive ? '#22c55e' : '#d1d5db' }}
            />
          </div>
          <p className="text-xs mb-3" style={{ color: bothActive ? '#5b21b6' : '#6b7280' }}>
            Weighted average combining both engines for maximum accuracy
          </p>
          <div className="flex items-center justify-between text-xs">
            <span style={{ color: bothActive ? '#6d28d9' : '#9ca3af' }}>Best results</span>
            <span 
              className="px-2 py-0.5 rounded-full font-medium"
              style={{ 
                backgroundColor: bothActive ? '#dcfce7' : '#f3f4f6',
                color: bothActive ? '#16a34a' : '#9ca3af'
              }}
            >
              {bothActive ? 'ACTIVE' : 'PARTIAL'}
            </span>
          </div>
        </div>
      </div>
      
      {/* Consensus Formula - Improved Design */}
      <div 
        className="rounded-2xl overflow-hidden"
        style={{ 
          background: 'linear-gradient(135deg, #1e1b4b 0%, #312e81 100%)'
        }}
      >
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-white/10">
                <Activity size={20} style={{ color: '#c4b5fd' }} />
              </div>
              <div>
                <h3 className="font-semibold text-white">Consensus Formula</h3>
                <p className="text-xs text-indigo-300">Weighted multi-provider averaging</p>
              </div>
            </div>
            <div className="relative group">
              <button className="p-2 rounded-lg bg-white/10 hover:bg-white/20 transition-colors">
                <HelpCircle size={16} style={{ color: '#c4b5fd' }} />
              </button>
              {/* Tooltip */}
              <div className="absolute right-0 top-full mt-2 w-80 p-4 bg-white rounded-xl shadow-2xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                <p className="text-sm font-medium text-gray-900 mb-2">Как работает Consensus / How it works</p>
                <p className="text-xs text-gray-600 mb-3">
                  Каждый провайдер анализирует текст независимо. Результаты объединяются взвешенным средним:
                </p>
                <ul className="text-xs text-gray-600 space-y-1.5">
                  <li className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-yellow-400"></span>
                    <strong>FOMO (Внутренний)</strong>: 1.5x вес — крипто-специфичный, <u>ключ не нужен</u>
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-green-400"></span>
                    <strong>OpenAI (Внешний)</strong>: 1.0x вес — требуется API ключ
                  </li>
                  <li>• Бонус +15% confidence когда оба провайдера согласны</li>
                </ul>
              </div>
            </div>
          </div>
          
          {/* Formula Visualization */}
          <div className="grid grid-cols-5 gap-2 mb-4">
            <div className="bg-white/10 rounded-xl p-3 text-center">
              <p className="text-xl font-bold text-yellow-300">1.5x</p>
              <p className="text-[10px] text-indigo-300 mt-1">FOMO Weight</p>
            </div>
            <div className="bg-white/10 rounded-xl p-3 text-center flex items-center justify-center">
              <span className="text-2xl text-indigo-400">×</span>
            </div>
            <div className="bg-white/10 rounded-xl p-3 text-center">
              <p className="text-xl font-bold text-green-300">score</p>
              <p className="text-[10px] text-indigo-300 mt-1">Provider Score</p>
            </div>
            <div className="bg-white/10 rounded-xl p-3 text-center flex items-center justify-center">
              <span className="text-2xl text-indigo-400">×</span>
            </div>
            <div className="bg-white/10 rounded-xl p-3 text-center">
              <p className="text-xl font-bold text-blue-300">conf</p>
              <p className="text-[10px] text-indigo-300 mt-1">Confidence</p>
            </div>
          </div>
          
          <div className="bg-white/5 rounded-xl p-4">
            <p className="text-xs text-indigo-200 font-mono text-center">
              consensus = Σ(weight × score × confidence) / Σ(weight × confidence)
            </p>
          </div>
        </div>
        
        {/* Agreement Bonus Section */}
        <div className="px-6 py-4 bg-black/20 border-t border-white/10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle size={16} style={{ color: '#86efac' }} />
              <span className="text-sm text-indigo-200">Agreement Bonus</span>
            </div>
            <span className="text-sm font-medium text-green-300">+15% confidence when providers agree</span>
          </div>
        </div>
      </div>
      
      {/* Intelligence Score Formula - Compact Design */}
      <div 
        className="rounded-2xl overflow-hidden"
        style={{ 
          background: 'linear-gradient(135deg, #164e63 0%, #0e7490 100%)'
        }}
      >
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-white/10">
                <Target size={20} style={{ color: '#67e8f9' }} />
              </div>
              <div>
                <h3 className="font-semibold text-white">News Intelligence Score</h3>
                <p className="text-xs text-cyan-300">Importance calculation (0-100)</p>
              </div>
            </div>
            <div className="relative group">
              <button className="p-2 rounded-lg bg-white/10 hover:bg-white/20 transition-colors">
                <HelpCircle size={16} style={{ color: '#67e8f9' }} />
              </button>
              {/* Tooltip */}
              <div className="absolute right-0 top-full mt-2 w-72 p-4 bg-white rounded-xl shadow-2xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                <p className="text-sm font-medium text-gray-900 mb-2">Intelligence Score Factors</p>
                <ul className="text-xs text-gray-600 space-y-2">
                  <li><span className="font-medium text-cyan-600">35% Source Weight</span> - Reliability of news source</li>
                  <li><span className="font-medium text-emerald-600">25% Source Count</span> - Multi-source confirmation</li>
                  <li><span className="font-medium text-amber-600">20% Entity Importance</span> - Key players involved</li>
                  <li><span className="font-medium text-violet-600">10% Sentiment</span> - Sentiment strength</li>
                  <li><span className="font-medium text-pink-600">10% Novelty</span> - Breaking news factor</li>
                </ul>
              </div>
            </div>
          </div>
          
          {/* Compact Factor Pills */}
          <div className="flex flex-wrap gap-2">
            <div className="flex items-center gap-2 bg-white/10 rounded-full px-4 py-2">
              <span className="text-lg font-bold text-cyan-300">35%</span>
              <span className="text-xs text-cyan-100">Source Weight</span>
            </div>
            <div className="flex items-center gap-2 bg-white/10 rounded-full px-4 py-2">
              <span className="text-lg font-bold text-emerald-300">25%</span>
              <span className="text-xs text-cyan-100">Source Count</span>
            </div>
            <div className="flex items-center gap-2 bg-white/10 rounded-full px-4 py-2">
              <span className="text-lg font-bold text-amber-300">20%</span>
              <span className="text-xs text-cyan-100">Entity Importance</span>
            </div>
            <div className="flex items-center gap-2 bg-white/10 rounded-full px-4 py-2">
              <span className="text-lg font-bold text-violet-300">10%</span>
              <span className="text-xs text-cyan-100">Sentiment</span>
            </div>
            <div className="flex items-center gap-2 bg-white/10 rounded-full px-4 py-2">
              <span className="text-lg font-bold text-pink-300">10%</span>
              <span className="text-xs text-cyan-100">Novelty</span>
            </div>
          </div>
        </div>
      </div>
      
      {/* Cache Statistics */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-gradient-to-br from-violet-50 to-purple-50 rounded-2xl p-4 border" style={{ borderColor: '#ddd6fe' }}>
          <p className="text-sm font-medium" style={{ color: '#7c3aed' }}>Providers Active</p>
          <p className="text-2xl font-bold" style={{ color: '#5b21b6' }}>
            {sentimentProviders.filter(p => p.available).length} / 2
          </p>
        </div>
        <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-2xl p-4 border" style={{ borderColor: '#bbf7d0' }}>
          <p className="text-sm font-medium" style={{ color: '#059669' }}>Total Cached</p>
          <p className="text-2xl font-bold" style={{ color: '#047857' }}>
            {sentimentHeatmapData[0]?.total || 0}
          </p>
        </div>
        <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl p-4 border" style={{ borderColor: '#c7d2fe' }}>
          <p className="text-sm font-medium" style={{ color: '#4f46e5' }}>FOMO Status</p>
          <p className="text-2xl font-bold" style={{ color: '#4338ca' }}>
            {fomoActive ? '✓ Active' : '—'}
          </p>
        </div>
        <div className="bg-gradient-to-br from-cyan-50 to-teal-50 rounded-2xl p-4 border" style={{ borderColor: '#99f6e4' }}>
          <p className="text-sm font-medium" style={{ color: '#0891b2' }}>OpenAI Status</p>
          <p className="text-2xl font-bold" style={{ color: '#0e7490' }}>
            {openaiActive ? '✓ Active' : 'No Key'}
          </p>
        </div>
      </div>
    </div>
  )};

  // Webhooks Admin Section
  const renderWebhooksAdmin = () => (
    <div className="space-y-6" data-testid="webhooks-admin">
      {/* Header with Add Button */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2" style={{ color: colors.text }}>
            <Wifi size={24} style={{ color: '#f97316' }} />
            Webhooks
          </h2>
          <p className="text-sm" style={{ color: colors.textSecondary }}>
            Интеграции для получения уведомлений о событиях в реальном времени
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={checkAllWebhookEvents}
            disabled={webhooksLoading}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl font-medium transition-all hover:shadow-md"
            style={{ backgroundColor: colors.surface, color: colors.textSecondary }}
            data-testid="check-webhook-events-btn"
          >
            <RefreshCw size={16} className={webhooksLoading ? 'animate-spin' : ''} />
            Проверить события
          </button>
          <button
            onClick={() => setShowAddWebhook(true)}
            data-testid="add-webhook-btn"
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl font-medium transition-all hover:shadow-md"
            style={{ backgroundColor: '#f97316', color: 'white' }}
          >
            <Plus size={18} />
            Добавить Webhook
          </button>
        </div>
      </div>

      {/* Add Webhook Modal */}
      {showAddWebhook && (
        <div className="bg-white rounded-2xl border p-6 shadow-xl" style={{ borderColor: colors.border }}>
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-bold" style={{ color: colors.text }}>Добавить Webhook</h3>
            <button 
              onClick={() => setShowAddWebhook(false)}
              className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <X size={20} style={{ color: colors.textMuted }} />
            </button>
          </div>
          
          <div className="space-y-5">
            {/* Name */}
            <div>
              <label className="block text-sm font-medium mb-2" style={{ color: colors.textSecondary }}>Название</label>
              <input
                type="text"
                value={newWebhook.name}
                onChange={(e) => setNewWebhook({ ...newWebhook, name: e.target.value })}
                placeholder="My Integration"
                className="w-full px-4 py-3 rounded-xl border bg-white hover:border-orange-400 focus:border-orange-500 focus:ring-2 focus:ring-orange-200 transition-all outline-none"
                style={{ borderColor: colors.border }}
                data-testid="webhook-name-input"
              />
            </div>
            
            {/* URL */}
            <div>
              <label className="block text-sm font-medium mb-2" style={{ color: colors.textSecondary }}>
                URL <span className="text-red-500">*</span>
              </label>
              <input
                type="url"
                value={newWebhook.url}
                onChange={(e) => setNewWebhook({ ...newWebhook, url: e.target.value })}
                placeholder="https://your-server.com/webhook"
                className="w-full px-4 py-3 rounded-xl border font-mono bg-white hover:border-orange-400 focus:border-orange-500 focus:ring-2 focus:ring-orange-200 transition-all outline-none"
                style={{ borderColor: colors.border }}
                data-testid="webhook-url-input"
              />
            </div>
            
            {/* Secret (optional) */}
            <div>
              <label className="block text-sm font-medium mb-2" style={{ color: colors.textSecondary }}>
                Secret Key (для HMAC подписи, опционально)
              </label>
              <input
                type="password"
                value={newWebhook.secret}
                onChange={(e) => setNewWebhook({ ...newWebhook, secret: e.target.value })}
                placeholder="your-secret-key"
                className="w-full px-4 py-3 rounded-xl border font-mono bg-white hover:border-orange-400 focus:border-orange-500 focus:ring-2 focus:ring-orange-200 transition-all outline-none"
                style={{ borderColor: colors.border }}
                data-testid="webhook-secret-input"
              />
            </div>
            
            {/* Filters Section */}
            <div className="p-4 bg-gray-50 rounded-xl border" style={{ borderColor: colors.border }}>
              <p className="text-sm font-medium mb-3" style={{ color: colors.text }}>
                🎯 Фильтры (опционально)
              </p>
              <p className="text-xs mb-3" style={{ color: colors.textMuted }}>
                Получать события только для определённых активов или проектов
              </p>
              
              <div className="grid grid-cols-2 gap-4">
                {/* Assets Filter */}
                <div>
                  <label className="block text-xs font-medium mb-2" style={{ color: colors.textSecondary }}>
                    Активы (через запятую)
                  </label>
                  <input
                    type="text"
                    value={newWebhook.filters?.assets?.join(', ') || ''}
                    onChange={(e) => {
                      const assets = e.target.value.split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
                      setNewWebhook({ ...newWebhook, filters: { ...newWebhook.filters, assets } });
                    }}
                    placeholder="BTC, ETH, SOL"
                    className="w-full px-3 py-2 rounded-lg border text-sm bg-white"
                    style={{ borderColor: colors.border }}
                    data-testid="webhook-filter-assets"
                  />
                </div>
                
                {/* Projects Filter */}
                <div>
                  <label className="block text-xs font-medium mb-2" style={{ color: colors.textSecondary }}>
                    Проекты (через запятую)
                  </label>
                  <input
                    type="text"
                    value={newWebhook.filters?.projects?.join(', ') || ''}
                    onChange={(e) => {
                      const projects = e.target.value.split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
                      setNewWebhook({ ...newWebhook, filters: { ...newWebhook.filters, projects } });
                    }}
                    placeholder="uniswap, compound"
                    className="w-full px-3 py-2 rounded-lg border text-sm bg-white"
                    style={{ borderColor: colors.border }}
                    data-testid="webhook-filter-projects"
                  />
                </div>
              </div>
            </div>
            
            {/* Event Types */}
            <div>
              <label className="block text-sm font-medium mb-3" style={{ color: colors.textSecondary }}>
                События для подписки <span className="text-red-500">*</span>
              </label>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {webhookEventTypes.map(eventType => (
                  <button
                    key={eventType.type}
                    type="button"
                    onClick={() => toggleWebhookEvent(eventType.type)}
                    className={`p-3 rounded-xl border-2 text-left transition-all ${
                      newWebhook.events.includes(eventType.type) 
                        ? 'border-orange-500 bg-orange-50' 
                        : 'border-gray-200 hover:border-orange-300'
                    }`}
                    data-testid={`webhook-event-${eventType.type}`}
                  >
                    <p className="font-medium text-sm" style={{ color: colors.text }}>{eventType.type}</p>
                    <p className="text-[10px] mt-1" style={{ color: colors.textMuted }}>{eventType.description}</p>
                  </button>
                ))}
              </div>
            </div>
          </div>
          
          {/* Test Result */}
          {testWebhookResult && (
            <div 
              className={`mt-4 p-4 rounded-xl border ${testWebhookResult.ok ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}
            >
              <div className="flex items-center gap-2">
                {testWebhookResult.ok ? (
                  <CheckCircle size={20} className="text-green-600" />
                ) : (
                  <XCircle size={20} className="text-red-600" />
                )}
                <span className={testWebhookResult.ok ? 'text-green-800' : 'text-red-800'}>
                  {testWebhookResult.ok ? `Успешно! Статус: ${testWebhookResult.status_code}` : `Ошибка: ${testWebhookResult.error || 'HTTP ' + testWebhookResult.status_code}`}
                </span>
              </div>
            </div>
          )}
          
          {/* Action Buttons */}
          <div className="flex justify-between gap-3 mt-6 pt-4 border-t" style={{ borderColor: colors.border }}>
            <button
              onClick={() => testWebhook(newWebhook.url)}
              disabled={!newWebhook.url}
              className="px-5 py-2.5 rounded-xl font-medium transition-all"
              style={{ 
                backgroundColor: newWebhook.url ? '#f0f9ff' : '#f3f4f6', 
                color: newWebhook.url ? '#0369a1' : '#9ca3af',
                cursor: newWebhook.url ? 'pointer' : 'not-allowed'
              }}
              data-testid="test-webhook-btn"
            >
              <Play size={16} className="inline mr-2" />
              Тест
            </button>
            <div className="flex gap-3">
              <button
                onClick={() => setShowAddWebhook(false)}
                className="px-5 py-2.5 rounded-xl font-medium transition-all hover:bg-gray-100"
                style={{ backgroundColor: colors.surface, color: colors.textSecondary }}
              >
                Отмена
              </button>
              <button
                onClick={addWebhook}
                disabled={!newWebhook.url || newWebhook.events.length === 0}
                className="px-5 py-2.5 rounded-xl font-medium transition-all"
                style={{ 
                  backgroundColor: (newWebhook.url && newWebhook.events.length > 0) ? '#f97316' : '#d1d5db', 
                  color: 'white',
                  cursor: (newWebhook.url && newWebhook.events.length > 0) ? 'pointer' : 'not-allowed'
                }}
                data-testid="save-webhook-btn"
              >
                Сохранить
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Webhook Modal */}
      {editingWebhook && (
        <div className="bg-white rounded-2xl border p-6 shadow-xl" style={{ borderColor: '#f97316' }}>
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-bold" style={{ color: colors.text }}>Редактировать Webhook</h3>
            <button 
              onClick={cancelEditWebhook}
              className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <X size={20} style={{ color: colors.textMuted }} />
            </button>
          </div>
          
          <div className="space-y-5">
            {/* Name */}
            <div>
              <label className="block text-sm font-medium mb-2" style={{ color: colors.textSecondary }}>Название</label>
              <input
                type="text"
                value={editingWebhook.name || ''}
                onChange={(e) => setEditingWebhook({ ...editingWebhook, name: e.target.value })}
                placeholder="My Integration"
                className="w-full px-4 py-3 rounded-xl border bg-white hover:border-orange-400 focus:border-orange-500 focus:ring-2 focus:ring-orange-200 transition-all outline-none"
                style={{ borderColor: colors.border }}
                data-testid="edit-webhook-name-input"
              />
            </div>
            
            {/* URL */}
            <div>
              <label className="block text-sm font-medium mb-2" style={{ color: colors.textSecondary }}>
                URL <span className="text-red-500">*</span>
              </label>
              <input
                type="url"
                value={editingWebhook.url || ''}
                onChange={(e) => setEditingWebhook({ ...editingWebhook, url: e.target.value })}
                placeholder="https://your-server.com/webhook"
                className="w-full px-4 py-3 rounded-xl border font-mono bg-white hover:border-orange-400 focus:border-orange-500 focus:ring-2 focus:ring-orange-200 transition-all outline-none"
                style={{ borderColor: colors.border }}
                data-testid="edit-webhook-url-input"
              />
            </div>
            
            {/* Secret */}
            <div>
              <label className="block text-sm font-medium mb-2" style={{ color: colors.textSecondary }}>
                Secret Key (оставьте пустым чтобы не менять)
              </label>
              <input
                type="password"
                value={editingWebhook.secret || ''}
                onChange={(e) => setEditingWebhook({ ...editingWebhook, secret: e.target.value })}
                placeholder="••••••••"
                className="w-full px-4 py-3 rounded-xl border font-mono bg-white hover:border-orange-400 focus:border-orange-500 focus:ring-2 focus:ring-orange-200 transition-all outline-none"
                style={{ borderColor: colors.border }}
                data-testid="edit-webhook-secret-input"
              />
            </div>
            
            {/* Enabled Toggle */}
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-3 cursor-pointer">
                <div className="relative">
                  <input
                    type="checkbox"
                    checked={editingWebhook.enabled}
                    onChange={(e) => setEditingWebhook({ ...editingWebhook, enabled: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 rounded-full peer peer-checked:bg-orange-500 transition-colors"></div>
                  <div className="absolute left-1 top-1 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-5 shadow-sm"></div>
                </div>
                <span className="text-sm font-medium" style={{ color: colors.text }}>
                  {editingWebhook.enabled ? 'Включен' : 'Отключен'}
                </span>
              </label>
            </div>
            
            {/* Event Types */}
            <div>
              <label className="block text-sm font-medium mb-3" style={{ color: colors.textSecondary }}>
                События ({editingWebhook.events?.length || 0} выбрано) <span className="text-red-500">*</span>
              </label>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-2 max-h-48 overflow-y-auto">
                {webhookEventTypes.map(eventType => (
                  <button
                    key={eventType.type}
                    type="button"
                    onClick={() => toggleEditWebhookEvent(eventType.type)}
                    className={`p-2 rounded-lg border-2 text-left transition-all ${
                      editingWebhook.events?.includes(eventType.type) 
                        ? 'border-orange-500 bg-orange-50' 
                        : 'border-gray-200 hover:border-orange-300'
                    }`}
                    data-testid={`edit-webhook-event-${eventType.type}`}
                  >
                    <p className="font-medium text-xs" style={{ color: colors.text }}>{eventType.type}</p>
                  </button>
                ))}
              </div>
            </div>
          </div>
          
          {/* Test Result */}
          {testWebhookResult && (
            <div 
              className={`mt-4 p-4 rounded-xl border ${testWebhookResult.ok ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}
            >
              <div className="flex items-center gap-2">
                {testWebhookResult.ok ? (
                  <CheckCircle size={20} className="text-green-600" />
                ) : (
                  <XCircle size={20} className="text-red-600" />
                )}
                <span className={testWebhookResult.ok ? 'text-green-800' : 'text-red-800'}>
                  {testWebhookResult.ok ? `Успешно! Статус: ${testWebhookResult.status_code}` : `Ошибка: ${testWebhookResult.error || 'HTTP ' + testWebhookResult.status_code}`}
                </span>
              </div>
            </div>
          )}
          
          {/* Action Buttons */}
          <div className="flex justify-between gap-3 mt-6 pt-4 border-t" style={{ borderColor: colors.border }}>
            <button
              onClick={() => testWebhook(editingWebhook.url)}
              disabled={!editingWebhook.url}
              className="px-5 py-2.5 rounded-xl font-medium transition-all"
              style={{ 
                backgroundColor: editingWebhook.url ? '#f0f9ff' : '#f3f4f6', 
                color: editingWebhook.url ? '#0369a1' : '#9ca3af',
                cursor: editingWebhook.url ? 'pointer' : 'not-allowed'
              }}
              data-testid="test-edit-webhook-btn"
            >
              <Play size={16} className="inline mr-2" />
              Тест
            </button>
            <div className="flex gap-3">
              <button
                onClick={cancelEditWebhook}
                className="px-5 py-2.5 rounded-xl font-medium transition-all hover:bg-gray-100"
                style={{ backgroundColor: colors.surface, color: colors.textSecondary }}
              >
                Отмена
              </button>
              <button
                onClick={updateWebhook}
                disabled={!editingWebhook.url || editingWebhook.events?.length === 0}
                className="px-5 py-2.5 rounded-xl font-medium transition-all"
                style={{ 
                  backgroundColor: (editingWebhook.url && editingWebhook.events?.length > 0) ? '#f97316' : '#d1d5db', 
                  color: 'white',
                  cursor: (editingWebhook.url && editingWebhook.events?.length > 0) ? 'pointer' : 'not-allowed'
                }}
                data-testid="update-webhook-btn"
              >
                Сохранить изменения
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Existing Webhooks */}
      <div className="space-y-4">
        <h3 className="font-semibold" style={{ color: colors.text }}>
          Подписки ({webhooks.length})
        </h3>
        
        {webhooks.length === 0 ? (
          <div className="text-center py-12 bg-gray-50 rounded-2xl border" style={{ borderColor: colors.border }}>
            <Wifi size={48} className="mx-auto mb-4" style={{ color: colors.textMuted }} />
            <p className="text-lg font-medium" style={{ color: colors.text }}>Нет активных webhooks</p>
            <p className="text-sm" style={{ color: colors.textSecondary }}>
              Добавьте webhook для получения уведомлений о событиях
            </p>
          </div>
        ) : (
          <div className="grid gap-4">
            {webhooks.map(webhook => (
              <div 
                key={webhook.id}
                className={`bg-white rounded-xl border p-4 hover:shadow-md transition-all ${!webhook.enabled ? 'opacity-60' : ''}`}
                style={{ borderColor: editingWebhook?.id === webhook.id ? '#f97316' : colors.border }}
                data-testid={`webhook-item-${webhook.id}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-semibold" style={{ color: colors.text }}>
                        {webhook.name || webhook.id}
                      </span>
                      <button
                        onClick={() => toggleWebhookEnabled(webhook.id, !webhook.enabled)}
                        className={`px-2 py-0.5 rounded-full text-xs font-medium cursor-pointer transition-colors ${
                          webhook.enabled 
                            ? 'bg-green-100 text-green-800 hover:bg-green-200' 
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                        }`}
                        title={webhook.enabled ? 'Нажмите чтобы отключить' : 'Нажмите чтобы включить'}
                      >
                        {webhook.enabled ? 'Active' : 'Disabled'}
                      </button>
                    </div>
                    <p className="text-sm font-mono mb-2" style={{ color: colors.textSecondary }}>
                      {webhook.url}
                    </p>
                    <div className="flex flex-wrap gap-1 mb-2">
                      {webhook.events?.slice(0, 5).map(event => (
                        <span 
                          key={event}
                          className="px-2 py-0.5 rounded-lg text-xs bg-orange-100 text-orange-800"
                        >
                          {event}
                        </span>
                      ))}
                      {webhook.events?.length > 5 && (
                        <span className="px-2 py-0.5 rounded-lg text-xs bg-gray-100 text-gray-600">
                          +{webhook.events.length - 5} ещё
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-4 text-xs" style={{ color: colors.textMuted }}>
                      <span>✓ {webhook.success_count || 0} успешных</span>
                      <span>✕ {webhook.error_count || 0} ошибок</span>
                      {webhook.last_triggered && (
                        <span>Последний: {new Date(webhook.last_triggered).toLocaleString('ru-RU')}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => startEditWebhook(webhook)}
                      className="p-2 rounded-lg hover:bg-blue-50 text-gray-400 hover:text-blue-500 transition-colors"
                      title="Редактировать"
                      data-testid={`edit-webhook-${webhook.id}`}
                    >
                      <Settings size={18} />
                    </button>
                    <button
                      onClick={() => deleteWebhook(webhook.id)}
                      className="p-2 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors"
                      title="Удалить"
                      data-testid={`delete-webhook-${webhook.id}`}
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Analytics Dashboard */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold flex items-center gap-2" style={{ color: colors.text }}>
            <BarChart3 size={18} style={{ color: '#8b5cf6' }} />
            Аналитика
          </h3>
          <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
            {['24h', '7d', '30d'].map(period => (
              <button
                key={period}
                onClick={() => fetchWebhookAnalytics(period)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                  analyticsPeriod === period 
                    ? 'bg-white shadow-sm text-violet-700' 
                    : 'text-gray-500 hover:text-gray-700'
                }`}
                data-testid={`analytics-period-${period}`}
              >
                {period}
              </button>
            ))}
          </div>
        </div>
        
        {webhookAnalytics ? (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <div className="bg-gradient-to-br from-violet-50 to-white rounded-xl p-4 border border-violet-200">
                <p className="text-xs font-medium text-violet-600 mb-1">Всего событий</p>
                <p className="text-2xl font-bold text-violet-800">{webhookAnalytics.summary?.total_events || 0}</p>
              </div>
              <div className="bg-gradient-to-br from-green-50 to-white rounded-xl p-4 border border-green-200">
                <p className="text-xs font-medium text-green-600 mb-1">Доставлено</p>
                <p className="text-2xl font-bold text-green-800">{webhookAnalytics.summary?.total_sent || 0}</p>
              </div>
              <div className="bg-gradient-to-br from-red-50 to-white rounded-xl p-4 border border-red-200">
                <p className="text-xs font-medium text-red-600 mb-1">Ошибки</p>
                <p className="text-2xl font-bold text-red-800">{webhookAnalytics.summary?.total_failed || 0}</p>
              </div>
              <div className="bg-gradient-to-br from-blue-50 to-white rounded-xl p-4 border border-blue-200">
                <p className="text-xs font-medium text-blue-600 mb-1">Success Rate</p>
                <p className="text-2xl font-bold text-blue-800">{webhookAnalytics.summary?.success_rate || 100}%</p>
              </div>
              <div className="bg-gradient-to-br from-orange-50 to-white rounded-xl p-4 border border-orange-200">
                <p className="text-xs font-medium text-orange-600 mb-1">Среднее/час</p>
                <p className="text-2xl font-bold text-orange-800">{webhookAnalytics.summary?.avg_events_per_hour || 0}</p>
              </div>
            </div>
            
            {/* Timeline Chart */}
            {webhookAnalytics.timeline && webhookAnalytics.timeline.length > 0 && (
              <div className="bg-white rounded-xl border p-4" style={{ borderColor: colors.border }}>
                <p className="text-sm font-medium mb-3" style={{ color: colors.text }}>
                  Активность за {analyticsPeriod === '24h' ? '24 часа' : analyticsPeriod === '7d' ? '7 дней' : '30 дней'}
                </p>
                <div className="h-32 flex items-end gap-1">
                  {webhookAnalytics.timeline.map((point, idx) => {
                    const maxEvents = Math.max(...webhookAnalytics.timeline.map(p => p.events || 0), 1);
                    const height = ((point.events || 0) / maxEvents) * 100;
                    return (
                      <div 
                        key={idx}
                        className="flex-1 flex flex-col items-center group relative"
                      >
                        <div 
                          className="w-full rounded-t transition-all hover:opacity-80"
                          style={{ 
                            height: `${Math.max(height, 2)}%`,
                            backgroundColor: point.failed > 0 ? '#fca5a5' : '#a78bfa',
                            minHeight: '4px'
                          }}
                        />
                        {idx % Math.ceil(webhookAnalytics.timeline.length / 8) === 0 && (
                          <span className="text-[9px] mt-1" style={{ color: colors.textMuted }}>
                            {point.label}
                          </span>
                        )}
                        {/* Tooltip */}
                        <div className="absolute bottom-full mb-2 hidden group-hover:block z-10">
                          <div className="bg-gray-900 text-white text-xs rounded px-2 py-1 whitespace-nowrap">
                            {point.events} событий, {point.sent} отправлено
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
            
            {/* Events by Type & Top Subscriptions */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Events by Type */}
              <div className="bg-white rounded-xl border p-4" style={{ borderColor: colors.border }}>
                <p className="text-sm font-medium mb-3" style={{ color: colors.text }}>
                  По типам событий
                </p>
                {webhookAnalytics.events_by_type?.length > 0 ? (
                  <div className="space-y-2">
                    {webhookAnalytics.events_by_type.slice(0, 6).map((item, idx) => {
                      const maxCount = Math.max(...webhookAnalytics.events_by_type.map(e => e.count), 1);
                      const width = (item.count / maxCount) * 100;
                      return (
                        <div key={idx} className="flex items-center gap-2">
                          <span className="text-xs w-28 truncate font-mono" style={{ color: colors.textSecondary }}>
                            {item.event_type}
                          </span>
                          <div className="flex-1 h-5 bg-gray-100 rounded-full overflow-hidden">
                            <div 
                              className="h-full rounded-full bg-gradient-to-r from-violet-400 to-violet-600"
                              style={{ width: `${width}%` }}
                            />
                          </div>
                          <span className="text-xs font-medium w-8 text-right" style={{ color: colors.text }}>
                            {item.count}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-sm text-center py-4" style={{ color: colors.textMuted }}>
                    Нет данных за период
                  </p>
                )}
              </div>
              
              {/* Top Subscriptions */}
              <div className="bg-white rounded-xl border p-4" style={{ borderColor: colors.border }}>
                <p className="text-sm font-medium mb-3" style={{ color: colors.text }}>
                  Активные подписки
                </p>
                {webhookAnalytics.top_subscriptions?.length > 0 ? (
                  <div className="space-y-2">
                    {webhookAnalytics.top_subscriptions.map((sub, idx) => (
                      <div key={idx} className="flex items-center justify-between p-2 rounded-lg hover:bg-gray-50">
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium truncate" style={{ color: colors.text }}>
                            {sub.name}
                          </p>
                          <p className="text-[10px] truncate font-mono" style={{ color: colors.textMuted }}>
                            {sub.url}
                          </p>
                        </div>
                        <div className="flex items-center gap-2 ml-2">
                          <span className="text-xs text-green-600">✓{sub.success_count}</span>
                          <span className="text-xs text-red-600">✕{sub.error_count}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-center py-4" style={{ color: colors.textMuted }}>
                    Нет активных подписок
                  </p>
                )}
              </div>
            </div>
            
            {/* Retry Stats & Recent Errors */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Retry Stats */}
              <div className="bg-white rounded-xl border p-4" style={{ borderColor: colors.border }}>
                <p className="text-sm font-medium mb-3" style={{ color: colors.text }}>
                  Статистика retry
                </p>
                <div className="grid grid-cols-3 gap-2">
                  <div className="text-center p-2 rounded-lg bg-yellow-50">
                    <p className="text-lg font-bold text-yellow-700">{webhookAnalytics.retry_stats?.pending || 0}</p>
                    <p className="text-[10px] text-yellow-600">Ожидают</p>
                  </div>
                  <div className="text-center p-2 rounded-lg bg-green-50">
                    <p className="text-lg font-bold text-green-700">{webhookAnalytics.retry_stats?.success || 0}</p>
                    <p className="text-[10px] text-green-600">Успешно</p>
                  </div>
                  <div className="text-center p-2 rounded-lg bg-red-50">
                    <p className="text-lg font-bold text-red-700">{webhookAnalytics.retry_stats?.failed || 0}</p>
                    <p className="text-[10px] text-red-600">Неудачно</p>
                  </div>
                </div>
                {webhookAnalytics.retry_stats?.total > 0 && (
                  <div className="mt-3 text-center">
                    <span className="text-sm font-medium" style={{ color: colors.text }}>
                      Retry Success Rate: {webhookAnalytics.retry_stats?.retry_success_rate || 0}%
                    </span>
                  </div>
                )}
              </div>
              
              {/* Recent Errors */}
              <div className="bg-white rounded-xl border p-4" style={{ borderColor: colors.border }}>
                <p className="text-sm font-medium mb-3" style={{ color: colors.text }}>
                  Последние ошибки
                </p>
                {webhookAnalytics.recent_errors?.length > 0 ? (
                  <div className="space-y-2 max-h-32 overflow-y-auto">
                    {webhookAnalytics.recent_errors.map((err, idx) => (
                      <div key={idx} className="p-2 rounded-lg bg-red-50 border border-red-100">
                        <div className="flex items-center gap-2">
                          <span className="px-1.5 py-0.5 rounded text-[10px] bg-red-200 text-red-800">
                            {err.event_type}
                          </span>
                          <span className="text-[10px] text-red-600">
                            {err.attempts} попыток
                          </span>
                        </div>
                        <p className="text-[10px] text-red-700 mt-1 truncate" title={err.error}>
                          {err.error}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-center py-4 text-green-600">
                    ✓ Нет ошибок за период
                  </p>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="text-center py-8 bg-gray-50 rounded-xl border" style={{ borderColor: colors.border }}>
            <BarChart3 size={32} className="mx-auto mb-2" style={{ color: colors.textMuted }} />
            <p className="text-sm" style={{ color: colors.textSecondary }}>
              Загрузка аналитики...
            </p>
          </div>
        )}
      </div>

      {/* Retry Status Section */}
      {(webhookRetryStats.pending > 0 || webhookRetryStats.failed > 0 || pendingRetries.length > 0 || failedDeliveries.length > 0) && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold flex items-center gap-2" style={{ color: colors.text }}>
              <RotateCcw size={18} style={{ color: '#f97316' }} />
              Retry Queue
            </h3>
            <button
              onClick={processRetries}
              disabled={webhooksLoading || webhookRetryStats.pending === 0}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all"
              style={{ 
                backgroundColor: webhookRetryStats.pending > 0 ? '#f97316' : colors.surface, 
                color: webhookRetryStats.pending > 0 ? 'white' : colors.textMuted,
                cursor: webhookRetryStats.pending > 0 ? 'pointer' : 'not-allowed'
              }}
              data-testid="process-retries-btn"
            >
              <Play size={14} />
              Обработать сейчас
            </button>
          </div>
          
          {/* Retry Stats Cards */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-yellow-50 rounded-xl p-4 border border-yellow-200">
              <p className="text-xs font-medium text-yellow-700 mb-1">Ожидают</p>
              <p className="text-2xl font-bold text-yellow-800">{webhookRetryStats.pending || 0}</p>
            </div>
            <div className="bg-green-50 rounded-xl p-4 border border-green-200">
              <p className="text-xs font-medium text-green-700 mb-1">Успешно доставлено</p>
              <p className="text-2xl font-bold text-green-800">{webhookRetryStats.success || 0}</p>
            </div>
            <div className="bg-red-50 rounded-xl p-4 border border-red-200">
              <p className="text-xs font-medium text-red-700 mb-1">Неудачные</p>
              <p className="text-2xl font-bold text-red-800">{webhookRetryStats.failed || 0}</p>
            </div>
          </div>
          
          {/* Pending Retries List */}
          {pendingRetries.length > 0 && (
            <div className="bg-yellow-50 rounded-xl border border-yellow-200 overflow-hidden">
              <div className="px-4 py-2 bg-yellow-100 border-b border-yellow-200">
                <span className="text-sm font-medium text-yellow-800">
                  Ожидающие повторной отправки ({pendingRetries.length})
                </span>
              </div>
              <div className="divide-y divide-yellow-200">
                {pendingRetries.map(retry => (
                  <div key={retry.id} className="p-3 hover:bg-yellow-100 transition-colors">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-xs font-mono text-yellow-800">{retry.subscription_url}</span>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="px-2 py-0.5 rounded text-xs bg-yellow-200 text-yellow-800">
                            {retry.event_type}
                          </span>
                          <span className="text-xs text-yellow-700">
                            Попытка {retry.attempt}/{retry.max_attempts}
                          </span>
                          <span className="text-xs text-yellow-600">
                            След. попытка: {new Date(retry.next_retry_at).toLocaleString('ru-RU')}
                          </span>
                        </div>
                      </div>
                    </div>
                    {retry.last_error && (
                      <p className="text-xs text-red-600 mt-1">Ошибка: {retry.last_error}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* Failed Deliveries List */}
          {failedDeliveries.length > 0 && (
            <div className="bg-red-50 rounded-xl border border-red-200 overflow-hidden">
              <div className="px-4 py-2 bg-red-100 border-b border-red-200">
                <span className="text-sm font-medium text-red-800">
                  Неудачные доставки ({failedDeliveries.length})
                </span>
              </div>
              <div className="divide-y divide-red-200">
                {failedDeliveries.map(retry => (
                  <div key={retry.id} className="p-3 hover:bg-red-100 transition-colors">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <span className="text-xs font-mono text-red-800">{retry.subscription_url}</span>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="px-2 py-0.5 rounded text-xs bg-red-200 text-red-800">
                            {retry.event_type}
                          </span>
                          <span className="text-xs text-red-700">
                            {retry.attempt} попыток исчерпано
                          </span>
                        </div>
                        {retry.last_error && (
                          <p className="text-xs text-red-600 mt-1">Ошибка: {retry.last_error}</p>
                        )}
                      </div>
                      <button
                        onClick={() => retryFailedDelivery(retry.id)}
                        className="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-200 text-red-800 hover:bg-red-300 transition-colors"
                        data-testid={`retry-failed-${retry.id}`}
                      >
                        Повторить
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Delivery Logs Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold flex items-center gap-2" style={{ color: colors.text }}>
            <FileText size={18} style={{ color: '#0ea5e9' }} />
            Логи доставки
          </h3>
          <button
            onClick={() => { setShowDeliveryLogs(!showDeliveryLogs); if (!showDeliveryLogs) fetchDeliveryLogs(deliveryLogFilter); }}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all"
            style={{ 
              backgroundColor: showDeliveryLogs ? '#0ea5e9' : colors.surface, 
              color: showDeliveryLogs ? 'white' : colors.textSecondary 
            }}
            data-testid="toggle-delivery-logs-btn"
          >
            {showDeliveryLogs ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            {showDeliveryLogs ? 'Скрыть' : 'Показать'}
          </button>
        </div>
        
        {showDeliveryLogs && (
          <div className="space-y-3">
            {/* Stats Bar */}
            <div className="flex items-center gap-4 p-3 bg-gradient-to-r from-sky-50 to-white rounded-xl border border-sky-200">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium" style={{ color: colors.text }}>Всего: {deliveryStats.total}</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-green-500"></span>
                <span className="text-sm text-green-700">{deliveryStats.success} успешных</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-red-500"></span>
                <span className="text-sm text-red-700">{deliveryStats.failed} ошибок</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="text-sm" style={{ color: colors.textSecondary }}>
                  Avg: {deliveryStats.avg_response_time_ms || 0}ms
                </span>
              </div>
              <div className="ml-auto">
                <span className="px-2 py-1 rounded-lg text-sm font-medium bg-sky-100 text-sky-800">
                  {deliveryStats.success_rate}% success
                </span>
              </div>
            </div>
            
            {/* Filters */}
            <div className="flex items-center gap-3">
              <select
                value={deliveryLogFilter.subscription_id}
                onChange={(e) => { 
                  const newFilter = { ...deliveryLogFilter, subscription_id: e.target.value };
                  setDeliveryLogFilter(newFilter);
                  fetchDeliveryLogs(newFilter);
                }}
                className="px-3 py-2 rounded-lg border text-sm bg-white"
                style={{ borderColor: colors.border }}
              >
                <option value="">Все подписки</option>
                {webhooks.map(wh => (
                  <option key={wh.id} value={wh.id}>{wh.name || wh.id}</option>
                ))}
              </select>
              <select
                value={deliveryLogFilter.status}
                onChange={(e) => {
                  const newFilter = { ...deliveryLogFilter, status: e.target.value };
                  setDeliveryLogFilter(newFilter);
                  fetchDeliveryLogs(newFilter);
                }}
                className="px-3 py-2 rounded-lg border text-sm bg-white"
                style={{ borderColor: colors.border }}
              >
                <option value="">Все статусы</option>
                <option value="success">Успешные</option>
                <option value="failed">Ошибки</option>
              </select>
              <button
                onClick={() => fetchDeliveryLogs(deliveryLogFilter)}
                className="px-3 py-2 rounded-lg bg-sky-100 text-sky-700 hover:bg-sky-200 transition-colors"
              >
                <RefreshCw size={16} />
              </button>
            </div>
            
            {/* Logs Table */}
            {deliveryLogs.length > 0 ? (
              <div className="bg-white rounded-xl border overflow-hidden" style={{ borderColor: colors.border }}>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gray-50 border-b" style={{ borderColor: colors.border }}>
                      <tr>
                        <th className="px-4 py-2 text-left text-xs font-medium" style={{ color: colors.textSecondary }}>Время</th>
                        <th className="px-4 py-2 text-left text-xs font-medium" style={{ color: colors.textSecondary }}>Событие</th>
                        <th className="px-4 py-2 text-left text-xs font-medium" style={{ color: colors.textSecondary }}>Подписка</th>
                        <th className="px-4 py-2 text-left text-xs font-medium" style={{ color: colors.textSecondary }}>Статус</th>
                        <th className="px-4 py-2 text-left text-xs font-medium" style={{ color: colors.textSecondary }}>Время ответа</th>
                        <th className="px-4 py-2 text-left text-xs font-medium" style={{ color: colors.textSecondary }}>Детали</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y" style={{ borderColor: colors.borderLight }}>
                      {deliveryLogs.map((log, idx) => (
                        <tr key={idx} className="hover:bg-gray-50">
                          <td className="px-4 py-2 text-xs" style={{ color: colors.textMuted }}>
                            {new Date(log.created_at).toLocaleString('ru-RU')}
                          </td>
                          <td className="px-4 py-2">
                            <span className="px-2 py-0.5 rounded text-xs bg-blue-100 text-blue-800">
                              {log.event_type}
                            </span>
                          </td>
                          <td className="px-4 py-2 text-xs truncate max-w-[150px]" style={{ color: colors.text }}>
                            {log.subscription_name}
                          </td>
                          <td className="px-4 py-2">
                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                              log.status === 'success' 
                                ? 'bg-green-100 text-green-800' 
                                : 'bg-red-100 text-red-800'
                            }`}>
                              {log.status === 'success' ? '✓' : '✕'} {log.status_code || log.status}
                            </span>
                          </td>
                          <td className="px-4 py-2 text-xs" style={{ color: colors.textSecondary }}>
                            {log.response_time_ms ? `${log.response_time_ms}ms` : '-'}
                          </td>
                          <td className="px-4 py-2 text-xs truncate max-w-[200px]" style={{ color: log.error ? '#dc2626' : colors.textMuted }}>
                            {log.error || 'OK'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div className="text-center py-8 bg-gray-50 rounded-xl border" style={{ borderColor: colors.border }}>
                <FileText size={32} className="mx-auto mb-2" style={{ color: colors.textMuted }} />
                <p className="text-sm" style={{ color: colors.textSecondary }}>
                  Нет логов доставки
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Recent Events */}
      <div className="space-y-4">
        <h3 className="font-semibold" style={{ color: colors.text }}>
          История событий ({webhookEvents.length})
        </h3>
        
        {webhookEvents.length === 0 ? (
          <div className="text-center py-8 bg-gray-50 rounded-xl border" style={{ borderColor: colors.border }}>
            <p className="text-sm" style={{ color: colors.textSecondary }}>
              Нет отправленных событий
            </p>
          </div>
        ) : (
          <div className="bg-white rounded-xl border overflow-hidden" style={{ borderColor: colors.border }}>
            <div className="max-h-80 overflow-y-auto">
              {webhookEvents.map((event, idx) => (
                <div 
                  key={idx}
                  className="p-3 border-b last:border-b-0 hover:bg-gray-50 transition-colors"
                  style={{ borderColor: colors.borderLight }}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                        {event.event_type}
                      </span>
                      <span className="text-xs" style={{ color: colors.textMuted }}>
                        {new Date(event.created_at).toLocaleString('ru-RU')}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-green-600">✓ {event.results?.sent || 0}</span>
                      <span className="text-red-600">✕ {event.results?.failed || 0}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Event Types Reference */}
      <div className="space-y-4">
        <h3 className="font-semibold" style={{ color: colors.text }}>
          Доступные типы событий
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {webhookEventTypes.map(eventType => (
            <div 
              key={eventType.type}
              className="bg-gradient-to-br from-gray-50 to-white rounded-xl border p-4"
              style={{ borderColor: colors.border }}
            >
              <p className="font-medium text-sm mb-1" style={{ color: colors.text }}>
                {eventType.type}
              </p>
              <p className="text-xs" style={{ color: colors.textMuted }}>
                {eventType.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  // Provider Pool Section - Shows API + Proxy bindings
  const renderProviderPool = () => (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold" style={{ color: colors.text }}>
            Provider Gateway
          </h2>
          <p className="text-sm" style={{ color: colors.textSecondary }}>
            {providerPool.stats?.total_providers || 0} providers • {providerPool.stats?.api_key_providers || 0} require API keys • {providerPool.stats?.public_providers || 0} public
          </p>
        </div>
        <button
          onClick={fetchProviderPool}
          className="flex items-center gap-2 px-4 py-2 rounded-xl transition-all"
          style={{ backgroundColor: colors.surface, color: colors.textSecondary }}
        >
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>

      {/* Category A: API Key Required */}
      <div 
        className="bg-white rounded-2xl border p-6"
        style={{ borderColor: colors.border }}
      >
        <h3 className="font-semibold mb-2 flex items-center gap-2" style={{ color: colors.text }}>
          <Key size={18} />
          Category A: API Key Required
        </h3>
        <p className="text-sm mb-4" style={{ color: colors.textSecondary }}>
          Configure API keys in the API Keys tab to enable these providers
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {providerPool.providers?.filter(p => p.requires_api_key === true).map(provider => (
            <div 
              key={provider.id}
              className="border rounded-xl p-4 hover:shadow-md transition-all"
              style={{ 
                borderColor: provider.status === 'active' ? colors.success : colors.border,
                backgroundColor: 'white'
              }}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center"
                    style={{ backgroundColor: colors.accentSoft }}>
                    <Database size={16} style={{ color: colors.accent }} />
                  </div>
                  <span className="font-semibold" style={{ color: colors.text }}>
                    {provider.name}
                  </span>
                </div>
                <span 
                  className="px-2 py-0.5 rounded-full text-xs font-medium"
                  style={{ 
                    backgroundColor: provider.status === 'active' ? colors.successSoft : colors.warningSoft,
                    color: provider.status === 'active' ? colors.success : colors.warning
                  }}
                >
                  {provider.status}
                </span>
              </div>
              <p className="text-xs mb-3" style={{ color: colors.textSecondary }}>
                {provider.description?.slice(0, 80) || 'Data provider'}
              </p>
              <div className="flex flex-wrap gap-1 mb-3">
                {provider.capabilities?.slice(0, 4).map(cap => (
                  <span key={cap} className="px-2 py-0.5 rounded text-xs"
                    style={{ backgroundColor: colors.surface, color: colors.textSecondary }}>
                    {cap.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
              <div className="text-xs flex items-center justify-between pt-2 border-t"
                style={{ borderColor: colors.border, color: colors.textMuted }}>
                <span>Rate: {provider.rate_limit}/min</span>
                <span className="capitalize">{provider.category?.replace(/_/g, ' ')}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Category B: Public APIs */}
      <div 
        className="bg-white rounded-2xl border p-6"
        style={{ borderColor: colors.border }}
      >
        <h3 className="font-semibold mb-2 flex items-center gap-2" style={{ color: colors.text }}>
          <Globe size={18} />
          Category B: Public APIs (No Key Required)
        </h3>
        <p className="text-sm mb-4" style={{ color: colors.textSecondary }}>
          Free public APIs - only proxy configuration needed for rate limiting
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {providerPool.providers?.filter(p => p.requires_api_key === false && p.type !== 'exchange').map(provider => (
            <div 
              key={provider.id}
              className="border rounded-xl p-4 hover:shadow-md transition-all relative"
              style={{ 
                borderColor: provider.is_new ? colors.warning : (provider.status === 'active' ? colors.success : colors.border)
              }}
            >
              {/* New badge */}
              {provider.is_new && (
                <span 
                  className="absolute -top-2 -right-2 px-2 py-0.5 rounded-full text-[10px] font-bold"
                  style={{ backgroundColor: colors.warning, color: 'white' }}
                >
                  NEW
                </span>
              )}
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium" style={{ color: colors.text }}>
                  {provider.name}
                </span>
                <span 
                  className="px-2 py-0.5 rounded-full text-xs font-medium"
                  style={{ 
                    backgroundColor: colors.successSoft,
                    color: colors.success
                  }}
                >
                  Public
                </span>
              </div>
              <div className="flex flex-wrap gap-1 mb-2">
                {provider.capabilities?.slice(0, 3).map(cap => (
                  <span key={cap} className="px-1.5 py-0.5 rounded text-xs"
                    style={{ backgroundColor: colors.accentSoft, color: colors.accent }}>
                    {cap.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
              <div className="text-xs" style={{ color: colors.textMuted }}>
                {provider.category?.replace(/_/g, ' ')} • {provider.rate_limit}/min
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Exchange Providers */}
      <div 
        className="bg-white rounded-2xl border p-6"
        style={{ borderColor: colors.border }}
      >
        <h3 className="font-semibold mb-4 flex items-center gap-2" style={{ color: colors.text }}>
          <TrendingUp size={18} />
          Exchange Providers
        </h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {providerPool.providers?.filter(p => p.type === 'exchange' || p.category === 'exchange').map(provider => (
            <div 
              key={provider.id || provider.name}
              className="border rounded-xl p-4"
              style={{ 
                borderColor: (provider.status === 'healthy' || provider.health_status === 'healthy') ? colors.success : 
                             (provider.status === 'error' || provider.health_status === 'error') ? colors.error : colors.border
              }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium capitalize" style={{ color: colors.text }}>
                  {provider.name}
                </span>
                <span 
                  className="px-2 py-0.5 rounded-full text-xs font-medium"
                  style={{ 
                    backgroundColor: (provider.health_status === 'healthy' || provider.status === 'healthy') ? colors.successSoft : 
                                     (provider.health_status === 'error' || provider.status === 'error') ? colors.errorSoft : colors.warningSoft,
                    color: (provider.health_status === 'healthy' || provider.status === 'healthy') ? colors.success : 
                           (provider.health_status === 'error' || provider.status === 'error') ? colors.error : colors.warning
                  }}
                >
                  {provider.health_status || provider.status}
                </span>
              </div>
              <div className="text-xs space-y-1" style={{ color: colors.textSecondary }}>
                {provider.latency && <p>Latency: {provider.latency.toFixed(0)}ms</p>}
                {provider.error && <p className="truncate" style={{ color: colors.error }}>Error: {provider.error}</p>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Capabilities Overview */}
      {providerPool.capabilities && Object.keys(providerPool.capabilities).length > 0 && (
        <div 
          className="rounded-2xl p-6"
          style={{ backgroundColor: colors.accentSoft }}
        >
          <h4 className="font-medium mb-4 flex items-center gap-2" style={{ color: colors.accent }}>
            <Layers size={18} />
            Available Capabilities
          </h4>
          <div className="flex flex-wrap gap-2">
            {Object.entries(providerPool.capabilities || {}).map(([cap, count]) => (
              <span key={cap} className="px-3 py-1.5 rounded-full text-sm bg-white flex items-center gap-1"
                style={{ color: colors.text }}>
                {cap.replace(/_/g, ' ')}
                <span className="text-xs px-1.5 py-0.5 rounded-full ml-1"
                  style={{ backgroundColor: colors.accentSoft, color: colors.accent }}>
                  {count}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Architecture Diagram */}
      <div 
        className="rounded-2xl p-6 border"
        style={{ borderColor: colors.border, backgroundColor: 'white' }}
      >
        <h4 className="font-medium mb-4" style={{ color: colors.text }}>
          Provider Gateway Architecture
        </h4>
        <div className="grid grid-cols-5 gap-2 text-center text-sm">
          <div className="rounded-xl p-3" style={{ backgroundColor: colors.surface, color: colors.text }}>
            <p className="font-medium">Client</p>
            <p className="text-xs" style={{ color: colors.textMuted }}>API Request</p>
          </div>
          <div className="flex items-center justify-center">
            <ChevronRight size={20} style={{ color: colors.accent }} />
          </div>
          <div className="rounded-xl p-3" style={{ backgroundColor: colors.accentSoft, color: colors.accent }}>
            <p className="font-medium">Provider Router</p>
            <p className="text-xs">Select best instance</p>
          </div>
          <div className="flex items-center justify-center">
            <ChevronRight size={20} style={{ color: colors.accent }} />
          </div>
          <div className="rounded-xl p-3" style={{ backgroundColor: colors.surface, color: colors.text }}>
            <p className="font-medium">External API</p>
            <p className="text-xs" style={{ color: colors.textMuted }}>+ Proxy + Key</p>
          </div>
        </div>
        <div className="mt-4 text-sm" style={{ color: colors.text }}>
          <p className="mb-2"><strong>Failover strategy:</strong></p>
          <p style={{ color: colors.textSecondary }}>
            Instance 1 (Proxy A + Key 1) → Instance 2 (Proxy B + Key 2) → Direct request
          </p>
        </div>
      </div>
    </div>
  );

  // Health Monitor Section
  const renderHealthMonitor = () => (
    <div className="space-y-6" data-testid="health-monitor">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold" style={{ color: colors.text }}>
            News Sources Health Monitor
          </h2>
          <p className="text-sm" style={{ color: colors.textSecondary }}>
            Parser Sandbox • Validation Layer • Auto-pause • Drift Detection
          </p>
        </div>
        <button
          onClick={fetchSourcesHealth}
          disabled={healthLoading}
          className="flex items-center gap-2 px-4 py-2 rounded-xl transition-all"
          style={{ backgroundColor: colors.surface, color: colors.textSecondary }}
        >
          <RefreshCw size={16} className={healthLoading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-white rounded-xl p-4 border" style={{ borderColor: colors.border }}>
          <p className="text-sm mb-1" style={{ color: colors.textSecondary }}>Total Sources</p>
          <p className="text-2xl font-bold" style={{ color: colors.text }}>
            {sourcesHealth.summary.total_sources || 0}
          </p>
        </div>
        <div className="bg-white rounded-xl p-4 border" style={{ borderColor: colors.success }}>
          <p className="text-sm mb-1" style={{ color: colors.textSecondary }}>Активные</p>
          <p className="text-2xl font-bold" style={{ color: colors.success }}>
            {sourcesHealth.summary.active || 0}
          </p>
        </div>
        <div className="bg-white rounded-xl p-4 border" style={{ borderColor: colors.warning }}>
          <p className="text-sm mb-1" style={{ color: colors.textSecondary }}>Degraded</p>
          <p className="text-2xl font-bold" style={{ color: colors.warning }}>
            {sourcesHealth.summary.degraded || 0}
          </p>
        </div>
        <div className="bg-white rounded-xl p-4 border" style={{ borderColor: colors.error }}>
          <p className="text-sm mb-1" style={{ color: colors.textSecondary }}>Paused</p>
          <p className="text-2xl font-bold" style={{ color: colors.error }}>
            {sourcesHealth.summary.paused || 0}
          </p>
        </div>
        <div className="bg-white rounded-xl p-4 border" style={{ borderColor: colors.accent }}>
          <p className="text-sm mb-1" style={{ color: colors.textSecondary }}>Avg Health</p>
          <p className="text-2xl font-bold" style={{ color: colors.accent }}>
            {((sourcesHealth.summary.avg_health_score || 0) * 100).toFixed(0)}%
          </p>
        </div>
      </div>

      {/* Sources Table */}
      <div className="bg-white rounded-2xl border overflow-hidden" style={{ borderColor: colors.border }}>
        <div className="p-4 border-b" style={{ borderColor: colors.border }}>
          <h3 className="font-semibold flex items-center gap-2" style={{ color: colors.text }}>
            <Server size={18} />
            Source Status
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr style={{ backgroundColor: colors.surface }}>
                <th className="text-left px-4 py-3 text-sm font-medium" style={{ color: colors.textSecondary }}>Source</th>
                <th className="text-center px-4 py-3 text-sm font-medium" style={{ color: colors.textSecondary }}>Status</th>
                <th className="text-center px-4 py-3 text-sm font-medium" style={{ color: colors.textSecondary }}>Health</th>
                <th className="text-center px-4 py-3 text-sm font-medium" style={{ color: colors.textSecondary }}>Success Rate</th>
                <th className="text-center px-4 py-3 text-sm font-medium" style={{ color: colors.textSecondary }}>Valid Rate</th>
                <th className="text-center px-4 py-3 text-sm font-medium" style={{ color: colors.textSecondary }}>Latency</th>
                <th className="text-center px-4 py-3 text-sm font-medium" style={{ color: colors.textSecondary }}>Drift</th>
                <th className="text-center px-4 py-3 text-sm font-medium" style={{ color: colors.textSecondary }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {sourcesHealth.sources?.map((source, idx) => {
                const statusColors = {
                  active: { bg: colors.successSoft, text: colors.success },
                  degraded: { bg: colors.warningSoft, text: colors.warning },
                  paused: { bg: colors.errorSoft, text: colors.error },
                  disabled: { bg: colors.surface, text: colors.textMuted }
                };
                const sc = statusColors[source.status] || statusColors.degraded;
                const healthPct = ((source.health_score || 0) * 100).toFixed(0);
                const successPct = ((source.success_rate || 0) * 100).toFixed(0);
                const validPct = ((source.validation?.valid_rate || source.valid_rate || 0) * 100).toFixed(0);
                
                return (
                  <tr 
                    key={source.source_id} 
                    className="border-b hover:bg-gray-50 transition-colors"
                    style={{ borderColor: colors.borderLight }}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center"
                          style={{ backgroundColor: colors.accentSoft }}>
                          <Rss size={14} style={{ color: colors.accent }} />
                        </div>
                        <div>
                          <p className="font-medium text-sm" style={{ color: colors.text }}>
                            {source.source_name || source.source_id}
                          </p>
                          <p className="text-xs" style={{ color: colors.textMuted }}>
                            {source.source_id}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span 
                        className="px-2 py-1 rounded-full text-xs font-medium capitalize"
                        style={{ backgroundColor: sc.bg, color: sc.text }}
                      >
                        {source.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-2">
                        <div className="w-16 h-2 rounded-full overflow-hidden" style={{ backgroundColor: colors.surface }}>
                          <div 
                            className="h-full rounded-full transition-all"
                            style={{ 
                              width: `${healthPct}%`,
                              backgroundColor: healthPct >= 80 ? colors.success : healthPct >= 50 ? colors.warning : colors.error
                            }}
                          />
                        </div>
                        <span className="text-xs font-medium" style={{ color: colors.text }}>{healthPct}%</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className="text-sm" style={{ color: successPct >= 90 ? colors.success : successPct >= 70 ? colors.warning : colors.error }}>
                        {successPct}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className="text-sm" style={{ color: validPct >= 90 ? colors.success : validPct >= 70 ? colors.warning : colors.error }}>
                        {validPct}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className="text-xs" style={{ color: colors.textSecondary }}>
                        {(source.avg_latency_ms || source.sandbox?.avg_duration_ms || 0).toFixed(0)}ms
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {source.drift_detected ? (
                        <span className="flex items-center justify-center gap-1 text-xs" style={{ color: colors.error }}>
                          <AlertTriangle size={14} /> Drift
                        </span>
                      ) : (
                        <CheckCircle size={14} style={{ color: colors.success }} className="mx-auto" />
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {source.status === 'paused' && (
                        <button
                          onClick={() => handleUnpauseSource(source.source_id)}
                          className="px-2 py-1 rounded text-xs font-medium transition-all hover:opacity-80"
                          style={{ backgroundColor: colors.accentSoft, color: colors.accent }}
                        >
                          <Play size={12} className="inline mr-1" />
                          Unpause
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Architecture Info */}
      <div className="bg-white rounded-2xl border p-6" style={{ borderColor: colors.border }}>
        <h3 className="font-semibold mb-4 flex items-center gap-2" style={{ color: colors.text }}>
          <Shield size={18} />
          Parser Sandbox Architecture
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl" style={{ backgroundColor: colors.accentSoft }}>
            <div className="flex items-center gap-2 mb-2">
              <Box size={16} style={{ color: colors.accent }} />
              <span className="font-medium text-sm" style={{ color: colors.accent }}>Sandbox Isolation</span>
            </div>
            <p className="text-xs" style={{ color: colors.textSecondary }}>
              Each parser runs isolated with 10s timeout, 3 retries, 2MB max response
            </p>
          </div>
          <div className="p-4 rounded-xl" style={{ backgroundColor: colors.successSoft }}>
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle size={16} style={{ color: colors.success }} />
              <span className="font-medium text-sm" style={{ color: colors.success }}>Validation Layer</span>
            </div>
            <p className="text-xs" style={{ color: colors.textSecondary }}>
              Title, content, date validation with spam detection and confidence scoring
            </p>
          </div>
          <div className="p-4 rounded-xl" style={{ backgroundColor: colors.warningSoft }}>
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle size={16} style={{ color: colors.warning }} />
              <span className="font-medium text-sm" style={{ color: colors.warning }}>Auto-Pause</span>
            </div>
            <p className="text-xs" style={{ color: colors.textSecondary }}>
              Sources with 5+ consecutive errors or health &lt;40% auto-paused for 30min
            </p>
          </div>
          <div className="p-4 rounded-xl" style={{ backgroundColor: colors.errorSoft }}>
            <div className="flex items-center gap-2 mb-2">
              <Activity size={16} style={{ color: colors.error }} />
              <span className="font-medium text-sm" style={{ color: colors.error }}>Drift Detection</span>
            </div>
            <p className="text-xs" style={{ color: colors.textSecondary }}>
              Detects parser drift when validation rate drops below 50% or confidence &lt;60%
            </p>
          </div>
        </div>
      </div>

      {/* Knowledge Graph Health */}
      <div className="bg-white rounded-2xl border p-6" style={{ borderColor: colors.border }}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold flex items-center gap-2" style={{ color: colors.text }}>
            <Network size={18} style={{ color: colors.accent }} />
            Knowledge Graph Health
          </h3>
          <button
            onClick={fetchGraphHealth}
            disabled={graphHealthLoading}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-all"
            style={{ backgroundColor: colors.surface, color: colors.textSecondary }}
          >
            <RefreshCw size={14} className={graphHealthLoading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
        
        {graphHealth ? (
          <>
            {/* Status Badge */}
            <div className="flex items-center gap-3 mb-6">
              <span 
                className="px-3 py-1.5 rounded-full text-sm font-medium"
                style={{ 
                  backgroundColor: graphHealth.status === 'healthy' ? colors.successSoft : 
                                   graphHealth.status === 'warning' ? colors.warningSoft : colors.errorSoft,
                  color: graphHealth.status === 'healthy' ? colors.success : 
                         graphHealth.status === 'warning' ? colors.warning : colors.error
                }}
              >
                {graphHealth.status === 'healthy' ? '✓ Healthy' : 
                 graphHealth.status === 'warning' ? '⚠ Warning' : '✕ Error'}
              </span>
              {graphHealth.duplicate_check?.potential_duplicates > 0 && (
                <span className="text-sm px-3 py-1.5 rounded-full" style={{ backgroundColor: colors.warningSoft, color: colors.warning }}>
                  {graphHealth.duplicate_check.potential_duplicates} potential duplicates
                </span>
              )}
            </div>
            
            {/* Graph Metrics */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
              <div className="p-4 rounded-xl" style={{ backgroundColor: colors.surface }}>
                <p className="text-xs mb-1" style={{ color: colors.textSecondary }}>Узлы</p>
                <p className="text-2xl font-bold" style={{ color: colors.accent }}>
                  {graphHealth.metrics?.nodes_count?.toLocaleString() || 0}
                </p>
              </div>
              <div className="p-4 rounded-xl" style={{ backgroundColor: colors.surface }}>
                <p className="text-xs mb-1" style={{ color: colors.textSecondary }}>Рёбра</p>
                <p className="text-2xl font-bold" style={{ color: colors.success }}>
                  {graphHealth.metrics?.edges_count?.toLocaleString() || 0}
                </p>
              </div>
              <div className="p-4 rounded-xl" style={{ backgroundColor: colors.surface }}>
                <p className="text-xs mb-1" style={{ color: colors.textSecondary }}>Aliases</p>
                <p className="text-2xl font-bold" style={{ color: '#8B5CF6' }}>
                  {graphHealth.metrics?.aliases_total || 0}
                </p>
              </div>
              <div className="p-4 rounded-xl" style={{ backgroundColor: colors.surface }}>
                <p className="text-xs mb-1" style={{ color: colors.textSecondary }}>Candidates</p>
                <p className="text-2xl font-bold" style={{ color: colors.warning }}>
                  {graphHealth.metrics?.alias_candidates || 0}
                </p>
              </div>
              <div className="p-4 rounded-xl" style={{ backgroundColor: colors.surface }}>
                <p className="text-xs mb-1" style={{ color: colors.textSecondary }}>Avg Degree</p>
                <p className="text-2xl font-bold" style={{ color: colors.text }}>
                  {graphHealth.metrics?.avg_degree?.toFixed(2) || 0}
                </p>
              </div>
            </div>
            
            {/* Node & Edge Distribution */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Node Types */}
              <div>
                <h4 className="text-sm font-medium mb-3" style={{ color: colors.textSecondary }}>Node Distribution</h4>
                <div className="space-y-2">
                  {Object.entries(graphHealth.distribution?.node_types || {}).map(([type, count]) => {
                    const maxCount = Math.max(...Object.values(graphHealth.distribution?.node_types || {}));
                    const percentage = maxCount > 0 ? (count / maxCount) * 100 : 0;
                    const typeColors = {
                      project: '#3B82F6',
                      token: '#8B5CF6',
                      person: '#F59E0B',
                      asset: '#10B981',
                      fund: '#06B6D4',
                      exchange: '#EF4444'
                    };
                    return (
                      <div key={type} className="flex items-center gap-3">
                        <span className="text-xs w-20 capitalize" style={{ color: colors.textSecondary }}>{type}</span>
                        <div className="flex-1 h-6 rounded-lg overflow-hidden" style={{ backgroundColor: colors.surface }}>
                          <div 
                            className="h-full rounded-lg transition-all duration-500"
                            style={{ 
                              width: `${percentage}%`, 
                              backgroundColor: typeColors[type] || colors.accent,
                              minWidth: count > 0 ? '20px' : '0'
                            }}
                          />
                        </div>
                        <span className="text-sm font-medium w-12 text-right" style={{ color: colors.text }}>{count}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
              
              {/* Edge Types */}
              <div>
                <h4 className="text-sm font-medium mb-3" style={{ color: colors.textSecondary }}>Edge Distribution</h4>
                <div className="space-y-2">
                  {Object.entries(graphHealth.distribution?.edge_types || {}).map(([type, count]) => {
                    const maxCount = Math.max(...Object.values(graphHealth.distribution?.edge_types || {}));
                    const percentage = maxCount > 0 ? (count / maxCount) * 100 : 0;
                    const edgeColors = {
                      invested_in: '#10B981',
                      has_token: '#8B5CF6',
                      traded_on: '#EF4444',
                      coinvested_with: '#3B82F6',
                      works_at: '#F59E0B',
                      founded: '#06B6D4',
                      mapped_to_asset: '#64748B'
                    };
                    return (
                      <div key={type} className="flex items-center gap-3">
                        <span className="text-xs w-28" style={{ color: colors.textSecondary }}>{type.replace(/_/g, ' ')}</span>
                        <div className="flex-1 h-6 rounded-lg overflow-hidden" style={{ backgroundColor: colors.surface }}>
                          <div 
                            className="h-full rounded-lg transition-all duration-500"
                            style={{ 
                              width: `${percentage}%`, 
                              backgroundColor: edgeColors[type] || colors.accent,
                              minWidth: count > 0 ? '20px' : '0'
                            }}
                          />
                        </div>
                        <span className="text-sm font-medium w-12 text-right" style={{ color: colors.text }}>{count}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
            
            {/* Duplicate Samples */}
            {graphHealth.duplicate_check?.samples?.length > 0 && (
              <div className="mt-6 p-4 rounded-xl" style={{ backgroundColor: colors.warningSoft }}>
                <h4 className="text-sm font-medium mb-2 flex items-center gap-2" style={{ color: colors.warning }}>
                  <AlertTriangle size={14} />
                  Potential Duplicates
                </h4>
                <div className="flex flex-wrap gap-2">
                  {graphHealth.duplicate_check.samples.slice(0, 5).map((dup, idx) => (
                    <span 
                      key={idx}
                      className="px-2 py-1 rounded text-xs"
                      style={{ backgroundColor: 'rgba(255,255,255,0.5)', color: colors.warning }}
                    >
                      {dup.label} ({dup.count}x)
                    </span>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="text-center py-8" style={{ color: colors.textMuted }}>
            <Network size={32} className="mx-auto mb-2 opacity-50" />
            <p className="text-sm">Click Refresh to load graph health data</p>
          </div>
        )}
      </div>
    </div>
  );

  // ═══════════════════════════════════════════════════════════════
  // NEWS SOURCES PAGE (Dedicated page for news sources management)
  // ═══════════════════════════════════════════════════════════════
  
  const renderNewsSourcesPage = () => {
    const stats = newsSources.stats || {};
    const sources = newsSources.sources || [];
    
    const tierColors = {
      A: { bg: colors.successSoft, text: colors.success, label: 'Primary' },
      B: { bg: colors.accentSoft, text: colors.accent, label: 'Secondary' },
      C: { bg: colors.warningSoft, text: colors.warning, label: 'Research' },
      D: { bg: colors.surface, text: colors.textSecondary, label: 'Aggregators' }
    };
    
    const categoryConfig = {
      news: { icon: <Newspaper size={14} />, color: colors.accent },
      research: { icon: <BookOpen size={14} />, color: '#8B5CF6' },
      official: { icon: <Shield size={14} />, color: colors.success },
      analytics: { icon: <TrendingUp size={14} />, color: '#F97316' },
      security: { icon: <AlertTriangle size={14} />, color: colors.error },
      defi: { icon: <Layers size={14} />, color: '#06B6D4' },
      dex: { icon: <Activity size={14} />, color: '#EC4899' },
      funding: { icon: <DollarSign size={14} />, color: '#10B981' },
      aggregator: { icon: <Database size={14} />, color: colors.textSecondary },
      derivatives: { icon: <BarChart2 size={14} />, color: '#F59E0B' },
      l2: { icon: <Layers size={14} />, color: '#3B82F6' },
      analysis: { icon: <Eye size={14} />, color: '#6366F1' }
    };
    
    const languageFlags = {
      en: '🇬🇧',
      ru: '🇷🇺',
      zh: '🇨🇳',
      jp: '🇯🇵',
      de: '🇩🇪',
      ua: '🇺🇦'
    };
    
    return (
      <div className="space-y-6" data-testid="news-sources-page">
        {/* Stats Subtitle */}
        <p className="text-sm" style={{ color: colors.textSecondary }}>
          {stats.total || 0} sources across {Object.keys(stats.by_language || {}).length} languages and {Object.keys(stats.by_category || {}).length} categories
        </p>

        {/* Search Bar */}
        <div className="bg-white rounded-2xl border p-4" style={{ borderColor: colors.border }}>
          <div className="relative">
            <Search 
              size={20} 
              className="absolute left-4 top-1/2 -translate-y-1/2"
              style={{ color: colors.textMuted }}
            />
            <input
              data-testid="news-sources-search"
              type="text"
              value={newsSourcesSearch}
              onChange={(e) => setNewsSourcesSearch(e.target.value)}
              placeholder="Search sources by name, domain, category... (e.g. incrypted, cointelegraph, defi)"
              className="w-full pl-12 pr-12 py-3 rounded-xl border transition-all focus:outline-none focus:ring-2"
              style={{ 
                borderColor: colors.border,
                backgroundColor: colors.surface,
                color: colors.text
              }}
            />
            {newsSourcesSearch && (
              <button
                onClick={() => setNewsSourcesSearch('')}
                className="absolute right-4 top-1/2 -translate-y-1/2 p-1 rounded-full hover:bg-gray-200 transition-all"
              >
                <X size={16} style={{ color: colors.textMuted }} />
              </button>
            )}
          </div>
          {newsSourcesSearch && (
            <p className="mt-2 text-sm" style={{ color: colors.textSecondary }}>
              Found <span className="font-bold" style={{ color: colors.accent }}>
                {sources.filter(s => 
                  s.name?.toLowerCase().includes(newsSourcesSearch.toLowerCase()) ||
                  s.domain?.toLowerCase().includes(newsSourcesSearch.toLowerCase()) ||
                  s.category?.toLowerCase().includes(newsSourcesSearch.toLowerCase()) ||
                  s.id?.toLowerCase().includes(newsSourcesSearch.toLowerCase())
                ).length}
              </span> matching sources
            </p>
          )}
        </div>

        {/* Stats Overview */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Object.entries(tierColors).map(([tier, config]) => (
            <div 
              key={tier}
              className="p-5 rounded-2xl border transition-all hover:shadow-lg cursor-pointer"
              style={{ 
                backgroundColor: newsSourcesFilter.tier === tier ? config.bg : 'white',
                borderColor: newsSourcesFilter.tier === tier ? config.text : colors.border
              }}
              onClick={() => setNewsSourcesFilter(prev => ({ 
                ...prev, 
                tier: prev.tier === tier ? null : tier 
              }))}
            >
              <div className="flex items-center justify-between mb-2">
                <span 
                  className="w-10 h-10 rounded-xl flex items-center justify-center font-bold text-lg"
                  style={{ backgroundColor: config.bg, color: config.text }}
                >
                  {tier}
                </span>
                <span className="text-3xl font-bold" style={{ color: config.text }}>
                  {stats.by_tier?.[tier] || 0}
                </span>
              </div>
              <p className="text-sm font-medium" style={{ color: colors.text }}>Tier {tier}</p>
              <p className="text-xs" style={{ color: colors.textSecondary }}>{config.label}</p>
            </div>
          ))}
        </div>

        {/* Filters & Stats Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Language Distribution */}
          <div className="bg-white rounded-2xl border p-5" style={{ borderColor: colors.border }}>
            <h3 className="font-semibold mb-4 flex items-center gap-2" style={{ color: colors.text }}>
              <Globe size={18} style={{ color: colors.accent }} />
              By Language
            </h3>
            <div className="space-y-2">
              {Object.entries(stats.by_language || {}).sort((a, b) => b[1] - a[1]).map(([lang, count]) => {
                const maxCount = Math.max(...Object.values(stats.by_language || {}));
                const pct = maxCount > 0 ? (count / maxCount) * 100 : 0;
                const isActive = newsSourcesFilter.language === lang;
                
                return (
                  <div 
                    key={lang} 
                    className="flex items-center gap-3 cursor-pointer p-2 rounded-lg transition-all hover:bg-gray-50"
                    style={{ backgroundColor: isActive ? colors.accentSoft : 'transparent' }}
                    onClick={() => setNewsSourcesFilter(prev => ({ 
                      ...prev, 
                      language: prev.language === lang ? null : lang 
                    }))}
                  >
                    <span className="text-lg">{languageFlags[lang] || '🌐'}</span>
                    <span className="text-sm w-8 uppercase font-medium" style={{ color: colors.text }}>{lang}</span>
                    <div className="flex-1 h-4 rounded-full overflow-hidden" style={{ backgroundColor: colors.surface }}>
                      <div 
                        className="h-full rounded-full transition-all"
                        style={{ width: `${pct}%`, backgroundColor: isActive ? colors.accent : colors.textMuted }}
                      />
                    </div>
                    <span className="text-sm font-medium w-8 text-right" style={{ color: colors.text }}>{count}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Category Distribution */}
          <div className="bg-white rounded-2xl border p-5" style={{ borderColor: colors.border }}>
            <h3 className="font-semibold mb-4 flex items-center gap-2" style={{ color: colors.text }}>
              <Layers size={18} style={{ color: colors.accent }} />
              By Category
            </h3>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {Object.entries(stats.by_category || {}).sort((a, b) => b[1] - a[1]).map(([cat, count]) => {
                const config = categoryConfig[cat] || { icon: <Globe size={14} />, color: colors.textSecondary };
                const isActive = newsSourcesFilter.category === cat;
                
                return (
                  <div 
                    key={cat}
                    className="flex items-center justify-between p-2 rounded-lg cursor-pointer transition-all hover:bg-gray-50"
                    style={{ backgroundColor: isActive ? colors.accentSoft : 'transparent' }}
                    onClick={() => setNewsSourcesFilter(prev => ({ 
                      ...prev, 
                      category: prev.category === cat ? null : cat 
                    }))}
                  >
                    <div className="flex items-center gap-2">
                      <span style={{ color: config.color }}>{config.icon}</span>
                      <span className="text-sm capitalize" style={{ color: colors.text }}>{cat}</span>
                    </div>
                    <span 
                      className="px-2 py-0.5 rounded-full text-xs font-medium"
                      style={{ backgroundColor: `${config.color}20`, color: config.color }}
                    >
                      {count}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Active Filters */}
          <div className="bg-white rounded-2xl border p-5" style={{ borderColor: colors.border }}>
            <h3 className="font-semibold mb-4 flex items-center gap-2" style={{ color: colors.text }}>
              <Target size={18} style={{ color: colors.accent }} />
              Active Filters
            </h3>
            <div className="space-y-3">
              {newsSourcesFilter.tier && (
                <div className="flex items-center justify-between p-3 rounded-xl" style={{ backgroundColor: tierColors[newsSourcesFilter.tier]?.bg }}>
                  <span className="text-sm" style={{ color: colors.text }}>Tier: {newsSourcesFilter.tier}</span>
                  <button onClick={() => setNewsSourcesFilter(prev => ({ ...prev, tier: null }))}>
                    <X size={16} style={{ color: colors.textMuted }} />
                  </button>
                </div>
              )}
              {newsSourcesFilter.language && (
                <div className="flex items-center justify-between p-3 rounded-xl" style={{ backgroundColor: colors.accentSoft }}>
                  <span className="text-sm" style={{ color: colors.text }}>
                    Language: {languageFlags[newsSourcesFilter.language]} {newsSourcesFilter.language.toUpperCase()}
                  </span>
                  <button onClick={() => setNewsSourcesFilter(prev => ({ ...prev, language: null }))}>
                    <X size={16} style={{ color: colors.textMuted }} />
                  </button>
                </div>
              )}
              {newsSourcesFilter.category && (
                <div className="flex items-center justify-between p-3 rounded-xl" style={{ backgroundColor: colors.warningSoft }}>
                  <span className="text-sm capitalize" style={{ color: colors.text }}>
                    Category: {newsSourcesFilter.category}
                  </span>
                  <button onClick={() => setNewsSourcesFilter(prev => ({ ...prev, category: null }))}>
                    <X size={16} style={{ color: colors.textMuted }} />
                  </button>
                </div>
              )}
              {!newsSourcesFilter.tier && !newsSourcesFilter.language && !newsSourcesFilter.category && (
                <p className="text-sm text-center py-4" style={{ color: colors.textMuted }}>
                  Click on any stat to filter
                </p>
              )}
              {(newsSourcesFilter.tier || newsSourcesFilter.language || newsSourcesFilter.category) && (
                <button
                  onClick={() => setNewsSourcesFilter({ tier: null, language: null, category: null })}
                  className="w-full px-4 py-2 rounded-xl text-sm font-medium transition-all"
                  style={{ backgroundColor: colors.surface, color: colors.textSecondary }}
                >
                  Clear All Filters
                </button>
              )}
            </div>
            
            {/* Showing count */}
            <div className="mt-4 pt-4 border-t" style={{ borderColor: colors.border }}>
              <p className="text-sm" style={{ color: colors.textSecondary }}>
                Showing <span className="font-bold" style={{ color: colors.accent }}>{sources.length}</span> of {stats.total || 0} sources
              </p>
            </div>
          </div>
        </div>

        {/* Sources List */}
        <div className="bg-white rounded-2xl border overflow-hidden" style={{ borderColor: colors.border }}>
          {/* Header */}
          <div 
            className="px-6 py-4 border-b flex items-center justify-between"
            style={{ backgroundColor: colors.surface, borderColor: colors.border }}
          >
            <span className="font-semibold" style={{ color: colors.text }}>
              Sources ({sources.length})
            </span>
            <div className="flex gap-2 text-xs" style={{ color: colors.textSecondary }}>
              <span>Tier</span>
              <span>•</span>
              <span>Name</span>
              <span>•</span>
              <span>Category</span>
              <span>•</span>
              <span>Language</span>
              <span>•</span>
              <span>Status</span>
            </div>
          </div>
          
          {/* List */}
          <div className="divide-y max-h-[600px] overflow-y-auto" style={{ borderColor: colors.border }}>
            {sources
              .filter(source => {
                if (!newsSourcesSearch) return true;
                const searchLower = newsSourcesSearch.toLowerCase();
                return (
                  source.name?.toLowerCase().includes(searchLower) ||
                  source.domain?.toLowerCase().includes(searchLower) ||
                  source.category?.toLowerCase().includes(searchLower) ||
                  source.id?.toLowerCase().includes(searchLower) ||
                  source.language?.toLowerCase().includes(searchLower)
                );
              })
              .map((source, idx) => {
              const tc = tierColors[source.tier] || tierColors.D;
              const catConfig = categoryConfig[source.category] || { icon: <Globe size={14} />, color: colors.textSecondary };
              
              return (
                <div 
                  key={source.id || idx}
                  className="px-6 py-4 flex items-center gap-4 transition-all hover:bg-gray-50"
                  data-testid={`source-row-${source.id}`}
                >
                  {/* Tier badge */}
                  <div 
                    className="w-10 h-10 rounded-xl flex items-center justify-center font-bold flex-shrink-0"
                    style={{ backgroundColor: tc.bg, color: tc.text }}
                  >
                    {source.tier}
                  </div>
                  
                  {/* Name & Domain */}
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate" style={{ color: colors.text }}>
                      {source.name}
                    </p>
                    <p className="text-sm truncate" style={{ color: colors.textMuted }}>
                      {source.domain}
                    </p>
                  </div>
                  
                  {/* Category */}
                  <div 
                    className="px-3 py-1.5 rounded-lg flex items-center gap-1.5 flex-shrink-0"
                    style={{ backgroundColor: `${catConfig.color}15` }}
                  >
                    <span style={{ color: catConfig.color }}>{catConfig.icon}</span>
                    <span className="text-xs font-medium capitalize" style={{ color: catConfig.color }}>
                      {source.category}
                    </span>
                  </div>
                  
                  {/* Language */}
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <span className="text-lg">{languageFlags[source.language] || '🌐'}</span>
                    <span className="text-xs uppercase font-medium" style={{ color: colors.textSecondary }}>
                      {source.language}
                    </span>
                  </div>
                  
                  {/* Status indicator */}
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span 
                      className="w-2.5 h-2.5 rounded-full"
                      style={{ 
                        backgroundColor: source.status === 'active' ? colors.success : 
                          source.status === 'degraded' ? colors.warning : colors.textMuted
                      }}
                    />
                    <span className="text-xs capitalize" style={{ color: colors.textSecondary }}>
                      {source.status || 'unknown'}
                    </span>
                  </div>
                  
                  {/* External link */}
                  <a 
                    href={`https://${source.domain}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-2 rounded-lg transition-all hover:bg-gray-100 flex-shrink-0"
                    style={{ color: colors.textMuted }}
                  >
                    <ExternalLink size={16} />
                  </a>
                </div>
              );
            })}
            
            {sources.length === 0 && !newsSourcesLoading && (
              <div className="px-6 py-12 text-center">
                <Rss size={48} style={{ color: colors.textMuted }} className="mx-auto mb-4" />
                <p className="text-lg font-medium" style={{ color: colors.text }}>No sources found</p>
                <p className="text-sm" style={{ color: colors.textSecondary }}>Try adjusting your filters</p>
              </div>
            )}
            
            {newsSourcesLoading && (
              <div className="px-6 py-12 text-center">
                <RefreshCw size={32} className="animate-spin mx-auto mb-4" style={{ color: colors.accent }} />
                <p className="text-sm" style={{ color: colors.textSecondary }}>Loading sources...</p>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  // Discovery System Dashboard
  const renderDiscoveryDashboard = () => {
    const d = discoveryDashboard || {};
    const scheduler = d.scheduler || {};
    const sources = d.sources || {};
    const endpoints = d.endpoints || {};
    const topEndpoints = d.top_endpoints || [];
    const driftAlerts = d.drift_alerts || [];
    const driftSummary = d.drift_summary || {};
    const coverage = d.coverage || {};
    const activity = d.activity || [];
    
    const severityColors = {
      critical: { bg: colors.errorSoft, text: colors.error },
      high: { bg: '#FEE2E2', text: '#DC2626' },
      medium: { bg: colors.warningSoft, text: colors.warning },
      low: { bg: colors.surface, text: colors.textSecondary }
    };
    
    const jobStatusColors = {
      active: colors.success,
      stopped: colors.error,
      delayed: colors.warning
    };
    
    return (
      <div className="space-y-6" data-testid="discovery-dashboard">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold" style={{ color: colors.text }}>
              Self-Learning Discovery System
            </h2>
            <p className="text-sm" style={{ color: colors.textSecondary }}>
              Browser Discovery • Drift Detection • Endpoint Scoring • Auto Re-discovery
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => triggerManualDiscovery()}
              className="flex items-center gap-2 px-4 py-2 rounded-xl transition-all font-medium"
              style={{ backgroundColor: colors.accentSoft, color: colors.accent }}
              data-testid="trigger-discovery-btn"
            >
              <Globe size={16} />
              Run Discovery
            </button>
            <button
              onClick={() => triggerDriftCheck()}
              className="flex items-center gap-2 px-3 py-2 rounded-xl transition-all"
              style={{ backgroundColor: colors.warningSoft, color: colors.warning }}
              data-testid="trigger-drift-btn"
            >
              <AlertTriangle size={16} />
              Check Drift
            </button>
            <button
              onClick={() => triggerScoring()}
              className="flex items-center gap-2 px-3 py-2 rounded-xl transition-all"
              style={{ backgroundColor: colors.successSoft, color: colors.success }}
              data-testid="trigger-scoring-btn"
            >
              <TrendingUp size={16} />
              Score All
            </button>
            <button
              onClick={fetchDiscoveryDashboard}
              disabled={discoveryDashboardLoading}
              className="flex items-center gap-2 px-3 py-2 rounded-xl transition-all"
              style={{ backgroundColor: colors.surface, color: colors.textSecondary }}
            >
              <RefreshCw size={16} className={discoveryDashboardLoading ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>

        {/* Data Tiers Overview */}
        {d.tiers && Object.keys(d.tiers).length > 0 && (
          <div className="space-y-4">
            {Object.entries(d.tiers).map(([tierId, tier]) => (
              <div key={tierId} className="bg-white rounded-2xl border p-5" style={{ borderColor: colors.border }}>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-semibold text-sm flex items-center gap-2" style={{ color: colors.text }}>
                    <Layers size={16} style={{ color: tierId === 'T1' ? colors.accent : tierId === 'T2' ? colors.warning : colors.textSecondary }} />
                    {tier.label}
                  </h3>
                  <div className="flex items-center gap-2">
                    <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                      style={{ backgroundColor: colors.successSoft, color: colors.success }}>
                      {tier.active_count} active
                    </span>
                    <span className="text-xs" style={{ color: colors.textSecondary }}>
                      {tier.total_records?.toLocaleString()} records
                    </span>
                  </div>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
                  {tier.sources.map((src) => (
                    <div key={src.id} className="p-3 rounded-xl" 
                      style={{ backgroundColor: src.status === 'active' ? colors.successSoft : colors.surface }}>
                      <div className="flex items-center gap-2 mb-1">
                        <div className="w-2 h-2 rounded-full" 
                          style={{ backgroundColor: src.status === 'active' ? colors.success : colors.error }} />
                        <span className="font-medium text-sm" style={{ color: colors.text }}>{src.name}</span>
                      </div>
                      <p className="text-lg font-bold" style={{ color: src.records > 0 ? colors.text : colors.textMuted }}>
                        {src.records.toLocaleString()}
                      </p>
                      <p className="text-[10px]" style={{ color: colors.textMuted }}>
                        {src.type} {src.last_updated ? `• ${new Date(src.last_updated).toLocaleDateString()}` : ''}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Graph Health Overview */}
        {d.graph && d.graph.nodes > 0 && (
          <div className="bg-white rounded-2xl border p-5" style={{ borderColor: colors.border }}>
            <h3 className="font-semibold flex items-center gap-2 mb-4" style={{ color: colors.text }}>
              <Network size={18} style={{ color: colors.accent }} />
              Knowledge Graph
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              <div className="p-3 rounded-xl text-center" style={{ backgroundColor: colors.accentSoft }}>
                <p className="text-2xl font-bold" style={{ color: colors.accent }}>{d.graph.nodes.toLocaleString()}</p>
                <p className="text-xs" style={{ color: colors.textSecondary }}>Nodes</p>
              </div>
              <div className="p-3 rounded-xl text-center" style={{ backgroundColor: colors.successSoft }}>
                <p className="text-2xl font-bold" style={{ color: colors.success }}>{d.graph.edges.toLocaleString()}</p>
                <p className="text-xs" style={{ color: colors.textSecondary }}>Edges</p>
              </div>
              <div className="p-3 rounded-xl text-center" style={{ backgroundColor: colors.surface }}>
                <p className="text-2xl font-bold" style={{ color: colors.text }}>{Object.keys(d.graph.node_types || {}).length}</p>
                <p className="text-xs" style={{ color: colors.textSecondary }}>Node Types</p>
              </div>
              <div className="p-3 rounded-xl text-center" style={{ backgroundColor: colors.surface }}>
                <p className="text-2xl font-bold" style={{ color: colors.text }}>{Object.keys(d.graph.edge_types || {}).length}</p>
                <p className="text-xs" style={{ color: colors.textSecondary }}>Edge Types</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs font-medium mb-2" style={{ color: colors.textSecondary }}>Node Type Distribution</p>
                <div className="space-y-1">
                  {Object.entries(d.graph.node_types || {}).slice(0, 6).map(([type, count]) => (
                    <div key={type} className="flex items-center gap-2">
                      <div className="flex-1 h-4 rounded overflow-hidden" style={{ backgroundColor: colors.surface }}>
                        <div className="h-full rounded" style={{ 
                          width: `${(count / d.graph.nodes) * 100}%`, 
                          backgroundColor: colors.accent 
                        }} />
                      </div>
                      <span className="text-[10px] w-20 text-right" style={{ color: colors.text }}>{type}: {count}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs font-medium mb-2" style={{ color: colors.textSecondary }}>Edge Type Distribution</p>
                <div className="space-y-1">
                  {Object.entries(d.graph.edge_types || {}).slice(0, 6).map(([type, count]) => (
                    <div key={type} className="flex items-center gap-2">
                      <div className="flex-1 h-4 rounded overflow-hidden" style={{ backgroundColor: colors.surface }}>
                        <div className="h-full rounded" style={{ 
                          width: `${(count / d.graph.edges) * 100}%`, 
                          backgroundColor: colors.success 
                        }} />
                      </div>
                      <span className="text-[10px] w-28 text-right truncate" style={{ color: colors.text }}>{type}: {count}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Row 1: Scheduler Status + Source Health */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Scheduler Status */}
          <div className="bg-white rounded-2xl border p-6" style={{ borderColor: colors.border }}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold flex items-center gap-2" style={{ color: colors.text }}>
                <Clock size={18} style={{ color: colors.accent }} />
                Scheduler Status
              </h3>
              <span 
                className="px-2 py-1 rounded-full text-xs font-medium"
                style={{ 
                  backgroundColor: scheduler.running ? colors.successSoft : colors.errorSoft,
                  color: scheduler.running ? colors.success : colors.error
                }}
              >
                {scheduler.running ? 'RUNNING' : 'STOPPED'}
              </span>
            </div>
            <div className="space-y-3">
              {(scheduler.jobs || []).map((job, idx) => (
                <div 
                  key={idx}
                  className="flex items-center justify-between p-3 rounded-xl"
                  style={{ backgroundColor: colors.surface }}
                >
                  <div className="flex items-center gap-3">
                    <div 
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: jobStatusColors[job.status] || colors.textMuted }}
                    />
                    <span className="font-medium text-sm" style={{ color: colors.text }}>
                      {job.name}
                    </span>
                  </div>
                  <span className="text-xs" style={{ color: colors.textSecondary }}>
                    {job.next_run ? new Date(job.next_run).toLocaleString() : 'N/A'}
                  </span>
                </div>
              ))}
              {(scheduler.jobs || []).length === 0 && (
                <p className="text-sm text-center py-4" style={{ color: colors.textMuted }}>
                  No scheduler jobs configured
                </p>
              )}
            </div>
          </div>

          {/* Endpoint & Source Stats */}
          <div className="bg-white rounded-2xl border p-6" style={{ borderColor: colors.border }}>
            <h3 className="font-semibold flex items-center gap-2 mb-4" style={{ color: colors.text }}>
              <Database size={18} style={{ color: colors.accent }} />
              Discovery Health
            </h3>
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="p-4 rounded-xl text-center" style={{ backgroundColor: colors.surface }}>
                <p className="text-2xl font-bold" style={{ color: colors.text }}>{sources.total || 0}</p>
                <p className="text-xs" style={{ color: colors.textSecondary }}>Total Sources</p>
              </div>
              <div className="p-4 rounded-xl text-center" style={{ backgroundColor: colors.successSoft }}>
                <p className="text-2xl font-bold" style={{ color: colors.success }}>{sources.active || 0}</p>
                <p className="text-xs" style={{ color: colors.textSecondary }}>Активные</p>
              </div>
              <div className="p-4 rounded-xl text-center" style={{ backgroundColor: colors.warningSoft }}>
                <p className="text-2xl font-bold" style={{ color: colors.warning }}>{sources.degraded || 0}</p>
                <p className="text-xs" style={{ color: colors.textSecondary }}>Degraded</p>
              </div>
              <div className="p-4 rounded-xl text-center" style={{ backgroundColor: colors.accentSoft }}>
                <p className="text-2xl font-bold" style={{ color: colors.accent }}>{endpoints.scored || 0}</p>
                <p className="text-xs" style={{ color: colors.textSecondary }}>Scored Endpoints</p>
              </div>
            </div>
            <div className="flex items-center justify-between text-sm" style={{ color: colors.textSecondary }}>
              <span>Total Endpoints: {endpoints.total || 0}</span>
              <span>Active: {endpoints.active || 0}</span>
            </div>
          </div>
        </div>

        {/* Row 2: Top Endpoints + Drift Alerts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Top Endpoints */}
          <div className="bg-white rounded-2xl border p-6" style={{ borderColor: colors.border }}>
            <h3 className="font-semibold flex items-center gap-2 mb-4" style={{ color: colors.text }}>
              <TrendingUp size={18} style={{ color: colors.success }} />
              Top Endpoints by Score
            </h3>
            <div className="space-y-2 max-h-72 overflow-y-auto">
              {topEndpoints.map((ep, idx) => (
                <div 
                  key={ep.id || idx}
                  className="flex items-center justify-between p-3 rounded-xl transition-all hover:shadow-sm"
                  style={{ backgroundColor: colors.surface }}
                  data-testid={`top-endpoint-${idx}`}
                >
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <div 
                      className="w-8 h-8 rounded-lg flex items-center justify-center font-bold text-sm"
                      style={{ 
                        backgroundColor: idx < 3 ? colors.accentSoft : colors.surface,
                        color: idx < 3 ? colors.accent : colors.textSecondary,
                        border: `1px solid ${colors.border}`
                      }}
                    >
                      {idx + 1}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-sm truncate" style={{ color: colors.text }}>
                        {ep.domain}
                      </p>
                      <p className="text-xs truncate" style={{ color: colors.textMuted }}>
                        {ep.path}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <div className="text-right">
                      <p className="font-bold text-lg" style={{ color: ep.score >= 70 ? colors.success : ep.score >= 50 ? colors.warning : colors.error }}>
                        {ep.score}
                      </p>
                      <p className="text-[10px]" style={{ color: colors.textMuted }}>
                        {ep.latency_ms}ms
                      </p>
                    </div>
                    {ep.replay_ok && (
                      <CheckCircle size={16} style={{ color: colors.success }} />
                    )}
                  </div>
                </div>
              ))}
              {topEndpoints.length === 0 && (
                <p className="text-sm text-center py-8" style={{ color: colors.textMuted }}>
                  No scored endpoints yet. Run scoring to populate.
                </p>
              )}
            </div>
          </div>

          {/* Drift Alerts */}
          <div className="bg-white rounded-2xl border p-6" style={{ borderColor: colors.border }}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold flex items-center gap-2" style={{ color: colors.text }}>
                <AlertTriangle size={18} style={{ color: colors.warning }} />
                Drift Alerts
              </h3>
              {Object.keys(driftSummary).length > 0 && (
                <div className="flex gap-2">
                  {Object.entries(driftSummary).map(([sev, count]) => (
                    <span 
                      key={sev}
                      className="px-2 py-0.5 rounded text-xs font-medium"
                      style={severityColors[sev] || severityColors.low}
                    >
                      {sev}: {count}
                    </span>
                  ))}
                </div>
              )}
            </div>
            <div className="space-y-2 max-h-72 overflow-y-auto">
              {driftAlerts.map((drift, idx) => {
                const sc = severityColors[drift.severity] || severityColors.low;
                return (
                  <div 
                    key={idx}
                    className="p-3 rounded-xl"
                    style={{ backgroundColor: sc.bg }}
                    data-testid={`drift-alert-${idx}`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium text-sm" style={{ color: sc.text }}>
                        {drift.domain}
                      </span>
                      <span 
                        className="px-2 py-0.5 rounded text-xs font-medium uppercase"
                        style={{ backgroundColor: 'rgba(0,0,0,0.1)', color: sc.text }}
                      >
                        {drift.severity}
                      </span>
                    </div>
                    <p className="text-xs" style={{ color: colors.textSecondary }}>
                      {drift.type} drift detected
                    </p>
                    <p className="text-[10px] mt-1" style={{ color: colors.textMuted }}>
                      {drift.detected_at ? new Date(drift.detected_at).toLocaleString() : ''}
                    </p>
                  </div>
                );
              })}
              {driftAlerts.length === 0 && (
                <div className="text-center py-8">
                  <CheckCircle size={32} style={{ color: colors.success }} className="mx-auto mb-2" />
                  <p className="text-sm" style={{ color: colors.success }}>No drift detected</p>
                  <p className="text-xs" style={{ color: colors.textMuted }}>All endpoints healthy</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Row 3: Coverage + Activity */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Endpoint Coverage */}
          <div className="bg-white rounded-2xl border p-6" style={{ borderColor: colors.border }}>
            <h3 className="font-semibold flex items-center gap-2 mb-4" style={{ color: colors.text }}>
              <Layers size={18} style={{ color: colors.accent }} />
              Endpoint Coverage by Capability
            </h3>
            <div className="space-y-3">
              {Object.entries(coverage).slice(0, 8).map(([cap, count], idx) => {
                const maxCount = Math.max(...Object.values(coverage));
                const pct = maxCount > 0 ? (count / maxCount) * 100 : 0;
                const capColors = {
                  market_data: colors.success,
                  defi_data: colors.accent,
                  dex_data: colors.warning,
                  funding: '#8B5CF6',
                  news: '#EC4899',
                  derivatives: '#F97316',
                  token_data: '#06B6D4',
                  onchain: '#10B981'
                };
                const barColor = capColors[cap] || colors.textSecondary;
                
                return (
                  <div key={cap} className="flex items-center gap-3">
                    <span className="text-sm w-28 truncate" style={{ color: colors.text }}>
                      {cap.replace(/_/g, ' ')}
                    </span>
                    <div className="flex-1 h-6 rounded-lg overflow-hidden" style={{ backgroundColor: colors.surface }}>
                      <div 
                        className="h-full rounded-lg transition-all flex items-center justify-end pr-2"
                        style={{ width: `${pct}%`, backgroundColor: barColor }}
                      >
                        <span className="text-xs font-medium text-white">{count}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
              {Object.keys(coverage).length === 0 && (
                <p className="text-sm text-center py-4" style={{ color: colors.textMuted }}>
                  No endpoint coverage data
                </p>
              )}
            </div>
          </div>

          {/* Discovery Activity */}
          <div className="bg-white rounded-2xl border p-6" style={{ borderColor: colors.border }}>
            <h3 className="font-semibold flex items-center gap-2 mb-4" style={{ color: colors.text }}>
              <Activity size={18} style={{ color: colors.accent }} />
              Recent Discovery Activity
            </h3>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {activity.slice(0, 15).map((log, idx) => (
                <div 
                  key={idx}
                  className="flex items-center gap-3 p-2 rounded-lg"
                  style={{ backgroundColor: colors.surface }}
                >
                  <div 
                    className="w-2 h-2 rounded-full flex-shrink-0"
                    style={{ 
                      backgroundColor: log.status === 'success' || log.status === 'completed' 
                        ? colors.success 
                        : log.status === 'error' ? colors.error : colors.warning
                    }}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm truncate" style={{ color: colors.text }}>
                      {log.domain || 'System'}
                      {log.endpoints_found > 0 && (
                        <span style={{ color: colors.success }}> (+{log.endpoints_found} endpoints)</span>
                      )}
                    </p>
                  </div>
                  <span className="text-xs flex-shrink-0" style={{ color: colors.textMuted }}>
                    {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : ''}
                  </span>
                </div>
              ))}
              {activity.length === 0 && (
                <p className="text-sm text-center py-4" style={{ color: colors.textMuted }}>
                  No recent activity
                </p>
              )}
            </div>
          </div>
        </div>

        {/* News Sources Registry */}
        <div className="bg-white rounded-2xl border p-6" style={{ borderColor: colors.border }} data-testid="news-sources-registry">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <Rss size={20} style={{ color: colors.accent }} />
              <span className="font-semibold" style={{ color: colors.text }}>News Sources Registry</span>
              <span 
                className="px-2 py-0.5 rounded-full text-xs"
                style={{ backgroundColor: colors.accentSoft, color: colors.accent }}
              >
                {newsSources.stats?.total || 0} sources
              </span>
            </div>
            <div className="flex gap-2">
              {/* Tier Filter */}
              <select
                value={newsSourcesFilter.tier || ''}
                onChange={(e) => setNewsSourcesFilter(prev => ({ ...prev, tier: e.target.value || null }))}
                className="px-3 py-1.5 rounded-lg text-xs"
                style={{ backgroundColor: colors.surface, color: colors.text, border: `1px solid ${colors.border}` }}
              >
                <option value="">All Tiers</option>
                <option value="A">Tier A (Primary)</option>
                <option value="B">Tier B (Secondary)</option>
                <option value="C">Tier C (Research)</option>
                <option value="D">Tier D (Aggregators)</option>
              </select>
              {/* Language Filter */}
              <select
                value={newsSourcesFilter.language || ''}
                onChange={(e) => setNewsSourcesFilter(prev => ({ ...prev, language: e.target.value || null }))}
                className="px-3 py-1.5 rounded-lg text-xs"
                style={{ backgroundColor: colors.surface, color: colors.text, border: `1px solid ${colors.border}` }}
              >
                <option value="">All Languages</option>
                <option value="en">English ({newsSources.stats?.by_language?.en || 0})</option>
                <option value="ru">Russian ({newsSources.stats?.by_language?.ru || 0})</option>
                <option value="zh">Chinese ({newsSources.stats?.by_language?.zh || 0})</option>
                <option value="jp">Japanese ({newsSources.stats?.by_language?.jp || 0})</option>
                <option value="de">German ({newsSources.stats?.by_language?.de || 0})</option>
                <option value="ua">Ukrainian ({newsSources.stats?.by_language?.ua || 0})</option>
              </select>
              {/* Category Filter */}
              <select
                value={newsSourcesFilter.category || ''}
                onChange={(e) => setNewsSourcesFilter(prev => ({ ...prev, category: e.target.value || null }))}
                className="px-3 py-1.5 rounded-lg text-xs"
                style={{ backgroundColor: colors.surface, color: colors.text, border: `1px solid ${colors.border}` }}
              >
                <option value="">All Categories</option>
                <option value="news">News ({newsSources.stats?.by_category?.news || 0})</option>
                <option value="research">Research ({newsSources.stats?.by_category?.research || 0})</option>
                <option value="official">Official ({newsSources.stats?.by_category?.official || 0})</option>
                <option value="analytics">Analytics ({newsSources.stats?.by_category?.analytics || 0})</option>
                <option value="security">Security ({newsSources.stats?.by_category?.security || 0})</option>
                <option value="defi">DeFi ({newsSources.stats?.by_category?.defi || 0})</option>
                <option value="dex">DEX ({newsSources.stats?.by_category?.dex || 0})</option>
                <option value="funding">Funding ({newsSources.stats?.by_category?.funding || 0})</option>
              </select>
              <button
                onClick={fetchNewsSources}
                disabled={newsSourcesLoading}
                className="p-1.5 rounded-lg transition-all"
                style={{ backgroundColor: colors.surface, color: colors.textSecondary }}
              >
                <RefreshCw size={14} className={newsSourcesLoading ? 'animate-spin' : ''} />
              </button>
            </div>
          </div>
          
          {/* Stats row */}
          <div className="grid grid-cols-4 gap-3 mb-4">
            <div className="p-3 rounded-xl text-center" style={{ backgroundColor: colors.successSoft }}>
              <p className="text-xl font-bold" style={{ color: colors.success }}>{newsSources.stats?.by_tier?.A || 0}</p>
              <p className="text-[10px]" style={{ color: colors.textSecondary }}>Tier A</p>
            </div>
            <div className="p-3 rounded-xl text-center" style={{ backgroundColor: colors.accentSoft }}>
              <p className="text-xl font-bold" style={{ color: colors.accent }}>{newsSources.stats?.by_tier?.B || 0}</p>
              <p className="text-[10px]" style={{ color: colors.textSecondary }}>Tier B</p>
            </div>
            <div className="p-3 rounded-xl text-center" style={{ backgroundColor: colors.warningSoft }}>
              <p className="text-xl font-bold" style={{ color: colors.warning }}>{newsSources.stats?.by_tier?.C || 0}</p>
              <p className="text-[10px]" style={{ color: colors.textSecondary }}>Tier C</p>
            </div>
            <div className="p-3 rounded-xl text-center" style={{ backgroundColor: colors.surface }}>
              <p className="text-xl font-bold" style={{ color: colors.textSecondary }}>{newsSources.stats?.by_tier?.D || 0}</p>
              <p className="text-[10px]" style={{ color: colors.textSecondary }}>Tier D</p>
            </div>
          </div>
          
          {/* Sources list */}
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {(newsSources.sources || []).map((source, idx) => {
              const tierColors = {
                A: { bg: colors.successSoft, text: colors.success },
                B: { bg: colors.accentSoft, text: colors.accent },
                C: { bg: colors.warningSoft, text: colors.warning },
                D: { bg: colors.surface, text: colors.textSecondary }
              };
              const categoryIcons = {
                news: <Newspaper size={14} />,
                research: <BookOpen size={14} />,
                official: <Shield size={14} />,
                analytics: <TrendingUp size={14} />,
                security: <AlertTriangle size={14} />,
                defi: <Layers size={14} />,
                dex: <Activity size={14} />,
                funding: <DollarSign size={14} />,
                aggregator: <Database size={14} />,
                derivatives: <BarChart2 size={14} />,
                l2: <Layers size={14} />,
                analysis: <Eye size={14} />
              };
              const tc = tierColors[source.tier] || tierColors.D;
              
              return (
                <div 
                  key={source.id || idx}
                  className="flex items-center justify-between p-3 rounded-xl transition-all hover:shadow-sm"
                  style={{ backgroundColor: colors.surface }}
                  data-testid={`news-source-${source.id}`}
                >
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <div 
                      className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                      style={{ backgroundColor: tc.bg }}
                    >
                      <span className="text-xs font-bold" style={{ color: tc.text }}>
                        {source.tier}
                      </span>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm truncate" style={{ color: colors.text }}>
                          {source.name}
                        </span>
                        <span 
                          className="px-1.5 py-0.5 rounded text-[10px] flex items-center gap-1"
                          style={{ backgroundColor: colors.accentSoft, color: colors.accent }}
                        >
                          {categoryIcons[source.category] || <Globe size={12} />}
                          {source.category}
                        </span>
                      </div>
                      <p className="text-xs truncate" style={{ color: colors.textMuted }}>
                        {source.domain}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <span 
                      className="px-2 py-0.5 rounded text-[10px] uppercase"
                      style={{ 
                        backgroundColor: source.language === 'en' ? colors.accentSoft : colors.warningSoft,
                        color: source.language === 'en' ? colors.accent : colors.warning
                      }}
                    >
                      {source.language}
                    </span>
                    <span 
                      className={`w-2 h-2 rounded-full`}
                      style={{ 
                        backgroundColor: source.status === 'active' ? colors.success : 
                          source.status === 'degraded' ? colors.warning : colors.textMuted
                      }}
                    />
                  </div>
                </div>
              );
            })}
            {(newsSources.sources || []).length === 0 && !newsSourcesLoading && (
              <p className="text-sm text-center py-8" style={{ color: colors.textMuted }}>
                No sources found
              </p>
            )}
          </div>
        </div>

        {/* Architecture Info */}
        <div className="bg-white rounded-2xl border p-6" style={{ borderColor: colors.border }}>
          <h3 className="font-semibold mb-4 flex items-center gap-2" style={{ color: colors.text }}>
            <Shield size={18} />
            Self-Learning Discovery Architecture
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl" style={{ backgroundColor: colors.accentSoft }}>
              <div className="flex items-center gap-2 mb-2">
                <Globe size={16} style={{ color: colors.accent }} />
                <span className="font-medium text-sm" style={{ color: colors.accent }}>Browser Discovery</span>
              </div>
              <p className="text-xs" style={{ color: colors.textSecondary }}>
                Playwright intercepts XHR/Fetch/GraphQL with human-like behavior simulation
              </p>
            </div>
            <div className="p-4 rounded-xl" style={{ backgroundColor: colors.warningSoft }}>
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle size={16} style={{ color: colors.warning }} />
                <span className="font-medium text-sm" style={{ color: colors.warning }}>Drift Detection</span>
              </div>
              <p className="text-xs" style={{ color: colors.textSecondary }}>
                Schema, status, performance, data drift with auto re-discovery on critical
              </p>
            </div>
            <div className="p-4 rounded-xl" style={{ backgroundColor: colors.successSoft }}>
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp size={16} style={{ color: colors.success }} />
                <span className="font-medium text-sm" style={{ color: colors.success }}>Endpoint Scoring</span>
              </div>
              <p className="text-xs" style={{ color: colors.textSecondary }}>
                5-factor scoring: Reliability, Performance, Quality, Coverage, Freshness
              </p>
            </div>
            <div className="p-4 rounded-xl" style={{ backgroundColor: '#EDE9FE' }}>
              <div className="flex items-center gap-2 mb-2">
                <Zap size={16} style={{ color: '#8B5CF6' }} />
                <span className="font-medium text-sm" style={{ color: '#8B5CF6' }}>API Replay</span>
              </div>
              <p className="text-xs" style={{ color: colors.textSecondary }}>
                Fetch data via stored blueprints (headers, cookies) without browser
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Proxy Admin Section
  const renderProxyAdmin = () => (
    <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold" style={{ color: colors.text }}>
              Proxy Management
            </h2>
            <p className="text-sm" style={{ color: colors.textSecondary }}>
              Настройка прокси для Binance, Bybit и парсеров
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => startParser()}
              disabled={parserRunning || !proxyStatus?.enabled}
              className="flex items-center gap-2 px-4 py-2 rounded-xl transition-all font-medium"
              style={{ 
                backgroundColor: proxyStatus?.enabled ? colors.success : colors.surface, 
                color: proxyStatus?.enabled ? 'white' : colors.textMuted 
              }}
              title={proxyStatus?.enabled ? "Start sync via proxy" : "Add and enable a proxy first"}
            >
              <Play size={16} className={parserRunning ? 'animate-pulse' : ''} />
              {parserRunning ? 'Syncing...' : 'Start Sync'}
            </button>
            <button
              onClick={() => testProxies()}
              disabled={proxyLoading}
              className="flex items-center gap-2 px-4 py-2 rounded-xl transition-all"
              style={{ backgroundColor: colors.accentSoft, color: colors.accent }}
            >
              <Wifi size={16} />
              Test
            </button>
            <button
              onClick={fetchProxyStatus}
              disabled={proxyLoading}
              className="flex items-center gap-2 px-4 py-2 rounded-xl transition-all"
              style={{ backgroundColor: colors.surface, color: colors.textSecondary }}
            >
              <RefreshCw size={16} className={proxyLoading ? 'animate-spin' : ''} />
              Refresh
            </button>
          </div>
        </div>
        
        {/* Parser Result */}
        {parserResult && (
          <div 
            className="rounded-2xl p-4 border"
            style={{ 
              borderColor: parserResult.ok ? colors.success : colors.error,
              backgroundColor: parserResult.ok ? colors.successSoft : colors.errorSoft 
            }}
          >
            <div className="flex items-center gap-2 mb-2">
              {parserResult.ok ? (
                <CheckCircle size={20} style={{ color: colors.success }} />
              ) : (
                <XCircle size={20} style={{ color: colors.error }} />
              )}
              <span className="font-medium" style={{ color: parserResult.ok ? colors.success : colors.error }}>
                {parserResult.ok ? 'Sync Completed' : 'Sync Failed'}
              </span>
            </div>
            {parserResult.synced && (
              <div className="grid grid-cols-3 gap-4 mt-3">
                {Object.entries(parserResult.synced).map(([key, value]) => (
                  <div key={key} className="text-sm">
                    <span className="font-medium capitalize">{key}: </span>
                    <span style={{ color: colors.textSecondary }}>
                      {typeof value === 'object' ? (value.total || value.error || JSON.stringify(value)) : value}
                    </span>
                  </div>
                ))}
              </div>
            )}
            {parserResult.error && (
              <p className="text-sm mt-2" style={{ color: colors.error }}>{parserResult.error}</p>
            )}
          </div>
        )}
        
        {/* Add Proxy Form */}
        <div 
          className="bg-white rounded-2xl border p-6"
          style={{ borderColor: colors.border }}
        >
          <h3 className="font-semibold mb-4 flex items-center gap-2" style={{ color: colors.text }}>
            <Plus size={18} />
            Add Proxy
          </h3>
          
          {/* Row 1: Type, Host, Port */}
          <div className="grid grid-cols-6 gap-4 mb-4">
            <div className="relative">
              <label className="text-sm mb-1 block" style={{ color: colors.textSecondary }}>
                Type *
              </label>
              <div 
                onClick={() => setTypeDropdownOpen(!typeDropdownOpen)}
                className="w-full px-4 py-2 rounded-xl border cursor-pointer flex items-center justify-between"
                style={{ borderColor: colors.border, backgroundColor: 'white' }}
              >
                <span style={{ color: colors.text }}>
                  {proxyTypes.find(t => t.value === newProxy.type)?.label}
                </span>
                <ChevronRight 
                  size={16} 
                  style={{ 
                    color: colors.textMuted,
                    transform: typeDropdownOpen ? 'rotate(90deg)' : 'rotate(0deg)',
                    transition: 'transform 0.2s ease'
                  }} 
                />
              </div>
              {typeDropdownOpen && (
                <div 
                  className="absolute top-full left-0 right-0 mt-1 rounded-xl border shadow-lg z-50 overflow-hidden"
                  style={{ backgroundColor: 'white', borderColor: colors.border }}
                >
                  {proxyTypes.map((type) => (
                    <div
                      key={type.value}
                      onClick={() => {
                        setNewProxy({...newProxy, type: type.value});
                        setTypeDropdownOpen(false);
                      }}
                      className="px-4 py-2.5 cursor-pointer transition-all flex items-center gap-2"
                      style={{ 
                        backgroundColor: newProxy.type === type.value ? colors.accentSoft : 'white',
                        color: newProxy.type === type.value ? colors.accent : colors.text
                      }}
                      onMouseEnter={(e) => e.target.style.backgroundColor = colors.surface}
                      onMouseLeave={(e) => e.target.style.backgroundColor = newProxy.type === type.value ? colors.accentSoft : 'white'}
                    >
                      {newProxy.type === type.value && (
                        <CheckCircle size={14} style={{ color: colors.accent }} />
                      )}
                      <span className="font-medium">{type.label}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="col-span-3">
              <label className="text-sm mb-1 block" style={{ color: colors.textSecondary }}>
                IP адрес / Host *
              </label>
              <input
                type="text"
                value={newProxy.host}
                onChange={(e) => setNewProxy({...newProxy, host: e.target.value})}
                placeholder="192.168.1.1 или proxy.example.com"
                className="w-full px-4 py-2 rounded-xl border"
                style={{ borderColor: colors.border }}
              />
            </div>
            <div>
              <label className="text-sm mb-1 block" style={{ color: colors.textSecondary }}>
                Port *
              </label>
              <input
                type="text"
                value={newProxy.port}
                onChange={(e) => setNewProxy({...newProxy, port: e.target.value})}
                placeholder="8080"
                className="w-full px-4 py-2 rounded-xl border"
                style={{ borderColor: colors.border }}
              />
            </div>
            <div>
              <label className="text-sm mb-1 block" style={{ color: colors.textSecondary }}>
                Priority
              </label>
              <input
                type="number"
                min="1"
                max="10"
                value={newProxy.priority}
                onChange={(e) => setNewProxy({...newProxy, priority: parseInt(e.target.value) || 1})}
                className="w-full px-4 py-2 rounded-xl border"
                style={{ borderColor: colors.border }}
              />
            </div>
          </div>
          
          {/* Row 2: Username, Password, Add Button */}
          <div className="grid grid-cols-6 gap-4">
            <div className="col-span-2">
              <label className="text-sm mb-1 block" style={{ color: colors.textSecondary }}>
                Username (optional)
              </label>
              <input
                type="text"
                value={newProxy.username}
                onChange={(e) => setNewProxy({...newProxy, username: e.target.value})}
                placeholder="optional"
                className="w-full px-4 py-2 rounded-xl border"
                style={{ borderColor: colors.border }}
              />
            </div>
            <div className="col-span-2">
              <label className="text-sm mb-1 block" style={{ color: colors.textSecondary }}>
                Password (optional)
              </label>
              <input
                type="password"
                value={newProxy.password}
                onChange={(e) => setNewProxy({...newProxy, password: e.target.value})}
                placeholder="optional"
                className="w-full px-4 py-2 rounded-xl border"
                style={{ borderColor: colors.border }}
              />
            </div>
            <div className="col-span-2 flex items-end">
              <button
                onClick={addProxy}
                disabled={proxyLoading || !newProxy.host || !newProxy.port}
                className="w-full flex items-center justify-center gap-2 px-6 py-2 rounded-xl font-medium transition-all"
                style={{ 
                  backgroundColor: (newProxy.host && newProxy.port) ? colors.accent : colors.surface, 
                  color: (newProxy.host && newProxy.port) ? 'white' : colors.textMuted 
                }}
              >
                <Plus size={16} />
                Add
              </button>
            </div>
          </div>
          
          {/* Preview */}
          {newProxy.host && newProxy.port && (
            <div 
              className="mt-4 p-3 rounded-xl text-sm"
              style={{ backgroundColor: colors.surface }}
            >
              <span style={{ color: colors.textSecondary }}>Preview: </span>
              <code style={{ color: colors.accent }}>
                {buildProxyServer()}
                {newProxy.username && ` (auth: ${newProxy.username}:***)`}
              </code>
            </div>
          )}
        </div>
        
        {/* Proxy List */}
        <div 
          className="bg-white rounded-2xl border p-6"
          style={{ borderColor: colors.border }}
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold flex items-center gap-2" style={{ color: colors.text }}>
              <Network size={18} />
              Configured Proxies
            </h3>
            {proxyStatus?.total > 0 && (
              <button
                onClick={clearAllProxies}
                className="text-sm px-3 py-1 rounded-lg"
                style={{ backgroundColor: colors.errorSoft, color: colors.error }}
              >
                Clear All
              </button>
            )}
          </div>
          
          {!proxyStatus || proxyStatus.total === 0 ? (
            <div className="text-center py-8">
              <Wifi size={48} className="mx-auto mb-4" style={{ color: colors.textMuted }} />
              <p className="font-medium" style={{ color: colors.text }}>Прокси не настроены</p>
              <p className="text-sm" style={{ color: colors.textSecondary }}>
                Добавьте прокси для маршрутизации трафика Binance/Bybit
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {proxyStatus.proxies?.map((proxy) => (
                <div 
                  key={proxy.id}
                  className="flex items-center justify-between p-4 rounded-xl border"
                  style={{ 
                    borderColor: proxy.enabled ? colors.border : colors.errorSoft,
                    backgroundColor: proxy.enabled ? 'white' : colors.surface
                  }}
                >
                  <div className="flex items-center gap-4">
                    <div 
                      className="w-10 h-10 rounded-xl flex items-center justify-center"
                      style={{ 
                        backgroundColor: proxy.enabled ? colors.successSoft : colors.errorSoft 
                      }}
                    >
                      {proxy.enabled ? (
                        <CheckCircle size={20} style={{ color: colors.success }} />
                      ) : (
                        <XCircle size={20} style={{ color: colors.error }} />
                      )}
                    </div>
                    <div>
                      <p className="font-medium" style={{ color: colors.text }}>
                        {proxy.server}
                        {proxy.has_auth && (
                          <span 
                            className="ml-2 text-xs px-2 py-0.5 rounded"
                            style={{ backgroundColor: colors.warningSoft, color: colors.warning }}
                          >
                            Auth
                          </span>
                        )}
                      </p>
                      <p className="text-sm" style={{ color: colors.textSecondary }}>
                        Priority: {proxy.priority} • 
                        Success: {proxy.success_count} • 
                        Errors: {proxy.error_count}
                        {proxy.last_error && (
                          <span style={{ color: colors.error }}> • Last error: {proxy.last_error.slice(0, 50)}...</span>
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => startParser(proxy.id)}
                      disabled={parserRunning || !proxy.enabled}
                      className="p-2 rounded-lg transition-all"
                      style={{ backgroundColor: proxy.enabled ? colors.successSoft : colors.surface }}
                      title={proxy.enabled ? "Start sync via this proxy" : "Enable proxy first"}
                    >
                      <Play size={16} style={{ color: proxy.enabled ? colors.success : colors.textMuted }} />
                    </button>
                    <button
                      onClick={() => testProxies(proxy.id)}
                      className="p-2 rounded-lg transition-all"
                      style={{ backgroundColor: colors.accentSoft }}
                      title="Test this proxy"
                    >
                      <Wifi size={16} style={{ color: colors.accent }} />
                    </button>
                    <button
                      onClick={() => toggleProxy(proxy.id, proxy.enabled)}
                      className="p-2 rounded-lg transition-all"
                      style={{ backgroundColor: proxy.enabled ? colors.warningSoft : colors.successSoft }}
                      title={proxy.enabled ? 'Disable' : 'Enable'}
                    >
                      {proxy.enabled ? (
                        <XCircle size={16} style={{ color: colors.warning }} />
                      ) : (
                        <CheckCircle size={16} style={{ color: colors.success }} />
                      )}
                    </button>
                    <button
                      onClick={() => removeProxy(proxy.id)}
                      className="p-2 rounded-lg transition-all"
                      style={{ backgroundColor: colors.errorSoft }}
                      title="Удалить"
                    >
                      <Trash2 size={16} style={{ color: colors.error }} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        
        {/* Test Results */}
        {testResults && (
          <div 
            className="bg-white rounded-2xl border p-6"
            style={{ borderColor: colors.border }}
          >
            <h3 className="font-semibold mb-4 flex items-center gap-2" style={{ color: colors.text }}>
              <Activity size={18} />
              Test Results
            </h3>
            <div className="space-y-4">
              {testResults.results?.map((result, i) => (
                <div key={i} className="border rounded-xl p-4" style={{ borderColor: colors.border }}>
                  <p className="font-medium mb-2" style={{ color: colors.text }}>
                    Proxy #{result.id}: {result.server}
                  </p>
                  <div className="grid grid-cols-3 gap-4">
                    {result.tests?.map((test, j) => (
                      <div 
                        key={j}
                        className="p-3 rounded-lg"
                        style={{ 
                          backgroundColor: test.success ? colors.successSoft : colors.errorSoft 
                        }}
                      >
                        <div className="flex items-center gap-2">
                          {test.success ? (
                            <CheckCircle size={16} style={{ color: colors.success }} />
                          ) : (
                            <XCircle size={16} style={{ color: colors.error }} />
                          )}
                          <span className="font-medium">{test.target}</span>
                        </div>
                        <p className="text-xs mt-1" style={{ color: colors.textSecondary }}>
                          Status: {test.status}
                          {test.error && ` - ${test.error.slice(0, 40)}...`}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Info Box */}
        <div 
          className="rounded-2xl p-6"
          style={{ backgroundColor: colors.accentSoft }}
        >
          <h4 className="font-medium mb-2" style={{ color: colors.accent }}>
            How Proxy Failover Works
          </h4>
          <ul className="text-sm space-y-1" style={{ color: colors.text }}>
            <li>• Proxies are used in priority order (1 = highest)</li>
            <li>• If primary proxy fails, system automatically switches to next</li>
            <li>• Binance and Bybit require proxy due to IP restrictions</li>
            <li>• CryptoRank parser also uses configured proxies</li>
          </ul>
        </div>
      </div>
    );

  // API Keys Admin Section
  const renderApiKeysAdmin = () => (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold" style={{ color: colors.text }}>
            API Keys Management
          </h2>
          <p className="text-sm" style={{ color: colors.textSecondary }}>
            Manage API keys for CoinGecko, CoinMarketCap, Messari and more
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={checkAllKeysHealth}
            disabled={apiKeysLoading}
            className="flex items-center gap-2 px-4 py-2 rounded-xl transition-all"
            style={{ backgroundColor: colors.successSoft, color: colors.success }}
          >
            <Activity size={16} />
            Check All
          </button>
          <button
            onClick={fetchApiKeys}
            disabled={apiKeysLoading}
            className="flex items-center gap-2 px-4 py-2 rounded-xl transition-all"
            style={{ backgroundColor: colors.surface, color: colors.textSecondary }}
          >
            <RefreshCw size={16} className={apiKeysLoading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {/* Service Summary Cards - Click to filter */}
      <div className="grid grid-cols-3 gap-4">
        {apiKeysData.services?.map(service => {
          const summary = apiKeysData.summary[service.id] || {};
          const isSelected = apiKeyServiceFilter === service.id;
          return (
            <div 
              key={service.id}
              onClick={() => setApiKeyServiceFilter(isSelected ? null : service.id)}
              className="bg-white rounded-2xl border p-4 cursor-pointer transition-all hover:shadow-md"
              style={{ 
                borderColor: isSelected ? colors.accent : colors.border,
                borderWidth: isSelected ? '2px' : '1px',
                backgroundColor: isSelected ? colors.accentSoft : 'white'
              }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium" style={{ color: colors.text }}>{service.name}</span>
                {summary.healthy_keys > 0 ? (
                  <span className="px-2 py-0.5 rounded-full text-xs" 
                    style={{ backgroundColor: colors.successSoft, color: colors.success }}>
                    {summary.healthy_keys} OK
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded-full text-xs" 
                    style={{ backgroundColor: colors.surface, color: colors.textMuted }}>
                    No keys
                  </span>
                )}
              </div>
              <div className="text-xs space-y-1" style={{ color: colors.textSecondary }}>
                <p>Keys: {summary.total_keys || 0} ({summary.enabled_keys || 0} enabled)</p>
                <p>Requests today: {summary.requests_today || 0}</p>
                <p>Rate limit: {service.free_rate_limit}/{service.rate_limit_window || 'min'}
                  {service.pro_rate_limit && ` → ${service.pro_rate_limit} (Pro)`}
                </p>
                {service.description && (
                  <p className="text-xs italic" style={{ color: colors.textMuted }}>
                    {service.description.substring(0, 60)}...
                  </p>
                )}
              </div>
              <div className="flex items-center justify-between mt-2">
                {isSelected && (
                  <span className="text-xs font-medium" style={{ color: colors.accent }}>
                    Filtering
                  </span>
                )}
                {service.docs_url && (
                  <a 
                    href={service.docs_url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="text-xs flex items-center gap-1 hover:underline"
                    style={{ color: colors.accent }}
                  >
                    Get Key <ExternalLink size={10} />
                  </a>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Add API Key Form */}
      <div 
        className="bg-white rounded-2xl border p-6"
        style={{ borderColor: colors.border }}
      >
        <h3 className="font-semibold mb-4 flex items-center gap-2" style={{ color: colors.text }}>
          <Plus size={18} />
          Add API Key
        </h3>
        
        <div className="grid grid-cols-6 gap-4 mb-4">
          {/* Service selector */}
          <div className="relative col-span-2">
            <label className="text-sm mb-1 block" style={{ color: colors.textSecondary }}>
              Service *
            </label>
            <div 
              onClick={() => setApiKeyServiceDropdown(!apiKeyServiceDropdown)}
              className="w-full px-4 py-2 rounded-xl cursor-pointer flex items-center justify-between border-0"
              style={{ backgroundColor: 'white', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}
            >
              <span style={{ color: newApiKey.service ? colors.text : colors.textMuted }}>
                {newApiKey.service 
                  ? (apiKeysData.services?.find(s => s.id === newApiKey.service)?.name || newApiKey.service)
                  : 'Select service...'}
              </span>
              <ChevronRight 
                size={16} 
                style={{ 
                  color: colors.textMuted,
                  transform: apiKeyServiceDropdown ? 'rotate(90deg)' : 'rotate(0deg)',
                  transition: 'transform 0.2s ease'
                }} 
              />
            </div>
            {apiKeyServiceDropdown && (
              <div 
                className="absolute top-full left-0 right-0 mt-1 rounded-xl z-50 overflow-hidden max-h-60 overflow-y-auto border-0"
                style={{ backgroundColor: 'white', boxShadow: '0 4px 20px rgba(0,0,0,0.15)' }}
              >
                {apiKeysData.services?.map((service) => (
                  <div
                    key={service.id}
                    onClick={() => {
                      setNewApiKey({...newApiKey, service: service.id});
                      setApiKeyServiceDropdown(false);
                    }}
                    className="px-4 py-2.5 cursor-pointer transition-all flex items-center gap-2"
                    style={{ 
                      backgroundColor: newApiKey.service === service.id ? colors.accentSoft : 'white',
                      color: newApiKey.service === service.id ? colors.accent : colors.text
                    }}
                    onMouseEnter={(e) => e.target.style.backgroundColor = colors.surface}
                    onMouseLeave={(e) => e.target.style.backgroundColor = newApiKey.service === service.id ? colors.accentSoft : 'white'}
                  >
                    {newApiKey.service === service.id && (
                      <CheckCircle size={14} style={{ color: colors.accent }} />
                    )}
                    <span className="font-medium">{service.name}</span>
                    {service.key_required && (
                      <span className="text-xs px-1.5 py-0.5 rounded" style={{ backgroundColor: colors.warningSoft, color: colors.warning }}>
                        Key required
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
          
          {/* API Key input */}
          <div className="col-span-3">
            <label className="text-sm mb-1 block" style={{ color: colors.textSecondary }}>
              API Key *
            </label>
            <input
              type="text"
              value={newApiKey.api_key}
              onChange={(e) => setNewApiKey({...newApiKey, api_key: e.target.value})}
              placeholder="Enter your API key"
              className="w-full px-4 py-2 rounded-xl border-0"
              style={{ backgroundColor: 'white', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}
            />
          </div>
          
          {/* Pro checkbox */}
          <div className="flex items-end">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={newApiKey.is_pro}
                onChange={(e) => setNewApiKey({...newApiKey, is_pro: e.target.checked})}
                className="w-4 h-4 rounded"
              />
              <span className="text-sm" style={{ color: colors.textSecondary }}>Pro tier</span>
            </label>
          </div>
        </div>
        
        <div className="grid grid-cols-6 gap-4">
          {/* Name */}
          <div className="col-span-2">
            <label className="text-sm mb-1 block" style={{ color: colors.textSecondary }}>
              Friendly Name (optional)
            </label>
            <input
              type="text"
              value={newApiKey.name}
              onChange={(e) => setNewApiKey({...newApiKey, name: e.target.value})}
              placeholder="e.g. My CoinGecko Key #1"
              className="w-full px-4 py-2 rounded-xl border-0"
              style={{ backgroundColor: 'white', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}
            />
          </div>
          
          {/* Proxy Binding */}
          <div className="col-span-2">
            <label className="text-sm mb-1 block" style={{ color: colors.textSecondary }}>
              Bind to Proxy (optional)
            </label>
            <select
              value={newApiKey.proxy_id || ''}
              onChange={(e) => setNewApiKey({...newApiKey, proxy_id: e.target.value || null})}
              className="w-full px-4 py-2 rounded-xl border-0 appearance-none cursor-pointer"
              style={{ backgroundColor: 'white', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}
            >
              <option value="">Direct (no proxy)</option>
              {proxyStatus?.proxies?.filter(p => p.enabled).sort((a, b) => a.priority - b.priority).map((proxy, idx) => (
                <option key={proxy.id} value={proxy.id}>
                  {proxy.server} (Priority: {proxy.priority})
                </option>
              ))}
            </select>
          </div>
          
          {/* Add button */}
          <div className="col-span-2 flex items-end">
            <button
              onClick={addApiKey}
              disabled={!newApiKey.api_key || !newApiKey.service || apiKeysLoading}
              className="w-full py-2 rounded-xl font-medium transition-all flex items-center justify-center gap-2"
              style={{ 
                backgroundColor: (newApiKey.api_key && newApiKey.service) ? colors.accent : colors.surface, 
                color: (newApiKey.api_key && newApiKey.service) ? 'white' : colors.textMuted 
              }}
            >
              <Plus size={16} />
              Add API Key
            </button>
          </div>
        </div>
      </div>

      {/* API Keys List */}
      <div 
        className="bg-white rounded-2xl border p-6"
        style={{ borderColor: colors.border }}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold flex items-center gap-2" style={{ color: colors.text }}>
            <Shield size={18} />
            Configured API Keys ({apiKeyServiceFilter 
              ? apiKeysData.keys?.filter(k => k.service === apiKeyServiceFilter).length 
              : apiKeysData.keys?.length || 0})
          </h3>
          {apiKeyServiceFilter && (
            <button
              onClick={() => setApiKeyServiceFilter(null)}
              className="text-sm px-3 py-1 rounded-lg transition-all"
              style={{ backgroundColor: colors.surface, color: colors.textSecondary }}
            >
              Show All Keys
            </button>
          )}
        </div>
        
        {(() => {
          const filteredKeys = apiKeyServiceFilter 
            ? apiKeysData.keys?.filter(k => k.service === apiKeyServiceFilter) 
            : apiKeysData.keys;
          
          if (!filteredKeys || filteredKeys.length === 0) {
            return (
              <div className="text-center py-8" style={{ color: colors.textSecondary }}>
                <Shield size={48} className="mx-auto mb-4 opacity-30" />
                <p>{apiKeyServiceFilter ? `No ${apiKeyServiceFilter} keys configured` : 'No API keys configured yet'}</p>
                <p className="text-sm">Add keys above to enable load-balanced API requests</p>
              </div>
            );
          }
          
          return (
            <div className="space-y-3">
              {filteredKeys.map((key) => (
              <div 
                key={key.id}
                className="border rounded-xl p-4 transition-all hover:shadow-md"
                style={{ 
                  borderColor: key.healthy ? colors.border : colors.error,
                  backgroundColor: !key.enabled ? colors.surface : 'white'
                }}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div 
                      className="w-10 h-10 rounded-xl flex items-center justify-center"
                      style={{ backgroundColor: key.healthy ? colors.successSoft : colors.errorSoft }}
                    >
                      {key.healthy ? (
                        <CheckCircle size={20} style={{ color: colors.success }} />
                      ) : (
                        <AlertTriangle size={20} style={{ color: colors.error }} />
                      )}
                    </div>
                    <div>
                      <p className="font-medium flex items-center gap-2 flex-wrap" style={{ color: colors.text }}>
                        {key.name}
                        <span className="text-xs px-2 py-0.5 rounded-full" 
                          style={{ backgroundColor: colors.accentSoft, color: colors.accent }}>
                          {key.service}
                        </span>
                        {key.is_pro && (
                          <span className="text-xs px-2 py-0.5 rounded-full" 
                            style={{ backgroundColor: colors.warningSoft, color: colors.warning }}>
                            PRO
                          </span>
                        )}
                        {key.proxy_id && (
                          <span className="text-xs px-2 py-0.5 rounded-full flex items-center gap-1" 
                            style={{ backgroundColor: colors.successSoft, color: colors.success }}>
                            <Server size={10} />
                            {proxyStatus?.proxies?.find(p => p.id === key.proxy_id)?.server || key.proxy_id}
                          </span>
                        )}
                        {!key.enabled && (
                          <span className="text-xs px-2 py-0.5 rounded-full" 
                            style={{ backgroundColor: colors.surface, color: colors.textMuted }}>
                            Disabled
                          </span>
                        )}
                      </p>
                      <p className="text-sm" style={{ color: colors.textSecondary }}>
                        Key: {key.api_key_masked} • 
                        Requests: {key.requests_total || 0} total, {key.requests_today || 0} today
                        {key.last_error_message && (
                          <span style={{ color: colors.error }}> • Error: {key.last_error_message.slice(0, 40)}...</span>
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {/* Usage indicator */}
                    <div className="text-right mr-4">
                      <div className="text-xs mb-1" style={{ color: colors.textSecondary }}>
                        {key.requests_this_minute || 0}/{key.rate_limit || 30} this min
                      </div>
                      <div className="w-24 h-2 rounded-full overflow-hidden" style={{ backgroundColor: colors.surface }}>
                        <div 
                          className="h-full rounded-full transition-all"
                          style={{ 
                            width: `${Math.min(100, ((key.requests_this_minute || 0) / (key.rate_limit || 30)) * 100)}%`,
                            backgroundColor: ((key.requests_this_minute || 0) / (key.rate_limit || 30)) > 0.8 
                              ? colors.warning 
                              : colors.success
                          }}
                        />
                      </div>
                    </div>
                    <button
                      onClick={() => checkApiKeyHealth(key.id)}
                      className="p-2 rounded-lg transition-all"
                      style={{ backgroundColor: colors.accentSoft }}
                      title="Test this key"
                    >
                      <Activity size={16} style={{ color: colors.accent }} />
                    </button>
                    <button
                      onClick={() => toggleApiKey(key.id, !key.enabled)}
                      className="p-2 rounded-lg transition-all"
                      style={{ backgroundColor: key.enabled ? colors.warningSoft : colors.successSoft }}
                      title={key.enabled ? 'Disable' : 'Enable'}
                    >
                      {key.enabled ? (
                        <XCircle size={16} style={{ color: colors.warning }} />
                      ) : (
                        <CheckCircle size={16} style={{ color: colors.success }} />
                      )}
                    </button>
                    <button
                      onClick={() => removeApiKey(key.id)}
                      className="p-2 rounded-lg transition-all"
                      style={{ backgroundColor: colors.errorSoft }}
                      title="Удалить"
                    >
                      <Trash2 size={16} style={{ color: colors.error }} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
          );
        })()}
      </div>

      {/* Info Box */}
      <div 
        className="rounded-2xl p-6"
        style={{ backgroundColor: colors.accentSoft }}
      >
        <h4 className="font-medium mb-2" style={{ color: colors.accent }}>
          How API Key Load Balancing Works
        </h4>
        <ul className="text-sm space-y-1" style={{ color: colors.text }}>
          <li>• Multiple keys per service distribute requests to avoid rate limits</li>
          <li>• Keys with most remaining capacity are used first (smart rotation)</li>
          <li>• Unhealthy keys are automatically skipped after 3 consecutive errors</li>
          <li>• Counters reset: per-minute automatically, per-day at midnight UTC</li>
          <li>• Free tier limits: CoinGecko 30/min, CoinMarketCap 333/day, Messari 20/min</li>
        </ul>
      </div>
    </div>
  );

  // Render Merge Candidates UI
  const renderMergeCandidates = () => (
    <div className="space-y-6">
      {/* Stats */}
      {mergeStats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-2xl border p-5" style={{ borderColor: colors.border }}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm" style={{ color: colors.textSecondary }}>Pending Candidates</p>
                <p className="text-2xl font-bold" style={{ color: colors.accent }}>{mergeStats.pending || 0}</p>
              </div>
              <Network size={24} style={{ color: colors.accent }} />
            </div>
          </div>
          <div className="bg-white rounded-2xl border p-5" style={{ borderColor: colors.border }}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm" style={{ color: colors.textSecondary }}>Merged Today</p>
                <p className="text-2xl font-bold" style={{ color: colors.success }}>{mergeStats.merged_today || 0}</p>
              </div>
              <CheckCircle size={24} style={{ color: colors.success }} />
            </div>
          </div>
          <div className="bg-white rounded-2xl border p-5" style={{ borderColor: colors.border }}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm" style={{ color: colors.textSecondary }}>Total Merged</p>
                <p className="text-2xl font-bold" style={{ color: colors.text }}>{mergeStats.total_merged || 0}</p>
              </div>
              <Database size={24} style={{ color: colors.textSecondary }} />
            </div>
          </div>
          <div className="bg-white rounded-2xl border p-5" style={{ borderColor: colors.border }}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm" style={{ color: colors.textSecondary }}>Dismissed</p>
                <p className="text-2xl font-bold" style={{ color: colors.warning }}>{mergeStats.dismissed || 0}</p>
              </div>
              <XCircle size={24} style={{ color: colors.warning }} />
            </div>
          </div>
        </div>
      )}

      {/* Candidates List */}
      <div className="bg-white rounded-2xl border" style={{ borderColor: colors.border }}>
        <div className="p-6 border-b" style={{ borderColor: colors.border }}>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold" style={{ color: colors.text }}>Кандидаты на объединение</h3>
              <p className="text-sm" style={{ color: colors.textSecondary }}>
                Entities that may be duplicates. Review and merge or dismiss.
              </p>
            </div>
            <button
              onClick={fetchMergeCandidates}
              className="flex items-center gap-2 px-4 py-2 rounded-xl border"
              style={{ borderColor: colors.border }}
            >
              <RefreshCw size={16} className={mergeLoading ? 'animate-spin' : ''} />
              Refresh
            </button>
          </div>
        </div>

        <div className="divide-y" style={{ borderColor: colors.borderLight }}>
          {mergeLoading ? (
            <div className="p-12 text-center">
              <RefreshCw className="animate-spin mx-auto mb-4" size={24} style={{ color: colors.accent }} />
              <p style={{ color: colors.textSecondary }}>Loading candidates...</p>
            </div>
          ) : mergeCandidates.length === 0 ? (
            <div className="p-12 text-center">
              <CheckCircle size={48} className="mx-auto mb-4" style={{ color: colors.success }} />
              <p className="font-medium" style={{ color: colors.text }}>No merge candidates</p>
              <p className="text-sm" style={{ color: colors.textSecondary }}>All entities are unique!</p>
            </div>
          ) : (
            mergeCandidates.map((candidate, idx) => (
              <div key={candidate.id || idx} className="p-6 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-4 mb-2">
                      {/* Entity 1 */}
                      <div className="flex-1 p-3 rounded-xl" style={{ backgroundColor: colors.surface }}>
                        <p className="font-medium" style={{ color: colors.text }}>{candidate.entity1?.label || candidate.source_label}</p>
                        <p className="text-xs" style={{ color: colors.textMuted }}>{candidate.entity1?.id || candidate.source_id}</p>
                        <p className="text-xs mt-1" style={{ color: colors.textSecondary }}>
                          Type: {candidate.entity1?.entity_type || candidate.source_type}
                        </p>
                      </div>
                      
                      {/* Arrow */}
                      <div className="flex flex-col items-center">
                        <ChevronRight size={20} style={{ color: colors.textMuted }} />
                        <span className="text-xs" style={{ color: colors.accent }}>
                          {Math.round((candidate.confidence || candidate.similarity || 0.9) * 100)}% match
                        </span>
                      </div>
                      
                      {/* Entity 2 */}
                      <div className="flex-1 p-3 rounded-xl" style={{ backgroundColor: '#ecfdf5' }}>
                        <p className="font-medium" style={{ color: colors.success }}>{candidate.entity2?.label || candidate.target_label}</p>
                        <p className="text-xs" style={{ color: colors.textMuted }}>{candidate.entity2?.id || candidate.target_id}</p>
                        <p className="text-xs mt-1" style={{ color: colors.textSecondary }}>
                          Type: {candidate.entity2?.entity_type || candidate.target_type}
                        </p>
                      </div>
                    </div>
                    
                    {candidate.reason && (
                      <p className="text-xs mt-2" style={{ color: colors.textMuted }}>
                        Reason: {candidate.reason}
                      </p>
                    )}
                  </div>
                  
                  {/* Actions */}
                  <div className="flex items-center gap-2 ml-4">
                    <button
                      onClick={() => executeMerge(
                        candidate.entity1?.id || candidate.source_id,
                        candidate.entity2?.id || candidate.target_id
                      )}
                      className="px-4 py-2 rounded-xl font-medium transition-all hover:shadow-md"
                      style={{ backgroundColor: colors.success, color: 'white' }}
                    >
                      Merge
                    </button>
                    <button
                      onClick={() => dismissMergeCandidate(candidate.id)}
                      className="px-4 py-2 rounded-xl border transition-all hover:bg-gray-50"
                      style={{ borderColor: colors.border, color: colors.textSecondary }}
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Info Box */}
      <div 
        className="p-4 rounded-xl"
        style={{ backgroundColor: '#fdf4ff', border: '1px solid #f0abfc' }}
      >
        <h4 className="font-medium mb-2" style={{ color: '#c026d3' }}>
          How Entity Merging Works
        </h4>
        <ul className="text-sm space-y-1" style={{ color: colors.text }}>
          <li>• Merge combines two duplicate entities into one canonical entity</li>
          <li>• All relationships are transferred to the target entity</li>
          <li>• Aliases from the source are added to the target</li>
          <li>• The source entity is marked as merged and hidden from searches</li>
        </ul>
      </div>
    </div>
  );

  // ── Profile Tab Component ──────────────────────────────────────
  const ProfileTab = () => {
    const [passwordForm, setPasswordForm] = useState({
      currentPassword: '',
      newPassword: '',
      confirmPassword: '',
    });
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(null);

    const handleChangePassword = async (e) => {
      e.preventDefault();
      setError(null);
      setSuccess(null);
      if (passwordForm.newPassword.length < 8) { setError('Пароль минимум 8 символов'); return; }
      if (passwordForm.newPassword !== passwordForm.confirmPassword) { setError('Пароли не совпадают'); return; }
      setSaving(true);
      try {
        const token = localStorage.getItem('admin_token');
        const res = await fetch(`${API_URL}/api/admin/auth/change-password`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ currentPassword: passwordForm.currentPassword, newPassword: passwordForm.newPassword }),
        });
        const data = await res.json();
        if (data.ok) {
          setSuccess('Пароль изменён');
          setPasswordForm({ currentPassword: '', newPassword: '', confirmPassword: '' });
        } else { setError(data.message || 'Ошибка'); }
      } catch (err) { setError(err.response?.data?.message || 'Ошибка'); }
      finally { setSaving(false); }
    };

    return (
      <div className="space-y-6" data-testid="intel-profile-tab">
        {/* Account Info */}
        <div className="rounded-lg border border-slate-200 p-5">
          <h3 className="text-sm font-semibold text-slate-900 mb-4">Account Information</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between py-2 border-b border-slate-100">
              <span className="text-sm text-slate-500">Username</span>
              <span className="text-sm font-medium text-slate-900">admin</span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-slate-100">
              <span className="text-sm text-slate-500">Role</span>
              <span className="text-xs font-medium text-slate-600">ADMIN</span>
            </div>
          </div>
        </div>

        {/* Change Password */}
        <div className="rounded-lg border border-slate-200 p-5">
          <h3 className="text-sm font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <Key className="w-4 h-4 text-amber-600" />
            Change Password
          </h3>
          {error && <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center gap-2"><AlertTriangle className="w-4 h-4" />{error}</div>}
          {success && <div className="mb-3 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700 flex items-center gap-2"><CheckCircle className="w-4 h-4" />{success}</div>}
          <form onSubmit={handleChangePassword} className="space-y-3">
            <div>
              <label className="text-xs text-slate-500">Current Password</label>
              <input type="password" value={passwordForm.currentPassword}
                onChange={e => setPasswordForm({ ...passwordForm, currentPassword: e.target.value })}
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-slate-400"
                placeholder="Enter current password" required data-testid="current-password" />
            </div>
            <div>
              <label className="text-xs text-slate-500">New Password</label>
              <input type="password" value={passwordForm.newPassword}
                onChange={e => setPasswordForm({ ...passwordForm, newPassword: e.target.value })}
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-slate-400"
                placeholder="Min 8 characters" required minLength={8} data-testid="new-password" />
            </div>
            <div>
              <label className="text-xs text-slate-500">Confirm Password</label>
              <input type="password" value={passwordForm.confirmPassword}
                onChange={e => setPasswordForm({ ...passwordForm, confirmPassword: e.target.value })}
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-slate-400"
                placeholder="Confirm new password" required data-testid="confirm-password" />
            </div>
            <button type="submit" disabled={saving} data-testid="change-password-btn"
              className="w-full py-2 rounded-lg text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 transition-colors">
              {saving ? 'Сохранение...' : 'Change Password'}
            </button>
          </form>
        </div>
      </div>
    );
  };

  // Main Admin render
  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center gap-3">
            <Shield size={24} className="text-indigo-600" />
            <div>
              <h1 className="text-2xl font-bold text-slate-900">Intel System</h1>
              <p className="text-sm text-slate-500">Управление прокси, ключами, провайдерами и системой обнаружения</p>
            </div>
          </div>
        </div>

    <div className="space-y-6">
      {/* Sub-tabs */}
      <div className="flex gap-4 border-b pb-4 flex-wrap" style={{ borderColor: colors.border }}>
        <button
          onClick={() => setAdminSubTab('proxy')}
          className="px-4 py-2 rounded-xl font-medium transition-all"
          style={{
            backgroundColor: adminSubTab === 'proxy' ? colors.accent : colors.surface,
            color: adminSubTab === 'proxy' ? 'white' : colors.textSecondary
          }}
        >
          <Server size={16} className="inline mr-2" />
          Proxy Pool
        </button>
        <button
          onClick={() => setAdminSubTab('api-keys')}
          className="px-4 py-2 rounded-xl font-medium transition-all"
          style={{
            backgroundColor: adminSubTab === 'api-keys' ? colors.accent : colors.surface,
            color: adminSubTab === 'api-keys' ? 'white' : colors.textSecondary
          }}
        >
          <Key size={16} className="inline mr-2" />
          API Keys
        </button>
        <button
          onClick={() => { setAdminSubTab('llm-keys'); fetchLlmKeys(); }}
          data-testid="admin-llm-keys-tab"
          className="px-4 py-2 rounded-xl font-medium transition-all"
          style={{
            backgroundColor: adminSubTab === 'llm-keys' ? '#8b5cf6' : colors.surface,
            color: adminSubTab === 'llm-keys' ? 'white' : colors.textSecondary
          }}
        >
          <Zap size={16} className="inline mr-2" />
          LLM Keys
        </button>
        <button
          onClick={() => { setAdminSubTab('sentiment-keys'); fetchSentimentKeys(); fetchSentimentProviders(); }}
          data-testid="admin-sentiment-keys-tab"
          className="px-4 py-2 rounded-xl font-medium transition-all"
          style={{
            backgroundColor: adminSubTab === 'sentiment-keys' ? '#06b6d4' : colors.surface,
            color: adminSubTab === 'sentiment-keys' ? 'white' : colors.textSecondary
          }}
        >
          <BarChart2 size={16} className="inline mr-2" />
          Sentiment
        </button>
        <button
          onClick={() => setAdminSubTab('providers')}
          className="px-4 py-2 rounded-xl font-medium transition-all"
          style={{
            backgroundColor: adminSubTab === 'providers' ? colors.accent : colors.surface,
            color: adminSubTab === 'providers' ? 'white' : colors.textSecondary
          }}
        >
          <Layers size={16} className="inline mr-2" />
          Provider Pool
        </button>
        <button
          onClick={() => setAdminSubTab('health')}
          className="px-4 py-2 rounded-xl font-medium transition-all"
          style={{
            backgroundColor: adminSubTab === 'health' ? colors.accent : colors.surface,
            color: adminSubTab === 'health' ? 'white' : colors.textSecondary
          }}
        >
          <Activity size={16} className="inline mr-2" />
          Health Monitor
        </button>
        <button
          onClick={() => setAdminSubTab('discovery')}
          className="px-4 py-2 rounded-xl font-medium transition-all"
          data-testid="admin-discovery-tab"
          style={{
            backgroundColor: adminSubTab === 'discovery' ? colors.accent : colors.surface,
            color: adminSubTab === 'discovery' ? 'white' : colors.textSecondary
          }}
        >
          <Globe size={16} className="inline mr-2" />
          Discovery System
        </button>
        <button
          onClick={() => { setAdminSubTab('webhooks'); fetchWebhooks(); }}
          className="px-4 py-2 rounded-xl font-medium transition-all"
          data-testid="admin-webhooks-tab"
          style={{
            backgroundColor: adminSubTab === 'webhooks' ? '#f97316' : colors.surface,
            color: adminSubTab === 'webhooks' ? 'white' : colors.textSecondary
          }}
        >
          <Wifi size={16} className="inline mr-2" />
          Webhooks
        </button>
        <button
          onClick={() => { setAdminSubTab('merge'); fetchMergeCandidates(); }}
          className="px-4 py-2 rounded-xl font-medium transition-all"
          data-testid="admin-merge-tab"
          style={{
            backgroundColor: adminSubTab === 'merge' ? '#ec4899' : colors.surface,
            color: adminSubTab === 'merge' ? 'white' : colors.textSecondary
          }}
        >
          <Network size={16} className="inline mr-2" />
          Entity Merge
        </button>
        <button
          onClick={() => setAdminSubTab('profile')}
          className="px-4 py-2 rounded-xl font-medium transition-all"
          data-testid="admin-profile-tab"
          style={{
            backgroundColor: adminSubTab === 'profile' ? '#475569' : colors.surface,
            color: adminSubTab === 'profile' ? 'white' : colors.textSecondary
          }}
        >
          <UserCog size={16} className="inline mr-2" />
          Profile
        </button>
      </div>

      {adminSubTab === 'proxy' && renderProxyAdmin()}
      {adminSubTab === 'api-keys' && renderApiKeysAdmin()}
      {adminSubTab === 'llm-keys' && renderLlmKeysAdmin()}
      {adminSubTab === 'sentiment-keys' && renderSentimentKeysAdmin()}
      {adminSubTab === 'providers' && renderProviderPool()}
      {adminSubTab === 'health' && renderHealthMonitor()}
      {adminSubTab === 'discovery' && renderDiscoveryDashboard()}
      {adminSubTab === 'webhooks' && renderWebhooksAdmin()}
      {adminSubTab === 'merge' && renderMergeCandidates()}
      {adminSubTab === 'profile' && <ProfileTab />}
    </div>
      </div>
    </AdminLayout>
  );
}

