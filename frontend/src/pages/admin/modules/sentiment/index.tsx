import React from "react";
import SentimentAdminDashboard from "./SentimentAdminDashboard";
import AdminLayout from "../../../../components/admin/AdminLayout";

export default function SentimentModuleAdminPage() {
  return (
    <AdminLayout>
      <SentimentAdminDashboard />
    </AdminLayout>
  );
}
