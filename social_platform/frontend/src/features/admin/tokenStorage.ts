/**
 * 平台管理员 token 存储工具。
 *
 * 未勾选 remember me 时使用 sessionStorage，勾选后使用 localStorage。
 * 管理员 access/refresh token 使用独立 key，避免和普通用户会话互相覆盖。
 */

const ACCESS_TOKEN_KEY = 'adminToken';
const REFRESH_TOKEN_KEY = 'adminRefreshToken';

/** 根据 remember_me 选择本次管理员会话的浏览器存储位置。 */
function getStorage(rememberMe: boolean): Storage {
  return rememberMe ? localStorage : sessionStorage;
}

/** 读取当前平台管理员 access token，优先 sessionStorage 以匹配默认不记住策略。 */
export function getAdminAccessToken(): string | null {
  return sessionStorage.getItem(ACCESS_TOKEN_KEY) || localStorage.getItem(ACCESS_TOKEN_KEY);
}

/** 读取当前平台管理员 refresh token，用于 401 后自动换取新的 token 对。 */
export function getAdminRefreshToken(): string | null {
  return sessionStorage.getItem(REFRESH_TOKEN_KEY) || localStorage.getItem(REFRESH_TOKEN_KEY);
}

/** 判断当前平台管理员 token 对是否存放在 localStorage 中。 */
export function isAdminRememberedSession(): boolean {
  return !!localStorage.getItem(REFRESH_TOKEN_KEY);
}

/** 写入一组新的平台管理员 access/refresh token，并清理另一种 storage 中的旧 token。 */
export function setAdminTokens(
  accessToken: string,
  refreshToken: string,
  rememberMe: boolean
): void {
  clearAdminTokens();
  const storage = getStorage(rememberMe);
  storage.setItem(ACCESS_TOKEN_KEY, accessToken);
  storage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

/** refresh 成功后沿用原 remember_me 位置写入轮换后的平台管理员 token 对。 */
export function updateAdminTokens(accessToken: string, refreshToken: string): void {
  setAdminTokens(accessToken, refreshToken, isAdminRememberedSession());
}

/** 清除所有可能位置上的平台管理员 token，本地登出和 refresh 失败都会调用。 */
export function clearAdminTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  sessionStorage.removeItem(REFRESH_TOKEN_KEY);
}
