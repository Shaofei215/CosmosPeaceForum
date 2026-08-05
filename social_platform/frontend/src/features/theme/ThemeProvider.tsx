import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { ThemeContext } from './ThemeContext';
import {
  SYSTEM_THEME_QUERY,
  THEME_STORAGE_KEY,
  applyTheme,
  getNextThemeMode,
  parseThemeMode,
  resolveTheme,
  type ThemeMode,
} from './theme';

/** 安全读取本地主题偏好，存储不可用时回退为跟随系统。 */
function readStoredTheme(): ThemeMode {
  try {
    return parseThemeMode(window.localStorage.getItem(THEME_STORAGE_KEY));
  } catch {
    return 'system';
  }
}

/** 安全写入本地主题偏好，隐私模式下存储失败不阻断切换。 */
function writeStoredTheme(mode: ThemeMode): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, mode);
  } catch {
    // 浏览器拒绝本地存储时仍保留当前页面内的主题状态。
  }
}

/** 为公开平台和平台管理后台提供统一主题状态。 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ThemeMode>(readStoredTheme);
  const [systemPrefersDark, setSystemPrefersDark] = useState(
    () => window.matchMedia(SYSTEM_THEME_QUERY).matches
  );
  const resolvedTheme = resolveTheme(mode, systemPrefersDark);

  useEffect(() => {
    const mediaQuery = window.matchMedia(SYSTEM_THEME_QUERY);
    const handleChange = (event: MediaQueryListEvent) => setSystemPrefersDark(event.matches);

    setSystemPrefersDark(mediaQuery.matches);
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  useEffect(() => {
    const handleStorage = (event: StorageEvent) => {
      if (event.key === THEME_STORAGE_KEY || event.key === null) {
        setMode(parseThemeMode(event.newValue));
      }
    };

    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  useEffect(() => {
    applyTheme(document.documentElement, resolvedTheme);
  }, [resolvedTheme]);

  const cycleTheme = useCallback(() => {
    setMode(currentMode => {
      const nextMode = getNextThemeMode(currentMode);
      writeStoredTheme(nextMode);
      return nextMode;
    });
  }, []);

  const value = useMemo(
    () => ({ mode, resolvedTheme, cycleTheme }),
    [cycleTheme, mode, resolvedTheme]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
