import { Navigate, useLocation } from 'react-router-dom';
import { useCurrentAdmin } from '../hooks';
import { useAuthStore } from '../stores/authStore';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  const location = useLocation();
  const { isLoading } = useCurrentAdmin();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (isLoading) {
    return <div className="min-h-screen p-8 text-sm text-muted-foreground">正在验证管理员身份...</div>;
  }

  return <>{children}</>;
}
