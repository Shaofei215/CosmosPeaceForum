/**
 * Management 管理端认证状态。
 *
 * tokenStorage 按 remember_me 决定 sessionStorage/localStorage；Zustand persist
 * 只保存管理员资料，避免默认短会话被误持久化。
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AuthUser } from '../types';
import { clearTokens, getAccessToken, setTokens } from '../tokenStorage';

interface AuthStore {
  user: AuthUser | null;
  isAuthenticated: boolean;
  setAuth: (token: string, user: AuthUser, refreshToken?: string, rememberMe?: boolean) => void;
  setUser: (user: AuthUser) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: Boolean(getAccessToken()),

      /** 保存认证状态；只有登录/刷新入口传入 refreshToken 时才重写 tokenStorage。 */
      setAuth: (token: string, user: AuthUser, refreshToken?: string, rememberMe = false) => {
        if (refreshToken) {
          setTokens(token, refreshToken, rememberMe);
        }
        set({
          user,
          isAuthenticated: true,
        });
      },

      setUser: (user: AuthUser) => {
        set({ user });
      },

      logout: () => {
        clearTokens();
        set({
          user: null,
          isAuthenticated: false,
        });
      },
    }),
    {
      name: 'management-auth-storage',
      partialize: (state) => ({
        user: state.user,
      }),
      // 重新加载页面时以 tokenStorage 为准，没有 token 就不恢复旧用户。
      merge: (persisted, current) => {
        const token = getAccessToken();
        const persistedState = persisted as Partial<AuthStore> | undefined;
        return {
          ...current,
          user: token ? persistedState?.user ?? null : null,
          isAuthenticated: Boolean(token),
        };
      },
    }
  )
);
