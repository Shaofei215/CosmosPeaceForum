/**
 * 公开平台认证状态管理。
 *
 * Zustand 只持久化用户资料；access/refresh token 由 tokenStorage 按 remember_me
 * 分别写入 sessionStorage 或 localStorage，避免默认登录被误持久化。
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, AuthState } from '../types';
import { clearTokens, getAccessToken, setTokens } from '../tokenStorage';

interface AuthStore extends AuthState {
  setAuth: (token: string, user: User, refreshToken?: string, rememberMe?: boolean) => void;
  updateUser: (updates: Partial<User>) => void;
  logout: () => void;
  setLoading: (loading: boolean) => void;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    set => ({
      user: null,
      token: getAccessToken(),
      isAuthenticated: Boolean(getAccessToken()),
      isLoading: false,

      /** 保存认证状态；只有传入 refreshToken 时才重写浏览器 token 存储位置。 */
      setAuth: (token: string, user: User, refreshToken?: string, rememberMe = false) => {
        if (refreshToken) {
          setTokens(token, refreshToken, rememberMe);
        }
        set({
          token,
          user,
          isAuthenticated: true,
          isLoading: false,
        });
      },

      updateUser: updates => {
        set(state => ({ user: state.user ? { ...state.user, ...updates } : null }));
      },

      logout: () => {
        clearTokens();
        set({
          token: null,
          user: null,
          isAuthenticated: false,
          isLoading: false,
        });
      },

      setLoading: (loading: boolean) => {
        set({ isLoading: loading });
      },
    }),
    {
      name: 'auth-storage',
      partialize: state => ({
        user: state.user,
      }),
      // 重新加载页面时以 tokenStorage 为准；没有 token 就不恢复旧用户。
      merge: (persisted, current) => {
        const token = getAccessToken();
        const persistedState = persisted as Partial<AuthStore> | undefined;
        return {
          ...current,
          user: token ? (persistedState?.user ?? null) : null,
          token,
          isAuthenticated: Boolean(token),
        };
      },
    }
  )
);
