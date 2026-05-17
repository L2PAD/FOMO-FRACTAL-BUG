/**
 * /admin/_layout — hard environmental boundary + admin auth provider.
 *
 * Three architectural invariants enforced here:
 *
 *   1. Hard native block: on Platform.OS !== 'web' we render NativeBlock
 *      and DO NOT render children.  This means AdminAuthProvider is
 *      never instantiated on native; adminClient interceptors never
 *      run; no admin fetches happen.
 *
 *   2. Isolated auth context: AdminAuthProvider is mounted ONLY here
 *      and never visible to the customer-app tree.  No global store
 *      access, no shared session.store hookup.
 *
 *   3. Routing skeleton: Stack-based navigation between login / users /
 *      operators / operators/[userId] is set up early so the routes are
 *      stable while 3C fills in detail-page logic.
 */
import React, { useEffect } from 'react';
import { Platform, View, StyleSheet } from 'react-native';
import { Stack, usePathname, useRouter } from 'expo-router';
import {
  AdminAuthProvider,
  useAdminAuth,
} from '../../src/admin/auth/AdminAuthContext';
import { bindAdminAuth } from '../../src/admin/api/adminClient';
import { NativeBlock } from '../../src/admin/NativeBlock';
import { QuarantineBanner } from '../../src/admin/QuarantineBanner';

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { ready, authenticated, getSecret, touch } = useAdminAuth();
  const pathname = usePathname();
  const router = useRouter();

  // Wire the adminClient interceptor to this provider's getters.
  useEffect(() => {
    bindAdminAuth(getSecret, touch);
  }, [getSecret, touch]);

  // Touch activity on every route change inside /admin.
  useEffect(() => {
    if (authenticated) touch();
  }, [pathname, authenticated, touch]);

  useEffect(() => {
    if (!ready) return;
    const onLogin = pathname === '/admin/login';
    if (!authenticated && !onLogin) {
      router.replace('/admin/login');
    } else if (authenticated && onLogin) {
      router.replace('/admin/operators');
    }
  }, [ready, authenticated, pathname, router]);

  return <>{children}</>;
}

export default function AdminLayout() {
  // Invariant 1: never mount admin children on native.  AdminAuthProvider
  // and adminClient are not even imported into the running tree here —
  // they're imported above, but never executed when we early-return below.
  if (Platform.OS !== 'web') {
    return <NativeBlock />;
  }

  return (
    <AdminAuthProvider>
      <AuthGuard>
        <View style={layoutStyles.root}>
          <QuarantineBanner />
          <View style={layoutStyles.body}>
            <Stack screenOptions={{ headerShown: false }} />
          </View>
        </View>
      </AuthGuard>
    </AdminAuthProvider>
  );
}

const layoutStyles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#ffffff' },
  body: { flex: 1 },
});
