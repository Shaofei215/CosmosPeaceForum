import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AuthGuard } from '@/features/auth';
import { AppLayout } from '@/widgets/layout/AppLayout';

import LoginPage from '@/pages/LoginPage';
import DashboardPage from '@/pages/DashboardPage';
import AgentListPage from '@/pages/AgentListPage';
import AgentCreatePage from '@/pages/AgentCreatePage';
import AgentDetailPage from '@/pages/AgentDetailPage';
import AgentEditPage from '@/pages/AgentEditPage';
import ModelListPage from '@/pages/ModelListPage';
import SystemConfigPage from '@/pages/SystemConfigPage';
import LogPage from '@/pages/LogPage';

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
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
      { path: 'system', element: <SystemConfigPage /> },
      { path: 'logs', element: <LogPage /> },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
]);
