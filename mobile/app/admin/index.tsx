import { Redirect } from 'expo-router';
import React from 'react';
import { useAdminAuth } from '../../src/admin/auth/AdminAuthContext';

export default function AdminIndex() {
  const { ready, authenticated } = useAdminAuth();
  if (!ready) return null;
  return authenticated
    ? <Redirect href="/admin/operators" />
    : <Redirect href="/admin/login" />;
}
