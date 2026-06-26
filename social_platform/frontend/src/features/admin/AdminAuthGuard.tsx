import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useCurrentAdmin, useAdminAuthStore } from '@/features/admin';

export function AdminAuthGuard() {
  const location = useLocation();
  const isAuthenticated = useAdminAuthStore(state => state.isAuthenticated);
  const { data: admin, isLoading } = useCurrentAdmin();

  if (!isAuthenticated) {
    return <Navigate to="/admin/login" replace state={{ from: location }} />;
  }

  if (isLoading) {
    return <div className="min-h-screen" />;
  }

  if (admin?.must_change_credentials && location.pathname !== '/admin/setup') {
    return <Navigate to="/admin/setup" replace />;
  }

  return <Outlet />;
}
