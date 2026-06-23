/**
 * 应用入口文件
 * 初始化React应用并挂载到DOM
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { router } from './router';
import { Providers } from './providers';
import { PLATFORM_DISPLAY_NAME } from '@/shared/config/branding';
import './styles/globals.css';

document.title = PLATFORM_DISPLAY_NAME;

/**
 * 渲染React应用
 */
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Providers>
      <RouterProvider router={router} />
    </Providers>
  </React.StrictMode>
);
