/**
 * 路由配置
 * 定义应用的所有路由
 */

import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AuthGuard } from '@/features/auth';
import { AdminAuthGuard } from '@/features/admin/AdminAuthGuard';
import { RootLayout } from '@/widgets/layout';
import { AdminLayout } from '@/widgets/admin-layout';

// 页面组件
import LoginPage from '@/pages/auth/LoginPage';
import ManagementLoginPage from '@/pages/auth/ManagementLoginPage';
import RegisterPage from '@/pages/auth/RegisterPage';
import ProfileSetupPage from '@/pages/auth/ProfileSetupPage';
import ForgotPasswordPage from '@/pages/auth/ForgotPasswordPage';
import ResetPasswordPage from '@/pages/auth/ResetPasswordPage';
import FeedPage from '@/pages/feed/FeedPage';
import PostDetailPage from '@/pages/post/PostDetailPage';
import ProfilePage from '@/pages/profile/ProfilePage';
import FollowingListPage from '@/pages/profile/FollowingListPage';
import FollowersListPage from '@/pages/profile/FollowersListPage';
import NotificationsPage from '@/pages/notification/NotificationsPage';
import ArticleEditorPage from '@/pages/article/ArticleEditorPage';
import SearchPage from '@/pages/search/SearchPage';
import HotTopicsPage from '@/pages/hot/HotTopicsPage';
import LegalDocumentPage from '@/pages/legal/LegalDocumentPage';
import ExternalRedirectPage from '@/pages/external/ExternalRedirectPage';
import AgentAccessPage from '@/pages/agent-access/AgentAccessPage';
import AdminLoginPage from '@/pages/admin/AdminLoginPage';
import AdminSetupPage from '@/pages/admin/AdminSetupPage';
import AdminDashboardPage from '@/pages/admin/AdminDashboardPage';
import AdminUsersPage from '@/pages/admin/AdminUsersPage';
import AdminContentPage from '@/pages/admin/AdminContentPage';
import AdminHotTopicsPage from '@/pages/admin/AdminHotTopicsPage';
import AdminAdminsPage from '@/pages/admin/AdminAdminsPage';
import AdminLogsPage from '@/pages/admin/AdminLogsPage';
import ErrorPage from '@/pages/error/ErrorPage';

/**
 * 应用路由配置
 */
export const router = createBrowserRouter([
  {
    path: '/external-redirect',
    element: <ExternalRedirectPage />,
  },
  {
    path: '/admin/login',
    element: <AdminLoginPage />,
  },
  {
    path: '/admin',
    element: <AdminAuthGuard />,
    children: [
      { path: 'setup', element: <AdminSetupPage /> },
      {
        element: <AdminLayout />,
        children: [
          { index: true, element: <Navigate to="/admin/dashboard" replace /> },
          { path: 'dashboard', element: <AdminDashboardPage /> },
          { path: 'users', element: <AdminUsersPage /> },
          { path: 'content', element: <AdminContentPage /> },
          { path: 'hot-topics', element: <AdminHotTopicsPage /> },
          { path: 'admins', element: <AdminAdminsPage /> },
          { path: 'logs', element: <AdminLogsPage /> },
        ],
      },
    ],
  },
  {
    path: '/',
    element: <RootLayout />,
    children: [
      // 默认重定向到信息流
      { index: true, element: <Navigate to="/feed" replace /> },

      // 公开路由
      { path: 'feed', element: <FeedPage /> },
      { path: 'post/:postId', element: <PostDetailPage /> },
      { path: 'user/:userId', element: <ProfilePage /> },
      { path: 'user/:userId/following', element: <FollowingListPage /> },
      { path: 'user/:userId/followers', element: <FollowersListPage /> },
      { path: 'search', element: <SearchPage /> },
      { path: 'hot', element: <HotTopicsPage /> },
      { path: 'agent-access', element: <AgentAccessPage /> },
      { path: 'legal/:documentSlug', element: <LegalDocumentPage /> },

      // 认证路由
      { path: 'login', element: <LoginPage /> },
      { path: 'management-login', element: <ManagementLoginPage /> },
      { path: 'register', element: <RegisterPage /> },
      { path: 'profile-setup', element: <ProfileSetupPage /> },
      { path: 'forgot-password', element: <ForgotPasswordPage /> },
      { path: 'reset-password', element: <ResetPasswordPage /> },

      // 受保护路由（需要登录）
      {
        element: <AuthGuard />,
        children: [
          { path: 'notifications', element: <NotificationsPage /> },
          { path: 'article/new', element: <ArticleEditorPage /> },
        ],
      },
    ],
  },
  // 404页面
  { path: '*', element: <ErrorPage /> },
]);
