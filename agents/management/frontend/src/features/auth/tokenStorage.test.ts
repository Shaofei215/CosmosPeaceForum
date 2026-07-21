// @vitest-environment jsdom

import { beforeEach, describe, expect, it } from 'vitest';

import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  isRememberedSession,
  setTokens,
  updateTokens,
} from './tokenStorage';

describe('tokenStorage', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it('默认把 token 对保存在当前浏览器会话中', () => {
    setTokens('session-access', 'session-refresh', false);

    expect(getAccessToken()).toBe('session-access');
    expect(getRefreshToken()).toBe('session-refresh');
    expect(isRememberedSession()).toBe(false);
    expect(localStorage).toHaveLength(0);
  });

  it('记住登录时把 access 与 refresh token 一起持久化', () => {
    setTokens('local-access', 'local-refresh', true);

    expect(getAccessToken()).toBe('local-access');
    expect(getRefreshToken()).toBe('local-refresh');
    expect(isRememberedSession()).toBe(true);
    expect(sessionStorage).toHaveLength(0);
  });

  it('轮换 token 时沿用原来的持久化策略', () => {
    setTokens('old-access', 'old-refresh', true);

    updateTokens('new-access', 'new-refresh');

    expect(localStorage.getItem('token')).toBe('new-access');
    expect(localStorage.getItem('refreshToken')).toBe('new-refresh');
    expect(sessionStorage).toHaveLength(0);
  });

  it('登出时同时清理两种 storage 中的残留 token', () => {
    localStorage.setItem('token', 'local-access');
    localStorage.setItem('refreshToken', 'local-refresh');
    sessionStorage.setItem('token', 'session-access');
    sessionStorage.setItem('refreshToken', 'session-refresh');

    clearTokens();

    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
    expect(localStorage).toHaveLength(0);
    expect(sessionStorage).toHaveLength(0);
  });
});
