import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AdminUser } from './types';

interface AdminAuthState {
  admin: AdminUser | null;
  token: string | null;
  isAuthenticated: boolean;
  setAuth: (token: string, admin: AdminUser) => void;
  setAdmin: (admin: AdminUser) => void;
  logout: () => void;
}

export const useAdminAuthStore = create<AdminAuthState>()(
  persist(
    set => ({
      admin: null,
      token: null,
      isAuthenticated: false,
      setAuth: (token, admin) => {
        localStorage.setItem('adminToken', token);
        set({ token, admin, isAuthenticated: true });
      },
      setAdmin: admin => set({ admin }),
      logout: () => {
        localStorage.removeItem('adminToken');
        set({ token: null, admin: null, isAuthenticated: false });
      },
    }),
    {
      name: 'platform-admin-auth',
      partialize: state => ({
        token: state.token,
        admin: state.admin,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
