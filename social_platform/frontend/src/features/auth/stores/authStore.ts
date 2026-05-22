/**
 * 认证状态管理
 * 使用Zustand管理认证状态
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, AuthState } from '../types';

/**
 * 认证状态存储
 */
interface AuthStore extends AuthState {
  /**
   * 设置认证信息
   *
   * @param token - 访问令牌
   * @param user - 用户信息
   */
  setAuth: (token: string, user: User) => void;

  /**
   * 清除认证信息（登出）
   */
  logout: () => void;

  /**
   * 设置加载状态
   *
   * @param loading - 是否加载中
   */
  setLoading: (loading: boolean) => void;
}

/**
 * 创建认证状态存储
 */
export const useAuthStore = create<AuthStore>()(
  persist(
    set => ({
      // 初始状态
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,

      /**
       * 设置认证信息
       */
      setAuth: (token: string, user: User) => {
        localStorage.setItem('token', token);
        set({
          token,
          user,
          isAuthenticated: true,
          isLoading: false,
        });
      },

      /**
       * 清除认证信息
       */
      logout: () => {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        set({
          token: null,
          user: null,
          isAuthenticated: false,
          isLoading: false,
        });
      },

      /**
       * 设置加载状态
       */
      setLoading: (loading: boolean) => {
        set({ isLoading: loading });
      },
    }),
    {
      name: 'auth-storage',
      partialize: state => ({
        token: state.token,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
