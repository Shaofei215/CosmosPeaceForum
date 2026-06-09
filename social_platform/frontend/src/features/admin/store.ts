/**
 * 平台内管理员认证状态。
 *
 * 管理员 token 使用独立 tokenStorage key；persist 只保存管理员资料，
 * 避免短会话 token 被 Zustand 写入长期 localStorage。
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AdminUser } from './types';
import { clearAdminTokens, getAdminAccessToken, setAdminTokens } from './tokenStorage';

interface AdminAuthState {
  admin: AdminUser | null;
  token: string | null;
  isAuthenticated: boolean;
  setAuth: (token: string, admin: AdminUser, refreshToken?: string, rememberMe?: boolean) => void;
  setAdmin: (admin: AdminUser) => void;
  logout: () => void;
}

export const useAdminAuthStore = create<AdminAuthState>()(
  persist(
    set => ({
      admin: null,
      token: getAdminAccessToken(),
      isAuthenticated: Boolean(getAdminAccessToken()),
      /** 保存管理员认证状态；传入 refreshToken 时同步 tokenStorage 生命周期。 */
      setAuth: (token, admin, refreshToken, rememberMe = false) => {
        if (refreshToken) {
          setAdminTokens(token, refreshToken, rememberMe);
        }
        set({ token, admin, isAuthenticated: true });
      },
      setAdmin: admin => set({ admin }),
      logout: () => {
        clearAdminTokens();
        set({ token: null, admin: null, isAuthenticated: false });
      },
    }),
    {
      name: 'platform-admin-auth',
      partialize: state => ({
        admin: state.admin,
      }),
      // 页面重载时以 admin tokenStorage 为准，没有 token 就丢弃旧管理员资料。
      merge: (persisted, current) => {
        const token = getAdminAccessToken();
        const persistedState = persisted as Partial<AdminAuthState> | undefined;
        return {
          ...current,
          admin: token ? (persistedState?.admin ?? null) : null,
          token,
          isAuthenticated: Boolean(token),
        };
      },
    }
  )
);
