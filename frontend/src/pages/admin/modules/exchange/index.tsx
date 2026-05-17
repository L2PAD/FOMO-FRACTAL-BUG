/**
 * Exchange Admin Page Entry
 * ==========================
 * 
 * BLOCK E6: Route entry for /admin/modules/exchange
 */

import ExchangeAdminDashboard from './ExchangeAdminDashboard';
import AdminLayout from '../../../../components/admin/AdminLayout';

export default function ExchangeAdminPage() {
  return (
    <AdminLayout>
      <ExchangeAdminDashboard />
    </AdminLayout>
  );
}
