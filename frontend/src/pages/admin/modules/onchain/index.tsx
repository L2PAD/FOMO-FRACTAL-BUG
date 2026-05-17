import React from 'react';
import OnchainAdminDashboard from './OnchainAdminDashboard';
import AdminLayout from '../../../../components/admin/AdminLayout';

export default function OnchainModuleAdminPage() {
  return (
    <AdminLayout>
      <OnchainAdminDashboard />
    </AdminLayout>
  );
}
