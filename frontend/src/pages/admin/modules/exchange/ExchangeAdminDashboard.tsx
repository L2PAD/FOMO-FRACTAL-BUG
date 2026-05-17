/**
 * Exchange Admin Dashboard
 * =========================
 * 
 * BLOCK E6: Production-grade admin dashboard
 * 1:1 parity with Sentiment Admin
 */

import React from 'react';
import { useExchangeAdminStatus } from './hooks/useExchangeStatus';
import LoadingCard from './components/LoadingCard';
import ErrorCard from './components/ErrorCard';
import HeaderStrip from './components/panels/HeaderStrip';
import UriPanel from './components/panels/UriPanel';
import DataHealthPanel from './components/panels/DataHealthPanel';
import DriftPanel from './components/panels/DriftPanel';
import CapitalPanel from './components/panels/CapitalPanel';
import LifecyclePanel from './components/panels/LifecyclePanel';
import CalibrationPanel from './components/panels/CalibrationPanel';
import GuardActionsPanel from './components/panels/GuardActionsPanel';
import EvidencePanel from './components/panels/EvidencePanel';
import FeatureLockPanel from './components/panels/FeatureLockPanel';
import ManualActionsPanel from './components/panels/ManualActionsPanel';
import ModelHealthPanel from '../../../../components/prediction/ModelHealthPanel';

export default function ExchangeAdminDashboard() {
  const { data, error, isLoading, refetch } = useExchangeAdminStatus({ pollMs: 15000 });

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-7xl mx-auto space-y-4">
          <LoadingCard title="Exchange Admin" />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <LoadingCard title="URI" />
            <LoadingCard title="Guard Actions" />
            <LoadingCard title="Data Health" />
            <LoadingCard title="Drift" />
          </div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-7xl mx-auto">
          <ErrorCard 
            title="Failed to load Exchange Admin" 
            message={error?.message || 'No data received'} 
            onRetry={refetch} 
          />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-4">
        {/* Header */}
        <HeaderStrip snapshot={data} />

        {/* ML Model Health — full width */}
        <ModelHealthPanel asset="BTC" />

        {/* Row 1: URI + Guard Actions */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <UriPanel snapshot={data} />
          <GuardActionsPanel snapshot={data} />
        </div>

        {/* Row 2: Data Health + Drift */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <DataHealthPanel snapshot={data} />
          <DriftPanel snapshot={data} />
        </div>

        {/* Row 3: Capital + Lifecycle */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <CapitalPanel snapshot={data} />
          <LifecyclePanel snapshot={data} />
        </div>

        {/* Row 4: Calibration + Feature Lock */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <CalibrationPanel snapshot={data} />
          <FeatureLockPanel snapshot={data} />
        </div>

        {/* Row 5: Evidence + Manual Actions */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <EvidencePanel snapshot={data} />
          <ManualActionsPanel onActionComplete={refetch} />
        </div>

        {/* Footer */}
        <div className="text-center text-xs text-gray-400 py-4">
          Auto-refresh every 15 seconds • Last update: {new Date().toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}
