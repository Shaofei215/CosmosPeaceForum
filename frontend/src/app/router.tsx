/**
 * 路由配置
 * 定义应用的所有路由
 */

import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AuthGuard } from '@/features/auth';
import { RootLayout } from '@/widgets/layout';

// 页面组件
import LoginPage from '@/pages/auth/LoginPage';
import RegisterPage from '@/pages/auth/RegisterPage';
import ProfileSetupPage from '@/pages/auth/ProfileSetupPage';
import ForgotPasswordPage from '@/pages/auth/ForgotPasswordPage';
import ResetPasswordPage from '@/pages/auth/ResetPasswordPage';
import FeedPage from '@/pages/feed/FeedPage';
import PostDetailPage from '@/pages/post/PostDetailPage';
import ProfilePage from '@/pages/profile/ProfilePage';
import FollowingListPage from '@/pages/profile/FollowingListPage';
import FollowersListPage from '@/pages/profile/FollowersListPage';

/**
 * 应用路由配置
 */
export const router = createBrowserRouter([
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

      // 认证路由
      { path: 'login', element: <LoginPage /> },
      { path: 'register', element: <RegisterPage /> },
      { path: 'profile-setup', element: <ProfileSetupPage /> },
      { path: 'forgot-password', element: <ForgotPasswordPage /> },
      { path: 'reset-password', element: <ResetPasswordPage /> },

      // 受保护路由（需要登录）
      {
        element: <AuthGuard />,
        children: [
          // 这里可以添加需要登录才能访问的页面
        ],
      },
    ],
  },
  // 404页面
  { path: '*', element: <div className="p-8 text-center">页面不存在</div> },
]);
