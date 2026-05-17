/**
 * Twitter Admin — Unified Control Page
 * ======================================
 *
 * 5-tab architecture:
 *   Overview → Parser → Governance → ML → Connections
 *
 * Parser infrastructure is NOT changed — only overview + links.
 * Connections module is NOT changed — only adapter status.
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminLayout from '../../../components/admin/AdminLayout';
import { useAdminAuth } from '../../../context/AdminAuthContext';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../../components/ui/tabs';
import { RefreshCw, Loader2 } from 'lucide-react';

import TwitterOverviewTab from './components/TwitterOverviewTab';
import TwitterParserTab from './components/TwitterParserTab';
import TwitterGovernanceTab from './components/TwitterGovernanceTab';
import TwitterMLTab from './components/TwitterMLTab';
import TwitterConnectionsTab from './components/TwitterConnectionsTab';
import TwitterStabilityTab from './components/TwitterStabilityTab';

export default function AdminTwitterUnifiedPage() {
  const navigate = useNavigate();
  const { isAuthenticated, loading: authLoading } = useAdminAuth();
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      navigate('/admin/login', { replace: true });
    }
  }, [authLoading, isAuthenticated, navigate]);

  if (authLoading) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6 space-y-6" data-testid="admin-twitter-unified-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-900" data-testid="twitter-page-title">
              Twitter
            </h1>
            <p className="text-sm text-slate-400 mt-0.5">Парсинг, политики, ML pipeline</p>
          </div>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="bg-slate-100/80 p-1 rounded-lg" data-testid="twitter-tabs">
            <TabsTrigger value="overview" data-testid="tab-tw-overview">Обзор</TabsTrigger>
            <TabsTrigger value="parser" data-testid="tab-tw-parser">Парсер</TabsTrigger>
            <TabsTrigger value="governance" data-testid="tab-tw-governance">Политики</TabsTrigger>
            <TabsTrigger value="ml" data-testid="tab-tw-ml">ML</TabsTrigger>
            <TabsTrigger value="connections" data-testid="tab-tw-connections">Адаптер</TabsTrigger>
            <TabsTrigger value="stability" data-testid="tab-tw-stability">Мониторинг</TabsTrigger>
          </TabsList>

          <div className="mt-6">
            <TabsContent value="overview">
              <TwitterOverviewTab />
            </TabsContent>

            <TabsContent value="parser">
              <TwitterParserTab />
            </TabsContent>

            <TabsContent value="governance">
              <TwitterGovernanceTab />
            </TabsContent>

            <TabsContent value="ml">
              <TwitterMLTab />
            </TabsContent>

            <TabsContent value="connections">
              <TwitterConnectionsTab />
            </TabsContent>

            <TabsContent value="stability">
              <TwitterStabilityTab />
            </TabsContent>
          </div>
        </Tabs>
      </div>
    </AdminLayout>
  );
}
