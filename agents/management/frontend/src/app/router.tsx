import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom';
import { AuthGuard } from '@/features/auth';
import { AppLayout } from '@/widgets/layout/AppLayout';

import LoginPage from '@/pages/LoginPage';
import SetupPage from '@/pages/SetupPage';
import DashboardPage from '@/pages/DashboardPage';
import AdminListPage from '@/pages/AdminListPage';
import AgentListPage from '@/pages/AgentListPage';
import AgentCreatePage from '@/pages/AgentCreatePage';
import AgentDetailPage from '@/pages/AgentDetailPage';
import AgentEditPage from '@/pages/AgentEditPage';
import ModelListPage from '@/pages/ModelListPage';
import MemoryListPage from '@/pages/MemoryListPage';
import MemoryDetailPage from '@/pages/MemoryDetailPage';
import SystemConfigPage from '@/pages/SystemConfigPage';
import PromptConfigPage from '@/pages/PromptConfigPage';
import LogPage from '@/pages/LogPage';
import ErrorPage from '@/pages/ErrorPage';
import RouteErrorPage from '@/pages/RouteErrorPage';

export const router = createBrowserRouter([
  {
    element: <Outlet />,
    errorElement: <RouteErrorPage />,
    children: [
      {
        path: '/login',
        element: <LoginPage />,
      },
      {
        path: '/setup',
        element: (
          <AuthGuard>
            <SetupPage />
          </AuthGuard>
        ),
      },
      {
        path: '/',
        element: (
          <AuthGuard>
            <AppLayout />
          </AuthGuard>
        ),
        children: [
          { index: true, element: <Navigate to="/dashboard" replace /> },
          { path: 'dashboard', element: <DashboardPage /> },
          { path: 'agents', element: <AgentListPage /> },
          { path: 'agents/new', element: <AgentCreatePage /> },
          { path: 'agents/:id', element: <AgentDetailPage /> },
          { path: 'agents/:id/edit', element: <AgentEditPage /> },
          { path: 'models', element: <ModelListPage /> },
          { path: 'memories', element: <MemoryListPage /> },
          { path: 'memories/:agentId', element: <MemoryDetailPage /> },
          { path: 'prompts', element: <PromptConfigPage /> },
          { path: 'system', element: <SystemConfigPage /> },
          { path: 'admins', element: <AdminListPage /> },
          { path: 'logs', element: <LogPage /> },
        ],
      },
      { path: '*', element: <ErrorPage /> },
    ],
  },
]);
