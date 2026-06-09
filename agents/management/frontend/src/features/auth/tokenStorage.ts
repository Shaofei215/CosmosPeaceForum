/**
 * Token 存储工具。
 *
 * 未勾选 remember me 时使用 sessionStorage，勾选后使用 localStorage。
 * access 与 refresh 必须放在同一种 storage 中，避免刷新后跨生命周期混用。
 */

const ACCESS_TOKEN_KEY = 'token';
const REFRESH_TOKEN_KEY = 'refreshToken';

/** 根据 remember_me 选择本次会话的浏览器存储位置。 */
function getStorage(rememberMe: boolean): Storage {
  return rememberMe ? localStorage : sessionStorage;
}

/** 读取当前可用 access token，优先 sessionStorage 以匹配默认不记住策略。 */
export function getAccessToken(): string | null {
  return sessionStorage.getItem(ACCESS_TOKEN_KEY) || localStorage.getItem(ACCESS_TOKEN_KEY);
}

/** 读取当前 refresh token，用于 401 后自动换取新的 token 对。 */
export function getRefreshToken(): string | null {
  return sessionStorage.getItem(REFRESH_TOKEN_KEY) || localStorage.getItem(REFRESH_TOKEN_KEY);
}

/** 判断当前 token 对是否存放在 localStorage 中。 */
export function isRememberedSession(): boolean {
  return !!localStorage.getItem(REFRESH_TOKEN_KEY);
}

/** 写入一组新的 access/refresh token，并先清理另一种 storage 中的旧 token。 */
export function setTokens(accessToken: string, refreshToken: string, rememberMe: boolean): void {
  clearTokens();
  const storage = getStorage(rememberMe);
  storage.setItem(ACCESS_TOKEN_KEY, accessToken);
  storage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

/** refresh 成功后沿用原 remember_me 位置写入轮换后的 token 对。 */
export function updateTokens(accessToken: string, refreshToken: string): void {
  setTokens(accessToken, refreshToken, isRememberedSession());
}

/** 清除所有可能位置上的 token，本地登出和 refresh 失败都会调用。 */
export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  sessionStorage.removeItem(REFRESH_TOKEN_KEY);
}
