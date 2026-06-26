import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useCurrentAdmin } from '../hooks';
import { useAuthStore } from '../stores/authStore';

export function AuthGuard({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  const location = useLocation();
  const { data: admin, isLoading } = useCurrentAdmin();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (isLoading) {
    return <div className="min-h-screen" />;
  }

  if (admin?.must_change_credentials && location.pathname !== '/setup') {
    return <Navigate to="/setup" replace />;
  }

  if (admin && !admin.must_change_credentials && location.pathname === '/setup') {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}
