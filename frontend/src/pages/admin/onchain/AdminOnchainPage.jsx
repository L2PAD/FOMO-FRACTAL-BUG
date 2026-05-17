/**
 * On-Chain Admin Dashboard — Tabbed Interface
 * ==============================================
 * Полноценная админка on-chain модуля.
 * 
 * Табы:
 *  - Обзор (Overview) — системный статус
 *  - Движок (Engine) — состояние движка
 *  - Инфраструктура (Infrastructure) — RPC, индексер, снапшоты
 *  - Управление (Governance) — drift, policy, guardrails
 *  - Исследования (Research) — observation model, ML
 *  - Валидация (Validation) — проверка корректности данных
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import AdminLayout from '../../../components/admin/AdminLayout';
import { useAdminAuth } from '../../../context/AdminAuthContext';
import {
  Activity, Zap, Server, Shield, FlaskConical, CheckSquare,
  RefreshCw, Loader2,
} from 'lucide-react';

import OverviewTab from './components/OverviewTab';
import EngineTab from './components/EngineTab';
import InfrastructureTab from './components/InfrastructureTab';
import GovernanceTab from './components/GovernanceTab';
import ResearchTab from './components/ResearchTab';
import ValidationTab from './components/ValidationTab';

const API = process.env.REACT_APP_BACKEND_URL;

const TABS = [
  { id: 'overview', label: 'Обзор', icon: Activity },
  { id: 'engine', label: 'Движок', icon: Zap },
  { id: 'infrastructure', label: 'Инфраструктура', icon: Server },
  { id: 'governance', label: 'Управление', icon: Shield },
  { id: 'research', label: 'Исследования', icon: FlaskConical },
  { id: 'validation', label: 'Валидация', icon: CheckSquare },
];

export default function AdminOnchainPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { isAuthenticated, loading: authLoading } = useAdminAuth();

  const activeTab = searchParams.get('tab') || 'overview';

  const [runtime, setRuntime] = useState(null);
  const [govState, setGovState] = useState(null);
  const [indexerStatus, setIndexerStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [rtRes, govRes, idxRes] = await Promise.allSettled([
        fetch(`${API}/api/v10/onchain-v2/admin/runtime`).then(r => r.json()),
        fetch(`${API}/api/v10/onchain-v2/admin/governance/state`).then(r => r.json()),
        fetch(`${API}/api/admin/indexer/status`).then(r => r.json()),
      ]);
      if (rtRes.status === 'fulfilled' && rtRes.value.ok) setRuntime(rtRes.value);
      if (govRes.status === 'fulfilled' && govRes.value.ok) setGovState(govRes.value);
      if (idxRes.status === 'fulfilled' && idxRes.value.ok) setIndexerStatus(idxRes.value);
    } catch (e) {
      console.error('[OnchainAdmin] Fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      navigate('/admin/login', { replace: true });
      return;
    }
    if (!authLoading && isAuthenticated) fetchAll();
  }, [authLoading, isAuthenticated, navigate, fetchAll]);

  useEffect(() => {
    const id = setInterval(fetchAll, 30_000);
    return () => clearInterval(id);
  }, [fetchAll]);

  const setTab = (tabId) => {
    setSearchParams({ tab: tabId });
  };

  if (authLoading) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center h-32">
          <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
        </div>
      </AdminLayout>
    );
  }

  const renderTab = () => {
    switch (activeTab) {
      case 'overview':
        return <OverviewTab runtime={runtime} govState={govState} indexerStatus={indexerStatus} loading={loading} />;
      case 'engine':
        return <EngineTab runtime={runtime} loading={loading} onRefresh={fetchAll} />;
      case 'infrastructure':
        return <InfrastructureTab runtime={runtime} />;
      case 'governance':
        return <GovernanceTab govState={govState} onRefresh={fetchAll} />;
      case 'research':
        return <ResearchTab />;
      case 'validation':
        return <ValidationTab />;
      default:
        return <OverviewTab runtime={runtime} govState={govState} indexerStatus={indexerStatus} loading={loading} />;
    }
  };

  return (
    <AdminLayout>
      <div className="space-y-6" data-testid="onchain-admin-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity className="w-5 h-5 text-indigo-600" />
            <div>
              <h1 className="text-xl font-semibold text-slate-900">On-Chain</h1>
              <p className="text-xs text-gray-500">
                Ethereum Mainnet · Admin Dashboard
              </p>
            </div>
          </div>
          <button
            onClick={fetchAll}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            data-testid="onchain-refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Обновить
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-1 border-b border-slate-200 overflow-x-auto" data-testid="onchain-tabs">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              data-testid={`tab-${id}`}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                activeTab === id
                  ? 'text-indigo-600 border-indigo-600'
                  : 'text-slate-500 border-transparent hover:text-slate-700 hover:border-slate-300'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div data-testid={`tab-content-${activeTab}`}>
          {renderTab()}
        </div>
      </div>
    </AdminLayout>
  );
}
