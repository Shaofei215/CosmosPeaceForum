import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { router } from './router';
import { Providers } from './providers';
import { MANAGEMENT_DOCUMENT_TITLE } from '@/shared/config/branding';
import './styles/globals.css';

document.title = MANAGEMENT_DOCUMENT_TITLE;

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Providers>
      <RouterProvider router={router} />
    </Providers>
  </React.StrictMode>
);
