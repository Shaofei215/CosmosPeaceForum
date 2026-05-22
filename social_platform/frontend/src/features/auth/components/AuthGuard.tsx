/**
 * 认证守卫组件
 * 保护需要登录才能访问的路由
 */

import { Navigate, useLocation, Outlet } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';

/**
 * 认证守卫组件
 * 如果用户未登录，重定向到登录页面
 */
export function AuthGuard() {
  const { isAuthenticated } = useAuthStore();
  const location = useLocation();

  // 如果未认证，重定向到登录页，并保存当前路径
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // 已认证，渲染子路由
  return <Outlet />;
}
