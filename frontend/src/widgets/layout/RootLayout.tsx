/**
 * 根布局组件
 * 提供应用的通用布局结构
 */

import { Outlet } from 'react-router-dom';
import { Header } from './Header';

/**
 * 根布局组件
 */
export function RootLayout() {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="container mx-auto px-4 py-6 max-w-3xl">
        <Outlet />
      </main>
    </div>
  );
}
